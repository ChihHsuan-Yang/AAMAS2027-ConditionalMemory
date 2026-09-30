#!/usr/bin/env python3
"""R3: the paired three-representation analysis. Contribution B + Figure 2.

The five questions this experiment exists to answer:

  1. Does compression preserve downstream usefulness?  -> paired dU per
     representation, ON THE SAME CELLS.
  2. Utility per 1k exposed tokens, per representation -> the frontier's y/x.
  3. Does summary or structured create harm raw does not? -> COUNTS, with the
     both-arms-fail denominator beside them (docs/ZERO_CONTRIBUTORS.md).
  4. Faithfulness, with what the proxies can and cannot catch.
  5. A1.5: charging formation cost must move summary/structured and leave RAW
     EXACTLY UNCHANGED. If raw moves at all the cost attribution is wrong.

THE JOIN, and why it is not ``memory_id``
------------------------------------------
``memory_id`` is a content hash over ``memory_text`` AND
``memory_representation`` (schema.MEMORY_ID_KEYS), so it necessarily DIFFERS
between arms -- that is the schema working correctly, since a summary of a
segment is not the same memory as the segment. Joining on it would match ZERO
rows across arms and print a well-formed table of nothing. The arms are joined
on ``(memory_unit_locator, future_task_id)``, carried on every row as
``provenance.pair_key``, and the join is asserted 1:1 and COMPLETE before any
number is computed.

No estimator is reimplemented. Cell statistics, labels and the bootstrap come
from ``p1mem.analysis``; the efficiency numbers from
``p1mem.analysis.efficiency``.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from p1mem.analysis import efficiency as EF  # noqa: E402
from p1mem.analysis import labels as lb  # noqa: E402
from p1mem.analysis import noise as nz  # noqa: E402
from p1mem.analysis.common import jsonable, wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

REPS = ("raw", "summary", "structured")
STRATA = ("BEARING", "MATCHED_CONTROL")


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def f4(x) -> str:
    return "—" if x is None else f"{x:.4f}"


def pair_key(r: dict) -> str:
    p = r.get("provenance") or {}
    # RAW rows predate pair_key: derive it from the locator the screened run
    # DID record, in source_episode_metadata. Raising rather than defaulting is
    # the point -- a .get(default) here would silently drop rows from one arm
    # and the paired test would run on a smaller, self-selected set.
    loc = p.get("memory_unit_locator")
    if loc is None:
        loc = (r.get("source_episode_metadata") or {}).get("memory_unit_locator")
    if loc is None:
        raise KeyError(
            f"row {r.get('row_id')} carries no memory_unit_locator in either "
            f"provenance or source_episode_metadata; it cannot be paired and "
            f"defaulting it would silently shrink the paired set")
    return f"{loc}|{r['future_task_id']}"


def bootstrap_paired(diffs: list[float], *, n_boot: int = 10000,
                     seed: int = 20260930) -> dict:
    """Percentile bootstrap of a mean paired difference over its units."""
    arr = np.asarray(diffs, dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": None, "ci_lower": None, "ci_upper": None,
                "p_two_sided": None}
    if arr.size == 1:
        return {"n": 1, "mean": float(arr[0]), "ci_lower": None,
                "ci_upper": None, "p_two_sided": None}
    rng = np.random.default_rng(seed)
    draws = arr[rng.integers(0, arr.size, size=(n_boot, arr.size))].mean(axis=1)
    lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    p = min(1.0, 2.0 * min(float((draws <= 0).mean()), float((draws >= 0).mean())))
    return {"n": int(arr.size), "mean": float(arr.mean()), "ci_lower": lo,
            "ci_upper": hi, "p_two_sided": p,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def cluster_bootstrap_paired(units: dict[Any, list[float]], *, n_boot: int = 10000,
                             seed: int = 20260930) -> dict:
    """Bootstrap resampling whole CLUSTERS (tasks or episodes), not rows.

    docs/CONTRAST_FRAMING.md: a third of all cells sit on ten tasks, so a
    cell-level interval treats repeated views of one task as independent draws.
    """
    keys = sorted(units, key=str)
    if not keys:
        return {"n_clusters": 0, "mean": None, "ci_lower": None, "ci_upper": None}
    flat = [v for k in keys for v in units[k]]
    point = float(np.mean(flat)) if flat else None
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        pick = [keys[i] for i in rng.integers(0, len(keys), size=len(keys))]
        vals = [v for k in pick for v in units[k]]
        if vals:
            draws.append(float(np.mean(vals)))
    if not draws:
        return {"n_clusters": len(keys), "mean": point, "ci_lower": None,
                "ci_upper": None}
    lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    return {"n_clusters": len(keys), "n_obs": len(flat), "mean": point,
            "ci_lower": lo, "ci_upper": hi,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-cells", type=Path,
                    default=REPO / "results/deltau_screened/cells.jsonl")
    ap.add_argument("--new-cells", type=Path,
                    default=REPO / "results/repr_scaleup/cells.jsonl")
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/repr_scaleup/analysis")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = {
        "_what": "R3 paired three-representation analysis on identical cells",
        "generated_at_utc": utc_now(),
    }

    # ---------------------------------------------------------------- load
    raw_all = load_jsonl(args.raw_cells)
    raw = [r for r in raw_all
           if (r.get("provenance") or {}).get("stratum") in STRATA]
    new = load_jsonl(args.new_cells)
    rows_by_rep: dict[str, list[dict]] = {"raw": raw}
    for r in new:
        rows_by_rep.setdefault(r["memory_representation"], []).append(r)
    log(f"loaded rows: { {k: len(v) for k, v in sorted(rows_by_rep.items())} }")

    # ------------------------------------------------- the join, ASSERTED
    # A join that matches half its rows still looks like success, so the
    # overlap is computed and required to be exactly the intersection before
    # any paired number is taken.
    cells_by_rep: dict[str, dict[str, list[dict]]] = {}
    for rep, rs in rows_by_rep.items():
        d: dict[str, list[dict]] = collections.defaultdict(list)
        for r in rs:
            d[pair_key(r)].append(r)
        cells_by_rep[rep] = dict(d)
    keysets = {rep: set(d) for rep, d in cells_by_rep.items()}
    common = set.intersection(*keysets.values())
    join = {
        "_what": "pair_key = (memory_unit_locator, future_task_id). memory_id is a "
                 "per-representation content hash and CANNOT join the arms.",
        "n_pair_keys_per_representation": {k: len(v) for k, v in sorted(keysets.items())},
        "n_common_to_all_three": len(common),
        "only_in": {rep: sorted(keysets[rep] - common)[:10]
                    for rep in sorted(keysets) if keysets[rep] - common},
        "n_only_in": {rep: len(keysets[rep] - common) for rep in sorted(keysets)},
        "replicates_per_pair_key": {
            rep: dict(collections.Counter(len(v) for v in d.values()))
            for rep, d in sorted(cells_by_rep.items())},
    }
    if not common:
        raise SystemExit("the three arms share ZERO pair keys; the join is broken")
    for rep, d in cells_by_rep.items():
        dup = {k: len(v) for k, v in d.items()
               if len({r["replicate_id"] for r in v}) != len(v)}
        if dup:
            raise SystemExit(f"{rep}: {len(dup)} pair keys have duplicate replicate ids")
    out["join"] = join
    log(f"join: {len(common)} pair keys common to all three "
        f"(per-arm {join['n_pair_keys_per_representation']})")

    # --------------------------------------------- cell statistics + floors
    # F_exec on the dU scale (Amendment A1.2), per representation, with the
    # positive control that it CAN return non-zero.
    floors: dict[str, Any] = {}
    for rep, rs in sorted(rows_by_rep.items()):
        est = nz.exec_floor(rs, scale="delta", n_boot=2000, allow_pooling=True)
        floors[rep] = {"point": est.point, "ci_lower": est.ci_lower,
                       "ci_upper": est.ci_upper, "n_units": est.n_units,
                       "flags": list(est.flags), "scale": est.scale}
    # POSITIVE CONTROL: a floor of 0.000 from an estimator never shown to
    # return non-zero is not a measurement.
    import copy
    import random as _rnd
    mut = copy.deepcopy(rows_by_rep["summary"])
    rng = _rnd.Random(7)
    n_pert, seen = 0, set()
    for r in mut:
        if r.get("error_code_if_any") or r.get("delta_utility") is None:
            continue
        if r.get("replicate_id") == 1 and r["cell_id"] not in seen and rng.random() < 0.5:
            seen.add(r["cell_id"])
            r["reward_with_memory"] = 1.0 - float(r["reward_with_memory"])
            r["delta_utility"] = r["reward_with_memory"] - r["reward_without_memory"]
            n_pert += 1
    pc = nz.exec_floor(mut, scale="delta", n_boot=2000, allow_pooling=True)
    floors["_positive_control"] = {
        "_what": f"F_exec after flipping one replicate in {n_pert} summary cells; "
                 f"MUST be > 0 or a 0.000 floor proves nothing",
        "n_cells_perturbed": n_pert, "point": pc.point,
        "fires": bool(pc.point is not None and pc.point > 0)}
    out["noise_floors_delta_scale"] = floors
    log(f"F_exec[delta]: "
        f"{ {k: f4(v['point']) for k, v in floors.items() if k != '_positive_control'} }"
        f"  positive control fires={floors['_positive_control']['fires']}")

    stats: dict[str, dict[str, lb.CellStat]] = {}
    for rep, rs in rows_by_rep.items():
        f = floors[rep]["point"]
        cs = lb.cell_statistics(rs, f, n_boot=args.n_boot, allow_pooling=True)
        by_key: dict[str, lb.CellStat] = {}
        cid2key = {}
        for r in rs:
            cid2key[r["cell_id"]] = pair_key(r)
        for c in cs:
            by_key[cid2key[c.cell_id]] = c
        stats[rep] = by_key

    # ======================================================= Q1: paired dU
    q1: dict[str, Any] = {
        "_what": "mean dU per representation, computed ONLY on the pair keys "
                 "common to all three arms, so the three numbers describe the "
                 "same memories against the same tasks.",
        "n_common_cells": len(common),
    }
    strat_of = {}
    task_of = {}
    ep_of = {}
    for k in common:
        r = cells_by_rep["raw"][k][0]
        strat_of[k] = (r.get("provenance") or {}).get("stratum")
        task_of[k] = r["future_task_id"]
        ep_of[k] = r["source_episode_id"]

    per_rep: dict[str, Any] = {}
    means: dict[str, dict[str, float]] = {}
    for rep in REPS:
        means[rep] = {k: stats[rep][k].mean_delta for k in common
                      if stats[rep][k].mean_delta is not None}
        vals = [means[rep][k] for k in sorted(means[rep])]
        entry = {"n_cells": len(vals), **bootstrap_paired(vals, n_boot=args.n_boot)}
        by_task = collections.defaultdict(list)
        for k in sorted(means[rep]):
            by_task[task_of[k]].append(means[rep][k])
        entry["task_clustered"] = cluster_bootstrap_paired(
            by_task, n_boot=args.n_boot)
        for st in STRATA:
            sv = [means[rep][k] for k in sorted(means[rep]) if strat_of[k] == st]
            entry[st] = {"n_cells": len(sv),
                         **bootstrap_paired(sv, n_boot=args.n_boot)}
        per_rep[rep] = entry
    q1["mean_delta_utility"] = per_rep

    # --- the PAIRED contrast: each cell contributes rep - raw --------------
    contrasts: dict[str, Any] = {}
    for rep in ("summary", "structured"):
        keys = sorted(k for k in common
                      if k in means[rep] and k in means["raw"])
        diffs = [means[rep][k] - means["raw"][k] for k in keys]
        e = {"_definition": f"per cell: mean dU({rep}) - mean dU(raw), same "
                            f"memory, same task, same filler",
             "n_paired_cells": len(keys),
             **bootstrap_paired(diffs, n_boot=args.n_boot)}
        bt = collections.defaultdict(list)
        be = collections.defaultdict(list)
        for k, d in zip(keys, diffs):
            bt[task_of[k]].append(d)
            be[ep_of[k]].append(d)
        e["task_clustered"] = cluster_bootstrap_paired(bt, n_boot=args.n_boot)
        e["episode_clustered"] = cluster_bootstrap_paired(be, n_boot=args.n_boot)
        # ZERO CONTRIBUTORS (docs/ZERO_CONTRIBUTORS.md): a cell that fails in
        # both arms under both representations contributes an exact 0.0 and is
        # not a measurement of "no difference".
        nz_diffs = [d for d in diffs if d != 0.0]
        e["contributors"] = {
            "_rule": "docs/ZERO_CONTRIBUTORS.md: state the non-zero contributor "
                     "count beside the nominal denominator, and report both the "
                     "diluted and the conditional magnitude.",
            "n_nominal": len(diffs),
            "n_nonzero": len(nz_diffs),
            "diluted_mean_over_all_cells": float(np.mean(diffs)) if diffs else None,
            "conditional_mean_over_contributors":
                float(np.mean(nz_diffs)) if nz_diffs else None,
            "status": ("UNDERPOWERED" if len(nz_diffs) < 8 else "ADEQUATE_COUNT"),
        }
        for st in STRATA:
            sk = [k for k in keys if strat_of[k] == st]
            sd = [means[rep][k] - means["raw"][k] for k in sk]
            e[st] = {"n_paired_cells": len(sd),
                     **bootstrap_paired(sd, n_boot=args.n_boot),
                     "n_nonzero": sum(1 for d in sd if d != 0.0)}
        contrasts[f"{rep}_minus_raw"] = e
    # summary vs structured, same cells
    keys = sorted(k for k in common
                  if k in means["summary"] and k in means["structured"])
    d2 = [means["summary"][k] - means["structured"][k] for k in keys]
    contrasts["summary_minus_structured"] = {
        "n_paired_cells": len(keys), **bootstrap_paired(d2, n_boot=args.n_boot),
        "n_nonzero": sum(1 for d in d2 if d != 0.0)}
    q1["paired_contrasts"] = contrasts

    # --- TRUNCATION SPLIT: 7 of 60 summaries hit the token cap -------------
    trunc_locs = {rep: {m["memory_unit_locator"] for m in
                        (json.loads(l) for l in args.memories.read_text().splitlines()
                         if l.strip())
                        if m["representation"] == rep and m.get("truncated")}
                  for rep in ("summary", "structured")}
    tsplit = {}
    for rep in ("summary", "structured"):
        tl = trunc_locs[rep]
        for name, pred in (("write_completed", lambda k: k.split("|")[0] not in tl),
                           ("write_truncated", lambda k: k.split("|")[0] in tl)):
            ks = sorted(k for k in common if k in means[rep] and k in means["raw"]
                        and pred(k))
            dd = [means[rep][k] - means["raw"][k] for k in ks]
            tsplit[f"{rep}:{name}"] = {
                "n_memories": len({k.split('|')[0] for k in ks}),
                "n_paired_cells": len(dd), **bootstrap_paired(dd, n_boot=args.n_boot)}
    q1["truncation_split"] = {
        "_what": "DEFECT R-1: 7 of 60 summaries and 3 of 60 structured writes hit "
                 "max_tokens=512. ok=True does not mean the model finished. Split "
                 "so a reader can see whether truncation drives the result.",
        "n_truncated_memories": {k: len(v) for k, v in trunc_locs.items()},
        "by_group": tsplit}
    # --- SAME-SESSION sensitivity check (DEFECT R-2) -----------------------
    # The Raw arm was measured 2026-09-29 and the new arms 2026-09-30, and the
    # endpoint is deterministic within a session but not across them
    # (cross_session_probe.json: 6/6 same-minute repeats identical, 6/6
    # reproduce 09-30, 2/6 reproduce 09-29). r2b re-measured Raw's WITH arm on
    # 100 cells TODAY with the cache disabled. Pairing that against the
    # WITHOUT arm THIS run recorded -- whose context bytes are identical across
    # representations, verified 554/554 -- gives a Raw dU measured entirely
    # within one session, at zero extra endpoint cost.
    rs_path = args.new_cells.parent / "raw_resample.json"
    if rs_path.exists():
        rs = json.loads(rs_path.read_text())
        same: dict[str, float] = {}
        for c in rs["cells"]:
            k = f"{c['memory_unit_locator']}|{c['future_task_id']}"
            if k not in common:
                continue
            # WITHOUT from THIS session. Byte-identical across summary and
            # structured (554/554), so either is the same measurement.
            wo = [float(r["reward_without_memory"])
                  for r in cells_by_rep["summary"].get(k, [])
                  if r.get("reward_without_memory") is not None]
            if not wo:
                continue
            same[k] = float(c["now_reward"]) - float(np.mean(wo))
        ks = sorted(same)
        cross = {k: means["raw"][k] for k in ks if k in means["raw"]}
        ss = {
            "_what": "Raw dU computed ENTIRELY within the 2026-09-30 session: "
                     "WITH from r2b's cache-disabled re-measurement, WITHOUT from "
                     "this run. Compared against the cross-session Raw dU on the "
                     "SAME cells, so the two numbers describe the same objects.",
            "n_cells": len(ks),
            "same_session_raw_mean_dU": (float(np.mean([same[k] for k in ks]))
                                         if ks else None),
            "cross_session_raw_mean_dU_same_cells": (
                float(np.mean([cross[k] for k in sorted(cross)]))
                if cross else None),
            "n_cells_where_they_differ": sum(
                1 for k in ks if k in cross and same[k] != cross[k]),
        }
        for rep in ("summary", "structured"):
            kk = sorted(k for k in ks if k in means[rep])
            d_same = [means[rep][k] - same[k] for k in kk]
            d_cross = [means[rep][k] - cross[k] for k in kk if k in cross]
            ss[f"{rep}_minus_raw"] = {
                "n_paired_cells": len(d_same),
                "same_session": bootstrap_paired(d_same, n_boot=args.n_boot),
                "cross_session_same_cells": bootstrap_paired(
                    d_cross, n_boot=args.n_boot),
            }
        q1["same_session_sensitivity"] = ss

    out["Q1_paired_delta_utility"] = q1

    # ======================================= Q3: harm, as COUNTS not rates
    q3: dict[str, Any] = {
        "_what": "docs/ZERO_CONTRIBUTORS.md + the brief: report COUNTS with the "
                 "denominator they rest on. A rate over cells that cannot show an "
                 "effect understates by construction.",
    }
    label_counts = {}
    for rep in REPS:
        cs = [stats[rep][k] for k in sorted(common) if k in stats[rep]]
        c = collections.Counter(x.label for x in cs)
        naive_neg = sum(1 for x in cs if x.mean_delta is not None and x.mean_delta < 0)
        naive_pos = sum(1 for x in cs if x.mean_delta is not None and x.mean_delta > 0)
        naive_zero = sum(1 for x in cs if x.mean_delta == 0.0)
        # both arms fail = the cell could not show an effect in either direction
        baf = 0
        for k in sorted(common):
            rs = rows_by_rep[rep]
            pass
        label_counts[rep] = {
            "n_cells": len(cs),
            "labels": dict(c),
            "naive_sign_counts": {"positive": naive_pos, "zero": naive_zero,
                                  "negative": naive_neg},
        }
    # both-arms-fail, per representation, over the common cells
    for rep in REPS:
        n_baf = n_tot = 0
        for k in sorted(common):
            rs = cells_by_rep[rep][k]
            usable = [r for r in rs if r.get("reward_with_memory") is not None]
            if not usable:
                continue
            n_tot += 1
            if all(float(r["reward_with_memory"]) == 0.0
                   and float(r["reward_without_memory"]) == 0.0 for r in usable):
                n_baf += 1
        rate, lo, hi = wilson_ci(n_baf, n_tot)
        label_counts[rep]["both_arms_fail"] = {
            "_what": "every replicate scores 0 in BOTH arms: the cell cannot show "
                     "an effect in either direction, so it is a structural zero in "
                     "the paired test",
            "numerator": n_baf, "denominator": n_tot, "rate": rate,
            "wilson_ci": [lo, hi]}
    q3["per_representation"] = label_counts

    # harm that raw does not create: PAIRED, cell by cell
    harm = {}
    for rep in ("summary", "structured"):
        ks = sorted(k for k in common if k in means[rep] and k in means["raw"])
        worse = [k for k in ks if means[rep][k] < means["raw"][k]]
        better = [k for k in ks if means[rep][k] > means["raw"][k]]
        same = [k for k in ks if means[rep][k] == means["raw"][k]]
        # the sharp version: raw helped and this representation harmed
        new_harm = [k for k in ks if means["raw"][k] >= 0 > means[rep][k]]
        raw_harm_only = [k for k in ks if means[rep][k] >= 0 > means["raw"][k]]
        harm[rep] = {
            "n_cells": len(ks),
            "n_worse_than_raw": len(worse),
            "n_better_than_raw": len(better),
            "n_identical_to_raw": len(same),
            "n_NEW_harm_raw_did_not_create": len(new_harm),
            "_new_harm_definition": "mean dU(raw) >= 0 AND mean dU(rep) < 0 on the "
                                    "SAME memory and task",
            "new_harm_cells": sorted(new_harm)[:20],
            "n_harm_raw_created_that_this_did_not": len(raw_harm_only),
            "n_robust_harmful_label": sum(
                1 for k in ks if stats[rep][k].label == lb.ROBUST_HARMFUL),
            "n_robust_harmful_label_raw": sum(
                1 for k in ks if stats["raw"][k].label == lb.ROBUST_HARMFUL),
        }
    q3["new_harm_vs_raw_paired"] = harm
    out["Q3_harm_counts"] = q3

    # ==================================== Q2 + Q5: efficiency and A1.5 check
    eff: dict[str, Any] = {
        "_what": "utility per 1000 EXPOSED tokens, per representation, restricted "
                 "to the cells common to all three arms so the axis and the "
                 "numerator describe the same objects.",
    }
    per_tok = {}
    for rep in REPS:
        rs = [r for r in rows_by_rep[rep] if pair_key(r) in common]
        cs = [stats[rep][k] for k in sorted(common) if k in stats[rep]]
        wf = EF.utility_per_exposed_token(cs, rs, n_boot=2000,
                                          include_formation=True)
        eo = EF.utility_per_exposed_token(cs, rs, n_boot=2000,
                                          include_formation=False)
        fc = EF.formation_cost(rs)
        key = rep if rep in wf else list(wf)[0]
        per_tok[rep] = {
            "exposure_only": eo[key].to_dict(),
            "with_formation_charged": wf[key].to_dict(),
            "formation_cost": {k: v.to_dict() for k, v in fc.items()},
            "median_exposed_tokens": float(np.median(
                [r["memory_tokens_exposed"] for r in rs])),
            "total_exposed_tokens_over_cells": float(sum(
                stats[rep][k].extra.get("_", 0) or 0 for k in [])),
        }
    eff["per_representation"] = per_tok

    # A1.5 CORRECTNESS CHECK, stated as a pass/fail with its own tolerance.
    a15 = {}
    for rep in REPS:
        a = per_tok[rep]["exposure_only"]["point"]
        b = per_tok[rep]["with_formation_charged"]["point"]
        moved = (a is not None and b is not None and a != b)
        ratio = (a / b) if (a not in (None, 0) and b not in (None, 0)) else None
        a15[rep] = {"exposure_only": a, "with_formation": b,
                    "moved": bool(moved),
                    "abs_change": (None if a is None or b is None else abs(a - b)),
                    "ratio_exposure_over_charged": ratio}
    a15["_rule"] = (
        "Amendment A1.5: charging formation cost must move summary and structured "
        "and leave RAW EXACTLY UNCHANGED, because raw makes zero extraction calls. "
        "If raw moves at all, the cost attribution is wrong.")
    a15["VERDICT"] = (
        "PASS: raw bit-identical, model-written arms moved"
        if (not a15["raw"]["moved"]
            and a15["summary"]["moved"] and a15["structured"]["moved"])
        else "FAIL: see per-representation 'moved'")
    eff["A1_5_formation_cost_check"] = a15
    out["Q2_Q5_efficiency"] = eff

    # ======================================================= Q4 faithfulness
    mem = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    faith: dict[str, Any] = {
        "_what": "deterministic proxies only. A HIGH score is weak evidence; a LOW "
                 "score is strong evidence of a problem.",
        "_cannot_catch": [
            "recombination: correct entities wired into a false relation",
            "omission: a summary that drops the decisive fact scores 1.0",
            "unsupported inference that introduces no new token",
            "negation/modality in free prose",
            "faithful paraphrase that renames an entity is scored UNSUPPORTED",
        ],
    }
    for rep in ("summary", "structured"):
        items = [m for m in mem if m["representation"] == rep and m["faithfulness"]]
        def agg(sel):
            v = [m["faithfulness"][sel] for m in items
                 if m["faithfulness"].get(sel) is not None]
            return {"n": len(v), "mean": (float(np.mean(v)) if v else None),
                    "min": (float(min(v)) if v else None)}
        faith[rep] = {
            "n_memories_scored": len(items),
            "number_support": agg("number_support"),
            "entity_support": agg("entity_support"),
            "contradiction_rate": agg("contradiction_rate"),
            "contradiction_rate_excl_scope_collision":
                agg("contradiction_rate_excl_scope_collision"),
            "n_with_any_unsupported_number": sum(
                1 for m in items
                if (m["faithfulness"].get("number_support") or 1.0) < 1.0),
            "n_with_zero_unsupported_numbers": sum(
                1 for m in items
                if (m["faithfulness"].get("number_support")) == 1.0),
        }
    wsum = json.loads(
        (args.memories.parent / "write_summary.json").read_text())
    faith["controls"] = wsum["faithfulness_controls"]
    faith["malformed_structured"] = wsum["malformed_structured"]
    faith["truncation"] = wsum["truncation"]
    out["Q4_faithfulness"] = faith

    write_json_atomic(args.out / "r3_representation_analysis.json", jsonable(out))
    log(f"WROTE {args.out}/r3_representation_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

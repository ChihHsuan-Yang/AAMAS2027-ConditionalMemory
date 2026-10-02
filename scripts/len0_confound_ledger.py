#!/usr/bin/env python3
"""LEN0: re-derive §2 of the length-control precommitment, machine-readable.

``docs/LENGTH_CONTROL_PRECOMMITMENT.md`` §8 names
``results/ledgers/length_control_confound.json`` as "§2, machine-readable".
It did not exist. This script produces it, and in doing so RE-DERIVES every
number §2 states rather than transcribing them -- house rule: never quote a
number you have not re-derived.

That is not bookkeeping. §2 is the measured confound the whole experiment
answers, and §2.3's retention table is the one measurement the design
explicitly DEPENDS on (§1: "the rule was chosen on this"). A design chosen on
a number nobody re-derived is a design resting on a claim.

The join is ``(memory_unit_locator, future_task_id)``. ``memory_id`` is a
per-representation content hash and returns ZERO rows across arms; that trap
is asserted in both directions before any figure is computed, and the join is
positive-controlled by reproducing the published Contribution-B table from it.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.analysis.common import jsonable  # noqa: E402
from p1mem.memory.tokens import count_tokens, tokenizer_provenance  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

from r3_analyze_representations import cluster_bootstrap_paired  # noqa: E402

STRATA = ("BEARING", "MATCHED_CONTROL")
#: What §2 STATES. Re-derived below and compared; a mismatch is reported as a
#: mismatch, never silently replaced by the fresh value.
CLAIMED = {
    "median_tokens": {"raw": 8344, "summary": 280, "structured": 216},
    "min_tokens": {"raw": 1490, "summary": 139, "structured": 120},
    "max_tokens": {"raw": 19801, "summary": 604, "structured": 453},
    "mean_tokens": {"raw": 9227.9, "summary": 322.8, "structured": 237.8},
    "n_cells": 277,
    "b_minus_mc": {"raw": 0.3174, "summary": 0.0613, "structured": -0.0498},
    "mean_dU": {"raw": 0.1805, "summary": 0.0397, "structured": 0.0181},
    "spearman_bearing": -0.209, "spearman_mc": 0.079,
    #: §2.2's quartile means. Q1 reproduces; Q2-Q4 do NOT -- see the note at
    #: the s2_2 block. Kept in the comparison set rather than dropped, because
    #: a figure quietly removed from a re-derivation is a figure nobody
    #: checked.
    "quartile_means_bearing": {"Q1": 0.5000, "Q2": 0.4062,
                               "Q3": 0.1379, "Q4": 0.3000},
    "retention_bearing": {"trunc_last": 39, "summary": 24, "structured": 17,
                          "trunc_first": 1},
}


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def spearman(x: list[float], y: list[float]) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return float(np.corrcoef(rank(x), rank(y))[0, 1])


def fit_tokens(text: str, budget: int, *, from_end: bool) -> str:
    if count_tokens(text) <= budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        piece = text[-mid:] if from_end else text[:mid]
        if count_tokens(piece) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[-lo:] if from_end else text[:lo]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--raw-cells", type=Path,
                    default=REPO / "results/deltau_screened/cells.jsonl")
    ap.add_argument("--new-cells", type=Path,
                    default=REPO / "results/repr_scaleup/cells.jsonl")
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/length_control_confound.json")
    args = ap.parse_args()

    out: dict[str, Any] = {
        "_what": "§2 of docs/LENGTH_CONTROL_PRECOMMITMENT.md, machine-readable. "
                 "Every figure RE-DERIVED from the row artifacts, then compared "
                 "against what §2 states. A mismatch is reported as a mismatch.",
        "generated_at_utc": utc_now(),
        "tokenizer": tokenizer_provenance(),
        "_join": "(memory_unit_locator, future_task_id). NEVER memory_id, which "
                 "is a per-representation content hash returning zero rows.",
    }
    mismatches: list[dict[str, Any]] = []

    def cmp(path: str, got, want, tol: float) -> None:
        ok = (got is not None and want is not None
              and abs(float(got) - float(want)) <= tol)
        if not ok:
            mismatches.append({"figure": path, "claimed_in_precommitment": want,
                               "re_derived": got, "tolerance": tol})

    # ------------------------------------------------------------- load
    raw_rows = [r for r in load_jsonl(args.raw_cells)
                if (r.get("provenance") or {}).get("stratum") in STRATA]
    new_rows = load_jsonl(args.new_cells)

    def pk(r: dict) -> str:
        p = r.get("provenance") or {}
        loc = p.get("memory_unit_locator") or (
            r.get("source_episode_metadata") or {}).get("memory_unit_locator")
        if loc is None:
            raise KeyError(f"row {r.get('row_id')} has no locator; a default "
                           f"here would silently shrink the paired set")
        return f"{loc}|{r['future_task_id']}"

    by_rep: dict[str, list[dict]] = {"raw": raw_rows}
    for r in new_rows:
        if (r.get("provenance") or {}).get("stratum") in STRATA:
            by_rep.setdefault(r["memory_representation"], []).append(r)

    keys = {rep: {pk(r) for r in rs} for rep, rs in by_rep.items()}
    common = set.intersection(*keys.values())
    mids = {rep: {r["memory_id"] for r in rs} for rep, rs in by_rep.items()}
    out["C_JOIN"] = {
        "n_pair_keys_per_representation": {k: len(v) for k, v in sorted(keys.items())},
        "n_common_to_all_three": len(common),
        "n_memory_ids_common_to_all_three": len(set.intersection(*mids.values())),
        "passed": bool(len(common) == 277
                       and len(set.intersection(*mids.values())) == 0),
    }
    cmp("n_cells", len(common), CLAIMED["n_cells"], 0)
    log(f"join: {len(common)} common | memory_id join "
        f"{len(set.intersection(*mids.values()))}")

    strat = {}
    task_of = {}
    for r in raw_rows:
        if pk(r) in common:
            strat[pk(r)] = (r.get("provenance") or {})["stratum"]
            task_of[pk(r)] = r["future_task_id"]

    # per-cell mean dU. None means COULD NOT BE SCORED: excluded, never 0.0.
    mean_du: dict[str, dict[str, float]] = {}
    n_null = {}
    for rep, rs in by_rep.items():
        acc: dict[str, list[float]] = collections.defaultdict(list)
        nn = 0
        for r in rs:
            if pk(r) not in common:
                continue
            if r["delta_utility"] is None or r.get("error_code_if_any"):
                nn += 1
                continue
            acc[pk(r)].append(float(r["delta_utility"]))
        mean_du[rep] = {k: float(np.mean(v)) for k, v in acc.items()}
        n_null[rep] = nn
    out["n_unscored_rows_excluded_not_zeroed"] = n_null

    # ---- POSITIVE CONTROL ON THE JOIN: reproduce the published table ----
    # "A join that reproduces the published table is a join that matched the
    # right rows." (§2)
    mem_of = {}
    for r in raw_rows:
        if pk(r) in common:
            mem_of[pk(r)] = ((r.get("provenance") or {}).get("memory_unit_locator")
                             or (r.get("source_episode_metadata") or {})
                             .get("memory_unit_locator"))
    pub: dict[str, Any] = {}
    for rep in ("raw", "summary", "structured"):
        per_mem: dict[str, dict[str, list[float]]] = collections.defaultdict(
            lambda: {"BEARING": [], "MATCHED_CONTROL": []})
        for k, v in mean_du[rep].items():
            per_mem[mem_of[k]][strat[k]].append(v)
        diffs = [float(np.mean(d["BEARING"])) - float(np.mean(d["MATCHED_CONTROL"]))
                 for d in per_mem.values() if d["BEARING"] and d["MATCHED_CONTROL"]]
        vals = [mean_du[rep][k] for k in sorted(mean_du[rep])]
        pub[rep] = {"n_memories": len(diffs),
                    "paired_B_minus_MC": float(np.mean(diffs)) if diffs else None,
                    "n_cells": len(vals),
                    "mean_delta_utility": float(np.mean(vals)) if vals else None}
        cmp(f"B_minus_MC.{rep}", pub[rep]["paired_B_minus_MC"],
            CLAIMED["b_minus_mc"][rep], 5e-4)
        cmp(f"mean_dU.{rep}", pub[rep]["mean_delta_utility"],
            CLAIMED["mean_dU"][rep], 5e-4)
    out["C_JOIN_POSITIVE_CONTROL_published_table"] = {
        "_what": "§2: re-deriving the published Contribution-B table from this "
                 "join must reproduce it to four decimals. A join that matches "
                 "half its rows still looks like success.",
        "per_representation": pub,
    }
    log(f"published table reproduced: "
        f"{ {k: round(v['paired_B_minus_MC'], 4) for k, v in pub.items()} }")

    # ---------------------------------------- §2.1 exposed-token distributions
    toks: dict[str, list[int]] = {}
    for rep, rs in by_rep.items():
        seen: dict[str, int] = {}
        for r in rs:
            if pk(r) in common:
                seen[pk(r)] = int(r["memory_tokens_exposed"])
        toks[rep] = [seen[k] for k in sorted(seen)]
    dist: dict[str, Any] = {}
    for rep, v in toks.items():
        a = np.asarray(v)
        dist[rep] = {"n": len(v), "min": int(a.min()), "p25": float(np.percentile(a, 25)),
                     "median": float(np.median(a)), "p75": float(np.percentile(a, 75)),
                     "max": int(a.max()), "mean": round(float(a.mean()), 1)}
        for stat in ("min", "median", "max"):
            cmp(f"§2.1.{rep}.{stat}", dist[rep][stat], CLAIMED[f"{stat}_tokens"][rep], 0.5)
        cmp(f"§2.1.{rep}.mean", dist[rep]["mean"], CLAIMED["mean_tokens"][rep], 0.05)
    overlap = {
        "n_raw_cells_inside_summary_range": sum(
            1 for t in toks["raw"] if min(toks["summary"]) <= t <= max(toks["summary"])),
        "n_raw_cells_inside_structured_range": sum(
            1 for t in toks["raw"]
            if min(toks["structured"]) <= t <= max(toks["structured"])),
        "raw_min_over_summary_max": round(min(toks["raw"]) / max(toks["summary"]), 2),
        "raw_min_over_structured_max": round(min(toks["raw"]) / max(toks["structured"]), 2),
        "median_ratio_raw_over_summary": round(
            float(np.median(toks["raw"])) / float(np.median(toks["summary"])), 1),
        "median_ratio_raw_over_structured": round(
            float(np.median(toks["raw"])) / float(np.median(toks["structured"])), 1),
    }
    out["s2_1_exposed_token_distributions"] = {
        "_what": "§2.1: the arms do not overlap AT ALL, so no reweighting, "
                 "covariate adjustment or matched subsample of EXISTING cells "
                 "can separate representation from length. That is why the "
                 "confound requires new conditions and new reader calls.",
        "per_representation": dist, "separation": overlap,
    }
    log(f"§2.1 raw median {dist['raw']['median']:.0f} vs summary "
        f"{dist['summary']['median']:.0f}; raw cells inside summary range: "
        f"{overlap['n_raw_cells_inside_summary_range']}")

    # ------------------------------------------- §2.2 within-Raw dose-response
    dose: dict[str, Any] = {}
    raw_tok = {}
    for r in raw_rows:
        if pk(r) in common:
            raw_tok[pk(r)] = int(r["memory_tokens_exposed"])
    for st in STRATA:
        ks = sorted(k for k in common if strat[k] == st and k in mean_du["raw"])
        x = [float(raw_tok[k]) for k in ks]
        y = [mean_du["raw"][k] for k in ks]
        qs = np.percentile(x, [25, 50, 75])
        buckets: dict[str, list[float]] = collections.defaultdict(list)
        for xi, yi in zip(x, y):
            q = "Q1" if xi <= qs[0] else ("Q2" if xi <= qs[1]
                                          else ("Q3" if xi <= qs[2] else "Q4"))
            buckets[q].append(yi)
        dose[st] = {
            "n": len(ks), "spearman_rho": round(spearman(x, y), 4),
            "pearson_r": round(float(np.corrcoef(x, y)[0, 1]), 4),
            "quartile_means": {q: round(float(np.mean(v)), 4)
                               for q, v in sorted(buckets.items())},
            "quartile_n": {q: len(v) for q, v in sorted(buckets.items())},
        }
    cmp("§2.2.spearman.BEARING", dose["BEARING"]["spearman_rho"],
        CLAIMED["spearman_bearing"], 0.002)
    cmp("§2.2.spearman.MATCHED_CONTROL", dose["MATCHED_CONTROL"]["spearman_rho"],
        CLAIMED["spearman_mc"], 0.002)
    for q, want in CLAIMED["quartile_means_bearing"].items():
        cmp(f"§2.2.quartile_mean.BEARING.{q}",
            dose["BEARING"]["quartile_means"][q], want, 5e-4)
    # 🔴 A FIGURE IN THE PRECOMMITMENT THAT DOES NOT REPRODUCE.
    # §2.2's BEARING quartile means are stated as Q1 +0.5000, Q2 +0.4062,
    # Q3 +0.1379, Q4 +0.3000. Re-derived here they are Q1 +0.5000, Q2 +0.3714,
    # Q3 +0.2059, Q4 +0.2812. Q1 matches; Q2-Q4 do not.
    #
    # It is NOT a quartile-boundary convention. The doc states its own cut
    # points (Q1 1,490-5,085, Q4 12,890-19,801) and those are exactly the
    # pooled percentiles over the 277 cells (p25=5,085, p75=12,890), which is
    # what is used here. Four different constructions were tried -- row-level
    # vs cell-mean, cuts over rows / over the 277 cells / over the 57
    # memories / within BEARING -- and three of the four give the SAME
    # +0.3714 / +0.2059 / +0.2812; none gives the doc's triple.
    #
    # What this does and does not touch. Everything §2.2 is CITED for
    # reproduces exactly: Spearman rho -0.209 / +0.079, Pearson -0.185 /
    # +0.067, n=135/142, and the claim the figures support -- that the
    # shortest quartile has the LARGEST mean dU and the dose-response runs the
    # wrong way for a more-tokens mechanism (Q1 +0.5000 is the largest in
    # every construction tried). The design does not depend on §2.2 at all
    # (§1's table: "does the design depend on its value? -- no"), and no arm,
    # budget or contrast was chosen from it.
    #
    # Reported, not quietly replaced. The precommitment is the instrument;
    # editing a figure in it after the fact destroys exactly what it is for.
    out["s2_2_within_raw_dose_response"] = {
        "_what": "§2.2: if more exposed tokens drove utility, dU should RISE "
                 "with length inside Raw, where representation is held fixed. "
                 "It does not -- the shortest quartile has the largest mean dU. "
                 "This does NOT prove the advantage is representational: the "
                 "within-Raw range never reaches the compressed arms' range, so "
                 "it is an extrapolation of ~2.5x beyond observed support.",
        "per_stratum": dose,
    }
    log(f"§2.2 BEARING rho={dose['BEARING']['spearman_rho']} "
        f"quartiles={dose['BEARING']['quartile_means']}")

    # --------------------------- §2.3 retention under candidate truncations
    # A property of the TEXT. No reader call.
    locs = sorted({mem_of[k] for k in common})
    need = {l.split(":")[0] for l in locs}
    texts: dict[str, str] = {}
    for traj in lmev2.read_jsonl(args.root / "trajectories.jsonl"):
        if traj["id"] not in need:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator in locs:
                texts[pv.memory_unit_locator] = pv.text
        if len(texts) >= len(locs):
            break
    if len(texts) != len(locs):
        raise SystemExit(f"text join matched {len(texts)}/{len(locs)}; aborting")
    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    written = {(m["representation"], m["memory_unit_locator"]): m for m in mem_rows}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}

    ok_ctrl, ctrls = LK.controls_summary()
    out["C_DET"] = {"n_pass": sum(c.passed for c in ctrls), "n_total": len(ctrls),
                    "passed": bool(ok_ctrl)}
    if not ok_ctrl:
        raise SystemExit("C-DET: the gold detector's own controls FAILED")

    task_of_key = {k: k.split("|", 1)[1] for k in common}
    ret: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"BEARING": 0, "MATCHED_CONTROL": 0})
    for k in sorted(common):
        loc, tid = mem_of[k], task_of_key[k]
        t = tasks[tid]
        full = texts[loc]
        budget = int(written[("summary", loc)]["memory_tokens"])
        cands = {
            "raw_full": full,
            "trunc_last": fit_tokens(full, budget, from_end=True),
            "trunc_first": fit_tokens(full, budget, from_end=False),
            "summary": written[("summary", loc)]["memory_text"],
            "structured": written[("structured", loc)]["memory_text"],
        }
        for name, txt in cands.items():
            if LK.detect(txt, t.answer, eval_function_spec=t.eval_function).any_leak:
                ret[name][strat[k]] += 1
    n_bear = sum(1 for k in common if strat[k] == "BEARING")
    n_mc = sum(1 for k in common if strat[k] == "MATCHED_CONTROL")
    out["s2_3_bearing_retention_by_rule"] = {
        "_what": "§2.3, THE ONE MEASUREMENT THE DESIGN DEPENDS ON (§1): the "
                 "truncation rule was chosen on these numbers. A property of "
                 "the TEXT, computed by the project's own pure-Python detector "
                 "with NO reader call. The detector's negative control is that "
                 "it is silent on all MATCHED_CONTROL cells.",
        "n_bearing": n_bear, "n_matched_control": n_mc,
        "per_rule": {k: {"BEARING_fires": v["BEARING"],
                         "BEARING_frac": round(v["BEARING"] / n_bear, 4),
                         "MATCHED_CONTROL_fires": v["MATCHED_CONTROL"]}
                     for k, v in sorted(ret.items())},
    }
    for rule, claim in CLAIMED["retention_bearing"].items():
        cmp(f"§2.3.retention.{rule}", ret[rule]["BEARING"], claim, 0)
    cmp("§2.3.detector_negative_control", ret["raw_full"]["MATCHED_CONTROL"], 0, 0)
    log(f"§2.3 retention(BEARING): "
        f"{ {k: v['BEARING'] for k, v in sorted(ret.items())} }")

    # ----------------------------------- §5.4's reference gap, re-derived
    ks = sorted(k for k in common if strat[k] == "BEARING"
                and k in mean_du["raw"] and k in mean_du["summary"])
    bt: dict[str, list[float]] = collections.defaultdict(list)
    for k in ks:
        bt[task_of[k]].append(mean_du["raw"][k] - mean_du["summary"][k])
    gap = cluster_bootstrap_paired(bt, n_boot=args.n_boot, seed=20261001)
    out["s5_4_published_raw_minus_summary_BEARING_gap"] = {
        "_what": "§5.4: the size of the synthetic uplift planted in C-POWER. "
                 "🔴 MEASURED ACROSS SESSIONS (Raw 2026-09-29, compressed "
                 "2026-09-30) and therefore NOT usable as a comparator (§5.1); "
                 "it is a plant size only.",
        **gap,
        "ci_half_width": (round((gap["ci_upper"] - gap["ci_lower"]) / 2, 4)
                          if gap.get("ci_lower") is not None else None),
    }

    out["REDERIVATION_MISMATCHES"] = {
        "_rule": "house rule: never quote a number you have not re-derived. A "
                 "mismatch is REPORTED, never silently replaced by the fresh "
                 "value -- the precommitment is the instrument and an "
                 "after-the-fact edit destroys it.",
        "n_figures_compared": 27,
        "n_mismatched": len(mismatches),
        "mismatches": mismatches,
    }
    write_json_atomic(args.out, jsonable(out))
    log(f"§2 re-derivation: {len(mismatches)} mismatch(es) out of "
        f"{out['REDERIVATION_MISMATCHES']['n_figures_compared']} figures")
    for m in mismatches:
        log(f"  MISMATCH {m['figure']}: claimed {m['claimed_in_precommitment']} "
            f"re-derived {m['re_derived']}")
    try:
        shown = args.out.relative_to(REPO)
    except ValueError:
        shown = args.out
    log(f"confound ledger -> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

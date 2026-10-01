#!/usr/bin/env python3
"""W3: the 2x2 Writer x Reader analysis.

THE MATCHED SET -- the only basis for any number here
------------------------------------------------------
Four arms have four independent ways to lose a cell. EVERY factorial number is
computed on the pair keys present under ALL FOUR combinations, per
representation, with the denominator printed beside it. A cell lost anywhere
is dropped everywhere.

THE JOIN
--------
(memory_unit_locator, future_task_id). NOT memory_id -- a per-representation,
per-WRITER content hash, so it differs across writer arms BY CONSTRUCTION.
NOT condition_id -- it embeds representation + writer + reader, so a join on
it returns ZERO rows. Both wrong joins are RUN and their zero is printed.

THE FOUR QUANTITIES (docs/WRITER_FACTORIAL_PRECOMMITMENT.md, section "The four
quantities", fixed before the data existed):

  WRITER       dU(gem_w, r) - dU(oss_w, r), per reader and averaged
  READER       dU(w, gem_r) - dU(w, oss_r), per writer; the writer-oss row is
               the published reader arm and is the REPLICATION CHECK
  SAME-FAMILY  1/2[oss/oss + gem/gem] - 1/2[oss/gem + gem/oss]
  INTERACTION  [gem/gem - oss/gem] - [gem/oss - oss/oss]

SAME-FAMILY is +INTERACTION/2 by construction (SAME sign, factor of two).
They are ONE quantity with two readings and are reported as such -- never as
two routes that agree.

🔴 THE PRECOMMITMENT GOT THIS SIGN WRONG. It said "-0.5 x INTERACTION". The
algebra: SF = 1/2(oo+gg) - 1/2(og+go) and INTER = (gg-og) - (go-oo)
                                               = gg - og - go + oo,
so SF = +INTER/2. Both QUANTITIES are defined and implemented exactly as the
precommitment specifies; only the stated relationship between them was wrong,
and the identity check below -- which verifies the relation on the actual
numbers rather than asserting it -- is what caught it.

NULLS: delta_utility None means could not be scored. Excluded, counted, never
0.0.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import random as _rnd
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.analysis import labels as lb          # noqa: E402
from p1mem.analysis import noise as nz           # noqa: E402
from p1mem.vendor.rcc_schema import load_jsonl, utc_now   # noqa: E402

REPS = ("summary", "structured")
STRATA = ("BEARING", "MATCHED_CONTROL")
SEED = 20261001
#: the four arms, keyed (writer, reader)
ARMS = (("oss", "oss"), ("oss", "gem"), ("gem", "oss"), ("gem", "gem"))


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def f4(x) -> str:
    return "None" if x is None else f"{x:.4f}"


def pair_key(r: dict) -> str:
    p = r.get("provenance") or {}
    loc = p.get("memory_unit_locator")
    if loc is None:
        loc = (r.get("source_episode_metadata") or {}).get("memory_unit_locator")
    if loc is None:
        raise KeyError(f"row {r.get('row_id')} has no memory_unit_locator; "
                       f"defaulting it would silently shrink the paired set")
    return f"{loc}|{r['future_task_id']}"


def boot_mean(xs, *, n_boot=10000, seed=SEED) -> dict:
    arr = np.asarray([x for x in xs if x is not None], dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": None, "ci_lower": None, "ci_upper": None,
                "excludes_zero": None}
    if arr.size == 1:
        return {"n": 1, "mean": float(arr[0]), "ci_lower": None,
                "ci_upper": None, "excludes_zero": None}
    rng = np.random.default_rng(seed)
    draws = arr[rng.integers(0, arr.size, size=(n_boot, arr.size))].mean(axis=1)
    lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    p = min(1.0, 2.0 * min(float((draws <= 0).mean()), float((draws >= 0).mean())))
    return {"n": int(arr.size), "mean": float(arr.mean()), "ci_lower": lo,
            "ci_upper": hi, "p_two_sided": p,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def boot_cluster(units: dict, *, n_boot=10000, seed=SEED) -> dict:
    """Resample whole CLUSTERS (tasks / episodes), not rows."""
    keys = sorted(units, key=str)
    if not keys:
        return {"n_clusters": 0, "mean": None, "ci_lower": None,
                "ci_upper": None, "excludes_zero": None}
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
        return {"n_clusters": len(keys), "n_obs": len(flat), "mean": point,
                "ci_lower": None, "ci_upper": None, "excludes_zero": None}
    lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    return {"n_clusters": len(keys), "n_obs": len(flat), "mean": point,
            "ci_lower": lo, "ci_upper": hi,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def contributors(vals: list[float]) -> dict:
    """docs/ZERO_CONTRIBUTORS.md: both magnitudes, beside the nominal n."""
    nz_ = [v for v in vals if v != 0.0]
    return {"n_nominal": len(vals), "n_nonzero": len(nz_),
            "diluted_mean": float(np.mean(vals)) if vals else None,
            "conditional_mean_on_nonzero": float(np.mean(nz_)) if nz_ else None,
            "_rule": "a cell that is 0 under every arm is a STRUCTURAL zero "
                     "(docs/BEARING_SCARCITY.md), not a measurement of 'no "
                     "difference'. A zero-spanning CI with few contributors is "
                     "UNDERPOWERED, not null (docs/PAIRED_POWER.md)."}


def cell_means(rows: list[dict], nrep: int) -> tuple[dict, dict]:
    """pair_key -> mean dU over the first nrep replicates, + a null ledger."""
    by: dict[str, dict[int, Any]] = collections.defaultdict(dict)
    for r in rows:
        by[pair_key(r)][int(r["replicate_id"])] = r
    means: dict[str, float] = {}
    ledger = {"cells": 0, "cells_with_a_null_replicate": 0, "cells_all_null": 0,
              "null_replicate_rows": 0, "cells_short_of_requested_replicates": 0}
    for k, d in by.items():
        ledger["cells"] += 1
        use = [d[i] for i in range(nrep) if i in d]
        if len(use) < nrep:
            ledger["cells_short_of_requested_replicates"] += 1
        vals = [r["delta_utility"] for r in use if r["delta_utility"] is not None]
        nnull = sum(1 for r in use if r["delta_utility"] is None)
        ledger["null_replicate_rows"] += nnull
        if nnull:
            ledger["cells_with_a_null_replicate"] += 1
        if not vals:
            ledger["cells_all_null"] += 1
            continue
        means[k] = float(np.mean(vals))
    return means, ledger


def arm_means(rows: list[dict], nrep: int, field: str, keys: set) -> dict:
    d = collections.defaultdict(list)
    for r in rows:
        if (int(r["replicate_id"]) < nrep and pair_key(r) in keys
                and r[field] is not None):
            d[pair_key(r)].append(float(r[field]))
    return {k: float(np.mean(v)) for k, v in d.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factorial-gemma-writer", type=Path,
                    default=REPO / "results/writer_factorial/factorial_cells_gemma.jsonl")
    ap.add_argument("--factorial-gptoss-writer", type=Path,
                    default=REPO / "results/writer_factorial/factorial_cells_gptoss.jsonl")
    ap.add_argument("--published-oss-writer-oss-reader", type=Path,
                    default=REPO / "results/repr_scaleup/cells.jsonl")
    ap.add_argument("--published-oss-writer-gem-reader", type=Path,
                    default=REPO / "results/gemma_reader/transfer_cells.jsonl")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/writer_factorial/writer_factorial_analysis.json")
    args = ap.parse_args()

    out: dict[str, Any] = {
        "_what": "WRITER x READER FACTORIAL on LongMemEval-V2: 2 writers "
                 "(gpt-oss-120b, gemma-4-31B-it) x 2 readers (same two) x "
                 "2 representations (summary, structured).",
        "_matched_set_rule": (
            "EVERY number is computed on the pair keys interpretable under ALL "
            "FOUR writer x reader combinations for that representation. A cell "
            "lost anywhere is dropped everywhere. Denominators are printed "
            "beside every number."),
        "_raw_is_not_in_the_factorial": (
            "raw is a deterministic span with ZERO model calls, so "
            "'writer gpt-oss raw' and 'writer Gemma raw' are the SAME BYTES. "
            "There is no writer axis for raw and it is excluded."),
        "generated_at_utc": utc_now(),
        "precommitment": "docs/WRITER_FACTORIAL_PRECOMMITMENT.md",
        "replicate_policy": {
            "n_replicates_used": args.replicates,
            "_why": "prereg section 12 makes the balanced minimum-replicate "
                    "subset primary; every arm is read at the first N."},
    }

    # ---------------------------------------------------------------- load
    #
    # 🔴 ALL FOUR ARMS COME FROM THE SAME SESSION. The first attempt used the
    # PUBLISHED writer-gpt-oss arms as the comparator and a control caught the
    # problem: the WITHOUT arm -- which contains NO memory and whose request
    # bytes F-GATE 4 proved byte-identical (500/500 context hashes) -- returned
    # DIFFERENT text in 554 of 1124 cases when re-issued a day later. gpt-oss
    # is deterministic WITHIN a session and NOT ACROSS sessions (this project's
    # defect #21, in a new place). Comparing a writer arm run today against one
    # run yesterday would confound WRITER with SESSION, and the confound is
    # the same size as the effect: the WITHOUT-arm reward moved -0.0320.
    #
    # So the gpt-oss writer arms were RE-RUN today, issuing byte-identical
    # requests (F-GATE 5 verified 1124/1124 match the published ones), and the
    # published arms are kept only as a drift REFERENCE, never as a comparator.
    fg = load_jsonl(args.factorial_gemma_writer)
    fo = load_jsonl(args.factorial_gptoss_writer)
    oo_rows = [r for r in fo if r["reader_model"] == "gpt-oss-120b"]
    og_rows = [r for r in fo if r["reader_model"] == "gemma-4-31B-it"]
    go_rows = [r for r in fg if r["reader_model"] == "gpt-oss-120b"]
    gg_rows = [r for r in fg if r["reader_model"] == "gemma-4-31B-it"]

    src = {("oss", "oss"): oo_rows, ("oss", "gem"): og_rows,
           ("gem", "oss"): go_rows, ("gem", "gem"): gg_rows}
    log(f"loaded rows per arm: { {f'{w}/{r}': len(v) for (w, r), v in src.items()} }")
    out["_all_four_arms_are_session_matched"] = {
        "_what": "every arm was executed in the SAME session on 2026-10-01.",
        "_why": "a control found gpt-oss is NOT deterministic across sessions: "
                "554 of 1124 byte-identical WITHOUT-arm requests returned "
                "different text when re-issued a day after the published run, "
                "moving the WITHOUT-arm reward by -0.0320. Using the published "
                "arms as the comparator would confound WRITER with SESSION by "
                "about the size of the effect being measured.",
        "run_ids": {f"{w}/{r}": sorted({
            (x.get("provenance") or {}).get("run_id") for x in v})
            for (w, r), v in src.items()},
    }

    # ---- the published arms, kept as a DRIFT REFERENCE, never a comparator --
    pub_oo = [r for r in load_jsonl(args.published_oss_writer_oss_reader)
              if r["memory_representation"] in REPS]
    pub_og = [r for r in load_jsonl(args.published_oss_writer_gem_reader)
              if r["memory_representation"] in REPS]

    def _k(r):
        p = r.get("provenance") or {}
        return (r["memory_representation"], p.get("memory_unit_locator"),
                r["future_task_id"], int(r["replicate_id"]))

    drift = {"_what": (
        "the SAME request re-issued in a later session. This is a measurement "
        "of endpoint stability ACROSS sessions, and it is the reason every arm "
        "above was re-run today. It is NEVER used as a comparator.")}
    for lab, pubrows, newrows in (("reader_gptoss", pub_oo, oo_rows),
                                  ("reader_gemma", pub_og, og_rows)):
        A = {_k(r): r for r in pubrows}
        B = {_k(r): r for r in newrows}
        c = sorted(set(A) & set(B), key=str)
        tdiff = sum(1 for k in c if A[k]["output_without_memory"]
                    != B[k]["output_without_memory"])
        both = [k for k in c if A[k]["reward_without_memory"] is not None
                and B[k]["reward_without_memory"] is not None]
        rdiff = sum(1 for k in both if A[k]["reward_without_memory"]
                    != B[k]["reward_without_memory"])
        d = [B[k]["reward_without_memory"] - A[k]["reward_without_memory"]
             for k in both]
        drift[lab] = {
            "n_compared": len(c),
            "WITHOUT_arm_output_text_differs": tdiff,
            "WITHOUT_arm_reward_differs": rdiff,
            "WITHOUT_arm_mean_reward_change": float(np.mean(d)) if d else None,
            "_note": "the WITHOUT arm has NO memory in it and its request bytes "
                     "are byte-identical, so every difference here is the "
                     "endpoint, not the experiment.",
        }
    out["CROSS_SESSION_DRIFT_vs_the_published_arms"] = drift
    log(f"cross-session drift (WITHOUT arm, published vs today): "
        f"{ {k: (v['WITHOUT_arm_output_text_differs'], v['n_compared']) for k, v in drift.items() if k != '_what'} }")

    # ---- ARM IDENTITY: prove each file is the arm I think it is ----
    ident: dict[str, Any] = {"_what": (
        "the four arms must differ in exactly the two model fields. Verified "
        "on the rows themselves, not assumed from the filenames.")}
    for (w, r), rows in src.items():
        wm = sorted({x["memory_writer_model"] for x in rows})
        rm = sorted({x["reader_model"] for x in rows})
        rc = sorted({x["reader_cluster"] for x in rows})
        ident[f"{w}/{r}"] = {
            "n_rows": len(rows), "memory_writer_model": wm, "reader_model": rm,
            "reader_cluster": rc,
            "condition_ids": sorted({x["condition_id"] for x in rows}),
            "reasoning_tokens_all_null": all(x.get("reasoning_tokens") is None
                                             for x in rows),
        }
    expect = {("oss", "oss"): ("gpt-oss-120b", "gpt-oss-120b"),
              ("oss", "gem"): ("gpt-oss-120b", "gemma-4-31B-it"),
              ("gem", "oss"): ("gemma-4-31B-it", "gpt-oss-120b"),
              ("gem", "gem"): ("gemma-4-31B-it", "gemma-4-31B-it")}
    for k, (ew, er) in expect.items():
        got = ident[f"{k[0]}/{k[1]}"]
        if got["memory_writer_model"] != [ew] or got["reader_model"] != [er]:
            raise SystemExit(
                f"arm {k} carries writer={got['memory_writer_model']} "
                f"reader={got['reader_model']}, expected ({ew}, {er}). The files "
                f"are not the arms this analysis assumes.")
    allcond = [c for v in ident.values() if isinstance(v, dict)
               for c in v.get("condition_ids", [])]
    ident["all_four_condition_sets_disjoint"] = len(allcond) == len(set(allcond))
    ident["all_four_clusters_are_metis"] = all(
        v.get("reader_cluster") == ["metis"] for v in ident.values()
        if isinstance(v, dict) and "reader_cluster" in v)
    out["arm_identity"] = ident
    log(f"arm identity verified; condition sets disjoint="
        f"{ident['all_four_condition_sets_disjoint']}, all metis="
        f"{ident['all_four_clusters_are_metis']}")

    # ---- MEMORY TEXT: the writer arms MUST differ, the reader arms MUST NOT ----
    txt: dict[str, Any] = {"_what": (
        "the WRITER intervention is the memory text. Within a writer the two "
        "readers must see byte-identical text; across writers it must differ. "
        "Both directions are checked -- a check that can only pass is not a "
        "check.")}
    for wname, a, b in (("oss", ("oss", "oss"), ("oss", "gem")),
                        ("gem", ("gem", "oss"), ("gem", "gem"))):
        A = {(r["memory_representation"], pair_key(r)): r["memory_text"] for r in src[a]}
        B = {(r["memory_representation"], pair_key(r)): r["memory_text"] for r in src[b]}
        common = set(A) & set(B)
        txt[f"within_writer_{wname}_same_text"] = {
            "compared": len(common),
            "identical": sum(1 for k in common if A[k] == B[k]),
            "differ": sum(1 for k in common if A[k] != B[k])}
    OSS = {(r["memory_representation"], pair_key(r)): r["memory_text"]
           for r in src[("oss", "oss")]}
    GEM = {(r["memory_representation"], pair_key(r)): r["memory_text"]
           for r in src[("gem", "oss")]}
    common = set(OSS) & set(GEM)
    txt["across_writers_text_differs"] = {
        "compared": len(common),
        "differ": sum(1 for k in common if OSS[k] != GEM[k]),
        "IDENTICAL": sum(1 for k in common if OSS[k] == GEM[k])}
    out["memory_text_checks"] = txt
    log(f"memory text: within-writer identical "
        f"{txt['within_writer_oss_same_text']['identical']}/"
        f"{txt['within_writer_oss_same_text']['compared']} (oss), "
        f"{txt['within_writer_gem_same_text']['identical']}/"
        f"{txt['within_writer_gem_same_text']['compared']} (gem); "
        f"across-writer differ {txt['across_writers_text_differs']['differ']}/"
        f"{txt['across_writers_text_differs']['compared']}")
    for wname in ("oss", "gem"):
        d = txt[f"within_writer_{wname}_same_text"]
        if d["differ"]:
            raise SystemExit(
                f"writer {wname}: {d['differ']} cells show DIFFERENT memory text "
                f"to the two readers. That arm is not reader-only.")
    if txt["across_writers_text_differs"]["differ"] == 0:
        raise SystemExit("the two writers produced identical text everywhere; "
                         "this would be an A/A reported as A/B")

    # ---- THE WRONG JOINS, RUN AND SHOWN TO RETURN ZERO ----
    g0 = src[("gem", "gem")][0]
    ooa = src[("oss", "oss")]
    traps = {
        "_what": "run the WRONG joins and print what they return, so the rule "
                 "is evidence rather than a quoted warning.",
        "probe_pair_key": pair_key(g0),
        "probe_representation": g0["memory_representation"],
        "rows_matched_by_memory_unit_locator_and_task": sum(
            1 for r in ooa if pair_key(r) == pair_key(g0)
            and r["memory_representation"] == g0["memory_representation"]),
        "rows_matched_by_condition_id": sum(
            1 for r in ooa if r["condition_id"] == g0["condition_id"]),
        "rows_matched_by_memory_id": sum(
            1 for r in ooa if r["memory_id"] == g0["memory_id"]),
        "_note": "condition_id embeds representation + writer + reader, so it "
                 "can never match across arms. memory_id is a content hash over "
                 "memory_text AND memory_writer_model, so it differs across "
                 "writers BY CONSTRUCTION. Only locator+task is correct.",
    }
    traps["condition_id_join_returns_zero"] = traps["rows_matched_by_condition_id"] == 0
    traps["memory_id_join_returns_zero_across_writers"] = (
        traps["rows_matched_by_memory_id"] == 0)
    out["join_traps_demonstrated"] = traps
    log(f"join traps: locator+task -> "
        f"{traps['rows_matched_by_memory_unit_locator_and_task']} rows; "
        f"condition_id -> {traps['rows_matched_by_condition_id']}; "
        f"memory_id -> {traps['rows_matched_by_memory_id']}")
    if traps["rows_matched_by_memory_unit_locator_and_task"] == 0:
        raise SystemExit("the CORRECT join returned zero rows on a key known to "
                         "exist; the join is broken, not the data")

    # ------------------------------------------------- per-cell means
    means: dict[tuple, dict[str, dict]] = {}
    nulls: dict[str, Any] = {}
    by_rep_rows: dict[tuple, dict[str, list]] = {}
    for arm, rows in src.items():
        per: dict[str, list] = collections.defaultdict(list)
        for r in rows:
            per[r["memory_representation"]].append(r)
        by_rep_rows[arm] = per
        means[arm] = {}
        for rep in REPS:
            m, led = cell_means(per.get(rep, []), args.replicates)
            means[arm][rep] = m
            nulls[f"{arm[0]}/{arm[1]}:{rep}"] = led

    out["unscoreable_ledger"] = {
        "_rule": "reward/delta None means COULD NOT BE SCORED. Excluded from "
                 "means and counted here. NEVER coerced to 0.0.",
        "per_arm_per_representation": nulls,
        "error_codes": {
            f"{w}/{r}:{rep}": dict(collections.Counter(
                x["error_code_if_any"] for x in by_rep_rows[(w, r)].get(rep, [])
                if x["error_code_if_any"]))
            for (w, r) in ARMS for rep in REPS},
    }

    # ------------------------------------------------- THE MATCHED SET
    matched: dict[str, list[str]] = {}
    coverage: dict[str, Any] = {}
    for rep in REPS:
        sets = {f"{w}/{r}": set(means[(w, r)][rep]) for (w, r) in ARMS}
        m = sorted(set.intersection(*sets.values()))
        matched[rep] = m
        coverage[rep] = {
            "interpretable_per_arm": {k: len(v) for k, v in sorted(sets.items())},
            "MATCHED_all_four_arms": len(m),
            "lost_per_arm_vs_the_union": {
                k: len(set.union(*sets.values()) - v) for k, v in sorted(sets.items())},
            "union_of_all_arms": len(set.union(*sets.values())),
        }
        if not m:
            raise SystemExit(f"matched set for {rep} is EMPTY; a zero here is a "
                             f"broken join until proven otherwise")
    out["matched_set_coverage"] = coverage
    log(f"MATCHED (all four arms): { {r: len(matched[r]) for r in REPS} }")

    # metadata per pair key
    strat_of, task_of, ep_of = {}, {}, {}
    for r in src[("oss", "oss")]:
        k = pair_key(r)
        strat_of[k] = (r.get("provenance") or {}).get("stratum")
        task_of[k] = r["future_task_id"]
        ep_of[k] = r["source_episode_id"]

    # loss balance across strata -- a loss falling mainly on BEARING would bias
    # the B - MC contrast even though the loss rule is non-outcome-based
    lossbal = {}
    for rep in REPS:
        union = set.union(*[set(means[a][rep]) for a in ARMS])
        lost = sorted(union - set(matched[rep]))
        lossbal[rep] = {
            "n_lost_from_the_matched_set": len(lost),
            "by_stratum": dict(collections.Counter(strat_of.get(k) for k in lost)),
            "kept_by_stratum": dict(collections.Counter(
                strat_of.get(k) for k in matched[rep]))}
    out["matched_set_coverage"]["loss_balance_across_strata"] = lossbal
    log(f"loss balance: { {r: lossbal[r]['by_stratum'] for r in REPS} }")

    # =================================================== the four cell means
    cellmeans: dict[str, Any] = {}
    for rep in REPS:
        keys = matched[rep]
        e: dict[str, Any] = {
            "_cell_set": "pair keys interpretable under ALL FOUR arms",
            "n_matched_cells": len(keys),
            "n_tasks": len({task_of[k] for k in keys}),
            "n_memories": len({k.split("|")[0] for k in keys}),
        }
        for (w, r) in ARMS:
            vals = [means[(w, r)][rep][k] for k in keys]
            e[f"deltaU_writer{w}_reader{r}"] = {
                **boot_mean(vals, n_boot=args.n_boot),
                "contributors": contributors(vals)}
        cellmeans[rep] = e
    out["deltaU_per_arm_matched"] = cellmeans

    # =================================================== the four contrasts
    def paired(rep: str, fn) -> dict:
        keys = matched[rep]
        d = [fn(rep, k) for k in keys]
        bt, be = collections.defaultdict(list), collections.defaultdict(list)
        for k, v in zip(keys, d):
            bt[task_of[k]].append(v)
            be[ep_of[k]].append(v)
        return {
            "n_matched_cells": len(keys),
            "cell_level": boot_mean(d, n_boot=args.n_boot),
            "task_clustered": boot_cluster(bt, n_boot=args.n_boot),
            "episode_clustered": boot_cluster(be, n_boot=args.n_boot),
            "GOVERNING": "task_clustered",
            "contributors": contributors(d),
        }

    M = means

    def wr(rep, k, w, r):
        return M[(w, r)][rep][k]

    contrasts: dict[str, Any] = {}
    for rep in REPS:
        c: dict[str, Any] = {}
        # --- WRITER effect ---
        c["WRITER_effect_under_reader_gptoss"] = {
            "_definition": "dU(writer gemma, reader gpt-oss) - "
                           "dU(writer gpt-oss, reader gpt-oss), paired per cell",
            **paired(rep, lambda rp, k: wr(rp, k, "gem", "oss") - wr(rp, k, "oss", "oss"))}
        c["WRITER_effect_under_reader_gemma"] = {
            "_definition": "dU(writer gemma, reader gemma) - "
                           "dU(writer gpt-oss, reader gemma), paired per cell",
            **paired(rep, lambda rp, k: wr(rp, k, "gem", "gem") - wr(rp, k, "oss", "gem"))}
        c["WRITER_main_effect"] = {
            "_definition": "average of the two writer contrasts above "
                           "(the 2x2 main effect for writer)",
            **paired(rep, lambda rp, k: 0.5 * ((wr(rp, k, "gem", "oss") - wr(rp, k, "oss", "oss"))
                                               + (wr(rp, k, "gem", "gem") - wr(rp, k, "oss", "gem"))))}
        # --- READER effect ---
        c["READER_effect_under_writer_gptoss"] = {
            "_definition": "dU(writer gpt-oss, reader gemma) - "
                           "dU(writer gpt-oss, reader gpt-oss). THIS IS THE "
                           "PUBLISHED READER ARM, recomputed on the 4-way "
                           "matched set. It is the replication check.",
            **paired(rep, lambda rp, k: wr(rp, k, "oss", "gem") - wr(rp, k, "oss", "oss"))}
        c["READER_effect_under_writer_gemma"] = {
            "_definition": "dU(writer gemma, reader gemma) - "
                           "dU(writer gemma, reader gpt-oss), paired per cell",
            **paired(rep, lambda rp, k: wr(rp, k, "gem", "gem") - wr(rp, k, "gem", "oss"))}
        c["READER_main_effect"] = {
            "_definition": "average of the two reader contrasts above",
            **paired(rep, lambda rp, k: 0.5 * ((wr(rp, k, "oss", "gem") - wr(rp, k, "oss", "oss"))
                                               + (wr(rp, k, "gem", "gem") - wr(rp, k, "gem", "oss"))))}
        # --- SAME-FAMILY ---
        c["SAME_FAMILY_effect"] = {
            "_definition": (
                "mean of [same-family: writer oss x reader oss, writer gem x "
                "reader gem] MINUS mean of [cross-family: writer oss x reader "
                "gem, writer gem x reader oss], paired within cell."),
            "_same_family_arms": ["oss/oss", "gem/gem"],
            "_cross_family_arms": ["oss/gem", "gem/oss"],
            "_IDENTICAL_TO": (
                "exactly +0.5 x INTERACTION below -- SAME sign, factor of two. "
                "SAME-FAMILY and INTERACTION are ONE contrast with two "
                "readings, not two findings that agree. Reporting them as "
                "mutual corroboration would be this project's own 'two routes "
                "converged' defect."),
            "_precommitment_sign_erratum": (
                "docs/WRITER_FACTORIAL_PRECOMMITMENT.md states '-0.5 x "
                "INTERACTION'. That sign is WRONG; the correct relation is "
                "+0.5. Both quantities are defined and computed exactly as "
                "pre-registered -- only the prose claim about their "
                "relationship was mistaken, and the machine-checked identity "
                "below is what caught it."),
            **paired(rep, lambda rp, k:
                     0.5 * (wr(rp, k, "oss", "oss") + wr(rp, k, "gem", "gem"))
                     - 0.5 * (wr(rp, k, "oss", "gem") + wr(rp, k, "gem", "oss")))}
        # --- INTERACTION ---
        c["INTERACTION"] = {
            "_definition": "[dU(gem,gem) - dU(oss,gem)] - [dU(gem,oss) - dU(oss,oss)]: "
                           "does writer choice matter differently per reader",
            **paired(rep, lambda rp, k:
                     (wr(rp, k, "gem", "gem") - wr(rp, k, "oss", "gem"))
                     - (wr(rp, k, "gem", "oss") - wr(rp, k, "oss", "oss")))}
        # the algebraic identity, CHECKED on the data rather than asserted
        keys = matched[rep]
        sf = [0.5 * (wr(rep, k, "oss", "oss") + wr(rep, k, "gem", "gem"))
              - 0.5 * (wr(rep, k, "oss", "gem") + wr(rep, k, "gem", "oss")) for k in keys]
        it = [(wr(rep, k, "gem", "gem") - wr(rep, k, "oss", "gem"))
              - (wr(rep, k, "gem", "oss") - wr(rep, k, "oss", "oss")) for k in keys]
        c["_same_family_equals_PLUS_half_interaction"] = {
            "_relation": "SAME_FAMILY == +0.5 * INTERACTION",
            "max_abs_difference": float(np.max(np.abs(
                np.asarray(sf) - 0.5 * np.asarray(it)))) if keys else None,
            "holds": bool(keys and np.allclose(np.asarray(sf),
                                               0.5 * np.asarray(it), atol=1e-12)),
            "max_abs_difference_against_the_PRECOMMITTED_MINUS_sign": float(
                np.max(np.abs(np.asarray(sf) + 0.5 * np.asarray(it)))) if keys else None,
            "precommitted_minus_sign_holds": bool(
                keys and np.allclose(np.asarray(sf), -0.5 * np.asarray(it),
                                     atol=1e-12)),
            "_why_checked": "the precommitment stated this relation as algebra "
                            "AND GOT THE SIGN WRONG ('-0.5'). Verifying it on "
                            "the actual numbers rather than trusting the prose "
                            "is what caught that. Both columns are reported so "
                            "the erratum is visible, not smoothed."}
        contrasts[rep] = c
    out["CONTRASTS"] = contrasts

    # --------- the replication check, stated loudly and on BOTH bases ---------
    pub = {}
    pubpath = REPO / "results/ledgers/gemma_reader/reader_transfer_analysis.json"
    if pubpath.exists():
        pa = json.loads(pubpath.read_text())
        for rep in REPS:
            e = pa["per_representation_matched"][rep]
            d = e["paired_difference_task_clustered"]
            pub[rep] = {"n_matched_cells": e["n_matched_cells"],
                        "mean": d["mean"], "ci_lower": d["ci_lower"],
                        "ci_upper": d["ci_upper"],
                        "excludes_zero": d["excludes_zero"]}
    repl = {"_what": (
        "The reader effect under writer gpt-oss is the SAME CONTRAST the "
        "published reader arm reports. It is recomputed here on the 4-way "
        "matched set AND in a fresh session, so TWO things differ from the "
        "published figure: a smaller cell set, and a different session. "
        "Both are stated; a DIRECTION or SIGNIFICANCE flip is a finding and "
        "is flagged."),
        "_two_differences_not_one": (
            "the published number came from runs on 2026-09-30; this one was "
            "re-executed on 2026-10-01 because the WITHOUT-arm control proved "
            "gpt-oss is not deterministic across sessions. So this is NOT a "
            "pure re-computation of the published number on fewer cells -- it "
            "is a re-MEASUREMENT. See CROSS_SESSION_DRIFT_vs_the_published_arms.")}
    for rep in REPS:
        here = contrasts[rep]["READER_effect_under_writer_gptoss"]["task_clustered"]
        there = pub.get(rep)
        row = {"four_way_matched_set": {
                   "n": contrasts[rep]["READER_effect_under_writer_gptoss"]["n_matched_cells"],
                   "mean": here["mean"], "ci_lower": here["ci_lower"],
                   "ci_upper": here["ci_upper"], "excludes_zero": here["excludes_zero"]},
               "published_two_way_matched_set": there}
        if there is not None and here["mean"] is not None:
            row["same_sign"] = bool(
                (here["mean"] >= 0) == (there["mean"] >= 0))
            row["same_significance_verdict"] = bool(
                here["excludes_zero"] == there["excludes_zero"])
            # the PRE-COMMITTED criterion, reported exactly as written
            row["REPRODUCES_precommitted_sign_and_significance"] = bool(
                row["same_sign"] and row["same_significance_verdict"])
            row["difference_in_point_estimate"] = here["mean"] - there["mean"]
            # ---- A SECOND criterion, ADDED AFTER SEEING THE DATA ----------
            # Declared as such. The pre-committed rule tests the SIGN, and a
            # sign test on a quantity whose true value is near zero is a bad
            # instrument: +0.0036 and -0.0036 "disagree" while being the same
            # null. Mutual CI containment asks the question the sign test was
            # meant to ask -- are the two estimates compatible -- and does not
            # degrade as the estimand approaches zero.
            #
            # 🔴 This does NOT replace the pre-committed verdict, which is
            # reported above and in the document regardless. It is added
            # BESIDE it, labelled, because weakening a criterion that fired
            # would be exactly the move the precommitment exists to prevent.
            row["_added_after_seeing_the_data"] = True
            row["published_mean_inside_todays_CI"] = bool(
                here["ci_lower"] <= there["mean"] <= here["ci_upper"])
            row["todays_mean_inside_published_CI"] = bool(
                there["ci_lower"] <= here["mean"] <= there["ci_upper"])
            row["both_span_zero"] = bool(
                not here["excludes_zero"] and not there["excludes_zero"])
            row["COMPATIBLE_mutual_CI_containment"] = bool(
                row["published_mean_inside_todays_CI"]
                and row["todays_mean_inside_published_CI"])
        repl[rep] = row
    repl["ALL_REPRODUCE_precommitted_criterion"] = all(
        repl[r].get("REPRODUCES_precommitted_sign_and_significance")
        for r in REPS if isinstance(repl.get(r), dict))
    repl["ALL_COMPATIBLE_added_criterion"] = all(
        repl[r].get("COMPATIBLE_mutual_CI_containment")
        for r in REPS if isinstance(repl.get(r), dict))
    repl["_how_to_read_a_disagreement_between_the_two"] = (
        "If the pre-committed criterion FAILS while the added one PASSES, the "
        "two estimates are statistically compatible and differ in SIGN on a "
        "near-zero quantity. That is a statement about the ESTIMAND being "
        "close to zero, not about a failure to replicate -- but the "
        "pre-committed verdict is still reported as FAILED, because a "
        "criterion rewritten after it fires is not a criterion.")
    out["READER_EFFECT_REPLICATION_CHECK"] = repl
    log(f"REPLICATION CHECK precommitted(sign+sig): "
        f"{[(r, repl[r].get('REPRODUCES_precommitted_sign_and_significance')) for r in REPS]}")
    log(f"REPLICATION CHECK added(mutual CI containment): "
        f"{[(r, repl[r].get('COMPATIBLE_mutual_CI_containment')) for r in REPS]}")

    # ---- DECOMPOSE the writer effect into its two arms --------------------
    # dU = reward_WITH - reward_WITHOUT. The WITHOUT arm has NO memory in it,
    # so a WRITER effect CANNOT move it. If it does, something other than the
    # memory changed, and that is a defect, not a finding.
    decomp = {}
    for rep in REPS:
        keys = set(matched[rep])
        d: dict[str, Any] = {"n_cells": len(keys)}
        for (w, r) in ARMS:
            rows = by_rep_rows[(w, r)].get(rep, [])
            withm = arm_means(rows, args.replicates, "reward_with_memory", keys)
            without = arm_means(rows, args.replicates, "reward_without_memory", keys)
            kk = sorted(set(withm) & set(without) & keys)
            d[f"{w}/{r}"] = {
                "n": len(kk),
                "mean_reward_WITH": float(np.mean([withm[k] for k in kk])) if kk else None,
                "mean_reward_WITHOUT": float(np.mean([without[k] for k in kk])) if kk else None,
            }
        # the WITHOUT arm must be unmoved by the writer
        for rname in ("oss", "gem"):
            a = d[f"oss/{rname}"]["mean_reward_WITHOUT"]
            b = d[f"gem/{rname}"]["mean_reward_WITHOUT"]
            d[f"WITHOUT_arm_change_from_writer_under_reader_{rname}"] = (
                None if (a is None or b is None) else b - a)
        d["_reading"] = (
            "The WITHOUT arm contains NO memory, so a WRITER change cannot "
            "move it. A non-zero change there would mean something other than "
            "the memory differed between the arms -- a defect, not a finding. "
            "F-GATE 4 asserted the WITHOUT-arm request bytes are identical "
            "across writers, so any residual here is reader sampling and "
            "should be exactly 0 at temperature 0.")
        decomp[rep] = d
    out["writer_effect_decomposed_by_arm"] = decomp

    # ---- memory length: the most obvious mechanism for any writer effect ----
    lens = {}
    for rep in REPS:
        keys = set(matched[rep])
        row = {}
        for wname, arm in (("oss", ("oss", "oss")), ("gem", ("gem", "oss"))):
            per = {pair_key(r): r["memory_tokens"]
                   for r in by_rep_rows[arm].get(rep, []) if pair_key(r) in keys}
            v = list(per.values())
            row[wname] = {"n": len(v), "mean_memory_tokens": float(np.mean(v)) if v else None,
                          "median_memory_tokens": float(np.median(v)) if v else None}
        if row["oss"]["mean_memory_tokens"] and row["gem"]["mean_memory_tokens"]:
            row["gemma_over_gptoss_mean_ratio"] = (
                row["gem"]["mean_memory_tokens"] / row["oss"]["mean_memory_tokens"])
        lens[rep] = row
    out["memory_length_by_writer_on_matched_cells"] = {
        "_what": "the most obvious mechanism for a writer effect is simply how "
                 "much the writer wrote. Reported so a writer effect is not "
                 "read as a claim about compression QUALITY when it may be "
                 "about compression AMOUNT.",
        "per_representation": lens}

    # ---- within-memory BEARING - MATCHED_CONTROL per arm -------------------
    bmc = {}
    for rep in REPS:
        keys = matched[rep]
        per = {}
        for (w, r) in ARMS:
            mm = means[(w, r)][rep]
            bym: dict[str, dict[str, list]] = collections.defaultdict(
                lambda: {"BEARING": [], "MATCHED_CONTROL": []})
            for k in keys:
                st = strat_of.get(k)
                if st in STRATA:
                    bym[k.split("|")[0]][st].append(mm[k])
            diffs = [float(np.mean(d["BEARING"])) - float(np.mean(d["MATCHED_CONTROL"]))
                     for _, d in sorted(bym.items())
                     if d["BEARING"] and d["MATCHED_CONTROL"]]
            per[f"{w}/{r}"] = {"n_memories": len(diffs),
                               "n_nonzero_contributors": sum(1 for x in diffs if x != 0.0),
                               **boot_mean(diffs, n_boot=args.n_boot)}
        bmc[rep] = per
    out["within_memory_bearing_minus_control_per_arm"] = {
        "_what": "the quantity docs/REPRESENTATION_RESULT.md actually reports, "
                 "computed under each of the four arms on the matched cells.",
        "per_representation": bmc}

    # ---- harm on BEARING cells, per arm ----
    harm = {}
    for rep in REPS:
        keys = [k for k in matched[rep] if strat_of.get(k) == "BEARING"]
        h = {"n_bearing_cells_matched": len(keys)}
        for (w, r) in ARMS:
            mm = means[(w, r)][rep]
            h[f"{w}/{r}"] = {"n_negative": sum(1 for k in keys if mm[k] < 0),
                             "most_negative": min((mm[k] for k in keys), default=None)}
        harm[rep] = h
    out["harm_on_bearing_cells_per_arm"] = harm

    # ---- noise floors, each arm against ITS OWN F_exec ----
    floors: dict[str, Any] = {}
    for (w, r) in ARMS:
        for rep in REPS:
            rows = [x for x in by_rep_rows[(w, r)].get(rep, [])
                    if int(x["replicate_id"]) < args.replicates]
            est = nz.exec_floor(rows, scale="delta", n_boot=2000, allow_pooling=True)
            floors[f"{w}/{r}:{rep}"] = {
                "point": est.point, "ci_lower": est.ci_lower,
                "ci_upper": est.ci_upper, "n_units": est.n_units,
                "flags": list(est.flags)}
    # POSITIVE CONTROL: the estimator must return non-zero when it should
    mut = copy.deepcopy([x for x in by_rep_rows[("gem", "gem")].get("summary", [])
                         if int(x["replicate_id"]) < args.replicates])
    rng = _rnd.Random(7)
    n_pert, seen = 0, set()
    for x in mut:
        if x.get("error_code_if_any") or x.get("delta_utility") is None:
            continue
        if int(x["replicate_id"]) == 1 and x["cell_id"] not in seen and rng.random() < 0.5:
            seen.add(x["cell_id"])
            x["reward_with_memory"] = 1.0 - float(x["reward_with_memory"])
            x["delta_utility"] = x["reward_with_memory"] - x["reward_without_memory"]
            n_pert += 1
    pc = nz.exec_floor(mut, scale="delta", n_boot=2000, allow_pooling=True)
    floors["_positive_control_gem_gem_summary"] = {
        "_what": f"F_exec after flipping one replicate in {n_pert} cells. MUST "
                 f"be > 0, or a 0.000 floor proves nothing.",
        "n_cells_perturbed": n_pert, "point": pc.point,
        "fires": bool(pc.point is not None and pc.point > 0)}
    out["noise_floors_delta_scale"] = floors
    log(f"F_exec: { {k: f4(v['point']) for k, v in floors.items() if not k.startswith('_')} }; "
        f"positive control fires={floors['_positive_control_gem_gem_summary']['fires']}")

    # ---- useful / neutral / harmful labels, each arm vs its own floor ----
    lab = {}
    for rep in REPS:
        got: dict[str, dict[str, str]] = {}
        for (w, r) in ARMS:
            rows = [x for x in by_rep_rows[(w, r)].get(rep, [])
                    if int(x["replicate_id"]) < args.replicates]
            f = floors[f"{w}/{r}:{rep}"]["point"]
            cs = lb.cell_statistics(rows, f, n_boot=2000, allow_pooling=True)
            cid2key = {x["cell_id"]: pair_key(x) for x in rows}
            got[f"{w}/{r}"] = {cid2key[c.cell_id]: c.label for c in cs}
        keys = [k for k in matched[rep] if all(k in got[f"{w}/{r}"] for (w, r) in ARMS)]
        lab[rep] = {
            "_rule": "prereg section 4, each arm against ITS OWN measured "
                     "F_exec. Using one arm's floor on another would be a "
                     "different experiment.",
            "n_cells": len(keys),
            "label_counts_per_arm": {
                a: dict(collections.Counter(got[a][k] for k in keys)) for a in got},
            "all_four_arms_agree": sum(
                1 for k in keys if len({got[a][k] for a in got}) == 1),
        }
    out["label_counts_per_arm"] = lab

    # ---- POSITIVE CONTROL: the contrast estimators must recover a known value
    rngc = np.random.default_rng(3)
    n = 200
    base = rngc.normal(size=n)
    # construct arms with a KNOWN writer effect of +0.5 under reader gem only,
    # i.e. writer main = +0.25 and interaction = +0.5
    synth = {("oss", "oss"): base, ("oss", "gem"): base + 0.1,
             ("gem", "oss"): base, ("gem", "gem"): base + 0.1 + 0.5}
    w_oss = float(np.mean(synth[("gem", "oss")] - synth[("oss", "oss")]))
    w_gem = float(np.mean(synth[("gem", "gem")] - synth[("oss", "gem")]))
    inter = float(np.mean((synth[("gem", "gem")] - synth[("oss", "gem")])
                          - (synth[("gem", "oss")] - synth[("oss", "oss")])))
    sfam = float(np.mean(0.5 * (synth[("oss", "oss")] + synth[("gem", "gem")])
                         - 0.5 * (synth[("oss", "gem")] + synth[("gem", "oss")])))
    out["_positive_control_contrast_estimators"] = {
        "_what": "the four contrasts must recover KNOWN values on constructed "
                 "input, or an observed zero is uninterpretable. Construction: "
                 "writer effect 0.0 under reader oss, +0.5 under reader gem.",
        "writer_under_reader_oss": w_oss, "expected": 0.0,
        "writer_under_reader_gem": w_gem, "expected_gem": 0.5,
        "interaction": inter, "expected_interaction": 0.5,
        "same_family": sfam, "expected_same_family": 0.25,
        "_expected_same_family_why": (
            "+0.25 = +0.5 x the interaction of 0.5. The precommitment's "
            "'-0.5 x INTERACTION' would predict -0.25; this control is "
            "constructed from a KNOWN ground truth and so settles the sign "
            "independently of either document."),
        "fires": bool(abs(w_oss) < 1e-9 and abs(w_gem - 0.5) < 1e-9
                      and abs(inter - 0.5) < 1e-9 and abs(sfam - 0.25) < 1e-9),
    }
    log(f"contrast estimator positive control fires="
        f"{out['_positive_control_contrast_estimators']['fires']}")

    # --------------------------- the verdict, WITH its denominators ----------
    lines = []
    for rep in REPS:
        c = contrasts[rep]
        for name in ("WRITER_main_effect", "READER_main_effect",
                     "SAME_FAMILY_effect", "INTERACTION"):
            d = c[name]["task_clustered"]
            ct = c[name]["contributors"]
            lines.append(
                f"{rep}/{name}: n={c[name]['n_matched_cells']} matched cells "
                f"({ct['n_nonzero']} non-zero contributors) | "
                f"{f4(d['mean'])} [{f4(d['ci_lower'])}, {f4(d['ci_upper'])}] "
                f"task-clustered, excludes_zero={d['excludes_zero']}")
    out["VERDICT_WITH_DENOMINATORS"] = lines
    for l in lines:
        log("VERDICT " + l)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out, indent=2, default=str)
    args.out.write_text(payload)
    # Mirror to the tracked ledger ONLY for the default output path. A
    # --out used for a planted-defect control would otherwise write a
    # fabricated analysis into results/ledgers/ under its own name, where a
    # later reader could mistake it for a measurement. (This happened once
    # during this run's own positive control and was caught by listing the
    # directory afterwards.)
    default_out = (REPO / "results/writer_factorial/writer_factorial_analysis.json")
    if args.out.resolve() == default_out.resolve():
        led = REPO / "results/ledgers/writer_factorial" / args.out.name
        led.parent.mkdir(parents=True, exist_ok=True)
        led.write_text(payload)
        log(f"wrote {args.out} and tracked copy {led}")
    else:
        log(f"wrote {args.out} (NON-DEFAULT --out: no tracked ledger copy, so a "
            f"control run cannot leave a fabricated analysis in results/ledgers/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

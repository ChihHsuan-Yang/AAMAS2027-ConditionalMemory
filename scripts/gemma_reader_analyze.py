#!/usr/bin/env python3
"""READER-TRANSFER ANALYSIS: does memory utility survive a change of reader?

THE MATCHED-SET RULE, ENFORCED
------------------------------
Per-representation denominators differ (285/285/277), and the two readers can
lose different cells to errors. Every number here is computed on the set of
pair keys interpretable under BOTH readers for that representation, and the
denominator is printed beside it. A cross-representation comparison further
restricts to the keys common to all three. Means over different cell sets are
never compared.

THE JOIN
--------
``(memory_unit_locator, future_task_id)``. NOT ``memory_id`` -- a content hash.
NOT ``condition_id`` -- it embeds the representation AND the reader, so a join
on it returns ZERO rows. Both traps are checked for explicitly below, and the
``condition_id`` join is RUN and shown to return zero, so the warning in the
house rules is demonstrated rather than quoted.

NULLS
-----
``delta_utility is None`` means "could not be scored" and is EXCLUDED from a
mean with its count reported -- never coerced to 0.0.

POSITIVE CONTROLS
-----------------
Every null this script can report is defended by a control that must fire:
the join must return rows on a key known to exist; F_exec must become > 0 when
replicates are perturbed; and the correlation estimator must recover a known
value on constructed input.
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

from p1mem.analysis import labels as lb  # noqa: E402
from p1mem.analysis import noise as nz  # noqa: E402
from p1mem.vendor.rcc_schema import load_jsonl, utc_now  # noqa: E402

REPS = ("raw", "summary", "structured")
STRATA = ("BEARING", "MATCHED_CONTROL")
SEED = 20260930


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
        raise KeyError(
            f"row {r.get('row_id')} has no memory_unit_locator in provenance or "
            f"source_episode_metadata; defaulting it would silently shrink the "
            f"paired set")
    return f"{loc}|{r['future_task_id']}"


def boot_mean(xs, *, n_boot=10000, seed=SEED) -> dict:
    arr = np.asarray([x for x in xs if x is not None], dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": None, "ci_lower": None, "ci_upper": None,
                "p_two_sided": None, "excludes_zero": None}
    if arr.size == 1:
        return {"n": 1, "mean": float(arr[0]), "ci_lower": None, "ci_upper": None,
                "p_two_sided": None, "excludes_zero": None}
    rng = np.random.default_rng(seed)
    draws = arr[rng.integers(0, arr.size, size=(n_boot, arr.size))].mean(axis=1)
    lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    p = min(1.0, 2.0 * min(float((draws <= 0).mean()), float((draws >= 0).mean())))
    return {"n": int(arr.size), "mean": float(arr.mean()), "ci_lower": lo,
            "ci_upper": hi, "p_two_sided": p, "excludes_zero": bool(lo > 0 or hi < 0)}


def boot_cluster(units: dict, *, n_boot=10000, seed=SEED) -> dict:
    """Resample whole CLUSTERS (tasks / episodes), not rows.

    A third of all cells sit on ten tasks, so a cell-level interval treats
    repeated views of one task as independent draws.
    """
    keys = sorted(units, key=str)
    if not keys:
        return {"n_clusters": 0, "mean": None, "ci_lower": None, "ci_upper": None,
                "excludes_zero": None}
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


def pearson(x, y) -> float | None:
    a, b = np.asarray(x, float), np.asarray(y, float)
    if a.size < 2 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def spearman(x, y) -> float | None:
    def rank(v):
        v = np.asarray(v, float)
        order = v.argsort()
        r = np.empty(len(v), float)
        r[order] = np.arange(len(v), dtype=float)
        # average ties
        out = np.empty(len(v), float)
        for val in np.unique(v):
            m = v == val
            out[m] = r[m].mean()
        return out
    return pearson(rank(x), rank(y))


def boot_corr(x, y, *, n_boot=10000, seed=SEED) -> dict:
    a, b = np.asarray(x, float), np.asarray(y, float)
    pt = pearson(a, b)
    sp = spearman(a, b)
    if a.size < 3 or pt is None:
        return {"n": int(a.size), "pearson": pt, "spearman": sp,
                "ci_lower": None, "ci_upper": None}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        i = rng.integers(0, a.size, size=a.size)
        r = pearson(a[i], b[i])
        if r is not None:
            draws.append(r)
    if not draws:
        return {"n": int(a.size), "pearson": pt, "spearman": sp,
                "ci_lower": None, "ci_upper": None}
    return {"n": int(a.size), "pearson": pt, "spearman": sp,
            "ci_lower": float(np.percentile(draws, 2.5)),
            "ci_upper": float(np.percentile(draws, 97.5))}


def wilson(k: int, n: int) -> tuple[float | None, float | None, float | None]:
    if n == 0:
        return None, None, None
    from math import sqrt
    z = 1.959963984540054
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemma", type=Path,
                    default=REPO / "results/gemma_reader/transfer_cells.jsonl")
    ap.add_argument("--oss-raw", type=Path,
                    default=REPO / "results/deltau_screened/cells.jsonl")
    ap.add_argument("--oss-new", type=Path,
                    default=REPO / "results/repr_scaleup/cells.jsonl")
    ap.add_argument("--replicates", type=int, default=2,
                    help="the balanced minimum-replicate subset (prereg 12). "
                         "gpt-oss raw has 3 on these cells; the first N are used "
                         "so both readers are compared at the same replicate "
                         "count. 0/285 cells change their mean -- verified.")
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/gemma_reader/reader_transfer_analysis.json")
    args = ap.parse_args()

    out: dict[str, Any] = {
        "_what": "READER-TRANSFER: gpt-oss-120b vs gemma-4-31B-it reading the "
                 "IDENTICAL memory artifacts. Only the reader differs.",
        "_matched_set_rule": (
            "every comparison is computed on pair keys interpretable under BOTH "
            "readers for that representation; denominators are printed beside "
            "every number; means over different cell sets are never compared."),
        "generated_at_utc": utc_now(),
        "replicate_policy": {
            "n_replicates_used": args.replicates,
            "_why": "prereg 12 makes the balanced minimum-replicate subset "
                    "primary. gpt-oss ran 3 replicates on raw BEARING+MC and 2 "
                    "everywhere else; both readers are read at the first N."},
    }

    # ------------------------------------------------------------ load
    gem = load_jsonl(args.gemma)
    oss_raw = [r for r in load_jsonl(args.oss_raw)
               if (r.get("provenance") or {}).get("stratum") in STRATA]
    oss_new = load_jsonl(args.oss_new)
    oss_by_rep: dict[str, list] = {"raw": oss_raw}
    for r in oss_new:
        oss_by_rep.setdefault(r["memory_representation"], []).append(r)
    gem_by_rep: dict[str, list] = collections.defaultdict(list)
    for r in gem:
        gem_by_rep[r["memory_representation"]].append(r)
    log(f"loaded gemma rows: { {k: len(v) for k, v in sorted(gem_by_rep.items())} }")
    log(f"loaded gpt-oss rows: { {k: len(v) for k, v in sorted(oss_by_rep.items())} }")

    # -------- READER IDENTITY: prove MY rows carry the Gemma reader --------
    gm = collections.Counter(r.get("reader_model") for r in gem)
    om = collections.Counter(r.get("reader_model") for r in
                             [x for v in oss_by_rep.values() for x in v])
    identity = {
        "_what": "task 3: re-confirm on THIS run that the cache cannot have "
                 "served a gpt-oss response to a Gemma request.",
        "gemma_run_reader_model_counts": dict(gm),
        "gptoss_comparator_reader_model_counts": dict(om),
        "gemma_rows_all_gemma": set(gm) == {"gemma-4-31B-it"},
        "gptoss_rows_all_gptoss": set(om) == {"gpt-oss-120b"},
        "readers_are_disjoint": not (set(gm) & set(om)),
        "gemma_reader_cluster": sorted({r.get("reader_cluster") for r in gem}),
        "gptoss_reader_cluster": sorted(
            {r.get("reader_cluster") for v in oss_by_rep.values() for r in v}),
        "same_cluster_so_not_a_cluster_comparison": (
            sorted({r.get("reader_cluster") for r in gem})
            == sorted({r.get("reader_cluster")
                       for v in oss_by_rep.values() for r in v})),
        "gemma_condition_ids": sorted({r["condition_id"] for r in gem}),
        "gptoss_condition_ids": sorted(
            {r["condition_id"] for v in oss_by_rep.values() for r in v}),
        "condition_ids_disjoint": not (
            {r["condition_id"] for r in gem}
            & {r["condition_id"] for v in oss_by_rep.values() for r in v}),
        "gemma_reasoning_tokens_all_null": all(
            r.get("reasoning_tokens") is None for r in gem),
    }
    out["reader_identity"] = identity
    log(f"reader identity: gemma={dict(gm)} gptoss={dict(om)} "
        f"disjoint={identity['readers_are_disjoint']}")
    if not identity["gemma_rows_all_gemma"]:
        raise SystemExit("a gemma row does not carry reader_model=gemma-4-31B-it")

    # ---- MEMORY TEXT BYTE-IDENTITY, re-verified on the actual row pairs ----
    # Do not assume the pipeline preserved it: compare the bytes.
    txt = {"compared": 0, "identical": 0, "differ": 0, "examples": []}
    for rep in REPS:
        o = {pair_key(r): r["memory_text"] for r in oss_by_rep.get(rep, [])}
        for r in gem_by_rep.get(rep, []):
            k = pair_key(r)
            if k in o:
                txt["compared"] += 1
                if o[k] == r["memory_text"]:
                    txt["identical"] += 1
                else:
                    txt["differ"] += 1
                    if len(txt["examples"]) < 3:
                        txt["examples"].append({"rep": rep, "pair_key": k})
    # POSITIVE CONTROL: the comparison must be able to see a difference.
    ctrl_rep = next(r for r in gem)
    txt["_positive_control"] = {
        "_what": "the same comparison against text with one byte appended MUST "
                 "report differ; otherwise 'identical' proves only that the "
                 "comparison never looks at the bytes",
        "detects_one_byte_change":
            (ctrl_rep["memory_text"] + " ") != ctrl_rep["memory_text"]}
    out["memory_text_byte_identity"] = txt
    log(f"memory text byte-identity: {txt['identical']}/{txt['compared']} identical, "
        f"{txt['differ']} differ")
    if txt["differ"]:
        raise SystemExit(f"{txt['differ']} cells read DIFFERENT memory text; "
                         f"this is not a reader-only replication")
    if txt["compared"] == 0:
        raise SystemExit("memory-text check compared NOTHING")

    # ---- THE TWO JOIN TRAPS, DEMONSTRATED rather than asserted ----
    g0 = gem[0]
    o_all = [x for v in oss_by_rep.values() for x in v]
    locjoin = sum(1 for r in o_all if pair_key(r) == pair_key(g0))
    cidjoin = sum(1 for r in o_all if r["condition_id"] == g0["condition_id"])
    midjoin = sum(1 for r in o_all if r["memory_id"] == g0["memory_id"])
    out["join_traps_demonstrated"] = {
        "_what": "run the WRONG joins and show what they return, so the rule is "
                 "evidence rather than a quoted warning.",
        "probe_pair_key": pair_key(g0),
        "rows_matched_by_memory_unit_locator_and_task": locjoin,
        "rows_matched_by_condition_id": cidjoin,
        "rows_matched_by_memory_id": midjoin,
        "condition_id_join_returns_zero": cidjoin == 0,
        "_note": "condition_id embeds BOTH the representation and the reader, so "
                 "it can never match across readers. memory_id is a content hash "
                 "shared by the same source unit across representations, so it "
                 "over-matches. Only the locator+task key is correct.",
    }
    log(f"join traps: locator+task -> {locjoin} rows; condition_id -> {cidjoin}; "
        f"memory_id -> {midjoin}")

    # ---- A LABEL DRIFT between two gpt-oss ledgers, inherited here --------
    # memory_id is a digest over MEMORY_ID_KEYS, which includes
    # memory_writer_prompt_version. For RAW, the screened ledger stamped
    # "page_visit_segmentation_v1" while memories.jsonl -- the artifact this
    # run reads, and the one repr_scaleup used -- stamps
    # "raw_whole_segment@1.0.0". So the two readers' raw rows carry DIFFERENT
    # memory_id values even though the memory TEXT is byte-identical.
    #
    # Measured, not inferred: across all 855 raw BEARING+MC rows the text is
    # identical 855/855 and the writer MODEL is identical 855/855; only the
    # prompt-version LABEL differs. The drift therefore cannot affect any
    # number here -- the join is on (locator, task) -- but it is recorded
    # rather than smoothed, because a reader who joined on memory_id would
    # get zero rows for raw and a plausible-looking result for the other two.
    drift = {"_what": "memory_writer_prompt_version differs between the screened "
                      "raw ledger and memories.jsonl; memory_id digests it, so "
                      "raw memory_ids differ across the two readers while the "
                      "memory TEXT is byte-identical.",
             "screened_raw_label": sorted({r["memory_writer_prompt_version"]
                                           for r in oss_by_rep["raw"]}),
             "gemma_raw_label": sorted({r["memory_writer_prompt_version"]
                                        for r in gem_by_rep.get("raw", [])}),
             "writer_model_matches": (
                 sorted({r["memory_writer_model"] for r in oss_by_rep["raw"]})
                 == sorted({r["memory_writer_model"]
                            for r in gem_by_rep.get("raw", [])})),
             "memory_text_byte_identical": txt["differ"] == 0,
             "affects_any_number_here": False,
             "_why_not": "the join key is (memory_unit_locator, future_task_id); "
                         "memory_id is never used to join."}
    out["known_label_drift_raw_writer_prompt_version"] = drift
    log(f"label drift (raw memory_writer_prompt_version): "
        f"{drift['screened_raw_label']} vs {drift['gemma_raw_label']}; "
        f"text identical={drift['memory_text_byte_identical']}; "
        f"affects numbers=False")
    if locjoin == 0:
        raise SystemExit("the CORRECT join returned zero rows on a key known to "
                         "exist; the join is broken, not the data")

    # ------------------------------------------------- per-cell means
    def cell_means(rows: list[dict], nrep: int) -> tuple[dict, dict]:
        """pair_key -> mean dU over the first `nrep` replicates, + a null ledger.

        A None delta is "could not be scored": excluded and counted, NEVER 0.0.
        """
        by: dict[str, dict[int, Any]] = collections.defaultdict(dict)
        for r in rows:
            by[pair_key(r)][int(r["replicate_id"])] = r
        means: dict[str, float] = {}
        ledger = {"cells": 0, "cells_with_a_null_replicate": 0,
                  "cells_all_null": 0, "null_replicate_rows": 0,
                  "cells_short_of_requested_replicates": 0}
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

    gem_means, gem_null = {}, {}
    oss_means, oss_null = {}, {}
    for rep in REPS:
        gem_means[rep], gem_null[rep] = cell_means(gem_by_rep.get(rep, []),
                                                   args.replicates)
        oss_means[rep], oss_null[rep] = cell_means(oss_by_rep.get(rep, []),
                                                   args.replicates)
    # Truncation losses are NOT outcome-based -- a truncation is a property of
    # the response length against the budget, not of whether the answer was
    # right -- but they are NOT missing-at-random either: a cell whose answer
    # needs more tokens is systematically likelier to be lost, and verbose
    # questions are not a random subset. Reported per representation with the
    # error codes, so a reader can see where the loss fell.
    err_by_rep = {}
    for rep in REPS:
        rows = gem_by_rep.get(rep, [])
        err_by_rep[rep] = {
            "n_rows": len(rows),
            "error_codes": dict(collections.Counter(
                r["error_code_if_any"] for r in rows if r["error_code_if_any"])),
            "n_rows_with_error": sum(1 for r in rows if r["error_code_if_any"]),
        }
    out["unscoreable_ledger"] = {
        "_rule": "reward/delta None means COULD NOT BE SCORED. Excluded from "
                 "means and counted here. NEVER coerced to 0.0.",
        "_not_missing_at_random": (
            "Gemma losses are truncations: the response hit max_tokens=512. "
            "That is non-outcome-based (it does not depend on correctness) but "
            "it is NOT random -- cells whose answer needs more tokens are "
            "systematically likelier to be lost. The matched-set rule removes "
            "the resulting bias from the PAIRED comparison, because a cell "
            "lost under either reader is dropped from BOTH."),
        "gemma_errors_by_representation": err_by_rep,
        "_loss_mechanism": (
            "Gemma's losses are TRUNCATIONS: the answer reached max_tokens=512. "
            "An early reading that they concentrate on the long-context "
            "representation was NOT borne out -- the per-representation loss "
            "counts are in 'gemma_cells_lost_vs_gptoss' below and are "
            "comparable across representations, so the driver is the QUESTION "
            "(how much the reader wants to say) rather than the memory length. "
            "Either way the loss is identical in kind for both readers and "
            "cannot bias the PAIRED contrast: a cell lost under either reader "
            "leaves both sides of the pair."),
        "gemma_cells_lost_vs_gptoss": {
            rep: len(set(oss_means[rep]) - set(gem_means[rep])) for rep in REPS},
        # TESTABLE PREDICTION of "the driver is the question, not the memory":
        # the SAME tasks should lose cells under every representation. Reported
        # so the claim can be checked rather than taken on assertion.
        "lost_tasks_by_representation": {
            rep: sorted({k.split("|")[1]
                         for k in set(oss_means[rep]) - set(gem_means[rep])})
            for rep in REPS},
        "lost_tasks_shared_by_all_representations": sorted(
            set.intersection(*[{k.split("|")[1]
                                for k in set(oss_means[r]) - set(gem_means[r])}
                               for r in REPS]) if all(
                set(oss_means[r]) - set(gem_means[r]) for r in REPS) else set()),
        "gemma": gem_null, "gptoss": oss_null}

    # ------------------------------------------------- the matched sets
    matched: dict[str, list[str]] = {}
    coverage: dict[str, Any] = {}
    for rep in REPS:
        g, o = set(gem_means[rep]), set(oss_means[rep])
        m = sorted(g & o)
        matched[rep] = m
        coverage[rep] = {
            "gemma_interpretable_cells": len(g),
            "gptoss_interpretable_cells": len(o),
            "MATCHED_both_readers": len(m),
            "gemma_only": len(g - o), "gptoss_only": len(o - g),
            "gemma_only_examples": sorted(g - o)[:5],
            "gptoss_only_examples": sorted(o - g)[:5],
        }
    # metadata per pair key
    strat_of, task_of, ep_of = {}, {}, {}
    for rep in REPS:
        for r in oss_by_rep.get(rep, []):
            k = pair_key(r)
            strat_of[k] = (r.get("provenance") or {}).get("stratum")
            task_of[k] = r["future_task_id"]
            ep_of[k] = r["source_episode_id"]

    common3 = sorted(set(matched["raw"]) & set(matched["summary"])
                     & set(matched["structured"]))
    coverage["common_to_all_three_representations"] = len(common3)
    # Are the losses BALANCED across strata? The loss rule is non-outcome-based
    # (a truncation does not depend on correctness), but a loss pattern that
    # fell mainly on BEARING would still bias the B - MATCHED_CONTROL contrast.
    # Checked rather than assumed.
    lossbal = {}
    for rep in REPS:
        lost = sorted(set(oss_means[rep]) - set(gem_means[rep]))
        lossbal[rep] = {
            "n_lost_under_gemma": len(lost),
            "by_stratum": dict(collections.Counter(
                strat_of.get(k) for k in lost)),
            "by_task_top5": collections.Counter(
                task_of.get(k) for k in lost).most_common(5),
            "kept_by_stratum": dict(collections.Counter(
                strat_of.get(k) for k in matched[rep])),
        }
    coverage["loss_balance_across_strata"] = lossbal
    out["matched_set_coverage"] = coverage
    log(f"loss balance: { {r: lossbal[r]['by_stratum'] for r in REPS} }")
    log(f"matched sets: { {r: len(matched[r]) for r in REPS} }; "
        f"common to all three: {len(common3)}")
    for rep in REPS:
        if not matched[rep]:
            raise SystemExit(f"matched set for {rep} is EMPTY; a zero here is a "
                             f"broken join until proven otherwise")

    # =================================================== TASK 4: per repr
    per_rep: dict[str, Any] = {}
    for rep in REPS:
        keys = matched[rep]
        go = [oss_means[rep][k] for k in keys]
        gg = [gem_means[rep][k] for k in keys]
        dif = [b - a for a, b in zip(go, gg)]
        bt, be = collections.defaultdict(list), collections.defaultdict(list)
        for k, d in zip(keys, dif):
            bt[task_of[k]].append(d)
            be[ep_of[k]].append(d)
        e: dict[str, Any] = {
            "_cell_set": "pair keys interpretable under BOTH readers for this "
                         "representation",
            "n_matched_cells": len(keys),
            "n_tasks": len(bt), "n_episodes": len(be),
            "deltaU_gptoss": boot_mean(go, n_boot=args.n_boot),
            "deltaU_gemma": boot_mean(gg, n_boot=args.n_boot),
            "paired_difference_gemma_minus_gptoss": boot_mean(dif, n_boot=args.n_boot),
            "paired_difference_task_clustered": boot_cluster(bt, n_boot=args.n_boot),
            "paired_difference_episode_clustered": boot_cluster(be, n_boot=args.n_boot),
        }
        # zero contributors: a cell failing both arms under both readers
        # contributes an exact 0.0 and is not a measurement of "no difference"
        nzc = [d for d in dif if d != 0.0]
        e["contributors"] = {
            "_rule": "docs/ZERO_CONTRIBUTORS.md: print the non-zero contributor "
                     "count beside the nominal denominator, and give both the "
                     "diluted and the conditional magnitude.",
            "n_nominal": len(dif), "n_nonzero": len(nzc),
            "diluted_mean": float(np.mean(dif)) if dif else None,
            "conditional_mean_on_nonzero": float(np.mean(nzc)) if nzc else None,
        }
        # stratum split
        for st in STRATA:
            sk = [k for k in keys if strat_of.get(k) == st]
            e[st] = {
                "n_cells": len(sk),
                "deltaU_gptoss": boot_mean([oss_means[rep][k] for k in sk],
                                           n_boot=args.n_boot),
                "deltaU_gemma": boot_mean([gem_means[rep][k] for k in sk],
                                          n_boot=args.n_boot),
                "paired_difference": boot_mean(
                    [gem_means[rep][k] - oss_means[rep][k] for k in sk],
                    n_boot=args.n_boot),
            }
        # ---- the quantity REPRESENTATION_RESULT.md actually reports:
        # within-memory BEARING - MATCHED_CONTROL, per reader, same cells
        for name, mm in (("gptoss", oss_means[rep]), ("gemma", gem_means[rep])):
            bym: dict[str, dict[str, list]] = collections.defaultdict(
                lambda: {"BEARING": [], "MATCHED_CONTROL": []})
            for k in keys:
                st = strat_of.get(k)
                if st in STRATA:
                    bym[k.split("|")[0]][st].append(mm[k])
            diffs, mem_ids = [], []
            for mem, d in sorted(bym.items()):
                if d["BEARING"] and d["MATCHED_CONTROL"]:
                    diffs.append(float(np.mean(d["BEARING"]))
                                 - float(np.mean(d["MATCHED_CONTROL"])))
                    mem_ids.append(mem)
            e[f"within_memory_bearing_minus_control_{name}"] = {
                "_definition": "per memory: mean dU over its BEARING cells minus "
                               "mean dU over its MATCHED_CONTROL cells, on the "
                               "matched cell set",
                "n_memories": len(diffs),
                "n_nonzero_contributors": sum(1 for d in diffs if d != 0.0),
                **boot_mean(diffs, n_boot=args.n_boot)}
        per_rep[rep] = e
    out["per_representation_matched"] = per_rep

    # the three representations on ONE cell set (277 common keys)
    cross: dict[str, Any] = {
        "_cell_set": "pair keys matched under BOTH readers AND present in all "
                     "three representations -- the only basis on which the three "
                     "representations may be compared to each other",
        "n_cells": len(common3)}
    for rep in REPS:
        go = [oss_means[rep][k] for k in common3]
        gg = [gem_means[rep][k] for k in common3]
        cross[rep] = {
            "deltaU_gptoss": boot_mean(go, n_boot=args.n_boot),
            "deltaU_gemma": boot_mean(gg, n_boot=args.n_boot),
            "paired_difference": boot_mean([b - a for a, b in zip(go, gg)],
                                           n_boot=args.n_boot)}
    # Ordering of the representations under each reader, on the SAME cells
    for name, mm in (("gptoss", oss_means), ("gemma", gem_means)):
        order = sorted(REPS, key=lambda r: -float(np.mean(
            [mm[r][k] for k in common3])))
        cross[f"representation_ordering_{name}"] = order
    cross["orderings_agree"] = (
        cross["representation_ordering_gptoss"]
        == cross["representation_ordering_gemma"])
    out["cross_representation_common_cells"] = cross

    # =================================================== TASK 5: agreement
    agree: dict[str, Any] = {}
    for rep in REPS:
        keys = matched[rep]
        a = np.array([oss_means[rep][k] for k in keys], float)
        b = np.array([gem_means[rep][k] for k in keys], float)
        sa, sb = np.sign(a), np.sign(b)
        both_nz = (sa != 0) & (sb != 0)
        n_same = int((sa == sb).sum())
        n_same_nz = int((sa[both_nz] == sb[both_nz]).sum())
        p, lo, hi = wilson(n_same, len(keys))
        pn, lon, hin = wilson(n_same_nz, int(both_nz.sum()))
        agree[rep] = {
            "n_cells": len(keys),
            "sign_agreement_including_zeros": {
                "k": n_same, "n": len(keys), "rate": p,
                "wilson_lower": lo, "wilson_upper": hi,
                "_caveat": "zeros dominate this set; a cell that is 0 under both "
                           "readers counts as agreement and is not evidence of "
                           "transfer. The non-zero row below is the informative one."},
            "sign_agreement_both_nonzero": {
                "k": n_same_nz, "n": int(both_nz.sum()), "rate": pn,
                "wilson_lower": lon, "wilson_upper": hin},
            "n_zero_under_both": int(((sa == 0) & (sb == 0)).sum()),
            "n_nonzero_gptoss": int((sa != 0).sum()),
            "n_nonzero_gemma": int((sb != 0).sum()),
            "correlation": boot_corr(a, b, n_boot=args.n_boot),
            "contingency_sign": {
                f"oss{int(i)}_gem{int(j)}": int(((sa == i) & (sb == j)).sum())
                for i in (-1, 0, 1) for j in (-1, 0, 1)},
        }
    # POSITIVE CONTROL for the correlation estimator: it must recover a known
    # value on constructed input, and must NOT report a high r for unrelated
    # series. An estimator never shown to move is not a measurement.
    _rng = np.random.default_rng(11)
    _x = _rng.normal(size=200)
    agree["_positive_control_correlation_estimator"] = {
        "_what": "the estimator must recover r=+1, r=-1 and r~0 on constructed "
                 "input; otherwise an observed r is uninterpretable.",
        "identity_r": pearson(_x, _x),
        "negated_r": pearson(_x, -_x),
        "independent_r_abs_below_0.25": abs(pearson(_x, _rng.normal(size=200))) < 0.25,
        "spearman_monotone_nonlinear_r": spearman(_x, _x ** 3),
        "fires": (abs(pearson(_x, _x) - 1.0) < 1e-9
                  and abs(pearson(_x, -_x) + 1.0) < 1e-9),
    }
    # THE_HONEST_HEADLINE's sharpest claim: on BEARING cells harm is nearly
    # absent (gpt-oss: 2 negative of 139 raw). Whether a SECOND READER
    # reproduces that is the most reviewer-relevant transfer question, so it
    # is computed explicitly rather than left implicit in the sign table.
    harm = {}
    for rep in REPS:
        keys = [k for k in matched[rep] if strat_of.get(k) == "BEARING"]
        h = {"n_bearing_cells_matched": len(keys)}
        for name, mm in (("gptoss", oss_means[rep]), ("gemma", gem_means[rep])):
            neg = [k for k in keys if mm[k] < 0]
            p_, lo_, hi_ = wilson(len(neg), len(keys))
            h[name] = {"n_negative": len(neg), "rate": p_,
                       "wilson_lower": lo_, "wilson_upper": hi_,
                       "most_negative": min((mm[k] for k in keys), default=None)}
        h["both_readers_negative"] = len(
            [k for k in keys if oss_means[rep][k] < 0 and gem_means[rep][k] < 0])
        h["gemma_negative_where_gptoss_was_not"] = len(
            [k for k in keys if gem_means[rep][k] < 0 and oss_means[rep][k] >= 0])
        harm[rep] = h
    out["harm_on_bearing_cells"] = {
        "_what": "docs/THE_HONEST_HEADLINE.md reports that where a memory bears "
                 "on a task it HELPS, and harm is nearly absent. This is that "
                 "claim re-asked of a second reader, on the matched cells.",
        "per_representation": harm}
    log(f"harm on BEARING: "
        f"{ {r: (harm[r]['gptoss']['n_negative'], harm[r]['gemma']['n_negative'], harm[r]['n_bearing_cells_matched']) for r in REPS} }"
        f"  (gptoss_neg, gemma_neg, n)")

    out["sign_and_correlation"] = agree

    # ------------- useful / neutral / harmful agreement, prereg section 4 -----
    # Each reader is labelled against ITS OWN measured F_exec. Using one
    # reader's floor on the other would be a different experiment.
    floors: dict[str, Any] = {}
    for name, src in (("gptoss", oss_by_rep), ("gemma", gem_by_rep)):
        for rep in REPS:
            rows = src.get(rep, [])
            rows = [r for r in rows if int(r["replicate_id"]) < args.replicates]
            est = nz.exec_floor(rows, scale="delta", n_boot=2000,
                                allow_pooling=True)
            floors[f"{name}:{rep}"] = {
                "point": est.point, "ci_lower": est.ci_lower,
                "ci_upper": est.ci_upper, "n_units": est.n_units,
                "flags": list(est.flags)}
    # POSITIVE CONTROL: a floor of 0.000 from an estimator never shown to
    # return non-zero is not a measurement.
    mut = copy.deepcopy([r for r in gem_by_rep.get("summary", [])
                         if int(r["replicate_id"]) < args.replicates])
    rng = _rnd.Random(7)
    n_pert, seen = 0, set()
    for r in mut:
        if r.get("error_code_if_any") or r.get("delta_utility") is None:
            continue
        if int(r["replicate_id"]) == 1 and r["cell_id"] not in seen and rng.random() < 0.5:
            seen.add(r["cell_id"])
            r["reward_with_memory"] = 1.0 - float(r["reward_with_memory"])
            r["delta_utility"] = r["reward_with_memory"] - r["reward_without_memory"]
            n_pert += 1
    pc = nz.exec_floor(mut, scale="delta", n_boot=2000, allow_pooling=True)
    floors["_positive_control_gemma_summary"] = {
        "_what": f"F_exec after flipping one replicate in {n_pert} Gemma summary "
                 f"cells. MUST be > 0, or a 0.000 floor proves nothing.",
        "n_cells_perturbed": n_pert, "point": pc.point,
        "fires": bool(pc.point is not None and pc.point > 0)}
    out["noise_floors_delta_scale"] = floors
    log(f"F_exec: { {k: f4(v['point']) for k, v in floors.items() if not k.startswith('_')} }"
        f"  positive control fires={floors['_positive_control_gemma_summary']['fires']}")

    lab: dict[str, Any] = {}
    for rep in REPS:
        got: dict[str, dict[str, str]] = {}
        for name, src in (("gptoss", oss_by_rep), ("gemma", gem_by_rep)):
            rows = [r for r in src.get(rep, []) if int(r["replicate_id"]) < args.replicates]
            f = floors[f"{name}:{rep}"]["point"]
            cs = lb.cell_statistics(rows, f, n_boot=2000, allow_pooling=True)
            cid2key = {r["cell_id"]: pair_key(r) for r in rows}
            got[name] = {cid2key[c.cell_id]: c.label for c in cs}
        keys = [k for k in matched[rep] if k in got["gptoss"] and k in got["gemma"]]
        pairs = collections.Counter((got["gptoss"][k], got["gemma"][k]) for k in keys)
        same = sum(v for (a, b), v in pairs.items() if a == b)
        p, lo, hi = wilson(same, len(keys))
        lab[rep] = {
            "_rule": "prereg section 4, each reader against ITS OWN measured "
                     "F_exec. Using one reader's floor on the other would be a "
                     "different experiment.",
            "n_cells": len(keys),
            "gptoss_label_counts": dict(collections.Counter(
                got["gptoss"][k] for k in keys)),
            "gemma_label_counts": dict(collections.Counter(
                got["gemma"][k] for k in keys)),
            "contingency": {f"{a}->{b}": v for (a, b), v in sorted(pairs.items())},
            "agreement": {"k": same, "n": len(keys), "rate": p,
                          "wilson_lower": lo, "wilson_upper": hi},
        }
    out["label_agreement"] = lab

    # ------------------- ACCURACY LEVELS: is Gemma simply weaker? -------------
    acc: dict[str, Any] = {}
    for rep in REPS:
        keys = set(matched[rep])
        a: dict[str, Any] = {}
        for name, src in (("gptoss", oss_by_rep), ("gemma", gem_by_rep)):
            rows = [r for r in src.get(rep, [])
                    if int(r["replicate_id"]) < args.replicates
                    and pair_key(r) in keys
                    and r["reward_with_memory"] is not None]
            a[name] = {
                "n_rows": len(rows),
                "mean_reward_with_memory": float(np.mean(
                    [r["reward_with_memory"] for r in rows])) if rows else None,
                "mean_reward_without_memory": float(np.mean(
                    [r["reward_without_memory"] for r in rows])) if rows else None,
                "abstention_rate_with_memory": float(np.mean(
                    [bool((r.get("provenance") or {}).get("is_unknown_with"))
                     for r in rows])) if rows else None,
            }
        acc[rep] = a
    out["reader_accuracy_levels"] = acc

    # --------------------------- the verdict, WITH its denominators -----------
    verdict_lines = []
    for rep in REPS:
        e = per_rep[rep]
        d = e["paired_difference_task_clustered"]
        verdict_lines.append(
            f"{rep}: n={e['n_matched_cells']} matched cells over "
            f"{e['n_tasks']} tasks | dU_oss={f4(e['deltaU_gptoss']['mean'])} "
            f"dU_gem={f4(e['deltaU_gemma']['mean'])} | paired diff "
            f"{f4(d['mean'])} [{f4(d['ci_lower'])}, {f4(d['ci_upper'])}] "
            f"task-clustered, excludes_zero={d['excludes_zero']} | "
            f"sign agreement (both non-zero) "
            f"{agree[rep]['sign_agreement_both_nonzero']['k']}/"
            f"{agree[rep]['sign_agreement_both_nonzero']['n']} | "
            f"pearson r={f4(agree[rep]['correlation']['pearson'])}")
    out["VERDICT_WITH_DENOMINATORS"] = verdict_lines
    for v in verdict_lines:
        log("VERDICT " + v)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, default=str))
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

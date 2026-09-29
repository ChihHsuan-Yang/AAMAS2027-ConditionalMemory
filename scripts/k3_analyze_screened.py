#!/usr/bin/env python3
"""K3: analyse the screened run PER STRATUM, per the pre-registration.

No estimator is reimplemented. This loads the rows, calls
``p1mem.analysis.{noise,labels,decomposition}`` once per stratum, and adds the
things those modules cannot supply on their own:

* **positive controls for every zero** (project rule: prove the detector can
  fire). A floor or a rate of 0.000 from an estimator never shown to return
  non-zero is not a measurement.
* **both-arms-fail rate per stratum** -- the diagnostic that decides whether
  the instrument can detect anything at all. It was 0.7850 (handwritten) and
  0.8375 (official) on the unscreened design. If BEARING is not far lower, the
  screen did not buy measurement capacity.
* **excess over the additive null** (prereg A1.1). A flip rate alone is NOT
  evidence of interaction: a purely additive model produces 60-90% sign flips.
* **episode-clustered CIs.** Several memory UNITS come from one trajectory (of
  the 46 corpus-wide memories with >=2 bearing tasks, only 23 episodes). A
  Wilson interval over units treats 6 views of one episode as 6 independent
  draws and is too narrow. Both are reported; the clustered one governs.
* **BEARING vs RANDOM**, which quantifies how much the unscreened design
  diluted the measurement, with a permutation test over memories.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: E402
    extract_boxed_answer, is_unknown)
from p1mem.analysis import decomposition as dc  # noqa: E402
from p1mem.analysis import labels as lb  # noqa: E402
from p1mem.analysis import noise as nz  # noqa: E402
from p1mem.analysis.common import jsonable, wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402

STRATA = ("BEARING", "MATCHED_CONTROL", "RANDOM")


def stratum_of(r: dict) -> str | None:
    return (r.get("provenance") or {}).get("stratum")


def rescore(rows: list[dict], root: Path) -> dict:
    """Re-score stored outputs with the official scorer (prereg section 2, F_judge).

    Applies the SAME rule the run applied -- harness.py:1055 forces score False
    when the parsed answer is UNKNOWN -- or F_judge would measure verifier drift
    between two code paths rather than scorer nondeterminism.
    """
    tasks = {t.id: t for t in lmev2.load_tasks(root)}
    out = {}
    for r in rows:
        if r.get("error_code_if_any"):
            continue
        t = tasks[r["future_task_id"]]
        new = {}
        for of, rf in (("output_with_memory", "reward_with_memory"),
                       ("output_without_memory", "reward_without_memory")):
            txt = r.get(of)
            if txt is None:
                continue
            p = extract_boxed_answer(txt)
            new[rf] = 0.0 if is_unknown(p) else float(t.score(p))
        out[r["row_id"]] = new
    return out


def pc_exec(rows: list[dict], n_boot: int) -> dict:
    """Prove exec_floor CAN return non-zero: flip one replicate in some cells."""
    mut = copy.deepcopy(rows)
    rng = random.Random(7)
    n, seen = 0, set()
    for r in mut:
        if r.get("error_code_if_any") or r.get("delta_utility") is None:
            continue
        cid = r["cell_id"]
        if r.get("replicate_id") == 1 and cid not in seen and rng.random() < 0.5:
            seen.add(cid)
            r["reward_with_memory"] = 1.0 - float(r["reward_with_memory"])
            r["delta_utility"] = r["reward_with_memory"] - r["reward_without_memory"]
            n += 1
    est = nz.exec_floor(mut, scale="delta", n_boot=n_boot, allow_pooling=True)
    return {"_what": f"F_exec after flipping one replicate in {n} cells; MUST be > 0",
            "n_cells_perturbed": n, "point": est.point,
            "fires": bool(est.point is not None and est.point > 0)}


def pc_judge(rows: list[dict], n_boot: int) -> dict:
    """Prove judge_floor CAN return non-zero: plant a re-scoring disagreement."""
    mut = copy.deepcopy(rows)
    live = [r for r in mut if not r.get("error_code_if_any")
            and r.get("reward_with_memory") is not None]
    fake = {r["row_id"]: {"reward_with_memory": 1.0 - float(r["reward_with_memory"]),
                          "reward_without_memory": float(r["reward_without_memory"])}
            for r in live[:20]}
    est = nz.judge_floor(mut, fake, n_boot=n_boot)
    return {"_what": f"F_judge against a re-scoring disagreeing on {len(fake)} rows; "
                     f"MUST be > 0",
            "n_rows_planted": len(fake), "point": est.point,
            "fires": bool(est.point is not None and est.point > 0)}


def both_arms_fail(rows: list[dict]) -> dict:
    """Per-CELL both-arms-fail rate: no replicate of either arm ever scored.

    THE diagnostic. A cell where both arms always fail contributes dU = 0 by
    construction and cannot express a memory effect of any size. It is the
    reason the unscreened design measured nothing: 78.5% / 83.75% of its cells
    were in this state.
    """
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("error_code_if_any") or r.get("reward_with_memory") is None:
            continue
        by[(r["memory_id"], r["future_task_id"])].append(r)
    if not by:
        return {"n_cells": 0, "rate": None,
                "_note": "no admissible cells; a rate here would be a .get default"}
    bf = sum(1 for v in by.values()
             if max(max(float(x["reward_with_memory"]),
                        float(x["reward_without_memory"])) for x in v) == 0.0)
    rate, lo, hi = wilson_ci(bf, len(by))
    return {"n_cells": len(by), "n_both_arms_fail": bf, "rate": rate,
            "wilson_ci": [lo, hi]}


def du_distribution(rows: list[dict]) -> dict:
    """dU distribution BEFORE labelling (prereg: report this first)."""
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("delta_utility") is None:
            continue
        by[(r["memory_id"], r["future_task_id"])].append(float(r["delta_utility"]))
    means = {k: float(np.mean(v)) for k, v in by.items()}
    per_rep = collections.Counter(
        float(r["delta_utility"]) for r in rows if r.get("delta_utility") is not None)
    return {
        "per_cell_mean": {
            "positive": sum(1 for v in means.values() if v > 0),
            "zero": sum(1 for v in means.values() if v == 0),
            "negative": sum(1 for v in means.values() if v < 0),
            "n_cells": len(means)},
        "per_replicate": {str(k): v for k, v in sorted(per_rep.items())},
        "mean_delta_over_cells": float(np.mean(list(means.values()))) if means else None,
        # `if rows else None` is NOT enough: rows can be non-empty while every
        # reward is None (an all-errored stratum), and np.mean([]) is nan, not
        # an error. A nan serialises into the artifact and reads as a measured
        # value. Guard on the FILTERED list, and emit None for "not measured".
        "mean_reward_with": (float(np.mean(_rw)) if (_rw := [
            float(r["reward_with_memory"]) for r in rows
            if r.get("reward_with_memory") is not None]) else None),
        "mean_reward_without": (float(np.mean(_ro)) if (_ro := [
            float(r["reward_without_memory"]) for r in rows
            if r.get("reward_without_memory") is not None]) else None),
        "cells_with_disagreeing_replicates": sum(
            1 for v in by.values() if len(set(v)) > 1),
    }


def cluster_ci(flags: dict[Any, bool], cluster_of: dict[Any, Any],
               n_boot: int = 10000, seed: int = 20260929) -> dict:
    """Cluster bootstrap over SOURCE EPISODES, resampling whole episodes.

    A Wilson interval over memory UNITS assumes independent draws. Several
    units come from one trajectory, so it is too narrow. Resampling episodes
    keeps units from one episode together, which is the dependence that
    matters.
    """
    if not flags:
        return {"n_units": 0, "n_clusters": 0, "point": None, "ci": [None, None]}
    by_cl = collections.defaultdict(list)
    for k, v in flags.items():
        by_cl[cluster_of[k]].append(bool(v))
    cls = sorted(by_cl, key=str)
    point = float(np.mean([v for vs in by_cl.values() for v in vs]))
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(cls), size=len(cls))
        vals = [v for i in pick for v in by_cl[cls[i]]]
        if vals:
            boots.append(float(np.mean(vals)))
    lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) \
        if boots else (None, None)
    return {"n_units": len(flags), "n_clusters": len(cls), "point": point,
            "ci": [lo, hi], "n_boot": n_boot,
            "_method": "cluster bootstrap resampling whole source episodes"}


def perm_contrast(rows_a: list[dict], rows_b: list[dict], *, n_perm: int = 20000,
                  seed: int = 20260929) -> dict:
    """Permutation test on mean cell-level dU, A vs B, shuffling the stratum label.

    Permuted WITHIN memory where possible: the memories are shared between
    strata by construction (MATCHED_CONTROL is the SAME memory as BEARING), so
    a global shuffle would also permute memory identity and test a different
    null. Cells are the unit.
    """
    def cellmeans(rows):
        by = collections.defaultdict(list)
        for r in rows:
            if r.get("delta_utility") is None:
                continue
            by[(r["memory_id"], r["future_task_id"])].append(float(r["delta_utility"]))
        return {k: float(np.mean(v)) for k, v in by.items()}

    A, B = cellmeans(rows_a), cellmeans(rows_b)
    if not A or not B:
        return {"n_a": len(A), "n_b": len(B), "observed": None,
                "p": None, "_note": "a stratum is empty; no test"}
    obs = float(np.mean(list(A.values())) - np.mean(list(B.values())))
    mem_of = {k: k[0] for k in list(A) + list(B)}
    pooled = [(mem_of[k], v, 0) for k, v in A.items()] + \
             [(mem_of[k], v, 1) for k, v in B.items()]
    by_mem = collections.defaultdict(list)
    for m, v, g in pooled:
        by_mem[m].append((v, g))
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        sa, sb = [], []
        for m, items in by_mem.items():
            labs = [g for _v, g in items]
            rng.shuffle(labs)
            for (v, _g), g2 in zip(items, labs):
                (sa if g2 == 0 else sb).append(v)
        if sa and sb:
            d = float(np.mean(sa) - np.mean(sb))
            if abs(d) >= abs(obs) - 1e-12:
                ge += 1
    # ---- TASK-CLUSTERED interval and a leave-one-task-out jackknife ----
    # The shared grid gives some tasks up to 40 cells each (24 tasks have >=20),
    # so cells are NOT independent observations: one task can carry 40 of them.
    # In particular exactly ONE deterministically-scored errors-gotchas question
    # exists benchmark-wide (626e401e), it sits only in RANDOM, and it alone
    # generates 40 cells = 4.6% of that stratum. An unclustered interval would
    # treat those 40 as 40 independent draws and could let a single question
    # drive the dilution figure.
    #
    # So: bootstrap resampling whole TASKS, and a jackknife dropping each task in
    # turn. If the difference survives dropping any single task, no one question
    # is carrying it -- which is the "correlation driven by one outlier" check.
    rng2 = np.random.default_rng(seed)
    a_by_task: dict[Any, list[float]] = collections.defaultdict(list)
    b_by_task: dict[Any, list[float]] = collections.defaultdict(list)
    for k, v in A.items():
        a_by_task[k[1]].append(v)
    for k, v in B.items():
        b_by_task[k[1]].append(v)
    all_tasks = sorted(set(a_by_task) | set(b_by_task), key=str)
    boots = []
    for _ in range(2000):
        pick = [all_tasks[i] for i in rng2.integers(0, len(all_tasks), len(all_tasks))]
        sa = [v for t in pick for v in a_by_task.get(t, ())]
        sb = [v for t in pick for v in b_by_task.get(t, ())]
        if sa and sb:
            boots.append(float(np.mean(sa) - np.mean(sb)))
    task_ci = ([float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
               if boots else [None, None])
    jack = {}
    for t in all_tasks:
        sa = [v for k, v in A.items() if k[1] != t]
        sb = [v for k, v in B.items() if k[1] != t]
        if sa and sb:
            jack[str(t)] = float(np.mean(sa) - np.mean(sb))
    jmin = min(jack.values()) if jack else None
    jmax = max(jack.values()) if jack else None
    worst = (min(jack, key=lambda k: abs(jack[k])) if jack else None)
    return {"n_cells_a": len(A), "n_cells_b": len(B),
            "n_tasks": len(all_tasks),
            "mean_a": float(np.mean(list(A.values()))),
            "mean_b": float(np.mean(list(B.values()))),
            "observed_difference": obs, "n_perm": n_perm,
            "p_two_sided": (ge + 1) / (n_perm + 1),
            "_null": "stratum label shuffled WITHIN memory, so memory identity is "
                     "held fixed and only the bearing label moves",
            "task_clustered_ci": task_ci,
            "task_clustered_ci_excludes_zero": (
                None if task_ci[0] is None else (task_ci[0] > 0 or task_ci[1] < 0)),
            "leave_one_task_out": {
                "min": jmin, "max": jmax,
                "task_whose_removal_shrinks_it_most": worst,
                "difference_without_that_task": jack.get(worst) if worst else None,
                "sign_stable_across_all_drops": (
                    None if not jack else
                    all(v > 0 for v in jack.values()) or all(v < 0 for v in jack.values())),
            },
            "_clustering_note":
                "cells are NOT independent: the shared grid gives some tasks up to 40 "
                "cells. The permutation p is cell-level; the task_clustered_ci and the "
                "leave-one-task-out range are what govern whether ONE question drives "
                "the difference."}


def analyse_stratum(rows: list[dict], name: str, root: Path, n_boot: int,
                    seed: int, out: Path, F_reference: float | None,
                    n_boot_decomp: int = 40, n_null: int = 200) -> dict:
    print(f"\n{'='*70}\nSTRATUM {name}: {len(rows)} rows")
    live = [r for r in rows if not r.get("error_code_if_any")]
    print(f"  {len(live)} usable, {len(rows)-len(live)} errored")
    res: dict[str, Any] = {
        "n_rows": len(rows), "n_usable_rows": len(live),
        "n_errored_rows": len(rows) - len(live),
        "n_memories": len({r["memory_id"] for r in rows}),
        "n_source_episodes": len({r["source_episode_id"] for r in rows}),
        "n_tasks": len({r["future_task_id"] for r in rows}),
        "n_cells": len({(r["memory_id"], r["future_task_id"]) for r in rows}),
    }
    if not live:
        res["flags"] = ["EMPTY_STRATUM"]
        return res

    res["delta_u_distribution_before_labelling"] = du_distribution(live)
    res["both_arms_fail"] = both_arms_fail(live)
    print(f"  both-arms-fail: {res['both_arms_fail']['n_both_arms_fail']}"
          f"/{res['both_arms_fail']['n_cells']} = "
          f"{res['both_arms_fail']['rate']:.4f}")
    d = res["delta_u_distribution_before_labelling"]["per_cell_mean"]
    print(f"  dU cells: +{d['positive']} / 0 {d['zero']} / -{d['negative']}")

    rs = rescore(rows, root)
    floors = nz.all_floors(rows, rescored=rs, n_boot=n_boot, seed=seed,
                           allow_pooling=True)
    floors["F_judge_within_dataset"] = nz.judge_floor(
        rows, None, n_boot=n_boot, seed=seed).to_dict()
    floors["positive_controls"] = {"F_exec": pc_exec(rows, n_boot),
                                   "F_judge": pc_judge(rows, n_boot)}
    res["floors"] = floors
    # PRE-REGISTRATION COMPLIANCE. Section 2: "Reference floor F = F_exec
    # estimated per benchmark, POOLED ACROSS TASKS". So the floor used for
    # LABELS is the pooled one, not this stratum's own.
    #
    # This is not pedantry. A per-stratum floor would be computed on the very
    # cells whose effect is under test: BEARING is where dU actually varies, so
    # its own floor is the largest, and using it would make BEARING cells the
    # HARDEST to label robust -- biasing the floor clause against the effect the
    # stratum exists to detect. That is the "selected subgroup" shape. The
    # stratum's own floors are still reported, as diagnostics.
    res["floors_note"] = (
        "labels use the POOLED F_exec[delta] over all strata (prereg section 2: "
        "the reference floor is per BENCHMARK, pooled). This stratum's own floors "
        "are reported as diagnostics only -- a per-stratum floor is computed on "
        "the cells whose effect is under test and would bias against it.")
    F_own = floors["F_exec_delta"]["point"]
    F = F_reference
    res["F_used_for_labels"] = F
    res["F_this_stratum_diagnostic_only"] = F_own
    print(f"  F_exec[delta] own={F_own} (diagnostic)  POOLED used for labels={F}")
    print(f"  F_empty={floors['F_empty']['point']}  F_judge={floors['F_judge']['point']}")
    for k, pc in floors["positive_controls"].items():
        print(f"    positive control {k}: fires={pc['fires']} point={pc['point']}")
        if not pc["fires"]:
            res.setdefault("flags", []).append(
                f"POSITIVE_CONTROL_DID_NOT_FIRE:{k} -- its zero is not a measurement")

    lab = lb.label_analysis(rows, F, n_boot=n_boot, seed=seed, bh_q=0.10,
                            allow_pooling=True)
    res["labels_and_flips"] = lab
    if F is not None:
        res["additive_null"] = lb.additive_null_flip_rate(
            rows, F, n_null=n_null, n_boot=max(200, n_boot // 10), seed=seed,
            allow_pooling=True)

    # episode-clustered flip CI
    fr = lab.get("flips") or {}
    per_mem = fr.get("per_memory") or {}
    ep_of = {r["memory_id"]: r["source_episode_id"] for r in rows}
    for kind in ("robust_flip", "naive_flip"):
        flags = {m: bool(v.get(kind)) for m, v in per_mem.items() if v.get("eligible")}
        res.setdefault("flip_episode_clustered", {})[kind] = cluster_ci(
            flags, {m: ep_of[m] for m in flags}, seed=seed)
    ec = res.get("flip_episode_clustered", {}).get("robust_flip", {})
    print(f"  robust flip: unit-level n={ec.get('n_units')} "
          f"episode-clustered n={ec.get('n_clusters')} point={ec.get('point')} "
          f"ci={ec.get('ci')}")

    dec = dc.variance_decomposition(rows, exec_floor_sd=F,
                                    n_boot=n_boot_decomp, seed=seed,
                                    allow_pooling=True)
    dd = dec.to_dict()
    res["variance_decomposition"] = dd
    ub = [f for f in dd.get("flags", []) if "AT_UPPER_BOUNDARY" in f]
    res["decomposition_identified"] = bool(
        dd.get("converged") and not dd.get("used_fallback") and not ub)
    print(f"  decomposition: converged={dd.get('converged')} "
          f"fallback={dd.get('used_fallback')} at_upper_boundary={len(ub)} "
          f"-> IDENTIFIED={res['decomposition_identified']}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_screened/cells.jsonl")
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/deltau_screened/analysis")
    ap.add_argument("--n-boot", type=int, default=2000)
    # The decomposition's bootstrap REFITS the REML model per resample. Measured:
    # when the fit FAILS it returns in ~6s, but when it CONVERGES each refit costs
    # real time, so 200 resamples can run for many minutes per stratum. My first
    # smoke test burned 7 CPU-minutes with no output for exactly this reason -- and
    # note the 6s figure was a measurement of the FAILURE path, not of the path real
    # data takes. Kept separate from --n-boot so the cheap estimators stay well
    # resampled while this one is bounded.
    ap.add_argument("--n-boot-decomp", type=int, default=40,
                    help="bootstrap resamples for the variance decomposition ONLY")
    ap.add_argument("--n-null", type=int, default=200,
                    help="simulations for the additive null (prereg A1.1)")
    ap.add_argument("--seed", type=int, default=20260929)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(args.rows)
    print(f"[rows] {len(rows)} from {args.rows}")
    missing = [r for r in rows if stratum_of(r) is None]
    if missing:
        raise SystemExit(f"{len(missing)} rows carry no provenance.stratum")
    by_s = collections.defaultdict(list)
    for r in rows:
        by_s[stratum_of(r)].append(r)
    print(f"[strata] { {k: len(v) for k, v in sorted(by_s.items())} }")
    unknown = set(by_s) - set(STRATA)
    if unknown:
        raise SystemExit(f"unknown strata {unknown}")

    # The POOLED reference floor, computed ONCE over all strata, is what labels
    # use (prereg section 2). Computed before any stratum so no stratum's own
    # spread can influence the threshold applied to it.
    F_ref_est = nz.exec_floor(rows, scale="delta", n_boot=args.n_boot,
                              seed=args.seed, allow_pooling=True)
    F_ref = F_ref_est.point
    print(f"[reference floor] pooled F_exec[delta] = {F_ref} "
          f"(prereg section 2: per benchmark, pooled)")
    report: dict[str, Any] = {
        "_what": "K3 per-stratum analysis of the screened main run",
        "rows_artifact": str(args.rows),
        "n_rows": len(rows),
        "strata_row_counts": {k: len(v) for k, v in sorted(by_s.items())},
        "reference_floor_pooled": F_ref_est.to_dict(),
        "_reference_floor_policy":
            "prereg section 2 fixes the reference floor as F_exec per BENCHMARK, "
            "pooled across tasks. It is computed once here and applied to every "
            "stratum's labels. Per-stratum floors are diagnostics only.",
        "per_stratum": {},
    }
    for st in STRATA:
        report["per_stratum"][st] = analyse_stratum(
            by_s.get(st, []), st, args.root, args.n_boot, args.seed, args.out,
            F_ref, args.n_boot_decomp, args.n_null)

    # ---- ALL strata pooled: the decomposition's best shot at identifiability ----
    print(f"\n{'='*70}\nPOOLED (all strata) -- decomposition identifiability")
    F_all = F_ref   # same pooled estimate used for labels; not recomputed
    dec = dc.variance_decomposition(rows, exec_floor_sd=F_all,
                                    n_boot=args.n_boot_decomp,
                                    seed=args.seed, allow_pooling=True)
    dd = dec.to_dict()
    ub = [f for f in dd.get("flags", []) if "AT_UPPER_BOUNDARY" in f]
    per_task = collections.Counter(r["future_task_id"] for r in rows)
    per_mem_t = collections.defaultdict(set)
    for r in rows:
        per_mem_t[r["memory_id"]].add(r["future_task_id"])
    report["pooled_decomposition"] = {
        "F_exec_delta": F_all,
        "decomposition": dd,
        "identified": bool(dd.get("converged") and not dd.get("used_fallback")
                           and not ub),
        "at_upper_boundary_flags": ub,
        "crossing": {
            "n_memories": len(per_mem_t), "n_tasks": len(per_task),
            "tasks_per_memory": {
                "min": min(len(v) for v in per_mem_t.values()),
                "max": max(len(v) for v in per_mem_t.values()),
                "mean": float(np.mean([len(v) for v in per_mem_t.values()])),
                "histogram": dict(sorted(collections.Counter(
                    len(v) for v in per_mem_t.values()).items()))},
            "memories_per_task": {
                "min": min(per_task.values()), "max": max(per_task.values()),
                "mean": float(np.mean(list(per_task.values()))),
                "histogram": dict(sorted(collections.Counter(
                    per_task.values()).items()))},
            "n_tasks_seen_by_1_memory": sum(1 for v in per_task.values() if v == 1),
            "n_tasks_seen_by_ge10_memories": sum(1 for v in per_task.values() if v >= 10),
            "_prior": {"n_tasks": 220, "n_tasks_seen_by_1_memory": 93,
                       "outcome": "AT_UPPER_BOUNDARY on task and interaction"},
        },
    }
    print(f"  converged={dd.get('converged')} fallback={dd.get('used_fallback')} "
          f"at_upper={len(ub)} -> IDENTIFIED={report['pooled_decomposition']['identified']}")
    for c in dc.COMPONENTS:
        print(f"    {c:<12} share "
              f"{dd.get('shares', {}).get(c, 'UNMEASURED')}")

    # ---- PER-DOMAIN shared grid: the only FULLY CROSSED sub-design ----
    # Tasks are domain-specific, so NO memory sees all 218 tasks and the
    # pre-registered MoM fallback can never engage on the pooled rows (its
    # balanced sub-design is 0 x 218). Within a domain the shared grid IS fully
    # crossed by construction -- every memory sees every shared task -- which is
    # exactly the balanced design section 6's fallback asks for. Verified from
    # the design manifest before the run: enterprise 20x12, web 40x12.
    #
    # This is reported SEPARATELY and never pooled with the above: a fit on the
    # shared grid answers "how do these variance components split among cells
    # that are crossed", which is a different (and answerable) question from the
    # pooled fit.
    print(f"\n{'='*70}\nPER-DOMAIN SHARED GRID (fully crossed sub-design)")
    dom_of = {r["memory_id"]: (r.get("source_episode_metadata") or {}).get("domain")
              for r in rows}
    report["shared_grid_decomposition"] = {}
    for dom in sorted({d for d in dom_of.values() if d}):
        sub = [r for r in rows if dom_of.get(r["memory_id"]) == dom]
        # restrict to the fully-crossed core: tasks every memory in this domain saw
        seen = collections.defaultdict(set)
        for r in sub:
            seen[r["memory_id"]].add(r["future_task_id"])
        if not seen:
            continue
        core = set.intersection(*seen.values()) if seen else set()
        crossed = [r for r in sub if r["future_task_id"] in core]
        entry: dict[str, Any] = {
            "n_memories": len(seen), "n_core_tasks": len(core),
            "n_rows_in_core": len(crossed),
            "_core_definition": "tasks seen by EVERY memory in this domain",
        }
        if len(core) >= 2 and len(seen) >= 2 and crossed:
            Fd = nz.exec_floor(crossed, scale="delta", n_boot=args.n_boot,
                               seed=args.seed, allow_pooling=True).point
            dsub = dc.variance_decomposition(crossed, exec_floor_sd=Fd,
                                             n_boot=args.n_boot_decomp,
                                             seed=args.seed, allow_pooling=True)
            ds = dsub.to_dict()
            ubs = [f for f in ds.get("flags", []) if "AT_UPPER_BOUNDARY" in f]
            entry["F_exec_delta"] = Fd
            entry["decomposition"] = ds
            entry["at_upper_boundary_flags"] = ubs
            entry["identified"] = bool(ds.get("converged")
                                       and not ds.get("used_fallback") and not ubs)
            # The MoM fallback is ALSO run explicitly: on a balanced design it is
            # the pre-registered estimator and needs no optimizer, so it cannot
            # hit a clip ceiling. Reporting both says whether the REML boundary
            # is a property of the DATA or of the optimizer.
            try:
                mom = dc.variance_decomposition(
                    crossed, exec_floor_sd=Fd, n_boot=0, seed=args.seed,
                    allow_pooling=True, force_fallback=True).to_dict()
            except TypeError:
                mom = {"_note": "variance_decomposition has no force_fallback kwarg"}
            entry["method_of_moments"] = mom
            print(f"  {dom:11s}: {len(seen)} memories x {len(core)} crossed tasks -> "
                  f"identified={entry['identified']} "
                  f"shares={ {k: round(v, 4) for k, v in ds.get('shares', {}).items()} }")
            if isinstance(mom.get("shares"), dict) and mom["shares"]:
                print(f"               MoM shares="
                      f"{ {k: round(v, 4) for k, v in mom['shares'].items()} }")
        else:
            entry["identified"] = False
            entry["_why"] = (f"crossed core is {len(seen)}x{len(core)}; needs >= 2x2")
            print(f"  {dom:11s}: crossed core {len(seen)}x{len(core)} -- too small")
        report["shared_grid_decomposition"][dom] = entry

    # ---- the contrasts ----
    print(f"\n{'='*70}\nCONTRASTS")
    report["contrasts"] = {
        "BEARING_vs_RANDOM": perm_contrast(by_s.get("BEARING", []),
                                           by_s.get("RANDOM", []), seed=args.seed),
        "BEARING_vs_MATCHED_CONTROL": perm_contrast(by_s.get("BEARING", []),
                                                    by_s.get("MATCHED_CONTROL", []),
                                                    seed=args.seed),
        "MATCHED_CONTROL_vs_RANDOM": perm_contrast(by_s.get("MATCHED_CONTROL", []),
                                                   by_s.get("RANDOM", []),
                                                   seed=args.seed),
    }
    for k, v in report["contrasts"].items():
        if v.get("observed_difference") is None:
            print(f"  {k}: no test ({v.get('_note')})")
        else:
            print(f"  {k}: mean_a={v['mean_a']:+.4f} (n={v['n_cells_a']}) "
                  f"mean_b={v['mean_b']:+.4f} (n={v['n_cells_b']}) "
                  f"diff={v['observed_difference']:+.4f} p={v['p_two_sided']:.4f}")

    # both-arms-fail side by side: THE headline diagnostic
    report["both_arms_fail_by_stratum"] = {
        st: report["per_stratum"][st].get("both_arms_fail") for st in STRATA}
    print("\n  both-arms-fail by stratum (the instrument-capacity diagnostic):")
    for st in STRATA:
        b = report["both_arms_fail_by_stratum"][st] or {}
        if b.get("rate") is not None:
            print(f"    {st:18s} {b['n_both_arms_fail']:4d}/{b['n_cells']:4d} = "
                  f"{b['rate']:.4f}  CI {[round(x,4) for x in b['wilson_ci']]}")
    report["_unscreened_comparator"] = {
        "handwritten_all_cells": 0.7850, "official_all_cells": 0.8375,
        "source": "docs/SUBAGENT_J_DIAGNOSTIC.md section 3 table"}

    write_json_atomic(args.out / "k3_screened_analysis.json", jsonable(report))
    print(f"\n[wrote] {args.out / 'k3_screened_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

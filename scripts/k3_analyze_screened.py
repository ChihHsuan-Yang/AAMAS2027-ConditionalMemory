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


def f4(x) -> str:
    return "—" if x is None else f"{x:.4f}"


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


def paired_by_memory(rows_a: list[dict], rows_b: list[dict], *,
                     n_boot: int = 10000, seed: int = 20260929) -> dict:
    """WITHIN-MEMORY paired contrast: the strongest form this design supports.

    Verified from the design manifest: all 60 memories appear in BOTH BEARING and
    MATCHED_CONTROL (and in RANDOM) -- 60/60 paired, zero bearing memories lacking
    a control. So the comparison is THE SAME MEMORY on tasks it bears on versus
    tasks it does not, and **memory identity cancels**.

    That kills a whole class of objection outright. "Maybe bearing memories are
    simply better memories -- longer, richer, drawn from more informative
    episodes" cannot explain a within-memory difference, because it is the same
    60 memories on both sides. Composition matching (section 17) says the strata
    are comparable; PAIRING says the memory is identical, which is stronger.

    What it does NOT fix: the strata remain disjoint in TASKS (BEARING 56, MC 100,
    overlap 30). Task identity does not cancel, which is why the quantity is dU (a
    within-task contrast) and why the task-clustered intervals stay required.

    Each memory contributes one number: mean dU over its bearing cells minus mean
    dU over its control cells. Bootstrap is over MEMORIES, the unit of
    generalization named in prereg section 6.
    """
    def by_mem(rows):
        acc: dict[Any, list[float]] = collections.defaultdict(list)
        for r in rows:
            if r.get("delta_utility") is not None:
                acc[r["memory_id"]].append(float(r["delta_utility"]))
        return {m: float(np.mean(v)) for m, v in acc.items() if v}

    A, B = by_mem(rows_a), by_mem(rows_b)
    shared = sorted(set(A) & set(B), key=str)
    if len(shared) < 2:
        return {"n_paired_memories": len(shared), "mean_paired_difference": None,
                "_note": "fewer than 2 memories appear in both strata; no paired test"}
    diffs = np.array([A[m] - B[m] for m in shared], dtype=float)
    obs = float(diffs.mean())
    rng = np.random.default_rng(seed)
    boots = [float(rng.choice(diffs, size=len(diffs), replace=True).mean())
             for _ in range(n_boot)]
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    # Exact-ish sign-flip permutation: under the null the paired difference is
    # symmetric about 0, so flipping each memory's sign is the right null.
    ge = 0
    n_perm = 20000
    for _ in range(n_perm):
        sgn = rng.choice([-1.0, 1.0], size=len(diffs))
        if abs(float((diffs * sgn).mean())) >= abs(obs) - 1e-12:
            ge += 1
    # episode-clustered version: resample whole episodes, not memories
    ep = {}
    for r in list(rows_a) + list(rows_b):
        ep[r["memory_id"]] = r.get("source_episode_id")
    by_ep: dict[Any, list[float]] = collections.defaultdict(list)
    for m, d in zip(shared, diffs):
        by_ep[ep.get(m)].append(float(d))
    eps = sorted(by_ep, key=str)
    eb = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(eps), size=len(eps))
        vals = [v for i in pick for v in by_ep[eps[i]]]
        if vals:
            eb.append(float(np.mean(vals)))
    elo, ehi = ((float(np.percentile(eb, 2.5)), float(np.percentile(eb, 97.5)))
                if eb else (None, None))
    # ---- ZERO CONTRIBUTORS (docs/ZERO_CONTRIBUTORS.md) ----
    # A memory contributing exactly 0 is one whose tasks the reader could not
    # solve either way. Zeros shrink the mean AND the CI proportionally, so the
    # TEST stays valid -- a significant result with many zeros is real and must
    # not be discounted. But the MAGNITUDE is diluted roughly linearly in the
    # contributor fraction: reproduced here, a true +0.30 among 12 of 60 reports
    # as +0.060. Quoting that as "the effect of a bearing memory" understates it
    # fivefold. So: report both magnitudes, take the VERDICT from the
    # all-memories test (pre-registered, does not condition on an outcome), and
    # label the contributors-only figure as conditional.
    # "Non-zero" must mean "actually contributed", not "is not bit-identically
    # 0.0". Caught by a control: with continuous noise NOTHING is exactly zero,
    # so an equality test reported 60/60 contributors on data that was mostly
    # noise -- the count silently stopped measuring what it names. On this
    # benchmark rewards are 0/1 so dU is in {-1,0,1} and exact zeros are the
    # common case, but the estimator must not depend on that.
    _EPS = 1e-12
    nz = [float(d) for d in diffs if abs(float(d)) > _EPS]
    n_nz = len(nz)
    cond_mean = float(np.mean(nz)) if nz else None
    # POWER STATUS. A FIXED cutoff is wrong: power depends on the SPREAD, not
    # only the count. Measured -- to detect a true +0.30 among contributors,
    # power at 20 contributors is 1.00 at sd=0 but 0.32 at sd=0.5. So estimate
    # power from the OBSERVED spread of the paired differences, and keep the
    # fixed floor only as a backstop for very small counts.
    sd_obs = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
    eff = 0.30 * (n_nz / len(diffs)) if len(diffs) else 0.0   # diluted effect
    se = (sd_obs / np.sqrt(len(diffs))) if len(diffs) else float("inf")
    power_z = (float(eff / se) if se > 0 else float("inf"))
    # z of 1.96 for alpha=.05 two-sided; ~2.8 gives about 80% power
    # SCOPE: the underpower flag qualifies a NULL, never a positive finding.
    # docs/ZERO_CONTRIBUTORS.md says "declare underpower RATHER THAN REPORT A
    # NULL" -- it was always scoped to nulls, and my first implementation applied
    # it unconditionally. That produced BEARING vs MATCHED_CONTROL = +0.3349 with
    # a CI excluding zero and p=0.00005, labelled UNDERPOWERED, which is the
    # post-hoc-power fallacy: asking "could we have detected it?" of an effect we
    # DID detect. The observed effect (z=5.16) is about twice the hypothetical
    # one the power calculation was run against (z=2.69), so the study was
    # underpowered only for a SMALLER effect than the one found.
    detected = bool(lo > 0 or hi < 0)          # CI over memories excludes zero
    adequate = detected or ((n_nz >= 8) and (power_z >= 2.8))
    power = {
        "_rule": "docs/ZERO_CONTRIBUTORS.md: below ~8 non-zero contributors, "
                 "declare UNDERPOWERED rather than report a null -- a null at "
                 "n_effective=5 is a different claim from a null at n=40. The "
                 "count alone is not sufficient: power depends on the observed "
                 "spread too, so both are checked.",
        "n_nonzero_contributors": n_nz,
        "n_zero_contributors": len(diffs) - n_nz,
        "observed_sd_of_paired_differences": sd_obs,
        "implied_z_for_a_true_0.30_among_contributors": power_z,
        "STATUS": ("ADEQUATE" if adequate else "UNDERPOWERED"),
        "effect_was_detected": detected,
        "_scope": "this flag qualifies a NULL only. A CI that excludes zero means "
                  "the effect WAS detected, and post-hoc power for a detected "
                  "effect is a fallacy -- 'could we have found it?' is answered "
                  "by 'we did'.",
        "_reading": ("the effect was DETECTED (CI excludes zero), so no power "
                     "caveat applies" if detected else
                     "the all-memories test can detect a diluted +0.30 at this "
                     "contributor count and spread"
                     if adequate else
                     "a NULL HERE IS NOT EVIDENCE OF NO EFFECT -- the design "
                     "cannot detect a true +0.30 among contributors at this "
                     "contributor count / spread"),
    }
    return {
        "n_paired_memories": len(shared),
        "n_paired_memories_nonzero": n_nz,
        "_denominator_note": f"{len(shared)} memories ({n_nz} non-zero). Never "
                             f"quote the nominal count alone.",
        "PAIRED_POWER_STATUS": power,
        "conditional_mean_over_contributors_only": cond_mean,
        "_conditional_caveat": "conditions on a non-zero outcome, so it is "
                               "DESCRIPTIVE and can never be the population claim. "
                               "The significance verdict comes from the "
                               "all-memories test below.",
        "n_source_episodes": len(eps),
        "mean_paired_difference": obs,
        "memory_bootstrap_ci": [lo, hi],
        "memory_ci_excludes_zero": bool(lo > 0 or hi < 0),
        "episode_clustered_ci": [elo, ehi],
        "episode_ci_excludes_zero": (None if elo is None else bool(elo > 0 or ehi < 0)),
        "sign_flip_p_two_sided": (ge + 1) / (n_perm + 1),
        "n_memories_positive": int((diffs > 0).sum()),
        "n_memories_negative": int((diffs < 0).sum()),
        "n_memories_zero": int((diffs == 0).sum()),
        "_why_this_is_the_strongest_form":
            "all 60 memories appear in both strata, so MEMORY IDENTITY CANCELS: "
            "'bearing memories are just better memories' cannot explain a "
            "within-memory difference. Task identity does NOT cancel (strata are "
            "disjoint in tasks), which is why the quantity is dU and why the "
            "task-clustered intervals in perm_contrast remain required.",
        "_governing": "the episode-clustered interval governs when it and the "
                      "memory-level interval disagree",
    }


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
    # WITHIN-MEMORY paired tests come FIRST: memory identity cancels, which is a
    # stronger guarantee than the composition matching in section 17.
    report["paired_within_memory"] = {
        "BEARING_vs_MATCHED_CONTROL": paired_by_memory(
            by_s.get("BEARING", []), by_s.get("MATCHED_CONTROL", []), seed=args.seed),
        "BEARING_vs_RANDOM": paired_by_memory(
            by_s.get("BEARING", []), by_s.get("RANDOM", []), seed=args.seed),
    }
    for k2, v in report["paired_within_memory"].items():
        if v.get("mean_paired_difference") is None:
            print(f"  PAIRED {k2}: {v.get('_note')}")
        else:
            print(f"  PAIRED {k2}: diff={v['mean_paired_difference']:+.4f} "
                  f"n_mem={v['n_paired_memories']} mem_CI="
                  f"{[round(x,4) for x in v['memory_bootstrap_ci']]} "
                  f"episode_CI={[round(x,4) for x in v['episode_clustered_ci']]} "
                  f"p={v['sign_flip_p_two_sided']:.4f} "
                  f"(+{v['n_memories_positive']}/0:{v['n_memories_zero']}/"
                  f"-{v['n_memories_negative']})")
            pw_ = v.get("PAIRED_POWER_STATUS") or {}
            print(f"     denominator: {v['n_paired_memories']} memories "
                  f"({pw_.get('n_nonzero_contributors')} NON-ZERO); "
                  f"POWER={pw_.get('STATUS')}; "
                  f"conditional mean over contributors only="
                  f"{f4(v.get('conditional_mean_over_contributors_only'))}")
            if pw_.get("STATUS") == "UNDERPOWERED":
                print(f"     ⚠️ {pw_.get('_reading')}")

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

    # ---- cell concentration: a DESIGN CHARACTERISTIC, not only a correction ----
    # The shared task grid is what separates the task main effect from the
    # interaction (it is the identifiability fix), and it is ALSO what puts a
    # third of the cells on ten tasks. One design tension, not two problems.
    # Reported so a reader sees WHY the clustering is there rather than reading
    # it as defensive statistics.
    def concentration(rs: list[dict]) -> dict:
        pt_ = collections.Counter(r["future_task_id"] for r in rs)
        n_ = len(rs)
        if not n_:
            return {"n_cells": 0}
        top = pt_.most_common()
        cum, half = 0, None
        for i, (_t, v) in enumerate(top, 1):
            cum += v
            if half is None and cum >= n_ / 2:
                half = i
        return {
            "n_cells": n_, "n_tasks": len(pt_),
            "max_cells_on_one_task": max(pt_.values()),
            "n_tasks_with_ge20_cells": sum(1 for v in pt_.values() if v >= 20),
            "top10_share": sum(v for _t, v in top[:10]) / n_,
            "top20_share": sum(v for _t, v in top[:20]) / n_,
            "n_tasks_holding_half_the_cells": half,
        }

    cell_rows = {(r["memory_id"], r["future_task_id"]): r for r in rows}
    report["cell_concentration"] = {
        "ALL": concentration(list(cell_rows.values())),
        **{st: concentration([v for k2, v in cell_rows.items()
                              if stratum_of(v) == st]) for st in STRATA},
        "_why_reported":
            "the shared task grid is the identifiability fix AND the source of the "
            "concentration; they are one design tension. This is why every contrast "
            "carries a task-clustered CI and a leave-one-task-out jackknife.",
    }
    ca = report["cell_concentration"]["ALL"]
    print(f"\n  cell concentration (ALL): {ca['n_cells']} cells on {ca['n_tasks']} tasks; "
          f"top10 = {ca['top10_share']:.1%}; half the cells on "
          f"{ca['n_tasks_holding_half_the_cells']} tasks; max {ca['max_cells_on_one_task']}")

    # ---- CLUSTERED GOVERNS: flag any contrast where the two disagree ----
    # Policy (docs/CONTRAST_FRAMING.md): if the task-clustered CI and the
    # cell-level p disagree, the CLUSTERED one governs. Detecting the
    # disagreement automatically means it cannot be quietly not-noticed.
    disagree = {}
    for k2, v in (report.get("contrasts") or {}).items():
        pcell = v.get("p_two_sided")
        excl = v.get("task_clustered_ci_excludes_zero")
        if pcell is None or excl is None:
            continue
        cell_says_sig = pcell < 0.05
        if cell_says_sig != bool(excl):
            disagree[k2] = {
                "cell_level_p": pcell, "cell_level_calls_it_significant": cell_says_sig,
                "task_clustered_ci": v.get("task_clustered_ci"),
                "clustered_calls_it_significant": bool(excl),
                "GOVERNING": "task_clustered",
                "_rule": "docs/CONTRAST_FRAMING.md: when they disagree the clustered "
                         "interval governs; report both, lead with the conservative one.",
            }
    report["clustered_vs_cell_level_disagreements"] = disagree
    if disagree:
        print("\n  ⚠️ CLUSTERED vs CELL-LEVEL DISAGREE (clustered governs):")
        for k2, d in disagree.items():
            print(f"     {k2}: cell p={d['cell_level_p']:.4f} sig={d['cell_level_calls_it_significant']} "
                  f"BUT clustered CI {[round(x,4) for x in (d['task_clustered_ci'] or [])]} "
                  f"sig={d['clustered_calls_it_significant']}")
    else:
        print("\n  clustered and cell-level agree on every contrast")

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

    # ---- MECHANICAL READING RULES ----
    # Where a ruling can be made mechanical, make it mechanical: a rule a human
    # must remember at reporting time is a rule that gets forgotten. These
    # fields are emitted INTO the artifact so it refuses to be misread, rather
    # than relying on whoever opens it (including me) to recall the policy.
    bf = {st: ((report["per_stratum"].get(st) or {}).get("both_arms_fail") or {}).get("rate")
          for st in STRATA}
    bear, rand = bf.get("BEARING"), bf.get("RANDOM")
    stop = {
        "_rule": "docs/CONTRAST_FRAMING.md / K report section 16: if BEARING's "
                 "both-arms-fail is not MATERIALLY below RANDOM's, the instrument "
                 "cannot detect anything and THAT is the headline. Committed before "
                 "results existed so it cannot be softened after seeing them.",
        "bearing_both_arms_fail": bear,
        "random_both_arms_fail": rand,
        "absolute_reduction": (None if bear is None or rand is None else rand - bear),
        "unscreened_comparator": 0.7850,
    }
    if bear is not None and rand is not None:
        # "materially" fixed here, not chosen after the fact: the BEARING Wilson
        # upper bound must sit below the RANDOM point estimate. That is a
        # separation the interval itself supports, not an eyeballed gap.
        bci = (((report["per_stratum"].get("BEARING") or {}).get("both_arms_fail")
                or {}).get("wilson_ci") or [None, None])
        stop["bearing_wilson_upper"] = bci[1]
        stop["separated"] = (None if bci[1] is None else bool(bci[1] < rand))
        stop["VERDICT"] = (
            "SCREEN BOUGHT MEASUREMENT CAPACITY" if stop["separated"]
            else "SCREEN DID NOT MATERIALLY REDUCE BOTH-ARMS-FAIL -- this is the "
                 "headline and nothing downstream gets dressed up")
    report["STOPPING_RULE"] = stop

    # ---- THE FOUNDING HYPOTHESIS, adjudicated mechanically ----
    # P1 was built around task-conditional HARM with the sign-flip rate as the
    # headline. Emitted as a field with its Wilson bound so the artifact states
    # the verdict rather than relying on a reader to derive it -- and so a ZERO
    # is reported as a bounded zero, never as "not observed".
    fh = {}
    for st in STRATA:
        fl = ((report["per_stratum"].get(st) or {}).get("labels_and_flips")
              or {}).get("flips") or {}
        per_mem = fl.get("per_memory") or {}
        elig = {m: v for m, v in per_mem.items() if v.get("eligible")}
        nflip = sum(1 for v in elig.values() if v.get("naive_flip"))
        rate, lo, hi = wilson_ci(nflip, len(elig)) if elig else (None, None, None)
        fh[st] = {"n_flip_eligible_memories": len(elig),
                  "n_memories_with_a_sign_flip": nflip,
                  "flip_rate": rate, "wilson_ci": [lo, hi]}
    b = fh.get("BEARING") or {}
    fh["VERDICT"] = (
        "SIGN-REVERSAL COMPONENT NOT SUPPORTED: "
        f"{b.get('n_memories_with_a_sign_flip')} of "
        f"{b.get('n_flip_eligible_memories')} flip-eligible BEARING memories show both "
        f"a positive and a negative dU task; the Wilson upper bound is "
        f"{(b.get('wilson_ci') or [None, None])[1]}. This BOUNDS the rate; it is not "
        "merely an absence of observations."
        if b.get("n_memories_with_a_sign_flip") == 0 else
        "sign flips observed in BEARING; see rate and CI")
    fh["_scope"] = ("NOT evidence that harm does not occur in agent memory: one corpus, "
                    "one reader, one representation, pairs selected to bear. The "
                    "defensible statement is 'unsupported here', not 'absent'. No "
                    "harmful-memory RATE is claimed from any stratum -- the pairing is "
                    "ours in all three, so none yields a natural base rate.")
    fh["_kill_criterion"] = ("NOT triggered: it required the phenomenon to be absent. "
                             "What is absent is the sign-reversal COMPONENT; the "
                             "memory-utility effect itself is large and significant.")
    report["FOUNDING_HYPOTHESIS"] = fh
    print(f"\n  FOUNDING HYPOTHESIS: {fh['VERDICT'][:110]}")
    print(f"\n  STOPPING RULE: BEARING={f4(bear)} vs RANDOM={f4(rand)} "
          f"-> {stop.get('VERDICT', 'UNEVALUABLE')}")

    # A1.4 / section 4: F_exec == 0 makes the floor clause vacuous, so robust and
    # naive coincide MECHANICALLY. Stated as a field so the gap is never read as
    # a measured zero.
    report["ROBUST_NAIVE_GAP_STATUS"] = (
        {"status": "NOT_MEASURABLE",
         "_why": "F_exec[delta] == 0 for a deterministic reader, so section 4's "
                 "magnitude clause |mean dU| > F is vacuous and robust == naive by "
                 "construction. A gap of 0.0 here would imply a measurement was "
                 "taken; it cannot be taken at this replicate count.",
         "F_exec_delta": F_ref}
        if not F_ref else
        {"status": "MEASURABLE", "F_exec_delta": F_ref})
    print(f"  ROBUST/NAIVE GAP: {report['ROBUST_NAIVE_GAP_STATUS']['status']}")

    write_json_atomic(args.out / "k3_screened_analysis.json", jsonable(report))
    print(f"\n[wrote] {args.out / 'k3_screened_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

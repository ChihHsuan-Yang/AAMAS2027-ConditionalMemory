#!/usr/bin/env python3
"""GF4: the gold-free bearing-control effect, its CI, and the verdict.

Per ``docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md`` §5 and §7. The analysis was
fixed before the screen ran and before any reward was looked at.

🔴 THE DECIDING QUANTITY, named in advance
------------------------------------------
``GF_BEARING AND NOT GOLD_BEARING`` versus its matched controls. The executed
screened cells were CHOSEN BY THE GOLD SCREEN, so any GF stratum intersected
with them is enriched for gold-bearing cells and a pooled contrast would
partly re-measure the gold screen. The GF run was built to supply this
stratum directly (160 of its 164 GF_BEARING cells are gold-free).

reward None means COULD NOT BE SCORED and is never coerced to 0.0.
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

import numpy as np  # noqa: E402

from p1mem.schema import write_json_atomic  # noqa: E402


def log(m: str) -> None:
    print(m, flush=True)


def cell_means(rows: list[dict]) -> dict[tuple, float]:
    """One dU per cell, replicates averaged (prereg section 3).

    A row whose dU is None (could not be scored) is DROPPED from the mean, not
    read as 0.0. A cell with no scorable replicate yields no cell at all.
    """
    by: dict[tuple, list[float]] = collections.defaultdict(list)
    for r in rows:
        if r.get("delta_utility") is None:
            continue
        by[(r["source_episode_metadata"]["memory_unit_locator"],
            r["future_task_id"])].append(float(r["delta_utility"]))
    return {k: float(np.mean(v)) for k, v in by.items() if v}


def task_clustered_ci(a: dict[tuple, float], b: dict[tuple, float], *,
                      n_boot: int = 10000, seed: int = 20261001) -> dict:
    """Bootstrap resampling whole TASKS.

    Cells are not independent: one task can carry many cells. Resampling tasks
    keeps a task's cells together, which is the dependence that matters.
    """
    if not a or not b:
        return {"n_a": len(a), "n_b": len(b), "difference": None,
                "ci": [None, None],
                "_note": "a stratum is empty; no interval is computed (an empty "
                         "stratum must not yield a number)"}
    at: dict[Any, list[float]] = collections.defaultdict(list)
    bt: dict[Any, list[float]] = collections.defaultdict(list)
    for (_m, t), v in a.items():
        at[t].append(v)
    for (_m, t), v in b.items():
        bt[t].append(v)
    tasks = sorted(set(at) | set(bt), key=str)
    obs = float(np.mean(list(a.values())) - np.mean(list(b.values())))
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = [tasks[i] for i in rng.integers(0, len(tasks), len(tasks))]
        sa = [v for t in pick for v in at.get(t, ())]
        sb = [v for t in pick for v in bt.get(t, ())]
        if sa and sb:
            boots.append(float(np.mean(sa) - np.mean(sb)))
    lo, hi = ((float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
              if boots else (None, None))
    return {"n_cells_a": len(a), "n_cells_b": len(b), "n_tasks": len(tasks),
            "mean_a": float(np.mean(list(a.values()))),
            "mean_b": float(np.mean(list(b.values()))),
            "difference": obs, "ci": [lo, hi],
            "ci_excludes_zero": (None if lo is None else bool(lo > 0 or hi < 0)),
            "n_boot": n_boot,
            "_method": "cluster bootstrap resampling whole TASKS"}


def episode_clustered_ci(a: dict[tuple, float], b: dict[tuple, float], locmap,
                         *, n_boot: int = 10000, seed: int = 20261001) -> dict:
    """Same contrast, resampling whole SOURCE EPISODES."""
    if not a or not b:
        return {"difference": None, "ci": [None, None], "_note": "a stratum is empty"}
    ae: dict[Any, list[float]] = collections.defaultdict(list)
    be: dict[Any, list[float]] = collections.defaultdict(list)
    for (m, _t), v in a.items():
        ae[locmap[m]].append(v)
    for (m, _t), v in b.items():
        be[locmap[m]].append(v)
    eps = sorted(set(ae) | set(be), key=str)
    obs = float(np.mean(list(a.values())) - np.mean(list(b.values())))
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = [eps[i] for i in rng.integers(0, len(eps), len(eps))]
        sa = [v for e in pick for v in ae.get(e, ())]
        sb = [v for e in pick for v in be.get(e, ())]
        if sa and sb:
            boots.append(float(np.mean(sa) - np.mean(sb)))
    lo, hi = ((float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
              if boots else (None, None))
    return {"n_episodes": len(eps), "difference": obs, "ci": [lo, hi],
            "ci_excludes_zero": (None if lo is None else bool(lo > 0 or hi < 0)),
            "_method": "cluster bootstrap resampling whole SOURCE EPISODES"}


def paired_by_memory(a: dict[tuple, float], b: dict[tuple, float], *,
                     n_boot: int = 10000, seed: int = 20261001) -> dict:
    """WITHIN-MEMORY paired contrast: memory identity cancels.

    'Bearing memories are simply better memories' cannot explain a difference
    measured on the SAME memory across its bearing and its control tasks.
    """
    A: dict[Any, list[float]] = collections.defaultdict(list)
    B: dict[Any, list[float]] = collections.defaultdict(list)
    for (m, _t), v in a.items():
        A[m].append(v)
    for (m, _t), v in b.items():
        B[m].append(v)
    shared = sorted(set(A) & set(B), key=str)
    if len(shared) < 2:
        return {"n_paired_memories": len(shared), "mean_paired_difference": None,
                "_note": "fewer than 2 memories in both strata; no paired test"}
    diffs = np.array([float(np.mean(A[m])) - float(np.mean(B[m])) for m in shared])
    obs = float(diffs.mean())
    rng = np.random.default_rng(seed)
    boots = [float(rng.choice(diffs, size=len(diffs), replace=True).mean())
             for _ in range(n_boot)]
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    ge = 0
    n_perm = 20000
    for _ in range(n_perm):
        sgn = rng.choice([-1.0, 1.0], size=len(diffs))
        if abs(float((diffs * sgn).mean())) >= abs(obs) - 1e-12:
            ge += 1
    nz = [d for d in diffs if abs(d) > 1e-12]
    return {"n_paired_memories": len(shared),
            "n_nonzero_contributors": len(nz),
            "n_zero_contributors": len(diffs) - len(nz),
            "_denominator_note": f"{len(shared)} memories ({len(nz)} non-zero). "
                                 f"Never quote the nominal count alone.",
            "mean_paired_difference": obs,
            "memory_bootstrap_ci": [lo, hi],
            "ci_excludes_zero": bool(lo > 0 or hi < 0),
            "sign_flip_p_two_sided": (ge + 1) / (n_perm + 1),
            "n_memories_positive": int((diffs > 0).sum()),
            "n_memories_negative": int((diffs < 0).sum()),
            "n_memories_zero": int((diffs == 0).sum())}


def both_arms_fail(rows: list[dict]) -> dict:
    """Per-CELL both-arms-fail rate: THE diagnostic for measurement capacity.

    A cell where both arms always fail contributes dU = 0 by construction and
    cannot express a memory effect of any size. If a bearing stratum's rate is
    no lower than a no-bearing baseline's, the screen has not concentrated
    measurable cells -- which is a statement about the SCREEN, separate from
    the size of any effect.
    """
    by: dict[tuple, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("reward_with_memory") is None:
            continue
        by[(r["source_episode_metadata"]["memory_unit_locator"],
            r["future_task_id"])].append(r)
    if not by:
        return {"n_cells": 0, "rate": None,
                "_note": "no admissible cell; a rate here would be a default"}
    bf = sum(1 for v in by.values()
             if max(max(float(x["reward_with_memory"]),
                        float(x["reward_without_memory"])) for x in v) == 0.0)
    return {"n_cells": len(by), "n_both_arms_fail": bf, "rate": bf / len(by)}


def arm_rates(rows: list[dict]) -> dict:
    """WITH / WITHOUT correctness, the figure that distinguishes a memory-utility
    result from 'a passage containing the answer helps'.

    None is NOT coerced: unscorable rows are counted in their own bucket and
    excluded from both numerator and denominator.
    """
    ok = [r for r in rows if r.get("reward_with_memory") is not None
          and r.get("reward_without_memory") is not None]
    uns = len(rows) - len(ok)
    if not ok:
        return {"n_rows": len(rows), "n_unscorable": uns, "with": None,
                "without": None, "_note": "no scorable row; a rate here would be "
                                          "an absence written as a zero"}
    cw = sum(1 for r in ok if float(r["reward_with_memory"]) == 1.0)
    co = sum(1 for r in ok if float(r["reward_without_memory"]) == 1.0)
    return {"n_rows": len(rows), "n_scorable_rows": len(ok), "n_unscorable": uns,
            "with_correct": cw, "with_rate": cw / len(ok),
            "without_correct": co, "without_rate": co / len(ok)}


def positive_control_c5(a: dict[tuple, float], b: dict[tuple, float], locmap,
                        planted: float, seed: int) -> dict:
    """C5. Prove the test CAN detect a gold-sized effect on THESE strata, and
    that the proof is not vacuous.

    A null from a test never shown to fire is not evidence of absence. Plant
    ``planted`` on every bearing cell and require the interval to exclude zero.

    🔴 **NON-VACUITY, added after the control passed on a design that could not
    possibly have failed it.** Tested on a 1-cell-per-stratum synthetic design,
    C5 returned PASS with the CI ``[0.3349, 0.3349]`` -- a ZERO-WIDTH interval.
    With one cell and one task there is nothing to resample, so the bootstrap
    returns the planted constant every time and "excludes zero" is arithmetic,
    not power. That is the register's most-repeated shape: *a control that
    cannot fail*. So C5 now additionally requires

      * a **non-degenerate** interval (width > 0), and
      * enough resampling units to form one (>= 5 tasks and >= 5 episodes),

    and it reports a **SHUFFLE** control beside the plant: with the stratum
    labels permuted the interval must NOT exclude zero. A test that fires on
    everything is not evidence either.
    """
    pa = {k: v + planted for k, v in a.items()}
    tc = task_clustered_ci(pa, b, seed=seed)
    ec = episode_clustered_ci(pa, b, locmap, seed=seed)
    w_t = (None if tc["ci"][0] is None else tc["ci"][1] - tc["ci"][0])
    w_e = (None if ec["ci"][0] is None else ec["ci"][1] - ec["ci"][0])
    n_tasks = tc.get("n_tasks", 0)
    n_eps = ec.get("n_episodes", 0)
    nondegenerate = bool(w_t and w_t > 0 and w_e and w_e > 0
                         and n_tasks >= 5 and n_eps >= 5)

    # SHUFFLE control: permute the stratum labels over the UNPLANTED data.
    rng = np.random.default_rng(seed + 1)
    pooled = [(k, v, 0) for k, v in a.items()] + [(k, v, 1) for k, v in b.items()]
    labs = [g for _k, _v, g in pooled]
    rng.shuffle(labs)
    sa = {k: v for (k, v, _g), g2 in zip(pooled, labs) if g2 == 0}
    sb = {k: v for (k, v, _g), g2 in zip(pooled, labs) if g2 == 1}
    sh = task_clustered_ci(sa, sb, n_boot=2000, seed=seed)

    return {"_what": f"C5: with +{planted} planted on every bearing cell the "
                     f"interval MUST exclude zero -- and the interval must be "
                     f"NON-DEGENERATE, and a label SHUFFLE must NOT fire",
            "planted_effect": planted,
            "task_clustered": {"difference": tc["difference"], "ci": tc["ci"],
                               "ci_width": w_t,
                               "excludes_zero": tc["ci_excludes_zero"]},
            "episode_clustered": {"difference": ec["difference"], "ci": ec["ci"],
                                  "ci_width": w_e,
                                  "excludes_zero": ec["ci_excludes_zero"]},
            "nonvacuity": {"n_tasks": n_tasks, "n_episodes": n_eps,
                           "task_ci_width": w_t, "episode_ci_width": w_e,
                           "PASS": nondegenerate,
                           "_why": "a zero-width interval 'excludes zero' by "
                                   "arithmetic, not by power -- measured on a "
                                   "1-cell design, which passed the first "
                                   "version of this control"},
            "shuffle_control": {"difference": sh["difference"], "ci": sh["ci"],
                                "excludes_zero": sh["ci_excludes_zero"],
                                "must_not_exclude_zero": True,
                                "PASS": sh["ci_excludes_zero"] is False},
            "PASS": bool(tc["ci_excludes_zero"] and ec["ci_excludes_zero"]
                         and nondegenerate and sh["ci_excludes_zero"] is False)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_goldfree/cells.jsonl")
    ap.add_argument("--bearing-stratum", default="GF_BEARING")
    ap.add_argument("--control-stratum", default="GF_MATCHED_CONTROL")
    ap.add_argument("--screened-rows", type=Path,
                    default=REPO / "results/deltau_screened/cells.jsonl")
    ap.add_argument("--planted-effect", type=float, default=0.3349,
                    help="C5 plants the GOLD screen's own measured effect")
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_gold_free_effect.json")
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.rows.read_text().splitlines() if l.strip()]
    log(f"[rows] {len(rows)} from {args.rows.name}")
    cond = collections.Counter(r["condition_id"] for r in rows)
    if len(cond) != 1:
        raise SystemExit(f"rows span {len(cond)} conditions: {dict(cond)}")
    sess = collections.Counter(r["provenance"].get("session_id") for r in rows)
    if len(sess) != 1 or None in sess:
        raise SystemExit(f"rows span {len(sess)} sessions: {dict(sess)} -- defect #25")
    log(f"[guard] one condition {list(cond)[0]}, one session {list(sess)[0]}")

    locmap = {r["source_episode_metadata"]["memory_unit_locator"]:
              r["source_episode_id"] for r in rows}
    by_s = collections.defaultdict(list)
    for r in rows:
        by_s[r["provenance"]["stratum"]].append(r)
    log(f"[strata] { {k: len(v) for k, v in sorted(by_s.items())} }")

    unscorable = sum(1 for r in rows if r.get("delta_utility") is None)
    log(f"[scoring] {unscorable} rows unscorable (dU None) -- NEVER coerced to 0.0")

    bear = by_s.get(args.bearing_stratum, [])
    ctrl = by_s.get(args.control_stratum, [])
    if not bear or not ctrl:
        raise SystemExit(
            f"stratum {args.bearing_stratum!r} has {len(bear)} rows and "
            f"{args.control_stratum!r} has {len(ctrl)}; an empty stratum cannot "
            f"yield a contrast (it would be a number from no data)")
    # the DECIDING split
    bear_gf_only = [r for r in bear if not r["provenance"]["also_gold_bearing"]]
    bear_also_gold = [r for r in bear if r["provenance"]["also_gold_bearing"]]
    log(f"[deciding] GF_BEARING: {len(bear_gf_only)} rows gold-FREE, "
        f"{len(bear_also_gold)} rows also-gold-bearing")

    A, B = cell_means(bear), cell_means(ctrl)
    A_gf, = (cell_means(bear_gf_only),)
    res: dict[str, Any] = {
        "_what": "GF4 gold-free bearing-control effect",
        "_precommitment": "docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md",
        "rows_artifact": str(args.rows.relative_to(REPO)),
        "n_rows": len(rows), "condition_id": list(cond)[0],
        "session_id": list(sess)[0],
        "_session_policy": "both arms of every cell in ONE session (DEFECT #25)",
        "strata_row_counts": {k: len(v) for k, v in sorted(by_s.items())},
        "n_rows_unscorable_dU_none": unscorable,
        "_none_policy": "reward None means COULD NOT BE SCORED; never coerced to 0.0",
        "bearing_stratum": args.bearing_stratum,
        "control_stratum": args.control_stratum,
        "arm_rates": {
            args.bearing_stratum: arm_rates(bear),
            f"{args.bearing_stratum}_gold_free_only": arm_rates(bear_gf_only),
            f"{args.bearing_stratum}_also_gold_bearing": arm_rates(bear_also_gold),
            args.control_stratum: arm_rates(ctrl)},
    }

    res["both_arms_fail"] = {
        args.bearing_stratum: both_arms_fail(bear),
        f"{args.bearing_stratum}_gold_free_only": both_arms_fail(bear_gf_only),
        args.control_stratum: both_arms_fail(ctrl),
        "_why": "a stratum whose cells mostly fail under BOTH arms cannot express "
                "an effect. Compare against the screened run's strata: gold "
                "BEARING 0.525, RANDOM 0.701, MATCHED_CONTROL 0.788.",
    }
    log(f"[both-arms-fail] bearing(gold-free) "
        f"{res['both_arms_fail'][args.bearing_stratum+'_gold_free_only']['rate']:.3f} "
        f"control {res['both_arms_fail'][args.control_stratum]['rate']:.3f} "
        f"| screened gold BEARING 0.525, RANDOM 0.701")

    log("\n=== POOLED GF contrast (NOT the deciding quantity) ===")
    res["pooled_gf_bearing_vs_control"] = {
        "task_clustered": task_clustered_ci(A, B, seed=args.seed),
        "episode_clustered": episode_clustered_ci(A, B, locmap, seed=args.seed),
        "paired_by_memory": paired_by_memory(A, B, seed=args.seed),
        "_caveat": "pooled over gold-free AND also-gold-bearing cells. Reported "
                   "for completeness; the DECIDING quantity is the gold-free one.",
    }
    tc = res["pooled_gf_bearing_vs_control"]["task_clustered"]
    log(f"  diff {tc['difference']} CI {tc['ci']} excludes0={tc['ci_excludes_zero']}")

    log("\n=== 🔴 DECIDING: GF-BEARING ∧ ¬GOLD-BEARING vs matched control ===")
    dec_tc = task_clustered_ci(A_gf, B, seed=args.seed)
    dec_ec = episode_clustered_ci(A_gf, B, locmap, seed=args.seed)
    dec_pm = paired_by_memory(A_gf, B, seed=args.seed)
    c5 = positive_control_c5(A_gf, B, locmap, args.planted_effect, args.seed)
    res["DECIDING_gold_free_only_vs_control"] = {
        "_why_this_governs": "the executed screened cells were chosen BY THE GOLD "
                             "SCREEN, so a contrast including also-gold-bearing "
                             "cells partly re-measures it. These cells are "
                             "gold-free by construction.",
        "task_clustered": dec_tc, "episode_clustered": dec_ec,
        "paired_by_memory": dec_pm,
        "positive_control_C5": c5,
    }
    log(f"  n_cells bearing={dec_tc['n_cells_a']} control={dec_tc['n_cells_b']} "
        f"over {dec_tc['n_tasks']} tasks")
    log(f"  mean_bearing={dec_tc['mean_a']:.4f} mean_control={dec_tc['mean_b']:.4f}")
    log(f"  TASK-clustered diff {dec_tc['difference']:.4f} CI {dec_tc['ci']} "
        f"excludes0={dec_tc['ci_excludes_zero']}")
    log(f"  EPISODE-clustered diff {dec_ec['difference']:.4f} CI {dec_ec['ci']} "
        f"excludes0={dec_ec['ci_excludes_zero']}")
    log(f"  paired-by-memory {dec_pm.get('mean_paired_difference')} "
        f"CI {dec_pm.get('memory_bootstrap_ci')} "
        f"n={dec_pm.get('n_paired_memories')} nonzero={dec_pm.get('n_nonzero_contributors')}")
    log(f"  C5 positive control (plant +{args.planted_effect}): PASS={c5['PASS']}")

    # ---- the verdict, by the pre-committed rule ----
    detected = bool(dec_tc["ci_excludes_zero"])
    if not c5["PASS"]:
        verdict = "CANNOT_BE_BUILT_TO_A_COMPARABLE_STANDARD"
        why = ("the positive control FAILED: the test could not detect a planted "
               "gold-sized effect on these strata, so neither a positive nor a "
               "null result from it is interpretable")
    elif detected and dec_tc["difference"] > 0:
        verdict = "SURVIVES"
        why = ("the gold-free bearing-control contrast is positive with a "
               "task-clustered 95% CI excluding zero, on cells the gold screen "
               "does NOT select")
    elif detected and dec_tc["difference"] < 0:
        verdict = "SURVIVES_WITH_OPPOSITE_SIGN"
        why = "the CI excludes zero but the effect is NEGATIVE"
    else:
        verdict = "DISAPPEARS"
        why = ("the gold-free contrast's CI includes zero while C5 shows the test "
               "could have detected a gold-sized effect; the headline is "
               "conditional on answer-containment")
    res["VERDICT"] = verdict
    res["VERDICT_why"] = why
    res["_verdict_rule"] = ("fixed in docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md §7 "
                            "before the screen was run; all three outcomes "
                            "acceptable, none aimed for")
    log(f"\n{'='*70}\nVERDICT: {verdict}\n  {why}")

    # ---- the GOLD comparator, re-derived here rather than quoted ----
    srows = [json.loads(l) for l in
             args.screened_rows.read_text().splitlines() if l.strip()]
    sb = [r for r in srows if r["provenance"]["stratum"] == "BEARING"]
    sc = [r for r in srows if r["provenance"]["stratum"] == "MATCHED_CONTROL"]
    SA, SB = cell_means(sb), cell_means(sc)
    slm = {r["source_episode_metadata"]["memory_unit_locator"]: r["source_episode_id"]
           for r in srows}
    res["gold_comparator_rederived"] = {
        "_what": "the GOLD screen's own bearing-control effect, RE-DERIVED here "
                 "from the screened rows rather than quoted",
        "arm_rates_BEARING": arm_rates(sb),
        "task_clustered": task_clustered_ci(SA, SB, seed=args.seed),
        "episode_clustered": episode_clustered_ci(SA, SB, slm, seed=args.seed),
        "paired_by_memory": paired_by_memory(SA, SB, seed=args.seed),
        "_cross_session_caveat": "the screened run and the GF run are SEPARATE "
                                 "SESSIONS (DEFECT #25). Each contrast is "
                                 "internally session-matched; the two effects are "
                                 "compared in SIGN and SIGNIFICANCE, and a "
                                 "numeric difference between them would be "
                                 "confounded with the session.",
    }
    g = res["gold_comparator_rederived"]["task_clustered"]
    ar = res["gold_comparator_rederived"]["arm_rates_BEARING"]
    log(f"\n[gold comparator, re-derived] diff {g['difference']:.4f} CI {g['ci']}")
    log(f"  BEARING arms: WITH {ar['with_correct']}/{ar['n_scorable_rows']} "
        f"= {ar['with_rate']:.4f}; WITHOUT {ar['without_correct']}/"
        f"{ar['n_scorable_rows']} = {ar['without_rate']:.4f}")

    write_json_atomic(args.out, res)
    log(f"\n[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

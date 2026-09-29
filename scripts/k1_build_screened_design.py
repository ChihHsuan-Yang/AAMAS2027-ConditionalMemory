#!/usr/bin/env python3
"""K1: build the SCREENED three-stratum (memory, task) design. ZERO endpoint calls.

WHY THIS EXISTS
---------------
``docs/PAIRING_VERDICT.md``: ``select_pairs`` paired each memory with 8
same-domain questions chosen for ``question_type`` SPREAD, with **no
requirement that the memory bears on the question**. ~95% of cells had no
plausible relationship, and they diluted the measurement to nothing.

This screens candidate cells with J's DISCRIMINATIVE detector: the detector
must single THIS memory out of the same-domain pool (fire on at most
``--max-pool-hits`` of the ~865 web / ~1024 enterprise units). Content-only
-- memory text and gold answer -- so no reward enters and the strata are NOT
outcome-selected. No endpoint call is made.

THREE STRATA, labelled on every row
-----------------------------------
BEARING          detector fires on (m,t) AND t is discriminative.
MATCHED_CONTROL  SAME memory, SAME task family (question_type within domain),
                 detector SILENT. Holds memory and family fixed and varies
                 only bearing -- the contrast that makes "bearing" mean
                 something rather than "this memory is an easy one".
RANDOM           the ORIGINAL unscreened rule, so dilution is measured.

TWO DIFFERENT CONSTRAINTS BIND TWO DIFFERENT HEADLINES
------------------------------------------------------
*The flip rate* is bound by BEARING-TASKS-PER-MEMORY: a sign flip needs one
memory with two bearing cells of opposite sign. Measured here, not assumed:
of the 165 memories with any bearing task, **119 have exactly one**. Only 46
have >=2. No amount of compute changes that; it is the corpus's structure.

*The variance decomposition* is bound by MEMORIES-PER-TASK. The last fit was
NOT identified -- task and interaction ratios both pinned at the optimizer's
exp(12) clip (``results/ledgers/h_official_variance_decomposition.json``,
flags ``AT_UPPER_BOUNDARY``). The measured cause, re-derived from
``results/deltau_pilot/cells.jsonl``: **93 of its 220 tasks were seen by
exactly ONE memory.** A task with one memory carries no information
separating a task main effect from a memory x task interaction. So
POWER_ANALYSIS's "widen the task axis" is necessary but NOT sufficient -- the
tasks must be SHARED. The SHARED_GRID below gives every memory in a domain the
same task list, so each shared task is seen by ~30 memories.

Both are satisfied in one grid.

ONE UNIT PER TRAJECTORY IS *NOT* ENFORCED HERE -- AND THAT IS REPORTED
----------------------------------------------------------------------
The 46 >=2-bearing memories sit on only **23 distinct trajectories** (one
hosts 6). Enforcing one-unit-per-trajectory would cut the flip denominator to
23. Both denominators are therefore emitted: ``n_memories`` and
``n_source_episodes``. A Wilson CI over 46 memory units drawn from 23 episodes
is too narrow, and the analysis must say so rather than quietly pick one.

Reads artifacts, writes artifacts. No network.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402

UNITS = REPO / "data/manifests/lmev2_memory_units_small.jsonl"
LEAK = REPO / "data/manifests/lmev2_leakage_small.jsonl"


def log(m: str) -> None:
    print(m, flush=True)


def load_fire(units: list[dict]) -> dict[str, set[str]]:
    """task_id -> memory locators the detector fires on, over the FULL corpus.

    This is the precomputed audit of every one of the 1,889 units against every
    same-domain task. It is the POOL the discriminative screen needs: screening
    against only the 60 memories already used would make the pool 30x too small
    and the screen correspondingly too permissive.
    """
    fire: dict[str, set[str]] = collections.defaultdict(set)
    n = 0
    for line in LEAK.open():
        if not line.strip():
            continue
        d = json.loads(line)
        fire[d["task_id"]].add(d["memory_id"])
        n += 1
    unknown = set().union(*fire.values()) - {u["memory_unit_locator"] for u in units}
    if unknown:
        raise RuntimeError(f"leakage manifest names {len(unknown)} unknown locators")
    log(f"[leak-manifest] {n} fired cells over {len(fire)} tasks")
    return fire


def verify_manifest(units, tasks, fire, root: Path, n_units: int, seed: int) -> dict:
    """POSITIVE CONTROL: re-derive the manifest from RAW TEXT for sampled units.

    A precomputed manifest is an instrument. Stale, mis-keyed, or built against
    a different unit set, every stratum below would be wrong and nothing
    downstream would notice -- the run would produce a clean, false answer. So
    reload the trajectory text, re-run ``LK.detect`` over the FULL same-domain
    task list, and require exact agreement.

    The control is only informative if it COULD have failed, so the number of
    re-derived FIRES is asserted nonzero: an all-negative recomputation
    agreeing with an all-negative manifest proves nothing.
    """
    ok, ctrl = LK.controls_summary()
    if not ok:
        raise RuntimeError("leakage detector self-controls FAILED")
    log(f"[control] detector self-controls {sum(r.passed for r in ctrl)}/{len(ctrl)} PASS")

    uloc = {u["memory_unit_locator"]: u for u in units}
    samp = random.Random(seed).sample(sorted(uloc), n_units)
    need = {s.split(":")[0] for s in samp}
    texts: dict[str, str] = {}
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] not in need:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator in samp:
                texts[pv.memory_unit_locator] = pv.text
        if len(texts) >= len(samp):
            break
    if len(texts) != len(samp):
        raise RuntimeError(f"recovered text for {len(texts)}/{len(samp)} sampled units")

    by_dom = collections.defaultdict(list)
    for t in tasks.values():
        by_dom[t.domain].append(t)
    agree = dis = fires = 0
    examples = []
    for loc, txt in texts.items():
        for t in by_dom[uloc[loc]["domain"]]:
            got = bool(LK.detect(txt, t.answer,
                                 eval_function_spec=t.eval_function).any_leak)
            exp = loc in fire.get(t.id, ())
            fires += got
            if got == exp:
                agree += 1
            else:
                dis += 1
                if len(examples) < 5:
                    examples.append({"memory": loc, "task": t.id,
                                     "recomputed": got, "manifest": exp})
    log(f"[control] manifest re-derivation: {agree}/{agree+dis} agree, {fires} fires")
    if dis:
        raise RuntimeError(f"manifest disagrees with live recomputation on {dis} cells")
    if fires == 0:
        raise RuntimeError("manifest control recomputed ZERO fires: control is vacuous")
    return {"n_units_sampled": len(samp), "n_cells_checked": agree + dis,
            "n_agree": agree, "n_disagree": dis, "n_recomputed_fires": fires,
            "disagreement_examples": examples,
            "_why_fires_reported": "a control with zero positives cannot fail"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--max-pool-hits", type=int, default=8,
                    help="discriminative threshold; J's sweep key max_pool_hits<=8")
    ap.add_argument("--target-token-cap", type=int, default=20000,
                    help="max target-memory tokens. Content-blind size rule, fixed "
                         "before any outcome is seen.")
    ap.add_argument("--filler-lo", type=int, default=1500)
    ap.add_argument("--filler-hi", type=int, default=5000)
    ap.add_argument("--k-filler", type=int, default=4)
    ap.add_argument("--n-memories", type=int, default=60)
    ap.add_argument("--shared-tasks-per-domain", type=int, default=12)
    ap.add_argument("--random-per-memory", type=int, default=3)
    ap.add_argument("--reps-bearing", type=int, default=3)
    ap.add_argument("--reps-grid", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--verify-units", type=int, default=12)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--cells-out", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    args = ap.parse_args()

    units = [json.loads(l) for l in UNITS.read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    # LLM-judged questions are excluded: FutureTask.score() RAISES for them
    # rather than returning a default, and prereg section 2 prefers
    # deterministic scoring so F_judge is not confounded with the memory effect.
    det = {tid: t for tid, t in tasks.items() if t.deterministic}
    log(f"[input] {len(units)} units, {len(tasks)} tasks ({len(det)} deterministic)")
    fire = load_fire(units)
    control = verify_manifest(units, tasks, fire, args.root, args.verify_units, args.seed)

    pool_size = collections.Counter(u["domain"] for u in units)
    pool_hits = {tid: len(fire.get(tid, ())) for tid in det}
    disc = [tid for tid in det if 1 <= pool_hits[tid] <= args.max_pool_hits]
    bear_all: dict[str, list[str]] = collections.defaultdict(list)
    for tid in disc:
        for m in fire[tid]:
            bear_all[m].append(tid)
    for v in bear_all.values():
        v.sort()

    ge2_all = sorted([m for m, v in bear_all.items() if len(v) >= 2])
    scarcity = {
        "n_deterministic_tasks": len(det),
        "n_discriminative_tasks": len(disc),
        "frac_discriminative": len(disc) / len(det),
        "pool_size_per_domain": dict(pool_size),
        "n_memories_with_any_bearing_task": len(bear_all),
        "n_bearing_edges_total": sum(len(v) for v in bear_all.values()),
        "bearing_tasks_per_memory_histogram": dict(sorted(
            collections.Counter(len(v) for v in bear_all.values()).items())),
        "median_bearing_tasks_per_bearing_memory": sorted(
            len(v) for v in bear_all.values())[len(bear_all) // 2],
        "n_memories_with_ge2_bearing_tasks": len(ge2_all),
        "n_source_episodes_with_ge2_bearing_tasks": len(
            {uloc[m]["trajectory_id"] for m in ge2_all}),
        "_scarcity_is_the_finding":
            f"{len(disc)} of {len(det)} deterministic tasks ({len(disc)/len(det):.1%}) "
            f"are discriminative. Of the {len(bear_all)} memories bearing on ANY task, "
            f"the MEDIAN bears on exactly "
            f"{sorted(len(v) for v in bear_all.values())[len(bear_all)//2]}. The "
            f"detector was NOT widened to inflate this. A sign flip needs >=2 bearing "
            f"cells on one memory, so {len(ge2_all)} memory units -- on only "
            f"{len({uloc[m]['trajectory_id'] for m in ge2_all})} source episodes -- "
            f"is the CEILING on the flip denominator in this corpus.",
    }
    log(f"[screen] {len(disc)}/{len(det)} tasks discriminative; "
        f"{len(bear_all)} memories bear on >=1; {len(ge2_all)} bear on >=2 "
        f"(on {len({uloc[m]['trajectory_id'] for m in ge2_all})} episodes)")

    # ---- memory frame ----
    # Targets: all >=2-bearing memories under the token cap FIRST (the scarce
    # resource), then >=1-bearing, then non-bearing filler memories so the
    # RANDOM and MATCHED_CONTROL strata are not confined to bearing memories.
    cap = args.target_token_cap
    ge2 = [m for m in ge2_all if uloc[m]["n_tokens"] <= cap]
    dropped_cap = [m for m in ge2_all if uloc[m]["n_tokens"] > cap]
    eq1 = sorted([m for m, v in bear_all.items()
                  if len(v) == 1 and uloc[m]["n_tokens"] <= cap])
    log(f"[cap] target token cap {cap}: kept {len(ge2)}/{len(ge2_all)} of the "
        f">=2-bearing memories (dropped {len(dropped_cap)} on size alone)")

    # Filler trajectories must be disjoint from EVERY bearing trajectory, so
    # filler can never carry a bearing target's episode.
    bear_trajs = {uloc[m]["trajectory_id"] for m in bear_all}
    filler_units = [u for u in units
                    if args.filler_lo <= u["n_tokens"] <= args.filler_hi
                    and u["trajectory_id"] not in bear_trajs]
    filler_trajs = {u["trajectory_id"] for u in filler_units}
    filler_pool: dict[str, list[dict]] = collections.defaultdict(list)
    for u in filler_units:
        filler_pool[u["domain"]].append(u)
    for v in filler_pool.values():
        v.sort(key=lambda u: u["memory_unit_locator"])
    log(f"[filler] {len(filler_units)} units on {len(filler_trajs)} trajectories, "
        f"disjoint from all {len(bear_trajs)} bearing trajectories; "
        f"{ {d: len(v) for d, v in sorted(filler_pool.items())} }")

    chosen = list(ge2)
    rng = random.Random(f"{args.seed}:memories")
    for extra in (eq1, sorted(u["memory_unit_locator"] for u in units
                              if u["trajectory_id"] not in bear_trajs
                              and u["trajectory_id"] not in filler_trajs
                              and u["n_tokens"] <= cap)):
        pool = [m for m in extra if m not in set(chosen)]
        rng.shuffle(pool)
        for m in pool:
            if len(chosen) >= args.n_memories:
                break
            chosen.append(m)
    chosen.sort()
    n_ge2 = len([m for m in chosen if m in set(ge2)])
    log(f"[memories] {len(chosen)} targets: {n_ge2} with >=2 bearing tasks, "
        f"{len([m for m in chosen if m in set(eq1)])} with exactly 1, "
        f"{len(chosen) - n_ge2 - len([m for m in chosen if m in set(eq1)])} non-bearing; "
        f"{len({uloc[m]['trajectory_id'] for m in chosen})} distinct episodes")
    if set(chosen) & {u["memory_unit_locator"] for u in filler_units}:
        raise RuntimeError("a target memory is also in the filler pool")

    # ---- SHARED task pool per domain: the identifiability fix ----
    by_domfam: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for tid, t in det.items():
        by_domfam[(t.domain, t.question_type)].append(tid)
    for v in by_domfam.values():
        v.sort()
    shared: dict[str, list[str]] = {}
    for dom in sorted({uloc[m]["domain"] for m in chosen}):
        fams = sorted([f for (d, f) in by_domfam if d == dom])
        r = random.Random(f"{args.seed}:shared:{dom}")
        picked: list[str] = []
        while len(picked) < args.shared_tasks_per_domain:
            progressed = False
            for f in fams:
                if len(picked) >= args.shared_tasks_per_domain:
                    break
                bucket = [t for t in by_domfam[(dom, f)] if t not in picked]
                if bucket:
                    picked.append(r.choice(bucket))
                    progressed = True
            if not progressed:
                break
        shared[dom] = sorted(picked)
        log(f"[shared] {dom}: {len(picked)} tasks, families="
            f"{dict(collections.Counter(det[t].question_type for t in picked))}")

    # ---- assemble ----
    cells: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(m: str, tid: str, stratum: str, why: str, reps: int) -> bool:
        if (m, tid) in seen:
            return False
        seen.add((m, tid))
        t = det[tid]
        cells.append({
            "memory_id": uloc[m]["memory_id"],
            "memory_unit_locator": m,
            "trajectory_id": uloc[m]["trajectory_id"],
            "domain": uloc[m]["domain"],
            "memory_tokens": uloc[m]["n_tokens"],
            "task_id": tid,
            "question_type": t.question_type,
            "eval_name": t.eval_name,
            "stratum": stratum,
            "why_stratum": why,
            "detector_fires": m in fire.get(tid, ()),
            "task_pool_hits": pool_hits[tid],
            "task_pool_size": pool_size[t.domain],
            "n_bearing_tasks_for_this_memory": len(bear_all.get(m, [])),
            "replicates": reps,
        })
        return True

    for m in chosen:
        for tid in bear_all.get(m, []):
            add(m, tid, "BEARING",
                f"detector fires; task fires on {pool_hits[tid]} of "
                f"{pool_size[det[tid].domain]} same-domain memories",
                args.reps_bearing)

    # MATCHED CONTROL: same memory, same family, detector SILENT, one per
    # bearing cell so the two strata are size-matched per memory.
    for m in chosen:
        dom = uloc[m]["domain"]
        btids = bear_all.get(m, [])
        fams = sorted({det[t].question_type for t in btids}) or \
            sorted({det[t].question_type for t in shared[dom]})
        r = random.Random(f"{args.seed}:mc:{m}")
        want_per_fam = max(1, -(-max(1, len(btids)) // max(1, len(fams))))
        got = 0
        for f in fams:
            pool = [t for t in by_domfam[(dom, f)]
                    if m not in fire.get(t, ()) and (m, t) not in seen]
            r.shuffle(pool)
            for tid in pool[:want_per_fam]:
                if add(m, tid, "MATCHED_CONTROL",
                       f"same memory, same task family '{f}', detector SILENT",
                       args.reps_bearing):
                    got += 1
        if got == 0:
            raise RuntimeError(f"memory {m} got ZERO matched controls")

    # SHARED grid: carries the crossing. Labelled by what the detector actually
    # says, so a shared task that happens to bear is not mislabelled RANDOM.
    for m in chosen:
        for tid in shared[uloc[m]["domain"]]:
            if (m, tid) in seen:
                continue
            f = m in fire.get(tid, ())
            if f and 1 <= pool_hits[tid] <= args.max_pool_hits:
                add(m, tid, "BEARING", "shared-grid cell that also passes the screen",
                    args.reps_grid)
            else:
                add(m, tid, "RANDOM",
                    "shared-grid; " + (f"detector fires but task is NON-discriminative "
                                       f"({pool_hits[tid]} pool hits)" if f
                                       else "detector silent"),
                    args.reps_grid)

    # RANDOM extra: the ORIGINAL select_pairs rule -- per-memory independent
    # question_type-spread draws with no bearing requirement.
    for m in chosen:
        dom = uloc[m]["domain"]
        fams = sorted([f for (d, f) in by_domfam if d == dom])
        r = random.Random(f"{args.seed}:rand:{m}")
        r.shuffle(fams)
        got = 0
        for f in fams:
            if got >= args.random_per_memory:
                break
            pool = [t for t in by_domfam[(dom, f)] if (m, t) not in seen]
            if not pool:
                continue
            tid = r.choice(pool)
            fr = m in fire.get(tid, ())
            lab = ("BEARING" if fr and 1 <= pool_hits[tid] <= args.max_pool_hits
                   else "RANDOM")
            if add(m, tid, lab,
                   ("unscreened question_type-spread draw that happens to pass the screen"
                    if lab == "BEARING" else
                    "unscreened question_type-spread draw (the ORIGINAL select_pairs rule)"),
                   args.reps_grid):
                got += 1

    # ---- crossing structure, reported both ways ----
    per_mem = collections.Counter(c["memory_unit_locator"] for c in cells)
    per_task = collections.Counter(c["task_id"] for c in cells)
    strat = collections.Counter(c["stratum"] for c in cells)
    calls = sum(c["replicates"] for c in cells) * 2
    bear_cells = [c for c in cells if c["stratum"] == "BEARING"]
    bmem = collections.Counter(c["memory_unit_locator"] for c in bear_cells)

    design = {
        "n_cells": len(cells),
        "n_memories": len(per_mem),
        "n_source_episodes": len({c["trajectory_id"] for c in cells}),
        "n_tasks": len(per_task),
        "strata": dict(strat),
        "strata_memories": {s: len({c["memory_unit_locator"] for c in cells
                                    if c["stratum"] == s}) for s in strat},
        "strata_tasks": {s: len({c["task_id"] for c in cells
                                 if c["stratum"] == s}) for s in strat},
        "strata_replicates": {s: sorted({c["replicates"] for c in cells
                                         if c["stratum"] == s}) for s in strat},
        "tasks_per_memory": {
            "min": min(per_mem.values()), "max": max(per_mem.values()),
            "mean": sum(per_mem.values()) / len(per_mem),
            "histogram": dict(sorted(collections.Counter(per_mem.values()).items()))},
        "memories_per_task": {
            "min": min(per_task.values()), "max": max(per_task.values()),
            "mean": sum(per_task.values()) / len(per_task),
            "histogram": dict(sorted(collections.Counter(per_task.values()).items()))},
        "n_tasks_seen_by_1_memory": sum(1 for v in per_task.values() if v == 1),
        "n_tasks_seen_by_ge2_memories": sum(1 for v in per_task.values() if v >= 2),
        "n_tasks_seen_by_ge10_memories": sum(1 for v in per_task.values() if v >= 10),
        "flip_denominator_bearing": {
            "n_memories_with_ge2_bearing_cells_in_design":
                sum(1 for v in bmem.values() if v >= 2),
            "n_source_episodes_for_those": len(
                {c["trajectory_id"] for c in bear_cells
                 if bmem[c["memory_unit_locator"]] >= 2}),
            "_note": "a Wilson CI over memory units ignores that several units come "
                     "from one episode; BOTH denominators are reported and neither "
                     "is silently preferred.",
        },
        "planned_calls": calls,
        "_prior_design_for_contrast": {
            "n_tasks": 220, "n_tasks_seen_by_1_memory": 93,
            "tasks_per_memory": 8,
            "source": "results/deltau_pilot/cells.jsonl",
            "outcome": "AT_UPPER_BOUNDARY on task AND interaction (exp(12) clip)"},
    }
    log(f"\n[design] {len(cells)} cells, {len(per_mem)} memories "
        f"({design['n_source_episodes']} episodes), {len(per_task)} tasks")
    log(f"[design] strata {dict(strat)}")
    log(f"[design] tasks/memory min {min(per_mem.values())} max {max(per_mem.values())} "
        f"mean {sum(per_mem.values())/len(per_mem):.1f}")
    log(f"[design] memories/task min {min(per_task.values())} "
        f"max {max(per_task.values())} mean {sum(per_task.values())/len(per_task):.1f}")
    log(f"[design] tasks seen by 1 memory: {design['n_tasks_seen_by_1_memory']} "
        f"(was 93/220); by >=10: {design['n_tasks_seen_by_ge10_memories']}")
    log(f"[design] flip denominator: "
        f"{design['flip_denominator_bearing']['n_memories_with_ge2_bearing_cells_in_design']} "
        f"memories / "
        f"{design['flip_denominator_bearing']['n_source_episodes_for_those']} episodes")
    log(f"[design] PLANNED CALLS {calls} (budget {args.max_calls})")
    if calls > args.max_calls:
        raise SystemExit(f"planned {calls} calls exceeds budget {args.max_calls}")

    args.cells_out.parent.mkdir(parents=True, exist_ok=True)
    with args.cells_out.open("w") as fh:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    log(f"[wrote] {args.cells_out}")

    write_json_atomic(args.out, {
        "_what": "K1 screened three-stratum design. Content-only screen, ZERO endpoint calls.",
        "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "manifest_positive_control": control,
        "screening_yield_and_scarcity": scarcity,
        "target_token_cap_dropped_memories": {
            "n": len(dropped_cap),
            "locators": dropped_cap,
            "tokens": {m: uloc[m]["n_tokens"] for m in dropped_cap},
            "_rule": "content-blind size cap fixed before any outcome is seen; keeps "
                     "context near the ~27k length at which J's 22/22 needle control "
                     "certified the reader."},
        "shared_task_pool": shared,
        "filler": {"n_units": len(filler_units), "n_trajectories": len(filler_trajs),
                   "per_domain": {d: len(v) for d, v in sorted(filler_pool.items())},
                   "band": [args.filler_lo, args.filler_hi],
                   "_disjoint": "filler trajectories are disjoint from every "
                                "trajectory hosting any bearing memory"},
        "design": design,
        "cells_artifact": str(args.cells_out),
    })
    log(f"[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

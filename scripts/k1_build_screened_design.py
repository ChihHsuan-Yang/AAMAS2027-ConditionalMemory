#!/usr/bin/env python3
"""K1: build the SCREENED (memory, task) design. ZERO endpoint calls.

WHY THIS EXISTS
---------------
``docs/PAIRING_VERDICT.md``: ``select_pairs`` paired each memory with 8
same-domain questions chosen for ``question_type`` spread, with **no
requirement that the memory bears on the question**. ~95% of cells had no
plausible relationship and diluted the measurement to nothing.

This script screens candidate cells with J's DISCRIMINATIVE detector
(``scripts/j1b_discriminative_oracle.py``): the detector must single THIS
memory out of the same-domain pool. Content-only; no reward enters; no
endpoint call is made.

THREE STRATA, labelled on every row
-----------------------------------
BEARING          the discriminative detector fires on (m, t) AND t is
                 discriminative (fires on <= --max-pool-hits of the full
                 same-domain pool of 865/1024 memories).
MATCHED_CONTROL  SAME memory, SAME task family (question_type, within
                 domain), detector does NOT fire. This is the contrast that
                 makes "bearing" mean something: it holds memory and task
                 family fixed and varies only whether the memory bears.
RANDOM           the CURRENT unscreened rule -- same-domain, question_type
                 spread, no bearing requirement -- so the dilution effect is
                 measured rather than assumed.

IDENTIFIABILITY IS A DESIGN CHOICE HERE, NOT AN ANALYSIS HOPE
-------------------------------------------------------------
The last variance decomposition was NOT identified: task and interaction
ratios both pinned at the optimizer's exp(12) clip
(``results/ledgers/h_official_variance_decomposition.json``, flags
``AT_UPPER_BOUNDARY``). The measured reason, re-derived here from
``results/deltau_pilot/cells.jsonl``: **93 of its 220 tasks were seen by
exactly ONE memory.** A task observed by one memory carries no information
separating a task main effect from a memory x task interaction.

POWER_ANALYSIS says 120x16 beats 240x8 because the interaction is identified
by CELLS. That is necessary but not sufficient: the tasks must be SHARED. So
the RANDOM and MATCHED_CONTROL strata draw from a SMALL SHARED TASK POOL that
every memory in a domain is evaluated on, giving a densely crossed
memory x task grid. BEARING cells are added on top; they are intrinsically
sparse because bearing is a property of the (m,t) pair.

Reads artifacts, writes one artifact. No network.
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


def load_units() -> list[dict]:
    return [json.loads(l) for l in UNITS.read_text().splitlines() if l.strip()]


def load_fire(units: list[dict]) -> dict[str, set[str]]:
    """task_id -> set of memory locators the as-shipped detector fires on.

    This is the precomputed full audit: every one of the 1,889 units against
    every same-domain task. It is the POOL the discriminative screen needs --
    screening against only the 60 already-used memories would make the pool
    16x too small and the screen 16x too permissive.
    """
    fire: dict[str, set[str]] = collections.defaultdict(set)
    n = 0
    for line in LEAK.open():
        if not line.strip():
            continue
        d = json.loads(line)
        fire[d["task_id"]].add(d["memory_id"])
        n += 1
    known = {u["memory_unit_locator"] for u in units}
    bad = set().union(*fire.values()) - known
    if bad:
        raise RuntimeError(f"leakage manifest names {len(bad)} unknown memory locators")
    log(f"[leak-manifest] {n} fired cells over {len(fire)} tasks")
    return fire


def verify_manifest(units, tasks, fire, root: Path, n_units: int, seed: int) -> dict:
    """POSITIVE CONTROL: re-derive the manifest for a sample of units from RAW TEXT.

    A precomputed manifest is an instrument. If it were stale, mis-keyed, or
    built against a different unit set, every stratum below would be wrong and
    nothing downstream would notice -- the run would simply produce a clean,
    false answer. So: reload the trajectory text, re-run ``LK.detect`` over the
    FULL same-domain task list, and require exact agreement. The control is
    only informative if it could have failed, so the number of re-derived
    FIRES is reported too: an all-negative recomputation agreeing with an
    all-negative manifest proves nothing.
    """
    ok, ctrl = LK.controls_summary()
    if not ok:
        raise RuntimeError("leakage detector self-controls FAILED")
    log(f"[control] detector self-controls {sum(r.passed for r in ctrl)}/{len(ctrl)} PASS")

    uloc = {u["memory_unit_locator"]: u for u in units}
    rng = random.Random(seed)
    samp = rng.sample(sorted(uloc), n_units)
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
            got = bool(LK.detect(txt, t.answer, eval_function_spec=t.eval_function).any_leak)
            exp = loc in fire.get(t.id, ())
            fires += got
            if got == exp:
                agree += 1
            else:
                dis += 1
                if len(examples) < 5:
                    examples.append({"memory": loc, "task": t.id,
                                     "recomputed": got, "manifest": exp})
    out = {"n_units_sampled": len(samp), "n_cells_checked": agree + dis,
           "n_agree": agree, "n_disagree": dis,
           "n_recomputed_fires": fires, "disagreement_examples": examples,
           "_why_fires_reported": "a control with zero positives cannot fail"}
    log(f"[control] manifest re-derivation: {agree}/{agree+dis} agree, "
        f"{fires} recomputed fires")
    if dis:
        raise RuntimeError(f"leakage manifest disagrees with live recomputation on {dis} cells")
    if fires == 0:
        raise RuntimeError("manifest control recomputed ZERO fires: the control is vacuous")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--max-pool-hits", type=int, default=8,
                    help="discriminative threshold; J's sweep key max_pool_hits<=8")
    ap.add_argument("--tok-lo", type=int, default=500)
    ap.add_argument("--tok-hi", type=int, default=8000)
    ap.add_argument("--filler-trajs", type=int, default=12)
    ap.add_argument("--n-memories", type=int, default=60)
    ap.add_argument("--shared-tasks-per-domain", type=int, default=10,
                    help="size of the SHARED task pool per domain, used for "
                         "MATCHED_CONTROL and RANDOM so tasks are crossed")
    ap.add_argument("--random-per-memory", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--verify-units", type=int, default=12)
    ap.add_argument("--out", type=Path, default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--cells-out", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    args = ap.parse_args()

    units = load_units()
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    det_tasks = {tid: t for tid, t in tasks.items() if t.deterministic}
    log(f"[input] {len(units)} memory units, {len(tasks)} tasks "
        f"({len(det_tasks)} deterministic)")
    fire = load_fire(units)
    control = verify_manifest(units, tasks, fire, args.root, args.verify_units, args.seed)

    # ---- candidate memory frame: token band + disjoint filler reservation ----
    # Identical rule to run_deltau_pilot.sample_memories so the filler pool is a
    # pure function of task_id and the WITHOUT arm is constant across memories
    # (prereg section 2 / A1.4).
    elig = [u for u in units if args.tok_lo <= (u.get("n_tokens") or 0) <= args.tok_hi]
    by_traj = collections.defaultdict(list)
    for u in elig:
        by_traj[u["trajectory_id"]].append(u)
    dom_of = {t: v[0]["domain"] for t, v in by_traj.items()}
    rng = random.Random(args.seed)
    filler_trajs: set[str] = set()
    for d in sorted(set(dom_of.values())):
        ts = sorted([t for t in by_traj if dom_of[t] == d])
        rng.shuffle(ts)
        filler_trajs |= set(ts[: args.filler_trajs])
    cand = {u["memory_unit_locator"]: u for u in elig
            if u["trajectory_id"] not in filler_trajs}
    log(f"[frame] token band [{args.tok_lo},{args.tok_hi}]: {len(elig)} units; "
        f"{len(filler_trajs)} filler trajectories reserved; "
        f"{len(cand)} candidate target memories")

    # ---- the discriminative screen ----
    pool_hits = {tid: len(fire.get(tid, ())) for tid in det_tasks}
    pool_size = collections.Counter(u["domain"] for u in units)
    disc_tasks = [tid for tid in det_tasks if 1 <= pool_hits[tid] <= args.max_pool_hits]
    bearing_edges: dict[str, list[str]] = {}
    for tid in disc_tasks:
        ms = sorted(fire[tid] & set(cand))
        if ms:
            bearing_edges[tid] = ms
    bear_by_mem: dict[str, list[str]] = collections.defaultdict(list)
    for tid, ms in bearing_edges.items():
        for m in ms:
            bear_by_mem[m].append(tid)
    for v in bear_by_mem.values():
        v.sort()

    yield_report = {
        "n_deterministic_tasks": len(det_tasks),
        "pool_size_per_domain": dict(pool_size),
        "pool_hit_histogram_over_deterministic_tasks": dict(sorted(
            collections.Counter(
                "0" if pool_hits[t] == 0 else
                str(pool_hits[t]) if pool_hits[t] <= 3 else
                "4-5" if pool_hits[t] <= 5 else
                "6-8" if pool_hits[t] <= 8 else
                "9-12" if pool_hits[t] <= 12 else
                "13-30" if pool_hits[t] <= 30 else
                "31-100" if pool_hits[t] <= 100 else ">100"
                for t in det_tasks).items())),
        "n_discriminative_tasks_full_pool": len(disc_tasks),
        "n_discriminative_tasks_with_candidate_memory": len(bearing_edges),
        "n_bearing_memories": len(bear_by_mem),
        "n_bearing_cells_available": sum(len(v) for v in bearing_edges.values()),
        "bearing_tasks_per_memory_histogram": dict(sorted(
            collections.Counter(len(v) for v in bear_by_mem.values()).items())),
        "_scarcity_reading":
            f"only {len(disc_tasks)} of {len(det_tasks)} deterministic tasks "
            f"({len(disc_tasks)/len(det_tasks):.1%}) are discriminative at "
            f"<= {args.max_pool_hits} pool hits. Bearing is a property of the PAIR, "
            f"and naturally occurring memories bear on future tasks rarely. This "
            f"scarcity IS a finding and the detector was NOT widened to inflate it.",
    }
    log(f"[screen] {len(disc_tasks)}/{len(det_tasks)} deterministic tasks are "
        f"discriminative (<= {args.max_pool_hits} of pool)")
    log(f"[screen] BEARING: {sum(len(v) for v in bearing_edges.values())} cells, "
        f"{len(bear_by_mem)} memories, {len(bearing_edges)} tasks")

    # ---- choose the memory set: all bearing memories, then fill to N ----
    # Bearing memories are taken FIRST because they are the scarce resource.
    # The rest are drawn at random from the same candidate frame so the RANDOM
    # and MATCHED_CONTROL strata are not restricted to bearing memories --
    # otherwise every stratum would sit on a memory set selected for bearing.
    rng2 = random.Random(f"{args.seed}:memories")
    chosen: list[str] = []
    seen_traj: set[str] = set()
    for m in sorted(bear_by_mem, key=lambda m: (-len(bear_by_mem[m]), m)):
        # one unit per trajectory: N views of one episode is not N memories
        if cand[m]["trajectory_id"] in seen_traj:
            continue
        chosen.append(m)
        seen_traj.add(cand[m]["trajectory_id"])
    n_bearing_chosen = len(chosen)
    rest = sorted(set(cand) - set(chosen))
    rng2.shuffle(rest)
    for m in rest:
        if len(chosen) >= args.n_memories:
            break
        if cand[m]["trajectory_id"] in seen_traj:
            continue
        chosen.append(m)
        seen_traj.add(cand[m]["trajectory_id"])
    chosen.sort()
    log(f"[memories] {len(chosen)} chosen ({n_bearing_chosen} carry >=1 bearing cell, "
        f"{len(chosen)-n_bearing_chosen} non-bearing filler) from "
        f"{len(seen_traj)} distinct trajectories")

    # ---- SHARED task pool per domain, for crossing ----
    # THE identifiability fix. Every memory in a domain gets the SAME shared
    # tasks, so each task is observed by ~30 memories instead of 1.
    by_domfam = collections.defaultdict(list)
    for tid, t in det_tasks.items():
        by_domfam[(t.domain, t.question_type)].append(tid)
    for v in by_domfam.values():
        v.sort()
    shared: dict[str, list[str]] = {}
    for dom in sorted({cand[m]["domain"] for m in chosen}):
        fams = sorted([f for (d, f) in by_domfam if d == dom])
        rng3 = random.Random(f"{args.seed}:shared:{dom}")
        picked: list[str] = []
        rnd = 0
        while len(picked) < args.shared_tasks_per_domain:
            progressed = False
            for f in fams:
                if len(picked) >= args.shared_tasks_per_domain:
                    break
                bucket = [t for t in by_domfam[(dom, f)] if t not in picked]
                if not bucket:
                    continue
                picked.append(rng3.choice(bucket))
                progressed = True
            rnd += 1
            if not progressed:
                break
        shared[dom] = sorted(picked)
        log(f"[shared] {dom}: {len(picked)} shared tasks, families="
            f"{dict(collections.Counter(det_tasks[t].question_type for t in picked))}")

    # ---- assemble cells ----
    cells: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(m: str, tid: str, stratum: str, why: str) -> bool:
        if (m, tid) in seen:
            return False
        seen.add((m, tid))
        t = det_tasks[tid]
        cells.append({
            "memory_id": cand[m]["memory_id"],
            "memory_unit_locator": m,
            "trajectory_id": cand[m]["trajectory_id"],
            "domain": cand[m]["domain"],
            "task_id": tid,
            "question_type": t.question_type,
            "stratum": stratum,
            "why": why,
            "detector_fires": m in fire.get(tid, ()),
            "task_pool_hits": pool_hits[tid],
            "task_pool_size": pool_size[t.domain],
            "memory_tokens": cand[m]["n_tokens"],
        })
        return True

    # BEARING first (scarce)
    for m in chosen:
        for tid in bear_by_mem.get(m, []):
            add(m, tid, "BEARING",
                f"discriminative detector fires; task fires on {pool_hits[tid]} of "
                f"{pool_size[det_tasks[tid].domain]} same-domain memories")

    # MATCHED CONTROL: same memory, same family, detector silent.
    for m in chosen:
        dom = cand[m]["domain"]
        fams = sorted({det_tasks[t].question_type for t in bear_by_mem.get(m, [])})
        if not fams:
            # a non-bearing memory has no bearing family to match; use the
            # families of the shared pool so the stratum is not confined to
            # bearing memories.
            fams = sorted({det_tasks[t].question_type for t in shared[dom]})
        rng4 = random.Random(f"{args.seed}:mc:{m}")
        want = max(1, len(bear_by_mem.get(m, [])))
        got = 0
        for f in fams:
            pool = [t for t in by_domfam[(dom, f)]
                    if m not in fire.get(t, ()) and (m, t) not in seen]
            rng4.shuffle(pool)
            for tid in pool[:want]:
                if add(m, tid, "MATCHED_CONTROL",
                       f"same memory, same task family '{f}', detector SILENT"):
                    got += 1
        if got == 0:
            log(f"[warn] memory {m} got ZERO matched controls")

    # SHARED grid -> these carry the crossing. Labelled by whether the detector
    # fires, so a shared task that happens to bear is not mislabelled.
    for m in chosen:
        dom = cand[m]["domain"]
        for tid in shared[dom]:
            if (m, tid) in seen:
                continue
            fires = m in fire.get(tid, ())
            if fires and 1 <= pool_hits[tid] <= args.max_pool_hits:
                add(m, tid, "BEARING", "shared-grid cell that also passes the screen")
            elif fires:
                add(m, tid, "RANDOM",
                    f"shared-grid; detector fires but task is NON-discriminative "
                    f"({pool_hits[tid]} pool hits)")
            else:
                add(m, tid, "RANDOM", "shared-grid; detector silent, unscreened pairing")

    # RANDOM extra: reproduce the ORIGINAL unscreened rule (question_type spread,
    # no bearing requirement) so the dilution effect is measurable on its own terms.
    for m in chosen:
        dom = cand[m]["domain"]
        fams = sorted([f for (d, f) in by_domfam if d == dom])
        rng5 = random.Random(f"{args.seed}:rand:{m}")
        rng5.shuffle(fams)
        got = 0
        for f in fams:
            if got >= args.random_per_memory:
                break
            pool = [t for t in by_domfam[(dom, f)] if (m, t) not in seen]
            if not pool:
                continue
            tid = rng5.choice(pool)
            fires = m in fire.get(tid, ())
            lab = ("BEARING" if fires and 1 <= pool_hits[tid] <= args.max_pool_hits
                   else "RANDOM")
            why = ("unscreened question_type-spread draw that happens to pass the screen"
                   if lab == "BEARING" else
                   "unscreened question_type-spread draw (the ORIGINAL select_pairs rule)")
            if add(m, tid, lab, why):
                got += 1

    # ---- report the design's own crossing structure ----
    per_mem = collections.Counter(c["memory_unit_locator"] for c in cells)
    per_task = collections.Counter(c["task_id"] for c in cells)
    strat = collections.Counter(c["stratum"] for c in cells)
    strat_mem = {s: len({c["memory_unit_locator"] for c in cells if c["stratum"] == s})
                 for s in strat}
    strat_task = {s: len({c["task_id"] for c in cells if c["stratum"] == s})
                  for s in strat}
    design = {
        "n_cells": len(cells),
        "n_memories": len(per_mem),
        "n_tasks": len(per_task),
        "strata": dict(strat),
        "strata_memories": strat_mem,
        "strata_tasks": strat_task,
        "tasks_per_memory": {"min": min(per_mem.values()), "max": max(per_mem.values()),
                             "mean": sum(per_mem.values()) / len(per_mem)},
        "memories_per_task_histogram": dict(sorted(
            collections.Counter(per_task.values()).items())),
        "n_tasks_seen_by_1_memory": sum(1 for v in per_task.values() if v == 1),
        "n_tasks_seen_by_ge2_memories": sum(1 for v in per_task.values() if v >= 2),
        "n_tasks_seen_by_ge10_memories": sum(1 for v in per_task.values() if v >= 10),
        "_identifiability_note":
            "the last fit pinned task and interaction at the exp(12) clip. Measured "
            "cause: 93 of its 220 tasks were seen by exactly ONE memory. A task with "
            "one memory cannot separate a task main effect from an interaction. The "
            "shared task pool below is the fix; n_tasks_seen_by_ge10_memories is the "
            "number to check.",
    }
    log(f"\n[design] {len(cells)} cells, {len(per_mem)} memories, {len(per_task)} tasks")
    log(f"[design] strata: {dict(strat)}")
    log(f"[design] tasks/memory: min {min(per_mem.values())} "
        f"max {max(per_mem.values())} mean {sum(per_mem.values())/len(per_mem):.1f}")
    log(f"[design] tasks seen by 1 memory: {design['n_tasks_seen_by_1_memory']}; "
        f">=10 memories: {design['n_tasks_seen_by_ge10_memories']}")

    args.cells_out.parent.mkdir(parents=True, exist_ok=True)
    with args.cells_out.open("w") as fh:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    log(f"[wrote] {args.cells_out}")

    payload = {
        "_what": "K1 screened three-stratum design. Content-only screen, ZERO endpoint calls.",
        "config": {k: (str(v) if isinstance(v, Path) else v)
                   for k, v in vars(args).items()},
        "manifest_positive_control": control,
        "screening_yield": yield_report,
        "shared_task_pool": {d: v for d, v in shared.items()},
        "n_bearing_memories_chosen": n_bearing_chosen,
        "design": design,
        "cells_artifact": str(args.cells_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, payload)
    log(f"[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

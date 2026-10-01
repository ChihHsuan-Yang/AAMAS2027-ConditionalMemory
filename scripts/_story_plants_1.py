"""ORDER-2 PLANTS: isolate each CAPTION guard from the pinned cross-checks.

In plant_sp.py several plants fired, but the message shows they were caught by
an `expect(...)` pin on a count rather than by the caption guard they were
aimed at. A guard whose firing is always PREEMPTED by another check has not
been shown to work -- that is the exact reasoning scripts/verify_figure_guards
.py records for its own second order of plants.

So here `expect` is neutralised (it still prints, but never appends to FAIL).
Only the structural `if ...: FAIL.append(...)` caption guards can then fire,
and each plant must be caught by ITS OWN guard.

An UNPLANTED control runs first in every group: with expect() neutralised a
silent pass could otherwise mean the guards were switched off too.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path("/Users/bellayang/Documents/2026/p1_memory_utility/repo")
_spec = importlib.util.spec_from_file_location("mf", REPO / "scripts/make_figures.py")
mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mf)

RESULTS = []
_real_expect = mf.expect


def _quiet_expect(name, got, want, tol=5e-4):
    """Print, but NEVER fail. Isolates the caption guards."""
    return None


def _run(fn, patch_load=None, isolate=True):
    mf.FAIL.clear()
    real_load = mf.load
    if isolate:
        mf.expect = _quiet_expect
    if patch_load is not None:
        def fake_load(rel):
            rows = real_load(rel)
            out = patch_load(rel, rows)
            return rows if out is None else out
        mf.load = fake_load
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                fn()
            except Exception as exc:                     # noqa: BLE001
                return [f"raised {type(exc).__name__}: {exc}"]
        return list(mf.FAIL)
    finally:
        mf.load = real_load
        mf.expect = _real_expect


def record(name, fired, msg=""):
    RESULTS.append((name, bool(fired), msg))


print("=" * 72)
print("ORDER 2 -- expect() neutralised; ONLY the caption guard can fire")
print("=" * 72)

f = _run(mf.sparsity_map)
record("[0] UNPLANTED, guards isolated, still PASSES", not f, "; ".join(f))

# --- C-iso: THE PADDING TRAP, isolated. Widen RANDOM's per-memory block
# without adding any positives: the per-area reading falls while the
# per-drawn reading is untouched, which is exactly what padding does.
def plant_pad_area(rel, rows):
    """Give ONE memory a huge RANDOM block of measured zeros. max() sets the
    block width for every row, so the padded area explodes and the per-area
    ratio collapses -- the figure would still contain every correct value."""
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    victim = rows[0]["memory_id"]
    extra = []
    for i in range(400):
        r = copy.deepcopy(rows[0])
        r.update({"stratum": "RANDOM", "memory_id": victim,
                  "future_task_id": f"PADTASK{i:04d}",
                  "reward_with_memory": 0.0, "reward_without_memory": 0.0,
                  "replicate_id": 0})
        extra.append(r)
        r2 = copy.deepcopy(r)
        r2["replicate_id"] = 1
        extra.append(r2)
    return rows + extra

f = _run(mf.sparsity_map, patch_load=plant_pad_area)
record("[C-iso] the grid is PADDED: per-area and per-drawn readings converge",
       any("per-drawn-cell ratio" in x and "per-area" in x for x in f),
       "; ".join(f[:1]))

# --- SEP-iso: the stratum separation itself disappears, with every count pin
# switched off, so only the Wilson-disjointness guard can catch it.
def plant_no_separation(rel, rows):
    """Make every RANDOM cell positive. BEARING no longer sits above it."""
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        if r["stratum"] == "RANDOM" and r.get("reward_with_memory") is not None:
            r["reward_with_memory"], r["reward_without_memory"] = 1.0, 0.0
    return rows

f = _run(mf.sparsity_map, patch_load=plant_no_separation)
record("[SEP-iso] BEARING no longer separates from RANDOM",
       any("entirely above" in x for x in f), "; ".join(f[:1]))

# --- D-iso: a column COULD be a task. Keep the cell structure intact by
# giving BEARING exactly 5 distinct tasks against its 9-column width, without
# merging any cells (each memory keeps its own task count).
def plant_narrow_tasks(rel, rows):
    """RENAME bearing tasks onto a 5-task vocabulary instead of DROPPING rows.

    A first version dropped rows, which removed one memory's entire BEARING
    stratum and was caught by the pairing guard instead -- a plant that is
    preempted has not exercised the guard it was aimed at. Renaming keeps
    every memory in every stratum and every cell count intact, and changes
    ONLY the quantity this guard reads: the task span.
    """
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    # Rename WITHIN each memory only: a memory's k bearing cells become
    # tasks T0..T(k-1). Every memory keeps exactly its own cells (no two
    # collapse, so dU levels and counts are untouched), but the number of
    # DISTINCT task ids across the stratum falls to max-cells-per-memory = 9,
    # which is exactly the block width -- the condition the guard forbids.
    per_mem = {}
    for r in rows:
        if r["stratum"] != "BEARING":
            continue
        m = r["memory_id"]
        seen = per_mem.setdefault(m, {})
        if r["future_task_id"] not in seen:
            seen[r["future_task_id"]] = f"T{len(seen):02d}"
        r["future_task_id"] = seen[r["future_task_id"]]
    return rows

f = _run(mf.sparsity_map, patch_load=plant_narrow_tasks)
record("[D-iso] a block spans fewer tasks than it has columns",
       any("COULD be a task" in x for x in f), "; ".join(f[:1]))

# --- FOURTH-iso: a fourth dU level, with the pins off, must still be caught
# by the three-mark legend guard.
def plant_level(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        if r.get("reward_with_memory") is not None:
            r["reward_with_memory"] = 0.5
            r["reward_without_memory"] = 0.0
            break
    return rows

f = _run(mf.sparsity_map, patch_load=plant_level)
record("[LVL-iso] a FOURTH dU level, pins off",
       any("distinct values" in x for x in f), "; ".join(f[:1]))

print()
for n, fired, msg in RESULTS:
    ok = fired if not n.startswith("[0]") else fired
    print(f"  {'PASS' if (fired if not n.startswith('[0]') else fired) else 'FAIL'}  {n}")
    if msg:
        print(f"          -> {msg[:160]}")
bad = [n for n, fired, _ in RESULTS if not fired and not n.startswith("[0]")]
bad += [n for n, fired, _ in RESULTS if n.startswith("[0]") and not fired]
print()
if bad:
    print("A GUARD DID NOT FIRE:", bad)
    sys.exit(1)
print("every isolated caption guard fired on its own defect.")

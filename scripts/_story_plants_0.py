"""Plant every NEW guard's own defect and require the guard to FIRE.

Written by SA-FIGURE-STORY. A guard only ever observed PASSING is not known
to discriminate -- three of this project's recorded defects were in guards,
and one printed a correct verdict from an empty input. So each guard added
for the sparsity figure and the session-matched reader figure is exercised
here by planting the exact defect it exists to catch.

Every plant runs against a COPY of the rows/artifact in memory; nothing on
disk is modified. An UNPLANTED control runs first in each group, because a
"FAIL" from a broken harness is indistinguishable from a guard firing.

Run: /Users/bellayang/miniconda3/bin/python3 .sa_figstory/plant_sp.py
Exit 1 if any guard fails to fire on its own defect.
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

SCREENED = "results/ledgers/repro/screened_cells_slim.jsonl"
SMDIR = "results/ledgers/repro/raw_session_matched"

RESULTS: list[tuple[str, bool, str]] = []


def record(name, fired, msg=""):
    RESULTS.append((name, bool(fired), msg))


def _run(fn, patch_load=None, patch_read=None):
    """Run fn with `load` and/or Path.read_text patched, collecting FAIL."""
    mf.FAIL.clear()
    real_load = mf.load
    real_json_loads = json.loads

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
        json.loads = real_json_loads


# ---------------------------------------------------------------- sparsity
print("=" * 72)
print("SPARSITY MAP (fig 1b) -- plant each guard's own defect")
print("=" * 72)

f = _run(mf.sparsity_map)
record("[0] UNPLANTED sparsity run PASSES", not f, "; ".join(f))

# --- plant A: a FOURTH dU level appears. The figure draws three discrete
# marks and its legend names three; a continuous value must break it.
def plant_four_levels(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        if r.get("reward_with_memory") is not None:
            r["reward_with_memory"] = 0.5      # -> a cell mean of +0.5
            r["reward_without_memory"] = 0.0
            break
    return rows

f = _run(mf.sparsity_map, patch_load=plant_four_levels)
record("[A] a FOURTH dU level appears -- the three-mark legend is now wrong",
       any("distinct dU levels" in x or "distinct values" in x for x in f),
       "; ".join(f[:2]))

# --- plant B: replicates DISAGREE, so a cell mean lands between levels. This
# is the CAUSE of three-valuedness; the figure's premise, not just its values.
def plant_disagree(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    seen = {}
    for r in rows:
        k = (r["stratum"], r["memory_id"], r["future_task_id"])
        if r.get("reward_with_memory") is None:
            continue
        if k in seen:
            r["reward_with_memory"] = 1.0 - (seen[k] or 0.0)
            break
        seen[k] = r["reward_with_memory"]
    return rows

f = _run(mf.sparsity_map, patch_load=plant_disagree)
record("[B] replicates DISAGREE -- the cell mean leaves the three-level grid",
       any("replicates disagree" in x or "distinct dU levels" in x for x in f),
       "; ".join(f[:2]))

# --- plant C: THE PADDING TRAP. Make the per-memory widths equal across
# strata, which is what a padded redraw would do. The per-drawn and per-area
# readings then converge and the layout rationale is false.
def plant_padded(rel, rows):
    """Give RANDOM the same per-memory width as BEARING by dropping its
    extra cells. Area and drawn densities then coincide."""
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    # Keep BEARING's positives but flatten RANDOM so its rate matches.
    for r in rows:
        if r["stratum"] == "RANDOM" and r.get("reward_with_memory") is not None:
            r["reward_with_memory"] = 1.0
            r["reward_without_memory"] = 0.0
    return rows

f = _run(mf.sparsity_map, patch_load=plant_padded)
record("[C] RANDOM's positive rate rises to BEARING's -- the stratum "
       "separation the caption asserts is gone",
       any("entirely above" in x or "per DRAWN cell" in x
           or "no longer well above" in x for x in f),
       "; ".join(f[:2]))

# --- plant D: a stratum becomes narrow enough that a COLUMN COULD BE A TASK,
# which would make the caption's "a column is not a task" disclaimer false in
# the other direction -- the figure should then be redrawn on a task axis.
def plant_one_task(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    tasks = sorted({r["future_task_id"] for r in rows if r["stratum"] == "BEARING"})
    keep = set(tasks[:4])          # 4 tasks < the 9-column block width
    for r in rows:
        if r["stratum"] == "BEARING":
            r["future_task_id"] = sorted(keep)[hash(r["memory_id"]) % 4]
    return rows

f = _run(mf.sparsity_map, patch_load=plant_one_task)
record("[D] a block spans fewer tasks than it has columns -- a column COULD "
       "now be a task and the layout must be re-argued",
       any("COULD be a task" in x or "distinct tasks per stratum" in x
           for x in f),
       "; ".join(f[:2]))

# --- plant E: the rows carry more than one representation, so the figure is
# no longer one memory x task surface.
def plant_two_reps(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["memory_representation"] = "summary"
    return rows

f = _run(mf.sparsity_map, patch_load=plant_two_reps)
record("[E] a second representation enters the screened rows",
       any("representations" in x for x in f), "; ".join(f[:2]))

# --- plant F: a second READER enters.
def plant_two_readers(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["reader_model"] = "gemma-4-31B-it"
    return rows

f = _run(mf.sparsity_map, patch_load=plant_two_readers)
record("[F] a second READER enters the screened rows",
       any("readers" in x for x in f), "; ".join(f[:2]))

# --- plant G: a memory loses a stratum, so the three blocks stop being a
# within-memory paired comparison.
def plant_missing_stratum(rel, rows):
    if not rel.endswith("screened_cells_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    victim = rows[0]["memory_id"]
    return [r for r in rows
            if not (r["memory_id"] == victim and r["stratum"] == "BEARING")]

f = _run(mf.sparsity_map, patch_load=plant_missing_stratum)
record("[G] a memory is missing a stratum -- the blocks are no longer paired",
       any("missing a stratum" in x or "memories" in x for x in f),
       "; ".join(f[:2]))

print()
for n, fired, msg in RESULTS:
    print(f"  {'PASS' if fired or n.startswith('[0]') else 'FAIL'}  {n}")
    if msg:
        print(f"          -> {msg[:150]}")

bad = [n for n, fired, _ in RESULTS if not fired and not n.startswith("[0]")]
bad += [n for n, fired, _ in RESULTS if n.startswith("[0]") and not fired]
print()
if bad:
    print("A GUARD DID NOT FIRE:", bad)
    sys.exit(1)
print("every planted sparsity defect was caught.")

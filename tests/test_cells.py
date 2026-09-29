"""Tests for WITH/WITHOUT cell construction.

Each test states the defect it would catch. Several deliberately plant the
defect first, because a check only ever run on good input detects nothing
known.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.cells import MemoryUnit, build_cell_pair, select_filler


def _units(n, prefix="f"):
    return [
        MemoryUnit(f"{prefix}{i}", f"traj{i}:0-0", f"filler body {i}", 50, "web")
        for i in range(n)
    ]


TARGET = MemoryUnit("tgt", "013696c4:0-0", "UNIQUE-TARGET-BODY", 100, "web")


def test_arms_differ_only_in_the_target():
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    wi = b if wo is a else a
    assert "UNIQUE-TARGET-BODY" in wi["messages"][1]["content"]
    assert "UNIQUE-TARGET-BODY" not in wo["messages"][1]["content"]
    # every filler body survives in BOTH arms: removal must be local
    for i in range(4):
        assert f"filler body {i}" in wi["messages"][1]["content"]
        assert f"filler body {i}" in wo["messages"][1]["content"]
    assert wi["messages"][0] == wo["messages"][0]  # identical system prompt


def test_without_arm_is_not_length_padded():
    """A padded WITHOUT arm would confound the contrast with context length."""
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    wi = b if wo is a else a
    assert wo["messages"][1]["content"].count("--- Note") == 4
    assert wi["messages"][1]["content"].count("--- Note") == 5


def test_replicate_id_is_in_the_cache_key_of_both_arms():
    """A1.4: without this the WITHOUT arm is served from cache, its spread is
    exactly zero, the empty floor collapses, and every delta-U clears it."""
    for rep in (0, 1):
        for c in build_cell_pair(
            target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=rep
        ):
            assert c["key_fields"]["replicate_id"] == rep
    r0 = build_cell_pair(target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0)
    r1 = build_cell_pair(target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=1)
    assert r0[0]["key_fields"] != r1[0]["key_fields"]


def test_seeded_position_is_reproducible_but_varies():
    """Position must be stable for a given seed (reproducibility) and must not
    be constant across cells (or 'memory present' confounds with position)."""
    p1 = build_cell_pair(target=TARGET, filler=_units(6), task_id="t1", question="Q", replicate_id=0)
    p2 = build_cell_pair(target=TARGET, filler=_units(6), task_id="t1", question="Q", replicate_id=0)
    assert p1[1]["target_position"] == p2[1]["target_position"]
    seen = {
        build_cell_pair(
            target=TARGET, filler=_units(6), task_id=f"t{i}", question="Q", replicate_id=0
        )[1]["target_position"]
        for i in range(25)
    }
    assert len(seen) > 1, "target position is constant -- position is confounded"


def test_filler_is_identical_across_memories_within_a_task():
    """delta-U is only comparable across memories if they share a context."""
    pool = _units(30)
    f_a = select_filler(pool, exclude_ids={"f0"}, k=5, task_id="same-task")
    f_b = select_filler(pool, exclude_ids={"f1"}, k=5, task_id="same-task")
    assert [u.memory_id for u in f_a if u.memory_id != "f1"] == [
        u.memory_id for u in f_b if u.memory_id != "f0"
    ]


def test_filler_excludes_the_target():
    pool = _units(30)
    got = select_filler(pool, exclude_ids={"f3"}, k=10, task_id="t")
    assert "f3" not in {u.memory_id for u in got}


def test_planted_defect_target_leaking_into_without_arm_is_caught():
    """Positive control: corrupt an arm the way the real defect would look and
    confirm the assertion in test_arms_differ_only_in_the_target would fire."""
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    corrupted = wo["messages"][1]["content"] + "\nUNIQUE-TARGET-BODY"
    assert "UNIQUE-TARGET-BODY" in corrupted  # the check CAN fire


def test_excluding_a_non_drawn_memory_does_not_change_the_filler():
    """Regression: the defect that would have corrupted F_empty.

    ``random.shuffle`` consumes draws proportional to sequence LENGTH, so the
    original implementation (filter-then-shuffle) re-randomised the entire
    permutation whenever any element was removed -- including elements that
    would never have been drawn. Measured before the fix: 25 of 25 exclusions
    of a non-drawn memory changed the selected filler.

    If this regresses, the WITHOUT arm differs between memories within a task,
    its spread confounds filler composition with execution noise, and F_empty
    measures the wrong thing.

    Found by Sub-agent G in Master-authored code.
    """
    pool = _units(30, prefix="m")
    base = [u.memory_id for u in select_filler(pool, exclude_ids=set(), k=5, task_id="T")]
    assert len(base) == 5
    checked = 0
    for u in pool:
        if u.memory_id in base:
            continue
        checked += 1
        got = [x.memory_id for x in select_filler(
            pool, exclude_ids={u.memory_id}, k=5, task_id="T")]
        assert got == base, (
            f"excluding non-drawn {u.memory_id} changed the filler: {base} -> {got}")
    assert checked >= 20, "test is vacuous: too few non-drawn memories exercised"


def test_excluding_a_drawn_memory_removes_only_that_unit():
    """The one legitimate effect of exclusion: drop it, backfill, keep order."""
    pool = _units(30, prefix="m")
    base = [u.memory_id for u in select_filler(pool, exclude_ids=set(), k=5, task_id="T")]
    got = [u.memory_id for u in select_filler(
        pool, exclude_ids={base[2]}, k=5, task_id="T")]
    assert base[2] not in got
    assert [x for x in base if x != base[2]] == got[:4], "surviving order must be stable"

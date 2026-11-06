"""Synthetic-fixture tests for the fixed-total-context analysis.

These test the logic only.  They are not evidence about the real x2 run, whose rows are
not part of the public release (see docs/RELEASE_COVERAGE.md).
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("x2a", REPO / "scripts/x2_analyze_fixed_context.py")
x2a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(x2a)


def row(mem, task, ep, stratum, arm, w, o, rep=0):
    return {"memory_id": f"{mem}-{arm}", "future_task_id": task, "source_episode_id": ep,
            "source_episode_metadata": {"memory_unit_locator": mem},
            "reward_with_memory": w, "reward_without_memory": o, "replicate_id": rep,
            "provenance": {"arm": arm, "stratum": stratum}}


def fixture():
    rows = []
    for i in range(6):                                  # six independent bearing cells
        for arm, w in (("raw", 1.0), ("summary", 0.0), ("structured", 0.0), ("trunc_last_matched", 0.0)):
            for rep in (0, 1):
                rows.append(row(f"m{i}", f"t{i}", f"e{i}", "BEARING", arm, w, 0.0, rep))
    return rows


def test_arm_means_and_contrasts():
    res = x2a.analyze(fixture(), n_boot=200)
    e = res["excluding_exposed"]
    assert e["n_bearing_cells"] == 6
    assert e["arms"]["raw"]["mean"] == 1.0 and e["arms"]["summary"]["mean"] == 0.0
    assert e["contrasts"]["summary_minus_raw"]["mean"] == -1.0


def test_exposed_cells_are_excluded_from_headline_only():
    rows = fixture()
    # a second memory from episode e0 paired with task t0 -> both cells are cache-key exposed
    for arm in ("raw", "summary", "structured", "trunc_last_matched"):
        rows.append(row("m0b", "t0", "e0", "BEARING", arm, 1.0, 0.0))
    res = x2a.analyze(rows, n_boot=100)
    assert res["n_exposed_pairs"] == 2
    assert res["excluding_exposed"]["n_bearing_cells"] == 5
    assert res["including_exposed"]["n_bearing_cells"] == 7


def test_missing_reward_is_dropped_not_zeroed():
    rows = fixture()
    rows.append(row("m0", "t0", "e0", "BEARING", "raw", None, 0.0, rep=2))
    cells = x2a.build_cells(rows)
    assert cells[("m0", "t0")]["arms"]["raw"] == 1.0   # unchanged: the None row did not add a zero


def test_counts_verdict_flags_a_mismatch():
    assert x2a.analyze(fixture(), n_boot=50)["counts_match_paper"] is False


def test_arms_with_different_memory_ids_still_form_one_cell():
    # Summary/Structured have their own memory_id; they must join the Raw cell, not split it.
    cells = x2a.build_cells(fixture())
    assert len(cells) == 6 and set(cells[("m0", "t0")]["arms"]) == set(x2a.ARMS)

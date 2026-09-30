"""Tests for the SWE-bench Verified adapter.

Two things these tests are FOR, beyond ordinary coverage:

1. **Pinning the selection verdict to the code.** The numbers in
   ``docs/SWEBENCH_FEASIBILITY.md`` justified replacing BEAM. They were first
   computed ad hoc, then again through the adapter. ``test_reproduces_*``
   asserts the adapter agrees, so a refactor that changes the pairing rule
   fails loudly instead of quietly invalidating the verdict.

2. **Proving the edit applier can fail.** Per the project rule, a checker only
   ever run on inputs it passes has not been shown to detect anything. The
   ``test_apply_edits_*`` cases plant absent and ambiguous search text and
   assert the applier REFUSES, and distinguish "no block" from "search miss".

Tests that need the 500-row parquet skip when it is absent, so the suite stays
runnable on a machine without the download; the pure-logic tests always run.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from p1mem.adapters.swebench import (
    COPYLEFT_REPOS,
    DATASET_N_ROWS,
    DATASET_SHA256,
    EditResult,
    FutureIssue,
    Relatedness,
    SolvedIssue,
    UPSTREAM_LICENSES,
    apply_edits,
    assert_writer_blind,
    build_future_tasks,
    build_memory_units,
    candidate_pairs,
    multi_task_report,
    parse_patch_files,
    parse_search_replace,
    render_raw_memory,
    select_pairs,
    structured_skeleton,
)

PARQUET = Path("/tmp/swebench/swebv.parquet")

#: Measured independently of this module on 2026-09-30, then reproduced
#: through it. (pairs, memories with >=2 recipients) per relatedness level.
MEASURED: dict[Relatedness, tuple[int, int]] = {
    Relatedness.REPO: (32050, 477),
    Relatedness.PACKAGE: (10160, 371),
    Relatedness.DIRECTORY: (3202, 316),
    Relatedness.FILE: (644, 133),
}

BEAM_PCT_DIAGONAL = 92.6


# --------------------------------------------------------------------------
# fixtures -- small hand-built rows, so the logic tests need no download
# --------------------------------------------------------------------------

def _row(iid, repo, when, path, added="x = 1", stmt="something is broken"):
    patch = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -1,1 +1,2 @@\n context\n+{added}\n"
    )
    return {
        "instance_id": iid, "repo": repo, "problem_statement": stmt,
        "patch": patch, "test_patch": "", "base_commit": "deadbeef",
        "created_at": when, "version": "1.0",
        "FAIL_TO_PASS": json.dumps(["test_a"]),
        "PASS_TO_PASS": json.dumps(["test_b", "test_c"]),
    }


@pytest.fixture
def toy_rows():
    return [
        _row("r-1", "acme/lib", "2020-01-01T00:00:00Z", "acme/core/mod.py"),
        _row("r-2", "acme/lib", "2021-01-01T00:00:00Z", "acme/core/mod.py"),
        _row("r-3", "acme/lib", "2022-01-01T00:00:00Z", "acme/core/other.py"),
        _row("r-4", "other/proj", "2022-06-01T00:00:00Z", "other/a.py"),
    ]


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def test_parse_patch_files_reads_post_image_paths():
    p = ("diff --git a/x/a.py b/x/a.py\n--- a/x/a.py\n+++ b/x/a.py\n"
         "diff --git a/x/b.py b/x/b.py\n--- a/x/b.py\n+++ b/x/b.py\n")
    assert parse_patch_files(p) == ("x/a.py", "x/b.py")


def test_parse_patch_files_empty_is_empty_not_error():
    assert parse_patch_files("") == ()
    assert parse_patch_files(None) == ()


def test_created_at_must_parse_rather_than_default():
    """A silent default would invert past/future ordering -- the one property
    the whole design rests on."""
    bad = _row("r-x", "acme/lib", "", "a.py")
    with pytest.raises(ValueError):
        build_memory_units([bad])


def test_test_lists_decode_from_json_strings():
    t = build_future_tasks([_row("r-1", "acme/lib", "2020-01-01T00:00:00Z", "a.py")])[0]
    assert t.fail_to_pass == ("test_a",)
    assert t.pass_to_pass == ("test_b", "test_c")
    assert t.deterministic is True


# --------------------------------------------------------------------------
# pairing
# --------------------------------------------------------------------------

def test_pairs_are_strictly_time_ordered(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    for p in candidate_pairs(mems, tasks, relatedness=Relatedness.REPO):
        assert p.donor_created_at < p.recipient_created_at


def test_no_self_pairs(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    for p in candidate_pairs(mems, tasks, relatedness=Relatedness.REPO):
        assert p.memory_id != p.task_id


def test_no_cross_repo_pairs(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    for p in candidate_pairs(mems, tasks, relatedness=Relatedness.REPO):
        assert p.repo == "acme/lib"  # other/proj cannot pair with acme/lib


def test_relatedness_levels_are_nested(toy_rows):
    """FILE subset of DIRECTORY subset of PACKAGE subset of REPO."""
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    sets = {}
    for lvl in Relatedness:
        sets[lvl] = {(p.memory_id, p.task_id)
                     for p in candidate_pairs(mems, tasks, relatedness=lvl)}
    assert sets[Relatedness.FILE] <= sets[Relatedness.DIRECTORY]
    assert sets[Relatedness.DIRECTORY] <= sets[Relatedness.PACKAGE]
    assert sets[Relatedness.PACKAGE] <= sets[Relatedness.REPO]
    # and the levels are genuinely different, or the test is vacuous
    assert sets[Relatedness.FILE] != sets[Relatedness.REPO]


def test_copyleft_excluded_by_default():
    rows = [
        _row("p-1", "pylint-dev/pylint", "2020-01-01T00:00:00Z", "pylint/a.py"),
        _row("p-2", "pylint-dev/pylint", "2021-01-01T00:00:00Z", "pylint/a.py"),
    ]
    mems = build_memory_units(rows)
    tasks = build_future_tasks(rows)
    assert candidate_pairs(mems, tasks, exclude_copyleft=True) == []
    assert len(candidate_pairs(mems, tasks, exclude_copyleft=False)) == 1


def test_select_pairs_is_deterministic_given_seed(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    a = select_pairs(mems, tasks, seed=7, relatedness=Relatedness.REPO,
                     min_tasks_per_memory=1)
    b = select_pairs(mems, tasks, seed=7, relatedness=Relatedness.REPO,
                     min_tasks_per_memory=1)
    assert [p.as_row() for p in a] == [p.as_row() for p in b]


def test_min_tasks_per_memory_enforces_the_multitask_axis(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    kept = select_pairs(mems, tasks, seed=1, relatedness=Relatedness.REPO,
                        min_tasks_per_memory=2)
    counts: dict[str, int] = {}
    for p in kept:
        counts[p.memory_id] = counts.get(p.memory_id, 0) + 1
    assert counts, "fixture should yield at least one multi-task memory"
    assert all(v >= 2 for v in counts.values())


def test_writer_blindness_signature_takes_no_task():
    """Structural guarantee: build_memory_units cannot receive a future task."""
    import inspect
    sig = inspect.signature(build_memory_units)
    assert list(sig.parameters) == ["rows"]


def test_assert_writer_blind_passes_on_consistent_data(toy_rows):
    mems = build_memory_units(toy_rows)
    tasks = build_future_tasks(toy_rows)
    assert_writer_blind(mems, tasks)  # must not raise


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def test_raw_memory_contains_statement_and_patch_and_no_future(toy_rows):
    m = build_memory_units(toy_rows)[0]
    text = render_raw_memory(m)
    assert "something is broken" in text
    assert "diff" in text
    assert "r-2" not in text and "r-3" not in text


def test_structured_skeleton_is_free_of_model_calls(toy_rows):
    rows = [_row("s-1", "acme/lib", "2020-01-01T00:00:00Z", "acme/core/mod.py",
                 added="def helper(self):")]
    m = build_memory_units(rows)[0]
    sk = structured_skeleton(m)
    assert sk["files_touched"] == ["acme/core/mod.py"]
    assert sk["symbols_added"] == ["helper"]
    assert sk["n_added_lines"] == 1


# --------------------------------------------------------------------------
# SEARCH/REPLACE -- and proving the applier can FAIL
# --------------------------------------------------------------------------

SRC = "def f():\n    return 1\n\ndef g():\n    return 2\n"


def _block(search, replace):
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"


def test_apply_edits_applies_an_exact_match():
    r = apply_edits(SRC, _block("    return 1", "    return 42"))
    assert r.applied and r.n_applied == 1
    assert "return 42" in r.new_text
    assert r.failure_mode == "ok"


def test_apply_edits_refuses_absent_search_text():
    """POSITIVE CONTROL for failure: text that is not in the source."""
    r = apply_edits(SRC, _block("    return 999", "    return 42"))
    assert not r.applied and r.n_blocks == 1
    assert r.new_text is None
    assert r.failure_mode == "search_miss"
    assert any("absent" in m for m in r.misses)


def test_apply_edits_refuses_ambiguous_search_text():
    """An ambiguous match applied to the first hit would edit the wrong code."""
    src = "x = 1\nx = 1\n"
    r = apply_edits(src, _block("x = 1", "x = 2"))
    assert not r.applied
    assert any("ambiguous" in m for m in r.misses)


def test_no_block_and_search_miss_are_distinguishable():
    """A floor-effect diagnosis needs format failure apart from wrong-location."""
    no_block = apply_edits(SRC, "I think you should change return 1 to return 42")
    miss = apply_edits(SRC, _block("    return 999", "    return 42"))
    assert no_block.failure_mode == "no_block"
    assert miss.failure_mode == "search_miss"
    assert no_block.failure_mode != miss.failure_mode


def test_parse_tolerates_marker_length_variation():
    resp = "<<<<<<<< SEARCH\na\n========\nb\n>>>>>>>> REPLACE"
    assert parse_search_replace(resp) == [("a", "b")]


def test_multiple_blocks_apply_in_order():
    resp = _block("    return 1", "    return 10") + "\n" + _block("    return 2", "    return 20")
    r = apply_edits(SRC, resp)
    assert r.n_applied == 2
    assert "return 10" in r.new_text and "return 20" in r.new_text


# --------------------------------------------------------------------------
# the selection verdict, pinned to the real 500-row dataset
# --------------------------------------------------------------------------

requires_parquet = pytest.mark.skipif(
    not PARQUET.exists(), reason=f"{PARQUET} not downloaded")


@pytest.fixture(scope="module")
def real_rows():
    import pyarrow.parquet as pq
    return pq.read_table(str(PARQUET)).to_pylist()


@requires_parquet
def test_dataset_shape_matches_provenance(real_rows):
    assert len(real_rows) == DATASET_N_ROWS


@requires_parquet
def test_dataset_sha256_matches_recorded_provenance():
    import hashlib
    h = hashlib.sha256(PARQUET.read_bytes()).hexdigest()
    assert h == DATASET_SHA256


@requires_parquet
@pytest.mark.parametrize("level", list(Relatedness))
def test_reproduces_the_measured_pair_counts(real_rows, level):
    """The numbers that justified dropping BEAM, re-derived through the adapter."""
    mems = build_memory_units(real_rows)
    tasks = build_future_tasks(real_rows)
    pairs = candidate_pairs(mems, tasks, relatedness=level, exclude_copyleft=False)
    rep = multi_task_report(pairs)
    exp_pairs, exp_multi = MEASURED[level]
    assert rep["n_pairs"] == exp_pairs
    assert rep["memories_with_ge2_tasks"] == exp_multi


@requires_parquet
def test_beats_beam_on_diagonality_at_every_level(real_rows):
    """The whole reason this benchmark replaced BEAM."""
    mems = build_memory_units(real_rows)
    tasks = build_future_tasks(real_rows)
    for level in Relatedness:
        rep = multi_task_report(
            candidate_pairs(mems, tasks, relatedness=level, exclude_copyleft=False))
        assert rep["pct_diagonal"] < BEAM_PCT_DIAGONAL, level


@requires_parquet
def test_every_repo_has_a_recorded_upstream_licence(real_rows):
    repos = {r["repo"] for r in real_rows}
    assert repos <= set(UPSTREAM_LICENSES), repos - set(UPSTREAM_LICENSES)


@requires_parquet
def test_copyleft_exclusion_costs_little(real_rows):
    """Excluding GPL must stay cheap, or the release posture changes."""
    mems = build_memory_units(real_rows)
    tasks = build_future_tasks(real_rows)
    with_gpl = len(candidate_pairs(mems, tasks, relatedness=Relatedness.DIRECTORY,
                                   exclude_copyleft=False))
    without = len(candidate_pairs(mems, tasks, relatedness=Relatedness.DIRECTORY,
                                  exclude_copyleft=True))
    assert with_gpl > without  # exclusion must actually bind
    assert (with_gpl - without) / with_gpl < 0.01


@requires_parquet
def test_all_timestamps_distinct_so_ordering_is_total(real_rows):
    mems = build_memory_units(real_rows)
    assert len({m.created_at for m in mems}) == len(mems)

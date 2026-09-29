"""D1 tests -- the three noise floors.

Every test here either recovers a PLANTED value or proves the estimator refuses to
produce a number it cannot support. A floor that silently reads 0.0 when nothing was
measured would be cleared by every effect in the paper, so the refusals are tested at
least as hard as the recoveries.
"""
from __future__ import annotations

import math

import pytest

from p1mem.analysis import noise
from p1mem.analysis.common import HeterogeneousPoolError
from p1mem.analysis.synthetic import make_dataset, inject_errors


# ------------------------------------------------------------------ F_exec recovery
def test_exec_floor_recovers_planted_with_arm_noise():
    ds = make_dataset(seed=11, sd_exec_with=0.10, sd_exec_without=0.08)
    est = noise.exec_floor(ds.rows, scale="with", n_boot=300)
    assert est.point == pytest.approx(0.10, abs=0.02)
    assert est.ci_lower <= 0.10 <= est.ci_upper


def test_exec_floor_recovers_planted_delta_scale_noise():
    """On the dU scale the planted SD is sqrt(sd_with^2 + sd_without^2), not either one."""
    ds = make_dataset(seed=12, sd_exec_with=0.10, sd_exec_without=0.08)
    truth = math.sqrt(0.10 ** 2 + 0.08 ** 2)
    est = noise.exec_floor(ds.rows, scale="delta", n_boot=300)
    assert est.point == pytest.approx(truth, abs=0.02)
    assert est.scale == "delta"


def test_exec_floor_tracks_a_doubled_noise_level():
    """A floor estimator that ignored its input would pass a single-point test."""
    a = noise.exec_floor(make_dataset(seed=13, sd_exec_with=0.05).rows,
                         scale="with", n_boot=1).point
    b = noise.exec_floor(make_dataset(seed=13, sd_exec_with=0.20).rows,
                         scale="with", n_boot=1).point
    assert b / a == pytest.approx(4.0, rel=0.25)


def test_exec_floor_is_unmeasured_not_zero_without_replicates():
    ds = make_dataset(seed=14, n_replicates=1)
    est = noise.exec_floor(ds.rows, n_boot=50)
    assert est.point is None, "a floor with no repeated cells must not be a number"
    assert any(f.startswith("NOT_MEASURED") for f in est.flags)


def test_exec_floor_refuses_to_pool_across_clusters():
    ds = make_dataset(seed=15)
    rows = [dict(r) for r in ds.rows]
    for r in rows[: len(rows) // 2]:
        r["reader_cluster"] = "sophia"
    with pytest.raises(HeterogeneousPoolError):
        noise.exec_floor(rows, n_boot=10)
    est = noise.exec_floor(rows, n_boot=10, allow_pooling=True)
    assert any(f.startswith("POOLED_ACROSS_IDENTITY") for f in est.flags)


def test_errored_rows_are_excluded_and_counted():
    ds = inject_errors(make_dataset(seed=16), 30)
    est = noise.exec_floor(ds.rows, n_boot=20)
    assert est.extra["admission"]["n_errored"] == 30
    assert est.n_obs == len(ds.rows) - 30


# ----------------------------------------------------------------- F_empty: THE test
def test_empty_floor_recovers_the_injected_without_arm_variance():
    """D1's key property: the WITHOUT arm is one condition, so its spread IS a floor.

    Rows are built so the WITHOUT arm genuinely is the identical condition for every
    memory on a given task, independently executed per cell with a KNOWN injected SD.
    The estimator must recover that SD.
    """
    truth = 0.13
    ds = make_dataset(seed=17, sd_exec_without=truth, n_memories=30, n_tasks=6)
    est = noise.empty_floor(ds.rows, n_boot=400)
    assert est.point == pytest.approx(truth, abs=0.02)
    assert est.ci_lower <= truth <= est.ci_upper
    assert est.extra["n_groups_excluded_as_reused"] == 0


@pytest.mark.parametrize("truth", [0.05, 0.10, 0.25])
def test_empty_floor_tracks_the_injected_level(truth):
    ds = make_dataset(seed=18, sd_exec_without=truth, n_memories=30)
    assert noise.empty_floor(ds.rows, n_boot=1).point == pytest.approx(truth, rel=0.20)


def test_empty_floor_agrees_with_exec_floor_on_the_without_arm():
    """Two routes to the same quantity: across memories, and across replicates.

    They estimate the same thing, so a large disagreement means one of them is wrong.
    """
    ds = make_dataset(seed=19, sd_exec_without=0.11, n_memories=30)
    a = noise.empty_floor(ds.rows, n_boot=1).point
    b = noise.exec_floor(ds.rows, scale="without", n_boot=1).point
    assert a == pytest.approx(b, rel=0.15)


def test_empty_floor_refuses_a_cached_without_arm():
    """The free floor is only free if the arm was really re-executed.

    A harness that generates the no-memory answer once per task and copies it gives a
    spread of exactly 0 -- an apparent perfect floor that every effect clears. The
    estimator must refuse rather than report 0.0.
    """
    ds = make_dataset(seed=20, cache_without_arm=True)
    est = noise.empty_floor(ds.rows, n_boot=50)
    assert est.point is None
    assert any(noise.EMPTY_ARM_REUSED in f for f in est.flags)
    assert est.extra["n_groups_excluded_as_reused"] > 0


def test_empty_floor_can_be_told_to_measure_a_cached_arm_and_gets_zero():
    """Proves the guard, not the data, is what produced the refusal above."""
    ds = make_dataset(seed=21, cache_without_arm=True)
    est = noise.empty_floor(ds.rows, n_boot=1, require_independent_execution=False)
    assert est.point == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------- F_judge
def test_judge_floor_is_unmeasured_when_nothing_is_byte_identical():
    ds = make_dataset(seed=22)
    for i, r in enumerate(ds.rows):
        r["output_with_memory"] = f"unique-with-{i}"
        r["output_without_memory"] = f"unique-without-{i}"
    est = noise.judge_floor(ds.rows, n_boot=20)
    assert est.point is None
    assert any(f.startswith("NOT_MEASURED") for f in est.flags)


def test_judge_floor_detects_a_planted_rescoring_disagreement():
    """Plant a known disagreement rate and confirm the estimator recovers it."""
    ds = make_dataset(seed=23)
    rows = ds.rows[:100]
    rescored = {}
    n_flip = 20
    for i, r in enumerate(rows):
        w = float(r["reward_with_memory"])
        wo = float(r["reward_without_memory"])
        if i < n_flip:
            w = w + 1.0  # the scorer returned something different on identical bytes
        rescored[r["row_id"]] = {"reward_with_memory": w, "reward_without_memory": wo}
    est = noise.judge_floor(rows, rescored, n_boot=200)
    # 200 comparisons (2 arms x 100 rows), 20 of which disagree.
    assert est.point == pytest.approx(n_flip / 200.0, abs=0.02)
    assert est.extra["n_disagreements"] == n_flip
    assert any(f.startswith("NONZERO_JUDGE_FLOOR") for f in est.flags)


def test_judge_floor_is_zero_when_a_rescore_is_exactly_reproducible():
    ds = make_dataset(seed=24)
    rows = ds.rows[:60]
    rescored = {r["row_id"]: {"reward_with_memory": r["reward_with_memory"],
                              "reward_without_memory": r["reward_without_memory"]}
                for r in rows}
    est = noise.judge_floor(rows, rescored, n_boot=50)
    assert est.point == pytest.approx(0.0, abs=1e-12)
    assert est.n_obs == 120


def test_judge_floor_does_not_compare_two_different_tasks():
    """The same text can be correct for one question and wrong for another.

    A reward is a function of (prediction, GOLD ANSWER, scorer). Grouping
    byte-identical outputs WITHOUT the task compares two different questions and
    reports a property of the benchmark as verifier nondeterminism.

    This is not hypothetical. On the first real LongMemEval-V2 pilot the text-only
    key gave F_judge = 0.1486 [0.116, 0.181] while re-scoring the same text for the
    SAME task gave 0.0000 over 1,916 comparisons -- all 18 "disagreeing" groups
    spanned more than one task. ``\boxed{F}`` was correct for one multiple-choice
    question and wrong for five others.

    The plant below reproduces exactly that shape: identical predictions, different
    questions, legitimately different rewards, and NO verifier disagreement.
    """
    rows = []
    for i in range(12):
        r = {
            "row_id": f"r{i}", "cell_id": f"c{i}", "memory_id": f"m{i}",
            "benchmark": "b", "future_task_id": f"task{i}",   # every task DIFFERENT
            "reader_cluster": "metis", "reader_model": "gpt-oss-120b",
            "reader_prompt_version": "v1", "reader_reasoning_effort": "low",
            "verifier_id": "mc_choice_match", "verifier_version": "vendored@abc",
            "error_code_if_any": None,
            # byte-identical prediction everywhere
            "output_with_memory": "\\boxed{F}",
            "output_without_memory": "\\boxed{F}",
            # correct for the first three questions, wrong for the rest --
            # a property of the gold answers, not of the scorer
            "reward_with_memory": 1.0 if i < 3 else 0.0,
            "reward_without_memory": 1.0 if i < 3 else 0.0,
            "delta_utility": 0.0,
        }
        rows.append(r)

    est = noise.judge_floor(rows, None, n_boot=50)
    assert est.point in (None, 0.0), (
        f"F_judge={est.point} from identical text scored against DIFFERENT gold "
        f"answers; the task must be part of the comparison key")
    assert not any(f.startswith("NONZERO_JUDGE_FLOOR") for f in est.flags)


def test_judge_floor_still_fires_on_a_real_disagreement_within_one_task():
    """The counterpart: adding the task to the key must not make the check blind.

    Same task, same scorer, byte-identical text, two different rewards -- that IS
    verifier nondeterminism and must still be caught.
    """
    rows = []
    for i in range(10):
        rows.append({
            "row_id": f"r{i}", "cell_id": f"c{i}", "memory_id": f"m{i}",
            "benchmark": "b", "future_task_id": "SAME_TASK",
            "reader_cluster": "metis", "reader_model": "gpt-oss-120b",
            "reader_prompt_version": "v1", "reader_reasoning_effort": "low",
            "verifier_id": "mc_choice_match", "verifier_version": "vendored@abc",
            "error_code_if_any": None,
            "output_with_memory": "\\boxed{F}",
            "output_without_memory": "\\boxed{F}",
            "reward_with_memory": 1.0 if i % 2 else 0.0,   # genuine instability
            "reward_without_memory": 0.0,
            "delta_utility": 0.0,
        })
    est = noise.judge_floor(rows, None, n_boot=50)
    assert est.point is not None and est.point > 0, (
        "a real within-task disagreement was missed; the task-aware key made the "
        "estimator unable to fire at all")
    assert any(f.startswith("NONZERO_JUDGE_FLOOR") for f in est.flags)


# ------------------------------------------------------------------ reference floor
def test_reference_floor_is_per_benchmark_and_carries_both_scales():
    ds = make_dataset(seed=25)
    other = [dict(r) for r in make_dataset(seed=26).rows]
    for r in other:
        r["benchmark"] = "beam"
    est = noise.reference_floor(ds.rows + other, n_boot=50)
    assert set(est) == {"longmemeval_v2", "beam"}
    for e in est.values():
        assert "per_arm" in e.extra and set(e.extra["per_arm"]) == {"with", "without"}
        assert any(f.startswith("SCALE_NOTE") for f in e.flags)


def test_all_floors_returns_every_named_floor():
    ds = make_dataset(seed=27)
    out = noise.all_floors(ds.rows, n_boot=30)
    for k in ("F_exec_delta", "F_exec_with", "F_exec_without", "F_empty", "F_judge",
              "reference"):
        assert k in out

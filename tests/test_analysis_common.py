"""Tests for the shared primitives and the synthetic generator itself.

The generator is a test instrument, so it needs its own tests: if it does not really
plant what it claims to plant, every recovery result above is meaningless.
"""
from __future__ import annotations

import numpy as np
import pytest

from p1mem import schema
from p1mem.analysis import common
from p1mem.analysis.synthetic import (
    REPRESENTATION_COST,
    make_dataset,
    inject_errors,
    plant_sign_flip,
)


# ------------------------------------------------------- the generator is trustworthy
def test_generated_rows_are_valid_canonical_schema_rows():
    ds = make_dataset(seed=160)
    for r in ds.rows[:20]:
        assert set(r) == set(schema.FIELD_ORDER)
        for f in schema.NON_NULLABLE_IDENTITY:
            assert r[f] not in (None, "")
        for f in schema.P3_RESERVED_FIELDS:
            assert r[f] is None


def test_generated_delta_matches_its_components():
    ds = make_dataset(seed=161)
    for r in ds.rows:
        assert r["delta_utility"] == pytest.approx(
            r["reward_with_memory"] - r["reward_without_memory"],
            abs=schema.DELTA_TOLERANCE,
        )


def test_generator_plants_the_variance_it_claims():
    """Large design: the drawn effects' variance must match the requested sd^2."""
    ds = make_dataset(seed=162, n_memories=300, n_tasks=40, sd_memory=0.2,
                      sd_task=0.15, sd_interaction=0.25, n_replicates=2)
    r = ds.realized_components()
    assert np.sqrt(r["memory"]) == pytest.approx(0.2, rel=0.12)
    assert np.sqrt(r["task"]) == pytest.approx(0.15, rel=0.20)
    assert np.sqrt(r["interaction"]) == pytest.approx(0.25, rel=0.05)


def test_zero_interaction_really_is_zero():
    ds = make_dataset(seed=163, zero_interaction=True)
    assert all(v == 0.0 for v in ds.ab_interaction.values())
    assert ds.spec.variance_shares()["interaction"] == 0.0


def test_without_arm_is_one_condition_independently_executed():
    """The structural fact F_empty rests on. If this breaks, the D1 test is vacuous."""
    ds = make_dataset(seed=164)
    by_task_rep = {}
    for r in ds.rows:
        by_task_rep.setdefault((r["future_task_id"], r["replicate_id"]), []).append(r)
    for _k, group in by_task_rep.items():
        assert len({r["memory_id"] for r in group}) > 1
        # Independently executed -> distinct outputs and distinct rewards.
        assert len({r["output_without_memory"] for r in group}) > 1
        assert len({r["reward_without_memory"] for r in group}) > 1


def test_cached_without_arm_mode_produces_identical_outputs():
    ds = make_dataset(seed=165, cache_without_arm=True)
    by_task_rep = {}
    for r in ds.rows:
        by_task_rep.setdefault((r["future_task_id"], r["replicate_id"]), []).append(r)
    for _k, group in by_task_rep.items():
        assert len({r["output_without_memory"] for r in group}) == 1


def test_representation_costs_follow_the_protocol():
    assert REPRESENTATION_COST["raw"]["calls"] == 0
    assert REPRESENTATION_COST["summary"]["calls"] == 1
    assert REPRESENTATION_COST["structured"]["calls"] == 1
    ds = make_dataset(seed=166)
    raw = [r for r in ds.rows if r["memory_representation"] == "raw"]
    assert all(r["memory_extraction_latency"] is None for r in raw)
    assert all(r["memory_writer_model"] == "none:deterministic_span" for r in raw)


def test_plant_sign_flip_creates_the_effect_it_claims():
    ds = make_dataset(seed=167)
    mem = f"{ds.rows[0]['source_episode_id']}:{ds.rows[0]['memory_representation']}"
    plant_sign_flip(ds, mem, "task000", "task001", magnitude=0.7)
    assert ds.true_delta[(mem, "task000")] == pytest.approx(0.7)
    assert ds.true_delta[(mem, "task001")] == pytest.approx(-0.7)


# ------------------------------------------------------------------ admission
def test_admission_drops_errored_rows_and_keeps_leakage_flagged_ones():
    ds = inject_errors(make_dataset(seed=168), 10)
    for r in ds.rows[200:210]:
        r["leakage_flag"] = True
    adm = common.admit_rows(ds.rows)
    assert adm.n_errored == 10
    assert adm.n_leakage_flagged == 10
    assert len(adm.rows) == len(ds.rows) - 10
    assert any(r.get("leakage_flag") for r in adm.rows), (
        "EXPERIMENT_PLAN 8.3: leaky cells are FLAGGED, never dropped"
    )


def test_admission_records_the_error_codes_it_saw():
    ds = inject_errors(make_dataset(seed=169), 7, code="timeout")
    adm = common.admit_rows(ds.rows)
    assert adm.error_codes == {"timeout": 7}


# ------------------------------------------------------------------ guards
def test_homogeneity_guard_names_every_offending_key():
    ds = make_dataset(seed=170)
    rows = [dict(r) for r in ds.rows]
    rows[0]["reader_cluster"] = "sophia"
    rows[1]["verifier_version"] = "v2"
    bad = common.homogeneity_report(rows)
    assert set(bad) == {"reader_cluster", "verifier_version"}
    with pytest.raises(common.HeterogeneousPoolError):
        common.require_homogeneous(rows)


# ------------------------------------------------------------------ statistics
def test_wilson_ci_matches_a_known_value():
    p, lo, hi = common.wilson_ci(3, 20)
    assert p == pytest.approx(0.15)
    assert lo == pytest.approx(0.0524, abs=1e-3)
    assert hi == pytest.approx(0.3604, abs=1e-3)


def test_wilson_ci_on_an_empty_denominator_is_none_not_zero():
    assert common.wilson_ci(0, 0) == (None, None, None)


def test_benjamini_hochberg_at_q_010():
    assert common.benjamini_hochberg([0.001, 0.02, 0.3, None], 0.10) == \
        [True, True, False, False]
    assert common.benjamini_hochberg([0.9, 0.8], 0.10) == [False, False]
    assert all(common.benjamini_hochberg([0.0001] * 5, 0.10))


def test_pooled_variance_is_none_when_nothing_was_repeated():
    v, df, used = common.pooled_variance([[1.0], [2.0], [3.0]])
    assert v is None and df == 0 and used == 0


def test_pooled_variance_recovers_a_known_value():
    v, df, used = common.pooled_variance([[1.0, 3.0], [10.0, 12.0]])
    assert v == pytest.approx(2.0)   # each group has ddof=1 variance 2.0
    assert df == 2 and used == 2


def test_bootstrap_mean_ci_on_one_observation_gives_no_interval():
    """One replicate cannot separate an effect from noise; a zero-width CI would lie."""
    mean, lo, hi, p = common.bootstrap_mean_ci([0.5])
    assert mean == 0.5 and lo is None and hi is None and p is None


def test_balanced_subset_takes_the_lowest_replicate_ids():
    ds = make_dataset(seed=171)
    rows = list(ds.rows)
    target = rows[0]["cell_id"]
    for i in range(5):
        r = dict(rows[0]); r["replicate_id"] = 50 + i
        rows.append(r)
    subset, n, dropped = common.balanced_replicate_subset(rows)
    assert n == 3 and dropped == 0
    kept = [r["replicate_id"] for r in subset if r["cell_id"] == target]
    assert sorted(kept) == [0, 1, 2]


def test_tercile_bands_split_into_thirds():
    xs = list(np.linspace(0.0, 1.0, 300))
    lo, hi = common.tercile_bands(xs)
    bands = [common.assign_band(x, (lo, hi)) for x in xs]
    for b in ("NEAR", "MID", "FAR"):
        assert abs(bands.count(b) - 100) <= 3
    assert common.assign_band(0.99, (lo, hi)) == "NEAR"
    assert common.assign_band(0.01, (lo, hi)) == "FAR"

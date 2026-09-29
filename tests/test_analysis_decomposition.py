"""D3 tests -- variance decomposition (prereg section 6).

Recovery is scored against the REALIZED component variances (the draws the generator
actually made), not the population parameters. With 24 memories the sample variance of
the drawn memory effects differs from sd_memory^2 by a visible amount; scoring against
the population value would charge the estimator for the generator's sampling error.
Both are reported in the report table.
"""
from __future__ import annotations

import numpy as np
import pytest

from p1mem.analysis import decomposition as dc, noise
from p1mem.analysis.common import HeterogeneousPoolError
from p1mem.analysis.synthetic import make_dataset


def _realized_shares(ds):
    rc = ds.realized_components()
    tot = sum(rc.values())
    return {k: v / tot for k, v in rc.items()}


# ------------------------------------------------------------------ REML recovery
def test_reml_recovers_the_realized_variance_shares():
    ds = make_dataset(seed=80, n_memories=30, n_tasks=8)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    assert d.converged and not d.used_fallback
    truth = _realized_shares(ds)
    for comp in dc.COMPONENTS:
        assert d.shares[comp] == pytest.approx(truth[comp], abs=0.08), comp


def test_reml_recovery_error_is_small_across_seeds():
    errs = []
    for seed in range(85, 91):
        ds = make_dataset(seed=seed, n_memories=30, n_tasks=8)
        d = dc.variance_decomposition(ds.rows, n_boot=0)
        errs.append(dc.recovery_error(d, _realized_shares(ds))["max_abs_share_error"])
    assert np.mean(errs) < 0.06, f"mean max share error {np.mean(errs):.4f}"


def test_reml_recovers_raw_variances_not_only_shares():
    ds = make_dataset(seed=92, n_memories=30, n_tasks=8)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    truth = ds.realized_components()
    assert d.components["residual"] == pytest.approx(truth["residual"], rel=0.25)
    assert d.components["interaction"] == pytest.approx(truth["interaction"], rel=0.35)


def test_reml_residual_agrees_with_the_independently_measured_exec_floor():
    """Two routes to the residual: the mixed model, and the D1 floor. They must agree."""
    ds = make_dataset(seed=93, n_memories=30)
    F = noise.exec_floor(ds.rows, scale="delta", n_boot=1).point
    d = dc.variance_decomposition(ds.rows, exec_floor_sd=F, n_boot=0)
    assert d.components["residual"] == pytest.approx(F ** 2, rel=0.20)
    assert d.exec_floor_variance == pytest.approx(F ** 2)
    assert any(f.startswith("EXEC_FLOOR_COMPARATOR") for f in d.flags)


# ------------------------------------------------------- the zero-interaction control
def test_zero_interaction_is_recovered_as_essentially_zero():
    """Plant no interaction; the estimator must not invent one."""
    shares = []
    for seed in (100, 101, 102, 103):
        ds = make_dataset(seed=seed, zero_interaction=True, n_memories=30, n_tasks=8)
        d = dc.variance_decomposition(ds.rows, n_boot=0)
        shares.append(d.shares["interaction"])
    assert max(shares) < 0.05, f"invented interaction share {shares}"


def test_main_effects_survive_when_interaction_is_removed():
    """The zero-interaction fit must still find the memory and task effects.

    Without this, 'interaction ~ 0' could just mean the fitter collapsed everything.
    """
    ds = make_dataset(seed=104, zero_interaction=True, n_memories=30, n_tasks=8)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    assert d.shares["memory"] > 0.3
    assert d.shares["task"] > 0.1


def test_pure_noise_puts_everything_in_the_residual():
    ds = make_dataset(seed=105, sd_memory=0.0, sd_task=0.0, zero_interaction=True,
                      n_memories=30, n_tasks=8)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    assert d.shares["residual"] > 0.85
    assert d.shares["interaction"] < 0.10
    assert d.shares["memory"] < 0.10


def test_boundary_components_are_flagged_not_reported_as_measured():
    ds = make_dataset(seed=106, sd_memory=0.0, sd_task=0.0, zero_interaction=True)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    near_zero = [c for c in dc.COMPONENTS if d.components[c] <= dc.BOUNDARY_TOL]
    if near_zero:
        for c in near_zero:
            assert any(f.startswith(f"AT_BOUNDARY:{c}") for f in d.flags)


def test_estimator_tracks_a_rising_interaction():
    """A decomposition that ignored its input would pass any single-point test."""
    got = []
    for sdi in (0.02, 0.25, 0.70):
        ds = make_dataset(seed=107, sd_interaction=sdi, n_memories=30, n_tasks=8)
        got.append(dc.variance_decomposition(ds.rows, n_boot=0).shares["interaction"])
    assert got[0] < got[1] < got[2]
    assert got[0] < 0.10 and got[2] > 0.70


# --------------------------------------------------------- the pre-registered fallback
def test_method_of_moments_fallback_recovers_the_same_shares():
    ds = make_dataset(seed=110, n_memories=30, n_tasks=8)
    reml = dc.variance_decomposition(ds.rows, n_boot=0)
    mom = dc.variance_decomposition(ds.rows, n_boot=0, force_fallback=True)
    assert mom.used_fallback
    for comp in dc.COMPONENTS:
        assert mom.shares[comp] == pytest.approx(reml.shares[comp], abs=0.08), comp


def test_fallback_is_flagged_as_such_and_never_silent():
    """Prereg section 6: 'Non-convergence is disclosed, never silently swapped.'"""
    ds = make_dataset(seed=111)
    mom = dc.variance_decomposition(ds.rows, n_boot=0, force_fallback=True)
    assert mom.used_fallback is True
    assert "method of moments" in mom.method
    assert any(f.startswith("FALLBACK_FORCED") for f in mom.flags)
    assert mom.to_dict()["used_fallback"] is True


def test_fallback_reports_its_balanced_sub_design_and_any_trimming():
    ds = make_dataset(seed=112, n_memories=30, n_tasks=8)
    rows = [r for r in ds.rows
            if not (r["future_task_id"] == "task007" and r["memory_id"].endswith("a"))]
    mom = dc.variance_decomposition(rows, n_boot=0, force_fallback=True)
    info = mom.extra["info"]
    assert "balanced_sub_design" in info and "trimmed" in info


def test_fallback_truncates_negative_variance_estimates_and_says_so():
    ds = make_dataset(seed=113, zero_interaction=True, n_memories=12, n_tasks=4)
    mom = dc.variance_decomposition(ds.rows, n_boot=0, force_fallback=True)
    assert all(v >= 0.0 for v in mom.components.values())
    assert "negative_estimates_truncated" in mom.extra["info"]


def test_automatic_fallback_on_an_oversized_design_is_disclosed():
    ds = make_dataset(seed=114)
    d = dc.variance_decomposition(ds.rows, n_boot=0, max_obs_for_reml=10)
    assert d.used_fallback
    assert any(f.startswith("FALLBACK_USED") for f in d.flags)


# -------------------------------------------------------------- bootstrap + guards
def test_bootstrap_ci_over_memories_covers_the_realized_share():
    ds = make_dataset(seed=115, n_memories=24, n_tasks=6)
    d = dc.variance_decomposition(ds.rows, n_boot=40, seed=7)
    truth = _realized_shares(ds)
    covered = sum(
        1 for c in dc.COMPONENTS
        if d.share_ci[c][0] is not None and d.share_ci[c][0] <= truth[c] <= d.share_ci[c][1]
    )
    assert covered >= 3, f"only {covered}/4 share CIs covered the realized value"


def test_degenerate_design_refuses_rather_than_inventing_an_interaction():
    ds = make_dataset(seed=116, n_tasks=1)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    assert not d.components
    assert any(f.startswith("DEGENERATE_DESIGN") for f in d.flags)


def test_refuses_to_pool_across_clusters():
    ds = make_dataset(seed=117)
    rows = [dict(r) for r in ds.rows]
    for r in rows[: len(rows) // 2]:
        r["reader_cluster"] = "sophia"
    with pytest.raises(HeterogeneousPoolError):
        dc.variance_decomposition(rows, n_boot=0)


def test_shares_sum_to_one():
    ds = make_dataset(seed=118)
    d = dc.variance_decomposition(ds.rows, n_boot=0)
    assert sum(d.shares.values()) == pytest.approx(1.0)

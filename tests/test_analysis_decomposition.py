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


def test_reml_recovery_error_shrinks_as_the_design_grows():
    """Consistency, which is the property that matters -- not a threshold I picked.

    A fixed error bound can be met by a biased estimator on a lucky design size. What
    distinguishes a correct variance-components estimator is that its error SHRINKS as
    memories and tasks are added, because the remaining gap is sampling error in the
    drawn effects rather than bias. Measured here at three design sizes; the error falls
    roughly as 1/sqrt(n) (0.040 -> 0.022 -> 0.010 over 12 seeds each).
    """
    def mean_err(n_mem, n_task, seeds):
        errs = []
        for seed in seeds:
            ds = make_dataset(seed=seed, n_memories=n_mem, n_tasks=n_task)
            d = dc.variance_decomposition(ds.rows, n_boot=0)
            errs.append(dc.recovery_error(d, _realized_shares(ds))["max_abs_share_error"])
        return float(np.mean(errs))

    seeds = range(200, 206)
    small = mean_err(30, 8, seeds)
    large = mean_err(120, 20, seeds)
    assert large < small / 2.0, (
        f"error did not shrink with design size: {small:.4f} -> {large:.4f}"
    )
    assert large < 0.03, f"error at the largest design is {large:.4f}"


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


# ------------------------------------------- the likelihood reduction is exact, not approximate
def test_reduced_likelihood_equals_the_dense_one():
    """The cell-mean reduction + Woodbury path must equal the textbook dense REML.

    ``decomposition.py`` never builds the n x n variance matrix: mu, a_m, b_t and
    (ab)_mt are constant within a cell, so the restricted likelihood factorizes into a
    within-cell piece and a model on the C cell means. That reduction is what makes the
    bootstrap affordable, and it is exact -- but "exact" is a claim, so it is checked
    here against a dense reference written independently from the textbook formula.

    The two differ by an additive constant (the within-cell piece the reduction folds
    into sigma^2), so the test is that the DIFFERENCE is constant across the parameter
    space, and that the two agree on the argmin.
    """
    import math
    from scipy.optimize import minimize

    def dense_neg2(log_ratios, d):
        r = np.exp(np.clip(np.asarray(log_ratios, dtype=float), -18, 12))
        n = d.y.size
        Zm = np.zeros((n, d.n_mem)); Zm[np.arange(n), d.mem_idx] = 1
        Zt = np.zeros((n, d.n_task)); Zt[np.arange(n), d.task_idx] = 1
        Zc = np.zeros((n, d.n_cell)); Zc[np.arange(n), d.cell_idx] = 1
        V = np.eye(n) + r[0] * Zm @ Zm.T + r[1] * Zt @ Zt.T + r[2] * Zc @ Zc.T
        x = np.ones(n)
        _s, logdetV = np.linalg.slogdet(V)
        XtViX = float(x @ np.linalg.solve(V, x))
        beta = float(x @ np.linalg.solve(V, d.y)) / XtViX
        res = d.y - beta
        quad = float(res @ np.linalg.solve(V, res))
        return logdetV + math.log(XtViX) + (n - 1) * math.log(quad / (n - 1))

    ds = make_dataset(seed=300, n_memories=6, n_tasks=4, n_replicates=3)
    d = dc._build_design(ds.rows, "delta_utility")
    means, counts, ssw, n_obs, _C = dc._cell_reduce(d)
    U, _ = dc._cell_level_matrices(d)
    args = (means, counts, ssw, n_obs, U, d.n_mem, d.n_task)

    pts = [[0, 0, 0], [-2, -1, 0.5], [1, 1, 1], [-5, 0, 2], [2, -3, -1],
           [-12, -12, -12], [0.3, -0.7, 1.4]]
    diffs = [dc._profiled_neg2_reml(np.array(x, dtype=float), *args) - dense_neg2(x, d)
             for x in pts]
    assert max(diffs) - min(diffs) < 1e-7, (
        f"the reduction is NOT exact: difference varies by {max(diffs) - min(diffs):.3e}"
    )

    opt = {"xatol": 1e-10, "fatol": 1e-12, "maxiter": 8000}
    a = minimize(dc._profiled_neg2_reml, [0, 0, 0], args=args,
                 method="Nelder-Mead", options=opt)
    b = minimize(dense_neg2, [0, 0, 0], args=(d,), method="Nelder-Mead", options=opt)
    assert np.max(np.abs(np.exp(a.x) - np.exp(b.x))) < 1e-4


# ---------------------------------------------------------------------------
# A FAILED FIT MUST NOT PRINT A NUMBER (regression, found by Sub-agent H)
# ---------------------------------------------------------------------------
# The pilot reported "variance shares all 0.0000". The fit had FAILED: shares
# was {}, converged False, flags NON_CONVERGENCE + FIT_FAILED, and the moments
# fallback refused with "balanced sub-design is 0x220; needs >= 2x2". The
# 0.0000 came from `dec.shares.get(c, 0.0)` over an EMPTY dict -- absence
# defaulting to a plausible zero, on the project's headline quantity.
# See docs/OFFICIAL_PROMPT_ARM.md section 4 and RESULTS_LEDGER row 54a.

def test_failed_fit_renders_unmeasured_not_zero():
    """Plant the exact defect: an empty shares dict, and require no 0.0000."""
    from p1mem.analysis.decomposition import COMPONENTS, Decomposition

    dec = Decomposition(
        components={}, shares={}, share_ci={},
        method="method of moments [FALLBACK]", converged=False, used_fallback=True,
        n_obs=958, n_cells=479, n_memories=60, n_tasks=220,
        flags=["NON_CONVERGENCE", "FIT_FAILED"],
    )
    text = str(dec)
    assert "0.0000" not in text, (
        f"a FAILED fit printed a number; absence must not default to zero:\n{text}")
    for c in COMPONENTS:
        assert "UNMEASURED" in text
    assert text.count("UNMEASURED") >= 2 * len(COMPONENTS)  # var + share each


def test_successful_fit_still_prints_its_numbers():
    """Positive control: the change must not silence a fit that DID produce shares."""
    from p1mem.analysis.decomposition import Decomposition

    dec = Decomposition(
        components={"memory": 0.25, "task": 0.25, "interaction": 0.25,
                    "residual": 0.25},
        shares={"memory": 0.25, "task": 0.25, "interaction": 0.25, "residual": 0.25},
        share_ci={}, method="REML", converged=True,
        used_fallback=False, n_obs=100, n_cells=50, n_memories=10, n_tasks=5,
    )
    text = str(dec)
    assert "UNMEASURED" not in text
    # count the SHARE field specifically: "var=0.250000" also contains "0.2500"
    assert text.count("share=0.2500") == 4


def test_partial_fit_marks_only_the_missing_component():
    """A component present prints; one absent says UNMEASURED. Both in one render."""
    from p1mem.analysis.decomposition import Decomposition

    dec = Decomposition(
        components={"memory": 0.5}, shares={"memory": 0.5}, share_ci={}, method="partial", converged=False, used_fallback=True,
        n_obs=10, n_cells=5, n_memories=3, n_tasks=2,
    )
    text = str(dec)
    assert "0.5000" in text            # the one that exists
    assert "UNMEASURED" in text        # the three that do not


def test_recovery_error_does_not_score_a_missing_component_as_zero():
    """A crashed fit must not look like a merely inaccurate one.

    Substituting 0.0 for an absent component scores it as an error of exactly
    the planted share -- a real, finite, comparable-looking number produced by
    an estimate that does not exist.
    """
    from p1mem.analysis.decomposition import Decomposition, recovery_error

    dec = Decomposition(
        components={}, shares={}, share_ci={},
        method="FAILED", converged=False, used_fallback=True,
        n_obs=10, n_cells=5, n_memories=3, n_tasks=2, flags=["FIT_FAILED"],
    )
    rec = recovery_error(dec, {"memory": 0.4, "task": 0.3, "interaction": 0.2,
                               "residual": 0.1})
    for comp in ("memory", "task", "interaction", "residual"):
        assert rec[comp]["recovered_share"] is None
        assert rec[comp]["abs_error"] is None


# ---------------------------------------------------------------------------
# A ZERO EXEC FLOOR MUST NOT CRASH THE DECOMPOSITION (found by Sub-agent H)
# ---------------------------------------------------------------------------
# F_exec = 0.0 is the EXPECTED measurement for a deterministic reader at
# temperature 0 with byte-identical replicates -- both P1 arms measured it.
# Section 6's comparator is a RATIO to F_exec^2, and the code divided by it
# unconditionally. On real data this raised ZeroDivisionError, killed the
# whole stage, and left shares={} -- which then printed as "all 0.0000".
# The script still exited 0, so the crash was invisible in the exit code.

def test_zero_exec_floor_does_not_raise():
    """The exact production input: a measured floor of exactly 0.0."""
    from p1mem.analysis.decomposition import variance_decomposition

    rows = make_dataset(seed=80, n_memories=30, n_tasks=8).rows
    dec = variance_decomposition(rows, exec_floor_sd=0.0, n_boot=0, seed=1)
    assert any("EXEC_FLOOR_COMPARATOR_UNDEFINED" in f for f in dec.flags), (
        "a zero floor must be DISCLOSED as an undefined ratio, not silently dropped")
    assert not any(f.startswith("EXEC_FLOOR_COMPARATOR:") for f in dec.flags)


def test_positive_exec_floor_still_reports_the_ratio():
    """Positive control: the guard must not suppress a ratio that IS defined."""
    from p1mem.analysis.decomposition import variance_decomposition

    rows = make_dataset(seed=80, n_memories=30, n_tasks=8).rows
    dec = variance_decomposition(rows, exec_floor_sd=0.25, n_boot=0, seed=1)
    assert any(f.startswith("EXEC_FLOOR_COMPARATOR:") for f in dec.flags)
    assert not any("EXEC_FLOOR_COMPARATOR_UNDEFINED" in f for f in dec.flags)


# ---------------------------------------------------------------------------
# AN UPPER-BOUNDARY SOLUTION IS NOT A MEASUREMENT (found by Sub-agent H)
# ---------------------------------------------------------------------------
# The module guarded a ratio driven to ZERO and flagged it AT_BOUNDARY, but
# not one pinned at the optimizer's UPPER clip. Measured on both P1 arms:
# task and interaction ratios both sat at exactly exp(12) and their shares
# came out EXACTLY equal to 16 significant figures. converged=True with a
# tight bootstrap CI -- an unidentified component wearing a measurement's
# clothes.

def test_upper_boundary_is_flagged_on_the_real_pilot_rows():
    """Observed on BOTH P1 arms, so assert it against the artifact itself.

    task and interaction ratios both sat at exactly exp(12) (the clip
    ceiling) and their shares came out EXACTLY equal to 16 significant
    figures, with converged=True and a tight bootstrap CI. That is the
    likelihood saying the two are not separable under a pairing where each
    memory has its own 8 tasks -- not a measurement.
    """
    import json
    from pathlib import Path

    from p1mem.analysis.decomposition import variance_decomposition

    art = (Path(__file__).resolve().parents[1]
           / "results/deltau_pilot/cells.jsonl")
    if not art.exists():
        pytest.skip("pilot row artifact not present in this checkout")
    rows = [json.loads(l) for l in art.read_text().splitlines() if l.strip()]
    dec = variance_decomposition(rows, exec_floor_sd=0.0, n_boot=0, seed=1,
                                 allow_pooling=True)
    assert dec.converged, "the fit converged when this defect was found"
    assert dec.shares["task"] == dec.shares["interaction"], (
        "exact equality was the tell that the two are not identified")
    ups = [f for f in dec.flags if f.startswith("AT_UPPER_BOUNDARY")]
    assert len(ups) >= 2, f"expected task AND interaction flagged; got {dec.flags}"
    assert set(dec.extra["info"]["components_at_upper_bound"]) >= {"task",
                                                                   "interaction"}


def test_to_dict_does_not_divide_by_a_zero_exec_floor():
    """SECOND SITE of the same division -- serialization, not the fit.

    The first guard covered the flag site only, and `to_dict()` raised
    ZeroDivisionError on the very next production run. One mechanism, two
    sites: a fix tested against the instance closes the instance, not the
    defect. This test covers the serializer directly.
    """
    from p1mem.analysis.decomposition import Decomposition

    dec = Decomposition(
        components={"memory": 0.1, "task": 0.2, "interaction": 0.3, "residual": 0.4},
        shares={"memory": 0.1, "task": 0.2, "interaction": 0.3, "residual": 0.4},
        exec_floor_variance=0.0,          # F_exec = 0 squared: the real input
        method="REML", converged=True, n_obs=10, n_cells=5,
        n_memories=3, n_tasks=2,
    )
    out = dec.to_dict()                    # must not raise
    assert out["interaction_share_vs_exec_floor"] is None
    assert out["exec_floor_variance_comparator"] == 0.0


def test_to_dict_still_computes_the_ratio_when_the_floor_is_positive():
    """Positive control for the serializer guard."""
    from p1mem.analysis.decomposition import Decomposition

    dec = Decomposition(
        components={"memory": 0.1, "task": 0.2, "interaction": 0.3, "residual": 0.4},
        shares={"memory": 0.1, "task": 0.2, "interaction": 0.3, "residual": 0.4},
        exec_floor_variance=0.5, method="REML", converged=True, n_obs=10,
        n_cells=5, n_memories=3, n_tasks=2,
    )
    assert dec.to_dict()["interaction_share_vs_exec_floor"] == pytest.approx(0.6)


def test_every_exec_floor_division_is_guarded():
    """Grep-level check that no THIRD site reintroduces the same defect.

    A future edit that divides by exec_floor_variance without a positivity
    guard fails here, rather than at 3am in a 40-minute production run.
    """
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/p1mem/analysis/decomposition.py").read_text()
    # every '/ ... exec_floor_variance' or '/ fvar' must sit near a positivity test
    for m in re.finditer(r"/\s*(self\.exec_floor_variance|fvar)\b", src):
        window = src[max(0, m.start() - 400):m.start()]
        assert ("exec_floor_variance <= 0" in window
                or "exec_floor_variance is None or self.exec_floor_variance <= 0" in window
                or "fvar is not None and fvar > 0" in window), (
            f"unguarded division by the exec floor near offset {m.start()}: "
            f"F_exec = 0 is an EXPECTED measurement and will crash this")

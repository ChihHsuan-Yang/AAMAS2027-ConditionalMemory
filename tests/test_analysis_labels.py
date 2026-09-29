"""D2 tests -- robust labels (prereg section 4) and sign flips (section 5).

The two tests that matter most are the last two groups: proving the flip detector can
FIRE on a planted flip, and proving it does NOT fire on data with no effect. A detector
only ever run on positive data cannot be told apart from one that always fires; a
detector only ever run on null data cannot be told apart from one that never fires.
"""
from __future__ import annotations

import pytest

from p1mem.analysis import labels, noise
from p1mem.analysis.synthetic import make_dataset, plant_sign_flip


def _floor(ds):
    return noise.exec_floor(ds.rows, scale="delta", n_boot=1).point


# ---------------------------------------------------------- section 4, clause by clause
def test_label_requires_both_clauses_ci_and_floor():
    """A cell can be statistically nonzero yet inside the floor. Prereg: that is NEUTRAL."""
    from p1mem.schema import derive_utility_label
    # Tight CI strictly above zero, but the mean is inside the floor.
    assert derive_utility_label(0.01, 0.03, 0.02, 0.05) == "neutral"
    # Same CI, floor now below the mean -> useful.
    assert derive_utility_label(0.01, 0.03, 0.02, 0.005) == "robust_useful"
    # CI straddles zero but the magnitude is large -> still neutral.
    assert derive_utility_label(-0.1, 0.9, 0.4, 0.05) == "neutral"
    assert derive_utility_label(-0.9, -0.5, -0.7, 0.05) == "robust_harmful"


def test_no_floor_means_undetermined_never_zero():
    """Until P1-051 measures F, every label is undetermined. 0 is not a substitute."""
    ds = make_dataset(seed=30)
    cells = labels.cell_statistics(ds.rows, None, n_boot=50)
    assert cells and all(c.label == "undetermined" for c in cells)
    rep = labels.sign_flip_report(cells)
    assert rep.robust.point == 0.0
    assert any(f.startswith("UNDETERMINED_CELLS") for f in rep.flags)


def test_single_replicate_cell_cannot_be_labelled_robust():
    ds = make_dataset(seed=31, n_replicates=1)
    cells = labels.cell_statistics(ds.rows, 0.01, n_boot=50)
    assert all(c.ci_lower is None for c in cells)
    assert all(c.label == "undetermined" for c in cells)


def test_a_higher_floor_demotes_labels_monotonically():
    ds = make_dataset(seed=32)
    counts = []
    for F in (0.0, 0.2, 0.5, 5.0):
        cells = labels.cell_statistics(ds.rows, F, n_boot=200)
        counts.append(sum(1 for c in cells if c.label != "neutral"))
    assert counts == sorted(counts, reverse=True)
    assert counts[-1] == 0, "an enormous floor must leave nothing robust"


# ------------------------------------------------------------------- section 5, denominator
def test_denominator_counts_distinct_tasks_not_cells():
    """A memory measured twice on ONE task cannot flip and is not in the denominator."""
    ds = make_dataset(seed=33, n_tasks=1)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=100)
    rep = labels.sign_flip_report(cells)
    assert rep.n_memories_eligible == 0
    assert rep.robust.point is None, "an empty denominator is undefined, not 0.0"
    assert any(f.startswith("EMPTY_DENOMINATOR") for f in rep.flags)


def test_both_rates_share_one_denominator():
    ds = make_dataset(seed=34)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=200)
    rep = labels.sign_flip_report(cells)
    assert rep.robust.extra["denominator"] == rep.naive.extra["denominator"]
    assert rep.robust.n_units == rep.naive.n_units


def test_wilson_interval_is_reported_and_brackets_the_rate():
    ds = make_dataset(seed=35)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=200)
    rep = labels.sign_flip_report(cells)
    assert rep.robust.ci_lower <= rep.robust.point <= rep.robust.ci_upper
    assert rep.robust.extra["interval"] == "Wilson 95%"


# --------------------------------------------------- the detector CAN fire (positive control)
def test_a_planted_flip_is_detected():
    ds = make_dataset(seed=36, sd_memory=0.01, sd_task=0.01, sd_interaction=0.01)
    mem = f"{ds.rows[0]['source_episode_id']}:{ds.rows[0]['memory_representation']}"
    plant_sign_flip(ds, mem, "task000", "task001", magnitude=0.8)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=400)
    rep = labels.sign_flip_report(cells)
    assert rep.robust.point > 0, "a planted +/-0.8 flip must be detected"
    hit = [m for m, v in rep.per_memory.items() if v["robust_flip"]]
    assert hit, "no memory was flagged despite a planted flip"


def test_a_raw_sign_difference_inside_the_floor_is_not_a_flip():
    """Prereg section 5: 'A raw sign difference is NOT a flip.'"""
    ds = make_dataset(seed=37, sd_memory=0.0, sd_task=0.0, sd_interaction=0.0)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=400)
    rep = labels.sign_flip_report(cells)
    # Pure noise: every cell's true dU is 0, so raw signs differ constantly.
    assert rep.naive.point > 0.8, "the naive rule should be fooled by pure noise"
    assert rep.robust.point < 0.20, "the robust rule must not be"
    assert rep.gap > 0.6


# ----------------------------------------------- the detector does NOT fire (null control)
def test_zero_effect_data_yields_near_zero_robust_rate():
    """No memory effect, no task effect, no interaction -- only execution noise."""
    rates = []
    for seed in range(40, 46):
        ds = make_dataset(seed=seed, sd_memory=0.0, sd_task=0.0, zero_interaction=True)
        cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=300)
        rates.append(labels.sign_flip_report(cells).robust.point)
    assert sum(rates) / len(rates) < 0.15, (
        f"robust flip rate on pure noise averaged {sum(rates)/len(rates):.3f}; a method "
        "that finds structure in noise is worse than useless here"
    )


def test_more_replicates_drive_the_null_rate_toward_zero():
    """A correct estimator converges on the truth; a broken one has a floor of its own."""
    def rate(n_rep):
        out = []
        for seed in (50, 51, 52):
            ds = make_dataset(seed=seed, sd_memory=0.0, sd_task=0.0,
                              zero_interaction=True, n_replicates=n_rep)
            cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=300)
            out.append(labels.sign_flip_report(cells).robust.point)
        return sum(out) / len(out)
    assert rate(8) <= rate(3) + 0.02


def test_zero_effect_data_produces_almost_no_robust_cell_labels():
    ds = make_dataset(seed=47, sd_memory=0.0, sd_task=0.0, zero_interaction=True)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=400)
    n_robust = sum(1 for c in cells if c.label in ("robust_useful", "robust_harmful"))
    assert n_robust / len(cells) < 0.12


# ---------------------------------------------------- additive null (supplementary)
def test_additive_null_fires_on_a_real_interaction():
    ds = make_dataset(seed=60, sd_interaction=0.35)
    out = labels.additive_null_flip_rate(ds.rows, _floor(ds), n_null=40, n_boot=120)
    assert out["p_value_one_sided"] < 0.10


def test_additive_null_does_not_fire_when_interaction_is_zero():
    """The point of the diagnostic: main effects alone must not read as interaction."""
    ps = []
    for seed in (61, 62, 63):
        ds = make_dataset(seed=seed, zero_interaction=True)
        out = labels.additive_null_flip_rate(ds.rows, _floor(ds), n_null=40, n_boot=120)
        ps.append(out["p_value_one_sided"])
    assert min(ps) > 0.05, f"false positive against the additive null: p={ps}"


def test_additive_null_is_flagged_as_not_preregistered():
    ds = make_dataset(seed=64)
    out = labels.additive_null_flip_rate(ds.rows, _floor(ds), n_null=10, n_boot=50)
    assert any(f.startswith("NOT_PREREGISTERED") for f in out["flags"])


# --------------------------------------------------------- sections 11 and 12
def test_bh_correction_reports_raw_and_corrected_counts():
    ds = make_dataset(seed=70)
    cells = labels.cell_statistics(ds.rows, _floor(ds), n_boot=300)
    corrected, counts = labels.apply_bh_correction(cells, q=0.10)
    assert counts["bh_useful"] <= counts["raw_useful"]
    assert counts["bh_harmful"] <= counts["raw_harmful"]
    assert len(corrected) == len(cells)
    for c in corrected:
        assert "label_before_bh" in c.extra


def test_balanced_subset_is_the_primary_number():
    ds = make_dataset(seed=71)
    rows = list(ds.rows)
    # Adaptive replication: give one cell many extra replicates.
    target = rows[0]["cell_id"]
    extra = [dict(r) for r in rows if r["cell_id"] == target][:1] * 9
    for i, r in enumerate(extra):
        r["replicate_id"] = 100 + i
    out = labels.label_analysis(rows + extra, _floor(ds), n_boot=100)
    assert "primary_balanced" in out and "secondary_all_replicates" in out
    assert out["primary_balanced"]["n_replicates_per_cell"] == 3
    assert any(f.startswith("BALANCED_SUBSET")
               for f in out["primary_balanced"]["flags"])


def test_label_analysis_reports_replicate_counts_per_cell():
    """Prereg section 12 requires the replicate count per cell be reported."""
    ds = make_dataset(seed=72)
    out = labels.label_analysis(ds.rows, _floor(ds), n_boot=60)
    assert all("n_replicates" in c for c in out["cells"])

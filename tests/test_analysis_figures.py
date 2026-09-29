"""D5 tests -- the figure generators, run on synthetic data NOW.

The brief's explicit warning: do not discover in October that the schema cannot support
Figure 2. So every figure is generated end to end here, and ``missing_fields`` is
asserted empty -- a test that only checked "the function returned" would not catch a
field that is present in the schema but null on every row.
"""
from __future__ import annotations

import pytest

from p1mem.analysis import figures as fg, labels, noise
from p1mem.analysis.synthetic import (
    make_dataset,
    retrieval_sweep_rows,
    set_similarity_utility_link,
)


@pytest.fixture(scope="module")
def data():
    ds = make_dataset(seed=150)
    sweep = retrieval_sweep_rows(ds)
    F = noise.exec_floor(ds.rows, scale="delta", n_boot=1).point
    cells = labels.cell_statistics(ds.rows, F, n_boot=200)
    return ds, sweep, cells


# ------------------------------------------------------------------ schema support
def test_the_schema_can_produce_all_three_figures(data):
    ds, sweep, cells = data
    out = fg.check_schema_support(sweep, cells, n_boot=20)
    assert out["figure2"]["producible"], out["figure2"]["missing_fields"]
    assert out["figure3"]["producible"], out["figure3"]["missing_fields"]
    assert out["figure4"]["producible"], out["figure4"]["missing_fields"]
    assert out["all_producible"]


def test_missing_field_detection_can_actually_fire(data):
    """Prove the check discriminates: null a required field and it must be reported."""
    ds, sweep, cells = data
    broken = [dict(r) for r in sweep]
    for r in broken:
        r["memory_tokens_exposed"] = None
    out = fg.figure2_data(broken, n_boot=5)
    assert any("memory_tokens_exposed" in m for m in out["missing_fields"])


def test_a_field_absent_from_the_row_is_distinguished_from_a_null_one(data):
    ds, sweep, cells = data
    stripped = [{k: v for k, v in r.items() if k != "semantic_similarity"}
                for r in ds.rows]
    out = fg.figure4_data(cells, stripped, n_boot=5)
    assert any("ABSENT FROM SCHEMA" in m for m in out["missing_fields"])


# ----------------------------------------------------------------------- Figure 2
def test_figure2_has_all_four_retrieval_arms_crossed_with_representation(data):
    ds, sweep, cells = data
    d = fg.figure2_data(sweep, n_boot=20)
    methods = {p["retrieval_method"] for p in d["points"]}
    assert methods == {"none", "keep_all", "top_k", "oracle"}
    assert len({p["representation"] for p in d["points"]}) == 3
    assert not any(f.startswith("MISSING_ARM") for f in d["flags"])


def test_figure2_labels_oracle_as_non_deployable_headroom(data):
    ds, sweep, cells = data
    d = fg.figure2_data(sweep, n_boot=20)
    oracle = [p for p in d["points"] if p["retrieval_method"] == "oracle"]
    assert oracle
    for p in oracle:
        assert p["non_deployable"] is True
        assert "NON-DEPLOYABLE" in p["label"]
    for p in d["points"]:
        if p["retrieval_method"] != "oracle":
            assert p["non_deployable"] is False


def test_figure2_axes_are_exposed_tokens_and_reward(data):
    ds, sweep, cells = data
    d = fg.figure2_data(sweep, n_boot=20)
    assert d["x_label"] == "memory tokens exposed to the reader"
    assert d["y_label"] == "task reward"
    no_mem = [p for p in d["points"] if p["retrieval_method"] == "none"]
    assert all(p["x_tokens_exposed"] == pytest.approx(0.0) for p in no_mem)
    # y is absolute reward, so the no-memory arm is NOT at the origin.
    assert all(p["y_reward"] != pytest.approx(0.0) for p in no_mem)
    assert all(p["extra"]["mean_delta_utility"] == pytest.approx(0.0, abs=1e-9)
               for p in no_mem)


def test_figure2_reports_a_missing_retrieval_arm(data):
    ds, sweep, cells = data
    partial = [r for r in sweep if r["retrieval_method"] != "oracle"]
    d = fg.figure2_data(partial, n_boot=5)
    assert any("MISSING_ARM:oracle" in f for f in d["flags"])


def test_figure2_renders(tmp_path, data):
    ds, sweep, cells = data
    out = tmp_path / "fig2.png"
    fg.figure2_figure(fg.figure2_data(sweep, n_boot=20), str(out))
    assert out.exists() and out.stat().st_size > 5000


# ----------------------------------------------------------------------- Figure 3
def test_figure3_profiles_every_memory_across_tasks(data):
    ds, sweep, cells = data
    d = fg.figure3_data(cells, ds.rows)
    assert d["n_memories"] == len({c.memory_id for c in cells})
    assert all(p["n_tasks"] >= 1 for p in d["profiles"])
    assert set(d["label_counts_by_representation"]) == {"raw", "summary", "structured"}


def test_figure3_puts_flipping_memories_first(data):
    ds, sweep, cells = data
    d = fg.figure3_data(cells, ds.rows)
    flips = [i for i, p in enumerate(d["profiles"]) if p["robust_flip"]]
    non = [i for i, p in enumerate(d["profiles"]) if not p["robust_flip"]]
    if flips and non:
        assert max(flips) < min(non)


def test_figure3_says_so_when_every_cell_is_undetermined(data):
    ds, sweep, cells = data
    unlabelled = labels.cell_statistics(ds.rows, None, n_boot=20)
    d = fg.figure3_data(unlabelled, ds.rows)
    assert any(f.startswith("ALL_UNDETERMINED") for f in d["flags"])


def test_figure3_renders(tmp_path, data):
    ds, sweep, cells = data
    out = tmp_path / "fig3.png"
    fg.figure3_figure(fg.figure3_data(cells, ds.rows), str(out))
    assert out.exists() and out.stat().st_size > 5000


# ----------------------------------------------------------------------- Figure 4
def test_figure4_bands_are_terciles_of_the_observed_distribution(data):
    ds, sweep, cells = data
    d = fg.figure4_data(cells, ds.rows, n_boot=20)
    counts = d["band_counts"]
    n = sum(counts.values())
    for b in fg.BANDS:
        assert abs(counts[b] - n / 3) <= max(2, 0.1 * n / 3), counts


def test_figure4_recomputes_bands_and_detects_a_populator_bug():
    """The stored band is not trusted; a wrong populator must be reported."""
    good = make_dataset(seed=151)
    bad = make_dataset(seed=151, band_populator_bug=True)
    F = noise.exec_floor(good.rows, scale="delta", n_boot=1).point
    c_good = labels.cell_statistics(good.rows, F, n_boot=100)
    c_bad = labels.cell_statistics(bad.rows, F, n_boot=100)
    n_good = fg.figure4_data(c_good, good.rows, n_boot=5)[
        "n_band_disagreements_with_stored_field"]
    n_bad = fg.figure4_data(c_bad, bad.rows, n_boot=5)[
        "n_band_disagreements_with_stored_field"]
    assert n_bad > 10 * max(1, n_good), (good := (n_good, n_bad))


def test_figure4_recovers_a_planted_similarity_utility_relationship():
    ds = make_dataset(seed=152)
    set_similarity_utility_link(ds, -0.8)
    F = noise.exec_floor(ds.rows, scale="delta", n_boot=1).point
    cells = labels.cell_statistics(ds.rows, F, n_boot=200)
    d = fg.figure4_data(cells, ds.rows, n_boot=100)
    assert d["overall"]["rho"] < -0.15
    assert d["overall"]["ci"][1] < 0.1


def test_figure4_reports_no_relationship_when_none_was_planted():
    ds = make_dataset(seed=153)
    F = noise.exec_floor(ds.rows, scale="delta", n_boot=1).point
    cells = labels.cell_statistics(ds.rows, F, n_boot=200)
    d = fg.figure4_data(cells, ds.rows, n_boot=200)
    assert abs(d["overall"]["rho"]) < 0.2
    assert d["overall"]["ci"][0] < 0 < d["overall"]["ci"][1]


def test_figure4_answers_the_prereg_primary_question(data):
    """Section 7: do robust sign flips occur INSIDE the NEAR band?"""
    ds, sweep, cells = data
    d = fg.figure4_data(cells, ds.rows, n_boot=20)
    nb = d["near_band"]
    assert "n_memories_with_robust_flip_inside_NEAR" in nb
    assert nb["fraction_robustly_harmful"] is not None
    assert "question" in nb


def test_figure4_renders(tmp_path, data):
    ds, sweep, cells = data
    out = tmp_path / "fig4.png"
    fg.figure4_figure(fg.figure4_data(cells, ds.rows, n_boot=20), str(out))
    assert out.exists() and out.stat().st_size > 5000

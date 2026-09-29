"""D4 tests -- efficiency metrics (prereg section 10, PROJECT_GOAL C).

The load-bearing test is ``test_formation_cost_changes_the_representation_ranking``:
MEMORY_PROTOCOL section 5 says an efficiency comparison that omits write cost flatters
the model-written representations, and this suite measures how much.
"""
from __future__ import annotations

import pytest

from p1mem.analysis import efficiency as eff, labels, noise
from p1mem.analysis.synthetic import make_dataset, inject_errors


def _cells(ds, n_boot=200):
    F = noise.exec_floor(ds.rows, scale="delta", n_boot=1).point
    return labels.cell_statistics(ds.rows, F, n_boot=n_boot)


def test_all_seven_families_are_present():
    ds = make_dataset(seed=130)
    rep = eff.efficiency_report(ds.rows, _cells(ds), n_boot=50)
    assert set(rep["families"]) == set(eff.FAMILIES)
    assert len(eff.FAMILIES) == 7


# ------------------------------------------------- formation cost, the critical rule
def test_raw_is_charged_no_writer_call_and_the_others_are_charged_one():
    """MEMORY_PROTOCOL section 1: Raw ~0 calls; Summary and Structured 1 call each."""
    ds = make_dataset(seed=131)
    fc = eff.formation_cost(ds.rows)
    assert fc["raw"].writer_calls_per_memory == pytest.approx(0.0)
    assert fc["summary"].writer_calls_per_memory == pytest.approx(1.0)
    assert fc["structured"].writer_calls_per_memory == pytest.approx(1.0)
    assert any(f.startswith("NO_WRITER_CALL") for f in fc["raw"].flags)


def test_formation_cost_is_reported_both_amortized_and_not():
    ds = make_dataset(seed=132)
    fc = eff.formation_cost(ds.rows)["summary"]
    assert fc.reuse_factor == pytest.approx(6.0)  # 6 tasks per memory
    assert fc.amortized_calls_per_cell == pytest.approx(1.0 / 6.0)
    assert fc.amortized_tokens_per_cell == pytest.approx(
        (fc.input_tokens_per_memory + fc.output_tokens_per_memory) / 6.0
    )


def test_formation_cost_changes_the_representation_ranking():
    """The failure MEMORY_PROTOCOL section 5 warns about, measured.

    Charging formation must move the model-written representations, and must NOT move
    Raw -- Raw pays no formation cost, so its number is identical either way. If both
    moved, the charge would be a constant offset and would prove nothing.
    """
    ds = make_dataset(seed=133)
    cells = _cells(ds)
    charged = eff.utility_per_exposed_token(cells, ds.rows, n_boot=100,
                                            include_formation=True)
    uncharged = eff.utility_per_exposed_token(cells, ds.rows, n_boot=100,
                                              include_formation=False)
    assert charged["raw"].point == pytest.approx(uncharged["raw"].point, rel=1e-9)
    for rep in ("summary", "structured"):
        assert abs(charged[rep].point) < abs(uncharged[rep].point), (
            f"{rep}: charging formation must shrink the per-token figure toward zero; "
            f"{uncharged[rep].point:.4f} -> {charged[rep].point:.4f}"
        )
    assert any(f.startswith("FORMATION_CHARGED")
               for f in charged["summary"].flags)
    assert any(f.startswith("FORMATION_NOT_CHARGED")
               for f in uncharged["summary"].flags)


def test_report_carries_both_utility_per_token_tables():
    ds = make_dataset(seed=134)
    rep = eff.efficiency_report(ds.rows, _cells(ds), n_boot=50)
    assert "utility_per_exposed_token_with_formation" in rep
    assert "utility_per_exposed_token_exposure_only" in rep
    assert "formation_cost_note" in rep


# ------------------------------------------------------------------ null handling
def test_null_extraction_latency_is_not_counted_as_zero_seconds():
    """schema.py: null means 'no call was made', which is not 0.0 seconds."""
    ds = make_dataset(seed=135)
    ex = eff.extraction_metrics(ds.rows)["by_representation"]["raw"]
    assert ex["extraction_latency_s"]["mean"] is None
    assert ex["extraction_latency_s"]["n"] == 0
    assert ex["n_with_no_writer_call"] == ex["n_memories"]


def test_null_reasoning_tokens_are_excluded_from_the_denominator():
    ds = make_dataset(seed=136)
    rows = [dict(r) for r in ds.rows]
    for r in rows[: len(rows) // 2]:
        r["reasoning_tokens"] = None
    m = eff.api_compute_metrics(rows)
    assert m["reasoning_tokens"]["n"] == len(rows) - len(rows) // 2
    assert m["n_rows_reasoning_tokens_null"] == len(rows) // 2
    assert any(f.startswith("MIXED_REASONING_REPORTING") for f in m["flags"])


def test_errored_rows_never_reach_the_efficiency_aggregates():
    ds = inject_errors(make_dataset(seed=137), 40)
    rep = eff.efficiency_report(ds.rows, None, n_boot=10)
    assert rep["admission"]["n_errored"] == 40
    assert rep["admission"]["n_admitted"] == len(ds.rows) - 40


# --------------------------------------------------------- derived metrics
def test_compression_ratio_is_paired_within_source_episode():
    ds = make_dataset(seed=138)
    cr = eff.compression_ratio(ds.rows)
    assert cr["by_representation"]["raw"]["mean"] == pytest.approx(1.0)
    assert cr["by_representation"]["summary"]["mean"] > 1.0
    assert cr["by_representation"]["summary"]["n_paired_episodes"] > 0


def test_compression_ratio_reports_when_no_episode_is_paired():
    ds = make_dataset(seed=139)
    rows = [r for r in ds.rows if r["memory_representation"] != "raw"]
    cr = eff.compression_ratio(rows)
    assert cr["by_representation"]["summary"]["n_paired_episodes"] == 0
    assert "flags" in cr["by_representation"]["summary"]


def test_selectivity_rates_need_labels_and_say_so_when_absent():
    ds = make_dataset(seed=140)
    without = eff.selectivity_metrics(ds.rows, None)
    assert "useful_retrieval_precision" not in without
    assert "note" in without
    with_labels = eff.selectivity_metrics(ds.rows, _cells(ds))
    for k in ("useful_retrieval_precision", "useful_exposure_rate",
              "harmful_exposure_rate"):
        assert with_labels[k]["point"] is not None
        assert with_labels[k]["ci_lower"] <= with_labels[k]["point"]


def test_useful_retrieval_precision_uses_exposed_cells_as_its_denominator():
    ds = make_dataset(seed=141)
    cells = _cells(ds)
    s = eff.selectivity_metrics(ds.rows, cells)
    assert s["useful_retrieval_precision"]["denominator"] == \
        s["n_cells_with_memory_exposed"]


def test_exposure_flags_impossible_truncation():
    ds = make_dataset(seed=142)
    rows = [dict(r) for r in ds.rows]
    for r in rows[:5]:
        r["memory_tokens_exposed"] = r["memory_tokens_retrieved"] + 100
    m = eff.exposure_metrics(rows)
    assert m["n_rows_exposed_exceeds_retrieved"] == 5
    assert any(f.startswith("IMPOSSIBLE_EXPOSURE") for f in m["flags"])


def test_storage_is_per_distinct_memory_not_per_row():
    ds = make_dataset(seed=143)
    st = eff.storage_metrics(ds.rows)
    n_distinct = len({r["memory_id"] for r in ds.rows})
    assert st["n_memories"] == n_distinct < len(ds.rows)


def test_utility_per_token_is_a_ratio_of_totals_not_a_mean_of_ratios():
    """A mean of per-cell ratios blows up as exposure goes to zero; a ratio of totals does not."""
    ds = make_dataset(seed=144)
    rows = [dict(r) for r in ds.rows]
    for r in rows[:3]:
        r["memory_tokens_exposed"] = 1  # a near-zero denominator
    cells = labels.cell_statistics(rows, 0.1, n_boot=100)
    out = eff.utility_per_exposed_token(cells, rows, n_boot=50)
    for e in out.values():
        assert e.point is not None and abs(e.point) < 1e4

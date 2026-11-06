"""The smallest reproduction of the primary result must keep reproducing."""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SLICE = REPO / "results/ledgers/repro/screened_cells_slim.jsonl"


def _load():
    spec = importlib.util.spec_from_file_location("reproduce_headline", REPO / "scripts/reproduce_headline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not SLICE.exists(), reason="tracked slice not present")
def test_headline_contrast_reproduces():
    m = _load()
    cell = m.cells(m.rows_from_slice(SLICE))
    contrast = m.per_memory_contrast(cell)
    assert len(cell) == 1157
    assert len(contrast) == 60
    assert abs(sum(contrast.values()) / len(contrast) - 0.334861) < 1e-6


@pytest.mark.skipif(not SLICE.exists(), reason="tracked slice not present")
def test_stratum_cell_counts_match_table_2():
    m = _load()
    cell = m.cells(m.rows_from_slice(SLICE))
    counts = {s: sum(1 for k in cell if k[2] == s) for s in m.STRATA}
    assert counts == {"BEARING": 139, "MATCHED_CONTROL": 146, "RANDOM": 872}


def test_missing_rewards_are_dropped_not_zeroed():
    m = _load()
    rows = [{"memory_id": "m", "task_id": "t", "stratum": "BEARING", "with": 1.0, "without": 0.0},
            {"memory_id": "m", "task_id": "t", "stratum": "BEARING", "with": None, "without": 0.0}]
    assert m.cells(rows) == {("m", "t", "BEARING"): 1.0}

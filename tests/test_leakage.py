"""Tests for the leakage detector.

The central test is not "does it find leaks" but "can it be shown to FAIL".
A detector only ever run on clean data has detected nothing known.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters import leakage  # noqa: E402

DATA_ROOT = Path(os.environ.get("LMEV2_ROOT", "/tmp/lmev2"))
needs_data = pytest.mark.skipif(
    not (DATA_ROOT / "questions.jsonl").exists(), reason="LMEv2 data absent"
)


def test_all_detector_controls_pass() -> None:
    ok, res = leakage.controls_summary()
    failed = [(r.name, r.detector, r.expected, r.observed) for r in res if not r.passed]
    assert ok, f"detector controls FAILED: {failed}"
    assert len(res) >= 15, "control suite has shrunk -- fewer cases than expected"


def test_controls_include_both_polarities() -> None:
    """A suite of only-positive or only-negative controls proves little."""
    res = leakage.prove_detector_can_fail()
    assert any(r.expected for r in res), "no positive control in the suite"
    assert any(not r.expected for r in res), "no negative control in the suite"


def test_detectors_are_not_all_the_same_test() -> None:
    """At least one case must separate each pair of detectors.

    If exact and normalized always agreed, reporting both would be padding.
    """
    res = leakage.prove_detector_can_fail()
    by_case: dict[str, dict[str, bool]] = {}
    for r in res:
        by_case.setdefault(r.name, {})[r.detector] = r.observed
    disagree = [
        n for n, d in by_case.items()
        if "exact" in d and "normalized" in d and d["exact"] != d["normalized"]
    ]
    assert disagree, "exact and normalized never disagree -- one is redundant"


def test_undecidable_is_none_not_false() -> None:
    """LLM-judged questions must not be silently scored as 'no leak'."""
    v = leakage.detect(
        "some memory text", "some gold",
        eval_function_spec="llm_abstention_checker|require_non_empty=true",
    )
    assert v.official is None
    assert v.undecidable is True
    assert "official_scorer_undecidable_llm_judged" in v.notes


def test_non_string_gold_answer_is_flagged_not_crashed() -> None:
    """LongMemEval-V1 stores 32 of 500 gold answers as bare ints."""
    v = leakage.detect("the count is 3 items", 3)
    assert v.exact is True
    assert any(n.startswith("gold_answer_not_a_string") for n in v.notes)
    assert "degenerate_short_gold_answer" in v.notes


def test_degenerate_short_answers_are_flagged() -> None:
    v = leakage.detect("a long memory mentioning B somewhere", "B")
    assert "degenerate_short_gold_answer" in v.notes


def test_verdict_has_no_drop_affordance() -> None:
    """Policy is FLAG, NEVER DROP -- enforced by the API shape."""
    v = leakage.detect("x", "y")
    assert not any(
        hasattr(v, a) for a in ("drop", "exclude", "filter", "remove")
    )


def test_numeric_none_means_not_applicable() -> None:
    v = leakage.detect("memory with no digits", "purely textual answer")
    assert v.numeric is None, "no number in gold -> detector is N/A, not 'clean'"


def test_numeric_tolerance_is_configurable_and_binds() -> None:
    assert leakage.numeric_leak("saw 100.5", "100", rel_tol=0.01) is True
    assert leakage.numeric_leak("saw 100.5", "100", rel_tol=1e-9) is False


def test_baseline_cleanliness_guard_actually_raises() -> None:
    """Positive control for the guard that caught my broken control."""
    with pytest.raises(AssertionError):
        leakage._assert_baseline_clean("a memory about Reports", "Reports", "probe")


@needs_data
def test_our_normalizer_agrees_with_the_official_one_on_real_gold_answers() -> None:
    """Drift between our normalizer and the benchmark's must be caught.

    leakage.normalize_text exists only so the module also works for
    benchmarks that ship no scorer. Where the official one exists, they must
    agree -- otherwise the V1 and V2 numbers are not comparable.
    """
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import normalize_phrase

    rows = [
        json.loads(line)
        for line in (DATA_ROOT / "questions.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 451
    mismatches = [
        (r["id"], leakage.normalize_text(r["answer"]), normalize_phrase(r["answer"]))
        for r in rows
        if leakage.normalize_text(r["answer"]) != normalize_phrase(r["answer"])
    ]
    assert not mismatches, f"normalizer drift on {len(mismatches)} answers: {mismatches[:3]}"

"""Semantic-type labelling, and honest reporting of inter-pass agreement."""
from __future__ import annotations

import pytest

from p1mem.memory import semantic_type as ST
from p1mem.memory.segment import SourceSegment


def seg(text: str) -> SourceSegment:
    return SourceSegment(segment_id="s:0-0", benchmark="b", benchmark_version="0",
                         source_episode_id="e", text=text, source_span={"i": 0})


class FakeRec:
    latency_s, input_tokens, output_tokens, retry_count = 0.5, 100, 3, 0
    finish_reason, cache_hit, reasoning_tokens = "stop", False, 10


class FakeClient:
    cache = None
    cluster, model = "metis", "gpt-oss-120b"

    def __init__(self, replies, raises=None):
        self.replies, self.raises, self.calls = list(replies), raises, []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        if self.raises:
            raise self.raises
        return self.replies.pop(0), FakeRec()


def test_labels_are_the_protocol_four():
    assert ST.SEMANTIC_TYPES == (
        "episodic", "semantic_fact", "procedural", "failure_reflection")


@pytest.mark.parametrize("reply,expect", [
    ("procedural", "procedural"),
    ("  Episodic  ", "episodic"),
    ("semantic_fact.", "semantic_fact"),
    ("`failure_reflection`", "failure_reflection"),
    ("semantic fact", "semantic_fact"),
    ("failure-reflection", "failure_reflection"),
])
def test_classifier_parses_a_compliant_answer(reply, expect):
    lab = ST.SemanticTypeClassifier(FakeClient([reply])).classify(seg("x"))
    assert lab.semantic_type == expect and lab.ok


@pytest.mark.parametrize("reply", [
    "I think this is probably procedural, because the agent clicks things.",
    "none of the above",
    "",
    "1",
])
def test_negative_control_a_non_compliant_answer_is_a_recorded_failure(reply):
    """NEGATIVE CONTROL. Fishing a category word out of a paragraph would count a
    non-compliant answer as compliant and hide the real compliance rate."""
    lab = ST.SemanticTypeClassifier(FakeClient([reply])).classify(seg("x"))
    assert lab.ok is False
    assert lab.error_code == "classifier_unparseable"
    assert lab.semantic_type == ST.DEFAULT_TYPE, "falls back, but flagged as a fallback"


def test_classifier_call_failure_is_recorded_not_raised():
    lab = ST.SemanticTypeClassifier(FakeClient([], raises=RuntimeError("boom"))).classify(seg("x"))
    assert lab.ok is False and lab.error_code.startswith("classifier_call_failed")
    assert lab.calls == 1


def test_classifier_prompt_sees_only_the_segment_text():
    c = FakeClient(["episodic"])
    ST.SemanticTypeClassifier(c).classify(seg("UNIQUE-BODY"))
    assert "UNIQUE-BODY" in c.calls[0][0]["content"]


def test_heuristic_is_deterministic_and_costs_nothing():
    a = ST.heuristic_semantic_type(seg("Traceback: failed to submit"))
    b = ST.heuristic_semantic_type(seg("Traceback: failed to submit"))
    assert a.semantic_type == b.semantic_type == "failure_reflection"
    assert a.calls == 0 and a.source == "heuristic"


def test_heuristic_is_labelled_as_a_heuristic_everywhere():
    """It must never be indistinguishable from a real classification."""
    lab = ST.heuristic_semantic_type(seg("click the button"))
    assert lab.source == "heuristic"
    assert lab.prompt_version == ST.HEURISTIC_RULE_VERSION


# ------------------------------------------------ agreement reporting honesty
def test_agreement_reports_kappa_alongside_raw():
    pairs = [("episodic", "episodic")] * 8 + [("episodic", "procedural")] * 2
    rep = ST.agreement_report(pairs)
    assert rep["n"] == 10 and rep["n_agree"] == 8
    assert rep["raw_agreement"] == pytest.approx(0.8)
    assert "cohens_kappa" in rep


def test_kappa_is_none_when_chance_agreement_is_total():
    """Both passes used one category: raw agreement is 1.0 and means NOTHING.

    Returning a number there would dress up a vacuous result. None is honest.
    """
    rep = ST.agreement_report([("episodic", "episodic")] * 20)
    assert rep["raw_agreement"] == 1.0
    assert rep["cohens_kappa"] is None
    assert "no information" in rep["interpretation"]


def test_kappa_penalises_a_skewed_corpus():
    """90% raw agreement on a 95/5 prior is close to chance, and kappa says so."""
    pairs = [("episodic", "episodic")] * 90 + [("episodic", "procedural")] * 5 \
        + [("procedural", "episodic")] * 5
    rep = ST.agreement_report(pairs)
    assert rep["raw_agreement"] == pytest.approx(0.90)
    assert rep["cohens_kappa"] is not None and rep["cohens_kappa"] < 0.5, (
        "kappa must expose that raw agreement is inflated by a skewed prior")


def test_confusion_matrix_shows_which_pair_disagrees():
    pairs = [("procedural", "episodic")] * 3 + [("episodic", "episodic")] * 2
    rep = ST.agreement_report(pairs)
    assert rep["confusion_a_by_b"]["procedural"]["episodic"] == 3
    text = ST.format_agreement_report(rep)
    assert "confusion" in text and "procedural" in text


def test_report_states_it_is_not_accuracy():
    rep = ST.agreement_report([("episodic", "procedural")])
    assert "no gold label" in rep["interpretation"]


def test_paired_labels_drops_unmatched_segments():
    """NEGATIVE CONTROL for a half-join: a segment missing one pass is not a
    disagreement, and counting it either way would be a fabricated number."""
    by_seg = {
        "a": {"native": "episodic", "clf": "episodic"},
        "b": {"native": "procedural"},               # classifier missing
        "c": {"clf": "episodic"},                    # native missing
    }
    pairs = ST.paired_labels(by_seg, "native", "clf")
    assert pairs == [("episodic", "episodic")]

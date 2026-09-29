"""The three representations: determinism, cost accounting, and JSON validation."""
from __future__ import annotations

import json

import pytest

from p1mem.memory import metrics as MT
from p1mem.memory import representations as R
from p1mem.memory.prompts import load_prompt
from p1mem.memory.segment import SourceSegment, segment_content_id

SRC_TEXT = (
    "### Trajectory span 1: t1 states 0-1\n\n"
    "Goal\n- Order 3 more Apple Watches\n\n"
    "Start URL\n- https://example.service-now.com/nav\n\n"
    "Actions\n1. click('42')\n\n"
    "Linked state evidence\n"
    "State 0 (step 0)\n- URL: https://example.service-now.com/nav\n"
    "- Action: click('42')\n- AXTree:\nStock count: 12\nStatus: Open\n"
)


def seg(text: str = SRC_TEXT) -> SourceSegment:
    return SourceSegment(
        segment_id="t1:0-1", benchmark="longmemeval_v2", benchmark_version="2cc8c540",
        source_episode_id="t1", text=text,
        source_span={"trajectory_id": "t1", "start_state_index": 0, "end_state_index": 1},
        episode_metadata={"domain": "enterprise", "outcome": "success"},
    )


class FakeRec:
    def __init__(self, **kw):
        self.latency_s = kw.get("latency_s", 1.25)
        self.input_tokens = kw.get("input_tokens", 400)
        self.output_tokens = kw.get("output_tokens", 90)
        self.reasoning_tokens = kw.get("reasoning_tokens", 40)
        self.retry_count = kw.get("retry_count", 0)
        self.finish_reason = kw.get("finish_reason", "stop")
        self.cache_hit = kw.get("cache_hit", False)


class FakeClient:
    """Stand-in for Sub-agent C's P1Client. Same (content, CallRecord) contract."""

    cache = None

    def __init__(self, replies, *, cluster="metis", model="gpt-oss-120b", raises=None):
        self.replies = list(replies)
        self.cluster, self.model = cluster, model
        self.raises = raises
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append((messages, kw))
        if self.raises is not None:
            raise self.raises
        return self.replies.pop(0), FakeRec()


# ------------------------------------------------------------------- A. raw
def test_raw_is_the_segment_verbatim_and_costs_nothing():
    rec = R.RawExtractiveWriter().write(seg())
    assert rec.ok and rec.representation == "raw"
    assert rec.memory_text == SRC_TEXT, "raw must be the span verbatim"
    assert rec.extraction_calls == 0
    # NULL, not 0.0: schema.py is explicit that null means 'no call'.
    assert rec.extraction_latency_s is None
    assert rec.extraction_input_tokens is None
    assert rec.extraction_output_tokens is None
    assert rec.writer_model == "none:deterministic_span"
    assert rec.writer_cluster == "none:deterministic_span"


def test_raw_is_deterministic_across_calls_and_instances():
    a = R.RawExtractiveWriter().write(seg())
    b = R.RawExtractiveWriter().write(seg())
    assert a.memory_text == b.memory_text
    assert a.memory_content_id == b.memory_content_id
    assert a.source_span["text_sha256"] == b.source_span["text_sha256"]


def test_raw_span_is_rederivable():
    rec = R.RawExtractiveWriter().write(seg())
    sp = rec.source_span
    for k in ("trajectory_id", "start_state_index", "end_state_index",
              "span_rule_version", "extraction", "text_sha256"):
        assert k in sp, f"memory_source_span missing {k}"
    from p1mem.vendor.rcc_schema import sha256_text
    assert sp["text_sha256"] == sha256_text(SRC_TEXT)


def test_raw_compression_ratio_is_exactly_one():
    rec = R.RawExtractiveWriter().write(seg())
    if rec.memory_tokens is not None:
        assert rec.compression_ratio == 1.0


def test_raw_does_not_select_a_subspan():
    """Protocol §1A forbids 'pick the most informative span'.

    Two segments differing only in which half looks informative must both be
    returned whole. If raw ever starts choosing, this fails.
    """
    a = R.RawExtractiveWriter().write(seg("boring boring boring"))
    b = R.RawExtractiveWriter().write(seg("boring ANSWER=42 boring"))
    assert a.memory_text == "boring boring boring"
    assert b.memory_text == "boring ANSWER=42 boring"


# --------------------------------------------------------------- B. summary
def test_summary_makes_exactly_one_call_and_records_its_cost():
    c = FakeClient(["The agent opened the stock dashboard and saw 12 items."])
    rec = R.SummaryWriter(c).write(seg())
    assert rec.ok and rec.representation == "summary"
    assert len(c.calls) == 1
    assert rec.extraction_calls == 1
    assert rec.extraction_latency_s == 1.25
    assert rec.extraction_input_tokens == 400 and rec.extraction_output_tokens == 90
    assert rec.extraction_reasoning_tokens == 40
    assert rec.writer_model == "gpt-oss-120b" and rec.writer_cluster == "metis"
    assert rec.prompt_version.startswith("summary_v1@1.0.0+")


def test_summary_prompt_carries_only_the_segment_text():
    c = FakeClient(["ok"])
    R.SummaryWriter(c).write(seg())
    sent = c.calls[0][0][0]["content"]
    assert SRC_TEXT in sent
    assert "enterprise" not in sent, "episode_metadata leaked into the prompt"


def test_summary_records_a_failed_call_instead_of_raising():
    from p1mem.client import TruncatedResponseError
    c = FakeClient([], raises=TruncatedResponseError("length with empty content"))
    rec = R.SummaryWriter(c).write(seg())
    assert rec.ok is False
    assert rec.error_code == R.ERR_CALL_FAILED
    assert "TruncatedResponseError" in rec.error_detail
    assert rec.memory_text == "", "a failed write must not produce a usable memory"
    assert rec.extraction_calls == 1, "a failed call still cost a call"


def test_summary_empty_content_is_a_failure_not_an_empty_memory():
    rec = R.SummaryWriter(FakeClient(["   \n  "])).write(seg())
    assert rec.ok is False and rec.error_code == R.ERR_EMPTY_CONTENT


# ------------------------------------------------------------ C. structured
GOOD = {
    "memory_type": "episodic", "situation": "Stock dashboard open",
    "action": "Clicked element 42", "outcome": "Saw 12 items in stock",
    "lesson": "Counts are on the dashboard", "scope": "ServiceNow stock views",
    "confidence": "high",
}


def test_structured_valid_json_is_parsed_validated_and_rendered():
    rec = R.StructuredWriter(FakeClient([json.dumps(GOOD)])).write(seg())
    assert rec.ok and rec.structured == GOOD
    assert rec.native_semantic_type == "episodic"
    # Rendering uses the SCHEMA key order, not the dict's.
    assert rec.memory_text.split("\n")[0].startswith("memory_type:")
    assert rec.memory_text.split("\n")[-1].startswith("confidence:")


def test_structured_rendering_is_key_order_independent():
    a = R.StructuredWriter(FakeClient([json.dumps(GOOD)])).write(seg())
    shuffled = dict(reversed(list(GOOD.items())))
    b = R.StructuredWriter(FakeClient([json.dumps(shuffled)])).write(seg())
    assert a.memory_text == b.memory_text, (
        "two structurally identical memories must render byte-identically, or their "
        "token counts are not comparable")


def test_structured_accepts_a_markdown_fence():
    body = "```json\n" + json.dumps(GOOD) + "\n```"
    assert R.StructuredWriter(FakeClient([body])).write(seg()).ok


def test_structured_accepts_surrounding_prose_via_brace_scan():
    body = "Here is the memory:\n" + json.dumps(GOOD) + "\nHope that helps."
    assert R.StructuredWriter(FakeClient([body])).write(seg()).ok


@pytest.mark.parametrize("bad,code", [
    ("not json at all", R.ERR_MALFORMED_JSON),
    ('{"memory_type": "episodic"', R.ERR_MALFORMED_JSON),
    ("[1,2,3]", R.ERR_MALFORMED_JSON),
    (json.dumps({k: v for k, v in GOOD.items() if k != "lesson"}), R.ERR_MISSING_KEYS),
    (json.dumps({**GOOD, "extra": "x"}), R.ERR_EXTRA_KEYS),
    (json.dumps({**GOOD, "memory_type": "anecdote"}), R.ERR_BAD_ENUM),
    (json.dumps({**GOOD, "confidence": "very high"}), R.ERR_BAD_ENUM),
    (json.dumps({**GOOD, "outcome": 12}), R.ERR_NON_STRING),
    (json.dumps({**GOOD, "outcome": None}), R.ERR_NON_STRING),
    (json.dumps({**GOOD, "scope": {"a": 1}}), R.ERR_NON_STRING),
    (json.dumps({**GOOD, "lesson": "   "}), R.ERR_NON_STRING),
])
def test_negative_control_malformed_structures_are_recorded_failures(bad, code):
    """NEGATIVE CONTROL: each planted defect must be CAUGHT and CLASSIFIED.

    Not a silent fallback to prose (protocol §1C), and not a generic failure:
    the specific code matters because the malformed-JSON RATE is reported.
    """
    rec = R.StructuredWriter(FakeClient([bad])).write(seg())
    assert rec.ok is False
    assert rec.error_code == code, f"got {rec.error_code}, expected {code}"
    assert rec.memory_text == "", "a malformed structure must not become a memory"
    assert rec.raw_model_output == bad, "the malformed output must be KEPT for review"


def test_structured_never_falls_back_to_prose():
    """The specific failure the protocol names."""
    prose = "The agent looked at the dashboard and saw twelve items."
    rec = R.StructuredWriter(FakeClient([prose])).write(seg())
    assert rec.ok is False
    assert prose not in rec.memory_text


def test_structured_no_key_repair():
    """A repaired structure is a DIFFERENT structure and would understate the rate."""
    near = json.dumps({**{k: v for k, v in GOOD.items() if k != "situation"},
                       "situuation": "typo"})
    rec = R.StructuredWriter(FakeClient([near])).write(seg())
    assert rec.ok is False and rec.error_code == R.ERR_MISSING_KEYS


def test_procedural_variant_uses_the_protocol_schema():
    w = R.StructuredWriter(FakeClient(["{}"]), variant="procedural")
    assert w.keys == ("memory_type", "trigger", "procedure", "failure_mode",
                      "successful_correction", "scope", "confidence")
    assert w.prompt.name == "structured_procedural_v1"


def test_procedural_variant_roundtrips():
    obj = {"memory_type": "procedural", "trigger": "t", "procedure": "p",
           "failure_mode": "none observed", "successful_correction": "not applicable",
           "scope": "s", "confidence": "medium"}
    rec = R.StructuredWriter(FakeClient([json.dumps(obj)]), variant="procedural").write(seg())
    assert rec.ok and rec.native_semantic_type == "procedural"


# --------------------------------------------------- shared-segment invariant
def test_write_all_uses_one_segment_for_all_three():
    s = seg()
    c = FakeClient(["a summary", json.dumps(GOOD)])
    out = R.write_all(s, raw=R.RawExtractiveWriter(),
                      summary=R.SummaryWriter(c), structured=R.StructuredWriter(c))
    assert set(out) == {"raw", "summary", "structured"}
    ids = {r.memory_content_id for r in out.values()}
    assert len(ids) == 1, "all three must derive from the SAME source segment"
    assert all(r.source_episode_id == "t1" for r in out.values())
    # Both model writers saw byte-identical segment text.
    assert SRC_TEXT in c.calls[0][0][0]["content"]
    assert SRC_TEXT in c.calls[1][0][0]["content"]


def test_metrics_keep_raws_zero_and_exclude_its_null_latency():
    s = seg()
    c = FakeClient(["a summary", json.dumps(GOOD)])
    recs = list(R.write_all(s, raw=R.RawExtractiveWriter(),
                            summary=R.SummaryWriter(c),
                            structured=R.StructuredWriter(c)).values())
    st = MT.summarise(recs)
    assert st["raw"].extraction_calls_total == 0
    assert st["raw"].latency_mean_s is None, "raw has no latency to average"
    assert st["raw"].latency_n == 0
    assert st["raw"].extraction_input_tokens_total is None, (
        "no call was made; None, not 0, or the frontier implies a call billing zero")
    assert st["summary"].extraction_calls_total == 1
    assert st["summary"].latency_n == 1 and st["summary"].latency_mean_s == 1.25
    table = MT.frontier_table(st)
    assert "raw" in table and "NO CALL WAS MADE" in table


def test_failed_writes_still_charge_their_call():
    recs = [R.SummaryWriter(FakeClient(["  "])).write(seg()) for _ in range(3)]
    st = MT.summarise(recs)
    assert st["summary"].n_failed == 3
    assert st["summary"].extraction_calls_total == 3, (
        "a failed write burned a call; dropping it under-charges the representation")

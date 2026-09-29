"""Faithfulness proxies: the positive control, planted defects, and the gaps.

Two kinds of test here, and both are necessary:

* **Planted hallucinations** that the proxy MUST catch. A check never run
  against the defect it is for is not known to detect anything.
* **Planted hallucinations that it MUST NOT catch** -- the documented blind
  spots, asserted as tests. Writing the limitation into a docstring and then
  never testing it lets the limitation quietly become false (or quietly get
  worse) without anyone noticing. These tests fail if someone later claims the
  proxy catches recombination.
"""
from __future__ import annotations

import pytest

from p1mem.memory import faithfulness as F

SOURCE = (
    "State 0 (step 0)\n"
    "- URL: https://shop.example.com/cart\n"
    "- Action: click('checkout')\n"
    "- AXTree:\n"
    "Status: Open\n"
    "Item: Apple Watch Series 9\n"
    "Stock count: 12\n"
    "Order total: 249.99\n"
)


# ------------------------------------------------- the positive control
def test_raw_control_scores_perfect():
    """The source against itself MUST be 1.0. Otherwise the proxy is broken.

    This is the check that makes every other number here meaningful: a
    tokenisation or normalisation asymmetry would show up as raw scoring
    below 1.0, and then every score the proxy produced is suspect.
    """
    s = F.raw_control(SOURCE)
    assert s.number_support == 1.0, f"unsupported numbers: {s.unsupported_numbers}"
    assert s.entity_support == 1.0, f"unsupported entities: {s.unsupported_entities}"
    assert s.n_bindings_contradicted == 0
    assert s.flagged is False


def test_a_faithful_summary_scores_well():
    mem = ("The agent opened the cart at https://shop.example.com/cart and clicked "
           "checkout. Stock count: 12. Order total: 249.99. Status: Open.")
    s = F.score_text(mem, SOURCE, representation="summary")
    assert s.number_support == 1.0
    assert s.entity_support == 1.0
    assert s.n_bindings_contradicted == 0


# --------------------------------------------- planted defects it MUST catch
def test_catches_an_invented_number():
    mem = "The agent saw 47 items in stock."
    s = F.score_text(mem, SOURCE, representation="summary")
    assert s.number_support is not None and s.number_support < 1.0
    assert "47" in s.unsupported_numbers
    assert s.flagged


def test_catches_an_invented_entity():
    mem = "The agent opened the Samsung Galaxy listing."
    s = F.score_text(mem, SOURCE, representation="summary")
    assert s.entity_support is not None and s.entity_support < 1.0
    assert any("Samsung" in e or "Galaxy" in e for e in s.unsupported_entities)


def test_catches_an_invented_url():
    mem = "The agent went to https://evil.example.org/admin."
    s = F.score_text(mem, SOURCE, representation="summary")
    assert any("evil.example.org" in e for e in s.unsupported_entities)


def test_catches_a_contradicted_explicit_value():
    mem = "Status: Closed\nStock count: 12\n"
    s = F.score_text(mem, SOURCE, representation="structured")
    assert s.n_bindings_contradicted >= 1
    keys = {c["key"] for c in s.contradictions}
    assert "status" in keys
    assert s.flagged


def test_a_memory_longer_than_its_source_is_flagged():
    s = F.score_text(SOURCE + SOURCE, SOURCE, representation="summary")
    assert s.length_ratio is not None and s.length_ratio > 1.0
    assert s.flagged


def test_a_binding_never_spans_a_line_break():
    """REGRESSION. The planted-contradiction test above found this.

    The binding regex originally used ``\\s*`` around the separator. With
    ``re.M``, ``\\s`` matches a NEWLINE, so a bare key line ("- AXTree:")
    swallowed the value off the FOLLOWING line. The source then carried no
    ``status`` binding at all, and a memory asserting "Status: Closed" against
    a source saying "Status: Open" scored as NO CONTRADICTION -- a silent
    false negative on the one thing the check exists to catch.

    It was invisible on every case the proxy had been run on, because those
    cases had no bare key line. A check only exercised on its home case is not
    known to discriminate.
    """
    from p1mem.memory.faithfulness import _bindings
    b = _bindings("- AXTree:\nStatus: Open\n")
    assert b.get("status") == {"open"}, f"status binding lost: {b}"
    assert "open" not in b.get("axtree", set()), "a binding consumed the next line"


def test_multiple_source_bindings_do_not_manufacture_a_contradiction():
    src = "- URL: https://a.example.com/x\n- URL: https://b.example.com/y\n"
    mem = "- URL: https://b.example.com/y\n"
    s = F.score_text(mem, src, representation="summary")
    assert s.n_bindings_contradicted == 0, (
        "a source binding a key several times must not make a memory naming one "
        "of them a contradiction")


# ------------------------------- the documented blind spots, asserted as tests
def test_BLIND_SPOT_recombination_is_not_caught():
    """Every token present, relation false. The biggest gap, and it is real."""
    mem = "The agent ordered 12 Apple Watch Series 9 units for 249.99 each."
    s = F.score_text(mem, SOURCE, representation="summary")
    assert s.number_support == 1.0
    assert s.entity_support == 1.0
    assert s.n_bindings_contradicted == 0
    assert s.flagged is False, (
        "if this now FAILS the proxy has improved -- update PROXY_LIMITATIONS and "
        "this test together, and re-state the claim wherever the scores are quoted")


def test_BLIND_SPOT_omission_scores_perfect():
    s = F.score_text("The agent clicked something.", SOURCE, representation="summary")
    assert s.number_support is None, "no numbers to check is None, not 1.0"
    assert s.n_bindings_contradicted == 0


def test_BLIND_SPOT_unsupported_inference_passes():
    s = F.score_text("The user was frustrated by the slow page.", SOURCE,
                     representation="summary")
    assert s.n_bindings_contradicted == 0
    assert s.number_support is None


def test_BLIND_SPOT_negation_in_prose_passes():
    s = F.score_text("The checkout did not complete.", SOURCE, representation="summary")
    assert s.n_bindings_contradicted == 0


def test_FALSE_ALARM_faithful_paraphrase_is_penalised():
    """Conservative for entities: a renaming paraphrase is scored unsupported.

    Asserted so the direction of the error is a measured property, not a claim.
    """
    s = F.score_text("The agent viewed the smartwatch product page.", SOURCE,
                     representation="summary")
    assert s.entity_support is None or s.entity_support < 1.0


# ---------------------------------------------------- null / aggregate handling
def test_empty_denominator_is_none_not_one():
    s = F.score_text("clicked a thing", SOURCE)
    assert s.number_support is None and s.entity_support is None


def test_aggregate_excludes_nulls_from_denominators():
    scores = [
        F.score_text("saw 12 items", SOURCE),                 # has a number
        F.score_text("clicked a thing", SOURCE),              # has none
        F.score_text("saw 47 items", SOURCE),                 # has a bad number
    ]
    agg = F.aggregate(scores)
    assert agg["n_scored"] == 3
    assert agg["n_with_numbers"] == 2, "the number-less memory must not be counted"
    assert agg["mean_number_support"] == pytest.approx(0.5)
    assert agg["limitations"], "aggregate must ship its own caveats"


def test_score_record_skips_raw_and_failed_writes():
    class Rec:
        representation, ok, memory_text = "raw", True, SOURCE
    assert F.score_record(Rec(), SOURCE) is None

    class Bad:
        representation, ok, memory_text = "summary", False, ""
    assert F.score_record(Bad(), SOURCE) is None


def test_llm_judge_is_not_silently_available():
    with pytest.raises(NotImplementedError):
        F.llm_judge_faithfulness("a", "b")

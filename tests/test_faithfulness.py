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


# ============================================================================
# REGRESSIONS FOUND BY raw_control ON REAL LongMemEval-V2 SEGMENTS (B6 pilot).
#
# Both were silent: the proxy produced plausible sub-1.0 scores and nothing
# looked wrong. Only self-scoring the SOURCE -- which must be exactly 1.0 --
# exposed them. This is the value of a positive control that MUST pass: a
# faithfulness proxy that flags the source as unfaithful to ITSELF is
# measuring its own normalisation, not the memory.
# ============================================================================

def test_regression_a_comma_separated_arg_list_is_not_one_number():
    """``scroll(0, 800)`` is TWO numbers, not the number 0,800.

    The extractor was ``\\d[\\d,]*``, which accepted any comma. A web-agent
    trajectory is full of ``scroll(0, 800)`` calls, so a verbatim copy of the
    source contained the invented number "0800" and scored 0.9857 against
    itself. A thousands separator only precedes exactly three digits.
    """
    from p1mem.memory.faithfulness import _numbers
    assert _numbers("scroll(0, 800)") == ["0", "800"]
    assert _numbers("scroll(0,800)") == ["0", "800"]
    assert _numbers("total 2,004.99") == ["2004.99"]
    assert _numbers("1,234,567 rows") == ["1234567"]
    assert _numbers("state-12 step 3") == ["12", "3"]
    # LENIENT where genuinely ambiguous: "scroll(1,800)" is read as 1800,
    # same as the money amount it is indistinguishable from. A false alarm on
    # a verbatim copy is worse than a missed flag, because it makes the
    # proxy's own noise look like a hallucination.
    assert _numbers("scroll(1,800)") == ["1800"]


def test_regression_a_number_matches_itself_across_comma_normalisation():
    """"$2,004.99" in the source must support "2004.99" in the memory.

    The extractor stripped thousands separators but the lookup searched a
    source that still had them, so a number could fail to match itself. That
    is a false alarm on the most consequential check we have.
    """
    src = "[1573] gridcell '$2,004.99'\n"
    s = F.score_text("The order total was $2,004.99.", src)
    assert s.number_support == 1.0, f"unsupported: {s.unsupported_numbers}"
    assert F.raw_control(src).number_support == 1.0


def test_regression_raw_control_passes_on_real_corpus_segments():
    """The control, run WIDE: every sampled real segment must self-score 1.0.

    A check run only on its home case is not known to discriminate. The two
    defects above were both invisible on the hand-written fixture at the top
    of this file and both appeared the moment the control met real data.
    """
    import json
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    manifest = repo / "data" / "manifests" / "lmev2_memory_units_small.jsonl"
    traj = Path("/tmp/lmev2/trajectories.jsonl")
    if not manifest.is_file() or not traj.is_file():
        pytest.skip("LongMemEval-V2 corpus not present on this machine")

    from p1mem.adapters import lmev2

    units = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
    want_trajs = sorted({u["trajectory_id"] for u in units})[:4]
    checked = 0
    for t in lmev2.read_jsonl(traj):
        if t["id"] not in want_trajs:
            continue
        for pv in lmev2.segment_page_visits(t)[:5]:
            sc = F.raw_control(pv.text)
            assert sc.number_support == 1.0, (
                f"{pv.memory_id}: source is not faithful to ITSELF; "
                f"unsupported numbers {sc.unsupported_numbers[:5]}")
            assert sc.entity_support == 1.0, (
                f"{pv.memory_id}: unsupported entities {sc.unsupported_entities[:5]}")
            assert sc.n_bindings_contradicted == 0
            checked += 1
        want_trajs.remove(t["id"])
        if not want_trajs:
            break
    assert checked >= 5, f"only {checked} real segments checked; may be vacuous"


def test_scope_collision_is_counted_separately_but_still_reported():
    """MEASURED in the B6 pilot: both 'contradictions' were this artifact.

    The structured schema has one per-SEGMENT ``action`` field; the source
    binds ``- Action:`` once per STATE. A correct summary of several actions
    therefore "contradicts" the one action the source binds. That is a scope
    collision, not a hallucination.

    It must be COUNTED (suppressing the key would hide a real contradiction
    that happens to land there) and reported SEPARATELY (so the headline rate
    is not a known artifact quoted as a hallucination rate).
    """
    src = "- Action: click('227')\n"
    mem = "action: clicked 227, then 1530, then sent a message to the user\n"
    s = F.score_text(mem, src, representation="structured")
    assert s.n_bindings_checked == 1
    assert s.n_bindings_contradicted == 1
    assert s.n_bindings_scope_collision == 1
    assert s.contradiction_rate == 1.0
    assert s.contradiction_rate_excl_scope_collision == 0.0
    assert s.contradictions[0]["scope_collision"] is True


def test_a_non_colliding_key_is_a_real_contradiction():
    """NEGATIVE CONTROL for the exemption: it must not swallow everything."""
    s = F.score_text("stock count: 99\n", "Stock count: 12\n", representation="structured")
    assert s.n_bindings_contradicted == 1
    assert s.n_bindings_scope_collision == 0
    assert s.contradiction_rate_excl_scope_collision == 1.0


def test_aggregate_ships_the_contradiction_caveat():
    # NOTE the fixture: the memory value must not CONTAIN the source value,
    # or the lenient substring check correctly finds it supported. An earlier
    # draft used "action: a, b" against "- Action: a" and measured nothing --
    # the assertion would have passed for the wrong reason had it been weaker.
    agg = F.aggregate([F.score_text("action: clicked 1530 then 1641\n",
                                    "- Action: click('227')\n")])
    assert agg["mean_contradiction_rate"] == 1.0
    assert agg["mean_contradiction_rate_excl_scope_collision"] == 0.0
    assert agg["n_scope_collisions"] == 1
    assert "UPPER BOUND" in agg["_contradiction_caveat"]

"""Unit tests for the LongMemEval-V2 adapter's scoring path.

Two things are under test and they are different:

1. That we call the OFFICIAL scorer, unmodified. Guarded by a sha256 pin.
2. That the scorer behaves as we claim in the report. Every assertion below
   uses a REAL gold answer taken from the shipped questions.jsonl, not an
   invented string, because the point is to characterise the actual scorer
   on the actual data.

Note on what a passing test means here: feeding the gold answer back as the
prediction is a positive control that proves the harness is wired up, but on
its own it proves almost nothing about discrimination. So every such case is
paired with a NEGATIVE case that must score False. A scorer that returned
True unconditionally would pass the positive half alone.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: E402
    eval_from_spec,
    mc_choice_match,
    mc_choice_set_match,
    norm_phrase_set_match,
    norm_phrase_set_match_ordered,
    normalize_phrase,
)

DATA_ROOT = Path(os.environ.get("LMEV2_ROOT", "/tmp/lmev2"))
needs_data = pytest.mark.skipif(
    not (DATA_ROOT / "questions.jsonl").exists(),
    reason=f"LongMemEval-V2 questions.jsonl not present under {DATA_ROOT}",
)


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------


def test_vendored_scorer_is_byte_exact_upstream() -> None:
    """The whole design rests on not having reimplemented the scorer."""
    assert lmev2.verify_vendored_scorer() == lmev2.VENDORED_SCORER_SHA256


@needs_data
def test_data_files_match_shipped_checksums() -> None:
    report = lmev2.verify_checksums(DATA_ROOT, strict=False)
    assert report == {name: "OK" for name in lmev2.EXPECTED_FILES}, report


# --------------------------------------------------------------------------
# scorer semantics, characterised on real data
# --------------------------------------------------------------------------


@needs_data
def test_every_gold_answer_scores_itself_correct() -> None:
    """Positive control across ALL 295 deterministic questions.

    Weak on its own -- see the negative-control test below -- but it is the
    check that would catch a spec string we cannot dispatch, a separator we
    mis-parsed, or a gold answer whose own normalization is empty.
    """
    tasks = [t for t in lmev2.load_tasks(DATA_ROOT) if t.deterministic]
    assert len(tasks) == 295, f"expected 295 deterministic tasks, got {len(tasks)}"
    failures = [t.id for t in tasks if not t.score(t.answer)]
    assert not failures, f"gold answer failed its own scorer for: {failures}"


@needs_data
def test_scorer_rejects_a_wrong_answer_for_every_question() -> None:
    """NEGATIVE control: the scorer must be able to return False.

    Without this, the positive control above is satisfied by a scorer that
    always returns True. Uses a fixed nonsense prediction that shares no
    tokens with any gold answer.
    """
    tasks = [t for t in lmev2.load_tasks(DATA_ROOT) if t.deterministic]
    nonsense = "zzqqxx nonsense prediction 90210 unrelated"
    wrongly_accepted = [t.id for t in tasks if t.score(nonsense)]
    assert not wrongly_accepted, (
        f"scorer accepted a nonsense prediction for: {wrongly_accepted}"
    )


@needs_data
def test_empty_prediction_never_scores_correct() -> None:
    tasks = [t for t in lmev2.load_tasks(DATA_ROOT) if t.deterministic]
    assert not [t.id for t in tasks if t.score("")]


@needs_data
def test_llm_judged_questions_raise_rather_than_default() -> None:
    """A missing judge must not silently become a score of False.

    This is the 'absence becomes a plausible zero' failure mode: if score()
    returned False for LLM-judged items, 156 of 451 questions would quietly
    read as 'model got it wrong' in every arm.
    """
    tasks = [t for t in lmev2.load_tasks(DATA_ROOT) if not t.deterministic]
    assert len(tasks) == 156, f"expected 156 LLM-judged tasks, got {len(tasks)}"
    with pytest.raises(NotImplementedError):
        tasks[0].score(tasks[0].answer)


# --------------------------------------------------------------------------
# the specific semantics we rely on elsewhere in the project
# --------------------------------------------------------------------------


def test_norm_phrase_set_match_is_containment_not_equality() -> None:
    """The single most important property: extra text does NOT penalise.

    Our leakage detector depends on exactly this -- it is what makes
    'score the memory text as if it were the answer' a valid leak test.
    """
    gold = "Incident Mobile, Incident Portal, My Open Incidents"
    verbose = (
        "After reviewing the modules I can say the available ones are "
        "Incident Mobile, Incident Portal, and My Open Incidents, plus much "
        "unrelated commentary about other pages entirely."
    )
    assert norm_phrase_set_match(verbose, gold, separators=[",", ";"]) is True
    # order does not matter for the unordered variant
    reordered = "My Open Incidents then Incident Portal then Incident Mobile"
    assert norm_phrase_set_match(reordered, gold, separators=[",", ";"]) is True
    # but a missing phrase does
    partial = "Incident Mobile and Incident Portal only"
    assert norm_phrase_set_match(partial, gold, separators=[",", ";"]) is False


def test_ordered_variant_actually_enforces_order() -> None:
    gold = "Grow Business; Run Business; Transform Business"
    ok = "first Grow Business, then Run Business, finally Transform Business"
    bad = "first Transform Business, then Run Business, finally Grow Business"
    assert norm_phrase_set_match_ordered(ok, gold, separators=[";"]) is True
    assert norm_phrase_set_match_ordered(bad, gold, separators=[";"]) is False
    # and the UNordered variant accepts the very case the ordered one rejects,
    # which is what proves the two are different tests
    assert norm_phrase_set_match(bad, gold, separators=[";"]) is True


def test_separator_variant_is_not_interchangeable() -> None:
    """Why the adapter must dispatch on the FULL spec string, not the name.

    Two questions both use norm_phrase_set_match but with different
    separators. Treating them as one scorer changes the verdict.
    """
    gold = "Reports;Problems"
    pred = "the Reports page"
    # separators=';' -> two required phrases -> pred is missing one -> False
    assert norm_phrase_set_match(pred, gold, separators=[";"]) is False
    # separators=',' -> ';' is not a separator, but normalize_phrase deletes
    # ';' anyway, leaving the single phrase 'reports problems' -> still False
    assert norm_phrase_set_match(pred, gold, separators=[","]) is False
    # the substantive difference shows when both words are present unordered
    both = "Problems and then Reports"
    assert norm_phrase_set_match(both, gold, separators=[";"]) is True
    assert norm_phrase_set_match(both, gold, separators=[","]) is False


def test_normalize_phrase_deletes_comma_and_semicolon_unconditionally() -> None:
    """Documented because it drives the separator behaviour above."""
    assert normalize_phrase("a,b;c") == "a b c"
    assert normalize_phrase("Fulfillment-Automation_Level") == (
        "fulfillment automation level"
    )


def test_mc_choice_match_prefers_boxed_and_is_exact() -> None:
    assert mc_choice_match(r"the answer is \boxed{G}", "G") is True
    assert mc_choice_match(r"\boxed{option G.}", "G") is True
    assert mc_choice_match(r"\boxed{H}", "G") is False
    # no boxed -> whole prediction is the candidate, so prose fails
    assert mc_choice_match("I think it is G because ...", "G") is False


def test_mc_choice_set_match_is_order_insensitive_set_equality() -> None:
    assert mc_choice_set_match("A, B and F", "A,B,F") is True
    assert mc_choice_set_match("F B A", "A,B,F") is True
    assert mc_choice_set_match("A and B", "A,B,F") is False
    assert mc_choice_set_match("A B F C", "A,B,F") is False


def test_require_non_empty_blocks_empty_gold() -> None:
    assert norm_phrase_set_match("anything", "", require_non_empty=True) is False


@needs_data
def test_adapter_dispatches_every_spec_string_present_in_the_data() -> None:
    """No spec string in the shipped data may be undispatchable."""
    specs = {
        r["eval_function"]
        for r in lmev2.read_jsonl(DATA_ROOT / "questions.jsonl")
    }
    assert len(specs) == 8, f"expected 8 distinct specs, got {len(specs)}: {specs}"
    for spec in specs:
        if spec.split("|", 1)[0] in lmev2.LLM_EVAL_FUNCTIONS:
            continue
        # must not raise
        eval_from_spec(spec, "probe prediction", "probe")

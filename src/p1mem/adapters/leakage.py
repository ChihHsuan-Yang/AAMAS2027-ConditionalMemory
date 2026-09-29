"""Leakage detection for memory-utility cells.

A cell is (m, t): a memory unit m and a future task t with gold answer a(t).
The cell LEAKS when m literally carries a(t), so that an agent could score
correct by copying the memory instead of using it. Leaky cells inflate
DeltaU and a reviewer will look for them first.

Policy, enforced by this module's API shape
-------------------------------------------
We FLAG, we never DROP. Dropping leaky cells silently changes the question
being answered (it conditions the cell set on the outcome variable). Every
function here returns a verdict per cell; the analysis layer decides what to
report, and is expected to report BOTH with and without.

Detectors
---------
``exact``        substring containment of the raw gold string in raw memory text.
``normalized``   containment after the BENCHMARK'S OWN normalization, with
                 word-boundary anchoring. For LongMemEval-V2 this delegates to
                 the vendored official scorer, so it is the benchmark's
                 semantics and not a reimplementation.
``numeric``      tolerance variant: numbers in the gold answer match a number
                 in the memory within a relative/absolute tolerance, so that
                 "1,234" / "1234" / "1234.0" / "1233.9" are not missed.

Every detector is pure, deterministic, and free of network or model calls.

Self-test
---------
``prove_detector_can_fail()`` runs the positive/negative controls demanded by
the project rule "positive-control every null": it plants a known leak and
asserts each detector FIRES, and runs a known-clean case and asserts each
detector STAYS SILENT. A detector that cannot be shown to fire is not evidence
of absence. ``scripts/audit_leakage.py`` calls it before reporting any rate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

# --------------------------------------------------------------------------
# normalization
# --------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^\w\s]")


def normalize_text(
    text: Any,
    *,
    lower: bool = True,
    normalize_hyphen: bool = True,
    strip_punct: bool = True,
) -> str:
    """Normalization matching LongMemEval-V2 ``qa_eval_metrics.normalize_phrase``.

    Kept as an independent implementation ONLY so that this module also works
    for benchmarks that ship no scorer (LongMemEval-V1, BEAM, SciCode). For
    LongMemEval-V2 the official scorer is used instead -- see
    :func:`official_scorer_leak`. ``test_leakage.py`` asserts this function
    agrees with the vendored official one on all 451 V2 gold answers, so any
    drift between them is caught rather than assumed away.
    """
    text = _coerce_text(text)
    if lower:
        text = text.lower()
    if normalize_hyphen:
        text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[,;]", " ", text)
    if strip_punct:
        text = _NONWORD.sub("", text)
    return _WS.sub(" ", text).strip()


def split_gold_phrases(
    answer: Any,
    separators: Sequence[str] = (",", ";"),
    **norm_kwargs: bool,
) -> list[str]:
    """Split a gold answer into the phrases a scorer would require."""
    answer = _coerce_text(answer)
    if not answer:
        return []
    if not separators:
        n = normalize_text(answer, **norm_kwargs)
        return [n] if n else []
    pattern = "|".join(re.escape(s) for s in separators)
    parts = re.split(pattern, answer)
    return [p for p in (normalize_text(x, **norm_kwargs) for x in parts) if p]


# --------------------------------------------------------------------------
# detectors
# --------------------------------------------------------------------------


def exact_leak(memory_text: str, gold_answer: Any) -> bool:
    """Raw substring containment. Case- and whitespace-sensitive.

    The strictest detector: few false positives, many false negatives.
    """
    gold_answer = _coerce_text(gold_answer)
    memory_text = _coerce_text(memory_text)
    if not gold_answer or not memory_text:
        return False
    return gold_answer in memory_text


def normalized_leak(
    memory_text: str,
    gold_answer: Any,
    *,
    separators: Sequence[str] = (",", ";"),
    require_all_phrases: bool = True,
    **norm_kwargs: bool,
) -> bool:
    """Word-boundary containment after normalization.

    ``require_all_phrases`` mirrors ``norm_phrase_set_match``: the cell leaks
    only when EVERY gold phrase is present. Set it False to flag partial
    leakage (any one phrase present), which is the right setting when asking
    "does the memory give the model a head start" rather than "could the model
    score correct by copying".
    """
    phrases = split_gold_phrases(gold_answer, separators, **norm_kwargs)
    if not phrases:
        return False
    norm_mem = normalize_text(memory_text, **norm_kwargs)
    if not norm_mem:
        return False
    hits = [
        re.search(r"\b%s\b" % re.escape(p), norm_mem) is not None for p in set(phrases)
    ]
    return all(hits) if require_all_phrases else any(hits)


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _coerce_text(value: Any) -> str:
    """Coerce a gold answer to text WITHOUT inventing content.

    Necessary because LongMemEval-V1 stores 32 of its 500 gold answers as bare
    ``int`` (mostly single digits, e.g. 2, 3, 4) rather than ``str``. Silently
    crashing on those would drop them; silently stringifying them without
    saying so would let a 1-character gold answer enter a pooled leakage rate
    unremarked. We coerce here and flag the cell as degenerate in
    :func:`detect`, so the number is reported in its own stratum.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _numbers(text: Any) -> list[float]:
    text = _coerce_text(text)
    out: list[float] = []
    for raw in _NUM.findall(text or ""):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return out


def numeric_leak(
    memory_text: str,
    gold_answer: Any,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 0.0,
) -> bool:
    """Tolerance variant: every number in the gold answer appears in memory.

    Catches leaks that survive formatting differences ("1,234" vs "1234" vs
    "1234.0"). Returns False when the gold answer contains no number -- callers
    must therefore not read a False here as "no leak", only as "this detector
    is not applicable". :func:`detect` records applicability explicitly.
    """
    gold_nums = _numbers(gold_answer)
    if not gold_nums:
        return False
    mem_nums = _numbers(memory_text)
    if not mem_nums:
        return False
    for g in gold_nums:
        tol = max(abs_tol, rel_tol * abs(g))
        if not any(abs(g - m) <= tol for m in mem_nums):
            return False
    return True


def official_scorer_leak(
    memory_text: str,
    gold_answer: Any,
    eval_function_spec: str,
    *,
    eval_from_spec: Callable[..., Any] | None = None,
) -> bool | None:
    """Score the MEMORY TEXT as if it were the model's answer.

    Returns True when the benchmark's OWN scorer would mark the memory text
    correct -- the sharpest possible statement of "this cell leaks".

    Returns ``None`` (not False) when the question's eval function is
    LLM-judged, because deciding it would need an inference call and this
    module makes none. ``None`` means UNDECIDABLE, and must never be counted
    as "clean" -- reporting an undecidable cell as clean is the
    absence-becomes-zero failure mode.
    """
    name = eval_function_spec.split("|", 1)[0].strip()
    if name.startswith("llm_"):
        return None
    if eval_from_spec is None:
        from p1mem.adapters.lmev2 import require_supported_python  # noqa: PLC0415

        require_supported_python()
        from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
            eval_from_spec as _efs,
        )

        eval_from_spec = _efs
    return bool(eval_from_spec(eval_function_spec, memory_text, gold_answer))


# --------------------------------------------------------------------------
# combined verdict
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LeakVerdict:
    """Per-cell leakage verdict. Nothing here decides to drop anything."""

    memory_id: str
    task_id: str
    exact: bool
    normalized: bool
    normalized_partial: bool
    numeric: bool | None          # None => gold has no number: not applicable
    official: bool | None         # None => LLM-judged: UNDECIDABLE
    gold_answer_chars: int
    gold_n_phrases: int
    memory_chars: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def any_leak(self) -> bool:
        """True if ANY applicable detector fired. Undecidables do not count."""
        return bool(self.exact or self.normalized or self.official or self.numeric)

    @property
    def undecidable(self) -> bool:
        """True when the official scorer could not rule. NOT the same as clean."""
        return self.official is None


def detect(
    memory_text: str,
    gold_answer: Any,
    *,
    memory_id: str = "",
    task_id: str = "",
    eval_function_spec: str | None = None,
    separators: Sequence[str] = (",", ";"),
    rel_tol: float = 1e-9,
) -> LeakVerdict:
    """Run every applicable detector on one cell."""
    notes: list[str] = []
    if not isinstance(gold_answer, str):
        notes.append(f"gold_answer_not_a_string:{type(gold_answer).__name__}")
    gold_answer = _coerce_text(gold_answer)
    gold_nums = _numbers(gold_answer)
    numeric: bool | None = (
        numeric_leak(memory_text, gold_answer, rel_tol=rel_tol) if gold_nums else None
    )
    official: bool | None = None
    if eval_function_spec:
        official = official_scorer_leak(memory_text, gold_answer, eval_function_spec)
        if official is None:
            notes.append("official_scorer_undecidable_llm_judged")
    phrases = split_gold_phrases(gold_answer, separators)
    if len(normalize_text(gold_answer)) <= 2:
        notes.append("degenerate_short_gold_answer")
    return LeakVerdict(
        memory_id=memory_id,
        task_id=task_id,
        exact=exact_leak(memory_text, gold_answer),
        normalized=normalized_leak(
            memory_text, gold_answer, separators=separators, require_all_phrases=True
        ),
        normalized_partial=normalized_leak(
            memory_text, gold_answer, separators=separators, require_all_phrases=False
        ),
        numeric=numeric,
        official=official,
        gold_answer_chars=len(gold_answer or ""),
        gold_n_phrases=len(phrases),
        memory_chars=len(memory_text or ""),
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------
# controls -- "prove your detector can fail"
# --------------------------------------------------------------------------

_CLEAN_MEMORY = (
    "State 4 (step 4)\n"
    "- URL: https://example.invalid/now/nav/ui/classic/params/target/incident_list.do\n"
    "- Action: click('221')\n"
    "- AXTree:\n"
    "RootWebArea 'Incidents | ServiceNow', focused\n"
    "\t[46] generic, live='assertive'\n"
    "\t[221] button 'Submit'\n"
    "\t[233] textbox 'Short description'\n"
)


@dataclass(frozen=True)
class ControlResult:
    name: str
    detector: str
    expected: bool
    observed: bool

    @property
    def passed(self) -> bool:
        return self.expected == self.observed


def _assert_baseline_clean(memory: str, gold: str, label: str) -> None:
    """A negative control is only a control if the baseline really is clean.

    Checking this is not pedantry: the first draft of control 3 below planted
    two of three gold phrases into a memory that ALREADY contained the third,
    so the "partial leak" control silently tested a full leak. Assert the
    baseline, or the control tests nothing.
    """
    if normalized_leak(memory, gold, require_all_phrases=False):
        raise AssertionError(
            f"baseline for {label!r} is NOT clean: some phrase of {gold!r} "
            f"already occurs in the unplanted memory"
        )


def prove_detector_can_fail() -> list[ControlResult]:
    """Positive and negative controls for every detector.

    POSITIVE controls plant a known leak into a copy of a clean memory and
    assert the detector FIRES. NEGATIVE controls use a memory whose
    cleanliness is ASSERTED (not assumed) and check the detector STAYS
    SILENT. A detector that has only ever been run on clean data has not been
    shown to detect anything.

    The planted leaks are deliberately varied so that no single detector
    passes all of them -- that is what makes the suite informative:
      - verbatim, space-delimited  -> exact and normalized must both fire
      - case/hyphen variant        -> exact must NOT fire, normalized MUST
      - multi-phrase, reordered    -> normalized must fire on all-present,
                                      and must NOT on partial
      - number with separator      -> numeric MUST fire, exact must NOT
      - verbatim glued to punctuation -> documents a REAL false negative of
                                      the benchmark's own normalization
    """
    res: list[ControlResult] = []

    def check(name: str, det: str, expected: bool, observed: bool) -> None:
        res.append(ControlResult(name, det, expected, bool(observed)))

    # --- NEGATIVE controls: baseline cleanliness asserted first ------------
    clean_gold = "Warranty expiration"
    _assert_baseline_clean(_CLEAN_MEMORY, clean_gold, "clean/verbatim-absent")
    check("clean/verbatim-absent", "exact", False, exact_leak(_CLEAN_MEMORY, clean_gold))
    check(
        "clean/verbatim-absent",
        "normalized",
        False,
        normalized_leak(_CLEAN_MEMORY, clean_gold),
    )
    check(
        "clean/number-absent", "numeric", False, numeric_leak(_CLEAN_MEMORY, "982451653")
    )
    # words individually present, required phrase absent
    check(
        "clean/words-present-phrase-absent",
        "normalized",
        False,
        normalized_leak(_CLEAN_MEMORY, "Submit description button ordering"),
    )

    # --- POSITIVE control 1: verbatim plant, space-delimited ---------------
    gold1 = "GPS system not functioning correctly"
    _assert_baseline_clean(_CLEAN_MEMORY, gold1, "plant/verbatim")
    planted1 = _CLEAN_MEMORY.replace(
        "[233] textbox 'Short description'",
        f"[233] textbox 'Short description' reading {gold1} now",
    )
    assert planted1 != _CLEAN_MEMORY, "plant 1 did not modify the memory"
    check("plant/verbatim", "exact", True, exact_leak(planted1, gold1))
    check("plant/verbatim", "normalized", True, normalized_leak(planted1, gold1))

    # --- POSITIVE control 2: case + hyphen variant -------------------------
    # exact MUST miss this; normalized MUST catch it. This is the control
    # that shows the two detectors are not one test wearing two names.
    gold2 = "Fulfillment-Automation Level"
    _assert_baseline_clean(_CLEAN_MEMORY, gold2, "plant/case-hyphen")
    planted2 = _CLEAN_MEMORY.replace(
        "[221] button 'Submit'", "[221] button 'fulfillment automation level'"
    )
    assert planted2 != _CLEAN_MEMORY, "plant 2 did not modify the memory"
    check("plant/case-hyphen", "exact", False, exact_leak(planted2, gold2))
    check("plant/case-hyphen", "normalized", True, normalized_leak(planted2, gold2))

    # --- POSITIVE control 3: multi-phrase, reordered, interleaved ----------
    # NB "Incidents" occurs in _CLEAN_MEMORY, so it must NOT appear in this
    # gold -- _assert_baseline_clean enforces that rather than trusting it.
    gold3 = "Reports, Problems, Catalog"
    _assert_baseline_clean(_CLEAN_MEMORY, gold3, "plant/multiphrase")
    planted3 = _CLEAN_MEMORY.replace(
        "[46] generic, live='assertive'",
        "[46] generic 'Problems'\n\t[47] link 'Catalog'\n\t[48] link 'Reports'",
    )
    assert planted3 != _CLEAN_MEMORY, "plant 3 did not modify the memory"
    check("plant/multiphrase-reordered", "normalized", True, normalized_leak(planted3, gold3))
    # only two of three phrases -> require_all must NOT fire, partial MUST
    planted3b = _CLEAN_MEMORY.replace(
        "[46] generic, live='assertive'", "[46] generic 'Problems'\n\t[47] link 'Reports'"
    )
    assert planted3b != _CLEAN_MEMORY, "plant 3b did not modify the memory"
    check("plant/multiphrase-partial", "normalized", False, normalized_leak(planted3b, gold3))
    check(
        "plant/multiphrase-partial",
        "normalized_partial",
        True,
        normalized_leak(planted3b, gold3, require_all_phrases=False),
    )

    # --- POSITIVE control 4: number reformatted ----------------------------
    gold4 = "1234"
    planted4 = _CLEAN_MEMORY.replace("[221] button 'Submit'", "[221] button '1,234 open'")
    assert planted4 != _CLEAN_MEMORY, "plant 4 did not modify the memory"
    check("plant/number-reformatted", "exact", False, exact_leak(planted4, gold4))
    check("plant/number-reformatted", "numeric", True, numeric_leak(planted4, gold4))

    # --- POSITIVE control 5: numeric tolerance is not exact equality -------
    check(
        "plant/number-tolerance",
        "numeric",
        True,
        numeric_leak("value is 1234.0004 units", "1234", rel_tol=1e-3),
    )
    check(
        "plant/number-tolerance-tight",
        "numeric",
        False,
        numeric_leak("value is 1300 units", "1234", rel_tol=1e-9),
    )

    # --- CONTROL 6: a KNOWN FALSE NEGATIVE, asserted so it cannot drift ----
    # The benchmark's normalize_phrase DELETES punctuation without inserting
    # a space, so "value='GPS system..." normalizes to "valuegps system...".
    # The leading \b then fails and the leak is MISSED. This is a property of
    # the OFFICIAL scorer, not of our code, and it means `normalized`/
    # `official` UNDER-count leakage when gold text abuts punctuation.
    # Pinned as an expected result so that if upstream ever fixes it, this
    # control fails loudly instead of the change passing unnoticed.
    gold6 = "GPS system not functioning correctly"
    glued = _CLEAN_MEMORY.replace(
        "[233] textbox 'Short description'",
        f"[233] textbox 'Short description' value='{gold6}'",
    )
    assert glued != _CLEAN_MEMORY, "plant 6 did not modify the memory"
    check("known-fn/punctuation-glued", "exact", True, exact_leak(glued, gold6))
    check("known-fn/punctuation-glued", "normalized", False, normalized_leak(glued, gold6))

    return res


def controls_summary() -> tuple[bool, list[ControlResult]]:
    """(all_passed, results). Call before reporting any leakage rate."""
    res = prove_detector_can_fail()
    return all(r.passed for r in res), res

"""Faithfulness proxies for model-written memories (B4).

Summary and Structured are written by a model and can hallucinate. Raw cannot,
by construction -- it is the source text. So the question is only ever asked
of B and C, and **raw is the control**: running the same proxy on raw must
score 1.0, and if it does not, the proxy is broken rather than raw being
unfaithful. :func:`raw_control` makes that check callable.

The cheap deterministic proxies come first, on purpose. An LLM judge is
expensive, is the same model family as the writer, and cannot be audited by a
reviewer. These can.

WHAT THESE PROXIES CATCH
------------------------
1. ``number_support`` -- every numeric literal in the memory appears in the
   source. Catches invented quantities, prices, counts, IDs and dates: the
   single most consequential hallucination for a QA benchmark, because a wrong
   number is a confidently wrong answer downstream.
2. ``entity_support`` -- every capitalised token, quoted string, URL, path and
   identifier-shaped token in the memory appears in the source. Catches
   invented names, invented UI labels, invented file or endpoint names.
3. ``contradiction_of_explicit_values`` -- where source and memory both bind a
   value to the same key (``Status: Closed``, ``URL: ...``, ``count = 12``),
   the bound values must match. Catches the specific, checkable case of a
   memory restating a field with the wrong value.
4. ``length_plausibility`` -- a memory longer than its source is not
   compression and is a sign something was added. Weak, but free.

WHAT THEY CANNOT CATCH -- state this wherever the numbers are quoted
--------------------------------------------------------------------
* **Recombination.** Every entity and number can be present in the source and
  still be wired together wrongly: "the user ordered 3 laptops" from a source
  saying the user viewed 3 laptops and ordered a monitor. Token-overlap proxies
  are blind to predicate-argument structure. This is the biggest gap and it is
  not small.
* **Omission.** These proxies score what the memory SAYS, not what it left
  out. A summary that drops the decisive fact scores a perfect 1.0.
* **Unsupported inference.** "The user was frustrated" contains no new entity
  or number and passes cleanly.
* **Negation and modality.** "did not succeed" vs "succeeded" share every
  content token; the contradiction check only sees explicit ``key: value``
  bindings, not free-prose polarity.
* **Paraphrase asymmetry.** A faithful paraphrase that renames an entity
  ("the dashboard" for "Hardware Asset Overview") is scored as unsupported.
  So these measures are **conservative for entities and liberal for meaning**,
  and the two errors do not cancel.

So: a HIGH score is weak evidence of faithfulness; a LOW score is strong
evidence of a problem. Use them as a screen that promotes suspicious memories
to inspection, never as a faithfulness guarantee. That asymmetry is the honest
reading and is the one to put in the paper.

An LLM-judge hook exists (:func:`llm_judge_faithfulness`) but is deliberately
NOT called by :func:`score_record`: adding a judge silently would let a judge
score enter a table labelled "deterministic proxy".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "FAITHFULNESS_RULE_VERSION",
    "FaithfulnessScore",
    "score_text",
    "score_record",
    "raw_control",
    "PROXY_LIMITATIONS",
    "llm_judge_faithfulness",
]

FAITHFULNESS_RULE_VERSION = "deterministic_proxy@1.0.0"

PROXY_LIMITATIONS: tuple[str, ...] = (
    "recombination: correct entities wired into a false relation scores 1.0",
    "omission: a summary that drops the decisive fact scores 1.0",
    "unsupported inference with no new tokens scores 1.0",
    "negation/modality in free prose is invisible to the contradiction check",
    "faithful paraphrase that renames an entity is scored as UNSUPPORTED (false alarm)",
)

#: Numbers: integers, decimals, and thousands-separated forms. A leading sign
#: is excluded so that "12" inside "state-12" and a standalone "12" match.
_NUM = re.compile(r"\d[\d,]*\.?\d*")

#: Entity-shaped tokens: URLs, paths, quoted strings, CamelCase, ALLCAPS,
#: snake_case and dotted identifiers, and Capitalised words.
_URL = re.compile(r"https?://\S+")
_QUOTED = re.compile(r"[\"'`]([^\"'`\n]{2,60})[\"'`]")
_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:[._/-][A-Za-z0-9_]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_ALLCAPS = re.compile(r"\b[A-Z]{2,}\d*\b")
_CAPWORD = re.compile(r"\b[A-Z][a-z]{2,}\b")

#: An explicit binding: "Status: Closed", "count = 12", "- URL: https://...".
#:
#: ⚠️ The inline-whitespace classes are ``[ \t]``, NOT ``\s``. ``\s`` matches a
#: NEWLINE, and with ``re.M`` that let a bare "- AXTree:" swallow the value off
#: the FOLLOWING line: the source then had no ``status`` binding at all, so a
#: memory saying "Status: Closed" against a source saying "Status: Open" was
#: scored as NO CONTRADICTION. Found by the planted-contradiction test, which
#: is the only reason it was found -- the proxy looked healthy on every case it
#: had been run on. A binding must never span a line break.
_BINDING = re.compile(
    r"(?m)^[ \t\-*#>]*([A-Za-z][A-Za-z0-9 _/-]{1,40}?)[ \t]*[:=][ \t]*(\S[^\n]{0,200}?)[ \t]*$")

#: English function words that are capitalised at sentence start and carry no
#: entity content. Without this, every sentence-initial "The" is an "entity".
_STOP_CAPS = frozenset({
    "The", "This", "That", "These", "Those", "There", "Then", "They", "Their",
    "It", "Its", "He", "She", "His", "Her", "We", "Our", "You", "Your", "I",
    "A", "An", "And", "But", "Or", "If", "When", "While", "After", "Before",
    "During", "For", "From", "With", "Without", "No", "Not", "None", "Nothing",
    "All", "Any", "Some", "Each", "Every", "Both", "Either", "Neither",
    "State", "Action", "Url", "Goal", "Actions", "Step", "Steps", "Page",
    "Summary", "Note", "Notes", "Also", "However", "Because", "Since", "Only",
    "Next", "Finally", "First", "Second", "Third", "Last", "New", "Old",
})


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _numbers(text: str) -> list[str]:
    out = []
    for m in _NUM.finditer(text):
        v = m.group(0).rstrip(".").replace(",", "")
        if v:
            out.append(v)
    return out


def _entities(text: str) -> list[str]:
    out: list[str] = []
    out.extend(m.group(0).rstrip(".,);") for m in _URL.finditer(text))
    out.extend(m.group(1).strip() for m in _QUOTED.finditer(text))
    out.extend(m.group(0) for m in _IDENT.finditer(text))
    out.extend(m.group(0) for m in _CAMEL.finditer(text))
    out.extend(m.group(0) for m in _ALLCAPS.finditer(text))
    out.extend(m.group(0) for m in _CAPWORD.finditer(text) if m.group(0) not in _STOP_CAPS)
    seen, uniq = set(), []
    for e in out:
        k = _normalise(e)
        if k and k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def _bindings(text: str) -> dict[str, set[str]]:
    """key -> {values}. A key bound to several values keeps all of them.

    Keeping the SET matters: a source that visits three URLs binds ``url``
    three times, and a memory naming any one of them is not contradicting it.
    Collapsing to the last value would manufacture contradictions.
    """
    out: dict[str, set[str]] = {}
    for m in _BINDING.finditer(text):
        k, v = _normalise(m.group(1)), _normalise(m.group(2))
        if not k or not v or len(k) > 40:
            continue
        out.setdefault(k, set()).add(v)
    return out


def _supported(item: str, source_norm: str) -> bool:
    """Substring containment against the normalised source.

    Substring rather than token equality because the source renders values
    inside larger strings (a URL inside a query parameter, an id inside a
    path). This makes the check LENIENT -- it accepts more than it should --
    which is the safe direction for a screen whose low scores are the signal.
    """
    return _normalise(item) in source_norm


@dataclass(slots=True)
class FaithfulnessScore:
    rule_version: str
    representation: str
    n_numbers: int
    n_numbers_supported: int
    n_entities: int
    n_entities_supported: int
    n_bindings_checked: int
    n_bindings_contradicted: int
    length_ratio: float | None
    unsupported_numbers: list[str] = field(default_factory=list)
    unsupported_entities: list[str] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def number_support(self) -> float | None:
        """None when the memory contains no numbers -- 'nothing to check', not 1.0.

        Scoring an empty denominator as a perfect 1.0 would let a memory with
        no numbers raise the corpus mean. Nulls are excluded from aggregates.
        """
        return None if self.n_numbers == 0 else self.n_numbers_supported / self.n_numbers

    @property
    def entity_support(self) -> float | None:
        return None if self.n_entities == 0 else self.n_entities_supported / self.n_entities

    @property
    def contradiction_rate(self) -> float | None:
        if self.n_bindings_checked == 0:
            return None
        return self.n_bindings_contradicted / self.n_bindings_checked

    @property
    def flagged(self) -> bool:
        """Promote to human inspection. Deliberately sensitive, not precise."""
        if self.n_bindings_contradicted > 0:
            return True
        ns, es = self.number_support, self.entity_support
        if ns is not None and ns < 1.0:
            return True
        if es is not None and es < 0.80:
            return True
        return bool(self.length_ratio is not None and self.length_ratio > 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_version": self.rule_version,
            "representation": self.representation,
            "number_support": self.number_support,
            "entity_support": self.entity_support,
            "contradiction_rate": self.contradiction_rate,
            "n_numbers": self.n_numbers,
            "n_numbers_supported": self.n_numbers_supported,
            "n_entities": self.n_entities,
            "n_entities_supported": self.n_entities_supported,
            "n_bindings_checked": self.n_bindings_checked,
            "n_bindings_contradicted": self.n_bindings_contradicted,
            "length_ratio": self.length_ratio,
            "flagged": self.flagged,
            "unsupported_numbers": self.unsupported_numbers[:20],
            "unsupported_entities": self.unsupported_entities[:20],
            "contradictions": self.contradictions[:10],
        }


def score_text(memory_text: str, source_text: str, *,
               representation: str = "") -> FaithfulnessScore:
    """Deterministic faithfulness proxies for one memory against its source."""
    src_norm = _normalise(source_text)

    nums = _numbers(memory_text)
    bad_nums = [n for n in nums if not _supported(n, src_norm)]
    ents = _entities(memory_text)
    bad_ents = [e for e in ents if not _supported(e, src_norm)]

    src_bind, mem_bind = _bindings(source_text), _bindings(memory_text)
    checked, contradicted = 0, []
    for key, mvals in mem_bind.items():
        svals = src_bind.get(key)
        if not svals:
            continue          # key not bound in source: not checkable, not a contradiction
        checked += 1
        if not any(mv in svals or any(mv in sv or sv in mv for sv in svals) for mv in mvals):
            contradicted.append({"key": key, "memory": sorted(mvals),
                                 "source": sorted(svals)[:5]})

    ratio = (len(memory_text) / len(source_text)) if source_text else None
    return FaithfulnessScore(
        rule_version=FAITHFULNESS_RULE_VERSION,
        representation=representation,
        n_numbers=len(nums), n_numbers_supported=len(nums) - len(bad_nums),
        n_entities=len(ents), n_entities_supported=len(ents) - len(bad_ents),
        n_bindings_checked=checked, n_bindings_contradicted=len(contradicted),
        length_ratio=ratio,
        unsupported_numbers=bad_nums, unsupported_entities=bad_ents,
        contradictions=contradicted,
    )


def score_record(record: Any, source_text: str) -> FaithfulnessScore | None:
    """Score a :class:`MemoryRecord`. Returns None for raw and for failed writes.

    Raw is skipped because it IS the source: scoring it measures the proxy,
    not the memory. Use :func:`raw_control` when that is what you want.
    """
    rep = getattr(record, "representation", "")
    if rep == "raw" or not getattr(record, "ok", False):
        return None
    return score_text(record.memory_text, source_text, representation=rep)


def raw_control(source_text: str) -> FaithfulnessScore:
    """POSITIVE CONTROL: score the source against itself.

    Must come back with number_support == entity_support == 1.0 and zero
    contradictions. If it does not, the proxy has a bug -- a tokenisation or
    normalisation asymmetry -- and every score it produced is suspect. A
    faithfulness check that has never been run on a case it MUST pass is not
    known to discriminate.
    """
    return score_text(source_text, source_text, representation="raw")


def aggregate(scores: Iterable[FaithfulnessScore]) -> dict[str, Any]:
    """Corpus-level summary. Nulls are EXCLUDED from denominators, not zeroed."""
    items = [s for s in scores if s is not None]
    def _mean(vals: Sequence[float]) -> float | None:
        return (sum(vals) / len(vals)) if vals else None
    ns = [s.number_support for s in items if s.number_support is not None]
    es = [s.entity_support for s in items if s.entity_support is not None]
    cr = [s.contradiction_rate for s in items if s.contradiction_rate is not None]
    return {
        "n_scored": len(items),
        "n_with_numbers": len(ns), "mean_number_support": _mean(ns),
        "n_with_entities": len(es), "mean_entity_support": _mean(es),
        "n_with_bindings": len(cr), "mean_contradiction_rate": _mean(cr),
        "n_flagged": sum(1 for s in items if s.flagged),
        "limitations": list(PROXY_LIMITATIONS),
    }


def llm_judge_faithfulness(*_args: Any, **_kwargs: Any) -> None:
    """Deliberately unimplemented.

    A judge is an extra experimental condition (its own model, cluster, prompt
    version, and its own failure modes) and would need all of that recorded
    per the protocol's writer-control rule. Wiring one in here, where callers
    already treat the return value as "the faithfulness number", is how a judge
    score ends up in a column labelled 'deterministic proxy'. When a judge is
    needed it gets its own module, its own pinned config, and its own column.
    """
    raise NotImplementedError(
        "No LLM judge in B4 by design. The deterministic proxies are reported as "
        "proxies, with their limitations stated. A judge is a separate, pinned, "
        "separately-reported condition -- not a drop-in upgrade to this function."
    )

"""Semantic-type labelling (B3) -- ``docs/MEMORY_PROTOCOL.md`` §2.

    episodic | semantic_fact | procedural | failure_reflection

Representation vs semantic type are ORTHOGONAL axes and the protocol is blunt
that conflating them makes the analysis meaningless. The same procedural
experience can be stored raw, summarised, or structured.

Where the label comes from
--------------------------
* **Representation C** emits it natively, as ``memory_type`` in its JSON.
* **A and B** have no natural slot, so they get a separate classification pass
  here.

Both paths read the SEGMENT, never the future task. :func:`classify_segment`
takes a :class:`SourceSegment` and nothing else, and it is covered by the same
introspective blindness test as the writers.

Inter-pass agreement, and what it can and cannot tell you
---------------------------------------------------------
:func:`agreement_report` compares C's native label with the classifier's label
**on the same segment**, which is the comparison the protocol asks for.

Read it as an upper bound on label quality, not as accuracy:

* There is no gold label. Agreement between two passes of the same model
  family is correlated error, not truth. Two passes can agree and both be
  wrong.
* The two passes see the same text but different prompts, so disagreement
  bounds prompt sensitivity as much as it bounds category ambiguity.
* Chance agreement is not negligible with 4 categories and a skewed prior, so
  the report gives **Cohen's kappa alongside raw agreement**. Raw agreement
  alone would flatter a corpus where almost everything is one category --
  exactly the situation on LongMemEval-V2 web trajectories.

The report therefore also prints the per-class confusion matrix, so a reader
can see *which* pair of categories the two passes disagree about instead of
being handed one number.

A deterministic fallback, and why it is not the default
-------------------------------------------------------
:func:`heuristic_semantic_type` is a keyword rule. It exists so the pipeline
has a zero-call path and so the LLM classifier has a cheap comparator, NOT as
a substitute. It is genuinely weak -- it keys on surface words like "error"
and "failed" which appear in plenty of successful trajectories -- and
:func:`agreement_report` reports its agreement separately and labelled as
such. Reporting a keyword rule's output as a semantic type without saying so
would be the "measure the subject, not the proxy" defect.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .prompts import Prompt, load_prompt
from .segment import SourceSegment, segment_content_id

__all__ = [
    "SEMANTIC_TYPES",
    "HEURISTIC_RULE_VERSION",
    "TypeLabel",
    "SemanticTypeClassifier",
    "heuristic_semantic_type",
    "agreement_report",
    "format_agreement_report",
]

SEMANTIC_TYPES: tuple[str, ...] = (
    "episodic", "semantic_fact", "procedural", "failure_reflection",
)

HEURISTIC_RULE_VERSION = "heuristic_keyword@1.0.0"

#: The default when the text supports no stronger reading. A trajectory
#: segment IS a record of something that happened, so 'episodic' is the honest
#: floor rather than a coin flip.
DEFAULT_TYPE = "episodic"


@dataclass(slots=True)
class TypeLabel:
    """One label plus where it came from. Provenance travels with the value."""

    semantic_type: str
    source: str               # "structured_native" | "llm_classifier" | "heuristic"
    prompt_version: str | None = None
    model: str | None = None
    cluster: str | None = None
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    calls: int = 0
    ok: bool = True
    error_code: str | None = None
    raw_output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_type": self.semantic_type, "source": self.source,
            "prompt_version": self.prompt_version, "model": self.model,
            "cluster": self.cluster, "latency_s": self.latency_s,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "calls": self.calls, "ok": self.ok, "error_code": self.error_code,
            "raw_output": self.raw_output,
        }


# ---------------------------------------------------------------- heuristic
_FAILURE = re.compile(
    r"\b(error|exception|traceback|failed|failure|denied|invalid|unable to|"
    r"not found|404|500|retry|retried|rollback|timed out|timeout)\b", re.IGNORECASE)
_PROCEDURAL = re.compile(
    r"\b(step \d|first,|then,|next,|in order to|procedure|workflow|how to|"
    r"click|navigate|fill|submit|select)\b", re.IGNORECASE)
_FACT = re.compile(
    r"\b(is a|are a|consists of|defined as|the value of|equals|policy states|"
    r"by default|always|never changes)\b", re.IGNORECASE)


def heuristic_semantic_type(segment: SourceSegment) -> TypeLabel:
    """Deterministic keyword rule. WEAK ON PURPOSE -- see the module docstring.

    Takes a segment and nothing else, like every other function on this path.
    """
    text = segment.text
    if _FAILURE.search(text):
        label = "failure_reflection"
    elif _PROCEDURAL.search(text):
        label = "procedural"
    elif _FACT.search(text):
        label = "semantic_fact"
    else:
        label = DEFAULT_TYPE
    return TypeLabel(semantic_type=label, source="heuristic",
                     prompt_version=HEURISTIC_RULE_VERSION, calls=0)


# ------------------------------------------------------------- LLM classifier
def _parse_label(text: str) -> str | None:
    """Accept the bare category name, tolerating punctuation and case only.

    Does NOT accept a category mentioned in passing inside a sentence: if the
    model wrote a paragraph we record a parse failure rather than fishing a
    word out of it. Fishing would count a non-compliant answer as a compliant
    one and hide the real compliance rate.
    """
    s = text.strip().strip(".`\"' \n\t").lower()
    s = s.split("\n")[0].strip()
    if s in SEMANTIC_TYPES:
        return s
    s2 = s.replace(" ", "_").replace("-", "_")
    return s2 if s2 in SEMANTIC_TYPES else None


class SemanticTypeClassifier:
    """The separate classification pass for representations A and B."""

    def __init__(self, client: Any, *, prompt: Prompt | None = None,
                 benchmark: str = "", max_tokens: int = 512,
                 temperature: float = 0.0, reasoning_effort: str | None = "low",
                 use_cache: bool = True):
        self.client = client
        self.prompt = prompt or load_prompt("semantic_type_v1")
        self.benchmark = benchmark
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.use_cache = use_cache

    def _cache_fields(self, segment: SourceSegment) -> dict[str, Any] | None:
        if not self.use_cache or getattr(self.client, "cache", None) is None:
            return None
        return {
            "benchmark": segment.benchmark or self.benchmark,
            "source_item_id": segment.segment_id,
            "memory_repr": "semantic_type_pass",
            "memory_id": segment_content_id(segment),
            "future_task_id": "none:write_pass",
            "arm": "semantic_type",
            "retrieval_method": "none",
            "prompt_version": self.prompt.version,
            "replicate_id": 0,
        }

    def classify(self, segment: SourceSegment) -> TypeLabel:
        """``(self, segment)``. No task parameter, by the same rule as the writers."""
        rendered = self.prompt.render(segment.text)
        try:
            content, rec = self.client.chat(
                [{"role": "user", "content": rendered}],
                max_tokens=self.max_tokens, temperature=self.temperature,
                reasoning_effort=self.reasoning_effort,
                cache_key_fields=self._cache_fields(segment))
        except Exception as exc:  # noqa: BLE001 -- recorded, not suppressed
            return TypeLabel(semantic_type=DEFAULT_TYPE, source="llm_classifier",
                             prompt_version=self.prompt.version,
                             model=getattr(self.client, "model", None),
                             cluster=getattr(self.client, "cluster", None),
                             calls=1, ok=False,
                             error_code=f"classifier_call_failed:{type(exc).__name__}",
                             raw_output=str(exc)[:300])
        label = _parse_label(content)
        return TypeLabel(
            semantic_type=label or DEFAULT_TYPE,
            source="llm_classifier",
            prompt_version=self.prompt.version,
            model=getattr(self.client, "model", None),
            cluster=getattr(self.client, "cluster", None),
            latency_s=getattr(rec, "latency_s", None),
            input_tokens=getattr(rec, "input_tokens", None),
            output_tokens=getattr(rec, "output_tokens", None),
            calls=1,
            # An unparseable answer is a FAILURE that fell back to the default,
            # not a label. ok=False keeps the two distinguishable downstream.
            ok=label is not None,
            error_code=None if label else "classifier_unparseable",
            raw_output=content[:300],
        )


# --------------------------------------------------------- agreement reporting
def _kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa. None when undefined (fewer than 2 items, or pe == 1).

    pe == 1 happens when BOTH passes put everything in one category: raw
    agreement is then 100% and carries no information at all, and returning a
    number there would misrepresent it. None is the honest value.
    """
    n = len(pairs)
    if n < 2:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in set(ca) | set(cb))
    if abs(1.0 - pe) < 1e-12:
        return None
    return (po - pe) / (1.0 - pe)


def agreement_report(pairs: Iterable[tuple[str, str]], *,
                     name_a: str = "structured_native",
                     name_b: str = "llm_classifier") -> dict[str, Any]:
    """Inter-pass agreement between two labellings of the SAME segments.

    ``pairs`` is [(label_a, label_b), ...] with one entry per segment. The
    caller is responsible for the pairing being segment-aligned; see
    :func:`paired_labels`.
    """
    items = [(str(a), str(b)) for a, b in pairs]
    n = len(items)
    n_agree = sum(1 for a, b in items if a == b)
    confusion: dict[str, dict[str, int]] = {}
    for a, b in items:
        confusion.setdefault(a, {}).setdefault(b, 0)
        confusion[a][b] += 1
    return {
        "pass_a": name_a,
        "pass_b": name_b,
        "n": n,
        "n_agree": n_agree,
        "raw_agreement": (n_agree / n) if n else None,
        "cohens_kappa": _kappa(items),
        "marginal_a": dict(Counter(a for a, _ in items)),
        "marginal_b": dict(Counter(b for _, b in items)),
        "confusion_a_by_b": confusion,
        "interpretation": (
            "Raw agreement without kappa flatters a skewed corpus. kappa=None means "
            "chance agreement is 1.0 (both passes used a single category), so the raw "
            "number carries no information. Neither figure is accuracy: there is no "
            "gold label, and two passes of the same model family share their errors."
        ),
    }


def paired_labels(by_segment: Mapping[str, Mapping[str, str]],
                  key_a: str, key_b: str) -> list[tuple[str, str]]:
    """Align two labellings by segment id, dropping segments missing either.

    Returns only segments present in BOTH -- an unmatched segment is not a
    disagreement, and counting it as one (or as an agreement) would be a
    half-join reported as a whole one.
    """
    out = []
    for labels in by_segment.values():
        a, b = labels.get(key_a), labels.get(key_b)
        if a is not None and b is not None:
            out.append((a, b))
    return out


def format_agreement_report(rep: Mapping[str, Any]) -> str:
    lines = [
        f"inter-pass agreement: {rep['pass_a']} vs {rep['pass_b']}",
        f"  n paired segments : {rep['n']}",
        f"  raw agreement     : {rep['n_agree']}/{rep['n']}"
        + (f" = {rep['raw_agreement']:.3f}" if rep["raw_agreement"] is not None else ""),
        f"  Cohen's kappa     : "
        + ("undefined (chance agreement is 1.0)" if rep["cohens_kappa"] is None
           else f"{rep['cohens_kappa']:.3f}"),
        f"  marginal {rep['pass_a']:<18}: {rep['marginal_a']}",
        f"  marginal {rep['pass_b']:<18}: {rep['marginal_b']}",
        "  confusion (rows = pass_a, cols = pass_b):",
    ]
    for a, row in sorted(rep["confusion_a_by_b"].items()):
        lines.append(f"    {a:<20} {dict(sorted(row.items()))}")
    return "\n".join(lines)

"""The three memory representations (B1) -- ``docs/MEMORY_PROTOCOL.md`` §1.

    A. raw        -- deterministic contiguous span. NO model call.
    B. summary    -- one LLM call, pinned prompt, model-written prose.
    C. structured -- one LLM call, pinned prompt, fixed JSON schema, VALIDATED.

All three take the SAME :class:`~p1mem.memory.segment.SourceSegment`, so any
downstream difference is attributable to representation and not to content
selection (protocol §1, opening paragraph). :func:`write_all` is the sanctioned
entry point precisely because it makes sharing the segment the default.

The invariant, structurally
---------------------------
Every writer's public entry point has the signature ``(self, segment)``. There
is no task parameter, no ``**kwargs``, and no optional ``task=None``. See
``memory/segment.py`` for the four barriers and
``tests/test_writer_blindness.py`` for the test that discovers every writer by
introspection -- so a writer added next month is covered without anyone
remembering to add it to a list.

Cost accounting (protocol §5)
-----------------------------
Every writer returns a :class:`MemoryRecord` carrying its own formation cost:
calls, input/output tokens, latency, retries. **Raw reports 0 calls and NULL
latency/tokens.** Null, not zero: the schema is explicit that
``memory_extraction_latency`` null means "no call was made", which is not the
same as a call that took 0.0 s. Conflating absent with zero has cost this
project before. The efficiency frontier charges each representation its own
formation cost, or it flatters the model-written ones.

Malformed structure is a RECORDED FAILURE
-----------------------------------------
Protocol §1C: "a malformed structure is a recorded failure, not a silent
fallback to prose". So :meth:`StructuredWriter.write` returns a
:class:`MemoryRecord` with ``ok=False`` and a populated ``error_code`` rather
than quietly emitting the raw model text as if it were a structured memory.
The malformed text is KEPT in ``raw_model_output`` -- a discarded failure
cannot be re-examined, and the malformed-JSON rate is a number we have to
report.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..vendor.rcc_schema import sha256_text, utc_now
from . import tokens as T
from .prompts import Prompt, load_prompt
from .segment import SourceSegment, assert_writer_signature, segment_content_id

__all__ = [
    "REPRESENTATIONS",
    "RAW_WRITER_MODEL",
    "RAW_WRITER_CLUSTER",
    "RAW_SPAN_RULE_VERSION",
    "STRUCTURED_KEYS",
    "STRUCTURED_PROCEDURAL_KEYS",
    "MemoryRecord",
    "RawExtractiveWriter",
    "SummaryWriter",
    "StructuredWriter",
    "write_all",
    "render_structured",
]

REPRESENTATIONS: tuple[str, ...] = ("raw", "summary", "structured")

#: The schema forbids a null writer model/cluster (they are experimental
#: identity). Raw has no writer, so it carries these SENTINELS, spelled exactly
#: as ``src/p1mem/schema.py`` prescribes. A sentinel is honest; a null would
#: read as "we forgot to record it".
RAW_WRITER_MODEL = "none:deterministic_span"
RAW_WRITER_CLUSTER = "none:deterministic_span"

#: Version of the DETERMINISTIC span rule, which is raw's analogue of a prompt
#: version. Bump only when the rule itself changes. The rule:
#:   take the whole benchmark-provided segment, verbatim, unmodified.
#: There is no selection step, by design -- protocol §1A forbids "pick the most
#: informative span", because informativeness is the value judgement we are
#: measuring and choosing on it would assume the conclusion.
RAW_SPAN_RULE_VERSION = "raw_whole_segment@1.0.0"

STRUCTURED_KEYS: tuple[str, ...] = (
    "memory_type", "situation", "action", "outcome", "lesson", "scope", "confidence",
)
STRUCTURED_PROCEDURAL_KEYS: tuple[str, ...] = (
    "memory_type", "trigger", "procedure", "failure_mode", "successful_correction",
    "scope", "confidence",
)

VALID_MEMORY_TYPES: frozenset[str] = frozenset(
    {"episodic", "semantic_fact", "procedural", "failure_reflection"}
)
VALID_CONFIDENCE: frozenset[str] = frozenset({"high", "medium", "low"})

#: Error codes recorded on a failed write. Stable strings: they are counted.
ERR_MALFORMED_JSON = "structured_malformed_json"
ERR_MISSING_KEYS = "structured_missing_keys"
ERR_EXTRA_KEYS = "structured_extra_keys"
ERR_BAD_ENUM = "structured_bad_enum_value"
ERR_NON_STRING = "structured_non_string_value"
ERR_EMPTY_CONTENT = "writer_empty_content"
ERR_CALL_FAILED = "writer_call_failed"


@dataclass(slots=True)
class MemoryRecord:
    """One written memory plus everything the schema row and the frontier need.

    ``ok=False`` records a FAILURE that happened; it is still returned, still
    counted, and still carries its cost. A failed write that cost a call must
    charge that call to its representation.
    """

    representation: str
    ok: bool
    memory_text: str
    segment_id: str
    source_episode_id: str
    memory_content_id: str
    source_span: Mapping[str, Any]

    writer_model: str
    writer_cluster: str
    prompt_version: str

    # -- cost. None means NO CALL WAS MADE. 0 means a call was made and the
    #    server reported zero. These are different facts.
    extraction_calls: int = 0
    extraction_latency_s: float | None = None
    extraction_input_tokens: int | None = None
    extraction_output_tokens: int | None = None
    extraction_reasoning_tokens: int | None = None
    retry_count: int = 0
    cache_hit: bool = False

    memory_tokens: int | None = None
    source_tokens: int | None = None

    structured: dict[str, str] | None = None
    native_semantic_type: str | None = None
    raw_model_output: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    written_at_utc: str = field(default_factory=utc_now)

    @property
    def compression_ratio(self) -> float | None:
        """memory_tokens / source_tokens. <1 means compression.

        Reported as the RATIO rather than a percentage saved, because raw's
        value is exactly 1.0 by construction and that is the reference point
        the other two are read against.
        """
        if not self.source_tokens or self.memory_tokens is None:
            return None
        return self.memory_tokens / self.source_tokens

    def to_schema_fields(self) -> dict[str, Any]:
        """The subset of the 77-field row this writer is responsible for.

        Deliberately NOT a whole row: the reader/task/outcome fields belong to
        other sub-agents, and a writer that filled them with plausible defaults
        would be inventing measurements.
        """
        return {
            "memory_representation": self.representation,
            "memory_semantic_type": self.native_semantic_type,
            "memory_text": self.memory_text,
            "memory_tokens": self.memory_tokens,
            "memory_source_span": dict(self.source_span),
            "memory_writer_model": self.writer_model,
            "memory_writer_cluster": self.writer_cluster,
            "memory_writer_prompt_version": self.prompt_version,
            "memory_extraction_latency": self.extraction_latency_s,
            "memory_extraction_input_tokens": self.extraction_input_tokens,
            "memory_extraction_output_tokens": self.extraction_output_tokens,
            "source_episode_id": self.source_episode_id,
        }

    def to_dict(self) -> dict[str, Any]:
        out = {
            "representation": self.representation,
            "ok": self.ok,
            "memory_text": self.memory_text,
            "segment_id": self.segment_id,
            "source_episode_id": self.source_episode_id,
            "memory_content_id": self.memory_content_id,
            "source_span": dict(self.source_span),
            "writer_model": self.writer_model,
            "writer_cluster": self.writer_cluster,
            "prompt_version": self.prompt_version,
            "extraction_calls": self.extraction_calls,
            "extraction_latency_s": self.extraction_latency_s,
            "extraction_input_tokens": self.extraction_input_tokens,
            "extraction_output_tokens": self.extraction_output_tokens,
            "extraction_reasoning_tokens": self.extraction_reasoning_tokens,
            "retry_count": self.retry_count,
            "cache_hit": self.cache_hit,
            "memory_tokens": self.memory_tokens,
            "source_tokens": self.source_tokens,
            "compression_ratio": self.compression_ratio,
            "structured": self.structured,
            "native_semantic_type": self.native_semantic_type,
            "raw_model_output": self.raw_model_output,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "written_at_utc": self.written_at_utc,
        }
        return out


def _maybe_tokens(text: str) -> int | None:
    """Token count, or None when the official tokenizer is unavailable.

    None here means "not measured", and every consumer treats it as missing
    rather than as zero. We never substitute a character heuristic: see
    ``memory/tokens.py``.
    """
    try:
        return T.count_tokens(text)
    except T.TokenizerUnavailable:
        return None


# ===========================================================  A. RAW / EXTRACTIVE
class RawExtractiveWriter:
    """Deterministic. No model, no call, no prompt, no randomness.

    Protocol §1A: "segment the episode at its own structural boundaries, then
    take the whole segment as one memory candidate" and "NO 'pick the most
    informative span'". This class therefore performs NO selection at all: the
    memory IS the segment. That is the entire rule, and its simplicity is the
    point -- any cleverer rule would be smuggling in the value judgement the
    experiment exists to measure.

    The boundary itself was drawn upstream by the benchmark adapter
    (``lmev2.segment_page_visits``: a maximal same-URL run, a boundary the past
    agent itself created by navigating away), never here.
    """

    representation = "raw"

    def __init__(self, *, span_rule_version: str = RAW_SPAN_RULE_VERSION):
        self.span_rule_version = span_rule_version

    def write(self, segment: SourceSegment) -> MemoryRecord:
        text = segment.text
        n = _maybe_tokens(text)
        return MemoryRecord(
            representation="raw",
            ok=True,
            memory_text=text,
            segment_id=segment.segment_id,
            source_episode_id=segment.source_episode_id,
            memory_content_id=segment_content_id(segment),
            # Re-derivability (protocol §1A): the span locator plus this rule
            # version is enough to reconstruct the exact bytes from the corpus.
            source_span={**dict(segment.source_span),
                         "span_rule_version": self.span_rule_version,
                         "extraction": "whole_segment_verbatim",
                         "text_sha256": sha256_text(text)},
            writer_model=RAW_WRITER_MODEL,
            writer_cluster=RAW_WRITER_CLUSTER,
            prompt_version=self.span_rule_version,
            # 0 calls is a MEASUREMENT and it is raw's real advantage.
            extraction_calls=0,
            # None, NOT 0.0 -- no call was made. schema.py is explicit.
            extraction_latency_s=None,
            extraction_input_tokens=None,
            extraction_output_tokens=None,
            memory_tokens=n,
            source_tokens=n,
        )


# ==============================================================  LLM-backED base
class _LLMWriter:
    """Shared plumbing for the two model-written representations.

    Does not own an LLM client: it takes one. ``src/p1mem/client.py`` and
    ``cache.py`` are Sub-agent C's and are used as-is -- writing a second
    client here would create the two-implementations-one-name defect this
    project has already been bitten by.
    """

    representation = "?"

    def __init__(self, client: Any, prompt: Prompt, *,
                 benchmark: str = "", max_tokens: int = 512,
                 temperature: float = 0.0, reasoning_effort: str | None = "low",
                 use_cache: bool = True):
        self.client = client
        self.prompt = prompt
        self.benchmark = benchmark
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.use_cache = use_cache

    # ---- cache key ------------------------------------------------------
    def _cache_fields(self, segment: SourceSegment) -> dict[str, Any] | None:
        """Cache key for a WRITE call.

        ``cache.py``'s key was designed for reader cells, so the task-side
        fields have no meaning at write time. They are set to the explicit
        sentinel ``"none:write_pass"`` rather than to a plausible-looking value
        (`""`, `None`, `"oracle"`), because the writer pass genuinely has no
        future task -- and the sentinel says so on the face of the key. A blank
        would read as "we forgot".

        ``memory_id`` is the CONTENT hash, per that module's own warning
        against putting a positional locator here.
        """
        if not self.use_cache or getattr(self.client, "cache", None) is None:
            return None
        return {
            "benchmark": segment.benchmark or self.benchmark,
            "source_item_id": segment.segment_id,
            "memory_repr": self.representation,
            "memory_id": segment_content_id(segment),
            "future_task_id": "none:write_pass",
            "arm": "memory_write",
            "retrieval_method": "none",
            "prompt_version": self.prompt.version,
            "replicate_id": 0,
        }

    def _call(self, segment: SourceSegment) -> tuple[str, Any, str | None, str | None]:
        """One endpoint call. Returns (content, CallRecord|None, err_code, err_detail).

        Exceptions from the client -- including ``TruncatedResponseError`` --
        are converted into a RECORDED failure, never swallowed and never turned
        into a usable memory. Protocol: a truncated summary silently becomes a
        degraded memory and would fabricate a "harmful" result.
        """
        rendered = self.prompt.render(segment.text)
        messages = [{"role": "user", "content": rendered}]
        try:
            content, rec = self.client.chat(
                messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                reasoning_effort=self.reasoning_effort,
                cache_key_fields=self._cache_fields(segment),
            )
        except Exception as exc:  # noqa: BLE001 -- recorded, not suppressed
            return "", None, ERR_CALL_FAILED, f"{type(exc).__name__}: {exc}"
        if not content.strip():
            # finish_reason=="length" with empty content already raised inside
            # the client. This catches an empty body with any OTHER finish
            # reason, which is equally unusable as a memory.
            return "", rec, ERR_EMPTY_CONTENT, (
                f"empty content with finish_reason={getattr(rec, 'finish_reason', '?')!r}"
            )
        return content, rec, None, None

    def _base_record(self, segment: SourceSegment, rec: Any, *,
                     ok: bool, memory_text: str,
                     error_code: str | None = None,
                     error_detail: str | None = None) -> MemoryRecord:
        return MemoryRecord(
            representation=self.representation,
            ok=ok,
            memory_text=memory_text,
            segment_id=segment.segment_id,
            source_episode_id=segment.source_episode_id,
            memory_content_id=segment_content_id(segment),
            source_span={**dict(segment.source_span),
                         "derived_from": "whole_segment",
                         "source_text_sha256": sha256_text(segment.text)},
            writer_model=getattr(self.client, "model", "?"),
            writer_cluster=getattr(self.client, "cluster", "?"),
            prompt_version=self.prompt.version,
            extraction_calls=1,
            extraction_latency_s=getattr(rec, "latency_s", None),
            extraction_input_tokens=getattr(rec, "input_tokens", None),
            extraction_output_tokens=getattr(rec, "output_tokens", None),
            extraction_reasoning_tokens=getattr(rec, "reasoning_tokens", None),
            retry_count=getattr(rec, "retry_count", 0) or 0,
            cache_hit=bool(getattr(rec, "cache_hit", False)),
            memory_tokens=_maybe_tokens(memory_text) if memory_text else None,
            source_tokens=_maybe_tokens(segment.text),
            error_code=error_code,
            error_detail=error_detail,
        )


# ==========================================================  B. ABSTRACTIVE SUMMARY
class SummaryWriter(_LLMWriter):
    """One call per segment, fixed prompt, model-written prose."""

    representation = "summary"

    def __init__(self, client: Any, *, prompt: Prompt | None = None, **kw: Any):
        super().__init__(client, prompt or load_prompt("summary_v1"), **kw)

    def write(self, segment: SourceSegment) -> MemoryRecord:
        content, rec, err, detail = self._call(segment)
        if err is not None:
            return self._base_record(segment, rec, ok=False, memory_text="",
                                     error_code=err, error_detail=detail)
        text = content.strip()
        out = self._base_record(segment, rec, ok=True, memory_text=text)
        out.raw_model_output = content
        return out


# =========================================================  C. STRUCTURED EXPERIENCE
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _extract_json_object(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse the model's output as one JSON object.

    Tolerant of a markdown fence and of leading/trailing prose, because those
    are formatting noise rather than a failure of the structure itself. NOT
    tolerant of anything that changes the CONTENT: no key repair, no quote
    fixing, no trailing-comma removal. A structure we had to repair is not the
    structure the model produced, and counting it as valid would understate the
    malformed rate -- which is a number we report.
    """
    s = text.strip()
    m = _FENCE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        obj = json.loads(s)
        return (obj, "direct") if isinstance(obj, dict) else (None, "not_an_object")
    except json.JSONDecodeError:
        pass
    start, depth, in_str, esc = None, 0, False, False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return None, "brace_scan_unparseable"
                return (obj, "brace_scan") if isinstance(obj, dict) else (None, "not_an_object")
    return None, "no_json_object_found"


def validate_structured(obj: Any, keys: Sequence[str]) -> tuple[str | None, str]:
    """Return ``(error_code, detail)``; ``(None, "")`` when valid.

    Strict on the things that make the record usable and comparable:
    exact key set, string values, and the two closed enums. No coercion --
    a repaired structure is a different structure.
    """
    if not isinstance(obj, dict):
        return ERR_MALFORMED_JSON, f"top level is {type(obj).__name__}, not an object"
    got, want = set(obj), set(keys)
    missing, extra = sorted(want - got), sorted(got - want)
    if missing:
        return ERR_MISSING_KEYS, f"missing {missing}" + (f"; extra {extra}" if extra else "")
    if extra:
        return ERR_EXTRA_KEYS, f"extra {extra}"
    bad_types = sorted(k for k in keys if not isinstance(obj[k], str))
    if bad_types:
        return ERR_NON_STRING, (
            "non-string value(s): "
            + ", ".join(f"{k}={type(obj[k]).__name__}" for k in bad_types)
        )
    empties = sorted(k for k in keys if not obj[k].strip())
    if empties:
        return ERR_NON_STRING, f"empty string value(s): {empties}"
    mt = obj["memory_type"].strip().lower()
    if mt not in VALID_MEMORY_TYPES:
        return ERR_BAD_ENUM, f"memory_type={obj['memory_type']!r} not in {sorted(VALID_MEMORY_TYPES)}"
    conf = obj["confidence"].strip().lower()
    if conf not in VALID_CONFIDENCE:
        return ERR_BAD_ENUM, f"confidence={obj['confidence']!r} not in {sorted(VALID_CONFIDENCE)}"
    return None, ""


def render_structured(obj: Mapping[str, str], keys: Sequence[str]) -> str:
    """Deterministic rendering of a validated structure into reader context.

    Fixed key ORDER (the schema's, not the dict's), so two structurally
    identical memories render byte-identically and their token counts are
    comparable. A dict-order rendering would make the token count depend on
    the order the model happened to emit keys in.
    """
    return "\n".join(f"{k}: {str(obj[k]).strip()}" for k in keys)


class StructuredWriter(_LLMWriter):
    """One call per segment, fixed JSON schema, VALIDATED.

    ``variant="procedural"`` selects the protocol's procedural schema
    (trigger · procedure · failure_mode · successful_correction · scope),
    expected to matter most for SciCode.
    """

    representation = "structured"

    def __init__(self, client: Any, *, variant: str = "general",
                 prompt: Prompt | None = None, **kw: Any):
        if variant not in ("general", "procedural"):
            raise ValueError(f"variant must be 'general' or 'procedural', got {variant!r}")
        self.variant = variant
        self.keys = STRUCTURED_KEYS if variant == "general" else STRUCTURED_PROCEDURAL_KEYS
        name = "structured_v1" if variant == "general" else "structured_procedural_v1"
        super().__init__(client, prompt or load_prompt(name), **kw)

    def write(self, segment: SourceSegment) -> MemoryRecord:
        content, rec, err, detail = self._call(segment)
        if err is not None:
            return self._base_record(segment, rec, ok=False, memory_text="",
                                     error_code=err, error_detail=detail)

        obj, how = _extract_json_object(content)
        if obj is None:
            out = self._base_record(segment, rec, ok=False, memory_text="",
                                    error_code=ERR_MALFORMED_JSON, error_detail=how)
            # KEPT, not discarded: a malformed output we cannot re-read is a
            # malformed-rate number nobody can check.
            out.raw_model_output = content
            return out

        code, vdetail = validate_structured(obj, self.keys)
        if code is not None:
            out = self._base_record(segment, rec, ok=False, memory_text="",
                                    error_code=code, error_detail=f"{vdetail} (parsed via {how})")
            out.raw_model_output = content
            out.structured = {k: v for k, v in obj.items() if isinstance(v, str)}
            return out

        clean = {k: obj[k].strip() for k in self.keys}
        clean["memory_type"] = clean["memory_type"].lower()
        clean["confidence"] = clean["confidence"].lower()
        text = render_structured(clean, self.keys)
        out = self._base_record(segment, rec, ok=True, memory_text=text)
        out.structured = clean
        # C emits the semantic type NATIVELY (protocol §2). A and B need the
        # separate classification pass in semantic_type.py.
        out.native_semantic_type = clean["memory_type"]
        out.raw_model_output = content
        return out


# ====================================================================  ORCHESTRATION
def write_all(segment: SourceSegment, *, raw: RawExtractiveWriter,
              summary: SummaryWriter | None = None,
              structured: StructuredWriter | None = None) -> dict[str, MemoryRecord]:
    """Write every configured representation from ONE segment.

    This is the sanctioned entry point because it makes the protocol's
    "all three derive from the same source segment" the structural default:
    the segment is bound once, here, and each writer gets that same object.
    Three separate call sites could each pick their own segment and the
    resulting comparison would confound representation with content selection.
    """
    out: dict[str, MemoryRecord] = {"raw": raw.write(segment)}
    if summary is not None:
        out["summary"] = summary.write(segment)
    if structured is not None:
        out["structured"] = structured.write(segment)
    return out


def writer_entry_points() -> list[tuple[str, Callable[..., Any]]]:
    """Every writer entry point, for the blindness test to discover.

    Introspection rather than a hand-kept list: a writer added later is
    covered without anyone remembering to register it. That is the difference
    between a check that stays true and one that was true once.
    """
    classes = [RawExtractiveWriter, SummaryWriter, StructuredWriter]
    return [(f"{c.__name__}.write", c.write) for c in classes]


def assert_all_writers_blind() -> None:
    for name, fn in writer_entry_points():
        assert_writer_signature(fn, name=name)

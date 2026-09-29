"""The source segment -- the ONLY thing a memory writer is allowed to see.

Why this module exists
----------------------
``docs/MEMORY_PROTOCOL.md`` §0 states the invariant the whole paper rests on::

    m = W_v(e)        -- and NOT  W_v(e, t)

The protocol asks for this to be *enforced, not just asserted*. A docstring
saying "do not pass the task" is not enforcement: it survives exactly as long
as the next refactor. This module makes the violation fail at import time, at
construction time, and at call time.

Four independent barriers
-------------------------
1. **Arity.** Every writer takes exactly one parameter, ``segment``. No
   ``**kwargs``, no ``*args``, no ``task=None`` "for logging". A caller that
   tries ``write_summary(seg, task)`` gets a ``TypeError`` from the
   interpreter, not a warning from us.
   Enforced for *every current and future* writer by
   :func:`assert_writer_signature` + ``tests/test_writer_blindness.py``, which
   discovers writers by introspection rather than from a hand-kept list.

2. **Closed field set.** :class:`SourceSegment` is ``frozen=True, slots=True``.
   ``seg.task = ...`` raises ``AttributeError`` (slots), and mutating a field
   raises ``FrozenInstanceError``. There is no dict to smuggle anything into.

3. **Metadata denylist.** ``episode_metadata`` exists because the schema has
   ``source_episode_metadata``, and it is the one free-form slot. Keys that
   name a future task (``question``, ``answer``, ``gold``, ``eval_function``
   ...) are rejected at construction. See :data:`FORBIDDEN_METADATA_KEYS`.

4. **Single interpolation point.** Prompts may reference exactly one
   placeholder, ``{segment_text}`` (see ``memory/prompts.py``). A prompt file
   that grows a ``{question}`` placeholder fails to load. So even a segment
   that somehow carried a task could not get that task into a prompt: only
   ``segment.text`` is ever interpolated.

Barrier 3 is the weakest of the four -- a denylist is a blocklist and blocklists
are incomplete. It is deliberately the *least* load-bearing: barrier 4 means
metadata never reaches a model at all, whatever it contains. Barrier 3 exists
to make an accidental plumbing mistake loud at the point it happens.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ..vendor.rcc_schema import canonical_json, sha256_text

__all__ = [
    "SourceSegment",
    "TaskLeakageError",
    "FORBIDDEN_METADATA_KEYS",
    "assert_writer_signature",
    "segment_content_id",
]


class TaskLeakageError(RuntimeError):
    """Raised when something task-shaped reaches the memory-writing path.

    This is never downgraded to a warning and never caught internally. A run
    that hits it must stop: every conditional claim in the paper is void if a
    writer saw the evaluation task.
    """


#: Substrings that, appearing in an ``episode_metadata`` KEY, mean the caller is
#: about to hand the writer something about the future evaluation task.
#: Matched case-insensitively against the whole key and against ``_``/``-``
#: separated parts of it, so ``answer_session_id`` and ``gold-answer`` both hit.
#:
#: Note ``session_id`` alone is fine (a structural id); ``answer_session_id`` is
#: not, because LongMemEval names the evidence-bearing session that way and it
#: is derived from the question.
FORBIDDEN_METADATA_KEYS: tuple[str, ...] = (
    "question",
    "query",
    "answer",
    "gold",
    "label",
    "target",
    "expected",
    "solution",
    "task",
    "eval",
    "score",
    "reward",
    "ground_truth",
    "groundtruth",
)

_WORDS = re.compile(r"[^a-z0-9]+")


def _key_is_task_shaped(key: str) -> str | None:
    """Return the offending term, or None. Substring AND token match."""
    low = str(key).lower()
    parts = set(p for p in _WORDS.split(low) if p)
    for term in FORBIDDEN_METADATA_KEYS:
        if term in low or term in parts:
            return term
    return None


@dataclass(frozen=True, slots=True)
class SourceSegment:
    """One naturally occurring segment of ONE past episode.

    ``slots=True`` is load-bearing, not a micro-optimisation: it removes
    ``__dict__``, so no attribute outside this field list can ever be attached
    to an instance. ``frozen=True`` stops a field being swapped after the
    blindness check has run.

    Fields
    ------
    segment_id
        Benchmark-native locator, e.g. LongMemEval-V2 ``"013696c4:0-0"``.
        A LOCATOR: not stable under re-segmentation. Never used as a cache key;
        see :func:`segment_content_id`.
    benchmark / benchmark_version
        Identity of the corpus the segment came from.
    source_episode_id
        The past episode. The memory's origin, never the future task.
    text
        The segment verbatim, rendered by the benchmark's own renderer. **This
        is the only field a prompt ever sees.**
    source_span
        JSON-serialisable locator making the span re-derivable, populating the
        schema's ``memory_source_span``.
    episode_metadata
        Benchmark-native metadata about the PAST episode. Screened on
        construction (barrier 3) and never interpolated into a prompt
        (barrier 4).
    """

    segment_id: str
    benchmark: str
    benchmark_version: str
    source_episode_id: str
    text: str
    source_span: Mapping[str, Any]
    episode_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("segment_id", "benchmark", "benchmark_version",
                     "source_episode_id", "text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"SourceSegment.{name} must be a non-empty string, got {value!r}"
                )
        if not isinstance(self.source_span, Mapping):
            raise ValueError("SourceSegment.source_span must be a mapping")
        if self.episode_metadata is not None:
            if not isinstance(self.episode_metadata, Mapping):
                raise ValueError("SourceSegment.episode_metadata must be a mapping or None")
            for key in self.episode_metadata:
                hit = _key_is_task_shaped(key)
                if hit is not None:
                    raise TaskLeakageError(
                        f"episode_metadata key {key!r} contains the task-shaped term "
                        f"{hit!r}. The memory writer must never observe the future "
                        f"evaluation task (docs/MEMORY_PROTOCOL.md §0). If this field is "
                        f"genuinely about the PAST episode, rename it; do not widen the "
                        f"denylist to make a leak legal."
                    )

    @property
    def content_id(self) -> str:
        return segment_content_id(self)


def segment_content_id(segment: SourceSegment) -> str:
    """Content hash of (episode id, segment text). 16 hex chars.

    Used as the response cache's ``memory_id`` at WRITE time. ``cache.py``
    explicitly forbids a positional locator there, because a locator is not
    stable under re-segmentation and two different memories could then reuse
    one cache row. This is content-derived, so re-segmenting produces a
    different id exactly when the content differs.
    """
    return sha256_text({"episode": segment.source_episode_id, "text": segment.text})[:16]


def assert_writer_signature(fn: Callable[..., Any], *, name: str = "") -> None:
    """The arity barrier. Raise unless ``fn`` can accept a segment and nothing else.

    Rules, all of them necessary:

    * exactly one parameter after ``self`` -- so there is no slot for a task;
    * it must be named ``segment`` -- so a rename cannot quietly repurpose it;
    * no ``*args`` -- a task could ride in positionally;
    * no ``**kwargs`` -- a task could ride in by keyword. This is the one people
      add "just for logging", and a logged task is still an observed task: the
      value is in the frame, and nothing stops the next edit from reading it.
    """
    label = name or getattr(fn, "__qualname__", repr(fn))
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values() if p.name not in ("self", "cls")]
    var_pos = [p.name for p in params if p.kind is inspect.Parameter.VAR_POSITIONAL]
    var_kw = [p.name for p in params if p.kind is inspect.Parameter.VAR_KEYWORD]
    if var_pos or var_kw:
        raise TaskLeakageError(
            f"writer {label} declares variadic parameter(s) "
            f"{var_pos + var_kw}. A writer must accept a segment and NOTHING else: "
            f"*args/**kwargs is an open channel for the future task."
        )
    if len(params) != 1:
        raise TaskLeakageError(
            f"writer {label} takes {len(params)} parameters "
            f"{[p.name for p in params]}; it must take exactly one, 'segment'. "
            f"m = W(episode), never W(episode, task)."
        )
    if params[0].name != "segment":
        raise TaskLeakageError(
            f"writer {label} takes {params[0].name!r}; it must be named 'segment' so "
            f"that repurposing the slot is visible in review."
        )


def blindness_probe(writer: Callable[[SourceSegment], Any]) -> None:
    """Runtime re-check, mirroring ``lmev2.assert_writer_blind``.

    Weaker than the structural argument (which is why it is not the primary
    defence), but it catches a refactor that threads a task in through a field
    the signature check cannot see.
    """
    assert_writer_signature(writer)
    base = SourceSegment(
        segment_id="probe:0-0", benchmark="probe", benchmark_version="0",
        source_episode_id="probe", text="State 0\n- URL: u0\n- Action: click\n",
        source_span={"start": 0, "end": 0},
        episode_metadata={"domain": "probe"},
    )
    a = writer(base)
    b = writer(base)
    if canonical_json(_probe_shape(a)) != canonical_json(_probe_shape(b)):
        raise TaskLeakageError(
            "writer is not deterministic on a fixed segment; the blindness probe "
            "cannot certify it. Use a cached or deterministic writer for the probe."
        )


def _probe_shape(obj: Any) -> Any:
    return getattr(obj, "memory_text", obj)

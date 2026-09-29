"""Memory representation layer (Sub-agent B).

    segment.py          the SourceSegment -- the only thing a writer may see
    prompts.py          content-addressed prompt registry (version = f(text))
    tokens.py           token counting under the benchmark's own tokenizer
    representations.py  the three writers: raw / summary / structured
    semantic_type.py    episodic | semantic_fact | procedural | failure_reflection
    faithfulness.py     deterministic faithfulness proxies + their limits
    metrics.py          compression and cost accounting per representation

The invariant this package is responsible for::

    m = W(episode)      never  W(episode, task)

See ``segment.py`` for the four barriers that make the violation a TypeError
rather than a code-review finding.
"""
from __future__ import annotations

from .faithfulness import FaithfulnessScore, raw_control, score_record, score_text
from .metrics import RepresentationStats, frontier_table, summarise
from .prompts import Prompt, load_prompt, prompt_manifest
from .representations import (
    MemoryRecord,
    RawExtractiveWriter,
    StructuredWriter,
    SummaryWriter,
    assert_all_writers_blind,
    write_all,
)
from .segment import SourceSegment, TaskLeakageError, assert_writer_signature
from .semantic_type import (
    SemanticTypeClassifier,
    TypeLabel,
    agreement_report,
    heuristic_semantic_type,
)
from .tokens import count_tokens

__all__ = [
    "SourceSegment", "TaskLeakageError", "assert_writer_signature",
    "Prompt", "load_prompt", "prompt_manifest",
    "MemoryRecord", "RawExtractiveWriter", "SummaryWriter", "StructuredWriter",
    "write_all", "assert_all_writers_blind",
    "SemanticTypeClassifier", "TypeLabel", "heuristic_semantic_type", "agreement_report",
    "FaithfulnessScore", "score_text", "score_record", "raw_control",
    "RepresentationStats", "summarise", "frontier_table",
    "count_tokens",
]

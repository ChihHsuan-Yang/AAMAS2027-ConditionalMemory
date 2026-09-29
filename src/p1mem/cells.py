"""WITH/WITHOUT cell construction with controlled filler.

Implements ``docs/MEMORY_PROTOCOL.md`` section 4: the two arms of a cell are
identical in every respect except the presence of the target memory.

Why filler is mandatory, and not a detail
-----------------------------------------
Measured on LongMemEval V1, the oracle context is *100% evidence*. Removing
"the memory" from such a context removes the entire context, so the resulting
contrast is a **no-context arm, not a memory ablation**, and it answers a
different question. Every cell therefore places the target memory inside a
fixed set of other naturally occurring units, so that removing it is a *local*
change -- a median 3.3% of its own episode.

The WITHOUT arm is K units; the WITH arm is K+1. That asymmetry *is* the
intervention. We deliberately do not length-pad the WITHOUT arm: a padded arm
changes the context distribution and confounds the very contrast being drawn.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Sequence

PROMPT_VERSION = "cells_v1"

SYSTEM = (
    "You are answering a question using notes from earlier browsing sessions. "
    "Answer from the notes when they are relevant. If the notes do not contain "
    "the answer, answer from your own knowledge. Be concise and answer directly."
)


def _seeded_rng(*parts: object) -> random.Random:
    """A deterministic RNG keyed by content, not by call order.

    Uses sha256 rather than ``hash()``: Python's string hash is salted per
    process, so a run seeded with it would not reproduce tomorrow.
    """
    h = hashlib.sha256("\x00".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


@dataclass(frozen=True)
class MemoryUnit:
    memory_id: str
    memory_unit_locator: str
    text: str
    n_tokens: int
    domain: str


def render_memory(unit: MemoryUnit, index: int) -> str:
    return f"--- Note {index} ---\n{unit.text}"


def build_context(
    target: MemoryUnit | None,
    filler: Sequence[MemoryUnit],
    *,
    seed_parts: tuple,
) -> tuple[str, int | None]:
    """Render a context, inserting ``target`` at a seeded position.

    Returns ``(context_text, target_position)``; position is ``None`` for the
    WITHOUT arm. Position is randomized and recorded because primacy/recency
    effects are a known confound -- holding the target always first or always
    last would silently confound "memory present" with "memory at a favourable
    position".
    """
    units = list(filler)
    pos: int | None = None
    if target is not None:
        rng = _seeded_rng(*seed_parts)
        pos = rng.randint(0, len(units))
        units.insert(pos, target)
    body = "\n\n".join(render_memory(u, i + 1) for i, u in enumerate(units))
    return body, pos


def build_cell_pair(
    *,
    target: MemoryUnit,
    filler: Sequence[MemoryUnit],
    task_id: str,
    question: str,
    replicate_id: int,
    benchmark: str = "longmemeval_v2",
    retrieval_method: str = "oracle_single",
) -> list[dict[str, Any]]:
    """Build the WITH and WITHOUT arms of one cell.

    Both arms share the same filler, the same seeded ordering of that filler,
    the same system prompt, and the same question. They differ only in whether
    ``target`` is present.

    The cache key carries ``replicate_id`` on BOTH arms. This is load-bearing:
    the WITHOUT arm's inputs are identical across every memory paired with a
    given task, so without the replicate in the key one generation would be
    reused everywhere, its across-draw spread would be exactly 0.000, the empty
    noise floor would collapse to zero, and *every* delta-U would trivially
    clear it. See ANALYSIS_PREREGISTRATION.md Amendment A1.4.
    """
    seed_parts = (task_id, target.memory_id, replicate_id)
    out = []
    for arm in ("without", "with"):
        ctx, pos = build_context(
            target if arm == "with" else None, filler, seed_parts=seed_parts
        )
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{ctx}\n\n--- Question ---\n{question}"},
        ]
        key_fields = {
            "benchmark": benchmark,
            "source_item_id": target.memory_unit_locator.split(":")[0],
            "memory_repr": "raw",
            "memory_id": target.memory_id,
            "future_task_id": task_id,
            "arm": arm,
            "retrieval_method": retrieval_method,
            "prompt_version": PROMPT_VERSION,
            "replicate_id": replicate_id,
        }
        out.append(
            {
                "cell_id": f"{target.memory_id}|{task_id}|{arm}|r{replicate_id}",
                "messages": messages,
                "key_fields": key_fields,
                "target_position": pos,
                "n_filler": len(filler),
            }
        )
    return out


def select_filler(
    candidates: Sequence[MemoryUnit],
    *,
    exclude_ids: set[str],
    k: int,
    task_id: str,
) -> list[MemoryUnit]:
    """Pick K filler units deterministically, seeded by the task alone.

    Every memory evaluated against a given task must see the **same** filler,
    or delta-U is not comparable across memories within that task: the WITHOUT
    arm would differ between memories and its spread would confound filler
    composition with execution noise, corrupting F_empty.

    Fixed 2026-09-29 (defect found by Sub-agent G in Master-authored code).
    The original filtered ``candidates`` by ``exclude_ids`` and *then* shuffled.
    ``random.shuffle`` consumes a number of draws that depends on the sequence
    LENGTH, so removing any element -- even one that would never have been
    drawn -- re-randomises the whole permutation. Measured on a 30-unit pool:
    **25 of 25** exclusions of a NON-drawn memory changed the selected filler.

    The fix shuffles the FULL candidate list first, making the permutation a
    pure function of ``task_id``, and only then drops excluded ids and takes K.
    Exclusion can now remove at most the excluded unit itself; it can never
    reorder or resample the rest.
    """
    ordered = list(candidates)
    rng = _seeded_rng("filler", task_id)
    rng.shuffle(ordered)
    return [u for u in ordered if u.memory_id not in exclude_ids][:k]

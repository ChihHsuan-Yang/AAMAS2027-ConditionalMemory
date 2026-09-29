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
    # Position is seeded by (task, memory) and deliberately NOT by replicate.
    # PREREG section 2 defines F_exec as outcome variation "with everything else
    # fixed", so replicates must be BYTE-IDENTICAL requests. Including
    # replicate_id here moved the target between replicates, which made the
    # replicate spread a POSITION effect rather than execution noise: measured
    # on the first noise-floor run, the WITH arm disagreed on 8 of 12 repeated
    # cells while the WITHOUT arm -- whose prompt really was fixed -- disagreed
    # on 0 of 11. That was misread as endpoint nondeterminism at temperature 0;
    # a cache-disabled probe on real 23k-27k-token cell prompts at concurrency
    # 16 returned 6/6 byte-identical, so the endpoint is deterministic and the
    # spread was entirely the moving position.
    seed_parts = (task_id, target.memory_id)
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


# ---------------------------------------------------------------------------
# The BENCHMARK'S OWN reader system prompts -- vendored VERBATIM.
# ---------------------------------------------------------------------------
# Source: LongMemEval-V2 ``evaluation/harness.py::DOMAIN_SYSTEM_PROMPTS``
# (upstream commit 2cc8c540..., harness sha256
# 93fe5855a74ad46d7e8b489cebac24de38a9b30ba7ec1de2dd8708bd4aeebdb6).
#
# These were produced by ``ast.literal_eval``-ing the upstream assignment and
# ``repr``-ing the result, NOT by copy-paste, so every byte is the byte the
# benchmark's own interpreter loads.
#
# WHY THEY MATTER: ``SYSTEM`` above is hand-written and invites an answer in
# every case. The official prompt forbids guessing and mandates
# ``\boxed{UNKNOWN}``. Measured on the pilot (results/deltau_pilot/cells.jsonl)
# the hand-written prompt abstained 0 of 958 times. A reader that always
# guesses on a hard retrieval task sits at its guessing floor, which is what
# the pilot's 17% accuracy is.
#
# ⚠️ UPSTREAM ESCAPING BUG, DELIBERATELY PRESERVED. The upstream literal is not
# a raw string, so the trailing "\boxed{}" is parsed as \x08 (BACKSPACE)
# followed by "oxed{}". The earlier "\\boxed{UNKNOWN}" is unaffected. This is
# the byte sequence the published benchmark actually sends, so repairing it
# would silently make our arm a DIFFERENT condition from the published one.
# ``assert_official_prompts_verbatim`` re-derives these from the harness on
# disk and raises on any drift, including a well-meaning repair.
OFFICIAL_PROMPT_VERSION = "official_v1"

OFFICIAL_DOMAIN_SYSTEM_PROMPTS: dict[str, str] = {
    'enterprise': (
        "You are an experienced colleague working in a customized ServiceNow environment. Answer based on your memory of the environment. If you do not know the answer, output exactly \\boxed{UNKNOWN}. Do not guess. Never attempt to guess an answer if you are not sure. If you believe the question's construction/premise is wrong, provide an explanation in \x08oxed{} explaining why the question is flawed."
    ),
    'web': (
        "You are an experienced colleague in a web browsing environment that has a customized magento-based shopping website, a customized magento-based shopping admin cms website, as well as a customized forum website based on reddit/postmill. Answer based on your memory of the environment. If you do not know the answer, output exactly \\boxed{UNKNOWN}. Do not guess. Never attempt to guess an answer if you are not sure. If you believe the question's construction/premise is wrong, provide an explanation in \x08oxed{} explaining why the question is flawed."
    ),
}

#: sha256 of each prompt STRING (not the file). Checked by the test suite and
#: by :func:`assert_official_prompts_verbatim`, and stamped into every run.
OFFICIAL_PROMPT_SHA256: dict[str, str] = {
    'enterprise': 'b2d24d41b022824ddea06b61255ead1a9aceae79e4f1658775fddd6d6e66320e',
    'web': 'c70772c5f4ab1dbdcee28218d5e2b98595a84d64196012cbd00bb9de9e63fd1f',
}


def official_system_prompt(domain: str) -> str:
    """The official reader system prompt for ``domain``.

    Mirrors ``harness.py::get_system_prompt``: an unknown domain RAISES rather
    than falling back to a default. A default here would silently answer web
    questions with the enterprise prompt -- the two differ in their opening
    sentence, which is the part that describes the environment.
    """
    if domain not in OFFICIAL_DOMAIN_SYSTEM_PROMPTS:
        raise KeyError(
            f"no official system prompt for domain {domain!r}; known: "
            f"{sorted(OFFICIAL_DOMAIN_SYSTEM_PROMPTS)}. harness.py::get_system_prompt "
            f"raises here too -- do not substitute a default."
        )
    return OFFICIAL_DOMAIN_SYSTEM_PROMPTS[domain]


def assert_official_prompts_verbatim(harness_path) -> dict[str, str]:
    """Re-derive the official prompts from ``harness.py`` and require equality.

    Parses the upstream assignment with ``ast`` rather than importing the
    harness (importing it pulls in ``openai``, ``tqdm`` and the benchmark's
    ``memory_modules`` package). Returns the per-domain sha256 map.

    Raises rather than warning: a prompt that has drifted from the published
    one is a different experimental condition wearing the same name.
    """
    import ast as _ast  # noqa: PLC0415
    import hashlib as _hashlib  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    path = _Path(harness_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found; cannot verify the official prompts are verbatim. "
            f"Refusing to assume they are."
        )
    found = None
    for node in _ast.parse(path.read_text()).body:
        if isinstance(node, _ast.Assign) and any(
            getattr(t, "id", None) == "DOMAIN_SYSTEM_PROMPTS" for t in node.targets
        ):
            found = _ast.literal_eval(node.value)
    if found is None:
        raise RuntimeError(f"no DOMAIN_SYSTEM_PROMPTS assignment in {path}")
    if found != OFFICIAL_DOMAIN_SYSTEM_PROMPTS:
        diff = {
            k: (OFFICIAL_DOMAIN_SYSTEM_PROMPTS.get(k), found.get(k))
            for k in set(found) | set(OFFICIAL_DOMAIN_SYSTEM_PROMPTS)
            if found.get(k) != OFFICIAL_DOMAIN_SYSTEM_PROMPTS.get(k)
        }
        raise RuntimeError(
            f"vendored official prompts differ from {path} on {sorted(diff)}. "
            f"They must stay byte-identical."
        )
    got = {k: _hashlib.sha256(v.encode()).hexdigest() for k, v in found.items()}
    if got != OFFICIAL_PROMPT_SHA256:
        raise RuntimeError(
            f"official prompt sha256 mismatch: expected {OFFICIAL_PROMPT_SHA256}, "
            f"got {got}"
        )
    return got

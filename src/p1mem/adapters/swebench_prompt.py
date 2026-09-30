"""Arm-symmetric prompt construction for the SWE-bench reader.

THE DEFECT THIS MODULE EXISTS TO REMOVE
---------------------------------------
The first localized pilot measured, on 7 interpretable cells:

    applicable edit   WITHOUT 7/7 = 100%   WITH 4/7 = 57.1%

The WITH arm failed to produce an applicable edit three times as often. Prompt
length was tested and rejected (failed WITH cells averaged 4,051 prompt tokens
vs 3,728 for successful ones). Re-eliciting the three failures with the
response text CAPTURED (the first run stored only the status) showed the
actual cause, and it is not what was hypothesised:

============================  ==========================================
django__django-11555 no_block ``+``-prefixed diff lines INSIDE the SEARCH
                              block; ``=======`` and ``>>>>>>> REPLACE``
                              never emitted
django__django-15375 no_block a ``-``/``+`` diff pair inside SEARCH;
                              ``=======`` never emitted
django__django-11239 search_  EVERY search line prefixed with a unified
               miss           diff's context space -- verified: the text
                              matches the source exactly after removing one
                              leading character from each line
============================  ==========================================

The WITHOUT arm at those same three cells emitted **zero** diff-marker lines
and all three envelope markers, 3/3. So the failure is **diff-format
contagion**: ``render_raw_memory`` wraps the donor patch in a ```` ```diff ````
fence, and the reader imitates that syntax instead of the SEARCH/REPLACE
syntax it was asked for. The memory competes for the OUTPUT FORMAT, not (as
first supposed) for the target region.

THE PROTOCOL CONSTRAINT THIS MUST NOT BREAK
-------------------------------------------
``docs/MEMORY_PROTOCOL.md`` §4: both arms are identical except for the
presence of ``m``. So the repair may NOT be "tell the WITH arm not to copy the
diff" -- an instruction present in one arm and absent in the other is a second
difference between the arms, and any subsequent DeltaU would confound memory
with instruction. **Every scaffold element here is emitted in BOTH arms.** The
only thing that varies is whether the memory slot holds a memory.

:func:`build_prompt` therefore renders a fixed set of sections in a fixed
order in both arms; in the WITHOUT arm the memory section is present with an
explicit "(none available)" body. :func:`assert_arm_symmetric` proves the two
renderings differ **only** inside the memory block, and is exercised on every
cell of every run, not just in a test.

THE THREE CHANGES, AND WHY EACH ONE
-----------------------------------
1. **The memory's diff is not rendered as a diff.** ``PatchFormat.DEFANGED``
   strips the ``+``/``-``/context column into a plain annotated listing inside
   a non-``diff`` fence. This removes the syntax being imitated at its source.
   It preserves the memory's full information content -- no line is dropped,
   the add/remove status is stated in words -- so this is a change of
   *encoding*, not of content.
2. **The editable region comes last**, immediately before the instruction, so
   the text nearest the "produce a SEARCH block" instruction is the text the
   SEARCH must match. Ordering is identical in both arms.
3. **The target is named explicitly and the format rule is restated at the
   point of use**, in both arms: the SEARCH must match ``### TARGET FILE``,
   and the SEARCH block may not contain diff markers.

Every one of these is a scaffold property, not an arm property.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .swebench import SolvedIssue
from .swebench_localize import Region

__all__ = [
    "PatchFormat",
    "PromptVariant",
    "PROMPT_VERSION",
    "ArmAsymmetry",
    "defang_patch",
    "render_memory",
    "build_prompt",
    "assert_arm_symmetric",
    "MEMORY_OPEN",
    "MEMORY_CLOSE",
]

#: Bumped whenever any byte of the scaffold changes. A prompt version is part
#: of experimental identity: results under v1 and v2 are different arms and
#: are never pooled.
PROMPT_VERSION = "swebench_v2_symmetric"

#: The memory slot's delimiters. ``assert_arm_symmetric`` uses them to prove
#: that everything OUTSIDE them is byte-identical across arms, so they must be
#: strings that cannot occur in source code or in an issue report.
MEMORY_OPEN = "<<<MEMORY>>>"
MEMORY_CLOSE = "<<<END MEMORY>>>"

# re.M is required: without it ``^`` anchors only at position 0, so a hunk
# header on any line but the first is invisible. Verified against the tracked
# parity artifact -- both spellings count 0 there, so no existing SWE-bench
# conclusion changes; the flag would have bitten the memory-side check below,
# where a hunk header lands mid-text rather than at the start.
_DIFF_HEADER = re.compile(r"^(diff --git |index |--- |\+\+\+ |@@ )", re.M)


class ArmAsymmetry(AssertionError):
    """The two arms differ somewhere other than inside the memory slot."""


class PatchFormat(str, Enum):
    """How a donor patch is encoded inside a memory.

    Named rather than left to a boolean, because it is the manipulated
    variable in the arm-symmetry repair and both settings must stay runnable
    so the repair can be measured against its own control.
    """

    #: Verbatim unified diff in a ```` ```diff ```` fence -- what v1 did, and
    #: the format the reader imitates. Kept so the fix has a control arm.
    RAW_DIFF = "raw_diff"
    #: Same information, no diff syntax: the ``+``/``-``/space column is
    #: removed and stated in words instead.
    DEFANGED = "defanged"


class PromptVariant(str, Enum):
    """Which scaffold to build. ``V1_LEGACY`` reproduces the failing run."""

    V1_LEGACY = "v1_legacy"
    V2_SYMMETRIC = "v2_symmetric"


# --------------------------------------------------------------------------
# defanging
# --------------------------------------------------------------------------


def defang_patch(patch: str) -> str:
    """Re-encode a unified diff with no diff syntax and no information loss.

    Every content line survives; the leading ``+``/``-``/space column that the
    reader imitates is replaced by an explicit word. Diff machinery lines
    (``diff --git``, ``index``, ``---``, ``+++``, ``@@``) become prose.

    This is deliberately NOT a summary. Dropping lines would change what the
    memory contains and confound the format repair with a content change; the
    only thing that changes is the encoding of the add/remove column.
    """
    out: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            out.append(f"[file] {parts[-1][2:] if parts[-1].startswith('b/') else parts[-1]}")
        elif line.startswith(("index ", "--- ", "+++ ", "new file mode",
                              "deleted file mode", "similarity index",
                              "rename from", "rename to")):
            continue
        elif line.startswith("@@"):
            out.append("[hunk]")
        elif line.startswith("+"):
            out.append(f"[added]    {line[1:]}")
        elif line.startswith("-"):
            out.append(f"[removed]  {line[1:]}")
        elif line.startswith("\\"):
            continue
        else:
            out.append(f"[context]  {line[1:] if line.startswith(' ') else line}")
    return "\n".join(out)


def render_memory(m: SolvedIssue, fmt: PatchFormat = PatchFormat.DEFANGED) -> str:
    """The memory's body, WITHOUT the surrounding slot markers.

    Content is the same past issue and the same fix under either format; only
    the patch's encoding differs.
    """
    if fmt is PatchFormat.RAW_DIFF:
        body = f"### How it was fixed\n```diff\n{m.patch.strip()}\n```"
    else:
        body = ("### How it was fixed (annotated listing, NOT a diff -- do not "
                "copy this notation)\n```text\n" + defang_patch(m.patch) + "\n```")
    return (f"### Past issue in {m.repo} (resolved {m.created_at.date()})\n"
            f"{m.problem_statement.strip()}\n\n{body}")


# --------------------------------------------------------------------------
# the scaffold
# --------------------------------------------------------------------------

_SYSTEM_V2 = (
    "You edit Python source to fix a bug.\n"
    "Reply ONLY with one or more edit blocks in EXACTLY this format:\n"
    "<<<<<<< SEARCH\n"
    "<lines copied verbatim from the TARGET FILE region shown below>\n"
    "=======\n"
    "<replacement lines>\n"
    ">>>>>>> REPLACE\n"
    "All three marker lines are required. The SEARCH text must match the "
    "TARGET FILE region byte-for-byte: copy it exactly as shown, with no "
    "added prefix characters and no '+', '-' or diff notation of any kind. "
    "Write the full replacement lines, not a diff."
)

_INSTRUCTION_V2 = (
    "Make the minimal edit that fixes the issue.\n"
    "Your SEARCH text must be copied verbatim from the TARGET FILE region "
    "immediately above. Do not search in, or copy notation from, any other "
    "section of this message."
)


@dataclass(frozen=True)
class BuiltPrompt:
    """A rendered prompt plus the fields a record needs to reproduce it."""

    system: str
    user: str
    variant: str
    patch_format: str
    prompt_version: str
    has_memory: bool


def _memory_slot(body: str) -> str:
    return f"{MEMORY_OPEN}\n{body}\n{MEMORY_CLOSE}"


def build_prompt(
    *,
    path: str,
    shown_region: str,
    issue_text: str,
    memory: SolvedIssue | None,
    variant: PromptVariant = PromptVariant.V2_SYMMETRIC,
    patch_format: PatchFormat = PatchFormat.DEFANGED,
    issue_chars: int = 1500,
    memory_body: str | None = None,
) -> BuiltPrompt:
    """Render one arm's prompt.

    ``memory=None`` is the WITHOUT arm. In ``V2_SYMMETRIC`` the memory SECTION
    is present in both arms -- only its body differs -- so the two renderings
    are byte-identical outside the slot markers. That is what makes ``DeltaU``
    attributable to the memory rather than to the scaffold.
    """
    issue = (issue_text or "").strip()[:issue_chars]

    if variant is PromptVariant.V1_LEGACY:
        # Reproduced byte-for-byte from scripts/swebench_floor_pilot.py's v1
        # so the repair can be compared against the run it repairs. Note the
        # asymmetry it carries: the WITHOUT arm has no memory section at all.
        from .swebench import SEARCH_REPLACE_INSTRUCTIONS, render_raw_memory
        user = (f"### Candidate regions of {path}\n```python\n{shown_region}\n```\n\n"
                f"### Issue\n{issue}\n\n"
                "Make the minimal edit that fixes the issue.")
        ctx = (render_raw_memory(memory) + "\n\n") if memory is not None else ""
        return BuiltPrompt(
            system="You edit Python source to fix a bug.\n" + SEARCH_REPLACE_INSTRUCTIONS,
            user=ctx + user, variant=variant.value,
            patch_format=PatchFormat.RAW_DIFF.value,
            prompt_version="swebench_v1", has_memory=memory is not None)

    # ``memory_body`` is the representation arm's entry point: a written
    # Summary/Structured memory is already text and has no SolvedIssue to
    # render. It occupies the SAME slot, so arm symmetry is unaffected and
    # still checked per cell. Supplying both is a caller error, not a
    # silent precedence rule.
    if memory_body is not None and memory is not None:
        raise ValueError("pass memory OR memory_body, not both: their bodies "
                         "would silently disagree about what the memory is")
    if memory_body is not None:
        body = memory_body
    elif memory is not None:
        body = render_memory(memory, patch_format)
    else:
        body = "(none available for this task)"
    user = (
        "### Prior experience (reference only -- this is NOT the file you edit)\n"
        f"{_memory_slot(body)}\n\n"
        f"### Issue\n{issue}\n\n"
        f"### TARGET FILE: {path}\n"
        "This, and only this, is the code you may edit. Your SEARCH block must "
        "match text inside it exactly.\n"
        f"```python\n{shown_region}\n```\n\n"
        f"{_INSTRUCTION_V2}"
    )
    return BuiltPrompt(
        system=_SYSTEM_V2, user=user, variant=variant.value,
        patch_format=patch_format.value if (memory is not None or memory_body is not None) else "n/a",
        prompt_version=PROMPT_VERSION,
        has_memory=(memory is not None or memory_body is not None))


# --------------------------------------------------------------------------
# the symmetry guarantee -- checked at runtime, on every cell
# --------------------------------------------------------------------------


def _split_slot(user: str) -> tuple[str, str, str]:
    i = user.index(MEMORY_OPEN)
    j = user.index(MEMORY_CLOSE) + len(MEMORY_CLOSE)
    return user[:i], user[i:j], user[j:]


def assert_arm_symmetric(without: BuiltPrompt, with_: BuiltPrompt) -> None:
    """Prove the two arms differ ONLY inside the memory slot.

    Raises :class:`ArmAsymmetry` with a unified diff of the offending region.
    Called per cell in the runner, not only in a test: a scaffold change that
    reintroduces an arm-only instruction must stop the run, not be discovered
    later in a report.

    A prompt that lacks the slot markers entirely (``V1_LEGACY``) cannot be
    checked, and asking to check it is itself an error rather than a pass --
    a symmetry check that silently returns on an uncheckable input is the
    "presence fails closed, absence fails open" defect.
    """
    for name, p in (("WITHOUT", without), ("WITH", with_)):
        if MEMORY_OPEN not in p.user or MEMORY_CLOSE not in p.user:
            raise ArmAsymmetry(
                f"{name} prompt has no memory slot, so symmetry is unverifiable "
                f"(variant={p.variant}). Refusing to report it as symmetric.")
    if without.system != with_.system:
        raise ArmAsymmetry("system prompts differ between arms:\n" + "\n".join(
            difflib.unified_diff(without.system.splitlines(),
                                 with_.system.splitlines(),
                                 "WITHOUT", "WITH", lineterm="")))
    pre_a, _, post_a = _split_slot(without.user)
    pre_b, _, post_b = _split_slot(with_.user)
    if pre_a != pre_b or post_a != post_b:
        raise ArmAsymmetry("arms differ OUTSIDE the memory slot:\n" + "\n".join(
            difflib.unified_diff((pre_a + "\n<<<SLOT>>>\n" + post_a).splitlines(),
                                 (pre_b + "\n<<<SLOT>>>\n" + post_b).splitlines(),
                                 "WITHOUT", "WITH", lineterm="")))
    if without.has_memory or not with_.has_memory:
        raise ArmAsymmetry(
            f"arms are mislabelled: WITHOUT.has_memory={without.has_memory}, "
            f"WITH.has_memory={with_.has_memory}")


def response_has_diff_contagion(response: str | None) -> dict[str, Any]:
    """Diagnose a response for the failure this module removes.

    Reports the observable signals rather than a verdict, so a run records
    WHY a block failed and a later reader is not left with a bare status.
    """
    text = response or ""
    body = text
    marker_lines = [ln for ln in body.splitlines()
                    if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    return {
        "has_search_marker": "<<<<<<< SEARCH" in text,
        "has_separator": "=======" in text,
        "has_replace_marker": ">>>>>>> REPLACE" in text,
        "n_diff_marker_lines": len(marker_lines),
        "n_hunk_headers": len(_DIFF_HEADER.findall(text)),
    }


# --------------------------------------------------------------------------
# representation arm
# --------------------------------------------------------------------------

#: What a representation writer is allowed to see for a SWE-bench memory.
#:
#: The patch is handed over **defanged**. That is not cosmetic. The arm-parity
#: repair exists because the reader imitates ``+``/``-`` notation it sees; a
#: model-written summary of a raw diff can reproduce that notation and quietly
#: reintroduce the contagion inside a representation that is supposed to be
#: compared against raw on equal footing. Defanging the writer's input makes
#: the three representations differ in *encoding of the memory*, not in whether
#: the reader is exposed to diff syntax.
REPRESENTATION_SEGMENT_VERSION = "swebench_segment_defanged@1.0.0"


def to_source_segment(m: "SolvedIssue", *, benchmark_version: str) -> Any:
    """The only object a representation writer sees for a SWE-bench memory.

    Mirrors the SciCode adapter's entry point, for the same reason: binding
    the segment once means all three representations are written from the
    SAME source text, so a later comparison cannot confound representation
    with content selection.
    """
    from p1mem.memory.segment import SourceSegment

    return SourceSegment(
        segment_id=m.instance_id,
        benchmark="swebench_verified",
        benchmark_version=benchmark_version,
        source_episode_id=m.instance_id,
        text=(f"### Past issue in {m.repo} (resolved {m.created_at.date()})\n"
              f"{m.problem_statement.strip()}\n\n"
              f"### How it was fixed (annotated listing, NOT a diff)\n"
              f"{defang_patch(m.patch)}"),
        source_span={"split": "test", "instance_id": m.instance_id,
                     "fields": ["problem_statement", "patch"],
                     "patch_encoding": "defanged"},
        episode_metadata={"repo": m.repo,
                          "n_files_touched": len(m.files),
                          "resolved": m.created_at.date().isoformat()},
    )


def memory_body_for_representation(rep: str, *, m: "SolvedIssue",
                                   written_text: str | None) -> str:
    """The memory block body for one representation.

    ``raw`` is the deterministic defanged rendering already used by the parity
    run -- unchanged, so the raw arm of this experiment IS the arm that passed
    parity. ``summary``/``structured`` wrap the writer's text in the same
    outer framing so the three differ only in the memory content itself.
    """
    if rep == "raw":
        return render_memory(m, PatchFormat.DEFANGED)
    if not written_text:
        raise ValueError(f"representation {rep!r} has no written text")
    return (f"### Past issue in {m.repo} (resolved {m.created_at.date()})\n"
            f"### What was learned (annotated notes, NOT a diff -- do not "
            f"copy this notation)\n```text\n{written_text.strip()}\n```")


def memory_contagion_risk(body: str) -> dict[str, Any]:
    """Does a MEMORY body carry the notation the reader imitates?

    Runs on the memory, not the response. The parity repair removed diff
    syntax from the raw memory; a model-written representation can put it
    back. Measuring this on every memory before the run means a
    representation arm cannot silently reintroduce the defect that voided v1.
    """
    lines = [ln for ln in body.splitlines()
             if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    return {
        "n_diff_marker_lines": len(lines),
        "n_hunk_headers": len(_DIFF_HEADER.findall(body)),
        "has_diff_fence": "```diff" in body,
        "clean": not lines and not _DIFF_HEADER.findall(body) and "```diff" not in body,
    }

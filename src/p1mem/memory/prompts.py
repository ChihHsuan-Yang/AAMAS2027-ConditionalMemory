"""Content-addressed prompt registry (B2).

Three prior incidents in this project came from prompt drift across copies
(see the memory note "Three functions, one name"): a copied function body is
not a copied prompt, and a hand-maintained ``PROMPT_VERSION = "v2"`` label
keeps saying ``v2`` after the text beneath it changes. So here the version IS
a function of the text:

    memory_writer_prompt_version = "<name>@<semver>+<sha256(text)[:12]>"

Edit one character of a prompt file and the version string on every row
changes. Nothing to remember, nothing to bump, and a stale copy is visibly a
different version rather than an identical-looking one.

Prompts live in ``configs/prompts/*.txt`` -- plain text, one prompt per file,
no code. They are loaded and the digest is computed from the **file bytes on
disk**, so the recorded version describes what actually ran, not a constant
some module re-declares. ``PROMPT_DIR`` is resolved from this file's location,
so there is exactly one copy in the tree and no second definition to drift
from (the "three functions, one name" defect).

The single-placeholder rule
---------------------------
A prompt body may contain exactly one placeholder, ``{segment_text}``. This is
barrier 4 of the task-leakage defence in ``memory/segment.py``: since the only
substitution the renderer performs is the segment's own text, there is no
syntax by which a future task could enter a prompt, even if one were somehow
in scope. A prompt file containing ``{question}``, ``{task}`` or any other
placeholder raises at load time.

``{{`` / ``}}`` escapes are supported for literal braces, which the structured
prompt needs to show a JSON example.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..vendor.rcc_schema import sha256_text

__all__ = [
    "PROMPT_DIR",
    "SEGMENT_PLACEHOLDER",
    "Prompt",
    "PromptError",
    "load_prompt",
    "all_prompts",
    "prompt_manifest",
]

#: configs/prompts/, resolved relative to this file: src/p1mem/memory/prompts.py
#: -> parents[3] == repo root. Resolved, not configurable, so there is one
#: prompt tree and a second copy cannot be silently preferred.
PROMPT_DIR = Path(__file__).resolve().parents[3] / "configs" / "prompts"

SEGMENT_PLACEHOLDER = "segment_text"

#: A prompt file's first line must be exactly ``#!p1mem-prompt <name> <semver>``.
#: The name and semver are human-readable provenance; they do NOT stand in for
#: the digest, which is always appended.
_HEADER = re.compile(r"^#!p1mem-prompt\s+([a-z0-9_]+)\s+(\d+\.\d+\.\d+)\s*$")

#: Finds ``{placeholder}`` while skipping ``{{`` and ``}}`` escapes.
_PLACEHOLDER = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


class PromptError(ValueError):
    """A prompt file is malformed, or would allow task text into a prompt."""


@dataclass(frozen=True, slots=True)
class Prompt:
    """One loaded prompt. ``version`` is derived from ``text``, never declared."""

    name: str
    semver: str
    text: str
    sha256: str
    path: str

    @property
    def version(self) -> str:
        """The string written to ``memory_writer_prompt_version`` on every row."""
        return f"{self.name}@{self.semver}+{self.sha256[:12]}"

    def render(self, segment_text: str) -> str:
        """Substitute the ONE permitted placeholder. No other input is accepted.

        Takes a bare string rather than a segment so that this function is
        physically incapable of reading any other segment field -- and so that
        no caller can pass an object with a ``.question`` attribute in the hope
        that a format spec picks it up.
        """
        if not isinstance(segment_text, str):
            raise PromptError(
                f"render() takes the segment TEXT as a str, got "
                f"{type(segment_text).__name__}. Passing an object would let a "
                f"format spec reach its other attributes."
            )
        out = self.text.replace("{" + SEGMENT_PLACEHOLDER + "}", segment_text)
        # Unescape literal braces only after substitution, so a brace inside the
        # segment text can never be interpreted as a placeholder.
        return out.replace("{{", "{").replace("}}", "}")


def _parse(path: Path, raw: str) -> Prompt:
    lines = raw.split("\n")
    if not lines:
        raise PromptError(f"{path}: empty prompt file")
    m = _HEADER.match(lines[0])
    if m is None:
        raise PromptError(
            f"{path}: first line must be '#!p1mem-prompt <name> <semver>', got "
            f"{lines[0]!r}"
        )
    name, semver = m.group(1), m.group(2)
    if name != path.stem:
        raise PromptError(
            f"{path}: header name {name!r} != filename stem {path.stem!r}. "
            f"Two names for one prompt is how a copy drifts."
        )
    body = "\n".join(lines[1:]).strip("\n")
    if not body.strip():
        raise PromptError(f"{path}: prompt body is empty")

    placeholders = set(_PLACEHOLDER.findall(body))
    illegal = sorted(placeholders - {SEGMENT_PLACEHOLDER})
    if illegal:
        raise PromptError(
            f"{path}: illegal placeholder(s) {illegal}. A memory-writer prompt may "
            f"interpolate ONLY {{{SEGMENT_PLACEHOLDER}}}. Any other placeholder is a "
            f"channel through which the future evaluation task could reach the writer "
            f"(docs/MEMORY_PROTOCOL.md §0). Use '{{{{' for a literal brace."
        )
    if SEGMENT_PLACEHOLDER not in placeholders:
        raise PromptError(
            f"{path}: prompt never interpolates {{{SEGMENT_PLACEHOLDER}}}; it would "
            f"produce the same memory for every segment."
        )

    # Digest the WHOLE FILE including the header: a semver bump with no body
    # change must still be visible as a different version, and a body change
    # with no semver bump must too.
    return Prompt(name=name, semver=semver, text=body,
                  sha256=sha256_text(raw), path=str(path))


@lru_cache(maxsize=None)
def _load_cached(path_str: str, mtime_ns: int, size: int) -> Prompt:
    # mtime and size are in the cache key so an edit on disk invalidates the
    # memoised Prompt. Caching on the path alone would reintroduce exactly the
    # stale-copy defect this module exists to prevent.
    path = Path(path_str)
    return _parse(path, path.read_text())


def load_prompt(name: str, *, prompt_dir: Path | None = None) -> Prompt:
    """Load ``<prompt_dir>/<name>.txt`` and derive its version from its bytes."""
    directory = Path(prompt_dir) if prompt_dir is not None else PROMPT_DIR
    path = directory / f"{name}.txt"
    if not path.is_file():
        available = sorted(p.stem for p in directory.glob("*.txt")) if directory.is_dir() else []
        raise PromptError(f"no prompt {name!r} at {path}. Available: {available}")
    st = path.stat()
    return _load_cached(str(path), st.st_mtime_ns, st.st_size)


def all_prompts(*, prompt_dir: Path | None = None) -> dict[str, Prompt]:
    directory = Path(prompt_dir) if prompt_dir is not None else PROMPT_DIR
    if not directory.is_dir():
        raise PromptError(f"prompt directory not found: {directory}")
    return {p.stem: load_prompt(p.stem, prompt_dir=directory)
            for p in sorted(directory.glob("*.txt"))}


def prompt_manifest(*, prompt_dir: Path | None = None) -> dict[str, dict[str, str]]:
    """Name -> {version, sha256, semver}. Written next to results as provenance."""
    return {
        name: {"version": p.version, "sha256": p.sha256, "semver": p.semver}
        for name, p in all_prompts(prompt_dir=prompt_dir).items()
    }

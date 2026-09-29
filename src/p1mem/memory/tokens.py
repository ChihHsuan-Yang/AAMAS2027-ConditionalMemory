"""Token counting under the benchmark's OWN tokenizer (B5).

Every token number this project reports -- memory size, compression ratio,
the efficiency frontier's x-axis -- must be counted with one tokenizer, and
that tokenizer must be the benchmark's, so our budgets are comparable to the
benchmark's own. ``lmev2.OFFICIAL_TOKENIZER`` names it: ``Qwen/Qwen3.5-9B``,
the tokenizer ``evaluation/harness.py::get_memory_context_processor()`` loads.

Why not ``transformers.AutoTokenizer``
--------------------------------------
``transformers`` is not installed in the 3.13 interpreter this project uses
and pulls in ``torch``. The tokenizer is already in the HF cache as a plain
``tokenizer.json``, so we load that file with the much smaller ``tokenizers``
package. Same vocabulary and same merges: ``AutoTokenizer.from_pretrained``
for a fast tokenizer is a thin wrapper over exactly this file.

``scripts/build_lmev2_units.py`` counted with ``tok(text, add_special_tokens=False)``
and produced ``data/manifests/lmev2_memory_unit_tokens.json``. We call
``encode(text, add_special_tokens=False)`` -- the same setting -- and
``tests/test_memory_tokens.py`` reproduces a recorded count from that manifest
so the two paths are pinned to each other rather than merely believed equal.

Fallback, and why it is loud
----------------------------
If the tokenizer cannot be loaded, :func:`count_tokens` RAISES. It does not
fall back to a character heuristic. A silently approximate token count would
put a wrong x-axis under the efficiency frontier, and a wrong axis is worse
than a missing one. Use :func:`tokenizer_available` to branch.
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache
from pathlib import Path

__all__ = [
    "OFFICIAL_TOKENIZER",
    "TokenizerUnavailable",
    "count_tokens",
    "tokenizer_available",
    "tokenizer_provenance",
]

#: Duplicated from ``lmev2.OFFICIAL_TOKENIZER`` only as a default; the real
#: value is read from the adapter at call time so there is one definition.
_DEFAULT_TOKENIZER = "Qwen/Qwen3.5-9B"


def _official_name() -> str:
    try:
        from ..adapters import lmev2  # noqa: PLC0415
        return lmev2.OFFICIAL_TOKENIZER
    except Exception:  # noqa: BLE001  -- adapter optional at import time
        return _DEFAULT_TOKENIZER


OFFICIAL_TOKENIZER = _official_name()


class TokenizerUnavailable(RuntimeError):
    """The official tokenizer could not be loaded. Never silently approximated."""


def _hf_cache_candidates(name: str) -> list[str]:
    root = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
    slug = "models--" + name.replace("/", "--")
    return sorted(glob.glob(str(Path(root) / "hub" / slug / "snapshots" / "*" / "tokenizer.json")))


@lru_cache(maxsize=4)
def _tokenizer(name: str):
    try:
        from tokenizers import Tokenizer  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise TokenizerUnavailable(
            f"the `tokenizers` package is not importable ({exc}); cannot count tokens "
            f"under {name}. Install it rather than substituting an approximation."
        ) from exc
    paths = _hf_cache_candidates(name)
    if not paths:
        raise TokenizerUnavailable(
            f"no cached tokenizer.json for {name} under the HF hub cache. "
            f"Token counts must use the benchmark's own tokenizer; refusing to guess."
        )
    return Tokenizer.from_file(paths[-1]), paths[-1]


def tokenizer_available(name: str | None = None) -> bool:
    try:
        _tokenizer(name or OFFICIAL_TOKENIZER)
        return True
    except TokenizerUnavailable:
        return False


def count_tokens(text: str, *, name: str | None = None) -> int:
    """Token count under the official tokenizer, ``add_special_tokens=False``.

    Matches ``scripts/build_lmev2_units.py``'s setting exactly.
    """
    if not isinstance(text, str):
        raise TypeError(f"count_tokens takes a str, got {type(text).__name__}")
    tok, _ = _tokenizer(name or OFFICIAL_TOKENIZER)
    return len(tok.encode(text, add_special_tokens=False).ids)


def tokenizer_provenance(name: str | None = None) -> dict[str, str]:
    """What was actually loaded, for the run manifest."""
    resolved = name or OFFICIAL_TOKENIZER
    tok, path = _tokenizer(resolved)
    return {"tokenizer": resolved, "tokenizer_file": path,
            "vocab_size": str(tok.get_vocab_size())}

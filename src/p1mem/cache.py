"""Append-only response cache for P1 endpoint calls.

Why this exists
---------------
A P1 run replays the same reader against the same (memory, task) pairs many
times across arms and replicates. Re-issuing an identical call wastes gateway
budget; re-issuing a *nearly* identical call and treating it as identical
silently corrupts the experiment. This cache is built to make the second
failure impossible, at the cost of some verbosity in the key.

The one rule that matters
-------------------------
**A cache hit must never cross a serving-configuration boundary.** Two calls
share a cache entry only if every field that could change the response is
equal -- including ``cluster``. Metis ``gpt-oss-120b`` and Sophia
``openai/gpt-oss-120b`` are different arms of the experiment and must never
share a row, even though they are "the same model". See
``tests/test_cache.py::test_cluster_changes_the_key``.

Design choices, and the reasons
-------------------------------
* **Append-only JSONL**, written with ``write_jsonl_atomic`` (tmp file +
  ``os.replace``), so an interrupted write can never truncate an existing
  cache. Reads use ``load_jsonl(strict=True)``: a malformed line RAISES. A
  silent-skip loader would turn a corrupted cache into a quietly smaller one,
  and a quietly smaller cache looks exactly like a cache miss.
* **Thread-locked**, following ``candidate_label_cache.py``: the lock guards
  the in-memory dict and the file append together, so concurrent workers
  cannot interleave a JSONL line or double-write a key. We run 16 workers.
* **The key is a hash of a canonical dict**, not a tuple of positional
  fields. Adding a new discriminating field is then a one-line change that
  *invalidates old rows by construction* rather than silently colliding with
  them.
* **Unknown key fields are rejected.** A typo like ``moel_id=`` would
  otherwise create a key missing the real model id and hit across models.

Hashing and I/O primitives are reused verbatim from the receiver-conditional
project via ``p1mem.vendor.rcc_schema`` -- unmodified, so their behaviour is
identical to code already exercised at scale.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .vendor.rcc_schema import (  # noqa: F401  (re-exported on purpose)
    canonical_json,
    load_jsonl,
    sha256_text,
    utc_now,
    write_jsonl_atomic,
)

CACHE_SCHEMA_VERSION = "p1mem_response_cache_v1"

# Every field that can change a response. All are REQUIRED on every lookup and
# store: a missing one raises rather than defaulting, because a default is not
# a choice -- an absent field silently merging two conditions is the exact
# failure this cache exists to prevent.
KEY_FIELDS: tuple[str, ...] = (
    "benchmark",          # e.g. "longmemeval"
    "source_item_id",     # the source item the memory was written from
    "memory_repr",        # memory representation (raw trace / summary / insight ...)
    # The canonical memory identity from src/p1mem/schema.py: a CONTENT HASH
    # (content + source episode id), stable across runs and re-segmentation.
    # This cache treats it as an opaque string and never derives or rewrites
    # it. Do NOT pass a positional locator such as "013696c4:0-0" here: a
    # locator is not stable under re-segmentation, so two different memories
    # could reuse one cache row after the corpus is rebuilt. A locator belongs
    # in the schema's memory_source_span, not in this key.
    "memory_id",
    "future_task_id",     # the future task being attempted
    "arm",                # "with_memory" | "without_memory"
    "retrieval_method",   # e.g. "oracle", "bm25", "sfr_embedding_top5"
    "model_id",           # EXACT id as sent to the server, never normalised
    "cluster",            # metis | sophia | minerva -- never collapsed
    "prompt_version",     # bump to invalidate on any prompt edit
    "decoding_params",    # dict: temperature, max_tokens, reasoning_effort, ...
    "replicate_id",       # replicate index for repeated sampling
    # ------------------------------------------------------------------
    # Added 2026-09-29 after a DEMONSTRATED cross-condition collision.
    #
    # Everything above identifies WHICH cell this is. Nothing above
    # identifies WHAT CONTEXT WAS ACTUALLY RENDERED. The pilot rendered K=6
    # filler units drawn from a 12-trajectory reservation; the screened run
    # renders K=4 from a bearing-disjoint 50-trajectory pool. Those are
    # different prompt bytes under a byte-identical key, so a pilot answer
    # could be served to the screened run. Only the separate cache FILE
    # prevented it -- an argument default, not an invariant.
    #
    # Verified by direct experiment: storing a K=6 response and looking up
    # the K=4 key returned HIT with the pilot's content.
    #
    # This field is the sha256 of the fully rendered messages. It makes the
    # key describe the request that was actually sent, so any change to
    # filler count, filler pool, ordering, or scaffold misses instead of
    # silently reusing a different experiment's answer.
    "context_sha256",
)


class CacheKeyError(ValueError):
    """Raised when a cache key is malformed. Never swallowed."""


def make_key(**fields: Any) -> dict[str, Any]:
    """Validate and normalise a cache key.

    Raises on a missing or unexpected field. ``decoding_params`` must be a
    mapping; it is canonicalised so key order cannot produce two keys for one
    configuration.
    """
    missing = [f for f in KEY_FIELDS if f not in fields]
    if missing:
        raise CacheKeyError(f"cache key missing required field(s): {sorted(missing)}")
    unexpected = [f for f in fields if f not in KEY_FIELDS]
    if unexpected:
        raise CacheKeyError(
            f"unexpected cache key field(s): {sorted(unexpected)}. "
            f"Allowed: {sorted(KEY_FIELDS)}. A silently-ignored field would "
            f"let two different conditions share one cache row."
        )

    decoding = fields["decoding_params"]
    if not isinstance(decoding, dict):
        raise CacheKeyError(
            f"decoding_params must be a dict, got {type(decoding).__name__}"
        )
    for name in ("cluster", "model_id", "arm", "prompt_version"):
        if fields[name] is None or str(fields[name]).strip() == "":
            raise CacheKeyError(f"cache key field {name!r} must be a non-empty value")

    key = {f: fields[f] for f in KEY_FIELDS}
    key["decoding_params"] = json.loads(canonical_json(decoding))
    key["schema_version"] = CACHE_SCHEMA_VERSION
    return key


def key_hash(key: dict[str, Any]) -> str:
    """Stable sha256 of a validated key dict."""
    return sha256_text(key)


@dataclass
class CachedResponse:
    """One cached endpoint response plus the accounting we need for the paper."""

    content: str
    resolved_model: str
    cluster: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int | None = None
    finish_reason: str = ""
    latency_s: float = 0.0
    retry_count: int = 0
    error_code: str | None = None
    raw_usage: dict[str, Any] = field(default_factory=dict)
    stored_at_utc: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "resolved_model": self.resolved_model,
            "cluster": self.cluster,
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "reasoning_tokens": self.reasoning_tokens,
            "finish_reason": self.finish_reason,
            "latency_s": float(self.latency_s),
            "retry_count": int(self.retry_count),
            "error_code": self.error_code,
            "raw_usage": self.raw_usage,
            "stored_at_utc": self.stored_at_utc or utc_now(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CachedResponse":
        return cls(
            content=row.get("content", ""),
            resolved_model=row.get("resolved_model", ""),
            cluster=row.get("cluster", ""),
            prompt_tokens=int(row.get("prompt_tokens") or 0),
            completion_tokens=int(row.get("completion_tokens") or 0),
            reasoning_tokens=row.get("reasoning_tokens"),
            finish_reason=row.get("finish_reason", ""),
            latency_s=float(row.get("latency_s") or 0.0),
            retry_count=int(row.get("retry_count") or 0),
            error_code=row.get("error_code"),
            raw_usage=row.get("raw_usage") or {},
            stored_at_utc=row.get("stored_at_utc", ""),
        )


class ResponseCache:
    """Thread-safe append-only JSONL response cache.

    Usage::

        cache = ResponseCache("results/cache/reader.jsonl")
        key = make_key(benchmark="longmemeval", ..., cluster="metis", ...)
        hit = cache.lookup(key)
        if hit is None:
            resp = call_endpoint(...)
            cache.store(key, resp)
    """

    def __init__(self, path: str | Path, *, strict: bool = True):
        self.path = Path(path).expanduser().resolve()
        self.strict = strict
        self._rows: dict[str, CachedResponse] = {}
        self._keys: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self.writes = 0
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------- loading
    def _load(self) -> None:
        if not self.path.exists():
            return
        # strict=True: a malformed line raises. A cache that silently drops
        # rows is indistinguishable from a cache miss, and a cache miss costs
        # real gateway budget and can change a measured number.
        rows = load_jsonl(self.path, strict=self.strict)
        for idx, row in enumerate(rows, start=1):
            khash = row.get("key_hash")
            key = row.get("key")
            resp = row.get("response")
            if not khash or not isinstance(key, dict) or not isinstance(resp, dict):
                raise ValueError(
                    f"Malformed cache row at {self.path}:{idx} "
                    f"(needs key_hash, key, response)"
                )
            recomputed = key_hash(key)
            if recomputed != khash:
                raise ValueError(
                    f"Cache row {idx} in {self.path} has key_hash {khash!r} but its "
                    f"key hashes to {recomputed!r}. The file was edited, produced by "
                    f"a different schema version, or corrupted. Refusing to use it."
                )
            # Last write wins, matching append-only replay order.
            self._rows[khash] = CachedResponse.from_row(resp)
            self._keys[khash] = key

    # ------------------------------------------------------------- lookup
    def lookup(self, key: dict[str, Any]) -> CachedResponse | None:
        khash = key_hash(key)
        with self._lock:
            hit = self._rows.get(khash)
            if hit is None:
                self.misses += 1
            else:
                self.hits += 1
            return hit

    def contains(self, key: dict[str, Any]) -> bool:
        with self._lock:
            return key_hash(key) in self._rows

    # -------------------------------------------------------------- store
    def store(self, key: dict[str, Any], response: CachedResponse,
              *, overwrite: bool = False) -> str:
        khash = key_hash(key)
        with self._lock:
            if khash in self._rows and not overwrite:
                return khash
            row = {
                "key_hash": khash,
                "key": key,
                "response": response.to_row(),
                "written_at_utc": utc_now(),
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Append is atomic for a single line under O_APPEND on POSIX for
            # writes below PIPE_BUF-ish sizes, but our rows are large, so the
            # lock above -- not the OS -- is what guarantees non-interleaving.
            # fsync so a laptop sleeping mid-run does not lose the row.
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._rows[khash] = response
            self._keys[khash] = key
            self.writes += 1
            return khash

    # ------------------------------------------------------------- compact
    def compact(self, dest: str | Path | None = None) -> Path:
        """Rewrite the cache with one row per key, atomically.

        Append-only means a key updated with ``overwrite=True`` appears more
        than once. This collapses duplicates using ``write_jsonl_atomic`` so an
        interrupted compaction cannot destroy the original.
        """
        target = Path(dest).expanduser().resolve() if dest else self.path
        with self._lock:
            rows = [
                {"key_hash": kh, "key": self._keys[kh],
                 "response": self._rows[kh].to_row(), "written_at_utc": utc_now()}
                for kh in sorted(self._rows)
            ]
            write_jsonl_atomic(target, rows)
        return target

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"rows": len(self._rows), "hits": self.hits,
                    "misses": self.misses, "writes": self.writes}

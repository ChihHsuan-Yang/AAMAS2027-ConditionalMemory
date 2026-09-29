"""Embedding client for Salesforce/SFR-Embedding-Mistral on Sophia.

Verified serving configuration (measured, not assumed):
  cluster           sophia
  framework path    /resource_server/sophia/vllm/v1/embeddings
  model             Salesforce/SFR-Embedding-Mistral
  dimension         4096
  determinism       cosine == 1.0 on identical text

``google/embeddinggemma-300m`` is advertised on Sophia and returns 502. Do not
use it without re-probing.

THE BUG THIS MODULE FIXES
-------------------------
The idiom here is lifted from
``code/emnlp_routing/scripts/train_embedding_router.py``, which guards a cached
embedding matrix like this::

    cached_ids = json.loads(ids_path.read_text())
    if cached_ids != df["problem_id"].tolist():
        raise RuntimeError("Cached embedding IDs do not match benchmark order")

That guard checks only the *identity and order of the rows*. It does not record
the embedding model. Re-running with a different ``--model_name`` finds the
same ids in the same order, passes the check, and silently returns vectors from
the PREVIOUS model -- a drift that produces plausible numbers and is invisible
downstream.

Here the model id is part of the cache key itself (``sha256(text) +
embedding_model_id``), so vectors from two models cannot collide. The
per-file guard is also kept and strengthened: a cache file records the model
id and dimension in a header row, and loading a file whose header disagrees
with the configured model RAISES.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence

from .client import GATEWAY, EndpointError, TokenProvider
from .vendor.rcc_schema import sha256_text, utc_now

EMBED_CLUSTER = "sophia"
EMBED_FRAMEWORK = "vllm"
EMBED_MODEL = "Salesforce/SFR-Embedding-Mistral"
EMBED_DIM = 4096
CACHE_HEADER_KIND = "p1mem_embedding_cache_header_v1"


class EmbeddingModelMismatchError(RuntimeError):
    """A cache file was produced by a different embedding model."""


def embedding_key(text: str, model_id: str) -> str:
    """sha256(text) + embedding model id -- the id is IN the key, not beside it."""
    return sha256_text({"text": text, "embedding_model_id": model_id})


class EmbeddingClient:
    """Batched, persistently cached embedding client."""

    def __init__(self, *, cache_path: str | Path,
                 model: str = EMBED_MODEL, cluster: str = EMBED_CLUSTER,
                 framework: str = EMBED_FRAMEWORK, expected_dim: int | None = EMBED_DIM,
                 token_provider: TokenProvider | None = None,
                 batch_size: int = 16, timeout_s: float = 300.0,
                 max_retries: int = 5):
        self.model = model
        self.cluster = cluster
        self.framework = framework
        self.expected_dim = expected_dim
        self.cache_path = Path(cache_path).expanduser().resolve()
        self.tokens = token_provider or TokenProvider()
        self.batch_size = batch_size
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._vectors: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.api_calls = 0
        self._load()

    @property
    def url(self) -> str:
        return f"{GATEWAY}/{self.cluster}/{self.framework}/v1/embeddings"

    # -------------------------------------------------------------- cache
    def _load(self) -> None:
        if not self.cache_path.exists():
            return
        with open(self.cache_path) as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)   # strict: malformed lines raise
                if row.get("kind") == CACHE_HEADER_KIND:
                    # The header guard the original lacked entirely.
                    if row.get("embedding_model_id") != self.model:
                        raise EmbeddingModelMismatchError(
                            f"{self.cache_path} was written with embedding model "
                            f"{row.get('embedding_model_id')!r} but this client is "
                            f"configured for {self.model!r}. Refusing to mix vector "
                            f"spaces -- use a separate cache file per model."
                        )
                    if (self.expected_dim is not None
                            and row.get("dim") not in (None, self.expected_dim)):
                        raise EmbeddingModelMismatchError(
                            f"{self.cache_path} header dim {row.get('dim')} != "
                            f"expected {self.expected_dim}")
                    continue
                key, vec = row.get("key"), row.get("vector")
                if not key or not isinstance(vec, list):
                    raise ValueError(
                        f"Malformed embedding cache row at {self.cache_path}:{lineno}")
                # Defence in depth: the key must be reproducible from the stored
                # model id, so a row copied between files cannot masquerade.
                if row.get("embedding_model_id") != self.model:
                    raise EmbeddingModelMismatchError(
                        f"row {lineno} of {self.cache_path} carries embedding model "
                        f"{row.get('embedding_model_id')!r}, expected {self.model!r}")
                self._vectors[key] = vec

    def _ensure_header(self) -> None:
        if self.cache_path.exists() and self.cache_path.stat().st_size > 0:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "a") as fh:
            fh.write(json.dumps({
                "kind": CACHE_HEADER_KIND,
                "embedding_model_id": self.model,
                "cluster": self.cluster,
                "dim": self.expected_dim,
                "created_at_utc": utc_now(),
            }, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _append(self, rows: list[dict[str, Any]]) -> None:
        with open(self.cache_path, "a") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ----------------------------------------------------------- transport
    def _post_batch(self, texts: Sequence[str]) -> list[list[float]]:
        body = {"model": self.model, "input": list(texts)}
        last = ""
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                self.url, data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {self.tokens.get()}",
                         "Content-Type": "application/json"},
                method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    payload = json.loads(r.read().decode())
                self.api_calls += 1
                resolved = payload.get("model")
                if resolved and resolved != self.model:
                    raise EmbeddingModelMismatchError(
                        f"requested embedding model {self.model!r}, server resolved "
                        f"{resolved!r}")
                data = sorted(payload.get("data") or [], key=lambda d: d.get("index", 0))
                vecs = [d["embedding"] for d in data]
                if len(vecs) != len(texts):
                    raise EndpointError(
                        f"embedding count {len(vecs)} != input count {len(texts)}")
                if self.expected_dim is not None:
                    for v in vecs:
                        if len(v) != self.expected_dim:
                            raise EndpointError(
                                f"embedding dim {len(v)} != expected {self.expected_dim}")
                return vecs
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read().decode()[:300]}"
                if e.code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise EndpointError(f"embeddings {last}") from e
                if e.code == 401:
                    self.tokens.invalidate()
            except (EmbeddingModelMismatchError, EndpointError):
                raise
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            if attempt == self.max_retries:
                raise EndpointError(f"embeddings failed after {attempt + 1} attempts: {last}")
            time.sleep(min(2 ** attempt, 30) * 0.5)
        raise EndpointError("unreachable")

    # -------------------------------------------------------------- public
    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        """Return one vector per input text, in input order. Cached by
        sha256(text) + embedding model id."""
        texts = list(texts)
        keys = [embedding_key(t, self.model) for t in texts]

        with self._lock:
            need = [(i, t, k) for i, (t, k) in enumerate(zip(texts, keys))
                    if k not in self._vectors]
            self.hits += len(texts) - len(need)
            self.misses += len(need)

        # De-duplicate within the request: the same text twice is one call.
        unique: dict[str, str] = {}
        for _, t, k in need:
            unique.setdefault(k, t)

        if unique:
            self._ensure_header()
            items = list(unique.items())
            for start in range(0, len(items), self.batch_size):
                chunk = items[start:start + self.batch_size]
                vecs = self._post_batch([t for _, t in chunk])
                rows = []
                with self._lock:
                    for (k, _t), v in zip(chunk, vecs):
                        self._vectors[k] = v
                        rows.append({"key": k, "vector": v,
                                     "embedding_model_id": self.model,
                                     "cluster": self.cluster,
                                     "dim": len(v),
                                     "stored_at_utc": utc_now()})
                    self._append(rows)

        with self._lock:
            return [self._vectors[k] for k in keys]

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"rows": len(self._vectors), "hits": self.hits,
                    "misses": self.misses, "api_calls": self.api_calls}

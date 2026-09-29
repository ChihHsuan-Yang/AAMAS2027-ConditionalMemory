"""OpenAI-compatible chat client for the ALCF inference gateway.

Scope: one cluster, one pinned model, per call. This client deliberately does
NOT abstract over clusters. ``P1Client(cluster="metis", model="gpt-oss-120b")``
and ``P1Client(cluster="sophia", model="openai/gpt-oss-120b")`` are two
different experimental arms and are never interchangeable.

Hard errors (raise, never warn, never return a scored response)
---------------------------------------------------------------
1. ``finish_reason == "length"`` with empty/blank ``content`` -> ``TruncatedResponseError``.
   These are reasoning models; reasoning tokens come out of the same
   ``max_tokens`` budget as the answer, so an under-budgeted call returns
   ``content: null`` while the model has in fact reasoned its way to the
   answer. Scoring that as a wrong answer would not merely lose a cell: it
   would push the measured utility delta negative and MANUFACTURE a harmful
   memory -- fabricating the exact phenomenon this project exists to measure.
2. Resolved model id != pinned model id -> ``ModelIdMismatchError``.
3. Model names are NEVER normalised across clusters. A silent rename would
   merge two arms into one.

Token handling: the Globus access token is re-fetched when it ages past
``token_refresh_s`` so a multi-hour run does not die at expiry. The token is
never logged, never stored in a record, and never included in an exception
message.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import CachedResponse, ResponseCache, make_key

GATEWAY = "https://inference-api.alcf.anl.gov/resource_server"
AUTH_DIR = Path("/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication")

# Framework path segment per cluster. Sophia serves via vLLM; Metis/Minerva via
# their "api" framework. Verified against /resource_server/list-endpoints.
CLUSTER_FRAMEWORK = {
    "sophia": "vllm",
    "metis": "api",
    "minerva": "api",
}

# Retryable HTTP codes. 503 is included because it is transient on a busy
# gateway -- but note a PERSISTENTLY 503 model (Minerva gpt-oss-120b) is a
# configuration error, which is why max_retries is finite and the final
# failure raises rather than returning an empty result.
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class ClientError(RuntimeError):
    """Base for client errors."""


class TruncatedResponseError(ClientError):
    """finish_reason == 'length' and content is empty. NOT a model answer."""


class ModelIdMismatchError(ClientError):
    """Server resolved a different model than the one pinned."""


class EndpointError(ClientError):
    """Non-retryable, or retries exhausted."""


@dataclass
class CallRecord:
    """Per-call accounting. One of these exists for every call we make."""

    cluster: str
    requested_model: str
    resolved_model: str = ""
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None
    retry_count: int = 0
    error_code: str | None = None
    finish_reason: str = ""
    cache_hit: bool = False
    http_status: int | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster": self.cluster,
            "requested_model": self.requested_model,
            "resolved_model": self.resolved_model,
            "latency_s": round(self.latency_s, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "retry_count": self.retry_count,
            "error_code": self.error_code,
            "finish_reason": self.finish_reason,
            "cache_hit": self.cache_hit,
            "http_status": self.http_status,
            "attempts": self.attempts,
        }


class TokenProvider:
    """Fetches and refreshes the Globus access token.

    Thread-safe. The token value is returned to callers for use in a header and
    is never logged or persisted by this module.
    """

    def __init__(self, refresh_s: float = 1800.0, auth_dir: Path = AUTH_DIR):
        self.refresh_s = refresh_s
        self.auth_dir = Path(auth_dir)
        self._token: str | None = None
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> str:
        proc = subprocess.run(
            [sys.executable, "inference_auth_token.py", "get_access_token"],
            cwd=str(self.auth_dir), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            # stderr is preserved: suppressing it would turn a missing
            # interpreter or a revoked refresh token into an indistinguishable
            # blank failure.
            raise EndpointError(
                f"token fetch failed (rc={proc.returncode}): {proc.stderr.strip()[:400]}"
            )
        token = proc.stdout.strip()
        if not token:
            raise EndpointError("token fetch returned empty output")
        return token

    def get(self, *, force: bool = False) -> str:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            if force or self._token is None or age > self.refresh_s:
                self._token = self._fetch()
                self._fetched_at = time.monotonic()
            return self._token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None


class P1Client:
    """Chat client pinned to one cluster + one model.

    ``model`` is sent verbatim and the resolved id must come back equal to it.
    """

    def __init__(self, *, cluster: str, model: str,
                 cache: ResponseCache | None = None,
                 token_provider: TokenProvider | None = None,
                 max_retries: int = 5, base_backoff_s: float = 1.0,
                 max_backoff_s: float = 60.0, timeout_s: float = 300.0,
                 max_concurrency: int = 16):
        if cluster not in CLUSTER_FRAMEWORK:
            raise ValueError(
                f"unknown cluster {cluster!r}; known: {sorted(CLUSTER_FRAMEWORK)}"
            )
        self.cluster = cluster
        self.model = model
        self.cache = cache
        self.tokens = token_provider or TokenProvider()
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s
        self.timeout_s = timeout_s
        # Advisory: the measured safe ceiling is 16 on Metis
        # (docs/ENDPOINT_THROUGHPUT.md). The semaphore makes the limit BIND
        # here rather than merely being recorded in a config field.
        self._sem = threading.Semaphore(max_concurrency)
        self.max_concurrency = max_concurrency

    @property
    def url(self) -> str:
        return f"{GATEWAY}/{self.cluster}/{CLUSTER_FRAMEWORK[self.cluster]}/v1/chat/completions"

    # ----------------------------------------------------------- transport
    def _post_once(self, body: dict[str, Any]) -> tuple[int, dict[str, Any] | None, str, str | None]:
        """One HTTP attempt. Returns (status, payload, error_text, retry_after)."""
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.tokens.get()}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return r.status, json.loads(r.read().decode()), "", None
        except urllib.error.HTTPError as e:
            return e.code, None, e.read().decode()[:600], e.headers.get("Retry-After")
        except Exception as e:  # noqa: BLE001
            return 0, None, f"{type(e).__name__}: {e}", None

    def _sleep_for(self, attempt: int, retry_after: str | None) -> float:
        """Honour Retry-After when present; otherwise jittered exponential.

        Measured note: Metis 429s carried NO Retry-After header, so the
        computed path is the one that actually runs in practice.
        """
        if retry_after:
            try:
                return min(float(retry_after), self.max_backoff_s)
            except ValueError:
                pass
        window = min(self.base_backoff_s * (2 ** attempt), self.max_backoff_s)
        return random.uniform(0.0, window)      # full jitter

    # -------------------------------------------------------------- public
    def chat(self, messages: list[dict[str, str]], *,
             max_tokens: int = 512, temperature: float = 0.0,
             reasoning_effort: str | None = "low",
             cache_key_fields: dict[str, Any] | None = None,
             extra_body: dict[str, Any] | None = None,
             ) -> tuple[str, CallRecord]:
        """Send one chat completion. Returns (content, CallRecord).

        If ``cache_key_fields`` is given it must contain every non-derivable
        cache key field; ``model_id``, ``cluster`` and ``decoding_params`` are
        filled from this client so they cannot disagree with what is sent.
        """
        decoding = {"temperature": temperature, "max_tokens": max_tokens}
        if reasoning_effort is not None:
            decoding["reasoning_effort"] = reasoning_effort
        if extra_body:
            decoding.update(extra_body)

        key = None
        if self.cache is not None and cache_key_fields is not None:
            key = make_key(**{**cache_key_fields,
                              "model_id": self.model,
                              "cluster": self.cluster,
                              "decoding_params": decoding})
            hit = self.cache.lookup(key)
            if hit is not None:
                rec = CallRecord(
                    cluster=self.cluster, requested_model=self.model,
                    resolved_model=hit.resolved_model, latency_s=hit.latency_s,
                    input_tokens=hit.prompt_tokens, output_tokens=hit.completion_tokens,
                    reasoning_tokens=hit.reasoning_tokens, retry_count=hit.retry_count,
                    finish_reason=hit.finish_reason, cache_hit=True, http_status=200)
                # A cached row must still satisfy the pin. A cache written
                # under a different model is a contradiction, not a shortcut.
                self._assert_model(hit.resolved_model)
                return hit.content, rec

        body: dict[str, Any] = {"model": self.model, "messages": messages,
                                "max_tokens": max_tokens, "temperature": temperature}
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort
        if extra_body:
            body.update(extra_body)

        rec = CallRecord(cluster=self.cluster, requested_model=self.model)
        t0 = time.monotonic()
        payload: dict[str, Any] | None = None

        with self._sem:
            for attempt in range(self.max_retries + 1):
                status, payload, err, retry_after = self._post_once(body)
                rec.attempts.append({"attempt": attempt, "status": status,
                                     "error": err[:200] if err else ""})
                rec.http_status = status
                if status == 200 and payload is not None:
                    break
                rec.error_code = str(status) if status else "transport_error"
                if status == 401:
                    # Token may have expired mid-run: refresh once and retry.
                    self.tokens.invalidate()
                if status not in RETRYABLE_STATUS and status != 0 and status != 401:
                    raise EndpointError(
                        f"{self.cluster}/{self.model} HTTP {status} (non-retryable): {err[:300]}")
                if attempt == self.max_retries:
                    raise EndpointError(
                        f"{self.cluster}/{self.model} failed after {attempt + 1} attempts; "
                        f"last status {status}: {err[:300]}")
                rec.retry_count += 1
                time.sleep(self._sleep_for(attempt, retry_after))

        rec.latency_s = time.monotonic() - t0
        assert payload is not None

        resolved = payload.get("model") or ""
        self._assert_model(resolved)
        rec.resolved_model = resolved

        usage = payload.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        rec.input_tokens = int(usage.get("prompt_tokens") or 0)
        rec.output_tokens = int(usage.get("completion_tokens") or 0)
        rec.reasoning_tokens = details.get("reasoning_tokens")

        choice = (payload.get("choices") or [{}])[0]
        rec.finish_reason = choice.get("finish_reason") or ""
        content = (choice.get("message") or {}).get("content") or ""

        if rec.finish_reason == "length" and not content.strip():
            rec.error_code = "truncated_no_content"
            raise TruncatedResponseError(
                f"{self.cluster}/{self.model}: finish_reason='length' with empty content. "
                f"max_tokens={max_tokens} was consumed by reasoning "
                f"(reasoning_tokens={rec.reasoning_tokens}, completion_tokens={rec.output_tokens}). "
                f"This is NOT a model answer -- scoring it would manufacture a false "
                f"utility delta. Raise max_tokens or lower reasoning_effort."
            )

        if key is not None and self.cache is not None:
            self.cache.store(key, CachedResponse(
                content=content, resolved_model=resolved, cluster=self.cluster,
                prompt_tokens=rec.input_tokens, completion_tokens=rec.output_tokens,
                reasoning_tokens=rec.reasoning_tokens, finish_reason=rec.finish_reason,
                latency_s=rec.latency_s, retry_count=rec.retry_count,
                error_code=rec.error_code, raw_usage=usage))
        return content, rec

    def _assert_model(self, resolved: str) -> None:
        """Exact match. No normalisation, no stripping of a vendor prefix.

        'gpt-oss-120b' and 'openai/gpt-oss-120b' are DIFFERENT arms here.
        """
        if resolved != self.model:
            raise ModelIdMismatchError(
                f"pinned model {self.model!r} on cluster {self.cluster!r} but server "
                f"resolved {resolved!r}. Aborting: a silent substitution would mix arms."
            )

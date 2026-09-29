"""Tests for the pinned chat client and the embedding client.

These use a fake transport, so they run offline and deterministically. The
point is the guard behaviour, not the network.
"""
from __future__ import annotations

import json

import pytest

from p1mem.cache import ResponseCache, make_key
from p1mem.client import (
    CLUSTER_FRAMEWORK,
    ModelIdMismatchError,
    P1Client,
    TruncatedResponseError,
)
from p1mem.embed import (
    EmbeddingClient,
    EmbeddingModelMismatchError,
    embedding_key,
)


class FakeTokens:
    def __init__(self):
        self.fetches = 0

    def get(self, *, force: bool = False) -> str:
        self.fetches += 1
        return "fake-token-never-real"

    def invalidate(self) -> None:
        pass


def ok_payload(model="gpt-oss-120b", content="the answer", finish="stop",
               ptok=4287, ctok=251, rtok=40):
    return {
        "model": model,
        "choices": [{"finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": ptok, "completion_tokens": ctok,
                  "completion_tokens_details": {"reasoning_tokens": rtok}},
    }


def client(tmp_path, *, cluster="metis", model="gpt-oss-120b", cache=True, **kw):
    c = P1Client(cluster=cluster, model=model,
                 cache=ResponseCache(tmp_path / "c.jsonl") if cache else None,
                 token_provider=FakeTokens(), **kw)
    return c


CK = dict(benchmark="longmemeval", source_item_id="i1", memory_repr="summary_v2",
          memory_id="m1", future_task_id="t1", arm="with_memory",
          retrieval_method="oracle", prompt_version="v3", replicate_id=0)


# --------------------------------------------------- mandated hard errors
def test_truncated_response_raises(tmp_path, monkeypatch):
    """finish_reason='length' + empty content must RAISE, not return.

    Scoring this as an answer would manufacture a false negative utility
    delta -- fabricating the phenomenon the project measures.
    """
    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", lambda body: (
        200, ok_payload(content=None, finish="length", ctok=512, rtok=512), "", None))
    with pytest.raises(TruncatedResponseError, match="finish_reason='length'"):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)


def test_truncated_whitespace_only_also_raises(tmp_path, monkeypatch):
    """Empty means empty after stripping -- ' \\n ' is not an answer either."""
    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", lambda body: (
        200, ok_payload(content="  \n ", finish="length"), "", None))
    with pytest.raises(TruncatedResponseError):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)


def test_length_finish_WITH_content_is_allowed(tmp_path, monkeypatch):
    """A long but complete-enough answer is not the failure we are guarding."""
    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", lambda body: (
        200, ok_payload(content="a real if truncated answer", finish="length"), "", None))
    content, rec = c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    assert content == "a real if truncated answer"
    assert rec.finish_reason == "length"


def test_model_mismatch_raises(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", lambda body: (
        200, ok_payload(model="gpt-oss-20b"), "", None))
    with pytest.raises(ModelIdMismatchError, match="gpt-oss-20b"):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)


def test_vendor_prefix_is_NOT_normalised(tmp_path, monkeypatch):
    """'gpt-oss-120b' vs 'openai/gpt-oss-120b' are different arms.

    A client that stripped the prefix to be helpful would merge Metis and
    Sophia results into one pool.
    """
    c = client(tmp_path, cluster="metis", model="gpt-oss-120b")
    monkeypatch.setattr(c, "_post_once", lambda body: (
        200, ok_payload(model="openai/gpt-oss-120b"), "", None))
    with pytest.raises(ModelIdMismatchError):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)


# -------------------------------------------------------------- accounting
def test_call_record_accounting(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", lambda body: (200, ok_payload(), "", None))
    _, rec = c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    assert rec.input_tokens == 4287 and rec.output_tokens == 251
    assert rec.reasoning_tokens == 40 and rec.retry_count == 0
    assert rec.resolved_model == "gpt-oss-120b" and rec.cluster == "metis"
    assert rec.error_code is None and rec.cache_hit is False
    assert rec.latency_s >= 0.0
    assert "cluster" in rec.to_dict()


def test_retry_then_success_records_retry_count(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        if calls["n"] <= 2:
            return 429, None, '{"detail": "Too many requests."}', None
        return 200, ok_payload(), "", None

    c = client(tmp_path, base_backoff_s=0.001, max_backoff_s=0.002)
    monkeypatch.setattr(c, "_post_once", flaky)
    _, rec = c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    assert rec.retry_count == 2 and calls["n"] == 3
    assert rec.attempts[0]["status"] == 429


def test_retry_after_header_is_honoured(tmp_path):
    c = client(tmp_path, base_backoff_s=100.0, max_backoff_s=1000.0)
    # Retry-After wins over the (much larger) computed backoff.
    assert c._sleep_for(5, "2") == 2.0
    # Absent header -> jittered exponential, bounded by max_backoff_s.
    assert 0.0 <= c._sleep_for(0, None) <= 100.0
    assert c._sleep_for(99, None) <= 1000.0
    # Junk header falls back to the computed path rather than crashing.
    assert 0.0 <= c._sleep_for(0, "not-a-number") <= 100.0


def test_non_retryable_status_raises_immediately(tmp_path, monkeypatch):
    calls = {"n": 0}

    def bad(body):
        calls["n"] += 1
        return 400, None, '{"error": "bad request"}', None

    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", bad)
    with pytest.raises(Exception, match="non-retryable"):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    assert calls["n"] == 1, "a 400 must not be retried"


def test_retries_exhausted_raises(tmp_path, monkeypatch):
    c = client(tmp_path, max_retries=2, base_backoff_s=0.001, max_backoff_s=0.002)
    monkeypatch.setattr(c, "_post_once", lambda body: (
        503, None, "'gpt-oss-120b' is not currently live", None))
    with pytest.raises(Exception, match="after 3 attempts"):
        c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)


# ------------------------------------------------------- cache integration
def test_second_identical_call_is_served_from_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    def once(body):
        calls["n"] += 1
        return 200, ok_payload(), "", None

    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", once)
    a, ra = c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    b, rb = c.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)
    assert a == b and calls["n"] == 1
    assert ra.cache_hit is False and rb.cache_hit is True


def test_cache_does_not_cross_clusters_through_the_client(tmp_path, monkeypatch):
    """End-to-end version of the mandated cross-cluster test."""
    shared = ResponseCache(tmp_path / "shared.jsonl")
    metis = P1Client(cluster="metis", model="gpt-oss-120b", cache=shared,
                     token_provider=FakeTokens())
    sophia = P1Client(cluster="sophia", model="openai/gpt-oss-120b", cache=shared,
                      token_provider=FakeTokens())
    monkeypatch.setattr(metis, "_post_once", lambda b: (
        200, ok_payload(model="gpt-oss-120b", content="metis says"), "", None))
    calls = {"n": 0}

    def sophia_post(b):
        calls["n"] += 1
        return 200, ok_payload(model="openai/gpt-oss-120b", content="sophia says"), "", None

    monkeypatch.setattr(sophia, "_post_once", sophia_post)

    assert metis.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)[0] == "metis says"
    # Same prompt, same key fields -- must NOT be served the Metis row.
    assert sophia.chat([{"role": "user", "content": "hi"}], cache_key_fields=CK)[0] == "sophia says"
    assert calls["n"] == 1, "Sophia call was served from the Metis cache entry"
    assert shared.stats()["rows"] == 2


def test_decoding_params_change_the_cached_entry(tmp_path, monkeypatch):
    calls = {"n": 0}

    def post(b):
        calls["n"] += 1
        return 200, ok_payload(), "", None

    c = client(tmp_path)
    monkeypatch.setattr(c, "_post_once", post)
    c.chat([{"role": "user", "content": "hi"}], max_tokens=512, cache_key_fields=CK)
    c.chat([{"role": "user", "content": "hi"}], max_tokens=1024, cache_key_fields=CK)
    assert calls["n"] == 2, "max_tokens must not be collapsed in the cache key"


def test_unknown_cluster_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown cluster"):
        P1Client(cluster="tara", model="x", token_provider=FakeTokens())
    assert set(CLUSTER_FRAMEWORK) == {"sophia", "metis", "minerva"}


def test_url_uses_the_right_framework_segment():
    assert P1Client(cluster="metis", model="m", token_provider=FakeTokens()).url.endswith(
        "/resource_server/metis/api/v1/chat/completions")
    assert P1Client(cluster="sophia", model="m", token_provider=FakeTokens()).url.endswith(
        "/resource_server/sophia/vllm/v1/chat/completions")


# ------------------------------------------------------- embedding client
def test_embedding_key_includes_the_model_id():
    """THE BUG FIX: the same text under two models must not share a key.

    The upstream train_embedding_router.py guard compares only problem ids and
    would happily reuse the other model's vectors.
    """
    a = embedding_key("hello", "Salesforce/SFR-Embedding-Mistral")
    b = embedding_key("hello", "google/embeddinggemma-300m")
    assert a != b
    assert embedding_key("hello", "m") == embedding_key("hello", "m")
    assert embedding_key("hello", "m") != embedding_key("hello!", "m")


def test_embedding_cache_rejects_a_different_model(tmp_path):
    path = tmp_path / "emb.jsonl"
    e = EmbeddingClient(cache_path=path, model="model-A", expected_dim=3,
                        token_provider=FakeTokens())
    e._ensure_header()
    e._append([{"key": embedding_key("t", "model-A"), "vector": [1.0, 2.0, 3.0],
                "embedding_model_id": "model-A", "cluster": "sophia", "dim": 3}])
    # Same file, different model -> must refuse rather than silently reuse.
    with pytest.raises(EmbeddingModelMismatchError, match="model-A"):
        EmbeddingClient(cache_path=path, model="model-B", expected_dim=3,
                        token_provider=FakeTokens())
    # Same model reloads fine.
    again = EmbeddingClient(cache_path=path, model="model-A", expected_dim=3,
                            token_provider=FakeTokens())
    assert again.stats()["rows"] == 1


def test_embedding_batching_dedups_and_caches(tmp_path, monkeypatch):
    path = tmp_path / "emb.jsonl"
    e = EmbeddingClient(cache_path=path, model="model-A", expected_dim=3,
                        batch_size=2, token_provider=FakeTokens())
    seen = []

    def fake_post(texts):
        seen.append(list(texts))
        return [[float(len(t)), 0.0, 0.0] for t in texts]

    monkeypatch.setattr(e, "_post_batch", fake_post)

    out = e.embed(["aa", "bbb", "aa", "cccc"])
    assert len(out) == 4
    assert out[0] == out[2] == [2.0, 0.0, 0.0]
    # "aa" appears twice but is embedded once.
    assert sorted(t for batch in seen for t in batch) == ["aa", "bbb", "cccc"]
    assert max(len(b) for b in seen) <= 2, "batch_size not honoured"

    # Second call is fully cached: no further API calls.
    seen.clear()
    again = e.embed(["aa", "bbb"])
    assert seen == [] and again[0] == [2.0, 0.0, 0.0]

    # And it survives a reload.
    reloaded = EmbeddingClient(cache_path=path, model="model-A", expected_dim=3,
                               token_provider=FakeTokens())
    assert reloaded.stats()["rows"] == 3


def test_embedding_dimension_is_checked(tmp_path, monkeypatch):
    e = EmbeddingClient(cache_path=tmp_path / "e.jsonl", model="m", expected_dim=4096,
                        token_provider=FakeTokens())
    monkeypatch.setattr(e, "_post_batch", lambda texts: [[0.0] * 5 for _ in texts])
    # _post_batch is faked here, so check the real guard directly instead.
    e2 = EmbeddingClient(cache_path=tmp_path / "e2.jsonl", model="m", expected_dim=4096,
                         token_provider=FakeTokens())

    class R:
        status = 200

        def read(self):
            return json.dumps({"model": "m",
                               "data": [{"index": 0, "embedding": [0.0] * 5}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: R())
    with pytest.raises(Exception, match="dim"):
        e2._post_batch(["x"])

"""Tests for the P1 response cache.

The two mandated tests are ``test_cluster_changes_the_key`` (a hit must never
cross a cluster boundary) and ``test_identical_call_hits``. The rest exist
because a cache that has only been tried on the case it was written for is not
known to discriminate anything: several tests below deliberately try to MAKE
the cache collide, and assert that it refuses.
"""
from __future__ import annotations

import json

import pytest

from p1mem.cache import (
    KEY_FIELDS,
    CachedResponse,
    CacheKeyError,
    ResponseCache,
    key_hash,
    make_key,
)

BASE = dict(
    benchmark="longmemeval",
    source_item_id="item_0042",
    memory_repr="summary_v2",
    memory_id="mem_7f3a",
    future_task_id="task_19",
    arm="with_memory",
    retrieval_method="sfr_embedding_top5",
    model_id="gpt-oss-120b",
    cluster="metis",
    prompt_version="p1_reader_v3",
    decoding_params={"temperature": 0.0, "max_tokens": 512, "reasoning_effort": "low"},
    replicate_id=0,
    # Derived by P1Client from the messages actually sent. Present here so the
    # suite exercises the same key shape production uses.
    context_sha256="c" * 64,
)


def resp(content: str = "hello", cluster: str = "metis") -> CachedResponse:
    return CachedResponse(content=content, resolved_model="gpt-oss-120b",
                          cluster=cluster, prompt_tokens=4287,
                          completion_tokens=251, finish_reason="stop",
                          latency_s=1.23)


# ------------------------------------------------- the two mandated tests
def test_cluster_changes_the_key(tmp_path):
    """MANDATED: two clusters, everything else identical -> DIFFERENT keys.

    This is the failure that would silently merge the Metis primary arm with
    the Sophia failover arm.
    """
    metis = make_key(**{**BASE, "cluster": "metis"})
    sophia = make_key(**{**BASE, "cluster": "sophia"})

    assert key_hash(metis) != key_hash(sophia), (
        "cluster is not discriminating the key -- a Sophia response could be "
        "served from a Metis cache entry"
    )

    # And prove it behaviourally, not just by hashing: store one, miss the other.
    cache = ResponseCache(tmp_path / "c.jsonl")
    cache.store(metis, resp(content="metis answer", cluster="metis"))

    assert cache.lookup(metis) is not None
    assert cache.lookup(sophia) is None, (
        "a Sophia lookup HIT a Metis-written row -- cross-cluster contamination"
    )

    # Storing the Sophia arm must add a row, not overwrite the Metis one.
    cache.store(sophia, resp(content="sophia answer", cluster="sophia"))
    assert cache.lookup(metis).content == "metis answer"
    assert cache.lookup(sophia).content == "sophia answer"
    assert cache.stats()["rows"] == 2


def test_identical_call_hits(tmp_path):
    """MANDATED: an identical call hits the cache."""
    cache = ResponseCache(tmp_path / "c.jsonl")
    key = make_key(**BASE)
    assert cache.lookup(key) is None

    cache.store(key, resp(content="the answer"))

    # Same key object.
    hit = cache.lookup(make_key(**BASE))
    assert hit is not None and hit.content == "the answer"

    # Key built with the fields in a DIFFERENT order, and decoding_params in a
    # different order -- still the same call, so still a hit.
    shuffled = {k: BASE[k] for k in reversed(list(BASE))}
    shuffled["decoding_params"] = {"reasoning_effort": "low", "max_tokens": 512,
                                   "temperature": 0.0}
    assert cache.lookup(make_key(**shuffled)) is not None

    # And it survives a reload from disk.
    reloaded = ResponseCache(tmp_path / "c.jsonl")
    assert reloaded.lookup(make_key(**BASE)).content == "the answer"
    assert reloaded.stats()["rows"] == 1


# ------------------------------------- every key field must discriminate
@pytest.mark.parametrize("fieldname,newvalue", [
    ("benchmark", "locomo"),
    ("source_item_id", "item_0043"),
    ("memory_repr", "raw_trace"),
    ("memory_id", "mem_0000"),
    ("future_task_id", "task_20"),
    ("arm", "without_memory"),
    ("retrieval_method", "bm25"),
    ("model_id", "openai/gpt-oss-120b"),
    ("cluster", "sophia"),
    ("prompt_version", "p1_reader_v4"),
    ("replicate_id", 1),
])
def test_each_field_changes_the_key(fieldname, newvalue):
    """Change exactly one field; the key must change.

    Run over EVERY key field, not just the interesting ones -- a field that is
    accepted but not hashed is invisible until it corrupts a result.
    """
    a = make_key(**BASE)
    b = make_key(**{**BASE, fieldname: newvalue})
    assert key_hash(a) != key_hash(b), f"{fieldname} does not affect the cache key"


@pytest.mark.parametrize("newparams", [
    {"temperature": 0.7, "max_tokens": 512, "reasoning_effort": "low"},
    {"temperature": 0.0, "max_tokens": 1024, "reasoning_effort": "low"},
    {"temperature": 0.0, "max_tokens": 512, "reasoning_effort": "high"},
    {"temperature": 0.0, "max_tokens": 512},
])
def test_decoding_params_change_the_key(newparams):
    assert key_hash(make_key(**BASE)) != key_hash(
        make_key(**{**BASE, "decoding_params": newparams}))


def test_key_fields_list_is_complete():
    """Guard against adding a constructor field and forgetting to hash it."""
    assert set(BASE) == set(KEY_FIELDS)


# ------------------------------------------------------- malformed keys
def test_missing_field_raises():
    incomplete = {k: v for k, v in BASE.items() if k != "cluster"}
    with pytest.raises(CacheKeyError, match="cluster"):
        make_key(**incomplete)


def test_unexpected_field_raises():
    """A typo must not silently produce a key missing the real field."""
    with pytest.raises(CacheKeyError, match="moel_id"):
        make_key(**BASE, moel_id="gpt-oss-120b")


def test_empty_cluster_raises():
    with pytest.raises(CacheKeyError):
        make_key(**{**BASE, "cluster": ""})


def test_non_dict_decoding_params_raises():
    with pytest.raises(CacheKeyError, match="decoding_params"):
        make_key(**{**BASE, "decoding_params": "temperature=0"})


# ------------------------------------------------- corruption detection
def test_malformed_line_raises_not_skipped(tmp_path):
    """strict=True: a corrupt line must RAISE.

    A silent-skip loader turns a damaged cache into a quietly smaller one,
    which is indistinguishable from a cache miss.
    """
    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    cache.store(make_key(**BASE), resp())
    with open(path, "a") as fh:
        fh.write("{not valid json\n")
    with pytest.raises(ValueError, match="Malformed JSON"):
        ResponseCache(path)


def test_tampered_row_is_detected(tmp_path):
    """PROVE THE CHECKER CAN FAIL: corrupt a copy in the shape of the defect
    we actually fear -- a key edited in place so a row answers for the wrong
    condition -- and assert the loader refuses it."""
    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    cache.store(make_key(**BASE), resp(content="metis answer"))

    # Hand-edit the stored key's cluster to "sophia" but leave key_hash alone:
    # exactly what a careless manual merge or a partial rewrite would produce.
    row = json.loads(path.read_text().strip())
    assert row["key"]["cluster"] == "metis"
    row["key"]["cluster"] = "sophia"
    path.write_text(json.dumps(row, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="key_hash"):
        ResponseCache(path)


def test_schema_version_is_in_the_key():
    """A schema bump must invalidate old rows by construction."""
    key = make_key(**BASE)
    assert key["schema_version"]
    bumped = dict(key, schema_version="p1mem_response_cache_v2")
    assert key_hash(key) != key_hash(bumped)


# ------------------------------------------------------- behaviour/IO
def test_store_is_idempotent(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    key = make_key(**BASE)
    cache.store(key, resp(content="first"))
    cache.store(key, resp(content="second"))          # ignored without overwrite
    assert cache.lookup(key).content == "first"
    assert len(path.read_text().strip().splitlines()) == 1


def test_overwrite_appends_and_last_wins(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    key = make_key(**BASE)
    cache.store(key, resp(content="first"))
    cache.store(key, resp(content="second"), overwrite=True)
    assert len(path.read_text().strip().splitlines()) == 2
    assert ResponseCache(path).lookup(key).content == "second"
    # compaction collapses to one row, preserving the winner
    ResponseCache(path).compact()
    assert len(path.read_text().strip().splitlines()) == 1
    assert ResponseCache(path).lookup(key).content == "second"


def test_concurrent_stores_do_not_interleave(tmp_path):
    """16 threads, matching our chosen concurrency. Every line must parse."""
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    n = 160

    def work(i: int) -> None:
        cache.store(make_key(**{**BASE, "future_task_id": f"task_{i}"}),
                    resp(content="x" * 500))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(work, range(n)))

    lines = path.read_text().strip().splitlines()
    assert len(lines) == n
    for line in lines:
        json.loads(line)          # raises if a write interleaved
    assert ResponseCache(path).stats()["rows"] == n


def test_concurrent_stores_of_one_key_write_exactly_one_row(tmp_path):
    """The lock must make check-then-act atomic.

    The previous test uses DISTINCT keys, so it never exercises the
    "is this key already stored?" race -- it passed even with the lock
    removed. Racing many threads on the SAME key is what actually tests it:
    without the lock every thread passes the containment check before any of
    them writes, and the file gets duplicate rows for one key.
    """
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    key = make_key(**BASE)
    barrier = __import__("threading").Barrier(16)

    def work(_i: int) -> None:
        barrier.wait()          # maximise the overlap
        cache.store(key, resp(content="x" * 2000))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(work, range(16)))

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1, (
        f"expected exactly 1 row for one key, got {len(lines)} -- "
        f"store() check-then-act is not atomic"
    )
    assert cache.stats()["writes"] == 1


def test_response_roundtrip_preserves_accounting(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = ResponseCache(path)
    key = make_key(**BASE)
    cache.store(key, CachedResponse(
        content="answer", resolved_model="gpt-oss-120b", cluster="metis",
        prompt_tokens=16832, completion_tokens=251, reasoning_tokens=40,
        finish_reason="stop", latency_s=2.588, retry_count=2,
        error_code=None, raw_usage={"total_tokens": 17083}))
    got = ResponseCache(path).lookup(key)
    assert (got.prompt_tokens, got.completion_tokens, got.reasoning_tokens) == (16832, 251, 40)
    assert got.retry_count == 2 and got.latency_s == 2.588
    assert got.raw_usage["total_tokens"] == 17083


def test_context_hash_separates_runs_that_render_different_filler(tmp_path):
    """The collision this field exists to close, demonstrated then closed.

    The pilot rendered K=6 filler from a 12-trajectory reservation; the
    screened run renders K=4 from a bearing-disjoint 50-trajectory pool. Every
    other key field is identical, so before context_sha256 the screened run
    would have been served the pilot's answer. Only the separate cache FILE
    prevented it -- an argument default, not an invariant.

    Found by Sub-agent K. My own earlier behavioural check could not have
    caught it: it varied only fields that were already in the key.
    """
    c = ResponseCache(tmp_path / "c.jsonl")
    pilot = dict(BASE, context_sha256="a" * 64)
    screened = dict(BASE, context_sha256="b" * 64)
    c.store(pilot, resp("ANSWER UNDER K=6 PILOT CONTEXT"))
    assert c.lookup(screened) is None, "different rendered context must MISS"
    assert c.lookup(dict(pilot)) is not None, "same rendered context must HIT"


def test_total_miss_from_a_key_shape_change_explains_itself(tmp_path):
    """A key-shape change must not present as "the cache is broken".

    Reproduces the real situation: results/deltau_screened/cache.jsonl was
    written under the 12-field v1 shape before context_sha256 was added.
    Read by current code it gives a TOTAL miss, and without a diagnostic
    someone hunts a nonexistent bug or loosens the key to silence it --
    which is exactly what the key exists to prevent.
    """
    import json
    path = tmp_path / "old.jsonl"
    old_key = {k: "x" for k in BASE if k != "context_sha256"}
    old_key["schema_version"] = "p1mem_response_cache_v1"
    path.write_text(json.dumps({
        "key": old_key, "key_hash": key_hash(old_key),
        "response": {"content": "old", "resolved_model": "gpt-oss-120b",
                     "cluster": "metis", "prompt_tokens": 1, "completion_tokens": 1,
                     "finish_reason": "stop", "latency_s": 0.1},
        "written_at_utc": "2026-09-29T00:00:00+00:00"}) + "\n")

    c = ResponseCache(path)
    assert c.stats()["rows"] == 1
    assert c.lookup(dict(BASE)) is None          # total miss
    msg = c.diagnose_total_miss()
    assert msg is not None, "a total miss on a non-empty cache must be explained"
    assert "context_sha256" in msg and "KEY SHAPE" in msg
    assert "Do NOT" in msg                        # says what not to do about it


def test_diagnostic_is_silent_when_the_cache_is_merely_cold(tmp_path):
    """Negative control: an empty cache is not a key-shape problem.

    Without this, a diagnostic that fires on everything would look like it
    works -- the vacuous-guard failure found elsewhere in this project today.
    """
    c = ResponseCache(tmp_path / "empty.jsonl")
    assert c.lookup(dict(BASE)) is None
    assert c.diagnose_total_miss() is None

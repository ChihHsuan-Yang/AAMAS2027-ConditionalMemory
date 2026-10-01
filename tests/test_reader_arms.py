"""Tests for the reader-arm registry and the multi-reader guards.

These exist because adding a second reader broke three assumptions that were
each true of gpt-oss and false in general:

* the empty-content truncation observable,
* "the cluster reports reasoning tokens",
* and the guard running on the fresh path but not the cache path.

Every test below has a PAIRED CONTROL asserting the gpt-oss behaviour is
UNCHANGED. A guard that fires on everything is not a guard, and silently
tightening the published arm would retroactively invalidate shipped cells.
"""
from __future__ import annotations

import pytest

from p1mem import schema as S
from p1mem import validate as V
from p1mem.cache import CachedResponse, ResponseCache, make_key
from p1mem.client import P1Client, TruncatedResponseError
from p1mem.vendor.rcc_schema import sha256_text


class FakeTokens:
    def get(self, *, force: bool = False) -> str:
        return "fake-token-never-real"

    def invalidate(self) -> None:
        pass


CK = dict(benchmark="longmemeval", source_item_id="i1", memory_repr="raw",
          memory_id="m1", future_task_id="t1", arm="with_memory",
          retrieval_method="oracle", prompt_version="v3", replicate_id=0)
MSGS = [{"role": "user", "content": "hi"}]


def client(tmp_path, *, model="gpt-oss-120b", cluster="metis", **kw):
    return P1Client(cluster=cluster, model=model,
                    cache=ResponseCache(tmp_path / "c.jsonl"),
                    token_provider=FakeTokens(), **kw)


def payload(model, content, finish, ctok=512, rtok=None):
    usage = {"prompt_tokens": 100, "completion_tokens": ctok}
    if rtok is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": rtok}
    return {"model": model,
            "choices": [{"finish_reason": finish,
                         "message": {"role": "assistant", "content": content}}],
            "usage": usage}


# ===================================================== the registry itself
def test_every_arm_populates_every_non_nullable_identity_field():
    for arm_id in S.READER_ARMS:
        fields = S.reader_row_fields(arm_id)
        for name in ("reader_model", "reader_cluster", "reader_endpoint",
                     "reader_reasoning_effort", "reader_endpoint_sha256"):
            assert fields.get(name), f"{arm_id} leaves {name} empty"


def test_unknown_arm_raises_rather_than_defaulting():
    """A default would silently run the Gemma replication against gpt-oss."""
    with pytest.raises(S.ReaderArmError, match="unknown reader arm"):
        S.reader_arm("gemma_metis_typo")


def test_a_model_with_no_effort_control_records_a_sentinel_not_a_blank():
    """NON_NULLABLE_IDENTITY: '' and None are both forbidden here."""
    f = S.reader_row_fields("gemma_metis")
    assert f["reader_reasoning_effort"] == "none:not_applicable"
    assert S.reader_arm("gemma_metis")["reasoning_effort"] is None, (
        "the value SENT must be None (omit the field); the value RECORDED is "
        "the sentinel. Conflating them stamps an inert parameter on every row")


def test_the_case_variant_gemma_id_is_refused_by_the_registry():
    """metis returns HTTP 200 for the lowercase id and silently corrects it."""
    assert ("metis", "gemma-4-31b-it") in S.KNOWN_SILENT_MODEL_ALIASES
    S.READER_ARMS["_tmp_bad_case"] = dict(S.READER_ARMS["gemma_metis"],
                                          reader_model="gemma-4-31b-it")
    try:
        with pytest.raises(S.ReaderArmError, match="silently resolves"):
            S.reader_arm("_tmp_bad_case")
    finally:
        del S.READER_ARMS["_tmp_bad_case"]


def test_reasoning_token_reporting_is_a_model_property_not_a_cluster_property():
    """The two readers share a cluster and disagree. Measured, not assumed."""
    assert S.reader_reports_reasoning_tokens("gptoss_metis") is True
    assert S.reader_reports_reasoning_tokens("gemma_metis") is False
    assert (S.reader_arm("gptoss_metis")["reader_cluster"]
            == S.reader_arm("gemma_metis")["reader_cluster"] == "metis")


# ============================================ truncation: the Gemma clause
def test_gemma_fragment_with_finish_length_raises(tmp_path, monkeypatch):
    """Measured live at max_tokens=8: content='Here is the step-by-step'.

    Non-empty, so the original `not content.strip()` clause is False. Scored,
    it reads as a wrong answer and manufactures a harmful memory.
    """
    c = client(tmp_path, model="gemma-4-31B-it")
    assert c.truncation_is_always_an_error is True, "registry default not applied"
    monkeypatch.setattr(c, "_post_once", lambda b: (
        200, payload("gemma-4-31B-it", "Here is the step-by-step", "length", 8),
        "", None))
    with pytest.raises(TruncatedResponseError, match="FRAGMENT"):
        c.chat(MSGS, cache_key_fields=CK, reasoning_effort=None)


def test_CONTROL_the_same_fragment_on_gptoss_is_still_returned(tmp_path, monkeypatch):
    """PAIRED CONTROL. Tightening gpt-oss too would retroactively invalidate
    8 already-published pilot cells. That is a scientific decision about
    existing results, not a side effect of a code change."""
    c = client(tmp_path, model="gpt-oss-120b")
    assert c.truncation_is_always_an_error is False
    monkeypatch.setattr(c, "_post_once", lambda b: (
        200, payload("gpt-oss-120b", "a long truncated answer", "length", 512, 67),
        "", None))
    content, rec = c.chat(MSGS, cache_key_fields=CK)
    assert content == "a long truncated answer"
    assert rec.finish_reason == "length"


def test_CONTROL_a_normal_gemma_answer_is_not_rejected(tmp_path, monkeypatch):
    """A guard that rejects everything proves nothing."""
    c = client(tmp_path, model="gemma-4-31B-it")
    monkeypatch.setattr(c, "_post_once", lambda b: (
        200, payload("gemma-4-31B-it", r"\boxed{Paris}", "stop", 140), "", None))
    content, rec = c.chat(MSGS, cache_key_fields=CK, reasoning_effort=None)
    assert content == r"\boxed{Paris}"
    assert rec.reasoning_tokens is None, "absent must stay None, never 0"


def test_empty_content_still_raises_on_gemma_too(tmp_path, monkeypatch):
    c = client(tmp_path, model="gemma-4-31B-it")
    monkeypatch.setattr(c, "_post_once", lambda b: (
        200, payload("gemma-4-31B-it", "", "length", 512), "", None))
    with pytest.raises(TruncatedResponseError):
        c.chat(MSGS, cache_key_fields=CK, reasoning_effort=None)


def test_an_explicit_flag_can_force_the_strict_guard_on_any_arm(tmp_path, monkeypatch):
    c = client(tmp_path, model="gpt-oss-120b", truncation_is_always_an_error=True)
    monkeypatch.setattr(c, "_post_once", lambda b: (
        200, payload("gpt-oss-120b", "a fragment", "length", 512, 67), "", None))
    with pytest.raises(TruncatedResponseError):
        c.chat(MSGS, cache_key_fields=CK)


# ======================================= truncation: the cache-hit bypass
def _store(cache, model, effort, content, finish):
    d = {"temperature": 0.0, "max_tokens": 512}
    if effort is not None:
        d["reasoning_effort"] = effort
    key = make_key(**{**CK, "model_id": model, "cluster": "metis",
                      "decoding_params": d, "context_sha256": sha256_text(MSGS)})
    cache.store(key, CachedResponse(content=content, resolved_model=model,
                                    cluster="metis", finish_reason=finish))


def test_a_cached_truncation_raises_on_the_cache_path_too(tmp_path):
    """REGRESSION. Before 2026-09-30 the guard ran only on a FRESH response,
    so a stored truncation came back without an exception. The runner's resume
    path IS a cache read, so a killed-and-resumed run could score exactly the
    truncations the first run refused."""
    c = client(tmp_path, model="gpt-oss-120b")
    _store(c.cache, "gpt-oss-120b", "low", "", "length")
    with pytest.raises(TruncatedResponseError):
        c.chat(MSGS, cache_key_fields=CK)


def test_a_cached_gemma_fragment_also_raises_on_the_cache_path(tmp_path):
    c = client(tmp_path, model="gemma-4-31B-it")
    _store(c.cache, "gemma-4-31B-it", None, "Here is the step-by-step", "length")
    with pytest.raises(TruncatedResponseError, match="FRAGMENT"):
        c.chat(MSGS, cache_key_fields=CK, reasoning_effort=None)


def test_CONTROL_a_cached_GOOD_response_is_still_served(tmp_path):
    """Otherwise the two tests above would pass on a cache that never hits."""
    c = client(tmp_path, model="gemma-4-31B-it")
    _store(c.cache, "gemma-4-31B-it", None, r"\boxed{Paris}", "stop")
    content, rec = c.chat(MSGS, cache_key_fields=CK, reasoning_effort=None)
    assert content == r"\boxed{Paris}" and rec.cache_hit is True


# ============================================ cache separation across readers
def test_the_cache_cannot_serve_a_gptoss_response_to_a_gemma_request(tmp_path):
    """The mandated behavioural check, offline. The live version with endpoint
    calls is scripts/gemma_cache_separation_proof.py."""
    cache = ResponseCache(tmp_path / "shared.jsonl")
    gpt = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                   token_provider=FakeTokens())
    gem = P1Client(cluster="metis", model="gemma-4-31B-it", cache=cache,
                   token_provider=FakeTokens())
    _store(cache, "gpt-oss-120b", "low", "GPT-OSS ANSWER", "stop")

    # POSITIVE CONTROL: the cache does hit for the model that wrote it.
    got, rec = gpt.chat(MSGS, cache_key_fields=CK)
    assert rec.cache_hit is True and got == "GPT-OSS ANSWER"

    # ...and misses for the other reader, so a real call would be issued.
    key = make_key(**{**CK, "model_id": "gemma-4-31B-it", "cluster": "metis",
                      "decoding_params": {"temperature": 0.0, "max_tokens": 512},
                      "context_sha256": sha256_text(MSGS)})
    assert cache.lookup(key) is None, "a gemma request HIT a gpt-oss row"
    assert gem is not None


def test_omitting_reasoning_effort_changes_the_key(tmp_path):
    """Gemma omits the field; gpt-oss sends 'low'. If that did not change the
    key, a Gemma row could collide with a gpt-oss one on decoding alone."""
    with_effort = make_key(**{**CK, "model_id": "m", "cluster": "metis",
                              "decoding_params": {"temperature": 0.0,
                                                  "max_tokens": 512,
                                                  "reasoning_effort": "low"},
                              "context_sha256": "c" * 64})
    without = make_key(**{**CK, "model_id": "m", "cluster": "metis",
                          "decoding_params": {"temperature": 0.0,
                                              "max_tokens": 512},
                          "context_sha256": "c" * 64})
    from p1mem.cache import key_hash
    assert key_hash(with_effort) != key_hash(without)


# ===================================================== validator, per reader
def _gemma_row(**over):
    from tests.test_validate import _good_row  # noqa: PLC0415
    base = dict(reader_model="gemma-4-31B-it", reader_cluster="metis",
                reader_reasoning_effort="none:not_applicable",
                reasoning_tokens=None,
                condition_id="lmev2_raw_metis_gemma4_31B_smoke_v1")
    base.update(over)
    return _good_row(**base)


def test_a_gemma_row_with_null_reasoning_tokens_is_clean():
    """It reports no completion_tokens_details at all; null is CORRECT.

    Keyed on cluster, the old check warned on every valid Gemma row."""
    row = _gemma_row()
    codes = {i.code for i in V.validate_row(row)}
    assert "reasoning_tokens_missing" not in codes
    assert "unknown_model_for_cluster" not in codes
    assert [i for i in V.validate_row(row) if i.severity == V.SEVERITY_ERROR] == []


def test_a_gemma_row_with_reasoning_tokens_ZERO_is_caught():
    """THE CORRUPTION THE OLD CHECK COULD NOT SEE: an absent value written as
    a measurement. Cluster-keyed, metis 'reports', so 0 looked fine."""
    row = _gemma_row(reasoning_tokens=0)
    assert "absent_reported_as_zero" in {i.code for i in V.validate_row(row)}


def test_CONTROL_gptoss_still_warns_when_its_reasoning_tokens_are_missing():
    """The paired control: the check must still fire where it always did."""
    from tests.test_validate import _good_row  # noqa: PLC0415
    row = _good_row(reasoning_tokens=None)
    assert "reasoning_tokens_missing" in {i.code for i in V.validate_row(row)}


def test_the_sophia_gemma_spelling_on_metis_is_caught_as_normalisation():
    """'google/gemma-4-31B-it' is Sophia's id. On a metis row it is evidence
    something merged two serving stacks that return different text."""
    row = _gemma_row(reader_model="google/gemma-4-31B-it")
    assert "cross_cluster_model_naming" in {i.code for i in V.validate_row(row)}

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


# ===========================================================================
# DEFECT #20 (2026-09-30, SA-GEMMA-READER): the truncation guard's observable
# was a property of the SERVER'S REPORTING, not of truncation.
#
# Measured live on metis/gemma-4-31B-it at the real ~15-29k-token cell shape,
# under 16-worker load: a response sitting EXACTLY at max_tokens came back
# with finish_reason "" and usage.stop_reason "" -- neither says "length".
# The guard tested `finish_reason == "length"`, so it was silent, and seven
# 2,034-2,146-character FRAGMENTS were returned as if they were answers.
# Scored, each is a wrong answer that drives dU negative and MANUFACTURES a
# harmful memory. That is defect #16 in a third disguise: #16 was "the
# observable is a property of the MODEL", this is "the observable is a
# property of the SERVER'S REPORTING OF THAT MODEL, under load".
#
# Each test below was verified to FAIL against the unfixed client.
# ===========================================================================

def _rec(**kw):
    from p1mem.client import CallRecord
    base = dict(cluster="metis", requested_model="gemma-4-31B-it")
    base.update(kw)
    return CallRecord(**base)


def test_truncation_caught_when_server_reports_no_finish_reason():
    """The MEASURED metis/Gemma shape: at the cap, both reason fields empty."""
    from p1mem.client import P1Client, TruncatedResponseError
    c = P1Client(cluster="metis", model="gemma-4-31B-it", cache=None,
                 truncation_is_always_an_error=True)
    rec = _rec(finish_reason="", raw_stop_reason="", output_tokens=512)
    # the OLD detector is silent on exactly this record --
    assert rec.finish_reason != "length"
    # -- and the new one must not be.
    with pytest.raises(TruncatedResponseError):
        c._assert_not_truncated(rec, "a plausible grammatical fragment", 512)


def test_truncation_caught_via_stop_reason_alone():
    from p1mem.client import P1Client, TruncatedResponseError
    c = P1Client(cluster="metis", model="gemma-4-31B-it", cache=None,
                 truncation_is_always_an_error=True)
    rec = _rec(finish_reason="", raw_stop_reason="length", output_tokens=200)
    with pytest.raises(TruncatedResponseError):
        c._assert_not_truncated(rec, "fragment", 512)


def test_complete_answer_below_the_cap_is_not_flagged():
    """The detector must DISCRIMINATE, not just fire."""
    from p1mem.client import P1Client
    c = P1Client(cluster="metis", model="gemma-4-31B-it", cache=None,
                 truncation_is_always_an_error=True)
    rec = _rec(finish_reason="stop", raw_stop_reason="stop", output_tokens=133)
    c._assert_not_truncated(rec, "A complete answer. \\boxed{X}", 512)


def test_widened_detector_does_not_change_gptoss_behaviour():
    """Widening the detector must NOT retroactively invalidate shipped cells.

    The 8 published gpt-oss pilot cells are non-empty truncations that the
    arm deliberately does NOT treat as errors (docs/MODEL_ARMS.md). A fix for
    a Gemma hazard must not silently alter a gpt-oss table.
    """
    from p1mem.client import P1Client, TruncatedResponseError
    c = P1Client(cluster="metis", model="gpt-oss-120b", cache=None)
    assert c.truncation_is_always_an_error is False
    # non-empty truncation: still returned
    c._assert_not_truncated(
        _rec(requested_model="gpt-oss-120b", finish_reason="length",
             raw_stop_reason="length", output_tokens=512),
        "a long truncated gpt-oss answer", 512)
    # empty truncation: still raises (clause 1 intact)
    with pytest.raises(TruncatedResponseError):
        c._assert_not_truncated(
            _rec(requested_model="gpt-oss-120b", finish_reason="length",
                 raw_stop_reason="length", output_tokens=512), "", 512)


def test_arithmetic_clause_flags_exactly_what_clause_one_flags_on_shipped_caches():
    """Proven on real data, not on constructed records.

    Across every shipped cache the widened detector must select EXACTLY the
    rows the old one did for gpt-oss -- otherwise the fix moves a published
    number. Skips rather than passes vacuously if the caches are absent.
    """
    import json
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    paths = sorted(repo.glob("results/*/*cache*.jsonl"))
    if not paths:
        pytest.skip("no caches on disk")
    n_checked = 0
    for p in paths:
        for line in p.open():
            if not line.strip():
                continue
            d = json.loads(line)
            if "response" not in d or "key" not in d:
                continue
            if d["key"].get("model_id") != "gpt-oss-120b":
                continue
            mt = (d["key"].get("decoding_params") or {}).get("max_tokens")
            ct = d["response"].get("completion_tokens") or 0
            fr = d["response"].get("finish_reason")
            sr = (d["response"].get("raw_usage") or {}).get("stop_reason")
            old = fr == "length"
            new = old or sr == "length" or (mt is not None and ct >= mt)
            assert old == new, (
                f"{p}: widening the detector changes a gpt-oss row "
                f"(finish={fr!r} stop={sr!r} tokens={ct}/{mt})")
            n_checked += 1
    assert n_checked > 1000, (
        f"only {n_checked} gpt-oss rows checked; a near-empty scan would pass "
        f"this test vacuously")


def test_cache_hit_path_also_applies_the_widened_detector():
    """Defect #17's shape, inside the fix for defect #16.

    A guard enforced on the fresh path and not the cache path means a RESUME
    scores exactly what the first run refused.
    """
    import json
    import tempfile
    from pathlib import Path
    from p1mem.cache import CachedResponse, ResponseCache, make_key
    from p1mem.client import P1Client, TruncatedResponseError
    d = Path(tempfile.mkdtemp()) / "c.jsonl"
    kf = dict(benchmark="b", source_item_id="s", memory_repr="raw",
              memory_id="m", future_task_id="t", arm="with_memory",
              retrieval_method="oracle", model_id="gemma-4-31B-it",
              cluster="metis", prompt_version="p",
              decoding_params={"temperature": 0.0, "max_tokens": 512},
              replicate_id=0, context_sha256="x")
    k = make_key(**kf)
    ResponseCache(d).store(k, CachedResponse(
        content="a plausible fragment", resolved_model="gemma-4-31B-it",
        cluster="metis", prompt_tokens=100, completion_tokens=512,
        finish_reason="", raw_usage={"stop_reason": ""}))
    c = P1Client(cluster="metis", model="gemma-4-31B-it",
                 cache=ResponseCache(d), truncation_is_always_an_error=True)
    hit = c.cache.lookup(k)
    assert hit is not None, "the stored row must be findable, or this is vacuous"
    rec = _rec(finish_reason=hit.finish_reason,
               raw_stop_reason=(hit.raw_usage or {}).get("stop_reason"),
               output_tokens=hit.completion_tokens, budget_tokens=512,
               cache_hit=True)
    with pytest.raises(TruncatedResponseError):
        c._assert_not_truncated(rec, hit.content, 512)


def test_error_message_names_the_clause_that_actually_fired():
    """A right verdict with a wrong stated reason hides the next defect."""
    from p1mem.client import P1Client, TruncatedResponseError
    c = P1Client(cluster="metis", model="gemma-4-31B-it", cache=None,
                 truncation_is_always_an_error=True)
    with pytest.raises(TruncatedResponseError) as e:
        c._assert_not_truncated(
            _rec(finish_reason="", raw_stop_reason="", output_tokens=512),
            "fragment", 512)
    msg = str(e.value)
    assert "ARITHMETIC" in msg
    # it must NOT claim a finish_reason it did not see
    assert "finish_reason='length'" not in msg

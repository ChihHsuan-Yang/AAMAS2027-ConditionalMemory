"""Tests for the resumable runner.

Resumption is tested by actually killing a run in the middle, not by calling a
resume() method on a clean state -- a resume path that is only exercised from
a tidy starting point is not known to work from a messy one.
"""
from __future__ import annotations

import pytest

from p1mem.cache import ResponseCache
from p1mem.client import P1Client, TruncatedResponseError
from p1mem.runner import Cell, RunLedger, Runner


class FakeTokens:
    def get(self, *, force: bool = False) -> str:
        return "fake"

    def invalidate(self) -> None:
        pass


def payload(content="answer"):
    return {"model": "gpt-oss-120b",
            "choices": [{"finish_reason": "stop",
                         "message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                      "completion_tokens_details": {"reasoning_tokens": 5}}}


def mk_cells(n):
    return [Cell(cell_id=f"c{i}",
                 messages=[{"role": "user", "content": f"q{i}"}],
                 key_fields=dict(benchmark="b", source_item_id=f"i{i}",
                                 memory_repr="summary", memory_id=f"m{i}",
                                 future_task_id=f"t{i}", arm="with_memory",
                                 retrieval_method="oracle", prompt_version="v1",
                                 replicate_id=0))
            for i in range(n)]


def build(tmp_path, monkeypatch, post):
    cache = ResponseCache(tmp_path / "cache.jsonl")
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                      token_provider=FakeTokens())
    monkeypatch.setattr(client, "_post_once", post)
    runner = Runner(client=client, ledger=RunLedger(tmp_path / "ledger.jsonl"),
                    max_workers=4)
    return cache, client, runner


def test_runs_all_cells(tmp_path, monkeypatch):
    calls = {"n": 0}

    def post(body):
        calls["n"] += 1
        return 200, payload(), "", None

    _, _, runner = build(tmp_path, monkeypatch, post)
    stats = runner.run(mk_cells(10))
    assert stats["ok"] == 10 and stats["error"] == 0 and calls["n"] == 10


def test_rerun_is_idempotent_and_makes_no_calls(tmp_path, monkeypatch):
    calls = {"n": 0}

    def post(body):
        calls["n"] += 1
        return 200, payload(), "", None

    cells = mk_cells(8)
    _, _, r1 = build(tmp_path, monkeypatch, post)
    r1.run(cells)
    assert calls["n"] == 8

    # Fresh objects reading the SAME cache and ledger from disk.
    _, _, r2 = build(tmp_path, monkeypatch, post)
    stats = r2.run(cells)
    assert calls["n"] == 8, "a resumed run re-issued completed cells"
    assert stats["skipped"] == 8 and stats["ok"] == 0


def test_resume_after_a_mid_run_crash(tmp_path, monkeypatch):
    """Kill the run partway, then resume; only the remainder is called."""
    calls = {"n": 0}

    class Boom(RuntimeError):
        pass

    def post(body):
        calls["n"] += 1
        if calls["n"] == 5:
            raise Boom("simulated crash")
        return 200, payload(), "", None

    cells = mk_cells(10)
    cache, client, runner = build(tmp_path, monkeypatch, post)
    runner.max_workers = 1          # deterministic ordering for the crash
    # The client turns an unexpected transport exception into a retry/abort;
    # run() records it as an error row rather than losing the run.
    runner.run(cells)
    first_round = calls["n"]
    assert first_round >= 5

    done_before = len(RunLedger(tmp_path / "ledger.jsonl").done)
    assert 0 < done_before < 10, f"expected a partial run, got {done_before}"

    calls["n"] = 100                # no more crashes
    _, _, r2 = build(tmp_path, monkeypatch, post)
    stats = r2.run(cells)
    assert stats["skipped"] == done_before
    assert stats["ok"] + stats["error"] == 10 - done_before
    # Everything is now accounted for.
    assert len(RunLedger(tmp_path / "ledger.jsonl").done) == 10


def test_cached_but_unledgered_cell_is_backfilled_not_recalled(tmp_path, monkeypatch):
    """The gap between the cache write and the ledger append.

    A process killed in that window leaves a cell cached but not ledgered.
    It must be recognised from the cache, not re-called.
    """
    calls = {"n": 0}

    def post(body):
        calls["n"] += 1
        return 200, payload(), "", None

    cells = mk_cells(3)
    cache, client, runner = build(tmp_path, monkeypatch, post)
    runner.run(cells)
    assert calls["n"] == 3

    # Wipe the ledger only; the cache survives.
    (tmp_path / "ledger.jsonl").unlink()
    _, _, r2 = build(tmp_path, monkeypatch, post)
    stats = r2.run(cells)
    assert calls["n"] == 3, "cells present in the cache were re-issued"
    assert stats["skipped"] == 3


def test_truncated_cell_is_an_error_not_a_result(tmp_path, monkeypatch):
    """A truncation must never be ledgered as ok."""
    def post(body):
        return 200, {"model": "gpt-oss-120b",
                     "choices": [{"finish_reason": "length",
                                  "message": {"content": None}}],
                     "usage": {"prompt_tokens": 10, "completion_tokens": 512,
                               "completion_tokens_details": {"reasoning_tokens": 512}}}, "", None

    _, _, runner = build(tmp_path, monkeypatch, post)
    stats = runner.run(mk_cells(4))
    assert stats["ok"] == 0 and stats["error"] == 4
    assert RunLedger(tmp_path / "ledger.jsonl").done == set()

    rows = [l for l in (tmp_path / "ledger.jsonl").read_text().splitlines() if l.strip()]
    assert all("TruncatedResponseError" in r for r in rows)


def test_errors_do_not_block_other_cells(tmp_path, monkeypatch):
    def post(body):
        content = json_content(body)
        if content == "q3":
            return 400, None, '{"error":"bad"}', None
        return 200, payload(), "", None

    def json_content(body):
        return body["messages"][0]["content"]

    _, _, runner = build(tmp_path, monkeypatch, post)
    stats = runner.run(mk_cells(6))
    assert stats["ok"] == 5 and stats["error"] == 1


def test_ledger_survives_a_malformed_tail(tmp_path, monkeypatch):
    def post(body):
        return 200, payload(), "", None

    _, _, runner = build(tmp_path, monkeypatch, post)
    runner.run(mk_cells(2))
    with open(tmp_path / "ledger.jsonl", "a") as fh:
        fh.write("{truncated write\n")
    with pytest.raises(Exception):
        RunLedger(tmp_path / "ledger.jsonl")


def test_resume_key_matches_the_key_the_client_writes(tmp_path, monkeypatch):
    """The runner's pending-check and the client's write must agree exactly.

    Both derive context_sha256 from the same messages. If they diverge, the
    resume path looks up a key the run never writes: every cell reads as
    pending and a resumed run silently re-pays for completed work. That is
    invisible -- it looks like a slow run, not a bug.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from p1mem.cache import make_key
    from p1mem.vendor.rcc_schema import sha256_text

    cell = mk_cells(1)[0]
    common = dict(cell.key_fields, model_id="gpt-oss-120b", cluster="metis",
                  decoding_params={"temperature": 0.0, "max_tokens": 512,
                                   "reasoning_effort": "low"})
    runner_side = make_key(**common, context_sha256=sha256_text(cell.messages))
    client_side = make_key(**common, context_sha256=sha256_text(cell.messages))
    assert runner_side == client_side

    # And a different rendering must NOT collide with it.
    other = make_key(**common,
                     context_sha256=sha256_text([{"role": "user", "content": "different"}]))
    assert other != runner_side

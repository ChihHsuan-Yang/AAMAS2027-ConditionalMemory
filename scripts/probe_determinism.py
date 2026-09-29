#!/usr/bin/env python3
"""G1a: is the Metis reader actually deterministic at temperature 0?

This question has to be settled BEFORE the noise floors, because it decides how
to read them:

* If the endpoint is deterministic, ``F_exec`` is ~0 and that is a real finding
  (a deterministic reader makes dU cleaner and the floor smaller), and
  ``noise.empty_floor``'s ``require_independent_execution`` guard will exclude
  byte-identical WITHOUT groups as "cached" even when they were genuinely
  re-executed. The guard cannot tell deterministic-and-real from cached-and-fake.
* If it is NOT deterministic, the floors are real spread and must be measured.

The only way to tell is to issue BYTE-IDENTICAL requests with the cache DISABLED
and count distinct responses. ``cache=None`` on the client, so every call here
leaves the machine; the call count is reported and is the number of requests
actually made, not the number of cells.

Usage:
    python3 scripts/probe_determinism.py --prompts 6 --repeats 5
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.client import P1Client  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402


def build_prompts(n: int) -> list[tuple[str, list[dict[str, str]]]]:
    """Real task-shaped prompts drawn from the benchmark's own questions.

    A probe on a toy prompt ("say hi") would certify nothing about the calls we
    actually make: short deterministic answers are the easy case. These use the
    real system prompt and real deterministic questions, so the probe runs in
    the target environment.
    """
    sys.path.insert(0, "/tmp/lmev2")
    qs = [json.loads(l) for l in open("/tmp/lmev2/questions.jsonl")]
    llm = {"llm_abstention_checker", "llm_gotchas_checker"}
    det = [q for q in qs if q["eval_function"].split("|", 1)[0].strip() not in llm]
    det.sort(key=lambda q: q["id"])
    from p1mem.cells import SYSTEM

    out = []
    for q in det[:n]:
        msgs = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"--- Question ---\n{q['question']}"},
        ]
        out.append((q["id"], msgs))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=int, default=6)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results" / "noise" / "determinism_probe.json")
    args = ap.parse_args()

    # cache=None: NOTHING here may be served from cache. That is the whole point.
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=None,
                      max_concurrency=8)
    assert client.cache is None, "cache must be disabled for a determinism probe"

    prompts = build_prompts(args.prompts)
    print(f"[{utc_now()}] determinism probe: {len(prompts)} prompts "
          f"x {args.repeats} repeats = {len(prompts) * args.repeats} REAL calls",
          flush=True)

    records = []
    n_calls = 0
    t0 = time.monotonic()
    for qid, msgs in prompts:
        for rep in range(args.repeats):
            content, rec = client.chat(msgs, max_tokens=args.max_tokens,
                                       temperature=0.0, reasoning_effort="low")
            n_calls += 1
            assert not rec.cache_hit, "a cache hit in a cache-disabled probe"
            records.append({"question_id": qid, "repeat": rep, "content": content,
                            "output_tokens": rec.output_tokens,
                            "reasoning_tokens": rec.reasoning_tokens,
                            "finish_reason": rec.finish_reason})
            print(f"  {qid} rep{rep}: {len(content)} chars, "
                  f"{rec.output_tokens} out tok", flush=True)

    by_q = collections.defaultdict(list)
    for r in records:
        by_q[r["question_id"]].append(r["content"])

    per_q = {}
    n_identical = 0
    for qid, contents in by_q.items():
        distinct = len(set(contents))
        per_q[qid] = {
            "n_repeats": len(contents),
            "n_distinct_outputs": distinct,
            "all_identical": distinct == 1,
            "output_lengths": [len(c) for c in contents],
        }
        n_identical += int(distinct == 1)

    verdict = ("DETERMINISTIC" if n_identical == len(by_q)
               else "NONDETERMINISTIC" if n_identical == 0
               else "MIXED")
    summary = {
        "run_at_utc": utc_now(),
        "wall_clock_s": round(time.monotonic() - t0, 2),
        "cluster": "metis", "model": "gpt-oss-120b",
        "temperature": 0.0, "reasoning_effort": "low",
        "max_tokens": args.max_tokens,
        "cache_disabled": True,
        "n_real_calls": n_calls,
        "n_prompts": len(by_q),
        "n_repeats_each": args.repeats,
        "n_prompts_fully_identical": n_identical,
        "verdict": verdict,
        "per_question": per_q,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    (args.out.parent / "determinism_probe_raw.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n")

    print()
    print(f"VERDICT: {verdict}  "
          f"({n_identical}/{len(by_q)} prompts returned byte-identical text "
          f"across {args.repeats} cache-disabled repeats)")
    print(f"REAL CALLS MADE: {n_calls}")
    print(f"WROTE {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

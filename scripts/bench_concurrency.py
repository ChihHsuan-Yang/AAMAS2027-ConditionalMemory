#!/usr/bin/env python3
"""C2: concurrency ladder against a pinned cluster+model, at representative shapes.

Design notes that matter for reading the numbers:

* Each level runs a fixed number of requests through a thread pool of N workers.
  Throughput is measured over the WALL CLOCK OF THAT LEVEL ONLY, using the
  level's own start/end timestamps -- never an arrival time, never a short delta.
* Shapes are interleaved (4k, 16k, 4k, 16k, ...) so every level sees the SAME mix.
  A level that happened to run all the cheap shapes first would show a flattering
  early rate; interleaving removes that.
* Failures are classified by kind (timeout / 429 / 5xx / other) and reported as
  rates, because a level that "got faster" by failing more is not faster.
* `finish_reason == "length"` with empty content is counted as a TRUNCATION, not
  a success -- see report C1.4. A truncated answer is not a served answer.
* No retries inside the benchmark: retry logic would mask the very failure rates
  we are trying to measure. The production client retries; this does not.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_endpoints import filler, get_token, post_chat  # noqa: E402


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile. Exact and unambiguous for small n."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(1, min(len(ordered), int(round(pct / 100.0 * len(ordered) + 0.5))))
    return ordered[k - 1]


def build_prompt(approx_tokens: int, idx: int) -> str:
    """A prompt shaped like a real P1 cell: long memory context in, a
    judgement of that memory's usefulness out, sized to ~256 output tokens.

    The output length matters as much as the input length: a benchmark whose
    answers are 47 tokens long measures a different service than one whose
    answers are 256, because decode time dominates at these context sizes.
    """
    return (
        "Below is a memory transcript from an agent's earlier episode.\n\n"
        f"[transcript {idx}]\n{filler(approx_tokens)}\n\n"
        "Question: Assess, in about 120 words, whether this transcript would help or "
        "hurt an agent attempting a NEW task about river navigation. Name the specific "
        "details that transfer, the ones that mislead, and end with a one-word verdict."
    )


def run_level(token: str, cluster: str, model: str, workers: int, n_requests: int,
              shapes: list[int], max_tokens: int, effort: str, timeout: float,
              log_fh) -> dict:
    lock = threading.Lock()
    records: list[dict] = []

    def one(i: int) -> None:
        approx = shapes[i % len(shapes)]
        extra = {"reasoning_effort": effort} if effort else None
        res = post_chat(token, cluster, model,
                        [{"role": "user", "content": build_prompt(approx, i)}],
                        max_tokens=max_tokens, temperature=0.0, timeout=timeout,
                        extra=extra)
        rec = {"i": i, "shape": approx, "latency": res["latency"], "http": res["http"]}
        if res["ok"]:
            p = res["payload"]
            u = p.get("usage") or {}
            ch = (p.get("choices") or [{}])[0]
            content = (ch.get("message") or {}).get("content") or ""
            fin = ch.get("finish_reason")
            rec.update({
                "outcome": "truncated" if (fin == "length" and not content.strip()) else "ok",
                "finish_reason": fin,
                "prompt_tokens": u.get("prompt_tokens"),
                "completion_tokens": u.get("completion_tokens"),
                "resolved_model": p.get("model"),
            })
        else:
            err = (res.get("error") or "")
            code = res["http"]
            if code == 429:
                kind = "rate_limited"
            elif code is not None and 500 <= code < 600:
                kind = "server_5xx"
            elif "timed out" in err.lower() or "timeout" in err.lower():
                kind = "timeout"
            else:
                kind = "other_error"
            rec.update({"outcome": kind, "error": err[:200],
                        "retry_after": res.get("retry_after")})
        with lock:
            records.append(rec)
            log_fh.write(json.dumps({"level": workers, **rec}, sort_keys=True) + "\n")
            log_fh.flush()

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(n_requests)))
    wall = time.monotonic() - t0

    ok = [r for r in records if r.get("outcome") == "ok"]
    lat_ok = [r["latency"] for r in ok]
    n = len(records)

    def rate(kind: str) -> float:
        return round(100.0 * sum(1 for r in records if r.get("outcome") == kind) / n, 2) if n else 0.0

    # First-request latency is reported separately: a cold connection/route can
    # dominate a small level's wall clock and is not a property of concurrency.
    first = next((r["latency"] for r in sorted(ok, key=lambda x: x["i"])), float("nan"))
    lat_warm = [r["latency"] for r in sorted(ok, key=lambda x: x["i"])[1:]]
    in_tok = sum(r.get("prompt_tokens") or 0 for r in ok)
    out_tok = sum(r.get("completion_tokens") or 0 for r in ok)
    return {
        "workers": workers,
        "requests": n,
        "wall_s": round(wall, 2),
        "completed_ok": len(ok),
        "req_per_s": round(len(ok) / wall, 3) if wall > 0 else 0.0,
        "completed_per_min": round(60.0 * len(ok) / wall, 1) if wall > 0 else 0.0,
        "p50_s": round(statistics.median(lat_ok), 3) if lat_ok else float("nan"),
        "p95_s": round(percentile(lat_ok, 95), 3) if lat_ok else float("nan"),
        "max_s": round(max(lat_ok), 3) if lat_ok else float("nan"),
        "first_req_s": round(first, 3) if first == first else float("nan"),
        "p95_excl_first_s": round(percentile(lat_warm, 95), 3) if lat_warm else float("nan"),
        "timeout_pct": rate("timeout"),
        "http429_pct": rate("rate_limited"),
        "http5xx_pct": rate("server_5xx"),
        "other_err_pct": rate("other_error"),
        "truncated_pct": rate("truncated"),
        "in_tok_per_s": round(in_tok / wall, 1) if wall > 0 else 0.0,
        "out_tok_per_s": round(out_tok / wall, 1) if wall > 0 else 0.0,
        "total_tok_per_s": round((in_tok + out_tok) / wall, 1) if wall > 0 else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", default="metis")
    ap.add_argument("--model", default="gpt-oss-120b")
    ap.add_argument("--levels", default="1,2,4,8,10,12,16")
    ap.add_argument("--requests-per-level", type=int, default=0,
                    help="0 = auto: max(--min-requests, workers * --waves)")
    ap.add_argument("--min-requests", type=int, default=20)
    ap.add_argument("--waves", type=int, default=3,
                    help="a level must run at least this many full waves, else its "
                         "throughput is one round trip rather than a sustained rate")
    ap.add_argument("--shapes", default="4000,16000")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--abort-fail-pct", type=float, default=40.0,
                    help="stop the ladder if a level's non-ok rate exceeds this")
    ap.add_argument("--out", default="results/bench/metis_ladder.jsonl")
    ap.add_argument("--raw", default="results/bench/metis_ladder_raw.jsonl")
    args = ap.parse_args()

    token = get_token()
    shapes = [int(s) for s in args.shapes.split(",")]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    summaries = []
    with open(args.raw, "a") as raw_fh, open(args.out, "a") as out_fh:
        for workers in [int(s) for s in args.levels.split(",")]:
            n_req = (args.requests_per_level if args.requests_per_level > 0
                     else max(args.min_requests, workers * args.waves))
            s = run_level(token, args.cluster, args.model, workers,
                          n_req, shapes, args.max_tokens,
                          args.effort, args.timeout, raw_fh)
            s["waves"] = round(n_req / workers, 2)
            s["cluster"] = args.cluster
            s["model"] = args.model
            s["max_tokens"] = args.max_tokens
            s["effort"] = args.effort
            s["shapes"] = args.shapes
            s["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            summaries.append(s)
            print(json.dumps(s), flush=True)
            out_fh.write(json.dumps(s, sort_keys=True) + "\n")
            out_fh.flush()
            failpct = (s["timeout_pct"] + s["http429_pct"] + s["http5xx_pct"]
                       + s["other_err_pct"] + s["truncated_pct"])
            if failpct > args.abort_fail_pct:
                print(f"ABORT LADDER: level {workers} non-ok {failpct:.1f}% "
                      f"> {args.abort_fail_pct}%", flush=True)
                break
            time.sleep(3)  # let the gateway settle between levels
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

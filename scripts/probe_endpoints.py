#!/usr/bin/env python3
"""C1 feasibility probe: does a model actually SERVE, at our real request shapes?

Makes real POSTs (an advertised model can 503/502 -- we proved that twice).
Reports: requested id -> resolved id, latency, usage, finish_reason, HTTP code.
Never prints the bearer token.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

GATEWAY = "https://inference-api.alcf.anl.gov/resource_server"
AUTH_DIR = "/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication"

# cluster -> framework segment in the chat-completions path
FRAMEWORK = {"sophia": "vllm", "metis": "api", "minerva": "api", "tara": "api"}


def get_token() -> str:
    out = subprocess.run(
        [sys.executable, "inference_auth_token.py", "get_access_token"],
        cwd=AUTH_DIR, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def chat_url(cluster: str) -> str:
    return f"{GATEWAY}/{cluster}/{FRAMEWORK[cluster]}/v1/chat/completions"


def filler(approx_tokens: int) -> str:
    """Deterministic English-ish filler. ~1.3 tokens/word for this vocabulary;
    the caller reports the SERVER-COUNTED prompt_tokens, never this estimate."""
    words = []
    vocab = ("the quick brown fox jumps over a lazy dog while seventeen silver "
             "kettles boil beneath an ancient wooden bridge near the river").split()
    i = 0
    while len(words) < approx_tokens:
        words.append(vocab[i % len(vocab)])
        i += 1
    return " ".join(words)


def post_chat(token: str, cluster: str, model: str, messages: list, *,
              max_tokens: int, temperature: float = 0.0, timeout: float = 600.0,
              extra: dict | None = None) -> dict:
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        chat_url(cluster), data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
            return {"ok": True, "http": r.status, "latency": time.monotonic() - t0,
                    "payload": payload}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:600]
        return {"ok": False, "http": e.code, "latency": time.monotonic() - t0,
                "error": raw, "retry_after": e.headers.get("Retry-After")}
    except Exception as e:  # noqa: BLE001 -- timeouts, conn resets
        return {"ok": False, "http": None, "latency": time.monotonic() - t0,
                "error": f"{type(e).__name__}: {e}"}


def summarize(tag: str, res: dict) -> dict:
    row = {"tag": tag, "http": res["http"], "latency_s": round(res["latency"], 3)}
    if res["ok"]:
        p = res["payload"]
        u = p.get("usage") or {}
        ch = (p.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        cd = u.get("completion_tokens_details") or {}
        row.update({
            "resolved_model": p.get("model"),
            "finish_reason": ch.get("finish_reason"),
            "prompt_tokens": u.get("prompt_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": cd.get("reasoning_tokens"),
            "content_chars": len(msg.get("content") or ""),
            "fingerprint": p.get("system_fingerprint"),
        })
    else:
        row["error"] = res.get("error", "")[:300]
        row["retry_after"] = res.get("retry_after")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--models", required=True, help="comma-separated")
    ap.add_argument("--shapes", default="4000,16000",
                    help="comma-separated approx input token targets")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    token = get_token()
    rows = []
    for model in args.models.split(","):
        for approx in [int(s) for s in args.shapes.split(",")]:
            prompt = (
                "Below is a memory transcript. Read it, then answer the question.\n\n"
                f"{filler(approx)}\n\nQuestion: In one short sentence, what colour was the fox?"
            )
            res = post_chat(token, args.cluster, model,
                            [{"role": "user", "content": prompt}],
                            max_tokens=args.max_tokens)
            row = summarize(f"{args.cluster}/{model}/~{approx}", res)
            row["target_input_tokens"] = approx
            rows.append(row)
            print(json.dumps(row), flush=True)
    if args.out:
        with open(args.out, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

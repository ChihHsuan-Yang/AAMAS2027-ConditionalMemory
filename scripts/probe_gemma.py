#!/usr/bin/env python3
"""SA-GEMMA step 3-4: prove/disprove LIVENESS of every plausible Gemma id
with a REAL chat POST. An advertised model is not a live model (this project
has been burned 4x). A negative control id that is NOT advertised is included
so an all-pass result cannot be a property of the harness.

max_tokens defaults to 512 (>=256 required): a small budget is eaten by
reasoning tokens and yields finish_reason='length' with empty content, which
is TRUNCATION, not death. Truncation is reported as its own outcome, never as
a failure and never as a scored answer.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time, urllib.error, urllib.request

GATEWAY = "https://inference-api.alcf.anl.gov/resource_server"
AUTH_DIR = "/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication"
FRAMEWORK = {"sophia": "vllm", "metis": "api", "minerva": "api", "tara": "api"}


def get_token() -> str:
    # stderr NOT suppressed: a missing interpreter must not read as a blank failure.
    out = subprocess.run([sys.executable, "inference_auth_token.py", "get_access_token"],
                         cwd=AUTH_DIR, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def post_chat(token, cluster, model, messages, *, max_tokens, temperature=0.0,
              timeout=300.0, extra=None):
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    if extra:
        body.update(extra)
    req = urllib.request.Request(
        f"{GATEWAY}/{cluster}/{FRAMEWORK[cluster]}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "http": r.status, "latency": time.monotonic() - t0,
                    "payload": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code, "latency": time.monotonic() - t0,
                "error": e.read().decode()[:800], "retry_after": e.headers.get("Retry-After")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "http": None, "latency": time.monotonic() - t0,
                "error": f"{type(e).__name__}: {e}"}


def classify(requested, res):
    """Liveness verdict. resolved!=requested is a MISMATCH, never normalised."""
    row = {"requested": requested, "http": res["http"],
           "latency_s": round(res["latency"], 3)}
    if not res["ok"]:
        row["verdict"] = "DEAD_OR_ERROR"
        row["error"] = res.get("error", "")[:400]
        return row
    p = res["payload"]
    u = p.get("usage") or {}
    cd = u.get("completion_tokens_details") or {}
    ch = (p.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content") or ""
    fin = ch.get("finish_reason")
    resolved = p.get("model")
    row.update({"resolved": resolved, "finish_reason": fin,
                "prompt_tokens": u.get("prompt_tokens"),
                "completion_tokens": u.get("completion_tokens"),
                "reasoning_tokens": cd.get("reasoning_tokens"),
                "content_chars": len(content),
                "content": content[:1200],
                "reasoning_field_present": "reasoning_content" in msg or "reasoning" in msg,
                "fingerprint": p.get("system_fingerprint")})
    if fin == "length" and not content.strip():
        row["verdict"] = "TRUNCATED_NOT_DEATH"
    elif resolved != requested:
        row["verdict"] = "ID_MISMATCH"
    elif content.strip():
        row["verdict"] = "LIVE"
    else:
        row["verdict"] = "EMPTY_CONTENT"
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True,
                    help="comma-separated cluster:model pairs")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--effort", default="", help="reasoning_effort; empty = omit")
    ap.add_argument("--prompt",
                    default="Reply with exactly this sentence and nothing else: "
                            "The capital of France is Paris.")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    token = get_token()
    rows = []
    for case in args.cases.split(","):
        cluster, model = case.split(":", 1)
        extra = {"reasoning_effort": args.effort} if args.effort else None
        res = post_chat(token, cluster, model,
                        [{"role": "user", "content": args.prompt}],
                        max_tokens=args.max_tokens, temperature=args.temperature,
                        extra=extra)
        row = classify(model, res)
        row.update({"cluster": cluster, "max_tokens": args.max_tokens,
                    "temperature": args.temperature,
                    "reasoning_effort": args.effort or None,
                    "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
    if args.out:
        with open(args.out, "a") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

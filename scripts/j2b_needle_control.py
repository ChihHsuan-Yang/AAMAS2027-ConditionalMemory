#!/usr/bin/env python3
"""J2b: a VALID positive control -- a planted needle in the REAL 27k context.

WHY THE FIRST POSITIVE CONTROL WAS DEFECTIVE
--------------------------------------------
J2 asked "What is the capital city of France?" under the benchmark's OWN system
prompt, which says: *"Answer based on your memory of the environment. If you do
not know the answer, output exactly \\boxed{UNKNOWN}. Do not guess."* The capital
of France is not a fact about the WorkArena/WebArena environment, so a
well-behaved model under that prompt SHOULD abstain. Two configs did
(high_effort, nemotron) and two answered anyway (base_replication, inkling).

That control therefore measured *prompt compliance*, not *harness capability*.
Reading a 0 there as "the harness cannot register a gain" would be the
project's own "test the mechanism, not a comparator" error: a control that
cannot exhibit the behaviour cannot certify its absence.

THE REPLACEMENT
---------------
Same 22 oracle cells, same real ~27k context, same official system prompt, same
scorer -- but ONE sentence is planted into the target memory and the question
asks for the planted fact. The needle is in-environment by construction (it is
phrased as a UI/config fact and inserted inside the trajectory text), so an
abstention is NOT the correct answer.

This is a positive control AND the decisive reader probe:

  * needle FOUND  -> the reader can retrieve a stated fact from 27k tokens
                     under this prompt, and the harness registers a 1. Failure
                     on the real questions is then NOT raw retrieval.
  * needle MISSED -> the reader cannot read this context at all, and every
                     null in J1/J2 is void for the reason H suspected.

Reads artifacts + makes calls. Writes results/j2_escalation/needle_*.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.cells import official_system_prompt  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def _j2():
    spec = importlib.util.spec_from_file_location(
        "j2mod", REPO / "scripts/j2_escalate_reader.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: The needle. A per-cell unique 6-digit code, phrased as an environment fact so
#: that abstention is not the correct answer under the official prompt.
def needle_for(memory_id: str, task_id: str) -> tuple[str, str]:
    h = hashlib.sha256(f"needle:{memory_id}:{task_id}".encode()).hexdigest()
    code = str(int(h[:8], 16) % 900000 + 100000)
    sentence = (f"\nNote for the operator: the internal reference code for this "
                f"page configuration is {code}.\n")
    return sentence, code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_official/cells.jsonl")
    ap.add_argument("--out", type=Path, default=REPO / "results/j2_escalation")
    ap.add_argument("--configs", default="base_replication,nemotron,inkling")
    ap.add_argument("--max-pool-hits", type=int, default=8)
    ap.add_argument("--n-control", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-calls", type=int, default=120)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    J = _j2()
    cfg_names = [c.strip() for c in args.configs.split(",") if c.strip()]
    for c in cfg_names:
        if c not in J.CONFIGS:
            raise SystemExit(f"unknown config {c!r}")

    oracle, control, cells, tasks, loc_of = J.pick_cells(
        args.rows, args.root, args.max_pool_hits, args.n_control, args.seed)
    ctxs = J.build_all_contexts(args.root, args.seed, 6, 1500, 5000, 12, "official")

    jobs = []
    for k in oracle:
        c = ctxs[(loc_of[k[0]], k[1])]
        mem = c["memory_text"]
        sentence, code = needle_for(k[0], k[1])
        if mem not in c["user_with"]:
            raise SystemExit(f"target memory not in WITH context for {k}")
        if code in c["user_with"]:
            raise SystemExit(f"needle code {code} ALREADY in context for {k}")
        # plant INSIDE the target memory, at its real position in the context
        planted_mem = mem + sentence
        user = c["user_with"].replace(mem, planted_mem, 1)
        if user.count(code) != 1:
            raise SystemExit(f"needle not planted exactly once for {k}")
        question = ("What is the internal reference code for the page "
                    "configuration mentioned in the notes? Put the final answer "
                    "in \\boxed{}.")
        body = user.rsplit("\n\n--- Question ---\n", 1)[0]
        for cname in cfg_names:
            jobs.append({
                "config": cname, "memory_id": k[0], "task_id": k[1],
                "code": code,
                "messages": [
                    {"role": "system", "content": c["system"]},
                    {"role": "user",
                     "content": f"{body}\n\n--- Question ---\n{question}"},
                ],
            })
    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls}) "
        f"over {len(oracle)} oracle cells x {len(cfg_names)} configs")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} > --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        return 0

    cache = ResponseCache(args.out / "needle_cache.jsonl")
    clients = {c: P1Client(cluster=J.CONFIGS[c]["cluster"], model=J.CONFIGS[c]["model"],
                           cache=cache, max_concurrency=args.workers)
               for c in cfg_names}

    def run_one(j):
        cfg = J.CONFIGS[j["config"]]
        kf = {"benchmark": "longmemeval_v2", "source_item_id": j["task_id"],
              "memory_repr": "raw", "memory_id": j["memory_id"],
              "future_task_id": j["task_id"], "arm": "with_memory",
              "retrieval_method": "oracle",
              "prompt_version": f"p1_j2b_needle|{j['config']}", "replicate_id": 0}
        try:
            c, rec = clients[j["config"]].chat(
                j["messages"], max_tokens=cfg["max_tokens"], temperature=0.0,
                reasoning_effort=cfg["reasoning_effort"], cache_key_fields=kf)
            return j, c, rec, None
        except ClientError as e:
            return j, None, None, f"{type(e).__name__}: {e}"

    log(f"executing {len(jobs)} calls at concurrency {args.workers} ...")
    t0 = time.monotonic()
    out, nerr = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            j, content, rec, err = fut.result()
            row = {"config": j["config"], "memory_id": j["memory_id"],
                   "task_id": j["task_id"], "code": j["code"],
                   "content": content, "error": err}
            if err:
                nerr += 1
            else:
                row["finish_reason"] = rec.finish_reason
                row["prompt_tokens"] = rec.input_tokens
                row["completion_tokens"] = rec.output_tokens
            out.append(row)
            if n % 20 == 0:
                log(f"  {n}/{len(jobs)} (err={nerr})")
    wall = time.monotonic() - t0
    log(f"done in {wall:.1f}s errors={nerr}")

    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        eval_from_spec, extract_boxed_answer, is_unknown,
    )
    spec = ("norm_phrase_set_match|lower=true|normalize_hyphen=true"
            "|strip_punct=true|separators=,;|require_non_empty=true")
    for r in out:
        if r["content"] is None:
            r["found"] = None; r["is_unknown"] = None; continue
        parsed = extract_boxed_answer(r["content"])
        r["is_unknown"] = bool(is_unknown(parsed))
        r["found"] = (0.0 if r["is_unknown"]
                      else float(bool(eval_from_spec(spec, parsed, r["code"]))))
        # also: did the code appear ANYWHERE in the response (lenient)
        r["code_in_response_anywhere"] = r["code"] in (r["content"] or "")

    rp = args.out / "needle_responses.jsonl"
    with open(rp, "w") as fh:
        for r in out:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    summary = {"run_at_utc": utc_now(), "wall_clock_s": round(wall, 2),
               "responses_artifact": str(rp), "n_cells": len(oracle),
               "errors": nerr, "per_config": {},
               "_what": "planted-needle positive control in the REAL 27k context"}
    print("\n=== J2b NEEDLE CONTROL (planted fact in the real 27k context) ===")
    for cname in cfg_names:
        rs = [r for r in out if r["config"] == cname and r["found"] is not None]
        n = len(rs)
        if not n:
            summary["per_config"][cname] = {"n": 0}
            print(f"  {cname:20s} NO DATA"); continue
        f = sum(r["found"] for r in rs)
        anyw = sum(r["code_in_response_anywhere"] for r in rs)
        unk = sum(r["is_unknown"] for r in rs)
        _, lo, hi = wilson_ci(round(f), n)
        summary["per_config"][cname] = {
            "n": n, "n_found_boxed": round(f), "found_rate": f / n,
            "found_wilson": [lo, hi],
            "n_code_anywhere_in_response": anyw,
            "n_abstained": unk,
            "n_errors": len([r for r in out if r["config"] == cname and r["found"] is None]),
        }
        print(f"  {cname:20s} n={n:3d} needle-found={f/n:.4f} "
              f"({round(f)}/{n}) [{lo:.3f},{hi:.3f}]  "
              f"code-anywhere={anyw}/{n}  abstained={unk}/{n}")
    write_json_atomic(args.out / "needle_summary.json", summary)
    print(f"\n[wrote] {args.out / 'needle_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

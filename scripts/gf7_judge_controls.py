#!/usr/bin/env python3
"""GF7: ask the GF-LLM judge about CONTROL candidates.

WHY THIS EXISTS
---------------
``gf5_llm_screen.py`` only ever showed the judge cells that survived the
LEXICAL recall stage. Its 799 NO verdicts are therefore all lexically similar
cells, and a matched control must be *same memory, same question_type family*.
Measured: **24 of the 42 GF-LLM bearing cells have no same-family judge-NO
cell at all**, so a control set drawn only from the existing cache would be
missing for most of the stratum -- or, worse, would silently fall back to
"cells the judge never saw", which is a different object from "cells the judge
rejected".

This asks the judge directly about same-memory/same-family candidates it has
not seen, writing into the SAME cache with the SAME prompt version, model,
cluster and temperature, so bearing and control verdicts are produced by one
instrument.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import gf5_llm_screen as G5  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--headroom", type=int, default=3,
                    help="candidates judged per control needed; the judge says NO "
                         "~95% of the time so 3x is ample")
    ap.add_argument("--size-cap", type=int, default=G5.SIZE_CAP_TOKENS)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--cache", type=Path,
                    default=REPO / "results/gf_llm/judge_cache.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_llm_controls.json")
    args = ap.parse_args()

    t0 = time.time()
    units = {u["memory_unit_locator"]: u for u in
             (json.loads(l) for l in
              (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
               ).read_text().splitlines() if l.strip())}
    ut = {}
    for line in (REPO / ".sa_goldfree_scratch/unit_texts.jsonl").read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            ut[d["memory_unit_locator"]] = d
    tasks = {t.id: t for t in lmev2.load_tasks(args.root) if t.deterministic}
    llm = [json.loads(l) for l in
           (REPO / "data/manifests/gf_llm_bearing.jsonl"
            ).read_text().splitlines() if l.strip()]

    judged: set[tuple[str, str]] = set()
    for line in args.cache.open():
        if not line.strip():
            continue
        d = json.loads(line)
        k = d.get("key") or {}
        if k.get("prompt_version") == G5.PROMPT_VERSION:
            judged.add((k.get("memory_id"), k.get("future_task_id")))
    log(f"judge cache holds {len(judged)} verdicts")

    by_domfam: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for tid, t in tasks.items():
        by_domfam[(t.domain, t.question_type)].append(tid)
    for v in by_domfam.values():
        v.sort()
    need: collections.Counter = collections.Counter()
    for r in llm:
        need[(r["memory_unit_locator"], tasks[r["task_id"]].question_type)] += 1

    cands: list[tuple[str, str]] = []
    for (m, fam), k in sorted(need.items()):
        dom = units[m]["domain"]
        mid = units[m]["memory_id"]
        if units[m]["n_tokens"] > args.size_cap:
            continue
        pool = [tid for tid in by_domfam[(dom, fam)] if (mid, tid) not in judged]
        cands.extend((m, tid) for tid in pool[: args.headroom * k])
    cands.sort()
    log(f"PLANNED CONTROL-JUDGE CALLS: {len(cands)} (budget {args.max_calls})")
    if len(cands) > args.max_calls:
        raise SystemExit(f"planned {len(cands)} exceeds {args.max_calls}")

    cache = ResponseCache(args.cache)
    client = P1Client(cluster=G5.JUDGE_CLUSTER, model=G5.JUDGE_MODEL, cache=cache,
                      max_concurrency=args.workers)
    ctrl = G5.control_judge_can_say_both(client, args.cache.name)
    log(f"judge control: PASS={ctrl['PASS']}")
    if not ctrl["PASS"]:
        raise SystemExit("judge control FAILED")

    for m, tid in cands:
        G5.assert_prompt_is_gold_free(
            G5.build_prompt(tasks[tid].question, ut[m]["text"]),
            tasks[tid].question, ut[m]["text"], tid)
    log(f"gold-freeness asserted on all {len(cands)} prompts")

    def run_one(mt):
        m, tid = mt
        try:
            txt, _ = client.chat(
                [{"role": "system", "content": G5.SYSTEM},
                 {"role": "user",
                  "content": G5.build_prompt(tasks[tid].question, ut[m]["text"])}],
                max_tokens=256, temperature=0.0, reasoning_effort="low",
                cache_key_fields={"benchmark": "longmemeval_v2",
                                  "source_item_id": units[m]["trajectory_id"],
                                  "memory_repr": "raw",
                                  "memory_id": units[m]["memory_id"],
                                  "future_task_id": tid, "arm": "with_memory",
                                  "retrieval_method": "oracle",
                                  "prompt_version": G5.PROMPT_VERSION,
                                  "replicate_id": 0})
            return m, tid, G5.parse_verdict(txt), None
        except ClientError as e:
            return m, tid, None, str(e)

    n_yes = n_no = n_und = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, c) for c in cands]
        for n, fut in enumerate(as_completed(futs), 1):
            _m, _t, v, err = fut.result()
            if err or v is None:
                n_und += 1
            elif v:
                n_yes += 1
            else:
                n_no += 1
            if n % 50 == 0:
                log(f"  {n}/{len(cands)} judged")
    log(f"control-candidate verdicts: {n_yes} YES, {n_no} NO, {n_und} undecided")
    write_json_atomic(args.out, {
        "_what": "GF7: judge verdicts on same-memory/same-family CONTROL candidates",
        "_why": "gf5 only showed the judge lexically-similar cells, so 24 of 42 "
                "bearing cells had no same-family judge-NO control. A control "
                "must be a cell the judge SAW and REJECTED, not one it never saw.",
        "judge_control": ctrl,
        "n_candidates": len(cands), "n_yes": n_yes, "n_no": n_no,
        "n_undecided": n_und,
        "_undecided_policy": "undecided is never counted as NO",
        "cache": str(args.cache.relative_to(REPO)),
        "wall_clock_s": round(time.time() - t0, 1),
    })
    log(f"[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

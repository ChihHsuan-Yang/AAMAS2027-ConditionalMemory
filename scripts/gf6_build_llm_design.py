#!/usr/bin/env python3
"""GF6: design for the GF-LLM strata. ZERO endpoint calls.

GF-LLM (``scripts/gf5_llm_screen.py``) selects 42 bearing cells, of which 32
are gold-free. Only 21 of the 42 have an executed measurement, and those are
spread across TWO sessions (the screened run and the GF-LEX run) -- defect #25
forbids pooling them. So the whole GF-LLM contrast is re-run in ONE session,
including the cells that already have a measurement elsewhere.

Controls are built by the same rule as everywhere else: SAME memory, SAME
question_type family, the detector SILENT -- here meaning the LLM judge was
asked and said NO, not merely that it was never asked. A control the judge
never saw would be a different kind of object from a bearing cell.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402


def log(m: str) -> None:
    print(m, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=600)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_llm_design.json")
    ap.add_argument("--cells-out", type=Path,
                    default=REPO / "data/manifests/gf_llm_cells.jsonl")
    args = ap.parse_args()

    units = {u["memory_unit_locator"]: u for u in
             (json.loads(l) for l in
              (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
               ).read_text().splitlines() if l.strip())}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root) if t.deterministic}
    llm = [json.loads(l) for l in
           (REPO / "data/manifests/gf_llm_bearing.jsonl"
            ).read_text().splitlines() if l.strip()]
    L = {(r["memory_unit_locator"], r["task_id"]): r for r in llm}
    log(f"[input] GF-LLM bearing {len(L)} cells "
        f"({sum(1 for r in llm if not r['also_gold_bearing'])} gold-free)")

    # The judge's NO verdicts, recovered from its cache, so a control is a cell
    # the judge SAW and REJECTED -- not one it never saw.
    import gf5_llm_screen as G5
    judged_no: set[tuple[str, str]] = set()
    judged_yes: set[tuple[str, str]] = set()
    cache_path = REPO / "results/gf_llm/judge_cache.jsonl"
    by_mid = collections.defaultdict(list)
    for loc, u in units.items():
        by_mid[u["memory_id"]].append(loc)
    n_cache = 0
    for line in cache_path.open():
        if not line.strip():
            continue
        d = json.loads(line)
        # The cache's own field names are `key` and `response`, NOT
        # `key_fields`/`content`. The first version of this loop guessed the
        # latter and recovered ZERO verdicts -- caught only because the
        # non-vacuity guard below refuses an empty recovery. A silent zero here
        # would have built every control from cells the judge never saw.
        k = d.get("key") or {}
        if k.get("prompt_version") != G5.PROMPT_VERSION:
            continue
        mid, tid = k.get("memory_id"), k.get("future_task_id")
        locs = by_mid.get(mid) or []
        if len(locs) != 1 or tid not in tasks:
            continue
        v = G5.parse_verdict((d.get("response") or {}).get("content"))
        n_cache += 1
        if v is False:
            judged_no.add((locs[0], tid))
        elif v is True:
            judged_yes.add((locs[0], tid))
    log(f"[judge cache] {n_cache} verdicts recovered: "
        f"{len(judged_yes)} YES, {len(judged_no)} NO")
    if not judged_no:
        raise SystemExit("recovered ZERO judge-NO verdicts; controls would be "
                         "cells the judge never saw, which is a different object")

    cells: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(m, tid, stratum, why, also_gold, extra=None):
        if (m, tid) in seen:
            return False
        seen.add((m, tid))
        t = tasks[tid]
        u = units[m]
        c = {"memory_unit_locator": m, "memory_id": u["memory_id"],
             "trajectory_id": u["trajectory_id"], "domain": u["domain"],
             "memory_tokens": u["n_tokens"], "task_id": tid,
             "question_type": t.question_type, "eval_name": t.eval_name,
             "stratum": stratum, "why_stratum": why,
             "gf_detector_fires": stratum == "GFLLM_BEARING",
             "also_gold_bearing": bool(also_gold),
             "gold_detector_fires_any": False,
             "task_pool_hits_gf": None, "task_pool_hits_gold": None,
             "task_pool_size": None, "replicates": args.replicates}
        c.update(extra or {})
        cells.append(c)
        return True

    for (m, tid), r in sorted(L.items()):
        add(m, tid, "GFLLM_BEARING",
            f"LLM judge YES; task fires on {r['task_pool_hits_llm']} of "
            f"{r['task_pool_size']} same-domain memories",
            r["also_gold_bearing"],
            {"task_pool_hits_gf": r["task_pool_hits_llm"],
             "task_pool_size": r["task_pool_size"],
             "also_gf_lex_bearing": r["also_gf_lex_bearing"]})

    by_domfam: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for tid, t in tasks.items():
        by_domfam[(t.domain, t.question_type)].append(tid)
    need: collections.Counter = collections.Counter()
    for (m, tid) in L:
        need[(m, tasks[tid].question_type)] += 1
    n_short = 0
    for (m, fam), k in sorted(need.items()):
        dom = units[m]["domain"]
        pool = [tid for tid in by_domfam[(dom, fam)]
                if (m, tid) in judged_no and (m, tid) not in seen]
        random.Random(f"{args.seed}:mcllm:{m}:{fam}").shuffle(pool)
        got = 0
        for tid in pool:
            if got >= k:
                break
            if add(m, tid, "GFLLM_MATCHED_CONTROL",
                   f"same memory, same task family '{fam}', the LLM judge SAW "
                   f"this cell and said NO", False):
                got += 1
        if got < k:
            n_short += 1
    bm = {c["memory_unit_locator"] for c in cells if c["stratum"] == "GFLLM_BEARING"}
    cm = {c["memory_unit_locator"] for c in cells
          if c["stratum"] == "GFLLM_MATCHED_CONTROL"}
    strat = collections.Counter(c["stratum"] for c in cells)
    calls = sum(c["replicates"] for c in cells) * 2
    dec = [c for c in cells
           if c["stratum"] == "GFLLM_BEARING" and not c["also_gold_bearing"]]
    log(f"[design] {len(cells)} cells, strata {dict(strat)}")
    log(f"[design] bearing memories {len(bm)}, with a control {len(bm & cm)} "
        f"({n_short} memory x family groups short)")
    log(f"[design] DECIDING (LLM-bearing AND NOT gold-bearing): {len(dec)} cells")
    log(f"[design] PLANNED CALLS {calls} (budget {args.max_calls})")
    if calls > args.max_calls:
        raise SystemExit(f"planned {calls} exceeds {args.max_calls}")
    if not (bm & cm):
        raise SystemExit("no bearing memory has a matched control")

    args.cells_out.parent.mkdir(parents=True, exist_ok=True)
    with args.cells_out.open("w") as fh:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    log(f"[wrote] {args.cells_out}")
    write_json_atomic(args.out, {
        "_what": "GF6 GF-LLM two-stratum design. ZERO endpoint calls.",
        "_why_rerun_everything": "21 of the 42 GF-LLM bearing cells already have a "
                                 "measurement, but spread across TWO sessions "
                                 "(screened + GF-LEX). DEFECT #25 forbids pooling "
                                 "across sessions, so the whole contrast is "
                                 "re-executed in one.",
        "config": {k: (str(v) if isinstance(v, Path) else v)
                   for k, v in vars(args).items()},
        "judge_cache_verdicts": {"n_yes": len(judged_yes), "n_no": len(judged_no)},
        "n_cells": len(cells), "strata": dict(strat),
        "n_bearing_memories": len(bm), "n_with_control": len(bm & cm),
        "n_memory_family_groups_short": n_short,
        "deciding_stratum_llm_and_not_gold": {"n_cells": len(dec)},
        "planned_calls": calls,
        "cells_artifact": str(args.cells_out.relative_to(REPO)),
    })
    log(f"[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

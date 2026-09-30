#!/usr/bin/env python3
"""R2b: re-measure a SUBSET of the Raw WITH arm today, to size cross-session drift.

WHY THIS RUN EXISTS
-------------------
The Raw arm was measured on 2026-09-29 (``k2_run_screened.py``); Summary and
Structured were measured on 2026-09-30 (``r2_run_representations.py``). Both
runs are byte-deterministic WITHIN themselves. They are NOT byte-identical to
each other:

    WITHOUT-arm output text, k2 vs R2, on byte-identical prompts:
        differs on 302 of 570 rows (53.0%)
        REWARD differs on 14 of 570 rows (2.46%)

A cache-disabled probe (``cross_session_probe.json``, 12 real calls) resolved
which side is unstable: 6/6 prompts reproduced R2 exactly and 2/6 reproduced
k2, with both same-minute repeats byte-identical on 6/6. So the endpoint is
deterministic within a session and drifts between them -- a serving change
between 09-29 and 09-30, not sampling noise.

Consequence: ``dU(summary) - dU(raw)`` mixes a WITH arm from one session with a
WITH arm from another. The WITHOUT side is directly measurable (both sessions
recorded it) and is corrected for in the analysis. The WITH side is not, because
nobody re-ran Raw's WITH arm today. This script does, on a sample, so the
residual is a MEASURED bound instead of an assumption.

One replicate per cell: within-session determinism is already established at
285/285 and 277/277, so a second replicate would buy a known-identical row.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.adapters import lmev2                            # noqa: E402
from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (   # noqa: E402
    extract_boxed_answer, is_unknown)
from p1mem.cells import SYSTEM, MemoryUnit, build_context   # noqa: E402
from p1mem.client import P1Client                           # noqa: E402
from p1mem.vendor.rcc_schema import utc_now                 # noqa: E402


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--n-cells", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260930)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=110)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/repr_scaleup/raw_resample.json")
    args = ap.parse_args()

    meta = json.load(open(REPO / "results/ledgers/k1_screened_design.json"))
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}

    fb = meta["filler"]["band"]
    mh = int(meta["config"]["max_pool_hits"])
    hits: dict = collections.Counter()
    fired: dict = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if not line.strip():
            continue
        d = json.loads(line)
        hits[d["task_id"]] += 1
        fired[d["task_id"]].add(d["memory_id"])
    bearing = {m for tid, ms in fired.items()
               if tasks[tid].deterministic and 1 <= hits[tid] <= mh for m in ms}
    ftr = {uloc[m]["trajectory_id"] for m in bearing}
    pool: dict = collections.defaultdict(list)
    for u in units:
        if fb[0] <= u["n_tokens"] <= fb[1] and u["trajectory_id"] not in ftr:
            pool[u["domain"]].append(u)

    # the k2 rows to reproduce
    raw = [json.loads(l) for l in
           (REPO / "results/deltau_screened/cells.jsonl").read_text().splitlines()
           if l.strip()]
    raw = [r for r in raw
           if (r.get("provenance") or {}).get("stratum")
           in ("BEARING", "MATCHED_CONTROL") and r["replicate_id"] == 0]
    log(f"k2 raw rows at replicate 0: {len(raw)}")
    rng = random.Random(args.seed)
    pick = rng.sample(sorted(raw, key=lambda r: r["row_id"]),
                      min(args.n_cells, len(raw)))
    log(f"sampling {len(pick)} cells (seed {args.seed})")
    if len(pick) > args.max_calls:
        raise SystemExit(f"{len(pick)} calls exceeds --max-calls {args.max_calls}")

    need = set()
    plan = []
    for r in pick:
        loc = (r["source_episode_metadata"] or {})["memory_unit_locator"]
        tid = r["future_task_id"]
        u = uloc[loc]
        order = sorted(pool[u["domain"]], key=lambda x: x["memory_unit_locator"])
        random.Random(f"filler:{tid}").shuffle(order)
        fil = order[:4]
        need |= {f["memory_unit_locator"] for f in fil} | {loc}
        plan.append((r, loc, tid, u, fil))

    texts: dict = {}
    for traj in lmev2.read_jsonl(args.root / "trajectories.jsonl"):
        if traj["id"] not in {l.split(":")[0] for l in need}:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator in need:
                texts[pv.memory_unit_locator] = pv.text
        if len(texts) >= len(need):
            break
    if len(texts) != len(need):
        raise SystemExit(f"text join matched {len(texts)} of {len(need)}; aborting")

    # cache=None: every call is a real request. Serving from the k2 cache would
    # make the comparison vacuous -- it would compare k2 with itself.
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=None,
                      max_concurrency=args.workers)

    def one(item):
        r, loc, tid, u, fil = item
        task = tasks[tid]
        fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                          texts[f["memory_unit_locator"]], f["n_tokens"],
                          f["domain"]) for f in fil]
        tgt = MemoryUnit(u["memory_id"], u["memory_unit_locator"], texts[loc],
                         u["n_tokens"], u["domain"])
        ctx, pos = build_context(tgt, fus, seed_parts=(tid, u["memory_id"]))
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user",
                 "content": f"{ctx}\n\n--- Question ---\n{task.question}"}]
        c, rec = client.chat(msgs, max_tokens=512, temperature=0.0,
                             reasoning_effort="low")
        p = extract_boxed_answer(c)
        rew = 0.0 if is_unknown(p) else float(task.score(p))
        # position must reproduce k2's, or this measures a position effect
        return {"row_id": r["row_id"], "memory_unit_locator": loc,
                "future_task_id": tid,
                "stratum": (r["provenance"] or {})["stratum"],
                "k2_position": (r["provenance"] or {}).get("target_position"),
                "now_position": pos,
                "k2_output": r["output_with_memory"], "now_output": c,
                "k2_reward": float(r["reward_with_memory"]), "now_reward": rew,
                "text_identical": c == r["output_with_memory"],
                "reward_identical": rew == float(r["reward_with_memory"])}

    log(f"issuing {len(plan)} cache-disabled calls at concurrency {args.workers} ...")
    t0 = time.monotonic()
    got = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool_x:
        futs = [pool_x.submit(one, it) for it in plan]
        for n, f in enumerate(as_completed(futs), 1):
            got.append(f.result())
            if n % 25 == 0:
                log(f"  {n}/{len(plan)}")
    wall = time.monotonic() - t0

    badpos = [g for g in got if g["k2_position"] != g["now_position"]]
    if badpos:
        raise SystemExit(
            f"{len(badpos)} cells landed the target at a DIFFERENT position than "
            f"k2 did; this probe would measure a position effect, not drift")
    n = len(got)
    nt = sum(1 for g in got if g["text_identical"])
    nr = sum(1 for g in got if g["reward_identical"])
    up = sum(1 for g in got if g["now_reward"] > g["k2_reward"])
    dn = sum(1 for g in got if g["now_reward"] < g["k2_reward"])
    mk = sum(g["k2_reward"] for g in got) / n
    mn = sum(g["now_reward"] for g in got) / n
    res = {
        "_what": "Raw WITH arm re-measured on 2026-09-30 against its 2026-09-29 "
                 "values, cache disabled, same filler, same target position "
                 "(asserted). Sizes the cross-session drift the paired "
                 "representation contrast is exposed to on its Raw side.",
        "run_at_utc": utc_now(), "wall_clock_s": round(wall, 2),
        "n_cells": n, "n_calls": n, "seed": args.seed,
        "target_position_reproduced": f"{n}/{n}",
        "text_identical": {"numerator": nt, "denominator": n, "rate": nt / n},
        "reward_identical": {"numerator": nr, "denominator": n, "rate": nr / n},
        "reward_changed": {"numerator": n - nr, "denominator": n,
                           "rate": (n - nr) / n, "now_higher": up, "k2_higher": dn},
        "mean_reward_with": {"k2_2026_09_29": mk, "now_2026_09_30": mn,
                             "difference_now_minus_k2": mn - mk},
        "by_stratum": {
            st: {"n": sum(1 for g in got if g["stratum"] == st),
                 "reward_changed": sum(1 for g in got
                                       if g["stratum"] == st
                                       and not g["reward_identical"])}
            for st in ("BEARING", "MATCHED_CONTROL")},
        "cells": got,
    }
    args.out.write_text(json.dumps(res, indent=2))
    log(f"text identical {nt}/{n}; REWARD identical {nr}/{n} "
        f"(changed {n-nr}: {up} up, {dn} down)")
    log(f"mean reward_with k2={mk:.4f} now={mn:.4f} diff={mn-mk:+.4f}")
    log(f"WROTE {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

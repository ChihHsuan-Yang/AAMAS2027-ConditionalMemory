#!/usr/bin/env python3
"""SciCode floor-effect pilot: WITH/WITHOUT on paired cells, real unit tests.

Leads with **both-arms-fail**, per the standing instruction. If that rate is
above 50% the run stops and the report diagnoses what binds rather than
spending more calls.

Protocol, unchanged from every other benchmark::

    past episode -> memory representation -> future task -> WITH/WITHOUT -> DeltaU -> cost

Design points that are not negotiable and are implemented, not asserted:

* **Both arms are identical except for the memory block.** Same reader, same
  decoding, same scaffold, same scoring function. ``render_task_prompt``
  takes the memory as its one varying argument.
* **Controlled filler in BOTH arms** (``MEMORY_PROTOCOL.md`` §4). The WITHOUT
  arm is not a no-context arm: it carries the same fixed set of other
  subproblem notes, with only the target memory removed. Measured on
  LongMemEval, omitting this answers a different question.
* **An unrunnable solution is an ERROR (``reward: None``), never 0.0.**
* **The writer never sees the future task** -- the representation writers take
  a ``SourceSegment`` and nothing else.

Run::

    /Users/bellayang/miniconda3/bin/python3 scripts/scicode_pilot.py --n-cells 12
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p1mem.adapters import scicode as S              # noqa: E402
from p1mem.client import P1Client                    # noqa: E402
from p1mem.memory.representations import (           # noqa: E402
    RawExtractiveWriter, StructuredWriter, SummaryWriter, render_structured,
    STRUCTURED_PROCEDURAL_KEYS, write_all,
)

CLUSTER = "metis"
MODEL = "gpt-oss-120b"
REASONING_EFFORT = "low"
TEMPERATURE = 0.0
READER_MAX_TOKENS = 1024          # 512 was too small for code (SWE-bench)
WRITER_MAX_TOKENS = 1024
CONCURRENCY = 16
SEED = 20261008

#: Number of OTHER memories placed in the context alongside the target, in
#: BOTH arms. Protocol §4: removal must be a local change.
FILLER_K = 2


def build_filler(memories, target_locator: str, k: int, seed: int) -> str:
    """A fixed set of other raw memories. Same in both arms of a cell.

    Drawn per-cell from a seed keyed by the target, so it is reproducible and
    does not depend on iteration order, and NEVER contains the target.
    """
    pool = sorted((m for m in memories
                   if m.memory_unit_locator != target_locator),
                  key=lambda m: m.memory_unit_locator)
    rng = random.Random(f"{seed}:filler:{target_locator}")
    picked = rng.sample(pool, min(k, len(pool))) if pool else []
    return "\n\n".join(m.episode_text for m in
                       sorted(picked, key=lambda m: m.memory_unit_locator))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/tmp/scicode_probe/problems_dev.jsonl")
    ap.add_argument("--test", default="/tmp/scicode_probe/problems_test.jsonl")
    ap.add_argument("--h5", default="/tmp/scicode_probe/test_data.h5")
    ap.add_argument("--scicode-src", default="/tmp/scicode_probe/SciCode/src")
    ap.add_argument("--workdir", default="/tmp/sci_harness/pilot")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--relatedness", default="lexical",
                    choices=[r.value for r in S.Relatedness])
    ap.add_argument("--n-cells", type=int, default=12)
    ap.add_argument("--tasks-per-memory", type=int, default=2)
    ap.add_argument("--representations", default="raw",
                    help="comma-separated subset of raw,summary,structured")
    ap.add_argument("--out", default=str(ROOT / "results/scicode/pilot.json"))
    a = ap.parse_args()

    reps = [r.strip() for r in a.representations.split(",") if r.strip()]
    dev_rows = S.load_jsonl(a.dev)
    test_rows = S.load_jsonl(a.test)
    memories = S.build_memory_units(dev_rows)
    tasks = S.build_future_tasks(test_rows)
    S.assert_writer_blind(memories, tasks)
    by_loc = {m.memory_unit_locator: m for m in memories}
    by_task = {t.task_id: t for t in tasks}

    pairs = S.select_pairs(
        memories, tasks, seed=SEED,
        tasks_per_memory=a.tasks_per_memory,
        relatedness=S.Relatedness(a.relatedness),
        min_tasks_per_memory=2)
    report = S.multi_task_report(pairs)
    print("selected design:", json.dumps(report))

    rng = random.Random(f"{SEED}:pilot_cells")
    chosen = pairs if len(pairs) <= a.n_cells else sorted(
        rng.sample(pairs, a.n_cells), key=lambda p: (p.memory_id, p.task_id))
    print(f"pilot cells: {len(chosen)} of {len(pairs)} design pairs")

    client = P1Client(cluster=CLUSTER, model=MODEL,
                      max_concurrency=CONCURRENCY, timeout_s=300)

    # ---------------- memory formation. NEVER sees a future task ----------
    raw_w = RawExtractiveWriter()
    sum_w = SummaryWriter(client, max_tokens=WRITER_MAX_TOKENS,
                          temperature=TEMPERATURE,
                          reasoning_effort=REASONING_EFFORT) if "summary" in reps else None
    str_w = StructuredWriter(client, variant="procedural",
                             max_tokens=WRITER_MAX_TOKENS,
                             temperature=TEMPERATURE,
                             reasoning_effort=REASONING_EFFORT) if "structured" in reps else None

    need = sorted({p.memory_unit_locator for p in chosen})
    written: dict[str, dict] = {}
    t_write = time.time()

    def _write(loc: str):
        seg = S.to_source_segment(by_loc[loc])
        return loc, write_all(seg, raw=raw_w, summary=sum_w, structured=str_w)

    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for loc, recs in ex.map(_write, need):
            written[loc] = recs
    write_s = time.time() - t_write
    print(f"memories written: {len(written)} in {write_s:.1f}s")

    def memory_text(loc: str, rep: str) -> str | None:
        rec = written[loc].get(rep)
        if rec is None or not rec.ok:
            return None
        if rep == "structured" and getattr(rec, "structured", None):
            return render_structured(rec.structured, STRUCTURED_PROCEDURAL_KEYS)
        return rec.memory_text

    # ---------------- the cells -------------------------------------------
    jobs = []
    for p in chosen:
        task = by_task[p.task_id]
        filler = build_filler(memories, p.memory_unit_locator, FILLER_K, SEED)
        for rep in reps:
            mtext = memory_text(p.memory_unit_locator, rep)
            jobs.append((p, rep, task, filler, mtext))

    def run_arm(job, arm: str):
        p, rep, task, filler, mtext = job
        block = mtext if arm == "with" else None
        if arm == "with" and mtext is None:
            return {"arm": arm, "reward": None, "kind": "memory_write_failed",
                    "error": True}
        prompt = S.render_task_prompt(task, block, filler=filler)
        try:
            content, rec = client.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=READER_MAX_TOKENS, temperature=TEMPERATURE,
                reasoning_effort=REASONING_EFFORT)
        except Exception as e:                                   # noqa: BLE001
            return {"arm": arm, "reward": None, "kind": "reader_call_failed",
                    "error": True, "detail": f"{type(e).__name__}: {e}"[:300]}
        res = S.score_solution(task, content, h5_path=a.h5,
                               scicode_src=a.scicode_src,
                               workdir=str(Path(a.workdir) / arm / rep),
                               python=a.python, timeout_s=300.0)
        return {"arm": arm, "reward": res.reward, "kind": res.kind,
                "error": res.is_error, "prompt_tokens": rec.input_tokens,
                "completion_tokens": rec.output_tokens,
                "finish_reason": rec.finish_reason,
                "latency_s": rec.latency_s,
                "response_chars": len(content or ""),
                "stderr_tail": res.stderr_tail[:200]}

    rows = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {}
        for job in jobs:
            for arm in ("without", "with"):
                futs[ex.submit(run_arm, job, arm)] = (job, arm)
        for fut in cf.as_completed(futs):
            job, arm = futs[fut]
            p, rep, task, _, _ = job
            r = fut.result()
            rows.append({"memory_id": p.memory_id, "task_id": p.task_id,
                         "representation": rep, "similarity": p.similarity,
                         "relatedness": p.relatedness, **r})
    run_s = time.time() - t0
    print(f"{len(rows)} arm-runs in {run_s:.1f}s")

    # ---------------- the gate: BOTH-ARMS-FAIL, first ---------------------
    cells: dict[tuple, dict] = {}
    for r in rows:
        cells.setdefault((r["memory_id"], r["task_id"], r["representation"]),
                         {})[r["arm"]] = r

    summary_by_rep: dict[str, dict] = {}
    for rep in reps:
        sub = {k: v for k, v in cells.items() if k[2] == rep}
        n_cells = len(sub)
        interp = {k: v for k, v in sub.items()
                  if v.get("with", {}).get("reward") is not None
                  and v.get("without", {}).get("reward") is not None}
        n_int = len(interp)
        baf = sum(1 for v in interp.values()
                  if v["with"]["reward"] == 0.0 and v["without"]["reward"] == 0.0)
        both_pass = sum(1 for v in interp.values()
                        if v["with"]["reward"] == 1.0 and v["without"]["reward"] == 1.0)
        deltas = [v["with"]["reward"] - v["without"]["reward"] for v in interp.values()]
        err_with = sum(1 for v in sub.values()
                       if v.get("with", {}).get("reward") is None)
        err_without = sum(1 for v in sub.values()
                          if v.get("without", {}).get("reward") is None)
        solved_without = sum(1 for v in sub.values()
                             if v.get("without", {}).get("reward") == 1.0)
        solved_with = sum(1 for v in sub.values()
                          if v.get("with", {}).get("reward") == 1.0)
        summary_by_rep[rep] = {
            "n_cells": n_cells,
            "n_interpretable": n_int,
            "both_arms_fail": baf,
            "both_arms_fail_rate": (baf / n_int) if n_int else None,
            "both_arms_fail_denominator": n_int,
            "both_arms_pass": both_pass,
            "errors_with_arm": err_with,
            "errors_without_arm": err_without,
            "solved_without_of_all_cells": f"{solved_without}/{n_cells}",
            "solved_with_of_all_cells": f"{solved_with}/{n_cells}",
            "mean_delta_u": (sum(deltas) / len(deltas)) if deltas else None,
            "delta_u_denominator": len(deltas),
            "n_helped": sum(1 for d in deltas if d > 0),
            "n_hurt": sum(1 for d in deltas if d < 0),
            "n_tied": sum(1 for d in deltas if d == 0),
            "error_kinds_with": _kinds(sub, "with"),
            "error_kinds_without": _kinds(sub, "without"),
        }

    out = {
        "config": {"cluster": CLUSTER, "model": MODEL,
                   "reasoning_effort": REASONING_EFFORT,
                   "temperature": TEMPERATURE,
                   "reader_max_tokens": READER_MAX_TOKENS,
                   "writer_max_tokens": WRITER_MAX_TOKENS,
                   "concurrency": CONCURRENCY, "seed": SEED,
                   "filler_k": FILLER_K,
                   "relatedness": a.relatedness,
                   "representations": reps,
                   "prompt_version": S.PROMPT_VERSION,
                   "benchmark_version": S.BENCHMARK_VERSION},
        "design": report,
        "n_calls": len(rows) + sum(
            1 for loc in written for rep in ("summary", "structured")
            if written[loc].get(rep) is not None),
        "write_seconds": write_s, "run_seconds": run_s,
        "summary_by_representation": summary_by_rep,
        "rows": rows,
    }
    p_out = Path(a.out)
    p_out.parent.mkdir(parents=True, exist_ok=True)
    p_out.write_text(json.dumps(out, indent=2))

    print("\n=== BOTH-ARMS-FAIL, reported first ===")
    for rep, s in summary_by_rep.items():
        rate = s["both_arms_fail_rate"]
        rs = "n/a (0 interpretable)" if rate is None else f"{rate:.3f}"
        print(f"  {rep:11s} both-arms-fail = {s['both_arms_fail']}/"
              f"{s['both_arms_fail_denominator']} = {rs}   "
              f"(errors with={s['errors_with_arm']} without={s['errors_without_arm']}, "
              f"cells={s['n_cells']})")
        print(f"              unaided solve {s['solved_without_of_all_cells']}, "
              f"with-memory {s['solved_with_of_all_cells']}, "
              f"mean dU={s['mean_delta_u']} over n={s['delta_u_denominator']}, "
              f"helped/hurt/tied={s['n_helped']}/{s['n_hurt']}/{s['n_tied']}")
    print(f"\nwritten: {p_out}")
    return 0


def _kinds(sub, arm):
    out = {}
    for v in sub.values():
        k = v.get(arm, {}).get("kind", "missing")
        out[k] = out.get(k, 0) + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())

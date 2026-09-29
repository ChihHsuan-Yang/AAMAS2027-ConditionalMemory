"""Measure the execution-noise floor on LongMemEval-V2 (PREREG section 2).

Three floors, on the delta-U scale (Amendment A1.2):
  F_exec   -- repeated identical cells across replicates
  F_empty  -- spread of the WITHOUT arm across independent draws (free)
  F_judge  -- re-scoring byte-identical outputs (expected ~0 for deterministic
              scorers; MEASURED, not assumed)
"""
from __future__ import annotations

import argparse, json, sys, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.cache import ResponseCache
from p1mem.cells import MemoryUnit, build_cell_pair, select_filler
from p1mem.client import P1Client
from p1mem.runner import Cell, RunLedger, Runner
from p1mem.adapters import lmev2


def load_units(path, limit=None):
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out.append(MemoryUnit(r["memory_id"], r["memory_unit_locator"],
                              r.get("text") or "", int(r.get("n_tokens") or 0), r["domain"]))
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=12)
    ap.add_argument("--replicates", type=int, default=4)
    ap.add_argument("--k-filler", type=int, default=4)
    ap.add_argument("--max-unit-tokens", type=int, default=12000)
    ap.add_argument("--out", default=str(REPO / "results" / "runs" / "noise_floor"))
    a = ap.parse_args()

    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    qs = {}
    for line in Path("/tmp/lmev2/questions.jsonl").read_text().splitlines():
        if line.strip():
            q = json.loads(line)
            if not q["eval_function"].startswith("llm_"):
                qs[q["id"]] = q

    units = load_units(REPO / "data/manifests/lmev2_memory_units_small.jsonl")
    # keep units small enough that K+1 fit comfortably in the window
    units = [u for u in units if 0 < u.n_tokens <= a.max_unit_tokens]
    print(f"deterministic questions: {len(qs)} | usable units: {len(units)}", flush=True)

    # need unit TEXT; the manifest stores only metadata, so rebuild from source
    text_by_loc = {}
    want = {u.memory_unit_locator for u in units}
    for traj in lmev2.read_jsonl("/tmp/lmev2/trajectories.jsonl"):
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator in want:
                text_by_loc[pv.memory_unit_locator] = pv.text
        if len(text_by_loc) >= len(want):
            break
    units = [MemoryUnit(u.memory_id, u.memory_unit_locator,
                        text_by_loc.get(u.memory_unit_locator, ""), u.n_tokens, u.domain)
             for u in units if text_by_loc.get(u.memory_unit_locator)]
    print(f"units with text recovered: {len(units)}", flush=True)
    if not units:
        sys.exit("no unit text recovered -- aborting rather than measuring nothing")

    task_ids = sorted(qs)[: a.tasks]
    by_domain = {}
    for u in units:
        by_domain.setdefault(u.domain, []).append(u)

    cells = []
    for tid in task_ids:
        q = qs[tid]
        dom = "web" if q["domain"] == "web" else "enterprise"
        pool = by_domain.get(dom) or units
        if len(pool) < a.k_filler + 1:
            continue
        target = pool[0]
        filler = select_filler(pool, exclude_ids={target.memory_id},
                               k=a.k_filler, task_id=tid)
        for rep in range(a.replicates):
            for c in build_cell_pair(target=target, filler=filler, task_id=tid,
                                     question=q["question"], replicate_id=rep):
                cells.append(Cell(cell_id=c["cell_id"], messages=c["messages"],
                                  key_fields=c["key_fields"]))

    print(f"cells to run: {len(cells)}", flush=True)
    cache = ResponseCache(outdir / "cache.jsonl")
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache, max_concurrency=16)
    ledger = RunLedger(outdir / "ledger.jsonl")
    runner = Runner(client=client, ledger=ledger, max_workers=16)
    runner.run(cells)
    print("run complete; ledger:", outdir / "ledger.jsonl", flush=True)


if __name__ == "__main__":
    main()

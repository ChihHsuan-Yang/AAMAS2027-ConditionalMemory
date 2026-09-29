#!/usr/bin/env python3
"""J3: is any slice of LongMemEval-V2 tractable enough to restrict to?

Solve rates by domain, question_type, eval_function, and their cross, with
DENOMINATORS on every cell. Restricting to a tractable slice is far cheaper
than changing readers, so this runs before any call is spent.

Both arms are reported. Every rate is PAIRED: WITH and WITHOUT are computed
over the SAME cells inside each group, never two rates over two different sets
(the project has logged that error twice).

Reads artifacts, writes artifacts. No endpoint calls.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402

ARMS = {
    "official": REPO / "results/deltau_official/cells.jsonl",
    "handwritten": REPO / "results/deltau_pilot/cells.jsonl",
}


def cellify(rows):
    out = collections.defaultdict(list)
    for r in rows:
        if not r.get("error_code_if_any"):
            out[(r["memory_id"], r["future_task_id"])].append(r)
    return out


def group_stats(cells, keyfn, label):
    g = collections.defaultdict(list)
    for k, v in cells.items():
        g[keyfn(v[0])].append(k)
    out = {}
    for lvl, keys in sorted(g.items(), key=lambda kv: str(kv[0])):
        n = len(keys)
        w = sum(sum(float(x["reward_with_memory"]) for x in cells[k]) / len(cells[k]) for k in keys)
        o = sum(sum(float(x["reward_without_memory"]) for x in cells[k]) / len(cells[k]) for k in keys)
        bf = sum(1 for k in keys
                 if max(max(float(x["reward_with_memory"]), float(x["reward_without_memory"]))
                        for x in cells[k]) == 0.0)
        _, wlo, whi = wilson_ci(round(w), n)
        out[str(lvl)] = {
            "n_cells": n,
            "n_correct_with": round(w), "acc_with": w / n, "acc_with_wilson": [wlo, whi],
            "n_correct_without": round(o), "acc_without": o / n,
            "delta": (w - o) / n,
            "both_arms_fail": bf, "both_arms_fail_rate": bf / n,
        }
    return {"grouping": label, "levels": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/j3_tractable_slice.json")
    args = ap.parse_args()

    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    payload = {"_what": "J3: solve rate by domain / question_type / eval_function",
               "_paired": "WITH and WITHOUT are over the SAME cells in every group",
               "arms": {}}

    for tag, path in ARMS.items():
        rows = load_jsonl(path)
        cells = cellify(rows)
        T = lambda r: tasks[r["future_task_id"]]  # noqa: E731
        arm = {
            "rows_artifact": str(path), "n_live_cells": len(cells),
            "by_domain": group_stats(cells, lambda r: T(r).domain, "domain"),
            "by_question_type": group_stats(cells, lambda r: T(r).question_type, "question_type"),
            "by_eval_function": group_stats(cells, lambda r: T(r).eval_name, "eval_function"),
            "by_environment": group_stats(cells, lambda r: T(r).environment, "task_environment"),
            "by_domain_x_qtype": group_stats(
                cells, lambda r: f"{T(r).domain}|{T(r).question_type}", "domain x question_type"),
            "by_qtype_x_eval": group_stats(
                cells, lambda r: f"{T(r).question_type}|{T(r).eval_name}", "question_type x eval"),
        }
        payload["arms"][tag] = arm

        print(f"\n################ {tag}  (n_live_cells={len(cells)}) ################")
        for gk in ("by_domain", "by_question_type", "by_eval_function",
                   "by_environment", "by_qtype_x_eval"):
            print(f"\n-- {arm[gk]['grouping']}")
            for lvl, d in sorted(arm[gk]["levels"].items(),
                                 key=lambda kv: -kv[1]["acc_with"]):
                print(f"   {lvl:42s} n={d['n_cells']:4d} "
                      f"accW={d['acc_with']:.4f} [{d['acc_with_wilson'][0]:.3f},"
                      f"{d['acc_with_wilson'][1]:.3f}] "
                      f"accWO={d['acc_without']:.4f} d={d['delta']:+.4f} "
                      f"bothfail={d['both_arms_fail']}/{d['n_cells']}"
                      f"={d['both_arms_fail_rate']:.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, payload)
    print(f"\n[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

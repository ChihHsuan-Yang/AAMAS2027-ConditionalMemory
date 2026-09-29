#!/usr/bin/env python3
"""H4: if both-arms-fail is still dominant, diagnose WHY instead of spending more calls.

Three candidate causes, each with a test that can distinguish it:

1. **The memory unit does not bear on the task.** Tested with the leakage
   flag as an ORACLE-BEARING subgroup: ``leakage_flag=True`` means the
   memory's own text literally contains the gold answer string, so the
   information needed IS in the WITH context. If the WITH arm still fails
   there, "the paired memory rarely bears on the task" cannot be the whole
   story.
2. **The task is too hard for the reader regardless of context.** Tested
   against the WITHOUT arm's ceiling and against per-eval-function and
   per-question-type breakdowns.
3. **The retrieval/context design buries the memory.** Tested against target
   position and context length.

⚠️ CIRCULARITY WARNING, stated up front. Cause (1)'s subgroup is defined by
the memory's CONTENT, not by any outcome, so it is not a selected subgroup.
But "cells where at least one arm succeeded" IS selected on the outcome, and
any rate computed on it is circular. This script reports that restriction only
as a diagnostic and never as a result -- the same discipline PILOT_VERDICT §3
applies.

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


def cells_of(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        if not r.get("error_code_if_any"):
            out[(r["memory_id"], r["future_task_id"])].append(r)
    return out


def _mean(vals) -> float:
    vals = list(vals)
    return sum(vals) / len(vals) if vals else float("nan")


def breakdown(cells, keyfn, label: str) -> dict:
    """Both-arms-fail and per-arm accuracy within each level of a grouping.

    Always paired: the two arms are computed over the SAME cells inside each
    group, so a group's numbers are never two rates over two different sets.
    """
    g = collections.defaultdict(list)
    for k, v in cells.items():
        g[keyfn(v[0])].append(v)
    out = {}
    for lvl, group in sorted(g.items(), key=lambda kv: str(kv[0])):
        n = len(group)
        w = _mean(_mean(float(x["reward_with_memory"]) for x in v) for v in group)
        o = _mean(_mean(float(x["reward_without_memory"]) for x in v) for v in group)
        bf = sum(1 for v in group
                 if max(max(float(x["reward_with_memory"]),
                            float(x["reward_without_memory"])) for x in v) == 0.0)
        out[str(lvl)] = {
            "n_cells": n, "mean_reward_with": w, "mean_reward_without": o,
            "delta": w - o, "both_arms_fail": bf, "both_arms_fail_fraction": bf / n,
        }
    return {"grouping": label, "levels": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_official/cells.jsonl")
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/deltau_official/analysis")
    ap.add_argument("--tag", default="official")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(args.rows)
    cells = cells_of(rows)
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    print(f"[rows] {len(rows)}  live cells {len(cells)}")

    n_bf = sum(1 for v in cells.values()
               if max(max(float(x["reward_with_memory"]),
                          float(x["reward_without_memory"])) for x in v) == 0.0)
    rate, lo, hi = wilson_ci(n_bf, len(cells))

    payload: dict = {
        "rows_artifact": str(args.rows),
        "n_cells": len(cells),
        "both_arms_fail": n_bf,
        "both_arms_fail_rate": rate, "wilson_lo": lo, "wilson_hi": hi,
        "_circularity_warning":
            "cause (1)'s ORACLE-BEARING subgroup is defined by memory CONTENT, not by "
            "any outcome, so it is not a selected subgroup. 'cells where at least one "
            "arm succeeded' IS selected on the outcome and any rate on it is circular; "
            "it is reported here only as a diagnostic, never as a result.",
    }

    # ---- cause 1: does the memory bear on the task at all?
    payload["cause_1_memory_bears_on_task"] = {
        "_test": "leakage_flag=True means the memory's own text literally contains the "
                 "gold answer, so the WITH context provably CONTAINS the needed "
                 "information. If the WITH arm still fails there, an irrelevant pairing "
                 "cannot be the whole explanation.",
        **breakdown(cells, lambda r: r.get("leakage_flag"), "leakage_flag"),
    }

    # ---- cause 2: task difficulty
    payload["cause_2_task_difficulty"] = {
        "by_eval_function": breakdown(
            cells, lambda r: tasks[r["future_task_id"]].eval_name, "eval_function"),
        "by_question_type": breakdown(
            cells, lambda r: tasks[r["future_task_id"]].question_type, "question_type"),
        "by_domain": breakdown(
            cells, lambda r: r["source_episode_metadata"]["domain"], "domain"),
    }

    # ---- cause 3: the context design
    payload["cause_3_context_design"] = {
        "by_target_position": breakdown(
            cells, lambda r: r["provenance"].get("target_position"), "target_position"),
        "by_similarity_band": breakdown(
            cells, lambda r: r["semantic_distance_band"], "semantic_distance_band"),
        "by_context_length_quartile": None,   # filled below
    }
    lens = sorted(int(v[0]["input_tokens"]) for v in cells.values())
    if lens:
        qs = [lens[len(lens) // 4], lens[len(lens) // 2], lens[3 * len(lens) // 4]]

        def qband(r):
            n = int(r["input_tokens"])
            return ("Q1" if n < qs[0] else "Q2" if n < qs[1]
                    else "Q3" if n < qs[2] else "Q4")

        payload["cause_3_context_design"]["by_context_length_quartile"] = {
            "cuts": qs, **breakdown(cells, qband, "input_tokens_quartile")}

    # ---- abstention, cross-tabbed against reward (the H1 interpretation point)
    tab = collections.Counter()
    for v in cells.values():
        for x in v:
            p = x.get("provenance", {})
            for arm, uf, rf in (("with", "is_unknown_with", "reward_with_memory"),
                                ("without", "is_unknown_without", "reward_without_memory")):
                tab[(arm, p.get(uf), float(x[rf]))] += 1
    payload["abstention_x_reward"] = {
        f"{a}|is_unknown={u}|reward={r}": n for (a, u, r), n in sorted(
            tab.items(), key=lambda kv: str(kv[0]))}

    out = args.out / f"11_floor_diagnosis_{args.tag}.json"
    write_json_atomic(out, payload)

    print(f"\nBOTH-ARMS-FAIL {n_bf}/{len(cells)} = {rate:.4f} [{lo:.4f}, {hi:.4f}]")
    for name in ("cause_1_memory_bears_on_task",):
        for lvl, d in payload[name]["levels"].items():
            print(f"  leakage_flag={lvl:>5}: cells={d['n_cells']:4d} "
                  f"WITH={d['mean_reward_with']:.4f} WITHOUT={d['mean_reward_without']:.4f} "
                  f"bothfail={d['both_arms_fail_fraction']:.4f}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

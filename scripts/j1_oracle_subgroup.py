#!/usr/bin/env python3
"""J1: the oracle-bearing subgroup, recomputed from memory CONTENT.

The stored ``leakage_flag`` on each row is NOT trusted. It is RE-DERIVED here
from ``memory_text`` + the task's gold answer via ``p1mem.adapters.leakage``,
and the re-derivation is diffed against the stored flag. A subgroup defined by
the memory's CONTENT is not selected on any outcome -- unlike "cells where at
least one arm succeeded", which is circular. That distinction is the whole
reason this subgroup can answer the reader-vs-task question.

Also reports J3: solve rates by domain and by question_type, with denominators.

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

from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402


def cellify(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        if not r.get("error_code_if_any"):
            out[(r["memory_id"], r["future_task_id"])].append(r)
    return out


def arm_stats(cells: dict, keys) -> dict:
    """Paired stats over an explicit key list. WITH/WITHOUT over the SAME cells."""
    keys = list(keys)
    n = len(keys)
    if n == 0:
        return {"n_cells": 0}
    w = o = 0
    bf = 0
    for k in keys:
        v = cells[k]
        mw = max(float(x["reward_with_memory"]) for x in v)
        mo = max(float(x["reward_without_memory"]) for x in v)
        # cell accuracy = mean over replicates (replicates are byte-identical)
        cw = sum(float(x["reward_with_memory"]) for x in v) / len(v)
        co = sum(float(x["reward_without_memory"]) for x in v) / len(v)
        w += cw
        o += co
        if max(mw, mo) == 0.0:
            bf += 1
    aw, awlo, awhi = wilson_ci(round(w), n)
    ao, aolo, aohi = wilson_ci(round(o), n)
    bfr, bflo, bfhi = wilson_ci(bf, n)
    return {
        "n_cells": n,
        "acc_with": w / n, "acc_with_wilson": [awlo, awhi], "n_correct_with": round(w),
        "acc_without": o / n, "acc_without_wilson": [aolo, aohi], "n_correct_without": round(o),
        "delta": (w - o) / n,
        "both_arms_fail": bf, "both_arms_fail_rate": bfr,
        "both_arms_fail_wilson": [bflo, bfhi],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path, default=REPO / "results/ledgers/j1_oracle_subgroup.json")
    args = ap.parse_args()

    # controls FIRST -- never report a leakage rate from an unproven detector
    ok, ctrl = LK.controls_summary()
    if not ok:
        print("[FATAL] leakage detector controls FAILED", file=sys.stderr)
        for c in ctrl:
            if not c.passed:
                print(f"  {c}", file=sys.stderr)
        return 2
    print(f"[controls] leakage detector: {sum(c.passed for c in ctrl)}/{len(ctrl)} PASS")

    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    payload: dict = {
        "_what": "J1 oracle-bearing subgroup, leakage RE-DERIVED from memory_text",
        "_not_selected_on_outcome":
            "the subgroup is defined by whether memory_text literally contains the gold "
            "answer -- a property of the CONTENT. No reward enters its definition. It is "
            "therefore NOT a selected subgroup; 'cells where at least one arm succeeded' "
            "would be, and is not used here.",
        "leakage_detector_controls": {"n": len(ctrl), "all_passed": ok},
        "arms": {},
    }

    for tag, path in [("official", REPO / "results/deltau_official/cells.jsonl"),
                      ("handwritten", REPO / "results/deltau_pilot/cells.jsonl")]:
        rows = load_jsonl(path)
        cells = cellify(rows)
        # --- re-derive leakage per cell from content
        rederived: dict[tuple[str, str], object] = {}
        detail: dict[tuple[str, str], dict] = {}
        for k, v in cells.items():
            r0 = v[0]
            t = tasks[r0["future_task_id"]]
            verdict = LK.detect(r0["memory_text"], t.answer,
                                memory_id=r0["memory_id"], task_id=t.id,
                                eval_function_spec=t.eval_function)
            flag = None if verdict.undecidable else bool(verdict.any_leak)
            rederived[k] = flag
            detail[k] = {
                "exact": verdict.exact, "normalized": verdict.normalized,
                "normalized_partial": verdict.normalized_partial,
                "numeric": verdict.numeric, "official": verdict.official,
                "undecidable": verdict.undecidable,
            }
        # --- diff against stored
        stored = {k: v[0].get("leakage_flag") for k, v in cells.items()}
        mismatch = [k for k in cells if stored[k] != rederived[k]]
        oracle = [k for k in cells if rederived[k] is True]
        clean = [k for k in cells if rederived[k] is False]
        undec = [k for k in cells if rederived[k] is None]

        # detector-wise counts within the oracle subgroup
        det_counts = collections.Counter()
        for k in oracle:
            d = detail[k]
            det_counts["exact"] += bool(d["exact"])
            det_counts["normalized"] += bool(d["normalized"])
            det_counts["numeric_only"] += bool(
                d["numeric"] and not d["exact"] and not d["normalized"] and not d["official"])
            det_counts["official"] += bool(d["official"])

        arm = {
            "rows_artifact": str(path),
            "n_rows": len(rows), "n_live_cells": len(cells),
            "stored_vs_rederived_mismatches": len(mismatch),
            "mismatch_examples": [list(k) for k in mismatch[:10]],
            "n_oracle_bearing": len(oracle),
            "n_clean": len(clean),
            "n_undecidable": len(undec),
            "oracle_detector_counts": dict(det_counts),
            "ORACLE_BEARING": arm_stats(cells, oracle),
            "CLEAN": arm_stats(cells, clean),
            "ALL": arm_stats(cells, list(cells)),
        }
        payload["arms"][tag] = arm
        print(f"\n=== {tag} ({path}) ===")
        print(f"  rows={len(rows)} live_cells={len(cells)} "
              f"stored-vs-rederived mismatches={len(mismatch)}")
        print(f"  oracle-bearing={len(oracle)}  clean={len(clean)}  undecidable={len(undec)}")
        print(f"  detectors firing in oracle subgroup: {dict(det_counts)}")
        for sub in ("ORACLE_BEARING", "CLEAN", "ALL"):
            s = arm[sub]
            print(f"  {sub:14s} n={s['n_cells']:4d} "
                  f"accWITH={s['acc_with']:.4f} accWITHOUT={s['acc_without']:.4f} "
                  f"bothfail={s['both_arms_fail']}/{s['n_cells']}={s['both_arms_fail_rate']:.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, payload)
    print(f"\n[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""J1b: a DISCRIMINATIVE oracle-bearing subgroup, and the control that shows why.

DEFECT FIXED HERE
-----------------
``leakage_flag`` (as shipped, = ``LeakVerdict.any_leak``) fires on a same-domain
memory the task was NEVER paired with at the same rate as on the paired one
(0.3224 vs 0.3208, ratio 0.995 -- see ``j1_mismatch_control`` below). It is
therefore ~uninformative about whether THIS memory bears on THIS task. The
cause is measured, not guessed: 96 of its 154 cells have a one-character
multiple-choice gold answer, and the literal "A" occurs in 60 of 60 memory
texts in this corpus.

The repair is not a stricter string match -- ``official``-scorer-positive is
also only 1.15x enriched. The repair is to make the subgroup DISCRIMINATIVE by
construction: for each task, run the detector against every same-domain memory,
and keep the cell only when the detector singles this memory out (fires on at
most ``--max-pool-hits`` of the pool). A detector that fires on 24 of 24
memories has said nothing about any of them.

The definition still uses only CONTENT (memory text, gold answer) and never a
reward, so the subgroup is NOT selected on the outcome.

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


def stats(cells, keys) -> dict:
    keys = list(keys)
    n = len(keys)
    if n == 0:
        return {"n_cells": 0}
    w = sum(sum(float(x["reward_with_memory"]) for x in cells[k]) / len(cells[k]) for k in keys)
    o = sum(sum(float(x["reward_without_memory"]) for x in cells[k]) / len(cells[k]) for k in keys)
    bf = sum(1 for k in keys
             if max(max(float(x["reward_with_memory"]), float(x["reward_without_memory"]))
                    for x in cells[k]) == 0.0)
    _, wlo, whi = wilson_ci(round(w), n)
    _, olo, ohi = wilson_ci(round(o), n)
    _, blo, bhi = wilson_ci(bf, n)
    return {
        "n_cells": n,
        "n_correct_with": round(w), "acc_with": w / n, "acc_with_wilson": [wlo, whi],
        "n_correct_without": round(o), "acc_without": o / n, "acc_without_wilson": [olo, ohi],
        "delta": (w - o) / n,
        "both_arms_fail": bf, "both_arms_fail_rate": bf / n,
        "both_arms_fail_wilson": [blo, bhi],
        "cell_keys": [list(k) for k in keys] if n <= 80 else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--max-pool-hits", type=int, default=5)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/j1b_discriminative_oracle.json")
    args = ap.parse_args()

    ok, ctrl = LK.controls_summary()
    if not ok:
        print("[FATAL] leakage controls failed", file=sys.stderr)
        return 2
    print(f"[controls] in-module planted-text controls: {len(ctrl)}/{len(ctrl)} PASS "
          "(they prove the detector FIRES on a plant; they do not test discrimination)")

    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    payload: dict = {
        "_what": "discriminative oracle-bearing subgroup + mismatch control",
        "_definition_is_content_only":
            "membership depends on memory_text and the gold answer only. No reward "
            "enters. It is NOT a subgroup selected on the outcome.",
        "max_pool_hits": args.max_pool_hits,
        "arms": {},
    }

    for tag, path in ARMS.items():
        rows = load_jsonl(path)
        cells = cellify(rows)
        memtext, memdom = {}, {}
        for k, v in cells.items():
            memtext[v[0]["memory_id"]] = v[0]["memory_text"]
            memdom[v[0]["memory_id"]] = v[0]["source_episode_metadata"]["domain"]
        taskdom = {v[0]["future_task_id"]: v[0]["source_episode_metadata"]["domain"]
                   for v in cells.values()}

        # per task: which same-domain memories does the detector fire on?
        fired: dict[str, dict[str, bool]] = {}
        for tid in {k[1] for k in cells}:
            t = tasks[tid]
            pool = [m for m in memtext if memdom[m] == taskdom[tid]]
            fired[tid] = {
                m: bool(LK.detect(memtext[m], t.answer,
                                  eval_function_spec=t.eval_function).any_leak)
                for m in pool
            }

        # --- MISMATCH CONTROL: paired vs never-paired firing rate
        paired = set(cells)
        np_, npl, nu, nul = 0, 0, 0, 0
        for tid, fm in fired.items():
            for mid, hit in fm.items():
                if (mid, tid) in paired:
                    np_ += 1; npl += hit
                else:
                    nu += 1; nul += hit
        mismatch = {
            "paired_fires": npl, "paired_n": np_, "paired_rate": npl / np_,
            "unpaired_same_domain_fires": nul, "unpaired_n": nu, "unpaired_rate": nul / nu,
            "enrichment_ratio": (npl / np_) / (nul / nu) if nul else None,
            "_reading": "a ratio near 1.0 means the flag says nothing about THIS pairing",
        }

        flagged = [k for k in cells if fired[k[1]][k[0]]]
        pool_hits = {k: sum(fired[k[1]].values()) for k in flagged}
        hist = collections.Counter(pool_hits.values())
        disc = [k for k in flagged if pool_hits[k] <= args.max_pool_hits]

        arm = {
            "rows_artifact": str(path),
            "n_live_cells": len(cells),
            "mismatch_control": mismatch,
            "pool_hit_histogram": {str(k): v for k, v in sorted(hist.items())},
            "pool_sizes": dict(collections.Counter(len(fired[k[1]]) for k in flagged)),
            "ALL_CELLS": stats(cells, list(cells)),
            "ORACLE_AS_SHIPPED": stats(cells, flagged),
            "NON_FLAGGED": stats(cells, [k for k in cells if not fired[k[1]][k[0]]]),
            "sweep": {},
        }
        for thr in (1, 2, 3, 5, 8, 12):
            arm["sweep"][f"max_pool_hits<={thr}"] = stats(
                cells, [k for k in flagged if pool_hits[k] <= thr])
        arm["DISCRIMINATIVE_ORACLE"] = stats(cells, disc)
        payload["arms"][tag] = arm

        print(f"\n=== {tag} ===  live cells {len(cells)}")
        print(f"  MISMATCH CONTROL  paired {npl}/{np_}={npl/np_:.4f}  "
              f"never-paired {nul}/{nu}={nul/nu:.4f}  "
              f"enrichment={mismatch['enrichment_ratio']:.3f}")
        for name in ("ALL_CELLS", "ORACLE_AS_SHIPPED", "NON_FLAGGED"):
            s = arm[name]
            print(f"  {name:22s} n={s['n_cells']:4d} accW={s['acc_with']:.4f} "
                  f"accWO={s['acc_without']:.4f} bothfail={s['both_arms_fail_rate']:.4f}")
        for thr in (1, 2, 3, 5, 8, 12):
            s = arm["sweep"][f"max_pool_hits<={thr}"]
            if s["n_cells"]:
                print(f"  discriminative<={thr:<2d}       n={s['n_cells']:4d} "
                      f"accW={s['acc_with']:.4f} {s['acc_with_wilson']} "
                      f"accWO={s['acc_without']:.4f} bothfail={s['both_arms_fail_rate']:.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, payload)
    print(f"\n[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

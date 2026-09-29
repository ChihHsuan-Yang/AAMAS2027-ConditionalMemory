#!/usr/bin/env python3
"""J2 analysis: does a stronger reader lift the oracle-bearing cells?

Reads results/j2_escalation/responses.jsonl and answers, per configuration:

 * the ORACLE lift vs the base replication, PAIRED per cell (McNemar exact),
 * the CONTROL lift over the same comparison -- so "the reader got better"
   can be told apart from "these cells are easier",
 * the difference-in-differences (oracle lift minus control lift),
 * the positive control, so a null is never reported from an instrument that
   was not shown capable of registering a 1,
 * a REPLICATION check of base_replication against the recorded official arm.
   If the base config does not reproduce the completed run's rewards on these
   cells, every comparison below it is void and this says so.

Reads artifacts, writes artifacts. No endpoint calls.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial McNemar on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resp", type=Path,
                    default=REPO / "results/j2_escalation/responses.jsonl")
    ap.add_argument("--official", type=Path,
                    default=REPO / "results/deltau_official/cells.jsonl")
    ap.add_argument("--base", default="base_replication")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/j2_analysis.json")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.resp)]
    idx = {(r["config"], r["group"], r["memory_id"], r["task_id"], r["arm"]): r
           for r in rows}
    configs, groups = [], set()
    for r in rows:
        if r["config"] not in configs:
            configs.append(r["config"])
        groups.add(r["group"])
    cellkeys = collections.defaultdict(set)
    for r in rows:
        if r["group"] in ("oracle", "control"):
            cellkeys[r["group"]].add((r["memory_id"], r["task_id"]))

    payload: dict = {"_what": "J2: does a stronger reader lift oracle-bearing cells?",
                     "responses_artifact": str(args.resp),
                     "configs": configs,
                     "n_oracle": len(cellkeys["oracle"]),
                     "n_control": len(cellkeys["control"]),
                     "positive_control": {}, "per_config": {},
                     "replication_check": {}, "paired_vs_base": {}}

    # ---- positive control, first: a null from an unproven harness is nothing
    print("=== POSITIVE CONTROL (must be reward 1.0) ===")
    for c in configs:
        pc = [r for r in rows if r["config"] == c and r["group"] == "positive_control"]
        v = pc[0] if pc else None
        payload["positive_control"][c] = {
            "reward": v["reward"] if v else None,
            "content": (v["content"] or "")[:160] if v else None,
            "error": v["error"] if v else "MISSING",
        }
        print(f"  {c:20s} reward={v['reward'] if v else None}  "
              f"content={(v['content'] or '')[:70]!r}" if v else f"  {c}: MISSING")

    # ---- replication: base config vs the recorded official arm, same cells
    off = collections.defaultdict(list)
    for r in load_jsonl(args.official):
        if not r.get("error_code_if_any"):
            off[(r["memory_id"], r["future_task_id"])].append(r)
    agree = dis = miss = 0
    disagreements = []
    for group in ("oracle", "control"):
        for k in sorted(cellkeys[group]):
            for arm, field in (("with_memory", "reward_with_memory"),
                               ("without_memory", "reward_without_memory")):
                new = idx.get((args.base, group, k[0], k[1], arm))
                if not new or new["reward"] is None or k not in off:
                    miss += 1
                    continue
                old = sum(float(x[field]) for x in off[k]) / len(off[k])
                if abs(old - new["reward"]) < 1e-9:
                    agree += 1
                else:
                    dis += 1
                    disagreements.append(
                        {"cell": list(k), "arm": arm, "recorded": old,
                         "replicated": new["reward"]})
    payload["replication_check"] = {
        "_what": f"config {args.base!r} re-issued now vs the recorded official arm",
        "agree": agree, "disagree": dis, "missing": miss,
        "agreement_rate": agree / (agree + dis) if (agree + dis) else None,
        "disagreements": disagreements[:40],
        "_reading": "the base config is byte-identical to the completed arm. Material "
                    "disagreement means the endpoint has drifted and every comparison "
                    "below is against a moving anchor.",
    }
    print(f"\n=== REPLICATION: {args.base} vs recorded official arm ===")
    print(f"  agree={agree} disagree={dis} missing={miss} "
          f"rate={payload['replication_check']['agreement_rate']}")
    for d in disagreements[:10]:
        print(f"    {d['cell']} {d['arm']}: recorded {d['recorded']} -> {d['replicated']}")

    # ---- per-config accuracy
    print("\n=== PER-CONFIG (paired WITH/WITHOUT over the same cells) ===")
    for c in configs:
        payload["per_config"][c] = {}
        for group in ("oracle", "control"):
            n = w = o = bf = unk = 0
            for k in sorted(cellkeys[group]):
                rw = idx.get((c, group, k[0], k[1], "with_memory"))
                ro = idx.get((c, group, k[0], k[1], "without_memory"))
                if not rw or not ro or rw["reward"] is None or ro["reward"] is None:
                    continue
                n += 1; w += rw["reward"]; o += ro["reward"]
                unk += bool(rw["is_unknown"])
                if max(rw["reward"], ro["reward"]) == 0.0:
                    bf += 1
            if not n:
                payload["per_config"][c][group] = {"n_cells": 0}
                continue
            _, wlo, whi = wilson_ci(round(w), n)
            payload["per_config"][c][group] = {
                "n_cells": n, "n_correct_with": round(w), "acc_with": w / n,
                "acc_with_wilson": [wlo, whi],
                "n_correct_without": round(o), "acc_without": o / n,
                "delta_with_minus_without": (w - o) / n,
                "both_arms_fail": bf, "both_arms_fail_rate": bf / n,
                "abstentions_with": unk,
            }
            s = payload["per_config"][c][group]
            print(f"  {c:20s} {group:8s} n={n:3d} accW={w/n:.4f} "
                  f"[{wlo:.3f},{whi:.3f}] accWO={o/n:.4f} "
                  f"dU={(w-o)/n:+.4f} bothfail={bf}/{n} abstainW={unk}")

    # ---- paired lift vs base, per group, + difference-in-differences
    print("\n=== PAIRED LIFT vs base, WITH-arm, McNemar exact ===")
    for c in configs:
        if c == args.base:
            continue
        payload["paired_vs_base"][c] = {}
        lifts = {}
        for group in ("oracle", "control"):
            b = cc = both = neither = n = 0
            for k in sorted(cellkeys[group]):
                rb = idx.get((args.base, group, k[0], k[1], "with_memory"))
                rn = idx.get((c, group, k[0], k[1], "with_memory"))
                if not rb or not rn or rb["reward"] is None or rn["reward"] is None:
                    continue
                n += 1
                ob, on = rb["reward"] > 0, rn["reward"] > 0
                if ob and not on: b += 1
                elif on and not ob: cc += 1
                elif ob and on: both += 1
                else: neither += 1
            p = mcnemar_exact(b, cc)
            lift = (cc - b) / n if n else float("nan")
            lifts[group] = lift
            payload["paired_vs_base"][c][group] = {
                "n_paired_cells": n,
                "base_only_correct": b, "new_only_correct": cc,
                "both_correct": both, "neither_correct": neither,
                "lift_in_accuracy": lift, "mcnemar_exact_p": p,
            }
            print(f"  {c:20s} {group:8s} n={n:3d} base-only={b:2d} new-only={cc:2d} "
                  f"both={both:2d} neither={neither:2d} lift={lift:+.4f} p={p:.4g}")
        if "oracle" in lifts and "control" in lifts:
            did = lifts["oracle"] - lifts["control"]
            payload["paired_vs_base"][c]["difference_in_differences"] = {
                "oracle_lift": lifts["oracle"], "control_lift": lifts["control"],
                "did": did,
                "_reading": "a positive DiD means the stronger reader helps MORE where "
                            "the answer is demonstrably present -- the reader-limited "
                            "signature. A DiD near zero with both lifts positive means "
                            "the reader improved everywhere.",
            }
            print(f"  {c:20s} DiD (oracle-control) = {did:+.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, payload)
    print(f"\n[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

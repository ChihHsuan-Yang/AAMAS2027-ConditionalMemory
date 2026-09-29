#!/usr/bin/env python3
"""H3: the official-prompt arm, reported with denominators, and compared to the
hand-written arm on the SAME cells.

Reads artifacts, writes artifacts. **No endpoint calls.**

What this adds over ``scripts/g_floors_and_flips.py``
-----------------------------------------------------
* the **both-arms-fail** count -- the diagnostic that decides whether the
  instrument can detect a memory effect at all (H2/H4);
* **abstention counts per arm, reported separately from reward**, because the
  official scoring rule forces an abstention to score 0 exactly like a wrong
  answer (``harness.py:1055``), so a cell can move wrong -> abstain with no
  change in reward;
* a **paired** arm-vs-arm comparison restricted to the cells both arms ran,
  rather than two raw rates over two sets.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.analysis.common import wilson_ci  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402


def cell_key(r: dict) -> tuple[str, str]:
    return (r["memory_id"], r["future_task_id"])


def arm_report(rows: list[dict], name: str) -> dict:
    """Every H3 quantity that is a property of ONE arm."""
    live = [r for r in rows if not r.get("error_code_if_any")]
    errored = [r for r in rows if r.get("error_code_if_any")]
    n = len(live)

    nw = sum(float(r["reward_with_memory"]) for r in live)
    no = sum(float(r["reward_without_memory"]) for r in live)

    # --- both-arms-fail, at CELL level (a cell = one (memory, task) across replicates)
    cells: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in live:
        cells[cell_key(r)].append(r)
    both_fail = capable = 0
    for v in cells.values():
        best = max(max(float(x["reward_with_memory"]), float(x["reward_without_memory"]))
                   for x in v)
        if best == 0.0:
            both_fail += 1
        else:
            capable += 1

    # --- abstention, from the row's own recorded field. Reported SEPARATELY
    #     from reward: under the official rule an abstention scores 0 exactly
    #     like a wrong answer, so reward alone cannot tell them apart.
    def unk(field: str) -> int | None:
        vals = [r.get("provenance", {}).get(field) for r in live]
        if all(v is None for v in vals):
            return None            # not recorded -> None, never 0
        return sum(1 for v in vals if v)

    # --- dU distribution BEFORE labelling
    per_rep = collections.Counter(
        round(float(r["delta_utility"]), 6) for r in live)
    per_cell = collections.Counter()
    for v in cells.values():
        m = sum(float(x["delta_utility"]) for x in v) / len(v)
        per_cell["positive" if m > 0 else ("negative" if m < 0 else "zero")] += 1

    rate_w, lo_w, hi_w = wilson_ci(int(round(nw)), n)
    rate_o, lo_o, hi_o = wilson_ci(int(round(no)), n)
    return {
        "arm": name,
        "reader_prompt_version": sorted({r["reader_prompt_version"] for r in rows}),
        "condition_id": sorted({r["condition_id"] for r in rows}),
        "n_rows": len(rows), "n_rows_live": n, "n_rows_errored": len(errored),
        "error_codes": dict(collections.Counter(
            r["error_code_if_any"] for r in errored)),
        "n_cells_live": len(cells),
        "n_memories": len({r["memory_id"] for r in live}),
        "n_tasks": len({r["future_task_id"] for r in live}),
        "accuracy_with_memory": {"correct": int(round(nw)), "denominator": n,
                                 "rate": rate_w, "wilson_lo": lo_w, "wilson_hi": hi_w},
        "accuracy_without_memory": {"correct": int(round(no)), "denominator": n,
                                    "rate": rate_o, "wilson_lo": lo_o, "wilson_hi": hi_o},
        "both_arms_fail_cells": both_fail,
        "cells_capable_of_showing_an_effect": capable,
        "both_arms_fail_fraction": both_fail / len(cells) if cells else None,
        "abstentions": {
            "with_memory": unk("is_unknown_with"),
            "without_memory": unk("is_unknown_without"),
            "denominator_rows": n,
            "_note": "an abstention scores 0 exactly like a wrong answer "
                     "(harness.py:1055 forces score_bool=False when is_unknown), "
                     "so this is reported SEPARATELY from reward; None means the "
                     "field was not recorded by the run, which is not zero",
        },
        "delta_utility_before_labelling": {
            "per_cell_mean": {k: per_cell.get(k, 0)
                              for k in ("positive", "zero", "negative")},
            "per_replicate": {str(k): v for k, v in sorted(per_rep.items())},
        },
    }


def paired(a_rows: list[dict], b_rows: list[dict], a: str, b: str) -> dict:
    """H3.9 -- the two prompts on the SAME cells.

    Raw rates over two different sets would be two unpaired numbers. Both arms
    ran the same design, but one cell errored in the pilot, so the comparison
    is restricted to the INTERSECTION and the size of that intersection is
    reported next to every figure.
    """
    def by_cell(rows):
        out = collections.defaultdict(dict)
        for r in rows:
            if r.get("error_code_if_any"):
                continue
            out[cell_key(r)][r["replicate_id"]] = r
        return out

    A, B = by_cell(a_rows), by_cell(b_rows)
    shared = sorted(set(A) & set(B))
    only_a, only_b = sorted(set(A) - set(B)), sorted(set(B) - set(A))

    def cellwise(store, key):
        v = store[key]
        return (sum(float(r["reward_with_memory"]) for r in v.values()) / len(v),
                sum(float(r["reward_without_memory"]) for r in v.values()) / len(v))

    tally = collections.Counter()
    moved_w = moved_o = 0
    cap_a = cap_b = 0
    for k in shared:
        aw, ao = cellwise(A, k)
        bw, bo = cellwise(B, k)
        cap_a += (max(aw, ao) > 0)
        cap_b += (max(bw, bo) > 0)
        if bw > aw:
            moved_w += 1
        elif bw < aw:
            moved_w -= 1
        if bo > ao:
            moved_o += 1
        elif bo < ao:
            moved_o -= 1
        tally[(max(aw, ao) > 0, max(bw, bo) > 0)] += 1

    # McNemar-style: cells capable under exactly one arm
    b_only = tally[(False, True)]
    a_only = tally[(True, False)]
    return {
        "arm_a": a, "arm_b": b,
        "n_shared_cells": len(shared),
        "cells_only_in_a": len(only_a), "cells_only_in_b": len(only_b),
        "capable_cells_a": cap_a, "capable_cells_b": cap_b,
        "capability_transitions": {
            "incapable_both": tally[(False, False)],
            "capable_a_only": a_only,
            "capable_b_only": b_only,
            "capable_both": tally[(True, True)],
        },
        "discordant_pairs": a_only + b_only,
        "_note": "paired over the intersection of the two arms' cells; "
                 "capability = at least one arm of the cell ever scored 1",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", type=Path,
                    default=REPO / "results/deltau_official/cells.jsonl")
    ap.add_argument("--handwritten", type=Path,
                    default=REPO / "results/deltau_pilot/cells.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/deltau_official/analysis")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    off = load_jsonl(args.official)
    hand = load_jsonl(args.handwritten)
    print(f"[rows] official={len(off)} handwritten={len(hand)}")

    # The arms must NOT share a reader_prompt_version, or they are one arm.
    vo = {r["reader_prompt_version"] for r in off}
    vh = {r["reader_prompt_version"] for r in hand}
    if vo & vh:
        raise SystemExit(
            f"the two arms share reader_prompt_version {sorted(vo & vh)}; they would "
            f"be the same experimental arm and the comparison would be A/A.")
    print(f"[arms] official={sorted(vo)}  handwritten={sorted(vh)}  DISJOINT ✓")

    payload = {
        "official": arm_report(off, "official"),
        "handwritten": arm_report(hand, "handwritten"),
        "paired_comparison": paired(hand, off, "handwritten", "official"),
    }
    write_json_atomic(args.out / "10_prompt_arm_comparison.json", payload)

    for k in ("handwritten", "official"):
        r = payload[k]
        aw, ao = r["accuracy_with_memory"], r["accuracy_without_memory"]
        print(f"\n== {k} ({r['reader_prompt_version']}) ==")
        print(f"   rows live {r['n_rows_live']} / {r['n_rows']}; cells {r['n_cells_live']}")
        print(f"   acc WITH    {aw['correct']}/{aw['denominator']} = {aw['rate']:.4f} "
              f"[{aw['wilson_lo']:.4f}, {aw['wilson_hi']:.4f}]")
        print(f"   acc WITHOUT {ao['correct']}/{ao['denominator']} = {ao['rate']:.4f} "
              f"[{ao['wilson_lo']:.4f}, {ao['wilson_hi']:.4f}]")
        print(f"   BOTH-ARMS-FAIL cells {r['both_arms_fail_cells']}/{r['n_cells_live']} "
              f"= {r['both_arms_fail_fraction']:.4f}   "
              f"capable {r['cells_capable_of_showing_an_effect']}")
        print(f"   abstentions with={r['abstentions']['with_memory']} "
              f"without={r['abstentions']['without_memory']} of {r['n_rows_live']} rows")
        print(f"   dU per cell {r['delta_utility_before_labelling']['per_cell_mean']}")
    p = payload["paired_comparison"]
    print(f"\n== paired on {p['n_shared_cells']} shared cells ==")
    print(f"   capable: handwritten {p['capable_cells_a']} -> official {p['capable_cells_b']}")
    print(f"   transitions {p['capability_transitions']}")
    print(f"\nwrote {args.out / '10_prompt_arm_comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

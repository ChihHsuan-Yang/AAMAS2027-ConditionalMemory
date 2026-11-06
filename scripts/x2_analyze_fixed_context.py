#!/usr/bin/env python3
"""Regenerate the fixed-total-context comparison (paper Table S5, Figure 3b) from x2 rows.

Input is ``cells.jsonl`` written by ``scripts/x2_fixed_context.py`` (condition
``lmev2_metis_gptoss120b_fixedctx_v1``).  The runner's own ``summary.json`` is a run-health
readout; this script computes the reported estimates.

Definitions (paper S11):
* Every arm of a cell is padded to the same total token count T, so arms differ only in the
  memory text.  Arms: raw, summary, structured, trunc_last_matched.
* Unit of analysis is the CELL, a (memory, task) pair; replicates are averaged first.
  Estimates are over BEARING cells.  Intervals are task-clustered percentile bootstraps.
* Disclosed cache-key defect: the no-memory arm was cached on (trajectory, task, replicate),
  so two memories from one trajectory paired with one task could share a no-memory response
  although their padding differs.  Such "exposed" cells are excluded from the headline and
  reported again with them included.
* Missing rewards are dropped, never scored as zero.

The paper reports, excluding exposed cells (n = 77 bearing cells): Raw +0.35 [+0.23, +0.49],
Summary +0.04, Structured +0.01, Summary-Raw -0.31, Structured-Raw -0.34; including them
(n = 135): Raw +0.37 [+0.25, +0.51].  The script prints whether the cell counts match
(63 exposed pairs, 77 and 135 bearing cells) so a reader sees immediately if the rows they
hold are the rows the paper used.  Point estimates should agree to two decimals; intervals
are bootstrap percentiles and may differ in the third decimal.

    python scripts/x2_analyze_fixed_context.py results/x2_fixed_context/cells.jsonl --out table_s5.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

ARMS = ("raw", "summary", "structured", "trunc_last_matched")
EXPECT = {"exposed_pairs": 63, "bearing_cells_excluding": 77, "bearing_cells_including": 135}


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open() if l.strip()]


def _num(x):
    return None if x is None or x != x else float(x)


def build_cells(rows: list[dict]) -> dict:
    """{(memory_id, task_id): {'stratum', 'episode', 'arms': {arm: mean dU}}} (replicates averaged)."""
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    meta = {}
    for r in rows:
        prov = r.get("provenance") or {}
        arm = prov.get("arm")
        if arm not in ARMS:
            continue
        # Summary and Structured memories have their own memory_id; the cell is identified by the
        # page visit they were written from (the Raw memory's unit locator).
        loc = (r.get("source_episode_metadata") or {}).get("memory_unit_locator") or r.get("memory_id")
        key = (loc, r["future_task_id"])
        meta[key] = {"stratum": prov.get("stratum"), "episode": r.get("source_episode_id")}
        w, o = _num(r.get("reward_with_memory")), _num(r.get("reward_without_memory"))
        if w is None or o is None:
            continue                                   # missing is not zero
        acc[key][arm].append(w - o)
    out = {}
    for key, arms in acc.items():
        out[key] = {**meta[key], "arms": {a: float(np.mean(v)) for a, v in arms.items()}}
    return out


def exposed_keys(cells: dict) -> set:
    """Cells whose (episode, task) pair is shared by more than one memory."""
    by_pair = collections.defaultdict(set)
    for (mem, task), c in cells.items():
        by_pair[(c["episode"], task)].add(mem)
    return {(mem, task) for (mem, task), c in cells.items()
            if len(by_pair[(c["episode"], task)]) > 1}


def boot_ci(values: np.ndarray, clusters: np.ndarray, n: int, seed: int):
    ids = np.unique(clusters)
    groups = [values[clusters == i] for i in ids]
    rng = np.random.default_rng(seed)
    means = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        means[b] = np.concatenate([groups[i] for i in pick]).mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def estimate(cells: dict, keys: list, n_boot: int, seed: int) -> dict:
    out = {"n_bearing_cells": len(keys), "arms": {}, "contrasts": {}}
    tasks = np.array([k[1] for k in keys])
    for arm in ARMS:
        v = np.array([cells[k]["arms"].get(arm, np.nan) for k in keys])
        ok = ~np.isnan(v)
        if ok.sum() == 0:
            continue
        lo, hi = boot_ci(v[ok], tasks[ok], n_boot, seed)
        out["arms"][arm] = {"n": int(ok.sum()), "mean": float(v[ok].mean()), "ci95": [lo, hi]}
    for a in ("summary", "structured", "trunc_last_matched"):
        d = np.array([cells[k]["arms"].get(a, np.nan) - cells[k]["arms"].get("raw", np.nan) for k in keys])
        ok = ~np.isnan(d)
        if ok.sum() == 0:
            continue
        lo, hi = boot_ci(d[ok], tasks[ok], n_boot, seed)
        out["contrasts"][f"{a}_minus_raw"] = {"n": int(ok.sum()), "mean": float(d[ok].mean()), "ci95": [lo, hi]}
    return out


def analyze(rows: list[dict], n_boot: int = 10000, seed: int = 20261008) -> dict:
    cells = build_cells(rows)
    exposed = exposed_keys(cells)
    bearing = sorted(k for k, c in cells.items() if c["stratum"] == "BEARING")
    clean = [k for k in bearing if k not in exposed]
    result = {
        "script": "scripts/x2_analyze_fixed_context.py",
        "n_cells_total": len(cells),
        "n_exposed_pairs": len(exposed),
        "excluding_exposed": estimate(cells, clean, n_boot, seed),
        "including_exposed": estimate(cells, bearing, n_boot, seed),
    }
    got = {"exposed_pairs": len(exposed),
           "bearing_cells_excluding": len(clean), "bearing_cells_including": len(bearing)}
    result["counts_vs_paper"] = {k: {"got": got[k], "paper": EXPECT[k], "match": got[k] == EXPECT[k]}
                                 for k in EXPECT}
    result["counts_match_paper"] = all(v["match"] for v in result["counts_vs_paper"].values())
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cells", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261008)
    a = ap.parse_args(argv)
    res = analyze(load(a.cells), a.n_boot, a.seed)
    for label in ("excluding_exposed", "including_exposed"):
        e = res[label]
        print(f"\n{label}  (bearing cells n={e['n_bearing_cells']})")
        for arm, v in e["arms"].items():
            print(f"  {arm:<20} {v['mean']:+.3f}  [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]  n={v['n']}")
        for c, v in e["contrasts"].items():
            print(f"  {c:<20} {v['mean']:+.3f}  [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]  n={v['n']}")
    print("\ncell counts vs paper:")
    for k, v in res["counts_vs_paper"].items():
        print(f"  {k:<26} got {v['got']:<4} paper {v['paper']:<4} {'ok' if v['match'] else 'DIFFERS'}")
    print("VERDICT:", "COUNTS_MATCH_PAPER" if res["counts_match_paper"] else "COUNTS_DIFFER_FROM_PAPER")
    if a.out:
        a.out.write_text(json.dumps(res, indent=2))
    return 0 if res["counts_match_paper"] else 1


if __name__ == "__main__":
    sys.exit(main())

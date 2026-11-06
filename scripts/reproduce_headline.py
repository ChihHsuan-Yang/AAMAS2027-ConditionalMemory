#!/usr/bin/env python3
"""Smallest reproduction of the paper's primary result, with no endpoint and no downloads.

Primary result: within each memory, the mean paired reward gain on answer-bearing
(BEARING) task pairs minus the mean gain on matched-control (MATCHED_CONTROL) task
pairs, averaged over memories.  Paper: +0.33, 60 memories, 1,157 cells.

Default input is the tracked slice ``results/ledgers/repro/screened_cells_slim.jsonl``.
The same computation can be run on the public dataset's overview table:

    python scripts/reproduce_headline.py --overview overview.parquet   # needs pyarrow

(``overview.parquet`` is ``data/overview.parquet`` in the Hugging Face dataset; the
primary run is ``condition_id == lmev2_raw_metis_gptoss120b_screened_v1``.)

Units, stated once: a *row* is one replicate of one pair; a *cell* is one
(memory, task) pair with its replicates averaged; the contrast is taken over memories.
Missing rewards are dropped, never scored as zero.  Exit status is non-zero if the
contrast differs from ``--expect`` by more than ``--tol``.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SLICE = REPO / "results/ledgers/repro/screened_cells_slim.jsonl"
PRIMARY_CONDITION = "lmev2_raw_metis_gptoss120b_screened_v1"
STRATA = ("BEARING", "MATCHED_CONTROL", "RANDOM")


def rows_from_slice(path: Path) -> list[dict]:
    out = []
    for line in path.open():
        r = json.loads(line)
        out.append({"memory_id": r["memory_id"], "task_id": r["future_task_id"],
                    "stratum": r["stratum"], "with": r["reward_with_memory"],
                    "without": r["reward_without_memory"]})
    return out


def rows_from_overview(path: Path) -> list[dict]:
    import pandas as pd
    df = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)
    df = df[df["condition_id"] == PRIMARY_CONDITION]
    return [{"memory_id": r.memory_id, "task_id": r.future_task_id,
             "stratum": r.bearing_label, "with": r.reward_with_memory,
             "without": r.reward_without_memory} for r in df.itertuples()]


def cells(rows: list[dict]) -> dict:
    acc = collections.defaultdict(list)
    for r in rows:
        if r["with"] is None or r["without"] is None or r["with"] != r["with"] or r["without"] != r["without"]:
            continue                                   # missing is not zero
        acc[(r["memory_id"], r["task_id"], r["stratum"])].append(r["with"] - r["without"])
    return {k: float(np.mean(v)) for k, v in acc.items()}


def per_memory_contrast(cell: dict) -> dict:
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for (m, _t, s), d in cell.items():
        per[m][s].append(d)
    return {m: float(np.mean(v["BEARING"]) - np.mean(v["MATCHED_CONTROL"]))
            for m, v in per.items() if v["BEARING"] and v["MATCHED_CONTROL"]}


def episode(memory_id: str) -> str:
    return memory_id.split("-")[1]                     # mem-<episode>-<hash>


def bootstrap(contrast: dict, cluster, n: int, seed: int) -> tuple[float, float]:
    groups = collections.defaultdict(list)
    for m, d in contrast.items():
        groups[cluster(m)].append(d)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        vals = [d for i in pick for d in groups[keys[i]]]
        means.append(np.mean(vals))
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slice", type=Path, default=DEFAULT_SLICE)
    ap.add_argument("--overview", type=Path, help="public overview table (parquet or csv)")
    ap.add_argument("--expect", type=float, default=0.334861)
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--bootstrap", type=int, default=0, metavar="N",
                    help="also print percentile intervals from N resamples (memory- and episode-clustered)")
    ap.add_argument("--seed", type=int, default=20261008)
    a = ap.parse_args(argv)

    rows = rows_from_overview(a.overview) if a.overview else rows_from_slice(a.slice)
    cell = cells(rows)
    contrast = per_memory_contrast(cell)
    value = float(np.mean(list(contrast.values())))

    print("source           :", a.overview or a.slice)
    print("rows             :", len(rows))
    print("cells            :", len(cell))
    for s in STRATA:
        d = [x for (_m, _t, st), x in cell.items() if st == s]
        print(f"  {s:<16} cells={len(d):<4} mean dU={np.mean(d):+.3f}")
    both = [r for r in rows if r["with"] is not None and r["without"] is not None]
    for s in STRATA:
        sub = [r for r in both if r["stratum"] == s]
        print(f"  {s:<16} both-arms-fail share of rows={sum(1 for r in sub if r['with'] == 0 and r['without'] == 0) / len(sub):.3f}")
    print("memories (both)  :", len(contrast))
    print(f"contrast         : {value:+.6f}   (expected {a.expect:+.6f})")
    if a.bootstrap:
        lo, hi = bootstrap(contrast, lambda m: m, a.bootstrap, a.seed)
        elo, ehi = bootstrap(contrast, episode, a.bootstrap, a.seed)
        print(f"95% CI memories  : [{lo:+.3f}, {hi:+.3f}]   ({a.bootstrap} resamples, seed {a.seed})")
        print(f"95% CI episodes  : [{elo:+.3f}, {ehi:+.3f}]")
    ok = abs(value - a.expect) <= a.tol
    print("VERDICT:", "REPRODUCED" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

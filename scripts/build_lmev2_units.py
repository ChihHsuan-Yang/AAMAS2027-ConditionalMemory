#!/usr/bin/env python3
"""Build LongMemEval-V2 memory units + pairing manifest, and measure tokens.

Writes to data/manifests/:
  lmev2_memory_units_<tier>.jsonl      one row per PageVisit (no AXTree text)
  lmev2_memory_unit_tokens.json        measured token distribution per unit def
  lmev2_pairs_<tier>_seed<N>.jsonl     the selected (memory, task) cells

Token counts use the OFFICIAL tokenizer (Qwen/Qwen3.5-9B), the one
evaluation/harness.py::count_memory_context_tokens loads, so our budgets are
comparable to the benchmark's own. --no-tokenize skips it for a fast rebuild.

Usage:
  python3 scripts/build_lmev2_units.py --root /tmp/lmev2 --tier small --seed 20261008
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters import lmev2  # noqa: E402


def quantiles(xs: list[int]) -> dict[str, float]:
    if not xs:
        return {}
    s = sorted(xs)

    def q(p: float) -> int:
        return s[min(len(s) - 1, int(p * len(s)))]

    return {
        "n": len(s), "min": s[0], "p10": q(0.10), "p25": q(0.25),
        "median": q(0.50), "p75": q(0.75), "p90": q(0.90), "p99": q(0.99),
        "max": s[-1], "mean": round(sum(s) / len(s), 1), "total": sum(s),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--tier", default="small", choices=["small", "medium"])
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--tasks-per-memory", type=int, default=8)
    ap.add_argument("--no-tokenize", action="store_true")
    ap.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "manifests",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print("verifying vendored scorer ...", flush=True)
    print("  sha256", lmev2.verify_vendored_scorer())
    print("verifying data checksums ...", flush=True)
    for k, v in lmev2.verify_checksums(args.root).items():
        print(f"  {k}: {v}")
    print("checking the memory writer is blind to future tasks ...", flush=True)
    lmev2.assert_writer_blind()
    print("  PASSED")

    haystack = lmev2.load_haystack(args.root, args.tier)
    keep = {tid for tids in haystack.values() for tid in tids}
    print(f"tier={args.tier}: working set {len(keep)} trajectories", flush=True)

    tok = None
    if not args.no_tokenize:
        from transformers import AutoTokenizer  # noqa: PLC0415

        print(f"loading official tokenizer {lmev2.OFFICIAL_TOKENIZER} ...", flush=True)
        tok = AutoTokenizer.from_pretrained(lmev2.OFFICIAL_TOKENIZER)

    units: list[lmev2.PageVisit] = []
    whole_traj_tokens: list[int] = []
    single_state_tokens: list[int] = []
    n_seen = 0
    for traj in lmev2.read_jsonl(args.root / "trajectories.jsonl"):
        if traj["id"] not in keep:
            continue
        n_seen += 1
        pvs = lmev2.segment_page_visits(traj)
        if tok is not None:
            for k, pv in enumerate(pvs):
                n = len(tok(pv.text, add_special_tokens=False)["input_ids"])
                pvs[k] = lmev2.PageVisit(**{**pv.__dict__, "n_tokens": n})
            hdr = lmev2.format_span_header(1, traj, 0, len(traj["states"]) - 1)
            body = "".join(lmev2.format_state_text(s) for s in traj["states"])
            whole_traj_tokens.append(
                len(tok(hdr + body, add_special_tokens=False)["input_ids"])
            )
            for s in traj["states"]:
                single_state_tokens.append(
                    len(
                        tok(
                            lmev2.format_state_text(s), add_special_tokens=False
                        )["input_ids"]
                    )
                )
        units.extend(pvs)
        if n_seen % 25 == 0:
            print(f"  {n_seen}/{len(keep)} trajectories", flush=True)

    upath = args.out / f"lmev2_memory_units_{args.tier}.jsonl"
    with open(upath, "w") as fh:
        for u in units:
            row = {k: v for k, v in u.__dict__.items() if k != "text"}
            row["text_chars"] = len(u.text)
            fh.write(json.dumps(row) + "\n")
    print(f"WROTE {upath}  ({len(units)} memory units)")

    if tok is not None:
        stats = {
            "tokenizer": lmev2.OFFICIAL_TOKENIZER,
            "tier": args.tier,
            "n_trajectories": n_seen,
            "units": {
                "A_whole_trajectory": quantiles(whole_traj_tokens),
                "B_single_state": quantiles(single_state_tokens),
                "C_page_visit_CHOSEN": quantiles([u.n_tokens for u in units]),
            },
            "page_visit_states_per_unit": quantiles([u.n_states for u in units]),
            "page_visits_per_trajectory": quantiles(
                list(
                    __import__("collections")
                    .Counter(u.trajectory_id for u in units)
                    .values()
                )
            ),
        }
        spath = args.out / "lmev2_memory_unit_tokens.json"
        spath.write_text(json.dumps(stats, indent=2) + "\n")
        print(f"WROTE {spath}")
        for name, d in stats["units"].items():
            print(f"  {name:26s} {d}")

    tasks = lmev2.load_tasks(args.root)
    med = lmev2.load_haystack(args.root, "medium")
    pairs = lmev2.select_pairs(
        units, tasks, seed=args.seed,
        tasks_per_memory=args.tasks_per_memory, haystack=med,
    )
    ppath = args.out / f"lmev2_pairs_{args.tier}_seed{args.seed}.jsonl"
    with open(ppath, "w") as fh:
        for p in pairs:
            fh.write(json.dumps(p.__dict__) + "\n")
    print(f"WROTE {ppath}  ({len(pairs)} cells)")

    # reproducibility: the same seed must give the same cells
    again = lmev2.select_pairs(
        units, tasks, seed=args.seed,
        tasks_per_memory=args.tasks_per_memory, haystack=med,
    )
    assert [p.__dict__ for p in pairs] == [p.__dict__ for p in again], (
        "pairing is NOT deterministic under a fixed seed"
    )
    other = lmev2.select_pairs(
        units, tasks, seed=args.seed + 1,
        tasks_per_memory=args.tasks_per_memory, haystack=med,
    )
    assert [p.__dict__ for p in pairs] != [p.__dict__ for p in other], (
        "changing the seed did not change the cells -- the seed is not bound"
    )
    print("pairing determinism: PASSED (same seed identical, different seed differs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

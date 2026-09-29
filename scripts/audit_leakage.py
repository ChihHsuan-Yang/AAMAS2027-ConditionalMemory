#!/usr/bin/env python3
"""Leakage audit for LongMemEval-V2 and LongMemEval-V1.

Reports, for every (memory unit, future task) cell, whether the memory
literally carries the gold answer. NOTHING IS EVER DROPPED -- dropping leaky
cells conditions the cell set on the outcome and changes the question being
answered. Cells are flagged so analysis can report both with and without.

The controls run FIRST and the audit ABORTS if any fails. A leakage rate from
a detector not shown to fire is not a measurement.

Usage:
  python3 scripts/audit_leakage.py --controls-only
  python3 scripts/audit_leakage.py --v2 --root /tmp/lmev2
  python3 scripts/audit_leakage.py --v1 --v1-root .../data/lmev1
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters import leakage, lmev2  # noqa: E402


def run_controls() -> bool:
    ok, res = leakage.controls_summary()
    print("=" * 78)
    print("DETECTOR CONTROLS  (positive plants must FIRE, clean cases must NOT)")
    print("=" * 78)
    for r in res:
        print(
            f"  {'PASS' if r.passed else 'FAIL'}  {r.name:36s} "
            f"{r.detector:20s} expected={r.expected!s:5s} observed={r.observed}"
        )
    print(f"  --> {sum(r.passed for r in res)}/{len(res)} passed; ALL={ok}")
    return ok


def bucket(n: int) -> str:
    if n <= 2:
        return "1 degenerate (<=2 chars)"
    if n <= 5:
        return "2 very short (3-5)"
    if n <= 12:
        return "3 short (6-12)"
    if n <= 30:
        return "4 medium (13-30)"
    return "5 long (>30)"


def audit_v2(root: Path, manifest_dir: Path, tier: str, limit_units: int | None) -> None:
    lmev2.require_supported_python()
    lmev2.verify_vendored_scorer()
    lmev2.verify_checksums(root)

    tasks = {t.id: t for t in lmev2.load_tasks(root)}
    haystack = lmev2.load_haystack(root, tier)
    keep = {tid for tids in haystack.values() for tid in tids}

    units: list[lmev2.PageVisit] = []
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] in keep:
            units.extend(lmev2.segment_page_visits(traj))
    if limit_units:
        units = units[:limit_units]
    print(f"\nV2 tier={tier}: {len(units)} memory units, {len(tasks)} tasks")

    # Cells: every memory against every same-domain task. On the small tier
    # that is the true availability structure, so the audit covers the whole
    # space rather than only the sampled pairs.
    by_dom: dict[str, list[lmev2.FutureTask]] = collections.defaultdict(list)
    for t in tasks.values():
        by_dom[t.domain].append(t)

    rows: list[dict] = []
    counts: collections.Counter = collections.Counter()
    for u in units:
        for t in by_dom[u.domain]:
            v = leakage.detect(
                u.text, t.answer,
                memory_id=u.memory_unit_locator, task_id=t.id,
                eval_function_spec=t.eval_function,
            )
            b = bucket(len(leakage.normalize_text(t.answer)))
            counts[("cells", b)] += 1
            counts[("cells_all", "all")] += 1
            if v.official is None:
                counts[("undecidable", b)] += 1
            for det in ("exact", "normalized", "numeric", "official"):
                if getattr(v, det) is True:
                    counts[(det, b)] += 1
                    counts[(det, "ALL")] += 1
            if v.any_leak:
                counts[("any", b)] += 1
                counts[("any", "ALL")] += 1
                rows.append(
                    {
                        "memory_id": v.memory_unit_locator, "task_id": v.task_id,
                        "exact": v.exact, "normalized": v.normalized,
                        "numeric": v.numeric, "official": v.official,
                        "gold_answer_chars": v.gold_answer_chars,
                        "question_type": t.question_type,
                        "eval_name": t.eval_name,
                        "gold_answer": t.answer,
                        "notes": list(v.notes),
                    }
                )

    total = counts[("cells_all", "all")]
    print(f"\ntotal cells audited: {total:,}")
    print(f"{'gold-length stratum':26s} {'cells':>10s} {'exact':>9s} {'norm':>9s} "
          f"{'numeric':>9s} {'official':>9s} {'ANY':>9s} {'undecid':>9s}")
    for b in sorted({k[1] for k in counts if k[0] == "cells"}):
        c = counts[("cells", b)]
        def pct(d: str) -> str:
            return f"{100.0 * counts[(d, b)] / c:8.3f}%" if c else "       -"
        print(f"{b:26s} {c:10,d} {pct('exact')} {pct('normalized')} "
              f"{pct('numeric')} {pct('official')} {pct('any')} "
              f"{100.0*counts[('undecidable',b)]/c:8.3f}%")
    print(f"{'POOLED':26s} {total:10,d} "
          f"{100.0*counts[('exact','ALL')]/total:8.3f}% "
          f"{100.0*counts[('normalized','ALL')]/total:8.3f}% "
          f"{100.0*counts[('numeric','ALL')]/total:8.3f}% "
          f"{100.0*counts[('official','ALL')]/total:8.3f}% "
          f"{100.0*counts[('any','ALL')]/total:8.3f}%")

    out = manifest_dir / f"lmev2_leakage_{tier}.jsonl"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nWROTE {out}  ({len(rows)} FLAGGED cells -- flagged, NOT dropped)")

    summ = manifest_dir / f"lmev2_leakage_{tier}_summary.json"
    summ.write_text(
        json.dumps(
            {
                "tier": tier, "n_memory_units": len(units),
                "n_tasks": len(tasks), "n_cells": total,
                "counts": {f"{k[0]}|{k[1]}": v for k, v in sorted(counts.items())},
                "policy": "FLAG_NEVER_DROP",
                "caveat": (
                    "normalized/official UNDER-count: the benchmark's "
                    "normalize_phrase strips punctuation without inserting a "
                    "space, so gold text abutting punctuation is missed. See "
                    "leakage.prove_detector_can_fail control "
                    "'known-fn/punctuation-glued'. Rates are lower bounds."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"WROTE {summ}")


def audit_v1(
    v1_root: Path, manifest_dir: Path, which: str = "oracle"
) -> None:
    """V1 audit at SESSION granularity, split by labelled-evidence status.

    V1 ships answer_session_ids AND a per-turn has_answer boolean, so evidence
    is addressable -- unlike V2, which has no evidence labels at all.

    ``which='oracle'`` audits longmemeval_oracle.json. Note that the oracle
    file is 100% labelled evidence (948/948 sessions), so it yields NO filler
    row; that is a true zero, positive-controlled by counting the sessions
    directly, not a detector failure. ``which='s'`` audits
    longmemeval_s_cleaned.json, which carries the real filler pool and is
    where the evidence-vs-filler CONTRAST can actually be measured.
    """
    fname = (
        "longmemeval_oracle.json" if which == "oracle" else "longmemeval_s_cleaned.json"
    )
    path = v1_root / fname
    if not path.exists():
        print(f"SKIP V1: {path} not present")
        return
    recs = json.loads(path.read_text())
    print(f"\nV1 {which}: {len(recs)} records")

    counts: collections.Counter = collections.Counter()
    rows: list[dict] = []
    for r in recs:
        gold = r["answer"]
        ev_ids = set(r.get("answer_session_ids") or ())
        for sid, sess in zip(r["haystack_session_ids"], r["haystack_sessions"]):
            text = "\n".join(
                f"{t.get('role')}: {t.get('content')}" for t in sess
            )
            v = leakage.detect(
                text, gold, memory_id=f"{r['question_id']}:{sid}",
                task_id=r["question_id"],
            )
            is_ev = sid in ev_ids
            key = "evidence" if is_ev else "filler"
            counts[(key, "cells")] += 1
            for det in ("exact", "normalized", "numeric"):
                if getattr(v, det) is True:
                    counts[(key, det)] += 1
            if v.any_leak:
                counts[(key, "any")] += 1
                rows.append(
                    {
                        "memory_id": v.memory_unit_locator, "task_id": v.task_id,
                        "is_labelled_evidence": is_ev,
                        "exact": v.exact, "normalized": v.normalized,
                        "numeric": v.numeric,
                        "question_type": r["question_type"],
                        "gold_answer_chars": v.gold_answer_chars,
                    }
                )

    print(f"{'session class':14s} {'cells':>9s} {'exact':>9s} {'norm':>9s} "
          f"{'numeric':>9s} {'ANY':>9s}")
    for key in ("evidence", "filler"):
        c = counts[(key, "cells")]
        if not c:
            print(f"{key:14s} {0:9,d}   (no cells of this class in this file)")
            continue
        def pct(d: str) -> str:
            return f"{100.0 * counts[(key, d)] / c:8.3f}%"
        print(f"{key:14s} {c:9,d} {pct('exact')} {pct('normalized')} "
              f"{pct('numeric')} {pct('any')}")

    manifest_dir.mkdir(parents=True, exist_ok=True)
    out = manifest_dir / f"lmev1_leakage_{which}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"WROTE {out}  ({len(rows)} flagged, NOT dropped)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--v1", action="store_true")
    ap.add_argument("--v1-which", default="oracle", choices=["oracle", "s"])
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument(
        "--v1-root", type=Path,
        default=Path("/Users/bellayang/Documents/2026/p1_memory_utility/data/lmev1"),
    )
    ap.add_argument("--tier", default="small")
    ap.add_argument("--limit-units", type=int, default=None)
    ap.add_argument(
        "--manifests", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "manifests",
    )
    args = ap.parse_args()

    if not run_controls():
        print("\nABORT: a detector control FAILED. A leakage rate from a "
              "detector not shown to fire is not a measurement.")
        return 1
    if args.controls_only:
        return 0
    if args.v2:
        audit_v2(args.root, args.manifests, args.tier, args.limit_units)
    if args.v1:
        audit_v1(args.v1_root, args.manifests, args.v1_which)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

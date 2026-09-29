#!/usr/bin/env python3
"""Run P1 cells from a JSONL spec: resumable, idempotent, cache-aware."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.runner import Cell, run_cells  # noqa: E402


def load_cells(path: Path) -> list[Cell]:
    cells = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)          # strict
        try:
            cells.append(Cell(cell_id=row["cell_id"], messages=row["messages"],
                              key_fields=row["key_fields"]))
        except KeyError as e:
            raise SystemExit(f"{path}:{lineno} missing field {e}") from e
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--cluster", default="metis")
    ap.add_argument("--model", default="gpt-oss-120b")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cells = load_cells(Path(args.cells))
    print(f"[run_cells] loaded {len(cells)} cells from {args.cells}")
    if args.dry_run:
        print("[run_cells] dry run: no calls issued")
        return 0

    stats = run_cells(cells, cluster=args.cluster, model=args.model,
                      cache_path=args.cache, ledger_path=args.ledger,
                      max_workers=args.workers, max_tokens=args.max_tokens,
                      reasoning_effort=args.effort)
    print(json.dumps(stats, indent=2))
    # Non-zero when any cell failed, so a wrapper cannot read success from a 0.
    return 1 if stats.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())

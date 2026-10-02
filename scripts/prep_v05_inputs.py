#!/usr/bin/env python3
"""Prepare the v0.5 result ledgers for export, WITHOUT editing them in place.

🔴 Why this script exists, and why it is not a flag on the exporter.

``export_hf.py`` does not migrate schemas, and the v0.5 inputs are already schema v3,
so the ``migrate_schema_v2.py`` path that v0.1-v0.4 used does not run over them. One
thing that path does is fill the *reason* for a deliberately-null field:
``_as_raw()`` writes ``FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE`` onto every ``raw`` row.

The two gold-free ledgers were written directly at v3 and never passed through it, so
their 824 rows carry ``faithfulness_check = None`` with an EMPTY ``faithfulness_notes``.
The validator warns ``faithfulness_null_without_reason`` on exactly that, and it is
right to: *an unexplained null cannot be told apart from an unpopulated field.* Shipping
824 of them would publish a silence where the project everywhere else publishes a reason.

What this script does NOT do: it does not invent the reason. The note is the project's
own constant, and this script writes it ONLY where its stated premise is verified true
on the row itself -- representation ``raw``, a deterministic-span writer, and no
faithfulness detail. Any row failing that premise is left untouched and reported, so a
wrong reason cannot be written onto a row it does not describe. (v0.2's lesson: a
documented reason for a null is a CLAIM, and it decays.)

``faithfulness_notes`` is in none of MEMORY_ID_KEYS / CELL_ID_KEYS / ROW_ID_KEYS, so
writing it cannot move any published id. That is asserted here rather than assumed.

Outputs go to a separate directory; the source ledgers are never modified.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from p1mem import schema as S  # noqa: E402


def premise_holds(row: dict) -> bool:
    """The conditions FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE actually asserts."""
    return (row.get("memory_representation") == "raw"
            and row.get("memory_writer_model") == "none:deterministic_span"
            and row.get("memory_writer_cluster") == "none:deterministic_span"
            and row.get("faithfulness_check") is None
            and row.get("faithfulness_detail") is None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", nargs="+", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)

    # An id must not be able to move. Assert, do not trust.
    for name, keys in (("MEMORY_ID_KEYS", S.MEMORY_ID_KEYS),
                       ("CELL_ID_KEYS", S.CELL_ID_KEYS),
                       ("ROW_ID_KEYS", S.ROW_ID_KEYS)):
        assert "faithfulness_notes" not in keys, (
            f"faithfulness_notes is in {name}; filling it would re-mint published ids")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    total_filled = total_skipped = total_kept = 0
    for p in args.inp:
        rows = S.load_jsonl(p, strict=True)
        filled = skipped = kept = 0
        ids_before = [(r.get("memory_id"), r.get("cell_id"), r.get("row_id")) for r in rows]
        for r in rows:
            notes = r.get("faithfulness_notes")
            if isinstance(notes, str) and notes.strip():
                kept += 1
                continue
            if premise_holds(r):
                r["faithfulness_notes"] = S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE
                filled += 1
            else:
                skipped += 1
        ids_after = [(r.get("memory_id"), r.get("cell_id"), r.get("row_id")) for r in rows]
        assert ids_before == ids_after, "an id moved -- refusing to write"
        out = args.out_dir / p.name if p.name != "cells.jsonl" else \
            args.out_dir / f"{p.parent.name}.jsonl"
        S.write_jsonl_atomic(out, rows)
        print(f"{p}: {len(rows)} rows | reason filled {filled} | already had one {kept} "
              f"| premise FALSE, left untouched {skipped} -> {out}")
        total_filled += filled; total_skipped += skipped; total_kept += kept
    print(f"TOTAL filled={total_filled} kept={total_kept} "
          f"left_untouched_premise_false={total_skipped}")
    if total_skipped:
        print("NOTE: rows whose premise is false keep an empty note and will still warn. "
              "That is correct -- a reason must not be written onto a row it does not "
              "describe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

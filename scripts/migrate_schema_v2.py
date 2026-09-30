#!/usr/bin/env python3
"""Upgrade a schema-v1 result ledger to schema v2 (the user's field list).

    python3 scripts/migrate_schema_v2.py --in results/deltau_screened/cells.jsonl \
                                         --out /tmp/v2/screened.jsonl

Schema v2 added 17 fields. Presence is the contract -- ``validate.py`` reports a missing
KEY, with null a legal value -- so a v1 row fails v2 validation until every new key
exists on it. This script adds them.

**It derives; it never invents.** Three rules, each enforced below:

1. A value is written only when it can be computed from fields ALREADY ON THE ROW, or
   joined from a manifest whose join is verified row-by-row. Nothing is inferred from a
   run clock, a filename, or a default.
2. A field with no derivable value gets an explicit ``None``, and where the reason is
   not obvious from the schema it is written into a paired ``*_notes`` field. An
   unexplained null cannot be told apart from a forgotten one.
3. The source ledger is NEVER modified. Migration writes a new file; the v1 ledger
   remains the append-only record of what was actually run.

The migration is verified by a positive control (``--self-test``) which corrupts a copy
of a row in the shape of each defect the new validator checks for, and asserts the
checks fire. A migration whose output has only ever been validated as correct is not
known to produce anything a validator could reject.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from p1mem import schema as S      # noqa: E402
from p1mem import validate as V    # noqa: E402

DEFAULT_UNIT_MANIFEST = REPO_ROOT / "data/manifests/lmev2_memory_units_small.jsonl"


def load_unit_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """locator -> unit record. The source of source_span_tokens."""
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            u = json.loads(line)
            out[u["memory_unit_locator"]] = u
    return out


def source_span_tokens_for(row: dict[str, Any], units: dict[str, dict[str, Any]]) -> int | None:
    """Tokens in the SOURCE span this memory was cut from.

    Joined on ``memory_unit_locator``, which is a positional locator and therefore only
    valid against the manifest the run actually used. The caller verifies the join rate
    and refuses to proceed on a partial join -- a half-matched join still looks like
    success (three of six settings silently matching zero rows is a defect this project
    has already seen).
    """
    meta = row.get("source_episode_metadata")
    if not isinstance(meta, dict):
        return None
    loc = meta.get("memory_unit_locator")
    if not isinstance(loc, str):
        return None
    u = units.get(loc)
    if u is None:
        return None
    n = u.get("n_tokens")
    return n if isinstance(n, int) and not isinstance(n, bool) else None


def migrate_rows(
    rows: Sequence[dict[str, Any]], units: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (v2 rows, stats). Pure: the inputs are not mutated."""
    # --- per-cell statistics, computed BEFORE the row pass so num_replicates and
    #     stability are measurements over what is actually present, not planned counts.
    by_cell: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_cell.setdefault(r.get("cell_id"), []).append(r)

    cell_n: dict[str, int] = {}
    cell_stability: dict[str, float | None] = {}
    for cid, items in by_cell.items():
        cell_n[cid] = len(items)
        deltas = [x.get("delta_utility") for x in items
                  if isinstance(x.get("delta_utility"), (int, float))
                  and not isinstance(x.get("delta_utility"), bool)]
        if len(deltas) < 2:
            # One replicate cannot measure agreement with itself. Null, not 1.0.
            cell_stability[cid] = None
        else:
            modal = max(set(deltas), key=deltas.count)
            cell_stability[cid] = deltas.count(modal) / len(deltas)

    stats = {
        "n_rows": len(rows),
        "n_cells": len(by_cell),
        "span_join_hits": 0,
        "span_join_misses": 0,
        "bearing_labels": {},
        "reserved_null": {
            "source_episode_completion_timestamp": 0,
            "parent_memory_id": 0,
            "faithfulness_check": 0,
            "context_budget": 0,
            "propagation_metadata": 0,
        },
    }

    out: list[dict[str, Any]] = []
    for r in rows:
        n = dict(r)

        # ---- chronology: no timestamp exists in LongMemEval-V2. Verified by an
        #      exhaustive key scan of all 1,870 trajectories. Null, never synthesized.
        n["source_episode_completion_timestamp"] = None
        stats["reserved_null"]["source_episode_completion_timestamp"] += 1

        # ---- lineage: raw spans have no parent MEMORY (their parent is the episode,
        #      which is already source_episode_id).
        n["parent_memory_id"] = None
        stats["reserved_null"]["parent_memory_id"] += 1

        coarse, fine = S.classify_memory_type(r)
        n["memory_type_coarse"] = coarse
        n["memory_type_fine"] = fine

        # ---- quality
        sst = source_span_tokens_for(r, units)
        if sst is None:
            stats["span_join_misses"] += 1
        else:
            stats["span_join_hits"] += 1
        n["source_span_tokens"] = sst
        n["compression_ratio"] = S.compute_compression_ratio(r.get("memory_tokens"), sst)
        n["extraction_cost_proxy"] = S.compute_extraction_cost_proxy(r)

        # ---- faithfulness: null WITH a reason, never a tautological 1.0.
        n["faithfulness_check"] = None
        stats["reserved_null"]["faithfulness_check"] += 1
        n["faithfulness_notes"] = (
            S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE
            if r.get("memory_representation") == "raw"
            else "NOT SCORED. No faithfulness proxy was run for this representation.")

        # ---- bearing
        label, evidence = S.build_bearing_evidence(r)
        n["bearing_label"] = label
        n["bearing_evidence"] = evidence
        stats["bearing_labels"][label] = stats["bearing_labels"].get(label, 0) + 1
        n["candidate_pool_size"] = (evidence or {}).get("task_pool_size")

        # ---- retrieval: no context budget was ever enforced (exposed == retrieved on
        #      every row, and the runner has no context cap). Null, not 0, not the
        #      output cap, and not the memory-SELECTION cap from BEARING_SCARCITY.
        n["context_budget"] = None
        stats["reserved_null"]["context_budget"] += 1

        # ---- counterfactual utility
        n["num_replicates"] = cell_n.get(r.get("cell_id"))
        n["confidence_or_stability"] = cell_stability.get(r.get("cell_id"))

        # ---- efficiency
        n["storage_bytes"] = S.compute_storage_bytes(r.get("memory_text"))

        # ---- P3: null by contract; validate.py REJECTS a populated value.
        n["propagation_metadata"] = None
        stats["reserved_null"]["propagation_metadata"] += 1

        n["schema_version"] = S.SCHEMA_VERSION

        # Field order, and a hard check that we produced exactly the contract.
        missing = [f for f in S.FIELD_ORDER if f not in n]
        extra = sorted(set(n) - set(S.FIELD_ORDER))
        if missing or extra:
            raise SystemExit(
                f"migration produced a non-conforming row: missing={missing} extra={extra}")
        out.append({f: n[f] for f in S.FIELD_ORDER})
    return out, stats


# ------------------------------------------------------------------ self-test
def self_test(sample: dict[str, Any]) -> list[str]:
    """Corrupt a migrated row in the shape of each new check, and assert it fires.

    The point is not to confirm the migration works -- the validator already says that.
    It is to prove the NEW CHECKS CAN FAIL. A check only ever run on data it passes has
    not been shown to discriminate.
    """
    log: list[str] = []

    def expect(code: str, mutate, what: str) -> None:
        bad = json.loads(json.dumps(sample))
        mutate(bad)
        codes = {i.code for i in V.validate_row(bad)}
        if code not in codes:
            raise AssertionError(
                f"SELF-TEST FAILED: planted {what} but {code!r} did not fire "
                f"(got {sorted(codes)})")
        log.append(f"PASS {code}: {what}")

    expect("faithfulness_scored_on_raw",
           lambda r: r.update(faithfulness_check=1.0),
           "a tautological 1.0 faithfulness score on a raw memory")
    expect("faithfulness_null_without_reason",
           lambda r: r.update(faithfulness_check=None, faithfulness_notes=""),
           "a null faithfulness score with no stated reason")
    expect("raw_compression_not_unity",
           lambda r: r.update(compression_ratio=0.25),
           "a raw memory claiming 4x compression")
    expect("compression_ratio_mismatch",
           lambda r: r.update(source_span_tokens=(r["memory_tokens"] or 1) * 2),
           "a compression ratio inconsistent with its own denominator")
    expect("storage_bytes_mismatch",
           lambda r: r.update(storage_bytes=1),
           "a storage_bytes that is not the text's byte length")
    expect("bearing_evidence_without_caveat",
           lambda r: r["bearing_evidence"].update(caveat=""),
           "bearing evidence shipped without its caveat")
    expect("bearing_screen_not_content_only",
           lambda r: r["bearing_evidence"].update(screen_is_content_only=False),
           "a bearing screen that let a reward in (would make the contrast circular)")
    expect("discriminativeness_mismatch",
           lambda r: r["bearing_evidence"].update(discriminativeness=0.999),
           "a discriminativeness that is not hits/size")
    expect("candidate_pool_size_mismatch",
           lambda r: r.update(candidate_pool_size=7),
           "a pool size disagreeing with the evidence it came from")
    expect("stability_out_of_range",
           lambda r: r.update(confidence_or_stability=1.5),
           "a stability outside [0,1]")
    expect("p3_field_populated",
           lambda r: r.update(propagation_metadata={"hop": 1}),
           "a P3 propagation field populated in a P1 row")
    expect("absent_latency_reported_as_zero",
           lambda r: r.update(memory_extraction_latency=0.0),
           "a no-call extraction latency written as a measured 0.0")

    # negatives: the clean migrated row must pass, or the checks reject everything.
    issues = [i for i in V.validate_row(sample) if i.severity == V.SEVERITY_ERROR]
    if issues:
        raise AssertionError(
            f"SELF-TEST FAILED: a correctly migrated row was rejected: "
            f"{[str(i) for i in issues[:5]]}")
    log.append("PASS negative-control: a correctly migrated row is accepted")

    # cross-row: num_replicates must be a measurement, not a plan.
    a = json.loads(json.dumps(sample))
    b = json.loads(json.dumps(sample))
    b["replicate_id"] = (a.get("replicate_id") or 0) + 1
    b["row_id"] = S.compute_row_id(b)
    for r in (a, b):
        r["num_replicates"] = 9          # neither cell has 9 rows
    codes = V.validate_dataset([a, b]).codes()
    if "num_replicates_mismatch" not in codes:
        raise AssertionError(
            f"SELF-TEST FAILED: a planned num_replicates that contradicts the rows "
            f"present did not fire (got {sorted(codes)})")
    log.append("PASS num_replicates_mismatch: a planned count contradicting the data")
    return log


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--units", type=Path, default=DEFAULT_UNIT_MANIFEST)
    ap.add_argument("--require-full-join", action="store_true", default=True)
    ap.add_argument("--allow-partial-join", dest="require_full_join",
                    action="store_false")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    rows = S.load_jsonl(args.inp, strict=True)
    units = load_unit_manifest(args.units)
    print(f"read {len(rows)} rows from {args.inp}")
    print(f"unit manifest: {len(units)} units from {args.units}")

    migrated, stats = migrate_rows(rows, units)

    hits, misses = stats["span_join_hits"], stats["span_join_misses"]
    print(f"source-span join: {hits} hit / {misses} miss "
          f"({hits / max(1, hits + misses):.1%})")
    if misses and args.require_full_join:
        raise SystemExit(
            f"REFUSING TO WRITE: {misses} rows did not join to the unit manifest, so "
            f"their compression_ratio would be silently null while others are 1.0. A "
            f"partial join still looks like success. Pass --allow-partial-join to "
            f"accept explicit nulls for the unjoined rows.")

    if args.self_test:
        for line in self_test(migrated[0]):
            print("  " + line)
        print("self-test OK: every new check fired on its planted defect and stayed "
              "quiet on the clean row")

    rep = V.validate_dataset(migrated)
    print("\n--- validation of MIGRATED rows ---")
    print(rep.summary())
    for i in rep.issues[:15]:
        print("  " + str(i))

    print("\nbearing labels:", stats["bearing_labels"])
    print("reserved-null counts:", stats["reserved_null"])

    if not rep.ok:
        raise SystemExit("migrated rows do not validate; nothing written")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    S.write_jsonl_atomic(args.out, migrated)
    print(f"\nwrote {len(migrated)} v2 rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def load_memory_records(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    """(representation, memory_unit_locator) -> the write-time memory record.

    The source of ``faithfulness_detail`` and of ``parent_memory_id``. Keyed on the
    LOCATOR, never on ``memory_id``: memory_id is a content hash and so differs across
    representations BY DESIGN, and joining representations on it returns zero rows,
    which reads as "no data" rather than "wrong key". That mistake has been made three
    times in this project (docs/DEFECT_REGISTER.md); the key here is the locator.
    """
    if path is None or not path.exists():
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        m = json.loads(line)
        out[(m["representation"], m["memory_unit_locator"])] = m
    return out


def load_parent_index(paths: Sequence[Path]) -> dict[str, str]:
    """memory_unit_locator -> the RAW memory_id cut from that same span.

    A summary's parent is the raw span it compressed. That raw memory already exists as
    a published row, so the parent id is a JOIN, not an invention -- but the join is
    only sound if the locator picks out exactly one raw memory_id, so the caller
    verifies uniqueness and refuses on a collision.
    """
    seen: dict[str, set[str]] = {}
    for p in paths:
        if not p.exists():
            continue
        for r in S.load_jsonl(p, strict=True):
            if r.get("memory_representation") != "raw":
                continue
            loc = (r.get("source_episode_metadata") or {}).get("memory_unit_locator")
            if isinstance(loc, str):
                seen.setdefault(loc, set()).add(r["memory_id"])
    collisions = {k: sorted(v) for k, v in seen.items() if len(v) != 1}
    if collisions:
        raise SystemExit(
            f"REFUSING TO WRITE: {len(collisions)} locators map to more than one raw "
            f"memory_id, so parent_memory_id would be ambiguous: "
            f"{list(collisions.items())[:3]}. A join key that is not unique invents "
            f"differences that are not in the data.")
    return {k: next(iter(v)) for k, v in seen.items()}


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
    rows: Sequence[dict[str, Any]], units: dict[str, dict[str, Any]],
    memrecs: dict[tuple[str, str], dict[str, Any]] | None = None,
    parents: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (v3 rows, stats). Pure: the inputs are not mutated."""
    memrecs = memrecs or {}
    parents = parents or {}
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
        "faithfulness": {"scored": 0, "scored_no_numbers": 0,
                         "raw_tautology": 0, "write_failed": 0,
                         "no_record_joined": 0},
        "parent_memory_id": {"joined": 0, "raw_has_no_parent": 0, "unjoined": 0},
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

        # ---- lineage. A RAW span still has no parent memory: its parent is the
        #      episode, which is already source_episode_id, and writing that here would
        #      conflate two different relations. But a SUMMARY or STRUCTURED memory was
        #      compressed FROM the raw span at the same locator, and that raw memory is
        #      a published row with a memory_id -- so the parent is a verified join, not
        #      an invention. schema.py said this field "becomes populatable the moment a
        #      summary or structured arm is run". That moment is v0.2.
        loc_for_parent = (r.get("source_episode_metadata") or {}).get(
            "memory_unit_locator")
        if r.get("memory_representation") == "raw":
            n["parent_memory_id"] = None
            stats["reserved_null"]["parent_memory_id"] += 1
            stats["parent_memory_id"]["raw_has_no_parent"] += 1
        else:
            pid = parents.get(loc_for_parent) if isinstance(loc_for_parent, str) else None
            n["parent_memory_id"] = pid
            if pid is None:
                stats["parent_memory_id"]["unjoined"] += 1
            else:
                stats["parent_memory_id"]["joined"] += 1

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

        # ---- faithfulness: null WITH a TRUE reason on raw, and a REAL SCORE on the
        #      model-written representations.
        #
        #      🔴 The v0.1 line here read: "NOT SCORED. No faithfulness proxy was run
        #      for this representation." Every row was raw, so that branch never
        #      executed and the sentence was never false. It would have become false
        #      on the first summary row: the proxy DOES run, at write time, in
        #      r1_write_representations.py, and its per-memory output sits in
        #      results/repr_scaleup/memories.jsonl. Publishing a null beside a stated
        #      reason that is untrue is worse than publishing a null with no reason,
        #      because a reader has no cue to check it. validate.py now rejects the
        #      combination outright rather than relying on this comment.
        rep_here = r.get("memory_representation")
        rec = memrecs.get((rep_here, loc_for_parent)) if isinstance(
            loc_for_parent, str) else None
        detail = (rec or {}).get("faithfulness")

        if rep_here == "raw":
            n["faithfulness_check"] = None
            n["faithfulness_detail"] = None
            n["faithfulness_notes"] = S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE
            stats["reserved_null"]["faithfulness_check"] += 1
            stats["faithfulness"]["raw_tautology"] += 1
        elif isinstance(detail, dict):
            # The headline float is number_support -- numeric literals present in the
            # source. One axis cannot carry this measurement (structured averages
            # number_support 1.0000 against entity_support 0.8322), so the FULL score
            # ships alongside it and the note says to read them together.
            ns_ = detail.get("number_support")
            has_headline = isinstance(ns_, (int, float)) and not isinstance(ns_, bool)
            n["faithfulness_check"] = float(ns_) if has_headline else None
            n["faithfulness_detail"] = detail
            n["faithfulness_notes"] = S.FAITHFULNESS_SCORED_NOTE.format(
                rule=detail.get("rule_version"))
            if not has_headline:
                # number_support is None when the memory contains NO NUMBERS: an empty
                # denominator, which faithfulness.py deliberately returns as None
                # rather than a perfect 1.0 so it cannot raise a corpus mean. The row
                # IS scored -- entity_support and the contradiction axes are present
                # in faithfulness_detail -- so the note must not read as "unscored".
                n["faithfulness_notes"] += (
                    "\nfaithfulness_check is NULL on this row because the memory "
                    "contains no numeric literal, so number_support has an EMPTY "
                    "DENOMINATOR. That is 'nothing to check', not a perfect score, "
                    "and faithfulness.py returns None rather than 1.0 precisely so a "
                    "number-free memory cannot lift the corpus mean. The other axes "
                    "in faithfulness_detail were measured normally.")
                stats["faithfulness"]["scored_no_numbers"] += 1
            stats["faithfulness"]["scored"] += 1
        elif rec is not None:
            # The write itself failed or was cut off, so there is no well-formed
            # memory to score. A failed write is a DIFFERENT FACT from an unmeasured
            # one, and the note must say which.
            n["faithfulness_check"] = None
            n["faithfulness_detail"] = None
            n["faithfulness_notes"] = S.FAITHFULNESS_WRITE_FAILED_NOTE.format(
                finish=rec.get("finish_reason"))
            stats["faithfulness"]["write_failed"] += 1
        else:
            n["faithfulness_check"] = None
            n["faithfulness_detail"] = None
            n["faithfulness_notes"] = (
                "NOT SCORED. No write-time memory record was joined for this row, so "
                "whether a proxy ran is unknown to this export. This is a JOIN gap, "
                "not a finding about the memory.")
            stats["faithfulness"]["no_record_joined"] += 1

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

        # ---- export provenance: written by scripts/export_hf.py, not here. NULL means
        #      "no licence policy has been applied to this row yet", which is a
        #      different fact from an empty withheld list ("a policy ran and withheld
        #      nothing"). A local ledger is pre-export, so null is the correct value.
        n["license_policy"] = None
        n["text_fields_withheld"] = None
        n["reconstruction_required"] = None

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

    🔴 EVERY PLANT NAMES THE REPRESENTATION IT NEEDS. Until v0.2 this function was
    handed whichever row happened to be first, and every row in the corpus was raw, so
    the raw-only plants (``faithfulness_scored_on_raw``,
    ``raw_compression_not_unity``, ``absent_latency_reported_as_zero``) fired for a
    reason nobody had chosen. Passing a summary ledger silently disarmed three of
    them -- they planted a defect the check was not looking for on that row and the
    check stayed quiet, which the harness would have read as PASS had it not compared
    codes. ``_as_raw`` and ``_as_written`` force the base, so the suite tests the same
    thing whichever ledger is migrated.
    """
    log: list[str] = []

    def _as_raw(r: dict[str, Any]) -> dict[str, Any]:
        r["memory_representation"] = "raw"
        r["memory_writer_model"] = "none:deterministic_span"
        r["memory_writer_cluster"] = "none:deterministic_span"
        r["faithfulness_detail"] = None
        r["faithfulness_check"] = None
        r["faithfulness_notes"] = S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE
        r["memory_extraction_latency"] = None
        r["extraction_cost_proxy"] = 0.0
        r["source_span_tokens"] = r.get("memory_tokens")
        r["compression_ratio"] = 1.0
        r["parent_memory_id"] = None
        return r

    def _as_written(r: dict[str, Any]) -> dict[str, Any]:
        r["memory_representation"] = "summary"
        r["faithfulness_check"] = 1.0
        r["faithfulness_notes"] = "SCORED by the deterministic proxy."
        r["faithfulness_detail"] = {
            "rule_version": "deterministic_proxy@1.0.0", "representation": "summary",
            "number_support": 1.0, "entity_support": 0.9}
        r["compression_ratio"] = None
        r["source_span_tokens"] = None
        return r

    def expect(code: str, mutate, what: str, *, base=None) -> None:
        bad = json.loads(json.dumps(sample))
        if base is not None:
            bad = base(bad)
        mutate(bad)
        codes = {i.code for i in V.validate_row(bad)}
        if code not in codes:
            raise AssertionError(
                f"SELF-TEST FAILED: planted {what} but {code!r} did not fire "
                f"(got {sorted(codes)})")
        log.append(f"PASS {code}: {what}")

    expect("faithfulness_scored_on_raw",
           lambda r: r.update(faithfulness_check=1.0),
           "a tautological 1.0 faithfulness score on a raw memory", base=_as_raw)
    expect("faithfulness_null_without_reason",
           lambda r: r.update(faithfulness_check=None, faithfulness_notes=""),
           "a null faithfulness score with no stated reason")
    expect("raw_compression_not_unity",
           lambda r: r.update(compression_ratio=0.25),
           "a raw memory claiming 4x compression", base=_as_raw)
    expect("compression_ratio_mismatch",
           lambda r: r.update(source_span_tokens=(r["memory_tokens"] or 1) * 2),
           "a compression ratio inconsistent with its own denominator", base=_as_raw)
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
           "a no-call extraction latency written as a measured 0.0", base=_as_raw)

    # --- v3 controls. The defect these exist for is a FALSE STATED REASON, not a
    #     wrong value, so the plant is a sentence rather than a number.
    expect("faithfulness_claimed_unscored_on_a_written_memory",
           lambda r: r.update(
               faithfulness_check=None, faithfulness_detail=None,
               faithfulness_notes=("NOT SCORED. No faithfulness proxy was run for "
                                   "this representation.")),
           "the v0.1 note claiming no proxy ran, on a model-written memory that IS "
           "scorable (the exact sentence v0.1 would have shipped)", base=_as_written)
    expect("faithfulness_detail_on_raw",
           lambda r: r.update(faithfulness_detail={
               "rule_version": "deterministic_proxy@1.0.0", "representation": "raw",
               "number_support": 1.0, "entity_support": 1.0}),
           "a tautological full score attached to a raw memory", base=_as_raw)
    expect("faithfulness_detail_incomplete",
           lambda r: r.update(
               faithfulness_detail={"rule_version": "x", "representation": "summary",
                                    "number_support": 1.0}),
           "a one-axis faithfulness score with entity_support dropped -- the shape "
           "that would report structured as a clean 1.0", base=_as_written)
    expect("faithfulness_check_detail_disagree",
           lambda r: r.update(
               faithfulness_detail={"rule_version": "x", "representation": "summary",
                                    "number_support": 0.5, "entity_support": 0.9}),
           "a headline float that is not the axis it claims to summarise",
           base=_as_written)
    expect("faithfulness_detail_wrong_representation",
           lambda r: r.update(
               faithfulness_detail={"rule_version": "x", "representation": "structured",
                                    "number_support": 1.0, "entity_support": 1.0}),
           "a score joined from the wrong representation's memory", base=_as_written)

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
    ap.add_argument("--memory-records", type=Path, default=None,
                    help="write-time memory records (memories.jsonl). Source of "
                         "faithfulness_detail. Required for a model-written arm.")
    ap.add_argument("--parents", nargs="*", default=[], type=Path,
                    help="already-migrated RAW ledgers, used to resolve "
                         "parent_memory_id for summary/structured rows by locator.")
    ap.add_argument("--require-full-join", action="store_true", default=True)
    ap.add_argument("--allow-partial-join", dest="require_full_join",
                    action="store_false")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    rows = S.load_jsonl(args.inp, strict=True)
    units = load_unit_manifest(args.units)
    memrecs = load_memory_records(args.memory_records)
    parents = load_parent_index(args.parents)
    print(f"read {len(rows)} rows from {args.inp}")
    print(f"unit manifest: {len(units)} units from {args.units}")
    print(f"memory records: {len(memrecs)} from {args.memory_records}")
    print(f"parent index: {len(parents)} raw memories from {len(args.parents)} ledger(s)")

    # A model-written arm without its write-time records would silently produce a
    # column of nulls that LOOKS like a deliberate reservation. Refuse instead.
    needs_records = {r.get("memory_representation") for r in rows} - {"raw"}
    if needs_records and not memrecs:
        raise SystemExit(
            f"REFUSING TO WRITE: this ledger contains model-written representations "
            f"{sorted(needs_records)}, whose faithfulness IS measurable, but no "
            f"--memory-records file was given. Exporting them with a null "
            f"faithfulness_detail would publish an unmeasured-looking column for a "
            f"quantity that was in fact measured at write time.")
    if needs_records and not parents:
        raise SystemExit(
            f"REFUSING TO WRITE: model-written rows need --parents (the migrated raw "
            f"ledgers) to resolve parent_memory_id. Without it every derived memory "
            f"would claim to have no parent, which is false.")

    migrated, stats = migrate_rows(rows, units, memrecs, parents)

    pstat = stats["parent_memory_id"]
    if pstat["unjoined"]:
        raise SystemExit(
            f"REFUSING TO WRITE: {pstat['unjoined']} model-written rows did not join "
            f"to a raw parent memory, so their parent_memory_id would be null while "
            f"others carry an id. A half-matched join still looks like success.")
    fstat = stats["faithfulness"]
    if fstat["no_record_joined"]:
        raise SystemExit(
            f"REFUSING TO WRITE: {fstat['no_record_joined']} rows found no write-time "
            f"memory record. Their faithfulness would be an unexplained null.")

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
    print("faithfulness:", stats["faithfulness"])
    print("parent_memory_id:", stats["parent_memory_id"])
    print("reserved-null counts:", stats["reserved_null"])

    if not rep.ok:
        raise SystemExit("migrated rows do not validate; nothing written")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    S.write_jsonl_atomic(args.out, migrated)
    print(f"\nwrote {len(migrated)} {S.SCHEMA_VERSION} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

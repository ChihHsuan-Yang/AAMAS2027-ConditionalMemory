#!/usr/bin/env python3
"""Prepare the v0.6 length-control ledger for export, WITHOUT editing it in place.

🔴 Why this script exists, and why it is not a flag on the exporter.

Same shape as ``scripts/prep_v05_inputs.py``, one release later. ``export_hf.py`` does
not migrate schemas, and ``results/length_control/cells.jsonl`` was written directly at
schema v3, so the ``migrate_schema_v2.py`` path that fills a deliberately-null field's
REASON never ran over it. All 4,432 rows therefore carry ``faithfulness_check = None``
with an EMPTY ``faithfulness_notes``, and the validator warns
``faithfulness_null_without_reason`` on every one of them -- rightly, because *an
unexplained null cannot be told apart from an unpopulated field*. Every other slice in
the published dataset carries a reason; shipping 4,432 silences would be the one
exception.

What this script does NOT do: it does not invent a reason, and it does not copy a
measured value. Each note is written ONLY where its own premise is VERIFIED TRUE on the
row, by re-deriving the premise from the row's own bytes. Rows failing their premise are
left untouched and reported, so a wrong reason cannot be written onto a row it does not
describe. (v0.2's lesson, restated at v0.4 and v0.5: *a documented reason for a null is
a CLAIM, and it decays.*)

Three notes, because this slice has three genuinely different reasons for its null --
and the project's existing constant is true of only one of them:

  A. FULL-SPAN EXTRACTIVE (``provenance.identical_to_raw_text`` is true). The memory
     text IS the source span, verbatim. ``S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE``
     applies **unchanged** -- it is the project's own constant and says exactly this.
     🔴 Which rows these are is MEASURED, not read off a field. The A/A arm
     ``trunc_last_20000`` renders the whole span on 554/554 and ``trunc_last_4096``
     does on 94 more, so keying on the ARM NAME would write the wrong note on 648
     rows; but keying on ``provenance.identical_to_raw_text`` would only move the
     trust from the arm name to a flag. This script compares the row's text with its
     own cell's full span and CROSS-CHECKS the flag against that comparison, refusing
     the row if they disagree. A planted row that set the flag true while carrying
     truncated text was accepted before this check existed.

  B. TRUNCATED EXTRACTIVE. Here the constant's own sentence -- "the memory text IS the
     source span, verbatim" -- is FALSE: the text is a verbatim contiguous SLICE of
     that span, not the span. The tautology argument still holds (every token is
     copied, so a source-grounded proxy returns 1.0 by construction), but the premise
     must be stated as what it is. The note is written only where this script has
     CHECKED, on the row, that the text really is a contiguous substring of that same
     cell's full-span text in the ``raw`` arm.

  C. MODEL-WRITTEN (``summary`` / ``structured``). A real score EXISTS: the proxy ran
     at write time and the per-memory result is in ``results/repr_scaleup/memories.jsonl``.
     The score is ATTACHED -- ``faithfulness_check`` (number_support) plus the full
     multi-axis ``faithfulness_detail`` -- exactly as ``migrate_schema_v2.py`` does for
     repr_scaleup, with ``S.FAITHFULNESS_SCORED_NOTE`` and a suffix saying the
     measurement came from the write pass and naming the join.
     🔴 This script first wrote a POINTER note and left the field null, following the
     shape of the v3-native slices published at v0.5. ``validate.py`` rejected all
     1,108 rows: a model-written memory IS scorable, so a note denying it is false.
     The rule's own comment warns that rewording a note until the guard's substring
     disappears is "a guard satisfied by editing a string rather than by changing the
     fact" -- so the note was not reworded; the measurement was attached. Only rows
     whose write-pass record is reached by BOTH join keys, agreeing on the same
     record, and whose detail names this row's representation, are filled.

``faithfulness_notes`` is in none of MEMORY_ID_KEYS / CELL_ID_KEYS / ROW_ID_KEYS, so
writing it cannot move any published id. That is asserted here rather than assumed.

Outputs go to a separate directory; the source ledger is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from p1mem import schema as S  # noqa: E402

DET = "none:deterministic_span"

#: The write-pass artifact that holds the real score for the model-written arms.
WRITE_PASS_ARTIFACT = "results/repr_scaleup/memories.jsonl"

TRUNCATED_NOTE = (
    "NOT SCORED. This memory is a length-controlled TRUNCATION: extractive, verbatim, "
    "written by a deterministic span rule with zero writer calls, and verified by this "
    "export to be a contiguous substring of the same cell's full source span (the "
    "`raw` arm's memory_text for this pair_key and replicate). A source-grounded "
    "faithfulness proxy therefore compares copied text with the text it was copied "
    "from and returns 1.0 by construction, exactly as it does for an untruncated raw "
    "memory -- see FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE, whose argument this shares.\n"
    "🔴 The constant's own wording is NOT reused here because one of its sentences "
    "would be false: the memory text is a verbatim SLICE of the source span, not the "
    "source span. Truncation removes content, and a tautological 1.0 says nothing "
    "about how much was removed. The quantity that does measure that is "
    "`provenance.bearing_content_retained`, which is populated on this row; "
    "`provenance.length_budget` and `provenance.memory_tokens_official` give the "
    "budget and the realised length."
)

#: Appended to the project's own FAITHFULNESS_SCORED_NOTE on these rows, because the
#: proxy ran on the WRITE pass and this ledger is a READ pass over frozen memory text.
MODEL_WRITTEN_PROVENANCE_SUFFIX = (
    "\nPROVENANCE OF THIS SCORE. It was measured on the WRITE pass, not by the "
    "length-control run that produced this row: the length-control arms REUSE the "
    "frozen memory text written by scripts/r1_write_representations.py, so the "
    "write-pass record is the record for this exact memory. The score is attached "
    "rather than merely pointed at because a model-written memory IS scorable and a "
    "'not scored' note on it would be false. The join is "
    "(memory_source_span.memory_unit_locator, memory_representation) against "
    + WRITE_PASS_ARTIFACT + "; this export asserted that key is unique there, and "
    "confirmed INDEPENDENTLY, by sha256 of memory_text, that both keys select the "
    "SAME record. Re-derive it rather than taking our word for it."
)


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_write_pass(path: Path) -> tuple[dict, dict]:
    """Two independent indexes over the write-pass artifact, so the join can be
    cross-checked rather than trusted. Returns (by_locator_rep, by_sha_rep)."""
    by_loc: dict[tuple[str, str], dict] = {}
    by_sha: dict[tuple[str, str], list[dict]] = {}
    for line in path.open():
        m = json.loads(line)
        rep = m.get("representation")
        loc = m.get("memory_unit_locator")
        key = (loc, rep)
        assert key not in by_loc, f"write-pass key {key!r} is NOT unique -- refusing"
        by_loc[key] = m
        t = m.get("memory_text")
        if isinstance(t, str):
            by_sha.setdefault((_sha(t), rep), []).append(m)
    return by_loc, by_sha


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--write-pass", type=Path,
                    default=REPO_ROOT / WRITE_PASS_ARTIFACT)
    args = ap.parse_args(argv)

    # An id must not be able to move. Assert, do not trust.
    for name, keys in (("MEMORY_ID_KEYS", S.MEMORY_ID_KEYS),
                       ("CELL_ID_KEYS", S.CELL_ID_KEYS),
                       ("ROW_ID_KEYS", S.ROW_ID_KEYS)):
        assert "faithfulness_notes" not in keys, (
            f"faithfulness_notes is in {name}; filling it would re-mint published ids")

    rows = S.load_jsonl(args.inp, strict=True)
    by_loc, by_sha = load_write_pass(args.write_pass)

    # The full-span text for each (pair_key, replicate), from the `raw` arm. This is
    # what premise B is checked against. The key must be unique within the arm or the
    # check is void -- 554 rows over 277 pair_keys, so pair_key ALONE is not enough.
    full: dict[tuple, str] = {}
    for r in rows:
        if r["provenance"]["arm"] != "raw":
            continue
        k = (r["provenance"]["pair_key"], r["replicate_id"])
        assert k not in full, f"raw-arm key {k!r} is not unique -- refusing"
        full[k] = r["memory_text"]

    ids_before = [(r.get("memory_id"), r.get("cell_id"), r.get("row_id")) for r in rows]

    stats = {"full_span_tautology": 0, "truncated_slice": 0, "model_written_scored": 0,
             "model_written_scored_no_numbers": 0, "already_had_one": 0,
             "premise_false_left_untouched": 0}
    refusals: list[str] = []

    for r in rows:
        notes = r.get("faithfulness_notes")
        if isinstance(notes, str) and notes.strip():
            stats["already_had_one"] += 1
            continue

        rep = r.get("memory_representation")
        prov = r.get("provenance") or {}
        det_writer = (r.get("memory_writer_model") == DET
                      and r.get("memory_writer_cluster") == DET)
        unscored = (r.get("faithfulness_check") is None
                    and r.get("faithfulness_detail") is None)

        # ---- C. model-written: a real score exists at write time, so ATTACH IT.
        #
        # 🔴 The first version of this script wrote a POINTER note instead, keeping
        # the field null. validate.py rejected all 1,108 rows with
        # ``faithfulness_claimed_unscored_on_a_written_memory``: a model-written memory
        # IS scorable, so a note saying otherwise is false. Its own comment warns that
        # rewording the note until the substring disappears is "a guard satisfied by
        # editing a string rather than by changing the fact" -- so the fix is to attach
        # the measurement, exactly as migrate_schema_v2.py does for repr_scaleup.
        if rep in ("summary", "structured"):
            loc = (r.get("memory_source_span") or {}).get("memory_unit_locator")
            a = by_loc.get((loc, rep))
            b = by_sha.get((_sha(r["memory_text"]), rep), [])
            detail = (a or {}).get("faithfulness")
            if not (unscored and a is not None and len(b) == 1 and a is b[0]
                    and isinstance(detail, dict)):
                stats["premise_false_left_untouched"] += 1
                refusals.append(f"{rep} row {r.get('row_id')}: write-pass join did not "
                                f"verify (locator={loc!r}, sha-matches={len(b)}, "
                                f"detail={type(detail).__name__})")
                continue
            if detail.get("representation") not in (None, rep):
                stats["premise_false_left_untouched"] += 1
                refusals.append(f"{rep} row {r.get('row_id')}: joined detail is for "
                                f"representation {detail.get('representation')!r}")
                continue
            ns_ = detail.get("number_support")
            has_headline = isinstance(ns_, (int, float)) and not isinstance(ns_, bool)
            r["faithfulness_check"] = float(ns_) if has_headline else None
            r["faithfulness_detail"] = detail
            note = S.FAITHFULNESS_SCORED_NOTE.format(rule=detail.get("rule_version"))
            if not has_headline:
                # number_support is None when the memory contains NO NUMBERS: an empty
                # denominator, which faithfulness.py returns as None rather than a
                # perfect 1.0 so a number-free memory cannot lift the corpus mean. The
                # row IS scored, so the note must not read as "unscored". Wording
                # follows migrate_schema_v2.py so the two paths say the same thing.
                note += (
                    "\nfaithfulness_check is NULL on this row because the memory "
                    "contains no numeric literal, so number_support has an EMPTY "
                    "DENOMINATOR. That is 'nothing to check', not a perfect score, "
                    "and faithfulness.py returns None rather than 1.0 precisely so a "
                    "number-free memory cannot lift the corpus mean. The other axes "
                    "in faithfulness_detail were measured normally.")
                stats["model_written_scored_no_numbers"] += 1
            r["faithfulness_notes"] = note + MODEL_WRITTEN_PROVENANCE_SUFFIX
            stats["model_written_scored"] += 1
            continue

        # ---- A / B. extractive
        #
        # 🔴 Which of the two notes applies is MEASURED here, by comparing this row's
        # text with its own cell's full span. It is NOT read off
        # ``provenance.identical_to_raw_text``. A planted row that sets that flag true
        # while carrying truncated text was ACCEPTED by the first version of this
        # script, which would have written "the memory text IS the source span,
        # verbatim" onto a row where that is false -- the exact failure the premise
        # check exists to prevent. The flag is now CROSS-CHECKED against the
        # measurement and a disagreement is a refusal, because the flag ships.
        if rep == "raw" and det_writer and unscored:
            src = full.get((prov.get("pair_key"), r.get("replicate_id")))
            text = r["memory_text"]
            is_full = isinstance(src, str) and text == src
            is_slice = isinstance(src, str) and text != src and text in src
            flag = prov.get("identical_to_raw_text")
            if src is None:
                stats["premise_false_left_untouched"] += 1
                refusals.append(f"raw row {r.get('row_id')}: no full-span row joined "
                                f"for pair_key {prov.get('pair_key')!r}")
            elif flag is not is_full:
                stats["premise_false_left_untouched"] += 1
                refusals.append(
                    f"raw row {r.get('row_id')}: provenance.identical_to_raw_text="
                    f"{flag!r} CONTRADICTS the measured comparison (identical="
                    f"{is_full}); refusing to write a note keyed on a false flag")
            elif is_full:
                r["faithfulness_notes"] = S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE
                stats["full_span_tautology"] += 1
            elif is_slice:
                r["faithfulness_notes"] = TRUNCATED_NOTE
                stats["truncated_slice"] += 1
            else:
                stats["premise_false_left_untouched"] += 1
                refusals.append(
                    f"raw row {r.get('row_id')}: memory_text is not a contiguous "
                    f"substring of its cell's full span")
            continue

        stats["premise_false_left_untouched"] += 1
        refusals.append(f"row {r.get('row_id')}: no note's premise holds "
                        f"(rep={rep!r}, det_writer={det_writer}, unscored={unscored})")

    ids_after = [(r.get("memory_id"), r.get("cell_id"), r.get("row_id")) for r in rows]
    assert ids_before == ids_after, "an id moved -- refusing to write"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / (args.inp.name if args.inp.name != "cells.jsonl"
                          else f"{args.inp.parent.name}.jsonl")
    S.write_jsonl_atomic(out, rows)

    print(f"{args.inp}: {len(rows)} rows -> {out}")
    for k, v in stats.items():
        print(f"  {k:32s} {v}")
    if refusals:
        print(f"  🔴 {len(refusals)} rows REFUSED a note (premise false). First few:")
        for line in refusals[:10]:
            print(f"      {line}")
        print("  That is correct behaviour -- a reason must not be written onto a row "
              "it does not describe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""LEN2: the contrasts, the controls and the verdict for the length control test.

Reads ``results/length_control/cells.jsonl`` (all eight arms, ONE session) and
applies ``docs/LENGTH_CONTROL_PRECOMMITMENT.md`` -- which was committed at
f702aaf BEFORE any truncated reader call existed. Nothing here chooses an
analysis after seeing an outcome: the primary contrast, the estimator, the CI
method, the controls and the meaning of every result were fixed in advance,
and §7's precedence rule decides the verdict.

WHAT THIS SCRIPT MAY NOT DO
---------------------------
* It may not read the verdict off the sensitivity, the secondary, or any
  subgroup. §7: "the verdict is taken from the primary contrast as defined in
  §4.2".
* It may not report an effect conditioned on cells that retained the bearing
  content (n=39, or n=9 for both-arms). §4.3 pre-registers that subgroup as
  OFF LIMITS because an effect measured on cells selected for retaining the
  signal is circular. Retention is reported as a 2x2 DESCRIPTIVE table.
* It may not coerce a null reward to 0.0. §4.4: ``reward is None`` means
  COULD NOT BE SCORED, and such cells are a NAMED exclusion with a count.

THE JOIN
--------
``memory_id`` is a per-representation CONTENT HASH and differs across arms by
construction, so joining on it returns ZERO rows and prints a well-formed
table of nothing. ``condition_id`` EMBEDS the representation name, so it is
equally useless as a join key. The arms join on
``(memory_unit_locator, future_task_id)`` = ``provenance.pair_key``. Both
traps are asserted, in both directions, before any number is computed.

No estimator is reimplemented: ``cluster_bootstrap_paired`` is imported from
``scripts/r3_analyze_representations.py``, the project's existing routine, as
§4.2 requires.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

from p1mem.analysis.common import jsonable  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

# §4.2: "the project's existing cluster_bootstrap_paired, not a
# reimplementation". Imported, not copied.
from r3_analyze_representations import (  # noqa: E402
    bootstrap_paired,
    cluster_bootstrap_paired,
)

BOOT_SEED = 20261001       # §4.2, fixed in the precommitment
N_BOOT = 10000             # §4.2
STRATA = ("BEARING", "MATCHED_CONTROL")
PRIMARY_T = "trunc_last_matched"
PRIMARY_S = "summary"
LADDER = ("trunc_last_matched", "trunc_last_1024", "trunc_last_4096")
#: §5.4 -- the published-data Raw-Summary BEARING gap, used ONLY as the size of
#: the synthetic uplift planted in C-POWER. It is a reference for the plant,
#: never a comparator for a measured number (§5.1 forbids cross-session
#: comparison), and it is re-derived in-session below as well.
CPOWER_PUBLISHED_GAP = 0.2741


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def f4(x) -> str:
    return "n/a" if x is None else f"{x:+.4f}"


def ci_str(d: dict) -> str:
    if d.get("ci_lower") is None:
        return "[n/a]"
    return f"[{d['ci_lower']:+.4f}, {d['ci_upper']:+.4f}]"


def _reader_delta(rows: list[dict]) -> dict:
    """§2.4's check IN THE TOKENIZER THAT CONSUMES THE TEXT.

    The budget is DEFINED in the official tokenizer but CONSUMED by the
    reader, so a matched budget in one is not automatically matched in the
    other. §2.4 claims the length-controlled arm is, if anything, marginally
    SHORTER than Summary in o200k_harmony -- so a surviving extractive
    advantage cannot have been bought with tokens. That claim is load-bearing
    for the primary contrast, so it is re-derived here per cell, from the
    ROWS' own recorded ``provenance.memory_tokens_reader_o200k``, rather than
    quoted from a summary or trusted to a ledger field.
    """
    tl: dict[str, int] = {}
    sm: dict[str, int] = {}
    for r in rows:
        p = r.get("provenance") or {}
        n = p.get("memory_tokens_reader_o200k")
        if n is None:
            continue
        if p.get("arm") == "trunc_last_matched":
            tl[p["memory_unit_locator"]] = n
        elif p.get("arm") == "summary":
            sm[p["memory_unit_locator"]] = n
    common = sorted(set(tl) & set(sm))
    if not common:
        return {"_unavailable": "no per-cell reader token counts found on the "
                                "rows for both arms"}
    d = sorted(tl[k] - sm[k] for k in common)
    n = len(d)
    return {"n_cells": n, "median": d[n // 2],
            "mean": round(sum(d) / n, 3), "min": d[0], "max": d[-1],
            "p5": d[max(0, int(0.05 * n))], "p95": d[min(n - 1, int(0.95 * n))],
            "_reading": "negative = the length-controlled arm is SHORTER than "
                        "summary in the reader's own tokenizer"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=Path,
                    default=REPO / "results/length_control/cells.jsonl")
    ap.add_argument("--run-ledger", type=Path,
                    default=REPO / "results/ledgers/length_control_run.json")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/length_control_result.json")
    args = ap.parse_args()

    out: dict[str, Any] = {
        "_what": "LEN2: length-controlled representation test, analysed against "
                 "docs/LENGTH_CONTROL_PRECOMMITMENT.md (committed f702aaf, "
                 "BEFORE any truncated reader call existed).",
        "generated_at_utc": utc_now(),
        "precommitment": "docs/LENGTH_CONTROL_PRECOMMITMENT.md",
        "n_boot": args.n_boot, "bootstrap_seed": BOOT_SEED,
    }

    rows = load_jsonl(args.cells)
    run = json.loads(args.run_ledger.read_text())
    log(f"loaded {len(rows)} rows from {args.cells.name}")

    by_arm: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_arm[(r.get("provenance") or {})["arm"]].append(r)
    arms = sorted(by_arm)
    log(f"arms: { {a: len(by_arm[a]) for a in arms} }")

    # ============================================================ CONTROLS
    # Controls come FIRST and the verdict is conditional on them: §7's O5
    # dominates all other outcomes, so a failure here means nothing else in
    # this file is reportable.
    ctrl: dict[str, Any] = {}

    # ---- C-SESSION (§5.1) ----------------------------------------------
    run_ids = {(r.get("provenance") or {}).get("run_id") for r in rows}
    sess = {(r.get("provenance") or {}).get("session_start_utc") for r in rows}
    ctrl["C_SESSION"] = {
        "_what": "§5.1: gpt-oss-120b is deterministic WITHIN a session and not "
                 "across one (554/1,124 rows differed on a byte-identical "
                 "re-issue 24h later). Every arm -- including raw and summary, "
                 "which have published numbers -- was re-executed in ONE "
                 "process. Published values are a prior reference only, never "
                 "a comparator.",
        "n_distinct_run_ids": len(run_ids), "run_ids": sorted(x for x in run_ids if x),
        "n_distinct_session_starts": len(sess),
        "n_arms_executed": len(arms),
        "wall_clock_s": run.get("wall_clock_s"),
        "n_preexisting_cache_rows": run.get("n_preexisting_cache_rows"),
        "cache_hits_during_run": run.get("cache_hits"),
        "real_endpoint_calls": run.get("real_endpoint_calls"),
        "planned_calls": run.get("planned_calls"),
        # 🔴 An ABSENT field must not read as a passing zero -- that is the
        # "absent input defaults to a plausible zero" shape. Each clause is
        # evaluated on a field that is PRESENT, and the strongest evidence
        # does not depend on any optional one: if every planned call was a
        # REAL endpoint call and the cache served nothing, then every row
        # came from this process, whatever a cache file held beforehand.
        "every_planned_call_was_issued_fresh": bool(
            run.get("real_endpoint_calls") is not None
            and run.get("planned_calls") is not None
            and run.get("cache_hits") == 0
            and run["real_endpoint_calls"] + run.get("errors", 0)
            == run["planned_calls"]),
        "_preexisting_cache_field_present":
            "n_preexisting_cache_rows" in run,
        "passed": bool(
            len(run_ids) == 1 and len(sess) == 1 and len(arms) == 8
            and run.get("cache_hits") == 0
            and run.get("real_endpoint_calls") is not None
            and run.get("planned_calls") is not None
            and run["real_endpoint_calls"] + run.get("errors", 0)
            == run["planned_calls"]
            # when the field IS recorded it must also be zero
            and not run.get("n_preexisting_cache_rows", 0)),
    }

    # ---- C-JOIN (§5.5): BOTH traps, in both directions ------------------
    def pk(r: dict) -> str:
        return (r.get("provenance") or {})["pair_key"]

    # The precommitment fixes the cell set at 277 (§4.1) and forbids adding or
    # dropping a cell on any outcome. That is asserted against the RUN LEDGER's
    # own count rather than hardcoded into every comparison, so a deliberate
    # smoke subset fails ONE explicit check instead of silently failing three
    # unrelated controls and reporting a false O5.
    n_expected = int(run.get("n_cells") or 0)
    ctrl["C_CELLSET"] = {
        "_what": "§4.1: the 277 cells present in all three published "
                 "representations -- 57 memories, 124 tasks, 135 BEARING + 142 "
                 "MATCHED_CONTROL. Fixed; no cell is added or dropped on any "
                 "outcome.",
        "n_cells_in_run_ledger": n_expected,
        "is_smoke_run_not_a_result": bool(run.get("is_smoke_run_not_a_result")),
        "passed": bool(n_expected == 277
                       and not run.get("is_smoke_run_not_a_result")),
    }

    keys = {a: {pk(r) for r in by_arm[a]} for a in arms}
    common = set.intersection(*keys.values())
    mid_sets = {a: {r["memory_id"] for r in by_arm[a]} for a in arms}
    cid_sets = {a: {r["condition_id"] for r in by_arm[a]} for a in arms}
    n_mid_common = len(set.intersection(*mid_sets.values()))
    n_cid_common = len(set.intersection(*cid_sets.values()))
    ctrl["C_JOIN"] = {
        "_what": "memory_id is a per-representation CONTENT HASH and "
                 "condition_id EMBEDS the representation name; joining on "
                 "either returns ZERO rows across arms and prints a "
                 "well-formed table of nothing. The join key is "
                 "(memory_unit_locator, future_task_id).",
        "n_pair_keys_per_arm": {a: len(keys[a]) for a in arms},
        "n_common_to_all_arms": len(common),
        "n_memory_ids_common_to_all_arms": n_mid_common,
        "n_condition_ids_common_to_all_arms": n_cid_common,
        "passed": bool(len(common) == n_expected and n_mid_common == 0
                       and n_cid_common == 0),
    }
    log(f"  [C-JOIN] locator {len(common)} | memory_id {n_mid_common} | "
        f"condition_id {n_cid_common}")

    # ---- C5 POSITION (§3.2) --------------------------------------------
    pos: dict[str, set] = collections.defaultdict(set)
    for r in rows:
        p = r.get("provenance") or {}
        if p.get("target_position") is not None:
            pos[p["pair_key"]].add(p["target_position"])
    n_pos_bad = sum(1 for v in pos.values() if len(v) != 1)
    ctrl["C5_POSITION"] = {
        "_what": "§3.2: position is seeded by (task_id, MANIFEST memory_id) -- "
                 "never the per-arm content hash, never replicate_id. Varying "
                 "position changed the answer in 8 of 12 cells "
                 "(docs/POSITION_EFFECT.md), so an arm that moved the target "
                 "would confound representation with position.",
        "n_pair_keys": len(pos),
        "n_pair_keys_with_differing_position_across_arms": n_pos_bad,
        "plant_from_run": next((p for p in run["controls"]["C_PLANT"]
                                if p["control"].startswith("P3_")), None),
        "passed": bool(n_pos_bad == 0 and len(pos) == n_expected),
    }

    # ---- C-AA (§5.2): the identity positive control ---------------------
    # trunc_last_20000 renders text byte-identical to raw (max Raw = 19,801)
    # but travels under a different condition_id and a different content hash,
    # so it is a genuinely separate set of calls. Its rewards must reproduce
    # raw's EXACTLY, in-session.
    idx: dict[tuple[str, str, int], dict] = {}
    for r in rows:
        idx[((r.get("provenance") or {})["arm"], pk(r), r["replicate_id"])] = r
    reps_seen = sorted({r["replicate_id"] for r in rows})
    aa_cells, aa_same_text, aa_same_rw, aa_same_out, aa_diff = 0, 0, 0, 0, []
    for k in sorted(common):
        for rep in reps_seen:
            a, b = idx.get(("raw", k, rep)), idx.get(("trunc_last_20000", k, rep))
            if a is None or b is None:
                continue
            aa_cells += 1
            if a["memory_text"] == b["memory_text"]:
                aa_same_text += 1
            # Rewards must match EXACTLY. None==None counts as agreement only
            # when both are None -- an unscored cell is not a reproduction.
            same_rw = (a["reward_with_memory"] == b["reward_with_memory"]
                       and a["reward_without_memory"] == b["reward_without_memory"]
                       and a["delta_utility"] == b["delta_utility"])
            if same_rw:
                aa_same_rw += 1
            if a["output_with_memory"] == b["output_with_memory"]:
                aa_same_out += 1
            if not same_rw and len(aa_diff) < 10:
                aa_diff.append({"pair_key": k, "replicate_id": rep,
                                "raw_dU": a["delta_utility"],
                                "aa_dU": b["delta_utility"]})
    ctrl["C_AA"] = {
        "_what": "§5.2: trunc_last_20000 renders text byte-identical to raw in "
                 "277/277 (budget 20,000 >= max Raw 19,801) but travels under a "
                 "different condition_id and content hash, so it is a genuinely "
                 "separate set of calls with a KNOWN CORRECT ANSWER. It "
                 "exercises the entire new code path end to end.",
        "n_comparisons": aa_cells,
        "n_memory_text_byte_identical": aa_same_text,
        "n_reward_triples_identical": aa_same_rw,
        "n_reader_outputs_byte_identical": aa_same_out,
        "disagreements": aa_diff,
        "cache_keys_separate_the_arms":
            (run["controls"].get("C_AA_text_identity") or {})
            .get("cache_keys_differ_under_identical_context"),
        "n_unique_memory_ids_raw_vs_aa": len(mid_sets.get("raw", set())
                                             & mid_sets.get("trunc_last_20000", set())),
        "passed": bool(aa_cells > 0 and aa_same_text == aa_cells
                       and aa_same_rw == aa_cells),
    }
    log(f"  [C-AA] text identical {aa_same_text}/{aa_cells}; rewards identical "
        f"{aa_same_rw}/{aa_cells}; outputs identical {aa_same_out}/{aa_cells}")

    # ---- C-PLANT, C-TOK, C-DET, C-WITHOUT: carried from the run ---------
    ctrl["C_PLANT"] = {
        "_what": "§5.3: each guard is run against a DELIBERATELY BROKEN input "
                 "and must FAIL; the unplanted case must pass. A guard "
                 "verified only on its home case is not known to discriminate.",
        "controls": run["controls"]["C_PLANT"],
        "n_total": len(run["controls"]["C_PLANT"]),
        "n_passed": sum(1 for p in run["controls"]["C_PLANT"] if p.get("passed")),
        "passed": all(p.get("passed") for p in run["controls"]["C_PLANT"]),
    }
    # C-TOK is RE-DERIVED from the per-cell truncation rows, never read off the
    # run ledger's summary. Two reasons, one of them measured:
    #   * house rule: never quote a number you have not re-derived;
    #   * the summary's max|delta| mixes two different things. A cell whose
    #     WHOLE text already fits the budget was never truncated, and its
    #     shortfall is a property of the source segment, not of the rule.
    #     Measured on the 4-cell smoke artifact, that mixture reported
    #     max|delta| = 17,127 -- the length of an untruncated segment -- which
    #     says nothing about whether the rule hits its budget.
    taj = args.cells.parent / "truncation_audit.json"
    ta_rows = json.loads(taj.read_text())
    for t in ta_rows:
        # 'identical_to_raw' is exactly 'the slice is the whole text', i.e.
        # nothing was cut. Older ledgers carry only that field.
        t["_cut"] = bool(t.get("was_truncated", not t["identical_to_raw"]))
    cut = [t for t in ta_rows if t["_cut"]]
    over = [t for t in cut if t["delta_vs_budget"] > 0]
    maxabs = max((abs(t["delta_vs_budget"]) for t in cut), default=None)
    ctrl["C_TOK"] = {
        "_what": "§5.5/§2.4: the budget is matched in the OFFICIAL tokenizer by "
                 "binary search on characters, and the READER tokenizer's count "
                 "(o200k_harmony) is recorded per cell so the match is auditable "
                 "in the tokenizer that actually consumes it. Re-derived here "
                 "from the per-cell rows.",
        "n_slices_built": len(ta_rows),
        "n_actually_truncated": len(cut),
        "n_whole_text_already_fit": len(ta_rows) - len(cut),
        "n_over_budget": len(over),
        "max_abs_delta_vs_budget_official_cut_cells_only": maxabs,
        "n_exact_among_cut": sum(1 for t in cut if t["delta_vs_budget"] == 0),
        "delta_histogram_cut_cells": dict(sorted(collections.Counter(
            t["delta_vs_budget"] for t in cut).items())),
        "_inexact_note": "a residual of -1 is a TOKENIZER BOUNDARY, not an "
                         "under-filled budget: measured on "
                         "trunc_first_matched|3331c568:2-2 (budget 196) the "
                         "maximal prefix is 510 chars = 195 tokens and 511 "
                         "chars = 197, so no prefix of exactly 196 tokens "
                         "exists. Maximality, not exact equality, is what the "
                         "run asserts.",
        "reader_tokenizer_delta_trunc_minus_summary": _reader_delta(rows),
        "memory_tokens_by_arm": run["memory_tokens_by_arm"],
        # Over budget is a hard failure. Under by a token on a boundary cell is
        # recorded, not failed -- the run already asserted MAXIMALITY per cell.
        "passed": bool(maxabs is not None and len(over) == 0 and maxabs <= 1),
    }
    # C-DET's negative control is checked on EVERY arm, not only on raw.
    # §2.3 states the detector fires on 0/142 MATCHED_CONTROL "which is the
    # detector's negative control on this set" -- and that is exactly true of
    # the EXTRACTIVE arms, whose text is a verbatim slice of the segment.
    # Measured here, the MODEL-WRITTEN summary arm fires on a small number of
    # MATCHED_CONTROL cells: a writer can emit a string matching a gold answer
    # the source span never contained. That is a property of the writer, not a
    # broken detector, so it is REPORTED per arm rather than folded into a
    # single pass/fail that would either hide it or fail the run for it. The
    # binding requirement is the one §2.3 names: silence on the extractive
    # arms, where the text is the source.
    mc_fires = {a: run["retention_by_arm"].get(a, {}).get("MATCHED_CONTROL_fires", 0)
                for a in sorted(run["retention_by_arm"])}
    extractive = [a for a in mc_fires if a == "raw" or a.startswith("trunc_")]
    ctrl["C_DET"] = {
        "_what": "§5.5: the gold detector's own controls pass before any "
                 "retention number is reported, and the detector is silent on "
                 "the MATCHED_CONTROL cells of every EXTRACTIVE arm.",
        **run["controls"]["leakage_detector_selftest"],
        "retention_by_arm": run["retention_by_arm"],
        "matched_control_fires_by_arm": mc_fires,
        "extractive_arms_checked": sorted(extractive),
        "n_matched_control_fires_on_extractive_arms":
            sum(mc_fires[a] for a in extractive),
        "_model_written_arm_note":
            "a nonzero count on summary/structured is a property of the "
            "WRITER (it can emit a string the source span never contained), "
            "not a detector fault; reported, not failed on",
        "passed": bool(run["controls"]["leakage_detector_selftest"]["n_pass"]
                       == run["controls"]["leakage_detector_selftest"]["n_total"]
                       and sum(mc_fires[a] for a in extractive) == 0),
    }
    cw = run["controls"].get("C_WITHOUT_cross_arm_identity") or {}
    ctrl["C_WITHOUT"] = {
        "_what": "§6/Amendment A1.4: the WITHOUT arm is REGENERATED per arm, "
                 "never reused. Its bytes are identical across arms by "
                 "construction, so eight independent generations coming back "
                 "byte-identical is a MEASURED demonstration that the reader is "
                 "deterministic in-session. Reusing one answer would have made "
                 "that agreement true by construction.",
        **cw,
        "passed": bool(cw.get("n_cells_compared") and not cw.get("n_disagreeing")),
    }

    # ---- C-KEY: no arm is a cache alias of another --------------------
    # The WITHOUT arm renders byte-identical context in all eight arms, and
    # trunc_last_20000's WITH context is byte-identical to raw's. If the cache
    # key did not separate those, one generation would be served to several
    # arms and their agreement would be TRUE BY CONSTRUCTION -- which would
    # make C-AA and C-WITHOUT unfalsifiable. Measured directly on the cache
    # the run wrote: count the request groups whose rendered context is shared
    # across arms, and require every stored key hash to still be distinct.
    cache_file = args.cells.parent / "eval_cache.jsonl"
    ckey: dict[str, Any] = {"_what": "no arm may be served another arm's "
                                     "cached generation; otherwise C-AA and "
                                     "C-WITHOUT agree by construction."}
    if cache_file.exists():
        crows = [json.loads(l) for l in cache_file.read_text().splitlines() if l.strip()]
        groups: dict[tuple, set] = collections.defaultdict(set)
        for cr in crows:
            k = cr["key"]
            groups[(k["future_task_id"], k["source_item_id"], k["arm"],
                    k["replicate_id"], k["context_sha256"])].add(k["memory_repr"])
        shared = sum(1 for v in groups.values() if len(v) > 1)
        hashes = {cr["key_hash"] for cr in crows}
        ckey.update({
            "n_cached_responses": len(crows),
            "n_distinct_key_hashes": len(hashes),
            "n_identical_context_groups_spanning_multiple_arms": shared,
            "passed": bool(len(hashes) == len(crows) and shared > 0),
            "_reading": "shared>0 proves arms DO render identical bytes; "
                        "distinct hashes == rows proves they were still "
                        "issued and stored separately",
        })
    else:
        ckey["passed"] = False
        ckey["_why"] = ("no eval_cache.jsonl beside the rows; cache "
                        "separation could not be verified")
    ctrl["C_KEY_no_cross_arm_cache_alias"] = ckey

    out["controls"] = ctrl
    controls_ok = all(v.get("passed") for v in ctrl.values())
    log(f"CONTROLS: { {k: v.get('passed') for k, v in ctrl.items()} }")

    # ================================================= per-cell mean dU
    # §4.4: reward None means COULD NOT BE SCORED. Such a cell is excluded
    # from the paired contrast as a NAMED exclusion with its count, never
    # silently and never as 0.0.
    stratum_of: dict[str, str] = {}
    task_of: dict[str, str] = {}
    for r in rows:
        p = r.get("provenance") or {}
        stratum_of[p["pair_key"]] = p["stratum"]
        task_of[p["pair_key"]] = r["future_task_id"]

    mean_du: dict[str, dict[str, float]] = {}
    unscored: dict[str, dict[str, Any]] = {}
    for a in arms:
        acc: dict[str, list[float]] = collections.defaultdict(list)
        n_null = 0
        null_keys: list[str] = []
        for r in by_arm[a]:
            if r["delta_utility"] is None or r["error_code_if_any"]:
                n_null += 1
                null_keys.append(pk(r))
                continue
            acc[pk(r)].append(float(r["delta_utility"]))
        mean_du[a] = {k: float(np.mean(v)) for k, v in acc.items()}
        unscored[a] = {"n_rows_unscored": n_null,
                       "n_pair_keys_affected": len(set(null_keys)),
                       # The REASON, not just the count: an http_error and a
                       # truncated reasoning response are different facts
                       # about the same null, and only one of them is a
                       # property of the endpoint.
                       "error_codes": dict(sorted(collections.Counter(
                           str(r["error_code_if_any"]) for r in by_arm[a]
                           if r["error_code_if_any"]).items())),
                       "pair_keys": sorted(set(null_keys))[:20]}
    # A cell with ONE failed replicate keeps a mean computed from the other
    # one. That is correct -- discarding a scored replicate would throw away a
    # real measurement -- but it means such a cell is averaged over fewer
    # draws than its neighbours, so the count is surfaced rather than left
    # implicit in an unchanged n.
    partial: dict[str, int] = {}
    for a in arms:
        cnt: dict[str, int] = collections.Counter()
        for r in by_arm[a]:
            if r["delta_utility"] is not None and not r["error_code_if_any"]:
                cnt[pk(r)] += 1
        full = max(cnt.values()) if cnt else 0
        partial[a] = sum(1 for k, v in cnt.items() if v < full)
    out["cells_averaged_over_fewer_replicates"] = {
        "_what": "cells where at least one replicate could not be scored, so "
                 "the cell mean rests on fewer draws than its neighbours'. "
                 "Kept (a scored replicate is a real measurement) and counted.",
        "per_arm": partial,
    }

    out["unscored_rows_named_exclusion"] = {
        "_rule": "§4.4: reward None means COULD NOT BE SCORED. Never coerced "
                 "to 0.0. Reported with its count and excluded from the paired "
                 "contrast as a NAMED exclusion.",
        "per_arm": unscored,
        "n_rows_unscored_total": sum(u["n_rows_unscored"] for u in unscored.values()),
    }

    # ================================================= THE PRIMARY (§4.2)
    def paired(arm_a: str, arm_b: str, stratum: str | None) -> dict:
        """Per-cell paired difference dU(a) - dU(b), task-clustered CI."""
        ks = sorted(k for k in common
                    if k in mean_du.get(arm_a, {}) and k in mean_du.get(arm_b, {})
                    and (stratum is None or stratum_of[k] == stratum))
        diffs = [mean_du[arm_a][k] - mean_du[arm_b][k] for k in ks]
        by_task: dict[str, list[float]] = collections.defaultdict(list)
        for k, d in zip(ks, diffs):
            by_task[task_of[k]].append(d)
        e = {
            "_definition": f"per cell: mean dU({arm_a}) - mean dU({arm_b}); same "
                           f"memory, same task, same filler, same position, "
                           f"session-matched",
            "stratum": stratum or "ALL",
            "n_cells": len(ks),
            "n_task_clusters": len(by_task),
            "cell_level": bootstrap_paired(diffs, n_boot=args.n_boot, seed=BOOT_SEED),
            "task_clustered": cluster_bootstrap_paired(
                by_task, n_boot=args.n_boot, seed=BOOT_SEED),
        }
        # docs/ZERO_CONTRIBUTORS.md: a cell failing in both arms contributes an
        # exact 0.0 and is not a measurement of "no difference".
        nzd = [d for d in diffs if d != 0.0]
        e["contributors"] = {"n_nominal": len(diffs), "n_nonzero": len(nzd),
                             "conditional_mean_over_nonzero":
                                 float(np.mean(nzd)) if nzd else None}
        return e

    primary = paired(PRIMARY_T, PRIMARY_S, "BEARING")
    out["PRIMARY"] = {
        "_what": "§4.2 THE CONTRAST THAT CARRIES THE CLAIM: per-cell paired "
                 "difference on BEARING cells, "
                 "D = dU(trunc_last_matched) - dU(summary), both arms "
                 "session-matched, matched exposed-token budget. 95% CI by "
                 "task-clustered bootstrap, 10,000 resamples of whole task "
                 "clusters, seed 20261001, percentile method.",
        **primary,
    }
    log(f"PRIMARY  D(trunc_last_matched - summary | BEARING) = "
        f"{f4(primary['task_clustered']['mean'])} "
        f"{ci_str(primary['task_clustered'])} "
        f"n={primary['n_cells']} clusters={primary['n_task_clusters']}")

    # Pre-registered sensitivity: reported ALWAYS, never used to pick a
    # headline (§4.2, §7).
    out["SENSITIVITY_vs_structured"] = {
        "_what": "§4.2 pre-registered sensitivity of the primary. Reported "
                 "always; the verdict is NOT taken from it.",
        **paired(PRIMARY_T, "structured", "BEARING"),
    }

    # The two contrasts §7's O2 needs besides the primary.
    out["RAW_vs_TRUNC"] = {
        "_what": "§7 O2 requires dU(raw) - dU(trunc_last_matched) to be "
                 "positive with a CI excluding zero before the Raw advantage "
                 "may be called an exposure-budget effect.",
        **paired("raw", PRIMARY_T, "BEARING"),
    }
    out["RAW_vs_SUMMARY_in_session"] = {
        "_what": "the session-matched Raw-Summary BEARING gap. NOTE: the "
                 "published +0.2741 was measured ACROSS sessions (Raw "
                 "2026-09-29, compressed 2026-09-30) and §5.1 forbids using it "
                 "as a comparator; this is its in-session replacement.",
        **paired("raw", PRIMARY_S, "BEARING"),
    }

    # ---- per-arm mean dU, every arm, both strata ------------------------
    per_arm: dict[str, Any] = {}
    for a in arms:
        ent: dict[str, Any] = {}
        for st in (None,) + STRATA:
            ks = sorted(k for k in common if k in mean_du[a]
                        and (st is None or stratum_of[k] == st))
            vals = [mean_du[a][k] for k in ks]
            bt: dict[str, list[float]] = collections.defaultdict(list)
            for k in ks:
                bt[task_of[k]].append(mean_du[a][k])
            ent[st or "ALL"] = {
                "n_cells": len(vals),
                "mean": float(np.mean(vals)) if vals else None,
                "task_clustered": cluster_bootstrap_paired(
                    bt, n_boot=args.n_boot, seed=BOOT_SEED),
            }
        per_arm[a] = ent
    out["mean_delta_utility_by_arm"] = {
        "_what": "mean dU per arm on the pair keys common to ALL eight arms, so "
                 "every number describes the same memories against the same "
                 "tasks in the same session.",
        "per_arm": per_arm,
    }
    for a in arms:
        e = per_arm[a]["BEARING"]
        log(f"  {a:20s} BEARING dU={f4(e['mean'])} {ci_str(e['task_clustered'])} "
            f"n={e['n_cells']}")

    # ================================================== THE LADDER (§4.2)
    ret_by_arm = run["retention_by_arm"]
    ladder: list[dict[str, Any]] = []
    for a in LADDER:
        e = per_arm[a]["BEARING"]
        ladder.append({
            "arm": a,
            "budget": run["arms"][a]["budget"] or "matched to each cell's own "
                                                  "summary token count",
            "median_memory_tokens_official":
                run["memory_tokens_by_arm"][a]["median_official"],
            "bearing_content_retained_n": ret_by_arm[a].get("BEARING_fires", 0),
            "bearing_content_retained_frac":
                ret_by_arm[a].get("BEARING_fires", 0) / 135.0,
            "mean_dU_BEARING": e["mean"],
            "ci": [e["task_clustered"].get("ci_lower"),
                   e["task_clustered"].get("ci_upper")],
            "n_cells": e["n_cells"],
        })
    # Does utility track RETENTION or TOKEN COUNT? §4.2: "If utility tracks
    # retention rather than token count, the mechanism is content presence;
    # the budget is instrumental."
    full = [{"arm": a, "ret": ret_by_arm[a].get("BEARING_fires", 0) / 135.0,
             "tok": run["memory_tokens_by_arm"][a]["median_official"],
             "du": per_arm[a]["BEARING"]["mean"]}
            for a in ("trunc_first_matched",) + LADDER + ("trunc_last_20000",)]
    rr = [x["ret"] for x in full]
    tt = [np.log10(x["tok"]) for x in full]
    dd = [x["du"] for x in full]
    out["LADDER"] = {
        "_what": "§4.2, pre-registered as the IDENTIFICATION, not decoration: "
                 "dU for trunc_last at {matched, 1024, 4096} against measured "
                 "retention at the same budgets. If utility tracks RETENTION "
                 "rather than TOKEN COUNT, the mechanism is content presence "
                 "and the budget is instrumental.",
        "rungs": ladder,
        "with_floor_and_ceiling": full,
        "pearson_dU_vs_retention": float(np.corrcoef(rr, dd)[0, 1]),
        "pearson_dU_vs_log10_tokens": float(np.corrcoef(tt, dd)[0, 1]),
        "_corr_caveat": "5 points, each an arm-level mean; these correlations "
                        "describe the shape of the ladder and carry no CI. "
                        "Two numbers over five points can be moved by one "
                        "rung, so they are NOT a test and nothing in the "
                        "verdict rests on them. The paired step contrasts "
                        "below are the part of the ladder that carries an "
                        "interval.",
        # Each STEP as a paired, task-clustered contrast on the same cells --
        # the ladder's claim ("utility recovers as the budget grows") stated
        # in a form that has a CI, rather than as the shape of five dots.
        "paired_steps_BEARING": {
            f"{b}_minus_{a}": paired(b, a, "BEARING")
            for a, b in (("trunc_last_matched", "trunc_last_1024"),
                         ("trunc_last_1024", "trunc_last_4096"),
                         ("trunc_last_4096", "trunc_last_20000"),
                         ("trunc_first_matched", "trunc_last_matched"))
        },
    }
    for r_ in ladder:
        log(f"  [ladder] {r_['arm']:20s} tok={r_['median_memory_tokens_official']:8.0f} "
            f"retention={r_['bearing_content_retained_frac']:.3f} "
            f"dU={f4(r_['mean_dU_BEARING'])}")

    # ======================================== C-POWER (§5.4), binding O2/O4
    # A null is not evidence unless the test could have detected the effect.
    # Plant a synthetic uplift equal to the measured Raw-Summary BEARING gap
    # into the trunc_last_matched arm and require the primary CI to exclude
    # zero.
    insession_gap = out["RAW_vs_SUMMARY_in_session"]["task_clustered"]["mean"]
    cpower: dict[str, Any] = {
        "_what": "§5.4: a null is not evidence unless the test could have "
                 "detected the effect. Into the trunc_last_matched arm's dU, "
                 "plant a synthetic uplift equal to the measured Raw-Summary "
                 "BEARING gap and require the primary CI to exclude zero. "
                 "A reported null is accompanied by this number or it is not "
                 "reported.",
        "primary_ci_half_width": (
            (primary["task_clustered"]["ci_upper"]
             - primary["task_clustered"]["ci_lower"]) / 2.0
            if primary["task_clustered"].get("ci_lower") is not None else None),
    }
    for label, gap in (("published_cross_session_reference", CPOWER_PUBLISHED_GAP),
                       ("in_session_raw_minus_summary", insession_gap)):
        if gap is None:
            continue
        ks = sorted(k for k in common if stratum_of[k] == "BEARING"
                    and k in mean_du[PRIMARY_T] and k in mean_du[PRIMARY_S])
        diffs = [mean_du[PRIMARY_T][k] + gap - mean_du[PRIMARY_S][k] for k in ks]
        bt: dict[str, list[float]] = collections.defaultdict(list)
        for k, d in zip(ks, diffs):
            bt[task_of[k]].append(d)
        res = cluster_bootstrap_paired(bt, n_boot=args.n_boot, seed=BOOT_SEED)
        # 🔴 DEFECT GF-4's OWN FIX, APPLIED HERE. "excludes zero" from a
        # zero-width interval is ARITHMETIC, NOT POWER: with too few clusters
        # there is nothing to resample, the bootstrap returns a degenerate
        # point, and the control fires on everything -- certifying a null with
        # a test that cannot fail. Observed in exactly this shape on the 4-cell
        # smoke artifact: detected=True, CI [+0.2741, +0.2741], width 0.
        lo_, hi_ = res.get("ci_lower"), res.get("ci_upper")
        width = (hi_ - lo_) if (lo_ is not None and hi_ is not None) else None
        nondegenerate = bool(width is not None and width > 0)
        enough = bool(res.get("n_clusters", 0) >= 5)
        cpower[label] = {"planted_uplift": gap, "n_cells": len(ks),
                         "task_clustered": res,
                         "ci_width": width,
                         "interval_is_nondegenerate": nondegenerate,
                         "has_at_least_5_task_clusters": enough,
                         "detected": bool(res.get("excludes_zero")
                                          and nondegenerate and enough)}
        # Log the GUARDED verdict, not the raw bootstrap flag: a message that
        # says detected=True beside a zero-width interval is the "check's
        # message is part of the check" defect.
        log(f"  [C-POWER] plant {gap:+.4f} -> {f4(res['mean'])} {ci_str(res)} "
            f"width={width} clusters={res.get('n_clusters')} "
            f"detected={cpower[label]['detected']}")
    # Negative half: planting ZERO must NOT be detected, or "detection" is
    # just the estimator always excluding zero.
    ks0 = sorted(k for k in common if stratum_of[k] == "BEARING"
                 and k in mean_du[PRIMARY_T] and k in mean_du[PRIMARY_S])
    bt0: dict[str, list[float]] = collections.defaultdict(list)
    for k in ks0:
        bt0[task_of[k]].append(mean_du[PRIMARY_T][k] - mean_du[PRIMARY_S][k])
    zero_res = cluster_bootstrap_paired(bt0, n_boot=args.n_boot, seed=BOOT_SEED)
    cpower["negative_control_zero_uplift"] = {
        "_what": "planting NOTHING must reproduce the primary exactly. This is "
                 "the other half of GF-4: a detector that fires on a zero "
                 "plant as well as on a real one measures nothing. It BINDS "
                 "only when the primary is a null (O2/O4) -- when the primary "
                 "itself excludes zero, so does this, and that is the real "
                 "effect rather than a vacuous detector.",
        "task_clustered": zero_res,
        "reproduces_primary_exactly": bool(
            zero_res.get("mean") == primary["task_clustered"].get("mean")),
        "fires_on_zero_plant": bool(zero_res.get("excludes_zero")),
    }
    # C-POWER passes only if a REAL planted effect is detected by a
    # NON-DEGENERATE interval over enough clusters. §5.4: "A reported null is
    # accompanied by this number or it is not reported."
    cpower["passed"] = bool(
        cpower.get("in_session_raw_minus_summary", {}).get("detected")
        or cpower.get("published_cross_session_reference", {}).get("detected"))
    cpower["_binds_on"] = ("O2 and O4 -- a null is not evidence unless the "
                           "test could have detected the effect")
    out["C_POWER"] = cpower

    # ====================================== SECONDARY (§4.2): B - MC per arm
    # The published table's own shape: within-memory paired B-MC over the 57
    # memories, so the new arms appear on the same footing as raw/summary.
    mem_of = {pk(r): (r.get("provenance") or {})["memory_unit_locator"] for r in rows}
    secondary: dict[str, Any] = {}
    for a in arms:
        per_mem: dict[str, dict[str, list[float]]] = collections.defaultdict(
            lambda: {"BEARING": [], "MATCHED_CONTROL": []})
        for k, v in mean_du[a].items():
            if k in common:
                per_mem[mem_of[k]][stratum_of[k]].append(v)
        diffs, mems = [], []
        for m, d in sorted(per_mem.items()):
            if d["BEARING"] and d["MATCHED_CONTROL"]:
                diffs.append(float(np.mean(d["BEARING"]))
                             - float(np.mean(d["MATCHED_CONTROL"])))
                mems.append(m)
        secondary[a] = {"n_memories": len(diffs),
                        **bootstrap_paired(diffs, n_boot=args.n_boot, seed=BOOT_SEED)}
    out["SECONDARY_B_minus_MC_by_arm"] = {
        "_what": "§4.2 SECONDARY, in the published Contribution-B table's own "
                 "shape: within-memory paired B-MC over the 57 memories, so the "
                 "new arms appear on the same footing as raw/summary/structured. "
                 "The verdict is NOT taken from this.",
        "per_arm": secondary,
    }

    # ================================ §4.3 the OFF-LIMITS subgroup, as a table
    ret_fire: dict[tuple[str, str], bool] = {}
    for r in rows:
        p = r.get("provenance") or {}
        ret_fire[(p["arm"], p["pair_key"])] = bool(p.get("bearing_content_retained"))
    bear = sorted(k for k in common if stratum_of[k] == "BEARING")
    tab = collections.Counter(
        (ret_fire.get((PRIMARY_T, k), False), ret_fire.get((PRIMARY_S, k), False))
        for k in bear)
    out["RETENTION_2x2_DESCRIPTIVE_ONLY"] = {
        "_what": "§4.3: conditioning on cells that retained the bearing content "
                 "(n=39 trunc, n=9 both) is PRE-REGISTERED AS EXCLUDED FROM THE "
                 "VERDICT -- an effect measured on cells selected for retaining "
                 "the signal is circular, and n=9 cannot carry a CI. Reported as "
                 "a 2x2 DESCRIPTIVE table and never as a conditioned effect "
                 "estimate.",
        "trunc_last_matched x summary, on BEARING (n=135)": {
            "both": tab[(True, True)], "trunc_only": tab[(True, False)],
            "summary_only": tab[(False, True)], "neither": tab[(False, False)]},
        "🔴": "NO effect estimate is computed on any cell of this table.",
    }

    # ====================================================== §7 THE VERDICT
    # Precedence, applied exactly: O5 dominates all. O4 is checked before
    # O1/O2/O3. Among those the sign and CI of the PRIMARY decide.
    tc = primary["task_clustered"]
    d_mean, d_lo, d_hi = tc.get("mean"), tc.get("ci_lower"), tc.get("ci_upper")
    excl = bool(tc.get("excludes_zero"))
    rt = out["RAW_vs_TRUNC"]["task_clustered"]
    t_abs = per_arm[PRIMARY_T]["BEARING"]["task_clustered"]
    s_abs = per_arm[PRIMARY_S]["BEARING"]["task_clustered"]

    steps: list[str] = []
    if not controls_ok:
        verdict, why = "O5", ("the harness failed its own control: "
                              + ", ".join(k for k, v in ctrl.items()
                                          if not v.get("passed")))
        steps.append("O5 dominates all: a control failed.")
    else:
        steps.append("O5 does NOT apply: C-AA reproduces raw exactly and every "
                     "C-PLANT guard fired on its planted defect.")
        # O4: both T and S at ~0 with CIs including zero, AND the ladder shows
        # no recovery at 1,024/4,096, AND C-POWER passes.
        t_zero = not t_abs.get("excludes_zero")
        s_zero = not s_abs.get("excludes_zero")
        ladder_flat = all(
            not per_arm[a]["BEARING"]["task_clustered"].get("excludes_zero")
            for a in ("trunc_last_1024", "trunc_last_4096"))
        if t_zero and s_zero and ladder_flat and cpower["passed"]:
            verdict = "O4"
            why = ("at this budget the bearing content is absent from every "
                   "arm and the comparison cannot be identified: both T and S "
                   "sit at ~0 with CIs including zero, and the ladder shows no "
                   "recovery at 1,024/4,096.")
            steps.append("O4 applies and is checked BEFORE O1/O2/O3: a "
                         "condition that retained nothing cannot adjudicate "
                         "representation.")
        else:
            steps.append(
                f"O4 does NOT apply: T_CI_excludes_0={not t_zero}, "
                f"S_CI_excludes_0={not s_zero}, ladder_flat={ladder_flat}, "
                f"C_POWER_passed={cpower['passed']} -- O4 requires all of "
                f"(T~0, S~0, flat ladder, C-POWER passes).")
            if excl and d_mean > 0:
                verdict = "O1"
                why = ("at equal exposed length the extractive representation "
                       "preserves more downstream utility than model-written "
                       "compression; the more-tokens explanation fails on its "
                       "own terms.")
            elif excl and d_mean < 0:
                verdict = "O3"
                why = ("model-written compression is BETTER than content-blind "
                       "extraction at an equal budget; Story 2 inverts.")
            else:
                # O2 as WRITTEN has three clauses, and each is recorded
                # separately so a partially-met O2 cannot be reported as a
                # fully-met one:
                #   (a) the primary CI includes zero                [here]
                #   (b) C-POWER shows a ~0.15 effect was detectable [C_POWER]
                #   (c) dU(raw) - dU(trunc) > 0 with a CI excluding zero
                raw_beats_trunc = bool(rt.get("excludes_zero")
                                       and (rt.get("mean") or 0) > 0)
                out["O2_clauses"] = {
                    "a_primary_ci_includes_zero": True,
                    "b_c_power_detects_planted_effect": bool(cpower["passed"]),
                    "c_raw_minus_trunc_positive_and_excludes_zero":
                        raw_beats_trunc,
                    "all_three_met": bool(cpower["passed"] and raw_beats_trunc),
                }
                verdict = "O2"
                # 🔴 §5.4 is binding here: "A reported null is accompanied by
                # this number or it is not reported." An earlier draft of this
                # branch ASSERTED that C-POWER showed the effect was
                # detectable, in the verdict text, without checking it -- a
                # check whose message states something it never verified. If
                # C-POWER did not pass, the primary is not evidence of no
                # difference; it is absence of evidence, and the text must say
                # that rather than the opposite.
                if cpower["passed"]:
                    why = ("the primary CI includes zero while C-POWER shows "
                           "the test could have detected the pre-registered "
                           "effect: extractive and model-written compression "
                           "are indistinguishable once length is held fixed")
                else:
                    why = ("the primary CI includes zero, but C-POWER did NOT "
                           "pass -- the test is not shown able to detect the "
                           "pre-registered effect, so this is ABSENCE OF "
                           "EVIDENCE, not evidence of no difference. §5.4: a "
                           "reported null is accompanied by that number or it "
                           "is not reported")
                why += (", and dU(raw)-dU(trunc) is positive with a CI "
                        "excluding zero, so the Raw advantage is an "
                        "exposure-budget effect."
                        if raw_beats_trunc else
                        ". NOTE: dU(raw)-dU(trunc_last_matched) does NOT "
                        "exclude zero, so O2's second clause is only "
                        "partially met and the exposure-budget reading is "
                        "weaker than O2 as written anticipated.")
            steps.append(f"Among O1/O2/O3 the sign and CI of the PRIMARY decide: "
                         f"mean={f4(d_mean)}, CI={ci_str(tc)}, "
                         f"excludes_zero={excl} -> {verdict}.")
        steps.append("The verdict is taken from the PRIMARY contrast only -- "
                     "not the sensitivity, not the secondary, not any subgroup "
                     "(§7).")

    # §5.4 again, as a FIELD and not only as prose: whether the null-shaped
    # outcomes may be reported at all.
    null_shaped = verdict in ("O2", "O4")
    out["NULL_IS_REPORTABLE"] = {
        "_rule": "§5.4: C-POWER is binding on O2 and O4. A null is not "
                 "evidence unless the test could have detected the effect.",
        "verdict_is_null_shaped": null_shaped,
        "c_power_passed": bool(cpower["passed"]),
        "reportable": bool((not null_shaped) or cpower["passed"]),
    }

    out["VERDICT"] = {
        "_rule": "§7 pre-registered precedence: O5 dominates all; O4 is checked "
                 "BEFORE O1/O2/O3; among those the sign and CI of the primary "
                 "decide. All five outcomes are acceptable and none was aimed "
                 "for.",
        "outcome": verdict,
        "why": why,
        "precedence_trace": steps,
        "primary_mean": d_mean, "primary_ci": [d_lo, d_hi],
        "primary_n_cells": primary["n_cells"],
        "primary_n_task_clusters": primary["n_task_clusters"],
        "controls_all_passed": controls_ok,
        "null_is_reportable": out["NULL_IS_REPORTABLE"]["reportable"],
    }
    log(f"VERDICT: {verdict} -- {why}")

    write_json_atomic(args.out, jsonable(out))
    try:
        shown = args.out.relative_to(REPO)
    except ValueError:
        shown = args.out
    log(f"result -> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

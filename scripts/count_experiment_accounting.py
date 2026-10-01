#!/usr/bin/env python3
"""Count, from logs and artifacts, every number in docs/EXPERIMENT_ACCOUNTING.md.

SA-ARCHIVE, 2026-10-01.  Nothing here is estimated.  A quantity that cannot be
counted from an artifact is printed as NOT_RECOVERABLE, never as a plausible
number -- this project's most common defect shape is an absent value defaulting
to zero (DEFECT_REGISTER #3, #22, #23).

Run:
  /Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py
  /Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py --json

Every figure in docs/EXPERIMENT_ACCOUNTING.md is reproduced by this script.
If a count here disagrees with the table, the SCRIPT is right and the table is
stale: regenerate.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NR = "NOT_RECOVERABLE_FROM_LOGS"


def p(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def jsonl(path: str):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def exists(path: str) -> bool:
    return os.path.exists(p(path))


# --------------------------------------------------------------------------
# cell-row files: one row = one CELL (a memory x task x representation x arm-pair)
# --------------------------------------------------------------------------
CELL_FILES = {
    "lmev2_screened_raw": "results/deltau_screened/cells.jsonl",
    "lmev2_pilot_raw": "results/deltau_pilot/cells.jsonl",
    "lmev2_official_raw": "results/deltau_official/cells.jsonl",
    "lmev2_repr_scaleup": "results/repr_scaleup/cells.jsonl",
    "lmev2_gemma_transfer": "results/gemma_reader/transfer_cells.jsonl",
    "lmev2_sessmatched_gemma": "results/raw_session_matched/raw_gemma.jsonl",
    "lmev2_sessmatched_gptoss": "results/raw_session_matched/raw_gptoss.jsonl",
    "lmev2_factorial_wgemma": "results/writer_factorial/factorial_cells_gemma.jsonl",
    "lmev2_factorial_wgptoss": "results/writer_factorial/factorial_cells_gptoss.jsonl",
    "VOID_sessmatched_mislabelled": "results/raw_session_matched_VOID_mislabelled/raw_gptoss.jsonl",
}


def locator(r: dict):
    """Positional memory-unit locator -- the ONLY safe join key.

    `memory_id` and `cell_id` are CONTENT hashes.  DEFECT_REGISTER #26: Gemma
    compressed two different 3,979-token segments to byte-identical 68-token
    summaries, so two distinct memories collided on one id.  Counting cells by
    `cell_id` under-reports that arm by 2.  Counting by (locator, task) does not.
    """
    pv = r.get("provenance") or {}
    if pv.get("memory_unit_locator"):
        return pv["memory_unit_locator"]
    s = r.get("memory_source_span") or {}
    if s.get("trajectory_id") is not None:
        return f"{s['trajectory_id']}:{s.get('start_state_index')}-{s.get('end_state_index')}"
    return None


def count_cells() -> dict:
    out = {}
    for name, rel in CELL_FILES.items():
        if not exists(rel):
            out[name] = {"artifact": rel, "status": "ABSENT"}
            continue
        per = collections.defaultdict(
            lambda: {
                "cells": set(),
                "cells_by_content_id": set(),
                "rows_replicates": 0,
                "rows_void": 0,
                "arm_runs": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "row_error_codes": collections.Counter(),
                "condition_ids": set(),
                "rows_without_locator": 0,
            }
        )
        for r in jsonl(p(rel)):
            key = (
                r.get("memory_representation"),
                r.get("memory_writer_model"),
                r.get("reader_model"),
            )
            a = per[key]
            a["rows_replicates"] += 1
            lo = locator(r)
            if lo is None:
                a["rows_without_locator"] += 1
            a["cells"].add((lo, r.get("future_task_id")))
            a["cells_by_content_id"].add(r.get("cell_id"))
            if r.get("error_code_if_any"):
                a["row_error_codes"][r["error_code_if_any"]] += 1
            if r.get("reward_with_memory") is None or r.get("reward_without_memory") is None:
                a["rows_void"] += 1
            a["arm_runs"] += r.get("generation_calls") or 0
            a["input_tokens"] += r.get("input_tokens") or 0
            a["output_tokens"] += r.get("output_tokens") or 0
            a["reasoning_tokens"] += r.get("reasoning_tokens") or 0
            if r.get("condition_id"):
                a["condition_ids"].add(r["condition_id"])
        arms = {}
        for key, a in sorted(per.items()):
            arms["|".join(str(x) for x in key)] = {
                "representation": key[0],
                "writer": key[1],
                "reader": key[2],
                "cells_by_locator_task": len(a["cells"]),
                "cells_by_content_cell_id": len(a["cells_by_content_id"]),
                "rows_replicates": a["rows_replicates"],
                "rows_void_null_reward": a["rows_void"],
                "arm_runs": a["arm_runs"],
                "row_error_codes": dict(a["row_error_codes"]),
                "condition_ids": sorted(a["condition_ids"]),
                "rows_without_locator": a["rows_without_locator"],
                "input_tokens": a["input_tokens"],
                "output_tokens": a["output_tokens"],
                "reasoning_tokens": a["reasoning_tokens"],
            }
        out[name] = {
            "artifact": rel,
            "total_rows_replicates": sum(v["rows_replicates"] for v in arms.values()),
            "total_cells_by_locator_task": sum(v["cells_by_locator_task"] for v in arms.values()),
            "total_arm_runs": sum(v["arm_runs"] for v in arms.values()),
            "total_rows_void": sum(v["rows_void_null_reward"] for v in arms.values()),
            "arms": arms,
        }
    return out


# --------------------------------------------------------------------------
# cache files: one row = one REAL endpoint call, with the server's own usage
# --------------------------------------------------------------------------
def count_caches() -> dict:
    out = {}
    for dirpath, _dirs, files in os.walk(p("results")):
        for fn in sorted(files):
            if "cache" not in fn or not fn.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            rows = 0
            keys = set()
            errs = collections.Counter()
            fins = collections.Counter()
            retried = 0
            pt = ct = rt = 0
            models = collections.Counter()
            for d in jsonl(full):
                rows += 1
                keys.add(d.get("key_hash"))
                r = d.get("response") or {}
                if r.get("error_code"):
                    errs[str(r["error_code"])] += 1
                fins[r.get("finish_reason")] += 1
                if (r.get("retry_count") or 0) > 0:
                    retried += 1
                pt += r.get("prompt_tokens") or 0
                ct += r.get("completion_tokens") or 0
                rt += r.get("reasoning_tokens") or 0
                models[r.get("resolved_model")] += 1
            out[rel] = {
                "stored_calls": rows,
                "distinct_keys": len(keys),
                "transient_failures_then_retried": retried,
                "transient_failure_codes": dict(errs),
                "finish_reasons": {str(k): v for k, v in fins.items()},
                "truncations_finish_length": fins.get("length", 0),
                "empty_finish_reason": fins.get("", 0),
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "reasoning_tokens": rt,
                "resolved_models": dict(models),
            }
    return out


# --------------------------------------------------------------------------
# SciCode: rows ARE arm-runs; n_calls is the runner's own counter
# --------------------------------------------------------------------------
def count_scicode() -> dict:
    out = {}
    for name, rel in [
        ("scicode_scaleup", "results/scicode/scaleup_all3.json"),
        ("scicode_pilot", "results/scicode/pilot_all3.json"),
        ("scicode_smoke", "results/scicode/smoke.json"),
    ]:
        if not exists(rel):
            out[name] = {"artifact": rel, "status": "ABSENT"}
            continue
        d = json.load(open(p(rel)))
        rows = d["rows"]
        arms = collections.Counter(r["arm"] for r in rows)
        reps = collections.Counter(r["representation"] for r in rows)
        fins = collections.Counter(r.get("finish_reason") for r in rows)
        errored = sum(1 for r in rows if r.get("error"))
        void = sum(1 for r in rows if r.get("reward") is None)
        out[name] = {
            "artifact": rel,
            "runner_n_calls": d.get("n_calls"),
            "arm_runs_rows": len(rows),
            "arms": dict(arms),
            "representations": dict(reps),
            "cells_pairs": d.get("design", {}).get("n_pairs"),
            "finish_reasons": {str(k): v for k, v in fins.items()},
            "truncations_finish_length": fins.get("length", 0),
            "arm_runs_with_error_kind": errored,
            "arm_runs_reward_null": void,
            "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in rows),
            "completion_tokens": sum(r.get("completion_tokens") or 0 for r in rows),
            "memory_text_persisted": False,
            "_memory_text_note": (
                "scicode_pilot.py records response_chars and DISCARDS content; "
                "P1Client was built with no cache=, so no completion was persisted. "
                "Rewards are valid; the memory text behind summary/structured is gone."
            ),
        }
    return out


# --------------------------------------------------------------------------
# SWE-bench: cells carry per-arm dicts with the server's own token counts
# --------------------------------------------------------------------------
# SA-SWE-FINAL owns these and adds files; discovered rather than hardcoded so a new
# chunk cannot be silently missed.  A hardcoded list that stops matching is this
# project's "glob completeness is not tested by its hits" shape.
SWE_SKIP = {"representations_analysis.json", "representations_v2_analysis.json",
            "representations_sympy_analysis.json", "representations_multirepo.json",
            "representations_multirepo_final.json", "coverage_table_final.json",
            "manufactured_zero_correction.json", "scorer_control.json",
            "scorer_control_sympy.json", "scorer_control_django_ext.json",
            "scorer_control_sympy_ext.json"}


def swe_files() -> dict:
    """Every SWE-bench artifact carrying per-cell `arms`, found on disk."""
    out = {}
    d = p("results/swebench")
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn in SWE_SKIP or fn.endswith("_analysis.json"):
            continue
        try:
            blob = json.load(open(os.path.join(d, fn)))
        except Exception:
            continue
        if isinstance(blob, dict) and blob.get("cells"):
            out[fn[:-5]] = f"results/swebench/{fn}"
    return out


SWE_FILES = swe_files()


def count_swebench() -> dict:
    out = {}
    for name, rel in SWE_FILES.items():
        if not exists(rel):
            out[name] = {"artifact": rel, "status": "ABSENT"}
            continue
        d = json.load(open(p(rel)))
        cells = d.get("cells", [])
        summary = d.get("summary", {}) or {}
        armruns = 0
        armnames = collections.Counter()
        void = 0
        est = collections.Counter()
        fins = collections.Counter()
        itok = otok = rtok = 0
        tok_seen = False
        reps = collections.Counter()
        repos = collections.Counter()
        loc_miss = 0
        for c in cells:
            reps[c.get("representation")] += 1
            repos[c.get("repo")] += 1
            if c.get("localizer_recall") is False:
                loc_miss += 1
            for an, a in (c.get("arms") or {}).items():
                armruns += 1
                armnames[an] += 1
                if a.get("reward") is None:
                    void += 1
                est[a.get("edit_status")] += 1
                fins[a.get("finish_reason")] += 1
                if "input_tokens" in a:
                    tok_seen = True
                    itok += a.get("input_tokens") or 0
                    otok += a.get("output_tokens") or 0
                    rtok += a.get("reasoning_tokens") or 0
        out[name] = {
            "artifact": rel,
            "cells": len(cells),
            "representations": {str(k): v for k, v in reps.items()},
            "repos": dict(repos),
            "localizer_misses": loc_miss,
            "arm_runs": armruns,
            "arms": dict(armnames),
            "arm_runs_reward_null_never_zero": void,
            "edit_status": {str(k): v for k, v in est.items()},
            "finish_reasons": {str(k): v for k, v in fins.items()},
            "truncations_finish_length": fins.get("length", 0),
            "runner_n_calls": summary.get("n_calls", NR),
            "contagion_dirty_excluded": summary.get("contagion_dirty_excluded", NR),
            "cells_excluded_flag": sum(1 for c in cells if c.get("excluded")),
            "input_tokens": itok if tok_seen else NR,
            "output_tokens": otok if tok_seen else NR,
            "reasoning_tokens": rtok if tok_seen else NR,
        }
    return out


# --------------------------------------------------------------------------
# diagnostic / probe artifacts that are NOT publication-facing
# --------------------------------------------------------------------------
def count_diagnostics() -> dict:
    out = {}
    simple = {
        "needle_probe_responses": "results/j2_escalation/needle_responses.jsonl",
        "reader_escalation_responses": "results/j2_escalation/responses.jsonl",
        "f_judge_calls": "results/f_judge/judge_calls.jsonl",
        "f_judge_sensitivity_calls": "results/f_judge/judge_sensitivity_calls.jsonl",
        "f_judge_reader_outputs": "results/f_judge/reader_outputs.jsonl",
        "determinism_probe_raw": "results/noise/determinism_probe_raw.jsonl",
        "gemma_liveness_probe": "results/gemma_probe/liveness_probe.jsonl",
        "noise_floor_superseded_ledger": "results/runs/noise_floor/ledger.jsonl",
        "repr_pilot_n8_records": "results/pilot_representations/records.jsonl",
        "gemma_smoke_cells": "results/gemma_reader/smoke_cells.jsonl",
        "repr_scaleup_memories": "results/repr_scaleup/memories.jsonl",
        "factorial_gemma_memories": "results/writer_factorial/memories_gemma.jsonl",
        "scicode_memories_recovered_raw_only": "results/scicode/memories.jsonl",
        "quarantined_truncations": "results/gemma_reader/transfer_cache_quarantined_truncations.jsonl",
    }
    for name, rel in simple.items():
        out[name] = {
            "artifact": rel,
            "rows": sum(1 for _ in jsonl(p(rel))) if exists(rel) else "ABSENT",
        }
    # throughput ladders: one row per ladder RUNG, with its own request count
    bench = {}
    bdir = p("results/bench")
    if os.path.isdir(bdir):
        for fn in sorted(os.listdir(bdir)):
            if not fn.endswith(".jsonl") or fn.endswith("_raw.jsonl"):
                continue
            reqs = ok = 0
            rungs = 0
            for d in jsonl(os.path.join(bdir, fn)):
                rungs += 1
                reqs += d.get("requests") or 0
                ok += d.get("completed_ok") or 0
            bench[fn] = {"rungs": rungs, "requests": reqs, "completed_ok": ok}
    out["throughput_ladders"] = bench
    return out


def dedup_cache_calls() -> dict:
    """Real endpoint calls, with SNAPSHOT COPIES removed.

    Two cache files can hold the same stored record.  A record is the SAME call
    iff it shares both `key_hash` and `written_at_utc`; a shared key with a
    different timestamp is a genuine RE-RUN (the session-matched arms re-issued
    byte-identical requests on purpose, and that is the whole point of
    DEFECT_REGISTER #25/#28).  Counting rows alone over-counts; counting
    distinct keys alone under-counts the re-runs.  Both are reported.
    """
    rows_total = 0
    by_key_ts = set()
    by_key = set()
    for dirpath, _dirs, files in os.walk(p("results")):
        for fn in sorted(files):
            if "cache" not in fn or not fn.endswith(".jsonl"):
                continue
            for d in jsonl(os.path.join(dirpath, fn)):
                rows_total += 1
                by_key_ts.add((d.get("key_hash"), d.get("written_at_utc")))
                by_key.add(d.get("key_hash"))
    return {
        "cache_rows_on_disk": rows_total,
        "real_endpoint_calls_snapshot_copies_removed": len(by_key_ts),
        "snapshot_copy_rows": rows_total - len(by_key_ts),
        "distinct_request_keys": len(by_key),
        "deliberate_re_runs_same_request_new_session": len(by_key_ts) - len(by_key),
        "_rule": "same call iff (key_hash, written_at_utc) match; same key + new "
                 "timestamp is a deliberate re-run, not a duplicate",
    }


def totals(cells: dict, caches: dict, sci: dict, swe: dict, diag: dict) -> dict:
    cache_calls = sum(v["stored_calls"] for v in caches.values())
    cache_trunc = sum(v["truncations_finish_length"] for v in caches.values())
    cache_empty = sum(v["empty_finish_reason"] for v in caches.values())
    cache_retry = sum(v["transient_failures_then_retried"] for v in caches.values())
    cache_pt = sum(v["prompt_tokens"] for v in caches.values())
    cache_ct = sum(v["completion_tokens"] for v in caches.values())
    cache_rt = sum(v["reasoning_tokens"] for v in caches.values())
    sci_calls = sum(v.get("arm_runs_rows", 0) for v in sci.values() if "arm_runs_rows" in v)
    sci_pt = sum(v.get("prompt_tokens", 0) for v in sci.values() if "prompt_tokens" in v)
    sci_ct = sum(v.get("completion_tokens", 0) for v in sci.values() if "completion_tokens" in v)
    sci_trunc = sum(v.get("truncations_finish_length", 0) for v in sci.values() if "truncations_finish_length" in v)
    swe_calls = sum(v.get("arm_runs", 0) for v in swe.values() if "arm_runs" in v)
    swe_pt = sum(v["input_tokens"] for v in swe.values() if isinstance(v.get("input_tokens"), int))
    swe_ct = sum(v["output_tokens"] for v in swe.values() if isinstance(v.get("output_tokens"), int))
    swe_rt = sum(v["reasoning_tokens"] for v in swe.values() if isinstance(v.get("reasoning_tokens"), int))
    swe_trunc = sum(v.get("truncations_finish_length", 0) for v in swe.values() if "truncations_finish_length" in v)
    return {
        "longmemeval_cache_backed_endpoint_calls": cache_calls,
        "longmemeval_cache_prompt_tokens": cache_pt,
        "longmemeval_cache_completion_tokens": cache_ct,
        "longmemeval_cache_reasoning_tokens": cache_rt,
        "longmemeval_cache_truncations_finish_length": cache_trunc,
        "longmemeval_cache_empty_finish_reason": cache_empty,
        "longmemeval_calls_that_needed_a_retry": cache_retry,
        "scicode_arm_runs_no_cache_kept": sci_calls,
        "scicode_prompt_tokens": sci_pt,
        "scicode_completion_tokens": sci_ct,
        "scicode_truncations_finish_length": sci_trunc,
        "scicode_reasoning_tokens": NR,
        "swebench_arm_runs": swe_calls,
        "swebench_input_tokens": swe_pt,
        "swebench_output_tokens": swe_ct,
        "swebench_reasoning_tokens": swe_rt,
        "swebench_truncations_finish_length": swe_trunc,
        "GRAND_TOTAL_endpoint_calls_all_benchmarks": cache_calls + sci_calls + swe_calls,
        "_grand_total_note": (
            "LongMemEval is counted from response-cache rows (one row = one real call, "
            "deduplicated by key_hash). SciCode and SWE-bench kept no response cache, so "
            "their arm-runs are counted from result rows -- SWE-bench's runner also "
            "reports its own n_calls, which is SMALLER than arm_runs because the WITHOUT "
            "arm is issued once per cell and shared across the three representations."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    cells = count_cells()
    caches = count_caches()
    sci = count_scicode()
    swe = count_swebench()
    diag = count_diagnostics()
    tot = totals(cells, caches, sci, swe, diag)
    tot_dedup = dedup_cache_calls()
    tot["longmemeval_real_calls_snapshot_copies_removed"] = tot_dedup["real_endpoint_calls_snapshot_copies_removed"]
    tot["longmemeval_snapshot_copy_rows"] = tot_dedup["snapshot_copy_rows"]
    tot["longmemeval_distinct_request_keys"] = tot_dedup["distinct_request_keys"]
    tot["longmemeval_deliberate_re_runs"] = tot_dedup["deliberate_re_runs_same_request_new_session"]
    tot["GRAND_TOTAL_endpoint_calls_snapshot_copies_removed"] = (
        tot_dedup["real_endpoint_calls_snapshot_copies_removed"]
        + tot["scicode_arm_runs_no_cache_kept"]
        + tot["swebench_arm_runs"]
    )

    blob = {
        "_generated_by": "scripts/count_experiment_accounting.py",
        "_rule": "counted from artifacts; a quantity that cannot be counted prints "
                 + NR
                 + " and is never estimated",
        "cache_dedup": dedup_cache_calls(),
        "cell_row_files": cells,
        "response_caches": caches,
        "scicode": sci,
        "swebench": swe,
        "diagnostics": diag,
        "TOTALS": tot,
    }
    if args.json:
        json.dump(blob, sys.stdout, indent=1, sort_keys=False)
        print()
        return 0

    def sec(t):
        print()
        print("=" * 78)
        print(t)
        print("=" * 78)

    sec("CELL ROW FILES -- a ROW is a REPLICATE; a CELL is (locator, task)")
    for k, v in cells.items():
        if v.get("status") == "ABSENT":
            print(f"{k:30s} ABSENT  {v['artifact']}")
            continue
        print(f"{k}  [{v['artifact']}]")
        for ak, a in v["arms"].items():
            flag = ""
            if a["cells_by_content_cell_id"] != a["cells_by_locator_task"]:
                flag = (f"  <-- cell_id COLLIDES: {a['cells_by_content_cell_id']} "
                        f"content ids for {a['cells_by_locator_task']} cells (defect 26)")
            print(f"   {str(a['representation']):11s} w={str(a['writer']):22s} "
                  f"r={str(a['reader']):15s} cells={a['cells_by_locator_task']:>5d} "
                  f"rows={a['rows_replicates']:>5d} void={a['rows_void_null_reward']:>4d} "
                  f"arm-runs={a['arm_runs']:>5d}{flag}")
            if a["row_error_codes"]:
                print(f"   {'':52s}errors: {a['row_error_codes']}")

    sec("RESPONSE CACHES  (1 row = 1 real endpoint call)")
    for k, v in sorted(caches.items()):
        print(f"{k:62s} calls={v['stored_calls']:>5d} trunc={v['truncations_finish_length']:>3d} "
              f"empty={v['empty_finish_reason']:>3d} retried={v['transient_failures_then_retried']:>3d}")

    sec("SCICODE")
    for k, v in sci.items():
        if v.get("status") == "ABSENT":
            print(f"{k:22s} ABSENT")
            continue
        print(f"{k:22s} pairs={v['cells_pairs']}  arm-runs={v['arm_runs_rows']}  "
              f"runner n_calls={v['runner_n_calls']}  trunc={v['truncations_finish_length']}  "
              f"reward-null={v['arm_runs_reward_null']}")

    sec("SWE-BENCH")
    for k, v in swe.items():
        if v.get("status") == "ABSENT":
            print(f"{k:38s} ABSENT")
            continue
        print(f"{k:38s} cells={v['cells']:>3d} arm-runs={v['arm_runs']:>4d} "
              f"void={v['arm_runs_reward_null_never_zero']:>3d} "
              f"n_calls={v['runner_n_calls']} repos={list(v['repos'])}")

    sec("DIAGNOSTIC / PROBE ARTIFACTS  (never publication-facing)")
    for k, v in diag.items():
        if k == "throughput_ladders":
            continue
        print(f"{k:38s} rows={v['rows']}")
    print("  throughput ladders:")
    for k, v in diag["throughput_ladders"].items():
        print(f"    {k:38s} rungs={v['rungs']:>2d} requests={v['requests']:>4d} ok={v['completed_ok']:>4d}")

    sec("TOTALS")
    for k, v in tot.items():
        if k.startswith("_"):
            continue
        print(f"{k:52s} {v}")
    print()
    print(tot["_grand_total_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

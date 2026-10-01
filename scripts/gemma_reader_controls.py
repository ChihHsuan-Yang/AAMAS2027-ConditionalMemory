#!/usr/bin/env python3
"""Controls for the reader-transfer arm, each paid for by data already on disk.

1. A FREE A/A CONTROL, for BOTH readers.
   The WITHOUT-memory request for a given (task, replicate) is byte-identical
   across the summary and structured representations -- same filler, same
   ordering, no target -- but the two were issued as SEPARATE endpoint calls,
   because ``memory_repr`` is in the cache key. That is a true A/A: identical
   bytes, two independent generations. Any disagreement is pure execution
   nondeterminism at temperature 0, measured on the real 16-25k-token shape,
   for free.

   This matters here because an F_exec of exactly 0.000 is otherwise a null
   with no positive control, and a reader comparison rests on both readers'
   floors being real measurements.

2. CACHE SEPARATION, re-confirmed on THIS run's rows and keys.
   With the positive control FIRST: the gpt-oss key must HIT in the gpt-oss
   cache before a Gemma miss means anything. A dead cache misses everywhere
   and would look identical to correct separation.

3. TRUNCATION ACCOUNTING. Every Gemma response with finish_reason="length"
   must have been REFUSED (no row scored it), because on Gemma a truncation
   comes back as a plausible fragment, not as null content.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.cache import ResponseCache, make_key  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def aa_control(cache_path: Path, label: str) -> dict:
    """Same WITHOUT-arm bytes, two separate calls. Identical content?"""
    groups: dict[tuple, dict] = {}
    for line in cache_path.open():
        if not line.strip():
            continue
        d = json.loads(line)
        k = d["key"]
        if k["arm"] != "without_memory":
            continue
        ctx = k.get("context_sha256")
        if ctx is None:
            continue   # v1 key shape carries no request hash; cannot pair safely
        g = groups.setdefault((k["future_task_id"], k["replicate_id"], ctx), {})
        g[k["memory_repr"]] = d["response"]["content"]
    paired = {k: v for k, v in groups.items() if len(v) >= 2}
    same = 0
    differing = []
    for k, v in paired.items():
        vals = list(v.values())
        if all(x == vals[0] for x in vals):
            same += 1
        else:
            differing.append({"task": k[0], "replicate": k[1],
                              "lengths": {r: len(c) for r, c in v.items()}})
    return {
        "_what": f"{label}: byte-identical WITHOUT-arm requests issued as "
                 f"SEPARATE calls (memory_repr is in the cache key). Identical "
                 f"content => the endpoint is deterministic at temperature 0 on "
                 f"the real context shape.",
        "n_paired_groups": len(paired),
        "n_identical": same,
        "n_differing": len(differing),
        "rate_identical": (same / len(paired)) if paired else None,
        "differing_examples": differing[:5],
        "_vacuity_check_n_groups_gt_0": len(paired) > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemma-cache", type=Path,
                    default=REPO / "results/gemma_reader/transfer_cache.jsonl")
    ap.add_argument("--gemma-rows", type=Path,
                    default=REPO / "results/gemma_reader/transfer_cells.jsonl")
    ap.add_argument("--oss-cache", type=Path,
                    default=REPO / "results/repr_scaleup/eval_cache.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/gemma_reader/reader_transfer_controls.json")
    args = ap.parse_args()

    out: dict = {"_what": "controls for the reader-transfer arm",
                 "generated_at_utc": utc_now()}

    # ---------------------------------------------------- 1. A/A controls
    out["aa_determinism_gptoss"] = aa_control(args.oss_cache, "gpt-oss-120b")
    out["aa_determinism_gemma"] = aa_control(args.gemma_cache, "gemma-4-31B-it")
    for k in ("aa_determinism_gptoss", "aa_determinism_gemma"):
        a = out[k]
        log(f"{k}: {a['n_identical']}/{a['n_paired_groups']} identical "
            f"({a['n_differing']} differ)")
        if not a["_vacuity_check_n_groups_gt_0"]:
            raise SystemExit(f"{k} compared ZERO groups -- a vacuous control")

    # --------------------------------------- 2. cache separation, re-confirmed
    sep: dict = {"_what": "the response cache cannot serve a gpt-oss answer to a "
                          "Gemma request. POSITIVE CONTROL FIRST: without a "
                          "demonstrated HIT, a 'miss' proves only that the cache "
                          "is dead."}
    oss = ResponseCache(args.oss_cache)
    k0 = json.loads(args.oss_cache.read_text().splitlines()[0])["key"]
    base = {f: k0[f] for f in k0 if f != "schema_version"}
    hit = oss.lookup(make_key(**base))
    sep["step1_positive_control_gptoss_key_in_gptoss_cache"] = {
        "result": "HIT" if hit else "MISS",
        "resolved_model": hit.resolved_model if hit else None}
    gkey = {**base, "model_id": "gemma-4-31B-it",
            "decoding_params": {"temperature": 0.0, "max_tokens": 512}}
    sep["step2_gemma_key_in_gptoss_cache"] = {
        "result": "HIT" if oss.lookup(make_key(**gkey)) else "MISS"}
    sep["step3_key_hashes_differ"] = make_key(**base) != make_key(**gkey)
    if args.gemma_cache.exists():
        gem = ResponseCache(args.gemma_cache)
        sep["step4_gptoss_key_in_gemma_cache"] = {
            "result": "HIT" if gem.lookup(make_key(**base)) else "MISS"}
        models = collections.Counter()
        for line in args.gemma_cache.open():
            if line.strip():
                models[json.loads(line)["response"]["resolved_model"]] += 1
        sep["gemma_cache_resolved_models"] = dict(models)
        sep["gemma_cache_only_serves_gemma"] = set(models) == {"gemma-4-31B-it"}
    sep["VERDICT"] = (
        sep["step1_positive_control_gptoss_key_in_gptoss_cache"]["result"] == "HIT"
        and sep["step2_gemma_key_in_gptoss_cache"]["result"] == "MISS"
        and sep.get("step4_gptoss_key_in_gemma_cache", {}).get("result") == "MISS"
        and sep["step3_key_hashes_differ"])
    out["cache_separation_reconfirmed_on_this_run"] = sep
    log(f"cache separation: step1={sep['step1_positive_control_gptoss_key_in_gptoss_cache']['result']} "
        f"step2={sep['step2_gemma_key_in_gptoss_cache']['result']} "
        f"step4={sep.get('step4_gptoss_key_in_gemma_cache', {}).get('result')} "
        f"VERDICT={sep['VERDICT']}")

    # --------------------------------------------- 3. truncation accounting
    if args.gemma_cache.exists():
        fr = collections.Counter()
        trunc_nonempty = 0
        for line in args.gemma_cache.open():
            if not line.strip():
                continue
            r = json.loads(line)["response"]
            fr[r["finish_reason"]] += 1
            if r["finish_reason"] == "length" and (r["content"] or "").strip():
                trunc_nonempty += 1
        rows = ([json.loads(l) for l in args.gemma_rows.read_text().splitlines()
                 if l.strip()] if args.gemma_rows.exists() else [])
        codes = collections.Counter(r["error_code_if_any"] for r in rows
                                    if r["error_code_if_any"])
        scored_with_error = [r for r in rows if r["error_code_if_any"]
                             and r["delta_utility"] is not None]
        out["truncation_accounting"] = {
            "_what": "On Gemma a truncation returns a plausible FRAGMENT, not "
                     "null content. Scored, it is a wrong answer that drives dU "
                     "negative and MANUFACTURES a harmful memory. Every such "
                     "response must have been refused.",
            "gemma_cache_finish_reasons": dict(fr),
            "responses_truncated_with_nonempty_content": trunc_nonempty,
            "row_error_codes": dict(codes),
            "rows_with_an_error_code_AND_a_non_null_delta": len(scored_with_error),
            "no_truncation_was_scored": len(scored_with_error) == 0,
            "rows_with_null_delta": sum(1 for r in rows
                                        if r["delta_utility"] is None),
        }
        log(f"truncation: finish_reasons={dict(fr)} "
            f"error_codes={dict(codes)} "
            f"scored-despite-error={len(scored_with_error)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, default=str))
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

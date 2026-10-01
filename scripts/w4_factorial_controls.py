#!/usr/bin/env python3
"""Controls for the Writer x Reader factorial. Every null defended.

1. CACHE SEPARATION ACROSS WRITERS, positive control FIRST.
   The two writer arms differ in the memory TEXT, so their requests differ and
   their cache keys must differ. But the key field that is supposed to carry
   that is checked here behaviourally, not by reading KEY_FIELDS: a
   writer-gpt-oss key must HIT in the published cache before a writer-Gemma key
   is shown to MISS. A dead cache misses everywhere and looks identical to
   correct separation.

2. A/A DETERMINISM on the factorial's own cache, for both readers.
   The WITHOUT-arm request for a given (task, replicate) is byte-identical
   across the two representations but was issued as two separate calls
   (memory_repr is in the key). Identical content => the endpoint is
   deterministic on the real context shape.

3. THE WITHOUT ARM IS WRITER-INVARIANT, measured on the REWARDS.
   The WITHOUT arm has no memory in it, so a writer change cannot move it.
   F-GATE 4 proved the request BYTES are identical; this proves the recorded
   rewards are too. A non-zero difference would be a defect, not a finding.

4. TRUNCATION ACCOUNTING -- no truncated Gemma response was ever scored.

5. THE MALFORMED-STRUCTURED CHECK STILL REJECTS. Gemma produced zero malformed
   structured writes. A rate of 0 from a validator never shown to reject is
   not a measurement, so the validator is made to FIRE on planted input and
   on the gpt-oss outputs it ALREADY rejected.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.cache import ResponseCache, make_key          # noqa: E402
from p1mem.memory import representations as R            # noqa: E402
from p1mem.vendor.rcc_schema import utc_now              # noqa: E402


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def aa_control(cache_path: Path, model_id: str, label: str) -> dict:
    groups: dict[tuple, dict] = {}
    for line in cache_path.open():
        if not line.strip():
            continue
        d = json.loads(line)
        k = d["key"]
        if k["arm"] != "without_memory" or k.get("model_id") != model_id:
            continue
        ctx = k.get("context_sha256")
        if ctx is None:
            continue
        g = groups.setdefault((k["future_task_id"], k["replicate_id"], ctx), {})
        g[k["memory_repr"]] = d["response"]["content"]
    paired = {k: v for k, v in groups.items() if len(v) >= 2}
    same, differing = 0, []
    for k, v in paired.items():
        vals = list(v.values())
        if all(x == vals[0] for x in vals):
            same += 1
        else:
            differing.append({"task": k[0], "replicate": k[1],
                              "lengths": {r: len(c) for r, c in v.items()}})
    return {
        "_what": f"{label}: byte-identical WITHOUT-arm requests issued as "
                 f"SEPARATE calls (memory_repr is in the key). Identical "
                 f"content => deterministic at temperature 0 on the real shape.",
        "n_paired_groups": len(paired), "n_identical": same,
        "n_differing": len(differing),
        "rate_identical": (same / len(paired)) if paired else None,
        "differing_examples": differing[:5],
        "_vacuity_check_n_groups_gt_0": len(paired) > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factorial-cache", type=Path,
                    default=REPO / "results/writer_factorial/factorial_cache.jsonl")
    ap.add_argument("--factorial-rows", type=Path,
                    default=REPO / "results/writer_factorial/factorial_cells_gemma.jsonl")
    ap.add_argument("--factorial-rows-gptoss", type=Path,
                    default=REPO / "results/writer_factorial/factorial_cells_gptoss.jsonl")
    ap.add_argument("--oss-cache", type=Path,
                    default=REPO / "results/repr_scaleup/eval_cache.jsonl")
    ap.add_argument("--gemma-memories", type=Path,
                    default=REPO / "results/writer_factorial/memories_gemma.jsonl")
    ap.add_argument("--oss-memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--oss-rows", type=Path,
                    default=REPO / "results/repr_scaleup/cells.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/writer_factorial/writer_factorial_controls.json")
    args = ap.parse_args()

    out: dict = {"_what": "controls for the Writer x Reader factorial",
                 "generated_at_utc": utc_now()}

    # ------------------------------------- 1. cache separation ACROSS WRITERS
    sep: dict = {"_what": (
        "the response cache cannot serve a writer-gpt-oss answer to a "
        "writer-Gemma request. POSITIVE CONTROL FIRST: without a demonstrated "
        "HIT, a 'miss' proves only that the cache is dead.")}
    oss = ResponseCache(args.oss_cache)
    k0 = json.loads(args.oss_cache.read_text().splitlines()[0])["key"]
    base = {f: k0[f] for f in k0 if f != "schema_version"}
    hit = oss.lookup(make_key(**base))
    sep["step1_POSITIVE_CONTROL_published_key_in_published_cache"] = {
        "result": "HIT" if hit else "MISS",
        "resolved_model": hit.resolved_model if hit else None}
    # the writer-Gemma request for the same cell renders DIFFERENT bytes, so
    # its context_sha256 differs. Simulate exactly that.
    wkey = {**base, "context_sha256": "0" * 64}
    sep["step2_writer_gemma_shaped_key_in_published_cache"] = {
        "result": "HIT" if oss.lookup(make_key(**wkey)) else "MISS"}
    sep["step3_key_hashes_differ"] = make_key(**base) != make_key(**wkey)
    if args.factorial_cache.exists():
        fc = ResponseCache(args.factorial_cache)
        sep["step4_published_key_in_factorial_cache"] = {
            "result": "HIT" if fc.lookup(make_key(**base)) else "MISS"}
        models = collections.Counter()
        memids = collections.Counter()
        for line in args.factorial_cache.open():
            if not line.strip():
                continue
            d = json.loads(line)
            models[d["response"]["resolved_model"]] += 1
            memids[d["key"]["memory_id"]] += 1
        sep["factorial_cache_resolved_models"] = dict(models)
        sep["factorial_cache_distinct_memory_ids"] = len(memids)
        # the published caches' memory ids are segment hashes; the factorial's
        # are writer-aware hashes. They must not overlap, or a writer-Gemma key
        # could collide with a published one on everything but the context.
        pub_ids = set()
        for line in args.oss_cache.open():
            if line.strip():
                pub_ids.add(json.loads(line)["key"]["memory_id"])
        sep["factorial_memory_ids_disjoint_from_published"] = not (
            set(memids) & pub_ids)
    sep["VERDICT"] = (
        sep["step1_POSITIVE_CONTROL_published_key_in_published_cache"]["result"] == "HIT"
        and sep["step2_writer_gemma_shaped_key_in_published_cache"]["result"] == "MISS"
        and sep.get("step4_published_key_in_factorial_cache", {}).get("result") == "MISS"
        and sep["step3_key_hashes_differ"])
    out["cache_separation_across_writers"] = sep
    log(f"cache separation: step1="
        f"{sep['step1_POSITIVE_CONTROL_published_key_in_published_cache']['result']} "
        f"step2={sep['step2_writer_gemma_shaped_key_in_published_cache']['result']} "
        f"step4={sep.get('step4_published_key_in_factorial_cache', {}).get('result')} "
        f"VERDICT={sep['VERDICT']}")

    # ----------------------------------------------------- 2. A/A determinism
    if args.factorial_cache.exists():
        for mid, lab in (("gpt-oss-120b", "reader gpt-oss, writer Gemma"),
                         ("gemma-4-31B-it", "reader Gemma, writer Gemma")):
            key = f"aa_determinism_{mid.replace('-', '_').replace('.', '')}"
            out[key] = aa_control(args.factorial_cache, mid, lab)
            a = out[key]
            log(f"{key}: {a['n_identical']}/{a['n_paired_groups']} identical")
            if not a["_vacuity_check_n_groups_gt_0"]:
                raise SystemExit(f"{key} compared ZERO groups -- a vacuous control")

    # ------------------------------- 3. the WITHOUT arm is writer-invariant
    rows = ([json.loads(l) for l in args.factorial_rows.read_text().splitlines()
             if l.strip()] if args.factorial_rows.exists() else [])
    ossrows = [json.loads(l) for l in args.oss_rows.read_text().splitlines()
               if l.strip()]

    def key_of(r):
        p = r.get("provenance") or {}
        return (r["memory_representation"], p.get("memory_unit_locator"),
                r["future_task_id"], int(r["replicate_id"]))

    rows_go = ([json.loads(l) for l in
                args.factorial_rows_gptoss.read_text().splitlines() if l.strip()]
               if args.factorial_rows_gptoss.exists() else [])

    def _inv(A_rows, B_rows, model, label, note):
        A = {key_of(r): r for r in A_rows if r["reader_model"] == model}
        B = {key_of(r): r for r in B_rows if r["reader_model"] == model}
        common = sorted(set(A) & set(B), key=str)
        same = diff = 0
        ex = []
        for k in common:
            a, b = A[k], B[k]
            if a["reward_without_memory"] is None or b["reward_without_memory"] is None:
                continue
            if a["reward_without_memory"] == b["reward_without_memory"]:
                same += 1
            else:
                diff += 1
                if len(ex) < 5:
                    ex.append({"key": list(k),
                               "writer_gptoss": a["reward_without_memory"],
                               "writer_gemma": b["reward_without_memory"]})
        txt = sum(1 for k in common
                  if A[k]["output_without_memory"] == B[k]["output_without_memory"])
        return {
            "_what": label, "_note": note,
            "n_compared": len(common), "n_reward_identical": same,
            "n_reward_differing": diff, "n_output_text_identical": txt,
            "differing_examples": ex, "HOLDS": diff == 0,
            "_vacuity_check": len(common) > 0,
        }

    # THE control: both writer arms from the SAME session. The WITHOUT arm has
    # no memory in it and identical request bytes, so it must be identical.
    inv = {}
    for model, mlab in (("gpt-oss-120b", "reader_gptoss"),
                        ("gemma-4-31B-it", "reader_gemma")):
        inv[mlab] = _inv(
            rows_go, rows, model,
            f"SESSION-MATCHED: writer gpt-oss vs writer Gemma, {mlab}, both "
            f"executed 2026-10-01. The WITHOUT arm contains NO memory and "
            f"F-GATE 4 proved its request bytes identical, so it MUST be "
            f"identical here.",
            "a difference here is a DEFECT, not a finding.")
    inv["HOLDS_ON_BOTH_READERS"] = all(
        v["HOLDS"] for k, v in inv.items() if isinstance(v, dict))
    out["without_arm_is_writer_invariant_SESSION_MATCHED"] = inv
    for k, v in inv.items():
        if isinstance(v, dict):
            log(f"WITHOUT-arm writer invariance [{k}]: rewards "
                f"{v['n_reward_identical']}/{v['n_compared']} identical "
                f"({v['n_reward_differing']} differ); output text "
                f"{v['n_output_text_identical']}/{v['n_compared']}")

    # THE DRIFT MEASUREMENT that forced the re-run. Kept, because it is a real
    # property of the endpoint and the reason the design changed.
    drift = _inv(ossrows, rows, "gpt-oss-120b",
                 "CROSS-SESSION (published 2026-09-30 vs today): the SAME "
                 "WITHOUT-arm request bytes, re-issued a day later.",
                 "This is NOT a writer comparison -- it is the endpoint's "
                 "cross-session stability, and it is why every arm was re-run "
                 "in one session. A non-zero count here is a finding about "
                 "the ENDPOINT.")
    drift["HOLDS"] = None
    drift["_this_is_a_measurement_not_a_gate"] = True
    out["cross_session_drift_that_forced_the_rerun"] = drift
    log(f"CROSS-SESSION drift (published vs today, WITHOUT arm): "
        f"text {drift['n_output_text_identical']}/{drift['n_compared']} identical, "
        f"rewards {drift['n_reward_differing']} differ")

    # --------------------------------------------- 4. truncation accounting
    if args.factorial_cache.exists():
        fr = collections.Counter()
        trunc_nonempty = 0
        at_cap = 0
        for line in args.factorial_cache.open():
            if not line.strip():
                continue
            d = json.loads(line)
            r = d["response"]
            mt = d["key"]["decoding_params"].get("max_tokens")
            fr[(d["key"]["model_id"], r["finish_reason"])] += 1
            if r["finish_reason"] == "length" and (r["content"] or "").strip():
                trunc_nonempty += 1
            if mt and (r.get("completion_tokens") or 0) >= mt:
                at_cap += 1
        allrows = rows + rows_go
        codes = collections.Counter(r["error_code_if_any"] for r in allrows
                                    if r["error_code_if_any"])
        scored_with_error = [r for r in allrows if r["error_code_if_any"]
                             and r["delta_utility"] is not None]
        out["truncation_accounting"] = {
            "_what": "On Gemma a truncation returns a plausible FRAGMENT, not "
                     "null content. Scored, it is a wrong answer that drives "
                     "dU negative and MANUFACTURES a harmful memory. The guard "
                     "tests three observables; the ARITHMETIC one "
                     "(completion_tokens >= max_tokens) is counted separately "
                     "because the server has been measured reporting neither "
                     "reason field.",
            "🔴_READ_THE_CACHE_COUNTS_CORRECTLY": (
                "P1Client raises the truncation guard BEFORE it stores to the "
                "cache (client.py: _assert_not_truncated then cache.store), so "
                "a REFUSED truncation is never written to the cache at all. "
                "The cache counts below are therefore 'truncations ADMITTED', "
                "which is 0 BY CONSTRUCTION on a strict arm -- they are NOT "
                "evidence that no truncation occurred. The number that shows "
                "how often it DID occur is the row error-code count "
                "(truncated_nonempty_at_token_budget / "
                "empty_output_finish_length) below; the number that shows none "
                "was SCORED is rows_with_an_error_code_AND_a_non_null_delta. "
                "An absent check must never read as a passing one."),
            "_denominator": "BOTH writer arms' rows, 2026-10-01 session",
            "n_rows_both_writer_arms": len(allrows),
            "n_truncations_REFUSED_visible_only_in_the_rows": sum(
                1 for r in allrows if r["error_code_if_any"] in (
                    "truncated_nonempty_at_token_budget",
                    "empty_output_finish_length")),
            "cache_finish_reasons": {f"{k[0]}:{k[1]}": v for k, v in sorted(
                fr.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
            "responses_at_or_above_max_tokens_ARITHMETIC_clause": at_cap,
            "responses_truncated_with_nonempty_content": trunc_nonempty,
            "row_error_codes": dict(codes),
            "rows_with_an_error_code_AND_a_non_null_delta": len(scored_with_error),
            "no_truncation_was_scored": len(scored_with_error) == 0,
            "rows_with_null_delta": sum(1 for r in allrows
                                        if r["delta_utility"] is None),
        }
        log(f"truncation: at_cap={at_cap} nonempty_length={trunc_nonempty} "
            f"codes={dict(codes)} scored-despite-error={len(scored_with_error)}")

    # ------------------- 5. the structured validator still REJECTS -----------
    gm = [json.loads(l) for l in args.gemma_memories.read_text().splitlines()
          if l.strip()]
    om = [json.loads(l) for l in args.oss_memories.read_text().splitlines()
          if l.strip()]
    gem_mal = [m for m in gm if m["representation"] == "structured" and not m["ok"]]
    oss_mal = [m for m in om if m["representation"] == "structured" and not m["ok"]]
    planted = [
        ("missing_keys", {"memory_type": "episodic"}),
        ("bad_enum", {**{k: "x" for k in R.STRUCTURED_KEYS},
                      "memory_type": "NOT_A_TYPE", "confidence": "high"}),
        ("extra_key", {**{k: ("episodic" if k == "memory_type" else
                             "high" if k == "confidence" else "x")
                          for k in R.STRUCTURED_KEYS}, "surprise": "y"}),
        ("non_string", {**{k: ("episodic" if k == "memory_type" else
                               "high" if k == "confidence" else "x")
                           for k in R.STRUCTURED_KEYS}, "situation": 7}),
    ]
    fired = {}
    for name, obj in planted:
        code, _ = R.validate_structured(obj, R.STRUCTURED_KEYS)
        fired[name] = code
    valid = {k: ("episodic" if k == "memory_type" else
                 "high" if k == "confidence" else "x") for k in R.STRUCTURED_KEYS}
    accept, _ = R.validate_structured(valid, R.STRUCTURED_KEYS)
    # and re-run it on the gpt-oss outputs it ALREADY rejected -- a real case
    replay = []
    for m in oss_mal:
        raw = m.get("raw_model_output")
        if raw is None:
            continue
        obj, how = R._extract_json_object(raw)
        code = (R.ERR_MALFORMED_JSON if obj is None
                else R.validate_structured(obj, R.STRUCTURED_KEYS)[0])
        replay.append({"locator": m["memory_unit_locator"],
                       "recorded": m["error_code"], "replayed": code,
                       "agrees": code == m["error_code"]})
    out["malformed_structured_validator_controls"] = {
        "_what": "Gemma produced ZERO malformed structured writes. A rate of 0 "
                 "from a validator never shown to reject is not a measurement, "
                 "so the validator is made to FIRE on four planted defects AND "
                 "replayed against the gpt-oss outputs it already rejected.",
        "planted_defects_and_the_code_each_produced": fired,
        "all_planted_defects_rejected": all(v is not None for v in fired.values()),
        "a_valid_object_is_ACCEPTED": accept is None,
        "replay_on_the_gptoss_rejections": replay,
        "replay_agrees_with_what_was_recorded": bool(replay) and all(
            r["agrees"] for r in replay),
        "gemma_malformed_count": len(gem_mal),
        "gptoss_malformed_count": len(oss_mal),
        "gemma_malformed_denominator": sum(
            1 for m in gm if m["representation"] == "structured"),
        "gptoss_malformed_denominator": sum(
            1 for m in om if m["representation"] == "structured"),
    }
    mv = out["malformed_structured_validator_controls"]
    log(f"validator controls: planted all rejected={mv['all_planted_defects_rejected']}, "
        f"valid accepted={mv['a_valid_object_is_ACCEPTED']}, "
        f"replay agrees={mv['replay_agrees_with_what_was_recorded']}; "
        f"gemma {mv['gemma_malformed_count']}/{mv['gemma_malformed_denominator']} vs "
        f"gptoss {mv['gptoss_malformed_count']}/{mv['gptoss_malformed_denominator']}")

    # ---- 6. DID A WRITER COLLAPSE TWO DISTINCT SEGMENTS TO ONE MEMORY? ----
    # memory_id / row_id are CONTENT hashes. If a writer compresses two
    # different segments to byte-identical text, those ids collide -- and the
    # validator reports duplicate_row_id. That is a real property of the
    # WRITER, not a plumbing bug, and it is a result worth reporting: a memory
    # system that merges two distinct experiences has lost information the
    # other writer kept.
    coll = {"_what": (
        "two DIFFERENT source segments compressed to byte-identical memory "
        "text. The ids are content hashes, so they collide and the validator "
        "reports duplicate_row_id. This is a property of the WRITER.")}
    for wname, mems in (("gemma", gm), ("gptoss", om)):
        per = {}
        for rep in ("summary", "structured"):
            texts = collections.defaultdict(list)
            for m in mems:
                if m["representation"] == rep and m["ok"]:
                    texts[m["memory_text"]].append(m["memory_unit_locator"])
            dup = {t: locs for t, locs in texts.items() if len(locs) > 1}
            per[rep] = {
                "n_memories": sum(len(v) for v in texts.values()),
                "n_distinct_texts": len(texts),
                "n_texts_shared_by_more_than_one_segment": len(dup),
                "colliding_locator_groups": [sorted(v) for v in dup.values()],
                "n_memories_involved": sum(len(v) for v in dup.values()),
            }
        coll[wname] = per
    gsum = coll["gemma"]["summary"]
    osum = coll["gptoss"]["summary"]
    coll["_finding"] = (
        f"Gemma collapsed {gsum['n_texts_shared_by_more_than_one_segment']} "
        f"summary text(s) across {gsum['n_memories_involved']} segments; "
        f"gpt-oss collapsed "
        f"{osum['n_texts_shared_by_more_than_one_segment']}. Gemma writes ~2x "
        f"shorter summaries, and at that compression two distinct episodes can "
        f"land on the same words.")
    coll["_does_it_affect_any_number"] = (
        "NO. The analysis joins on (memory_unit_locator, future_task_id), "
        "which is positional and cannot collide; the affected cells stay "
        "separate in the matched set. It WOULD have corrupted any analysis "
        "joining on memory_id -- which is exactly why this project's join rule "
        "forbids that.")
    out["writer_collapsed_distinct_segments"] = coll
    log(f"segment collapse: gemma summary "
        f"{gsum['n_texts_shared_by_more_than_one_segment']} collapsed text(s) "
        f"over {gsum['n_memories_involved']} segments; gptoss summary "
        f"{osum['n_texts_shared_by_more_than_one_segment']}")

    # ---------------------------------------------------------- the verdict
    gates = {
        "cache_separation": sep["VERDICT"],
        "without_arm_writer_invariant_session_matched":
            out["without_arm_is_writer_invariant_SESSION_MATCHED"][
                "HOLDS_ON_BOTH_READERS"],
        "no_truncation_scored": out.get("truncation_accounting", {}).get(
            "no_truncation_was_scored", False),
        "validator_rejects_planted_defects": mv["all_planted_defects_rejected"],
        "validator_accepts_a_valid_object": mv["a_valid_object_is_ACCEPTED"],
        "validator_replay_agrees": mv["replay_agrees_with_what_was_recorded"],
    }
    for k in list(out):
        if k.startswith("aa_determinism_"):
            gates[f"{k}_non_vacuous"] = out[k]["_vacuity_check_n_groups_gt_0"]
    out["CONTROL_GATES"] = gates
    out["ALL_CONTROLS_PASS"] = all(gates.values())
    log(f"CONTROL GATES: {gates}")
    log(f"ALL_CONTROLS_PASS: {out['ALL_CONTROLS_PASS']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out, indent=2, default=str)
    args.out.write_text(payload)
    led = REPO / "results/ledgers/writer_factorial" / args.out.name
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text(payload)
    log(f"wrote {args.out} and tracked copy {led}")
    return 0 if out["ALL_CONTROLS_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

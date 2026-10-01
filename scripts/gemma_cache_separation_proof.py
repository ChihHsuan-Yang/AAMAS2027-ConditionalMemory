#!/usr/bin/env python3
"""PROVE, behaviourally, that the response cache cannot serve a gpt-oss
answer to a Gemma request.

Task item 3 says "a claim is not enough", and that is the right standard:
reading ``cache.KEY_FIELDS`` and seeing ``model_id`` in the list proves that
a field EXISTS, not that it DISCRIMINATES. This script constructs two requests
that are identical in every byte except the model, issues both against the
LIVE endpoints through the project's own ``P1Client``, and shows a MISS.

THE POSITIVE CONTROL IS THE POINT
---------------------------------
A cache that never hits at all would also show a "miss" at the cross-model
step and look perfectly correct. So the sequence is:

  1. gpt-oss, cold          -> MISS   (nothing cached yet)
  2. gpt-oss, again         -> HIT    <-- POSITIVE CONTROL: the cache works
  3. gemma, same key fields -> MISS   <-- the separation being proven
  4. gemma, again           -> HIT    (and serves GEMMA's text, not gpt-oss's)

Without step 2, step 3 is uninterpretable. Without step 4, we have not shown
that the Gemma row is independently usable rather than simply unstorable.

A FURTHER CONTROL, because "the key differs" is not the whole claim
-------------------------------------------------------------------
Step 5 asserts the two stored rows carry DIFFERENT ``key_hash`` AND different
``resolved_model`` AND different response text. A key that differed while the
stored content was the same would still be a crossing by any measure anyone
cares about.

NOTE ON READING THE ARTIFACT: a cache row's ``row["key"]`` is the key DICT and
``row["key_hash"]`` is the digest. Two agents have now mis-read this same
four-field record -- one read ``row["key_fields"]`` (absent) and got a
confident ``None``, one did ``{r["key"] for r in rows}`` and got a TypeError.
The field names used below were checked against a real row first.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem import schema as S  # noqa: E402
from p1mem.cache import KEY_FIELDS, ResponseCache  # noqa: E402
from p1mem.client import P1Client  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

#: Identical for both readers. Short and self-contained: this script proves a
#: CACHE property, so the prompt only has to be byte-identical across arms.
MESSAGES = [
    {"role": "system", "content": "Answer concisely."},
    {"role": "user", "content": "What is the capital of France? Answer in one sentence."},
]

#: Every non-derived cache-key field. model_id / cluster / decoding_params /
#: context_sha256 are filled IN THE CLIENT from the client's own pins, so a
#: caller cannot describe a request it is not making.
KEY_FIELDS_SHARED = {
    "benchmark": "cache_separation_proof",
    "source_item_id": "proof_item",
    "memory_repr": "raw",
    "memory_id": "proof_memory_content_hash",
    "future_task_id": "proof_task",
    "arm": "with_memory",
    "retrieval_method": "oracle",
    "prompt_version": "cache_separation_proof_v1",
    "replicate_id": 0,
}


def log(m: str) -> None:
    print(m, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/gemma_reader/cache_separation_proof.json")
    ap.add_argument("--cache", type=Path,
                    default=REPO / "results/gemma_reader/cache_separation_cache.jsonl")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.cache.exists():
        # A pre-populated cache would make step 1 a HIT and void the whole
        # sequence. Start cold, explicitly, rather than hoping.
        args.cache.unlink()
        log(f"removed pre-existing {args.cache.name} so step 1 is genuinely cold")

    log("KEY_FIELDS as the module defines them (read, not recalled):")
    log(f"  {list(KEY_FIELDS)}")
    assert "model_id" in KEY_FIELDS, "model_id is not even in the key"
    assert "cluster" in KEY_FIELDS, "cluster is not even in the key"

    cache = ResponseCache(args.cache)
    gptoss_arm = S.reader_arm("gptoss_metis")
    gemma_arm = S.reader_arm("gemma_metis")

    clients = {}
    for name, arm in (("gptoss", gptoss_arm), ("gemma", gemma_arm)):
        clients[name] = P1Client(cluster=arm["reader_cluster"],
                                 model=arm["reader_model"], cache=cache,
                                 max_concurrency=1)

    steps = []

    def call(label: str, which: str, expect_hit: bool) -> dict:
        arm = gptoss_arm if which == "gptoss" else gemma_arm
        content, rec = clients[which].chat(
            MESSAGES, max_tokens=arm["max_tokens"],
            temperature=float(arm["temperature"]),
            reasoning_effort=arm["reasoning_effort"],
            cache_key_fields=dict(KEY_FIELDS_SHARED))
        row = {"step": label, "reader": which,
               "requested_model": arm["reader_model"],
               "resolved_model": rec.resolved_model,
               "cache_hit": rec.cache_hit, "expected_hit": expect_hit,
               "agrees_with_expectation": rec.cache_hit == expect_hit,
               "finish_reason": rec.finish_reason,
               "reasoning_tokens": rec.reasoning_tokens,
               "content_sha256": S.sha256_text(content),
               "content": content}
        steps.append(row)
        verdict = "OK " if row["agrees_with_expectation"] else "FAIL"
        log(f"  [{verdict}] {label:52s} cache_hit={rec.cache_hit!s:5s} "
            f"(expected {expect_hit}) resolved={rec.resolved_model!r} "
            f"rows_now={cache.stats()['rows']}")
        return row

    log("\nSEQUENCE (the positive control is step 2; without it step 3 is vacuous):")
    s1 = call("1. gpt-oss, cold cache                        -> MISS", "gptoss", False)
    s2 = call("2. gpt-oss again  [POSITIVE CONTROL]          -> HIT", "gptoss", True)
    s3 = call("3. gemma, SAME key fields                     -> MISS", "gemma", False)
    s4 = call("4. gemma again                                -> HIT", "gemma", True)

    # ---- step 5: inspect the stored rows themselves ----
    rows = [json.loads(line) for line in args.cache.open() if line.strip()]
    key_hashes = [r["key_hash"] for r in rows]           # the DIGEST
    key_models = [r["key"]["model_id"] for r in rows]     # key is the DICT
    resolved = [r["response"]["resolved_model"] for r in rows]
    contents = [r["response"]["content"] for r in rows]

    checks = {
        "step1_cold_miss": s1["agrees_with_expectation"],
        "step2_positive_control_hit": s2["agrees_with_expectation"],
        "step3_cross_model_miss": s3["agrees_with_expectation"],
        "step4_gemma_hit": s4["agrees_with_expectation"],
        "exactly_two_rows_stored": len(rows) == 2,
        "two_distinct_key_hashes": len(set(key_hashes)) == 2,
        "two_distinct_model_ids_in_keys": len(set(key_models)) == 2,
        "resolved_model_matches_requested_in_every_row":
            all(r["key"]["model_id"] == r["response"]["resolved_model"] for r in rows),
        # The content check: if both arms stored the SAME text, a "different
        # key" would be a distinction without a difference.
        "the_two_readers_returned_different_text": len(set(contents)) == 2,
        "gemma_row_does_not_carry_gptoss_text":
            s3["content"] != s1["content"],
        "gemma_hit_serves_gemma_text": s4["content"] == s3["content"],
    }

    log("\nSTORED ROWS (read from the JSONL, field names verified against a real row):")
    for r in rows:
        log(f"  key_hash={r['key_hash'][:16]} key['model_id']={r['key']['model_id']!r} "
            f"resolved={r['response']['resolved_model']!r} "
            f"content={r['response']['content'][:52]!r}")

    log("\nCHECKS:")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k}")

    all_ok = all(checks.values())
    out = {
        "_what": "behavioural proof that the response cache cannot serve a "
                 "gpt-oss response to a gemma request",
        "run_at_utc": utc_now(),
        "key_fields": list(KEY_FIELDS),
        "cache_schema_version": __import__("p1mem.cache", fromlist=["x"]
                                           ).CACHE_SCHEMA_VERSION,
        "shared_key_fields": KEY_FIELDS_SHARED,
        "messages_sha256": S.sha256_text(MESSAGES),
        "steps": steps,
        "stored_rows": [{"key_hash": r["key_hash"],
                         "key_model_id": r["key"]["model_id"],
                         "key_cluster": r["key"]["cluster"],
                         "key_decoding_params": r["key"]["decoding_params"],
                         "resolved_model": r["response"]["resolved_model"],
                         "content_sha256": S.sha256_text(r["response"]["content"])}
                        for r in rows],
        "checks": checks,
        "VERDICT": "CACHE_SEPARATION_PROVEN" if all_ok else "FAILED",
    }
    args.out.write_text(json.dumps(out, indent=2))
    log(f"\nVERDICT: {out['VERDICT']}")
    log(f"wrote {args.out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

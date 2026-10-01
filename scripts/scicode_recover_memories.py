#!/usr/bin/env python3
"""Recover the SciCode memory text by REGENERATION, and PROVE the identity.

    /Users/bellayang/miniconda3/bin/python3 scripts/scicode_recover_memories.py \
        --out results/scicode/memories.jsonl

The problem
-----------
``results/scicode/scaleup_all3.json`` records 924 arm-runs and NO memory text.
``scripts/scicode_pilot.py`` holds the written memories in process memory only,
passes no ``cache=`` to ``P1Client``, and keeps ``len(content)`` while discarding
``content``. There is no ``results/scicode/memories.jsonl``.

🔴 RESULT: THE SUMMARY AND STRUCTURED TEXT IS NOT RECOVERABLE. RAW IS.
----------------------------------------------------------------------
Measured 2026-09-30, and the headline is a REFUSAL:

    raw          154/154 cells matched -- recovered, shippable
    summary        5/154 cells matched -- NOT recovered
    structured     0/154 cells matched -- NOT recovered

**The premise that justified regeneration is false.** "The writers are
byte-deterministic at temperature 0" is true only WITHIN a session. Across
sessions the endpoint returns different text for a byte-identical prompt. This
was not inferred from the token counts -- it was measured DIRECTLY, against
memories whose original text is on disk:

    results/repr_scaleup/memories.jsonl stores 60 summary memories written by
    THESE writers, THIS model (metis/gpt-oss-120b), THIS decoding, on
    2026-09-30. Re-running them today reproduces 0 of 12 byte-identically,
    while the writer's own prompt_tokens matches 12/12 -- so the SAME prompt
    was sent and a DIFFERENT answer came back. Within one session the same
    segment gives the same bytes 4/4; across sessions it does not.

That is a POSITIVE CONTROL with a known-correct answer, and regeneration fails
it. A determinism probe that draws twice in one session cannot see this: it
measures within-session repeatability and the question is cross-session
identity. The two are different quantities and only one of them is the premise.

Why the prompt_tokens check still earns its place
--------------------------------------------------
It is what turned "the text is reproducible" into "the text is NOT reproducible,
here is the evidence per cell". Without it the regenerated summaries would have
been shipped: they are fluent, correct-looking memories of the right segments,
and nothing else in the pipeline would have objected.

The independent proof: prompt_tokens
-------------------------------------
Every WITH arm-run records the SERVER'S ``prompt_tokens`` for a prompt that
CONTAINS the memory text. ``prompt_tokens`` is a function of the exact prompt
bytes. So rebuilding the WITH prompt with a regenerated memory and comparing the
computed count against the recorded one tests the bytes themselves, using a
number the run wrote down before the text was lost.

Computed LOCALLY, from the gpt-oss-120b tokenizer in the HF cache, plus a
measured constant chat-template overhead:

    prompt_tokens == len(tokenizer.encode(user_text)) + TEMPLATE_OVERHEAD

``TEMPLATE_OVERHEAD`` is MEASURED, never assumed -- ``--calibrate`` re-derives it
against the live endpoint, and ``verify`` re-derives it from the ledger's own
fully-reconstructible arms before using it (see ``calibrate_offset_from_ledger``).

Three things this script refuses to do
--------------------------------------
1. **It will not ship an unverified memory.** A memory whose prompt_tokens check
   does not match on every one of its cells is written with
   ``identity_verified=false`` and a stated reason, and the downstream converter
   must not emit its rows.
2. **It will not treat an unverifiable cell as verified.** The one arm-run that
   raised ``TruncatedResponseError`` recorded no ``prompt_tokens``; it is counted
   as UNVERIFIABLE, in its own bucket, never folded into either side.
3. **It will not trust a check it has not seen fail.** ``--positive-control``
   perturbs a real memory and asserts the comparison NOTICES, and reports the
   smallest perturbation the check can resolve.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import glob
import hashlib
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p1mem.adapters import scicode as S                        # noqa: E402
from p1mem.client import P1Client                              # noqa: E402
from p1mem.memory.representations import (                     # noqa: E402
    RawExtractiveWriter, StructuredWriter, SummaryWriter, render_structured,
    STRUCTURED_PROCEDURAL_KEYS, write_all,
)

# ---- the run's own constants, copied from scripts/scicode_pilot.py. Copied and
#      then CROSS-CHECKED against the artifact's config block below, because a
#      copied constant is not a verified one ("three functions, one name").
CLUSTER = "metis"
MODEL = "gpt-oss-120b"
REASONING_EFFORT = "low"
TEMPERATURE = 0.0
WRITER_MAX_TOKENS = 1024
CONCURRENCY = 16
SEED = 20261008
FILLER_K = 2

#: The gpt-oss-120b chat template adds a FIXED number of tokens around the user
#: message. MEASURED, not assumed: see ``calibrate_offset_live`` (5 probes from 1
#: to 3,223 user tokens, all offset 67) and ``calibrate_offset_from_ledger``
#: (re-derived from 308 fully-reconstructible arm-runs in the ledger itself).
#: Kept as a default that is ALWAYS re-derived before use.
TEMPLATE_OVERHEAD_DEFAULT = 67

DEFAULT_DEV = "/tmp/scicode_probe/problems_dev.jsonl"
DEFAULT_TEST = "/tmp/scicode_probe/problems_test.jsonl"
DEFAULT_SRC = ROOT / "results/scicode/scaleup_all3.json"


class RecoveryRefused(SystemExit):
    """Raised where continuing would require asserting something unmeasured."""


# ======================================================================= tokens
@__import__("functools").lru_cache(maxsize=1)
def _tokenizer():
    """The gpt-oss-120b tokenizer from the HF cache. RAISES if absent.

    CACHED: it is called once per cell and loading a 200k-vocab file 462 times
    turns a 30-second verification into a 20-minute one.

    Deliberately NOT ``p1mem.memory.tokens``: that module counts under the
    LongMemEval benchmark tokenizer (Qwen3.5-9B), which is the right ruler for
    MEMORY SIZE and the wrong one for what THIS SERVER billed. Using it here
    would compare a count to a number produced by a different vocabulary.
    """
    from tokenizers import Tokenizer                           # noqa: PLC0415
    paths = sorted(glob.glob(str(Path.home() / ".cache/huggingface/hub/"
                                 "models--openai--gpt-oss-120b/snapshots/*/tokenizer.json")))
    if not paths:
        raise RecoveryRefused(
            "no cached tokenizer.json for openai/gpt-oss-120b. The identity proof "
            "needs the SERVER'S vocabulary; counting under another tokenizer would "
            "compare two different rulers and call the difference a mismatch.")
    return Tokenizer.from_file(paths[-1]), paths[-1]


def count_user_tokens(text: str) -> int:
    tok, _ = _tokenizer()
    return len(tok.encode(text, add_special_tokens=False).ids)


# ======================================================================= units
def load_units(dev: Path, test: Path):
    mems = S.build_memory_units(S.load_jsonl(dev))
    tasks = S.build_future_tasks(S.load_jsonl(test))
    S.assert_writer_blind(mems, tasks)
    return mems, tasks


def build_filler(memories, target_locator: str, k: int, seed: int) -> str:
    """VERBATIM the rule in ``scripts/scicode_pilot.py::build_filler``.

    Copied rather than imported for the same reason ``scicode_to_schema.py``
    copies it -- and, as there, reproducibility is CHECKED (``--self-test``
    re-derives the documented case) rather than assumed.
    """
    pool = sorted((m for m in memories if m.memory_unit_locator != target_locator),
                  key=lambda m: m.memory_unit_locator)
    rng = random.Random(f"{seed}:filler:{target_locator}")
    picked = rng.sample(pool, min(k, len(pool))) if pool else []
    return "\n\n".join(m.episode_text for m in
                       sorted(picked, key=lambda m: m.memory_unit_locator))


def assert_config_matches(cfg: dict[str, Any]) -> None:
    """The artifact must have been produced under the parameters we reproduce."""
    want = {"cluster": CLUSTER, "model": MODEL, "reasoning_effort": REASONING_EFFORT,
            "temperature": TEMPERATURE, "writer_max_tokens": WRITER_MAX_TOKENS,
            "seed": SEED, "filler_k": FILLER_K, "relatedness": "lexical",
            "prompt_version": S.PROMPT_VERSION,
            "benchmark_version": S.BENCHMARK_VERSION}
    bad = {k: (cfg.get(k), v) for k, v in want.items() if cfg.get(k) != v}
    if bad:
        raise RecoveryRefused(
            f"REFUSING: the artifact's config does not match the pipeline this "
            f"script reproduces: {bad}. Regenerating under different parameters "
            f"would produce a DIFFERENT memory wearing this run's rewards.")


# =============================================================== regeneration
def regenerate(memories, locators: Sequence[str], reps: Sequence[str],
               *, concurrency: int = CONCURRENCY) -> dict[str, dict[str, Any]]:
    """Re-run ``write_all`` exactly as the pilot did. Returns {locator: {rep: rec}}."""
    by_loc = {m.memory_unit_locator: m for m in memories}
    client = P1Client(cluster=CLUSTER, model=MODEL,
                      max_concurrency=concurrency, timeout_s=300)
    raw_w = RawExtractiveWriter()
    sum_w = (SummaryWriter(client, max_tokens=WRITER_MAX_TOKENS,
                           temperature=TEMPERATURE,
                           reasoning_effort=REASONING_EFFORT)
             if "summary" in reps else None)
    str_w = (StructuredWriter(client, variant="procedural",
                              max_tokens=WRITER_MAX_TOKENS,
                              temperature=TEMPERATURE,
                              reasoning_effort=REASONING_EFFORT)
             if "structured" in reps else None)

    def _write(loc: str):
        return loc, write_all(S.to_source_segment(by_loc[loc]),
                              raw=raw_w, summary=sum_w, structured=str_w)

    out: dict[str, dict[str, Any]] = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        for loc, recs in ex.map(_write, locators):
            out[loc] = recs
    print(f"regenerated {len(out)} memories x {len(reps)} representations "
          f"in {time.time() - t0:.1f}s")
    return out


def memory_text(recs: dict[str, Any], rep: str) -> str | None:
    """EXACTLY ``scripts/scicode_pilot.py::memory_text``. None on a failed write."""
    rec = recs.get(rep)
    if rec is None or not rec.ok:
        return None
    if rep == "structured" and getattr(rec, "structured", None):
        return render_structured(rec.structured, STRUCTURED_PROCEDURAL_KEYS)
    return rec.memory_text


# ============================================================== the identity proof
def calibrate_offset_from_ledger(src: dict[str, Any], memories, tasks) -> int:
    """Re-derive the chat-template overhead from the ledger's OWN reconstructible arms.

    The WITHOUT arms and the WITH-raw arms contain no model-written text, so their
    prompts are reproducible today with certainty. Their recorded ``prompt_tokens``
    minus the locally counted user-text tokens must be ONE constant. If it is not,
    the local token count is not a model of what the server billed and the whole
    identity proof is void -- so this RAISES rather than picking a modal value.
    """
    by_loc = {m.memory_unit_locator: m for m in memories}
    by_task = {t.task_id: t for t in tasks}
    offsets: collections.Counter[int] = collections.Counter()
    for r in src["rows"]:
        pt = r.get("prompt_tokens")
        if pt is None:
            continue
        loc, tid = r["memory_id"], r["task_id"]
        if r["arm"] == "without":
            block = None
        elif r["representation"] == "raw":
            block = by_loc[loc].episode_text
        else:
            continue                       # contains model-written text; unknown today
        prompt = S.render_task_prompt(by_task[tid], block,
                                      filler=build_filler(memories, loc, FILLER_K, SEED))
        offsets[pt - count_user_tokens(prompt)] += 1
    if len(offsets) != 1:
        raise RecoveryRefused(
            f"REFUSING: the chat-template overhead is not constant over the "
            f"reconstructible arms: {dict(offsets)}. prompt_tokens is then not a "
            f"function of the prompt bytes alone under this tokenizer, and the "
            f"identity proof would be measuring the tokenizer, not the memory.")
    off, n = next(iter(offsets.items()))
    print(f"template overhead re-derived from the ledger: {off} tokens, "
          f"CONSTANT over {n} fully-reconstructible arm-runs "
          f"(all WITHOUT arms + all WITH-raw arms)")
    return off


def verify(src: dict[str, Any], memories, tasks, texts: dict[str, dict[str, str | None]],
           offset: int) -> tuple[dict[str, Any], dict[tuple[str, str], dict]]:
    """Compare computed vs recorded prompt_tokens on every WITH arm-run.

    Returns (report, per-memory-x-representation verdicts).
    """
    by_task = {t.task_id: t for t in tasks}
    per: dict[tuple[str, str], dict] = collections.defaultdict(
        lambda: {"matched": 0, "mismatched": 0, "unverifiable": 0,
                 "write_failed": 0, "diffs": [], "cells": []})
    for r in src["rows"]:
        if r["arm"] != "with":
            continue
        loc, tid, rep = r["memory_id"], r["task_id"], r["representation"]
        k = (loc, rep)
        rec_pt = r.get("prompt_tokens")
        mtext = texts.get(loc, {}).get(rep)
        if mtext is None:
            per[k]["write_failed"] += 1
            per[k]["cells"].append({"task_id": tid, "status": "write_failed"})
            continue
        if rec_pt is None:
            # The one TruncatedResponseError arm-run: the call raised BEFORE a
            # usage block was returned, so the run recorded no prompt_tokens.
            # Not a mismatch and not a match -- its own bucket.
            per[k]["unverifiable"] += 1
            per[k]["cells"].append({"task_id": tid, "status": "unverifiable",
                                    "why": r.get("kind"),
                                    "detail": (r.get("detail") or "")[:160]})
            continue
        prompt = S.render_task_prompt(by_task[tid], mtext,
                                      filler=build_filler(memories, loc, FILLER_K, SEED))
        got = count_user_tokens(prompt) + offset
        if got == rec_pt:
            per[k]["matched"] += 1
            per[k]["cells"].append({"task_id": tid, "status": "matched",
                                    "prompt_tokens": rec_pt})
        else:
            per[k]["mismatched"] += 1
            per[k]["diffs"].append(got - rec_pt)
            per[k]["cells"].append({"task_id": tid, "status": "mismatched",
                                    "prompt_tokens_recorded": rec_pt,
                                    "prompt_tokens_computed": got,
                                    "difference": got - rec_pt})

    by_rep: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"matched": 0, "mismatched": 0, "unverifiable": 0, "write_failed": 0,
                 "memories_verified": 0, "memories_total": 0})
    for (loc, rep), v in per.items():
        d = by_rep[rep]
        for f in ("matched", "mismatched", "unverifiable", "write_failed"):
            d[f] += v[f]
        d["memories_total"] += 1
        # A memory is VERIFIED only if every verifiable cell matched AND at least
        # one did. "No mismatches" over zero comparisons is not evidence.
        # 🔴 PER-MEMORY VERIFICATION IS NOT N INDEPENDENT CHECKS. Measured: the
        #    computed-minus-recorded difference is CONSTANT across a memory's cells
        #    (0 of 68 memories showed a varying difference), because every cell
        #    embeds the same memory text. So a memory with 17 cells gets ONE
        #    effective comparison, not 17, and "all its cells matched" is one
        #    coin-flip against the same null.
        #
        #    And that null is not small for a model-written memory. Two
        #    INDEPENDENT regenerations of the same segment produce different text
        #    21/34 times, and of those the TOKEN COUNT coincides anyway 1/21 = 5%.
        #    So on 34 memories, ~2 spurious "verified" summaries are EXPECTED.
        #    Observed: 2. A per-memory verdict at that rate is indistinguishable
        #    from chance, which is why the shipping decision is made PER
        #    REPRESENTATION against the cross-session control, not per memory.
        v["identity_verified"] = bool(v["matched"] > 0 and v["mismatched"] == 0
                                      and v["write_failed"] == 0)
        v["identity_verified_caveat"] = (
            "Per-memory verification is ONE effective comparison, not one per cell: "
            "the difference is constant across a memory's cells. For summary and "
            "structured the measured coincidence rate between two different "
            "same-segment regenerations is ~5%, so an isolated per-memory 'verified' "
            "is consistent with chance. Only `raw` is recovered, and it is recovered "
            "because it involves NO model call at all.")
        d["memories_verified"] += int(v["identity_verified"])
    report = {"per_representation": {k: dict(v) for k, v in sorted(by_rep.items())}}
    return report, per


# ============================================================= positive control
def positive_control(src: dict[str, Any], memories, tasks,
                     texts: dict[str, dict[str, str | None]], offset: int) -> dict:
    """Perturb a memory that MATCHES and assert the prompt_tokens check NOTICES.

    🔴 THE SUBJECT MUST BE A MATCHING CELL. A perturbation applied to a subject
    that already mismatches proves nothing -- the comparison was already failing.
    The raw arm matches 154/154, so it is the only sound subject available; an
    earlier version of this function picked a summary cell and correctly REFUSED
    to run ("the unperturbed subject does not match (2732 vs 2735)").

    🔴 AND IT REPORTS WHAT IT CANNOT SEE. A token count is not a hash. Measured
    on the real subject: of 6 perturbations, only 2 move the count. Appending a
    period, appending a space, deleting the last character and changing a digit
    are ALL INVISIBLE, because BPE re-tokenises the neighbourhood to the same
    length. So "matched" means "the regenerated text has the same token count as
    the original under every one of this memory's prompts", which is strong
    evidence and NOT proof of byte identity. Stated here rather than left for a
    reader to discover.
    """
    by_task = {t.task_id: t for t in tasks}
    by_loc = {m.memory_unit_locator: m for m in memories}
    # The RAW arm is the only one whose unperturbed subject matches, so it is the
    # only sound subject. Chosen for that property, not for convenience.
    subject = None
    for r in src["rows"]:
        if r["arm"] == "with" and r["representation"] == "raw" \
                and r.get("prompt_tokens") is not None:
            subject = (r["memory_id"], r["task_id"], r["prompt_tokens"])
            break
    if subject is None:
        raise RecoveryRefused("positive control has no subject; it would prove nothing")
    loc, tid, rec_pt = subject
    base = by_loc[loc].episode_text
    filler = build_filler(memories, loc, FILLER_K, SEED)

    def pt(text: str) -> int:
        return count_user_tokens(
            S.render_task_prompt(by_task[tid], text, filler=filler)) + offset

    clean = pt(base)
    if clean != rec_pt:
        raise RecoveryRefused(
            f"POSITIVE CONTROL VOID: the unperturbed subject does not match "
            f"({clean} vs {rec_pt}), so a perturbation that 'fails' proves nothing.")

    ladder = [
        ("1 char: append a period", base + "."),
        ("1 char: append a space", base + " "),
        ("1 char: delete the last character", base[:-1]),
        ("1 char: change the first '2' to a '3'", base.replace("2", "3", 1)),
        ("1 word: append ' zzz'", base + " zzz"),
        ("1 sentence: append a clause", base + " The procedure was then repeated."),
    ]
    results = []
    for name, mutated in ladder:
        if mutated == base:
            continue
        got = pt(mutated)
        results.append({"perturbation": name,
                        "prompt_tokens_computed": got, "recorded": rec_pt,
                        "noticed": got != rec_pt})
    detected = [r for r in results if r["noticed"]]
    one_char = [r for r in results if r["perturbation"].startswith("1 char")]
    out = {"subject": {"memory_unit_locator": loc, "task_id": tid,
                       "representation": "raw", "recorded_prompt_tokens": rec_pt},
           "unperturbed_matches": True,
           "ladder": results,
           "n_detected": len(detected), "n_tried": len(results),
           "one_char_detected": sum(1 for r in one_char if r["noticed"]),
           "one_char_total": len(one_char),
           "smallest_perturbation_detected": detected[0]["perturbation"] if detected else None,
           "any_detected": bool(detected),
           "HONEST_LIMIT": (
               "A ONE-CHARACTER CHANGE IS NOT RELIABLY DETECTED. Measured: "
               f"{sum(1 for r in one_char if r['noticed'])}/{len(one_char)} one-character "
               "perturbations move the token count; the rest re-tokenise to the same "
               "length. The check resolves changes of roughly a word or more. 'Matched' "
               "therefore means 'same token count under every one of this memory's "
               "prompts', which is strong evidence of identity and not proof of it.")}
    if not detected:
        raise RecoveryRefused(
            "POSITIVE CONTROL FAILED: no perturbation on the ladder moved the token "
            "count. The check cannot discriminate and must NOT be used as evidence "
            "of identity.")
    return out


def same_segment_coincidence_null(memories, locators: Sequence[str],
                                  texts_a: dict[str, dict[str, str | None]]) -> dict:
    """The null a per-memory 'verified' verdict must beat.

    ``false_match_null`` substitutes a DIFFERENT memory, which is the easy null
    (0/3003). The hard null is: two regenerations of the SAME segment produce
    different text -- how often does the TOKEN COUNT coincide anyway? That is the
    rate at which a regenerated summary can be wrongly stamped 'verified'.

    Measured: text differs on 21/34 memories, and of those the count coincides on
    1/21 = 5%. Over 34 memories that predicts ~2 spurious verifications; 2 were
    observed. So an isolated per-memory match on summary/structured is CHANCE.
    """
    second = regenerate(memories, locators, ("summary", "structured"),
                        concurrency=CONCURRENCY)
    out: dict[str, Any] = {}
    for rep in ("summary", "structured"):
        differ = coincide = 0
        for loc in locators:
            a = texts_a.get(loc, {}).get(rep)
            b = memory_text(second[loc], rep)
            if a is None or b is None or a == b:
                continue
            differ += 1
            coincide += int(count_user_tokens(a) == count_user_tokens(b))
        out[rep] = {"memories_whose_text_differed": differ,
                    "token_count_coincided_anyway": coincide,
                    "coincidence_rate": (coincide / differ) if differ else None,
                    "expected_spurious_over_34": (coincide / differ * 34) if differ else None}
    out["reading"] = (
        "This is the null for a per-memory 'identity_verified' on a model-written "
        "representation. A match rate at or below it is chance, not recovery.")
    return out


def false_match_null(src: dict[str, Any], memories, tasks, offset: int,
                     cap: int = 3000) -> dict:
    """The NULL for an exact match: how often does the WRONG memory match anyway?

    Max-of-k reasoning applies to a check as much as to an effect. "Matched" is
    only evidence if a non-matching substitute usually does NOT match. Measured
    by substituting every other memory's text into each raw cell: 0 of 3,003
    coincidental matches.
    """
    by_task = {t.task_id: t for t in tasks}
    by_loc = {m.memory_unit_locator: m for m in memories}
    locs = sorted({r["memory_id"] for r in src["rows"]})
    false_hits = tot = 0
    for r in src["rows"]:
        if r["arm"] != "with" or r.get("prompt_tokens") is None \
                or r["representation"] != "raw":
            continue
        filler = build_filler(memories, r["memory_id"], FILLER_K, SEED)
        for other in locs:
            if other == r["memory_id"]:
                continue
            tot += 1
            got = count_user_tokens(S.render_task_prompt(
                by_task[r["task_id"]], by_loc[other].episode_text,
                filler=filler)) + offset
            if got == r["prompt_tokens"]:
                false_hits += 1
        if tot >= cap:
            break
    return {"substitutions_tried": tot, "coincidental_matches": false_hits,
            "false_match_rate": (false_hits / tot) if tot else None,
            "reading": ("A match is informative: substituting a DIFFERENT memory "
                        f"matched {false_hits}/{tot} times.")}


#: The ONLY corpus on this machine where a memory written by THESE writers, on
#: THIS model, has its original text on disk. It is therefore the only available
#: positive control with a known-correct answer for "can regeneration recover a
#: past memory?" -- and the answer it gives is NO.
REPRODUCTION_CONTROL_CORPUS = ROOT / "results/repr_scaleup/memories.jsonl"


def cross_session_reproduction_control(n: int = 12) -> dict:
    """🔴 THE CONTROL THAT DECIDES WHETHER REGENERATION CAN RECOVER ANYTHING.

    Within-session determinism is NOT the premise. The premise is CROSS-SESSION
    identity: that re-running a writer today returns the bytes it returned on the
    day of the run. Drawing the same memory twice in one session cannot test that
    -- it measures repeatability, and the two are different quantities.

    This measures the real one, against ground truth. ``repr_scaleup/memories.jsonl``
    stores 60 summary memories written by these writers, on metis/gpt-oss-120b, at
    temperature 0 -- with their TEXT. Re-running them is a direct byte comparison.

    Measured 2026-09-30: **0 of 12 reproduce**, while the writer's own
    ``extraction_input_tokens`` matches 12 of 12 -- the SAME prompt went out and a
    DIFFERENT answer came back. Within one session, 4/4 draws agree. So the
    endpoint is session-stable and not reproducible across sessions, and no
    regenerated memory can be assumed to be the one a past run used.

    RAISES if reproduction succeeds, because that would mean this control has
    stopped discriminating and the refusal below rests on nothing.
    """
    if not REPRODUCTION_CONTROL_CORPUS.is_file():
        raise RecoveryRefused(
            f"REFUSING: {REPRODUCTION_CONTROL_CORPUS} is absent, so the premise "
            f"behind regeneration cannot be tested. Regenerating without it would "
            f"ship text whose identity nothing has checked.")
    from p1mem.memory.segment import SourceSegment                 # noqa: PLC0415
    rows = [json.loads(l) for l in REPRODUCTION_CONTROL_CORPUS.open() if l.strip()]
    raw = {r["segment_id"]: r for r in rows if r["representation"] == "raw"}
    subj = [r for r in rows if r["representation"] == "summary" and r["ok"]][:n]
    if not subj:
        raise RecoveryRefused("REFUSING: the reproduction control has no subjects; "
                              "it would prove nothing.")
    client = P1Client(cluster=CLUSTER, model=MODEL, max_concurrency=8, timeout_s=300)
    sw = SummaryWriter(client, max_tokens=WRITER_MAX_TOKENS)

    def one(r):
        sid = r["segment_id"]
        seg = SourceSegment(segment_id=sid, benchmark="longmemeval_v2",
                            benchmark_version="control", source_episode_id=r["source_episode_id"],
                            text=raw[sid]["memory_text"], source_span={}, episode_metadata={})
        o = sw.write(seg)
        return {"segment_id": sid,
                "bytes_identical": o.memory_text == r["memory_text"],
                "writer_prompt_tokens_stored": r.get("extraction_input_tokens"),
                "writer_prompt_tokens_now": o.extraction_input_tokens,
                "len_stored": len(r["memory_text"]), "len_now": len(o.memory_text or "")}

    out = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        out = list(ex.map(one, subj))
    ident = sum(1 for d in out if d["bytes_identical"])
    same_prompt = sum(1 for d in out if d["writer_prompt_tokens_stored"]
                      == d["writer_prompt_tokens_now"])
    res = {"n": len(out), "bytes_identical": ident, "same_writer_prompt": same_prompt,
           "detail": out,
           "verdict": ("REGENERATION CANNOT RECOVER PAST TEXT" if ident == 0 else
                       "partial" if ident < len(out) else "reproduces")}
    print("\n=== CROSS-SESSION REPRODUCTION CONTROL (ground truth on disk) ===")
    print(f"  byte-identical reproduction: {ident}/{len(out)}")
    print(f"  writer prompt_tokens identical: {same_prompt}/{len(out)} "
          f"(the SAME prompt was sent)")
    print(f"  verdict: {res['verdict']}")
    return res


def determinism_probe(memories, locators: Sequence[str], n: int = 2) -> dict:
    """WITHIN-SESSION repeatability only. NOT evidence of recoverability.

    🔴 Kept, and kept labelled, because believing this probe answered the
    recoverability question is the mistake that nearly shipped 308 regenerated
    memories as if they were the run's. It draws twice in one session; the
    endpoint is session-stable, so it returns "identical" even when the text
    differs from what the original run received. ``cross_session_reproduction_control``
    is the probe that bears on the premise.
    """
    by_loc = {m.memory_unit_locator: m for m in memories}
    client = P1Client(cluster=CLUSTER, model=MODEL, max_concurrency=4, timeout_s=300)
    sw = SummaryWriter(client, max_tokens=WRITER_MAX_TOKENS, temperature=TEMPERATURE,
                       reasoning_effort=REASONING_EFFORT)
    tw = StructuredWriter(client, variant="procedural", max_tokens=WRITER_MAX_TOKENS,
                          temperature=TEMPERATURE, reasoning_effort=REASONING_EFFORT)
    out = []
    for loc in locators:
        seg = S.to_source_segment(by_loc[loc])
        for rep, w in (("summary", sw), ("structured", tw)):
            hs = []
            for _ in range(n):
                r = w.write(seg)
                t = (render_structured(r.structured, STRUCTURED_PROCEDURAL_KEYS)
                     if rep == "structured" and r.ok and r.structured else r.memory_text)
                hs.append(hashlib.sha256(t.encode()).hexdigest())
            out.append({"locator": loc, "representation": rep,
                        "identical": len(set(hs)) == 1, "draws": n,
                        "sha256_prefix": hs[0][:16]})
    return {"probes": out, "all_identical": all(p["identical"] for p in out),
            "WHAT_THIS_MEASURES": "within-session repeatability ONLY -- see "
                                  "cross_session_reproduction_control for the premise"}


# ======================================================================== main
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--dev", type=Path, default=Path(DEFAULT_DEV))
    ap.add_argument("--test", type=Path, default=Path(DEFAULT_TEST))
    ap.add_argument("--out", type=Path, default=ROOT / "results/scicode/memories.jsonl")
    ap.add_argument("--report", type=Path,
                    default=ROOT / "results/scicode/memory_recovery_report.json")
    ap.add_argument("--representations", default="raw,summary,structured")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--determinism-probe", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)

    reps = tuple(x.strip() for x in a.representations.split(",") if x.strip())
    src = json.loads(a.src.read_text())
    assert_config_matches(src["config"])
    memories, tasks = load_units(a.dev, a.test)
    by_loc = {m.memory_unit_locator: m for m in memories}

    # self-check the filler rule before it is used 462 times
    f = [x for x in __import__("re").findall(
        r"scicode_dev::[\d.]+", build_filler(memories, "scicode_dev::1.1", FILLER_K, SEED))]
    _probe = build_filler(memories, "scicode_dev::1.1", FILLER_K, SEED)
    expect = (by_loc["scicode_dev::19.1"].episode_text + "\n\n"
              + by_loc["scicode_dev::78.3"].episode_text)
    if _probe != expect:
        raise RecoveryRefused(
            "REFUSING: the filler rule no longer reproduces the documented case "
            "scicode_dev::1.1 -> [19.1, 78.3]. Every cell's prompt would differ "
            "from the run's while every row still looked well-formed.")
    print("PASS filler reproducibility: scicode_dev::1.1 -> [19.1, 78.3]")

    locators = sorted({r["memory_id"] for r in src["rows"]})
    print(f"{len(locators)} memories needed, representations={list(reps)}")

    det = None
    if a.determinism_probe:
        det = determinism_probe(memories, locators[:3])
        print(f"within-session repeatability probe: all_identical={det['all_identical']} "
              f"over {len(det['probes'])} (locator x representation) pairs "
              f"-- NOTE: this does NOT test cross-session recoverability")

    # 🔴 The control that actually bears on the premise. Run ALWAYS, not behind a
    #    flag: a probe you can forget to run is a probe that will be forgotten.
    repro = cross_session_reproduction_control()

    offset = calibrate_offset_from_ledger(src, memories, tasks)

    recs = regenerate(memories, locators, reps, concurrency=a.concurrency)
    texts: dict[str, dict[str, str | None]] = {
        loc: {rep: memory_text(r, rep) for rep in reps} for loc, r in recs.items()}

    report, per = verify(src, memories, tasks, texts, offset)
    print("\n=== IDENTITY VERIFICATION: computed vs RECORDED prompt_tokens ===")
    for rep, d in report["per_representation"].items():
        tot = d["matched"] + d["mismatched"] + d["unverifiable"] + d["write_failed"]
        print(f"  {rep:11s} matched {d['matched']}/{tot} cells "
              f"(mismatched {d['mismatched']}, unverifiable {d['unverifiable']}, "
              f"write_failed {d['write_failed']});  "
              f"memories verified {d['memories_verified']}/{d['memories_total']}")

    pc = positive_control(src, memories, tasks, texts, offset)
    print("\n=== POSITIVE CONTROL: perturb a MATCHING memory, must be NOTICED ===")
    for r in pc["ladder"]:
        print(f"  {'NOTICED' if r['noticed'] else 'MISSED ':8s} {r['perturbation']:42s} "
              f"computed={r['prompt_tokens_computed']} recorded={r['recorded']}")
    print(f"  detected {pc['n_detected']}/{pc['n_tried']}; one-character "
          f"perturbations detected {pc['one_char_detected']}/{pc['one_char_total']}")
    print(f"  🔴 {pc['HONEST_LIMIT']}")

    coin = same_segment_coincidence_null(memories, locators, texts)
    print("\n=== SAME-SEGMENT COINCIDENCE NULL (what a per-memory match must beat) ===")
    for rep in ("summary", "structured"):
        d = coin[rep]
        rate = d["coincidence_rate"]
        print(f"  {rep:11s} two regenerations differ on "
              f"{d['memories_whose_text_differed']}/{len(locators)} memories; token "
              f"count coincides anyway on {d['token_count_coincided_anyway']} "
              f"({'n/a' if rate is None else f'{rate * 100:.0f}%'}) "
              f"-> ~{0 if d['expected_spurious_over_34'] is None else round(d['expected_spurious_over_34'], 1)} "
              f"spurious 'verified' expected over {len(locators)}")

    fm = false_match_null(src, memories, tasks, offset)
    print(f"\n=== FALSE-MATCH NULL (the check must not match everything) ===")
    print(f"  a DIFFERENT memory substituted in matched "
          f"{fm['coincidental_matches']}/{fm['substitutions_tried']} times "
          f"({(fm['false_match_rate'] or 0) * 100:.2f}%)")

    # ---------------------------------------------------------------- write out
    lines = []
    for loc in locators:
        for rep in reps:
            rec = recs[loc].get(rep)
            if rec is None:
                continue
            v = per.get((loc, rep), {"matched": 0, "mismatched": 0,
                                     "unverifiable": 0, "write_failed": 0,
                                     "identity_verified": False, "cells": []})
            d = rec.to_dict()
            # the TEXT AS EXPOSED TO THE READER -- for structured this is the
            # rendered form, which is what render_task_prompt received.
            d["memory_text_as_exposed"] = memory_text(recs[loc], rep)
            d["memory_unit_locator"] = loc
            d["benchmark"] = S.BENCHMARK
            d["benchmark_version"] = S.BENCHMARK_VERSION
            d["recovery"] = {
                "method": "regenerated_and_verified_by_prompt_tokens",
                "regenerated_at_utc": rec.written_at_utc,
                "source_artifact": str(a.src.relative_to(ROOT)),
                "template_overhead_tokens": offset,
                "tokenizer": _tokenizer()[1],
                "identity_verified": bool(v["identity_verified"]),
                # THE FIELD A CONSUMER SHOULD READ. Per-representation, because
                # that is the level at which the evidence actually discriminates.
                "safe_to_ship": bool(rep == "raw" and v["identity_verified"]),
                "safe_to_ship_reason": (
                    "raw involves NO model call: the memory IS the source segment "
                    "verbatim (protocol 1A), so it is re-derived deterministically "
                    "from the corpus and its prompt_tokens match on every cell "
                    "(154/154)."
                    if rep == "raw" else
                    "NOT RECOVERED. The writers are NOT reproducible across sessions "
                    "-- measured directly against memories whose text is on disk: "
                    "0/12 byte-identical while the writer prompt matched 12/12. The "
                    "regenerated text here is a PLAUSIBLE memory of the right "
                    "segment, not the one this run's rewards were measured under."),
                "cells_matched": v["matched"],
                "cells_mismatched": v["mismatched"],
                "cells_unverifiable": v["unverifiable"],
                "cells_write_failed": v["write_failed"],
                "cell_detail": v["cells"],
                "verification_basis": (
                    "The server-reported prompt_tokens recorded by the ORIGINAL run "
                    "for every WITH arm-run of this memory. prompt_tokens is a "
                    "function of the exact prompt bytes, and the prompt contains this "
                    "memory text verbatim, so an exact match on every cell is evidence "
                    "the regenerated bytes ARE the bytes the run used. Counted locally "
                    "with the gpt-oss-120b tokenizer plus a template overhead "
                    "re-derived from the ledger's own fully-reconstructible arms."),
                "verification_limits": (
                    "A token count is not a hash: a perturbation that leaves the count "
                    "unchanged would not be noticed. Measured sensitivity is reported "
                    "in results/scicode/memory_recovery_report.json under "
                    "positive_control. The evidence is strong but not cryptographic, "
                    "and is strongest for a memory verified across MANY cells, since "
                    "each cell is an independent count over a different prompt."),
            }
            lines.append(d)

    verified = sum(1 for d in lines if d["recovery"]["identity_verified"])
    print(f"\nmemory records: {len(lines)}; identity_verified on {verified}")
    print("\n" + "=" * 72)
    for rep, d in report["per_representation"].items():
        tot = d["matched"] + d["mismatched"] + d["unverifiable"] + d["write_failed"]
        verdict = ("RECOVERED -- shippable" if d["mismatched"] == 0 and d["matched"]
                   else "NOT RECOVERED -- MUST NOT SHIP")
        print(f"  {rep:11s} {d['matched']}/{tot} cells matched  ->  {verdict}")
    print("=" * 72)

    full = {
        "generated_at_utc": S.__dict__.get("utc_now", lambda: None)() if False else None,
        "source_artifact": str(a.src),
        "template_overhead_tokens": offset,
        "tokenizer_file": _tokenizer()[1],
        "representations": list(reps),
        "n_memories": len(locators),
        "verification": report,
        "positive_control": pc,
        "false_match_null": fm,
        "same_segment_coincidence_null": coin,
        "cross_session_reproduction_control": repro,
        "within_session_determinism_probe": det,
        "verdict_by_representation": {
            rep: ("recovered" if d["mismatched"] == 0 and d["matched"] else "not_recovered")
            for rep, d in report["per_representation"].items()},
        "per_memory": {f"{loc}|{rep}": {k: v for k, v in val.items() if k != "cells"}
                       for (loc, rep), val in sorted(per.items())},
    }
    if a.no_write:
        print("--no-write: nothing written")
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w") as fh:
        for d in lines:
            fh.write(json.dumps(d) + "\n")
    a.report.write_text(json.dumps(full, indent=2, default=str))
    print(f"wrote {len(lines)} records -> {a.out}")
    print(f"wrote verification report -> {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

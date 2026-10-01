#!/usr/bin/env python3
"""GF5: GF-LLM, the secondary gold-free screen. Pre-committed in
``docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md`` §3.

WHY IT IS NEEDED, measured rather than anticipated
--------------------------------------------------
GF-LEX fires on 218 cells and **95% of those firings rest on a SINGLE
anchor term**. The most productive anchors are generic words that happen to be
rare in the memory pool -- ``five`` (49 firings), ``two`` (27), ``typically``
(16), ``whenever``, ``appears``, ``without``. Reading the cells shows the
expected failure: a question asking what a banner says "whenever you change"
fires on a memory containing the phrase, which is right; but a question asking
what button "appears" fires on a memory where a review "appears positive",
which is pure coincidence.

So GF-LEX's firing set is a mixture of real topical matches and lexical
accidents, and a null from it alone could not distinguish "gold-free bearing
has no effect" from "this detector does not identify bearing". GF-LLM asks a
model the question directly.

GOLD-FREE BY CONSTRUCTION: the prompt contains the QUESTION and the MEMORY.
It never contains the gold answer, the eval spec, a reward, or a reader
output. The model is asked whether the memory contains what the question
NEEDS -- not what the answer is. Writer-blindness discipline does not apply
(this is a screen, not a writer); temperature 0, a fixed prompt version and a
recorded model/cluster do.

TWO STAGES, because the exhaustive form is 277,594 calls
--------------------------------------------------------
recall    the same anchors, requiring only ceil(|A|/3) present, plus a
          content-blind 20,000-token size cap (the design's own). Exhaustive
          over the pool and cheap.
precision one LLM call per surviving candidate.

Because recall is exhaustive and the LLM stage can only SHRINK its output, the
composite's full-pool firing set is EXACT -- so the 1<=k<=8 discriminativeness
constraint is enforced in the same shape as the gold screen's, not approximated.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from gf1_gold_free_screen import (BOILERPLATE_Q_FRAC, MAX_DF,  # noqa: E402
                                  MAX_POOL_HITS, MIN_DF, question_anchors)
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.leakage import normalize_text  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.memory.tokens import count_tokens  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

PROMPT_VERSION = "gf_bearing_judge_v1"
JUDGE_MODEL = "gpt-oss-120b"
JUDGE_CLUSTER = "metis"
RECALL_FRACTION = 1.0 / 3.0
SIZE_CAP_TOKENS = 20000

SYSTEM = (
    "You judge whether a stored memory is RELEVANT to a question. "
    "You are not answering the question and you are not told the answer."
)

#: The gold answer is absent from this template BY CONSTRUCTION -- there is no
#: field for it. ``assert_prompt_is_gold_free`` proves it at run time.
TEMPLATE = """Below is a QUESTION and a MEMORY recorded from an earlier session.

Decide: does the MEMORY contain the specific information this QUESTION asks about?

Answer YES only if someone reading this memory would find the particular fact,
value, label or step the question is asking for. Answer NO if the memory is
merely about a similar topic, mentions the same words, or is about the same
website or system without containing what is asked for.

--- QUESTION ---
{question}

--- MEMORY ---
{memory}

Reply with exactly one word: YES or NO."""


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def build_prompt(question: str, memory: str) -> str:
    return TEMPLATE.format(question=question, memory=memory)


def assert_prompt_is_gold_free(prompt: str, question: str, memory: str,
                               task_id: str) -> None:
    """RUN-TIME PROOF that nothing but the question and the memory reached the
    judge.

    The structural argument is that ``build_prompt`` takes no gold parameter.
    This is the refactor-proof companion, in the spirit of
    ``lmev2.assert_writer_blind``: re-render the template from the two declared
    inputs and require BYTE EQUALITY with what is about to be sent. Any third
    field -- a gold answer, an eval spec, a reward -- would break the equality.

    🔴 **THIS CHECK REPLACED A WRONG ONE, and the wrong one fired.** The first
    version asserted that the normalized gold STRING did not occur in the
    question/instruction block. It aborted the run on task ``ca8e070b``, whose
    question ends *"...true or false?"* against the gold answer ``false``.

    That was a FALSE POSITIVE, and the distinction matters for what this screen
    claims. **Gold-free means the gold answer is not supplied as a privileged
    input** -- not that the gold string is absent from the question. The
    question is a legitimate input: a deployable retriever reads it too. A
    substring test conflates "the screen was told the answer" with "the
    benchmark's own question happens to contain its answer", which is a
    property of the corpus.

    Measured, and disclosed rather than suppressed: **69 of the 295
    deterministically-scored questions contain their own normalized gold
    answer** -- mostly true/false items and ones whose answer is a word from
    the prompt (``User``, ``Incident``, ``one``, ``four``). This is a fact
    about LongMemEval-V2's questions. It affects BOTH screens' candidate
    universe equally and is reported in the ledger as
    ``n_tasks_whose_question_contains_its_own_gold``.
    """
    if prompt != TEMPLATE.format(question=question, memory=memory):
        raise SystemExit(
            f"judge prompt for task {task_id} is NOT a pure rendering of "
            f"(question, memory) through the fixed template: some other field "
            f"entered the prompt. The screen would not be gold-free.")
    if "{" in TEMPLATE.replace("{question}", "").replace("{memory}", ""):
        raise SystemExit("the judge TEMPLATE has a field other than "
                         "question/memory")


def control_judge_can_say_both(client, cache_note: str) -> dict:
    """Prove the judge can answer YES and can answer NO.

    A judge that says NO to everything would produce an empty firing set, and
    an empty set is indistinguishable from 'nothing bears'. Two hand-built
    cases, one of each, with the expected answers fixed here in advance.
    """
    q = "On the Products page, what is the label of the blue button in the top right?"
    yes_mem = ("State 3 (step 3)\n- URL: https://shop.invalid/admin/products\n"
               "- AXTree:\nRootWebArea 'Products'\n\t[88] button 'Add Product', "
               "visible, class='primary blue', top-right\n")
    no_mem = ("State 1 (step 1)\n- URL: https://shop.invalid/admin/customers\n"
              "- AXTree:\nRootWebArea 'Customers'\n\t[12] textbox 'Search customers'\n"
              "\t[14] link 'Export CSV'\n")
    out = {}
    for lab, mem, expect in (("positive", yes_mem, "YES"), ("negative", no_mem, "NO")):
        txt, _ = client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": build_prompt(q, mem)}],
            max_tokens=256, temperature=0.0, reasoning_effort="low",
            cache_key_fields={"benchmark": "gf_control", "source_item_id": lab,
                              "memory_repr": "raw", "memory_id": lab,
                              "future_task_id": "ctrl", "arm": "with_memory",
                              "retrieval_method": "oracle",
                              "prompt_version": PROMPT_VERSION, "replicate_id": 0})
        out[lab] = {"expected": expect, "raw": txt, "parsed": parse_verdict(txt)}
    ok = (out["positive"]["parsed"] is True and out["negative"]["parsed"] is False)
    return {"_what": "the judge must be able to say YES and NO; a judge that "
                     "never fires makes an empty firing set uninterpretable",
            "cases": out, "PASS": bool(ok), "_cache": cache_note}


def parse_verdict(text: str | None) -> bool | None:
    """YES/NO -> True/False. UNPARSEABLE -> None, never False.

    An unparseable judgement is NOT a 'no'. Returning False would turn an
    absence into a measurement -- the register's most repeated defect.
    """
    if text is None:
        return None
    t = text.strip().upper()
    for line in reversed([x for x in t.splitlines() if x.strip()]):
        s = line.strip().strip(".*_` ").strip()
        if s.startswith("YES"):
            return True
        if s.startswith("NO"):
            return False
    if "YES" in t and "NO" not in t:
        return True
    if "NO" in t and "YES" not in t:
        return False
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=1200)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_llm_screen.json")
    ap.add_argument("--fires-out", type=Path,
                    default=REPO / "data/manifests/gf_llm_bearing.jsonl")
    ap.add_argument("--cache", type=Path,
                    default=REPO / "results/gf_llm/judge_cache.jsonl")
    args = ap.parse_args()

    t0 = time.time()
    units = {u["memory_unit_locator"]: u for u in
             (json.loads(l) for l in
              (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
               ).read_text().splitlines() if l.strip())}
    ut = {}
    for line in (REPO / ".sa_goldfree_scratch/unit_texts.jsonl").read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            ut[d["memory_unit_locator"]] = d
    tasks = {t.id: t for t in lmev2.load_tasks(args.root) if t.deterministic}

    unit_terms = {loc: set(normalize_text(d["text"]).split()) for loc, d in ut.items()}
    by_dom: dict[str, list[str]] = collections.defaultdict(list)
    for loc, d in ut.items():
        by_dom[d["domain"]].append(loc)
    for v in by_dom.values():
        v.sort()
    df: dict[str, collections.Counter] = {}
    for dom, locs in by_dom.items():
        c: collections.Counter = collections.Counter()
        for l in locs:
            c.update(unit_terms[l])
        df[dom] = c
    qn: collections.Counter = collections.Counter()
    qdf: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for t in tasks.values():
        qn[t.domain] += 1
        qdf[t.domain].update(set(normalize_text(t.question).split()))
    boiler = {d: {w for w, c in qdf[d].items() if c >= BOILERPLATE_Q_FRAC * qn[d]}
              for d in qdf}

    # ---- recall stage: exhaustive over the pool ----
    cands: list[tuple[str, str]] = []
    anchors_by_task = {}
    n_over_cap = 0
    for t in tasks.values():
        anc = question_anchors(t.question, df[t.domain], boiler[t.domain],
                               min_df=MIN_DF, max_df=MAX_DF)
        anchors_by_task[t.id] = anc
        if not anc:
            continue
        need = math.ceil(RECALL_FRACTION * len(anc))
        for m in by_dom[t.domain]:
            if sum(1 for w in anc if w in unit_terms[m]) >= need:
                if units[m]["n_tokens"] > SIZE_CAP_TOKENS:
                    n_over_cap += 1
                    continue
                cands.append((m, t.id))
    cands.sort()
    log(f"recall stage: {len(cands)} candidates "
        f"(+{n_over_cap} excluded by the {SIZE_CAP_TOKENS}-token content-blind cap)")
    log(f"PLANNED JUDGE CALLS: {len(cands)} (budget {args.max_calls})")
    if len(cands) > args.max_calls:
        raise SystemExit(f"planned {len(cands)} exceeds --max-calls {args.max_calls}")

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    cache = ResponseCache(args.cache)
    client = P1Client(cluster=JUDGE_CLUSTER, model=JUDGE_MODEL, cache=cache,
                      max_concurrency=args.workers)

    ctrl = control_judge_can_say_both(client, str(args.cache.name))
    log(f"judge control: PASS={ctrl['PASS']} "
        f"positive={ctrl['cases']['positive']['parsed']} "
        f"negative={ctrl['cases']['negative']['parsed']}")
    if not ctrl["PASS"]:
        raise SystemExit("judge control FAILED: a judge not shown to say both "
                         "YES and NO makes its firing set uninterpretable")

    # gold-freeness, proven on every prompt
    for m, tid in cands:
        assert_prompt_is_gold_free(
            build_prompt(tasks[tid].question, ut[m]["text"]),
            tasks[tid].question, ut[m]["text"], tid)
    log(f"gold-freeness asserted on all {len(cands)} judge prompts")
    # DISCLOSED corpus property (see assert_prompt_is_gold_free): how many
    # questions contain their own gold answer. Not a defect of either screen --
    # it is what the benchmark ships -- but a reader must be able to see it.
    n_self = sum(1 for t in tasks.values()
                 if (g := normalize_text(t.answer)) and len(g) > 2
                 and g in normalize_text(t.question))
    log(f"corpus property: {n_self}/{len(tasks)} deterministic questions contain "
        f"their own normalized gold answer (true/false items etc.) -- disclosed, "
        f"affects both screens equally")

    def run_one(mt):
        m, tid = mt
        t = tasks[tid]
        try:
            txt, rec = client.chat(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": build_prompt(t.question, ut[m]["text"])}],
                max_tokens=256, temperature=0.0, reasoning_effort="low",
                cache_key_fields={"benchmark": "longmemeval_v2",
                                  "source_item_id": units[m]["trajectory_id"],
                                  "memory_repr": "raw", "memory_id": units[m]["memory_id"],
                                  "future_task_id": tid, "arm": "with_memory",
                                  "retrieval_method": "oracle",
                                  "prompt_version": PROMPT_VERSION,
                                  "replicate_id": 0})
            return m, tid, txt, rec, None
        except ClientError as e:
            return m, tid, None, None, f"{type(e).__name__}: {e}"

    log(f"judging {len(cands)} candidates at concurrency {args.workers} ...")
    verdicts: dict[tuple[str, str], bool | None] = {}
    raw: dict[tuple[str, str], str | None] = {}
    n_err = n_unparse = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, c) for c in cands]
        for n, fut in enumerate(as_completed(futs), 1):
            m, tid, txt, _rec, err = fut.result()
            if err:
                n_err += 1
                verdicts[(m, tid)] = None
            else:
                v = parse_verdict(txt)
                if v is None:
                    n_unparse += 1
                verdicts[(m, tid)] = v
                raw[(m, tid)] = txt
            if n % 200 == 0:
                log(f"  {n}/{len(cands)} judged (errors={n_err} unparsed={n_unparse})")
    log(f"judging done: {n_err} errors, {n_unparse} unparseable "
        f"(both counted as UNDECIDED, never as NO)")

    yes = {k for k, v in verdicts.items() if v is True}
    hits_per_task: collections.Counter = collections.Counter(tid for _m, tid in yes)
    disc = {tid for tid, k in hits_per_task.items() if 1 <= k <= MAX_POOL_HITS}
    fires = sorted([(m, tid) for (m, tid) in yes if tid in disc])
    log(f"judge YES on {len(yes)} cells; {len(disc)} tasks discriminative "
        f"(1..{MAX_POOL_HITS}); GF-LLM-BEARING = {len(fires)} cells")

    # ---- overlap with GOLD and with GF-LEX ----
    gold: dict[str, set[str]] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if line.strip():
            d = json.loads(line)
            gold[d["task_id"]].add(d["memory_id"])
    gold_disc = {tid for tid in tasks if 1 <= len(gold.get(tid, ())) <= MAX_POOL_HITS}
    GOLD = {(m, tid) for tid in gold_disc for m in gold[tid]}
    LEX = {(r["memory_unit_locator"], r["task_id"]) for r in
           (json.loads(l) for l in
            (REPO / "data/manifests/gf_lex_bearing.jsonl").read_text().splitlines()
            if l.strip())}
    F = set(fires)
    universe = sum(len(by_dom[t.domain]) for t in tasks.values())

    def mat(a, b, na, nb):
        return {"both": len(a & b), f"{na}_only": len(a - b),
                f"{nb}_only": len(b - a), f"n_{na}": len(a), f"n_{nb}": len(b),
                f"frac_of_{nb}_also_{na}": (len(a & b) / len(b)) if b else None,
                f"frac_of_{na}_also_{nb}": (len(a & b) / len(a)) if a else None}

    ov_gold = mat(F, GOLD, "llm", "gold")
    ov_lex = mat(F, LEX, "llm", "lex")
    log(f"[overlap vs GOLD] {ov_gold}")
    log(f"[overlap vs GF-LEX] {ov_lex}")

    args.fires_out.parent.mkdir(parents=True, exist_ok=True)
    with args.fires_out.open("w") as fh:
        for m, tid in fires:
            fh.write(json.dumps({
                "memory_unit_locator": m, "task_id": tid,
                "domain": units[m]["domain"],
                "question_type": tasks[tid].question_type,
                "trajectory_id": units[m]["trajectory_id"],
                "memory_tokens": units[m]["n_tokens"],
                "task_pool_hits_llm": hits_per_task[tid],
                "task_pool_size": len(by_dom[units[m]["domain"]]),
                "also_gold_bearing": (m, tid) in GOLD,
                "also_gf_lex_bearing": (m, tid) in LEX,
            }, sort_keys=True) + "\n")
    log(f"[wrote] {args.fires_out} ({len(fires)} rows)")

    write_json_atomic(args.out, {
        "_what": "GF5 GF-LLM secondary gold-free screen. NO gold answer in any "
                 "prompt; proven per-prompt by assert_prompt_is_gold_free.",
        "_precommitment": "docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md §3",
        "_why_needed": "95% of GF-LEX firings rest on a SINGLE anchor term, and "
                       "the most productive anchors are generic words that are "
                       "merely rare in the pool (five, two, typically, whenever). "
                       "A null from GF-LEX alone could not separate 'gold-free "
                       "bearing has no effect' from 'this detector does not "
                       "identify bearing'.",
        "judge": {"cluster": JUDGE_CLUSTER, "model": JUDGE_MODEL,
                  "prompt_version": PROMPT_VERSION, "temperature": 0.0,
                  "reasoning_effort": "low", "max_tokens": 256,
                  "system_prompt": SYSTEM, "template": TEMPLATE},
        "judge_control": ctrl,
        "recall_stage": {"fraction_of_anchors_required": RECALL_FRACTION,
                         "size_cap_tokens": SIZE_CAP_TOKENS,
                         "n_candidates": len(cands),
                         "n_excluded_by_size_cap": n_over_cap,
                         "_exactness": "recall is EXHAUSTIVE over the pool and the "
                                       "LLM stage can only shrink it, so the "
                                       "composite's full-pool firing set is exact "
                                       "and the 1<=k<=8 constraint is enforced in "
                                       "the same shape, not approximated"},
        "judging": {"n_errors": n_err, "n_unparseable": n_unparse,
                    "_undecided_policy": "an error or an unparseable verdict is "
                                         "UNDECIDED, never a NO"},
        "yield": {"n_judge_yes": len(yes), "n_discriminative_tasks": len(disc),
                  "n_bearing_cells": len(fires),
                  "n_memories": len({m for m, _ in fires}),
                  "n_universe_cells": universe},
        "n_tasks_whose_question_contains_its_own_gold": {
            "n": n_self, "of": len(tasks),
            "_what": "a property of LongMemEval-V2's questions, not of either "
                     "screen: true/false items and items whose answer is a word "
                     "in the prompt. The question is a LEGITIMATE input to a "
                     "gold-free screen -- a deployable retriever reads it too -- "
                     "so this is disclosed, not corrected.",
            "_history": "the first version of assert_prompt_is_gold_free tested "
                        "for the gold SUBSTRING and aborted the run on task "
                        "ca8e070b ('...true or false?' / gold 'false'). The check "
                        "was testing the wrong proposition and was replaced by a "
                        "byte-exact template reconstruction."},
        "overlap_vs_gold": ov_gold,
        "overlap_vs_gf_lex": ov_lex,
        "fires_artifact": str(args.fires_out.relative_to(REPO)),
        "wall_clock_s": round(time.time() - t0, 1),
    })
    log(f"[wrote] {args.out} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

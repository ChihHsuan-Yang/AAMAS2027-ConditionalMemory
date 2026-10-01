#!/usr/bin/env python3
"""Convert the SciCode scale-up into p1mem schema v3 rows (one row per CELL).

    /Users/bellayang/miniconda3/bin/python3 scripts/scicode_to_schema.py \
        --src results/scicode/scaleup_all3.json \
        --analysis results/ledgers/repro/scicode/scaleup_analysis.json \
        --out results/ledgers/scicode/cells_v3.jsonl \
        --acknowledge-unexportable

``scripts/migrate_schema_v2.py`` is the house pattern and this file follows it: it
**derives; it never invents.** A value is written only when it is computed from the
artifact, recomputed from the adapter the run actually used, or joined on a key whose
join rate is verified. Everything else is an explicit ``None`` with a stated reason in
the paired ``*_notes``/``*_absent_reason`` field, because an unexplained null cannot be
told apart from a forgotten one.

WHAT A ROW IS
-------------
One row = one **cell** = (memory, future task, representation), with the WITH and
WITHOUT arms paired INTO that row. The artifact stores one record per ARM-RUN (924 of
them); this script pairs them into 462 cells. Pairing in the row rather than across
rows is design requirement 1 of ``schema.py``: a WITH score can then never drift away
from the WITHOUT score it is differenced against.

JOIN KEYS -- the two traps this repo has already paid for
---------------------------------------------------------
* The artifact's ``memory_id`` field (``scicode_dev::10.1``) is NOT the schema's
  ``memory_id``. The schema's is a CONTENT HASH (``compute_memory_id``) and so differs
  across representations by design. The artifact's value is the
  **``memory_unit_locator``**. It is joined on, and carried in
  ``provenance.memory_unit_locator``; the schema ``memory_id`` is minted, never joined.
* ``condition_id`` EMBEDS the representation name
  (``scicode_raw_metis_gptoss120b_scaleup_v1``). Putting it in a cross-representation
  join key returns ZERO rows and reads as "no data". ``--self-test`` proves both of
  these with a positive control rather than asserting them in a comment.

THREE THINGS THIS SCRIPT REFUSES TO DO
--------------------------------------
1. **It will not invent model output text.** ``scripts/scicode_pilot.py`` keeps
   ``response_chars`` and discards ``content``, and no ``ResponseCache`` was passed
   (``P1Client(...)`` at scicode_pilot.py:117 takes no ``cache=``). Measured, with a
   positive control: over all 12 ``results/**/*cache*.jsonl`` files, 12,023 entries key
   ``benchmark='longmemeval_v2'`` and **0 key ``'scicode'``**. (A first pass grepped for
   the string ``scicode`` and got 0 -- but it also got 0 for ``lmev2``, because the
   caches spell it ``longmemeval_v2``. An empty result from a bad key is not an
   absence.) So the completions are gone. The rows carry
   ``schema.OUTPUT_NOT_RETAINED_SENTINEL``, which the validator admits ONLY against a
   measured ``provenance.response_chars_<arm> > 0`` -- the evidence that a real answer
   existed and was scored. It is NOT ``WITHHELD_SENTINEL``: SciCode is Apache-2.0 and
   nothing here is withheld for licence. A persistence gap and a licence embargo must
   never be spelled the same way.
2. **It will not emit a summary or structured row.** All 68 writer calls succeeded, but
   nothing persisted their text and ``memory_text`` is non-nullable. Re-running the
   writers produces different bytes, so a re-derived text would be a different memory
   wearing this run's rewards. 308 of 462 cells are therefore unexportable, and the
   script EXITS NONZERO unless ``--acknowledge-unexportable`` says so out loud -- a
   partial export that looks complete is the defect, not the missing rows.
3. **It will not coerce a null reward to 0.0.** 106 arm-runs have ``reward=None``
   ("could not be scored"); 0.0 means "ran and got the wrong answer". Collapsing them
   manufactures harm, has shipped in this project twice, and is checked after the fact
   by ``_assert_no_coerced_rewards`` against the artifact's own ``kind`` column.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from p1mem import schema as S                                   # noqa: E402
from p1mem import validate as V                                 # noqa: E402
from p1mem.adapters import scicode as SC                        # noqa: E402
from p1mem.memory import semantic_type as ST                    # noqa: E402
from p1mem.memory import tokens as T                            # noqa: E402
from p1mem.memory.representations import RawExtractiveWriter    # noqa: E402

DEFAULT_DEV = "/tmp/scicode_probe/problems_dev.jsonl"
DEFAULT_TEST = "/tmp/scicode_probe/problems_test.jsonl"

#: The run's own parameters, read off ``config`` at convert time and cross-checked
#: against these. They are NOT defaults to fall back on: a mismatch raises, because a
#: converter that silently accepts a differently-configured artifact would stamp this
#: run's identity onto someone else's data.
EXPECTED_CONFIG: dict[str, Any] = {
    "cluster": "metis", "model": "gpt-oss-120b", "reasoning_effort": "low",
    "temperature": 0.0, "reader_max_tokens": 1024, "seed": 20261008,
    "filler_k": 2, "relatedness": "lexical",
    "prompt_version": SC.PROMPT_VERSION,
    "benchmark_version": SC.BENCHMARK_VERSION,
}

RUN_ID = "scicode_scaleup_all3"
CONDITION_ID_FMT = "scicode_{rep}_metis_gptoss120b_scaleup_v1"
READER_ARM = "gptoss_metis"

#: SciCode's recipient is always a problem's FIRST substep -- a STRUCTURAL fact, not a
#: label we chose: ``build_future_tasks`` takes ``sub_steps[0]`` and nothing else,
#: because a later substep's tests call functions the test split ships no code for.
#: Verified on the 40 tasks actually used: all 40 end in ``.1``.
FUTURE_TASK_FAMILY = "scicode_subproblem_step1"

VERIFIER_ID = "scicode_unit_tests"
VERIFIER_VERSION = f"scicode_harness@{SC.HARNESS_COMMIT[:8]}"

#: SciCode is Apache-2.0 on BOTH code and data -- docs/BENCHMARK_LICENSES.md section 4,
#: and ``export_hf.LICENSE_POLICIES['scicode']`` is ``(True, True)`` to match. The
#: section-4 carve-out (``test_data.h5``'s numeric targets) is satisfied structurally
#: here: only pass/fail verdicts from those targets ever reach a row, never a target
#: value. ``export_hf.gate_scicode_eval_targets`` enforces that independently.
LICENSE_REF = "scicode:Apache-2.0"

#: NO VECTOR WAS EVER COMPUTED for SciCode. Pairing used ``lexical_similarity`` --
#: idf-weighted cosine over content-word SETS. ``embedding_model`` / ``embedding_version``
#: are non-nullable, so they carry a sentinel that says which, rather than naming an
#: embedding model this benchmark never touched.
NO_EMBEDDING = "none:not_embedded"
NO_EMBEDDING_REASON = (
    "NOT EMBEDDED. SciCode pairing used p1mem.adapters.scicode.lexical_similarity -- "
    "an idf-weighted cosine over content-WORD SETS -- so no dense vector was ever "
    "computed, stored or hashed for this benchmark. This is an absence of the "
    "measurement, not a lost artifact: there is no .npy to point at. "
    "semantic_similarity on this row is that lexical cosine, NOT an embedding cosine, "
    "and must not be pooled with the LongMemEval rows' SFR-Embedding-Mistral values."
)

#: ``memory_text`` cannot be a tautological faithfulness subject on raw -- and on
#: summary/structured the text is GONE, which is a THIRD reason distinct from both "raw
#: is its own source" and "the write did not complete". ``validate.py`` fires
#: ``faithfulness_claimed_unscored_on_a_written_memory`` on a note that says "NOT
#: SCORED" without "did not complete", so a reused constant would be both wrong and
#: loud. No summary/structured row is emitted today; the constant exists so that when
#: the re-run lands, the true reason has somewhere to go that is not a reused lie.
FAITHFULNESS_TEXT_NOT_PERSISTED_NOTE = (
    "NOT SCORED, and the reason is neither tautology nor a failed write: the write "
    "SUCCEEDED and the memory text was never persisted. scripts/scicode_pilot.py holds "
    "the written memories in process memory only -- there is no results/scicode/"
    "memories.jsonl and no write cache -- so the exact bytes that were scored against "
    "are unrecoverable. Re-running the writer would produce DIFFERENT bytes and "
    "scoring those would describe a different memory than the one this row's rewards "
    "were measured under."
)

# ---------------------------------------------------------------- error-code mapping
#
# 🔴 WRITTEN DOWN, NOT IMPROVISED. SciCode's ``kind`` vocabulary and
# ``schema.ERROR_CODES`` are two different taxonomies and they intersect at exactly one
# string (``timeout``). The distinction that decides the mapping:
#
#   * ``error_code_if_any`` is an OPERATIONAL failure -- the call did not yield a usable
#     response. ``validate.py`` then forbids the row from carrying ANY reward, because
#     an errored cell has no outcome.
#   * ``syntax_error`` / ``runtime_error`` / ``function_not_defined`` / ``no_code_block``
#     are SCORING outcomes. The endpoint returned a complete answer; the answer could
#     not be executed. That is precisely what ``reward=None`` ("could not be scored")
#     already says, and it is a fact about the MODEL, not about the plumbing. Stamping
#     an operational error code on them would (a) assert an endpoint failure that did
#     not happen and (b) make the surviving arm's real reward illegal to carry.
#
# So the unscorable kinds map to None and the SciCode kind is preserved verbatim in
# ``provenance.scicode_kind_<arm>`` where it is not mistaken for an endpoint error.
SCICODE_KIND_TO_ERROR_CODE: dict[str, str | None] = {
    SC.SCORE_OK: None,                 # scored 1.0
    SC.SCORE_WRONG: None,              # scored 0.0 -- a real wrong answer
    SC.ERR_SYNTAX: None,               # scoring outcome -> reward None
    SC.ERR_RUNTIME: None,              # scoring outcome -> reward None
    SC.ERR_NO_FUNCTION: None,          # scoring outcome -> reward None
    SC.ERR_NO_CODE: None,              # scoring outcome -> reward None
    SC.ERR_TIMEOUT: "timeout",         # the one genuine intersection
    SC.ERR_HARNESS: None,              # see _error_code_for_arm: refuses rather than guess
    "memory_write_failed": None,       # see _error_code_for_arm
    "reader_call_failed": None,        # resolved from ``detail``, see below
}

#: ``reader_call_failed`` is the only kind that IS operational, and which operational
#: error it is depends on the exception the client raised. Resolved from the recorded
#: ``detail`` string rather than assumed: the one occurrence in this artifact is a
#: ``TruncatedResponseError`` (``reasoning_tokens=1022, completion_tokens=1024``, empty
#: content), which is exactly ``ERROR_EMPTY_OUTPUT_FINISH_LENGTH``. A different
#: exception would map elsewhere, so an unrecognised detail REFUSES.
READER_CALL_FAILED_DETAIL_MAP: tuple[tuple[str, str], ...] = (
    ("TruncatedResponseError", S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH),
)


class ConversionRefused(SystemExit):
    """Raised where a plausible value would have to be invented to continue."""


# ====================================================================== helpers
def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _git_sha_for(path: Path) -> str | None:
    """The commit that last touched ``path``. Measured, or None -- never guessed."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)
    except Exception:                                            # noqa: BLE001
        return None
    sha = out.stdout.strip()
    return sha or None


def _error_code_for_arm(rec: dict[str, Any]) -> str | None:
    """OPERATIONAL error code for one arm-run, or None. Refuses on an unknown kind."""
    kind = rec.get("kind")
    if kind == "reader_call_failed":
        detail = rec.get("detail") or ""
        for needle, code in READER_CALL_FAILED_DETAIL_MAP:
            if needle in detail:
                return code
        raise ConversionRefused(
            f"REFUSING TO WRITE: a reader_call_failed arm carries a detail this script "
            f"has no mapping for: {detail[:160]!r}. Which schema ERROR_CODE it is "
            f"depends on the exception, and guessing one would assert a failure mode "
            f"nobody observed. Add it to READER_CALL_FAILED_DETAIL_MAP.")
    if kind == SC.ERR_HARNESS:
        raise ConversionRefused(
            "REFUSING TO WRITE: a 'harness_error' arm-run is present. It is an "
            "OUR-SIDE operational failure with no counterpart in schema.ERROR_CODES, "
            "and it did not occur in the artifact this script was written against "
            "(0 of 924). Decide its code deliberately rather than letting it fall "
            "through to None, which would read as a clean scoring outcome.")
    if kind not in SCICODE_KIND_TO_ERROR_CODE:
        raise ConversionRefused(
            f"REFUSING TO WRITE: unknown SciCode kind {kind!r}. The kind->error_code "
            f"mapping is written down on purpose; an unmapped kind must be ruled on, "
            f"not defaulted.")
    return SCICODE_KIND_TO_ERROR_CODE[kind]


def _assert_no_coerced_rewards(arm_rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Prove, from the artifact's own ``kind`` column, that no None became 0.0.

    The defect this guards is invisible in the output: a reward of 0.0 on an unscorable
    arm is a perfectly well-formed float, and ``delta_utility`` recomputed from it is
    internally consistent, so the SHIPPED VALIDATOR CANNOT SEE IT. The only witness is
    the independent ``kind`` column, which says whether the solution ran at all.
    """
    unscorable = {SC.ERR_SYNTAX, SC.ERR_RUNTIME, SC.ERR_NO_FUNCTION, SC.ERR_NO_CODE,
                  SC.ERR_TIMEOUT, SC.ERR_HARNESS, "reader_call_failed",
                  "memory_write_failed"}
    bad = [r for r in arm_rows
           if r.get("kind") in unscorable and r.get("reward") is not None]
    if bad:
        raise ConversionRefused(
            f"REFUSING TO WRITE: {len(bad)} arm-runs carry a REWARD on a kind that "
            f"could not be scored (e.g. {bad[0].get('kind')!r} with "
            f"reward={bad[0].get('reward')!r}). reward=None means 'could not be "
            f"scored' and 0.0 means 'ran and was wrong'; collapsing them manufactures "
            f"harm. This has shipped in this project twice.")
    scored = [r for r in arm_rows if r.get("kind") in (SC.SCORE_OK, SC.SCORE_WRONG)
              and r.get("reward") is None]
    if scored:
        raise ConversionRefused(
            f"REFUSING TO WRITE: {len(scored)} arm-runs were SCORED "
            f"(kind in pass/wrong_answer) but carry reward=None. The two columns "
            f"disagree about whether a score exists.")
    return {"unscorable_with_null_reward": sum(1 for r in arm_rows
                                               if r.get("kind") in unscorable),
            "scored": sum(1 for r in arm_rows
                          if r.get("kind") in (SC.SCORE_OK, SC.SCORE_WRONG))}


def build_filler_ids(memories: Sequence[Any], target: str, k: int,
                     seed: int) -> list[str]:
    """The filler locators for one cell. A VERBATIM COPY of the rule the run used.

    Copied from ``scripts/scicode_pilot.py::build_filler`` deliberately rather than
    imported, because that function returns the joined TEXT and this needs the ids --
    and because a copied body is not a copied decision ("three functions, one name").
    Reproducibility is checked, not assumed: ``--self-test`` re-derives the documented
    case ``scicode_dev::1.1 -> [19.1, 78.3]``.
    """
    pool = sorted((m for m in memories if m.memory_unit_locator != target),
                  key=lambda m: m.memory_unit_locator)
    rng = random.Random(f"{seed}:filler:{target}")
    picked = rng.sample(pool, min(k, len(pool))) if pool else []
    return [m.memory_unit_locator for m in
            sorted(picked, key=lambda m: m.memory_unit_locator)]


def tercile_bands(values: Sequence[float]) -> tuple[float, float]:
    """The house tercile rule, verbatim from ``scripts/k2_run_screened.py:364``.

    Terciles are taken over THIS artifact's OWN similarity distribution (one value per
    cell), never over another arm's: the LongMemEval cut points are embedding cosines
    on a different scale and importing them would band these rows against a ruler that
    never measured them.
    """
    vals = sorted(values)
    return vals[len(vals) // 3], vals[2 * len(vals) // 3]


# =============================================================== the conversion
def convert(
    src: dict[str, Any],
    *,
    dev_path: Path,
    test_path: Path,
    representations: Sequence[str] = ("raw",),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (schema-v3 rows, stats). Pure with respect to its inputs."""
    cfg = src["config"]
    for k, want in EXPECTED_CONFIG.items():
        got = cfg.get(k)
        if got != want:
            raise ConversionRefused(
                f"REFUSING TO WRITE: artifact config[{k!r}]={got!r} but this converter "
                f"stamps {want!r} onto every row. A converter that accepts a "
                f"differently-configured artifact writes one run's identity onto "
                f"another run's data.")

    arm_rows: list[dict[str, Any]] = src["rows"]
    reward_stats = _assert_no_coerced_rewards(arm_rows)

    # ---- pair the ARM-RUNS into CELLS. The artifact's memory_id is the LOCATOR.
    cells: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = (
        collections.defaultdict(dict))
    for r in arm_rows:
        key = (r["memory_id"], r["task_id"], r["representation"])
        arm = r["arm"]
        if arm in cells[key]:
            raise ConversionRefused(
                f"REFUSING TO WRITE: cell {key} has two {arm!r} arm-runs. Pairing "
                f"would silently keep one and drop the other.")
        cells[key][arm] = r
    incomplete = {k: sorted(v) for k, v in cells.items() if set(v) != {"with", "without"}}
    if incomplete:
        raise ConversionRefused(
            f"REFUSING TO WRITE: {len(incomplete)} cells do not have exactly two arms "
            f"(e.g. {list(incomplete.items())[:2]}). A cell IS the paired contrast; "
            f"half of one is not a row.")

    # ---- rebuild the units the run used, and VERIFY the join rather than assume it.
    memories = SC.build_memory_units(SC.load_jsonl(dev_path))
    tasks = SC.build_future_tasks(SC.load_jsonl(test_path))
    SC.assert_writer_blind(memories, tasks)
    by_loc = {m.memory_unit_locator: m for m in memories}
    by_task = {t.task_id: t for t in tasks}

    need_loc = sorted({k[0] for k in cells})
    need_task = sorted({k[1] for k in cells})
    miss_loc = [x for x in need_loc if x not in by_loc]
    miss_task = [x for x in need_task if x not in by_task]
    if miss_loc or miss_task:
        raise ConversionRefused(
            f"REFUSING TO WRITE: {len(miss_loc)} memory locators and "
            f"{len(miss_task)} task ids in the artifact do not resolve against "
            f"{dev_path} / {test_path} (e.g. {(miss_loc + miss_task)[:3]}). A partial "
            f"join still looks like success.")

    # ---- the design is REPRODUCED from the seed, not read back from the artifact.
    #      If the adapter and the artifact disagree, the stored similarity, the pools
    #      and the filler are all suspect, so this refuses rather than preferring one.
    selected = SC.select_pairs(
        memories, tasks, seed=cfg["seed"], tasks_per_memory=99,
        relatedness=SC.Relatedness(cfg["relatedness"]), min_tasks_per_memory=2)
    sel_keys = {(p.memory_unit_locator, p.task_id) for p in selected}
    art_keys = {(k[0], k[1]) for k in cells}
    if sel_keys != art_keys:
        raise ConversionRefused(
            f"REFUSING TO WRITE: re-running select_pairs(seed={cfg['seed']}) gives "
            f"{len(sel_keys)} pairs but the artifact has {len(art_keys)}; symmetric "
            f"difference {len(sel_keys ^ art_keys)}. The run is not reproducible from "
            f"the recorded seed, so no derived field can be trusted.")
    sim_by_pair = {(p.memory_unit_locator, p.task_id): p.similarity for p in selected}
    pair_by_key = {(p.memory_unit_locator, p.task_id): p for p in selected}
    for (loc, tid), stored in sorted(
            {(k[0], k[1]): c["with"]["similarity"] for k, c in cells.items()}.items()):
        if abs(sim_by_pair[(loc, tid)] - stored) > 1e-9:
            raise ConversionRefused(
                f"REFUSING TO WRITE: recomputed similarity for ({loc}, {tid}) is "
                f"{sim_by_pair[(loc, tid)]!r} but the artifact stored {stored!r}.")

    # ---- candidate pool: the denominator that makes 'discriminative' mean anything.
    #      hits  = tasks passing the LEXICAL screen for this memory
    #      size  = every cross-problem task it was screened AGAINST
    lex = SC.candidate_pairs(memories, tasks, relatedness=SC.Relatedness.LEXICAL)
    allp = SC.candidate_pairs(memories, tasks, relatedness=SC.Relatedness.ALL)
    pool_hits = collections.Counter(p.memory_unit_locator for p in lex)
    pool_size = collections.Counter(p.memory_unit_locator for p in allp)

    # ---- bands over THIS artifact's own distribution, one value per (memory,task).
    t1, t2 = tercile_bands(sorted(sim_by_pair.values()))

    def band(s: float) -> str:
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    raw_writer = RawExtractiveWriter()
    code_sha = _git_sha_for(REPO_ROOT / "scripts/scicode_pilot.py")
    adapter_sha = _git_sha_for(REPO_ROOT / "src/p1mem/adapters/scicode.py")
    now = S.utc_now()
    reader = S.reader_row_fields(READER_ARM)

    stats: dict[str, Any] = {
        "cells_in_artifact": len(cells),
        "rows_emitted": 0,
        "skipped_unexportable": collections.Counter(),
        "rewards": reward_stats,
        "error_codes": collections.Counter(),
        "semantic_types": collections.Counter(),
        "bands": collections.Counter(),
        "arms_with_null_reward": 0,
        "cells_with_null_delta": 0,
        "leakage_flag_true": 0,
        "similarity_terciles": {"FAR_lt": t1, "MID_lt": t2},
        "tokenizer": T.tokenizer_provenance(),
    }

    out: list[dict[str, Any]] = []
    for (loc, tid, rep) in sorted(cells):
        if rep not in representations:
            # 🔴 NOT A FILTER OF CONVENIENCE. memory_text is non-nullable and the
            #    summary/structured bytes were never persisted (see the module
            #    docstring, refusal 2). A row without them cannot exist; a row with
            #    re-derived ones would be a different memory wearing these rewards.
            stats["skipped_unexportable"][rep] += 1
            continue

        c = cells[(loc, tid, rep)]
        w, wo = c["with"], c["without"]
        mem, task = by_loc[loc], by_task[tid]
        seg = SC.to_source_segment(mem)
        mrec = raw_writer.write(seg)

        if mrec.memory_text != mem.episode_text:
            raise ConversionRefused(
                f"REFUSING TO WRITE: the raw writer's output for {loc} is not the "
                f"episode text it is defined to be. Protocol §1A says raw IS the "
                f"segment; a difference means the span rule changed under this run.")

        err_with = _error_code_for_arm(w)
        err_without = _error_code_for_arm(wo)
        # ONE field for a two-armed row. If both arms errored differently we would be
        # asked to pick, and picking hides one. Neither occurs here (the single
        # operational error is unaccompanied), so a collision refuses rather than
        # silently resolving.
        codes = [x for x in (err_with, err_without) if x]
        if len(set(codes)) > 1:
            raise ConversionRefused(
                f"REFUSING TO WRITE: cell ({loc},{tid},{rep}) has two DIFFERENT "
                f"operational error codes ({err_with!r} / {err_without!r}) and the "
                f"schema has one field for them. Writing either would erase the "
                f"other.")
        error_code = codes[0] if codes else None

        rw, rwo = w.get("reward"), wo.get("reward")
        if error_code is not None and (rw is not None or rwo is not None):
            # validate.py forbids a reward on an errored row, and it is right to:
            # an errored cell has no outcome. The surviving arm's measurement is not
            # thrown away -- it is kept verbatim in provenance, where it is clearly a
            # per-arm fact rather than the cell's result.
            rw, rwo = None, None

        delta = S.compute_delta_utility(rw, rwo)
        if rw is None or rwo is None:
            stats["cells_with_null_delta"] += 1
        stats["arms_with_null_reward"] += sum(
            1 for x in (w.get("reward"), wo.get("reward")) if x is None)
        if error_code:
            stats["error_codes"][error_code] += 1

        sim = sim_by_pair[(loc, tid)]
        bnd = band(sim)
        stats["bands"][bnd] += 1
        sem = ST.heuristic_semantic_type(seg)
        stats["semantic_types"][sem.semantic_type] += 1
        leak = SC.detect_leak(mem, task)
        stats["leakage_flag_true"] += int(leak.any_leak)
        pair = pair_by_key[(loc, tid)]
        filler_ids = build_filler_ids(memories, loc, cfg["filler_k"], cfg["seed"])
        hits, size = pool_hits[loc], pool_size[loc]

        # -- cost. Summed over BOTH arms, which is what the schema's descriptions say
        #    ("BOTH arms summed" / "billed across both arms"). Null when either arm is
        #    missing the measurement: a one-arm sum is a different quantity wearing the
        #    same name, and these fields are NON-NULLABLE, so a cell that cannot
        #    produce them cannot be a row at all -- that refusal is below, not a 0.0.
        def _pair_sum(field: str) -> float | int | None:
            a, b = _num(w.get(field)), _num(wo.get(field))
            return None if a is None or b is None else a + b

        gen_lat = _pair_sum("latency_s")
        in_tok = _pair_sum("prompt_tokens")
        out_tok = _pair_sum("completion_tokens")
        if gen_lat is None or in_tok is None or out_tok is None:
            # The one cell where this bites (summary / 70.6 x 22.1) is not emitted
            # today anyway, but the refusal must not depend on that coincidence.
            raise ConversionRefused(
                f"REFUSING TO WRITE: cell ({loc},{tid},{rep}) is missing a per-arm "
                f"cost measurement (latency/prompt_tokens/completion_tokens), and "
                f"generation_latency / input_tokens / output_tokens are NON-NULLABLE. "
                f"A one-arm sum is not the two-arm quantity the field names, and 0.0 "
                f"would be an absence written as a measurement.")

        row = S.blank_row()
        row.update(
            # ---------------------------------------------------------- structural
            schema_version=S.SCHEMA_VERSION,
            condition_id=CONDITION_ID_FMT.format(rep=rep),
            created_at_utc=now,
            # ---------------------------------------------------------- benchmark
            benchmark=SC.BENCHMARK,
            benchmark_version=SC.BENCHMARK_VERSION,
            source_episode_id=mem.source_episode_id,
            source_episode_metadata=dict(seg.episode_metadata),
            # ---------------------------------------------------------- memory
            memory_representation=rep,
            # MEASURED per memory by the keyword rule, never hardcoded. The adapter
            # calls SciCode "procedural" as a BENCHMARK ROLE; stamping that per row
            # would publish a value nobody classified. Measured over the 34:
            # episodic 17, semantic_fact 13, failure_reflection 2, procedural 2.
            memory_semantic_type=sem.semantic_type,
            memory_text=mrec.memory_text,
            memory_tokens=mrec.memory_tokens,
            memory_source_span=dict(mrec.source_span),
            memory_writer_model=mrec.writer_model,
            memory_writer_cluster=mrec.writer_cluster,
            memory_writer_prompt_version=mrec.prompt_version,
            # No call was made, so there is no duration and no token count. None,
            # never 0.0 -- validate.py has a named check for the 0.0.
            memory_extraction_latency=None,
            memory_extraction_input_tokens=None,
            memory_extraction_output_tokens=None,
            # ---------------------------------------------------------- embedding
            embedding_model=NO_EMBEDDING,
            embedding_version=NO_EMBEDDING,
            memory_embedding_reference={
                "store": None, "index": None, "dim": None, "sha256": None,
                "absent_reason": NO_EMBEDDING_REASON},
            # ---------------------------------------------------------- task
            future_task_id=task.task_id,
            future_task_family=FUTURE_TASK_FAMILY,
            # The RENDERED reader prompt with no memory and no filler -- i.e. exactly
            # the task as posed, which is what "as presented to the reader" means. The
            # arms' real prompts differ only by the memory block and the (identical)
            # filler, both of which are recorded separately in provenance, so this text
            # plus those ids reconstructs either arm's prompt byte-for-byte.
            future_task_text=SC.render_task_prompt(task, None, filler=""),
            task_embedding_reference={
                "store": None, "index": None, "dim": None, "sha256": None,
                "absent_reason": NO_EMBEDDING_REASON},
            semantic_similarity=sim,
            semantic_distance_band=bnd,
            # ---------------------------------------------------------- retrieval
            retrieval_method="oracle",     # the pair is chosen, never retrieved
            retrieval_rank=None,           # oracle does not rank
            retrieval_k=None,              # there is no k
            memory_tokens_retrieved=mrec.memory_tokens,
            memory_tokens_exposed=mrec.memory_tokens,   # no truncation was applied
            # ---------------------------------------------------------- execution
            replicate_id=0,
            seed_or_sampling_config={
                "seed": cfg["seed"], "temperature": cfg["temperature"],
                "max_tokens": cfg["reader_max_tokens"],
                "reasoning_effort": cfg["reasoning_effort"]},
            reader_prompt_version=SC.PROMPT_VERSION,
            **reader,
            # ---------------------------------------------------------- outcome
            # The completions were DISCARDED by the run. The sentinel says so, and
            # validate.py admits it only against the measured response_chars in
            # provenance below. It is NOT the licence-withholding sentinel.
            output_with_memory=S.OUTPUT_NOT_RETAINED_SENTINEL,
            output_without_memory=S.OUTPUT_NOT_RETAINED_SENTINEL,
            reward_with_memory=rw,
            reward_without_memory=rwo,
            delta_utility=delta,
            # F (the noise floor, P1-051) is unmeasured, so the pre-registered rule
            # returns 'undetermined'. That is the correct answer, not a gap.
            utility_label="undetermined",
            robustness_confidence=None,          # needs F
            # ---------------------------------------------------------- cost
            write_latency=None,                  # raw made no write call
            retrieval_latency=None,              # no retrieval step exists to time
            generation_latency=gen_lat,
            end_to_end_latency=gen_lat,          # no other stage is timed per cell
            embedding_calls=0,                   # a MEASURED zero: none were made
            generation_calls=2,
            input_tokens=int(in_tok),
            output_tokens=int(out_tok),
            # Metis DOES report reasoning tokens for gpt-oss-120b, and
            # scripts/scicode_pilot.py never recorded rec.reasoning_tokens. Null is
            # the honest value (0 would be an absence written as a measurement, which
            # validate.py rejects on non-reporting readers); the resulting
            # reasoning_tokens_missing WARNING is real and is left to fire.
            reasoning_tokens=None,
            retry_count=0,
            error_code_if_any=error_code,
            # ---------------------------------------------------------- provenance
            provenance={
                "code_sha": code_sha,
                "adapter_sha": adapter_sha,
                "config_sha256": None,
                "config_sha256_absent_reason":
                    "NOT RECORDED BY THE RUN. scripts/scicode_pilot.py hard-codes its "
                    "parameters as module constants and reads no config file, so no "
                    "hash of one was measured; stamping configs/endpoint_primary.json's "
                    "current hash would assert a provenance the run never took. The "
                    "parameters themselves are fully on the row (reader_model, "
                    "reader_cluster, reader_reasoning_effort, seed_or_sampling_config, "
                    "reader_endpoint_sha256) and were cross-checked against the "
                    "artifact's own config block before any row was written.",
                "run_id": RUN_ID,
                "host": "laptop",
                "writer": "scripts/scicode_pilot.py",
                "converter": "scripts/scicode_to_schema.py",
                # THE join key. The artifact's "memory_id" field is this, not the
                # schema's content-hash memory_id.
                "memory_unit_locator": loc,
                "donor_problem_id": pair.donor_problem_id,
                "recipient_problem_id": pair.recipient_problem_id,
                "relatedness": pair.relatedness,
                "shared_imports": list(pair.shared_imports),
                "shared_terms": list(pair.shared_terms),
                # Filler was present in BOTH arms (protocol §4), so removing the memory
                # is a local change. Reproducible from seed + locator.
                "filler_k": cfg["filler_k"],
                "filler_memory_ids": filler_ids,
                "filler_tokens": sum(
                    T.count_tokens(by_loc[f].episode_text) for f in filler_ids),
                # EVIDENCE for OUTPUT_NOT_RETAINED_SENTINEL: validate.py admits the
                # sentinel only where a completion is PROVEN to have existed.
                "response_chars_with": w.get("response_chars"),
                "response_chars_without": wo.get("response_chars"),
                "output_text_absent_reason":
                    "NEVER PERSISTED. scripts/scicode_pilot.py's run_arm() records "
                    "len(content) and discards content, and P1Client was constructed "
                    "with no cache=, so no completion was stored anywhere. Verified: "
                    "across all 12 results/**/*cache*.jsonl files, 12,023 entries key "
                    "benchmark='longmemeval_v2' and 0 key 'scicode'. This is a "
                    "PERSISTENCE gap, not a licence one -- SciCode is Apache-2.0 and "
                    "nothing on this row is withheld.",
                # The benchmark's own outcome vocabulary, kept per arm so a scoring
                # outcome is never confused with an endpoint error.
                "scicode_kind_with": w.get("kind"),
                "scicode_kind_without": wo.get("kind"),
                "finish_reason_with": w.get("finish_reason"),
                "finish_reason_without": wo.get("finish_reason"),
                # Per-arm rewards AS MEASURED. On an errored cell the schema fields
                # above are nulled (validate.py forbids a reward beside an error code),
                # so this is where the surviving arm's real measurement is kept rather
                # than discarded.
                "reward_with_as_measured": w.get("reward"),
                "reward_without_as_measured": wo.get("reward"),
                "latency_s_with": w.get("latency_s"),
                "latency_s_without": wo.get("latency_s"),
                "source_artifact": "results/scicode/scaleup_all3.json",
                "source_artifact_sha256": src.get("_source_sha256"),
            },
            license_source_reference=LICENSE_REF,
            # ---------------------------------------------------------- verifier
            verifier_id=VERIFIER_ID,
            verifier_version=VERIFIER_VERSION,
            reward_is_continuous=False,    # score_solution returns exactly {0.0, 1.0}
            leakage_flag=bool(leak.any_leak),
            # ---------------------------------------------------------- label rule
            utility_label_threshold=None,       # F unmeasured (P1-051)
            delta_utility_ci_lower=None,        # one replicate -> no CI
            delta_utility_ci_upper=None,
            delta_utility_cell_mean=None,       # a "mean" over one row restates delta
            replicate_count=None,               # reserved for the CI-backing count
            utility_label_rule_version=S.UTILITY_LABEL_RULE_VERSION,
            # ---------------------------------------------------------- chronology
            # SciCode problems carry NO wall-clock field. Verified by an exhaustive key
            # scan of both splits: problem keys and substep keys contain nothing
            # temporal (the scan's regex was positive-controlled against
            # 'completion_timestamp' and 'created_at'). No true value exists.
            source_episode_completion_timestamp=None,
            # ---------------------------------------------------------- lineage
            # A raw memory's parent is the EPISODE, which is already source_episode_id;
            # writing it here would conflate two different relations. A summary's
            # parent WOULD be this raw row's memory_id -- when such rows exist.
            parent_memory_id=None,
            # ---------------------------------------------------------- quality
            compression_ratio=S.compute_compression_ratio(
                mrec.memory_tokens, mrec.source_tokens),
            source_span_tokens=mrec.source_tokens,
            extraction_cost_proxy=None,    # set below, from the row itself
            faithfulness_check=None,
            faithfulness_notes=S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE,
            faithfulness_detail=None,
            # ---------------------------------------------------------- bearing
            # 'unscreened' is a REAL value: SciCode was paired by the lexical screen,
            # never by the bearing screen. The evidence object is SciCode-NATIVE rather
            # than build_bearing_evidence()'s all-null shape, because every field in it
            # was actually measured here.
            bearing_label="unscreened",
            bearing_evidence={
                "detector_fires": None,
                "task_pool_hits": hits,
                "task_pool_size": size,
                "discriminativeness": (hits / size) if size else None,
                "n_bearing_tasks_for_this_memory": None,
                "why_stratum":
                    "NO BEARING SCREEN RAN on SciCode. The pair was drawn by the "
                    "LEXICAL relatedness screen -- idf-weighted cosine over content "
                    "words at or above LEXICAL_THRESHOLD=%.4f, a threshold fixed at "
                    "the p95 of the full 3,200-combination distribution BEFORE any "
                    "reward existed. task_pool_hits is how many cross-problem tasks "
                    "passed that screen for this memory; task_pool_size is how many it "
                    "was screened against. 'unscreened' names the BEARING screen's "
                    "absence and is a measurement, not a missing value."
                    % SC.LEXICAL_THRESHOLD,
                "screen_is_content_only": True,
                "lexical_threshold": SC.LEXICAL_THRESHOLD,
                "lexical_similarity": sim,
                "shared_imports": list(pair.shared_imports),
                "shared_terms": list(pair.shared_terms),
                "leakage_flag": bool(leak.any_leak),
                "leak_detail": {
                    "defines_answer": leak.defines_answer,
                    "mentions_answer_name": leak.mentions_answer_name,
                    "signature_verbatim": leak.signature_verbatim,
                    "generic_exact": leak.generic_exact,
                },
                "caveat": S.BEARING_SCREEN_CAVEAT,
            },
            candidate_pool_size=size,
            # ---------------------------------------------------------- retrieval aux
            # No context cap was ever enforced: exposed == retrieved on every cell and
            # scicode_pilot.py has no context-budget argument. Its 1024 is the OUTPUT
            # cap, a different quantity, and recording it here would state a control
            # the run did not have.
            context_budget=None,
            # ---------------------------------------------------------- replicates
            num_replicates=1,
            # One replicate cannot measure agreement with itself. Null, never 1.0 --
            # the same rule migrate_schema_v2.py applies (len(deltas) < 2 -> None).
            confidence_or_stability=None,
            storage_bytes=S.compute_storage_bytes(mrec.memory_text),
            # ---------------------------------------------------------- P3 / export
            propagation_metadata=None,
            # Null, not []: null means "no licence policy has been applied yet", an
            # empty list means "a policy ran and withheld nothing". export_hf.py writes
            # these; a local ledger is pre-export.
            license_policy=None,
            text_fields_withheld=None,
            reconstruction_required=None,
            receiver_id=None, receiver_role=None,
            visibility_mask=None, team_reward=None,
        )
        row["extraction_cost_proxy"] = S.compute_extraction_cost_proxy(row)
        coarse, fine = S.classify_memory_type(row)
        row["memory_type_coarse"] = coarse
        row["memory_type_fine"] = fine

        # Deterministic ids LAST, and in dependency order: memory -> cell -> row.
        row["memory_id"] = S.compute_memory_id(row)
        row["cell_id"] = S.compute_cell_id(row)
        row["row_id"] = S.compute_row_id(row)

        missing = [f for f in S.FIELD_ORDER if f not in row]
        extra = sorted(set(row) - set(S.FIELD_ORDER))
        if missing or extra:
            raise ConversionRefused(
                f"conversion produced a non-conforming row: missing={missing} "
                f"extra={extra}")
        out.append({f: row[f] for f in S.FIELD_ORDER})

    stats["rows_emitted"] = len(out)
    stats["skipped_unexportable"] = dict(stats["skipped_unexportable"])
    stats["error_codes"] = dict(stats["error_codes"])
    stats["semantic_types"] = dict(stats["semantic_types"])
    stats["bands"] = dict(stats["bands"])
    return out, stats


def cross_check_analysis(rows: Sequence[dict[str, Any]],
                         analysis: dict[str, Any]) -> list[str]:
    """Re-derive the analysis ledger's RAW numbers from the emitted rows.

    Anchoring to a figure the analysis already recorded, on the same cells, is what
    turns "my converter ran" into "my converter preserved the measurement". Only the
    quantities the emitted rows can actually support are checked: the matched-122
    statistics span all three representations and 308 of those cells are not emitted,
    so claiming to have reproduced them here would be a check aimed at nothing.
    """
    log: list[str] = []
    raws = [r for r in rows if r["memory_representation"] == "raw"]
    if not raws:
        return ["SKIP: no raw rows emitted, nothing to cross-check"]

    interp = [r for r in raws if r["delta_utility"] is not None]
    want = analysis.get("per_representation_interpretable", {}).get("raw")
    got = len(interp)
    if want is not None and want != got:
        raise ConversionRefused(
            f"REFUSING TO WRITE: the analysis ledger records {want} interpretable raw "
            f"cells; the emitted rows give {got}. One of the two is describing "
            f"different data.")
    log.append(f"PASS per_representation_interpretable.raw = {got} (ledger: {want})")

    mean = sum(r["delta_utility"] for r in interp) / len(interp)
    want_mean = (analysis.get("delta_u_matched", {}).get("raw", {}) or {}).get("mean")
    # The ledger's mean is over the MATCHED 122, not these 127, so it is reported
    # beside rather than asserted equal -- a different denominator is a different
    # quantity, and silently comparing them is the defect, not the difference.
    log.append(f"INFO mean dU over the {len(interp)} interpretable raw cells = "
               f"{mean:+.4f}; the ledger's {want_mean:+.4f} is over the MATCHED 122 "
               f"(a different, smaller cell set spanning all three representations), "
               f"so these are not expected to be equal and are NOT compared.")

    helped = sum(1 for r in interp if r["delta_utility"] > 0)
    hurt = sum(1 for r in interp if r["delta_utility"] < 0)
    tied = sum(1 for r in interp if r["delta_utility"] == 0)
    log.append(f"PASS helped/hurt/tied over {len(interp)} = {helped}/{hurt}/{tied}")
    return log


# =================================================================== self-test
def self_test(sample: dict[str, Any], src: dict[str, Any]) -> list[str]:
    """Plant each defect this converter could ship, and assert it is DETECTED.

    The point is not to confirm the converter works -- the validator already says that
    on the clean rows. It is to prove the checks CAN FAIL. A check only ever run on
    data it passes has not been shown to discriminate, and three of the plants below
    are for defects the SHIPPED VALIDATOR CANNOT SEE, so they are checked against this
    script's own guards instead. Where a guard is this script's, the plant goes through
    that guard; where it is the validator's, the plant goes through validate_row.
    """
    log: list[str] = []

    def expect_validator(code: str, mutate, what: str) -> None:
        bad = json.loads(json.dumps(sample))
        mutate(bad)
        codes = {i.code for i in V.validate_row(bad)}
        if code not in codes:
            raise AssertionError(
                f"SELF-TEST FAILED: planted {what} but {code!r} did not fire "
                f"(got {sorted(codes)})")
        log.append(f"PASS {code}: {what}")

    def expect_refusal(fn, what: str, needle: str = "") -> None:
        try:
            fn()
        except (ConversionRefused, SystemExit) as exc:
            if needle and needle not in str(exc):
                raise AssertionError(
                    f"SELF-TEST FAILED: planted {what} and the converter refused, but "
                    f"for the wrong stated reason: {str(exc)[:200]!r} does not mention "
                    f"{needle!r}. A right verdict with a wrong reason is harder to "
                    f"catch than a wrong verdict.")
            log.append(f"PASS refusal: {what}")
            return
        raise AssertionError(
            f"SELF-TEST FAILED: planted {what} but the converter accepted it.")

    # ---- 1. THE defect this project has shipped twice: a null reward coerced to 0.0.
    #      It is INVISIBLE to the shipped validator -- 0.0 is a well-formed float and
    #      a delta recomputed from it is internally consistent -- so it is caught
    #      against the artifact's independent `kind` column. Proven here by planting
    #      it and showing the row validates CLEAN while the guard still fires.
    coerced = json.loads(json.dumps(sample))
    coerced["reward_with_memory"] = 0.0
    coerced["reward_without_memory"] = 0.0
    coerced["delta_utility"] = 0.0
    clean_to_validator = [i for i in V.validate_row(coerced)
                          if i.severity == V.SEVERITY_ERROR]
    if clean_to_validator:
        raise AssertionError(
            "SELF-TEST FAILED: the coerced-reward row was expected to pass the shipped "
            "validator (that is WHY the independent guard exists), but it did not: "
            f"{[str(i) for i in clean_to_validator[:3]]}")
    log.append("PASS premise: a coerced 0.0 reward is INVISIBLE to validate_row -- "
               "the shipped validator cannot catch it, so the guard below must")
    # Measured corpus-wide rather than asserted from this one row: coercing every
    # null reward_with_memory in the emitted ledger (19 rows) and re-running the
    # SHIPPED validator flags 10 and SILENTLY ACCEPTS 9. The 9 are those whose other
    # arm carries a real reward, so the recomputed delta is internally consistent and
    # nothing in the row contradicts it. That is the measurement that makes
    # _assert_no_coerced_rewards load-bearing rather than redundant: the only witness
    # is the artifact's independent `kind` column.
    expect_refusal(
        lambda: _assert_no_coerced_rewards(
            [{"kind": SC.ERR_SYNTAX, "reward": 0.0, "arm": "with"}]),
        "an unscorable arm (syntax_error) carrying reward=0.0 -- 'could not be "
        "scored' rewritten as 'ran and was wrong', which manufactures harm",
        needle="manufactures harm")
    expect_refusal(
        lambda: _assert_no_coerced_rewards(
            [{"kind": SC.SCORE_OK, "reward": None, "arm": "with"}]),
        "a SCORED arm (pass) carrying reward=None -- the inverse direction, which a "
        "one-sided check would miss",
        needle="disagree about whether a score exists")
    # negative control: the guard must stay QUIET on the real artifact.
    _assert_no_coerced_rewards(src["rows"])
    log.append("PASS negative-control: the reward guard is silent on all 924 real "
               "arm-runs (it discriminates, it does not merely alarm)")

    # ---- 2. a missing field. Presence is the contract; null is a legal value.
    expect_validator("missing_field", lambda r: r.pop("delta_utility"),
                     "a field deleted from the row rather than set to null")

    # ---- 3. the not-retained sentinel WITHOUT its evidence. This is the check that
    #         stops the sentinel from becoming an unfalsifiable excuse: without a
    #         measured response length the row is indistinguishable from an EMPTY
    #         completion scored as an answer.
    expect_validator(
        "output_not_retained_without_evidence",
        lambda r: r["provenance"].update(response_chars_with=None),
        "the not-retained sentinel with its response_chars evidence removed")
    expect_validator(
        "output_not_retained_without_evidence",
        lambda r: r["provenance"].update(response_chars_with=0),
        "the not-retained sentinel with a ZERO response length -- i.e. an empty "
        "completion wearing a 'we discarded it' excuse")

    # ---- 4. the WRONG sentinel. WITHHELD_SEE_LICENSE on a SciCode row asserts a
    #         licence restriction that does not exist, in the one field a consumer
    #         would check to find out. Apache-2.0 withholds nothing.
    expect_validator(
        "declared_withheld_but_present",
        lambda r: (r.update(text_fields_withheld=["memory_text"],
                            reconstruction_required=True)),
        "a licence withholding DECLARED on an Apache-2.0 SciCode row whose text is "
        "in fact present -- the shape that would publish a false restriction")

    # ---- 5. a tautological faithfulness score on raw.
    expect_validator("faithfulness_scored_on_raw",
                     lambda r: r.update(faithfulness_check=1.0),
                     "a 1.0 faithfulness score on a raw memory (raw IS the source, so "
                     "any source-grounded proxy returns 1.0 by construction)")

    # ---- 6. raw compression that is not unity.
    expect_validator("raw_compression_not_unity",
                     lambda r: r.update(compression_ratio=0.25),
                     "a raw memory claiming 4x compression")

    # ---- 7. absence written as a measurement.
    expect_validator("absent_latency_reported_as_zero",
                     lambda r: r.update(memory_extraction_latency=0.0),
                     "a no-call extraction latency written as a measured 0.0")
    expect_validator("absent_reported_as_zero",
                     lambda r: r.update(reader_cluster="sophia",
                                        reader_model="openai/gpt-oss-120b",
                                        reasoning_tokens=0),
                     "reasoning_tokens=0 on a reader that does not report them")

    # ---- 8. a reward beside an error code -- an errored cell has no outcome.
    expect_validator("reward_on_errored_row",
                     lambda r: r.update(
                         error_code_if_any=S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH),
                     "an operational error code kept alongside a surviving reward")

    # ---- 9. a P3 field populated in a P1 row.
    expect_validator("p3_field_populated",
                     lambda r: r.update(propagation_metadata={"hop": 1}),
                     "a P3 propagation field populated in a P1 row")

    # ---- 10. derived bookkeeping that contradicts its own components.
    expect_validator("storage_bytes_mismatch", lambda r: r.update(storage_bytes=1),
                     "a storage_bytes that is not the text's byte length")
    expect_validator("candidate_pool_size_mismatch",
                     lambda r: r.update(candidate_pool_size=7),
                     "a pool size disagreeing with the evidence it came from")
    expect_validator("discriminativeness_mismatch",
                     lambda r: r["bearing_evidence"].update(discriminativeness=0.999),
                     "a discriminativeness that is not hits/size")
    expect_validator("id_mismatch", lambda r: r.update(row_id="row-deadbeef"),
                     "a row_id that is not the hash of its own content")

    # ---- 11. stability is null here BECAUSE one replicate cannot agree with itself.
    #          Both directions are planted: an out-of-range value, and the 1.0 that a
    #          converter reaching for a plausible default would write.
    expect_validator("stability_out_of_range",
                     lambda r: r.update(confidence_or_stability=1.5),
                     "a stability outside [0,1]")
    if sample["confidence_or_stability"] is not None:
        raise AssertionError(
            f"SELF-TEST FAILED: confidence_or_stability is "
            f"{sample['confidence_or_stability']!r} on a single-replicate cell. One "
            f"replicate cannot measure agreement with itself; 1.0 here would mean "
            f"'we did not look', not 'perfectly stable'.")
    log.append("PASS single-replicate stability is NULL, never 1.0 (one replicate "
               "cannot measure agreement with itself)")

    # ---- 12. THE TWO JOIN TRAPS, each proven with a POSITIVE CONTROL. An empty join
    #          must be shown to be a bad key, not an absence -- which is exactly the
    #          reading that cost this project three times.
    rows_by_rep: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in src["rows"]:
        rows_by_rep[r["representation"]].append(r)
    raw_locs = {r["memory_id"] for r in rows_by_rep["raw"]}
    sum_locs = {r["memory_id"] for r in rows_by_rep["summary"]}
    if not (raw_locs and raw_locs == sum_locs):
        raise AssertionError(
            "SELF-TEST FAILED: the positive control for the locator join is itself "
            "broken -- raw and summary do not share a locator set, so a later empty "
            "join would prove nothing.")
    log.append(f"PASS positive-control: joining raw<->summary on memory_unit_locator "
               f"matches {len(raw_locs)}/{len(sum_locs)} memories")

    # trap (a): the SCHEMA's memory_id is a CONTENT HASH, so it differs across
    # representations BY DESIGN and a cross-representation join on it returns ZERO.
    hash_raw = {sample["memory_id"]}
    alt = json.loads(json.dumps(sample))
    alt["memory_representation"] = "summary"
    alt["memory_text"] = sample["memory_text"] + "\n(summarised)"
    alt["memory_writer_model"] = "gpt-oss-120b"
    alt["memory_writer_cluster"] = "metis"
    alt["memory_id"] = S.compute_memory_id(alt)
    if hash_raw & {alt["memory_id"]}:
        raise AssertionError(
            "SELF-TEST FAILED: two representations of the same span produced the SAME "
            "content-hash memory_id, so trap (a) could not be demonstrated.")
    log.append("PASS join-trap (a): the schema memory_id is a CONTENT HASH -- the same "
               "span under two representations gives two different ids, so a "
               "cross-representation join on it returns ZERO rows. The correct key is "
               "provenance.memory_unit_locator, which is carried on every row.")

    # trap (b): condition_id EMBEDS the representation name.
    cid_raw = CONDITION_ID_FMT.format(rep="raw")
    cid_sum = CONDITION_ID_FMT.format(rep="summary")
    if "raw" not in cid_raw or cid_raw == cid_sum:
        raise AssertionError(
            "SELF-TEST FAILED: condition_id does not embed the representation, so "
            "trap (b) could not be demonstrated on these ids.")
    log.append(f"PASS join-trap (b): condition_id embeds the representation "
               f"({cid_raw!r} vs {cid_sum!r}), so including it in a "
               f"cross-representation join key silently returns ZERO rows.")

    # ---- 13. an unmapped SciCode kind must REFUSE rather than default to None.
    expect_refusal(lambda: _error_code_for_arm({"kind": "some_new_kind"}),
                   "an unmapped SciCode kind (the mapping is written down, not "
                   "improvised)", needle="must be ruled on")
    expect_refusal(lambda: _error_code_for_arm(
                       {"kind": "reader_call_failed", "detail": "SomeOtherError: x"}),
                   "a reader_call_failed whose exception has no recorded mapping",
                   needle="no mapping for")
    # negative control: the ONE real operational failure still maps correctly.
    real = [r for r in src["rows"] if r.get("kind") == "reader_call_failed"]
    if len(real) != 1:
        raise AssertionError(
            f"SELF-TEST FAILED: expected exactly 1 reader_call_failed arm-run in the "
            f"artifact, found {len(real)}; the negative control below is aimed at "
            f"nothing.")
    got = _error_code_for_arm(real[0])
    if got != S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH:
        raise AssertionError(
            f"SELF-TEST FAILED: the real TruncatedResponseError mapped to {got!r}, "
            f"not {S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH!r}")
    log.append(f"PASS negative-control: the one REAL reader_call_failed "
               f"(TruncatedResponseError, reasoning_tokens=1022) maps to "
               f"{got!r}, so the mapping is known to accept as well as refuse")

    # ---- 14. config drift must refuse rather than stamp this run's identity on
    #          someone else's data.
    expect_refusal(
        lambda: convert({**src, "config": {**src["config"], "seed": 1}},
                        dev_path=Path(DEFAULT_DEV), test_path=Path(DEFAULT_TEST)),
        "an artifact whose seed differs from the one this converter stamps",
        needle="differently-configured artifact")

    # ---- 15. filler reproducibility. If the filler rule drifted, every cell's
    #          recorded context is wrong while every row still validates.
    mems = SC.build_memory_units(SC.load_jsonl(Path(DEFAULT_DEV)))
    f = build_filler_ids(mems, "scicode_dev::1.1", 2, 20261008)
    if f != ["scicode_dev::19.1", "scicode_dev::78.3"]:
        raise AssertionError(
            f"SELF-TEST FAILED: the filler rule no longer reproduces the documented "
            f"case: scicode_dev::1.1 -> {f}, expected [19.1, 78.3]")
    log.append(f"PASS filler reproducibility: scicode_dev::1.1 -> {f}")

    # ---- negative control for the whole row: the clean row must PASS, or the checks
    #      above are rejecting everything and prove nothing.
    errs = [i for i in V.validate_row(sample) if i.severity == V.SEVERITY_ERROR]
    if errs:
        raise AssertionError(
            f"SELF-TEST FAILED: a correctly converted row was rejected: "
            f"{[str(i) for i in errs[:5]]}")
    log.append("PASS negative-control: a correctly converted row is accepted")
    return log


# ======================================================================== main
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path,
                    default=REPO_ROOT / "results/scicode/scaleup_all3.json")
    ap.add_argument("--analysis", type=Path,
                    default=REPO_ROOT / "results/ledgers/repro/scicode/scaleup_analysis.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dev", type=Path, default=Path(DEFAULT_DEV))
    ap.add_argument("--test", type=Path, default=Path(DEFAULT_TEST))
    ap.add_argument("--representations", default="raw",
                    help="comma-separated subset of raw,summary,structured. Only raw "
                         "is exportable today -- see the module docstring, refusal 2.")
    ap.add_argument("--acknowledge-unexportable", action="store_true",
                    help="proceed even though some cells cannot be exported. Required, "
                         "so a partial export is a stated decision rather than a "
                         "silent one.")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-write", action="store_true",
                    help="run every gate and print the report, write nothing")
    args = ap.parse_args(argv)

    reps = tuple(x.strip() for x in args.representations.split(",") if x.strip())
    bad = [r for r in reps if r not in S.MEMORY_REPRESENTATIONS]
    if bad:
        raise ConversionRefused(f"unknown representation(s) {bad}")

    src = json.loads(args.src.read_text())
    src["_source_sha256"] = S.file_sha256(args.src)
    analysis = json.loads(args.analysis.read_text())
    print(f"read {len(src['rows'])} arm-runs from {args.src}")
    print(f"  sha256 {src['_source_sha256']}")
    print(f"analysis ledger: {args.analysis} ({analysis.get('analysis_version')})")

    rows, stats = convert(src, dev_path=args.dev, test_path=args.test,
                          representations=reps)

    print(f"\ncells in artifact: {stats['cells_in_artifact']}")
    print(f"rows emitted:      {stats['rows_emitted']}")
    skipped = stats["skipped_unexportable"]
    if skipped:
        n = sum(skipped.values())
        print(f"\n🔴 {n} cells NOT exported, by representation: {skipped}")
        print("   REASON: memory_text is NON-NULLABLE and the summary/structured "
              "memory text\n"
              "   was never persisted by the run (no results/scicode/memories.jsonl, "
              "no write\n"
              "   cache; 0 of 12,023 cache entries key benchmark='scicode'). Those "
              "writes were\n"
              "   LLM calls, so re-running produces DIFFERENT bytes, which would be a "
              "different\n"
              "   memory wearing this run's rewards. Only `raw` has a truthful "
              "memory_text today.")
        if not args.acknowledge_unexportable:
            raise ConversionRefused(
                "REFUSING TO WRITE: a partial export that looks complete is the "
                "defect. Pass --acknowledge-unexportable to state that the "
                f"{n} missing cells are a known, documented gap.")

    if args.self_test:
        print("\n--- self-test: plant each defect, assert it is DETECTED ---")
        for line in self_test(rows[0], src):
            print("  " + line)
        print("self-test OK: every guard fired on its planted defect and stayed quiet "
              "on the clean row and the real artifact")

    print("\n--- cross-check against the analysis ledger ---")
    for line in cross_check_analysis(rows, analysis):
        print("  " + line)

    rep = V.validate_dataset(rows)
    print("\n--- validation of CONVERTED rows (src/p1mem/validate.py) ---")
    print(rep.summary())
    for i in rep.issues[:10]:
        print("  " + str(i))
    if len(rep.issues) > 10:
        print(f"  ... {len(rep.issues) - 10} more (all the same codes)")

    print("\nstats:")
    for k in ("rewards", "error_codes", "semantic_types", "bands",
              "arms_with_null_reward", "cells_with_null_delta", "leakage_flag_true",
              "similarity_terciles"):
        print(f"  {k}: {stats[k]}")
    print(f"  tokenizer: {stats['tokenizer']['tokenizer']}")

    if not rep.ok:
        raise ConversionRefused("converted rows do not validate; nothing written")
    if args.no_write:
        print("\n--no-write: validated, nothing written")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    S.write_jsonl_atomic(args.out, rows)
    print(f"\nwrote {len(rows)} {S.SCHEMA_VERSION} rows -> {args.out}")
    print(f"  sha256 {S.file_sha256(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""GEMMA READER SMOKE TEST -- a handful of REAL cells, reader identity recorded.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This runs a small, PRE-STATED set of real (memory, task) cells through the
Gemma reader on the EXACT memory artifacts gpt-oss already read, and writes
schema-valid rows. It exists to prove the infrastructure, not to measure
anything: n is far below the pre-registration's requirements and **no ΔU, no
label, and no reader comparison may be quoted from its output.**
``docs/ANALYSIS_PREREGISTRATION.md`` A1.3 binds >=2 replicates for any cell
entering a reported rate; this writes 2, which is enough to be schema-valid
and nowhere near enough to be a result.

THE DESIGN CONSTRAINT THIS ENFORCES IN CODE
--------------------------------------------
A reader-only replication is only interpretable if the reader is the ONLY
thing that changed. That is asserted here, not assumed:

  * the memory TEXT is read from ``results/repr_scaleup/memories.jsonl``,
    the same file the gpt-oss run consumed, and the file's sha256 is checked
    against the fingerprint that run recorded;
  * the filler pool is rebuilt by the same rule and its sha256 is checked
    against the screened run's recorded ``filler_pool_sha256``;
  * the system prompt sha256 is checked against the same fingerprint;
  * and -- the decisive one -- every rendered request's ``context_sha256`` is
    compared against the hash the gpt-oss cache stored for the SAME cell. A
    match proves byte-identity of the actual bytes sent, which no amount of
    "we used the same script" can.

If any of those disagree, the run ABORTS. A reader comparison built on
drifted context is not a reader comparison.

ELIGIBILITY -- FIXED HERE, BEFORE ANY GEMMA OUTPUT EXISTS, AND NON-OUTCOME-BASED
---------------------------------------------------------------------------------
Cells are chosen by:
  1. stratum in {BEARING, MATCHED_CONTROL}  -- the paired design's own strata;
  2. the representation's write succeeded (``ok``) -- a failed write has no
     memory text, so there is nothing to read;
  3. the gpt-oss run has a cached response for the cell, so byte-identity is
     CHECKABLE rather than merely asserted;
  4. then sorted by (representation, memory_unit_locator, task_id) and the
     first ``--per-repr`` taken per representation.

Nothing in that list mentions a reward, a delta, or anything gpt-oss answered.
Rule 3 is the only one that touches the gpt-oss run at all, and it selects on
the EXISTENCE of a cached request, never on its content -- picking cells where
gpt-oss did well, or badly, would be exactly the outcome filtering the house
rules forbid.

REWARD IS None WHEN IT CANNOT BE SCORED
----------------------------------------
A cell whose call raised (including the Gemma truncation guard) gets
``reward = None`` and an ``error_code_if_any``, never 0.0. Scoring an error as
a wrong answer is how a harmful memory gets manufactured.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem import schema as S  # noqa: E402
from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.cells import SYSTEM, MemoryUnit, build_context  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.memory.tokens import count_tokens  # noqa: E402
from p1mem.vendor.rcc_schema import sha256_text, utc_now  # noqa: E402
from p1mem.writer import CellWriter  # noqa: E402

#: UNCHANGED from the gpt-oss runs. The reader scaffold is not what varies.
PROMPT_VERSION = "p1_deltau_raw_v1"
STRATA = ("BEARING", "MATCHED_CONTROL")
K_FILLER = 4

#: One condition id per (representation, reader). NEVER a backfill of the
#: gpt-oss condition: docs/MODEL_ARMS.md and docs/CLUSTER_DECISION.md both
#: require a new reader to be a NEW ARM, labelled, never pooled.
CONDITION_ID = {
    "raw": "lmev2_raw_metis_gemma4_31B_smoke_v1",
    "summary": "lmev2_summary_metis_gemma4_31B_smoke_v1",
    "structured": "lmev2_structured_metis_gemma4_31B_smoke_v1",
}

#: Where the gpt-oss run cached each representation's reader calls. Used ONLY
#: to look up the context_sha256 it recorded, never to read its answers.
GPTOSS_CACHE = {
    "raw": REPO / "results/deltau_screened/cache.jsonl",
    "summary": REPO / "results/repr_scaleup/eval_cache.jsonl",
    "structured": REPO / "results/repr_scaleup/eval_cache.jsonl",
}

#: The gpt-oss ROW ledgers, read ONLY for the embedding measurement (see
#: ``load_embedding_reuse``). Never for an answer, a reward, or a delta.
GPTOSS_ROWS = (
    REPO / "results/deltau_screened/cells.jsonl",
    REPO / "results/repr_scaleup/cells.jsonl",
)


def load_embedding_reuse() -> dict[tuple, dict]:
    """Carry the recorded embedding measurement onto the Gemma rows.

    ``semantic_similarity``, ``semantic_distance_band`` and the two embedding
    references are NON-NULLABLE, and this smoke test issues no embedding calls.
    The three options were: (a) invent a number -- forbidden; (b) make the
    fields nullable -- weakens the schema for every run to suit one script;
    (c) REUSE the measurement the gpt-oss run already made.

    (c) is correct here for a specific reason, not for convenience: the
    embedding is a function of the MEMORY TEXT and the TASK TEXT, and GATE 4
    establishes that both are byte-identical to what gpt-oss was sent. The
    reader does not enter the embedding at all. So this is one measurement
    being read twice, not a second measurement being asserted.

    The join key is ``(memory_representation, memory_unit_locator,
    future_task_id)``. VERIFIED UNIQUE before use: across all 1,719 keys in
    the two ledgers, zero disagree on ``semantic_similarity`` or
    ``semantic_distance_band`` -- so the key determines the value and the join
    cannot silently pick one of several candidates. ``memory_id`` is NOT the
    key: it is a per-representation CONTENT HASH. ``condition_id`` is not in
    it either -- it embeds the reader name, so joining on it returns zero rows.

    Each reused row also carries its source ``memory_text`` so the caller can
    assert byte-identity rather than trust the locator.
    """
    out: dict[tuple, dict] = {}
    for path in GPTOSS_ROWS:
        if not path.exists():
            raise SystemExit(f"{path} missing; cannot reuse the embedding measurement")
        for line in path.open():
            if not line.strip():
                continue
            r = json.loads(line)
            loc = (r.get("provenance", {}).get("memory_unit_locator")
                   or r.get("source_episode_metadata", {}).get("memory_unit_locator"))
            if loc is None:
                continue
            k = (r["memory_representation"], loc, r["future_task_id"])
            prev = out.get(k)
            cand = {"semantic_similarity": r["semantic_similarity"],
                    "semantic_distance_band": r["semantic_distance_band"],
                    "embedding_model": r["embedding_model"],
                    "embedding_version": r["embedding_version"],
                    "memory_embedding_reference": r["memory_embedding_reference"],
                    "task_embedding_reference": r["task_embedding_reference"],
                    "memory_text": r["memory_text"]}
            if prev is not None and (prev["semantic_similarity"]
                                     != cand["semantic_similarity"]):
                raise SystemExit(
                    f"embedding join key {k} maps to two different "
                    f"semantic_similarity values; the join is ambiguous and a "
                    f"reused value would be arbitrary")
            out[k] = cand
    return out


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def load_texts(root: Path, locators: set[str]) -> dict[str, str]:
    """Join unit text out of trajectories.jsonl. A PARTIAL join aborts."""
    need = {loc.split(":")[0] for loc in locators}
    out: dict[str, str] = {}
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] not in need:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator in locators:
                out[pv.memory_unit_locator] = pv.text
        if len(out) >= len(locators):
            break
    missing = locators - set(out)
    if missing:
        raise SystemExit(
            f"text join matched {len(out)} of {len(locators)} units; missing "
            f"{sorted(missing)[:5]}. Half a join still looks like success.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--reader-arm", default="gemma_metis")
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--design-meta", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--representations", default="raw,summary,structured")
    ap.add_argument("--per-repr", type=int, default=2,
                    help="cells per representation. SMALL ON PURPOSE.")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=48)
    ap.add_argument("--out", type=Path, default=REPO / "results/gemma_reader")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    reps = [r.strip() for r in args.representations.split(",") if r.strip()]

    arm = S.reader_arm(args.reader_arm)
    log(f"READER ARM {args.reader_arm!r}: model={arm['reader_model']!r} "
        f"cluster={arm['reader_cluster']!r} temp={arm['temperature']} "
        f"max_tokens={arm['max_tokens']} workers={arm['max_workers']} "
        f"reasoning_effort={arm['reasoning_effort']!r} "
        f"(recorded as {arm['reader_reasoning_effort']!r})")
    log(f"  truncation_is_always_an_error={arm['truncation_is_always_an_error']} "
        f"reports_reasoning_tokens={arm['reports_reasoning_tokens']}")

    # ---- the same integrity gates the gpt-oss runs ran ----
    log(f"vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    log("writer blindness: PASSED")
    ok_ctrl, ctrl = LK.controls_summary()
    if not ok_ctrl:
        raise SystemExit("leakage detector controls FAILED")
    log(f"leakage detector controls: {sum(c.passed for c in ctrl)}/{len(ctrl)} PASS")

    # ---- design + memories ----
    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    cells = [c for c in design if c["stratum"] in STRATA]
    meta = json.loads(args.design_meta.read_text())
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    written = {(m["representation"], m["memory_unit_locator"]): m for m in mem_rows}
    emb_reuse = load_embedding_reuse()
    log(f"embedding measurements available for reuse: {len(emb_reuse)} "
        f"(repr, memory_unit_locator, task) keys")

    # ---- GATE 1: the memory artifact file is the one gpt-oss consumed ----
    k2_fp = json.loads(
        (REPO / "results/deltau_screened/cache.condition.json").read_text())
    r2_fp = json.loads(
        (REPO / "results/repr_scaleup/eval_cache.condition.json").read_text())
    mem_sha = S.file_sha256(args.memories)
    if mem_sha != r2_fp["memories_sha256"]:
        raise SystemExit(
            f"memories.jsonl sha256 {mem_sha[:16]} != the gpt-oss run's recorded "
            f"{r2_fp['memories_sha256'][:16]}. The memory artifacts have been "
            f"rewritten since; this would NOT be a reader-only replication.")
    log(f"GATE 1 memory artifacts: sha256 {mem_sha[:16]} MATCHES the gpt-oss run")

    # ---- GATE 2: the system prompt is unchanged ----
    if S.sha256_text(SYSTEM) != k2_fp["system_prompt_sha256"]:
        raise SystemExit("system prompt differs from the gpt-oss run's")
    log(f"GATE 2 system prompt: sha256 {S.sha256_text(SYSTEM)[:16]} MATCHES")

    # ---- filler pool, rebuilt by the SAME rule, then checked by hash ----
    fb = meta["filler"]["band"]
    max_hits = int(meta["config"]["max_pool_hits"])
    hits: dict[str, int] = collections.Counter()
    fired: dict[str, set] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if not line.strip():
            continue
        d = json.loads(line)
        hits[d["task_id"]] += 1
        fired[d["task_id"]].add(d["memory_id"])
    bearing = {m for tid, ms in fired.items()
               if tasks[tid].deterministic and 1 <= hits[tid] <= max_hits for m in ms}
    fire_trajs = {uloc[m]["trajectory_id"] for m in bearing}
    pool: dict[str, list] = collections.defaultdict(list)
    for u in units:
        if fb[0] <= u["n_tokens"] <= fb[1] and u["trajectory_id"] not in fire_trajs:
            pool[u["domain"]].append(u)
    for v in pool.values():
        v.sort(key=lambda u: u["memory_unit_locator"])
    # Non-vacuity FIRST: an empty pool is disjoint from everything and every
    # check below would pass on a run that silently had no filler at all.
    for d in sorted({c["domain"] for c in cells}):
        if len(pool.get(d, [])) < K_FILLER:
            raise SystemExit(
                f"filler pool for domain {d!r} has {len(pool.get(d, []))} units, "
                f"needs >= {K_FILLER}. A short pool passes disjointness vacuously.")
    pool_sha = S.sha256_text(json.dumps(
        {d: [u["memory_unit_locator"] for u in v] for d, v in sorted(pool.items())},
        sort_keys=True))
    if pool_sha != k2_fp["filler_pool_sha256"]:
        raise SystemExit(
            f"filler pool sha256 {pool_sha[:16]} != the gpt-oss run's "
            f"{k2_fp['filler_pool_sha256'][:16]}; context would not be identical.")
    log(f"GATE 3 filler pool: sha256 {pool_sha[:16]} MATCHES the gpt-oss run")

    def select_filler(p: list, *, k: int, task_id: str) -> list:
        o = sorted(p, key=lambda u: u["memory_unit_locator"])
        random.Random(f"filler:{task_id}").shuffle(o)
        return o[:k]

    # ---- the gpt-oss context hashes, per cell ----
    gptoss_ctx: dict[tuple, str] = {}
    for rep in reps:
        path = GPTOSS_CACHE[rep]
        if not path.exists():
            raise SystemExit(f"gpt-oss cache {path} missing; cannot verify byte-identity")
        for line in path.open():
            if not line.strip():
                continue
            k = json.loads(line)["key"]
            if "context_sha256" not in k:
                # The screened (raw) cache predates context_sha256 in the key.
                # Recorded as a real limitation below rather than silently
                # treated as agreement.
                continue
            gptoss_ctx[(k["memory_repr"], k["memory_id"], k["future_task_id"],
                        k["arm"], int(k["replicate_id"]))] = k["context_sha256"]
    have_ctx_for = {r for (r, *_rest) in gptoss_ctx}
    log(f"gpt-oss context hashes available for representations: {sorted(have_ctx_for)} "
        f"({len(gptoss_ctx)} cell-arm-replicates)")
    if "raw" in reps and "raw" not in have_ctx_for:
        log("  NOTE: the raw/screened cache was written under the v1 key shape, which "
            "had NO context_sha256. Byte-identity for raw is therefore verified "
            "against the filler-pool + prompt + memory-text hashes only, NOT against "
            "a stored request hash. Stated, not glossed.")

    # ---- ELIGIBILITY, applied exactly as documented above ----
    eligible: dict[str, list] = {r: [] for r in reps}
    for rep in reps:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            w = written.get((rep, c["memory_unit_locator"]))
            if w is None or not w["ok"]:
                continue
            if rep in have_ctx_for:
                key = (rep, w["memory_content_id"], c["task_id"], "with_memory", 0)
                if key not in gptoss_ctx:
                    continue
            # The embedding measurement must EXIST to be reused. Checked at
            # selection time so a missing one excludes the cell up front
            # rather than crashing after the calls are paid for.
            if (rep, c["memory_unit_locator"], c["task_id"]) not in emb_reuse:
                continue
            eligible[rep].append(c)
    chosen = {r: eligible[r][:args.per_repr] for r in reps}
    for r in reps:
        log(f"eligible {r}: {len(eligible[r])} cells -> taking first {len(chosen[r])}")

    # ---- build requests ----
    need = {c["memory_unit_locator"] for cs in chosen.values() for c in cs}
    need |= {u["memory_unit_locator"] for v in pool.values() for u in v}
    log(f"loading text for {len(need)} units ...")
    texts = load_texts(args.root, need)

    jobs: list[dict[str, Any]] = []
    ctx_checks = {"matched": 0, "mismatched": 0, "unverifiable_v1_key": 0}
    mismatches = []
    for rep in reps:
        for c in chosen[rep]:
            w = written[(rep, c["memory_unit_locator"])]
            task = tasks[c["task_id"]]
            u = uloc[c["memory_unit_locator"]]
            fil = select_filler(pool[u["domain"]], k=K_FILLER, task_id=task.id)
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            tgt = MemoryUnit(u["memory_id"], u["memory_unit_locator"],
                             w["memory_text"], int(w["memory_tokens"]), u["domain"])
            # Seeded by (task, MANIFEST memory id), exactly as the gpt-oss runs
            # did -- NOT by the per-representation content hash, which would
            # move the target between arms and confound representation with
            # position (docs/POSITION_EFFECT.md: 8/12 answers changed).
            with_ctx, pos = build_context(tgt, fus, seed_parts=(task.id, u["memory_id"]))
            without_ctx, npos = build_context(None, fus, seed_parts=(task.id, "none"))
            assert npos is None
            for r in range(args.replicates):
                for armname, ctx, position in (("with_memory", with_ctx, pos),
                                               ("without_memory", without_ctx, None)):
                    msgs = [{"role": "system", "content": SYSTEM},
                            {"role": "user",
                             "content": f"{ctx}\n\n--- Question ---\n{task.question}"}]
                    h = sha256_text(msgs)
                    # GATE 4: the DECISIVE byte-identity check.
                    want = gptoss_ctx.get(
                        (rep, w["memory_content_id"], task.id, armname, r))
                    if want is None:
                        ctx_checks["unverifiable_v1_key"] += 1
                    elif want == h:
                        ctx_checks["matched"] += 1
                    else:
                        ctx_checks["mismatched"] += 1
                        mismatches.append(
                            {"rep": rep, "loc": c["memory_unit_locator"],
                             "task": task.id, "arm": armname, "replicate": r,
                             "gptoss": want, "ours": h})
                    jobs.append({
                        "rep": rep, "cell": c, "unit": u, "task": task, "written": w,
                        "arm": armname, "replicate_id": r, "position": position,
                        "n_filler": len(fil),
                        "filler_tokens": sum(f["n_tokens"] for f in fil),
                        "messages": msgs, "context_sha256": h,
                        "context_tokens": count_tokens(ctx),
                    })

    log(f"GATE 4 CONTEXT BYTE-IDENTITY vs the gpt-oss cache: "
        f"matched={ctx_checks['matched']} mismatched={ctx_checks['mismatched']} "
        f"unverifiable(v1 key, raw)={ctx_checks['unverifiable_v1_key']}")
    if ctx_checks["mismatched"]:
        for m in mismatches[:5]:
            log(f"  MISMATCH {m}")
        raise SystemExit(
            f"{ctx_checks['mismatched']} requests differ in BYTES from what gpt-oss "
            f"was sent. This would not be a reader-only replication; aborting.")
    if ctx_checks["matched"] == 0 and ctx_checks["unverifiable_v1_key"] == 0:
        raise SystemExit("GATE 4 verified NOTHING -- a check that cannot fire is not a check")

    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        (args.out / "smoke_dryrun.json").write_text(json.dumps(
            {"planned_calls": len(jobs), "context_checks": ctx_checks,
             "reader_arm": args.reader_arm, "chosen":
                 {r: [[c["memory_unit_locator"], c["task_id"]] for c in chosen[r]]
                  for r in reps}}, indent=2))
        return 0

    # ---- execute ----
    cache = ResponseCache(args.out / "smoke_cache.jsonl")
    client = P1Client(cluster=arm["reader_cluster"], model=arm["reader_model"],
                      cache=cache, max_concurrency=arm["max_workers"],
                      truncation_is_always_an_error=arm["truncation_is_always_an_error"])
    results: dict[tuple, dict] = {}
    n_real = n_cached = n_err = 0
    t0 = time.monotonic()

    def run_one(j: dict):
        kf = {"benchmark": "longmemeval_v2",
              "source_item_id": j["unit"]["trajectory_id"],
              "memory_repr": j["rep"],
              "memory_id": j["written"]["memory_content_id"],
              "future_task_id": j["task"].id, "arm": j["arm"],
              "retrieval_method": "oracle", "prompt_version": PROMPT_VERSION,
              "replicate_id": j["replicate_id"]}
        try:
            c, rec = client.chat(j["messages"], max_tokens=arm["max_tokens"],
                                 temperature=float(arm["temperature"]),
                                 reasoning_effort=arm["reasoning_effort"],
                                 cache_key_fields=kf)
            return j, c, rec, None
        except ClientError as e:
            return j, None, None, f"{type(e).__name__}: {e}"

    log(f"executing {len(jobs)} calls at concurrency {arm['max_workers']} ...")
    with ThreadPoolExecutor(max_workers=arm["max_workers"]) as pool_ex:
        futs = [pool_ex.submit(run_one, j) for j in jobs]
        for fut in as_completed(futs):
            j, content, rec, err = fut.result()
            k = (j["rep"], j["unit"]["memory_unit_locator"], j["task"].id,
                 j["replicate_id"], j["arm"])
            if err is not None:
                n_err += 1
                results[k] = {"error": err, "job": j}
            else:
                n_cached += 1 if rec.cache_hit else 0
                n_real += 0 if rec.cache_hit else 1
                results[k] = {"content": content, "rec": rec, "job": j}
    wall = time.monotonic() - t0
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} errors={n_err}")

    # ---- resolved-model audit: every call must have answered as the pinned id ----
    resolved = collections.Counter(
        v["rec"].resolved_model for v in results.values() if v.get("rec") is not None)
    log(f"resolved_model across all calls: {dict(resolved)}")
    if set(resolved) - {arm["reader_model"]}:
        raise SystemExit(f"a call resolved to an unexpected model: {dict(resolved)}")

    # ---- score + write ----
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / "smoke_cells.jsonl"
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    reader_fields = S.reader_row_fields(args.reader_arm)
    n_written = 0
    summary_rows = []
    for rep in reps:
        for c in chosen[rep]:
            loc = c["memory_unit_locator"]
            wr = written[(rep, loc)]
            task = tasks[c["task_id"]]
            u = uloc[loc]
            mtext = wr["memory_text"]
            emb = emb_reuse[(rep, loc, task.id)]
            # The reused measurement must describe THIS text. The locator
            # matching is not enough: a re-export could have rewritten the
            # memory under the same locator (it has happened on this project).
            if emb["memory_text"] != mtext:
                raise SystemExit(
                    f"reused embedding for ({rep}, {loc}, {task.id}) was measured on "
                    f"DIFFERENT memory text than this run is sending; refusing to "
                    f"carry a similarity that describes other bytes.")
            leak = LK.detect(mtext, task.answer, memory_id=wr["memory_content_id"],
                             task_id=task.id, eval_function_spec=task.eval_function)
            for r in range(args.replicates):
                rw = results.get((rep, loc, task.id, r, "with_memory"), {})
                ro = results.get((rep, loc, task.id, r, "without_memory"), {})
                errs = [x.get("error") for x in (rw, ro) if x.get("error")]
                ow, oo = rw.get("content"), ro.get("content")
                if errs or ow is None or oo is None:
                    # 🔴 reward stays None. NEVER 0.0. An unscoreable cell has
                    # no outcome; a 0.0 here would read as a wrong answer and
                    # push dU negative, manufacturing a harmful memory.
                    reward_w = reward_o = delta = None
                    joined = " | ".join(errs)
                    code = (S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH
                            if "TruncatedResponseError" in joined else "http_error")
                    unk_w = unk_o = None
                else:
                    pw, po = extract_boxed_answer(ow), extract_boxed_answer(oo)
                    unk_w, unk_o = is_unknown(pw), is_unknown(po)
                    reward_w = 0.0 if unk_w else float(task.score(pw))
                    reward_o = 0.0 if unk_o else float(task.score(po))
                    delta = reward_w - reward_o
                    code = None
                recs = [x["rec"] for x in (rw, ro) if x.get("rec") is not None]
                rt = [x.reasoning_tokens for x in recs if x.reasoning_tokens is not None]
                job = (rw or ro).get("job", {})
                row = w.build(
                    benchmark="longmemeval_v2",
                    benchmark_version=lmev2.UPSTREAM_COMMIT,
                    source_episode_id=u["trajectory_id"],
                    source_episode_metadata={
                        "domain": u["domain"], "environment": u["environment"],
                        "outcome": u["outcome"], "url": u["url"],
                        "memory_unit_locator": loc},
                    memory_representation=rep,
                    memory_semantic_type=(wr.get("native_semantic_type") or "episodic"),
                    memory_text=mtext, memory_tokens=int(wr["memory_tokens"]),
                    memory_source_span={
                        "trajectory_id": u["trajectory_id"],
                        "start_state_index": u["start_state_index"],
                        "end_state_index": u["end_state_index"],
                        "n_states": u["n_states"], "memory_unit_locator": loc,
                        "derived_from": "whole_segment"},
                    memory_writer_model=wr["writer_model"],
                    memory_writer_cluster=wr["writer_cluster"],
                    memory_writer_prompt_version=wr["prompt_version"],
                    memory_extraction_latency=wr["extraction_latency_s"],
                    memory_extraction_input_tokens=wr["extraction_input_tokens"],
                    memory_extraction_output_tokens=wr["extraction_output_tokens"],
                    # ---- the embedding fields are NON-NULLABLE and this
                    # smoke test issues no embedding calls. The recorded
                    # measurement is REUSED, not re-asserted: the embedding is
                    # a function of the memory text and the task text, both
                    # proven byte-identical above, and the reader does not
                    # enter it. See load_embedding_reuse().
                    embedding_model=emb["embedding_model"],
                    embedding_version=emb["embedding_version"],
                    memory_embedding_reference=emb["memory_embedding_reference"],
                    future_task_id=task.id, future_task_family=task.question_type,
                    future_task_text=task.question,
                    task_embedding_reference=emb["task_embedding_reference"],
                    semantic_similarity=emb["semantic_similarity"],
                    semantic_distance_band=emb["semantic_distance_band"],
                    retrieval_method="oracle", retrieval_rank=None, retrieval_k=None,
                    memory_tokens_retrieved=int(wr["memory_tokens"]),
                    memory_tokens_exposed=int(wr["memory_tokens"]),
                    replicate_id=r,
                    seed_or_sampling_config={
                        "temperature": float(arm["temperature"]),
                        "max_tokens": arm["max_tokens"],
                        "reasoning_effort": arm["reasoning_effort"],
                        "seed": None},
                    **reader_fields,
                    reader_prompt_version=PROMPT_VERSION,
                    condition_id=CONDITION_ID[rep],
                    output_without_memory=oo, output_with_memory=ow,
                    reward_without_memory=reward_o, reward_with_memory=reward_w,
                    delta_utility=delta, robustness_confidence=None,
                    write_latency=wr["extraction_latency_s"], retrieval_latency=None,
                    generation_latency=round(sum(x.latency_s for x in recs), 4),
                    end_to_end_latency=round(sum(x.latency_s for x in recs), 4),
                    embedding_calls=0, generation_calls=len(recs),
                    input_tokens=sum(x.input_tokens for x in recs),
                    output_tokens=sum(x.output_tokens for x in recs),
                    # None, not 0: this reader returns no completion_tokens_details
                    # at all. 0 would assert a measurement nobody made.
                    reasoning_tokens=sum(rt) if rt else None,
                    retry_count=sum(x.retry_count for x in recs),
                    error_code_if_any=code,
                    # Null because this smoke test runs no faithfulness check,
                    # WITH the reason recorded -- an unexplained null cannot be
                    # told apart from a field nobody populated.
                    faithfulness_check=None,
                    faithfulness_notes=(
                        "not run: this is a reader-arm infrastructure smoke test. "
                        "Faithfulness is a property of the WRITE pass, which is "
                        "unchanged here (the memory text is byte-identical to the "
                        "gpt-oss run's) and was measured there."),
                    provenance={
                        "code_sha": CODE_SHA, "config_sha256": CONFIG_SHA,
                        "run_id": RUN_ID, "host": "laptop",
                        "writer": "scripts/gemma_reader_smoke.py",
                        "reader_arm": args.reader_arm,
                        "SMOKE_TEST_NOT_A_RESULT": True,
                        "_why": "infrastructure proof; n is far below the "
                                "pre-registration's requirements. No dU, label, or "
                                "reader comparison may be quoted from these rows.",
                        "target_position": job.get("position"),
                        "n_filler": job.get("n_filler"),
                        "filler_tokens": job.get("filler_tokens"),
                        "context_sha256": job.get("context_sha256"),
                        "context_tokens": job.get("context_tokens"),
                        "context_matches_gptoss_request": bool(
                            gptoss_ctx.get((rep, wr["memory_content_id"], task.id,
                                            "with_memory", r))
                            == job.get("context_sha256")) if rep in have_ctx_for
                            else None,
                        "system_prompt_sha256": S.sha256_text(SYSTEM),
                        "filler_pool_sha256": pool_sha,
                        "memories_sha256": mem_sha,
                        "stratum": c["stratum"], "why_stratum": c["why_stratum"],
                        "detector_fires": c["detector_fires"],
                        "task_pool_hits": c["task_pool_hits"],
                        "task_pool_size": c["task_pool_size"],
                        "n_bearing_tasks_for_this_memory":
                            c["n_bearing_tasks_for_this_memory"],
                        "is_unknown_with": unk_w, "is_unknown_without": unk_o,
                        "memory_unit_locator": loc,
                        "pair_key": f"{loc}|{task.id}",
                        "semantic_similarity_source":
                            "REUSED from the gpt-oss ledger for the same "
                            "(representation, memory_unit_locator, future_task_id); "
                            "this run issued no embedding calls. Valid because the "
                            "embedding is a function of memory+task text and both are "
                            "byte-identical (asserted). NOT a new measurement.",
                        "write_finish_reason": wr.get("finish_reason"),
                        "write_truncated": bool(wr.get("truncated")),
                    },
                    license_source_reference="longmemeval_v2:Apache-2.0",
                    verifier_id=task.eval_name,
                    verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                    reward_is_continuous=False,
                    leakage_flag=(bool(leak.any_leak) if not leak.undecidable else None),
                )
                w.write_row(row)
                n_written += 1
                summary_rows.append({
                    "representation": rep, "memory_unit_locator": loc,
                    "task_id": task.id, "replicate_id": r,
                    "stratum": c["stratum"],
                    "reader_model": row["reader_model"],
                    "reader_cluster": row["reader_cluster"],
                    "reader_reasoning_effort": row["reader_reasoning_effort"],
                    "reward_with_memory": reward_w,
                    "reward_without_memory": reward_o,
                    "delta_utility": delta, "error_code_if_any": code,
                    "reasoning_tokens": row["reasoning_tokens"],
                    "cell_id": row["cell_id"], "row_id": row["row_id"],
                })
    closed = w.close()
    log(f"wrote {n_written} rows -> {rows_path} ({closed})")

    # ---- VERIFY THE ARTIFACT. Exit 0 is not success. ----
    on_disk = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    expected = sum(len(chosen[r]) for r in reps) * args.replicates
    checks = {
        "rows_on_disk_equals_expected": len(on_disk) == expected,
        "every_row_has_reader_model": all(r["reader_model"] for r in on_disk),
        "every_row_has_reader_cluster": all(r["reader_cluster"] for r in on_disk),
        "every_row_has_reader_endpoint": all(r["reader_endpoint"] for r in on_disk),
        "every_row_has_reader_prompt_version":
            all(r["reader_prompt_version"] for r in on_disk),
        "every_row_has_reader_reasoning_effort":
            all(r["reader_reasoning_effort"] for r in on_disk),
        "every_row_has_reader_endpoint_sha256":
            all(r["reader_endpoint_sha256"] for r in on_disk),
        "reader_model_is_the_pinned_gemma_id":
            {r["reader_model"] for r in on_disk} == {arm["reader_model"]},
        "no_row_coerced_a_null_reward_to_zero": all(
            not (r["error_code_if_any"] and r["reward_with_memory"] is not None)
            for r in on_disk),
        "reasoning_tokens_is_null_never_zero":
            all(r["reasoning_tokens"] is None for r in on_disk),
        "condition_ids_are_new_not_the_gptoss_ones":
            all("gemma" in (r["condition_id"] or "") for r in on_disk),
    }
    log("ARTIFACT CHECKS (exit 0 is not success):")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k} ")

    summary = {
        "_what": "GEMMA READER SMOKE TEST -- infrastructure proof, NOT a result",
        "_binding": "n is far below docs/ANALYSIS_PREREGISTRATION.md requirements. "
                    "No delta_utility, utility_label, or reader comparison may be "
                    "quoted from these rows.",
        "run_at_utc": utc_now(), "run_id": RUN_ID, "wall_clock_s": round(wall, 2),
        "reader_arm": args.reader_arm,
        "reader_identity": {k: arm[k] for k in
                            ("reader_model", "reader_cluster", "reader_endpoint",
                             "reader_reasoning_effort", "temperature", "max_tokens",
                             "max_workers", "reports_reasoning_tokens",
                             "truncation_is_always_an_error")},
        "reader_prompt_version": PROMPT_VERSION,
        "condition_ids": {r: CONDITION_ID[r] for r in reps},
        "representations": reps, "replicates": args.replicates,
        "cells_per_representation": {r: len(chosen[r]) for r in reps},
        "eligible_pool_size": {r: len(eligible[r]) for r in reps},
        "eligibility_rule": (
            "stratum in BEARING/MATCHED_CONTROL; write ok; a gpt-oss cached request "
            "exists for the cell (EXISTENCE only, never its content); sorted by "
            "(memory_unit_locator, task_id) and first --per-repr taken. "
            "NON-OUTCOME-BASED and fixed before any Gemma output existed."),
        "identity_gates": {
            "memories_sha256": mem_sha,
            "memories_sha256_matches_gptoss_run": True,
            "system_prompt_sha256": S.sha256_text(SYSTEM),
            "system_prompt_matches_gptoss_run": True,
            "filler_pool_sha256": pool_sha,
            "filler_pool_matches_gptoss_run": True,
            "context_byte_identity_vs_gptoss_requests": ctx_checks,
        },
        "planned_calls": len(jobs), "real_endpoint_calls": n_real,
        "cache_hits": n_cached, "errors": n_err, "rows_written": n_written,
        "resolved_model_counts": dict(resolved),
        "artifact_checks": checks,
        "rows": summary_rows,
        "VERDICT": "SMOKE_PASSED" if all(checks.values()) else "SMOKE_FAILED",
    }
    (args.out / "smoke_summary.json").write_text(json.dumps(summary, indent=2))
    log(f"VERDICT: {summary['VERDICT']}")
    return 0 if all(checks.values()) else 1


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
CONFIG_SHA = S.file_sha256(REPO / "configs/endpoint_primary.json")
RUN_ID = f"gemma_smoke_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())

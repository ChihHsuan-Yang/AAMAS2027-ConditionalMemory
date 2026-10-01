#!/usr/bin/env python3
"""READER-ONLY REPLICATION at scale -- gemma-4-31B-it reads gpt-oss's memories.

THE DESIGN CONSTRAINT, ENFORCED IN CODE
----------------------------------------
Only the reader changes. Everything else is held byte-for-byte and the holding
is ASSERTED, not claimed. Five gates; any disagreement ABORTS before a call is
paid for.

  GATE 1  memories.jsonl sha256 == the gpt-oss run's recorded fingerprint
  GATE 2  system prompt sha256  == the gpt-oss run's recorded fingerprint
  GATE 3  rebuilt filler pool sha256 == the screened run's recorded value
  GATE 4  every rendered request's context_sha256 == the hash the gpt-oss
          CACHE stored for the same cell. Decisive: it compares the bytes
          actually sent. UNAVAILABLE for raw -- the screened cache predates
          context_sha256 in the key shape. Recorded as unverifiable_v1_key,
          never counted as agreement.
  GATE 5  per-cell target_position / n_filler / filler_tokens == the values
          the gpt-oss ROW recorded. Added here because gate 4 cannot cover
          raw, and gates 1-3 are global: they cannot catch a per-cell drift.
          This is the only per-cell byte check raw has.

ELIGIBILITY -- NON-OUTCOME-BASED, FIXED IN docs/READER_TRANSFER_PRECOMMITMENT.md
-------------------------------------------------------------------------------
stratum in {BEARING, MATCHED_CONTROL} (285 design cells) x {raw, summary,
structured}, minus the 8 cells whose structured WRITE failed -> 847. No rule
mentions a reward, a delta, a label, or anything either reader answered.

REWARD None
-----------
A call that raises -- including the Gemma truncation guard -- gives
reward = None and an error_code_if_any. NEVER 0.0: a 0.0 reads as a wrong
answer, drives dU negative, and manufactures a harmful memory.
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

PROMPT_VERSION = "p1_deltau_raw_v1"      # UNCHANGED from the gpt-oss runs
STRATA = ("BEARING", "MATCHED_CONTROL")
K_FILLER = 4
REPS = ("raw", "summary", "structured")

#: One condition id per (representation, reader). NEVER a backfill of the
#: gpt-oss condition: a new reader is a NEW ARM, labelled, never pooled.
CONDITION_ID = {
    "raw": "lmev2_raw_metis_gemma4_31B_readertransfer_v1",
    "summary": "lmev2_summary_metis_gemma4_31B_readertransfer_v1",
    "structured": "lmev2_structured_metis_gemma4_31B_readertransfer_v1",
}

#: gpt-oss reader caches -- read ONLY for the context_sha256 they recorded.
GPTOSS_CACHE = {
    "raw": REPO / "results/deltau_screened/cache.jsonl",
    "summary": REPO / "results/repr_scaleup/eval_cache.jsonl",
    "structured": REPO / "results/repr_scaleup/eval_cache.jsonl",
}

#: gpt-oss ROW ledgers -- read for the embedding measurement and for GATE 5's
#: per-cell context fingerprints. Never for an answer, a reward, or a delta.
GPTOSS_ROWS = (
    REPO / "results/deltau_screened/cells.jsonl",
    REPO / "results/repr_scaleup/cells.jsonl",
)


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def row_locator(r: dict) -> str | None:
    return ((r.get("provenance") or {}).get("memory_unit_locator")
            or (r.get("source_episode_metadata") or {}).get("memory_unit_locator"))


def load_gptoss_cell_facts() -> dict[tuple, dict]:
    """Per-cell facts from the gpt-oss ledgers: embedding + context fingerprint.

    Two uses, both non-outcome:

    * the embedding fields are NON-NULLABLE and this run issues no embedding
      calls. The embedding is a function of the MEMORY TEXT and the TASK TEXT,
      both proven byte-identical by the gates, and the reader does not enter
      it -- so this is ONE measurement read twice, not a second asserted.
    * ``target_position`` / ``n_filler`` / ``filler_tokens`` are GATE 5's
      per-cell byte check.

    Join key is ``(memory_representation, memory_unit_locator,
    future_task_id)``. ``memory_id`` is NOT the key -- it is a content hash;
    ``condition_id`` is not either -- it embeds the representation AND the
    reader, so joining on it returns zero rows.
    """
    out: dict[tuple, dict] = {}
    for path in GPTOSS_ROWS:
        if not path.exists():
            raise SystemExit(f"{path} missing; cannot reuse the gpt-oss measurement")
        for line in path.open():
            if not line.strip():
                continue
            r = json.loads(line)
            loc = row_locator(r)
            if loc is None:
                continue
            k = (r["memory_representation"], loc, r["future_task_id"])
            p = r.get("provenance") or {}
            cand = {
                "semantic_similarity": r["semantic_similarity"],
                "semantic_distance_band": r["semantic_distance_band"],
                "embedding_model": r["embedding_model"],
                "embedding_version": r["embedding_version"],
                "memory_embedding_reference": r["memory_embedding_reference"],
                "task_embedding_reference": r["task_embedding_reference"],
                "memory_text": r["memory_text"],
                "target_position": p.get("target_position"),
                "n_filler": p.get("n_filler"),
                "filler_tokens": p.get("filler_tokens"),
                "stratum": p.get("stratum"),
            }
            prev = out.get(k)
            if prev is not None:
                for f in ("semantic_similarity", "target_position", "n_filler",
                          "filler_tokens", "memory_text"):
                    if prev[f] != cand[f]:
                        raise SystemExit(
                            f"gpt-oss join key {k} maps to two different {f!r} "
                            f"values; a reused value would be arbitrary")
            out[k] = cand
    return out


def load_texts(root: Path, locators: set[str]) -> dict[str, str]:
    """Join unit text out of trajectories.jsonl. A PARTIAL join ABORTS."""
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
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--limit-cells", type=int, default=0,
                    help="0 = the whole eligible set. A positive value takes "
                         "the FIRST n by (memory_unit_locator, task_id) -- the "
                         "precommitted subset rule, never an outcome filter.")
    ap.add_argument("--max-calls", type=int, default=4000)
    ap.add_argument("--out", type=Path, default=REPO / "results/gemma_reader")
    ap.add_argument("--rows-name", default="transfer_cells.jsonl")
    ap.add_argument("--cache-name", default="transfer_cache.jsonl")
    ap.add_argument("--summary-name", default="transfer_summary.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plant-context-defect", action="store_true",
                    help="POSITIVE CONTROL: corrupt one rendered request so "
                         "GATE 4 MUST abort. A gate that has only ever passed "
                         "is not known to discriminate.")
    ap.add_argument("--plant-position-defect", action="store_true",
                    help="POSITIVE CONTROL for GATE 5.")
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
    facts = load_gptoss_cell_facts()
    log(f"gpt-oss per-cell facts available: {len(facts)} "
        f"(representation, memory_unit_locator, future_task_id) keys")

    # ---- GATE 1 / GATE 2 ----
    k2_fp = json.loads(
        (REPO / "results/deltau_screened/cache.condition.json").read_text())
    r2_fp = json.loads(
        (REPO / "results/repr_scaleup/eval_cache.condition.json").read_text())
    mem_sha = S.file_sha256(args.memories)
    if mem_sha != r2_fp["memories_sha256"]:
        raise SystemExit(
            f"memories.jsonl sha256 {mem_sha[:16]} != the gpt-oss run's recorded "
            f"{r2_fp['memories_sha256'][:16]}. This would NOT be reader-only.")
    log(f"GATE 1 memory artifacts: sha256 {mem_sha[:16]} MATCHES the gpt-oss run")
    if S.sha256_text(SYSTEM) != k2_fp["system_prompt_sha256"]:
        raise SystemExit("system prompt differs from the gpt-oss run's")
    log(f"GATE 2 system prompt: sha256 {S.sha256_text(SYSTEM)[:16]} MATCHES")

    # ---- GATE 3: filler pool rebuilt by the SAME rule, then hashed ----
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
    # Non-vacuity FIRST: an empty pool is disjoint from everything, so every
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

    # ---- the gpt-oss context hashes, per cell-arm-replicate ----
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
                continue      # v1 key shape: no stored request hash. See GATE 5.
            gptoss_ctx[(k["memory_repr"], k["memory_id"], k["future_task_id"],
                        k["arm"], int(k["replicate_id"]))] = k["context_sha256"]
    have_ctx_for = {r for (r, *_rest) in gptoss_ctx}
    log(f"gpt-oss context hashes available for: {sorted(have_ctx_for)} "
        f"({len(gptoss_ctx)} cell-arm-replicates)")
    for rep in reps:
        if rep not in have_ctx_for:
            log(f"  NOTE: {rep!r} has NO stored request hash (v1 cache key shape). "
                f"GATE 4 cannot cover it; GATE 5 is its per-cell check. Stated, "
                f"not glossed -- an absent check must never read as a passing one.")

    # ---- ELIGIBILITY ----
    eligible: dict[str, list] = {r: [] for r in reps}
    excluded: dict[str, list] = {r: [] for r in reps}
    for rep in reps:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            w = written.get((rep, c["memory_unit_locator"]))
            if w is None:
                excluded[rep].append({"cell": c["memory_unit_locator"] + "|" + c["task_id"],
                                      "reason": "no_memory_written"})
                continue
            if not w["ok"]:
                excluded[rep].append({"cell": c["memory_unit_locator"] + "|" + c["task_id"],
                                      "reason": "write_failed",
                                      "error_code": w.get("error_code")})
                continue
            if (rep, c["memory_unit_locator"], c["task_id"]) not in facts:
                excluded[rep].append({"cell": c["memory_unit_locator"] + "|" + c["task_id"],
                                      "reason": "no_gptoss_row_to_reuse_embedding_from"})
                continue
            eligible[rep].append(c)
    if args.limit_cells:
        chosen = {r: eligible[r][:args.limit_cells] for r in reps}
    else:
        chosen = {r: list(eligible[r]) for r in reps}
    for r in reps:
        log(f"eligible {r}: {len(eligible[r])} cells (excluded {len(excluded[r])}) "
            f"-> running {len(chosen[r])}")

    # ---- build requests ----
    need = {c["memory_unit_locator"] for cs in chosen.values() for c in cs}
    need |= {u["memory_unit_locator"] for v in pool.values() for u in v}
    log(f"loading text for {len(need)} units ...")
    texts = load_texts(args.root, need)

    jobs: list[dict[str, Any]] = []
    ctx_checks = {"matched": 0, "mismatched": 0, "unverifiable_v1_key": 0}
    g5 = {"matched": 0, "mismatched": 0}
    mismatches: list[dict] = []
    g5_mismatches: list[dict] = []
    for rep in reps:
        for ci, c in enumerate(chosen[rep]):
            w = written[(rep, c["memory_unit_locator"])]
            task = tasks[c["task_id"]]
            u = uloc[c["memory_unit_locator"]]
            fil = select_filler(pool[u["domain"]], k=K_FILLER, task_id=task.id)
            if args.plant_position_defect and ci == 0:
                # POSITIVE CONTROL for GATE 5: drop one filler unit. This is a
                # REAL rendering drift -- n_filler, filler_tokens and the
                # rendered bytes all move -- not a mis-recorded field. On raw,
                # where GATE 4 is blind, GATE 5 is the ONLY check that can see
                # it, which is exactly the case this control must exercise.
                fil = fil[:-1]
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            tgt = MemoryUnit(u["memory_id"], u["memory_unit_locator"],
                             w["memory_text"], int(w["memory_tokens"]), u["domain"])
            # Seeded by (task, MANIFEST memory id) exactly as the gpt-oss runs
            # did -- NOT by the per-representation content hash, which would
            # move the target between arms and confound representation with
            # position.
            with_ctx, pos = build_context(tgt, fus, seed_parts=(task.id, u["memory_id"]))
            without_ctx, npos = build_context(None, fus, seed_parts=(task.id, "none"))
            assert npos is None
            n_filler = len(fil)
            filler_tokens = sum(f["n_tokens"] for f in fil)

            # ---- GATE 5: per-cell context fingerprints vs the gpt-oss ROW ----
            fact = facts[(rep, c["memory_unit_locator"], task.id)]
            got = (pos, n_filler, filler_tokens)
            wantg5 = (fact["target_position"], fact["n_filler"], fact["filler_tokens"])
            if got == wantg5:
                g5["matched"] += 1
            else:
                g5["mismatched"] += 1
                g5_mismatches.append({"rep": rep, "loc": c["memory_unit_locator"],
                                      "task": task.id, "gptoss": wantg5, "ours": got})

            for r in range(args.replicates):
                for armname, ctx, position in (("with_memory", with_ctx, pos),
                                               ("without_memory", without_ctx, None)):
                    msgs = [{"role": "system", "content": SYSTEM},
                            {"role": "user",
                             "content": f"{ctx}\n\n--- Question ---\n{task.question}"}]
                    if args.plant_context_defect and ci == 0 and r == 0:
                        msgs[1]["content"] += " "     # one byte
                    h = sha256_text(msgs)
                    # ---- GATE 4 ----
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
                        "n_filler": n_filler, "filler_tokens": filler_tokens,
                        "messages": msgs, "context_sha256": h,
                        "context_tokens": count_tokens(ctx),
                    })

    log(f"GATE 4 CONTEXT BYTE-IDENTITY vs the gpt-oss cache: "
        f"matched={ctx_checks['matched']} mismatched={ctx_checks['mismatched']} "
        f"unverifiable(v1 key)={ctx_checks['unverifiable_v1_key']}")
    if ctx_checks["mismatched"]:
        for m in mismatches[:5]:
            log(f"  MISMATCH {m}")
        raise SystemExit(
            f"{ctx_checks['mismatched']} requests differ in BYTES from what gpt-oss "
            f"was sent. This would not be a reader-only replication; aborting.")
    if ctx_checks["matched"] == 0 and ctx_checks["unverifiable_v1_key"] == 0:
        raise SystemExit("GATE 4 verified NOTHING -- a check that cannot fire is not a check")
    log(f"GATE 5 PER-CELL CONTEXT FINGERPRINTS vs the gpt-oss rows: "
        f"matched={g5['matched']} mismatched={g5['mismatched']}")
    if g5["mismatched"]:
        for m in g5_mismatches[:5]:
            log(f"  G5 MISMATCH {m}")
        raise SystemExit(
            f"{g5['mismatched']} cells render the target at a different position or "
            f"with different filler than gpt-oss saw; aborting.")
    if g5["matched"] == 0:
        raise SystemExit("GATE 5 verified NOTHING")

    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        (args.out / "transfer_dryrun.json").write_text(json.dumps(
            {"planned_calls": len(jobs), "gate4": ctx_checks, "gate5": g5,
             "reader_arm": args.reader_arm,
             "eligible": {r: len(eligible[r]) for r in reps},
             "chosen": {r: len(chosen[r]) for r in reps},
             "excluded": {r: excluded[r] for r in reps}}, indent=2))
        return 0

    # ---- execute ----
    cache = ResponseCache(args.out / args.cache_name)
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
    done = 0
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
            done += 1
            if done % 200 == 0:
                el = time.monotonic() - t0
                log(f"  {done}/{len(jobs)} in {el:.0f}s "
                    f"({done / el * 60:.1f}/min) real={n_real} err={n_err}")
    wall = time.monotonic() - t0
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} errors={n_err}")

    # ---- resolved-model audit ----
    resolved = collections.Counter(
        v["rec"].resolved_model for v in results.values() if v.get("rec") is not None)
    log(f"resolved_model across all calls: {dict(resolved)}")
    if set(resolved) - {arm["reader_model"]}:
        raise SystemExit(f"a call resolved to an unexpected model: {dict(resolved)}")

    # ---- score + write ----
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / args.rows_name
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    reader_fields = S.reader_row_fields(args.reader_arm)
    n_written = 0
    summary_rows: list[dict] = []
    for rep in reps:
        for c in chosen[rep]:
            loc = c["memory_unit_locator"]
            wr = written[(rep, loc)]
            task = tasks[c["task_id"]]
            u = uloc[loc]
            mtext = wr["memory_text"]
            fact = facts[(rep, loc, task.id)]
            # The reused measurement must describe THIS text. The locator
            # matching is not enough: a re-export could have rewritten the
            # memory under the same locator (it has happened on this project).
            if fact["memory_text"] != mtext:
                raise SystemExit(
                    f"reused gpt-oss facts for ({rep}, {loc}, {task.id}) were measured "
                    f"on DIFFERENT memory text; refusing to carry them.")
            leak = LK.detect(mtext, task.answer, memory_id=wr["memory_content_id"],
                             task_id=task.id, eval_function_spec=task.eval_function)
            for r in range(args.replicates):
                rw = results.get((rep, loc, task.id, r, "with_memory"), {})
                ro = results.get((rep, loc, task.id, r, "without_memory"), {})
                errs = [x.get("error") for x in (rw, ro) if x.get("error")]
                ow, oo = rw.get("content"), ro.get("content")
                if errs or ow is None or oo is None:
                    # reward stays None. NEVER 0.0.
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
                    # Embedding fields are NON-NULLABLE and this run issues no
                    # embedding calls. The recorded measurement is REUSED, not
                    # re-asserted: the embedding is a function of memory+task
                    # text, both proven byte-identical, and the reader does not
                    # enter it.
                    embedding_model=fact["embedding_model"],
                    embedding_version=fact["embedding_version"],
                    memory_embedding_reference=fact["memory_embedding_reference"],
                    future_task_id=task.id, future_task_family=task.question_type,
                    future_task_text=task.question,
                    task_embedding_reference=fact["task_embedding_reference"],
                    semantic_similarity=fact["semantic_similarity"],
                    semantic_distance_band=fact["semantic_distance_band"],
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
                    faithfulness_check=None,
                    faithfulness_notes=(
                        "not run on the READ pass. Faithfulness is a property of the "
                        "WRITE pass, which is unchanged here (the memory text is "
                        "byte-identical to the gpt-oss run's, asserted by GATE 1) and "
                        "was measured there: results/repr_scaleup/memories.jsonl."),
                    provenance={
                        "code_sha": CODE_SHA, "config_sha256": CONFIG_SHA,
                        "run_id": RUN_ID, "host": "laptop",
                        "writer": "scripts/gemma_reader_run.py",
                        "reader_arm": args.reader_arm,
                        "READER_TRANSFER_ARM": True,
                        "gptoss_comparator_condition_id": {
                            "raw": "lmev2_raw_metis_gptoss120b_screened_v1",
                            "summary": "lmev2_summary_metis_gptoss120b_screened_v1",
                            "structured":
                                "lmev2_structured_metis_gptoss120b_screened_v1",
                        }[rep],
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
                        "gate5_position_filler_match_gptoss_row": True,
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
                    "reward_with_memory": reward_w,
                    "reward_without_memory": reward_o,
                    "delta_utility": delta, "error_code_if_any": code,
                    "cell_id": row["cell_id"], "row_id": row["row_id"],
                })
    closed = w.close()
    log(f"wrote {n_written} rows -> {rows_path} ({closed})")

    # ---- VERIFY THE ARTIFACT. Exit 0 is not success. ----
    on_disk = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    expected = sum(len(chosen[r]) for r in reps) * args.replicates
    nulls = [r for r in on_disk if r["delta_utility"] is None]
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
        "every_errored_row_has_null_reward": all(
            (r["reward_with_memory"] is None and r["reward_without_memory"] is None)
            for r in on_disk if r["error_code_if_any"]),
        "reasoning_tokens_is_null_never_zero":
            all(r["reasoning_tokens"] is None for r in on_disk),
        "condition_ids_are_new_not_the_gptoss_ones":
            all("gemma" in (r["condition_id"] or "") for r in on_disk),
        "replicates_per_cell_as_requested": (
            set(collections.Counter(
                (r["provenance"]["pair_key"], r["memory_representation"])
                for r in on_disk).values()) == {args.replicates}),
    }
    log("ARTIFACT CHECKS (exit 0 is not success):")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k}")

    summary = {
        "_what": "READER-ONLY REPLICATION: gemma-4-31B-it reads the EXACT memory "
                 "artifacts gpt-oss-120b read. Only the reader changed.",
        "precommitment": "docs/READER_TRANSFER_PRECOMMITMENT.md (written before "
                         "any design-cell Gemma call)",
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
        "excluded": {r: excluded[r] for r in reps},
        "eligibility_rule": (
            "stratum in BEARING/MATCHED_CONTROL (285 design cells) x "
            "{raw,summary,structured}; the write succeeded; a gpt-oss row exists "
            "to reuse the embedding measurement from. NON-OUTCOME-BASED, fixed in "
            "docs/READER_TRANSFER_PRECOMMITMENT.md before any Gemma design-cell "
            "output existed."),
        "identity_gates": {
            "gate1_memories_sha256": mem_sha,
            "gate1_matches_gptoss_run": True,
            "gate2_system_prompt_sha256": S.sha256_text(SYSTEM),
            "gate2_matches_gptoss_run": True,
            "gate3_filler_pool_sha256": pool_sha,
            "gate3_matches_gptoss_run": True,
            "gate4_context_byte_identity_vs_gptoss_requests": ctx_checks,
            "gate4_coverage_note": (
                "raw has NO stored request hash (the screened cache uses the v1 key "
                "shape, which had no context_sha256). Those requests are counted as "
                "unverifiable_v1_key, never as agreement. GATE 5 is raw's per-cell "
                "check."),
            "gate5_per_cell_position_and_filler_vs_gptoss_rows": g5,
        },
        "planned_calls": len(jobs), "real_endpoint_calls": n_real,
        "cache_hits": n_cached, "errors": n_err, "rows_written": n_written,
        "rows_with_null_delta": len(nulls),
        "resolved_model_counts": dict(resolved),
        "artifact_checks": checks,
        "VERDICT": "RUN_PASSED" if all(checks.values()) else "RUN_FAILED",
    }
    (args.out / args.summary_name).write_text(json.dumps(summary, indent=2))
    log(f"VERDICT: {summary['VERDICT']}")
    return 0 if all(checks.values()) else 1


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
CONFIG_SHA = S.file_sha256(REPO / "configs/endpoint_primary.json")
RUN_ID = f"gemma_transfer_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())

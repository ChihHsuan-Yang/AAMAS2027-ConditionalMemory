#!/usr/bin/env python3
"""R2: run the WITH/WITHOUT evaluation for SUMMARY and STRUCTURED.

Same 285 BEARING+MATCHED_CONTROL cells the Raw screened run already measured,
same source experiences, same future tasks (prereg section 9's within-episode
pairing). RANDOM is deliberately out of scope: it is the dilution diagnostic
and does not need three representations.

EVERYTHING HELD FIXED FROM ``scripts/k2_run_screened.py``, because the paired
comparison is only meaningful if the representation is the sole difference:

* the same filler pool, the same K=4, the same ``filler:{task_id}`` seed, so a
  given task renders the SAME four filler notes in all three arms;
* the same target position rule, seeded by ``(task_id, memory_id)`` and NOT by
  replicate, so replicates are byte-identical requests (prereg section 2);
* the same system prompt and question scaffold;
* the same deterministic scorer and the same UNKNOWN rule.

🔴 WHAT IS *NOT* HELD FIXED, AND WHY THAT IS CORRECT
-----------------------------------------------------
``memory_id`` is a content hash over ``memory_text`` AND
``memory_representation``, so the three arms have different memory ids and
different ``cell_id``s. That is experimental identity working as designed: a
summary of a segment is not the same memory as the segment. The cells are
joined for the paired analysis on ``(memory_unit_locator, future_task_id)``,
which is the thing that actually matches across arms, never on ``memory_id``.

THE WITHOUT ARM IS RE-GENERATED PER REPRESENTATION, AND MUST BE
----------------------------------------------------------------
Its context is K=4 filler and no target, so its BYTES are identical across the
three representations. It would be cheaper to reuse Raw's WITHOUT answers.
Two reasons not to:

1. Amendment A1.4 binds the WITHOUT arm to be genuinely re-generated. Reusing
   one generation across arms is the same hazard at a different scale.
2. It is the only available cross-arm control. If the WITHOUT arm is
   re-generated independently for three arms and returns byte-identical text,
   that is a measured demonstration that the reader is deterministic and that
   the three arms differ only in the target -- a fact the paired ΔU rests on.
   Reusing the answers would make that agreement true by construction.

``--assert-without-matches-raw`` checks it after the fact and reports the rate.
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

import numpy as np  # noqa: E402

from p1mem import schema as S  # noqa: E402
from p1mem.adapters import leakage as LK  # noqa: E402
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.cache import ResponseCache  # noqa: E402
from p1mem.cells import SYSTEM, MemoryUnit, build_context  # noqa: E402
from p1mem.client import ClientError, P1Client  # noqa: E402
from p1mem.embed import EMBED_DIM, EMBED_MODEL, EmbeddingClient  # noqa: E402
from p1mem.memory.tokens import count_tokens  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402
from p1mem.writer import CellWriter  # noqa: E402

# Identical to the screened run: the reader scaffold did not change, and
# bumping it would make the three arms non-comparable for no reason.
PROMPT_VERSION = "p1_deltau_raw_v1"
STRATA = ("BEARING", "MATCHED_CONTROL")
EMBED_TOKEN_BUDGET = 2000
EMBED_MIN_BUDGET = 500

#: One condition id per representation. NOT a backfill of the raw condition:
#: MEMORY_PROTOCOL section 3 -- a different writer configuration is a new arm.
CONDITION_ID = {
    "summary": "lmev2_summary_metis_gptoss120b_screened_v1",
    "structured": "lmev2_structured_metis_gptoss120b_screened_v1",
}


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def truncate_to_tokens(text: str, budget: int) -> tuple[str, bool]:
    if count_tokens(text) <= budget:
        return text, False
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(text[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo], True


def embed_with_backoff(emb, labelled, budget):
    from p1mem.client import EndpointError  # noqa: PLC0415
    vecs, used = {}, {}
    for key, text in labelled:
        b = budget
        while True:
            t, _ = truncate_to_tokens(text, b)
            try:
                vecs[key] = emb.embed([t])[0]
                used[key] = b
                break
            except EndpointError:
                b //= 2
                if b < EMBED_MIN_BUDGET:
                    raise RuntimeError(
                        f"embedding {key!r} failed even at {EMBED_MIN_BUDGET} tokens; "
                        f"refusing to write a null into non-nullable "
                        f"semantic_similarity")
                log(f"  embed retry {key[:24]}: budget -> {b}")
    return vecs, used


def load_texts(root: Path, locators: set[str]) -> dict[str, str]:
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
        raise RuntimeError(
            f"text join matched {len(out)} of {len(locators)} units; missing "
            f"{sorted(missing)[:5]}. A partial join must abort.")
    return out


def assert_cache_condition(cache_path: Path, fingerprint: dict) -> dict:
    """Refuse to reuse a cache written under a different context configuration.

    Same guard as ``k2_run_screened.assert_cache_condition``. The cache KEY now
    carries ``context_sha256`` so a cross-condition collision is no longer
    possible on the key alone -- but the fingerprint still catches reuse of a
    cache FILE written under a different filler pool or prompt, which would
    otherwise be a total miss that merely looks like an expensive rerun.
    """
    side = cache_path.with_suffix(".condition.json")
    if side.exists():
        prev = json.loads(side.read_text())
        if prev != fingerprint:
            diff = {k: (prev.get(k), fingerprint.get(k))
                    for k in set(prev) | set(fingerprint)
                    if prev.get(k) != fingerprint.get(k)}
            raise SystemExit(
                f"cache at {cache_path} was written under a DIFFERENT configuration.\n"
                f"  differing (stored, current): {json.dumps(diff, indent=2)}\n"
                f"  fix: point --out at a fresh directory.")
        log(f"cache condition fingerprint MATCHES prior run at {side.name}")
    else:
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps(fingerprint, indent=2, sort_keys=True))
        log(f"cache condition fingerprint written -> {side.name}")
    n_prior = sum(1 for _ in cache_path.open()) if cache_path.exists() else 0
    log(f"cache at {cache_path.name}: {n_prior} prior entries")
    return {"fingerprint": fingerprint, "n_prior_cache_entries": n_prior}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--design-meta", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/repr_scaleup/memories.jsonl")
    ap.add_argument("--representations", default="summary,structured")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--k-filler", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=2400)
    ap.add_argument("--out", type=Path, default=REPO / "results/repr_scaleup")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    reps = [r.strip() for r in args.representations.split(",") if r.strip()]
    for r in reps:
        if r not in CONDITION_ID:
            raise SystemExit(f"unknown representation {r!r}")

    log(f"verifying vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    log("writer blindness: PASSED")
    ok_ctrl, ctrl = LK.controls_summary()
    if not ok_ctrl:
        raise SystemExit("leakage detector controls FAILED")
    log(f"leakage detector controls: {sum(c.passed for c in ctrl)}/{len(ctrl)} PASS")

    # ---- design ----
    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    cells = [c for c in design if c["stratum"] in STRATA]
    meta = json.loads(args.design_meta.read_text())
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    log(f"design: {len(cells)} cells in {STRATA}, "
        f"{len({c['memory_unit_locator'] for c in cells})} memories, "
        f"{len({c['task_id'] for c in cells})} tasks, "
        f"strata {dict(collections.Counter(c['stratum'] for c in cells))}")
    for c in cells:
        if not tasks[c["task_id"]].deterministic:
            raise SystemExit(f"design contains LLM-judged task {c['task_id']}")

    # ---- the written memories ----
    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    written: dict[tuple[str, str], dict] = {
        (m["representation"], m["memory_unit_locator"]): m for m in mem_rows}
    target_locs = {c["memory_unit_locator"] for c in cells}
    for rep in reps:
        have = {loc for (r, loc) in written if r == rep}
        if not target_locs <= have:
            raise SystemExit(
                f"{len(target_locs - have)} design memories have no {rep} write; "
                f"run scripts/r1_write_representations.py first")
        n_ok = sum(1 for loc in target_locs if written[(rep, loc)]["ok"])
        n_tr = sum(1 for loc in target_locs if written[(rep, loc)].get("truncated"))
        log(f"{rep}: {n_ok}/{len(target_locs)} memories usable "
            f"(ok=True); {n_tr} truncated at the token cap")

    # ---- filler pool: rebuilt by the SAME rule as the screened run ----
    fb = meta["filler"]["band"]
    max_hits = int(meta["config"]["max_pool_hits"])
    hits: dict[str, int] = collections.Counter()
    fired_by_task: dict[str, set[str]] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if not line.strip():
            continue
        d = json.loads(line)
        hits[d["task_id"]] += 1
        fired_by_task[d["task_id"]].add(d["memory_id"])
    bearing_locs = {m for tid, ms in fired_by_task.items()
                    if tasks[tid].deterministic and 1 <= hits[tid] <= max_hits
                    for m in ms}
    fire_trajs = {uloc[m]["trajectory_id"] for m in bearing_locs}
    if len(fire_trajs) >= 200:
        raise SystemExit("filler exclusion set covers every trajectory; pool empty")
    bear_trajs = {c["trajectory_id"] for c in cells if c["stratum"] == "BEARING"}
    if not bear_trajs <= fire_trajs:
        raise SystemExit("design and corpus definitions of 'bearing' disagree")
    filler_pool: dict[str, list[dict]] = collections.defaultdict(list)
    for u in units:
        if fb[0] <= u["n_tokens"] <= fb[1] and u["trajectory_id"] not in fire_trajs:
            filler_pool[u["domain"]].append(u)
    for v in filler_pool.values():
        v.sort(key=lambda u: u["memory_unit_locator"])

    # Non-vacuity FIRST: an empty pool is disjoint from everything and every
    # check below would pass while the run silently became a no-filler
    # experiment. That is exactly what k2's dry run did.
    for d in sorted({c["domain"] for c in cells}):
        if len(filler_pool.get(d, [])) < args.k_filler:
            raise SystemExit(
                f"filler pool for domain {d!r} has {len(filler_pool.get(d, []))} "
                f"units, needs >= {args.k_filler}")
    filler_locs = {u["memory_unit_locator"] for v in filler_pool.values() for u in v}
    filler_ftrajs = {u["trajectory_id"] for v in filler_pool.values() for u in v}
    target_trajs = {c["trajectory_id"] for c in cells}
    if not filler_ftrajs:
        raise SystemExit("filler pool spans ZERO trajectories; disjointness is vacuous")
    if target_locs & filler_locs:
        raise SystemExit("a target memory is in the filler pool")
    if target_trajs & filler_ftrajs:
        raise SystemExit("a target trajectory is in the filler pool")
    if bear_trajs & filler_ftrajs:
        raise SystemExit("a BEARING trajectory is in the filler pool")
    pool_sha = S.sha256_text(json.dumps(
        {d: [u["memory_unit_locator"] for u in v]
         for d, v in sorted(filler_pool.items())}, sort_keys=True))
    log(f"filler pool: { {d: len(v) for d, v in sorted(filler_pool.items())} }, "
        f"sha256 {pool_sha[:12]}")
    # THE POOL MUST BE THE SCREENED RUN'S POOL, or the WITHOUT arm is not
    # comparable and the paired design is broken. Checked against the
    # fingerprint k2 recorded, not re-derived and hoped.
    k2_fp = json.loads(
        (REPO / "results/deltau_screened/cache.condition.json").read_text())
    if pool_sha != k2_fp["filler_pool_sha256"]:
        raise SystemExit(
            f"filler pool sha256 {pool_sha[:12]} != the screened run's "
            f"{k2_fp['filler_pool_sha256'][:12]}. The WITHOUT arm would not be "
            f"comparable across representations and the paired design is void.")
    if S.sha256_text(SYSTEM) != k2_fp["system_prompt_sha256"]:
        raise SystemExit("system prompt differs from the screened run's")
    log("filler pool + system prompt MATCH the screened run's recorded fingerprint")

    def select_filler(pool: list[dict], *, k: int, task_id: str) -> list[dict]:
        order = sorted(pool, key=lambda u: u["memory_unit_locator"])
        random.Random(f"filler:{task_id}").shuffle(order)
        return order[:k]

    log(f"loading filler text for {len(filler_locs)} units ...")
    texts = load_texts(args.root, set(filler_locs))
    log(f"loaded {len(texts)} filler texts")

    # ---- build every request up front so the cost is known before spending ----
    jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    ctx_tokens: dict[str, list[int]] = collections.defaultdict(list)
    for rep in reps:
        for c in cells:
            w = written[(rep, c["memory_unit_locator"])]
            if not w["ok"]:
                # A failed write has NO memory text. Evaluating it would be
                # evaluating the empty string as a memory, which is a different
                # experiment. Recorded as excluded, with its reason, so the
                # denominator below is explicit rather than implied.
                skipped.append({"representation": rep, "cell": c,
                                "reason": w["error_code"],
                                "truncated": w.get("truncated")})
                continue
            task = tasks[c["task_id"]]
            u = uloc[c["memory_unit_locator"]]
            fil = select_filler(filler_pool[u["domain"]], k=args.k_filler,
                                task_id=task.id)
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            mem_tok = int(w["memory_tokens"])
            # Position is seeded by (task, MANIFEST memory id) -- the SAME seed
            # parts the screened run used -- so the target lands in the same
            # slot in all three representations. Seeding on the per-arm content
            # hash would move it between arms and confound representation with
            # position, which this project has already measured as a 2-in-3
            # answer change (docs/POSITION_EFFECT.md).
            tgt = MemoryUnit(u["memory_id"], u["memory_unit_locator"],
                             w["memory_text"], mem_tok, u["domain"])
            with_ctx, pos = build_context(tgt, fus,
                                          seed_parts=(task.id, u["memory_id"]))
            without_ctx, npos = build_context(None, fus,
                                              seed_parts=(task.id, "none"))
            assert npos is None
            ctx_tokens[rep].append(count_tokens(with_ctx))
            for r in range(args.replicates):
                for arm, ctx, position in (("with_memory", with_ctx, pos),
                                           ("without_memory", without_ctx, None)):
                    jobs.append({
                        "rep": rep, "cell": c, "unit": u, "task": task,
                        "written": w, "arm": arm, "replicate_id": r,
                        "position": position, "n_filler": len(fil),
                        "filler_tokens": sum(f["n_tokens"] for f in fil),
                        "memory_tokens": mem_tok,
                        "messages": [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user",
                             "content": f"{ctx}\n\n--- Question ---\n{task.question}"},
                        ],
                    })
    for rep in reps:
        q = sorted(ctx_tokens[rep])
        log(f"{rep}: WITH-arm context tokens min={q[0]} p25={q[len(q)//4]} "
            f"median={q[len(q)//2]} p75={q[3*len(q)//4]} max={q[-1]} "
            f"over {len(q)} cells")
    log(f"EXCLUDED cells (failed write, no memory text): {len(skipped)} "
        f"{dict(collections.Counter((s['representation'], s['reason']) for s in skipped))}")
    sysseen = collections.Counter(j["messages"][0]["content"] for j in jobs)
    log(f"system prompts in use: {len(sysseen)} distinct")
    log(f"PLANNED CALLS: {len(jobs)} (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        return 0

    # ---- embeddings: semantic_similarity is NON-NULLABLE ----
    # Each representation has its OWN memory text, so its own vector. Reusing
    # raw's would put raw's similarity on a summary row.
    log("embedding memories and tasks ...")
    emb = EmbeddingClient(cache_path=str(args.out / "embeddings.jsonl"))
    labelled: list[tuple[str, str]] = []
    for rep in reps:
        for loc in sorted(target_locs):
            w = written[(rep, loc)]
            if w["ok"]:
                labelled.append((f"{rep}|{loc}", w["memory_text"]))
    task_ids = sorted({c["task_id"] for c in cells})
    labelled += [(f"task|{t}", tasks[t].question) for t in task_ids]
    vmap, budget_used = embed_with_backoff(emb, labelled, EMBED_TOKEN_BUDGET)
    order = [k for k, _ in labelled]
    arr = np.asarray([vmap[k] for k in order], dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    store = args.out / "embeddings.npy"
    np.save(store, arr)
    idx = {k: i for i, k in enumerate(order)}
    sha = S.file_sha256(store)
    trunc_emb = {k: count_tokens(t) > budget_used[k] for k, t in labelled}
    log(f"embeddings {arr.shape} -> {store.name} "
        f"(truncated for embedding: {sum(trunc_emb.values())}/{len(trunc_emb)})")

    sim: dict[tuple[str, str, str], float] = {}
    for rep in reps:
        for c in cells:
            loc = c["memory_unit_locator"]
            k = f"{rep}|{loc}"
            if k in idx:
                sim[(rep, loc, c["task_id"])] = float(
                    arr[idx[k]] @ arr[idx[f"task|{c['task_id']}"]])
    # Terciles are computed PER REPRESENTATION. Prereg section 7 fixes bands by
    # tercile of the observed distribution "per benchmark"; a single pooled cut
    # across representations would put most of one arm in one band, because the
    # arms' similarity distributions differ by construction (a 225-token schema
    # embeds differently from a 7,000-token trace).
    cuts: dict[str, tuple[float, float]] = {}
    for rep in reps:
        vals = sorted(v for (r, _, _), v in sim.items() if r == rep)
        cuts[rep] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])
        log(f"{rep} similarity terciles: FAR<{cuts[rep][0]:.4f}"
            f"<=MID<{cuts[rep][1]:.4f}<=NEAR")

    def band(rep: str, s: float) -> str:
        t1, t2 = cuts[rep]
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    # ---- execute ----
    cache_path = args.out / "eval_cache.jsonl"
    guard = assert_cache_condition(cache_path, {
        "condition_ids": {r: CONDITION_ID[r] for r in sorted(reps)},
        "reader_prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": S.sha256_text(SYSTEM),
        "k_filler": args.k_filler,
        "filler_band": list(fb),
        "filler_pool_sha256": pool_sha,
        "design_cells_sha256": S.file_sha256(args.design),
        "memories_sha256": S.file_sha256(args.memories),
        "replicates": args.replicates,
        "max_tokens": args.max_tokens,
        "reasoning_effort": "low",
        "temperature": 0.0,
    })
    cache = ResponseCache(cache_path)
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                      max_concurrency=args.workers)
    results: dict[tuple, dict] = {}
    n_real = n_cached = n_err = 0
    t0 = time.monotonic()

    def run_one(j: dict):
        kf = {"benchmark": "longmemeval_v2",
              "source_item_id": j["unit"]["trajectory_id"],
              # The REPRESENTATION is in the key, and so is the per-arm content
              # hash. Two arms cannot share a row.
              "memory_repr": j["rep"],
              "memory_id": j["written"]["memory_content_id"],
              "future_task_id": j["task"].id, "arm": j["arm"],
              "retrieval_method": "oracle", "prompt_version": PROMPT_VERSION,
              "replicate_id": j["replicate_id"]}
        try:
            c, rec = client.chat(j["messages"], max_tokens=args.max_tokens,
                                 temperature=0.0, reasoning_effort="low",
                                 cache_key_fields=kf)
            return j, c, rec, None
        except ClientError as e:
            return j, None, None, f"{type(e).__name__}: {e}"

    log(f"executing {len(jobs)} calls at concurrency {args.workers} ...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_one, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            j, content, rec, err = fut.result()
            k = (j["rep"], j["unit"]["memory_unit_locator"], j["task"].id,
                 j["replicate_id"], j["arm"])
            if err is not None:
                n_err += 1
                results[k] = {"error": err, "job": j}
            else:
                if rec.cache_hit:
                    n_cached += 1
                else:
                    n_real += 1
                results[k] = {"content": content, "rec": rec, "job": j}
            if n % 250 == 0:
                el = time.monotonic() - t0
                log(f"  {n}/{len(jobs)} done (real={n_real} cached={n_cached} "
                    f"err={n_err}) {n/el*60:.0f}/min")
    wall = time.monotonic() - t0
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} "
        f"errors={n_err}")

    # ---- score + write ----
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / "cells.jsonl"
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    n_written = 0
    scored: list[dict] = []
    for rep in reps:
        for c in cells:
            loc = c["memory_unit_locator"]
            wr = written[(rep, loc)]
            if not wr["ok"]:
                continue
            task = tasks[c["task_id"]]
            u = uloc[loc]
            mtext = wr["memory_text"]
            leak = LK.detect(mtext, task.answer, memory_id=wr["memory_content_id"],
                             task_id=task.id, eval_function_spec=task.eval_function)
            s = sim[(rep, loc, task.id)]
            ek = f"{rep}|{loc}"
            for r in range(args.replicates):
                rw = results.get((rep, loc, task.id, r, "with_memory"), {})
                ro = results.get((rep, loc, task.id, r, "without_memory"), {})
                errs = [x.get("error") for x in (rw, ro) if x.get("error")]
                ow, oo = rw.get("content"), ro.get("content")
                if errs or ow is None or oo is None:
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
                rt = [x.reasoning_tokens for x in recs
                      if x.reasoning_tokens is not None]
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
                    memory_semantic_type=(wr.get("native_semantic_type")
                                          or "episodic"),
                    memory_text=mtext, memory_tokens=int(wr["memory_tokens"]),
                    memory_source_span={
                        "trajectory_id": u["trajectory_id"],
                        "start_state_index": u["start_state_index"],
                        "end_state_index": u["end_state_index"],
                        "n_states": u["n_states"],
                        "memory_unit_locator": loc,
                        "derived_from": "whole_segment"},
                    memory_writer_model=wr["writer_model"],
                    memory_writer_cluster=wr["writer_cluster"],
                    memory_writer_prompt_version=wr["prompt_version"],
                    memory_extraction_latency=wr["extraction_latency_s"],
                    memory_extraction_input_tokens=wr["extraction_input_tokens"],
                    memory_extraction_output_tokens=wr["extraction_output_tokens"],
                    embedding_model=EMBED_MODEL,
                    embedding_version=f"sophia_vllm_dim{EMBED_DIM}",
                    memory_embedding_reference={
                        "store": "embeddings.npy", "index": idx[ek],
                        "dim": EMBED_DIM, "sha256": sha,
                        "input_truncated": trunc_emb[ek],
                        "input_token_budget": budget_used[ek]},
                    future_task_id=task.id, future_task_family=task.question_type,
                    future_task_text=task.question,
                    task_embedding_reference={
                        "store": "embeddings.npy", "index": idx[f"task|{task.id}"],
                        "dim": EMBED_DIM, "sha256": sha, "input_truncated": False,
                        "input_token_budget": budget_used[f"task|{task.id}"]},
                    semantic_similarity=s, semantic_distance_band=band(rep, s),
                    retrieval_method="oracle", retrieval_rank=None, retrieval_k=None,
                    memory_tokens_retrieved=int(wr["memory_tokens"]),
                    memory_tokens_exposed=int(wr["memory_tokens"]),
                    replicate_id=r,
                    seed_or_sampling_config={"temperature": 0.0,
                                             "max_tokens": args.max_tokens,
                                             "reasoning_effort": "low", "seed": None},
                    reader_model="gpt-oss-120b", reader_cluster="metis",
                    reader_endpoint="metis:/resource_server/metis/api/v1",
                    reader_prompt_version=PROMPT_VERSION,
                    reader_endpoint_sha256=S.sanitized_base_url_hash(
                        "https://inference-api.alcf.anl.gov/resource_server/"
                        "metis/api/v1"),
                    reader_reasoning_effort="low", condition_id=CONDITION_ID[rep],
                    output_without_memory=oo, output_with_memory=ow,
                    reward_without_memory=reward_o, reward_with_memory=reward_w,
                    delta_utility=delta, robustness_confidence=None,
                    write_latency=wr["extraction_latency_s"],
                    retrieval_latency=None,
                    generation_latency=round(sum(x.latency_s for x in recs), 4),
                    end_to_end_latency=round(sum(x.latency_s for x in recs), 4),
                    embedding_calls=0, generation_calls=len(recs),
                    input_tokens=sum(x.input_tokens for x in recs),
                    output_tokens=sum(x.output_tokens for x in recs),
                    reasoning_tokens=sum(rt) if rt else None,
                    retry_count=sum(x.retry_count for x in recs),
                    error_code_if_any=code,
                    provenance={
                        "code_sha": CODE_SHA, "run_id": RUN_ID, "host": "laptop",
                        "writer": "scripts/r2_run_representations.py",
                        "target_position": job.get("position"),
                        "n_filler": job.get("n_filler"),
                        "filler_tokens": job.get("filler_tokens"),
                        "prompt_arm": "handwritten",
                        "system_prompt_sha256": S.sha256_text(SYSTEM),
                        "stratum": c["stratum"],
                        "why_stratum": c["why_stratum"],
                        "detector_fires": c["detector_fires"],
                        "task_pool_hits": c["task_pool_hits"],
                        "task_pool_size": c["task_pool_size"],
                        "n_bearing_tasks_for_this_memory":
                            c["n_bearing_tasks_for_this_memory"],
                        "is_unknown_with": unk_w, "is_unknown_without": unk_o,
                        # The pairing key. memory_id is a per-representation
                        # content hash, so it CANNOT join the arms; this can.
                        "memory_unit_locator": loc,
                        "pair_key": f"{loc}|{task.id}",
                        # Carried so an analysis can split on it without
                        # re-reading the write pass.
                        "write_finish_reason": wr.get("finish_reason"),
                        "write_truncated": bool(wr.get("truncated")),
                        "memory_writer_error_code": wr.get("error_code"),
                    },
                    license_source_reference="longmemeval_v2:Apache-2.0",
                    verifier_id=task.eval_name,
                    verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                    reward_is_continuous=False,
                    leakage_flag=(bool(leak.any_leak) if not leak.undecidable
                                  else None),
                )
                w.write_row(row)
                n_written += 1
                scored.append({"rep": rep, "stratum": c["stratum"],
                               "reward_with": reward_w, "reward_without": reward_o,
                               "delta": delta})
    log(f"wrote {n_written} rows -> {rows_path} ({w.close()})")

    ok_rows = [s for s in scored if s["delta"] is not None]
    by = collections.defaultdict(list)
    for s in ok_rows:
        by[(s["rep"], s["stratum"])].append(s)
    summary = {
        "_what": "R2 evaluation of summary + structured on the screened "
                 "BEARING/MATCHED_CONTROL cells",
        "run_at_utc": utc_now(), "run_id": RUN_ID, "wall_clock_s": round(wall, 2),
        "representations": reps,
        "condition_ids": {r: CONDITION_ID[r] for r in reps},
        "reader_prompt_version": PROMPT_VERSION,
        "replicates": args.replicates,
        "n_design_cells": len(cells),
        "n_cells_evaluated": {r: sum(1 for c in cells
                                     if written[(r, c["memory_unit_locator"])]["ok"])
                              for r in reps},
        "n_cells_excluded_failed_write": {
            r: sum(1 for s in skipped if s["representation"] == r) for r in reps},
        "excluded_detail": [{"representation": s["representation"],
                             "memory_unit_locator": s["cell"]["memory_unit_locator"],
                             "task_id": s["cell"]["task_id"],
                             "stratum": s["cell"]["stratum"],
                             "reason": s["reason"], "truncated": s["truncated"]}
                            for s in skipped],
        "planned_calls": len(jobs), "real_endpoint_calls": n_real,
        "cache_hits": n_cached, "errors": n_err, "rows_written": n_written,
        "cache_condition_guard": guard,
        "filler_pool_sha256": pool_sha,
        "filler_pool_matches_screened_run": True,
        "context_tokens_with_arm": {
            r: {"min": sorted(ctx_tokens[r])[0],
                "median": sorted(ctx_tokens[r])[len(ctx_tokens[r]) // 2],
                "max": sorted(ctx_tokens[r])[-1]} for r in reps},
        "similarity_terciles": {r: {"far_below": cuts[r][0],
                                    "near_at_or_above": cuts[r][1]} for r in reps},
        "per_representation_stratum_raw": {
            f"{k[0]}:{k[1]}": {
                "n_rows": len(v),
                "mean_reward_with": float(np.mean([x["reward_with"] for x in v])),
                "mean_reward_without": float(np.mean([x["reward_without"] for x in v])),
                "mean_delta": float(np.mean([x["delta"] for x in v]))}
            for k, v in sorted(by.items())},
        "_note": "row-level means, a run-health readout. The per-CELL paired analysis "
                 "is scripts/r3_analyze_representations.py.",
    }
    (args.out / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    log(json.dumps(summary["per_representation_stratum_raw"], indent=2))
    log(f"real={n_real} cached={n_cached} errors={n_err} rows={n_written}")
    return 0


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
RUN_ID = f"r2_repr_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())

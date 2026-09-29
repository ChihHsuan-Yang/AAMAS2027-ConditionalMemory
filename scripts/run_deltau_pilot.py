#!/usr/bin/env python3
"""G2: the first real dU cells on LongMemEval-V2, raw representation.

Design, and why each choice is what it is
-----------------------------------------
**Target/filler pools are DISJOINT trajectories.** Filler is drawn from a
reserved set of trajectories that no target memory ever comes from. This is
not tidiness: it makes the filler a pure function of ``task_id``, so the
WITHOUT arm is genuinely identical across every memory paired with a task,
which is exactly the condition ``ANALYSIS_PREREGISTRATION.md`` section 2 needs
for F_empty to be a floor. (``p1mem.cells.select_filler`` instead filters the
target out of the pool by id, which changes the shuffle -- excluding a unit
that is not even among the chosen K still perturbs 3 of 5 filler slots. Its
docstring's "every memory sees the same filler" is false as written.)

**Target position is seeded by (task_id, memory_id) and NOT by replicate.**
Prereg section 2 defines F_exec as variation "with everything else fixed". If
position moved between replicates, F_exec would confound a position effect
with execution noise. Replicates are therefore byte-identical requests and
their spread is execution noise by construction.

**The WITHOUT arm is executed independently for every (memory, task,
replicate).** Its inputs are identical across memories within a task, so the
spread across memories is pure execution noise -- the free floor of section 2.
Amendment A1.4 warns that a cache serving one generation everywhere makes this
0.000 by construction; the cache key carries ``memory_id`` and ``replicate_id``
so each is a distinct real call, and the run asserts the realised call count
against the expected one.

No new definitions are invented here: labels, floors and flips are computed by
D's analysis layer from the rows this script writes.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
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

PROMPT_VERSION = "p1_deltau_raw_v1"
CONDITION_ID = "lmev2_raw_metis_gptoss120b_v1"
#: Sophia's SFR embedding endpoint returns HTTP 500 on long inputs. The budget
#: below is counted with the OFFICIAL QWEN tokenizer, which is NOT the
#: embedding model's tokenizer (SFR-Embedding-Mistral). The two disagree on
#: AXTree text, so a Qwen count is only a PROXY for what the embedding server
#: sees: measured on real memory text, a 3,400-Qwen-token budget still failed
#: 3 of 10 inputs, while 2,400 passed 10 of 10. 2,000 is used for margin, and
#: :func:`embed_with_backoff` re-truncates and retries rather than letting one
#: long unit kill the run -- an absent embedding would become a null in a
#: non-nullable field.
EMBED_TOKEN_BUDGET = 2000
EMBED_MIN_BUDGET = 500


def log(msg: str) -> None:
    print(f"[{utc_now()}] {msg}", flush=True)


# ---------------------------------------------------------------- sampling
def sample_memories(units: list[dict], *, n: int, lo: int, hi: int,
                    n_filler_trajs: int, seed: int
                    ) -> tuple[list[dict], dict[str, list[dict]]]:
    """Pick n target units and a disjoint per-domain filler pool.

    The size filter is computed from the trajectory alone (token count), never
    from content or informativeness -- MEMORY_PROTOCOL section 1 forbids a
    "most informative span" rule, and a content filter would be one.
    """
    elig = [u for u in units if lo <= (u.get("n_tokens") or 0) <= hi]
    by_traj: dict[str, list[dict]] = collections.defaultdict(list)
    for u in elig:
        by_traj[u["trajectory_id"]].append(u)
    dom_of = {t: v[0]["domain"] for t, v in by_traj.items()}

    rng = random.Random(seed)
    filler_pool: dict[str, list[dict]] = {}
    target_trajs: list[str] = []
    for d in sorted({*dom_of.values()}):
        ts = sorted([t for t in by_traj if dom_of[t] == d])
        rng.shuffle(ts)
        fill, targ = ts[:n_filler_trajs], ts[n_filler_trajs:]
        filler_pool[d] = sorted(
            [u for t in fill for u in by_traj[t]],
            key=lambda u: u["memory_unit_locator"])
        target_trajs.extend(targ)

    rng.shuffle(target_trajs)
    chosen: list[dict] = []
    for t in target_trajs:
        if len(chosen) >= n:
            break
        # One unit per trajectory: n views of one episode is not n memories.
        chosen.append(rng.choice(sorted(by_traj[t],
                                        key=lambda u: u["memory_unit_locator"])))
    if len(chosen) < n:
        raise RuntimeError(
            f"only {len(chosen)} target trajectories available in token band "
            f"[{lo},{hi}] after reserving {n_filler_trajs} filler trajectories "
            f"per domain; asked for {n}. Widen the band or reserve fewer.")
    return sorted(chosen, key=lambda u: u["memory_unit_locator"]), filler_pool


def select_filler(pool: list[dict], *, k: int, task_id: str) -> list[dict]:
    """K filler units, a pure function of task_id.

    The pool does not depend on the target, so unlike ``cells.select_filler``
    the draw cannot shift when the target changes.
    """
    order = sorted(pool, key=lambda u: u["memory_unit_locator"])
    rng = random.Random(f"filler:{task_id}")
    rng.shuffle(order)
    return order[:k]


# ---------------------------------------------------------------- rendering
def render_text(units: list[dict], texts: dict[str, str],
                target: dict | None, *, task_id: str) -> tuple[str, int | None]:
    fillers = [MemoryUnit(u["memory_id"], u["memory_unit_locator"],
                          texts[u["memory_unit_locator"]], u["n_tokens"],
                          u["domain"]) for u in units]
    tgt = None
    if target is not None:
        tgt = MemoryUnit(target["memory_id"], target["memory_unit_locator"],
                         texts[target["memory_unit_locator"]],
                         target["n_tokens"], target["domain"])
    # Seeded by (task, memory) only -- NOT replicate, so replicates are
    # byte-identical and F_exec is pure execution noise.
    return build_context(tgt, fillers,
                         seed_parts=(task_id, target["memory_id"] if target else "none"))


def load_texts(root: Path, locators: set[str]) -> dict[str, str]:
    """Re-render unit text from the trajectories with the adapter's renderers."""
    need_trajs = {loc.split(":")[0] for loc in locators}
    out: dict[str, str] = {}
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] not in need_trajs:
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
            f"{sorted(missing)[:5]}. A partial join must abort -- half a join "
            f"still looks like success.")
    return out


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


def embed_with_backoff(emb: "EmbeddingClient", labelled: list[tuple[str, str]],
                       budget: int) -> tuple[dict[str, list[float]], dict[str, int]]:
    """Embed one input at a time, halving the budget on a server rejection.

    The endpoint's real limit is in ITS tokenizer, not ours, so our budget is a
    proxy and a single over-long unit would otherwise abort the whole run.
    Every successful budget is recorded per input so the row can state what was
    actually embedded, rather than implying the full text was.
    """
    from p1mem.client import EndpointError  # noqa: PLC0415

    vecs: dict[str, list[float]] = {}
    used: dict[str, int] = {}
    for key, text in labelled:
        b = budget
        while True:
            t, _tr = truncate_to_tokens(text, b)
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
                log(f"  embed retry for {key[:24]}: budget -> {b} tokens")
    return vecs, used


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--n-memories", type=int, default=60)
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--k-filler", type=int, default=6)
    ap.add_argument("--tok-lo", type=int, default=1500)
    ap.add_argument("--tok-hi", type=int, default=5000)
    ap.add_argument("--filler-trajs", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=3000)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "deltau_pilot")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    log(f"verifying vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    log("writer blindness: PASSED")

    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl").read_text().splitlines() if l.strip()]
    pairs = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_pairs_small_seed20261008.jsonl").read_text().splitlines() if l.strip()]
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}

    targets, filler_pool = sample_memories(
        units, n=args.n_memories, lo=args.tok_lo, hi=args.tok_hi,
        n_filler_trajs=args.filler_trajs, seed=args.seed)
    tgt_ids = {u["memory_id"] for u in targets}
    tgt_trajs = {u["trajectory_id"] for u in targets}
    fill_trajs = {u["trajectory_id"] for v in filler_pool.values() for u in v}
    assert not (tgt_trajs & fill_trajs), (
        "target and filler trajectory pools overlap; filler would leak a target")
    log(f"sampled {len(targets)} target memories from {len(tgt_trajs)} trajectories; "
        f"filler pool {[(d, len(v)) for d, v in sorted(filler_pool.items())]} "
        f"from {len(fill_trajs)} disjoint trajectories")

    by_mem = collections.defaultdict(list)
    for p in pairs:
        if p["memory_id"] in tgt_ids:
            by_mem[p["memory_id"]].append(p)
    cell_specs = [(u, p) for u in targets for p in sorted(by_mem[u["memory_id"]],
                                                          key=lambda p: p["task_id"])]
    log(f"{len(cell_specs)} (memory, task) cells; "
        f"{len({p['task_id'] for _u, p in cell_specs})} distinct tasks")

    # ---- text
    locators = {u["memory_unit_locator"] for u in targets}
    locators |= {u["memory_unit_locator"] for v in filler_pool.values() for u in v}
    log(f"loading text for {len(locators)} units from trajectories.jsonl ...")
    texts = load_texts(args.root, locators)
    log(f"loaded {len(texts)} unit texts")

    # ---- build every request up front so the call count is known before spending
    jobs: list[dict[str, Any]] = []
    ctx_tokens: list[int] = []
    for u, p in cell_specs:
        task = tasks[p["task_id"]]
        fil = select_filler(filler_pool[u["domain"]], k=args.k_filler,
                            task_id=task.id)
        assert u["memory_id"] not in {f["memory_id"] for f in fil}
        with_ctx, pos = render_text(fil, texts, u, task_id=task.id)
        without_ctx, npos = render_text(fil, texts, None, task_id=task.id)
        assert npos is None
        for rep in range(args.replicates):
            for arm, ctx, position in (("with_memory", with_ctx, pos),
                                       ("without_memory", without_ctx, None)):
                jobs.append({
                    "unit": u, "pair": p, "task": task, "arm": arm,
                    "replicate_id": rep, "position": position,
                    "n_filler": len(fil),
                    "filler_tokens": sum(f["n_tokens"] for f in fil),
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user",
                         "content": f"{ctx}\n\n--- Question ---\n{task.question}"},
                    ],
                })
        ctx_tokens.append(count_tokens(with_ctx))

    q = sorted(ctx_tokens)
    log(f"WITH-arm context tokens: min={q[0]} p25={q[len(q)//4]} median={q[len(q)//2]} "
        f"p75={q[3*len(q)//4]} max={q[-1]}  (K={args.k_filler} filler units)")
    log(f"PLANNED CALLS: {len(jobs)}  (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} calls exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        return 0

    # ---- embeddings (semantic_similarity is non-nullable)
    log("embedding memories and tasks ...")
    emb = EmbeddingClient(cache_path=args.out / "embeddings.jsonl")
    mem_texts = {u["memory_id"]: texts[u["memory_unit_locator"]] for u in targets}
    task_ids = sorted({p["task_id"] for _u, p in cell_specs})
    mem_ids = sorted(mem_texts)
    labelled = ([(m, mem_texts[m]) for m in mem_ids]
                + [(t, tasks[t].question) for t in task_ids])
    vmap, budget_used = embed_with_backoff(emb, labelled, EMBED_TOKEN_BUDGET)
    vecs = [vmap[k] for k in mem_ids + task_ids]
    arr = np.asarray(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    store = args.out / "embeddings.npy"
    np.save(store, arr)
    idx = {k: i for i, k in enumerate(mem_ids + task_ids)}
    sha = S.file_sha256(store)
    mem_trunc = {m: count_tokens(mem_texts[m]) > budget_used[m] for m in mem_ids}
    log(f"embeddings: {arr.shape} -> {store.name}  "
        f"(truncated for embedding: {sum(mem_trunc.values())}/{len(mem_trunc)} memories)")

    sim = {(m, t): float(arr[idx[m]] @ arr[idx[t]]) for m in mem_ids for t in task_ids}
    vals = sorted({sim[(u['memory_id'], p['task_id'])] for u, p in cell_specs})
    t1, t2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    log(f"similarity terciles: FAR<{t1:.4f}<=MID<{t2:.4f}<=NEAR")

    def band(s: float) -> str:
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    # ---- execute
    cache = ResponseCache(args.out / "cache.jsonl")
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                      max_concurrency=args.workers)
    results: dict[tuple, dict] = {}
    n_real = n_cached = n_err = 0
    t0 = time.monotonic()

    def run_one(j: dict) -> tuple[dict, str | None, Any, str | None]:
        kf = {
            "benchmark": "longmemeval_v2",
            "source_item_id": j["unit"]["trajectory_id"],
            "memory_repr": "raw",
            "memory_id": j["unit"]["memory_id"],
            "future_task_id": j["task"].id,
            "arm": j["arm"],
            "retrieval_method": "oracle",
            "prompt_version": PROMPT_VERSION,
            "replicate_id": j["replicate_id"],
        }
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
            k = (j["unit"]["memory_id"], j["task"].id, j["replicate_id"], j["arm"])
            if err is not None:
                n_err += 1
                results[k] = {"error": err, "job": j}
            else:
                if rec.cache_hit:
                    n_cached += 1
                else:
                    n_real += 1
                results[k] = {"content": content, "rec": rec, "job": j}
            if n % 200 == 0:
                log(f"  {n}/{len(jobs)} done (real={n_real} cached={n_cached} err={n_err})")
    wall = time.monotonic() - t0
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} errors={n_err}")

    # ---- score + write rows
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import extract_boxed_answer, is_unknown

    rows_path = args.out / "cells.jsonl"
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    n_written = 0
    scored: list[dict] = []
    for u, p in cell_specs:
        task = tasks[p["task_id"]]
        mid = u["memory_id"]
        mtext = texts[u["memory_unit_locator"]]
        leak = LK.detect(mtext, task.answer, memory_id=mid, task_id=task.id,
                         eval_function_spec=task.eval_function)
        s = sim[(mid, task.id)]
        for rep in range(args.replicates):
            rw = results.get((mid, task.id, rep, "with_memory"), {})
            ro = results.get((mid, task.id, rep, "without_memory"), {})
            errs = [r.get("error") for r in (rw, ro) if r.get("error")]
            ow, oo = rw.get("content"), ro.get("content")
            if errs or ow is None or oo is None:
                reward_w = reward_o = delta = None
                code = "endpoint_error"
            else:
                reward_w = float(task.score(extract_boxed_answer(ow)))
                reward_o = float(task.score(extract_boxed_answer(oo)))
                delta = reward_w - reward_o
                code = None
            recs = [r["rec"] for r in (rw, ro) if r.get("rec") is not None]
            rt = [r.reasoning_tokens for r in recs if r.reasoning_tokens is not None]
            job = (rw or ro).get("job", {})
            row = w.build(
                benchmark="longmemeval_v2",
                benchmark_version=lmev2.UPSTREAM_COMMIT,
                source_episode_id=u["trajectory_id"],
                source_episode_metadata={"domain": u["domain"],
                                         "environment": u["environment"],
                                         "outcome": u["outcome"], "url": u["url"],
                                         "memory_unit_locator": u["memory_unit_locator"]},
                memory_representation="raw",
                memory_semantic_type="episodic",
                memory_text=mtext,
                memory_tokens=u["n_tokens"],
                memory_source_span={"trajectory_id": u["trajectory_id"],
                                    "start_state_index": u["start_state_index"],
                                    "end_state_index": u["end_state_index"],
                                    "n_states": u["n_states"]},
                memory_writer_model="none:deterministic_span",
                memory_writer_cluster="none:deterministic_span",
                memory_writer_prompt_version="page_visit_segmentation_v1",
                memory_extraction_latency=None,
                memory_extraction_input_tokens=None,
                memory_extraction_output_tokens=None,
                embedding_model=EMBED_MODEL,
                embedding_version=f"sophia_vllm_dim{EMBED_DIM}",
                memory_embedding_reference={"store": "embeddings.npy",
                                            "index": idx[mid], "dim": EMBED_DIM,
                                            "sha256": sha,
                                            "input_truncated": mem_trunc[mid],
                                            "input_token_budget": budget_used[mid]},
                future_task_id=task.id,
                future_task_family=task.question_type,
                future_task_text=task.question,
                task_embedding_reference={"store": "embeddings.npy",
                                          "index": idx[task.id], "dim": EMBED_DIM,
                                          "sha256": sha, "input_truncated": False,
                                          "input_token_budget": budget_used[task.id]},
                semantic_similarity=s,
                semantic_distance_band=band(s),
                retrieval_method="oracle",
                retrieval_rank=None, retrieval_k=None,
                memory_tokens_retrieved=u["n_tokens"],
                memory_tokens_exposed=u["n_tokens"],
                replicate_id=rep,
                seed_or_sampling_config={"temperature": 0.0,
                                         "max_tokens": args.max_tokens,
                                         "reasoning_effort": "low", "seed": None},
                reader_model="gpt-oss-120b",
                reader_cluster="metis",
                reader_endpoint="metis:/resource_server/metis/api/v1",
                reader_prompt_version=PROMPT_VERSION,
                reader_reasoning_effort="low",
                condition_id=CONDITION_ID,
                output_without_memory=oo, output_with_memory=ow,
                reward_without_memory=reward_o, reward_with_memory=reward_w,
                delta_utility=delta,
                robustness_confidence=None,
                write_latency=None, retrieval_latency=None,
                generation_latency=round(sum(r.latency_s for r in recs), 4),
                end_to_end_latency=round(sum(r.latency_s for r in recs), 4),
                embedding_calls=0,
                generation_calls=len(recs),
                input_tokens=sum(r.input_tokens for r in recs),
                output_tokens=sum(r.output_tokens for r in recs),
                reasoning_tokens=sum(rt) if rt else None,
                retry_count=sum(r.retry_count for r in recs),
                error_code_if_any=code,
                provenance={"code_sha": CODE_SHA, "config_sha256": CONFIG_SHA,
                            "run_id": RUN_ID, "host": "laptop",
                            "writer": "scripts/run_deltau_pilot.py",
                            "target_position": job.get("position"),
                            "n_filler": job.get("n_filler"),
                            "filler_tokens": job.get("filler_tokens")},
                license_source_reference="longmemeval_v2:Apache-2.0",
                verifier_id=task.eval_name,
                verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                reward_is_continuous=False,
                leakage_flag=bool(leak.any_leak) if not leak.undecidable else None,
            )
            w.write_row(row)
            n_written += 1
            scored.append({"memory_id": mid, "task_id": task.id, "replicate": rep,
                           "reward_with": reward_w, "reward_without": reward_o,
                           "delta": delta, "unknown_with": is_unknown(
                               extract_boxed_answer(ow)) if ow else None})
    log(f"wrote {n_written} rows -> {rows_path} ({w.close()})")

    summary = {
        "run_at_utc": utc_now(), "run_id": RUN_ID, "wall_clock_s": round(wall, 2),
        "n_memories": len(targets), "n_cells": len(cell_specs),
        "n_distinct_tasks": len({p["task_id"] for _u, p in cell_specs}),
        "replicates": args.replicates, "k_filler": args.k_filler,
        "token_band": [args.tok_lo, args.tok_hi],
        "planned_calls": len(jobs),
        "real_endpoint_calls": n_real, "cache_hits": n_cached, "errors": n_err,
        "context_tokens_with_arm": {"min": q[0], "p25": q[len(q)//4],
                                    "median": q[len(q)//2],
                                    "p75": q[3*len(q)//4], "max": q[-1]},
        "similarity_terciles": {"far_below": t1, "near_at_or_above": t2},
        "embedding_truncated_memories": int(sum(mem_trunc.values())),
        "rows_written": n_written,
        "mean_reward_with": float(np.mean([s["reward_with"] for s in scored
                                           if s["reward_with"] is not None])),
        "mean_reward_without": float(np.mean([s["reward_without"] for s in scored
                                              if s["reward_without"] is not None])),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    log(json.dumps(summary, indent=2))
    return 0


import subprocess  # noqa: E402

CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
CONFIG_SHA = S.file_sha256(REPO / "configs/endpoint_primary.json")
RUN_ID = f"g2_deltau_pilot_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())

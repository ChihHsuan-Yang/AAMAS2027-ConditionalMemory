#!/usr/bin/env python3
"""X2: representations compared at a FIXED TOTAL CONTEXT (reviewer request).

Derived from scripts/x1_position_session.py (itself K2 with targeted changes),
keeping every safeguard. Question answered: does Raw still beat compressed
memory when a long raw memory must DISPLACE other context, as in deployment?

Design, per (memory, task) cell of the representation subset (BEARING and
MATCHED_CONTROL cells of memories with valid Summary AND Structured texts):
* T = tokens(base filler, K units) + tokens(Raw memory)  -- the Raw arm's size.
* Arms: raw, summary, structured, trunc_last_matched (last N Raw tokens,
  N = that memory's Summary length), and WITHOUT.
* The memory sits at the SAME seeded position among the K base filler as in
  K2 (seed: task, memory). Every arm except Raw is then PADDED after the base
  context with further bearing-disjoint filler units, the last one trimmed,
  until its memory+filler tokens reach T. The WITHOUT arm is padded to T too.
  So all arms of a cell carry the same token count; padding is the only
  difference between them.
* Cache key: memory_repr = arm, memory_id = sha256(memory text), as in the
  length-control run, so arms can never share a cached response.

Done marker: <out>/summary.json. Resumable through <out>/cache.jsonl.

--- original K2 header follows ---
K2: execute the K1 screened three-stratum design. THE MAIN RUN.

Pinned arm, unchanged from the pilot's hand-written arm:
metis / gpt-oss-120b / reasoning_effort=low / temperature=0 / max_tokens=512 /
concurrency 16 / reader_prompt_version = p1_deltau_raw_v1.

Held fixed from ``scripts/run_deltau_pilot.py`` -- each for a stated reason:

* **Target position seeded by (task_id, memory_id), NOT replicate.** Prereg
  section 2 defines F_exec as variation "with everything else fixed"; if
  position moved between replicates, F_exec would confound a position effect
  with execution noise. Replicates are byte-identical requests.
* **The WITHOUT arm is re-generated per (memory, task, replicate).** Its
  inputs are identical across memories within a task, so its spread is the
  free F_empty floor of prereg section 2 -- but ONLY if it is really
  re-generated. Amendment A1.4: a cache serving one generation everywhere
  makes F_empty exactly 0.000 by construction and every dU trivially clears
  it. ``memory_id`` and ``replicate_id`` are in the cache key.
* **Filler is a pure function of task_id**, drawn from trajectories DISJOINT
  from every trajectory hosting any bearing memory, so filler can never carry
  a bearing target's episode. Asserted in code (``--assert-filler-disjoint``),
  not left to the pool construction staying correct.
* **Deterministically-scored questions only.** ``FutureTask.score()`` raises
  for LLM-judged ones rather than returning a default.

Every row carries ``provenance.stratum`` so the three strata are separable in
analysis without re-deriving the screen.
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

PROMPT_VERSION = "p1_deltau_raw_v1"          # hand-written arm, as in deltau_pilot
CONDITION_ID = "lmev2_metis_gptoss120b_fixedctx_v1"
#: memory_representation is a CLOSED enum; a truncated span is extractive, so raw
REPR_OF_ARM = {"raw": "raw", "summary": "summary", "structured": "structured",
               "trunc_last_matched": "raw"}
EMBED_TOKEN_BUDGET = 2000
EMBED_MIN_BUDGET = 500


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


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
                        f"refusing to write a null into non-nullable semantic_similarity")
                log(f"  embed retry {key[:24]}: budget -> {b}")
    return vecs, used


def assert_cache_condition(cache_path: Path, fingerprint: dict) -> dict:
    """Refuse to reuse a cache written under a DIFFERENT context configuration.

    THE HAZARD, measured not imagined: ``cache.KEY_FIELDS`` is
    (benchmark, source_item_id, memory_repr, memory_id, future_task_id, arm,
    retrieval_method, model_id, cluster, prompt_version, decoding_params,
    replicate_id). It does **not** contain the number of filler units, the
    filler pool, or any hash of the rendered context. The pilot rendered K=6
    filler drawn from a 12-trajectory-per-domain reservation; this run renders
    K=4 drawn from a bearing-disjoint 50-trajectory pool. Those produce
    **different context bytes under an identical cache key**.

    So the only thing separating the two conditions is that they write to
    different cache FILES -- a property of an argument default, not a checked
    invariant. ``condition_id`` cannot be added to the key (make_key rejects
    unknown fields, correctly), and adding a required field to the shared
    KEY_FIELDS would break every other caller.

    This writes a fingerprint of the context-determining configuration beside
    the cache and requires it to match on reuse. An existing cache with a
    different fingerprint RAISES rather than serving hits from another
    condition.
    """
    side = cache_path.with_suffix(".condition.json")
    if side.exists():
        prev = json.loads(side.read_text())
        if prev != fingerprint:
            diff = {k: (prev.get(k), fingerprint.get(k))
                    for k in set(prev) | set(fingerprint)
                    if prev.get(k) != fingerprint.get(k)}
            raise SystemExit(
                f"cache at {cache_path} was written under a DIFFERENT context "
                f"configuration; reusing it would serve responses generated from "
                f"different context bytes under an identical cache key.\n"
                f"  differing fields (stored, current): {json.dumps(diff, indent=2)}\n"
                f"  fix: point --out at a fresh directory.")
        log(f"cache condition fingerprint MATCHES prior run at {side.name}")
    else:
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps(fingerprint, indent=2, sort_keys=True))
        log(f"cache condition fingerprint written -> {side.name}")
    n_prior = sum(1 for _ in cache_path.open()) if cache_path.exists() else 0
    log(f"cache at {cache_path.name}: {n_prior} prior entries")
    return {"fingerprint": fingerprint, "sidecar": str(side),
            "n_prior_cache_entries": n_prior}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--design-meta", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--k-filler", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=6000)
    ap.add_argument("--out", type=Path, default=REPO / "results/x2_fixed_context")
    ap.add_argument("--strata", default="BEARING,MATCHED_CONTROL")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--memories", type=Path,
                    default=REPO / "results/ledgers/repro/repr_scaleup/memories_slim.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    log(f"verifying vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    log("writer blindness: PASSED")
    ok, ctrl = LK.controls_summary()
    if not ok:
        raise SystemExit("leakage detector controls FAILED")
    log(f"leakage detector controls: {sum(r.passed for r in ctrl)}/{len(ctrl)} PASS")

    cells = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    keep = set(args.strata.split(","))
    cells = [dict(c, replicates=args.replicates) for c in cells if c["stratum"] in keep]
    if not cells:
        raise SystemExit(f"no design cells in strata {sorted(keep)}")
    # model-written texts; keep only memories with valid Summary AND Structured
    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines() if l.strip()]
    written: dict[tuple[str, str], str] = {}
    for r in mem_rows:
        if r["representation"] in ("summary", "structured") and r["ok"] and r["memory_text"]:
            written[(r["memory_unit_locator"], r["representation"])] = r["memory_text"]
    mem_meta = {(r["memory_unit_locator"], r["representation"]): r for r in mem_rows
                if r["representation"] in ("summary", "structured") and r["ok"]}
    ok_locs = {loc for (loc, rp) in written if rp == "summary"} & \
              {loc for (loc, rp) in written if rp == "structured"}
    n_before = len(cells)
    cells = [c for c in cells if c["memory_unit_locator"] in ok_locs]
    log(f"representation subset: {len(cells)} of {n_before} cells "
        f"({len({c['memory_unit_locator'] for c in cells})} memories with valid "
        f"Summary and Structured texts)")
    meta = json.loads(args.design_meta.read_text())
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    log(f"design: {len(cells)} cells, "
        f"{len({c['memory_unit_locator'] for c in cells})} memories, "
        f"{len({c['task_id'] for c in cells})} tasks, "
        f"strata {dict(collections.Counter(c['stratum'] for c in cells))}")

    for c in cells:
        if not tasks[c["task_id"]].deterministic:
            raise SystemExit(f"design contains LLM-judged task {c['task_id']}")

    # ---- filler pool: trajectories disjoint from EVERY bearing trajectory ----
    # DEFECT FOUND BY THE DRY RUN, recorded rather than quietly fixed: the first
    # version excluded every trajectory with ANY fired leakage cell. That is all
    # 200 of 200 -- the as-shipped detector fires somewhere on every trajectory
    # (PAIRING_VERDICT section 1: the literal "A" appears in 60 of 60 memory
    # texts). The pool came out EMPTY, and the disjointness assertion below
    # PASSED on it, because the empty set is disjoint from everything. Two
    # defects: the wrong exclusion set, and a control that could not fail.
    # The correct exclusion set is trajectories hosting a memory that BEARS on
    # some discriminative task -- 61 of 200, computed the same way K1 did.
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
    log(f"bearing memories corpus-wide: {len(bearing_locs)} on {len(fire_trajs)} "
        f"trajectories (excluded from filler)")
    if len(fire_trajs) >= 200:
        raise SystemExit(
            f"filler exclusion set covers {len(fire_trajs)} of 200 trajectories; "
            f"the pool would be empty. This is the dry-run defect recurring.")
    # bearing trajectories, recomputed from the design's own definition
    bear_trajs = {c["trajectory_id"] for c in cells if c["stratum"] == "BEARING"}
    if not bear_trajs <= fire_trajs:
        raise SystemExit(
            f"{len(bear_trajs - fire_trajs)} trajectories carry a BEARING cell in the "
            f"design but are not in the corpus-wide bearing set; the two definitions "
            f"of 'bearing' disagree and filler could leak a bearing target")
    filler_pool: dict[str, list[dict]] = collections.defaultdict(list)
    for u in units:
        if fb[0] <= u["n_tokens"] <= fb[1] and u["trajectory_id"] not in fire_trajs:
            filler_pool[u["domain"]].append(u)
    for v in filler_pool.values():
        v.sort(key=lambda u: u["memory_unit_locator"])
    log(f"filler pool: { {d: len(v) for d, v in sorted(filler_pool.items())} } from "
        f"{len({u['trajectory_id'] for v in filler_pool.values() for u in v})} trajectories")

    target_locs = {c["memory_unit_locator"] for c in cells}
    target_trajs = {c["trajectory_id"] for c in cells}
    filler_locs = {u["memory_unit_locator"] for v in filler_pool.values() for u in v}
    filler_ftrajs = {u["trajectory_id"] for v in filler_pool.values() for u in v}
    # ASSERTED, not assumed: filler must not carry a target's episode at all.
    # The non-vacuity guard comes FIRST. An empty filler pool is disjoint from
    # everything, so the three checks below would all pass while the run
    # silently became a no-filler experiment -- which is exactly what the dry
    # run did. A control that cannot fail is not a control.
    need_domains = {c["domain"] for c in cells}
    for d in sorted(need_domains):
        if len(filler_pool.get(d, [])) < args.k_filler:
            raise SystemExit(
                f"filler pool for domain {d!r} has {len(filler_pool.get(d, []))} units, "
                f"needs >= {args.k_filler}. Refusing to run: an empty or short pool "
                f"passes every disjointness check vacuously.")
    if not filler_ftrajs:
        raise SystemExit("filler pool spans ZERO trajectories; disjointness is vacuous")
    if target_locs & filler_locs:
        raise SystemExit("a target memory is in the filler pool")
    if target_trajs & filler_ftrajs:
        raise SystemExit(
            f"{len(target_trajs & filler_ftrajs)} trajectories are in BOTH the target "
            f"and filler pools; filler could leak a target's own episode")
    if bear_trajs & filler_ftrajs:
        raise SystemExit("a BEARING trajectory is in the filler pool")
    log(f"filler/target disjointness ASSERTED: 0 shared locators, 0 shared trajectories "
        f"({len(target_trajs)} target vs {len(filler_ftrajs)} filler trajectories)")

    def select_filler(pool: list[dict], *, k: int, task_id: str) -> list[dict]:
        order = sorted(pool, key=lambda u: u["memory_unit_locator"])
        random.Random(f"filler:{task_id}").shuffle(order)
        return order[:k]

    # ---- text ----
    need = set(target_locs) | filler_locs
    log(f"loading text for {len(need)} units ...")
    texts = load_texts(args.root, need)
    log(f"loaded {len(texts)} unit texts")

    # ---- build every request up front so the call count is known before spending ----
    jobs: list[dict[str, Any]] = []
    ctx_tokens: list[int] = []
    from p1mem.cells import render_memory  # noqa: PLC0415
    def fit_tail(text: str, budget: int) -> str:
        """Longest suffix of ``text`` within ``budget`` tokens (content-blind)."""
        if count_tokens(text) <= budget:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if count_tokens(text[-mid:]) <= budget:
                lo = mid
            else:
                hi = mid - 1
        return text[-lo:] if lo else ""

    def padded(base_ctx: str, n_base_units: int, pad_pool: list[dict],
               need_tokens: int) -> tuple[str, int, int]:
        """Append filler units after ``base_ctx`` until ``need_tokens`` filler
        tokens are added; the last unit is trimmed (head kept) to fit."""
        parts, got = [], 0
        for f in pad_pool:
            if got >= need_tokens:
                break
            t = texts[f["memory_unit_locator"]]
            n = count_tokens(t)
            if got + n > need_tokens:
                t, _ = truncate_to_tokens(t, need_tokens - got)
                n = count_tokens(t)
            mu = MemoryUnit(f["memory_id"], f["memory_unit_locator"], t, n, f["domain"])
            parts.append(render_memory(mu, n_base_units + len(parts) + 1))
            got += n
        if got < need_tokens - 50:
            raise SystemExit(f"padding pool exhausted: {got} of {need_tokens} tokens")
        return (base_ctx + ("\n\n" + "\n\n".join(parts) if parts else ""),
                got, len(parts))

    ARMS = ("raw", "summary", "structured", "trunc_last_matched")
    mem_text: dict[tuple[str, str], str] = {}
    for c in cells:
        loc = c["memory_unit_locator"]
        raw = texts[loc]
        mem_text[(loc, "raw")] = raw
        mem_text[(loc, "summary")] = written[(loc, "summary")]
        mem_text[(loc, "structured")] = written[(loc, "structured")]
        mem_text[(loc, "trunc_last_matched")] = fit_tail(
            raw, count_tokens(written[(loc, "summary")]))
    for c in cells:
        task = tasks[c["task_id"]]
        u = uloc[c["memory_unit_locator"]]
        loc = u["memory_unit_locator"]
        order = sorted(filler_pool[u["domain"]], key=lambda x: x["memory_unit_locator"])
        random.Random(f"filler:{task.id}").shuffle(order)
        fil, pad_pool = order[:args.k_filler], order[args.k_filler:]
        assert u["memory_id"] not in {f["memory_id"] for f in fil + pad_pool}
        fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                          texts[f["memory_unit_locator"]], f["n_tokens"], f["domain"])
               for f in fil]
        base_tok = sum(count_tokens(x.text) for x in fus)
        raw_tok = count_tokens(mem_text[(loc, "raw")])
        T = base_tok + raw_tok
        # WITHOUT arm: base filler padded by the Raw memory's size
        wo_base, npos = build_context(None, fus, seed_parts=(task.id, "none"))
        assert npos is None
        wo_ctx, wo_pad, wo_npad = padded(wo_base, len(fus), pad_pool, raw_tok)
        arm_ctx = {}
        for arm in ARMS:
            mt = mem_text[(loc, arm)]
            m_tok = count_tokens(mt)
            tgt = MemoryUnit(u["memory_id"], loc, mt, m_tok, u["domain"])
            # same seeded position as K2 (task, memory), among the base filler
            base_ctx, pos = build_context(tgt, fus, seed_parts=(task.id, u["memory_id"]))
            ctx, pad_tok, npad = padded(base_ctx, len(fus) + 1, pad_pool, max(0, T - base_tok - m_tok))
            arm_ctx[arm] = (ctx, pos, m_tok, pad_tok, npad)
            ctx_tokens.append(count_tokens(ctx))
        for rep in range(c["replicates"]):
            for arm in ARMS + ("without_memory",):
                if arm == "without_memory":
                    ctx, position, m_tok, pad_tok, npad = wo_ctx, None, 0, wo_pad, wo_npad
                    mt = ""
                else:
                    ctx, position, m_tok, pad_tok, npad = arm_ctx[arm]
                    mt = mem_text[(loc, arm)]
                jobs.append({
                    "cell": c, "unit": u, "task": task, "arm": arm,
                    "sub": "without_memory" if arm == "without_memory" else "with_memory",
                    "mem_sha": S.sha256_text(mt) if mt else "none",
                    "replicate_id": rep, "position": position,
                    "n_filler": len(fil), "n_pad_units": npad, "pad_tokens": pad_tok,
                    "memory_tokens_arm": m_tok, "fixed_total_T": T,
                    "filler_tokens": base_tok,
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user",
                         "content": f"{ctx}\n\n--- Question ---\n{task.question}"},
                    ],
                })
    q = sorted(ctx_tokens)
    log(f"WITH-arm context tokens: min={q[0]} p25={q[len(q)//4]} median={q[len(q)//2]} "
        f"p75={q[3*len(q)//4]} max={q[-1]}  (K={args.k_filler} filler)")
    sysseen = collections.Counter(j["messages"][0]["content"] for j in jobs)
    log(f"system prompts in use: {len(sysseen)} distinct "
        f"-> { {S.sha256_text(k)[:12]: v for k, v in sysseen.items()} }")
    log(f"PLANNED CALLS: {len(jobs)}  (budget {args.max_calls})")
    if len(jobs) > args.max_calls:
        raise SystemExit(f"planned {len(jobs)} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        return 0

    # ---- embeddings (semantic_similarity is NON-NULLABLE) ----
    log("embedding memories and tasks ...")
    emb = EmbeddingClient(cache_path=str(args.out / "embeddings.jsonl"))
    mem_texts = {uloc[l]["memory_id"]: texts[l] for l in sorted(target_locs)}
    mem_ids = sorted(mem_texts)
    task_ids = sorted({c["task_id"] for c in cells})
    vmap, budget_used = embed_with_backoff(
        emb, [(m, mem_texts[m]) for m in mem_ids]
        + [(t, tasks[t].question) for t in task_ids], EMBED_TOKEN_BUDGET)
    arr = np.asarray([vmap[k] for k in mem_ids + task_ids], dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    store = args.out / "embeddings.npy"
    np.save(store, arr)
    idx = {k: i for i, k in enumerate(mem_ids + task_ids)}
    sha = S.file_sha256(store)
    mem_trunc = {m: count_tokens(mem_texts[m]) > budget_used[m] for m in mem_ids}
    log(f"embeddings {arr.shape} -> {store.name} "
        f"(truncated for embedding: {sum(mem_trunc.values())}/{len(mem_trunc)})")

    sim = {(uloc[c["memory_unit_locator"]]["memory_id"], c["task_id"]):
           float(arr[idx[uloc[c["memory_unit_locator"]]["memory_id"]]]
                 @ arr[idx[c["task_id"]]]) for c in cells}
    vals = sorted(sim.values())
    t1, t2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    log(f"similarity terciles: FAR<{t1:.4f}<=MID<{t2:.4f}<=NEAR")

    def band(s: float) -> str:
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    # ---- execute ----
    cache_path = args.out / "cache.jsonl"
    cache_guard = assert_cache_condition(cache_path, {
        "condition_id": CONDITION_ID,
        "reader_prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": S.sha256_text(SYSTEM),
        "k_filler": args.k_filler,
        "filler_band": list(fb),
        "filler_pool_sha256": S.sha256_text(json.dumps(
            {d: [u["memory_unit_locator"] for u in v]
             for d, v in sorted(filler_pool.items())}, sort_keys=True)),
        "design_cells_sha256": S.file_sha256(args.design),
        "max_tokens": args.max_tokens,
        "design": "fixed_total_context_v1",
        "arms": ["raw", "summary", "structured", "trunc_last_matched"],
        "memories_sha256": S.file_sha256(args.memories),
        "replicates": args.replicates,
        "strata": sorted(keep),
        "reasoning_effort": "low",
        "temperature": 0.0,
        "_why": "cache.KEY_FIELDS does not capture context configuration; see "
                "assert_cache_condition.",
    })
    cache = ResponseCache(cache_path)
    client = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                      max_concurrency=args.workers)
    results: dict[tuple, dict] = {}
    n_real = n_cached = n_err = 0
    t0 = time.monotonic()

    def run_one(j: dict):
        # NB condition_id is deliberately NOT in the cache key: make_key rejects
        # unknown fields (correctly -- a silently-ignored field would let two
        # conditions share a row). Condition isolation is instead enforced by
        # the CACHE FILE, guarded by assert_cache_condition() above.
        kf = {"benchmark": "longmemeval_v2",
              "source_item_id": j["unit"]["trajectory_id"],
              "memory_repr": j["arm"], "memory_id": j["mem_sha"],
              "future_task_id": j["task"].id, "arm": j["sub"],
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
            k = (j["unit"]["memory_unit_locator"], j["task"].id,
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
    log(f"execution done in {wall:.1f}s: real={n_real} cached={n_cached} errors={n_err}")

    # ---- score + write ----
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / "cells.jsonl"
    if rows_path.exists():
        rows_path.unlink()
    w = CellWriter(rows_path, strict=True)
    n_written = 0
    scored: list[dict] = []
    for c in cells:
        task = tasks[c["task_id"]]
        loc = c["memory_unit_locator"]
        u = uloc[loc]
        mid = u["memory_id"]
        mtext = texts[loc]
        leak = LK.detect(mtext, task.answer, memory_id=mid, task_id=task.id,
                         eval_function_spec=task.eval_function)
        s = sim[(mid, task.id)]
        for rep in range(c["replicates"]):
          ro = results.get((loc, task.id, rep, "without_memory"), {})
          for arm in ("raw", "summary", "structured", "trunc_last_matched"):
            rw = results.get((loc, task.id, rep, arm), {})
            mtext = mem_text[(loc, arm)]
            leak = LK.detect(mtext, task.answer, memory_id=mid, task_id=task.id,
                             eval_function_spec=task.eval_function)
            m_tok = count_tokens(mtext)
            wmeta = mem_meta.get((loc, arm), {})
            errs = [r.get("error") for r in (rw, ro) if r.get("error")]
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
            recs = [r["rec"] for r in (rw, ro) if r.get("rec") is not None]
            rt = [r.reasoning_tokens for r in recs if r.reasoning_tokens is not None]
            job = rw.get("job") or ro.get("job", {})
            row = w.build(
                benchmark="longmemeval_v2", benchmark_version=lmev2.UPSTREAM_COMMIT,
                source_episode_id=u["trajectory_id"],
                source_episode_metadata={"domain": u["domain"],
                                         "environment": u["environment"],
                                         "outcome": u["outcome"], "url": u["url"],
                                         "memory_unit_locator": loc},
                memory_representation=REPR_OF_ARM[arm],
                memory_semantic_type="episodic",
                memory_text=mtext, memory_tokens=m_tok,
                memory_source_span={"trajectory_id": u["trajectory_id"],
                                    "start_state_index": u["start_state_index"],
                                    "end_state_index": u["end_state_index"],
                                    "n_states": u["n_states"]},
                memory_writer_model=wmeta.get("writer_model") or "none:deterministic_span",
                memory_writer_cluster=wmeta.get("writer_cluster") or "none:deterministic_span",
                memory_writer_prompt_version=(wmeta.get("prompt_version")
                                              or "page_visit_segmentation_v1"),
                memory_extraction_latency=wmeta.get("extraction_latency_s"),
                memory_extraction_input_tokens=wmeta.get("extraction_input_tokens"),
                memory_extraction_output_tokens=wmeta.get("extraction_output_tokens"),
                embedding_model=EMBED_MODEL,
                embedding_version=f"sophia_vllm_dim{EMBED_DIM}",
                memory_embedding_reference={"store": "embeddings.npy", "index": idx[mid],
                                            "dim": EMBED_DIM, "sha256": sha,
                                            "input_truncated": mem_trunc[mid],
                                            "input_token_budget": budget_used[mid]},
                future_task_id=task.id, future_task_family=task.question_type,
                future_task_text=task.question,
                task_embedding_reference={"store": "embeddings.npy",
                                          "index": idx[task.id], "dim": EMBED_DIM,
                                          "sha256": sha, "input_truncated": False,
                                          "input_token_budget": budget_used[task.id]},
                semantic_similarity=s, semantic_distance_band=band(s),
                retrieval_method="oracle", retrieval_rank=None, retrieval_k=None,
                memory_tokens_retrieved=m_tok,
                memory_tokens_exposed=m_tok, replicate_id=rep,
                seed_or_sampling_config={"temperature": 0.0,
                                         "max_tokens": args.max_tokens,
                                         "reasoning_effort": "low", "seed": None},
                reader_model="gpt-oss-120b", reader_cluster="metis",
                reader_endpoint="metis:/resource_server/metis/api/v1",
                reader_prompt_version=PROMPT_VERSION,
                reader_endpoint_sha256=S.sanitized_base_url_hash(
                    "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1"),
                reader_reasoning_effort="low", condition_id=f"{CONDITION_ID}_{arm}",
                output_without_memory=oo, output_with_memory=ow,
                reward_without_memory=reward_o, reward_with_memory=reward_w,
                delta_utility=delta, robustness_confidence=None,
                write_latency=None, retrieval_latency=None,
                generation_latency=round(sum(r.latency_s for r in recs), 4),
                end_to_end_latency=round(sum(r.latency_s for r in recs), 4),
                embedding_calls=0, generation_calls=len(recs),
                input_tokens=sum(r.input_tokens for r in recs),
                output_tokens=sum(r.output_tokens for r in recs),
                reasoning_tokens=sum(rt) if rt else None,
                retry_count=sum(r.retry_count for r in recs),
                error_code_if_any=code,
                provenance={"code_sha": CODE_SHA, "config_sha256": CONFIG_SHA,
                            "run_id": RUN_ID, "host": HOST,
                            "writer": "scripts/x2_fixed_context.py",
                            "arm": arm,
                            "fixed_total_T": job.get("fixed_total_T"),
                            "pad_tokens": (rw.get("job") or {}).get("pad_tokens"),
                            "n_pad_units": (rw.get("job") or {}).get("n_pad_units"),
                            "without_pad_tokens": (ro.get("job") or {}).get("pad_tokens"),
                            "target_position": job.get("position"),
                            "n_filler": job.get("n_filler"),
                            "filler_tokens": job.get("filler_tokens"),
                            "prompt_arm": "handwritten",
                            "system_prompt_sha256": S.sha256_text(SYSTEM),
                            # THE SCREEN, on every row, so analysis never
                            # re-derives it and cannot disagree with the design.
                            "stratum": c["stratum"],
                            "why_stratum": c["why_stratum"],
                            "detector_fires": c["detector_fires"],
                            "task_pool_hits": c["task_pool_hits"],
                            "task_pool_size": c["task_pool_size"],
                            "n_bearing_tasks_for_this_memory":
                                c["n_bearing_tasks_for_this_memory"],
                            "is_unknown_with": unk_w, "is_unknown_without": unk_o},
                license_source_reference="longmemeval_v2:Apache-2.0",
                verifier_id=task.eval_name,
                verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                reward_is_continuous=False,
                leakage_flag=bool(leak.any_leak) if not leak.undecidable else None,
            )
            w.write_row(row)
            n_written += 1
            scored.append({"stratum": f'{c["stratum"]}|{arm}', "reward_with": reward_w,
                           "reward_without": reward_o, "delta": delta})
    log(f"wrote {n_written} rows -> {rows_path} ({w.close()})")

    ok_rows = [s for s in scored if s["delta"] is not None]
    by_s = collections.defaultdict(list)
    for s in ok_rows:
        by_s[s["stratum"]].append(s)
    summary = {
        "run_at_utc": utc_now(), "run_id": RUN_ID, "wall_clock_s": round(wall, 2),
        "prompt_arm": "handwritten", "reader_prompt_version": PROMPT_VERSION,
        "condition_id": CONDITION_ID,
        "n_cells": len(cells), "n_memories": len(target_locs),
        "n_source_episodes": len(target_trajs),
        "n_tasks": len(task_ids), "rows_written": n_written,
        "planned_calls": len(jobs), "real_endpoint_calls": n_real,
        "cache_hits": n_cached, "errors": n_err,
        "cache_condition_guard": cache_guard,
        "context_tokens_with_arm": {"min": q[0], "p25": q[len(q)//4],
                                    "median": q[len(q)//2],
                                    "p75": q[3*len(q)//4], "max": q[-1]},
        "similarity_terciles": {"far_below": t1, "near_at_or_above": t2},
        "embedding_truncated_memories": int(sum(mem_trunc.values())),
        "per_stratum_raw": {
            st: {"n_rows": len(v),
                 "mean_reward_with": float(np.mean([x["reward_with"] for x in v])),
                 "mean_reward_without": float(np.mean([x["reward_without"] for x in v])),
                 "mean_delta": float(np.mean([x["delta"] for x in v]))}
            for st, v in sorted(by_s.items())},
        "_per_stratum_raw_note":
            "row-level means over usable rows. The per-CELL analysis (prereg section 3 "
            "averages replicates first) is scripts/k3_analyze_screened.py; these are "
            "a run-health readout, not the reported estimates.",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    log(json.dumps(summary["per_stratum_raw"], indent=2))
    log(f"real={n_real} cached={n_cached} errors={n_err} rows={n_written}")
    return 0


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
CONFIG_SHA = S.file_sha256(REPO / "configs/endpoint_primary.json")
RUN_ID = f"x2_fixedctx_{utc_now().replace(':', '').replace('-', '')}"
import socket  # noqa: E402
HOST = socket.gethostname()

if __name__ == "__main__":
    raise SystemExit(main())

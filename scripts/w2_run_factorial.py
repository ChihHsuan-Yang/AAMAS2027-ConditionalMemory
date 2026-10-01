#!/usr/bin/env python3
"""W2: run the writer-Gemma halves of the Writer x Reader factorial.

Two new cells of the 2x2, per representation in {summary, structured}:

    W1/W2   writer Gemma  x  reader gpt-oss-120b
    W3/W4   writer Gemma  x  reader gemma-4-31B-it

The writer-gpt-oss halves already exist and are NOT re-run:
    A2/A3   results/repr_scaleup/cells.jsonl        (reader gpt-oss)
    R2/R3   results/gemma_reader/transfer_cells.jsonl (reader Gemma)

WHAT VARIES, AND WHAT IS HELD
------------------------------
The memory TEXT varies -- that IS the writer intervention. Everything that is
not a function of the memory text is held byte-for-byte and ASSERTED:

  F-GATE 1  filler pool sha256 == the screened run's recorded value
  F-GATE 2  system prompt sha256 == the screened run's recorded value
  F-GATE 3  per cell, target_position / n_filler / filler_tokens == the values
            the gpt-oss ROW recorded. The position seed is
            (task_id, MANIFEST memory_id), so a Gemma-written memory lands in
            the slot its gpt-oss counterpart occupied. POSITION_EFFECT.md
            measured 8/12 answers change when the target moves.
  F-GATE 4  every WITHOUT-arm request's context_sha256 == the hash the
            published runs stored for the same (task, replicate). The WITHOUT
            arm contains NO target, so it MUST be byte-identical across
            writers; if it is not, the filler or scaffold drifted.
  F-GATE 5  POSITIVE CONTROL, the other direction: every WITH-arm request's
            context_sha256 must DIFFER from the published one. If the WITH arm
            matched, the Gemma memory never reached the prompt and this would
            be an A/A comparison reported as A/B.

semantic_similarity is RE-MEASURED for the Gemma memory texts. Reusing
gpt-oss's would put one memory's similarity on a different memory's row.

reward None means could not be scored. NEVER 0.0.
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

import numpy as np                                          # noqa: E402

from p1mem import schema as S                               # noqa: E402
from p1mem.adapters import leakage as LK                    # noqa: E402
from p1mem.adapters import lmev2                            # noqa: E402
from p1mem.cache import ResponseCache                       # noqa: E402
from p1mem.cells import SYSTEM, MemoryUnit, build_context   # noqa: E402
from p1mem.client import ClientError, P1Client              # noqa: E402
from p1mem.embed import EMBED_DIM, EMBED_MODEL, EmbeddingClient  # noqa: E402
from p1mem.memory.tokens import count_tokens                # noqa: E402
from p1mem.vendor.rcc_schema import sha256_text, utc_now    # noqa: E402
from p1mem.writer import CellWriter                         # noqa: E402

PROMPT_VERSION = "p1_deltau_raw_v1"      # UNCHANGED from every prior arm
STRATA = ("BEARING", "MATCHED_CONTROL")
K_FILLER = 4
REPS = ("summary", "structured")
EMBED_TOKEN_BUDGET = 2000

#: The two writer arms this script can run. BOTH are run in the SAME session,
#: because the WITHOUT-arm control proved gpt-oss is NOT deterministic across
#: sessions: 554 of 1124 byte-identical WITHOUT-arm requests returned different
#: text when re-issued a day later. Comparing a writer arm run today against
#: one run yesterday confounds WRITER with SESSION.
WRITERS = {
    "gemma": {
        "arm": "gemma_metis", "model": "gemma-4-31B-it",
        "memories": "results/writer_factorial/memories_gemma.jsonl",
        "tag": "wgemma4_31B",
        # this writer's memory text DIFFERS from the published run's, so the
        # WITH-arm request bytes must differ
        "with_arm_must_match_published": False,
    },
    "gptoss": {
        "arm": "gptoss_metis", "model": "gpt-oss-120b",
        "memories": "results/repr_scaleup/memories.jsonl",
        "tag": "wgptoss120b",
        # SAME memory text as the published run, so the WITH-arm request bytes
        # must MATCH. That flips F-GATE 5 into a byte-identity check and is a
        # strictly stronger assertion than the differs-check.
        "with_arm_must_match_published": True,
    },
}


def condition_id(writer: str, rep: str, reader_arm: str) -> str:
    """Names BOTH models AND the session, so nothing can pool by accident."""
    rtag = "rgemma4_31B" if reader_arm == "gemma_metis" else "rgptoss120b"
    return f"lmev2_{rep}_{WRITERS[writer]['tag']}_{rtag}_factorial_v1"

#: Published caches, read ONLY for the WITHOUT-arm context hashes they stored.
PUBLISHED_CACHES = (
    REPO / "results/repr_scaleup/eval_cache.jsonl",       # reader gpt-oss
    REPO / "results/gemma_reader/transfer_cache.jsonl",   # reader Gemma
)
GPTOSS_ROWS = REPO / "results/repr_scaleup/cells.jsonl"


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
        raise SystemExit(
            f"text join matched {len(out)} of {len(locators)} units; missing "
            f"{sorted(missing)[:5]}. Half a join still looks like success.")
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--design-meta", type=Path,
                    default=REPO / "results/ledgers/k1_screened_design.json")
    ap.add_argument("--writer", default="gemma", choices=sorted(WRITERS),
                    help="which WRITER arm to run. Both must be run in the "
                         "SAME session; see WRITERS.")
    ap.add_argument("--memories", type=Path, default=None,
                    help="defaults to the --writer's own memories file")
    ap.add_argument("--readers", default="gptoss_metis,gemma_metis")
    ap.add_argument("--representations", default="summary,structured")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--limit-cells", type=int, default=0,
                    help="0 = the whole eligible set. A positive value takes the "
                         "FIRST n by (memory_unit_locator, task_id) IDENTICALLY "
                         "for every arm -- the precommitted BALANCED subset rule, "
                         "never an outcome filter.")
    ap.add_argument("--max-calls", type=int, default=5200)
    ap.add_argument("--out", type=Path, default=REPO / "results/writer_factorial")
    ap.add_argument("--rows-name", default=None)
    ap.add_argument("--cache-name", default="factorial_cache.jsonl")
    ap.add_argument("--summary-name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plant-position-defect", action="store_true",
                    help="POSITIVE CONTROL: drop one filler unit so F-GATE 3/4 abort")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    reps = [r.strip() for r in args.representations.split(",") if r.strip()]
    readers = [r.strip() for r in args.readers.split(",") if r.strip()]
    WSPEC = WRITERS[args.writer]
    WRITER_ARM = WSPEC["arm"]
    if args.memories is None:
        args.memories = REPO / WSPEC["memories"]
    if args.rows_name is None:
        args.rows_name = f"factorial_cells_{args.writer}.jsonl"
    if args.summary_name is None:
        args.summary_name = f"factorial_summary_{args.writer}.json"
    log(f"WRITER ARM {args.writer!r}: model={WSPEC['model']!r} "
        f"memories={args.memories.name} "
        f"with_arm_must_match_published={WSPEC['with_arm_must_match_published']}")

    for rid in readers:
        a = S.reader_arm(rid)
        log(f"READER ARM {rid!r}: model={a['reader_model']!r} cluster={a['reader_cluster']!r} "
            f"temp={a['temperature']} max_tokens={a['max_tokens']} workers={a['max_workers']} "
            f"reasoning_effort={a['reasoning_effort']!r} "
            f"truncation_is_always_an_error={a['truncation_is_always_an_error']}")

    log(f"vendored scorer: {lmev2.verify_vendored_scorer()[:16]}...")
    lmev2.assert_writer_blind()
    log("writer blindness: PASSED")
    ok_ctrl, ctrl = LK.controls_summary()
    if not ok_ctrl:
        raise SystemExit("leakage detector controls FAILED")
    log(f"leakage detector controls: {sum(c.passed for c in ctrl)}/{len(ctrl)} PASS")

    # ---- design + the Gemma-written memories ----
    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    cells = [c for c in design if c["stratum"] in STRATA]
    meta = json.loads(args.design_meta.read_text())
    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    mem_rows = [json.loads(l) for l in args.memories.read_text().splitlines()
                if l.strip()]
    # raw lives in the same file for the gpt-oss arm and has NO writer (0 model
    # calls). It is not in the factorial; restrict to the representations in
    # scope before the writer-identity check, or that check sees the raw
    # sentinel and refuses a correct file.
    mem_rows = [m for m in mem_rows if m["representation"] in reps]
    written = {(m["representation"], m["memory_unit_locator"]): m for m in mem_rows}
    mem_sha = S.file_sha256(args.memories)
    log(f"{args.writer} memories: {len(mem_rows)} rows, sha256 {mem_sha[:16]}")
    if {m["writer_model"] for m in mem_rows} != {WSPEC["model"]}:
        raise SystemExit(
            f"the memories file carries writer(s) "
            f"{sorted({m['writer_model'] for m in mem_rows})}, expected "
            f"{WSPEC['model']!r}")

    # ---- the gpt-oss ROWS, for F-GATE 3 and for the comparator anchor ----
    oss_fact: dict[tuple, dict] = {}
    for line in GPTOSS_ROWS.open():
        if not line.strip():
            continue
        r = json.loads(line)
        p = r.get("provenance") or {}
        loc = p.get("memory_unit_locator")
        if loc is None:
            continue
        oss_fact[(r["memory_representation"], loc, r["future_task_id"])] = {
            "target_position": p.get("target_position"),
            "n_filler": p.get("n_filler"),
            "filler_tokens": p.get("filler_tokens"),
            "memory_text": r["memory_text"],
        }
    log(f"gpt-oss per-cell facts: {len(oss_fact)} keys")

    # ---- F-GATE 1 / F-GATE 2 ----
    k2_fp = json.loads(
        (REPO / "results/deltau_screened/cache.condition.json").read_text())
    if S.sha256_text(SYSTEM) != k2_fp["system_prompt_sha256"]:
        raise SystemExit("system prompt differs from the screened run's")
    log(f"F-GATE 2 system prompt: sha256 {S.sha256_text(SYSTEM)[:16]} MATCHES")

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
            f"filler pool sha256 {pool_sha[:16]} != the screened run's "
            f"{k2_fp['filler_pool_sha256'][:16]}")
    log(f"F-GATE 1 filler pool: sha256 {pool_sha[:16]} MATCHES the screened run")

    def select_filler(p: list, *, k: int, task_id: str) -> list:
        o = sorted(p, key=lambda u: u["memory_unit_locator"])
        random.Random(f"filler:{task_id}").shuffle(o)
        return o[:k]

    # ---- the published WITHOUT-arm context hashes, for F-GATE 4 ----
    # The WITHOUT arm has NO target, so its bytes depend only on (task, filler).
    # Verified on the published caches: for every (task, replicate), all
    # representations share one context_sha256.
    pub_without: dict[tuple, set] = collections.defaultdict(set)
    pub_with: dict[tuple, set] = collections.defaultdict(set)
    for path in PUBLISHED_CACHES:
        if not path.exists():
            raise SystemExit(f"published cache {path} missing")
        for line in path.open():
            if not line.strip():
                continue
            k = json.loads(line)["key"]
            if "context_sha256" not in k:
                continue
            tgt = pub_without if k["arm"] == "without_memory" else pub_with
            tgt[(k["memory_repr"], k["future_task_id"], int(k["replicate_id"]))
                ].add(k["context_sha256"])
    bad = {k: v for k, v in pub_without.items() if len(v) != 1}
    if bad:
        raise SystemExit(f"{len(bad)} published WITHOUT-arm keys have >1 context hash")
    log(f"published context hashes: WITHOUT {len(pub_without)} keys, "
        f"WITH {len(pub_with)} keys")

    # ---- ELIGIBILITY -- non-outcome-based, fixed in the precommitment ----
    eligible: dict[str, list] = {}
    excluded: dict[str, list] = {}
    for rep in reps:
        el, ex = [], []
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            w = written.get((rep, c["memory_unit_locator"]))
            cid = c["memory_unit_locator"] + "|" + c["task_id"]
            if w is None:
                ex.append({"cell": cid, "reason": "no_memory_written"})
            elif not w["ok"]:
                ex.append({"cell": cid, "reason": f"{args.writer}_write_failed",
                           "error_code": w.get("error_code")})
            elif (rep, c["memory_unit_locator"], c["task_id"]) not in oss_fact:
                ex.append({"cell": cid, "reason": "no_gptoss_row_for_gate3"})
            else:
                el.append(c)
        eligible[rep], excluded[rep] = el, ex
    if args.limit_cells:
        chosen = {r: eligible[r][:args.limit_cells] for r in reps}
        log(f"SUBSET RULE INVOKED: first {args.limit_cells} by "
            f"(memory_unit_locator, task_id), IDENTICALLY for every arm")
    else:
        chosen = {r: list(eligible[r]) for r in reps}
    for r in reps:
        log(f"eligible {r}: {len(eligible[r])} cells (excluded {len(excluded[r])}) "
            f"-> running {len(chosen[r])}")

    # ---- build every request up front ----
    need = {c["memory_unit_locator"] for cs in chosen.values() for c in cs}
    need |= {u["memory_unit_locator"] for v in pool.values() for u in v}
    log(f"loading text for {len(need)} units ...")
    texts = load_texts(args.root, need)

    g3 = {"matched": 0, "mismatched": 0}
    g4 = {"matched": 0, "mismatched": 0, "no_published_reference": 0}
    g5 = {"matches_published": 0, "differs_from_published": 0,
          "no_published_reference": 0}
    g3_bad, g4_bad, g5_bad = [], [], []
    plan: dict[tuple, dict] = {}
    for rep in reps:
        for ci, c in enumerate(chosen[rep]):
            w = written[(rep, c["memory_unit_locator"])]
            task = tasks[c["task_id"]]
            u = uloc[c["memory_unit_locator"]]
            fil = select_filler(pool[u["domain"]], k=K_FILLER, task_id=task.id)
            if args.plant_position_defect and ci == 0:
                fil = fil[:-1]
            fus = [MemoryUnit(f["memory_id"], f["memory_unit_locator"],
                              texts[f["memory_unit_locator"]], f["n_tokens"],
                              f["domain"]) for f in fil]
            tgt = MemoryUnit(u["memory_id"], u["memory_unit_locator"],
                             w["memory_text"], int(w["memory_tokens"]), u["domain"])
            # Seeded by (task, MANIFEST memory id) -- the SAME seed parts every
            # prior arm used, so the Gemma memory lands in the slot the gpt-oss
            # memory occupied.
            with_ctx, pos = build_context(tgt, fus, seed_parts=(task.id, u["memory_id"]))
            without_ctx, npos = build_context(None, fus, seed_parts=(task.id, "none"))
            assert npos is None
            n_filler, filler_tokens = len(fil), sum(f["n_tokens"] for f in fil)

            # ---- F-GATE 3 ----
            fact = oss_fact[(rep, c["memory_unit_locator"], task.id)]
            got = (pos, n_filler, filler_tokens)
            want = (fact["target_position"], fact["n_filler"], fact["filler_tokens"])
            if got == want:
                g3["matched"] += 1
            else:
                g3["mismatched"] += 1
                g3_bad.append({"rep": rep, "loc": c["memory_unit_locator"],
                               "task": task.id, "gptoss": want, "ours": got})
            plan[(rep, c["memory_unit_locator"], task.id)] = {
                "cell": c, "unit": u, "task": task, "written": w,
                "with_ctx": with_ctx, "without_ctx": without_ctx, "position": pos,
                "n_filler": n_filler, "filler_tokens": filler_tokens,
                "with_tokens": count_tokens(with_ctx),
            }

            for r in range(args.replicates):
                for armname, ctx in (("with_memory", with_ctx),
                                     ("without_memory", without_ctx)):
                    msgs = [{"role": "system", "content": SYSTEM},
                            {"role": "user",
                             "content": f"{ctx}\n\n--- Question ---\n{task.question}"}]
                    h = sha256_text(msgs)
                    pubset = (pub_without if armname == "without_memory"
                              else pub_with).get((rep, task.id, r))
                    if armname == "without_memory":
                        # ---- F-GATE 4: MUST be byte-identical ----
                        if pubset is None:
                            g4["no_published_reference"] += 1
                        elif h in pubset:
                            g4["matched"] += 1
                        else:
                            g4["mismatched"] += 1
                            g4_bad.append({"rep": rep, "task": task.id,
                                           "replicate": r, "ours": h[:16],
                                           "published": sorted(pubset)[0][:16]})
                    else:
                        # ---- F-GATE 5, DIRECTION-AWARE ----
                        # writer gemma: the memory text changed, so the WITH
                        # bytes MUST differ. writer gptoss: the memory text is
                        # the published one, so they MUST MATCH -- a strictly
                        # stronger assertion, and the one that proves the
                        # re-run arm is the published arm's exact request.
                        if pubset is None:
                            g5["no_published_reference"] += 1
                        elif h in pubset:
                            g5["matches_published"] += 1
                        else:
                            g5["differs_from_published"] += 1
                            g5_bad.append({"rep": rep, "loc": c["memory_unit_locator"],
                                           "task": task.id, "replicate": r})
                    plan[(rep, c["memory_unit_locator"], task.id)].setdefault(
                        "msgs", {})[(armname, r)] = (msgs, h)

    log(f"F-GATE 3 PER-CELL POSITION+FILLER vs the gpt-oss rows: {g3}")
    if g3["mismatched"]:
        for b in g3_bad[:5]:
            log(f"  G3 MISMATCH {b}")
        raise SystemExit(f"{g3['mismatched']} cells render the target at a "
                         f"different position or with different filler; aborting.")
    if g3["matched"] == 0:
        raise SystemExit("F-GATE 3 verified NOTHING")
    log(f"F-GATE 4 WITHOUT-ARM BYTE-IDENTITY vs the published runs: {g4}")
    if g4["mismatched"]:
        for b in g4_bad[:5]:
            log(f"  G4 MISMATCH {b}")
        raise SystemExit(
            f"{g4['mismatched']} WITHOUT-arm requests differ in BYTES from the "
            f"published runs. The WITHOUT arm has no target in it, so it MUST "
            f"be identical; the filler or scaffold has drifted.")
    if g4["matched"] == 0:
        raise SystemExit("F-GATE 4 verified NOTHING")
    must_match = WSPEC["with_arm_must_match_published"]
    log(f"F-GATE 5 WITH-ARM vs published (must_match={must_match}): {g5}")
    if must_match:
        # writer gpt-oss re-run: SAME memory text => SAME bytes.
        if g5["differs_from_published"]:
            for b in g5_bad[:5]:
                log(f"  G5 DIFFERS {b}")
            raise SystemExit(
                f"{g5['differs_from_published']} WITH-arm requests differ in BYTES "
                f"from the published writer-gpt-oss ones, but this arm re-uses the "
                f"published memory text. The re-run would not be the same request.")
        if g5["matches_published"] == 0:
            raise SystemExit("F-GATE 5 verified NOTHING")
    else:
        # writer gemma: DIFFERENT memory text => bytes MUST differ.
        if g5["matches_published"]:
            raise SystemExit(
                f"{g5['matches_published']} WITH-arm requests are byte-identical "
                f"to the published writer-gpt-oss ones. The new memory never "
                f"reached the prompt; this would be an A/A reported as A/B.")
        if g5["differs_from_published"] == 0:
            raise SystemExit("F-GATE 5 verified NOTHING")

    n_cells = sum(len(chosen[r]) for r in reps)
    n_jobs = n_cells * args.replicates * 2 * len(readers)
    log(f"PLANNED CALLS: {n_jobs} ({n_cells} cells x {args.replicates} reps x 2 arms "
        f"x {len(readers)} readers), budget {args.max_calls}")
    if n_jobs > args.max_calls:
        raise SystemExit(f"planned {n_jobs} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        (args.out / "factorial_dryrun.json").write_text(json.dumps(
            {"planned_calls": n_jobs, "gate3": g3, "gate4": g4, "gate5": g5,
             "eligible": {r: len(eligible[r]) for r in reps},
             "chosen": {r: len(chosen[r]) for r in reps},
             "excluded": {r: excluded[r] for r in reps}}, indent=2))
        return 0

    # ---- embeddings for the GEMMA memory texts. RE-MEASURED, never reused. ----
    log("embedding the Gemma-written memories and the tasks ...")
    emb = EmbeddingClient(cache_path=str(args.out / "embeddings_gemma.jsonl"))
    labelled: list[tuple[str, str]] = []
    for rep in reps:
        for loc in sorted({c["memory_unit_locator"] for c in chosen[rep]}):
            labelled.append((f"{rep}|{loc}", written[(rep, loc)]["memory_text"]))
    task_ids = sorted({c["task_id"] for cs in chosen.values() for c in cs})
    labelled += [(f"task|{t}", tasks[t].question) for t in task_ids]
    vmap, budget_used = {}, {}
    for key, text in labelled:
        t, tr = truncate_to_tokens(text, EMBED_TOKEN_BUDGET)
        vmap[key] = emb.embed([t])[0]
        budget_used[key] = EMBED_TOKEN_BUDGET
    order = [k for k, _ in labelled]
    arr = np.asarray([vmap[k] for k in order], dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    store = args.out / "embeddings_gemma.npy"
    np.save(store, arr)
    idx = {k: i for i, k in enumerate(order)}
    emb_sha = S.file_sha256(store)
    trunc_emb = {k: count_tokens(t) > budget_used[k] for k, t in labelled}
    log(f"embeddings {arr.shape} -> {store.name} "
        f"(truncated: {sum(trunc_emb.values())}/{len(trunc_emb)})")

    sim: dict[tuple, float] = {}
    for rep in reps:
        for c in chosen[rep]:
            loc = c["memory_unit_locator"]
            sim[(rep, loc, c["task_id"])] = float(
                arr[idx[f"{rep}|{loc}"]] @ arr[idx[f"task|{c['task_id']}"]])
    # Terciles PER REPRESENTATION, as prereg section 7 and r2 both do.
    cuts = {}
    for rep in reps:
        vals = sorted(v for (r, _, _), v in sim.items() if r == rep)
        cuts[rep] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])
        log(f"{rep} similarity terciles: FAR<{cuts[rep][0]:.4f}<=MID<{cuts[rep][1]:.4f}<=NEAR")

    def band(rep: str, s: float) -> str:
        t1, t2 = cuts[rep]
        return "FAR" if s < t1 else ("MID" if s < t2 else "NEAR")

    # ---- execute, one reader at a time ----
    cache = ResponseCache(args.out / args.cache_name)
    results: dict[tuple, dict] = {}
    totals = {}
    for rid in readers:
        a = S.reader_arm(rid)
        client = P1Client(cluster=a["reader_cluster"], model=a["reader_model"],
                          cache=cache, max_concurrency=a["max_workers"],
                          truncation_is_always_an_error=a["truncation_is_always_an_error"])
        jobs = []
        for rep in reps:
            for c in chosen[rep]:
                key = (rep, c["memory_unit_locator"], c["task_id"])
                pl = plan[key]
                for r in range(args.replicates):
                    for armname in ("with_memory", "without_memory"):
                        msgs, h = pl["msgs"][(armname, r)]
                        jobs.append({"reader": rid, "rep": rep, "key": key, "plan": pl,
                                     "arm": armname, "replicate_id": r,
                                     "messages": msgs, "context_sha256": h})

        def run_one(j: dict, _a=a, _c=client):
            w = j["plan"]["written"]
            kf = {"benchmark": "longmemeval_v2",
                  "source_item_id": j["plan"]["unit"]["trajectory_id"],
                  "memory_repr": j["rep"],
                  # 🔴 WRITER-AWARE. memory_content_id is a hash of the SEGMENT
                  # and is therefore IDENTICAL across writers; using it alone
                  # would make a writer-Gemma key collide with the published
                  # writer-gpt-oss key on everything but context_sha256. The
                  # memory id must name the MEMORY, so it is a hash of the
                  # memory TEXT and the writer model.
                  "memory_id": sha256_text(
                      {"writer": w["writer_model"], "text": w["memory_text"]})[:16],
                  "future_task_id": j["key"][2], "arm": j["arm"],
                  "retrieval_method": "oracle", "prompt_version": PROMPT_VERSION,
                  "replicate_id": j["replicate_id"]}
            try:
                c_, rec = _c.chat(j["messages"], max_tokens=_a["max_tokens"],
                                  temperature=float(_a["temperature"]),
                                  reasoning_effort=_a["reasoning_effort"],
                                  cache_key_fields=kf)
                return j, c_, rec, None
            except ClientError as e:
                return j, None, None, f"{type(e).__name__}: {e}"

        log(f"executing {len(jobs)} calls for reader {rid!r} at concurrency "
            f"{a['max_workers']} ...")
        t0 = time.monotonic()
        n_real = n_cached = n_err = done = 0
        with ThreadPoolExecutor(max_workers=a["max_workers"]) as pool_ex:
            futs = [pool_ex.submit(run_one, j) for j in jobs]
            for fut in as_completed(futs):
                j, content, rec, err = fut.result()
                k = (j["reader"], *j["key"], j["replicate_id"], j["arm"])
                if err is not None:
                    n_err += 1
                    results[k] = {"error": err, "job": j}
                else:
                    n_cached += 1 if rec.cache_hit else 0
                    n_real += 0 if rec.cache_hit else 1
                    results[k] = {"content": content, "rec": rec, "job": j}
                done += 1
                if done % 250 == 0:
                    el = time.monotonic() - t0
                    log(f"  [{rid}] {done}/{len(jobs)} in {el:.0f}s "
                        f"({done / el * 60:.1f}/min) real={n_real} err={n_err}")
        wall = time.monotonic() - t0
        resolved = collections.Counter(
            v["rec"].resolved_model for kk, v in results.items()
            if kk[0] == rid and v.get("rec") is not None)
        log(f"[{rid}] done in {wall:.1f}s: real={n_real} cached={n_cached} "
            f"errors={n_err}; resolved={dict(resolved)}")
        if set(resolved) - {a["reader_model"]}:
            raise SystemExit(f"a call resolved to an unexpected model: {dict(resolved)}")
        totals[rid] = {"wall_clock_s": round(wall, 2), "real": n_real,
                       "cached": n_cached, "errors": n_err,
                       "resolved_model_counts": dict(resolved)}

    # ---- score + write ----
    from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
        extract_boxed_answer, is_unknown)

    rows_path = args.out / args.rows_name
    if rows_path.exists():
        rows_path.unlink()
    w_out = CellWriter(rows_path, strict=True)
    n_written = 0
    for rid in readers:
        a = S.reader_arm(rid)
        reader_fields = S.reader_row_fields(rid)
        for rep in reps:
            for c in chosen[rep]:
                loc = c["memory_unit_locator"]
                key = (rep, loc, c["task_id"])
                pl = plan[key]
                wr, task, u = pl["written"], pl["task"], pl["unit"]
                mtext = wr["memory_text"]
                leak = LK.detect(mtext, task.answer,
                                 memory_id=wr["memory_content_id"], task_id=task.id,
                                 eval_function_spec=task.eval_function)
                s = sim[key]
                ek = f"{rep}|{loc}"
                for r in range(args.replicates):
                    rw = results.get((rid, *key, r, "with_memory"), {})
                    ro = results.get((rid, *key, r, "without_memory"), {})
                    errs = [x.get("error") for x in (rw, ro) if x.get("error")]
                    ow, oo = rw.get("content"), ro.get("content")
                    if errs or ow is None or oo is None:
                        reward_w = reward_o = delta = None    # NEVER 0.0
                        joined = " | ".join(errs)
                        if "TruncatedResponseError" not in joined:
                            code = "http_error"
                        elif "FRAGMENT" in joined:
                            code = S.ERROR_TRUNCATED_FRAGMENT
                        else:
                            code = S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH
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
                    row = w_out.build(
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
                            "n_states": u["n_states"], "memory_unit_locator": loc,
                            "derived_from": "whole_segment"},
                        memory_writer_model=wr["writer_model"],
                        memory_writer_cluster=wr["writer_cluster"],
                        memory_writer_prompt_version=wr["prompt_version"],
                        memory_extraction_latency=wr["extraction_latency_s"],
                        memory_extraction_input_tokens=wr["extraction_input_tokens"],
                        memory_extraction_output_tokens=wr["extraction_output_tokens"],
                        # RE-MEASURED for the Gemma text. Never reused.
                        embedding_model=EMBED_MODEL,
                        embedding_version=f"sophia_vllm_dim{EMBED_DIM}",
                        memory_embedding_reference={
                            "store": "embeddings_gemma.npy", "index": idx[ek],
                            "dim": EMBED_DIM, "sha256": emb_sha,
                            "input_truncated": trunc_emb[ek],
                            "input_token_budget": budget_used[ek]},
                        future_task_id=task.id, future_task_family=task.question_type,
                        future_task_text=task.question,
                        task_embedding_reference={
                            "store": "embeddings_gemma.npy",
                            "index": idx[f"task|{task.id}"], "dim": EMBED_DIM,
                            "sha256": emb_sha, "input_truncated": False,
                            "input_token_budget": budget_used[f"task|{task.id}"]},
                        semantic_similarity=s, semantic_distance_band=band(rep, s),
                        retrieval_method="oracle", retrieval_rank=None, retrieval_k=None,
                        memory_tokens_retrieved=int(wr["memory_tokens"]),
                        memory_tokens_exposed=int(wr["memory_tokens"]),
                        replicate_id=r,
                        seed_or_sampling_config={
                            "temperature": float(a["temperature"]),
                            "max_tokens": a["max_tokens"],
                            "reasoning_effort": a["reasoning_effort"], "seed": None},
                        **reader_fields,
                        reader_prompt_version=PROMPT_VERSION,
                        condition_id=condition_id(args.writer, rep, rid),
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
                        # None, not 0, when the reader reports nothing.
                        reasoning_tokens=sum(rt) if rt else None,
                        retry_count=sum(x.retry_count for x in recs),
                        error_code_if_any=code,
                        faithfulness_check=None,
                        faithfulness_notes=(
                            "measured on the WRITE pass for this writer arm: "
                            "results/writer_factorial/write_summary_gemma.json"),
                        provenance={
                            "code_sha": CODE_SHA, "config_sha256": CONFIG_SHA,
                            "run_id": RUN_ID, "host": "laptop",
                            "writer": "scripts/w2_run_factorial.py",
                            "WRITER_FACTORIAL_ARM": True,
                            "writer_arm": WRITER_ARM, "reader_arm": rid,
                            "writer_family": args.writer,
                            "reader_family": ("gemma" if rid == "gemma_metis"
                                              else "gptoss"),
                            "same_family": (
                                (args.writer == "gemma") ==
                                (rid == "gemma_metis")),
                            "SESSION_MATCHED_RUN_ID": RUN_ID,
                            "target_position": pl["position"],
                            "n_filler": pl["n_filler"],
                            "filler_tokens": pl["filler_tokens"],
                            "context_sha256": pl["msgs"][("with_memory", r)][1],
                            "without_arm_context_sha256":
                                pl["msgs"][("without_memory", r)][1],
                            "context_tokens": pl["with_tokens"],
                            "gate3_position_filler_match_gptoss_row": True,
                            "gate4_without_arm_matches_published": True,
                            "gate5_with_arm_vs_published": (
                                "matches" if WSPEC["with_arm_must_match_published"]
                                else "differs"),
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
                            "write_finish_reason": wr.get("finish_reason"),
                            "write_truncated": bool(wr.get("truncated")),
                        },
                        license_source_reference="longmemeval_v2:Apache-2.0",
                        verifier_id=task.eval_name,
                        verifier_version=f"vendored@{lmev2.VENDORED_SCORER_SHA256[:12]}",
                        reward_is_continuous=False,
                        leakage_flag=(bool(leak.any_leak) if not leak.undecidable
                                      else None),
                    )
                    w_out.write_row(row)
                    n_written += 1
    closed = w_out.close()
    log(f"wrote {n_written} rows -> {rows_path} ({closed})")

    # ---- VERIFY THE ARTIFACT. Exit 0 is not success. ----
    on_disk = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    expected = sum(len(chosen[r]) for r in reps) * args.replicates * len(readers)
    gem_rows = [r for r in on_disk if r["reader_model"] == "gemma-4-31B-it"]
    oss_rows_new = [r for r in on_disk if r["reader_model"] == "gpt-oss-120b"]
    checks = {
        "rows_on_disk_equals_expected": len(on_disk) == expected,
        "every_row_written_by_the_requested_writer":
            {r["memory_writer_model"] for r in on_disk} == {WSPEC["model"]},
        "both_readers_present":
            {r["reader_model"] for r in on_disk}
            == {S.reader_arm(x)["reader_model"] for x in readers},
        "reader_row_counts_are_balanced": len(gem_rows) == len(oss_rows_new),
        "condition_ids_name_both_models":
            all((r["condition_id"] or "").startswith("lmev2_")
                and WSPEC["tag"] in (r["condition_id"] or "")
                and "_factorial_v1" in (r["condition_id"] or "")
                for r in on_disk),
        "condition_ids_disjoint_from_published": not (
            {r["condition_id"] for r in on_disk}
            & {"lmev2_summary_metis_gptoss120b_screened_v1",
               "lmev2_structured_metis_gptoss120b_screened_v1",
               "lmev2_summary_metis_gemma4_31B_readertransfer_v1",
               "lmev2_structured_metis_gemma4_31B_readertransfer_v1"}),
        "gemma_reader_reasoning_tokens_null_never_zero":
            all(r["reasoning_tokens"] is None for r in gem_rows),
        "no_row_coerced_a_null_reward_to_zero": all(
            not (r["error_code_if_any"] and r["reward_with_memory"] is not None)
            for r in on_disk),
        "every_errored_row_has_null_reward": all(
            (r["reward_with_memory"] is None and r["reward_without_memory"] is None)
            for r in on_disk if r["error_code_if_any"]),
        "replicates_per_cell_as_requested": (
            set(collections.Counter(
                (r["provenance"]["pair_key"], r["memory_representation"],
                 r["reader_model"]) for r in on_disk).values())
            == {args.replicates}),
        "memory_text_is_this_writers_text": all(
            r["memory_text"] == written[(r["memory_representation"],
                                         r["provenance"]["memory_unit_locator"])
                                        ]["memory_text"] for r in on_disk),
    }
    log("ARTIFACT CHECKS (exit 0 is not success):")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k}")

    summary = {
        "_what": "WRITER x READER FACTORIAL, the two writer-Gemma cells: "
                 "Gemma-written memories read by gpt-oss-120b (W1/W2) and by "
                 "gemma-4-31B-it (W3/W4).",
        "precommitment": "docs/WRITER_FACTORIAL_PRECOMMITMENT.md",
        "run_at_utc": utc_now(), "run_id": RUN_ID,
        "writer_arm": WRITER_ARM, "writer_model": WSPEC["model"],
        "writer": args.writer,
        "readers": readers,
        "reader_identity": {rid: {k: S.reader_arm(rid)[k] for k in
                                  ("reader_model", "reader_cluster", "reader_endpoint",
                                   "reader_reasoning_effort", "temperature",
                                   "max_tokens", "max_workers",
                                   "reports_reasoning_tokens",
                                   "truncation_is_always_an_error")}
                            for rid in readers},
        "condition_ids": {f"{rep}|{rid}": condition_id(args.writer, rep, rid)
                          for rep in reps for rid in readers},
        "representations": reps, "replicates": args.replicates,
        "cells_per_representation": {r: len(chosen[r]) for r in reps},
        "eligible_pool_size": {r: len(eligible[r]) for r in reps},
        "excluded": {r: excluded[r] for r in reps},
        "subset_rule_invoked": bool(args.limit_cells),
        "eligibility_rule": (
            "stratum in BEARING/MATCHED_CONTROL (285 design cells) x "
            "{summary, structured}; the GEMMA write succeeded; a gpt-oss row "
            "exists for F-GATE 3. NON-OUTCOME-BASED, fixed in "
            "docs/WRITER_FACTORIAL_PRECOMMITMENT.md before any Gemma memory "
            "was written."),
        "identity_gates": {
            "fgate1_filler_pool_sha256": pool_sha,
            "fgate2_system_prompt_sha256": S.sha256_text(SYSTEM),
            "fgate3_per_cell_position_and_filler_vs_gptoss_rows": g3,
            "fgate4_without_arm_byte_identity_vs_published": g4,
            "fgate5_with_arm_vs_published": g5,
            "fgate5_direction": ("MUST_MATCH" if WSPEC["with_arm_must_match_published"]
                                 else "MUST_DIFFER"),
            "_fgate5_note": (
                "F-GATE 4 and F-GATE 5 are the two directions of one check. "
                "The WITHOUT arm has no target and MUST be byte-identical "
                "across writers. For writer GEMMA the WITH arm MUST DIFFER "
                "from the published request (new memory text). For the writer "
                "GPTOSS re-run it MUST MATCH -- same memory text, so the same "
                "bytes; that is the stronger assertion and it proves the "
                "re-run issues the published arm's exact request."),
        },
        "memories_sha256": mem_sha,
        "embedding": {"store": "embeddings_gemma.npy", "sha256": emb_sha,
                      "shape": list(arr.shape),
                      "_note": "RE-MEASURED for the Gemma memory texts. Reusing "
                               "gpt-oss's would put one memory's similarity on a "
                               "different memory's row."},
        "similarity_terciles": {r: {"far_below": cuts[r][0],
                                    "near_at_or_above": cuts[r][1]} for r in reps},
        "per_reader_execution": totals,
        "rows_written": n_written,
        "rows_with_null_delta": sum(1 for r in on_disk if r["delta_utility"] is None),
        "artifact_checks": checks,
        "VERDICT": "RUN_PASSED" if all(checks.values()) else "RUN_FAILED",
    }
    payload = json.dumps(summary, indent=2, default=str)
    (args.out / args.summary_name).write_text(payload)
    led = REPO / "results/ledgers/writer_factorial" / args.summary_name
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text(payload)
    log(f"wrote tracked copy {led}")
    log(f"VERDICT: {summary['VERDICT']}")
    return 0 if all(checks.values()) else 1


CODE_SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "unknown"
CONFIG_SHA = S.file_sha256(REPO / "configs/endpoint_primary.json")
RUN_ID = f"writer_factorial_{utc_now().replace(':', '').replace('-', '')}"

if __name__ == "__main__":
    raise SystemExit(main())

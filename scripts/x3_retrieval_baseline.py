#!/usr/bin/env python3
"""X3: retrieval baselines scored against the bearing screen's ground truth.

Reviewer request: the paper's similarity result used a PREFIX-truncated
embedding that almost never sees the bearing content. This scores real
retrievers on the question the screen answers -- which unit of a task's domain
pool bears on it -- with NO reader calls (embeddings only).

Ground truth (as K1/K2): a deterministically scored task is discriminative when
the screen fires on 1..max_pool_hits (8) units of the corpus; the units it
fires on are its bearing units. Expected: 75 tasks, 266 edges (asserted).

Methods, each ranking every unit of the task's domain pool:
  bm25          Okapi BM25 (k1=1.5, b=0.75) over the full unit text
  dense_prefix  SFR-Embedding-Mistral on the first 2,000 tokens (the paper's
                configuration, for comparison)
  dense_chunk   SFR-Embedding-Mistral on 512-token chunks; unit score = max
                over its chunks
Queries are the raw question text, as in the paper.

Metrics per task, then averaged over tasks with task-clustered bootstrap CIs:
recall@1/5/10 (share of the task's bearing units in the top k), MRR (first
bearing unit), AUROC (bearing vs non-bearing units of the pool).

Also reported (no extra cost): how the deterministic tasks split by number of
units the screen fires on (0 / 1-8 / >8) and the bearing-breadth distribution
with and without the cap.

Resumable: embeddings are cached in <out>/embeddings.jsonl. Done marker:
<out>/summary.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.embed import EmbeddingClient  # noqa: E402
from p1mem.memory.tokens import OFFICIAL_TOKENIZER, _tokenizer  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402
from x1_position_session import load_texts  # noqa: E402

PREFIX_TOKENS, CHUNK_TOKENS, KS = 2000, 512, (1, 5, 10)


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def chunks_by_tokens(text: str, size: int, limit: int | None = None) -> list[str]:
    """Split ``text`` into consecutive windows of ``size`` official tokens,
    cutting on the tokenizer's character offsets (exact, no approximation)."""
    tok, _ = _tokenizer(OFFICIAL_TOKENIZER)
    enc = tok.encode(text, add_special_tokens=False)
    offs = enc.offsets
    out = []
    for s in range(0, len(offs), size):
        e = min(s + size, len(offs)) - 1
        out.append(text[offs[s][0]:offs[e][1]])
        if limit and len(out) >= limit:
            break
    return out or [text]


_WORD = re.compile(r"\w+")


def bm25_scores(query: str, docs: list[list[str]], df: dict, n_docs: int,
                avgdl: float, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
    q = [w for w in _WORD.findall(query.lower())]
    out = np.zeros(len(docs))
    for i, d in enumerate(docs):
        tf = collections.Counter(d)
        dl = len(d)
        s = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (n_docs - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * dl / avgdl))
        out[i] = s
    return out


def auroc(scores: np.ndarray, pos: np.ndarray) -> float:
    """Mann-Whitney AUROC with average ranks for ties."""
    from scipy.stats import rankdata  # noqa: PLC0415
    r = rankdata(scores)
    n1, n0 = pos.sum(), (~pos).sum()
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def per_task_metrics(scores: np.ndarray, pos: np.ndarray) -> dict:
    order = np.argsort(-scores, kind="stable")
    ranked_pos = pos[order]
    first = int(np.argmax(ranked_pos)) + 1
    m = {f"recall@{k}": float(ranked_pos[:k].sum() / pos.sum()) for k in KS}
    m["mrr"] = 1.0 / first
    m["auroc"] = auroc(scores, pos)
    return m


def clustered_ci(vals: list[float], B: int = 10000, seed: int = 20261005) -> list[float]:
    rng = np.random.default_rng(seed)
    v = np.asarray(vals)
    bs = v[rng.integers(0, len(v), (B, len(v)))].mean(1)
    return [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path, default=REPO / "results/x3_retrieval")
    ap.add_argument("--max-pool-hits", type=int, default=8)
    ap.add_argument("--methods", default="bm25,dense_prefix,dense_chunk")
    ap.add_argument("--dry-run", action="store_true",
                    help="build ground truth and chunks, report counts, no embedding calls")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    methods = args.methods.split(",")

    units = [json.loads(l) for l in (REPO / "data/manifests/lmev2_memory_units_small.jsonl")
             .read_text().splitlines() if l.strip()]
    tasks = {t.id: t for t in lmev2.load_tasks(args.root)}
    det = {tid for tid, t in tasks.items() if t.deterministic}

    # ---- ground truth, exactly as K1/K2 define it ----
    fired = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if line.strip():
            d = json.loads(line)
            fired[d["task_id"]].add(d["memory_id"])
    hits = {t: len(fired.get(t, ())) for t in det}
    disc = sorted(t for t in det if 1 <= hits[t] <= args.max_pool_hits)
    edges = {t: fired[t] for t in disc}
    n_edges = sum(len(v) for v in edges.values())
    log(f"ground truth: {len(disc)} discriminative tasks, {n_edges} bearing edges")
    if (len(disc), n_edges) != (75, 266):
        raise SystemExit(f"ground truth mismatch: expected 75 tasks / 266 edges, got "
                         f"{len(disc)} / {n_edges}; data or manifest differs from the paper's")
    breadth_cap = collections.Counter(collections.Counter(
        m for t in disc for m in edges[t]).values())
    over = [t for t in det if hits[t] > args.max_pool_hits]
    breadth_nocap = collections.Counter(collections.Counter(
        m for t in disc + over for m in fired[t]).values())
    screen_stats = {
        "n_deterministic_tasks": len(det),
        "n_zero_fire": sum(1 for t in det if hits[t] == 0),
        "n_discriminative_1_to_cap": len(disc),
        "n_over_cap": len(over),
        "breadth_with_cap": dict(sorted(breadth_cap.items())),
        "breadth_without_cap": dict(sorted(breadth_nocap.items())),
        "n_memories_bearing_with_cap": sum(breadth_cap.values()),
        "n_memories_bearing_without_cap": sum(breadth_nocap.values()),
    }
    log(f"screen split: {screen_stats['n_zero_fire']} zero-fire, {len(disc)} in 1..cap, "
        f"{len(over)} over cap, of {len(det)} deterministic tasks")

    pools = collections.defaultdict(list)
    for u in units:
        pools[u["domain"]].append(u["memory_unit_locator"])
    for d in pools:
        pools[d].sort()
    need = {loc for t in disc for loc in pools[tasks[t].domain]}
    log(f"loading text for {len(need)} pool units ...")
    texts = load_texts(args.root, need)

    chunks = {loc: chunks_by_tokens(texts[loc], CHUNK_TOKENS) for loc in sorted(need)} \
        if "dense_chunk" in methods else {}
    prefix = {loc: chunks_by_tokens(texts[loc], PREFIX_TOKENS, limit=1)[0]
              for loc in sorted(need)} if "dense_prefix" in methods else {}
    n_chunks = sum(len(v) for v in chunks.values())
    log(f"dense inputs: {n_chunks} chunks, {len(prefix)} prefixes, {len(disc)} queries")
    if args.dry_run:
        (args.out / "dry_run.json").write_text(json.dumps(
            {"screen_stats": screen_stats, "n_pool_units": len(need),
             "n_chunks": n_chunks}, indent=2))
        log("dry run: no embedding calls")
        return 0

    vec = {}
    if "dense_chunk" in methods or "dense_prefix" in methods:
        emb = EmbeddingClient(cache_path=str(args.out / "embeddings.jsonl"))
        items = [("q:" + t, tasks[t].question) for t in disc]
        items += [("p:" + loc, prefix[loc]) for loc in prefix]
        items += [(f"c:{loc}:{i}", c) for loc, cs in chunks.items() for i, c in enumerate(cs)]
        t0 = time.monotonic()
        B = 512
        for s in range(0, len(items), B):
            part = items[s:s + B]
            for (k, _), v in zip(part, emb.embed([x for _, x in part])):
                a = np.asarray(v, dtype=np.float32)
                vec[k] = a / np.linalg.norm(a)
            log(f"  embedded {min(s + B, len(items))}/{len(items)} "
                f"({(time.monotonic() - t0) / 60:.1f} min)")

    tok_docs = {loc: _WORD.findall(texts[loc].lower()) for loc in need} if "bm25" in methods else {}
    per_task = []
    for t in disc:
        pool = pools[tasks[t].domain]
        pos = np.array([loc in edges[t] for loc in pool])
        row = {"task_id": t, "domain": tasks[t].domain, "pool": len(pool),
               "n_bearing": int(pos.sum())}
        if "bm25" in methods:
            docs = [tok_docs[loc] for loc in pool]
            df = collections.Counter(w for d in docs for w in set(d))
            avgdl = sum(len(d) for d in docs) / len(docs)
            row["bm25"] = per_task_metrics(bm25_scores(tasks[t].question, docs, df,
                                                       len(docs), avgdl), pos)
        if "dense_prefix" in methods:
            q = vec["q:" + t]
            row["dense_prefix"] = per_task_metrics(
                np.array([q @ vec["p:" + loc] for loc in pool]), pos)
        if "dense_chunk" in methods:
            q = vec["q:" + t]
            row["dense_chunk"] = per_task_metrics(np.array(
                [max(q @ vec[f"c:{loc}:{i}"] for i in range(len(chunks[loc])))
                 for loc in pool]), pos)
        per_task.append(row)
    with open(args.out / "per_task.jsonl", "w") as fh:
        for r in per_task:
            fh.write(json.dumps(r) + "\n")

    summary = {"run_at_utc": utc_now(), "n_tasks": len(disc), "n_edges": n_edges,
               "pool_sizes": {d: len(v) for d, v in pools.items()},
               "chunk_tokens": CHUNK_TOKENS, "prefix_tokens": PREFIX_TOKENS,
               "tokenizer": OFFICIAL_TOKENIZER, "screen_stats": screen_stats,
               "methods": {}}
    for mth in methods:
        summary["methods"][mth] = {
            k: {"mean": float(np.mean([r[mth][k] for r in per_task])),
                "task_clustered_ci": clustered_ci([r[mth][k] for r in per_task])}
            for k in [f"recall@{k}" for k in KS] + ["mrr", "auroc"]}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    log(json.dumps(summary["methods"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

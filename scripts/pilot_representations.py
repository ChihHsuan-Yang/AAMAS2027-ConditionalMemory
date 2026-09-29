#!/usr/bin/env python3
"""B6: small live pilot of the three representations on real LongMemEval-V2 data.

Budget-capped by construction. ``--max-calls`` is enforced by a counter checked
BEFORE every request, not merely recorded in a config field: a limit that is
written down but never consulted is not a limit (this project has been bitten
by exactly that). Exceeding it aborts the run.

Segment selection is deterministic (seeded) and uses NO question, no
eval_function, and no answer. The selector reads the units manifest, which is
itself built from trajectories alone. There is no code path here by which a
future task can reach a writer.

    python3 scripts/pilot_representations.py --n 8 --max-calls 40
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.cache import ResponseCache                       # noqa: E402
from p1mem.client import P1Client                           # noqa: E402
from p1mem.memory import faithfulness as F                  # noqa: E402
from p1mem.memory import metrics as MT                      # noqa: E402
from p1mem.memory import representations as R               # noqa: E402
from p1mem.memory import semantic_type as ST                # noqa: E402
from p1mem.memory import tokens as T                        # noqa: E402
from p1mem.memory.prompts import prompt_manifest            # noqa: E402
from p1mem.memory.segment import SourceSegment              # noqa: E402
from p1mem.vendor.rcc_schema import utc_now                 # noqa: E402


class CallBudget:
    """A cap that BINDS. Checked before each call, raises when exhausted."""

    def __init__(self, limit: int):
        self.limit = int(limit)
        self.used = 0

    def take(self) -> None:
        if self.used >= self.limit:
            raise RuntimeError(
                f"endpoint call budget exhausted: {self.used}/{self.limit}. "
                f"Aborting rather than silently exceeding it.")
        self.used += 1


class BudgetedClient:
    """Wraps Sub-agent C's P1Client and charges the budget per real call.

    Cache hits are NOT charged: they cost no gateway request. The wrapper
    reports both numbers so the pilot's stated call count is the number of
    requests that actually left this machine.
    """

    def __init__(self, inner: P1Client, budget: CallBudget):
        self._inner = inner
        self._budget = budget
        self.cache = inner.cache
        self.cluster = inner.cluster
        self.model = inner.model
        self.n_real = 0
        self.n_cached = 0

    def chat(self, messages, **kw):
        self._budget.take()          # reserve BEFORE the request
        content, rec = self._inner.chat(messages, **kw)
        if getattr(rec, "cache_hit", False):
            self._budget.used -= 1   # refund: no request was made
            self.n_cached += 1
        else:
            self.n_real += 1
        return content, rec


def load_segments(root: Path, n: int, seed: int) -> list[SourceSegment]:
    """Deterministic sample of real page-visit units. No question is read."""
    manifest = REPO / "data" / "manifests" / "lmev2_memory_units_small.jsonl"
    units = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]

    # Prefer mid-sized units: the p99 is 487k tokens and a 500k-token prompt is
    # a different experiment (and would blow the context). Median is ~7.3k.
    # This is a SIZE filter, computed from the trajectory alone -- it is not a
    # content or informativeness filter, which the protocol forbids.
    eligible = [u for u in units if 500 <= (u.get("n_tokens") or 0) <= 12000]
    rng = random.Random(seed)
    by_traj: dict[str, list] = {}
    for u in eligible:
        by_traj.setdefault(u["trajectory_id"], []).append(u)
    # One unit per trajectory, so the pilot is not n views of one episode.
    trajs = sorted(by_traj)
    rng.shuffle(trajs)
    chosen = []
    for tid in trajs[:n]:
        chosen.append(rng.choice(sorted(by_traj[tid], key=lambda u: u["memory_id"])))
    want = {u["memory_id"] for u in chosen}
    meta = {u["memory_id"]: u for u in chosen}

    # Re-render the text from the trajectory with the adapter's own renderers.
    from p1mem.adapters import lmev2
    need_trajs = {u["trajectory_id"] for u in chosen}
    out: list[SourceSegment] = []
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] not in need_trajs:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_id not in want:
                continue
            m = meta[pv.memory_id]
            out.append(SourceSegment(
                segment_id=pv.memory_id,
                benchmark="longmemeval_v2",
                benchmark_version=lmev2.UPSTREAM_COMMIT,
                source_episode_id=pv.trajectory_id,
                text=pv.text,
                source_span={"trajectory_id": pv.trajectory_id,
                             "start_state_index": pv.start_state_index,
                             "end_state_index": pv.end_state_index,
                             "n_states": pv.n_states, "url": pv.url},
                # Past-episode metadata only. A task-shaped key would raise.
                episode_metadata={"domain": m["domain"],
                                  "environment": m["environment"],
                                  "outcome": m["outcome"],
                                  "recorded_n_tokens": m.get("n_tokens")},
            ))
        if len(out) >= len(want):
            break
    return sorted(out, key=lambda s: s.segment_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "pilot_representations")
    ap.add_argument("--max-tokens", type=int, default=512)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    budget = CallBudget(args.max_calls)

    print(f"[{utc_now()}] B6 pilot: n={args.n} seed={args.seed} "
          f"budget={args.max_calls} calls", flush=True)
    R.assert_all_writers_blind()
    print("writer blindness: signatures PASS", flush=True)
    print("tokenizer:", T.tokenizer_provenance(), flush=True)
    print("prompts:", json.dumps(prompt_manifest(), indent=1), flush=True)

    segs = load_segments(args.root, args.n, args.seed)
    print(f"loaded {len(segs)} real segments: "
          f"{[s.segment_id for s in segs]}", flush=True)

    cache = ResponseCache(args.out / "cache.jsonl")
    inner = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                     max_concurrency=4)
    client = BudgetedClient(inner, budget)

    raw_w = R.RawExtractiveWriter()
    sum_w = R.SummaryWriter(client, max_tokens=args.max_tokens)
    str_w = R.StructuredWriter(client, max_tokens=args.max_tokens)
    clf = ST.SemanticTypeClassifier(client, max_tokens=args.max_tokens)

    records, rows = [], []
    labels_by_segment: dict[str, dict[str, str]] = {}
    t0 = time.monotonic()

    for i, seg in enumerate(segs, 1):
        print(f"[{utc_now()}] segment {i}/{len(segs)} {seg.segment_id} "
              f"({len(seg.text)} chars) budget {budget.used}/{budget.limit}", flush=True)
        out = R.write_all(seg, raw=raw_w, summary=sum_w, structured=str_w)
        lab = clf.classify(seg)
        heur = ST.heuristic_semantic_type(seg)

        labels_by_segment[seg.segment_id] = {
            "llm_classifier": lab.semantic_type if lab.ok else None,
            "heuristic": heur.semantic_type,
            "structured_native": out["structured"].native_semantic_type,
        }
        labels_by_segment[seg.segment_id] = {
            k: v for k, v in labels_by_segment[seg.segment_id].items() if v is not None}

        for rep, rec in out.items():
            # A and B have no native label: attach the classifier's.
            if rep in ("raw", "summary") and lab.ok:
                rec.native_semantic_type = lab.semantic_type
            records.append(rec)
            fs = F.score_record(rec, seg.text)
            rows.append({**rec.to_dict(),
                         "faithfulness": fs.to_dict() if fs else None,
                         "semantic_type_label": (lab.to_dict() if rep != "structured"
                                                 else {"source": "structured_native",
                                                       "semantic_type": rec.native_semantic_type}),
                         "heuristic_label": heur.to_dict()})
            status = "ok" if rec.ok else f"FAIL {rec.error_code}"
            print(f"    {rep:<11} {status:<34} "
                  f"tok={rec.memory_tokens} cr="
                  f"{(f'{rec.compression_ratio:.4f}' if rec.compression_ratio else '-')} "
                  f"lat={rec.extraction_latency_s}", flush=True)
        print(f"    semantic_type: clf={lab.semantic_type}(ok={lab.ok}) "
              f"native={out['structured'].native_semantic_type} heur={heur.semantic_type}",
              flush=True)

    wall = time.monotonic() - t0
    stats = MT.summarise(records)

    # Faithfulness by representation, scored against each record's own source.
    src_by_seg = {s.segment_id: s.text for s in segs}
    by_rep_scores: dict[str, list] = {}
    for rec in records:
        fs = F.score_record(rec, src_by_seg[rec.segment_id])
        if fs is not None:
            by_rep_scores.setdefault(rec.representation, []).append(fs)
    faith = {rep: F.aggregate(v) for rep, v in by_rep_scores.items()}
    faith["raw_control"] = {
        "_what": "the source scored against itself -- MUST be 1.0 or the proxy is broken",
        "scores": [F.raw_control(t).to_dict() for t in list(src_by_seg.values())[:3]],
    }

    agree = ST.agreement_report(
        ST.paired_labels(labels_by_segment, "structured_native", "llm_classifier"))
    agree_heur = ST.agreement_report(
        ST.paired_labels(labels_by_segment, "structured_native", "heuristic"),
        name_b="heuristic_keyword")

    summary = {
        "run_at_utc": utc_now(),
        "wall_clock_s": round(wall, 2),
        "n_segments": len(segs),
        "segment_ids": [s.segment_id for s in segs],
        "budget": {"limit": budget.limit, "used_real_calls": client.n_real,
                   "cache_hits": client.n_cached, "counter": budget.used},
        "endpoint": {"cluster": inner.cluster, "model": inner.model, "url": inner.url},
        "decoding": {"temperature": 0.0, "max_tokens": args.max_tokens,
                     "reasoning_effort": "low"},
        "prompts": prompt_manifest(),
        "tokenizer": T.tokenizer_provenance(),
        "per_representation": {k: v.to_dict() for k, v in stats.items()},
        "faithfulness": faith,
        "semantic_type_agreement": agree,
        "semantic_type_agreement_vs_heuristic": agree_heur,
        "labels_by_segment": labels_by_segment,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out / "records.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")

    print()
    print(MT.frontier_table(stats))
    print()
    print(ST.format_agreement_report(agree))
    print()
    print(f"real endpoint calls: {client.n_real} (cache hits {client.n_cached}); "
          f"budget {budget.limit}")
    print(f"WROTE {args.out}/summary.json and records.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

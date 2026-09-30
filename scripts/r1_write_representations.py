#!/usr/bin/env python3
"""R1: write SUMMARY and STRUCTURED memories for the 60 screened memories.

Scope: exactly the memory units that appear in the BEARING and MATCHED_CONTROL
strata of ``data/manifests/k1_screened_cells.jsonl``. Those are the memories
the Raw arm was already evaluated on, so the three representations end up
measured on the SAME source experiences -- which is the whole point of the
paired design (prereg section 9).

The invariant (MEMORY_PROTOCOL section 0) is enforced by the code being called,
not by this script: ``R.assert_all_writers_blind()`` runs first, the writers
take a ``SourceSegment`` and nothing else, and ``SourceSegment`` rejects
task-shaped metadata at construction. This script reads the UNITS manifest and
the trajectories file. It never opens ``questions.jsonl``.

Budget: 2 calls per memory (summary + structured) = 120, enforced by a counter
checked BEFORE each request. A limit that is written down but never consulted
is not a limit.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem import schema as S                              # noqa: E402
from p1mem.adapters import lmev2                           # noqa: E402
from p1mem.cache import ResponseCache                      # noqa: E402
from p1mem.client import P1Client                          # noqa: E402
from p1mem.memory import faithfulness as F                 # noqa: E402
from p1mem.memory import metrics as MT                     # noqa: E402
from p1mem.memory import representations as R              # noqa: E402
from p1mem.memory import tokens as T                       # noqa: E402
from p1mem.memory.prompts import prompt_manifest           # noqa: E402
from p1mem.memory.segment import SourceSegment             # noqa: E402
from p1mem.vendor.rcc_schema import utc_now                # noqa: E402

STRATA = ("BEARING", "MATCHED_CONTROL")
LOCATOR = "memory_unit_locator"


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


class CallBudget:
    """A cap that BINDS: checked before each request, raises when exhausted."""

    def __init__(self, limit: int):
        self.limit = int(limit)
        self.used = 0
        import threading
        self._lock = threading.Lock()

    def take(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise RuntimeError(
                    f"endpoint call budget exhausted: {self.used}/{self.limit}. "
                    f"Aborting rather than silently exceeding it.")
            self.used += 1

    def refund(self) -> None:
        with self._lock:
            self.used -= 1


class BudgetedClient:
    """Charges the budget per REAL request; refunds cache hits."""

    def __init__(self, inner: P1Client, budget: CallBudget):
        self._inner = inner
        self._budget = budget
        self.cache = inner.cache
        self.cluster = inner.cluster
        self.model = inner.model
        self.n_real = 0
        self.n_cached = 0

    def chat(self, messages, **kw):
        self._budget.take()
        content, rec = self._inner.chat(messages, **kw)
        if getattr(rec, "cache_hit", False):
            self._budget.refund()
            self.n_cached += 1
        else:
            self.n_real += 1
        return content, rec


def load_segments(root: Path, locators: set[str], uloc: dict) -> list[SourceSegment]:
    """Re-render the exact page-visit text for each locator. A PARTIAL JOIN ABORTS."""
    need = {loc.split(":")[0] for loc in locators}
    out: list[SourceSegment] = []
    seen: set[str] = set()
    for traj in lmev2.read_jsonl(root / "trajectories.jsonl"):
        if traj["id"] not in need:
            continue
        for pv in lmev2.segment_page_visits(traj):
            if pv.memory_unit_locator not in locators or pv.memory_unit_locator in seen:
                continue
            seen.add(pv.memory_unit_locator)
            m = uloc[pv.memory_unit_locator]
            out.append(SourceSegment(
                segment_id=pv.memory_unit_locator,
                benchmark="longmemeval_v2",
                benchmark_version=lmev2.UPSTREAM_COMMIT,
                source_episode_id=pv.trajectory_id,
                text=pv.text,
                source_span={"trajectory_id": pv.trajectory_id,
                             "start_state_index": pv.start_state_index,
                             "end_state_index": pv.end_state_index,
                             "n_states": pv.n_states, "url": pv.url},
                # PAST-episode metadata only; a task-shaped key raises.
                episode_metadata={"domain": m["domain"],
                                  "environment": m["environment"],
                                  "outcome": m["outcome"],
                                  "recorded_n_tokens": m.get("n_tokens")},
            ))
        if len(out) >= len(locators):
            break
    if len(out) != len(locators):
        missing = sorted(locators - seen)
        raise RuntimeError(
            f"segment join matched {len(out)} of {len(locators)} units; missing "
            f"{missing[:5]}. A partial join must ABORT -- half a join still looks "
            f"like success.")
    return sorted(out, key=lambda s: s.segment_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--max-calls", type=int, default=160)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", type=Path, default=REPO / "results/repr_scaleup")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    R.assert_all_writers_blind()
    log("writer blindness: signatures PASS")
    log(f"tokenizer: {T.tokenizer_provenance()}")
    log(f"prompts: {json.dumps(prompt_manifest())}")

    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    bm = [c for c in design if c["stratum"] in STRATA]
    locators = {c[LOCATOR] for c in bm}
    log(f"design: {len(bm)} cells in {STRATA}, {len(locators)} distinct memories, "
        f"{len({c['task_id'] for c in bm})} distinct tasks")
    if len(locators) != 60:
        raise SystemExit(f"expected 60 memories, got {len(locators)}")

    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u[LOCATOR]: u for u in units}
    missing = locators - set(uloc)
    if missing:
        raise SystemExit(f"{len(missing)} locators absent from the units manifest")

    log(f"loading segment text for {len(locators)} units from {args.root} ...")
    t0 = time.monotonic()
    segs = load_segments(args.root, locators, uloc)
    log(f"loaded {len(segs)} segments in {time.monotonic() - t0:.1f}s")

    # The manifest recorded n_tokens at build time. Reproduce it here rather
    # than trusting it: a corpus rebuilt under a different segmentation would
    # keep the same locator and silently change the text.
    mismatch = [s.segment_id for s in segs
                if T.count_tokens(s.text) != int(uloc[s.segment_id]["n_tokens"])]
    if mismatch:
        raise SystemExit(
            f"{len(mismatch)} segments disagree with the manifest's recorded n_tokens "
            f"(e.g. {mismatch[:3]}). The text this script re-rendered is NOT the text "
            f"the screened run measured; refusing to write memories from it.")
    log(f"token-count reproduction vs manifest: {len(segs)}/{len(segs)} MATCH")

    n_planned = 2 * len(segs)
    log(f"PLANNED CALLS: {n_planned} (budget {args.max_calls})")
    if n_planned > args.max_calls:
        raise SystemExit(f"planned {n_planned} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        return 0

    budget = CallBudget(args.max_calls)
    cache = ResponseCache(args.out / "write_cache.jsonl")
    inner = P1Client(cluster="metis", model="gpt-oss-120b", cache=cache,
                     max_concurrency=args.workers)
    client = BudgetedClient(inner, budget)

    raw_w = R.RawExtractiveWriter()
    sum_w = R.SummaryWriter(client, max_tokens=args.max_tokens)
    str_w = R.StructuredWriter(client, max_tokens=args.max_tokens)

    def one(seg: SourceSegment) -> tuple[SourceSegment, dict[str, R.MemoryRecord]]:
        # write_all binds the segment ONCE and hands the same object to all
        # three writers -- protocol section 1's "same source segment" as a
        # structural default rather than a convention.
        return seg, R.write_all(seg, raw=raw_w, summary=sum_w, structured=str_w)

    log(f"writing {n_planned} model-written memories at concurrency {args.workers} ...")
    t0 = time.monotonic()
    got: dict[str, dict[str, R.MemoryRecord]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(one, s) for s in segs]
        for n, fut in enumerate(as_completed(futs), 1):
            seg, out = fut.result()
            got[seg.segment_id] = out
            if n % 10 == 0:
                log(f"  {n}/{len(segs)} segments "
                    f"(real={client.n_real} cached={client.n_cached})")
    wall = time.monotonic() - t0
    log(f"write pass done in {wall:.1f}s: real={client.n_real} cached={client.n_cached}")

    src_by_seg = {s.segment_id: s.text for s in segs}
    rows: list[dict[str, Any]] = []
    records: list[R.MemoryRecord] = []
    for seg in segs:
        out = got[seg.segment_id]
        for rep in ("raw", "summary", "structured"):
            rec = out[rep]
            records.append(rec)
            fs = F.score_record(rec, src_by_seg[seg.segment_id])
            rows.append({
                **rec.to_dict(),
                "memory_unit_locator": seg.segment_id,
                "manifest_memory_id": uloc[seg.segment_id]["memory_id"],
                "domain": uloc[seg.segment_id]["domain"],
                "faithfulness": fs.to_dict() if fs is not None else None,
            })

    ok = collections.Counter((r.representation, r.ok) for r in records)
    errs = collections.Counter(
        (r.representation, r.error_code) for r in records if not r.ok)
    log(f"write outcomes: {dict(ok)}")
    if errs:
        log(f"failures: {dict(errs)}")

    # --- TRUNCATION, read off the endpoint's own finish_reason -------------
    # ok=True does NOT mean the model finished: the client raises only when
    # finish_reason=="length" AND content is empty, and a summary cut off
    # mid-sentence arrives non-empty. Counted here so every rate below can
    # state whether it split on it.
    fr = collections.Counter((r.representation, r.finish_reason) for r in records)
    trunc = {rep: sum(1 for r in records if r.representation == rep and r.truncated)
             for rep in R.REPRESENTATIONS}
    trunc_ok = {rep: sum(1 for r in records
                         if r.representation == rep and r.truncated and r.ok)
                for rep in R.REPRESENTATIONS}
    log(f"finish_reason: {dict(fr)}")
    log(f"TRUNCATED (finish_reason=='length'): {trunc}; "
        f"of which admitted ok=True: {trunc_ok}")

    stats = MT.summarise(records)

    # --- faithfulness, with the raw control AND a planted negative control ----
    by_rep: dict[str, list] = {}
    for rec in records:
        fs = F.score_record(rec, src_by_seg[rec.segment_id])
        if fs is not None:
            by_rep.setdefault(rec.representation, []).append(fs)
    faith = {rep: F.aggregate(v) for rep, v in by_rep.items()}

    controls = {
        "_what": "the proxy must score a verbatim copy at 1.0 AND must FIRE on a "
                 "planted hallucination. A check only ever run on its home case is "
                 "not known to discriminate.",
        "raw_control_self_score": [
            {"segment_id": s.segment_id, **F.raw_control(s.text).to_dict()}
            for s in segs[:5]],
    }
    # Plant an invented number and an invented entity into a REAL summary and
    # require the proxy to fire. Without this a rate of 0 proves nothing.
    planted = []
    for rec in [r for r in records if r.representation == "summary" and r.ok][:5]:
        bad = rec.memory_text + (
            " The order total was $91735.42 and it was approved by Zorbulax Thringwell.")
        fs = F.score_text(bad, src_by_seg[rec.segment_id])
        planted.append({"segment_id": rec.segment_id,
                        "number_support": fs.number_support,
                        "entity_support": fs.entity_support,
                        "fires": bool((fs.number_support or 1.0) < 1.0)})
    controls["planted_hallucination"] = {
        "_what": "one invented number + one invented entity appended to a real summary; "
                 "number_support MUST drop below 1.0",
        "n": len(planted), "detail": planted,
        "n_fired": sum(1 for p in planted if p["fires"]),
        "all_fired": bool(planted) and all(p["fires"] for p in planted),
    }

    summary = {
        "_what": "R1 write pass: summary + structured for the 60 BEARING/MATCHED_CONTROL "
                 "memories of the screened design",
        "run_at_utc": utc_now(),
        "wall_clock_s": round(wall, 2),
        "n_segments": len(segs),
        "strata": list(STRATA),
        "design_cells_sha256": S.file_sha256(args.design),
        "budget": {"limit": budget.limit, "planned": n_planned,
                   "real_endpoint_calls": client.n_real,
                   "cache_hits": client.n_cached, "counter": budget.used},
        "endpoint": {"cluster": inner.cluster, "model": inner.model, "url": inner.url},
        "decoding": {"temperature": 0.0, "max_tokens": args.max_tokens,
                     "reasoning_effort": "low"},
        "prompts": prompt_manifest(),
        "tokenizer": T.tokenizer_provenance(),
        "write_outcomes": {f"{k[0]}:{'ok' if k[1] else 'FAIL'}": v
                           for k, v in sorted(ok.items())},
        "write_failures": {f"{k[0]}:{k[1]}": v for k, v in sorted(errs.items())},
        "truncation": {
            "_what": "the endpoint's OWN finish_reason per write call. ok=True does "
                     "NOT imply the model finished: P1Client raises only on "
                     "finish_reason=='length' WITH empty content, and a summary cut "
                     "off mid-sentence arrives non-empty and passes the writer's only "
                     "validity test (non-empty).",
            "finish_reason_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(
                fr.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
            "n_truncated": trunc,
            "n_truncated_admitted_ok": trunc_ok,
            "truncated_summary_segment_ids": sorted(
                r.segment_id for r in records
                if r.representation == "summary" and r.truncated),
            "truncated_structured_segment_ids": sorted(
                r.segment_id for r in records
                if r.representation == "structured" and r.truncated),
        },
        "malformed_structured": {
            "_definition": "structured writes whose output failed JSON parse or schema "
                           "validation. TWO denominators, because they answer different "
                           "questions and disagree.",
            "all_writes": {
                "numerator": sum(1 for r in records
                                 if r.representation == "structured" and not r.ok),
                "denominator": sum(1 for r in records
                                   if r.representation == "structured"),
            },
            "writes_that_finished": {
                "_definition": "restricted to finish_reason != 'length' -- writes the "
                               "model was allowed to complete",
                "numerator": sum(1 for r in records
                                 if r.representation == "structured"
                                 and not r.ok and not r.truncated),
                "denominator": sum(1 for r in records
                                   if r.representation == "structured"
                                   and not r.truncated),
            },
            "writes_that_hit_the_cap": {
                "numerator": sum(1 for r in records
                                 if r.representation == "structured"
                                 and not r.ok and r.truncated),
                "denominator": sum(1 for r in records
                                   if r.representation == "structured" and r.truncated),
            },
            "by_error_code": {k[1]: v for k, v in errs.items() if k[0] == "structured"},
        },
        "per_representation": {k: v.to_dict() for k, v in stats.items()},
        "faithfulness": faith,
        "faithfulness_controls": controls,
    }
    (args.out / "write_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (args.out / "memories.jsonl").write_text(
        "\n".join(json.dumps(r, default=str) for r in rows) + "\n")

    print()
    print(MT.frontier_table(stats))
    print()
    log(f"WROTE {args.out}/memories.jsonl ({len(rows)} rows) and write_summary.json")
    log(f"real endpoint calls: {client.n_real} (cache hits {client.n_cached})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

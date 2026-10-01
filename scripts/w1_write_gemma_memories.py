#!/usr/bin/env python3
"""W1: write SUMMARY and STRUCTURED memories with GEMMA, from the SAME segments.

This is a NEW WRITER ARM. It never touches results/repr_scaleup/memories.jsonl;
that file is opened read-only and its sha256 is asserted before and after.

WHAT VARIES: the writing model, and nothing else.
-------------------------------------------------
  W-GATE 0  writer blindness -- assert_all_writers_blind() + assert_writer_blind(),
            plus a POSITIVE CONTROL that a task-shaped metadata key RAISES.
  W-GATE 1  every segment re-renders to the manifest's recorded n_tokens.
  W-GATE 2  every segment's sha256 == the source_text_sha256 the GPT-OSS WRITE
            PASS recorded for the same locator. This is the decisive one: it
            compares the bytes the two writers were shown.
  W-GATE 3  the prompt version digests equal the gpt-oss run's byte-for-byte.
  W-GATE 4  memories.jsonl sha256 unchanged after the run.

Malformed structured output stays a FAILURE with its error code. No repair, no
fallback, no retry. The rate is a RESULT and is reported per writer.

reasoning_tokens is None on Gemma -- an absence, never 0.
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
from p1mem.memory.prompts import load_prompt, prompt_manifest  # noqa: E402
from p1mem.memory.segment import (SourceSegment, TaskLeakageError,  # noqa: E402
                                  assert_writer_signature)
from p1mem.vendor.rcc_schema import sha256_text, utc_now   # noqa: E402

STRATA = ("BEARING", "MATCHED_CONTROL")
LOCATOR = "memory_unit_locator"
OSS_MEMORIES = REPO / "results/repr_scaleup/memories.jsonl"
#: the sha256 the gpt-oss run AND the published reader arm both recorded.
OSS_MEMORIES_SHA = ("b342151c7f3cac5aa34ddd6d09981dd0272584343870a1c32994ae42a5"
                    "f7ce5a")


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
                    f"endpoint call budget exhausted: {self.used}/{self.limit}")
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
            f"{missing[:5]}. Half a join still looks like success.")
    return sorted(out, key=lambda s: s.segment_id)


def blindness_controls() -> dict:
    """W-GATE 0's POSITIVE CONTROLS. A barrier that has only ever passed is not
    known to discriminate, so each one is made to FIRE here."""
    out: dict[str, Any] = {}

    # 1. metadata denylist must RAISE on a task-shaped key
    fired = False
    try:
        SourceSegment(segment_id="p:0-0", benchmark="p", benchmark_version="0",
                      source_episode_id="p", text="t", source_span={},
                      episode_metadata={"question": "what is the answer"})
    except TaskLeakageError:
        fired = True
    out["metadata_denylist_raises_on_task_key"] = fired

    # 2. the arity barrier must RAISE on a writer that accepts a task
    def bad_writer(segment, task=None):  # noqa: ANN001
        return segment
    fired2 = False
    try:
        assert_writer_signature(bad_writer, name="bad_writer")
    except TaskLeakageError:
        fired2 = True
    out["arity_barrier_raises_on_two_param_writer"] = fired2

    # 3. a prompt carrying a {question} placeholder must fail to load
    import tempfile                                           # noqa: PLC0415
    from p1mem.memory.prompts import PromptError              # noqa: PLC0415
    fired3 = False
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "leaky_v1.txt"
        p.write_text("#!p1mem-prompt leaky_v1 1.0.0\n{segment_text}\n{question}\n")
        try:
            load_prompt("leaky_v1", prompt_dir=Path(td))
        except PromptError:
            fired3 = True
    out["prompt_placeholder_barrier_raises_on_question"] = fired3

    # 4. the structured validator must still REJECT a malformed object
    code, _ = R.validate_structured({"memory_type": "episodic"}, R.STRUCTURED_KEYS)
    out["structured_validator_rejects_missing_keys"] = code is not None
    code2, _ = R.validate_structured(
        {k: ("episodic" if k == "memory_type" else
             "high" if k == "confidence" else "x") for k in R.STRUCTURED_KEYS},
        R.STRUCTURED_KEYS)
    out["structured_validator_accepts_a_valid_object"] = code2 is None

    out["all_fired"] = all(v for k, v in out.items() if k != "all_fired")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--design", type=Path,
                    default=REPO / "data/manifests/k1_screened_cells.jsonl")
    ap.add_argument("--writer-arm", default="gemma_metis",
                    help="READER_ARMS id reused for its model/cluster/effort pins")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--max-calls", type=int, default=160)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", type=Path, default=REPO / "results/writer_factorial")
    ap.add_argument("--memories-name", default="memories_gemma.jsonl")
    ap.add_argument("--summary-name", default="write_summary_gemma.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plant-segment-defect", action="store_true",
                    help="POSITIVE CONTROL: corrupt one segment so W-GATE 2 aborts")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    arm = S.reader_arm(args.writer_arm)
    log(f"WRITER ARM {args.writer_arm!r}: model={arm['reader_model']!r} "
        f"cluster={arm['reader_cluster']!r} reasoning_effort={arm['reasoning_effort']!r}")

    # ---- W-GATE 0 ----
    R.assert_all_writers_blind()
    lmev2.assert_writer_blind()
    ctrls = blindness_controls()
    log(f"W-GATE 0 writer blindness: assert_all_writers_blind PASS, "
        f"assert_writer_blind PASS, positive controls {ctrls}")
    if not ctrls["all_fired"]:
        raise SystemExit("a blindness/validator positive control did NOT fire; "
                         "a barrier that cannot be shown to reject is not a barrier")

    # ---- the gpt-oss write pass, READ-ONLY ----
    sha_before = S.file_sha256(OSS_MEMORIES)
    if sha_before != OSS_MEMORIES_SHA:
        raise SystemExit(
            f"results/repr_scaleup/memories.jsonl sha256 {sha_before[:16]} != the "
            f"recorded {OSS_MEMORIES_SHA[:16]}; the gpt-oss writer arm on disk is "
            f"not the one the published results were measured on.")
    log(f"gpt-oss memories.jsonl sha256 {sha_before[:16]} MATCHES the published arm")
    oss_rows = [json.loads(l) for l in OSS_MEMORIES.read_text().splitlines() if l.strip()]
    oss = {(m["representation"], m[LOCATOR]): m for m in oss_rows}

    # ---- design ----
    design = [json.loads(l) for l in args.design.read_text().splitlines() if l.strip()]
    bm = [c for c in design if c["stratum"] in STRATA]
    locators = {c[LOCATOR] for c in bm}
    log(f"design: {len(bm)} cells in {STRATA}, {len(locators)} distinct memories")
    if len(locators) != 60:
        raise SystemExit(f"expected 60 memories, got {len(locators)}")

    units = [json.loads(l) for l in
             (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
              ).read_text().splitlines() if l.strip()]
    uloc = {u[LOCATOR]: u for u in units}

    log(f"loading segment text for {len(locators)} units from {args.root} ...")
    t0 = time.monotonic()
    segs = load_segments(args.root, locators, uloc)
    log(f"loaded {len(segs)} segments in {time.monotonic() - t0:.1f}s")
    if args.plant_segment_defect:
        s0 = segs[0]
        segs[0] = SourceSegment(
            segment_id=s0.segment_id, benchmark=s0.benchmark,
            benchmark_version=s0.benchmark_version,
            source_episode_id=s0.source_episode_id, text=s0.text + " ",
            source_span=s0.source_span, episode_metadata=s0.episode_metadata)
        log("PLANTED one-byte segment change; W-GATE 2 must abort")

    # ---- W-GATE 1: reproduce the manifest's recorded token count ----
    mismatch = [s.segment_id for s in segs
                if T.count_tokens(s.text) != int(uloc[s.segment_id]["n_tokens"])]
    if mismatch and not args.plant_segment_defect:
        raise SystemExit(
            f"{len(mismatch)} segments disagree with the manifest's n_tokens "
            f"(e.g. {mismatch[:3]})")
    log(f"W-GATE 1 token-count reproduction vs manifest: "
        f"{len(segs) - len(mismatch)}/{len(segs)} MATCH")

    # ---- W-GATE 2: the DECISIVE one. Same bytes shown to both writers. ----
    # The gpt-oss SUMMARY/STRUCTURED write recorded source_text_sha256 in its
    # own source_span. Comparing against it proves the two writers saw the same
    # segment, which no amount of "we used the same script" establishes.
    g2 = {"matched": 0, "mismatched": 0, "no_reference": 0}
    g2_bad = []
    for s in segs:
        want = (oss.get(("summary", s.segment_id)) or {}).get("source_span", {}).get(
            "source_text_sha256")
        if want is None:
            g2["no_reference"] += 1
            continue
        got = sha256_text(s.text)
        if got == want:
            g2["matched"] += 1
        else:
            g2["mismatched"] += 1
            g2_bad.append({"locator": s.segment_id, "oss": want[:16], "ours": got[:16]})
    log(f"W-GATE 2 segment byte-identity vs the gpt-oss WRITE pass: {g2}")
    if g2["mismatched"]:
        for b in g2_bad[:5]:
            log(f"  G2 MISMATCH {b}")
        raise SystemExit(
            f"{g2['mismatched']} segments differ in BYTES from what gpt-oss was "
            f"shown. The two writers would not have seen the same experience.")
    if g2["matched"] == 0:
        raise SystemExit("W-GATE 2 verified NOTHING -- a check that cannot fire "
                         "is not a check")

    # ---- W-GATE 3: the SAME prompts, byte-for-byte ----
    pm = prompt_manifest()
    oss_pv = {rep: sorted({m["prompt_version"] for m in oss_rows
                           if m["representation"] == rep})
              for rep in ("summary", "structured")}
    ours_pv = {"summary": pm["summary_v1"]["version"],
               "structured": pm["structured_v1"]["version"]}
    g3 = {rep: (oss_pv[rep] == [ours_pv[rep]]) for rep in ours_pv}
    log(f"W-GATE 3 prompt versions: ours={ours_pv} gptoss={oss_pv} match={g3}")
    if not all(g3.values()):
        raise SystemExit(
            f"prompt version differs from the gpt-oss writer arm: {oss_pv} vs "
            f"{ours_pv}. Only the MODEL may change.")
    # the digest must be able to MOVE -- otherwise equality proves nothing
    alt = sha256_text(load_prompt("summary_v1").text + " ")
    g3["digest_moves_on_a_one_byte_change"] = alt != pm["summary_v1"]["sha256"]

    n_planned = 2 * len(segs)
    log(f"PLANNED CALLS: {n_planned} (budget {args.max_calls})")
    if n_planned > args.max_calls:
        raise SystemExit(f"planned {n_planned} exceeds --max-calls {args.max_calls}")
    if args.dry_run:
        log("dry run: no calls issued")
        (args.out / "write_dryrun_gemma.json").write_text(json.dumps(
            {"planned_calls": n_planned, "wgate1_mismatch": len(mismatch),
             "wgate2": g2, "wgate3": g3, "blindness_controls": ctrls}, indent=2))
        return 0

    # ---- execute ----
    budget = CallBudget(args.max_calls)
    cache = ResponseCache(args.out / "write_cache_gemma.jsonl")
    # truncation_is_always_an_error=False on the WRITE pass, MATCHING the
    # gpt-oss write pass exactly. representations.py records finish_reason and
    # keeps a truncated-but-parseable memory on purpose; gpt-oss's 7 truncated
    # summaries are in the published arm on that basis. Turning the guard on
    # for Gemma's writes alone would make the two writer arms differ in their
    # ADMISSION RULE as well as their model. See the precommitment.
    inner = P1Client(cluster=arm["reader_cluster"], model=arm["reader_model"],
                     cache=cache, max_concurrency=args.workers,
                     truncation_is_always_an_error=False)
    client = BudgetedClient(inner, budget)

    sum_w = R.SummaryWriter(client, max_tokens=args.max_tokens,
                            reasoning_effort=arm["reasoning_effort"])
    str_w = R.StructuredWriter(client, max_tokens=args.max_tokens,
                               reasoning_effort=arm["reasoning_effort"])

    def one(seg: SourceSegment):
        return seg, {"summary": sum_w.write(seg), "structured": str_w.write(seg)}

    log(f"writing {n_planned} Gemma memories at concurrency {args.workers} ...")
    t0 = time.monotonic()
    got: dict[str, dict[str, R.MemoryRecord]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(one, s) for s in segs]
        for n, fut in enumerate(as_completed(futs), 1):
            seg, o = fut.result()
            got[seg.segment_id] = o
            if n % 10 == 0:
                log(f"  {n}/{len(segs)} segments "
                    f"(real={client.n_real} cached={client.n_cached})")
    wall = time.monotonic() - t0
    log(f"write pass done in {wall:.1f}s: real={client.n_real} cached={client.n_cached}")

    # ---- resolved-model audit ----
    log(f"resolved model pinned by P1Client._assert_model to {inner.model!r} "
        f"on every call (a mismatch raises)")

    src_by_seg = {s.segment_id: s.text for s in segs}
    rows: list[dict[str, Any]] = []
    records: list[R.MemoryRecord] = []
    for seg in segs:
        o = got[seg.segment_id]
        for rep in ("summary", "structured"):
            rec = o[rep]
            records.append(rec)
            fs = F.score_record(rec, src_by_seg[seg.segment_id])
            rows.append({
                **rec.to_dict(),
                LOCATOR: seg.segment_id,
                "manifest_memory_id": uloc[seg.segment_id]["memory_id"],
                "domain": uloc[seg.segment_id]["domain"],
                "faithfulness": fs.to_dict() if fs is not None else None,
                "writer_arm": args.writer_arm,
            })

    ok = collections.Counter((r.representation, r.ok) for r in records)
    errs = collections.Counter((r.representation, r.error_code)
                               for r in records if not r.ok)
    fr = collections.Counter((r.representation, r.finish_reason) for r in records)
    trunc = {rep: sum(1 for r in records if r.representation == rep and r.truncated)
             for rep in ("summary", "structured")}
    log(f"write outcomes: {dict(ok)}")
    log(f"failures: {dict(errs)}")
    log(f"finish_reason: {dict(fr)}; truncated: {trunc}")

    # ---- the memories MUST differ from gpt-oss's, or the writer never changed
    diff = {"compared": 0, "differ": 0, "identical": 0, "identical_examples": []}
    for r in rows:
        o = oss.get((r["representation"], r[LOCATOR]))
        if o is None or not o["ok"] or not r["ok"]:
            continue
        diff["compared"] += 1
        if o["memory_text"] != r["memory_text"]:
            diff["differ"] += 1
        else:
            diff["identical"] += 1
            if len(diff["identical_examples"]) < 3:
                diff["identical_examples"].append(
                    {"rep": r["representation"], "loc": r[LOCATOR]})
    log(f"Gemma vs gpt-oss memory text: {diff['differ']}/{diff['compared']} DIFFER "
        f"({diff['identical']} identical)")
    if diff["compared"] and diff["differ"] == 0:
        raise SystemExit(
            "every Gemma memory is byte-identical to gpt-oss's. The writer did "
            "not change; this would be an A/A comparison reported as A/B.")

    # ---- cost, per writer. NEVER pooled. ----
    def cost(recs, rep):
        rr = [r for r in recs if r.representation == rep]
        lat = [r.extraction_latency_s for r in rr if r.extraction_latency_s is not None]
        it = [r.extraction_input_tokens for r in rr if r.extraction_input_tokens is not None]
        ot = [r.extraction_output_tokens for r in rr if r.extraction_output_tokens is not None]
        rt = [r.extraction_reasoning_tokens for r in rr
              if r.extraction_reasoning_tokens is not None]
        return {
            "n_memories": len(rr),
            "n_calls": sum(r.extraction_calls for r in rr),
            "sum_input_tokens": sum(it) if it else None,
            "sum_output_tokens": sum(ot) if ot else None,
            "mean_input_tokens": (sum(it) / len(it)) if it else None,
            "mean_output_tokens": (sum(ot) / len(ot)) if ot else None,
            "mean_latency_s": (sum(lat) / len(lat)) if lat else None,
            "sum_latency_s": sum(lat) if lat else None,
            # None, NOT 0. metis/gemma returns no completion_tokens_details.
            "sum_reasoning_tokens": sum(rt) if rt else None,
            "n_rows_reporting_reasoning_tokens": len(rt),
            "_reasoning_tokens_note": (
                "None means the server returned no completion_tokens_details at "
                "all. That is an ABSENCE, not a measured zero, and a token-cost "
                "comparison against gpt-oss (which does report them) is therefore "
                "NOT apples-to-apples."),
        }

    gem_cost = {rep: cost(records, rep) for rep in ("summary", "structured")}

    class _Rec:  # minimal shim so the same cost() runs on the gpt-oss rows
        __slots__ = ("representation", "extraction_calls", "extraction_latency_s",
                     "extraction_input_tokens", "extraction_output_tokens",
                     "extraction_reasoning_tokens")

    oss_recs = []
    for m in oss_rows:
        if m["representation"] not in ("summary", "structured"):
            continue
        r = _Rec()
        r.representation = m["representation"]
        r.extraction_calls = m["extraction_calls"]
        r.extraction_latency_s = m["extraction_latency_s"]
        r.extraction_input_tokens = m["extraction_input_tokens"]
        r.extraction_output_tokens = m["extraction_output_tokens"]
        r.extraction_reasoning_tokens = m["extraction_reasoning_tokens"]
        oss_recs.append(r)
    oss_cost = {rep: cost(oss_recs, rep) for rep in ("summary", "structured")}

    stats = MT.summarise(records)

    by_rep: dict[str, list] = {}
    for rec in records:
        fs = F.score_record(rec, src_by_seg[rec.segment_id])
        if fs is not None:
            by_rep.setdefault(rec.representation, []).append(fs)
    faith = {rep: F.aggregate(v) for rep, v in by_rep.items()}

    # faithfulness proxy must still FIRE on a planted hallucination
    planted = []
    for rec in [r for r in records if r.representation == "summary" and r.ok][:5]:
        bad = rec.memory_text + (
            " The order total was $91735.42 and it was approved by Zorbulax Thringwell.")
        fs = F.score_text(bad, src_by_seg[rec.segment_id])
        planted.append({"segment_id": rec.segment_id,
                        "number_support": fs.number_support,
                        "fires": bool((fs.number_support or 1.0) < 1.0)})

    # ---- W-GATE 4: we did not touch the gpt-oss arm ----
    sha_after = S.file_sha256(OSS_MEMORIES)
    if sha_after != sha_before:
        raise SystemExit("results/repr_scaleup/memories.jsonl CHANGED during this run")
    log(f"W-GATE 4 gpt-oss memories.jsonl unchanged: {sha_after[:16]}")

    mem_path = args.out / args.memories_name
    mem_path.write_text("\n".join(json.dumps(r, default=str) for r in rows) + "\n")

    def _mal(rep: str) -> dict:
        rr = [r for r in records if r.representation == rep]
        fin = [r for r in rr if not r.truncated]
        cap = [r for r in rr if r.truncated]
        return {
            "all_writes": {"numerator": sum(1 for r in rr if not r.ok),
                           "denominator": len(rr)},
            "writes_that_finished": {
                "_definition": "finish_reason != 'length'",
                "numerator": sum(1 for r in fin if not r.ok),
                "denominator": len(fin)},
            "writes_that_hit_the_cap": {
                "numerator": sum(1 for r in cap if not r.ok),
                "denominator": len(cap)},
            "by_error_code": {k[1]: v for k, v in errs.items() if k[0] == rep},
        }

    summary = {
        "_what": "W1 WRITE PASS: Gemma-written summary + structured memories from "
                 "the SAME 60 BEARING/MATCHED_CONTROL segments gpt-oss saw. A NEW "
                 "writer arm; the gpt-oss arm is untouched.",
        "precommitment": "docs/WRITER_FACTORIAL_PRECOMMITMENT.md",
        "run_at_utc": utc_now(),
        "wall_clock_s": round(wall, 2),
        "writer_arm": args.writer_arm,
        "writer_identity": {
            "writer_model": arm["reader_model"],
            "writer_cluster": arm["reader_cluster"],
            "reasoning_effort_sent": arm["reasoning_effort"],
            "temperature": 0.0, "max_tokens": args.max_tokens,
            "workers": args.workers,
            "truncation_is_always_an_error_on_the_WRITE_pass": False,
            "_why_guard_off": (
                "MATCHES the gpt-oss write pass exactly. representations.py "
                "records finish_reason and keeps a truncated-but-parseable "
                "memory on purpose; gpt-oss's 7 truncated summaries and 3 "
                "truncated structured writes are in the published arm on that "
                "basis. Enabling it for Gemma alone would make the two writer "
                "arms differ in their ADMISSION RULE as well as their model."),
        },
        "n_segments": len(segs), "strata": list(STRATA),
        "gates": {
            "wgate0_writer_blindness_positive_controls": ctrls,
            "wgate1_token_count_reproduction": {
                "matched": len(segs) - len(mismatch), "total": len(segs)},
            "wgate2_segment_bytes_vs_gptoss_write_pass": g2,
            "wgate3_prompt_versions": {"ours": ours_pv, "gptoss": oss_pv, **g3},
            "wgate4_gptoss_memories_sha256_unchanged": {
                "before": sha_before, "after": sha_after, "unchanged": True},
        },
        "budget": {"limit": budget.limit, "planned": n_planned,
                   "real_endpoint_calls": client.n_real,
                   "cache_hits": client.n_cached, "counter": budget.used},
        "prompts": prompt_manifest(),
        "tokenizer": T.tokenizer_provenance(),
        "write_outcomes": {f"{k[0]}:{'ok' if k[1] else 'FAIL'}": v
                           for k, v in sorted(ok.items())},
        "write_failures": {f"{k[0]}:{k[1]}": v for k, v in sorted(errs.items())},
        "truncation": {
            "finish_reason_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(
                fr.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
            "n_truncated": trunc,
            "truncated_locators": {
                rep: sorted(r.segment_id for r in records
                            if r.representation == rep and r.truncated)
                for rep in ("summary", "structured")},
        },
        "MALFORMED_STRUCTURED_RATE_IS_A_RESULT": {
            "_rule": "NO silent repair, NO fallback to summary, NO retry. A "
                     "malformed structure is recorded with its error code and "
                     "the rate is reported PER WRITER.",
            "gemma": {rep: _mal(rep) for rep in ("summary", "structured")},
            "gptoss_same_segments": {
                rep: {
                    "all_writes": {
                        "numerator": sum(1 for m in oss_rows
                                         if m["representation"] == rep and not m["ok"]),
                        "denominator": sum(1 for m in oss_rows
                                           if m["representation"] == rep)},
                    "writes_that_finished": {
                        "numerator": sum(1 for m in oss_rows
                                         if m["representation"] == rep and not m["ok"]
                                         and not m.get("truncated")),
                        "denominator": sum(1 for m in oss_rows
                                           if m["representation"] == rep
                                           and not m.get("truncated"))},
                    "by_error_code": dict(collections.Counter(
                        m["error_code"] for m in oss_rows
                        if m["representation"] == rep and not m["ok"])),
                } for rep in ("summary", "structured")},
        },
        "FORMATION_COST_NEVER_POOLED": {
            "_rule": "Gemma and gpt-oss formation costs are different "
                     "currencies and are kept in separate blocks. Gemma reports "
                     "NO reasoning tokens at all -- an absence, never 0.",
            "gemma": gem_cost,
            "gptoss_same_segments": oss_cost,
        },
        "memory_text_differs_from_gptoss": diff,
        "per_representation": {k: v.to_dict() for k, v in stats.items()},
        "faithfulness": faith,
        "faithfulness_planted_control": {
            "_what": "one invented number appended to a real Gemma summary; "
                     "number_support MUST drop below 1.0",
            "n": len(planted), "n_fired": sum(1 for p in planted if p["fires"]),
            "all_fired": bool(planted) and all(p["fires"] for p in planted),
            "detail": planted},
    }

    checks = {
        "rows_on_disk_equals_expected":
            len([l for l in mem_path.read_text().splitlines() if l.strip()])
            == 2 * len(segs),
        "every_row_carries_the_locator": all(r.get(LOCATOR) for r in rows),
        "locators_match_the_gptoss_set":
            {r[LOCATOR] for r in rows} == {m[LOCATOR] for m in oss_rows},
        "writer_model_is_gemma": {r["writer_model"] for r in rows} == {arm["reader_model"]},
        "reasoning_tokens_all_null_never_zero":
            all(r["extraction_reasoning_tokens"] is None for r in rows),
        "no_failed_write_carries_memory_text":
            all((not r["ok"]) <= (r["memory_text"] == "") for r in rows),
        "every_failed_write_has_an_error_code":
            all(r["error_code"] for r in rows if not r["ok"]),
        "every_failed_structured_write_kept_its_raw_output":
            all(r["raw_model_output"] is not None for r in rows
                if not r["ok"] and r["representation"] == "structured"
                and r["error_code"] != R.ERR_CALL_FAILED),
        "prompt_version_equals_the_gptoss_one": all(g3[k] for k in ("summary", "structured")),
        "gptoss_memories_untouched": sha_after == sha_before,
        "memories_differ_from_gptoss": diff["differ"] > 0,
        "faithfulness_control_fired": summary["faithfulness_planted_control"]["all_fired"],
        "blindness_controls_fired": ctrls["all_fired"],
    }
    summary["artifact_checks"] = checks
    summary["VERDICT"] = "WRITE_PASSED" if all(checks.values()) else "WRITE_FAILED"
    log("ARTIFACT CHECKS (exit 0 is not success):")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k}")

    payload = json.dumps(summary, indent=2, default=str)
    (args.out / args.summary_name).write_text(payload)
    led = REPO / "results/ledgers/writer_factorial" / args.summary_name
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text(payload)
    print()
    print(MT.frontier_table(stats))
    print()
    log(f"WROTE {mem_path} ({len(rows)} rows); tracked summary {led}")
    log(f"VERDICT: {summary['VERDICT']}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

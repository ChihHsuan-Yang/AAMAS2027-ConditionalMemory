"""SWE-bench representation arm: Raw / Summary / Structured on matched cells.

WHY THIS SCRIPT EXISTS
----------------------
Every SWE-bench cell measured so far varies memory **presence** (WITH vs
WITHOUT). None carries a ``memory_representation`` field, so the cross-benchmark
representation figure could not include SWE-bench at all. This script adds the
missing axis.

WHAT IT INHERITS AND MUST NOT BREAK
-----------------------------------
* The **same gates** as the floor pilot: a passing scorer positive control and
  a passing apply-parity artifact for the current prompt version, both read
  from disk. This script refuses to run without them.
* The ``raw`` arm is byte-identical to the arm that PASSED parity
  (``render_memory(..., DEFANGED)``). The representation comparison is
  therefore anchored to a known-good arm rather than to a new rendering.

THE FAILURE THIS SCRIPT IS BUILT TO PREVENT
-------------------------------------------
v1 was voided by **diff-format contagion**: the reader imitated the ``+``/``-``
notation in the memory. A model-written summary of a raw diff can put that
notation straight back, inside a representation that is then compared against
raw as though the only difference were compression.

Two defences, both measured rather than asserted:

1. the writer's input is the **defanged** patch, so there is no diff syntax to
   copy (``to_source_segment``);
2. every written memory is checked with ``memory_contagion_risk`` BEFORE the
   reader ever sees it, and a dirty memory is **excluded from the cell set and
   counted**, never silently run.

🔴 An unapplicable edit is ``reward: None``, NEVER 0.0.
🔴 All three representations are run on the SAME cells, and only cells
   interpretable under ALL THREE enter the matched comparison -- the same rule
   the SciCode scale-up had to adopt when per-representation denominators
   diverged.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.client import P1Client, TruncatedResponseError  # noqa: E402
from p1mem.adapters.swebench import (  # noqa: E402
    apply_edits, build_future_tasks, build_memory_units,
)
from p1mem.adapters.swebench_harness import (  # noqa: E402
    Runner, checkout_base, git_show, is_single_file_solvable, score_patched_file,
)
from p1mem.adapters.swebench_localize import (  # noqa: E402
    assert_gold_blind, localize, recall_at_region,
)
from p1mem.adapters.swebench_prompt import (  # noqa: E402
    PROMPT_VERSION, PatchFormat, PromptVariant, assert_arm_symmetric,
    build_prompt, memory_body_for_representation, memory_contagion_risk,
    render_memory, response_has_diff_contagion, to_source_segment,
)
from p1mem.memory.representations import (  # noqa: E402
    STRUCTURED_KEYS, RawExtractiveWriter, StructuredWriter, SummaryWriter,
    render_structured, write_all,
)
from p1mem.vendor.rcc_schema import sha256_text  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swebench_pilot_v2 import (  # noqa: E402
    REPOS, ArmResult, check_parity, check_scorer_control, select_cells,
)

BENCHMARK_VERSION = "swebench_verified@princeton-nlp"
REPS = ("raw", "summary", "structured")


def _build(path: str, shown: str, issue: str, body: str | None):
    """One prompt. ``body=None`` is the WITHOUT arm."""
    common = dict(path=path, shown_region=shown, issue_text=issue,
                  variant=PromptVariant.V2_SYMMETRIC,
                  patch_format=PatchFormat.DEFANGED)
    return build_prompt(memory=None, memory_body=body, **common)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest",
                    default="data/manifests/swebench_pairs_file_seed20261008.jsonl")
    ap.add_argument("--parquet", default="/tmp/swebench/swebv.parquet")
    ap.add_argument("--cells", type=int, default=32)
    ap.add_argument("--repo", default="")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=120)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--writer-max-tokens", type=int, default=1024)
    ap.add_argument("--parity-artifact", default="results/swebench/parity_v2.json")
    ap.add_argument("--parity-threshold", type=float, default=0.10)
    ap.add_argument("--scorer-control", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    assert_gold_blind(localize)

    controls = a.scorer_control or ["results/swebench/scorer_control.json",
                                    "results/swebench/scorer_control_sympy.json"]
    ok, why = check_scorer_control(controls)
    print(f"GATE scorer control : {'PASS' if ok else 'FAIL'} -- {why}")
    if not ok:
        print("REFUSING to measure.")
        return 2
    ok, why = check_parity(a.parity_artifact, threshold=a.parity_threshold)
    print(f"GATE apply parity   : {'PASS' if ok else 'FAIL'} -- {why}")
    if not ok:
        print("REFUSING to measure.")
        return 2

    import pyarrow.parquet as pq
    rows = pq.read_table(a.parquet).to_pylist()
    mems = {m.instance_id: m for m in build_memory_units(rows)}
    tasks = {t.instance_id: t for t in build_future_tasks(rows)}
    chosen, skipped = select_cells(a.manifest, tasks, a.cells, a.repo, frozenset())
    print(f"  selected {len(chosen)} cells (skipped {skipped} multi-file gold fixes)")

    client = P1Client(cluster="metis", model="gpt-oss-120b")

    # ---------------- memory formation: ONE segment, three writers ---------
    need = sorted({c["memory_id"] for c in chosen})
    raw_w = RawExtractiveWriter()
    sum_w = SummaryWriter(client, max_tokens=a.writer_max_tokens,
                          temperature=0.0, reasoning_effort="low")
    str_w = StructuredWriter(client, variant="general",
                             max_tokens=a.writer_max_tokens,
                             temperature=0.0, reasoning_effort="low")

    def _write(mid: str):
        seg = to_source_segment(mems[mid], benchmark_version=BENCHMARK_VERSION)
        return mid, write_all(seg, raw=raw_w, summary=sum_w, structured=str_w)

    written: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for mid, recs in ex.map(_write, need):
            written[mid] = recs
    print(f"  memories written: {len(written)}")

    # ---------------- contagion screen on the MEMORY, before any reader ----
    bodies: dict[tuple[str, str], str] = {}
    contagion: dict[str, Any] = {}
    dirty: list[dict[str, Any]] = []
    write_fail: list[dict[str, str]] = []
    for mid in need:
        for rep in REPS:
            if rep == "raw":
                body = render_memory(mems[mid], PatchFormat.DEFANGED)
            else:
                rec = written[mid].get(rep)
                if rec is None or not rec.ok:
                    write_fail.append({"memory_id": mid, "representation": rep,
                                       "error_code": getattr(rec, "error_code", "missing")})
                    continue
                text = (render_structured(rec.structured, STRUCTURED_KEYS)
                        if rep == "structured" and getattr(rec, "structured", None)
                        else rec.memory_text)
                body = memory_body_for_representation(rep, m=mems[mid], written_text=text)
            risk = memory_contagion_risk(body)
            contagion[f"{mid}::{rep}"] = risk
            if not risk["clean"]:
                dirty.append({"memory_id": mid, "representation": rep, **risk})
                continue
            bodies[(mid, rep)] = body

    print(f"  contagion screen: {len(dirty)} dirty memory bodies EXCLUDED, "
          f"{len(write_fail)} write failures")
    for d in dirty[:5]:
        print(f"    DIRTY {d['memory_id']} {d['representation']}: {d}")

    # ---------------- the cells -------------------------------------------
    out_cells: list[dict[str, Any]] = []
    calls = 0
    for c in chosen:
        t, d = tasks[c["task_id"]], mems[c["memory_id"]]
        path = c["shared_files"][0]
        rd, runner = REPOS[c["repo"]]["dir"], REPOS[c["repo"]]["runner"]
        if not checkout_base(rd, t.base_commit):
            print(f"  SKIP {t.instance_id}: cannot check out"); continue
        src = git_show(rd, t.base_commit, path)
        if src is None:
            print(f"  SKIP {t.instance_id}: {path} absent at base"); continue
        regions = localize(src, t.problem_statement, path=path,
                           top_k=a.top_k, max_lines=a.max_lines)
        recall = recall_at_region(regions, t.patch, path)
        shown = "\n\n".join(r.render() for r in regions)

        p_without = _build(path, shown, t.problem_statement, None)

        def _run(bp) -> ArmResult:
            nonlocal calls
            try:
                content, rec = client.chat(
                    [{"role": "system", "content": bp.system},
                     {"role": "user", "content": bp.user}],
                    max_tokens=a.max_tokens, temperature=0.0,
                    reasoning_effort="low")
            except TruncatedResponseError as e:
                calls += 1
                return ArmResult(arm="", edit_status="truncated", reward=None,
                                 prompt_sha256=sha256_text(bp.system + "\n" + bp.user),
                                 test_detail=str(e)[:300])
            calls += 1
            er = apply_edits(src, content)
            ar = ArmResult(arm="", edit_status=er.failure_mode, reward=None,
                           n_blocks=er.n_blocks, misses=list(er.misses),
                           response=content or "",
                           contagion=response_has_diff_contagion(content),
                           prompt_sha256=sha256_text(bp.system + "\n" + bp.user),
                           input_tokens=rec.input_tokens, output_tokens=rec.output_tokens,
                           reasoning_tokens=rec.reasoning_tokens,
                           finish_reason=rec.finish_reason)
            if er.applied:
                ar.reward, ar.test_detail = score_patched_file(
                    rd, runner, t, path, er.new_text)
            return ar

        # WITHOUT is shared across representations: the prompt carries no
        # memory, so it is byte-identical for all three. Running it once and
        # reusing it is not a shortcut -- it makes the three contrasts share
        # one baseline, and it gives the free F_exec control the SciCode
        # scale-up used, since any per-rep disagreement would be pure noise.
        without = _run(p_without)
        without.arm = "WITHOUT"

        for rep in REPS:
            body = bodies.get((d.instance_id, rep))
            if body is None:
                out_cells.append({"memory_id": d.instance_id, "task_id": t.instance_id,
                                  "repo": c["repo"], "path": path, "representation": rep,
                                  "localizer_recall": recall, "excluded": True,
                                  "exclusion_reason": "memory unavailable or contagion-dirty",
                                  "arms": {"WITHOUT": asdict(without)}})
                continue
            p_with = _build(path, shown, t.problem_statement, body)
            assert_arm_symmetric(p_without, p_with)
            with_ = _run(p_with); with_.arm = "WITH"
            out_cells.append({
                "memory_id": d.instance_id, "task_id": t.instance_id,
                "repo": c["repo"], "path": path, "representation": rep,
                "localizer_recall": recall, "excluded": False,
                "memory_contagion": contagion.get(f"{d.instance_id}::{rep}"),
                "arms": {"WITHOUT": asdict(without), "WITH": asdict(with_)},
            })
        print(f"  {t.instance_id:26s} recall={'HIT ' if recall else 'MISS'} calls={calls}")

    payload = {
        "summary": {
            "mode": "representation",
            "prompt_version": PROMPT_VERSION,
            "patch_format": PatchFormat.DEFANGED.value,
            "prompt_variant": PromptVariant.V2_SYMMETRIC.value,
            "model": "gpt-oss-120b", "cluster": "metis",
            "temperature": 0.0, "reasoning_effort": "low",
            "max_tokens": a.max_tokens, "writer_max_tokens": a.writer_max_tokens,
            "structured_variant": "general",
            "benchmark_version": BENCHMARK_VERSION,
            "n_cells_selected": len(chosen), "n_calls": calls,
            "n_memories": len(written),
            "contagion_dirty_excluded": len(dirty),
            "write_failures": len(write_fail),
            "dirty_detail": dirty, "write_fail_detail": write_fail,
            "WITHOUT_shared_across_representations": True,
        },
        "cells": out_cells,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(payload, indent=1))
    print(f"\nwritten: {a.out}  ({calls} calls, {len(out_cells)} rep-cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

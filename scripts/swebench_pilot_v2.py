"""Arm-symmetric SWE-bench pilot: parity screen, then the floor measurement.

WHAT THIS REPLACES
------------------
``swebench_floor_pilot.py`` (v1) measured both-arms-fail 4/7 = 57.1% and was
correctly stopped: the WITH arm failed to produce an applicable edit three
times as often as WITHOUT (3/7 vs 0/7). Re-eliciting those three failures with
the response text CAPTURED -- v1 stored only the status -- showed the cause is
**diff-format contagion**: the memory's ```` ```diff ```` fence teaches the
reader to answer in diff syntax instead of SEARCH/REPLACE. See
``p1mem.adapters.swebench_prompt``.

TWO MODES, AND THE ORDER IS BINDING
-----------------------------------
``--mode parity``  measure WITH-arm apply-failure against WITHOUT's. This is a
                   FORMAT measurement and reports no reward.
``--mode floor``   the localized pilot: both-arms-fail, solve rate per arm,
                   apply-failure rate per arm, paired DeltaU.

🔴 **No SWE-bench number enters any table until parity holds.** ``--mode
floor`` therefore REFUSES to run unless a parity artifact for the same prompt
version says so, and unless a scorer positive control artifact exists and
passed. Both are checked from files on disk, not from an assertion in prose.

WHAT IS RECORDED THAT v1 DID NOT RECORD
---------------------------------------
* the model's **raw response** for every arm of every cell -- a stored status
  is a verifier, not a recovery, and v1's missing text is why the mechanism
  had to be re-elicited at all;
* ``assert_arm_symmetric`` is called on **every cell**, not once in a test;
* a contagion diagnostic per response, so a later reader sees WHY a block
  failed rather than a bare label;
* the prompt version, patch format, and both prompts' sha256.

🔴 An unapplicable edit is ``reward: None``, NEVER 0.0. Scoring those as zero
on the v1 data would have shown memory HARMING (2/7 vs 3/7) -- harm
manufactured entirely by an edit-format artifact.

Usage
-----
    PYTHONPATH=src python3 scripts/swebench_pilot_v2.py --mode parity --cells 12 \
        --out results/swebench/parity_v2.json
    PYTHONPATH=src python3 scripts/swebench_pilot_v2.py --mode floor --cells 35 \
        --out results/swebench/floor_pilot_v2.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters.swebench import (  # noqa: E402
    apply_edits,
    build_future_tasks,
    build_memory_units,
)
from p1mem.adapters.swebench_harness import (  # noqa: E402
    Runner,
    checkout_base,
    git_show,
    is_single_file_solvable,
    score_patched_file,
)
from p1mem.adapters.swebench_localize import (  # noqa: E402
    assert_gold_blind,
    localize,
    recall_at_region,
)
from p1mem.adapters.swebench_prompt import (  # noqa: E402
    PROMPT_VERSION,
    PatchFormat,
    PromptVariant,
    assert_arm_symmetric,
    build_prompt,
    response_has_diff_contagion,
)
from p1mem.vendor.rcc_schema import sha256_text  # noqa: E402

REPOS: dict[str, dict[str, Any]] = {
    "django/django": {
        "dir": Path("/tmp/swebench/django"),
        "runner": Runner("django", "/tmp/swebench/venv_dj39/bin/python"),
    },
    "sympy/sympy": {
        "dir": Path("/tmp/swebench/sympy"),
        # Python 3.9 with py==1.10.0 and mpmath==1.2.1. Each pin was forced by
        # the scorer control failing 0/5 under 3.13; see swebench_harness.
        "runner": Runner("pytest", "/tmp/swebench/venv_sympy39/bin/python"),
    },
}


@dataclass
class ArmResult:
    arm: str
    edit_status: str            # ok | no_block | search_miss
    reward: float | None        # None when no edit applied -- NEVER 0.0
    n_blocks: int = 0
    misses: list[str] = field(default_factory=list)
    response: str = ""          # kept: a status is not a recovery
    contagion: dict[str, Any] = field(default_factory=dict)
    prompt_sha256: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None
    finish_reason: str = ""
    test_detail: str = ""


@dataclass
class CellResult:
    memory_id: str
    task_id: str
    repo: str
    path: str
    localizer_recall: bool
    region_lines: list[list[int]]
    arms: dict[str, Any]
    interpretable: bool
    arm_symmetric: bool


# --------------------------------------------------------------------------
# the gates that stand between this script and a table
# --------------------------------------------------------------------------


def check_scorer_control(paths: list[str]) -> tuple[bool, str]:
    """Require a PASSING scorer positive control artifact, read from disk."""
    if not paths:
        return False, "no scorer-control artifact named"
    runners, total, passed, neg_ok, neg_n = set(), 0, 0, 0, 0
    for p in paths:
        f = Path(p)
        if not f.exists():
            return False, f"scorer control artifact missing: {p}"
        s = json.loads(f.read_text())["summary"]
        if s["n_attempted"] == 0 or s["n_pass"] != s["n_attempted"]:
            return False, f"{p}: {s['n_pass']}/{s['n_attempted']} -- NOT clean"
        runners.update(s.get("runner_kinds", []))
        total += s["n_attempted"]
        passed += s["n_pass"]
        neg_ok += s.get("negative_control_pass", 0)
        neg_n += s.get("negative_control_attempted", 0)
    if neg_n == 0 or neg_ok != neg_n:
        return False, f"negative control {neg_ok}/{neg_n} -- a control that "
    return True, (f"{passed}/{total} across runners {sorted(runners)}, "
                  f"negative control {neg_ok}/{neg_n}")


def check_parity(path: str, *, threshold: float) -> tuple[bool, str]:
    """Require a parity artifact, for THIS prompt version, that reached parity."""
    f = Path(path)
    if not f.exists():
        return False, f"parity artifact missing: {path}"
    s = json.loads(f.read_text())["summary"]
    if s.get("prompt_version") != PROMPT_VERSION:
        return False, (f"parity was measured under {s.get('prompt_version')!r}, "
                       f"not the current {PROMPT_VERSION!r}")
    gap = s["apply_fail_rate_WITH"] - s["apply_fail_rate_WITHOUT"]
    if gap > threshold:
        return False, (f"apply-failure gap {gap:+.3f} exceeds {threshold} "
                       f"(WITH {s['apply_fail_WITH']}/{s['n_arms']}, "
                       f"WITHOUT {s['apply_fail_WITHOUT']}/{s['n_arms']})")
    return True, (f"gap {gap:+.3f} (WITH {s['apply_fail_WITH']}/{s['n_arms']}, "
                  f"WITHOUT {s['apply_fail_WITHOUT']}/{s['n_arms']})")


# --------------------------------------------------------------------------


def select_cells(manifest: str, tasks: dict, n: int, repo: str = "",
                 skip: frozenset[str] = frozenset()) -> tuple[list[dict], int]:
    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    skipped = 0
    for c in (json.loads(l) for l in open(manifest)):
        if c["repo"] not in REPOS or c["task_id"] in seen:
            continue
        if repo and c["repo"] != repo:
            continue
        if c["task_id"] in skip:
            continue
        if not is_single_file_solvable(tasks[c["task_id"]].files, c["shared_files"][0]):
            skipped += 1
            continue
        seen.add(c["task_id"])
        chosen.append(c)
        if len(chosen) >= n:
            break
    return chosen, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["parity", "floor"], required=True)
    ap.add_argument("--manifest",
                    default="data/manifests/swebench_pairs_file_seed20261008.jsonl")
    ap.add_argument("--parquet", default="/tmp/swebench/swebv.parquet")
    ap.add_argument("--cells", type=int, default=12)
    ap.add_argument("--repo", default="")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=120)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--variant", default=PromptVariant.V2_SYMMETRIC.value,
                    choices=[v.value for v in PromptVariant])
    ap.add_argument("--patch-format", default=PatchFormat.DEFANGED.value,
                    choices=[f.value for f in PatchFormat])
    ap.add_argument("--skip-tasks", default="",
                    help="comma-separated task ids to exclude (e.g. the parity screen's)")
    ap.add_argument("--parity-artifact", default="results/swebench/parity_v2.json")
    ap.add_argument("--parity-threshold", type=float, default=0.10)
    ap.add_argument("--scorer-control", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    variant = PromptVariant(args.variant)
    pfmt = PatchFormat(args.patch_format)

    assert_gold_blind(localize)

    controls = args.scorer_control or ["results/swebench/scorer_control.json",
                                       "results/swebench/scorer_control_sympy.json"]
    if args.mode == "floor":
        ok, why = check_scorer_control(controls)
        print(f"GATE scorer control : {'PASS' if ok else 'FAIL'} -- {why}")
        if not ok:
            print("REFUSING to measure. Fix the scorer before measuring anything.")
            return 2
        ok, why = check_parity(args.parity_artifact, threshold=args.parity_threshold)
        print(f"GATE apply parity   : {'PASS' if ok else 'FAIL'} -- {why}")
        if not ok:
            print("REFUSING to measure. No SWE-bench number enters a table "
                  "until WITH-arm apply failure reaches parity.")
            return 2

    import pyarrow.parquet as pq
    rows = pq.read_table(args.parquet).to_pylist()
    mems = {m.instance_id: m for m in build_memory_units(rows)}
    tasks = {t.instance_id: t for t in build_future_tasks(rows)}

    skip = frozenset(x for x in args.skip_tasks.split(",") if x)
    chosen, skipped = select_cells(args.manifest, tasks, args.cells, args.repo, skip)
    print(f"  selected {len(chosen)} cells "
          f"(skipped {skipped} multi-file gold fixes, {len(skip)} held out)")

    from p1mem.client import P1Client
    client = P1Client(cluster="metis", model="gpt-oss-120b")

    results: list[CellResult] = []
    calls = 0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for c in chosen:
        t, d = tasks[c["task_id"]], mems[c["memory_id"]]
        path = c["shared_files"][0]
        rd, runner = REPOS[c["repo"]]["dir"], REPOS[c["repo"]]["runner"]
        if not checkout_base(rd, t.base_commit):
            print(f"  SKIP {t.instance_id}: cannot check out {t.base_commit[:10]}")
            continue
        src = git_show(rd, t.base_commit, path)
        if src is None:
            print(f"  SKIP {t.instance_id}: {path} absent at base")
            continue

        regions = localize(src, t.problem_statement, path=path,
                           top_k=args.top_k, max_lines=args.max_lines)
        recall = recall_at_region(regions, t.patch, path)
        shown = "\n\n".join(r.render() for r in regions)

        common = dict(path=path, shown_region=shown, issue_text=t.problem_statement,
                      variant=variant, patch_format=pfmt)
        p_without = build_prompt(memory=None, **common)
        p_with = build_prompt(memory=d, **common)

        symmetric = True
        if variant is PromptVariant.V2_SYMMETRIC:
            # Per cell, not once in a test: a scaffold change that reintroduces
            # an arm-only instruction must stop the run.
            assert_arm_symmetric(p_without, p_with)
        else:
            symmetric = False

        arms: dict[str, Any] = {}
        for arm, bp in (("WITHOUT", p_without), ("WITH", p_with)):
            content, rec = client.chat(
                [{"role": "system", "content": bp.system},
                 {"role": "user", "content": bp.user}],
                max_tokens=args.max_tokens, temperature=0.0, reasoning_effort="low")
            calls += 1
            er = apply_edits(src, content)
            ar = ArmResult(
                arm=arm, edit_status=er.failure_mode, reward=None,
                n_blocks=er.n_blocks, misses=list(er.misses), response=content or "",
                contagion=response_has_diff_contagion(content),
                prompt_sha256=sha256_text(bp.system + "\n" + bp.user),
                input_tokens=rec.input_tokens, output_tokens=rec.output_tokens,
                reasoning_tokens=rec.reasoning_tokens, finish_reason=rec.finish_reason)
            if er.applied and args.mode == "floor":
                # reward is computed ONLY for an applicable edit. An
                # unapplicable one stays None; a 0.0 here would manufacture a
                # harmful memory out of an edit-format artifact.
                ar.reward, ar.test_detail = score_patched_file(
                    rd, runner, t, path, er.new_text)
            arms[arm] = asdict(ar)

        results.append(CellResult(
            memory_id=d.instance_id, task_id=t.instance_id, repo=c["repo"], path=path,
            localizer_recall=recall,
            region_lines=[[r.start_line, r.end_line] for r in regions],
            arms=arms, interpretable=recall, arm_symmetric=symmetric))
        print(f"  {t.instance_id:26s} recall={'HIT ' if recall else 'MISS'} "
              + " ".join(f"{k}={v['edit_status']}"
                         + (f"/{v['reward']}" if v["reward"] is not None else "")
                         for k, v in arms.items()), flush=True)
        out_path.write_text(json.dumps(
            {"summary": summarize(results, calls, args, variant, pfmt),
             "cells": [asdict(r) for r in results]}, indent=2))

    summary = summarize(results, calls, args, variant, pfmt)
    out_path.write_text(json.dumps(
        {"summary": summary, "cells": [asdict(r) for r in results]}, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nwrote {out_path}  (model calls: {calls})")
    return 0


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------


def _wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _cluster_bootstrap(pairs: list[tuple[str, float]], n_boot: int = 10000,
                       seed: int = 20261008) -> dict[str, Any] | None:
    """Paired mean with a CI clustered on the DONOR memory.

    Cells sharing a donor are not independent -- one memory appears in up to 4
    cells -- so the resample unit is the donor, not the cell. Resampling cells
    would understate the interval.
    """
    if not pairs:
        return None
    import random as _r
    by: dict[str, list[float]] = {}
    for g, v in pairs:
        by.setdefault(g, []).append(v)
        groups = None
    groups = sorted(by)
    obs = sum(v for _g, v in pairs) / len(pairs)
    rng = _r.Random(seed)
    boots: list[float] = []
    for _ in range(n_boot):
        vals: list[float] = []
        for _i in range(len(groups)):
            vals.extend(by[groups[rng.randrange(len(groups))]])
        boots.append(sum(vals) / len(vals))
    boots.sort()
    return {"mean": round(obs, 4), "n_pairs": len(pairs), "n_clusters": len(groups),
            "ci95_clustered": [round(boots[int(0.025 * n_boot)], 4),
                               round(boots[int(0.975 * n_boot)], 4)],
            "cluster_unit": "donor memory_id", "n_boot": n_boot}


def summarize(results: list[CellResult], calls: int, args, variant, pfmt) -> dict[str, Any]:
    interp = [r for r in results if r.interpretable and r.arms]

    def st(r, a): return r.arms.get(a, {}).get("edit_status")
    def rw(r, a): return r.arms.get(a, {}).get("reward")

    n = len(interp)
    af_with = sum(1 for r in interp if st(r, "WITH") != "ok")
    af_without = sum(1 for r in interp if st(r, "WITHOUT") != "ok")

    out: dict[str, Any] = {
        "mode": args.mode,
        "prompt_version": (PROMPT_VERSION if variant is PromptVariant.V2_SYMMETRIC
                           else "swebench_v1"),
        "prompt_variant": variant.value,
        "patch_format": pfmt.value,
        "max_tokens": args.max_tokens,
        "model": "gpt-oss-120b", "cluster": "metis", "temperature": 0.0,
        "reasoning_effort": "low",
        "n_cells": len(results),
        "localizer_recall": sum(1 for r in results if r.localizer_recall),
        "n_interpretable": n,
        "n_arms": n,
        "all_cells_arm_symmetric": all(r.arm_symmetric for r in results) and bool(results),
        "apply_fail_WITH": af_with,
        "apply_fail_WITHOUT": af_without,
        "apply_fail_rate_WITH": round(af_with / n, 4) if n else None,
        "apply_fail_rate_WITHOUT": round(af_without / n, 4) if n else None,
        "apply_fail_gap": round((af_with - af_without) / n, 4) if n else None,
        "apply_fail_denominator": n,
        "apply_fail_ci95_WITH": _wilson(af_with, n),
        "apply_fail_ci95_WITHOUT": _wilson(af_without, n),
        "edit_status_WITH": _counts(interp, "WITH"),
        "edit_status_WITHOUT": _counts(interp, "WITHOUT"),
        "diff_contagion_WITH": _contagion(interp, "WITH"),
        "diff_contagion_WITHOUT": _contagion(interp, "WITHOUT"),
        "model_calls": calls,
    }

    if args.mode == "floor":
        both_fail = sum(1 for r in interp
                        if (rw(r, "WITH") or 0.0) == 0.0
                        and (rw(r, "WITHOUT") or 0.0) == 0.0)
        sw = sum(1 for r in interp if rw(r, "WITH") == 1.0)
        so = sum(1 for r in interp if rw(r, "WITHOUT") == 1.0)
        both_ok = [r for r in interp
                   if rw(r, "WITH") is not None and rw(r, "WITHOUT") is not None]
        bf_ok = sum(1 for r in both_ok
                    if rw(r, "WITH") == 0.0 and rw(r, "WITHOUT") == 0.0)
        disc = [(r.memory_id, rw(r, "WITH") - rw(r, "WITHOUT")) for r in both_ok]
        n_pos = sum(1 for _g, v in disc if v > 0)
        n_neg = sum(1 for _g, v in disc if v < 0)
        out.update({
            "both_arms_fail": both_fail,
            "both_arms_fail_pct": round(100.0 * both_fail / n, 2) if n else None,
            "both_arms_fail_ci95": _wilson(both_fail, n),
            "both_arms_fail_denominator": n,
            "solve_WITH": sw, "solve_WITHOUT": so,
            "solve_rate_WITH": round(sw / n, 4) if n else None,
            "solve_rate_WITHOUT": round(so / n, 4) if n else None,
            "n_both_applicable": len(both_ok),
            "both_arms_fail_both_applicable": bf_ok,
            "both_arms_fail_pct_both_applicable": (
                round(100.0 * bf_ok / len(both_ok), 2) if both_ok else None),
            "delta_u_paired": _cluster_bootstrap(disc),
            "discordant_pairs": {"WITH_better": n_pos, "WITHOUT_better": n_neg},
            "reward_none_count": sum(1 for r in interp for a in ("WITH", "WITHOUT")
                                     if rw(r, a) is None),
            "reward_zero_count": sum(1 for r in interp for a in ("WITH", "WITHOUT")
                                     if rw(r, a) == 0.0),
            "no_apply_failure_scored_zero": all(
                rw(r, a) is None
                for r in interp for a in ("WITH", "WITHOUT")
                if st(r, a) != "ok"),
        })
    return out


def _counts(rs: list[CellResult], arm: str) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(r.arms.get(arm, {}).get("edit_status", "n/a") for r in rs))


def _contagion(rs: list[CellResult], arm: str) -> dict[str, int]:
    cs = [r.arms.get(arm, {}).get("contagion", {}) for r in rs]
    return {
        "responses_with_diff_marker_lines": sum(
            1 for c in cs if c.get("n_diff_marker_lines", 0) > 0),
        "total_diff_marker_lines": sum(c.get("n_diff_marker_lines", 0) for c in cs),
        "missing_separator": sum(1 for c in cs if not c.get("has_separator")),
        "missing_replace_marker": sum(1 for c in cs if not c.get("has_replace_marker")),
    }


if __name__ == "__main__":
    raise SystemExit(main())

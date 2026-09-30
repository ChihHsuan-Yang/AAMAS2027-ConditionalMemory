"""Floor-effect pilot for SWE-bench Verified, with gold-blind localization.

THE QUESTION
------------
On LongMemEval, ~80% both-arms-fail meant two full arms measured nothing. The
single number that decides whether SWE-bench can host the experiment is the
**both-arms-fail rate**. This script measures it.

WHY THIS SCRIPT EXISTS (the first pilot was void)
-------------------------------------------------
The first attempt showed the reader the first 90 lines of each file while the
gold patch edited lines up to 1,386. A byte-exact SEARCH for unseen code is
impossible, so ``search_miss`` was the only reachable outcome. This run uses
``p1mem.adapters.swebench_localize``, whose signature structurally cannot
accept a patch, and it **reports localizer recall so an uninterpretable cell
is excluded from the floor statistic rather than counted as a failure.**

THREE OUTCOMES THAT MUST NOT BE CONFLATED
-----------------------------------------
``no_block``     the reader emitted no well-formed edit  -> FORMAT failure
``search_miss``  the edit did not match the shown source -> LOCATION failure
``applied``      the edit applied; only then is a test result meaningful

An unapplicable edit is an ERROR, not a reward of 0. Scoring it as 0 would
push DeltaU negative and manufacture a "harmful" memory -- the exact defect
``p1mem.client`` already guards for truncation. ``reward`` is therefore
``None`` (not 0.0) whenever no edit applied, and the summary reports the
apply-failure rate with its own denominator.

Usage
-----
    PYTHONPATH=src python3 scripts/swebench_floor_pilot.py \
        --cells 10 --top-k 5 --out results/swebench/floor_pilot.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters.swebench import (  # noqa: E402
    SEARCH_REPLACE_INSTRUCTIONS,
    apply_edits,
    build_future_tasks,
    build_memory_units,
    render_raw_memory,
)
from p1mem.adapters.swebench_localize import (  # noqa: E402
    assert_gold_blind,
    localize,
    recall_at_region,
)

SYSTEM = "You edit Python source to fix a bug.\n" + SEARCH_REPLACE_INSTRUCTIONS

#: Filled from --max-tokens so the summary records the arm parameter actually used.
MAX_TOKENS_USED = [0]


@dataclass
class ArmResult:
    arm: str
    edit_status: str          # ok | no_block | search_miss
    reward: float | None      # None when no edit applied -- NEVER 0.0
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


def checkout_base(repo_dir: Path, commit: str) -> bool:
    """Put the worktree at this recipient's base commit, discarding leftovers."""
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "--", "."], check=False)
    subprocess.run(["git", "-C", str(repo_dir), "clean", "-qfd"], check=False)
    r = subprocess.run(["git", "-C", str(repo_dir), "-c", "advice.detachedHead=false",
                        "checkout", "-q", commit], capture_output=True, text=True)
    return r.returncode == 0


def git_show(repo_dir: Path, commit: str, path: str) -> str | None:
    p = subprocess.run(["git", "-C", str(repo_dir), "show", f"{commit}:{path}"],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def run_tests(repo_dir: Path, runner: dict[str, Any], tests: list[str]) -> tuple[bool, str]:
    """Run the recipient's tests. Returns (all_passed, tail_of_output).

    Exit code alone is not trusted for the django runner, which reports through
    its own summary line; both runners are matched on their output.
    """
    if runner["kind"] == "pytest":
        cmd = [runner["python"], "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"]
        cwd = repo_dir
    else:  # django
        cmd = [runner["python"], "runtests.py", *tests, "--settings=test_sqlite", "-v1"]
        cwd = repo_dir / "tests"
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    out = (p.stdout + p.stderr).strip()
    tail = "\n".join(out.splitlines()[-4:])
    if runner["kind"] == "pytest":
        ok = p.returncode == 0 and " failed" not in out and " error" not in out
    else:
        # Django's runner prints a bare "OK" or "FAILED (...)" on its own line and
        # then trailing notes ("Destroying test database..."), so neither
        # endswith() nor a substring test is safe -- an early "OK" line combined
        # with a later failure would read as a pass. Scan the status lines.
        # "OK", "OK (skipped=5)" and "OK (expected failures=1)" are all passes;
        # "FAILED (errors=1)" is not. Trailing "Destroying test database..."
        # lines mean the status is NOT the last line, so scan for status lines
        # rather than inspecting the tail. Both spellings were observed during
        # bring-up and each silently mis-scored a gold patch as a failure.
        status = [ln.strip() for ln in out.splitlines()
                  if ln.strip() == "OK" or ln.strip().startswith(("OK (", "FAILED"))]
        ok = bool(status) and all(x.startswith("OK") for x in status) and p.returncode == 0
    return ok, tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest",
                    default="data/manifests/swebench_pairs_file_seed20261008.jsonl")
    ap.add_argument("--parquet", default="/tmp/swebench/swebv.parquet")
    ap.add_argument("--cells", type=int, default=10)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=120)
    ap.add_argument("--max-tokens", type=int, default=1024,
                    help="512 is consumed entirely by reasoning on these prompts "
                         "(observed reasoning_tokens=510, empty content), which the "
                         "client correctly refuses to score. Recorded as an arm "
                         "parameter: WITH and WITHOUT must share it.")
    ap.add_argument("--out", default="results/swebench/floor_pilot.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="localize and report recall, make NO model calls")
    args = ap.parse_args()

    # The guarantee that keeps this pilot interpretable.
    assert_gold_blind(localize)

    import pyarrow.parquet as pq
    rows = pq.read_table(args.parquet).to_pylist()
    mems = {m.instance_id: m for m in build_memory_units(rows)}
    tasks = {t.instance_id: t for t in build_future_tasks(rows)}

    repos = {
        "django/django": {
            "dir": Path("/tmp/swebench/django"),
            "runner": {"kind": "django", "python": "/tmp/swebench/venv_dj39/bin/python"},
        },
        "sympy/sympy": {
            "dir": Path("/tmp/swebench/sympy"),
            "runner": {"kind": "pytest", "python": "/tmp/swebench/venv_sympy/bin/python"},
        },
    }

    cells = [json.loads(l) for l in open(args.manifest)]
    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    skipped_multifile = 0
    for c in cells:
        if c["repo"] not in repos or c["task_id"] in seen:
            continue
        t = tasks[c["task_id"]]
        # ELIGIBILITY: this harness shows and edits ONE file, so a recipient whose
        # gold fix spans several files is UNSOLVABLE BY CONSTRUCTION. Including it
        # would guarantee a 0.0 and inflate both-arms-fail with a harness artifact
        # -- the same "only reachable outcome" defect that voided the first pilot.
        # Caught by the scorer's positive control failing on a 5-file fix.
        if len(t.files) != 1 or t.files[0] != c["shared_files"][0]:
            skipped_multifile += 1
            continue
        seen.add(c["task_id"])
        chosen.append(c)
        if len(chosen) >= args.cells:
            break
    print(f"  (skipped {skipped_multifile} recipients whose gold fix spans >1 file)")

    client = None
    if not args.dry_run:
        from p1mem.client import P1Client
        client = P1Client(cluster="metis", model="gpt-oss-120b")

    MAX_TOKENS_USED[0] = args.max_tokens
    results: list[CellResult] = []
    calls = 0
    for c in chosen:
        t = tasks[c["task_id"]]
        d = mems[c["memory_id"]]
        path = c["shared_files"][0]
        rd = repos[c["repo"]]["dir"]
        # Each recipient has its OWN base commit. Leaving the worktree where the
        # previous cell left it makes the gold patch fail to apply and every
        # reward a harness artifact.
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
        arms: dict[str, Any] = {}

        if not args.dry_run:
            for arm, ctx in (("WITHOUT", ""), ("WITH", render_raw_memory(d) + "\n\n")):
                user = (f"### Candidate regions of {path}\n```python\n{shown}\n```\n\n"
                        f"### Issue\n{t.problem_statement.strip()[:1500]}\n\n"
                        "Make the minimal edit that fixes the issue.")
                content, _ = client.chat(
                    [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": ctx + user}],
                    max_tokens=args.max_tokens, temperature=0.0,
                    reasoning_effort="low")
                calls += 1
                er = apply_edits(src, content)
                if not er.applied:
                    arms[arm] = asdict(ArmResult(arm, er.failure_mode, None))
                    continue
                res = _score_arm(rd, repos[c["repo"]]["runner"], t, path, er.new_text)
                arms[arm] = asdict(ArmResult(arm, "ok", res[0], res[1]))

        results.append(CellResult(
            memory_id=d.instance_id, task_id=t.instance_id, repo=c["repo"], path=path,
            localizer_recall=recall,
            region_lines=[[r.start_line, r.end_line] for r in regions],
            arms=arms, interpretable=recall,
        ))
        print(f"  {t.instance_id:26s} recall={'HIT ' if recall else 'MISS'} "
              f"{ {k: v['edit_status'] for k, v in arms.items()} }")

    summary = summarize(results, calls)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"summary": summary, "cells": [asdict(r) for r in results]}, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nwrote {out}  (model calls: {calls})")
    return 0


def _score_arm(repo_dir: Path, runner: dict[str, Any], task, path: str,
               new_text: str) -> tuple[float, str]:
    """Write the edited file, run F2P and P2P, restore. Reward in {0.0, 1.0}."""
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)
    subprocess.run(["git", "-C", str(repo_dir), "apply", "-"],
                   input=task.test_patch, text=True, check=False)
    target = repo_dir / path
    backup = target.read_text()
    try:
        target.write_text(new_text)
        f2p_ok, detail = run_tests(repo_dir, runner, _test_ids(task.fail_to_pass, runner))
        p2p_ok = True
        if f2p_ok and task.pass_to_pass:
            p2p_ok, _ = run_tests(repo_dir, runner,
                                  _test_ids(task.pass_to_pass[:20], runner))
        return (1.0 if (f2p_ok and p2p_ok) else 0.0, detail)
    finally:
        target.write_text(backup)
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)


def _test_ids(tests, runner) -> list[str]:
    """Normalize SWE-bench test ids to the runner's CLI form.

    Django stores ``test_x (module.Class)``; its runner wants
    ``module.Class`` (the whole class -- running a single method in isolation
    breaks tests that mutate shared state, which produced a FALSE failure of
    the gold patch during harness bring-up).
    """
    out: list[str] = []
    for t in tests:
        if runner["kind"] == "django":
            # Django's verbose runner prints a test's DOCSTRING instead of its
            # name when it has one, and SWE-bench records exactly what was
            # printed. So a P2P entry may be prose ("F expressions can be used
            # in Meta.ordering.") rather than an id. Passing that to runtests.py
            # makes it error, which read as a gold-patch FAILURE and would have
            # turned every django cell into a false both-arms-fail. Drop the
            # prose entries -- an id has no spaces and is dotted.
            if "(" in t and t.endswith(")"):
                out.append(t.split("(", 1)[1].rstrip(")"))
            elif " " not in t and "." in t:
                out.append(t)
            # else: a docstring label, not addressable -- skip it
        else:
            out.append(t)
    # de-duplicate, keep order
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def summarize(results: list[CellResult], calls: int) -> dict[str, Any]:
    interp = [r for r in results if r.interpretable and r.arms]
    scored = [r for r in interp
              if r.arms.get("WITH", {}).get("reward") is not None
              or r.arms.get("WITHOUT", {}).get("reward") is not None]
    def _st(r, arm): return r.arms.get(arm, {}).get("edit_status")
    def _rw(r, arm): return r.arms.get(arm, {}).get("reward")
    n_i = len(interp)
    both_fail = sum(1 for r in interp
                    if (_rw(r, "WITH") or 0.0) == 0.0 and (_rw(r, "WITHOUT") or 0.0) == 0.0)
    return {
        "n_cells": len(results),
        "eligibility": "single-file gold fix only (multi-file is unsolvable by this harness)",
        "localizer_recall": sum(1 for r in results if r.localizer_recall),
        "localizer_recall_pct": (100.0 * sum(1 for r in results if r.localizer_recall)
                                 / len(results)) if results else 0.0,
        "n_interpretable": n_i,
        "both_arms_fail": both_fail,
        "both_arms_fail_pct": (100.0 * both_fail / n_i) if n_i else None,
        "solve_WITH": sum(1 for r in interp if _rw(r, "WITH") == 1.0),
        "solve_WITHOUT": sum(1 for r in interp if _rw(r, "WITHOUT") == 1.0),
        "apply_fail_WITH": sum(1 for r in interp if _st(r, "WITH") != "ok"),
        "apply_fail_WITHOUT": sum(1 for r in interp if _st(r, "WITHOUT") != "ok"),
        "apply_fail_denominator": n_i,
        "edit_status_WITH": _counts(interp, "WITH"),
        "edit_status_WITHOUT": _counts(interp, "WITHOUT"),
        "n_scored_cells": len(scored),
        "model_calls": calls,
        "max_tokens": MAX_TOKENS_USED[0],
    }


def _counts(rs: list[CellResult], arm: str) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(r.arms.get(arm, {}).get("edit_status", "n/a") for r in rs))


if __name__ == "__main__":
    raise SystemExit(main())

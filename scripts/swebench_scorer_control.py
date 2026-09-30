"""Positive control for the SWE-bench scorer. NO model calls.

THE CLAIM UNDER TEST
--------------------
For each cell: applying the **gold patch** must score **1.0**, and the
**unedited base file** must score **0.0**. Two directions, so a scorer that
always returns 1.0 and a scorer that always returns 0.0 both fail.

WHY THIS RUNS BEFORE EVERY PILOT
--------------------------------
The predecessor's control went **0/6 -> 3/6 -> 10/10** while four harness
defects were fixed, and every one produced a plausible ``0.0`` rather than a
crash:

1. multi-file gold fixes are unsolvable by a single-file harness;
2. the worktree was not reset to each recipient's base commit;
3. django records a test's DOCSTRING where an id belongs -- one
   ``PASS_TO_PASS`` entry was literally ``"F expressions can be used in
   Meta.ordering."``;
4. ``OK (skipped=5)`` is a pass, and trailing "Destroying test database..."
   lines mean the status is not the last line.

Without the control, ~100% both-arms-fail would have been reported and the
benchmark killed on four bugs in its own harness.

IT SCORES THROUGH THE PILOT'S OWN SCORER
----------------------------------------
Both this script and ``swebench_floor_pilot.py`` call
``p1mem.adapters.swebench_harness.score_patched_file``. A control that
exercises a private copy certifies nothing about the code the pilot runs.

IT ALSO PROVES IT CAN FAIL
--------------------------
``--negative-control`` corrupts the gold patch by hand -- deleting the single
added line -- and requires that the corrupted "gold" scores 0.0. A control
only ever run on data it is guaranteed to pass detects nothing known.

Usage
-----
    PYTHONPATH=src python3 scripts/swebench_scorer_control.py --cells 10 \
        --out results/swebench/scorer_control.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.adapters.swebench import build_future_tasks  # noqa: E402
from p1mem.adapters.swebench_harness import (  # noqa: E402
    Runner,
    checkout_base,
    git_show,
    is_single_file_solvable,
    score_patched_file,
)

REPOS: dict[str, dict[str, Any]] = {
    "django/django": {
        "dir": Path("/tmp/swebench/django"),
        "runner": Runner("django", "/tmp/swebench/venv_dj39/bin/python"),
    },
    "sympy/sympy": {
        "dir": Path("/tmp/swebench/sympy"),
        # Python 3.9, NOT 3.13: sympy at these commits imports distutils,
        # removed in 3.12, so every test errored before running and every
        # gold patch scored 0.0 -- defect (5b), found by the control.
        "runner": Runner("pytest", "/tmp/swebench/venv_sympy39/bin/python"),
    },
}


def apply_gold_to_text(repo_dir: Path, task, path: str, base_src: str) -> str | None:
    """The gold post-image of ``path``: ``git show <base>:<path>`` + gold patch.

    Applied with ``git apply`` to a clean tree, then read back, so the result
    is the real post-image and not a hand-reconstructed one.
    """
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)
    p = subprocess.run(["git", "-C", str(repo_dir), "apply", "-"],
                       input=task.patch, text=True, capture_output=True)
    if p.returncode != 0:
        # stderr is NOT suppressed: a gold patch that will not apply is an
        # instrument failure and must not look like a scored 0.0.
        print(f"    gold apply FAILED rc={p.returncode}: {p.stderr.strip()[:200]}")
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)
        return None
    text = (repo_dir / path).read_text()
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)
    return text if text != base_src else None


def corrupt_gold(gold_text: str, base_src: str, level: int = 1) -> str | None:
    """Break the gold fix in the smallest way that should still score 0.0.

    Deletes the FIRST line the gold patch inserted, located by POSITION with
    ``difflib`` rather than by set membership. Membership silently failed to
    construct a corruption on 3 of 10 cells, because an added line such as
    ``    allow_distinct = True`` also occurs elsewhere in the same file and
    so "already in base" -- an unconstructed corruption is an untested cell
    that reads as a clean skip.
    """
    import difflib as _dl
    a, b = base_src.splitlines(), gold_text.splitlines()
    sm = _dl.SequenceMatcher(a=a, b=b, autojunk=False)
    ops = sm.get_opcodes()
    inserted = [j for tag, _i1, _i2, j1, j2 in ops
                if tag in ("insert", "replace")
                for j in range(j1, j2) if b[j].strip()]
    if level in (1, 2):
        if not inserted:
            return None
        if level == 1:
            j = inserted[0]
            return "\n".join(b[:j] + b[j + 1:]) + "\n"
        drop = set(inserted)
        return "\n".join(x for i, x in enumerate(b) if i not in drop) + "\n"

    # level 3: PUT BACK a line the gold patch DELETED.
    #
    # Levels 1-2 only ever undo insertions, so they cannot corrupt a fix whose
    # active ingredient is a removal. sympy-20801 is a pure two-line MOVE: the
    # same `if not self: return not other` is deleted from one branch and
    # re-inserted later, and it is the DELETION that fixes the bug. Dropping
    # the re-inserted copy therefore leaves a program that still passes, and
    # scoring it 1.0 is the scorer being CORRECT, not failing. Restoring the
    # deleted line is the corruption that actually breaks such a fix.
    for tag, i1, i2, j1, _j2 in ops:
        if tag in ("delete", "replace"):
            for i in range(i1, i2):
                if a[i].strip():
                    return "\n".join(b[:j1] + [a[i]] + b[j1:]) + "\n"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest",
                    default="data/manifests/swebench_pairs_file_seed20261008.jsonl")
    ap.add_argument("--parquet", default="/tmp/swebench/swebv.parquet")
    ap.add_argument("--cells", type=int, default=10)
    ap.add_argument("--repo", default="", help="restrict to one repo. The control "
                    "must be run on BOTH runners: a scorer exercised only on the "
                    "django runner is not known to discriminate on the pytest one.")
    ap.add_argument("--negative-control", action="store_true",
                    help="also require a hand-corrupted gold patch to score 0.0")
    ap.add_argument("--out", default="results/swebench/scorer_control.json")
    args = ap.parse_args()

    import pyarrow.parquet as pq
    rows = pq.read_table(args.parquet).to_pylist()
    tasks = {t.instance_id: t for t in build_future_tasks(rows)}

    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    for c in (json.loads(l) for l in open(args.manifest)):
        if c["repo"] not in REPOS or c["task_id"] in seen:
            continue
        if args.repo and c["repo"] != args.repo:
            continue
        t = tasks[c["task_id"]]
        if not is_single_file_solvable(t.files, c["shared_files"][0]):
            continue
        seen.add(c["task_id"])
        chosen.append(c)
        if len(chosen) >= args.cells:
            break

    records: list[dict[str, Any]] = []
    for c in chosen:
        t = tasks[c["task_id"]]
        path = c["shared_files"][0]
        rd, runner = REPOS[c["repo"]]["dir"], REPOS[c["repo"]]["runner"]
        rec: dict[str, Any] = {"task_id": t.instance_id, "repo": c["repo"], "path": path}
        if not checkout_base(rd, t.base_commit):
            rec["error"] = f"cannot check out {t.base_commit}"
            records.append(rec)
            print(f"  {t.instance_id:26s} ERROR checkout")
            continue
        base_src = git_show(rd, t.base_commit, path)
        if base_src is None:
            rec["error"] = f"{path} absent at base"
            records.append(rec)
            continue

        gold_text = apply_gold_to_text(rd, t, path, base_src)
        if gold_text is None:
            rec["error"] = "gold patch did not apply, or changed nothing"
            records.append(rec)
            print(f"  {t.instance_id:26s} ERROR gold")
            continue

        g_reward, g_detail = score_patched_file(rd, runner, t, path, gold_text)
        b_reward, b_detail = score_patched_file(rd, runner, t, path, base_src)
        rec.update(gold_reward=g_reward, base_reward=b_reward,
                   gold_detail=g_detail[:300], base_detail=b_detail[:300],
                   pass_=(g_reward == 1.0 and b_reward == 0.0))
        line = f"  {t.instance_id:26s} gold={g_reward} base={b_reward}"

        if args.negative_control:
            bad = corrupt_gold(gold_text, base_src, level=1)
            if bad is None:
                rec["negative_control"] = "could not construct a corruption"
            else:
                n_reward, _ = score_patched_file(rd, runner, t, path, bad)
                rec["corrupt_gold_reward"] = n_reward
                rec["corruption_level"] = 1
                if n_reward == 1.0:
                    # A one-line deletion was not enough to break this fix --
                    # a property of the PATCH, not of the scorer. sympy-20801
                    # is a pure two-line MOVE, so dropping one line leaves a
                    # program that still passes. Escalate DETERMINISTICALLY
                    # rather than excuse the cell: drop EVERY inserted line.
                    # If even that scores 1.0, the F2P test does not test the
                    # fix and the cell is a real scorer failure.
                    for lvl in (2, 3):
                        nxt = corrupt_gold(gold_text, base_src, level=lvl)
                        if nxt is None or nxt == bad:
                            continue
                        n_next, _ = score_patched_file(rd, runner, t, path, nxt)
                        rec[f"corrupt_gold_reward_level{lvl}"] = n_next
                        rec["corruption_level"] = lvl
                        n_reward = n_next
                        if n_next == 0.0:
                            break
                rec["negative_control_pass"] = (n_reward == 0.0)
                line += f" corrupt(L{rec['corruption_level']})={n_reward}"
        records.append(rec)
        print(line + ("  PASS" if rec["pass_"] else "  ** FAIL **"), flush=True)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(_summarize(records, args), indent=2))

    summary = _summarize(records, args)
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary["summary"], indent=2))
    s = summary["summary"]
    ok = s["n_pass"] == s["n_attempted"] and s["n_attempted"] > 0
    if args.negative_control:
        ok = ok and s["negative_control_pass"] == s["negative_control_attempted"] \
            and s["negative_control_attempted"] > 0
    print(f"\nwrote {args.out}")
    print("SCORER CONTROL: " + ("PASS" if ok else "FAIL -- do not measure anything"))
    return 0 if ok else 1


def _summarize(records: list[dict[str, Any]], args) -> dict[str, Any]:
    scored = [r for r in records if "pass_" in r]
    neg = [r for r in records if "negative_control_pass" in r]
    return {
        "summary": {
            "n_cells_selected": len(records),
            "n_attempted": len(scored),
            "n_error": sum(1 for r in records if "error" in r),
            "n_pass": sum(1 for r in scored if r["pass_"]),
            "n_gold_scored_1": sum(1 for r in scored if r["gold_reward"] == 1.0),
            "n_base_scored_0": sum(1 for r in scored if r["base_reward"] == 0.0),
            "negative_control_attempted": len(neg),
            "negative_control_pass": sum(1 for r in neg if r["negative_control_pass"]),
            "negative_control_needed_escalation": sum(
                1 for r in neg if r.get("corruption_level", 1) > 1),
            "claim": "gold must score 1.0 AND base must score 0.0 on the same cell",
            "repos": sorted({r["repo"] for r in records}),
            "runner_kinds": sorted({REPOS[r["repo"]]["runner"].kind for r in records}),
        },
        "cells": records,
    }


if __name__ == "__main__":
    raise SystemExit(main())

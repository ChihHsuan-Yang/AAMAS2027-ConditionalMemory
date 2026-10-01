"""The SWE-bench coverage identity, re-derived from artifacts and classified.

    eligible -> attempted -> valid completed -> excluded (with reasons)

must sum EXACTLY, per repository and overall. Nothing here is quoted from a
document; every cell is recomputed from the manifest, the parquet, and the
executed artifacts named on the command line.

THE EXCLUSION TAXONOMY, and why each class exists
-------------------------------------------------
Each reason is a DIFFERENT kind of absence, and collapsing them would hide the
one that is actionable:

* ``runner_absence``   -- the repo has no working test runner in ``REPOS``.
  An environment limit, not a property of the pair.
* ``licensing``        -- excluded by ``exclude_copyleft`` at manifest build.
* ``protocol``         -- the frozen protocol removes it: a multi-file gold fix
  (``is_single_file_solvable`` false), or a recipient already carrying a donor
  (dedup-by-recipient).
* ``localizer_miss``   -- the cell RAN; the localizer never showed the region
  the gold patch edits, so neither arm could have fixed it. A property of the
  retrieval step, not of memory.
* ``unapplicable_edit``-- the cell RAN; the model's SEARCH/REPLACE block did
  not apply (``search_miss``/``no_block``) or the completion truncated, so
  ``reward`` is ``None``. 🔴 NEVER 0.0.
* ``scorer_invalidity``-- the cell RAN and an edit applied, but the harness
  printed no verdict (``status_lines=0``: an import or collection error), OR
  the scorer is not known to DISCRIMINATE on that instance (its gold patch
  does not score 1.0 and its base 0.0 under the per-instance control). Both
  are "no evidence exists", not "the fix was wrong" -- DEFECT_REGISTER #21.
* ``not_yet_attempted``-- eligible and runnable, simply not run.

🔴 ``scorer_invalidity`` is reported in two layers, because they answer
different questions. The ``status_lines=0`` layer is a property of THIS run.
The per-instance-control layer is a property of the INSTRUMENT on that
instance, and it is knowable without running the arm at all.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from p1mem.adapters.swebench import build_future_tasks  # noqa: E402
from p1mem.adapters.swebench_harness import is_single_file_solvable  # noqa: E402
from swebench_pilot_v2 import REPOS, select_cells  # noqa: E402

REPS = ("raw", "summary", "structured")
_SL0 = re.compile(r"status_lines=0\b")


def scorer_valid_instances(paths: list[str]) -> dict[str, set[str]]:
    """Instances where the scorer is PROVEN to discriminate: gold 1.0, base 0.0.

    A cell whose gold patch does not score 1.0 is one where a 0.0 from the
    model cannot be read as "the fix was wrong" -- the instrument does not
    separate the two states there. This is strictly stronger than "the suite
    printed a verdict".
    """
    out: dict[str, set[str]] = collections.defaultdict(set)
    for p in paths:
        f = Path(p)
        if not f.exists():
            continue
        for c in json.loads(f.read_text())["cells"]:
            if c.get("gold_reward") == 1.0 and c.get("base_reward") == 0.0:
                out[c["repo"]].add(c["task_id"])
    return out


def classify(cells: list[dict], valid: dict[str, set[str]]) -> dict[str, Any]:
    """Per recipient: the reason it does or does not reach a reported number.

    A recipient is VALID COMPLETED only if it is interpretable under ALL THREE
    representations -- the matched-set rule. Reasons are assigned in a fixed
    precedence so that each recipient lands in exactly one class.
    """
    by_task: dict[str, list[dict]] = collections.defaultdict(list)
    for c in cells:
        by_task[c["task_id"]].append(c)

    verdict: dict[str, str] = {}
    du: dict[str, dict] = {r: {} for r in REPS}
    for tid, group in by_task.items():
        repo = group[0]["repo"]
        reasons: set[str] = set()
        ok_reps: set[str] = set()
        for c in group:
            rep = c["representation"]
            if c.get("excluded"):
                reasons.add("memory_unavailable_or_contagion_dirty")
                continue
            if not c["localizer_recall"]:
                reasons.add("localizer_miss")
                continue
            w, wo = c["arms"].get("WITH", {}), c["arms"].get("WITHOUT", {})
            # defect #21, applied on read: no verdict printed => no evidence
            for arm in (w, wo):
                if arm.get("reward") is not None and _SL0.search(
                        arm.get("test_detail") or ""):
                    arm["reward"] = None
                    arm["_demoted_manufactured_zero"] = True
            if w.get("reward") is None or wo.get("reward") is None:
                bad = any((a.get("edit_status") in ("search_miss", "no_block",
                                                    "truncated"))
                          for a in (w, wo))
                reasons.add("unapplicable_edit" if bad else "scorer_invalidity")
                continue
            if tid not in valid.get(repo, set()):
                # the arms produced numbers, but the instrument is not known
                # to discriminate on this instance
                reasons.add("scorer_invalidity")
                continue
            ok_reps.add(rep)
            du[rep][(c["memory_id"], tid)] = w["reward"] - wo["reward"]
        if ok_reps == set(REPS):
            verdict[tid] = "valid_completed"
        else:
            for r in ("localizer_miss", "unapplicable_edit", "scorer_invalidity",
                      "memory_unavailable_or_contagion_dirty"):
                if r in reasons:
                    verdict[tid] = r
                    break
            else:
                verdict[tid] = "scorer_invalidity"
    # a cell matched under all three is only kept if it survives in all three
    matched = (sorted(set.intersection(*[set(du[r]) for r in REPS]))
               if all(du[r] for r in REPS) else [])
    keep = {k[1] for k in matched}
    for tid, v in list(verdict.items()):
        if v == "valid_completed" and tid not in keep:
            verdict[tid] = "scorer_invalidity"
    return {"verdict": verdict, "du": du, "matched": matched}


def self_test() -> int:
    """Plant each exclusion class and require the classifier to name it.

    A classifier only ever run on real data is not known to discriminate: the
    reason a cell lands in a class would be unfalsifiable. Each control below
    constructs the defect it guards, and two of them run in the OPPOSITE
    direction -- a manufactured 0.0 must become ``valid_completed`` the moment
    the suite actually prints a verdict, and a cell interpretable in only two
    of three representations must NOT be ``valid_completed``.
    """
    import copy
    print("POSITIVE CONTROLS -- each must FAIL the thing it guards\n")

    def mk(tid, rep, **kw):
        c = {"memory_id": "m1", "task_id": tid, "repo": "r/r",
             "representation": rep, "localizer_recall": True, "excluded": False,
             "arms": {"WITHOUT": {"reward": 0.0, "edit_status": "ok",
                                  "test_detail": "F2P rc=1 status_lines=3 :: failed"},
                      "WITH": {"reward": 1.0, "edit_status": "ok",
                               "test_detail": "F2P rc=0 status_lines=3 :: ok"}}}
        c.update(kw)
        return c

    valid = {"r/r": {"tGOOD", "tSL0", "tMISS", "tUNAPP", "tDIRTY"}}
    cells = []
    cells += [mk("tGOOD", r) for r in REPS]
    cells += [mk("tMISS", r, localizer_recall=False) for r in REPS]
    cells += [mk("tDIRTY", r, excluded=True) for r in REPS]
    for r in REPS:
        c = mk("tUNAPP", r)
        c["arms"]["WITH"] = {"reward": None, "edit_status": "search_miss",
                             "test_detail": ""}
        cells.append(c)
    for r in REPS:
        c = mk("tSL0", r)
        c["arms"]["WITH"] = {"reward": 0.0, "edit_status": "ok",
                             "test_detail": "F2P rc=1 status_lines=0 :: ImportError"}
        cells.append(c)
    cells += [mk("tNOTVALID", r) for r in REPS]

    got = classify(copy.deepcopy(cells), valid)["verdict"]
    exp = {"tGOOD": "valid_completed", "tMISS": "localizer_miss",
           "tDIRTY": "memory_unavailable_or_contagion_dirty",
           "tUNAPP": "unapplicable_edit", "tSL0": "scorer_invalidity",
           "tNOTVALID": "scorer_invalidity"}
    ok = True
    for t, e in exp.items():
        good = got.get(t) == e
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] {t:10s} -> {got.get(t)}")

    c2 = copy.deepcopy(cells)
    for c in c2:
        if c["task_id"] == "tSL0":
            c["arms"]["WITH"]["test_detail"] = "F2P rc=1 status_lines=7 :: failed"
    flip = classify(c2, valid)["verdict"]["tSL0"] == "valid_completed"
    ok &= flip
    print(f"  [{'PASS' if flip else 'FAIL'}] a status_lines=0 cell becomes valid once "
          f"the suite PRINTS a verdict -- the rule keys on EVIDENCE, not the value")

    c3 = [c for c in copy.deepcopy(cells)
          if not (c["task_id"] == "tGOOD" and c["representation"] == "structured")]
    part = classify(c3, valid)["verdict"]["tGOOD"] != "valid_completed"
    ok &= part
    print(f"  [{'PASS' if part else 'FAIL'}] interpretable in only 2 of 3 "
          f"representations is NOT valid_completed (matched-set rule)")

    print("\n" + ("ALL CONTROLS PASS" if ok else "CONTROL FAILURE"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest",
                    default="data/manifests/swebench_pairs_file_seed20261008.jsonl")
    ap.add_argument("--parquet", default="/tmp/swebench/swebv.parquet")
    ap.add_argument("--src", action="append", default=[])
    ap.add_argument("--scorer-control", action="append", default=[])
    ap.add_argument("--out", default="results/swebench/coverage_table.json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    import pyarrow.parquet as pq
    rows = pq.read_table(a.parquet).to_pylist()
    tasks = {t.instance_id: t for t in build_future_tasks(rows)}
    man = [json.loads(l) for l in open(a.manifest)]

    valid = scorer_valid_instances(a.scorer_control)
    print("scorer-valid instances per repo: "
          + ", ".join(f"{k} {len(v)}" for k, v in sorted(valid.items())))

    cells: list[dict] = []
    for p in a.src:
        # fail closed on a voided artifact -- see swebench_multirepo_analysis
        if Path(p).name == "representations_v1.json":
            raise SystemExit(f"ABORT: {p} is VOIDED (its contagion screen "
                             f"misfired on ASCII table borders) and must "
                             f"never be an input. Use representations_v2.json.")
        cells += json.loads(Path(p).read_text())["cells"]
    cls = classify(cells, valid)

    repos = sorted({r["repo"] for r in man})
    table: dict[str, Any] = {}
    for repo in repos:
        pairs = [r for r in man if r["repo"] == repo]
        sfs = [r for r in pairs
               if is_single_file_solvable(tasks[r["task_id"]].files,
                                          r["shared_files"][0])]
        has_runner = repo in REPOS
        runnable = (select_cells(a.manifest, tasks, 10 ** 9, repo, frozenset())[0]
                    if has_runner else [])
        run_ids = {c["task_id"] for c in runnable}
        attempted = {c["task_id"] for c in cells if c["repo"] == repo}
        excl: collections.Counter = collections.Counter()
        valid_done = 0
        for tid in run_ids:
            if tid not in attempted:
                excl["not_yet_attempted"] += 1
                continue
            v = cls["verdict"][tid]
            if v == "valid_completed":
                valid_done += 1
            else:
                excl[v] += 1
        # pairs that never reached the runnable universe
        multi = len(pairs) - len(sfs)
        dedup = len(sfs) - len(run_ids) if has_runner else 0
        table[repo] = {
            "manifest_pairs": len(pairs),
            "single_file_solvable_pairs": len(sfs),
            "has_runner": has_runner,
            "ELIGIBLE_runnable_recipients": len(run_ids),
            "ATTEMPTED": len(attempted & run_ids),
            "VALID_COMPLETED": valid_done,
            "EXCLUDED": dict(sorted(excl.items())),
            "EXCLUDED_total": sum(excl.values()),
            "identity_holds":
                len(run_ids) == valid_done + sum(excl.values()),
            "pair_funnel": {
                "pairs": len(pairs),
                "removed_multi_file_gold_fix_protocol": multi,
                "removed_no_runner": 0 if has_runner else len(sfs),
                "removed_dedup_by_recipient_protocol": dedup,
                "runnable": len(run_ids),
                "funnel_closes": len(pairs) - multi
                                 - (0 if has_runner else len(sfs))
                                 - dedup == len(run_ids),
            },
            "scorer_valid_instances": len(valid.get(repo, set())),
        }

    tot = {k: sum(t[k] for t in table.values())
           for k in ("manifest_pairs", "single_file_solvable_pairs",
                     "ELIGIBLE_runnable_recipients", "ATTEMPTED",
                     "VALID_COMPLETED", "EXCLUDED_total")}
    allex: collections.Counter = collections.Counter()
    for t in table.values():
        allex.update(t["EXCLUDED"])
    tot["EXCLUDED"] = dict(sorted(allex.items()))
    tot["identity_holds"] = (tot["ELIGIBLE_runnable_recipients"]
                             == tot["VALID_COMPLETED"] + tot["EXCLUDED_total"])

    out = {
        "_what": ("eligible -> attempted -> valid completed -> excluded, "
                  "summing exactly per repo and overall. Every figure is "
                  "re-derived here from the manifest, the parquet and the "
                  "named artifacts; none is quoted from a document."),
        "_exclusion_taxonomy": {
            "runner_absence": "repo has no working test runner",
            "licensing": "removed by exclude_copyleft at manifest build",
            "protocol": "multi-file gold fix, or dedup-by-recipient",
            "localizer_miss": "ran; the region the gold patch edits was never shown",
            "unapplicable_edit": "ran; the edit did not apply or the completion truncated -- reward None, NEVER 0.0",
            "scorer_invalidity": "ran; no verdict printed (status_lines=0), or the scorer is not known to discriminate on that instance",
            "memory_unavailable_or_contagion_dirty": "the memory body failed the contagion screen",
            "not_yet_attempted": "eligible and runnable, not run",
        },
        "sources": sorted(a.src),
        "scorer_controls": sorted(a.scorer_control),
        "per_repo": table,
        "TOTAL": tot,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))

    print(f"\n{'repo':26s} {'elig':>5} {'att':>4} {'valid':>6} {'excl':>5}  sum?")
    for repo, t in table.items():
        print(f"{repo:26s} {t['ELIGIBLE_runnable_recipients']:5d} "
              f"{t['ATTEMPTED']:4d} {t['VALID_COMPLETED']:6d} "
              f"{t['EXCLUDED_total']:5d}  {'OK' if t['identity_holds'] else 'BROKEN'}")
    print(f"{'TOTAL':26s} {tot['ELIGIBLE_runnable_recipients']:5d} "
          f"{tot['ATTEMPTED']:4d} {tot['VALID_COMPLETED']:6d} "
          f"{tot['EXCLUDED_total']:5d}  "
          f"{'OK' if tot['identity_holds'] else 'BROKEN'}")
    print("\nexclusions overall:")
    for k, v in tot["EXCLUDED"].items():
        print(f"  {v:4d}  {k}")
    print(f"\nwritten: {a.out}")
    return 0 if tot["identity_holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

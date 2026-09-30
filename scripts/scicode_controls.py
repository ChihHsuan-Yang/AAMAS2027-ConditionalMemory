#!/usr/bin/env python3
"""Prove the SciCode scorer and leakage detector can FAIL.

A verifier only ever observed passing is not known to discriminate. This script
runs, in one pass:

* **positive controls** -- each dev subproblem's own gold code against its own
  tests. Must score exactly 1.0.
* **negative controls** -- deliberately corrupted variants of that same gold
  code. Must score 0.0 (a real wrong answer) or return ``None`` with an error
  kind, and each control declares WHICH, so a scorer that returns the wrong
  *kind* of failure is caught as well as one that returns the wrong verdict.
* **the error/wrong-answer boundary** -- the defect this project has hit twice
  is scoring an unrunnable solution as 0.0. Controls 4-7 are unrunnable and
  every one of them must come back ``reward is None``.
* **leakage controls** -- a planted leak must FIRE and a clean pair must stay
  silent, using the already-validated ``adapters/leakage.py``.

Run:  /Users/bellayang/miniconda3/bin/python3 scripts/scicode_controls.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p1mem.adapters import leakage as L           # noqa: E402
from p1mem.adapters import scicode as S           # noqa: E402
SC = S

DEFAULT_DEV = "/tmp/scicode_probe/problems_dev.jsonl"
DEFAULT_TEST = "/tmp/scicode_probe/problems_test.jsonl"
DEFAULT_H5 = "/tmp/scicode_probe/test_data.h5"
DEFAULT_SRC = "/tmp/scicode_probe/SciCode/src"


def _corrupt_output(memory: S.SolvedSubproblem) -> str:
    """Shadow the gold function so it returns a perturbed value.

    The function still exists, still runs, still returns a number -- so this
    MUST reach the benchmark's own assertion and fail there, i.e. 0.0, not an
    error. It separates "wrong answer" from "did not run".
    """
    name = memory.function_name
    return (
        f"{memory.gold_code}\n\n"
        f"_p1mem_orig = {name}\n"
        f"def {name}(*a, **k):\n"
        f"    _r = _p1mem_orig(*a, **k)\n"
        f"    try:\n"
        f"        return _r * 1.37 + 0.913\n"
        f"    except Exception:\n"
        f"        return 0\n"
    )


def _constant(memory: S.SolvedSubproblem) -> str:
    sig = memory.function_header.splitlines()[0]
    return f"{sig}\n    return 0\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=DEFAULT_DEV)
    ap.add_argument("--test", default=DEFAULT_TEST)
    ap.add_argument("--h5", default=DEFAULT_H5)
    ap.add_argument("--scicode-src", default=DEFAULT_SRC)
    ap.add_argument("--workdir", default="/tmp/sci_harness/controls")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out", default=str(ROOT / "results/scicode/controls.json"))
    a = ap.parse_args()

    dev_rows = S.load_jsonl(a.dev)
    test_rows = S.load_jsonl(a.test)
    memories = S.build_memory_units(dev_rows)
    tasks = S.build_future_tasks(test_rows)
    S.assert_writer_blind(memories, tasks)

    by_step = {s["step_number"]: (r, s)
               for r in dev_rows for s in r["sub_steps"]}
    kw = dict(h5_path=a.h5, scicode_src=a.scicode_src,
              workdir=a.workdir, python=a.python, timeout_s=300.0)

    results: list[dict] = []

    def record(name: str, step: str, expect_reward, expect_error: bool,
               res: S.ScoreResult) -> None:
        got = res.reward
        ok = (got == expect_reward) and (res.is_error == expect_error)
        results.append({
            "control": name, "step": step, "expect_reward": expect_reward,
            "expect_error": expect_error, "observed_reward": got,
            "observed_kind": res.kind, "observed_is_error": res.is_error,
            "passed": ok, "stderr_tail": res.stderr_tail[:200],
        })

    # ---- 1. POSITIVE: gold must score 1.0, on EVERY step-1 dev subproblem
    step1 = [m for m in memories if m.step_number.endswith(".1")]
    for m in step1:
        _, step = by_step[m.step_number]
        res = S.score_gold(m, test_cases=tuple(step["test_cases"]), **kw)
        record("POS gold->1.0", m.step_number, 1.0, False, res)

    # ---- 2. NEGATIVE, must be a WRONG ANSWER (0.0), not an error
    for m in step1[:6]:
        _, step = by_step[m.step_number]
        task = S.FutureSubproblem(
            step_number=m.step_number, problem_id=m.problem_id,
            problem_name=m.problem_name, step_description=m.step_description,
            step_background=m.step_background, function_header=m.function_header,
            dependencies=m.dependencies, return_line=m.return_line,
            test_cases=tuple(step["test_cases"]))
        res = S.score_solution(
            task, f"```python\n{_corrupt_output(m)}\n```", **kw)
        record("NEG perturbed-output->0.0", m.step_number, 0.0, False, res)
        res = S.score_solution(task, f"```python\n{_constant(m)}\n```", **kw)
        record("NEG constant-0->0.0", m.step_number, 0.0, False, res)

    # ---- 3. THE BOUNDARY: unrunnable must be None, NEVER 0.0
    m = step1[0]
    _, step = by_step[m.step_number]
    task = S.FutureSubproblem(
        step_number=m.step_number, problem_id=m.problem_id,
        problem_name=m.problem_name, step_description=m.step_description,
        step_background=m.step_background, function_header=m.function_header,
        dependencies=m.dependencies, return_line=m.return_line,
        test_cases=tuple(step["test_cases"]))
    name = m.function_name
    for label, response in [
        ("ERR empty-response->None", ""),
        ("ERR prose-refusal->None", "I cannot solve this problem."),
        ("ERR syntax-error->None", f"```python\ndef {name}(:\n    pass\n```"),
        ("ERR wrong-function-name->None",
         "```python\ndef p1mem_not_the_function(x):\n    return x\n```"),
        ("ERR runtime-error->None",
         f"```python\ndef {name}(*a, **k):\n    raise ValueError('boom')\n```"),
    ]:
        res = S.score_solution(task, response, **kw)
        record(label, m.step_number, None, True, res)

    # ---- 4. LEAKAGE: planted leak must FIRE; clean pair must stay silent
    #
    # The SUBJECT matters, and my first draft got it wrong: I passed a
    # recipient's whole 358-character docstring as the "gold answer", and the
    # numeric detector correctly fired on the clean pair from incidental
    # number overlap. A control that fires for a reason unrelated to the
    # hazard is a broken control, not a finding. The gold-shaped string for a
    # SciCode recipient is its SIGNATURE LINE -- the smallest literal string
    # that identifies the answer -- so that is what is tested.
    leak_rows: list[dict] = []
    t0 = tasks[0]
    clean_mem = memories[0].episode_text
    gold = SC.signature_line(t0.function_header)
    planted = clean_mem + "\n\n" + gold
    v_clean = L.detect(clean_mem, gold,
                       memory_id="control_clean", task_id=t0.task_id)
    v_leak = L.detect(planted, gold,
                      memory_id="control_planted", task_id=t0.task_id)
    # A negative control is only a control if the baseline really is clean.
    leak_rows.append({"control": "LEAK planted-signature-must-fire",
                      "expected": True, "observed": v_leak.any_leak,
                      "passed": v_leak.any_leak is True})
    leak_rows.append({"control": "LEAK clean-must-be-silent",
                      "expected": False, "observed": v_clean.any_leak,
                      "passed": v_clean.any_leak is False,
                      "detectors": {"exact": v_clean.exact,
                                    "normalized": v_clean.normalized,
                                    "numeric": v_clean.numeric}})
    # The SciCode-specific detector must fire on a KNOWN positive found in the
    # real data (donor 19.1 defines `tensor`, which recipient 65.1 requires)
    # and stay silent on a pair known not to share a definition.
    mem_by_step = {m.step_number: m for m in memories}
    task_by_step = {t.step_number: t for t in tasks}
    if "19.1" in mem_by_step and "65.1" in task_by_step:
        pos = SC.defines_recipient_function(mem_by_step["19.1"],
                                            task_by_step["65.1"])
        leak_rows.append({"control": "LEAK real-positive 19.1->65.1 (tensor)",
                          "expected": True, "observed": pos,
                          "passed": pos is True})
        neg = SC.defines_recipient_function(mem_by_step["1.1"],
                                            task_by_step["65.1"])
        leak_rows.append({"control": "LEAK real-negative 1.1->65.1",
                          "expected": False, "observed": neg,
                          "passed": neg is False})
    ok_builtin, builtin = L.controls_summary()
    leak_rows.append({"control": "LEAK leakage.py own controls",
                      "expected": True, "observed": ok_builtin,
                      "n_controls": len(builtin), "passed": bool(ok_builtin)})

    n_pass = sum(1 for r in results if r["passed"])
    n_leak_pass = sum(1 for r in leak_rows if r["passed"])
    summary = {
        "scorer_controls_passed": n_pass,
        "scorer_controls_total": len(results),
        "leakage_controls_passed": n_leak_pass,
        "leakage_controls_total": len(leak_rows),
        "all_passed": n_pass == len(results) and n_leak_pass == len(leak_rows),
        "scorer_controls": results,
        "leakage_controls": leak_rows,
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))

    for r in results:
        mark = "ok  " if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['control']:32s} {r['step']:>5s} "
              f"reward={str(r['observed_reward']):5s} kind={r['observed_kind']}")
    for r in leak_rows:
        mark = "ok  " if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['control']:32s} expected={r['expected']} "
              f"observed={r['observed']}")
    print(f"\nSCORER   {n_pass}/{len(results)} controls passed")
    print(f"LEAKAGE  {n_leak_pass}/{len(leak_rows)} controls passed")
    print(f"written: {out}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

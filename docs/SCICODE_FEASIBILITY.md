# SciCode as Benchmark 3 — executed, not scoped

**Sub-agent SA-SCI, 2026-09-30.** Full evidence and reproduction:
`subagent_SCI_report.md` (project root). Every number here was computed on this machine
from the artifact named beside it.

## Verdict: ✅ RUNNABLE, and the pilot CLEARED the floor gate. Report as a case study.

| # | check | verdict | evidence |
|---|---|---|---|
| 1 | multi-task per memory | ✅ | **34 memories meet ≥2 tasks** in the selected design; 0% diagonal vs BEAM's 92.6% |
| 2 | objective reward | ✅ | SciCode's own test cases vs official `test_data.h5`; gold positive control **15/15** |
| 3 | error ≠ 0.0 | ✅ | `ScoreResult` raises if an error kind carries a number; 5/5 error controls → `None` |
| 4 | leakage | ✅ | **1 / 3,200** full-answer leaks; detector fires on a real positive, silent on a real negative |
| 5 | licence | ✅ | data Apache-2.0 (`cardData`), harness Apache-2.0 (LICENSE read). No ShareAlike |
| 6 | writer blindness | ✅ | structural (`SourceSegment`, 4 barriers) + `assert_writer_blind` rejects within-problem pairs |
| 7 | **floor effect** | ✅ | **both-arms-fail 0.370–0.456, all below the 0.50 gate**, arms symmetric in error rate |

## The pair count, and the prior estimate

The inherited estimate was **"~8–12 donor→recipient pairs"**. Verified, and it depends
entirely on a relatedness definition that was never named:

| relatedness | pairs | memories | **≥2 tasks** | % diagonal (denom) |
|---|---:|---:|---:|---:|
| `ALL` (every cross-problem pair) | 3,200 | 50 | 50 | 0.0% (50) |
| `DEPENDENCY` (shared non-generic import) | **12** | 7 | 5 | 28.6% (7) |
| `LEXICAL` (idf-cosine ≥ 0.0315 = measured p95) | **163** | 43 | **34** | 20.9% (43) |

> **The estimate is exactly right at `DEPENDENCY` (12) and a ~13× understatement at
> `LEXICAL` (163).** It was not wrong; it quoted one level without naming it. The
> threshold was fixed at the 95th percentile of the full similarity distribution —
> from the *distribution*, never from an outcome.

## Two structural facts that bind the design

1. **`ground_truth_code` exists only in the DEV split** (test substep key union has no
   solution field). A memory is a *solved* subproblem, so donors come from dev:
   **50 candidates, not 338**.
2. **A recipient must be a problem's FIRST substep** — a later substep's tests call its
   earlier steps' functions and the test split ships no code for them. Measured: **0/65**
   step-1 substeps reference a later function; **64/65** have test cases.

Dev and test `problem_id` sets are **disjoint**, so donor∈dev / recipient∈test is
**cross-problem by construction**, which is what `BENCHMARK_DECISIONS.md` required.

## Pilot — 204 cells, 476 calls, metis / gpt-oss-120b / low / temp 0 / 1024 tok

| representation | interp. | **both-arms-fail** | mean ΔU | discordant | exact p | task-clustered CI |
|---|---:|---:|---:|---|---:|---|
| raw | 57 | **0.456** | +0.0000 | +1/−1 | 1.000 | [−0.050, +0.054] |
| summary | 58 | **0.379** | +0.0690 | +5/−1 | 0.219 | [+0.000, +0.151] |
| structured (procedural) | 54 | **0.370** | +0.0556 | +3/−0 | 0.250 | [+0.000, +0.146] |

Unaided solve rate **31/68 = 45.6%** — healthy, not a floor. Errors are symmetric across
arms (9/8, 8/8, 11/9), so there is **no SWE-bench-style WITH-arm confound**.

**Every interval touches zero.** The pilot shows the benchmark is *measurable*, not that
memory helps. Report as a case study with N stated.

## 🔴 The reader is NOT deterministic at temperature 0 here

The WITHOUT-arm prompt is byte-identical across the three representations, giving a free
A/A control: **response text differs in 10/68 = 14.7%** of cells and **reward differs in
1/68 = 1.5%**. So the scoring noise floor is 1.5%, and unlike LongMemEval (`F_exec = 0.000`)
`F_exec` is **non-zero on SciCode**. That is a difference between benchmarks, not a
correction to the LongMemEval finding.

## Two controls FAILED first, and each caught a real defect

1. **Gold positive control 0/15 through the adapter, 15/15 by hand.** `scicode.parse.parse`
   imports `datasets.load_dataset` at module scope but never calls it in local scoring;
   without a stub **every** score is `harness_error`. The adapter now creates the stub
   itself. *Without this control I would have reported SciCode as unrunnable.*
2. **The clean leakage control fired** — my control was wrong, not the detector: I passed a
   358-char docstring as the "gold answer" and the numeric detector hit incidental number
   overlap. The gold-shaped string is the **signature line**.

A third defect was found by the smoke run: a `max_tokens`-truncated reply leaked its
unterminated ```` ```python ```` marker into the scored program. Reward was still `None`
(so no number was corrupted) but the recorded *kind* was wrong, and the kind is what a
floor diagnosis reads. Fixed in `extract_code`, with a test.

## Artifacts

| what | path |
|---|---|
| adapter | `src/p1mem/adapters/scicode.py` |
| controls | `scripts/scicode_controls.py` → `results/scicode/controls.json` |
| pilot | `scripts/scicode_pilot.py` → `results/scicode/pilot_all3.json` |
| tests | `tests/test_scicode_adapter.py` (45, mutation-checked: 4/4 planted defects caught) |
| corpus | `/tmp/scicode_probe/` (not in the repo; 1.05 GB HDF5) |

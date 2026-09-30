# SciCode — Benchmark 3, executed

**SA-SCI, 2026-09-30. Every number re-derived by the Master Agent from
`results/scicode/pilot_all3.json`.** 204 cells, 476 calls, 84 s.

---

## 1. The gate: PASSED under all three representations

| representation | both-arms-fail | denominator |
|---|---:|---:|
| raw | **0.456** | 26/57 |
| summary | **0.379** | 22/58 |
| structured | **0.370** | 20/54 |

All below the 0.50 stop threshold. Unaided solve **31/68**, and errors are **symmetric
across arms** (9/8, 8/8, 11/9) — none of the WITH-arm asymmetry that currently blocks
SWE-bench. **SciCode can host the experiment.**

## 2. The multi-task axis, and a naming failure in the inherited estimate

The inherited "~8–12 pairs" is **exactly right at one relatedness level and a ~13×
understatement at another — the level was never named.**

| relatedness | pairs | memories | **≥2 tasks** | % diagonal |
|---|---:|---:|---:|---:|
| `ALL` | 3,200 | 50 | 50 | **0.0%** |
| `DEPENDENCY` (shared non-generic import) | **12** | 7 | 5 | 28.6% |
| `LEXICAL` (idf-cosine ≥ 0.0315, the measured p95) | **163** | 43 | **34** | 20.9% |

Every level clears BEAM's 92.6%. The threshold was fixed at the distribution's p95, never
at an outcome.

Two structural facts were measured before the design was fixed: `ground_truth_code` exists
**only in dev** (50 donors, not 338), and a recipient must be a problem's **first** substep
(0/65 step-1 tests reference a later function). Dev and test problem ids are disjoint, so
pairing is **cross-problem by construction**.

## 3. ΔU — the benchmark is measurable; memory is not shown to help

| representation | mean ΔU | helped / hurt | n |
|---|---:|---|---:|
| raw | **+0.0000** | 1 / 1 | 57 |
| summary | +0.0690 | 5 / 1 | 58 |
| structured (procedural) | +0.0556 | 3 / 0 | 54 |

**Every task-clustered CI touches zero.** The pilot establishes that the instrument works,
not that memory helps. Report it that way.

## 4. 🔬 The representation ranking INVERTS relative to LongMemEval

| | LongMemEval-V2 | SciCode |
|---|---|---|
| raw | **+0.3174**, CI excludes zero | **+0.0000** |
| summary | +0.0613 (spans zero) | **+0.0690** (largest here) |
| structured | −0.0498 (spans zero) | +0.0556 |

On LongMemEval raw dominates and compression destroys the effect. **On SciCode raw is
exactly zero and the compressed forms are the only ones with a positive point estimate.**

⚠️ **All SciCode intervals touch zero, so this is a difference in point estimates, not an
established reversal.** But it is the single most important reason not to generalize the
LongMemEval representation ranking — which the execution brief warned against assuming —
and it is a direct argument for the cross-benchmark axis.

## 5. A finding that bears on every other benchmark

> **The reader is NOT deterministic at temperature 0 on SciCode.**

The WITHOUT-arm prompt is byte-identical across the three representations, which makes a
**free A/A control**: text differs in **10/68 (14.7%)**, reward in **1/68 (1.5%)**.

So `F_exec` is **non-zero here**, unlike LongMemEval where 0/1,157 cells varied. That means
the variance decomposition — unidentifiable on LongMemEval precisely *because* `F_exec = 0`
left no residual scale — may be identifiable on SciCode. **Recorded as a lead, not a
result.**

## 6. Three defects, two caught by controls that failed first

- 🔴 **Gold positive control 0/15 through the adapter, 15/15 by hand.** `scicode.parse`
  imports `datasets.load_dataset` at module scope; without a stub **every** score is
  `harness_error`. **Without that control, SciCode would have been reported unrunnable.**
- **The clean leakage control fired — and the control was wrong, not the detector.** A
  358-char docstring had been passed as the gold answer; the gold-shaped string is the
  signature line.
- A truncated reply leaked an unterminated fence into the scored program: right verdict
  (`None`), **wrong recorded kind** — and kinds are what a floor diagnosis reads.

**Leakage: 1/3,200 full-answer leaks** (dev 19.1 and test 65.1 both define `tensor`),
flagged not dropped, with the detector proven to fire on that real positive and stay silent
on a real negative. `mentions_answer_name` (18/3,200) and the numeric detector (542/850)
are reported separately and deliberately excluded from `any_leak`.

## 7. Status

**Keep as a case study with N stated.** 45 new tests, mutation-checked 4/4. Suite 593
passing; `audit_claims.py` green.

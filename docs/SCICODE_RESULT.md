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

## 4. The point-estimate ordering differs from LongMemEval

| | LongMemEval-V2 | SciCode |
|---|---|---|
| raw | **+0.3174**, CI excludes zero | **+0.0000** |
| summary | +0.0613 (spans zero) | **+0.0690** (largest here) |
| structured | −0.0498 (spans zero) | +0.0556 |

On LongMemEval raw dominates and compression destroys the effect. In the SciCode pilot raw
is exactly zero and the compressed forms carry the only positive point estimates.

> 🔴 **This is NOT an established inversion, and must not be described as one.** Every
> SciCode interval crosses zero. The defensible statements are:
> **"the point-estimate ordering differs across benchmarks"**, or
> **"LongMemEval's Raw-dominant ordering is not reproduced in the SciCode pilot."**
>
> Strengthen this only if scaled SciCode evidence supports it.

It is still the reason not to generalize the LongMemEval ranking — which the execution
brief warned against assuming — and a direct argument for the cross-benchmark axis.

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

---

# SCALE-UP (2026-09-30) — the pre-committed completion of this arm

`results/scicode/scaleup_all3.json` · analysis
`results/scicode/analysis/scaleup_analysis.json` · design frozen in advance in
[`SCICODE_SCALEUP_PRECOMMITMENT.md`](SCICODE_SCALEUP_PRECOMMITMENT.md).

**154 pairs — the entire candidate pool** (34 memories, 40 tasks, 0.0% diagonal,
median 4 tasks/memory, max 17) × 3 representations × 2 arms = **924 arm-runs**, 189 s.
The 68 pilot pairs are a verified strict **subset**: this run *added* cells, it did not
resample them.

## The denominators differ, so the comparison uses a matched set

Interpretable cells per representation are **127 raw / 134 summary / 130 structured** —
they differ because the *harness* errors on different cells. Comparing means across those
three sets would compare different cells. Everything below therefore uses the **122 cells
interpretable under all three representations**.

## A free execution-noise floor, available only on this design

The WITHOUT arm contains no memory, so for one (memory, task) the prompt is
**byte-identical across all three representations**. Any disagreement is pure
execution/scoring noise. Measured: **5/135 = 0.0370**.

🔴 **This floor is the size of the effects.** The largest matched point estimate
(structured, +0.0246) sits *below* F_exec = 0.0370.

## Matched-set result (n=122, task-clustered bootstrap)

| representation | ΔU | CI95 | helped / hurt / tied |
|---|---|---|---|
| raw | **−0.0082** | [−0.0496, +0.0227] | 2 / 3 / 117 |
| summary | **+0.0164** | [−0.0370, +0.0833] | 7 / 5 / 110 |
| structured | **+0.0246** | [−0.0165, +0.0794] | 4 / 1 / 117 |

## The ordering question, asked directly

Paired contrasts on the *same* 122 cells:

| contrast | Δ | CI95 | verdict |
|---|---|---|---|
| structured − raw | +0.0328 | [−0.0342, +0.1200] | **crosses 0** |
| summary − raw | +0.0246 | [−0.0342, +0.0991] | **crosses 0** |
| structured − summary | +0.0082 | [−0.0811, +0.0820] | **crosses 0** |

## Verdict — stated against the pre-commitment, not after it

`ORDERING_VERDICT: NOT_ESTABLISHED` · `INVERSION_LANGUAGE_PERMITTED: false`

The pre-commitment said the stronger claim would be licensed only if the scaled intervals
separated. **They do not.** More than doubling the cell count did not separate any
contrast, and the pre-registered uninformativeness condition partly obtains: both-arms-fail
stayed at 0.28–0.32, so 117–122 of 122 cells are **tied** and cannot express a delta in
either direction. The added N bought less power than the cell count suggests — a property
of SciCode's difficulty under this reader, which is the honest thing to report.

**The wording stays exactly as it was.** The point-estimate ordering differs across
benchmarks: LongMemEval's Raw-dominant ordering is **not reproduced** in SciCode, where raw
is the only negative point estimate. That is a difference in point estimates and nothing
more. Scaling did not upgrade it, and this section exists to record that scaling was
*tried* and the claim was *not* upgraded.

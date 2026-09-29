# Paired-Test Power — why the underpower rule is not a fixed count

**2026-09-29, fixed before the screened results exist.**

---

## My original rule was under-specified

I ruled: *"if non-zero contributors fall below ~8, declare underpower rather than report a
null."* Sub-agent K flagged that a fixed count is correct at **only one noise level**, and
declined to implement it silently — the right call.

## Two independent power measurements, which disagree in magnitude

Power to detect a true +0.30 among contributors, 60 nominal memories:

| contributors | sd=0 | sd=0.25 | sd=0.5 |
|---:|---:|---:|---:|
| **Sub-agent K** | | | |
| 40 | 1.00 | 1.00 | 0.85 |
| 20 | 1.00 | 0.81 | **0.32** |
| 8 | 1.00 | 0.17 | 0.12 |
| 5 | 1.00 | 0.10 | 0.06 |
| **Master Agent** | | | |
| 40 | 1.00 | 1.00 | 0.97 |
| 20 | 1.00 | 1.00 | 0.80 |
| 8 | 1.00 | 0.90 | 0.40 |
| 5 | 1.00 | 0.71 | 0.30 |

🔴 **These disagree substantially** — at n=8, sd=0.5 I measure 0.40 against K's 0.12. The
two simulations differ in how the interval is formed (I resample all 60 nominal memories
including the structural zeros; K's differs in at least its trial count and likely its
resampling unit). **Neither is audited as the correct one, and the discrepancy is recorded
rather than resolved**, because the decision does not depend on it.

## What both agree on, and what the rule therefore is

Both tables show the same qualitative fact, and it is the one that matters:

> **Power depends on the spread among contributors, not on their count alone.** At sd = 0 a
> handful of contributors suffices; at sd = 0.5, twenty contributors is still weak on
> either measurement.

**Adopted:** K's implementation — the count floor (≥8) as a *necessary* backstop, plus a
z computed from the **observed** spread. My fixed count is retained as the floor, demoted
from being the whole test. A case with 8 contributors at high observed spread correctly
returns `UNDERPOWERED` even though the count alone passes.

This is the better rule under either power table, which is why the disagreement above does
not need settling before the run.

⚠️ **If the reported status is ever close to the boundary, the disagreement must be
settled first** — with an audited power simulation — before the verdict is quoted.

## The subtlest defect of the day, in K's own code

K defined a non-zero contributor as `d != 0.0`. On this benchmark ΔU ∈ {−1, 0, +1}, so
exact zeros dominate and the definition behaves correctly.

**Under continuous noise nothing is exactly zero**, so the field reported **60/60
contributors on data that was almost entirely noise** — silently reporting the opposite of
the truth, in the one situation where the field's answer matters.

> It survived first reading **because the wrong definition and the right one agree on the
> data in front of you.** That is the same shape as the vacuous disjointness assertion, the
> non-discriminative leakage flag, and my own `diagnose_total_miss`: *a check only ever
> exercised on its home case is not known to discriminate.*

Now a tolerance test. Verified on discrete ΔU: walking contributors 40 → 3 moves the status
ADEQUATE → UNDERPOWERED while the conditional mean holds at +1.0000 and the diluted mean
falls +0.667 → +0.050 — the dilution gap, reproduced.

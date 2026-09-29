# Variance Decomposition — identifiability status, recorded before the results

**Master Agent, 2026-09-29, verified from `data/manifests/k1_screened_cells.jsonl` before
the screened run's outcomes exist.**

---

## What determines identifiability here

The interaction term is separated from the task main effect only by tasks that **several
memories are observed on**. A task seen by exactly one memory contributes nothing to that
separation — its task effect and its interaction are the same number.

## Measured, both designs

| | pilot | screened | direction |
|---|---:|---:|---|
| memories | 60 | 60 | — |
| tasks | 220 | 218 | — |
| mean tasks per memory | 8.0 | **19.3** | ✅ much better |
| **tasks seen by exactly ONE memory** | 93 / 220 = **42%** | 83 / 218 = **38%** | ⚠️ barely moved |

Memories-per-task, screened: 83 tasks×1, 55×2, 20×3, 18×4, 4×5, 9×6, 3×7, 1×8.

## Honest expectation

Widening the task axis fixed the axis it was aimed at — 8 → 19.3 tasks per memory. But the
binding constraint for *identifiability* is the **other** margin, and it improved only
4 points. **38% of tasks still contribute nothing to separating task from interaction.**

> The decomposition may well come back `AT_UPPER_BOUNDARY` again. If it does, that is
> reported as **not identified**, and **no share is quoted from a clipped ratio** — the
> previous fit returned shares equal to 16 significant figures while reporting
> `converged=True` with a tight CI.

This is recorded now, before the numbers, so that a failure to identify is read as the
predicted outcome of a measured structural property rather than discovered and explained
afterwards.

## Why this margin is hard to fix on this corpus

It follows from bearing scarcity (`docs/BEARING_SCARCITY.md`): a memory bears on a median
of **one** future task. To get many memories per task you need many memories bearing on the
*same* task — and the screening found only 76 discriminative tasks across 1,889 units.

Adding compute does not help. The fix would be a corpus where memories and tasks overlap
more densely, which is a different benchmark, not a bigger run.

## What survives if the decomposition is not identified

The variance decomposition was one of three planned evidence lines. The other two do not
depend on it:

1. **BEARING vs MATCHED_CONTROL ΔU** — a within-cell contrast, composition-matched to
   within 0.02 on every question family. Unaffected by identifiability.
2. **The excess flip rate over the additive null** — a rate comparison, not a variance
   model.

And the identifiability failure is **itself a reportable finding**: it quantifies how
sparse memory–task bearing is in a realistic corpus, which is the same phenomenon the paper
documents from the other direction.

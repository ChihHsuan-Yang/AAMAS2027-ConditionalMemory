# Memory–Task Bearing Is Scarce — a structural finding, and a ceiling on the headline

**Measured 2026-09-29 by Sub-agent K, independently re-derived by the Master Agent** from
`data/manifests/lmev2_leakage_small.jsonl` (114,207 fired cells over all 1,889 units ×
same-domain tasks).

Screening is deterministic, content-only, and costs **zero endpoint calls**.

---

## The finding

Across 295 deterministic LongMemEval-V2 tasks and 1,889 naturally occurring memory units:

| quantity | value |
|---|---|
| tasks that are **discriminative** (1 ≤ pool_hits ≤ 8) | **76 of 295 = 25.7%** |
| tasks firing on **>100** of the ~865–1,024 same-domain memory pool | **152** |
| tasks firing on **0** memories | 15 |
| memories with **≥1** bearing task | **165 of 1,889** |
| total bearing (memory, task) edges | **267** |
| 🔴 **memories with ≥2 bearing tasks** | **46** |

Bearing-tasks-per-memory: **119 memories have exactly 1**, 18 have 2, 17 have 3, 5 have 4,
2 have 5, 1 has 6, 2 have 8, 1 has 9.

> **In this corpus, a naturally occurring memory bears on a median of ONE future task out
> of hundreds.**

That is a substantive claim about long-term agent memory, not a nuisance parameter. It also
explains, mechanically, why the unscreened design measured nothing: pairing each memory
with 8 arbitrary same-domain questions draws overwhelmingly from the ~95% of pairs with no
relationship.

## The ceiling this puts on the headline metric

A sign flip requires one memory with **≥2 bearing cells of opposite sign**. So the flip
rate's denominator is **46**, not 60, not 69, and not 1,889.

Wilson 95% CI widths at n = 46:

| observed rate | 95% CI | width |
|---|---|---|
| 0.10 | [0.042, 0.220] | 0.178 |
| 0.25 | [0.148, 0.391] | 0.244 |
| 0.50 | [0.361, 0.639] | 0.278 |

> **Enough to distinguish "flips happen" from "flips are rare". Not enough to distinguish
> 0.20 from 0.35.**

**No amount of compute changes this.** It is a property of the benchmark's memory–task
structure, and it must be stated in the paper as a limit on precision rather than
discovered by a reviewer.

## What we do NOT do about it

**We do not relax the discriminativeness threshold to inflate the denominator.** A looser
threshold readmits the non-discriminative flag already shown to fire on unpaired memories
at ratio 0.995 (`docs/PAIRING_VERDICT.md`). A larger contaminated denominator is worse than
a smaller honest one.

## Design consequences

1. **Report n = 46 with its Wilson CI**, and state the ceiling explicitly.
2. **Concentrate budget on those 46 memories** — every bearing task plus matched controls,
   at ≥3 replicates where affordable. The flip-rate CI is denominator-bound, but per-cell
   labels are replicate-bound, and A1.3 means a single-replicate cell can never be labelled.
3. **Use a small shared task pool for the variance decomposition.** The two analyses have
   *different* binding constraints — the decomposition needs many memories per task, the
   flip rate needs many bearing tasks per memory — and one grid can satisfy both.

## Why the previous decomposition was unidentified — the sharper diagnosis

Not merely "8 tasks per memory". In `results/deltau_pilot/cells.jsonl` the
**memories-per-task** distribution was: **93 tasks seen by exactly 1 memory**, 61 by 2, 44
by 3, 13 by 4, 5 by 5.

A task observed by a single memory contributes **nothing** to separating the task main
effect from the interaction — which is precisely why both ratios pinned at the optimizer's
`exp(12)` clip ceiling while still reporting `converged=True`.

## Provenance

K positive-controlled the manifest by recomputing 2,706 cells from raw trajectory text:
**2,706/2,706 agreement, 681 real fires**, and `leakage.controls_summary()` **17/17 PASS**.

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
| tasks that are **discriminative** (1 ≤ pool_hits ≤ 8) | **76**, of which **75 deterministic** (1 is LLM-judged and excluded) |
| tasks firing on **>100** of the ~865–1,024 same-domain memory pool | **152** |
| tasks firing on **0** memories | 15 |
| memories with **≥1** bearing task | **165 of 1,889** |
| total bearing (memory, task) edges | **266** (75-task basis; 267 on the 76-task basis) |
| 🔴 **memories with ≥2 bearing tasks** | **46** |

Bearing-tasks-per-memory (**75-task basis**): **119 memories have exactly 1**, 18 have 2,
**18 have 3**, 5 have 4, 2 have 5, 1 has 6, 2 have 8, 1 has 9.

> ⚠️ **State the basis whenever these are quoted.** Two bases exist and they differ:
> **76 discriminative tasks** (including one LLM-judged) → **267 edges**, 17 memories with
> exactly 3; **75 deterministic tasks** → **266 edges**, 18 with exactly 3. The executed
> design (`results/ledgers/k1_screened_design.json`) and `scripts/audit_claims.py` both use
> the **75-task basis**, so that is canonical. An earlier version of this file mixed the two
> in one sentence — quoting 76/75 tasks alongside the 76-basis edge count. Found by SA-FIG;
> the error was the Master Agent's.

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

## 🔴 The 46 are not 46 independent draws — episode clustering

Found by Sub-agent K, **independently verified by the Master Agent**: the 46 memories sit
on only **23 distinct source trajectories**.

| memories from one trajectory | trajectories |
|---|---|
| 1 | 9 |
| 2 | 8 |
| 3 | 5 |
| **6** | **1** |

Six page visits from one browsing episode are six *views of one episode*, not six
independent memories. A Wilson interval at n = 46 treats them as independent and is
therefore **too narrow**.

> **Binding: report BOTH the unit-level (n = 46) and the episode-clustered (n = 23) rate,
> with the clustered interval as the conservative one. Where the two readings differ, the
> clustered one governs the claim.** They are not substitutes.

`run_deltau_pilot.sample_memories` already enforces one unit per trajectory for exactly
this reason; the screened design must not quietly discard that discipline.

## The token-band cap — a content-blind exclusion, fixed before outcomes

The bearing set is token-heavy: median **12,261**, max **694,188** (the pilot band was
1,500–5,000). Keeping all 46 means ~40k-token contexts at the tail.

**Cap: 20,000 tokens**, which retains **35 of 46 memories (21 of 23 episodes)** and 114 of
147 bearing edges, giving ~25k median context at K = 4 filler — comparable to the pilot's
27k.

The reason is not convenience. **~25k is inside the regime J's 22/22 needle control
actually certified; ~40k is not.** An effect measured where the reader is known to read
beats a larger denominator where it is not.

The rule is **content-blind, size-only, and fixed before any outcome is observed**, and the
11 excluded memories are named in the run manifest. Report **35 units / 21 episodes**, with
46/23 beside them so the cost of the cap is visible.

## Filler cannot leak a bearing target

Filler is drawn from **244 units on 50 trajectories disjoint from every bearing
trajectory**, and the disjointness is asserted in code so a violation fails the run rather
than silently contaminating it.

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

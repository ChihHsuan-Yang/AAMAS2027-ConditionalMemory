# Representation Comparison — Contribution B

**SA-R's scale-up, 2026-09-30. Every figure below recomputed by the Master Agent from the
row artifacts.** 285 design cells, 60 memories, 126 tasks, 2 replicates, ~349 s wall.

---

## The result: compression destroys the effect

Paired within-memory (BEARING − MATCHED_CONTROL), on the **277 cells present in all three
representations**, 57 memories:

| representation | paired B−MC | 95% CI | non-zero contributors |
|---|---:|---|---:|
| **Raw** | **+0.3174** | **[+0.1912, +0.4457]** | 33 / 57 |
| Summary | +0.0613 | [−0.0430, +0.1635] | 26 / 57 |
| Structured | −0.0498 | [−0.1441, +0.0379] | 20 / 57 |

> **Only Raw's interval excludes zero.** Summarizing or structuring the same source
> experience, with the same writer, reader and tasks, **removes the measured benefit.**

Unpaired means tell the same story: BEARING mean ΔU **+0.3453** (raw) vs **+0.0647**
(summary) vs **+0.0148** (structured).

## The cost axis inverts the ranking — but ONLY if formation cost is not charged

🔴 **CORRECTED 2026-09-30 by SA-R.** The table first published here charged no formation
cost. `MEMORY_PROTOCOL.md` §5 requires it ("the efficiency frontier must charge each
representation for its own formation cost, or it flatters the model-written ones"), and
Amendment A1.5 pre-registers the check. Both columns are kept, because the size of the
discount an uncharged comparison hands the model-written arms *is* the finding.

| representation | median exposed tok | ΔU / 1k, **exposure only** | ΔU / 1k, **formation charged** |
|---|---:|---:|---:|
| Raw | 8,344 | +0.0368 | **+0.0368** |
| **Summary** | 282 | **+0.2054** | **+0.0342** |
| Structured | 216 | +0.0622 | +0.0076 |

BEARING cells, ratio of totals. Amortized formation cost is **1,626 tokens/cell**
(summary) and **1,715** (structured) — the writer read the whole 7,092-token median
segment to produce a 282-token memory, and that read is billed.

> **Uncharged, Summary looks 5.6× more token-efficient than Raw. Charged, it is
> 0.93× — i.e. no better.** The ranking does not survive the accounting the protocol
> mandates. Structured is 4.8× *worse* than Raw once charged.

**Raw's number is bit-identical in both columns** (+0.03677601 either way), which is
Amendment A1.5's correctness test for the attribution: raw makes zero extraction calls,
so if it had moved at all the cost would have been mis-assigned.

⚠️ Both Summary efficiency figures rest on a mean whose CI includes zero. **Neither is a
superior operating point.** The honest frontier statement is that at this compression
ratio there is **no operating point where compression wins**, once its own cost is paid.

The amortization is a design parameter, not a property of the representation: each memory
here is reused across **4.86 cells**. A deployment reusing one memory hundreds of times
would drive the formation term toward zero and recover the exposure-only column. That is
why both are reported.

## What this answers from the brief's nine questions

1. **Does compression preserve downstream usefulness?** **No** — not at this ratio. 0.063
   (summary) and 0.037 (structured) compression lose the effect.
2. **Which gives the highest utility per exposed token?** **Summary, by 5.6×, only if the
   writer call is free.** Charged its own formation cost as `MEMORY_PROTOCOL` §5 requires,
   Summary is +0.0342 against Raw's +0.0368 — **no advantage** — and Structured is 4.8×
   worse. At a reuse factor of 4.86 the compression does not pay for itself.
3. **Which creates the most harmful transfer?** No representation shows robust harm;
   structured's point estimate is negative but its CI spans zero.
4. **Are some Raw memories useful only because of incidental detail?** **Consistent with
   the data but not established** — the raw-only benefit is what a "yes" would look like,
   and we have not isolated the mechanism.

Unanswered: domain dependence (one benchmark), and whether a *less aggressive* compression
preserves the effect — we tested two points, both ≤0.063.

## Instrument findings from SA-R, verified

**The pilot's "0/8 malformed JSON" did not scale, and the right reading is two numbers:**

| | numerator | denominator | rate |
|---|---:|---:|---|
| malformed structured, all writes | 3 | **60** | **0.050** |
| malformed **given the write completed** | **0** | **57** | **0.000** |
| malformed given the write hit the token cap | 3 | 3 | **1.000** |

All three failures are `finish_reason == "length"` with **valid JSON cut off mid-value** —
a budget failure, not a formatting one. At n = 8 the pilot never met the cap, so it could
not have observed this. **8 cells were excluded from structured** for failed writes; the
exclusion is recorded per cell, not silently dropped.

**The 2-vs-3 replicate substitution was measured, not assumed.** On the 285 existing Raw
cells: mean-of-3 differs from mean-of-first-2 in **0/285**; replicates disagree in
**0/285**. Verified independently by the Master Agent.

**Faithfulness proxy is controlled in both directions.** Self-scoring gives 1.0 on 5/5; a
**planted hallucination fires on 5/5** (number_support 1.000 → 0.909–0.980). Without the
negative control, "no unsupported numbers" would be a claim about a detector never shown
to fire.

## 🔴 The Raw arm and the new arms were measured on DIFFERENT DAYS, and the endpoint moved

**Found by SA-R via a control that had no reason to fail.** The WITHOUT arm renders
byte-identical context in all three representations, so its answers must agree. Within
the 2026-09-30 run they do, exactly:

| within-session check | result |
|---|---|
| summary-WITHOUT vs structured-WITHOUT, same run | **554 / 554 identical** |
| distinct `context_sha256` per (task, replicate) WITHOUT group | **0 of 252** have more than one |
| replicate-to-replicate, summary / structured | **285/285** and **277/277** identical, both arms |

Against the Raw run of 2026-09-29, on prompts re-derived and hash-matched as
byte-identical, they do not: **text differs on 302 of 570 rows (53.0%)** and **reward on
14 (2.46%)**.

A **cache-disabled probe** (`results/repr_scaleup/cross_session_probe.json`, 12 real
calls, 6 prompts × 2 repeats) settles which side moved: same-minute repeats **6/6
byte-identical**, reproduces the 09-30 answer **6/6**, reproduces the 09-29 answer
**2/6**. So this is a **serving change between the two days**, not sampling
nondeterminism at temperature 0.

### Sized, not assumed

`scripts/r2b_raw_resample.py` re-measured Raw's WITH arm on **100 cells today**, cache
disabled, same filler, with the target position asserted to reproduce k2's on **100/100**
(otherwise the probe would measure a position effect instead of drift).

| Raw WITH arm, 09-29 vs today | |
|---|---|
| output text identical | 52 / 100 |
| **reward identical** | **86 / 100** |
| reward changed | 14 — **7 up, 7 down** |
| **mean reward_with** | **0.3100 → 0.3100, difference +0.0000** |

The drift is **symmetric and mean-preserving on this sample**. A fully same-session Raw
ΔU — WITH from that resample, WITHOUT from this run — reproduces the contrast at n=99:

| contrast | same-session | cross-session, same cells |
|---|---|---|
| summary − raw | −0.1515 [−0.2525, −0.0505] | −0.1616 [−0.2727, −0.0505] |
| structured − raw | −0.1616 [−0.2525, −0.0606] | −0.1717 [−0.2828, −0.0606] |

> **The conclusion does not rest on the cross-session join.** But every Raw-vs-new
> comparison in this document carries a per-cell noise term that a same-session
> comparison would not, and the paper must say so.

## A join trap, hit by the Master Agent — third occurrence

`memory_id` is a **content hash**, so it **differs across representations by design**.
Joining Raw to Summary on `memory_id` returns **zero paired memories**, which reads as "no
data" rather than "wrong key". The correct join is **`memory_unit_locator`**.

This is the third time the `memory_id`/locator ambiguity has produced a silent zero in this
project. See `docs/DEFECT_REGISTER.md`.

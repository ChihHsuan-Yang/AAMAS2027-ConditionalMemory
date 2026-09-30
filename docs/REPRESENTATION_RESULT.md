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

## But the cost axis inverts the ranking

| representation | median exposed tokens | ΔU per 1k exposed tokens (BEARING) |
|---|---:|---:|
| Raw | **8,221** | +0.0420 |
| **Summary** | **282** | **+0.2296** |
| Structured | 216 | +0.0686 |

**Summary is ~5.5× more token-efficient than Raw** while delivering ~19% of the absolute
effect. At a fixed context budget that trade may be worth taking; at a fixed task it is
not. **This is the frontier, and the two axes genuinely disagree** — which is the point of
having both.

⚠️ The Summary efficiency figure rests on a mean whose CI includes zero. **Do not present
it as a superior operating point**; present it as the trade the frontier exposes.

## What this answers from the brief's nine questions

1. **Does compression preserve downstream usefulness?** **No** — not at this ratio. 0.063
   (summary) and 0.037 (structured) compression lose the effect.
2. **Which gives the highest utility per exposed token?** **Summary**, by ~5.5× over Raw.
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

## A join trap, hit by the Master Agent — third occurrence

`memory_id` is a **content hash**, so it **differs across representations by design**.
Joining Raw to Summary on `memory_id` returns **zero paired memories**, which reads as "no
data" rather than "wrong key". The correct join is **`memory_unit_locator`**.

This is the third time the `memory_id`/locator ambiguity has produced a silent zero in this
project. See `docs/DEFECT_REGISTER.md`.

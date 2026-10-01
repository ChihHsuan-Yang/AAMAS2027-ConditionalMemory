# The Additive Null and the Decomposition — two decisive negatives

**2026-09-29.** Both verified independently by the Master Agent from
`results/deltau_screened/cells.jsonl`.

---

## 1. The excess over the additive null is NEGATIVE in every stratum

Amendment A1.1 requires, for any conditionality claim, **both** an interaction variance
share above the noise floor **and** an excess flip rate over the fitted additive null.

Master Agent's independent computation (fit `μ + a_m + b_t`, simulate with the interaction
removed, 2,000 draws per stratum):

| stratum | observed flip rate | additive-null prediction | **excess** |
|---|---:|---:|---:|
| BEARING | 0.0000 | 0.3854 | **−0.3854** |
| MATCHED_CONTROL | 0.0286 | 0.6116 | **−0.5830** |
| RANDOM | 0.2833 | 0.9966 | **−0.7133** |

Sub-agent K's audited code gives −0.2286 / −0.6857 / −0.7167, p = 1.0000. **The magnitudes
differ** (different simulation details; neither is audited as canonical) — **the sign is
identical in all three strata, and the sign is what the claim turns on.**

> **There are FEWER sign flips than an interaction-free model predicts.** Even RANDOM's
> 0.2833 — the number an unscreened design would publish as evidence of task-conditional
> memory value — is far *below* what memory and task main effects alone produce.

This is stronger than "flips are not evidence of interaction". Flips are **not even at the
level additivity alone would generate**. The A1.1 evidence standard is not merely unmet; it
is met in the wrong direction.

## 2. The decomposition is unidentifiable — and my accepted diagnosis was wrong

**What I accepted earlier:** that the previous fit failed because 93 of 220 tasks were seen
by exactly one memory, and that widening the task axis would fix it.

**The fix worked.** On the crossed core — tasks seen by ≥2 memories — single-memory tasks
went to **0 by construction**, and mean tasks per memory rose 8 → **19.3**.

**The fit is still unidentified.** Task and interaction shares come back **exactly equal to
16 significant figures**, pinned at the optimizer's clip, with a fitted residual of
**3.07e-06**.

### The real cause: `F_exec = 0`

Verified: **0 of 1,157 cells have replicates that disagree.** The reader is deterministic
at temperature 0 **within a session**, so the residual variance is exactly zero — and
**with no residual scale there is nothing to identify variance components against.**

> **The scope does not weaken this conclusion, and is stated so the number is
> not over-read.** The replicates being compared were issued **0.0–15.7 s apart**
> (median 0.0 s) inside one 0.81 h run, re-derived from
> `results/deltau_screened/cache.jsonl`. That is exactly the right scope for an
> *execution*-noise floor, and unidentifiability follows from it. What it does
> not license is "a re-run tomorrow scores the same": across one day the same
> WITHOUT requests moved 554/1,124 on this model. There is no measured
> F_session. See `docs/SESSION_DETERMINISM_AUDIT.md`.

> The crossing defect was real and the fix succeeded. **The conclusion did not follow from
> it.** A successful repair that does not produce the expected result is evidence the
> diagnosis was wrong, not evidence the repair failed.

MoM on the crossed cores returns 0.5876 / 0.6044, but from the same degenerate residual, so
it rescues nothing. **No variance share is quoted anywhere as a result.**

### A denominator discrepancy, resolved

K reports single-memory tasks as **0/218**; I computed **83/218**. Both are correct and
measure different subjects: K's is on the **crossed core** (0 by construction), mine is over
**all tasks**. Per stratum: BEARING 20/56, MATCHED_CONTROL 63/100, RANDOM 80/147. Recorded
because "0/218" without its subject would read as a stronger claim than it is.

## 3. What this means for the paper

**Neither leg of A1.1's evidence standard is satisfiable on this design.** The interaction
variance share cannot be estimated at all, and the excess is negative.

That is not a gap to apologize for — it is a finding about what a deterministic reader
costs you. A reader with no execution noise gives clean ΔU measurements and **destroys the
variance-decomposition approach entirely**, because components are only identifiable
relative to a residual. Anyone planning this measurement should know that the two goals are
in tension.

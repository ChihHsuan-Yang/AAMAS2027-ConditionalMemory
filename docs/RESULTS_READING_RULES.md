# How to Read the Screened Result — rules fixed before the numbers

**2026-09-29, written while the run is at 5,008/5,198.** Every rule below is already
committed elsewhere; this is the single page to read alongside
`k3_screened_analysis.json` so the artifact cannot be misread by whoever opens it —
including by me.

---

## Read in this order. Do not skip to the effect size.

### 1. `STOPPING_RULE.VERDICT` — read this first, before any ΔU

- `SCREEN DID NOT MATERIALLY REDUCE BOTH-ARMS-FAIL` → **that is the headline.** The
  instrument cannot detect the phenomenon, the downstream numbers are uninterpretable, and
  nothing gets dressed up. The paper reports a documented negative and the three settled
  findings that do not depend on this run.
- `SCREEN BOUGHT MEASUREMENT CAPACITY` → continue to 2.

Criterion, fixed in code before the data: BEARING's Wilson **upper** bound below RANDOM's
point estimate. Verified to return both verdicts.

### 2. `PAIRED_POWER_STATUS`

- `UNDERPOWERED` → **a null here is not evidence of no effect.** Report as underpowered.
  ⚠️ If the status is near its boundary, the two power simulations disagree by 2–3×
  (`docs/PAIRED_POWER.md`) and must be settled by an audited simulation **before** the
  verdict is quoted.
- `ADEQUATE` → continue.

### 3. `paired_within_memory` — the claim-carrying contrast

All three strata contain the **identical 60 memories**, so this is paired: memory identity
cancels, and per-memory quality is *arithmetically* incapable of producing a difference
(verified bit-identical across quality sd 0→500).

Report **three** numbers together, never one:
- the **all-memories** mean — honest, diluted by structural zeros, and the one the
  significance verdict comes from (it is pre-registered and does not condition on outcome);
- the **contributors-only** mean — the conditional magnitude, which **conditions on an
  outcome** and can never be the population claim;
- the **non-zero contributor count** beside the nominal 60.

### 4. Intervals — the clustered one governs

Where `GOVERNING: task_clustered` appears, the cell-level *p* is **not** the number to
quote. A cell-level *p* of 0.0015 has already been observed surviving the removal of one
task by exactly +0.0000. Likewise the episode-clustered flip interval governs over the
unit-level one: 35 units sit on 21 episodes.

### 5. Flip rate — descriptive only

**A sign flip is not evidence of interaction.** Flips occur at 53–92% with interaction
*identically zero* (Amendment A1.1). Quote the flip rate **only** beside the excess over
the fitted additive null. Report `robust == naive` as **NOT MEASURABLE**, never as a gap of
zero — under a deterministic reader the measurement cannot be taken.

### 6. Variance decomposition — probably not identified

Predicted before the run: 38% of tasks are still seen by exactly one memory. If
`AT_UPPER_BOUNDARY`, report **not identified** and quote **no share**. A clipped ratio
previously returned shares equal to 16 significant figures while reporting
`converged=True`.

---

## What the paper says under each outcome

| outcome | the paper |
|---|---|
| screen worked, effect present | leads with the effect; scarcity and dilution explain why naive designs miss it |
| screen worked, no effect | a real negative on a capable instrument — reportable, and the instrument is the contribution |
| **screen failed** | leads with **why the measurement is hard**: bearing scarcity, ~80% both-arms-fail, the reader ruled out, the position confound |
| underpowered | states the ceiling is the corpus (a memory bears on a median of one task), not the budget |

**In every branch there is a paper.** The four settled findings — scarcity, dilution, the
reader ruling-out, and the position confound — are measured, written, and independent of
this run's outcome.

## The standing rule

> No number from this artifact enters the manuscript until it is re-derived from the row
> file by `scripts/audit_claims.py`, which is proven able to fail (a single flipped reward
> trips four checks).

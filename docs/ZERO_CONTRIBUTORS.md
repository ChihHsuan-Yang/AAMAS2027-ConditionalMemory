# Zero Contributors — reporting rule, fixed before the results

**2026-09-29.** Raised by Sub-agent K from a pre-flight on old data with random strata
(non-predictive, but diagnostic of a structural risk); quantified by the Master Agent.

---

## The issue

In the paired per-memory test, each memory contributes one number: its mean ΔU on bearing
cells minus its mean ΔU on control cells. A memory whose cells **all fail in both arms**
contributes **exactly 0.0** — not a small number, a structural zero.

K's pre-flight showed `+3 / 0:48 / −9`: **48 of 60 memories contributed exactly zero.**

> **A paired test over 60 memories where 48 are zeros is not a test over 60.**

## What zeros do, measured

Simulated: 60 memories, a true effect of +0.30 among contributors, the rest exactly zero.

| non-zero contributors | mean paired diff | 95% bootstrap CI | excludes 0 |
|---:|---:|---|---|
| 60 | 0.3302 | [+0.2463, +0.4136] | yes |
| 30 | 0.1258 | [+0.0712, +0.1872] | yes |
| 20 | 0.1269 | [+0.0728, +0.1840] | yes |
| 12 | 0.0695 | [+0.0218, +0.1242] | yes |
| 8 | 0.0471 | [+0.0145, +0.0891] | yes |
| **5** | 0.0087 | [−0.0011, +0.0223] | **NO** |

Two things follow, and they pull in different directions:

1. **The test stays valid.** Zeros shrink the mean *and* the CI proportionally, so the
   type-I error is not inflated — a significant result with many zeros is still a real
   result.
2. 🔴 **The reported magnitude is diluted by the zeros.** At 12 contributors the same
   underlying +0.30 effect reports as **+0.0695**. Quoting that as "the effect of a bearing
   memory" understates it by more than 4×, because it averages over memories where no
   effect could have been observed.

## Reporting rule

Whenever the paired test is reported:

1. **State the count of non-zero contributors beside the nominal denominator.**
   "60 memories (12 non-zero contributors)" — never "60 memories" alone.
2. **Report both magnitudes, labelled:**
   - *over all memories* — the honest population-level figure, diluted by zeros;
   - *over contributors only* — the conditional effect where an effect could be observed.
   Neither alone is the answer; the first understates the mechanism, the second conditions
   on an outcome and cannot be a population claim.
3. **The significance verdict comes from the all-memories test**, which is the
   pre-registered one and does not condition on an outcome.
4. If non-zero contributors fall below ~8, **say the test is underpowered** rather than
   reporting a null — at 5 contributors the simulation above fails to detect a true +0.30.

## Why this is not a workaround

The zeros are the same phenomenon the paper documents from two other directions:
memory–task bearing is scarce (`BEARING_SCARCITY.md`), and unscreened cells fail in both
arms (`PILOT_VERDICT.md`). A memory that contributes zero to the paired test is a memory
whose tasks the reader could not solve either way. **That is a finding about the corpus and
the reader, not a nuisance to be averaged over silently.**

# Defect Register — 2026-09-29

Every instrument defect found on the project's first execution day, with who found it and
what it would have cost. **Kept because the pattern matters more than any single entry:
each one produced a plausible-looking number.**

Nothing here is a process complaint. It is the evidence base for the paper's methods
section and for the claim that the measurement is trustworthy.

---

## Defects that reached a reported number before being caught

| # | Defect | Reported as | Caught by | Would have cost |
|---|---|---|---|---|
| 1 | Replicates were not byte-identical — position seeded by `replicate_id` | "endpoint is nondeterministic, 4.3%" | Sub-agent G | a fabricated execution-noise floor |
| 2 | `judge_floor` grouped byte-identical text **without the task** | "F_judge = 0.1486" | Sub-agent H | a fabricated judge floor; 18/18 groups spanned tasks |
| 3 | `ZeroDivisionError` crashed the decomposition **while the script exited 0**; caller read an empty dict through `.get(c, 0.0)` | "variance shares all 0.0000" | Sub-agent H | **a null reported as measured** |
| 4 | `leakage_flag` is not discriminative — fires on unpaired memories at ratio **0.995** | "the bottleneck is reader capability" | Sub-agent J | **the wrong scientific conclusion**, and a benchmark change |
| 5 | Embedding cap bisected on prose 2× sparser than real data | "working cap 3,400 tokens" | Sub-agent G | 10/10 embedding failures at run time |

## Defects caught before they reached a number

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 6 | `select_filler` re-randomized on exclusion (25/25 non-drawn exclusions changed the draw) | Sub-agent G | corrupted `F_empty`: the WITHOUT arm would differ between memories |
| 7 | WITHOUT arm servable from cache across memories | Master (pre-registered as A1.4) | `F_empty = 0` ⇒ **every ΔU trivially "significant"** |
| 8 | Sign flips occur at 53–92% with **zero** interaction | Sub-agent D | **the headline claim**: a flip rate reported as evidence of conditionality |
| 9 | REML not identified — shares equal to 16 s.f. at the clip ceiling, `converged=True` | Sub-agent H | a fabricated variance decomposition |
| 10 | Truncation scored as a wrong answer (`reasoning_tokens` eats `max_tokens`) | Sub-agent C | ΔU pushed negative ⇒ **manufactured harmful memories** |
| 11 | HF `auth-check` returns 200 for repos we cannot write | Sub-agent E | a failed upload believed pre-verified |
| 12 | `reader_model` in the condition key defeated the cluster-homogeneity check | Sub-agent E | silent pooling of two clusters |
| 13 | Cache-lock test vacuous (distinct keys never exercised check-then-act) | Sub-agent C, by mutation testing | an unprotected race believed tested |
| 14 | Concurrency ladder measured one wave at the top level | Sub-agent C | a wrong throughput ceiling |
| 15 | Python 3.9 aborts pytest collection on a vendored file | Master | **a healthy suite looking broken** |

## The pattern

**Eleven of these produced a plausible number.** None announced itself as an error. The
recurring shape, in one line:

> A check that inspects the wrong subject reports confidently.

Sub-shapes, each seen more than once today:
- **an absent value defaulting to a plausible one** (#3, #11, and a near-miss in J's own
  verification script);
- **a null with no positive control** (#4, #6, and my own leakage-denominator error);
- **a measurement made on unrepresentative material** (#5, #14);
- **a crash inside a pipeline whose exit code stayed 0** (#3).

## What actually caught them

Not review-by-reading. In every case: **re-running the measurement against a control that
should behave differently.**

- mismatch control on an unpaired memory (#4)
- planted defect that the estimator must flag (#2, #3)
- mutation testing (#13)
- comparison against a no-exclusion baseline rather than between two exclusions (#6)
- exercising the same probe on real data rather than synthetic (#5)
- a positive control on a known-good case (#15)

## The same defect, found independently by two agents within minutes

**Joining on a field that shares a NAME rather than a REFERENT.**

`results/deltau_screened/cells.jsonl` carries `memory_id` as a canonical content hash
(`mem-013696c4-eae1...`). `data/manifests/k1_screened_cells.jsonl` carries a *different*
upstream `memory_id` (`cc470fce0740eb16`) plus the locator. **Same field name, different
referent.**

| who | symptom | what it would have cost |
|---|---|---|
| Sub-agent K | verification reported **all 2,599 rows disagree** with the design on stratum | a false integrity alarm on a clean run |
| Master Agent | paired test returned **0 memories** | reporting the headline contrast as empty |

Both re-joined on the locator and got **2,599/2,599 agreement, zero mismatches**.

Two things worth keeping:

1. **The 100% disagreement rate was the tell.** As K put it, a *partial* mismatch would
   have been far more dangerous — it would have looked like a data problem worth
   investigating rather than an obviously broken join. A result that is uniformly extreme
   is usually a property of the instrument.
2. **This is the `memory_id` collision from this morning, resurfacing.** It was ruled on
   (`memory_id` = content hash, `memory_unit_locator` = positional) and the ruling was
   applied — but only in the manifests I rewrote, not in the upstream file K's design was
   built from. **A naming ruling enforced in some artifacts and not others is worse than
   no ruling**, because downstream code then joins on a name that is authoritative in one
   file and misleading in another.

## 🔴 The most dangerous defect of the session: a correct verdict derived from no data

Sub-agent K's `FOUNDING_HYPOTHESIS` field printed:

```text
SIGN-REVERSAL COMPONENT NOT SUPPORTED: 0 of 0 flip-eligible BEARING memories
```

**0 of 0.** It read `labels_and_flips["flips"]`, a key that does not exist — the emitter
produces `primary_balanced` / `secondary_all_replicates` / `bh_corrected`. A `.get()` chain
defaulted to `{}`, the denominator came out zero, and the verdict string was assembled from
nothing.

### Why this is worse than every other defect here

**The verdict was correct.** The true value is 0 of 35, the conclusion the paper will
publish is the one the data supports, and the sentence would have survived every review —
including mine.

> **It was not derived from the data.** Had the truth been "17 flips", the field would have
> printed the identical verdict. A guard that reaches the right conclusion from an empty
> input **has not been tested by agreeing with you.**

Every other defect in this register announced itself by producing a *wrong* number. This
one produced a right one.

### What actually caught it

Not review, not a test, not the verdict looking odd. **K had hand-computed 0 of 35 from the
rows an hour earlier, and the printed denominator disagreed.** Without that prior
independent number, nothing in the pipeline would have flagged it.

### The two rules this yields

1. **A verdict must print the evidence it rests on.** `0 of 0` and `0 of 35` give the same
   conclusion and are distinguishable only because the denominator is shown. A verdict
   string without its denominator cannot be checked by anyone, including its author.
2. **A zero denominator must raise, never report.** Fixed to read `primary_balanced`
   (prereg §12: the balanced minimum-replicate subset is primary) and to raise on a missing
   block or an empty denominator.

This generalizes past this project: **the last defect you find is the one whose output you
agreed with.**

## A named pattern: the pooled number hides the structure that matters

Three times in one day, a correctly-computed pooled figure led to a wrong reading, and each
time the fix was to split it by the variable that actually varied:

| pooled figure | what it hid |
|---|---|
| V2 leakage **26.96%** | 97.71% at ≤2-char golds (multiple choice — measuring the alphabet) vs **4.68%** at >30 chars. The pooled rate tracks answer length, not memory |
| both-arms-fail **~80%** | that the rate is a property of the *pairing*, and collapses on cells where the memory bears on the task |
| task concentration **34.6%** | that MATCHED_CONTROL — the stratum carrying the claim — is **2.2× less concentrated** than RANDOM (max 4 cells/task vs 40) |

None of these was a computation error. Each was a real number that answered a question
nobody had asked, and in two of the three the pooled version pointed the *opposite* way
from the truth.

> **Rule: before quoting a rate, ask what it is an average over, and split it by that.**
> If the split changes the reading, the pooled number does not go in the paper alone.

### Fourth instance, and the subtlest: a matching COUNT read as convergence

Sub-agent K observed that the paired test's **35 non-zero contributors** equalled the
**35-unit flip denominator** pre-computed from the design manifest hours earlier, and was
about to report it as two routes converging.

Checked by the Master Agent: **they are different sets.**

| | |
|---|---|
| non-zero paired contributors | 35 |
| memories with ≥2 BEARING cells | 35 |
| **overlap** | **25** |
| in one set only | 10 each way |

The cardinality matches; the membership does not. *"Two routes agree"* implies mutual
corroboration, and here **neither corroborates the other.**

It also fails an obvious mechanism check: a memory with ≥2 bearing cells can contribute
exactly zero (if all its cells fail both arms), and a memory with one bearing cell can
contribute non-zero. There is no reason for the sets to coincide — and they don't.

> **The subtlest form of the pattern: the number was right, the count was right, and only
> the identity of what was counted was wrong.** Before reporting two measurements as
> agreeing, check that they are measurements *of the same objects*, not merely of the same
> size.

**The mechanism is visible in the rows**, and it is the scarcity finding again:

| case | count | in the executed run |
|---|---|---|
| memories with **≥3** bearing cells contributing **exactly zero** | **4** | all their cells fail both arms |
| memories with **exactly 1** bearing cell contributing **non-zero** | **10** | one bearing cell is enough |

So both directions of non-membership are populated by real, inspectable cases. A memory
with four bearing cells contributing exactly zero *is* the scarcity result — the mechanism
was already written down elsewhere in the report and still was not applied to the sentence
in question.

⚠️ Note when quoting individual examples: the short `mem-…` prefixes are **not unique** —
two distinct memories share each 8-hex prefix in this run. Quote the full id.

K's own framing of why this instance is worse than the pooled-number cases is worth
keeping: those *answered a well-posed question badly*, whereas this one **asserted
corroboration that did not exist** — the kind of sentence that makes a reviewer trust a
table they should check.

## Make the ruling mechanical where you can

A ruling a human must remember at reporting time is a ruling that will eventually be
forgotten. Sub-agent K's `GOVERNING: task_clustered` field — emitted into the analysis
artifact whenever the clustered CI and the cell-level p disagree — is the better form: the
artifact refuses to be misread, rather than relying on the reader to recall a policy.

Prefer: a field in the artifact > an assertion in code > a line in a doc > an agreement.

## Three of these were mine

Defects #1, #4, #5 were in code or reasoning I authored, and #3 I reported to the user as a
measured result. Each was found by an agent I had asked to check my work. That is the
argument for the cross-checking discipline, and the reason none of them is in the paper.

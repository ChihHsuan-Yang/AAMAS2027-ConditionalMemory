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

## Added 2026-09-30 — found while building the Gemma reader arm (SA-GEMMA-READER)

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 16 | **The truncation guard's observable was a property of gpt-oss, not of truncation.** `finish_reason=="length" AND not content.strip()` fires on gpt-oss because reasoning tokens eat the budget and the answer comes back null. Gemma has no separate reasoning stream, spends the budget on the ANSWER, and returns a grammatical FRAGMENT (`"Here is the step-by-step"` at `max_tokens=8`). The clause is False; the fragment is returned as a normal answer | SA-GEMMA (flagged), SA-GEMMA-READER (fixed + regression-tested) | a fragment scored as a wrong answer ⇒ ΔU negative ⇒ **a manufactured harmful memory** — defect #10 recurring in a new disguise |
| 17 | **The truncation guard and the model-id pin ran on a FRESH response but NOT on a cache hit.** Demonstrated: store `finish_reason="length"` + `content=""`, read it back, no exception | SA-GEMMA-READER, by trying the cache path on purpose | the runner's RESUME path is a cache read, so a killed-and-resumed run would score exactly the truncations the first run refused — and the first run's refusal is what makes the ledger trustworthy |
| 18 | **`CLUSTER_REPORTS_REASONING_TOKENS` is keyed on CLUSTER, on a premise measured on one model.** "Metis reports reasoning tokens" is true of `gpt-oss-120b` and FALSE of `gemma-4-31B-it` on the same cluster (no `completion_tokens_details` at all) | SA-GEMMA-READER, by validating a Gemma row before writing one | two failures at once: a spurious `reasoning_tokens_missing` warning on every correct Gemma row (training a reader to ignore it), and **silence on the real corruption** — `reasoning_tokens=0`, an absence written as a measurement |
| 19 | **A case-variant model id returns HTTP 200 and is silently corrected.** `gemma-4-31b-it` (lowercase b) is not a 404; metis resolves it to `gemma-4-31B-it` | SA-GEMMA | `_assert_model` catches it at call time, but a mis-cased config would pass every dry run and every liveness check |

### Pre-existing truncation exposure on the gpt-oss arms — a finding, not a fix

Auditing the shipped caches for defect #16's shape found it is **not
Gemma-specific**: `results/deltau_pilot/cache.jsonl` has **8** rows with
`finish_reason=="length"` and non-empty content, and those 8 reached **8
scored cells** — 6 WITHOUT-arm fragments of 3,011 chars, and 2 WITH-arm rows
whose entire output was `\boxed{C`, a truncated answer token scored as a wrong
answer.

**All 8 have ΔU = 0.0 and `utility_label = undetermined`, so no reported
number moves.** The two main runs (`deltau_screened`, `repr_scaleup`) have
**zero**. Handed back undecided in `docs/MODEL_ARMS.md`: re-running or
annotating those cells is a decision about published results, not a code
change, and the strict guard was deliberately NOT switched on for the gpt-oss
arms so that fixing a Gemma hazard could not silently alter a shipped table.

### The shape, again

Three of the four are the same shape in a new costume:

> **A check that was verified on its home case is not known to discriminate on
> an unfamiliar one.** #16 and #18 each passed every test for an entire
> project because the only reader was the one they were written against. The
> new reader did not break them; it revealed that their subject had always
> been the model, not the thing they claimed to measure.

#17 is the adjacent shape: **a guard enforced on one path and not its
alternative**, where the unguarded path is the one a resumed run takes.

What caught them: not reading the code. Running the new model against the old
assumption, and — for #17 — deliberately constructing the stored row the guard
was supposed to reject. Each fix carries a regression test **verified to fail
against the unfixed code** (three mutations, each caught).

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

## Two published numbers the audit could not see — found by SA-ARCHIVE

Both were mine, both were in the manuscript, and both survived because **the audit checked
the point estimate and never the quantity the sentence actually asserted.**

### 1. A confidence interval no artifact contained

The paper printed the episode-clustered CI as **[+0.1989, +0.4758]**; the analysis artifact
says **[+0.1974, +0.4736]**. The printed values were my own one-off bootstrap, not the
audited ones — close enough to look right, different enough to be wrong.

> **The audit verified `mean_paired_difference` and never either interval.** A number can
> be adjacent to an audited one and still be unaudited.

Fixed in the paper and in `SCREENED_RESULT.md`; the audit now checks **both** intervals
against the artifact, and I verified the check fires by restoring the wrong value.

### 2. "Roughly 5×" was true of the wrong representation

The paper said charging formation cost makes Raw more efficient **by roughly 5×**. On the
audited basis — formation amortised **per memory**, not per cell — that is:

| | ratio |
|---|---:|
| uncharged, Summary / Raw | 5.58× |
| **charged, Raw / Summary** | **1.08×** |
| charged, Raw / Structured | 4.84× |

**4.84× is Structured. The sentence was about Summary, where the true figure is 1.08×.**
So charging *erases* Summary's advantage rather than reversing it — a weaker and more
accurate claim. Corrected, with audit guards on all three ratios plus a check that the
manuscript no longer contains the overclaiming phrase.

⚠️ Note the near-miss underneath: my own re-derivation gave **4.88×**, agreeing with the
paper, because I amortised formation **per cell** while the audit amortises **per memory**.
Two defensible bases, one of which made a wrong sentence look verified. Same shape as the
76/75-task basis error.

## A single table column built on two different bases (mine)

I handed SA-FIG2 a three-column efficiency table. It verified the numbers before drawing
and **two of the three columns did not hold up.**

**The exposed column mixed bases.** Verified by the Master Agent:

| | all BEARING (n=139) | common-277 join (n=135) |
|---|---:|---:|
| raw | **+0.0380** | +0.0368 |
| summary | +0.1987 | **+0.2054** |
| structured | +0.0622 | +0.0622 |

My table took Raw's **+0.038** from the 139-cell basis and Structured's **+0.062** from the
135-cell join. Both correct; **they do not describe the same objects**, and they sat in one
column as if they did.

**The charged column silently changed amortization.** My figures charged the whole ~7.9k
writer call to *every read* (reuse = 1); the audited accounting amortizes over the measured
**4.86** reuse. That is the same per-cell vs per-memory split that made my "roughly 5×"
claim look verified.

> **A column is a claim that its entries are comparable.** Mine was not, and nothing in the
> audit checked *comparability* — only individual values. The generator now refuses a
> mixed-basis substitution, verified by planting exactly that defect.

### SA-FIG2's own tell, worth keeping

A naive string replace hit **Figure 3's** geometry instead of Figure 4's — both used
`xshift=124pt`. It caught this because **the overfull box stayed at 10.87727pt after an edit
that should have moved it.** *An unchanged measurement after a change is the tell.*

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

## A measurement insensitive to the thing it was measuring (mine)

I reported the manuscript had "roughly zero slack" for further figures, from the **total
page count**: 8 pages before Figure 1, 9 after.

**Total page count cannot answer that question here.** References are uncapped and absorb
the change, so the count stays at 9 across a wide range of added float height. SA-FIG
measured the right observable — **where the body ends** — by inserting dummy floats of
known height and bisecting:

| added float height | body still ends p8? |
|---|---|
| +100pt / +250pt / +290pt / +310pt | ✅ yes |
| +330pt / +400pt | ❌ spills to p9 |

**≈310pt of single-column float height remains free** — about another figure's worth.
Figure 2 went in at ~171pt and the body still ends on page 8, which I confirmed
independently.

> I used the *right criterion in words* — "where does the body end" — and then read the
> **wrong instrument** for it. Page count is a proxy that is flat in the region of
> interest. The same shape as measuring throughput at the wrong prompt length, or reading
> a rate off the wrong denominator.

**Rule: when a quantity must guide a decision, check that the instrument actually moves
when the quantity does.** A bisection against the real observable takes minutes and
replaces an estimate with a bound.

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

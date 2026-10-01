# Length-controlled representation test — PRE-COMMITMENT

**Written 2026-10-01 by SA-LENGTH, BEFORE any reader call was issued against a
truncated memory.** It closes the strongest remaining alternative explanation
for Story 2.

The question a reviewer will ask:

> Raw memories are ~30× longer than the model-written ones. Is the measured Raw
> advantage a **representation** effect, or simply a **more-tokens** effect?

Restated as the testable form:

> **At comparable exposed-memory length, does the extractive representation
> still preserve more downstream utility than model-written compression?**

---

## 1. What was measured first, and what is frozen here

Per the binding order of work, **the confound was measured before the design was
chosen**. That measurement is §2. It is disclosed in full because it preceded
the freeze and because parts of it touch outcome data.

**Frozen here, before execution:** the condition definitions, the truncation
rule and its version string, the cell set, the contrast that carries the claim,
the estimator, the CI method, the controls, and the meaning of every possible
outcome.

**Disclosed, because it preceded the freeze:**

| looked at before freezing | why it was necessary | does the design depend on its value? |
|---|---|---|
| exposed-token distributions per representation on the 277 matched cells | the confound itself — step 1 of the order of work | no |
| **within-Raw dose-response** (uses published `delta_utility`) | the only way to ask "how much could length explain" from existing data | **no** — the design is identical under either sign |
| **bearing-content retention** under each candidate truncation rule (gold detector on truncated text, **no reader call**) | choosing a truncation rule blind to whether it retains anything would have burned the budget on a condition that cannot answer the question | **yes — the rule was chosen on this.** See §4.3 for why this is a feasibility measurement and not an outcome-selected analysis |
| exact token-budget achievability under the official tokenizer | budget matching must be *measured*, not assumed | no |

🔴 **No reader call has been made with a truncated memory. No ΔU, reward, or
model output of any truncated condition has been computed or seen.** The
retention figures in §2.3 are a property of the *text*, computed offline by a
pure-Python detector.

---

## 2. THE MEASURED CONFOUND (step 1, complete)

All figures re-derived by SA-LENGTH from `results/deltau_screened/cells.jsonl`
(Raw) and `results/repr_scaleup/cells.jsonl` (Summary, Structured), joined on
`(memory_unit_locator, future_task_id)` — **never** on `memory_id`, which is a
per-representation content hash and returns zero rows across arms.

**Positive control on the join, run first:** the join yields exactly the
published **277** common cells, and re-deriving the published Contribution-B
table from it reproduces it to four decimals — paired B−MC of **+0.3174**
(raw), **+0.0613** (summary), **−0.0498** (structured) over 57 memories, and
mean ΔU **+0.1805 / +0.0397 / +0.0181** over 277 cells. A join that reproduces
the published table is a join that matched the right rows.

### 2.1 Exposed-token distributions — the arms do not overlap at all

Exposed memory tokens, official tokenizer (`Qwen/Qwen3.5-9B`,
`add_special_tokens=False`), one value per cell, 277 cells:

| representation | min | p25 | **median** | p75 | max | mean |
|---|---:|---:|---:|---:|---:|---:|
| **Raw** | 1,490 | 5,085 | **8,344** | 12,890 | 19,801 | 9,227.9 |
| **Summary** | 139 | 215 | **280** | 407 | 604 | 322.8 |
| **Structured** | 120 | 188 | **216** | 275 | 453 | 237.8 |

> 🔴 **The distributions are completely separated.** Raw's **minimum** (1,490)
> exceeds Summary's **maximum** (604) by 2.5× and Structured's maximum (453) by
> 3.3×. **0 of 277** Raw cells fall inside the Summary range; **0 of 277** fall
> inside the Structured range. Median ratio: Raw is **30.0×** Summary and
> **41.3×** Structured.

**This is the whole problem, stated precisely.** There is no subset of the
existing data on which length is matched. Within the published experiment,
representation and exposed length are not merely correlated — they are
*perfectly* separated, so **no reweighting, covariate adjustment, or matched
subsample of existing cells can separate them.** Any length control requires
**new conditions and new reader calls**. This is why the confound cannot be
closed by analysis and is pre-registered as an experiment.

### 2.2 How much could length plausibly explain? — the within-Raw dose-response

If "more exposed tokens → more utility" were driving the result, utility should
rise with memory length *within* the Raw arm, where representation is held
constant. Spearman and quartile means over the same 277 cells:

| stratum | n | Spearman ρ(tokens, ΔU) | Pearson r | Q1 (1,490–5,085) | Q2 | Q3 | Q4 (12,890–19,801) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **BEARING** | 135 | **−0.209** | −0.185 | **+0.5000** | +0.4062 | +0.1379 | +0.3000 |
| MATCHED_CONTROL | 142 | +0.079 | +0.067 | +0.0278 | 0.0000 | 0.0000 | +0.0714 |

> **Within the Raw arm the dose-response runs the wrong way.** The *shortest*
> quartile of Raw memories has the **largest** mean ΔU (+0.50); the longest
> quartile has +0.30. A naive more-tokens mechanism predicts the opposite
> ordering.

**What this does and does not license.** It does **not** prove the Raw advantage
is representational: the within-Raw range (1,490–19,801) never reaches the
compressed arms' range (120–604), so this is an extrapolation of ~2.5× beyond
the observed support, and a mechanism could behave differently in the gap. It
*does* mean the simplest version of the reviewer's objection — "utility rises
with exposed tokens, Raw just has more" — **is contradicted by the data inside
the arm where it is directly testable.** The honest summary of step 1:

> **Length cannot be ruled out, because the arms do not overlap at all; but the
> monotone-in-tokens mechanism that would explain the gap is not visible inside
> Raw, where it would be easiest to see.**

### 2.3 Feasibility: does a content-blind truncation keep the bearing content?

The gold-answer detector (`p1mem.adapters.leakage.detect`, the project's own
screen, `any_leak`) fires on **135/135** BEARING cells for full Raw text — that
is the definition of the stratum — and on **0/142** MATCHED_CONTROL cells, which
is the detector's negative control on this set. Applied to candidate truncations
at **each cell's own Summary token budget**:

| condition at matched budget | bearing content retained (BEARING, n=135) |
|---|---:|
| Raw, full segment | 135/135 = **100.0%** (by construction) |
| **TRUNC-LAST** (final N tokens) | **39/135 = 28.9%** |
| **SUMMARY** (model-written) | 24/135 = 17.8% |
| STRUCTURED (model-written) | 17/135 = 12.6% |
| TRUNC-SEEDED (seeded contiguous window) | 11/135 = 8.1% |
| **TRUNC-FIRST** (first N tokens) | **1/135 = 0.7%** |

Budget ladder for TRUNC-LAST, same cells:

| budget | retention | median exposed tokens |
|---|---:|---:|
| matched to Summary (median 280) | 28.9% | 282 |
| 512 | 40.0% | 512 |
| 1,024 | 48.1% | 1,024 |
| 4,096 | 83.7% | 4,096 |
| 8,192 | 90.4% | 8,191 |
| ≥ 19,801 | 100% (text is identical to Raw) | = Raw |

**Three consequences, all of which shape the design:**

1. **TRUNC-FIRST at the matched budget measures truncation, not
   representation.** At 0.7% retention it is a condition in which the thing
   being compared has been removed. It is kept as a **floor**, never as the
   claim-carrying arm.
2. **TRUNC-LAST at the matched budget retains *more* than Summary does
   (28.9% vs 17.8%).** This matters for fairness: the length-controlled
   extractive condition is **not** handicapped relative to the compression it
   is tested against.
3. **Retention is itself a result.** At the compressed budget, *every* arm
   loses most of the bearing content; Raw retains it only because its budget is
   ~30× larger. That observation is part of the answer, and §7 fixes how it is
   read.

### 2.4 Budget matching is exact, and is checked in the reader's tokenizer too

Truncation is by binary search on characters against the **official tokenizer**
— the same routine `r2_run_representations.py` already uses. Achieved minus
target, over all 277 cells: **mean 0.00, median 0, min 0, max 0 — exact in
277/277.**

Because the budget is *defined* in the official tokenizer but *consumed* by the
reader, both are reported. Reader tokenizer (`o200k_harmony`): Summary median
246 tok, TRUNC-LAST median 235 tok; the per-cell difference (trunc − summary)
has median **−5**, mean −0.6, p5 −22, p95 +46 on a ~246-token memory. **The
length-controlled arm is, if anything, marginally *shorter* in the reader's own
tokenizer** — so a surviving extractive advantage cannot be bought with tokens.

### 2.5 What is NOT matched, stated plainly

Matching *exposed memory* tokens leaves **total context** unmatched: median WITH
-context is ~24,356 tok for Raw and ~16,292 tok for every compressed arm
(filler is identical, median 16,012). This is unavoidable — equalising total
context would require padding, which `src/p1mem/cells.py` refuses for a
documented reason. The direction is conservative for the primary contrast
(TRUNC vs SUMMARY are matched on both), and is a caveat only for TRUNC vs RAW.

---

## 3. The conditions

All share one source segment per memory and differ **only** in the text placed
at the target slot. Eight arms, **all executed in ONE session** (§5.1).

| arm | `condition_id` | memory text | budget |
|---|---|---|---|
| `raw` | `lmev2_raw_lenctl_v1` | whole segment verbatim | — (median 8,344) |
| `summary` | `lmev2_summary_lenctl_v1` | the existing frozen Summary | — (median 280) |
| `structured` | `lmev2_structured_lenctl_v1` | the existing frozen Structured | — (median 216) |
| **`trunc_last_matched`** | `lmev2_trunclast_matched_lenctl_v1` | **final N tokens of the segment** | **N = that cell's own Summary token count** |
| `trunc_first_matched` | `lmev2_truncfirst_matched_lenctl_v1` | first N tokens of the segment | same N |
| `trunc_last_1024` | `lmev2_trunclast_1024_lenctl_v1` | final 1,024 tokens | 1,024 |
| `trunc_last_4096` | `lmev2_trunclast_4096_lenctl_v1` | final 4,096 tokens | 4,096 |
| `trunc_last_20000` | `lmev2_trunclast_20000_lenctl_v1` | final 20,000 tokens | 20,000 — **≥ max Raw (19,801), so the text is byte-identical to Raw in 277/277. This is the A/A control, not a condition.** |

### 3.1 The truncation rule, and why it is content-blind

```
TRUNC_RULE_VERSION = "trunc_last_n_tokens@1.0.0"   /   "trunc_first_n_tokens@1.0.0"
```

The rule takes a **fixed positional slice** of the segment to a **fixed token
budget**. It reads **no task, no question, no gold answer, no reward, no
embedding, and no informativeness score.** It is the same kind of object as
`RAW_SPAN_RULE_VERSION = "raw_whole_segment@1.0.0"`: a deterministic span rule
with a version string, zero model calls, and `extraction_calls = 0`.

**Why not "select the most informative span".** `MEMORY_PROTOCOL.md` §1A forbids
it and `representations.py` implements that prohibition deliberately:
informativeness is the value judgement under measurement, so selecting on it
assumes the conclusion. A task-aware extractive rule would beat Summary by
construction and the result would be worthless.

**Why last-N and not first-N as the primary.** Both are content-blind. They are
run **as a pair** precisely because neither is neutral *with respect to the
corpus*: these are browsing trajectories, and the measured 0.7% vs 28.9%
retention gap says the bearing content lives near the **end** of a page-visit
segment. That is a property of this corpus, disclosed here, and it is why:

- **last-N carries the claim**: at the matched budget it is the content-blind
  rule that gives the extractive representation its *best honest shot*, and it
  is not handicapped against Summary (28.9% > 17.8%). A null from a crippled
  condition would be uninformative.
- **first-N is the floor**: it bounds what a length-matched extractive condition
  looks like when the bearing content is gone. The gap between them is a
  **measurement of where bearing content sits**, reported as a result.

🔴 **This is a disclosed limitation of the generalisation, not of the test.**
"Extractive selection at matched budget" is instantiated here as *one* positional
rule on *one* corpus. The claim licensed is about that rule, not about every
extractive rule.

### 3.2 Held fixed across all arms — the list is load-bearing

* **Position.** Seeded by `(task_id, manifest memory_id)` — **never** by the
  per-arm content hash and never by `replicate_id`. Varying position changed the
  answer in **8 of 12** cells (`docs/POSITION_EFFECT.md`); an arm that moved the
  target would confound representation with position. **Asserted equal across
  all eight arms per cell (C5).**
* The same K=4 filler, the same `filler:{task_id}` seed, the same pool (sha
  asserted against the screened run's recorded fingerprint).
* The same system prompt, question scaffold, reader, cluster, `temperature=0`,
  `reasoning_effort=low`, `max_tokens=512`, 2 replicates.
* The same 277 cells, the same strata.

---

## 4. Cell set, contrast, analysis

### 4.1 Cell set

The **277 cells present in all three published representations** — 57 memories,
124 tasks, 135 BEARING + 142 MATCHED_CONTROL. Fixed; no cell is added or dropped
on any outcome. Join key `(memory_unit_locator, future_task_id)`.

### 4.2 The contrast that carries the claim

> **PRIMARY.** Per-cell paired difference on **BEARING** cells:
> **Δ = ΔU(`trunc_last_matched`) − ΔU(`summary`)**, both arms session-matched,
> same memory, same task, same filler, same position, **matched exposed-token
> budget**. Point estimate = mean over 135 cells; 95% CI by **task-clustered
> bootstrap**, 10,000 resamples of whole task clusters (55 clusters), seed
> `20261001`, percentile method — the project's existing
> `cluster_bootstrap_paired`, not a reimplementation.

Task clustering is required: a third of all cells sit on ten tasks
(`docs/CONTRAST_FRAMING.md`).

**Pre-registered sensitivity of the primary** (reported always, never used to
pick a headline): the same contrast with Δ = ΔU(trunc_last_matched) − ΔU(structured).

**SECONDARY, in the published table's own shape:** within-memory paired
**B−MC** per arm over the 57 memories, so the new arms appear in the
Contribution-B table on the same footing as Raw/Summary/Structured.

**THE LADDER (pre-registered as the identification, not as decoration):**
ΔU for `trunc_last` at {matched, 1024, 4096} against measured retention at the
same budgets. If utility tracks **retention** rather than **token count**, the
mechanism is content presence; the budget is instrumental. This is what
distinguishes "exposure budget" from "tokens" as the narrowed Story 2.

### 4.3 The subgroup that is pre-registered as OFF LIMITS

It is tempting to condition on "cells where the truncation retained the bearing
content" (n = 39) or on "cells where both arms retained it" (**n = 9**). Both
are **pre-registered as excluded from the verdict**: an effect measured on cells
selected for retaining the signal is circular, and n=9 cannot carry a CI.
Retention is reported as a **2×2 descriptive table** — TRUNC-LAST × SUMMARY on
BEARING: both 9, trunc-only 30, summary-only 15, neither 81 — and **never** as
a conditioned effect estimate.

### 4.4 Rules that bind the analysis

* `reward is None` means **could not be scored**. Never coerced to 0.0. Cells
  with a null reward in any arm are reported with their count and excluded from
  the paired contrast as a **named** exclusion, never silently.
* Every number in the result doc is re-derived from the row artifact.
* No absolute `/Users/<name>/` path in any tracked artifact (defect 23/29).

---

## 5. Controls, fixed in advance

### 5.1 C-SESSION — all eight arms in ONE session (defect #25)

`gpt-oss-120b` is deterministic **within** a session and **not across** one:
byte-identical re-issues 24 h later differed on **554/1,124** rows. Raw's
published numbers were measured 2026-09-29 and the compressed arms 2026-09-30,
so **the published cross-arm comparison spans sessions.** Every arm here —
including Raw and Summary, which already have published numbers — is
**re-executed in one process**. Published values are used only as a *prior
reference*, never as a comparator. Asserted: one `run_id`, and the wall-clock
span of the whole execution recorded.

### 5.2 C-AA — the identity positive control

`trunc_last_20000` renders text **byte-identical to Raw** in 277/277 cells
(max Raw = 19,801), but travels under a different `condition_id` and a different
memory content hash, so it is a genuinely separate set of calls.

* **Assert:** truncated text == raw text, 277/277, by sha256.
* **Require:** its rewards reproduce the `raw` arm's **exactly**, in-session.
* **If they do not**, the harness is wrong and no other number from this run is
  reportable. This is the strongest available end-to-end control: it exercises
  the entire new code path and has a known correct answer.

### 5.3 C-PLANT — plant the defect, watch the guard fail

A guard verified only on its home case is not known to discriminate. Each is run
against a **deliberately broken** version and must FAIL:

1. truncation that returns the full text → the budget assertion must fire.
2. truncation off by +25 tokens → the exact-budget assertion must fire.
3. position re-seeded per arm → the position-equality assertion (C5) must fire.
4. `memory_id` used as the join key → must return **0** rows, demonstrating the
   known trap is detected rather than silently producing an empty table.
5. a `None` reward coerced to 0.0 → the None-guard must fire.

Each plant is asserted to fail the guard **and** the unplanted case asserted to
pass it. A control that cannot fail is not a control.

### 5.4 C-POWER — positive-control the null (binding on O2 and O4)

A null is not evidence unless the test could have detected the effect. Into the
`trunc_last_matched` arm's ΔU, plant a synthetic uplift equal to the **measured
session-matched Raw−Summary BEARING gap** and require the primary CI to exclude
zero. For reference, the published-data gap is **+0.2741**, task-clustered CI
[+0.1259, +0.4203] over 55 clusters, CI half-width **0.147** — so this design
resolves a true difference of ~0.15 or larger. **A reported null is
accompanied by this number or it is not reported.**

### 5.5 C-JOIN, C-TOK, C-DET

* **C-JOIN** — the join returns exactly 277 on `memory_unit_locator`, and
  **0** on `memory_id`; both asserted.
* **C-TOK** — achieved budget == target in the official tokenizer for every
  truncated cell; the reader-tokenizer (`o200k_harmony`) counts are recorded per
  cell so the match is auditable in the tokenizer that actually consumes it.
* **C-DET** — the gold detector's own controls (`LK.controls_summary()`) pass
  before any retention number is reported, and the detector is shown to be
  silent on 142/142 MATCHED_CONTROL cells.

---

## 6. Cost

8 arms × 277 cells × 2 replicates × 2 sub-arms (with/without) = **8,864 calls**.
At the measured 341 completions/min that is **~26 min**. The WITHOUT arm is
regenerated per arm (Amendment A1.4) and its cross-arm byte-identity is a free
control.

---

## 7. WHAT EACH OUTCOME MEANS — written before the result is seen

Let **T** = `trunc_last_matched`, **S** = `summary`, **R** = `raw`, all
session-matched. Primary Δ = ΔU(T) − ΔU(S) on BEARING, task-clustered CI.
**All five outcomes are acceptable. No outcome is being aimed for.**

### O1 — REPRESENTATION SURVIVES AT MATCHED LENGTH
**Δ > 0 and its CI excludes zero.**
At equal exposed length, the extractive representation preserves more downstream
utility than model-written compression. The more-tokens explanation fails on its
own terms. **Story 2 keeps a representation claim**, narrowed to its warrant:
*a content-blind extractive slice beats model-written compression at an equal
token budget, on this corpus, for this positional rule.* The paper must still
report that both short arms lose most of the bearing content, and that Raw's
absolute advantage over both is partly budget.

### O2 — THE EFFECT DISAPPEARS AT MATCHED LENGTH
**Δ's CI includes zero, while C-POWER shows the test could have detected a
~0.15 effect, and ΔU(R) − ΔU(T) is positive with a CI excluding zero.**
Then **extractive and model-written compression are indistinguishable once
length is held fixed, and the Raw advantage is an exposure-budget effect.**
**Story 2 must narrow, in the manuscript, to "exposure budget and formation
cost"** — and must say plainly that *the representation comparison does not
survive a length control*. The Contribution-B sentence "compression destroys the
effect" would have to be rewritten as **"compressing to this budget destroys the
effect, and an extractive memory at the same budget loses it too — what Raw buys
is the budget to carry the bearing content, at zero formation cost."** The
cost-axis result (Raw is not beaten once formation cost is charged) is
unaffected and becomes the load-bearing half of Story 2.

### O3 — COMPRESSION WINS AT MATCHED LENGTH
**Δ < 0 and its CI excludes zero.**
Model-written compression is *better* than content-blind extraction at an equal
budget. Then Raw's advantage is entirely its length, **and** the paper gains a
positive finding it does not currently have: at a fixed small budget, paying a
writer call buys more utility than truncating. Story 2 inverts and must say so.

### O4 — THE CONDITION DEGENERATES INTO A TRUNCATION TEST
**Both T and S sit at ≈0 with CIs including zero, the ladder shows no recovery
at 1,024/4,096, and C-POWER passes.**
Then at this budget the bearing content is absent from every arm, and the
comparison **cannot be identified at the compressed budget** — it is measuring
truncation. This is reported as **"not identifiable at a 280-token budget"**,
with the retention table as the explanation, and the ladder reports the budget at
which identification becomes possible. **No effect number from such a stratum is
reported as if it were an answer.**

### O5 — THE HARNESS FAILS ITS OWN CONTROL
**C-AA does not reproduce Raw exactly, or any C-PLANT guard fails to fire.**
Nothing from the run is reportable. The defect is recorded and fixed, and the
run repeated.

**Pre-registered precedence.** O5 dominates all. O4 is checked before O1/O2/O3:
a condition that retained nothing cannot adjudicate representation. Among
O1/O2/O3 the sign and CI of Δ decide, and **the verdict is taken from the
primary contrast as defined in §4.2 — not from the sensitivity, not from the
secondary, and not from any subgroup.**

---

## 8. Artifacts

| path | content |
|---|---|
| `docs/LENGTH_CONTROL_PRECOMMITMENT.md` | this document, committed before execution |
| `scripts/len1_build_length_control.py` | truncation rule, conditions, all controls |
| `scripts/len2_analyze_length_control.py` | contrasts, CIs, verdict against §7 |
| `results/length_control/cells.jsonl` | every row of all eight arms |
| `results/ledgers/length_control_confound.json` | §2, machine-readable |
| `results/ledgers/length_control_result.json` | the contrast, CIs, controls, verdict |
| `docs/LENGTH_CONTROL_RESULT.md` | the result, read against §7 |

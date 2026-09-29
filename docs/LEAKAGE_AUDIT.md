# Leakage Audit — LongMemEval-V2

Measured by Sub-agent A; **every rate below re-derived independently by the Master Agent**
from `data/manifests/lmev2_leakage_informative_summary.json`.

Policy: **FLAG, NEVER DROP.** 18,169 cells flagged, 0 dropped. Dropping leaky cells
changes the question being answered.

---

## The rates — and why the pooled number must not be quoted alone

| gold-answer length | flagged / cells | any-leak rate |
|---|---:|---:|
| 6–12 chars | 12,458 / 51,957 | **23.98%** |
| 13–30 chars | 4,696 / 63,183 | **7.43%** |
| **>30 chars** | 1,015 / 30,453 | **3.33%** |
| pooled | 18,169 / 145,593 | *12.48%* |

**All four reproduce exactly.** 1,889 memory units × 141 tasks.

> 🔴 **Do not quote 12.48% on its own.** The monotone fall with gold length —
> 23.98% → 7.43% → 3.33% — is a **degeneracy signature**, not a property of memory. A
> 6-character gold answer ("Yes", "$14.69", a SKU fragment) appears by chance in long
> web-trajectory text; a >30-character answer does not. The pooled figure is therefore
> dominated by how short the answers happen to be, not by how often a memory really
> contains the answer.
>
> **The >30-char stratum at 3.33% is the closest thing to a true leak rate**, and it is the
> number to reason with. Report the stratified table, always.

## Every rate is a LOWER bound — a real bug in the official scorer

`normalize_phrase` in the benchmark's own `qa_eval_metrics.py` strips punctuation
**without inserting a space**, so `value='GPS…` collapses to `valuegps…` and a genuine
leak goes undetected. Pinned as an expected-failure control.

Concretely: **594 cells were caught by our `exact` detector and missed by the official
scorer.** Marginals in the summary file (`exact` 7,851, `official` 13,576, `any` 18,169)
show the detectors are non-nested; the 594 is a per-detector intersection recorded by A.

The **156 LLM-judged questions are structurally undecidable** for leakage without an
inference call, and are excluded from the audit.

## Detector validation — on real data, not only on plants

Controls **17/17 pass**; **two failed on first run** (both control-construction errors, one
of which exposed the scorer bug above).

The strongest evidence is not the plants. On LongMemEval **V1**, where ground-truth
evidence labels exist, the detector — *with no access to those labels* — separates:

- labelled evidence **471/948 = 49.68%**
- filler **4,492/22,919 = 19.60%**
- **ratio 2.53×**, and the separation **holds in every gold-length stratum** (18.1× at
  13–30 chars)

A detector that discriminates a known-positive population it was never shown is genuinely
measuring something.

⚠️ **Denominator trap.** `lmev1_leakage_s.jsonl` stores **only flagged rows**. Computing
the rate over manifest rows gives 76.2% vs 48.3% — a figure that conditions on already
being flagged and is meaningless. The Master Agent made exactly this error on first
re-check. The denominators are the full evidence (948) and filler (22,919) populations.

## One label correction

The summary file records `"n_tasks": 156`, which is the count of **LLM-judged** questions
— the ones *excluded*. The audited set is **141 deterministic tasks** (verified: all 141
task ids in the flagged rows have non-`llm_` eval functions). A mislabel in the summary
key, not a wrong measurement; the rates are unaffected.

## How this enters the analysis

1. Report the **stratified** table in the paper; never the pooled rate alone.
2. Report every headline result **with and without** flagged cells. If the conclusion
   depends on including them, say so explicitly.
3. State that rates are lower bounds, with the scorer bug as the reason.
4. Leakage is **not** a defect of the benchmark — a naturally occurring memory that happens
   to contain the answer *is* a real memory being genuinely useful. What must be excluded
   is *task-directed writing*, which the protocol prevents structurally. The audit
   separates the two.

## Results — LongMemEval-V2, FULL matrix (COMPLETE)

All 1,889 units x all same-domain questions (451, incl. LLM-judged) = **423,664 cells**
(1,024 ent x 211 + 865 web x 240 = 423,664). Controls 17/17. **114,207 flagged, none dropped.**
Bucketed on **raw** `len(answer)`.

| stratum (raw chars) | cells | exact | normalized | numeric | official | **ANY** | undecidable |
|---|---|---|---|---|---|---|---|
| <=2 | 56,441 | 97.688% | 20.161% | 1.784% | 1.743% | **97.714%** | 0.000% |
| 3–5 | 75,560 | 38.003% | 20.386% | 3.330% | 19.722% | **44.737%** | 0.000% |
| 6–12 | 53,846 | 12.627% | 18.014% | 5.692% | 17.639% | **23.476%** | 3.508% |
| 13–30 | 68,691 | 1.504% | 5.598% | 1.240% | 5.583% | **6.836%** | 8.019% |
| >30 | 169,126 | 0.023% | 0.189% | 4.492% | 0.144% | **4.681%** | **81.994%** |
| POOLED | 423,664 | 21.650% | 9.594% | 3.549% | 6.954% | **26.957%** | — |

🔴 **The <=2-char row leaks 97.7%** — multiple-choice golds (`G`, `B`, `D`), where one letter appears in
essentially every accessibility tree. That is the alphabet, not the data, and those 56,441 cells alone drag
the pooled figure to 26.957%. **Never quote the pooled number.** The credible figure is the long-answer
row: **4.681% at >30 chars**.

⚠️ The >30 stratum is **81.994% undecidable** (LLM-judged prose answers). Reported as undecidable, never
as clean.

### Cross-validation: two independent runs agree to 3 decimals
The informative-strata run buckets on **normalized** length over the **156** deterministic tasks; the full
run buckets on **raw** length over all **451**. Restricting the full run's committed rows to deterministic
tasks with normalized length >= 6 reproduces it exactly: 6–12 **23.978%**, 13–30 **7.432%**, >30
**3.333%**, ALL **12.479%** over 145,593 cells — identical to the informative run in every cell.
This check was only possible because the audit writes **row-level flags**, not summary rates.

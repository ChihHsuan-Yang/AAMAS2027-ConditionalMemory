# Benchmark Scope Decisions

**Master Agent, 2026-09-29**, on Sub-agent A's measurements (re-verified where noted).

---

## The frozen object requires one thing above all

> **The same memory must be evaluable against MULTIPLE distinct future tasks.**

A benchmark that cannot supply that axis cannot carry Contribution A, however good it is
otherwise.

## Verdicts

| Benchmark | Role | Verdict |
|---|---|---|
| **LongMemEval-V2** | **PRIMARY** | ✅ confirmed: **1,889 memories × 8 tasks each = 15,112 pairs** |
| **SciCode** | secondary, scientific/procedural | ⚠️ usable but **small: ~8–12 donor→recipient pairs** |
| **BEAM** | **DEMOTED to secondary** | 🔴 **92.6% of cited turns are cited by exactly one question** |

## LongMemEval-V2 — the memory unit, settled by measurement

**Unit: the PAGE VISIT** — the maximal run of consecutive trajectory states sharing one
URL. The boundary is drawn by the past agent's **own navigation**, so it is naturally
occurring, and `segment_page_visits()` takes a trajectory and nothing else, so it is
structurally incapable of seeing a future task.

Measured with the **official** `Qwen/Qwen3.5-9B` tokenizer over 200 trajectories / 5,095
states → 1,889 units:

| unit | median tokens | p90 | max |
|---|---:|---:|---:|
| whole trajectory | **103,886** | 646,256 | 2,573,538 |
| single state | 5,628 | 15,592 | 127,129 |
| **page visit (CHOSEN)** | **7,261** | 35,994 | 2,565,842 |

> The inherited "~164k tokens per trajectory" is **not representative** — the distribution
> is extremely right-skewed (median 103,886, p99 2.46M). Subdivision was not a preference;
> a whole trajectory cannot be a memory.

Two properties that make the ablation valid:
- ablating one unit removes a median **3.3% of its own episode / 0.058% of the haystack** —
  a genuinely **local** intervention, which is exactly what `MEMORY_PROTOCOL.md` §4 requires;
- segmentation **preserves answerability for 94.2%** of deterministic questions.

**Verified by the Master Agent** from the committed pair manifest: 15,112 rows, 1,889
distinct memories, **every one paired with exactly 8 tasks**.

⚠️ Current pairing is stratified by **question type**, not embedding distance. The
NEAR/MID/FAR bands (`ANALYSIS_PREREGISTRATION.md` §7) are a **separate post-pass** over
cosine terciles once embeddings exist. Do not confuse the two strata.

## BEAM — demoted, with the reason measured

Obtainable (code MIT / data **CC BY-SA 4.0**). But the diagonality concern is **confirmed
on the data: 92.6% of cited turns are cited by exactly one question.** BEAM cannot supply
the multi-task-per-memory axis, so it cannot carry Contribution A.

**Decision:** BEAM is a **secondary generalization check**, not a primary benchmark, and
only if time permits after V2 is complete. It also ships as a **separate CC BY-SA 4.0
dataset** (see `docs/HF_RELEASE_POLICY.md`) — ShareAlike would otherwise relicense
everything else.

> This is a scope reduction against the frozen plan's three-benchmark target, made on
> measured evidence rather than on time pressure. The handoff permits a *documented
> scientifically justified exception*; this is one.

## SciCode — kept, sized honestly

Apache-2.0. The memory is **a reusable helper function plus its procedure** (e.g. the
minimum-image convention under periodic boundary conditions), and it must be
**cross-problem** — the within-problem version merely re-measures context the harness
already injects.

🔴 **Usable N is ~8–12 donor→recipient pairs, not 80 problems.** That is enough for a
qualitative procedural-memory section, and **not** enough for a variance decomposition
(see `docs/POWER_ANALYSIS.md`: 60 memories minimum). Report it as a case study with its N
stated, never as a second main table.

## Two measurement hazards to carry into the analysis

1. **Exactly one deterministically-scorable `errors-gotchas` question exists**
   benchmark-wide, and it alone accounts for **12.5% of web cells**. **Cluster standard
   errors by `task_id`**, or one question will drive an apparent effect.
2. **All leakage rates are LOWER BOUNDS.** A real bug in the *official* scorer's
   `normalize_phrase` strips punctuation without inserting a space (`value='GPS…` →
   `valuegps…`), so some leaks are missed. Pinned as an expected-failure control. The 156
   LLM-judged questions are **undecidable** for leakage without an inference call.

## Leakage detector — validated on real data, not only on plants

Controls **17/17 pass**, and **two failed on first run** (both control-construction errors;
one exposed the scorer bug above).

The strongest validation is not the plants: on V1 the detector separates labelled evidence
from filler **49.68% vs 19.60%** with no access to labels, and the separation **holds in
every gold-answer-length stratum** (18.1× at 13–30 chars). A detector that discriminates a
known-positive population it was never shown is genuinely working.

**Policy: FLAG, NEVER DROP.** Dropping leaky cells changes the question being answered.

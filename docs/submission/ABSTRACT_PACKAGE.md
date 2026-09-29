# AAMAS 2027 Main Track — Abstract Submission Package

**Ready to paste. Due 1 Oct 2026 AoE.** Drafted 2026-09-29.

---

## 1. Title options

Ranked. All avoid every forbidden claim (see `docs/LITERATURE_BOUNDARY.md`).

| # | Title | Note |
|---|---|---|
| **1** | **Memory Utility Is Not a Scalar: Measuring Task-Conditional Value in Long-Term Agent Memory** | The working title. States the claim as a measurement. ⚠️ Asserts the conclusion — if the interaction turns out to be inside the noise floor, this title becomes false and must change by 8 Oct. |
| **2** | **What Is This Memory Useful For? Measuring Memory-Task Interaction in Long-Term Agent Memory** | **Safest.** Poses the question rather than asserting the answer, so it survives either outcome. Recommended if we want the title fixed now and never revisited. |
| 3 | Useful to Whom? Task-Conditional Utility of Naturally Occurring Agent Memories | Punchier; "to whom" slightly mis-signals multi-agent rather than multi-task. |
| 4 | One Memory, Many Tasks: Decomposing the Downstream Value of Agent Memory | Names the matrix directly; "decomposing" signals the variance analysis. |
| 5 | Does a Memory Have a Value, or Only a Value For Something? | Most distinctive, least conventional. Higher variance with reviewers. |

**Recommendation: register under #2**, and switch to #1 on 8 Oct only if the measurement
supports it. A title can be revised between abstract and paper; an overclaim in the
abstract that the results contradict is far more costly.

> The abstract below is written to be true under **either** outcome — it commits to
> reporting the measurement, not to its sign. This is deliberate. If we register a
> conclusion and the kill criterion fires, we would be forced either to withdraw or to
> submit a paper whose abstract contradicts its results.

## 2. Abstract — FINAL, 268 words

Plain text, no math symbols (the instructions require *"plain text"*). Verified 268 words,
inside *"around 100-300 words"*. Forbidden-claim scan: clean.

The canonical copy is [`abstract_v1.txt`](abstract_v1.txt) — **paste from that file**, not
from this table, to avoid markdown artifacts.

---

Long-term memory is increasingly treated as a store of reusable value: agent memory systems score each retained item and keep the highest-scoring ones. That design assumes a memory's value is a scalar property of the item. We ask whether it is.

We study the downstream causal utility of naturally occurring cross-episode memories, defined as the difference in task reward when a memory is available versus absent, measured by paired re-execution of a frozen agent rather than by semantic similarity or model-judged importance. Holding the executor, decoding, context budget, and scoring fixed, we evaluate the same memory against multiple distinct future tasks drawn at controlled semantic distances from the episode that produced it, and repeat every condition across seeds.

This lets us ask a question the utility-based memory literature has not: not how valuable a memory is on average, but how much of its value belongs to the memory itself rather than to the memory-task pairing. We decompose measured utility into a memory main effect, a task main effect, and a memory-by-task interaction, and compare that interaction against an execution-noise floor estimated from repeated identical conditions. We then measure how often a single naturally occurring memory helps one future task while harming another, counting only sign changes that clear the noise floor, and report how that rate varies with semantic distance from the source episode.

Methods that aggregate utility across semantically related queries treat this variation as noise to be averaged away. We report whether it is instead structure, and state the conditions under which a scalar memory score is an adequate summary of what a memory is worth.

---

### Why it is worded this way

| Choice | Reason |
|---|---|
| "We ask whether it is" | Registers a question, not a result. Survives the kill criterion. |
| "naturally occurring" | The load-bearing word. Planted-fault benchmarks make harm prevalence a *design parameter*; the natural base rate is the defensible number. |
| "paired re-execution of a frozen agent" | Signals the counterfactual is measured, and pre-empts the Memory-R2 fairness critique (shared memory state, single-item ablation). |
| "rather than by semantic similarity or model-judged importance" | States the contrast **without** the forbidden "relevance is not utility" framing. |
| "a question the utility-based memory literature has not" | Asserts a gap in *what is measured*, not priority of *idea*. Not a "first" claim. |
| "how much of its value belongs to the memory itself rather than to the memory-task pairing" | The actual contribution in one sentence: a variance decomposition. |
| "counting only sign changes that clear the noise floor" | Tells a reviewer up front we are not reporting noise as a phenomenon. |
| "Methods that aggregate utility across semantically related queries" | Describes UMEM's neighbourhood averaging **without naming it** (abstract is not the place) and sets up the seam. |
| "We report whether it is instead structure" | Honest. Not "we show that it is". |
| No numbers | We have no results. Registering a number we cannot reproduce would be fabrication. |

### Forbidden-claim scan — clean

Automated scan for: `first`, `novel`, `we introduce`, `we propose`, `relevance`,
`learning what to remember`, `gate`, `state-of-the-art`, `outperform`, `demonstrate that`,
`we show that`, and any `N%` numeric result. **Zero hits.**

## 3. Keywords

AAMAS collects *"keywords characterizing your paper"*. Ordered most- to least-important:

```text
agent memory
long-term memory
counterfactual evaluation
memory utility
task-conditional value
empirical analysis
LLM agents
variance decomposition
```

Short form if the field is capped at ~5:
`agent memory; long-term memory; counterfactual evaluation; memory utility; LLM agents`

## 4. Area

| Field | Value |
|---|---|
| **Primary area** | **Learning and Adaptation (LEARN)** |
| Secondary 1 | Generative and Agentic AI (GAAI) |
| Secondary 2 | Engineering and Analysis of Multiagent Systems (EMAS) |

Rationale: the paper is about what an adaptive agent should retain from experience — LEARN
is the home area. GAAI covers the LLM-agent substrate. EMAS covers empirical analysis
methodology, which is the paper's mode. Up to 2 secondary areas are permitted.

⚠️ Out-of-area papers may be desk-rejected, and ACs check area scope at abstract time.

## 5. Other fields to expect on the form

| Field | Our answer | Confidence |
|---|---|---|
| Title | option #2 (see §1) | ready |
| Abstract | §2 | ready |
| Keywords | §3 | ready |
| Primary / secondary area | §4 | ready |
| Authors + OpenReview ids | 🔴 **user decision** | blocked |
| **Reciprocal reviewer designation** | 🔴 **user decision** | blocked |
| Findings opt-in/opt-out | recommend **opt in** — archival, citable, CC-BY, same format; opting out only narrows outcomes | ready, user confirms |
| Student paper? | user confirms (affects Best Student Paper eligibility only) | user decision |
| Conflicts of interest | user supplies | user decision |

## 6. Pre-submission checklist for 1 Oct

- [ ] User fixes the **author list** (treat as final — see `ELIGIBILITY.md` §6)
- [ ] User confirms **every author has an active OpenReview profile** — must be done by
      hand; the API is login-gated and returns misleading empty results anonymously
- [ ] User **designates the reciprocal reviewer** — a qualified *author*, who must accept
      the invitation by 8 Oct and review by 13 Nov. Changing this later needs PC approval.
- [ ] Paste title, abstract, keywords, area
- [ ] Answer Findings and student-paper fields
- [ ] Submit **before** 1 Oct 2026 23:59 AoE (= 2 Oct 11:59 UTC). Do not rely on any grace.

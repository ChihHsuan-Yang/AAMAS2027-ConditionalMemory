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

## 2. Abstract — FINAL (v2), 268 words

> ⚠️ **v1 is superseded.** v1 said we ask "a question the utility-based memory literature
> has not". That is **false as of 2026-09-29**: EvoMemEval's released artifact contains
> 46 memories evaluated on ≥2 distinct tasks, 17 of which flip between `useful` and
> `harmful` (verified by the Master Agent from downloaded data — see
> `docs/EVOMEMEVAL_VERDICT.md`). Registering v1 would have put an overclaim in the
> permanent record. v2 **concedes the phenomenon is already observed** and claims only
> what survives: signed + replicated + variance-decomposed, against a measured noise floor.

Plain text, no math symbols. **268 words.** Forbidden-claim scan: clean.

Canonical copy: [`abstract_v2.txt`](abstract_v2.txt) — **paste from that file.**

---

Agent memory systems increasingly score each retained item by its downstream usefulness and keep the highest-scoring ones. That design treats a memory's value as a scalar property of the item. Recent work shows the same memory can be useful for one future task and harmful for another, but reports this categorically and one execution per pair, which leaves two questions open: how much of a memory's measured value is attributable to the memory itself rather than to the memory-task pairing, and how many observed reversals survive ordinary execution noise.

We measure the downstream causal utility of naturally occurring cross-episode memories as a signed, repeated quantity: the difference in task reward when a memory is available versus absent, obtained by paired re-execution of a frozen agent, with the executor, decoding, context budget, and scoring held fixed between arms. We evaluate the same memory against several distinct future tasks drawn at controlled semantic distances from the episode that produced it, and repeat every condition across seeds.

We begin by estimating an execution-noise floor from repeated identical conditions, including a no-memory arm that is identical across all memory conditions. Against that floor we decompose measured utility into a memory main effect, a task main effect, and a memory-by-task interaction, reporting the interaction's share of variance. We then count how often one memory's utility changes sign across tasks, admitting only changes that clear the floor, and report how that rate varies with semantic distance.

Methods that average utility over semantically neighboring queries treat this variation as noise. We report whether it is instead structure, and state when a scalar memory score suffices.

---

### Why it is worded this way

| Choice | Reason |
|---|---|
| "Recent work shows the same memory can be useful for one future task and harmful for another" | **Concedes EvoMemEval up front.** A reviewer who knows that work will otherwise stop reading. Conceding it costs nothing and buys credibility for what follows |
| "but reports this categorically and one execution per pair" | The precise, verified gap. Their labels are `useful`/`neutral`/`harmful`, single-shot per cell — so no floor, and no way to know which reversals are real |
| "signed, repeated quantity" | The three-word statement of the contribution |
| "naturally occurring" | Load-bearing: planted-fault benchmarks make harm prevalence a design parameter |
| "paired re-execution of a frozen agent" | Pre-empts the Memory-R2 fairness critique |
| "held fixed between arms" | Pre-empts the verifier-drift confound |
| "a no-memory arm that is identical across all memory conditions" | Names the free noise floor — a reviewer can check the logic without our data |
| "admitting only changes that clear the floor" | Says up front we are not reporting noise as a phenomenon |
| "Methods that average utility over semantically neighboring queries" | Describes UMEM's neighbourhood averaging without naming it; this is the verified seam |
| No numbers | We have no results yet |

### Forbidden-claim scan — CLEAN

Scanned for `first`, `novel`, `we introduce`, `we propose`, `relevance`,
`learning what to remember`, `gate`, `state-of-the-art`, `outperform`, `demonstrate that`,
`we show that`, and any `N%`. **Zero hits.**

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
| Abstract | §2 (**v2** — paste `abstract_v2.txt`) | ready |
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

# Literature Boundary — binding constraints on what this project may claim

**Status:** inherited from the 2026-09-28 audit, currently being re-verified by Sub-agent A.
Until that re-verification lands, treat every *positive* finding here as verified against a
fetched primary source, and every *absence* as provisional.

> ## Why absences here are weak
> The 2026-09-28 audit ran with `WebSearch` hard-blocked by an org policy and with
> arXiv/Semantic Scholar/OpenAlex frequently returning 429. It produced **five confident
> false negatives**, each caught only by a positive control.
>
> **`WebSearch` is STILL BLOCKED as of 2026-09-29** (re-confirmed by the Master Agent:
> HTTP 400, `constraints/vertexai.allowedPartnerModelFeatures`). `WebFetch` works.
>
> **Positive-control every null.** If a query returns nothing, run the same query shape
> against an artifact you know exists. If the control is also empty, report a *channel
> failure*, not an absence.

---

## 1. Forbidden claims

None of the following may appear in this repository, in `docs/`, in code comments, or in
the manuscript. Each is already false.

- ❌ first future-utility memory approach
- ❌ first cross-task / cross-episode memory evaluation
- ❌ first task-conditioned retention or memory controller
- ❌ first counterfactual memory supervision / "we introduce counterfactual memory utility"
- ❌ first learned memory gate
- ❌ "learning what to remember" as a framing (**AdaMem owns the phrase**)
- ❌ first to show relevance differs from utility
- ❌ first to evaluate memory across future queries
- ❌ "We are the first to show memory utility is task-conditional"
- ❌ "Existing memory systems optimize semantic relevance rather than downstream utility"
      — this is near-verbatim MeClear's opening. Quote and cite it instead.

**No "first" claim of any kind** until a fresh adversarial search completes with a working
channel and is recorded in this file.

### Required substitutions

| Instead of | Write |
|---|---|
| "we are first to show utility is task-conditional" | "prior work **asserts** task-conditionality as a design rationale **without measuring it**; we measure it" |
| "memory systems optimize relevance not utility" | quote MeClear and cite it |

## 2. The closest collision: UMEM (arXiv:2602.10652)

Verified 2026-09-29 by the Master Agent (arXiv `abs`, HTTP 200): *"UMEM: Unified Memory
Extraction and Management Framework for Generalizable Memory"*, Ye, Jiang, Jiang, Lan, Du,
Fu, Shi, Jia, Wang, Luo — submitted 11 Feb 2026, cs.CL, CC BY 4.0.

Confirmed from the abstract: UMEM trains a single LLM for joint memory extraction and
management, adds **"Semantic Neighborhood Modeling"**, and trains with a
**"neighborhood-level marginal utility reward"** under GRPO, explicitly judging a memory's
value **"across groups of semantically similar queries rather than one query alone."**

UMEM therefore already has: persistent cross-episode memory; downstream marginal-utility
reward; evaluation of one memory on queries other than its source; a capacity comparison.

### The seam P1 claims — UNDER RE-VERIFICATION

> UMEM uses cross-query variation as a **denoising instrument** — it averages over a
> cosine neighbourhood because it treats that variation as **noise**. P1 asks whether the
> variation is **signal**: whether it carries task-specific structure that averaging
> destroys.

Sub-agent A is verifying, from the full PDF: the exact reward formula, the exact N, the
Appendix C.1 ablation sentence, and — decisively — **whether UMEM anywhere reports the
variance or dispersion of per-task utility rather than only its mean.** If it reports
dispersion, this seam narrows sharply and must be restated.

**If the seam does not survive verification, the project's framing changes. It is not
optional to check.**

## 3. Open risks to the seam

| Risk | Status |
|---|---|
| **EvoMemEval** (OpenReview `n3GMbobXnc`) may already evaluate one memory against several distinct future tasks | 🔴 **being checked — highest priority.** If yes, P1's last surviving component is at risk |
| MeClear (2609.09115) computes per-memory LOO + Shapley from real re-execution — but **within one query's context, never across queries** | to re-verify |
| MemGate posits a per-(memory, query) admissibility indicator but never materializes it | to re-verify |
| Multi-Factor Value Model (2606.12945): a [16,16] MLP **ties** a 4-feature linear scorer | counter-evidence to any capacity headroom claim |
| UMEM found 4B beats 1B | counter-evidence in the other direction |

## 4. Two design hazards that bind the experiment

These affect the experiment design, not just the citations.

1. **TraceRetain** (2606.29178, ICML 2026) is an honest null: *"differences among bounded
   retention policies fall within Wilson 95% CIs"* on clean benchmarks. **Without real
   memory pollution, every arm lands in the same CI and P1 measures nothing.** The stress
   condition must be justified before running, not after.

2. **Memory-R2** (2605.21768): *"Once different rollouts write, update, or delete different
   memories, they no longer share the same intermediate memory state, making
   trajectory-level comparisons fundamentally unfair."* P1's single-memory ablation against
   a **fixed** memory set is closer to their local-rerollout fix than to the design they
   criticize — **but this must be argued explicitly in the paper, not assumed.**

## 5. Prior art outside the memory literature

- **When2Tool** (2605.09252): tool necessity is *linearly decodable* from pre-generation
  representations at AUROC 0.89–0.96, beating the model's own verbalized reasoning. If a
  linear probe also solves memory retention, P1's learning stage is a domain transfer of a
  known result, not a discovery. P1's honest differentiator: tool necessity is resolvable
  from the current turn; memory retention has a **deferred, counterfactual payoff that
  depends on a task not yet seen.**
- **Influence Guided Context Selection** (2509.21359, Sep 2025): LOO downstream deltas +
  a trained surrogate for value prediction — a year earlier, outside memory.

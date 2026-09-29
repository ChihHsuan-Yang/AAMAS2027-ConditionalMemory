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

> ⚠️ **The fresh adversarial search has NOT completed.** It was dispatched and did not
> return before its agent ended. Treat this section as **incomplete**, not as clear. No
> novelty sentence may enter the manuscript on the strength of it.

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

### The seam P1 claims — ✅ VERIFIED TO SURVIVE (2026-09-29, full PDF)

> UMEM uses cross-query variation as a **denoising instrument** — it averages over a
> cosine neighbourhood because it treats that variation as **noise**. P1 asks whether the
> variation is **signal**: whether it carries task-specific structure that averaging
> destroys.

**Verified from the full 16-page PDF.** The reward is `Δu(q′) = G_succ(q′) + R_eff(q′)`
with `G_succ(q′) = c(τ^mem) − c(τ^ref)`, then collapsed, verbatim: *"the average marginal
utility over the neighborhood, r_g = E_{q′∼NN(q)}[Δu(q′)]."*

**Dispersion: VERIFIED NEGATIVE.** UMEM computes the per-task values and keeps only the
mean. A controlled grep finds no variance, dispersion, spread, or negative-utility
reporting anywhere in the paper. **The seam survives.**

### Two corrections to the inherited notes — do not repeat them

1. 🔴 **N = 3, not 5.** §5.1 states *"Top-N (N = 3)"*. N = 5 is the **too-broad ablation
   arm**, not the operating point. The inherited `LITERATURE.md` has this wrong.
2. 🔴 **Appendix C.1 is Lemma C.1, with a proof** — not a bare assumption. It concludes the
   neighbourhood *"effectively captures the cluster of future queries that will likely
   retrieve (and reuse) the same memory."* **Engage it as an argument; do not dismiss it as
   an assumption.**

⚠️ **Do not over-quote the ablation.** *"An overly broad one (N = 5) introduces noise that
dilutes the reward signal"* is single-run, has no confidence intervals, and N = 5 actually
*improves* HLE by 1.6 on one backbone.

## 2b. 🔴 EMBER (arXiv:2606.05894) — a real collision the prior audit missed

**Verified from the full PDF, 2026-09-29.** EMBER's **MultiQ** split, verbatim:
*"MultiQ-LongMemEval-RR tests whether **one frozen retained memory can serve multiple
future tasks**."* Table 4 caption: *"One retained memory serves multiple future queries
over the same history."* Construction: *"groups five future questions over one compiled
history... 100 groups."* — **5 tasks per memory, 100 bundles.**

It also reports a dispersion-like statistic under another name. Table 18: *"coverage
balance is min_j RetainRecall(q_{g,j}), averaged over bundles; it measures whether one
frozen memory also covers the hardest query in the bundle."* Heuristics reach mean
0.106–0.120 while coverage balance sits at **0.0000** across all four budgets.

### What this forbids, and what survives

**Forbidden, concretely:** any claim to be first to evaluate one memory against several
future tasks. EMBER did it, named it, and tabulated it.

**Why P1's object still differs — three structural gaps, all verified:**

| | EMBER MultiQ | P1 |
|---|---|---|
| Granularity | policy × bundle vector, **no per-item score** | per-(memory, task) cell — **a matrix** |
| Metric range | Retain-Recall in [0,1], non-negative | signed ΔU, **can go negative** |
| Sign changes | **structurally inexpressible** — a `min` over a non-negative recall cannot say "helped A, harmed B" | the headline measurement |
| Intervention | retention-budget comparison | **counterfactual removal** of a single memory |

**Required framing:** distinguish on **granularity and sign**, and cite EMBER when
introducing the multiple-future-tasks setting. Do not present that setting as new.

## 3. Open risks to the seam

| Risk | Status |
|---|---|
| **EvoMemEval** (OpenReview `n3GMbobXnc`) may already evaluate one memory against several distinct future tasks | 🔴 **UNRESOLVED — channel-dead, not absent.** The abstract's *"evaluated on held-out future tasks"* is ambiguous between one-item-many-tasks and pool-vs-pool, and asserts no per-memory statistic. Every PDF route 403s, **and the positive control (`DT7JyQC3MR`) 403s identically** — so the failure says nothing about this paper. **Resolved by one logged-in fetch of `openreview.net/pdf?id=n3GMbobXnc`.** Already off the table regardless: the counterfactual protocol, "predict memory utility before execution", and "retrieval similarity is not a reliable proxy for utility" |
| **EMBER** MultiQ — one memory, 5 future tasks | 🔴 **VERIFIED COLLISION** — see §2b. Cite it; distinguish on granularity and sign |
| MeClear (2609.09115) computes per-memory LOO + Shapley from real re-execution — but **within one query's context, never across queries** | to re-verify |
| MemGate posits a per-(memory, query) admissibility indicator but never materializes it | to re-verify |
| Multi-Factor Value Model (2606.12945): a [16,16] MLP **ties** a 4-feature linear scorer | ✅ confirmed verbatim (0.773 vs 0.770, +0.003 ± 0.013, 55% of splits). **But only four of seven factors are live, and "task utility" is one of the dead ones** — their own L5 concedes it. It does **not** pre-empt P1 |
| **MeClear asserts P1's phenomenon verbatim** | *"A stored record that degrades performance on a query can provide indispensable contextual grounding for subsequent tasks, rendering permanent database overwrites prone to catastrophic cross-task performance regression."* **Cite this as the assertion P1 converts into a number** |
| **Memory-R1 = arXiv:2508.19828** (ACL 2026 Long) | resolved; tasks per memory = 1. ⚠️ `http://export.arxiv.org` 301s and silently returns 0 results — **likely the prior audit's false-negative generator** |
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

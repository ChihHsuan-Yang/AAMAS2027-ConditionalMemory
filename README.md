# Memory Utility Is Not a Scalar

**Measuring Task-Conditional Value in Long-Term Agent Memory**

> **What is this memory useful for?**

Status: **measurement phase, no experiments run.** Initialized 2026-09-29.

---

## The question

Does a long-term memory have something like a stable intrinsic value, `Value(memory)` —
or is its causal downstream value fundamentally a function of the future task,
`Value(memory, task)`?

The same naturally occurring memory may help Task A, do nothing for Task B, and harm
Task C. If that is true and measurable above execution noise, then a single scalar memory
score is the wrong object.

The scientific object:

```text
DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)
```

measured by **actual downstream execution** — never by semantic similarity, never by an
LLM's judgment of importance.

## This is not a memory-gate paper

The 2026 literature converged on learned memory-write policies, and that framing is
anticipated — most directly by UMEM (arXiv:2602.10652). See
[`docs/LITERATURE_BOUNDARY.md`](docs/LITERATURE_BOUNDARY.md) for the binding
forbidden-claims list.

A learned predictor appears only if the measurement survives a kill criterion.

## Repository map

| Path | Contents |
|---|---|
| [`docs/PROJECT_GOAL.md`](docs/PROJECT_GOAL.md) | the question and the non-negotiable order of work |
| [`docs/MASTER_TODO.md`](docs/MASTER_TODO.md) | authoritative task state — owner, status, dependency, evidence |
| [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md) | Experiments 0/1/2, the analysis, the kill criterion |
| [`docs/LITERATURE_BOUNDARY.md`](docs/LITERATURE_BOUNDARY.md) | what may not be claimed, and why |
| [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) | decisions with their evidence and their falsifiers |
| [`docs/ALCF_RESOURCES.md`](docs/ALCF_RESOURCES.md) | endpoints, auth, and the rules binding every run |
| [`docs/RESULTS_LEDGER.md`](docs/RESULTS_LEDGER.md) | every number, its artifact, its date |
| `src/p1mem/` | package (empty — nothing built until the plan is reviewed) |
| `configs/` · `scripts/` · `tests/` | run configs, entry points, tests |
| `data/` · `results/` | not committed; see each README |

## Ground rules

1. **Order of work is fixed:** noise floor → counterfactual matrix → interaction test →
   sign flips → *only then* a predictor.
2. **A null is a result.** If the interaction is inside the noise floor, the project stops
   and says so. Do not build a system to rescue a null.
3. **Positive-control every null.** `WebSearch` is blocked in this environment; an empty
   result is a dead channel until proven otherwise.
4. **Every paper number lives in the results ledger first**, with its artifact path and
   measurement date.
5. **WITH and WITHOUT arms are identical** in model, decoding, scaffold, and verifier
   version. Any asymmetry is a confound.
6. **No secrets** in the repo, logs, or reports.

## Setup

Not yet specified — the dependency set follows the experiment design. See
`docs/MASTER_TODO.md` Phase 2.

---

## Current Project State

**Updated 2026-09-30.** Detail in [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md).

### Current scientific story

Past experience can be represented as memory in different ways. We ask **what future tasks
each memory is actually useful for**, when it is neutral or harmful, and **what it costs**
in storage, retrieval, exposure, latency and compute. The paper is about
**Memory × Task × Representation × Cost**; the object is `U(memory, future_task)`.

### Benchmarks

| | status |
|---|---|
| **LongMemEval-V2** | ✅ **primary, complete** — 1,889 memories, 1,157 evaluated cells, 5,198 calls, 0 errors |
| **SciCode** | 🟡 scoped, not built — memory = a reusable procedure; usable N ≈ 8–12 cross-problem pairs, so a case study |
| **BEAM** | ❌ **DROPPED for core P1** — **92.6% of cited turns are cited by exactly one question**, so it cannot supply the multi-task-per-memory axis. Also CC BY-SA 4.0 (ShareAlike would force a separate release) |
| **replacement** | 🟡 selection pending — prefer a coding/software benchmark with cross-episode transfer |

### Memory representations

| | status |
|---|---|
| **Raw / extractive** | ✅ at scale — 1,889 units, deterministic, **0 model calls** |
| **Summary** | 🟡 pilot (8 segments, compression 0.063) — **scale-up running** |
| **Structured** | 🟡 pilot (8 segments, compression 0.037, 0/8 malformed) — **scale-up running** |

### Strongest verified findings

1. **Screening the pairing makes the effect measurable** — both-arms-fail 0.7007 → **0.5252**; a stopping rule committed in code *before* the data passed.
2. **Where a memory bears on a task, it helps** — paired within-memory **+0.3349**, episode-clustered CI **[0.1974, 0.4736]**, p = 5×10⁻⁵, on the same 60 memories.
3. **Bearing is scarce** — a memory bears on a **median of one** future task out of hundreds.
4. **The founding hypothesis is not supported** — **0 sign flips / 35** bearing memories (bound ≤9.9%); flips concentrate in the unscreened stratum (**17/60**); the excess over the additive null is **negative in every stratum**.
5. **Similarity is a poor proxy for utility** — Spearman **+0.087** overall, **+0.006** unscreened.

### Failed / dropped

BEAM (diagonality) · the semantic-type axis (κ = 0.000) · the variance decomposition
(unidentifiable: `F_exec = 0` leaves no residual scale) · unscreened pairing (~80%
both-arms-fail) · the official-prompt "fix" (**lowered** accuracy 5.7 pts — abstentions
score as wrong).

### Figures · dataset · manuscript

Figures: 2 tables in; **0 figures** — pipeline + audit in progress.
HF `AgentsSci/AAMAS2027-ConditionalMemory`: **empty**, v0.1 in progress.
Overleaf `964bbcb` — 8 pages, 0 undefined citations, anonymity verified.

### Verification

`scripts/audit_claims.py` re-derives **38 headline claims** from tracked artifacts and is
**proven able to fail**. 416 tests pass. **17 instrument defects** found on the first
execution day, **none reaching a reported number** — see
[`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md).

### Handoff

Read [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) →
[`docs/THE_HONEST_HEADLINE.md`](docs/THE_HONEST_HEADLINE.md) →
[`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md). Then run `audit_claims.py` before
touching the manuscript. **Never quote a number you have not re-derived.**

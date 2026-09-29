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

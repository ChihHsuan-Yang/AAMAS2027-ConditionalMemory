# P1 — Project Goal

**Working title:** *Memory Utility Is Not a Scalar: Measuring Task-Conditional Value in Long-Term Agent Memory*

Status: **measurement phase. No experiments run yet.** (initialized 2026-09-29)

---

## The question

> **What is this memory useful for?**

Not "is this memory good?" — that presupposes the answer is a scalar.

## The scientific object

For a memory `m` written during a past episode, and a **later, different** future task `t`:

```text
DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)
```

measured by **actual downstream execution**. Never by semantic similarity. Never by an
LLM's judgment of importance.

The hypothesis under test:

> The downstream causal utility of a long-term memory contains a meaningful
> **memory x future-task interaction** that cannot be explained by one global
> memory-value scalar or by execution noise.

This is a hypothesis. It is not an assumed conclusion. See `docs/EXPERIMENT_PLAN.md`
for the kill criterion that would end the project.

## What is NOT the contribution

This project is **not** a memory gate. The 2026 literature converged hard on learned
memory-write policies; that framing is anticipated. See `docs/LITERATURE_BOUNDARY.md`
for the forbidden-claims list, which is binding on every document in this repo and on
the manuscript.

A learned predictor appears only in a late stage, and only if the measurement survives.
Its purpose is to test whether measured structure is *exploitable*, not to claim a small
MLP is novel.

## Non-negotiable scientific order

1. Establish the execution / seed noise floor.
2. Construct memory x future-task counterfactual measurements.
3. Determine whether the memory x task interaction is real.
4. Measure natural sign flips.
5. **Only if the phenomenon is meaningful**, train a predictor.

Do not start at step 5. A fast, honest falsification is a successful outcome.

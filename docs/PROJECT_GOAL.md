# P1 — Project Goal (FROZEN 2026-09-29)

**Working title:** *What Is This Memory Useful For? Conditional Evaluation of Long-Term
Agent Memory*

**Target:** AAMAS 2027 main track. Abstract 1 Oct 2026 AoE, paper 8 Oct 2026 AoE.

> ## This story is FROZEN.
> New literature may change novelty wording, citations, baselines, or added experiments.
> It does **not** change what this project studies. Only evidence that the entire planned
> experiment has already been executed — same memory-acquisition comparison, same
> cross-benchmark conditional utility, same harmfulness/reliability, same efficiency
> framework, same derived dataset — may reopen the framing.

---

## The question

> **What is this memory useful for?**

Past agent experience can be stored in different forms. A memory is valuable only insofar
as it changes future behavior. So we evaluate: which future tasks a memory helps, which it
leaves unaffected, which it harms, how stable those effects are, and what storage,
retrieval, context, latency, and compute that benefit costs.

## The object

```text
U(memory, future_task)
```

measured behaviorally through actual downstream execution:

```text
DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)
```

This project is **conditional memory evaluation**. It is **not** a vector database, not a
learned gate, not a RAG system, not a pure variance paper, and not a claim to have
discovered task-conditioned memory.

## Four contributions

### A — Conditional memory measurement
Evaluate the same past experience across multiple future tasks. Characterize each memory
as broadly useful, task-specific, neutral, conditionally harmful, or sign-flipping.
**Do not reduce a memory to one global importance score.**

### B — Memory representation comparison
The same source experience stored three ways: **Raw/Extractive**, **Abstractive Summary**,
**Structured Experience**. This measures how memory *formation* affects downstream utility
and harm.

### C — Utility + efficiency evaluation
Not only accuracy. Storage, retrieval, exposure, latency, API/compute, selectivity, and
extraction efficiency — combining into a **Memory Utility–Efficiency Frontier**.

### D — Reusable dataset + harness
A **Conditional Memory Utility Dataset** capturing
`memory × future task × representation × replicate × utility × cost`, designed so P3 can
add `receiver / receiver subset` without redesign.

## Benchmarks — frozen initial set

| # | Benchmark | Role |
|---|---|---|
| 1 | **LongMemEval-V2** | primary long-term agent-memory benchmark; highest priority |
| 2 | **BEAM** | multi-domain / memory-ability generalization |
| 3 | **SciCode** | scientific & procedural memory |

No additional benchmarks until these are substantially complete.

## Hard invariants

1. **The memory writer never sees the future evaluation task.** Memory formation depends
   only on past experience. This is the leakage guarantee the whole design rests on.
2. **WITH and WITHOUT arms are identical** in model, cluster, serving config, decoding,
   scaffold, context budget, and scoring. Any asymmetry is a confound.
3. **Cluster is part of the experimental unit.** Never merge generations from different
   clusters into one condition because the model names look alike.
4. **Replication before interpretation.** A single-shot utility label cannot distinguish a
   real effect from execution noise. Sign flips must clear a measured floor.
5. **Continuous rewards are retained.** Do not collapse to binary early.
6. **Every paper number traces** to an artifact, script, config, and model manifest.

## What would stop the project

If the conditional structure is entirely inside the noise floor — no robust sign flips, no
interaction beyond execution variance, a single scalar explaining nearly everything — that
is a reportable result, and the paper reports it plainly rather than building a system to
rescue it.

**Note:** this is now a weaker stopping condition than in the original plan, because
Contributions B, C, and D do not depend on A finding a positive result. A null on A still
leaves a representation comparison, an efficiency frontier, and a dataset.

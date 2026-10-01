# Scope freeze — 2026-10-01

**The scientific scope of P1 is FROZEN.** This document is the authority on what
is in and what is out. An agent that wants to add an experiment must find its
justification in §3 or not run it.

## 1. The frozen question and axes

> **What is this memory useful for?**

**Task × Representation × Benchmark × Cost × Reader Generalization.**

The current evidence is sufficient for a substantial paper. From here the
priorities are **completion, verification, manuscript quality, release quality
and reproducibility** — not new findings.

## 2. The seven results the paper is written around

| | result | status |
|---|---|---|
| **A** | **Conditional / sparse utility** — usefulness concentrates on the small subset of future tasks the experience actually bears on | established |
| **B** | **Similarity is not utility** — generic semantic similarity is a weak proxy for downstream utility | established |
| **C** | **Representation matters** — on LongMemEval-V2 Raw preserves the strongest utility; Summary/Structured lose much of it. 🔴 **Do not universalize this ordering** to benchmarks where the contrasts are not established | established on LongMemEval only |
| **D** | **Cost accounting matters** — shorter exposed memory is not automatically cheaper once formation cost is charged | established |
| **E** | **Reader generalization** — the Raw effect survives gpt-oss → Gemma under a **session-matched** design: **+0.0982 [+0.0247, +0.1730]**, n=550 | established, session-matched |
| **F** | **No same-family writer–reader advantage** detectable — all four factorial contrasts span zero | informative null |
| **G** | **Cross-benchmark heterogeneity** — LongMemEval's Raw-dominant ordering is **not established** across SciCode / SWE-bench | established as a limit |

## 3. What may still be run

Only work that:

1. completes already-approved benchmark coverage,
2. validates an existing claim,
3. repairs an invalid run, or
4. closes a **validity-critical** gap found by the final audit.

## 4. What is closed — DEFERRED, not killed

Additional benchmarks · Jev baseline · learned memory gate · RL memory manager ·
new retrieval architectures · semantic-type redesign · new representation
families · **any model backbone beyond gpt-oss-120b and gemma-4-31B-it**.

These are good ideas. They belong in `POST-SUBMISSION / FUTURE WORK` in
`MASTER_TODO.md`, and they are not reasons to delay submission.

## 5. Storylines that are not to be resurrected

The **sign-flip headline**, the **variance-decomposition headline**, the
**semantic-type taxonomy**, **harmful-memory prevalence**, a **retention
policy**, a **learned gate**. Each was demoted for a measured reason recorded
in `docs/`; demotion is not an oversight to be corrected by a later agent.

🔴 **Do not reframe the paper again** unless the final audit surfaces a
contradiction.

## 6. Model scope, frozen

| role | approved |
|---|---|
| reader | `gpt-oss-120b`, `gemma-4-31B-it` |
| writer | gpt-oss; Gemma **only** where already generated for the factorial |

**The session-matched Raw reader-transfer value is canonical.** The superseded
cross-session estimate (+0.1268) stays visible in the documentation as history
— retraction is labelling, not deletion — but never leads.

## 7. Benchmark completion rule

- **LongMemEval-V2** — the **screened design** is 100% complete. The 15,112-pair
  frozen pairing universe is a **different universe**; never claim all 15,112
  cells were executed.
- **SciCode** — the eligible transfer pool is complete. The limitation stands:
  historical Summary/Structured memory **text** was not persisted and must not
  be fabricated. Their reward measurements remain valid.
- **SWE-bench** — finish every remaining valid cell under the frozen eligible
  universe; mark the rest excluded **with reasons**. 🔴 **Do not redefine
  "eligible" after seeing outcomes.**

## 8. Figure policy

Evidence-driven. If space forces a choice, **prefer empirical-result figures
over explanatory diagrams**. Do not keep a figure because effort went into it.

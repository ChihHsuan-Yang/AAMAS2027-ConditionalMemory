# Defect Register — 2026-09-29

Every instrument defect found on the project's first execution day, with who found it and
what it would have cost. **Kept because the pattern matters more than any single entry:
each one produced a plausible-looking number.**

Nothing here is a process complaint. It is the evidence base for the paper's methods
section and for the claim that the measurement is trustworthy.

---

## Defects that reached a reported number before being caught

| # | Defect | Reported as | Caught by | Would have cost |
|---|---|---|---|---|
| 1 | Replicates were not byte-identical — position seeded by `replicate_id` | "endpoint is nondeterministic, 4.3%" | Sub-agent G | a fabricated execution-noise floor |
| 2 | `judge_floor` grouped byte-identical text **without the task** | "F_judge = 0.1486" | Sub-agent H | a fabricated judge floor; 18/18 groups spanned tasks |
| 3 | `ZeroDivisionError` crashed the decomposition **while the script exited 0**; caller read an empty dict through `.get(c, 0.0)` | "variance shares all 0.0000" | Sub-agent H | **a null reported as measured** |
| 4 | `leakage_flag` is not discriminative — fires on unpaired memories at ratio **0.995** | "the bottleneck is reader capability" | Sub-agent J | **the wrong scientific conclusion**, and a benchmark change |
| 5 | Embedding cap bisected on prose 2× sparser than real data | "working cap 3,400 tokens" | Sub-agent G | 10/10 embedding failures at run time |

## Defects caught before they reached a number

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 6 | `select_filler` re-randomized on exclusion (25/25 non-drawn exclusions changed the draw) | Sub-agent G | corrupted `F_empty`: the WITHOUT arm would differ between memories |
| 7 | WITHOUT arm servable from cache across memories | Master (pre-registered as A1.4) | `F_empty = 0` ⇒ **every ΔU trivially "significant"** |
| 8 | Sign flips occur at 53–92% with **zero** interaction | Sub-agent D | **the headline claim**: a flip rate reported as evidence of conditionality |
| 9 | REML not identified — shares equal to 16 s.f. at the clip ceiling, `converged=True` | Sub-agent H | a fabricated variance decomposition |
| 10 | Truncation scored as a wrong answer (`reasoning_tokens` eats `max_tokens`) | Sub-agent C | ΔU pushed negative ⇒ **manufactured harmful memories** |
| 11 | HF `auth-check` returns 200 for repos we cannot write | Sub-agent E | a failed upload believed pre-verified |
| 12 | `reader_model` in the condition key defeated the cluster-homogeneity check | Sub-agent E | silent pooling of two clusters |
| 13 | Cache-lock test vacuous (distinct keys never exercised check-then-act) | Sub-agent C, by mutation testing | an unprotected race believed tested |
| 14 | Concurrency ladder measured one wave at the top level | Sub-agent C | a wrong throughput ceiling |
| 15 | Python 3.9 aborts pytest collection on a vendored file | Master | **a healthy suite looking broken** |

## The pattern

**Eleven of these produced a plausible number.** None announced itself as an error. The
recurring shape, in one line:

> A check that inspects the wrong subject reports confidently.

Sub-shapes, each seen more than once today:
- **an absent value defaulting to a plausible one** (#3, #11, and a near-miss in J's own
  verification script);
- **a null with no positive control** (#4, #6, and my own leakage-denominator error);
- **a measurement made on unrepresentative material** (#5, #14);
- **a crash inside a pipeline whose exit code stayed 0** (#3).

## What actually caught them

Not review-by-reading. In every case: **re-running the measurement against a control that
should behave differently.**

- mismatch control on an unpaired memory (#4)
- planted defect that the estimator must flag (#2, #3)
- mutation testing (#13)
- comparison against a no-exclusion baseline rather than between two exclusions (#6)
- exercising the same probe on real data rather than synthetic (#5)
- a positive control on a known-good case (#15)

## Three of these were mine

Defects #1, #4, #5 were in code or reasoning I authored, and #3 I reported to the user as a
measured result. Each was found by an agent I had asked to check my work. That is the
argument for the cross-checking discipline, and the reason none of them is in the paper.

# Coverage manifest — the authoritative definition of "full benchmark coverage"

**Written 2026-09-30.** Supersedes any coverage number stated elsewhere. Every
figure here was re-derived from the benchmark or the executed artifacts; where
a number is quoted from a sub-agent it was independently re-checked, and where
my re-check disagreed the disagreement is recorded rather than smoothed.

## What "run everything" means

> **Attempt 100% of the items that are scientifically eligible under the frozen
> protocol.**

It does **not** mean forcing invalid, leaked, unsourceable, unscorable, or
licence-prohibited cells into the experiment. Exclusions are legitimate — but
every one must be **explicit, counted, and non-outcome-based**. No convenience
subsampling. No silently leaving difficult items unrun. No inclusion rule that
depends on an observed ΔU.

For each benchmark the identity

```
eligible universe = executed + remaining + excluded(with reasons)
```

must sum **exactly**. Where it does, it is shown. Where a definitional choice
changes the universe, both numbers are given rather than one being picked.

---

## 1. LongMemEval-V2

| quantity | value | basis |
|---|---:|---|
| questions total | **451** | `questions.jsonl`, 451 distinct ids, 0 duplicates |
| deterministically scored | **295** | re-derived from the adapter's scorer assignment |
| LLM-judged | **156** | `llm_abstention_checker` 128 + `llm_gotchas_checker` 28 |
| memory units (page visits) | **1,889** | enterprise 1,024 + web 865 |
| answerable deterministic questions | **278 / 295** (94.2%) | 17 have no carrying unit |

### Two different universes, and which one governs

This is the subtlety that makes a single "coverage %" misleading.

**Universe A — the frozen pairing rule** (`select_pairs`, seed 20261008,
`tasks_per_memory=8`): **15,112** pairs = 1,889 × 8 exactly.

| | cells |
|---|---:|
| eligible | **15,112** |
| executed | 574 |
| remaining | **14,538** |
| *sum check* | 574 + 14,538 = 15,112 ✅ |

**Universe B — the screened design, which is what the paper reports**:
**1,157** cells (BEARING 139 + MATCHED_CONTROL 146 + RANDOM 872).

| | cells |
|---|---:|
| eligible | **1,157** |
| executed | **1,157 (100%)** |
| remaining | 0 |

🔴 **B is not a subset of A.** B ∩ A = 102; B \ A = 1,055. The screened design
is a **re-pairing** under the content screen, not a sample drawn from A. Quoting
"100% coverage" without naming the universe would be false against A, and
quoting "3.8% coverage" would be false against the design the paper actually
reports. **Both numbers are true of different objects and neither alone is
honest.**

**Representation sub-universe** (BEARING + MATCHED_CONTROL = 285 cells × 3
representations = **855**): 847 executed, **8 excluded** (structured write
failures — 277 structured vs 285 raw/summary).

### Exclusion ledger

| reason | count | kind |
|---|---:|---|
| not yet attempted in Universe A | 14,538 | **not-yet-attempted** |
| no carrying memory unit (deterministic) | 17 | protocol |
| structured write failure | 8 | harness |
| LLM-judged questions | 156 | **scorer regime — see below** |

### The 156 LLM-judged questions

They are **not** excluded on grounds of difficulty or outcome. They are excluded
because `F_judge` — scorer disagreement on byte-identical outputs — is 0 for the
deterministic scorers and **unmeasured** for the LLM judge. Including them in
the same stratum would mix a zero-noise scorer with one whose noise has never
been quantified on this data.

They are **eligible for a separate scorer stratum**, kept visibly apart, never
pooled. Executing them requires measuring `F_judge` first by re-scoring stored
byte-identical outputs. **Status: eligible, not excluded, not yet run.**

---

## 2. SciCode — the "whole pool" claim, verified and qualified

| quantity | value |
|---|---:|
| dev / test problems | 15 / 65 |
| memory units / future tasks | 50 / 64 |
| candidate pairs — **lexical** (shipped) | **163** |
| candidate pairs — dependency | 12 |
| candidate pairs — unrestricted | 3,200 |
| **eligible (lexical, ≥2 tasks/memory)** | **154** |
| executed | **154 (100%)** |
| remaining | **0** |
| excluded | 3,046 |
| *sum check* | 154 + 0 + 3,046 = 3,200 ✅ |

**The "154 = the whole pool" claim is TRUE — but only under `relatedness=lexical`.**
Three qualifications, each of which a reader could otherwise mistake:

1. **9 pairs are lost** to the `min_tasks_per_memory=2` rule (9 single-task
   memories). That rule is protocol, not outcome — a memory meeting one task
   cannot speak to the multi-task axis this project exists to measure.
2. **7 of the 12 dependency-relatedness pairs are never admitted by lexical.**
   A `dep OR lex` union would yield **164** eligible pairs, +10 over the shipped
   154. That union is **not implemented**, so those 10 pairs are an *unexecuted
   eligible set under a different defensible relatedness definition* — recorded
   here rather than quietly absent.
3. The similarity threshold is a rounded `0.0315`; the exact p95 is
   `0.03153035`, which would yield **151** rather than 154. The shipped rounding
   is *more* inclusive, so it cannot have excluded anything on an outcome.

**🔴 A design property does not survive to the analysis set.** The design is
0.0% diagonal (no memory paired with exactly one task, all 154 pairs). On the
**matched 122-cell** analysis set it is **15.2%** — 5 of 33 memories fall to a
single task because harness errors drop tasks unevenly. *I re-derived this
myself: 0/34 solo at design, 5/33 solo on the matched set.* The paper's
diagonality claim is a statement about the **design**, and must not be
transferred to the analysis set.

Also: **1 replicate per cell** (LongMemEval has ≥2, satisfying prereg A1.3).
**106 of 924 arm-runs have reward None** — correctly never 0.0.

**Verdict: SciCode full coverage DONE under the frozen lexical definition**,
with the +10 union pairs recorded as a known, unexecuted alternative.

---

## 3. SWE-bench Verified — the largest remaining gap

| stage | pairs | note |
|---|---:|---|
| parquet rows / manifest pairs | 500 / **406** | 133 donors, 176 recipients, **8 repos** |
| FILE candidates (excl. copyleft) | 642 | |
| eligible after `min_tasks≥2`, uncapped | **552** | |
| after `tasks_per_memory=4` cap | **406** | 🔴 the cap is **LIVE, not inert** — it removes 146 |
| survive `is_single_file_solvable` | **303** | −103, all multi-file gold fixes |
| in a repo with a working runner | **239** | django 227 + sympy 12 |
| after dedup-by-recipient = **runnable universe** | **107** | django 96 + sympy 11 |
| **executed (all runs, all django)** | **55** | |
| representation arm v2 | 32 recipients / 96 cells / 13 matched | |
| **remaining runnable today** | **52** | django 41, **sympy 11** |

### Per-repository coverage

| repo | SFS pairs | runner | executed | status |
|---|---:|---|---:|---|
| django/django | 227 | ✅ | 55 | partial |
| sympy/sympy | 12 | ✅ | **0** | **runnable, never attempted** |
| sphinx-doc/sphinx | 37 | ❌ | 0 | no runner |
| matplotlib | 10 | ❌ | 0 | blocked: C build, no Docker on arm64 |
| xarray | 9 | ❌ | 0 | no runner |
| requests | 4 | ❌ | 0 | no runner |
| astropy | 2 | ❌ | 0 | blocked: C build |
| pytest-dev/pytest | 2 | ❌ | 0 | no runner |

**🔴 Two findings that change the scale-up plan:**

1. **`tasks_per_memory=4` is binding**, removing 146 eligible pairs. On SciCode
   the equivalent knob was made inert deliberately. Here it silently caps the
   universe, and the manifest it produced has been treated as *the* pair list.
2. **sympy has a working runner and a passing scorer control (20/20, negative
   control 20/20) and has never been run.** The django-only result is not a
   constraint of the harness — 11 sympy pairs are runnable **today**. This is
   the single highest-value fix for the "django-heavy" criticism.

64 SFS pairs sit in 6 repos with no runner; 12 of those are blocked by C
extension builds (no Docker on arm64) and are a genuine environment limit, not
an oversight.

**Other properties:** localizer recall 58.2% (floor pilot) / 65.6% (reps run) —
the dominant source of cell loss. 1 replicate per cell. **No F_exec exists for
SWE-bench**: the WITHOUT arm is shared byte-identically across all three
representations (32/32), so there is no A/A control — a 0 would be an artefact
of the design, not a measurement.

---

## 4. Summary — are the three benchmarks comparably covered?

**No, and the manifest exists to stop that being glossed.**

| benchmark | governing universe | executed | coverage | honest one-line reading |
|---|---:|---:|---:|---|
| LongMemEval-V2 | 1,157 (screened design) | 1,157 | **100%** | complete **on the design the paper reports**; 3.8% of the 15,112-pair frozen universe |
| SciCode | 154 (lexical) | 154 | **100%** | complete under the shipped relatedness; +10 pairs exist under a union definition |
| SWE-bench Verified | 107 (runnable) | 55 | **51%** | and **all 55 are django**; 11 sympy pairs runnable and unattempted |

## 5. Immediate consequences for the campaign

1. **Run sympy now** — 11 pairs, runner and scorer control already passing. It
   is the cheapest possible answer to "django-only".
2. **Decide whether `tasks_per_memory=4` stays.** It is a live cap on the
   SWE-bench universe; making it inert (as SciCode's was) raises the eligible
   pool from 406 to 552 and the runnable pool correspondingly.
3. **LongMemEval's two universes must be named every time a coverage % is
   quoted.** A bare percentage is false against one of them.
4. **The 156 LLM-judged questions need `F_judge` measured** before they can
   form a separate stratum.
5. **SciCode is DONE.** Do not re-run its cells.

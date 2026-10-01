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

### 🔴 EXECUTION coverage is 462 cells; EXPORTABLE coverage is 154 (added 2026-09-30)

All 462 cells (154 pairs x 3 representations) were executed and scored. Only the
**154 `raw`** cells can be published, and the distinction must be named every time
a SciCode coverage figure is quoted — it is the same two-universes trap as
LongMemEval's above.

| | cells |
|---|---:|
| executed and scored | **462** |
| exportable (memory text exists and is verified) | **154** (`raw`) |
| **not exportable** | **308** (`summary` 154 + `structured` 154) |

The run never persisted the model-written memory text, and it is **not
recoverable**. That is a measurement, not an assumption:

* regeneration vs. the server's recorded `prompt_tokens` matches **154/154** for
  `raw` (no model call: raw IS the segment), **5/154** summary, **0/154** structured;
* against ground truth on disk (`results/repr_scaleup/memories.jsonl`, 60 Summary
  memories written by the same writers and model **with their text**), regeneration
  reproduces **0 of 12** byte-identically while the writer prompt matches **12/12**;
* the 5 summary matches sit at the measured coincidence null (~5-8%), i.e. chance.

The rewards for those 308 cells are real and are kept in
`results/scicode/scaleup_all3.json`; what cannot be shown is the memory whose
utility they measure. Evidence: `results/scicode/memory_recovery_report.json`.

**Consequence: SciCode is NOT representation-matched in the release**, while
LongMemEval is. Any cross-benchmark representation comparison must say so.

---

## 3. SWE-bench Verified — COMPLETE under the frozen protocol (2026-10-01)

**Every runnable cell in the frozen universe has now been attempted.**
`remaining = 0` in both repositories. Re-derived this session from the
manifest, the parquet and the executed artifacts; nothing below is quoted
from an earlier document.

### The pair funnel — it closes exactly, per repo

| repo | pairs | −multi-file gold fix | −no runner | −dedup-by-recipient | **runnable** |
|---|---:|---:|---:|---:|---:|
| django/django | 303 | 76 | 0 | 131 | **96** |
| sympy/sympy | 13 | 1 | 0 | 1 | **11** |
| sphinx-doc/sphinx | 48 | 11 | 37 | 0 | 0 |
| pydata/xarray | 22 | 13 | 9 | 0 | 0 |
| matplotlib/matplotlib | 10 | 0 | 10 | 0 | 0 |
| psf/requests | 4 | 0 | 4 | 0 | 0 |
| pytest-dev/pytest | 4 | 2 | 2 | 0 | 0 |
| astropy/astropy | 2 | 0 | 2 | 0 | 0 |
| **TOTAL** | **406** | **103** | **64** | **132** | **107** |

`406 − 103 − 64 − 132 = 107` ✅ (and each row closes individually).

### The coverage identity — `eligible = valid completed + excluded`

Generated by `scripts/swebench_coverage_table.py`
→ `results/swebench/coverage_table_final.json`.

| repo | eligible | attempted | **valid completed** | excluded | sums? |
|---|---:|---:|---:|---:|:--:|
| django/django | 96 | **96 (100%)** | **34** | 62 | ✅ |
| sympy/sympy | 11 | **11 (100%)** | **3** | 8 | ✅ |
| **TOTAL** | **107** | **107 (100%)** | **37** | **70** | ✅ |

### Exclusion ledger, classified

| reason | django | sympy | total | kind |
|---|---:|---:|---:|---|
| localizer miss | 33 | 6 | **39** | retrieval — the region the gold patch edits was never shown |
| unapplicable edit (`reward: None`) | 20 | 0 | **20** | harness — 🔴 never scored 0.0 |
| scorer invalidity | 9 | 1 | **10** | instrument — no verdict printed, or the scorer is not known to discriminate there |
| memory contagion-dirty | 0 | 1 | **1** | protocol |
| **not yet attempted** | **0** | **0** | **0** | — |
| runner absence / licensing | 0 | 0 | 0 | (removed before the runnable universe; see the funnel) |

**`valid completed` is the matched set**: a recipient counts only if it is
interpretable under **all three** representations. It is therefore *stricter*
than the per-representation denominators, by design.

### 🔴 The scorer does not discriminate on every django instance

This is new and it is the session's most consequential finding. The shipped
control covered **12** django instances; extending it to **all 96**
(`results/swebench/scorer_control_django_ext.json`, no model calls) gives:

| repo | instances where gold→1.0 **and** base→0.0 | share |
|---|---|---:|
| django/django | **73 / 96** | 76.0% |
| sympy/sympy | **11 / 11** | 100% |

On the other **23 django instances** a model scoring 0.0 cannot be read as
"the fix was wrong" — the instrument does not separate the two states there.
All 12 shipped control instances **reproduced exactly** (gold/base identical),
so this is added resolution, not a contradiction. **The frozen gate is
unchanged and still reads 20/20**; the extended artifact is a finer
*per-instance* diagnostic and is deliberately **not** wired in as a gate.

Reassuringly, all 34 django cells that reach a reported number sit on
scorer-valid instances, and every contrast is unchanged whether the extra 3
are kept or dropped (pooled 40 → 37).

### 🔴 Six negative controls were themselves manufactured zeros

Re-running the negative control under the **fixed** scorer flips **6 of 20**
shipped instances from `corrupt→0.0` to `corrupt→None`: the corrupted gold
produced **no test verdict**, and the old artifact had recorded that as "the
corruption was detected". The negative control was partly passing *on the very
defect it exists to catch*. Under the fixed scorer the honest counts are
django **38/73** and sympy **6/11** corruptions provably detected; **zero**
corruptions scored 1.0 in either repo, which is the direction that would have
indicated a blind scorer.

### sympy's own scorer control now covers all 11 recipients

`sympy__sympy-16766`, `-21612` and `-22914` — previously scored by a runner
never controlled on them — were controlled this session and **all three pass**
(gold 1.0, base 0.0). The gap flagged in `SWEBENCH_MULTIREPO.md` §1 is closed.

### What coverage does NOT buy

**There is still no `F_exec` for SWE-bench.** The WITHOUT arm is byte-identical
across the three representations (verified **96/96** django and **11/11**
sympy tasks, one prompt sha each), so the design has no A/A replicate and an
execution-noise floor of 0 would be an artefact. Running every eligible cell
does not create a replicate that the design never had.

---

## 4. Summary — are the three benchmarks comparably covered?

**No, and the manifest exists to stop that being glossed.**

| benchmark | governing universe | executed | coverage | honest one-line reading |
|---|---:|---:|---:|---|
| LongMemEval-V2 | 1,157 (screened design) | 1,157 | **100%** | complete **on the design the paper reports**; 3.8% of the 15,112-pair frozen universe |
| SciCode | 154 (lexical) | 154 | **100%** | complete under the shipped relatedness; +10 pairs exist under a union definition |
| SWE-bench Verified | 107 (runnable) | **107** | **100%** | **two repos** (django 96, sympy 11), all attempted; **37** reach a reported number — 39 localizer misses, 20 unapplicable edits, 10 scorer-invalid, 1 contagion-dirty |

## 5. Immediate consequences for the campaign

1. ~~**Run sympy now**~~ — **DONE 2026-09-30.** 11/11 cells.
   ~~**Run the remaining django cells**~~ — **DONE 2026-10-01.** 64 further
   recipients in two chunks of 32; **SWE-bench is now 107/107 attempted.**
2. **Decide whether `tasks_per_memory=4` stays.** It is a live cap on the
   SWE-bench universe; making it inert raises the pair pool 406 → 552 but the
   **runnable** pool only 107 → 117 (**+10, not +146**), and dedup-by-recipient
   would silently **re-pair 13 already-executed django cells** into different
   cells under the same `task_id`. Not applied. A subset at one stage becomes
   a re-pairing at the next.
   🔴 **2b. The django scorer discriminates on only 73 of 96 instances.** That
   now bounds SWE-bench harder than the cap does: raising the universe adds
   cells the instrument may not be able to read. Extend
   `swebench_scorer_control.py` to any new instance **before** running it.
3. **LongMemEval's two universes must be named every time a coverage % is
   quoted.** A bare percentage is false against one of them.
4. **The 156 LLM-judged questions need `F_judge` measured** before they can
   form a separate stratum.
5. **SciCode is DONE.** Do not re-run its cells.

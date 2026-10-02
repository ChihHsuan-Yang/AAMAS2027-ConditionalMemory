# What Is This Memory Useful For?

### Measuring Task-Conditioned Utility in Long-Term Agent Memory

**AAMAS 2027 submission.** Scientific scope is **FROZEN**
([`docs/SCOPE_FREEZE.md`](docs/SCOPE_FREEZE.md)). 30,159 real endpoint calls across
three benchmarks and two reader backbones, **0 unrecoverable losses** — counted, not
estimated ([`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md)).

---

# ▶ START HERE

**You need nothing but this page.** No Overleaf URL, no local path, no dataset name, no
internal document name is assumed.

## 1 · What the paper says — three stories, and only three

| | story | status |
|---|---|---|
| **1** | **Memory utility is sparse and task-conditioned.** A memory is strongly useful for the few future tasks it bears on and inert for most others, so one global score per memory discards the structure a policy needs | established |
| **2** | **Representation and cost materially change measured utility.** The same experience written as Raw / Summary / Structured is not behaviourally equivalent, and compression's apparent efficiency changes once you charge it for writing itself | established on LongMemEval-V2; **a length control is in flight** |
| **3** | **The main Raw effect survives a change of reader.** Byte-identical memories, a second backbone, session-matched: the effect persists | established |

Everything else in the paper — similarity, screening, sign reversal, the cross-benchmark
boundary, the writer×reader factorial, the dataset — **supports, bounds or validates
these three**. None is a fourth story.

🔴 **The founding hypothesis was NOT supported.** The project set out to find
task-conditional *harm* (the same memory helping one task and hurting another) and did
not find it; the sparsity result replaced it. That negative is reported in the paper's
own introduction, and [`docs/THE_HONEST_HEADLINE.md`](docs/THE_HONEST_HEADLINE.md)
records it.

## 2 · Where the paper lives

| | |
|---|---|
| 📦 **canonical paper package** | **[`paper/`](paper/)** — self-contained; `latexmk -pdf main.tex` **twice** (bibtex needs the second pass). Verified to build standalone and render byte-identically to the Overleaf copy |
| ✍️ **Overleaf project** (the target remote, unchanged) | `git.overleaf.com/6abbde4a9eb777031afef068` |
| 💾 **local Overleaf clone** | `../overleaf` (sibling of this repo), commit **`a320c74`** |
| 🔴 **status** | **Overleaf git access is temporarily unavailable** (account/Premium; `push` *and* `fetch` both fail, so it is the remote, not a credential). The local clone is **1 commit ahead** of the server. **Nothing is lost.** See [Paper / Overleaf status](#paper--overleaf-status) |

⚠️ **On recovery, push the local clone — do not re-apply edits by hand.** The content is
already there.

## 3 · Where the data live

🤗 **`AgentsSci/AAMAS2027-ConditionalMemory`** —
<https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory> · **private** ·
5,924 rows · tags `v0.1-lmev2-derived` → **`v0.4-swebench-metrics`** (current)

| benchmark | rows | what is actually in them |
|---|---:|---|
| **LongMemEval-V2** | 5,643 | ✅ **complete** — memory text, task text, both arm outputs, rewards, costs, provenance. 2 rows carry an endpoint error with null rewards (never 0.0) |
| **SciCode** | 154 | ⚠️ **`raw` only, 154 of 462 cells.** Memory text is present; **both output fields are `__OUTPUT_NOT_RETAINED__`**. The 308 Summary/Structured cells are **absent — their text was never persisted and is *not recoverable***. A **persistence** gap, not a licence one. Rewards remain valid |
| **SWE-bench Verified** | 127 | ⚠️ **metrics and ids only.** Every text field is `__WITHHELD_SEE_LICENSE__` and declared in `text_fields_withheld`, because the corpus **declares no licence**. A **licence** withholding — not the same fact as SciCode's |

The two sentinels are never swapped. Full per-field detail:
[`docs/TRACE_AVAILABILITY.md`](docs/TRACE_AVAILABILITY.md).

## 4 · Where every number comes from

| map | what it answers |
|---|---|
| [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md) | **paper → artifact.** Every figure and table with its generator, canonical input, GitHub path, HF subset and **unit**; memory construction per benchmark; eligibility/validity rules and what is **never** scored as reward zero |
| [`docs/TRACE_AVAILABILITY.md`](docs/TRACE_AVAILABILITY.md) | **can it be reproduced and audited?** Per result: source episode, each memory text, both arm outputs, reward, scorer, endpoint and replicate metadata — HF / GitHub / local-only / **unavailable forever**. Gaps recorded, not softened |
| [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) · [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md) | every headline result, one row each · figure decisions and the generator contract |
| [`docs/DATASET_INDEX.md`](docs/DATASET_INDEX.md) · [`docs/COVERAGE_MANIFEST.md`](docs/COVERAGE_MANIFEST.md) | one row per HF snapshot with its limitations · the authoritative definition of "full coverage" per benchmark, with the universe **named** |
| [`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md) | **30+ instrument defects found and fixed.** Read before trusting any check — several were checks that passed while measuring the wrong thing |

## 5 · How to reproduce the paper

```bash
python3 scripts/make_figures.py    # regenerates EVERY number -> paper/figdata.tex; fails if an artifact stops supporting a caption
python3 scripts/audit_claims.py    # 224 checks re-derived from tracked artifacts
python3 -m pytest -q               # 638 tests
cd paper && latexmk -pdf main.tex  # twice
```

No number in the manuscript is hand-typed where a generator can emit it. Interpreter and
environment: [`docs/DEV_ENVIRONMENT.md`](docs/DEV_ENVIRONMENT.md).

## 6 · Where to continue the work

👉 **[`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md)** — current state, exact paths,
running jobs, restart commands, known-invalid runs, next actions.

**Remaining scientific TODOs: 3** — finish the pre-registered length control
([`docs/LENGTH_CONTROL_PRECOMMITMENT.md`](docs/LENGTH_CONTROL_PRECOMMITMENT.md), frozen
*before* any outcome); integrate its verdict; run and address a final fresh mock review.
Everything else open is documentation, synchronization or page compression —
[`docs/MASTER_TODO.md`](docs/MASTER_TODO.md) has all 198 items in terminal states.

🔴 **Two standing traps before you quote anything.** The HF `benchmark` field spells
`longmemeval_v2` / `scicode` / `swebench_verified` — a grep for `lmev2` or `swebench`
returns a **false zero**. And `/tmp/lmev2/questions.jsonl` is untracked, outside the
repo, in shared `/tmp`, and gates the bearing-scarcity figure.

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
| [`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md) | **every cell, call and token — counted from logs, never estimated** |
| [`docs/SCOPE_FREEZE.md`](docs/SCOPE_FREEZE.md) | what is in scope. **The scope is frozen** |
| [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md) | **paper → artifact.** Every figure, table, memory-construction rule and eligibility rule, with verified paths |
| [`docs/TRACE_AVAILABILITY.md`](docs/TRACE_AVAILABILITY.md) | **what still exists.** Per-result trace audit: HF-private / GitHub / local-only / unavailable forever |
| [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) · [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md) | result and figure navigation tables |
| [`docs/DATASET_INDEX.md`](docs/DATASET_INDEX.md) · [`docs/COVERAGE_MANIFEST.md`](docs/COVERAGE_MANIFEST.md) | published snapshots; the authoritative coverage universes |
| [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) | current state, the entry point |
| `src/p1mem/` | the package: adapters, client, schema, validator, leakage detector |
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

**Use `/Users/bellayang/miniconda3/bin/python3` (3.13).** The system `python3` is 3.9 and
aborts pytest collection on a vendored file. `pip install -e .` per `pyproject.toml`, then
`pytest -q` (**638 tests**) and `python3 scripts/audit_claims.py` (**218 checks in 21
sections**). Both green at `9f835a2`.

---

## Current Project State

**Updated 2026-10-01 by SA-ARCHIVE.** This section is the **navigation hub** — read it
first, then [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) **Part I** for detail
(current state at the top, history below). Indices:
[`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md) (every cell, call and
token), [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) (every result → artifact → script →
paper) and [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md) (every figure).

🔴 **Five agents work this repo concurrently** (SA-PAGE `main.tex` · SA-HF releases ·
SA-SWE-FINAL SWE-bench · SA-FINAL-AUDIT the audit · SA-ARCHIVE these docs). **Never
`git add -A`** — it has mis-attributed files twice, in both directions.

### The story, in one sentence

Memory utility in this corpus is **not** "sometimes helpful, sometimes harmful depending
on the task" — it is **sparse and one-sided**: a memory bears on a median of *one* future
task out of hundreds, helps substantially where it bears, does approximately nothing where
it does not, and compressing it destroys the benefit — so a single scalar `Value(memory)`
is the wrong object, for a different reason than we hypothesised.

### Identity

| | |
|---|---|
| **Title** | *What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent Memory* (re-checked against `overleaf/main.tex:65` on 2026-10-01; the previous line here said “Conditional Evaluation of” and was stale) |
| **Venue** | AAMAS 2027 main track — abstract 1 Oct AoE, paper 8 Oct AoE |
| **Overleaf** | <https://git.overleaf.com/6abbde4a9eb777031afef068> (`main`), local clone `../overleaf`; manuscript-side lookup `overleaf/ARTIFACT_LOOKUP.md` |
| **Current Overleaf commit** | **`1961825`** "Cite two figures the text never pointed at; tighten the reader paragraph" |
| **Code repo** | <https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory> (`main`) |
| **HF dataset** | <https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory> (**private**) |
| **Current HF version** | **v0.4 `swebench-metrics`**, tag `v0.4-swebench-metrics` (commit `bc66629f`, == branch `main` byte-for-byte) — **5,924 rows** (longmemeval_v2 5,643 / scicode 154 / swebench_verified 127), schema `p1mem_conditional_memory_utility_v3`, **98 fields**, **private**. Licence frontmatter is `other` + `license_name: mixed-per-row-see-data-card`, NOT apache-2.0: the 127 SWE-bench rows are metrics-and-ids only. All four tags exist (v0.1/v0.2/v0.3/v0.4). **Re-verified 2026-10-01 by SA-SYNC by downloading every tag** — row counts, schema version, benchmark composition and withholding state all reproduce exactly. 🔴 The benchmark field spells `longmemeval_v2` / `scicode` / `swebench_verified`; a grep for `lmev2` or `swebench` returns a false zero. |
| **Code repo HEAD** | **`9f835a2`** "docs: freeze the scientific scope", 2026-10-01 12:21 CDT · 227 commits |

### Main local paths

| what | where |
|---|---|
| code repo | `/Users/bellayang/Documents/2026/p1_memory_utility/repo` |
| manuscript | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` |
| HF staging (**never committed**) | `/Users/bellayang/Documents/2026/p1_memory_utility/hf_staging/` |
| sub-agent reports | `/Users/bellayang/Documents/2026/p1_memory_utility/subagent_*_report.md` |
| LongMemEval-V2 source | `/tmp/lmev2` (checksum-verified; `trajectories.jsonl` ~1.1 GiB) |
| main result rows | `results/deltau_screened/cells.jsonl` (**untracked**) |
| clone-reproducible slices | `results/ledgers/repro/` (**tracked**, sha256 in `MANIFEST.json`) |

**Python: `/Users/bellayang/miniconda3/bin/python3` (3.13).** The system `python3` is 3.9
and aborts pytest collection on a vendored file — a healthy suite looks broken.

# Paper / Overleaf status

**Title.** *What Is This Memory Useful For? Measuring Task-Conditioned Utility
in Long-Term Agent Memory*

🔴 **Overleaf git access is temporarily unavailable** (account/Premium access;
both `git push` and `git fetch` return `no git access`, so it is the remote and
not a credential). **No manuscript content is lost.**

| | |
|---|---|
| **canonical paper package** | [`paper/`](paper/) — self-contained, compiles standalone |
| **GitHub commit holding the mirror** | `6ef8f1e` |
| **local Overleaf clone** | `../overleaf` (sibling of this repo), commit **`a320c74`**, **one commit ahead of the Overleaf server** |
| **build status** | ✅ 11 pages, 0 undefined control sequences / citations / references; the mirror's rendered text is **byte-identical** to the Overleaf copy's PDF |
| **target remote** | `git.overleaf.com/6abbde4a9eb777031afef068` — **unchanged, and must NOT be replaced** |

**When access returns:** fetch the existing remote, reconcile only if it moved,
push the local clone, then fresh-clone it, compile independently, and verify
title, tables, figures and `ARTIFACT_LOOKUP.md` against [`paper/`](paper/).

⚠️ **Do not re-apply manuscript edits by hand from the mirror.** The local
Overleaf clone already contains them; pushing it is the whole operation.

### Navigation

| | |
|---|---|
| paper → artifact map | [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md) |
| what traces still exist | [`docs/TRACE_AVAILABILITY.md`](docs/TRACE_AVAILABILITY.md) |
| figure lookup · table lookup | [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md) · [`docs/PAPER_ARTIFACT_MAP.md`](docs/PAPER_ARTIFACT_MAP.md) §(b) |
| handoff entry point | [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) |
| result index · coverage | [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) · [`docs/COVERAGE_MANIFEST.md`](docs/COVERAGE_MANIFEST.md) |
| dataset index · scope freeze | [`docs/DATASET_INDEX.md`](docs/DATASET_INDEX.md) · [`docs/SCOPE_FREEZE.md`](docs/SCOPE_FREEZE.md) |
| Hugging Face dataset | `AgentsSci/AAMAS2027-ConditionalMemory` (**private**; tags v0.1 … v0.4) |

### Coverage and model identity — read these two tables first

Authoritative definitions: [`docs/COVERAGE_MANIFEST.md`](docs/COVERAGE_MANIFEST.md)
(what "full coverage" means) and [`docs/MODEL_ARMS.md`](docs/MODEL_ARMS.md)
(which model produced which result).

| Benchmark | Eligible pool | Executed | Coverage | Reader | Writer | Representation | Status |
|---|---:|---:|---:|---|---|---|---|
| **LongMemEval-V2** (screened design — what the paper reports) | 1,157 | 1,157 | **100%** | gpt-oss-120b **+ gemma-4-31B-it** | deterministic + gpt-oss **+ gemma** | raw / summary / structured | **DONE** |
| LongMemEval-V2 (frozen 8-task pairing universe) | 15,112 | 574 | 3.8% | gpt-oss-120b | — | raw | partial |
| LongMemEval-V2 (representation sub-universe, 285 × 3) | 855 | 847 | 99.1% | both | both | all three | 8 structured write failures |
| LongMemEval-V2 (LLM-judged stratum) | 156 q | 0 | 0% | — | — | — | **eligible, not excluded**, blocked on F_judge |
| **SciCode** | 154 | 154 | **100%** | gpt-oss-120b | deterministic + gpt-oss | raw / summary / structured | **DONE** — raw-only in the release |
| **SWE-bench Verified** (runnable universe) | 107 | **107** | **100%** | gpt-oss-120b | deterministic + gpt-oss | raw / summary / structured | ✅ **COMPLETE** at `bd25ad4` — django 96 + sympy 11, remaining 0 |

🔴 **LongMemEval has two universes and neither percentage alone is honest.** The
screened design is a **re-pairing**, not a subset of the frozen universe —
B ∩ A = **102**, B \ A = **1,055**. Always name the universe when quoting a coverage %.

✅ **SWE-bench coverage is COMPLETE** (`bd25ad4`): 107/107 attempted, **remaining 0**,
across django (96) and sympy (11). The identity closes exactly — 37 valid completed + 70
excluded with reasons (39 localizer miss · 20 unapplicable edit · 10 scorer invalidity ·
1 contagion-dirty · **0 not-yet-attempted**). 🔴 **Tripling the matched set 15 → 40
separated no contrast family-wise**: `ORDERING_VERDICT: NOT_ESTABLISHED` in django, sympy
and pooled. ⚠️ sympy's own scorer control is **8/8**, not 20/20 — the 20/20 is the
**union** with django's 12/12, which is what the gate reads.

| Arm | Writer | Reader | Cluster | Prompt | Temp | Max output | Workers |
|---|---|---|---|---|---:|---:|---:|
| LongMemEval raw/summary/structured | deterministic / gpt-oss-120b | **gpt-oss-120b** | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| SciCode raw/summary/structured | deterministic / gpt-oss-120b | **gpt-oss-120b** | metis | `scicode_deltau_v1` | 0 | 1024 | 16 |
| SWE-bench raw/summary/structured | deterministic / gpt-oss-120b | **gpt-oss-120b** | metis | `swebench_v2_symmetric` | 0 | 2048 | 16 / sequential |
| **Reader-only replication** — **DONE** | *unchanged* (gpt-oss memories, byte-identical 1694/1694) | **gemma-4-31B-it** | metis | `p1_deltau_raw_v1` | 0 | **512** | **16** (measured, not inherited) |
| **Writer × Reader factorial** — **DONE** | gpt-oss **and** gemma-4-31B-it | both | metis | `summary_v1@…6ee16b28b818` / `structured_v1@…163d4cd3eb70` | 0 | **512** | **16** |

🔴 **Raw has no writer axis.** "Writer gpt-oss raw" and "writer Gemma raw" are the **same
bytes** — a deterministic span costs 0 model calls — so Raw is absent from the factorial by
construction, not by omission. Machine-readable configs: `src/p1mem/schema.py::READER_ARMS`.

**Gemma is verified live** at `metis/gemma-4-31B-it` (capital B) — the *same*
cluster as gpt-oss, so a reader comparison does not become a cluster
comparison. Measured, not assumed: 16 workers (252/252 clean; 25% 429s at 24,
72% at 32), 74.0 completed/min at 24k context against gpt-oss's 169.9/min.
`reasoning_effort` is **accepted but inert** on Gemma (byte-identical output
across low/medium/high, with a gpt-oss positive control showing 58/118/473
reasoning tokens — so the probe can see the effect when it exists), and Gemma
reports **no** `reasoning_tokens` at all. Cost is therefore **not poolable
across models**. Evidence: [`docs/GEMMA_ENDPOINT_PROBE.md`](docs/GEMMA_ENDPOINT_PROBE.md).

### Benchmarks

| | status |
|---|---|
| **LongMemEval-V2** | ✅ **primary, complete** — 1,889 memory units, 1,157 evaluated cells, 5,198 calls, 0 errors, plus two earlier unscreened arms |
| **SWE-bench Verified** | ✅ **representation arms COMPLETE — 107/107 attempted, remaining 0.** Pairing is excellent (406 cells, 133 donors, **0.0% diagonal**, 0/406 temporal violations, real unit tests). The v1 arm asymmetry was **output-format imitation** (the reader copied the memory's diff fence), fixed by lossless `[added]`/`[removed]` re-encoding: apply-failure gap **0.375 → 0.000**, 8/8 arm-symmetric. v2 + the two v3 django chunks (288 django rep-cells) + sympy (33 rep-cells) give matched **40 CELLS** (django 37 + sympy 3) after the defect-21 correction — the superseded 15 was the pre-scale-up universe (`results/swebench/representations_multirepo.json`); canonical is `representations_multirepo_final.json`. **Every contrast `NOT_ESTABLISHED`** per-repo and pooled, family-wise. 🔴 **40 matched CELLS is a different unit from the 107 attempted / 37 valid ITEMS** in `docs/COVERAGE_MANIFEST.md` §3 — never compare the two. The 32-cell presence pilot's 37.5% [22.9, 54.8] (p=0.125) is a **different cell set** and must not be inherited as the representation arm's gate. 🔴 **No licence is declared: metrics + ids ONLY.** `docs/BENCHMARK_C_DECISION.md`, `docs/SWEBENCH_MULTIREPO.md` |
| **SciCode** | ✅ **complete as a case study, never a main table.** The full **154-pair eligible pool** × 3 representations × 2 arms = **924 arm-runs**. Matched set **n=122**: raw −0.0082 · summary +0.0164 · structured +0.0246. 🔴 **All three contrasts cross zero → `ORDERING_VERDICT: NOT_ESTABLISHED`**, and the free control **F_exec = 5/135 = 0.0370 is LARGER than the biggest point estimate**. The defensible reading is that **the point-estimate ordering differs across benchmarks**; this is **not** an established "inversion" and two guards forbid that word, both verified by planting it. 🔴 **Ships raw-only (154 of 462 cells): the summary/structured memory TEXT was never persisted** and is not recoverable — a *persistence* gap, never the SWE-bench licence embargo. The rewards stay valid. `docs/SCICODE_RESULT.md` |
| **BEAM** | ❌ **DROPPED, with the measured reason: 92.6% of cited turns are cited by exactly one question**, so BEAM cannot supply the multi-task-per-memory axis this paper needs. Secondary reason: **CC BY-SA 4.0** — ShareAlike is infectious and would force a separate dataset release. `docs/BENCHMARK_DECISIONS.md`, `docs/BENCHMARK_LICENSES.md` |
| rejected replacements | **DS-1000** (CC BY-SA 4.0 — the same ShareAlike trap) · **SWE-Gym** (MIT, 1,868 multi-recipient donors, held in reserve, but it is agent *training* data so contamination argues against it) · **τ-bench** (HF API 401 — **UNRESOLVED**, not absent) |

### Memory representations

| | status |
|---|---|
| **Raw / extractive** | ✅ **at scale** — 1,889 units, deterministic, **0 model calls**, median 8,344 exposed tokens |
| **Summary** | ✅ **at scale** — 60 written, median 282 exposed tokens, compression 0.063. **7 of 60 were truncated mid-sentence and admitted `ok=True`** |
| **Structured** | ✅ **at scale** — 60 written, median 216 exposed tokens, compression 0.037. **3 of 60 malformed, all `finish_reason == length`**; 0 of the 57 that finished. 8 cells excluded for failed writes, listed per cell |

Join representations on **`memory_unit_locator`**, never `memory_id` — the latter is a
per-representation content hash and returns **zero** paired memories.

### Main findings

All re-derived by `scripts/audit_claims.py` unless noted. Per-result provenance:
[`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md).

1. **Screening the pairing makes the effect measurable.** Both-arms-fail **0.7007 →
   0.5252**; the pre-committed rule (BEARING Wilson upper below RANDOM's point estimate)
   passed on data it had never seen.
2. **Where a memory bears on a task, it helps.** Paired within-memory **+0.3349** over 60
   memories (**35 non-zero contributors**; contributors-only **+0.5740**), episode-clustered
   **[+0.1974, +0.4736]** excludes zero, p = 5×10⁻⁵. The audit now asserts the manuscript
   prints that interval and the memory bootstrap **[+0.2085, +0.4606]**; the older pair
   `docs/SCREENED_RESULT.md` still shows exists in **no artifact** — `RESULT_INDEX.md` §F1.
3. **Bearing is scarce.** A memory bears on a **median of one** future task out of
   hundreds: 165 of 1,889 units bear on any task, **46** on two or more, from only **23**
   source episodes. This is a ceiling on precision that no amount of compute moves.
4. **The founding hypothesis is not supported.** **0 sign flips in 35** flip-eligible
   bearing memories (bounded ≤9.9%, not merely unobserved); reversals concentrate in the
   unscreened stratum (**17/60**); and the excess over the fitted additive null is
   **negative in every stratum** — flips are *below* what main effects alone produce.
5. **Compression destroys the effect.** Only **Raw**'s paired B−MC interval excludes zero;
   Summary and Structured — same writer, same reader, same tasks — do not.
6. **The efficiency ranking reverses once formation cost is charged.** Uncharged, Summary
   looks ~5.6× more token-efficient than Raw. Charged its own formation cost (1,626
   tokens/cell amortized, as `MEMORY_PROTOCOL` §5 requires), it is **≈1.08× worse — i.e.
   no better**, and Structured is 4.85× worse. Raw is **bit-identical** in both columns,
   which is the correctness test that the cost was attributed to the right arm.
7. **Similarity is a poor proxy for utility.** Spearman **+0.087** over all 1,157 cells,
   **+0.006** in the unscreened stratum, against a content screen that separates +0.3453
   from +0.0274 using no embedding at all.
8. **The reader is not the bottleneck.** A planted per-cell code in the real ~27k context
   is recovered **22/22** by the base config; three stronger readers solve **zero** cells
   the base missed.
9. **Memory utility TRANSFERS across readers.** 🔴 **Canonical = SESSION-MATCHED
   +0.0982 [+0.0247, +0.1730], n=550** (matched replicate rows over 275 cells), both arms
   re-run 14 minutes apart with `memory_text` byte-identical 550/550.
   `VERDICT: SURVIVES_SESSION_MATCHING`. ⚠️ **The cross-session +0.1268 is SUPERSEDED** —
   its arms were 11 h apart and this endpoint is not deterministic across sessions. It
   stays visible as history and **never leads**. **The WITHOUT-arm decomposition did not
   survive** (−0.0364 session-matched vs −0.0688): do not quote "about half the gain is a
   weaker reader."
10. **No same-family writer–reader advantage.** All four factorial contrasts span zero —
   an informative null, not an underpowered one. Raw is not in the factorial (no writer axis).
11. **Cross-benchmark heterogeneity is a limit, not a ranking.** LongMemEval's
   Raw-dominant ordering is **not established** on SciCode or SWE-bench.

### Main figures and tables

**5 figures and 3 tables**, counted from `main.tex` on 2026-10-01 (⚠️ earlier docs said
"3 figures / 2 tables" — both were **stale**):

| | |
|---|---|
| `fig:pipeline` | the conditional memory utility protocol |
| `fig:bearing` | bearing scarcity **+** sign reversal |
| `fig:similarity` | similarity vs the content screen |
| `fig:frontier` | **utility–efficiency frontier** (P1-C03, shipped) |
| `fig:readertransfer` | **memory utility survives a change of reader** |
| `tab:coverage` | coverage, on the universe each result is reported over |
| `tab:crossbench` | the paired representation contrast, all three benchmarks real |
| `tab:screened` | both-arms-fail and mean ΔU per stratum, both unscreened arms as comparators |

**Every caption number is generated, never typed**, by `scripts/make_figures.py` →
`overleaf/figdata.tex`, which **exits non-zero if it disagrees with the audit**.
`scripts/verify_figure_guards.py` plants **22** defects and requires every guard to fire.
🔴 **Figure `tab:crossbench` plots contrasts, not per-representation ΔU** — the benchmarks
have different execution floors and the contrast differences them out. Details and
rejected figures: [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md).

### Running jobs (2026-10-01 12:45 CDT)

**Five agents are working concurrently.** Do not edit another agent's files.

| agent | owns | state |
|---|---|---|
| **SA-PAGE** | `overleaf/main.tex` | **RUNNING** |
| **SA-HF** | HF releases, `docs/DATASET_INDEX.md`, `docs/hf_card/` | **DONE** — v0.3 and v0.4 both shipped and verified on the downloaded tags |
| **SA-SWE-FINAL** | new SWE-bench cells, `COVERAGE_MANIFEST.md` §3, `SWEBENCH_MULTIREPO.md` | **RUNNING** — 41 django cells remain |
| **SA-FINAL-AUDIT** | the standing claim/evidence audit | **RUNNING** |
| **SA-ARCHIVE** | `README.md`, `HANDOFF_CURRENT.md`, `RESULT_INDEX.md`, `FIGURE_INDEX.md`, `MODEL_ARMS.md`, `MASTER_TODO.md`, `EXPERIMENT_ACCOUNTING.md` | this section |

**SWE-bench numbers are in flux** — cite SA-SWE-FINAL's artifact and say *"as of
`<commit>`"* rather than freezing a figure you did not derive.

**Liveness for endpoint-bound work:** `lsof -p <pid> | grep -c ESTABLISHED` → expect 16.
🔴 **CPU% near zero is NOT a stall**, and **stdout is block-buffered, so an empty log is
NOT a stall either.** Every runner is idempotent through its response cache.

Exact commands and restart procedures:
[`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) §8. **No compute job is on any
cluster queue** — every run to date executed on this laptop against the ALCF gateway.

⚠️ **Never `git add -A`** — it has already mis-attributed files twice in this repo, in
both directions. 🔴 **And staging an explicit path is NOT sufficient:** `git commit`
commits the **whole index**, which is shared with every other agent. Use a
**pathspec-limited commit** and verify every time:

```bash
git commit -F <msgfile> -- path/one path/two     # ONLY these paths
git show --stat HEAD                              # then VERIFY
```

If the stat shows files you did not write: `git reset --soft HEAD~1` (this preserves the
other agent's staging) and re-commit with `--`. SA-ARCHIVE hit this on 2026-10-01 — a
`git add README.md` produced a 23-file, 29,075-insertion commit carrying another agent's
work. `git show --stat` is what caught it.

### Failed, invalid, and superseded runs

| run / claim | verdict |
|---|---|
| `results/raw_session_matched_VOID_mislabelled/` (570 rows, 1,201 calls) | 🔴 **VOID** (defect 27) — a hardcoded `CONDITION_ID` labelled gpt-oss rows `gemma4_31B`. The runner's own gate caught it (`VERDICT: RUN_FAILED`). Kept so it cannot re-circulate |
| the cross-session reader transfer **+0.1268** | ⚠️ **SUPERSEDED** by the session-matched **+0.0982**. History, never the lead |
| "about half the gain is a weaker reader" | 🔴 **WITHDRAWN** — the WITHOUT-arm decomposition was inflated ~2× by a session confound (−0.0364 reader vs −0.0688 published) |
| SWE-bench representation arm **v1** | ⚠️ **SUPERSEDED by v2** — v1's contagion screen misfired on `+---+` **ASCII table borders in the issue text**. The screen was wrong, not the defanging |
| 37 SWE-bench arm-reads scored `0.0` | 🔴 **CORRECTED to `None`** (defect 21) — a pytest *collection* error is not a wrong answer. Matched n fell 17 → **15**. Quote the corrected numbers |
| `results/runs/noise_floor/` | ❌ **superseded** — one arbitrary memory per task, 2/92 accuracy |
| both unscreened arms | ⚠️ **valid but floor-limited** (~78.5% / 83.75% both-arms-fail). Keep as the dilution comparator; **never quote as the effect** |
| the official-prompt "fix" | ❌ **refuted its own hypothesis** — accuracy fell 5.7 pts because 128 correct guesses became abstentions and the harness scores an abstention as wrong (McNemar p = 1.12e-9). Do **not** re-run another prompt wording |
| "variance shares all 0.0000" | 🔴 **RETRACTED — never measured.** A `ZeroDivisionError` crashed the stage *while the script exited 0*, and `.get(c, 0.0)` over the empty dict produced a plausible zero |
| variance decomposition (all attempts) | ❌ **unidentifiable**, and the diagnosed cause is **`F_exec = 0`** — a deterministic reader leaves no residual scale — **not** the task-crossing defect that was fixed. **No share may be quoted**; `audit_claims.py` fails if one appears |
| semantic-type axis | ❌ **killed** — κ = 0.000, the native pass labelled all 8 segments `episodic` |
| SWE-bench floor pilot #1 | ❌ **VOID, and SA-N said so unprompted** — the model saw only the first 90 lines of each file and 4 of 5 gold patches edit code outside that window, so `search_miss` was the only reachable outcome. Numbers kept, not deleted, so they cannot later circulate as evidence |
| SWE-bench floor pilot #2 | ⚠️ **stopped at the gate, not cleared** (57.1% > ~50%) |
| representation pilot (n=8) | ⚠️ **superseded for every rate.** "0/8 malformed" did not scale. Keep only its compression ratios |
| `Mistral-Large-3-675B`, `gpt-oss-120b` on Minerva, Sophia's embedding model | ❌ **advertised but dead** (404 / 503 / 502) — four such cases in one day |

### Known bugs and traps

1. **Advertised ≠ live.** Prove every model dependency with a real POST, with a negative control.
2. **HF `auth-check` returns 200 for repos you cannot write.** Only an empty-body commit POST discriminates (400 vs 403).
3. **`memory_id` means two things.** Rows carry a content hash; some manifests carry a positional locator. **Join on `memory_unit_locator`.** This has produced a silent zero **three** times.
4. **A guard only observed passing is not known to fail.** One printed a correct verdict — "0 of 0" — from a key that does not exist.
5. **A zero from `.get(default)` is not a measurement.** An absent value defaulting to a plausible one is this project's most common defect shape.
6. **Exit code 0 is not success.** A stage crashed while its script returned 0.
7. **Pooled rates hide the structure that matters.** Leakage by answer length, both-arms-fail by stratum, concentration by stratum — split before quoting.
8. **Matching counts are not corroboration.** Two 35s named different sets (overlap 25).
9. **Throughput is prompt-length dependent** — 341/min at 4k is ~106/min at 24k.
10. `datascience_collab` expires **2026-10-01**; use AuroraGPT. Aurora is allocated but gateway-bound and unused.
11. **`F_empty` is `null`, not 0.000.** The WITHOUT arm was served from cache in 254 groups, so its spread is zero by construction. Report **UNMEASURED**.
12. **The endpoint drifted between 2026-09-29 and 2026-09-30.** Byte-identical prompts give different text on 53% of rows across days (mean-preserving on reward: 0.3100 → 0.3100, 7 up / 7 down). Within a session it is exactly deterministic. **Every cross-day comparison carries a per-cell noise term.**
13. **`ok=True` did not mean the writer finished.** 7 truncated summaries were admitted as valid.
14. **The screened cache is readable only by the pre-`5330158` 12-field key shape.**
15. **`git add -A` is a mis-attribution generator here.** Stage explicit paths.
16. 🔴 **`condition_id` EMBEDS the representation name** (`lmev2_summary_..._v1`). Including it in a join key returns **ZERO rows** — and an empty join was once read as "not measurable". Correct key: `(memory_unit_locator, future_task_id)`.
17. 🔴 **`gpt-oss-120b` is deterministic WITHIN a session, NOT ACROSS** (defect 25). 554 of 1,124 byte-identical no-memory requests returned different text in a later session. **Compare only session-matched arms.** Gemma: 0/1,124.
18. 🔴 **Temperature 0 is not a persistence strategy.** Any arm that discards model-written text is **unrecoverable** (defect 22) — SciCode's summary/structured memory text is gone for exactly this reason.
19. 🔴 **An absolute `/Users/<name>/` path de-anonymises, and a credential scanner is blind to it** (defect 23). The audit now scans tracked artifacts for this, and the scan is proven non-vacuous.
20. 🔴 **A pytest collection error is not a wrong answer** (defect 21).
21. 🔴 **`export_hf.py` does NOT migrate schemas.** The ledgers are **v1/v2** and it needs **v3**.
22. **`cell_id` is a content hash and CAN collide** — 283 ids cover 285 cells on one factorial arm (defect 26). **Positive-control every join before believing its null.**

Full evidence base, with who found each and what it would have cost:
[`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md). Every count behind these:
[`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md).

### Current TODO — five agent-actionable items

Authoritative, with terminal states for all **198** IDs:
[`docs/MASTER_TODO.md`](docs/MASTER_TODO.md). **DONE 135 · DEFERRED 38 · KILLED 16 ·
TODO 7 · RUNNING 1 · BLOCKED 1**, re-derived by running the page's own snippet.

| ID | state | what it waits on |
|---|---|---|
| **P1-C17** | TODO | the one genuinely open submission-critical item: final manuscript sync, compile, anonymity, citations |
| ~~P1-C19~~ | **DONE** at `bd25ad4` | SWE-bench coverage complete: 107/107 attempted, remaining 0 |
| **P1-C21** | **DONE** | HF v0.3 (SciCode) and v0.4 (SWE-bench, **metrics + ids ONLY**) both shipped; v0.4 is current |
| **P1-C22** | TODO | three `main.tex` ↔ artifact inconsistencies, all retracted-number-still-circulating |
| **P1-I11** | TODO | 🔴 **the representation scale-up slices are STILL untracked** — Contribution B's 1,124 rows exist on one laptop |
| **P1-I13** | TODO | the efficiency ratios in `main.tex` (`5.2×` → **5.58×**; "roughly 5×" is wrong for Summary, which is **1.08×**) |

**P1-C20 (the page budget) is BLOCKED on the author by design** — the body runs ~5,400
chars onto page 9 and closing it now removes *content*, which is not an agent's decision
([`docs/PAGE_BUDGET_DECISION.md`](docs/PAGE_BUDGET_DECISION.md) measures five options).

### POST-SUBMISSION / FUTURE WORK — DEFERRED, not killed

Jev baseline · learned memory gate · **RL memory manager** · LLM memory-manager comparison ·
**new retrieval architectures** · semantic-type redesign · **new representation families** ·
**additional benchmarks** · **additional backbones** · cross-model replication · production
vector store · harmful-memory prevalence · full P3 receiver integration · retention policy ·
position-effect expansion · **the cross-session floor nobody has measured** · **the SciCode
dep-OR-lex union (+10 eligible pairs, unexecuted)**. Full list with IDs:
`MASTER_TODO.md` §3.

🔴 **Four storylines are NOT to be resurrected** ([`docs/SCOPE_FREEZE.md`](docs/SCOPE_FREEZE.md)
§5): the **sign-flip headline**, the **variance-decomposition headline**, the
**semantic-type taxonomy** as a live axis, and **harmful-memory prevalence** on this
design. Each was demoted for a measured reason; *demotion is not an oversight for a later
agent to correct.*

### Verification

`scripts/audit_claims.py` re-derives **129 PASS / 0 FAIL across 16 sections** from tracked
artifacts and is **proven able to fail** (a single flipped reward trips four checks; each
newly added guard is verified by planting the defect it forbids and watching it FAIL).
**638 tests pass** under the 3.13 interpreter. `scripts/make_figures.py` independently
recomputes every figure number and **exits non-zero if it disagrees with the audit**, and
`scripts/verify_figure_guards.py` plants 22 defects and requires every guard to fire.
`scripts/count_experiment_accounting.py` regenerates every number in
[`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md).

**Counted 2026-10-01, not estimated: 30,159 real endpoint calls** across the three
benchmarks (LongMemEval 27,803 + SciCode 1,340 + SWE-bench **1,016**), ~508.1M input and
~4.57M output tokens, 131 truncations, 47 retried calls, **0 unrecoverable losses**.
Re-derive with `scripts/count_experiment_accounting.py`; the authoritative table is
[`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md) §1. The earlier **29,775
/ SWE-bench 632** figures predate the django v3 chunks (`bd25ad4`) and are superseded.

### Handoff — the entry point

**A new Master Agent should be able to take over from
[`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) Part I alone**, without reading any
chat history. Read, in this order:

1. This section, then [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) **Part I**
   (current state at the top; history is Part II).
2. [`docs/SCOPE_FREEZE.md`](docs/SCOPE_FREEZE.md) — **the scope is frozen.** Only
   coverage completion, claim validation, repair of an invalid run, or a
   validity-critical audit gap may still be run.
3. [`docs/EXPERIMENT_ACCOUNTING.md`](docs/EXPERIMENT_ACCOUNTING.md) — every cell, call and
   token, counted from logs. A quantity it cannot count says
   `not recoverable from logs`, never a plausible zero.
4. [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) **§F** (the open disagreements) and
   **§G** (results that must NOT be quoted), then
   [`docs/THE_HONEST_HEADLINE.md`](docs/THE_HONEST_HEADLINE.md) and
   [`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md).
5. [`docs/MASTER_TODO.md`](docs/MASTER_TODO.md) §5 — the ten open rows and what each waits on.

Then run, in order:

```bash
/Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py      # 218 checks, 21 sections
/Users/bellayang/miniconda3/bin/python3 -m pytest -q                 # 638 tests
/Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py
```

**If the audit fails, stop and find out why before anything else.**

🔴 **The five standing rules:**
**(1)** Never quote a number you have not re-derived from an artifact.
**(2)** Never `git add -A`, and never a bare `git commit` either — the index is shared.
Use `git commit -F <msg> -- <paths>` and verify with `git show --stat`.
**(3)** Join on `memory_unit_locator`; `memory_id`, `cell_id` and `condition_id` all
produce silent zeros.
**(4)** Positive-control every null — an empty result is a dead channel until proven
otherwise.
**(5)** Compare only session-matched arms; this endpoint is not deterministic across
sessions.

# Memory Utility Is Not a Scalar

**Measuring Task-Conditional Value in Long-Term Agent Memory**

> **What is this memory useful for?**

Status: **analysis and write-up.** Initialized 2026-09-29; the main measurement is complete
(9,036 real endpoint calls across three LongMemEval-V2 ΔU arms, plus 2,480 for the
representation scale-up; 0 errors throughout). Jump to
[`## Current Project State`](#current-project-state).

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
`pytest -q` (**593 tests**) and `python3 scripts/audit_claims.py` (**123 checks**).

---

## Current Project State

**Updated 2026-09-30 by SA-ARCHIVE.** This section is the **navigation hub** — read it
first, then `docs/HANDOFF_CURRENT.md` for detail. Indices:
[`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) (every result → artifact → script → paper)
and [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md) (every figure).

### The story, in one sentence

Memory utility in this corpus is **not** "sometimes helpful, sometimes harmful depending
on the task" — it is **sparse and one-sided**: a memory bears on a median of *one* future
task out of hundreds, helps substantially where it bears, does approximately nothing where
it does not, and compressing it destroys the benefit — so a single scalar `Value(memory)`
is the wrong object, for a different reason than we hypothesised.

### Identity

| | |
|---|---|
| **Title** | *What Is This Memory Useful For? Conditional Evaluation of Long-Term Agent Memory* |
| **Venue** | AAMAS 2027 main track — abstract 1 Oct AoE, paper 8 Oct AoE |
| **Overleaf** | `git.overleaf.com/6abbde4a9eb777031afef068` (`main`), local clone `../overleaf` |
| **Current Overleaf commit** | **`3c06d3a`** "Abstract v5: lead with conditional utility and sparsity", 2026-09-30 16:16 CDT |
| **Code repo** | `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` (`main`) |
| **HF dataset** | `AgentsSci/AAMAS2027-ConditionalMemory` (**private**) |
| **Current HF version** | **v0.2 `repr-derived`**, tag `v0.2-repr-derived` — 5,643 rows (raw 4,519 / summary 570 / structured 554), schema `p1mem_conditional_memory_utility_v3`, **98 fields**, **private**. Verified by downloading the tag; unauthenticated fetch → 401. v0.3 (SciCode) and v0.4 (SWE-bench) not yet cut. |

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

### Benchmarks

| | status |
|---|---|
| **LongMemEval-V2** | ✅ **primary, complete** — 1,889 memory units, 1,157 evaluated cells, 5,198 calls, 0 errors, plus two earlier unscreened arms |
| **SWE-bench Verified** | 🟡 **gate PASSED; the measurement arm is NOT done.** Pairing is excellent (406 cells, 133 donors, **0.0% diagonal**, 0/406 temporal violations, real unit tests). The v1 arm asymmetry was diagnosed as **output-format imitation** (the reader copied the memory's ``` ```diff ``` fence) and fixed by lossless `[added]`/`[removed]` re-encoding: apply-failure gap **0.375 → 0.000**, 8/8 cells arm-symmetric (`results/swebench/parity_v2.json`). What exists so far is a **32-cell, django-only** presence pilot: both-arms-fail 12/32 = 37.5% [22.9, 54.8], ΔU **not significant** (exact p=0.125). 🔴 **No representation arm exists yet** — these cells carry no `memory_representation` field; they vary memory *presence*, not representation. `docs/BENCHMARK_C_DECISION.md` |
| **SciCode** | 🟡 **executed as a case study, never a main table.** Gate cleared; all three representations run on a 68-pair pilot (408 rows). both-arms-fail 0.456 raw / 0.379 summary / 0.370 structured; ΔU +0.0000 / +0.0690 / +0.0556. 🔴 **Every interval crosses zero.** The defensible reading is that **the point-estimate ordering differs across benchmarks** — LongMemEval's Raw-dominant ordering is **not reproduced** here. This is **not** an established "inversion" and `audit_claims.py` forbids that word. A full-pool 154-pair scale-up is running. `docs/SCICODE_RESULT.md` |
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
   CI excludes zero, p = 5×10⁻⁵. ⚠️ **Two CI values circulate** — see `docs/RESULT_INDEX.md`
   §F1 before quoting one.
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

### Main figures

3 in the paper (pipeline · bearing scarcity + sign reversal · similarity vs the content
screen), all with **every caption number generated, never typed**, by
`scripts/make_figures.py` → `overleaf/figdata.tex`. A **utility–efficiency frontier** is
being added (P1-C03); a **cross-benchmark** figure is blocked. Details and rejected
figures: [`docs/FIGURE_INDEX.md`](docs/FIGURE_INDEX.md).

### Main tables

2 in the paper: **`tab:flips`** (sign reversal by stratum) and **`tab:screened`** (both-arms-fail
and mean ΔU per stratum, with both unscreened arms as comparator rows). Both are typed into
`main.tex` and protected by `audit_claims.py` rather than generated.

### Running jobs (2026-09-30 17:45 CDT)

All six Phase-3 sub-agents have **finished and been integrated**. The Master Agent now
executes directly. **One job is in flight:**

- **SciCode representation scale-up** — the full 154-pair candidate pool × 3
  representations × 2 arms (924 calls), pid 90620, out
  `results/scicode/scaleup_all3.json`. Design pre-committed before running:
  [`docs/SCICODE_SCALEUP_PRECOMMITMENT.md`](docs/SCICODE_SCALEUP_PRECOMMITMENT.md).
  Liveness = `lsof -p <pid> | grep -c ESTABLISHED` → 16. **Its stdout log is
  block-buffered; empty ≠ stalled, and CPU%% ≈ 0 is normal for endpoint-bound work.**

Exact command and restart procedure: [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md)
§Currently running. **No long-running compute job is on any cluster queue** — every run to
date executed on this laptop against the ALCF gateway.

⚠️ **Never `git add -A`** — it has already mis-attributed files twice in this repo, in
both directions. Stage explicit paths and verify with `git show --stat`.

### Failed, invalid, and superseded runs

| run / claim | verdict |
|---|---|
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

Full evidence base, with who found each and what it would have cost:
[`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md).

### Active TODOs

Authoritative list with terminal states: [`docs/MASTER_TODO.md`](docs/MASTER_TODO.md).
Submission-critical open items: the frontier figure (P1-C03), HF v0.2 (P1-C04), the
SWE-bench parity fix and pilot (P1-C05/06), the SciCode adapter and pilot (P1-C08/09), the
**AI-assistance disclosure section, which AAMAS requires and which is still empty**
(P1-C18), and the final manuscript sync (P1-C17).

### HOLD / post-submission

P1-H01…H10: Jev baseline · learned conditional memory gate · LLM memory-manager comparison ·
cross-model replication · production vector store · more benchmarks · semantic-type
taxonomy redesign · harmful-memory prevalence study · full P3 receiver integration ·
training a retention policy. **Recorded so they are not lost; none is in scope now.**

### Verification

`scripts/audit_claims.py` re-derives **123 checks** from tracked artifacts and is **proven
able to fail** (a single flipped reward trips four checks; each newly added guard is
verified by planting the defect it forbids and watching it FAIL).
**593 tests pass** under the 3.13 interpreter. `scripts/make_figures.py` independently
recomputes every figure number and **exits non-zero if it disagrees with the audit**.

### Handoff

1. Read this section, then [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md), then
   [`docs/THE_HONEST_HEADLINE.md`](docs/THE_HONEST_HEADLINE.md), then
   [`docs/DEFECT_REGISTER.md`](docs/DEFECT_REGISTER.md).
2. Use [`docs/RESULT_INDEX.md`](docs/RESULT_INDEX.md) to go from any claim to its artifact,
   script and manuscript location — and read its **§F disagreements** before quoting a CI
   or an efficiency ratio.
3. Run `/Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py`. **If it fails,
   stop and find out why before anything else.**
4. Run the suite with the 3.13 interpreter.
5. **Never quote a number you have not re-derived from an artifact**, and never
   `git add -A`.

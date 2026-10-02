# P1 — HANDOFF CURRENT

> # 🟢 HANDOFF READY — 2026-10-02
>
> **The scientific work is complete enough for a new agent to take over.** The
> three-story framing is **frozen**. No experiment, model, benchmark,
> representation or analysis branch is open.
>
> **Remaining scientific TODOs: 0.** One editorial task is **deferred**, not
> unfinished: see *Mock review* below.

## Your first five actions

1. Read **§Main story** in [`../README.md`](../README.md) — three stories, and
   the founding hypothesis that was **not** supported.
2. Run a **fresh blind mock review** (details below). This is the first task.
3. Address substantive clarity objections it raises.
4. Venue-compliance and page-budget pass —
   [`PAGE_BUDGET_DECISION.md`](PAGE_BUDGET_DECISION.md) has the options costed.
5. Push the manuscript to Overleaf **once a human restores access** (below).

**Do not open new science** unless the mock review finds a validity-critical
hole.

## Mock review — DEFERRED TO NEXT AGENT

> **Final fresh mock review: DEFERRED TO NEXT AGENT — the attempts stalled on
> tooling/read infrastructure, not on manuscript content.**

Three sub-agent attempts each stalled at ~600 s while *reading* the paper: once
on the PDF, once on a pre-extracted 102 KB text file, once on three
page-aligned chunks with an explicit read-then-write instruction. The paper
itself was never the problem. **This is not an unfinished experiment.**

When you run it, give the reviewer **only** the PDF or its text, with no access
to this repository, and ask the question in this form:

> *Do not look for a particular number of contributions.* Report how many
> distinct headline claims you come away with, and what they are, in your own
> words — before forming any other opinion.

If the reviewer recovers **three**, the structure works. If five or six,
simplify and repeat. Also ask for **alternative explanations** per claim: the
previous blind review's deciding objection (the bearing screen might be an
oracle) was correct and led to the gold-free experiment.

## 🔴 Do NOT redo these

| | why |
|---|---|
| Re-apply the gold-free or length-control manuscript edits | **already in `../overleaf/main.tex`.** Check: `grep -c 'never sees the gold answer' ../overleaf/main.tex` → **1** |
| Re-run SciCode | 154/154 is the **full** eligible pool under the frozen relatedness rule |
| Recover SciCode Summary/Structured memory text | never persisted; cross-session regeneration is **0/8** byte-identical. Not recoverable |
| Relax SWE-bench `tasks_per_memory=4` | **+10** runnable cells, not +146 — and it silently re-pairs 13 already-executed cells |
| Reopen sign-flip, variance decomposition, semantic-type | each demoted for a **measured** reason |
| Retry the Overleaf remote on a schedule | a human must restore access first |

## Canonical vs superseded

| ✅ canonical | ❌ superseded / void |
|---|---|
| reader transfer **+0.0982 [+0.0247,+0.1730]**, session-matched, 275 cells | cross-session **+0.1268** |
| SWE-bench **n=40** (`representations_multirepo_final.json`) | n=15, n=17, `representations_v1.json` (**VOID**) |
| length control **O2** — budget, not rewriting | "rewriting removes the benefit" (**refuted**; two audit guards pin it) |
| **both** gold-free screens reported | reporting only the one that worked |

Full list: [`INVALID_AND_SUPERSEDED.md`](INVALID_AND_SUPERSEDED.md).

## Overleaf — frozen local canonical copy

| | |
|---|---|
| remote | `git.overleaf.com/6abbde4a9eb777031afef068` — **unchanged; do not replace** |
| access | 🔴 **UNAVAILABLE** (account/Premium). `push` *and* `fetch` both fail, so it is the remote, not a credential |
| local clone | `../overleaf` — **commit `c1a66da`** |
| pending | **4 commits** ahead of the server (`650a911`) |
| GitHub mirror | [`../paper/`](../paper/) — **byte-identical** to the local clone |
| build | ✅ verified **independently**: `paper/` copied to a scratch dir and built with no access to `../overleaf` — 0 undefined control sequences / citations / references, 11 pages, rendered text **identical** to the local PDF |

### Restore procedure, when a human regains access

```bash
cd ../overleaf
git fetch origin                      # 1. confirm the remote is reachable
git rev-list --count origin/main..HEAD   # 2. expect 4; reconcile ONLY if the remote moved
git push origin main                  # 3. push the existing canonical history
git rev-list --count origin/main..HEAD   # 4. expect 0 — verify by COUNT, not exit code
cd /tmp && git clone <remote> verify  # 5. fresh clone
cd verify && latexmk -pdf main.tex    #    build it twice (bibtex)
```

Then compare the fresh clone's rendered text against [`../paper/`](../paper/).
**Pushing the local clone is the whole operation** — the content is already
there.

---

## Historical detail (superseded by the block above where they differ)


## 1. Read these, in this order

1. **This file, Part I.**
2. [`SCOPE_FREEZE.md`](SCOPE_FREEZE.md) — what is in scope. The scope is **frozen**.
3. [`EXPERIMENT_ACCOUNTING.md`](EXPERIMENT_ACCOUNTING.md) — every cell, call and token, counted.
4. [`RESULT_INDEX.md`](RESULT_INDEX.md) **§F** — the open disagreements between sources of
   truth. Also [`FIGURE_INDEX.md`](FIGURE_INDEX.md) before touching any figure.
5. [`THE_HONEST_HEADLINE.md`](THE_HONEST_HEADLINE.md), then
   [`DEFECT_REGISTER.md`](DEFECT_REGISTER.md), then [`MASTER_TODO.md`](MASTER_TODO.md).

Pre-commitments, each written **before** the data they govern existed:
[`ANALYSIS_PREREGISTRATION.md`](ANALYSIS_PREREGISTRATION.md) ·
[`READER_TRANSFER_PRECOMMITMENT.md`](READER_TRANSFER_PRECOMMITMENT.md) ·
[`WRITER_FACTORIAL_PRECOMMITMENT.md`](WRITER_FACTORIAL_PRECOMMITMENT.md) ·
[`SCICODE_SCALEUP_PRECOMMITMENT.md`](SCICODE_SCALEUP_PRECOMMITMENT.md).
Results: [`READER_TRANSFER_RESULT.md`](READER_TRANSFER_RESULT.md) ·
[`WRITER_FACTORIAL_RESULT.md`](WRITER_FACTORIAL_RESULT.md) ·
[`REPRESENTATION_RESULT.md`](REPRESENTATION_RESULT.md) ·
[`SCICODE_RESULT.md`](SCICODE_RESULT.md) · [`SCREENED_RESULT.md`](SCREENED_RESULT.md) ·
[`SESSION_DETERMINISM_AUDIT.md`](SESSION_DETERMINISM_AUDIT.md).

Then:

```bash
/Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py      # 218 checks, 21 sections
/Users/bellayang/miniconda3/bin/python3 -m pytest -q                 # 638 tests
/Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py
```

**If the audit fails, stop and find out why before anything else.** Both were green at
`9f835a2` (2026-10-01 12:21 CDT).

## 2. Who is working right now — DO NOT EDIT THEIR FILES

Five agents work this repo concurrently and **share one git index**. `git add -A` has
mis-attributed files twice — and staging an explicit path is **still not enough**, because
`git commit` commits the whole index. **Use `git commit -F <msg> -- <paths>` and verify
with `git show --stat` every time.** See §10 trap 23; I hit this on 2026-10-01.

| agent | owns |
|---|---|
| **SA-PAGE** | `overleaf/main.tex` |
| **SA-HF** | HF releases, `docs/DATASET_INDEX.md`, `docs/hf_card/` |
| **SA-SWE-FINAL** | new SWE-bench cells, `docs/COVERAGE_MANIFEST.md` §3, `docs/SWEBENCH_MULTIREPO.md` |
| **SA-FINAL-AUDIT** | standing claim/evidence audit |
| **SA-ARCHIVE** | `README.md`, `HANDOFF_CURRENT.md`, `RESULT_INDEX.md`, `FIGURE_INDEX.md`, `MODEL_ARMS.md`, `MASTER_TODO.md`, `EXPERIMENT_ACCOUNTING.md` |

**SWE-bench coverage is COMPLETE as of `bd25ad4`** (107/107 attempted, remaining 0), but
its diagnostic tree may still grow. Cite SA-SWE-FINAL's artifact and say *"as of
`<commit>`"* rather than freezing a figure you did not derive.

## 3. Identity, paths and remotes

| what | where |
|---|---|
| **code repo** | `/Users/bellayang/Documents/2026/p1_memory_utility/repo` → `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` (`main`) |
| **repo HEAD** | **`9f835a2`** "docs: freeze the scientific scope", 2026-10-01 12:21 CDT · **227 commits** |
| **manuscript** | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` → `git.overleaf.com/6abbde4a9eb777031afef068` (`main`) |
| **Overleaf HEAD** | **`1961825`** "Cite two figures the text never pointed at; tighten the reader paragraph" · working tree clean |
| **HF dataset** | `AgentsSci/AAMAS2027-ConditionalMemory` (**private**) |
| **HF version** | **v0.5 `reader-generalization`** — **12,384 rows** (longmemeval_v2 **12,103** / scicode 154 / swebench_verified 127), by reader **gpt-oss-120b 9,566 / gemma-4-31B-it 2,818**, schema `p1mem_conditional_memory_utility_v3`, **98 fields**, private. Built from repo commit `57b068f`. Frontmatter `license: other` + `license_name: mixed-per-row-see-data-card`. **Five tags retained.** Verified 2026-10-02 **on the DOWNLOADED tag**: the card's own command prints `12384 rows | 0 errors | 1703 warnings`, matching the card exactly, and all 17 files are byte-identical to staging. 🔴 **v0.5 is the first release with ANY `gemma-4-31B-it` reader row** — through v0.4 it was `gpt-oss-120b` on 5,924/5,924, so the Story 3 evidence base was in the paper and not in the data. 🔴 **The v0.5 tag was moved once**: the first upload carried 3 `__pycache__/*.pyc` left by a verification step that imported the shipped package without `-B`; never in MANIFEST, no data byte changed, tag now on the cleaned commit. 🔴 Known shipped defect retained: `docs/DATASET_INDEX.md` inside the **v0.3** tag still says "No SciCode row is in any published snapshot" while that tag ships 154 — fixed from v0.4 on, left published at v0.3 and recorded |
| HF staging (**never committed, never uploaded from the repo**) | `/Users/bellayang/Documents/2026/p1_memory_utility/hf_staging/AAMAS2027-ConditionalMemory/` |
| data card | `docs/hf_card/README.md` (byte-identical to the uploaded card) |
| LongMemEval-V2 source | `/tmp/lmev2` (checksum-verified; `trajectories.jsonl` ~1.1 GiB, `questions.jsonl` 451 rows) |
| LongMemEval V1 | `data/lmev1/` |
| ALCF auth | `/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication/inference_auth_token.py` |
| sub-agent reports | `../subagent_*_report.md` |
| **venue** | AAMAS 2027 main track — abstract 1 Oct AoE, **paper 8 Oct AoE** |

**Python: `/Users/bellayang/miniconda3/bin/python3` (3.13).** The system `python3` is 3.9
and aborts pytest collection on a vendored file — **a healthy suite looks broken**. Scripts
importing `p1mem` directly need `PYTHONPATH=src` unless the package is installed `-e`.

## 4. Frozen configuration — a change is a NEW ARM, never a backfill

Machine-readable: `src/p1mem/schema.py::READER_ARMS`. A runner asks for an arm **by name**
and `reader_row_fields()` splats all five identity fields, so a script cannot fill four and
leave the fifth null.

```text
endpoint        : https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
embeddings      : Salesforce/SFR-Embedding-Mistral on Sophia, dim 4096
                  2,000-Qwen-token budget with halving retry; 98.5% of units truncated
memory unit     : page visit (maximal run of states sharing one URL), median 7,261 tok
tokenizer       : Qwen/Qwen3.5-9B
```

### Readers

| arm | model | cluster | reasoning_effort | temp | max_tokens | workers | reports reasoning tok | truncation = error |
|---|---|---|---|---:|---:|---:|---|---|
| `gptoss_metis` | `gpt-oss-120b` (BARE name) | metis | `low` | 0 | 512 | **16** | **yes** | no |
| `gemma_metis` | `gemma-4-31B-it` (capital B) | metis | **field OMITTED**, recorded `none:not_applicable` | 0 | 512 | **16** | **no** | **yes** |
| `gemma_sophia_failover` | `google/gemma-4-31B-it` | sophia | omitted | 0 | 512 | 16 ⚠️ **inherited, NOT measured** | no | yes |

**Gemma's 16 workers are measured, not inherited:** 252/252 clean at ≤16, **25.00%** 429s at
24, **71.88%** at 32. Throughput 74.0 completed/min at the real 25,176-token shape against
gpt-oss's 169.9/min. `reasoning_effort` is **accepted but verifiably inert** on Gemma
(byte-identical output across omitted/low/medium/high, with a gpt-oss positive control
showing 58/118/473 reasoning tokens — the probe can see the effect when it exists).
**Cost is NOT poolable across models.** Evidence: [`GEMMA_ENDPOINT_PROBE.md`](GEMMA_ENDPOINT_PROBE.md).

### Writers

| representation | writer | model calls | prompt version |
|---|---|---:|---|
| **Raw** | `RawExtractiveWriter`, deterministic span | **0** | — |
| **Summary** | `gpt-oss-120b` or `gemma-4-31B-it` | 1/memory | `summary_v1@1.0.0+6ee16b28b818` |
| **Structured** | `gpt-oss-120b` or `gemma-4-31B-it` | 1/memory | `structured_v1@1.0.0+163d4cd3eb70` |

🔴 **Raw has no writer axis.** "Writer gpt-oss raw" and "writer Gemma raw" are the **same
bytes**, so Raw is absent from the factorial by construction, not by omission.

### Reader prompts

| benchmark | prompt version | max output |
|---|---|---:|
| LongMemEval-V2 | `p1_deltau_raw_v1` | 512 |
| LongMemEval-V2 (official-prompt arm) | `p1_deltau_raw_official_v1` | 512 |
| SciCode | `scicode_deltau_v1` | 1024 |
| SWE-bench | `swebench_v2_symmetric` | 2048 (reader) / 1024 (writer) |

**Cluster and prompt version are experimental identity.**

## 5. Current conclusions — state these consistently everywhere

### 5.1 Reader transfer — the CANONICAL value

> ✅ **SESSION-MATCHED: +0.0982, task-clustered [+0.0247, +0.1730], n = 550.**
> `VERDICT: SURVIVES_SESSION_MATCHING` · `results/ledgers/raw_session_matched_analysis.json`

Both arms re-run **14 minutes apart** on 2026-10-01; `memory_text` byte-identical 550/550;
sign agreement 110/116. Each mean lies inside the other's CI.

⚠️ **n=550 is matched REPLICATE ROWS over 275 distinct cells** (I re-derived both). Name
the unit when you quote it.

🔴 **The cross-session +0.1268 [+0.0511, +0.2050] is SUPERSEDED.** Its arms were 11 hours
apart and defect #25 makes that a real confound. It stays visible as history — *retraction
is labelling, not deletion* — but **never leads**.

🔴 **The WITHOUT-arm decomposition did NOT survive**: −0.0364 session-matched vs −0.0688
cross-session. **Do not quote "about half the gain is a weaker reader."**

### 5.2 Everything else

- **Screening the pairing makes the effect measurable.** Both-arms-fail **0.7007 → 0.5252**;
  the pre-committed rule passed on data it had never seen.
- **Paired within-memory effect +0.3349** over 60 memories (**35 non-zero contributors**;
  contributors-only **+0.5740**), p = 5e-5, episode-clustered interval excludes zero.
  The artifact says **[+0.1974, +0.4736]**, memory bootstrap **[+0.2085, +0.4606]** — and
  `audit_claims.py` now asserts the manuscript prints **those two**, so F1 is closed in the
  **artifact's** direction. ⚠️ The older **[+0.1989, +0.4758]** / **[+0.2138, +0.4622]**
  pair that `docs/SCREENED_RESULT.md` still prints appears in **no artifact on disk** — do
  not reintroduce it. `docs/RESULT_INDEX.md` §F1 holds the full history.
- **Bearing is scarce:** 165/1,889 units bear on any task, **46** on ≥2, from **23** episodes.
- **Founding hypothesis unsupported:** 0 sign flips / 35 bearing memories, bounded ≤9.9%;
  flips concentrate in RANDOM (17/60); **the additive-null excess is negative in all strata**.
- **Compression destroys the effect:** only Raw's paired B−MC interval excludes zero.
- **The cost ranking reverses once formation is charged:** uncharged Summary ≈**5.58×** Raw
  (`docs/REPRESENTATION_RESULT.md` says **5.6×**, consistent); charged, Raw/Summary
  ≈**1.08×** — **no advantage** — and Raw/Structured **4.85×**. Raw is bit-identical across
  both columns (the A1.5 correctness test). ⚠️ `main.tex` still says **5.2×** and "roughly
  5×" — wrong for Summary, which is the representation that sentence is about. Open as
  **P1-I13**; `RESULT_INDEX.md` §F3.
- **Similarity barely predicts utility:** per-cell ρ = **+0.0868** overall, **+0.0061** in
  RANDOM, **+0.1644** in BEARING.
- **The reader is not the bottleneck:** 22/22 on a planted needle in the real ~27k context.
- **No same-family writer–reader advantage:** all four factorial contrasts span zero.
- **Decomposition unidentifiable** — cause is **`F_exec = 0`**, not the crossing defect.
- **SciCode:** matched n=122, all three contrasts cross zero → `ORDERING_VERDICT:
  NOT_ESTABLISHED`. F_exec = 0.0370 is **larger** than the biggest point estimate.
- **SWE-bench:** coverage **COMPLETE, 107/107** at `bd25ad4`. Every contrast remains
  `NOT_ESTABLISHED` per-repo and pooled — **tripling the matched set 15 → 40 separated
  nothing family-wise**, which is a far stronger null than a coverage excuse. 🔴 django's
  `structured − summary` is **nominally** +0.1081 [+0.027, +0.2162] but rests on 4 nonzero
  cells of 37, appears in neither chunk alone, inverts in sympy, and **spans zero under
  Bonferroni for the 3 contrasts**. The verdict is driven by the family-wise result.

## 6. Benchmark coverage, in one table

Authoritative definitions: [`COVERAGE_MANIFEST.md`](COVERAGE_MANIFEST.md). Counts:
[`EXPERIMENT_ACCOUNTING.md`](EXPERIMENT_ACCOUNTING.md).

| benchmark / universe | eligible | executed | coverage | status |
|---|---:|---:|---:|---|
| **LongMemEval-V2 — screened design** (what the paper reports) | 1,157 | 1,157 | **100%** | **DONE** |
| LongMemEval-V2 — frozen 8-task pairing universe | 15,112 | 574 | 3.8% | partial |
| LongMemEval-V2 — representation sub-universe (285 × 3) | 855 | 847 | 99.1% | 8 structured write failures |
| LongMemEval-V2 — LLM-judged stratum | 156 q | 0 | 0% | **eligible, not excluded**, blocked on F_judge |
| **SciCode** (lexical relatedness) | 154 | 154 | **100%** | **DONE** — raw-only in the release |
| **SWE-bench Verified** (runnable universe) | 107 | **107** | **100%** | ✅ **COMPLETE** at `bd25ad4` — remaining 0; 37 valid completed + 70 excluded with reasons |

🔴 **LongMemEval has TWO universes and neither percentage alone is honest.** The screened
design is a **re-pairing**, not a subset: B ∩ A = **102**, B \ A = **1,055** (re-derived).
Always name the universe.

## 7. Result artifacts and where they live

`results/**` is gitignored **except `results/ledgers/**`**. Full row files exist **on this
laptop only**; clone-reproducible slim slices are under `results/ledgers/repro/` with
sha256 in `MANIFEST.json`.

| run | path | cells | real calls | tracked? |
|---|---|---:|---:|---|
| **screened main** | `results/deltau_screened/cells.jsonl` (2,599 rows) + `analysis/k3_screened_analysis.json`, `k4_tables.md` | 1,157 | 5,198 | slim slice |
| representation scale-up | `results/repr_scaleup/cells.jsonl`, `memories.jsonl`, `analysis/r3_representation_analysis.json`, `write_summary.json`, `eval_summary.json` | 562 | 2,248 reads + 120 writes = **2,368** | 🔴 **no — see §9** |
| drift probes | `results/repr_scaleup/cross_session_probe.json` (12), `raw_resample.json` (100) | — | 112 | no |
| **reader transfer (Gemma)** | `results/gemma_reader/transfer_cells.jsonl` | 847 | 3,294 | `results/ledgers/repro/gemma_reader/` |
| **session-matched raw** | `results/raw_session_matched/raw_{gemma,gptoss}.jsonl` | 285 each | 1,110 + 1,138 | `results/ledgers/repro/raw_session_matched/` |
| writer × reader factorial | `results/writer_factorial/factorial_cells_{gemma,gptoss}.jsonl` | 562 each × 2 readers | 8,860 + 120 writes | summaries + controls |
| unscreened arm 1 (pilot) | `results/deltau_pilot/cells.jsonl` | 480 | 1,918 | slim slice |
| unscreened arm 2 (official prompt) | `results/deltau_official/cells.jsonl` | 480 | 1,920 | slim slice |
| SciCode scale-up | `results/scicode/scaleup_all3.json`; recovery `results/scicode/memories.jsonl` | 154 pairs | 924 arm-runs | `results/ledgers/repro/scicode/` |
| SWE-bench repr v2 / sympy | `results/swebench/representations_v2.json`, `representations_sympy.json`, `representations_analysis.json` | 96 / 33 | 128 / 42 | `results/ledgers/repro/swebench/` |
| SWE-bench gates | `results/swebench/parity_v2.json`, `floor_pilot.json`, `scorer_control*.json` | 14 / 10 | 28 / 20 | floor pilot **tracked** |
| cross-benchmark floor | `results/ledgers/repro/cross_benchmark_without_arm_floor.json` | — | — | **tracked** |
| reader diagnostic | `results/j2_escalation/needle_summary.json` + `results/ledgers/j2*.json` | — | ~516 | ledgers only |
| design manifest | `data/manifests/k1_screened_cells.jsonl` (1,157 rows) | — | — | **tracked** |
| bearing structure | `data/manifests/lmev2_leakage_small.jsonl` | — | — | **tracked** |
| frozen pairing universe | `data/manifests/lmev2_pairs_small_seed20261008.jsonl` (15,112) | — | — | **tracked** |
| SWE-bench pairs | `data/manifests/swebench_pairs_file_seed20261008.jsonl` | — | — | **tracked** |
| **repro slices + sha256** | `results/ledgers/repro/` + `MANIFEST.json` | — | — | **tracked** |

### Caches

| cache | calls | note |
|---|---:|---|
| `results/deltau_screened/cache.jsonl` | 5,198 | 🔴 readable only by the **pre-`5330158` 12-field key shape** |
| `results/writer_factorial/factorial_cache.jsonl` | 8,860 | 13-field key incl. `context_sha256` |
| `results/gemma_reader/transfer_cache.jsonl` | 3,294 | `.PRE_TRUNCATION_FIX.jsonl` (642) is a **snapshot copy**, not extra calls |
| `results/raw_session_matched/raw_{gptoss,gemma}_cache.jsonl` | 1,138 / 1,110 | the canonical session-matched arms |
| `results/raw_session_matched_VOID_mislabelled/` | 1,201 | 🔴 **VOID** (defect #27). Kept so it cannot re-circulate |

**Cache separation across readers is proven behaviourally**, not assumed:
`results/gemma_reader/cache_separation_proof.json`, `VERDICT: CACHE_SEPARATION_PROVEN`.

## 8. Scripts — what to run

| script | what |
|---|---|
| `scripts/audit_claims.py` | **218 checks in 21 sections; proven able to fail.** Run before any manuscript edit |
| `scripts/make_figures.py` | recomputes every figure/caption number → `overleaf/figdata.tex`; **exits non-zero if it disagrees with the audit** |
| `scripts/count_experiment_accounting.py` | regenerates every number in `EXPERIMENT_ACCOUNTING.md` |
| `scripts/verify_figure_guards.py` | plants each forbidden figure claim and asserts the guard FAILS |
| `scripts/k1_build_screened_design.py` → `k2_run_screened.py` → `k3_analyze_screened.py` → `k4_report_tables.py` | the screened main run |
| `scripts/r1_write_representations.py` → `r2_run_representations.py` → `r3_analyze_representations.py`, `r2b_raw_resample.py` | the representation scale-up |
| `gemma_reader_run.py` → `gemma_reader_analyze.py` → `gemma_reader_report.py`, `gemma_reader_controls.py` | the reader-transfer arm |
| `raw_session_matched_analysis.py` | the **canonical** session-matched raw contrast |
| `w1_write_gemma_memories.py` → `w2_run_factorial.py` → `w3_analyze_factorial.py` → `w4…w7` | the writer × reader factorial |
| `scicode_pilot.py`, `scicode_to_schema.py`, `scicode_recover_memories.py`, `scicode_controls.py` | SciCode |
| `swebench_representations.py`, `swebench_analyze_representations.py`, `swebench_multirepo_analysis.py`, `swebench_scorer_control.py`, `swebench_floor_pilot.py`, `src/p1mem/adapters/swebench.py` | SWE-bench (**SA-SWE-FINAL owns**) |
| `scripts/export_hf.py`, `scripts/migrate_schema_v2.py` | release (**SA-HF owns**) |
| `scripts/audit_leakage.py`, `probe_determinism.py`, `probe_gemma.py`, `scripts/j2_escalate_reader.py`, `scripts/run_deltau_pilot.py`, `scripts/h_compare_prompt_arms.py` | audits, probes, earlier arms |

### Re-runnable commands

```bash
# the canonical session-matched raw reader contrast
/Users/bellayang/miniconda3/bin/python3 scripts/gemma_reader_run.py \
  --reader-arm gptoss_metis --representations raw --out-dir results/raw_session_matched
/Users/bellayang/miniconda3/bin/python3 scripts/gemma_reader_run.py \
  --reader-arm gemma_metis  --representations raw --out-dir results/raw_session_matched
/Users/bellayang/miniconda3/bin/python3 scripts/raw_session_matched_analysis.py

# SciCode, whole eligible pool (--tasks-per-memory 99 makes sampling INERT; max pool is 17)
/Users/bellayang/miniconda3/bin/python3 scripts/scicode_pilot.py \
  --n-cells 999 --tasks-per-memory 99 --relatedness lexical \
  --representations raw,summary,structured \
  --workdir /tmp/sci_harness/scaleup --out results/scicode/scaleup_all3.json

# SWE-bench representation arm  (SA-SWE-FINAL owns this; coordinate before running)
/Users/bellayang/miniconda3/bin/python3 scripts/swebench_representations.py \
  --cells 32 --out results/swebench/representations_v2.json
/Users/bellayang/miniconda3/bin/python3 scripts/swebench_analyze_representations.py \
  --src results/swebench/representations_v2.json \
  --out results/swebench/representations_v2_analysis.json
```

**Every run on this project executed on this laptop against the ALCF gateway.** No batch or
cluster job is queued. Aurora is allocated but **gateway-bound and unused**.

**Liveness for endpoint-bound work:** `lsof -p <pid> | grep -c ESTABLISHED` → expect the
bound concurrency (16). 🔴 **CPU% near zero is NOT a stall**, and **stdout is
block-buffered — an empty log is NOT a stall either** (`logs/scicode_scaleup.log`,
`logs/swebench_repr2.log` are the precedents). Every runner is **idempotent through its
response cache**: if one dies, re-issue the same command.

## 9. Running right now, and what is next

| what | owner | state |
|---|---|---|
| HF **v0.3** then **v0.4** releases | **SA-HF** | **DONE** — both tags published and verified on the downloaded bytes |
| `main.tex` page-budget edits | **SA-PAGE** | **RUNNING** |
| new SWE-bench cells + `COVERAGE_MANIFEST` §3 | **SA-SWE-FINAL** | ✅ **coverage COMPLETE** at `bd25ad4` — 107/107, remaining 0 |
| standing claim/evidence audit | **SA-FINAL-AUDIT** | **RUNNING** |

**No endpoint-bound measurement job of SA-ARCHIVE's is in flight.**

### Open, submission-critical

`MASTER_TODO.md` is authoritative. Still open: **P1-C17** final manuscript sync,
**P1-C13** figures/tables placement, **P1-C16** standing audit, **P1-C03** frontier figure,
**P1-I11** (🔴 **the representation scale-up's row files are still untracked** — Contribution
B's evidence base exists on this laptop only; the ΔU arms got slim slices, the repr arm did
not), **P1-I13** the efficiency ratios in `main.tex`.

## 10. 🔴 KNOWN TRAPS — a successor must not repeat these

### The joins

1. **`memory_id` is a per-representation CONTENT HASH.** Join on **`memory_unit_locator`**.
   This has produced a silent zero **three** times.
2. **`condition_id` EMBEDS the representation name** (`lmev2_summary_..._v1`). Including it
   in a join key returns **ZERO rows** — and an empty join was once read as "not measurable".
   Correct key: `(memory_unit_locator, future_task_id)` → 285/285.
3. **`cell_id` is also a content hash and CAN collide.** Gemma compressed two different
   3,979-token segments to byte-identical 68-token summaries, so 283 ids cover 285 cells
   (defect #26). **Always positive-control a join before believing its null.**

### The models

4. **`gpt-oss-120b` is deterministic WITHIN a session, NOT ACROSS.** 554 of 1,124
   byte-identical WITHOUT-arm requests returned different text in a later session
   (reward differs on 82; mean change −0.0303). **Compare only session-matched arms**
   (defect #25). Gemma: 0/1,124 — stable across sessions. The earlier 09-29→09-30 probe
   agrees: text differs on **53%** of rows, reward on **2.46%**, and it is **mean-preserving**
   on a 100-cell resample (0.3100 → 0.3100, 7 up / 7 down). A cache-disabled probe settles
   it as a **serving change**, not sampling noise: same-minute repeats 6/6 identical,
   reproducing 09-30 6/6 and 09-29 2/6. **Every cross-day comparison carries a per-cell
   noise term a same-session one would not.**
5. **Temperature 0 is not a persistence strategy.** Any arm that discards model-written
   text is **unrecoverable** (defect #22). SciCode's summary/structured memory text is gone
   for this reason — `scicode_pilot.py` recorded `response_chars` and discarded `content`,
   with no `cache=` — and its rewards remain valid.
6. **Advertised ≠ live.** Four endpoints were advertised and dead in one day. Prove every
   model dependency with a real POST **and a negative control**.
7. **`reasoning_effort` is inert on Gemma and Gemma reports no reasoning tokens.** A zero in
   that column is an **absence**, not a measurement. Cost is **not poolable across models**.
8. **Throughput is prompt-length dependent** — 341/min at 4k is ~106/min at 24k.

### The instruments

9. **Exit code 0 is not success.** A stage crashed while its script returned 0.
10. **A zero from `.get(default)` is not a measurement.** This project's most common defect.
11. **A guard only observed passing is not known to fail.** One printed a correct verdict —
    "0 of 0" — from a key that does not exist. **Positive-control every null.**
12. **Pooled rates hide the structure that matters.** Split before quoting.
13. **Matching counts are not corroboration.** Two 35s named different sets (overlap 25).
14. **`ok=True` did not mean the writer finished.** 7 truncated summaries were admitted.
15. **Malformed-JSON rates need two denominators:** 3/60 over all structured writes,
    **0/57** over writes that finished, 3/3 over writes that hit the cap.
16. **Unapplicable edits must be `reward: None`, never `0.0`.** On SWE-bench, scoring the
    three WITH-arm apply failures as zeros would have shown memory *harming*.
17. **A pytest collection error is not a wrong answer** (defect #21). `score_patched_file`
    returned `0.0` whenever F2P was not ok, **ignoring `n_status_lines`** — the field that
    exists precisely to separate *tests ran and failed* from *tests never ran*. 37 arm-reads
    carried a manufactured `0.0`, now `None` with detail prefixed `UNSCORABLE`; matched n
    fell 17 → 15. **Quote the corrected numbers.**
18. **A post-hoc restriction is not a result.** The 0.2424 flip rate conditions on an outcome.

### The release

19. **An absolute `/Users/<name>/` path de-anonymises, and a credential scanner is blind to
    it** (defect #23). 9 tracked ledger files once carried 15 such paths, one inside
    `results/ledgers/repro/` — the tree `README.md` points reviewers at. `audit_claims.py`
    now scans for this and the scan is proven non-vacuous.
20. **`export_hf.py` does NOT migrate schemas.** The ledgers are **v1/v2** and it needs
    **v3**. Migrate first.
21. **HF `auth-check` returns 200 for repos you cannot write.** Only an empty-body commit
    POST discriminates (400 vs 403).
22. **SWE-bench declares NO licence.** Metrics + instance ids ONLY; the exporter must call
    `assert_content_redistributable`. Enforced in
    `p1mem.schema.CONTENT_EMBARGOED_BENCHMARKS` with 4 tests; findings in
    `docs/BENCHMARK_LICENSES.md` §5.
23. **🔴 NEVER `git add -A`** — and **that rule alone is NOT sufficient.** Concurrent
    agents have already swept each other's in-progress files into the wrong commit, in
    both directions. 🔴 **New, found by SA-ARCHIVE 2026-10-01 by hitting it:** staging an
    explicit path is **not enough**, because `git commit` commits the **entire index**,
    not what you just staged. I ran `git add README.md` and the resulting commit carried
    **23 files and 29,075 insertions** — all of SA-SWE-FINAL's staged SWE-bench work,
    under my commit message. *The index is shared state between agents; your `git add` is
    an append to it, not a declaration of what the commit contains.*

    **The safe form is a pathspec-limited commit, which ignores the rest of the index:**

    ```bash
    git commit -F <msgfile> -- path/one path/two     # ONLY these paths
    git show --stat HEAD                              # then VERIFY, every time
    ```

    `git show --stat` is what caught it. **Run it after every commit**, and if the stat
    shows files you did not write: `git reset --soft HEAD~1` (which preserves the other
    agent's staging) and re-commit with `--`.

### The numbers

24. **`F_empty` is `null`, not 0.000.** Both `01_noise_floors.json` artifacts carry
    `point: null` with flag `WITHOUT_ARM_REUSED:254 group(s)` — the WITHOUT arm was
    cache-served, so its spread is zero **by construction**. Report **UNMEASURED**. Same
    rule as the robust−naive gap (`ROBUST_NAIVE_GAP_STATUS = NOT_MEASURABLE`).
25. **Never quote a variance / interaction share.** The fit is unidentified; the audit fails
    if one appears.
26. **"Inversion" is forbidden** for the SciCode/LongMemEval difference. Two guards enforce
    it, both verified by planting the sentence. Permitted: *"the point-estimate ordering
    differs across benchmarks."*
27. **Do not quote the withdrawn "120 units / 6.4%" embedding figure** — it was computed
    against the withdrawn **3,400**-token cap, which failed 10/10 on real text. The adopted
    2,000-token budget gives **29 units / 1.5%**.
28. **SWE-bench has no WITHOUT-arm floor, by design.** The WITHOUT call is issued once per
    cell and shared, so the term cancels exactly. `make_figures.py` **fails the build** if
    that number is emitted beside the two measured floors.
29. **Figure 5 plots contrasts, not per-representation ΔU.** The benchmarks have different
    execution floors; the contrast differences them out. Do not add a raw-ΔU bar chart.
30. **`tasks_per_memory=4` on SWE-bench is binding and must not be relaxed in place.**
    Relaxing grows pairs 406→**552** but the *runnable* universe only 107→117 (**+10, not
    +146** — quoting +146 as available work overstates it 14×). Worse, `select_cells` dedups
    by recipient first-wins over locator-sorted order, so newly admitted earlier donors
    **displace incumbents**: 26 django recipients change donor and **13 are among the
    already-executed cells** — they would silently become different cells under the same
    `task_id`. *A subset at one stage becomes a re-pairing at the next.* Any uncapped
    universe needs a **new pre-committed manifest under a new filename**.
31. `datascience_collab` expired **2026-10-01**; use AuroraGPT.

Full evidence base: [`DEFECT_REGISTER.md`](DEFECT_REGISTER.md).

## 11. Invalid, void and superseded — kept, never quoted

| run / claim | verdict |
|---|---|
| `results/raw_session_matched_VOID_mislabelled/` (570 rows, 1,201 calls) | 🔴 **VOID** (defect #27): a hardcoded `CONDITION_ID` labelled gpt-oss rows `gemma4_31B`. The runner's own gate caught it (`VERDICT: RUN_FAILED`) |
| cross-session reader transfer **+0.1268** | ⚠️ **SUPERSEDED** by the session-matched +0.0982. History, never the lead |
| the "about half the gain is a weaker reader" decomposition | 🔴 **WITHDRAWN** — inflated ~2× by the session confound |
| SWE-bench repr **v1** (`results/swebench/representations_v1.json`, 190 arm-runs) | ⚠️ **SUPERSEDED by v2** — v1's contagion screen misfired on `+---+` **ASCII table borders in the issue text**. The screen was wrong, not the defanging |
| SWE-bench floor pilot **#1** (`results/swebench/floor_pilot.json`, 20 arm-runs, `scripts/swebench_floor_pilot.py`) | ❌ **VOID, and SA-N said so unprompted** — the model saw only the first 90 lines of each file and 4 of 5 gold patches edit code outside that window, so `search_miss` was the only reachable outcome. Numbers kept, not deleted |
| SWE-bench floor pilot #2 | ⚠️ **stopped at the gate, not cleared** (57.1% > ~50%). The later 32-cell presence pilot cleared at **37.5%** [22.9, 54.8], ΔU not significant (exact p=0.125) |
| `results/runs/noise_floor/` | ❌ **superseded** — one arbitrary memory per task, 2/92 |
| representation pilot (n=8) | ⚠️ **superseded for every rate**; keep only its compression ratios |
| both unscreened arms | ⚠️ **valid but floor-limited** (~78.5% / 83.75%). Dilution comparator, never the effect |
| the official-prompt "fix" | ❌ **refuted its own hypothesis** — accuracy fell **5.7 pts** because 128 correct guesses became abstentions and the harness scores an abstention as wrong (McNemar p = 1.12e-9). **Do not re-run another prompt wording** |
| "variance shares all 0.0000" | 🔴 **RETRACTED — never measured.** A `ZeroDivisionError` crashed the stage *while the script exited 0*, and `.get(c, 0.0)` over the empty dict produced a plausible zero. The reporter now prints UNMEASURED and a test forbids a number from a failed fit |
| variance decomposition (all attempts) | ❌ **unidentifiable**; cause is `F_exec = 0` |
| semantic-type axis | ❌ **killed** — κ = 0.000, the native pass labelled all 8 segments `episodic` |
| `Mistral-Large-3-675B`, `gpt-oss-120b` on Minerva, Sophia's embedding model | ❌ **advertised but dead** (404 / 503 / 502) |

## 12. Known gaps, stated so they are not rediscovered

- **No F_exec for SWE-bench, in either repo.** The WITHOUT arm is byte-identical across all
  three representations (11/11 sympy, 32/32 django), so the design contains no A/A
  replicate. Fixing this needs a deliberate replicate arm, not another repo.
- **SciCode memory text was never persisted** and is **not recoverable**: regeneration vs
  the server's recorded `prompt_tokens` matches 154/154 raw, **5/154 summary, 0/154
  structured**, and the 5 sit at the measured coincidence null. A **persistence** gap, never
  to be conflated with the SWE-bench licence embargo.
- **SciCode's `dep OR lex` union would add +10 eligible pairs** (164 vs 154). Unexecuted.
- **F_judge = 0/240 is endpoint determinism, not rubric robustness** (temp 1.0 gives 8/8
  distinct texts). Honest statement: **≤1.5% for this judge under greedy decoding**.
- **64 SFS SWE-bench pairs sit in 6 repos with no runner**; sphinx (37, pure Python) is the
  cheapest unlock. 12 are genuinely blocked by C builds on arm64.
- **The cross-session floor has never been measured** as its own quantity.
- **Per-cell reader agreement is weak**: restricted to cells non-zero under either reader,
  raw Pearson r falls to 0.2129 (n=109) and structured to −0.0699 (n=35). The readers agree
  on **ordering and direction**, not cell by cell. Reported as a limitation.

## 13. Verification posture

- `scripts/audit_claims.py` — **129 PASS/FAIL checks across 16 sections**, re-derived from
  tracked artifacts, **proven able to fail** (a single flipped reward trips four checks;
  each new guard is verified by planting the defect it forbids and watching it FAIL).
- **638 tests pass** under the 3.13 interpreter.
- `scripts/make_figures.py` independently recomputes every figure number and **exits
  non-zero if it disagrees with the audit**.
- Guard inventory, each verified by planting its defect: `audit_claims.py` (SciCode
  "inversion" wording; absolute-path identity scan; both printed CIs), `make_figures.py`
  (SciCode verdict and intervals, SWE-bench verdict and intervals, SWE-bench acquiring a
  floor), `schema.py` (content-embargoed benchmarks).

---

# PART II — HISTORY

Preserved so no fact is lost. **Part I is current where these disagree.** Each block is
dated; nothing below has been edited except to mark what Part I supersedes.

## H1 — 2026-09-30 17:45 CDT (Master Agent, mid-run)

The repo was at `027be3c` / 174 commits; Overleaf at `604e2b3`. HF v0.2 was current and
v0.3/v0.4 were uncut.

**Conclusions as stated then** — all still current except where §5 above corrects them:
screen worked (0.7007 → 0.5252); paired within-memory +0.3349 over 60 memories with 35
non-zero contributors, contributors-only +0.5740; 0 sign flips / 35; bearing scarce
(165/1,889, 46 on ≥2, 23 episodes); compression destroys the effect; cost ranking reverses
once formation is charged; similarity barely predicts utility; the reader is not the
bottleneck (22/22 needle); decomposition unidentifiable because `F_exec = 0`.

**SWE-bench was not cleared:** floor pilot 4/7 = 57.1%, above the gate, from an
arm-asymmetric apply failure rather than task difficulty.

**In flight:** the SciCode representation scale-up (pid 90620, launched 17:37 CDT),
pre-committed in `SCICODE_SCALEUP_PRECOMMITMENT.md`, with `--tasks-per-memory 99` making
sampling **inert** (max pool is 17) so the design is the entire pool, not a knob tuned after
seeing the pilot direction.

**The ten original traps**, kept verbatim in substance, are traps 6, 21, 1, 11, 10, 9, 12,
13, 8 and the `datascience_collab` expiry in Part I §10.

## H2 — 2026-09-30 ~18:20 CDT (addendum 1)

**Landed:** the SciCode scale-up (154 pairs / 924 arm-runs, matched n=122, all contrasts
cross zero, `ORDERING_VERDICT: NOT_ESTABLISHED`, F_exec 0.0370 larger than the biggest
point estimate); **Figure 5 populated** at Overleaf `5bba778` with LongMemEval and SciCode
real and the SWE-bench row **visibly empty and labelled**; **SWE-bench representation arm
v1** (126 calls, 96 rep-cells, matched n=12 — later superseded); the **SWE-bench content
embargo** (`BENCHMARK_LICENSES.md` §5 + `schema.CONTENT_EMBARGOED_BENCHMARKS`, 4 tests).

**Why v2 exists.** v1's contagion screen flagged one *raw* memory as dirty. Investigated
rather than reported: the defanged patch contributed **zero** diff lines; the six offending
lines were `+---+` **ASCII table borders in the issue text**. `_is_diff_line` now excludes
table rules while still failing closed on ambiguous cases (`- item one` still counts dirty).

## H3 — 2026-09-30 ~18:45 CDT (addendum 2)

**Landed:** SWE-bench repr **v2** (128 calls, **0 dirty memories**, matched **n=13**, django
only; summary−raw −0.1538 [−0.3846, 0.0], structured−raw −0.0769 [−0.2308, 0.0], both cross
zero); **Figure 5 complete** at Overleaf `4c2832a`; the cross-benchmark floor artifact
(`results/ledgers/repro/cross_benchmark_without_arm_floor.json`: LongMemEval 7/285 = 0.0246,
SciCode 5/135 = 0.0370, SWE-bench **not measurable by design**).

### 🔴 A correction future readers must not undo

An earlier Figure 5 caption said the benchmarks have "different execution floors (0 and
0.037)". **Those were two different quantities.** LongMemEval's `F_exec` is paired
re-execution of the *same* prompt within one run; SciCode's 0.037 was the WITHOUT arm
compared *across representations*. And LongMemEval's **`F_empty` is UNMEASURED, not zero** —
`k3_screened_analysis.json` records `WITHOUT_ARM_REUSED` for 108 groups because the cache
served that arm. **A cached zero is not a measured zero.** The caption now quotes one
construction for both, emitted as macros from the floor artifact.

Two join traps were recorded here, both of which produced a confident zero: `condition_id`
embedding the representation name, and `memory_id` as a content hash. Both are Part I §10.

## H4 — 2026-10-01 ~00:30 CDT (addendum 3, the model-generalization phase)

**The reader-transfer arm:** 1,694 LongMemEval cells re-read by `gemma-4-31B-it` reusing the
gpt-oss memories, with the design invariant **verified, not assumed** — all 1,694 rows carry
`memory_text` byte-identical to the gpt-oss run (match 1694, mismatch 0, no counterpart 0),
joined on `(memory_unit_locator, future_task_id, memory_representation)`.

**The cross-session table as published then** (⚠️ **the raw row is SUPERSEDED** by the
session-matched +0.0982 in Part I §5.1; summary and structured stand):

| representation | n | ΔU gpt-oss | ΔU Gemma | paired diff | CI (task-clustered) | |
|---|---:|---:|---:|---:|---|---|
| raw | 276 | +0.1884 | +0.3152 | +0.1268 | [+0.0511, +0.2050] | excludes 0 — **SUPERSEDED** |
| summary | 274 | +0.0511 | +0.0547 | +0.0036 | [−0.0492, +0.0600] | spans 0 |
| structured | 269 | +0.0186 | +0.0297 | +0.0112 | [−0.0522, +0.0845] | spans 0 |

Sign agreement on Raw 49/50 (98%). B−MC on Raw: gpt-oss +0.3462 [+0.2210, +0.4761] → Gemma
+0.6002 [+0.4787, +0.7144]. Outcomes were pre-committed in
`READER_TRANSFER_PRECOMMITMENT.md`: *no transfer* was an equally valid result.

**SWE-bench stopped being django-only:** sympy ran clean (11 cells, arm complete under the
shipped manifest); coverage 55/107 all-django → **66/107 across two repos**. Every contrast
remains `NOT_ESTABLISHED` per-repo and pooled — **the django-only criticism is answered on
coverage grounds, not on power.**

**Two corrections a successor must not reverse** (both now Part I §10): defect 21, the
pytest collection error scored as a wrong answer (37 arm-reads, matched n 17 → 15); and
sympy's scorer control being **8/8, not 20/20** — the 20/20 is the union with django's 12/12,
which is what the gate reads, because the default `--scorer-control` list names both files.

**`tasks_per_memory=4` — investigated, deliberately NOT changed.** Now Part I §10 trap 30.

## H5 — 2026-10-01 ~03:35 CDT (session-scope sweep)

The reader-transfer result was marked **PROVISIONAL at every site**, then **confirmed** by
the session-matched re-run and the flags lifted (`e77c56b` → `25960a9` → `9cdf532`).

**Defect #25** established that `gpt-oss-120b` is deterministic within a session and not
across one. **Defect #27** voided 570 mislabelled rows. **Defect #28** showed that the
reader-transfer arm had compared two readers executed in different sessions and that no
document said so — the published WITHOUT-arm decomposition rested on a baseline shift that
is **half the day**. Settled by the session-matched re-run: WITHOUT splits **−0.0327 session
/ −0.0364 reader**, and ΔU still rises **+0.0982**. **The headline survives; only its
decomposition was inflated**, by about 2×. **Defect #29**: the fix for #25 reproduced #23 by
writing an absolute `/Users/<name>/` path into git-tracked `results/ledgers/`; re-scanning
found 9 tracked files already carrying 15 such paths, one inside `results/ledgers/repro/`.

## H6 — 2026-10-01 12:21 CDT (scope freeze)

`docs/SCOPE_FREEZE.md` froze the scientific scope: the question, the five axes, the seven
results the paper is written around, and the rule that only **completion, validation,
repair of an invalid run, or a validity-critical gap** may still be run. Deferred rather
than killed: additional benchmarks, Jev, learned gate, RL memory manager, new retrieval
architectures, semantic-type redesign, new representation families, any backbone beyond
gpt-oss-120b and gemma-4-31B-it. Five sub-agents were dispatched against that freeze.


---

## 🔴 OVERLEAF GIT ACCESS IS DOWN — mirrored to GitHub 2026-10-02

> **The Overleaf remote is temporarily unavailable. No manuscript content is
> lost.**

`git push` **and** `git fetch` to
`git.overleaf.com/6abbde4a9eb777031afef068` both return `no git access`.
Fetch failing too means this is the remote (account/Premium access), not the
stored token.

| | |
|---|---|
| local Overleaf clone | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` |
| local Overleaf commit | **`a320c74`** — "Story 1 support: a screen that never sees gold finds the same effect" |
| ahead of the server by | **1 commit** (server is at `650a911`) |
| GitHub mirror | **[`paper/`](../paper/)** — self-contained and standalone-compilable |
| GitHub commit holding it | **`6ef8f1e`** |
| flat backup | `../overleaf_backup/` (main.tex, figdata.tex, main.pdf, p1refs.bib) |
| build status | ✅ 11 pages, 0 undefined control sequences / citations / references |

**Independently verified**, not assumed: `paper/` was copied to a scratch
directory and built there with no access to the overleaf tree. Its rendered
text is **byte-identical** to the Overleaf copy's own PDF (65,268 characters).

### What has NOT reached the Overleaf server

Exactly one commit, `a320c74`: the gold-free screen integrated as Story 1
support — the 15.6% → 50.0% result on cells the gold screen never selected,
both screens reported, and the both-arms-fail diagnostic that settles which to
believe. Everything earlier is on the server.

### ⚠️ When access returns

> **Do not re-apply already integrated manuscript edits.** Push and reconcile
> the existing local canonical commit instead.

The content is already in `../overleaf/main.tex`. Check with
`grep -c 'never sees the gold answer' main.tex` → expect **1**. Then:

1. `cd ../overleaf && git fetch origin`
2. reconcile only if the remote moved (it should not have)
3. `git push origin main`
4. fresh-clone the project elsewhere, compile it, and verify title, tables,
   figures and `ARTIFACT_LOOKUP.md` against `paper/`

🔴 **Do not create a replacement Overleaf project, change the remote, or
overwrite history.** The existing project is the target.

**This is a tooling outage, not a scientific blocker.** Every number in the
unpushed commit is generated from a tracked artifact here, so the manuscript is
reconstructible from `scripts/make_figures.py` + `figdata.tex` even if both
local copies were lost.

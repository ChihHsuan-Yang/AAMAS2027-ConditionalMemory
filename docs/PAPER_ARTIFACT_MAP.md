# Paper → Artifact Map

**Paper:** *What Is This Memory Useful For? Measuring Task-Conditioned Utility in
Long-Term Agent Memory* (AAMAS 2027 submission).
**Written 2026-10-01 by SA-PROVENANCE.** Companion: [`TRACE_AVAILABILITY.md`](TRACE_AVAILABILITY.md).

> **What this file is for.** Take any figure, table, claim, benchmark or dataset row in
> the manuscript and find the code and data behind it without reading chat history.
>
> **Every path in this file was `stat`ed on 2026-10-01.** 60 of 60 exist. A path that
> 404s is a defect — report it rather than working around it. A path you did not stat
> is not a path.
>
> **No number here may be quoted without re-deriving it.** Two independent re-derivers
> exist and both are proven able to fail:
> `/Users/bellayang/miniconda3/bin/python3 scripts/make_figures.py` (writes
> `overleaf/figdata.tex`, 455 lines, exits non-zero on disagreement) and
> `scripts/audit_claims.py` (218 checks). Re-run of `make_figures.py` on 2026-10-01
> left `overleaf/figdata.tex` **byte-identical** to the committed copy (`git status`
> clean), so the committed macros are current.

### Repository roots

| | |
|---|---|
| code + data | `/Users/bellayang/Documents/2026/p1_memory_utility/repo` — `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` |
| manuscript | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` — `git.overleaf.com/6abbde4a9eb777031afef068` |
| dataset | `AgentsSci/AAMAS2027-ConditionalMemory` (**private**) — tags `v0.1-lmev2-derived`, `v0.2-repr-derived`, `v0.3-scicode-derived`, `v0.4-swebench-metrics` |
| python | `/Users/bellayang/miniconda3/bin/python3` (3.13) |

All repo-relative paths below are relative to the code repo root. Figure and table
numbers are the **rendered** numbers, read from `overleaf/main.aux`, not guessed from
source order.

---

## (a) Figure lookup — all six figures

| Paper item | Scientific purpose | Generator | Canonical input artifact | GitHub result path | HF tag / subset | Notes |
|---|---|---|---|---|---|---|
| **Figure 1** `fig:pipeline` (p.3, `main.tex:349–429`) | Split write-time (task-blind) from read-time so the leakage invariant is *visual*; annotate "identical controlled filler in both arms" at the WITH/WITHOUT fork; put cost on the same row as the utility it paid for | **none** — hand-drawn TikZ inline in `main.tex`. Carries no measured number, so nothing for `audit_claims.py` to re-derive | **none** (schematic) | — | — | The protocol it draws is implemented by `src/p1mem/memory/segment.py` (4 writer-blindness barriers), `src/p1mem/cells.py` (paired arms, filler), `src/p1mem/runner.py`. Do not add a number to this figure |
| **Figure 2** `fig:bearing` (p.6, `main.tex:878–961`) | (a) a memory bears on a median of **one** future task → caps the reversal denominator; (b) reversals sit where the pairing is meaningless — BEARING's Wilson interval lies entirely below RANDOM's | `scripts/make_figures.py::bearing_breadth()` (L62) and `::flips_by_stratum()` (L107) → `\bear*`, `\flip*` macros in `overleaf/figdata.tex`; TikZ consumes them | (a) `data/manifests/lmev2_leakage_small.jsonl` **+ `/tmp/lmev2/questions.jsonl`** (see 🔴 below); (b) `results/ledgers/repro/screened_cells_slim.jsonl`; basis pin `results/ledgers/k1_screened_design.json` | all three **tracked** in git | LongMemEval-V2 rows, every tag (the `benchmark` value is `longmemeval_v2`, **not** `lmev2`) | 🔴 **Panel (a) cannot be regenerated from a clone.** `make_figures.py:32` hard-codes `QUESTIONS = Path("/tmp/lmev2/questions.jsonl")` and `sys.exit`s if absent. See §(d) and `TRACE_AVAILABILITY.md` §5 |
| **Figure 3** `fig:sparsity` (p.7, `main.tex:1067–1129`) | The paper's **central claim** drawn at cell level: one square per measured cell; utility is sparse over future tasks and the sparsity is structured by stratum | `scripts/make_figures.py::sparsity_map()` (L149) → `\sp*` macros | `results/ledgers/repro/screened_cells_slim.jsonl` (1,157 cells, `raw` only, one reader) | **tracked** | LongMemEval-V2 `raw` rows, any tag ≥ v0.1 | 🔴 **This figure is in NEITHER `FIGURE_INDEX.md` NOR `RESULT_INDEX.md`** — grep for `sparsity` returns 0 in both (positive control: `bearing` returns 3, `frontier` returns 2). Newly recorded here. Four binding design constraints are in the generator docstring: three-valued ΔU asserted, unmeasured slots drawn as nothing, measured zero drawn as a light square, row sort disclosed |
| **Figure 4** `fig:similarity` (p.7, `main.tex:1200–1256`) | (a) mean ΔU by similarity sextile, **two series** — the second excludes BEARING cells so the pooled trend does not credit the embedding with the content screen's work; (b) mean ΔU by stratum | `scripts/make_figures.py::similarity_vs_bearing()` (L356) → `\sim*`, `\strat*` macros | `results/ledgers/repro/screened_cells_slim.jsonl`; per-row embeddings `results/deltau_screened/embeddings.jsonl` | slim **tracked**; `embeddings.jsonl` **local-only** | LongMemEval-V2 `semantic_similarity` + `memory_embedding_reference` fields, any tag | **Do not "simplify" to one series.** BEARING cells concentrate in high-similarity bins (54 of 139 top sextile vs 5 bottom); the generator *asserts* that concentration so the confound cannot vanish quietly. Similarity is computed on a truncated prefix for 98.5% of units → the relationship is attenuated and the plot is a **lower bound** (`docs/EMBEDDING_LIMITATION.md`) |
| **Figure 5** `fig:frontier` (p.8, `main.tex:1295–1391`) | ΔU against exposed tokens per representation under **two cost accountings**; the visual form of the cost reversal. Efficiency is the **slope from the origin**, so it is not a separate number and cannot drift from the plotted point | `scripts/make_figures.py::frontier()` (L436) → `\fr*` macros | `results/deltau_screened/cells.jsonl`, `results/repr_scaleup/cells.jsonl`, `results/repr_scaleup/memories.jsonl`, `results/repr_scaleup/analysis/r3_representation_analysis.json` | 🔴 **all four local-only** (`results/**` is gitignored except `results/ledgers/**`) | LongMemEval-V2 `raw`/`summary`/`structured` rows, tag ≥ **v0.2** | **One basis**: both axes over the same 277 cells / 57 memories, using the *paired within-memory* estimand (+0.3174), never the unpaired BEARING mean (+0.3453) — mixing them would place a y from one estimand over an x from another. Raw must not move between panels (it makes zero extraction calls); asserted **exactly**, not to a tolerance. The formation constant has **two bases** (57-over-277 here vs `REPRESENTATION_RESULT.md`'s 60-over-285/277) and both are asserted so the wrong one cannot be substituted |
| **Figure 6** `fig:readertransfer` (p.9, `main.tex:1516–1601`) | The Raw memory effect survives a **second reader** (Gemma), with both readers re-executed **in one session** so the session/reader confound is not in the quoted number | `scripts/make_figures.py::reader_session_matched()` (L1006) for panel (a)+(b); `::reader_generalization()` (L751) for the cross-session comparator | `results/ledgers/repro/raw_session_matched/raw_gptoss_slim.jsonl`, `..._gemma_slim.jsonl`, `..._analysis.json`; comparator `results/ledgers/repro/gemma_reader/transfer_cells_slim.jsonl`, `results/ledgers/gemma_reader/reader_transfer_analysis.json` | **all five tracked** | ✅ **ON HF from v0.5** (`v0.5-reader-generalization`): the full 570+570 session-matched rows ship as `results/raw_session_matched/raw_gptoss.jsonl` + `raw_gemma.jsonl`, filter `condition_id LIKE 'lmev2_raw_metis_%_readertransfer_v1'`. 🔴 **This cell read "NOT ON HF. No Gemma row is in any tag" through v0.4, and it was true**: `reader_model` was `gpt-oss-120b` on 5,924/5,924, so this figure's evidence base was in the paper and absent from the release. v0.5 carries **2,818** Gemma reader rows | **Join key is the whole difficulty**: only `(memory_unit_locator, future_task_id, memory_representation)` crosses readers. `memory_id` is a per-representation content hash → joins to nothing; `condition_id` embeds representation AND reader → zero rows. Both wrong joins are **run and asserted to return zero**, so the non-empty matched set is evidence the key is right. Unit trap: 275 cells / 550 **replicate rows** / 123 tasks are three different units |

---

## (b) Table lookup — all three tables, with the exact universe and unit

### Table 1 `tab:coverage` — Coverage (p.4, `main.tex:674–698`)

| | |
|---|---|
| **Purpose** | Show each result's coverage **on the universe it is reported over**, and make `eligible = completed + excluded` a check the build can fail |
| **Generator** | `scripts/make_figures.py::coverage()` (L1253) → `\cov*` macros. Every term is counted **from its own source**; deriving any from the others was found **vacuous** by planting a changed eligible count |
| **Values (re-derived 2026-10-01)** | LongMemEval-V2 1,157 / 1,157 / 0 / 100.0% · SciCode 462 / 391 / 71 / 84.6% · SWE-bench 321 / 141 / 180 / 43.9% |

**UNIT per row — these are three different objects and the row labels do not say so:**

| row | **unit** | **exact universe** | counted from |
|---|---|---|---|
| LongMemEval-V2 | **(memory, task) cell**, `raw` only, one representation | the **screened design** (BEARING 139 + MATCHED_CONTROL 146 + RANDOM 872 = 1,157). 🔴 **Not** the 15,112-pair frozen grid; B ∩ A = 102, B \ A = 1,055 — the screened design is a **re-pairing**, not a sample | eligible ← `data/manifests/k1_screened_cells.jsonl`; attempted/completed ← `results/deltau_screened/cells.jsonl`; design pin ← `results/ledgers/k1_screened_design.json` |
| SciCode | **(memory, task, representation) rep-cell** | 154 lexical pairs × 3 representations = **462** | eligible ← `results/scicode/scaleup_all3.json` `design.n_pairs`; completed ← `results/ledgers/repro/scicode/scaleup_analysis.json` `per_representation_interpretable` (127+134+130=391); excluded ← counted from the arm-run rows |
| SWE-bench | **(memory, task, representation) rep-cell** | **321** = sum of `len(cells)` over the four source artifacts (`representations_sympy.json` 33 + `representations_v2.json` 96 + `representations_v3_django_a.json` 96 + `representations_v3_django_b.json` 96) | `results/ledgers/repro/swebench/representations_multirepo_final.json` `pooled` |

**Verified against `docs/COVERAGE_MANIFEST.md`:**

| manifest says | table says | reconciliation |
|---|---|---|
| LongMemEval 1,157 eligible / 1,157 executed / 100% (Universe B) | 1,157 / 1,157 / 100.0% | ✅ **agrees exactly** |
| SciCode "154 (lexical), 154 executed, 100%" **and** §"EXECUTION coverage is 462 cells" | **462** eligible, 391 completed, **84.6%** | ✅ consistent, **different unit**: the manifest's 100% is over *pairs*, the table's 84.6% is over *rep-cells*. 🔴 The manifest's §1/§4 summary table reports the pair unit and the table reports the rep-cell unit; a reader comparing "100%" to "84.6%" will think one is wrong. Both are true of different objects |
| SWE-bench 107 eligible / 107 attempted / **37 valid completed** / 70 excluded (**recipient** unit) | **321** / **141** / 180 (**rep-cell** unit) | ✅ consistent, **different unit**. 107 recipients × 3 representations = 321 rep-cells. 🔴 **The numbers 321, 141 and 180 appear NOWHERE in `COVERAGE_MANIFEST.md`** — grep returns 0 for each (positive control: `107` returns 6). The manifest and the paper table share no figure for this row |

🔴 **`37` vs `40` for SWE-bench, both correct, different definitions.**
`results/swebench/coverage_table_final.json` `TOTAL.VALID_COMPLETED` = **37** (django 34 + sympy 3);
`results/swebench/representations_multirepo_final.json` `pooled.MATCHED_CELL_SET_N` = **40** (django 37 + sympy 3).
The difference is **3 django cells sitting on instances the scorer is not known to discriminate on** (73/96 django instances pass gold→1.0 ∧ base→0.0). Every contrast is unchanged whether the 3 are kept or dropped. **Table 3 uses 40.**

### Table 2 `tab:screened` — Screened run (p.6, `main.tex:1014–1038`)

| | |
|---|---|
| **Purpose** | Both-arms-fail and mean ΔU per stratum, with the two unscreened arms as comparators. The "materially reduced" criterion (BEARING Wilson **upper** bound below the comparator's **point** estimate) was fixed in code before these numbers existed |
| **UNIT** | **cell** (memory, task), `raw`, 2 replicates averaged |
| **EXACT UNIVERSE** | the same 1,157 screened cells as Table 1, split BEARING 139 / MATCHED_CONTROL 146 / RANDOM 872. **All three strata contain the identical 60 memories**, so the contrast is paired within memory. Comparator rows: pilot 479 cells, official-prompt 480 cells — **different runs, not subsets** |
| **Generator / inputs** | both-arms-fail and Wilson columns typed, re-derived by `scripts/audit_claims.py` from `results/deltau_screened/cells.jsonl`; **mean ΔU column reads generated macros** `\stratBearV` / `\stratCtrlV` / `\stratRandV` from `scripts/make_figures.py::similarity_vs_bearing()`. Analysis-side rendering: `results/deltau_screened/analysis/k4_tables.md` (tracked copy `results/ledgers/repro/k4_tables.md`), written by `scripts/k4_report_tables.py` |
| **Stopping rule** | `results/deltau_screened/analysis/k3_screened_analysis.json` → `STOPPING_RULE`; tracked copy `results/ledgers/repro/k3_screened_analysis.json` |
| **HF** | LongMemEval-V2 `raw` rows, `bearing_label` ∈ {BEARING, MATCHED_CONTROL, RANDOM}, any tag |

🔴 **The bearing screen is gold-conditioned.** The discriminative detector reads the
**gold answer** (`docs/BEARING_SCREEN_DISCLOSURE.md`). "Content-only" meant *no model
output and no reward enter the screen* — strata are **not outcome-selected** — but they
**are** selected on answer-containment. This is a **measurement instrument, not a
deployable retrieval policy**. The non-triviality check is that 54% of bearing cells
still fail with the memory present (WITHOUT 48/417 = 11.5% → WITH 192/417 = 46.0%).
🔴 **`tab:flips` NO LONGER EXISTS** — removed 2026-09-30 as a duplicate display of the
sparsity evidence. `FIGURE_INDEX.md` still lists it as ✅ DONE; that row is stale.

### Table 3 `tab:crossbench` — Paired representation contrast (p.8, `main.tex:1459–1490`)

| | |
|---|---|
| **Purpose** | The **one quantity the three benchmarks define identically**: ΔU under one representation minus ΔU under Raw, **per cell** on the same memory and task. Contrasts rather than per-representation ΔU, because each benchmark carries its own no-memory-arm nondeterminism and a paired contrast differences that term out |
| **UNIT** | **(memory, task) cell**, paired across representations. Intervals are **task-clustered**, not cell-level |
| **Generator** | `scripts/make_figures.py::crossbench()` (L572) → `\xb*` macros |

| row | **exact universe** | canonical input | n |
|---|---|---|---|
| LongMemEval-V2 | the 277 design cells present in **all three** representations, over 57 memories | `results/repr_scaleup/analysis/r3_representation_analysis.json` | **277** |
| SciCode | the **122** cells interpretable under all three representations (per-representation denominators 127/134/130 differ because the *harness* errors on different cells; a mean over those would compare different cells) | `results/ledgers/repro/scicode/scaleup_analysis.json` | **122** |
| SWE-bench | the **40** matched cells, interpretable under all three representations, defect-21 corrected, **two repos** (django 37 + sympy 3) | `results/ledgers/repro/swebench/representations_multirepo_final.json` → `pooled` | **40** |

✅ **Verified: the SWE-bench row points at the FINAL artifact, n=40, django 37 + sympy 3
— not the older n=15.** Re-derived from the artifact: `pooled.MATCHED_CELL_SET_N` = 40,
`cells_per_repo` = {django/django: 37, sympy/sympy: 3}, and `figdata.tex` carries
`\xbSRSwN{40}`. The generator's own expectation comment records that the pre-scale-up
values (129 rep-cells, 56 completed, matched 15) **failed loudly** when it was repointed
at the final file, which is what they are for.

🔴 **The pooled SWE-bench number is dominated by one repo**: the artifact's own
`_composition_sentence` says django supplies **92.5%** of the 40 cells.

**The floor clause in the caption**: `\xbFloorLmK/\xbFloorLmN` = 7/285 = 0.0246 and
`\xbFloorScK/\xbFloorScN` = 5/135 = 0.0370, from
`results/ledgers/repro/cross_benchmark_without_arm_floor.json`. 🔴 **SWE-bench has no
such floor and a 0 would be an artefact**: the runner issues the WITHOUT call **once per
cell** and reuses it across representations by design, so the term cancels exactly. The
artifact records `rate: null` with that reason, and `make_figures.py` fails the build if
SWE-bench ever acquires a WITHOUT-arm floor.

**Caption guards the generator enforces**: the build FAILS if any SciCode or SWE-bench
interval stops crossing zero, if either `ORDERING_VERDICT` changes from
`NOT_ESTABLISHED`, or if the defect-21 correction is reverted.

---

## (c) Memory construction, per benchmark

### 1. LongMemEval-V2

| | |
|---|---|
| **Source trajectory location** | `/tmp/lmev2/trajectories.jsonl` (1.20 GB), `/tmp/lmev2/haystacks/`, questions `/tmp/lmev2/questions.jsonl`. 🔴 **UNTRACKED, outside the repo, in shared `/tmp`** — see §(d) and `TRACE_AVAILABILITY.md` §5. Integrity: `/tmp/lmev2/checksums.sha256`; `questions.jsonl` re-verified 2026-10-01 → `0a3ae5eb…92b7`, **matches** |
| **Segmentation code** | `src/p1mem/memory/segment.py::segment_page_visits()`, driven by `src/p1mem/adapters/lmev2.py`; entry point `scripts/build_lmev2_units.py --root /tmp/lmev2 --tier small --seed 20261008` |
| **Memory unit definition** | **PAGE VISIT** — the maximal run of consecutive trajectory states sharing one `state["url"]`. The boundary is drawn by the *past agent's own navigation*: `segment_page_visits()` takes a trajectory **and nothing else**, so it is structurally incapable of seeing a future task. **1,889 units** (enterprise 1,024 + web 865) over 200 trajectories / 5,095 states. Median 7,261 Qwen tokens; median 1 state; header duplication +3.44%. ⚠️ **23 of 1,889 (1.2%) are their whole trajectory** — ablating one removes a whole past episode, a categorically different intervention |
| **Raw writer** | `src/p1mem/memory/representations.py::RawExtractiveWriter` (L280). **Deterministic, zero model calls** — the memory text IS the source span verbatim. `memory_writer_model = memory_writer_cluster = "none:deterministic_span"`, `memory_writer_prompt_version = "raw_whole_segment@1.0.0"`, `compression_ratio = 1.0` **by construction** |
| **Summary writer** | `representations.py::SummaryWriter` (L444), prompt `configs/prompts/summary_v1.txt`. Measured on disk: `gpt-oss-120b`, prompt version **`summary_v1@1.0.0+6ee16b28b818`**, 60 memories |
| **Structured writer** | `representations.py::StructuredWriter` (L557), prompt `configs/prompts/structured_v1.txt` (general) or `structured_procedural_v1.txt`; keys `STRUCTURED_KEYS` (L101) / `STRUCTURED_PROCEDURAL_KEYS` (L104); JSON extraction `_extract_json_object` (L467), validation `validate_structured` (L513), rendering `render_structured` (L546). Measured: `gpt-oss-120b`, **`structured_v1@1.0.0+163d4cd3eb70`**, 60 memories |
| **Lineage fields** | `MemoryRecord` (`representations.py:125`): `representation`, `ok`, `memory_text`, `segment_id`, `source_episode_id`, `memory_content_id`, `source_span`, `writer_model`, `writer_cluster`, `prompt_version`, `extraction_calls`, `extraction_latency_s`, `extraction_{input,output,reasoning}_tokens`, `retry_count`, `cache_hit`, `memory_tokens`, `source_tokens`, `compression_ratio` (property), `structured`, `native_semantic_type`, `raw_model_output`, **`finish_reason`**, `truncated` (property), `error_code`, `error_detail`, `written_at_utc`. 🔴 `extraction_* = None` means **NO CALL WAS MADE**; `0` means a call was made and the server reported zero. Different facts. 🔴 `finish_reason` exists because a summary truncated mid-sentence comes back **non-empty**, passes the only validity test, and is written `ok=True` — **7 of 60 summaries** did exactly that. It deliberately does **not** change `ok` |
| **Where source segment boundaries are stored** | per-memory: `MemoryRecord.source_span` → schema field `memory_source_span` (`{trajectory_id, start_state_index, end_state_index, n_states}`); corpus-level: `data/manifests/lmev2_memory_units_small.jsonl` (1.58 MB, **tracked**) with per-unit token counts `data/manifests/lmev2_memory_unit_tokens.json`; pairing `data/manifests/lmev2_pairs_small_seed20261008.jsonl` (4.55 MB, **tracked**). The segment id is a **locator** (`"013696c4:28-28"`), not stable under re-segmentation, and is **never** a cache key — `segment_content_id()` is |
| **Where generated memory text is stored** | `results/repr_scaleup/memories.jsonl` (2.30 MB, **local-only**) — 60 raw + 60 summary + 60 structured with their text, writer, prompt version and cost. Raw text is also recoverable from the trajectory + segmentation rule at zero cost |
| **Which HF rows contain it** | `benchmark == "longmemeval_v2"`: **5,643 rows** on every tag from v0.2 (`raw` 4,519 · `summary` 570 · `structured` 554), 2,679 distinct `cell_id`. `memory_text` real on **5,643/5,643**. v0.1 is `raw` only, 4,519 rows |

🔴 **The 8 missing structured cells** (554 vs 570): 3 of 60 structured writes hit the
512-token cap and returned JSON cut off mid-value. Recorded per cell, **not dropped**.

### 2. SciCode

| | |
|---|---|
| **Source / donor definition** | `src/p1mem/adapters/scicode.py::SolvedSubproblem` (L209) — one **dev** subproblem that was solved: *a reusable helper function plus its procedure*. The gold code is the helper; the step description plus scientist-written background is the procedure. Built from a dev row alone; **there is no parameter through which a future task could reach it.** Dataset `SciCode1/SciCode` @ `4510f6a6aa27c43fad7b43da2c59602a86e88480`, Apache-2.0; harness `scicode-bench/SciCode` @ `e3158ea011d4`. `ground_truth_code` exists **only in dev** → 50 donors, not 338 |
| **Recipient / future-task definition** | `scicode.py::FutureSubproblem` (L285) — a **test** problem's **first** subproblem, scored by its own SciCode test cases against the official HDF5 targets, **never** by an LLM judge (`deterministic` is always True). 0/65 step-1 tests reference a later function. Dev and test problem ids are **disjoint**, so pairing is cross-problem by construction |
| **Procedural memory construction** | `SolvedSubproblem.episode_text` (L260) is the verbatim raw span — *this rule IS the raw representation* (protocol §1A: take the whole segment, perform no selection). It is handed to a writer only through `scicode.py::to_source_segment()` (L430), which populates `SourceSegment` and so inherits all four blindness barriers. Pairing: `candidate_pairs` (L540) / `select_pairs` (L581) at `Relatedness.LEXICAL`, idf-weighted cosine, `LEXICAL_THRESHOLD = 0.0315` (the measured p95; the exact p95 is `0.03153035`, and the shipped rounding is **more** inclusive so it cannot have excluded on an outcome), seed 20261008, `min_tasks_per_memory=2` |
| **WHICH historical memory text was persisted** | 🔴 **`raw` ONLY — 154 of 462 cells.** The scale-up runner recorded `response_chars` and **discarded the content**; the client had no `cache=`. Verified: `results/scicode/scaleup_all3.json` rows carry `response_chars` and **no** `memory_text` field on 462/462 |
| **Which CANNOT be reconstructed exactly, and why** | 🔴 **The 308 `summary` + `structured` cells. Not recoverable.** Evidence `results/scicode/memory_recovery_report.json`: regeneration against the server's own recorded `prompt_tokens` matches **154/154 raw** (no call — raw IS the segment), **5/154 summary**, **0/154 structured**; the 5 sit at the measured coincidence null (~5–8%, i.e. chance). Against ground truth on disk (12 LongMemEval Summary memories whose text exists), cross-session regeneration at matched settings reproduces **0 of 12** byte-identically while the writer prompt matches **12/12** — `cross_session_reproduction_control.verdict = "REGENERATION CANNOT RECOVER PAST TEXT"`. Defect 22's companion figure is **0/8** at fully matched settings vs **3/3** within session. 🔴 **0/12 and 0/8 are different subjects on different corpora and must not be pooled into "0/20".** 🔴 **The rewards for those 308 cells remain VALID and are not retracted** — what cannot be shown is the memory whose utility they measure |
| **What is and is not released on HF** | **Released (v0.3, v0.4): 154 `raw` rows**, `benchmark == "scicode"`, `memory_text` real on 154/154, `future_task_text` real on 154/154, `license_policy = "scicode"`, `license_source_reference = "scicode:Apache-2.0"`, `text_fields_withheld = []` on 154/154. **Not released: the 308 summary/structured cells** — they are absent from the dataset entirely, not present-with-a-sentinel. On the 154 shipped rows, `output_with_memory` and `output_without_memory` carry **`__OUTPUT_NOT_RETAINED_BY_THE_RUN__`** on 154/154 — a **persistence** marker, never a licence one |

🔴 **A design property that does not survive to the analysis set.** The design is **0.0%
diagonal** (0/34 memories solo); on the matched 122-cell analysis set it is **15.2%**
(5/33 solo), because harness errors drop tasks unevenly. The diagonality claim is about
the **design** and must not be transferred to the analysis set.

### 3. SWE-bench Verified

| | |
|---|---|
| **Donor → recipient pairing** | `src/p1mem/adapters/swebench.py`: donor `SolvedIssue` (L187) = one past resolved issue + its patch; recipient `FutureIssue` (L222) = a later issue scored by its **own** `fail_to_pass` / `pass_to_pass` tests (`deterministic` always True). `candidate_pairs` (L366) / `select_pairs` (L405) at `Relatedness.FILE`, seed 20261008, **single-file gold fixes only**, temporal order enforced (0/406 violations). Manifest `data/manifests/swebench_pairs_file_seed20261008.jsonl` (**tracked**) + `..._summary.json`. Funnel: 406 pairs − 103 multi-file gold − 64 no-runner − 132 dedup-by-recipient = **107 runnable** (django 96, sympy 11); closes exactly per repo in `results/swebench/coverage_table_final.json` |
| **The localizer** | `src/p1mem/adapters/swebench_localize.py` — gold-blind top-5 region selection. `extract_query_terms` (L109) from the issue text, `candidate_regions` (L177), `_score` (L200), `localize` (L216). 🔴 **`assert_gold_blind()` (L260) and the `GoldLeakedIntoLocalizer` exception (L74) exist so the localizer provably never sees the gold patch.** `recall_at_region` (L302) measures whether the region the gold patch edits was ever shown; a miss is an **exclusion**, never a reward of 0.0 |
| **Representation creation** | `src/p1mem/adapters/swebench_prompt.py`. `render_memory` (L175) with `PatchFormat.DEFANGED` via `defang_patch` (L142), `REPRESENTATION_SEGMENT_VERSION = "swebench_segment_defanged@1.0.0"`, `to_source_segment` (L380), `memory_body_for_representation` (L408). Raw: `swebench.py::render_raw_memory` (L473), deterministic, **zero model calls**, median 637 reader tokens. Structured skeleton: `swebench.py::structured_skeleton` (L510) — the diff has real structure so the skeleton is free; only the prose fields need a call. 🔴 **Arm symmetry is asserted**: `assert_arm_symmetric` (L309) and the `ArmAsymmetry` exception (L110); `memory_contagion_risk` (L426) / `response_has_diff_contagion` (L345) screen the memory body. Prompt version `swebench_v2_symmetric` |
| **Benchmark-content licensing restriction** | 🔴 **`princeton-nlp/SWE-bench_Verified` declares NO licence** — `cardData.license` is `None`, no `license:*` tag, no statement on its card. The MIT grant covers the **harness** (`SWE-bench/SWE-bench`), **not the corpus**. **An absent licence is not a permissive licence**, and `gated: false` means fetchable, not redistributable. Ruling: `docs/BENCHMARK_LICENSES.md`, `docs/HF_RELEASE_POLICY.md` |
| **Exact derived fields that CAN be published** | Verified by downloading `v0.4-swebench-metrics` (127 rows). **Withheld on 127/127** (sentinel `__WITHHELD_SEE_LICENSE__`, and **declared** in `text_fields_withheld` on 127/127): `memory_text`, `future_task_text`, `output_with_memory`, `output_without_memory`, `source_episode_metadata` (shipped as `{"__withheld__": true, "license": "swebench_verified"}`). **Published real**: `source_episode_id` (= the instance id, e.g. `django__django-10097`), `future_task_id` (the recipient instance id), `cell_id`, `memory_id`, `memory_source_span` (`{__content_withheld__: true, fields: [problem_statement, patch], instance_id, patch_…}`), `reward_with_memory`, `reward_without_memory`, `delta_utility`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `generation_calls`, `verifier_id` (`swebench_f2p_p2p_pytest`), `verifier_version` (`swebench_harness@SWE-bench:MIT`), `license_policy`, `license_source_reference` (`swebench_verified:NO-LICENCE-DECLARED`), `reader_*`, `seed_or_sampling_config`, `provenance`, `memory_writer_*`, `reconstruction_required = true`, `schema_version`. **Null on 127/127** (never measured, not withheld): `compression_ratio`, `memory_tokens`, `semantic_similarity`, `memory_embedding_reference`, `faithfulness_*`, `context_budget`, `parent_memory_id` |

🔴 **`memory_id` on a SWE-bench row is NOT a content hash.** No unredacted ledger of that
text exists anywhere; the id is minted over the **sentinel** and identifies
`(memory_instance_id, memory_representation)`. Re-deriving it from upstream text gives a
**different** value by construction. **Join on the instance ids.** The validator reports
this per row as `id_unverifiable_withheld_input` (127 warnings) rather than passing
silently.

🔴 **The two sentinels must never be interchanged.** SciCode's
`__OUTPUT_NOT_RETAINED_BY_THE_RUN__` asserts *no text exists*; SWE-bench's
`__WITHHELD_SEE_LICENSE__` asserts *text exists and may not ship*. Writing the SciCode
sentinel on a SWE-bench row would excuse us from a restriction that does apply. **The
generic embargo gate cannot see either swap** — both read as "withheld" to a check that
only asks whether content is present. The converter's self-test plants exactly that swap
and requires the refusal.

---

## (d) Eligibility and validity, per benchmark — and what is NEVER scored as reward zero

> **The governing invariant, stated once.** A cell that produced **no evidence** carries
> `reward: None`, never `0.0`. A `0.0` means *the system was asked and got it wrong*. The
> distinction is the difference between a measurement and a manufactured harm — and it
> has already failed once in this project at scale (defect 21: **37** arm-reads carried a
> manufactured `0.0`).

### LongMemEval-V2

| rule | definition | implementation | test / guard | manifest |
|---|---|---|---|---|
| **eligible** | a `(memory, task)` cell in the frozen pairing `select_pairs(seed=20261008, tasks_per_memory=8)` → 15,112; **the reported universe** is the 1,157-cell screened re-pairing | `src/p1mem/adapters/lmev2.py::select_pairs`; `scripts/k1_build_screened_design.py` | `tests/test_cells.py`; design pin `results/ledgers/k1_screened_design.json`, asserted by `make_figures.py::coverage()` | `COVERAGE_MANIFEST.md` §1 |
| **valid / interpretable** | both arms produced a reward | `src/p1mem/runner.py`, `src/p1mem/cells.py` | `tests/test_runner.py`, `tests/test_reader_arms.py` | — |
| **excluded — no carrying unit** | 17 of 295 deterministic questions have no memory unit that carries the answer. Protocol, not outcome | `scripts/audit_leakage.py` | `tests/test_leakage.py` (17/17 detector controls pass) | `COVERAGE_MANIFEST.md` §1 exclusion ledger |
| **excluded — structured write failure** | 8 cells: 3 of 60 structured writes hit the 512-token cap → unparseable JSON → `ok=False` | `representations.py::StructuredWriter`, `validate_structured` | `tests/test_representations.py` | §1, "277 structured vs 285 raw/summary" |
| 🔴 **NEVER scored zero — unavailable scorer** | the **156 LLM-judged** questions. `FutureTask.score()` **raises** `NotImplementedError` rather than returning a default — a silent `False` would turn "cannot evaluate" into "wrong answer" for 156 of 451 questions **in every arm** | `lmev2.py:226–234`; `LLM_EVAL_FUNCTIONS` (L75) | `tests/test_lmev2_scoring.py` | §1 — "eligible for a separate scorer stratum, **not excluded**, not yet run" (blocked on measuring `F_judge`) |
| 🔴 **NEVER scored zero — endpoint error** | measured in the release: **2 rows** carry `error_code_if_any = "endpoint_error"` with `reward_with_memory`, `reward_without_memory` and `delta_utility` all **null** and `output_with_memory` null (both in the pilot condition `lmev2_raw_metis_gptoss120b_v1`, same `cell_id`) | `src/p1mem/client.py` | `tests/test_client.py` | newly recorded here |
| **malformed memory** | truncation is recorded (`finish_reason == "length"`, `MemoryRecord.truncated`) and deliberately does **not** flip `ok` — whether a truncated-but-parseable memory is admitted is an experimental decision. **7 of 60 summaries** were admitted `ok=True` while truncated | `representations.py:125–200` | `tests/test_representations.py` | `RESULT_INDEX.md` D3 |
| **leakage condition** | FLAG-NEVER-DROP. Rates are **lower bounds** (official scorer bug). Never quote the pooled rate | `src/p1mem/adapters/leakage.py`, `scripts/audit_leakage.py` | `tests/test_leakage.py`; writer blindness `tests/test_writer_blindness.py` | `docs/LEAKAGE_AUDIT.md` |
| **writer blindness** | 4 barriers: arity (`assert_writer_signature`), frozen `slots=True` dataclass, metadata denylist (`_key_is_task_shaped` → `TaskLeakageError`), single `{segment_text}` interpolation point | `src/p1mem/memory/segment.py` | `tests/test_writer_blindness.py`; runtime re-check `blindness_probe()` with its own positive control | `docs/MEMORY_PROTOCOL.md` §0 |

### SciCode

| rule | definition | implementation | test / guard | manifest |
|---|---|---|---|---|
| **eligible** | lexical relatedness ≥ 0.0315 **and** `min_tasks_per_memory = 2` → **154** pairs of 3,200 unrestricted | `scicode.py::candidate_pairs` / `select_pairs` | `tests/test_scicode_adapter.py` (45 tests, mutation-checked 4/4) | `COVERAGE_MANIFEST.md` §2 — `154 + 0 + 3,046 = 3,200` ✅ |
| **valid / interpretable** | both arms scored → per-representation 127 raw / 134 summary / 130 structured; **matched** = interpretable under all three = **122** | `scripts/scicode_pilot.py`; analysis in `results/ledgers/repro/scicode/scaleup_analysis.json` | `make_figures.py::coverage()` asserts 462/462 attempted and 391 completed | §2 |
| 🔴 **NEVER scored zero** | **`None`, never `0.0`, for an unrunnable or unparseable solution.** `0.0` is returned **only** when the code ran to an assertion failure — a real wrong answer. Error kinds `ERR_NO_CODE`, `ERR_NO_FUNCTION`, `ERR_SYNTAX`, `ERR_RUNTIME`, `ERR_TIMEOUT`, `ERR_HARNESS` all carry `reward=None`, and `ScoreResult.__post_init__` **raises** if a kind marked error carries a non-None reward | `scicode.py:656–860`, esp. L687, L705, L828–860 | `tests/test_scicode_adapter.py`; the **gold positive control** (0/15 through the adapter vs 15/15 by hand) is what caught the module-scope `datasets` import that would have made **every** score `harness_error` | §2 — "**106 of 924 arm-runs have reward None** — correctly never 0.0" |
| **excluded** | 3,046 pairs outside the lexical pool; 9 lost to `min_tasks_per_memory=2`; **71 rep-cells** unscorable at execution | as above | `make_figures.py` counts `sc_unscored` **from the rows**, not as `eligible − completed` | §2 |
| **known unexecuted eligible set** | 🔴 **+10 pairs** exist under a `dep OR lex` union (164 vs 154); 7 of the 12 dependency pairs are never admitted by lexical. **Not implemented** — recorded, not quietly absent | — | — | §2 qualification 2 |
| **leakage** | 1/3,200 full-answer leaks (dev 19.1 and test 65.1 both define `tensor`), **flagged not dropped**, detector proven to fire on that real positive and stay silent on a real negative. `mentions_answer_name` (18/3,200) and the numeric detector (542/850) are reported separately and **excluded from `any_leak`** | `scripts/scicode_controls.py` → `results/ledgers/repro/scicode/controls.json` | the clean-leakage control **fired and the control was wrong, not the detector** | `SCICODE_RESULT.md` §6 |
| 🔴 **void-invalid for publication** | the 308 summary/structured cells: **rewards valid, memory text unrecoverable**. Never imply the text is recoverable | `scripts/scicode_recover_memories.py` → `results/scicode/memory_recovery_report.json` | positive control present, with an **honest limit**: a one-character change is **not** reliably detected (0/4 one-char perturbations move the token count); false-match null 0/3,003 | §2, "EXECUTION 462 / EXPORTABLE 154" |

### SWE-bench Verified

| rule | definition | implementation | test / guard | manifest |
|---|---|---|---|---|
| **eligible** | runnable recipient: single-file gold fix, repo has a working runner, deduped by recipient → **107** (django 96 + sympy 11); as rep-cells, **321** | `swebench.py::select_pairs`; `scripts/swebench_coverage_table.py` | `tests/test_swebench_adapter.py` (31 tests), `tests/test_swebench_harness.py` | `COVERAGE_MANIFEST.md` §3 funnel, closes per repo |
| **valid completed** | interpretable under **all three** representations — *stricter* than the per-representation denominators, by design. **37** recipients (`coverage_table_final.json`) / **40** matched rep-cells (`representations_multirepo_final.json`) | `scripts/swebench_multirepo_analysis.py` | identity asserted per repo (`identity_holds: true` on all 8 repos) | §3 |
| **excluded — localizer miss** | the region the gold patch edits was never shown: **39** recipients (django 33 + sympy 6). Retrieval exclusion, **not** a wrong answer | `swebench_localize.py::recall_at_region` | `assert_gold_blind()`, `GoldLeakedIntoLocalizer` | §3 exclusion ledger |
| 🔴 **excluded — unapplicable edit, NEVER 0.0** | the SEARCH/REPLACE edit did not apply, or the completion truncated: **20** recipients. `score_patched_file` **is only ever called when an edit APPLIED**; an unapplicable edit is `reward: None` at the caller and **never reaches a scorer**, because a `0.0` there would manufacture a harmful memory out of an edit-format artefact | `swebench.py::apply_edits` (L562), `swebench_harness.py:312–320` | `tests/test_swebench_harness.py` | §3 |
| 🔴 **excluded — test-collection failure / no verdict, NEVER 0.0** | `n_status_lines == 0` means **no verdict was printed at all** (import error, collection error, missing test id). `score_patched_file` returns `None` with `"UNSCORABLE no F2P verdict printed"` / `"…no P2P verdict…"`. **This is defect 21**: the field was computed, written into the detail string, and then **ignored** by the `if not f2p.ok` branch, so **27 django + 10 sympy = 37 arm-reads carried a manufactured 0.0** | `swebench_harness.py::django_status_ok` (L132), `TestOutcome.n_status_lines` (L94), `score_patched_file` (L342, L352) | `scripts/swebench_coverage_table.py:180–201` **plants a `status_lines=0` cell and requires the verdict to flip**; `_SL0` regex L57 | §3; correction block in `representations_multirepo_final.json` → `defect21_manufactured_zero_correction` (37 demoted, django 27 / sympy 10), re-verified **independently of the converter's own count**: 37 moved, **179 real rewards unchanged** |
| 🔴 **excluded — scorer invalidity** | ran but the instrument is not known to discriminate there: **10** recipients. Separately, **the django scorer discriminates on only 73 of 96 instances** (gold→1.0 ∧ base→0.0); sympy is 11/11. On the other 23, a model scoring 0.0 cannot be read as "the fix was wrong" | `scripts/swebench_scorer_control.py` → `results/swebench/scorer_control_django_ext.json`, `scorer_control_sympy_ext.json` | all 12 originally shipped control instances **reproduced exactly**, so this is added resolution, not a contradiction. The frozen gate still reads 20/20 and the extended artifact is deliberately **not** wired in as a gate | §3 |
| **excluded — memory contagion-dirty** | the memory body failed the contagion screen: **1** recipient (sympy); 2 sympy **cells** upstream, which is why the HF raw column is 41 and not 43 | `swebench_prompt.py::memory_contagion_risk` (L426), `response_has_diff_contagion` (L345) | `tests/test_swebench_prompt.py` | §3 |
| 🔴 **negative control, corrected** | re-running the negative control under the **fixed** scorer flips **6 of 20** shipped instances from `corrupt→0.0` to `corrupt→None`: the old artifact recorded "no verdict" as "the corruption was detected". The control was partly passing **on the very defect it exists to catch**. Honest counts: django **38/73**, sympy **6/11** corruptions provably detected; **zero** corruptions scored 1.0 in either repo | `scripts/swebench_scorer_control.py` | — | §3 |
| 🔴 **no `F_exec`** | the WITHOUT arm is **byte-identical across the three representations** (96/96 django, 11/11 sympy, one prompt sha each), so the design has **no A/A replicate**. An execution-noise floor of 0 would be an artefact. Running every eligible cell does **not** create a replicate the design never had | by construction in the runner | `cross_benchmark_without_arm_floor.json` records `rate: null` with that reason, and `make_figures.py` **fails the build** if SWE-bench acquires a floor | §3 "What coverage does NOT buy" |
| **floor gate, unmet** | `results/swebench/floor_pilot.json`: both-arms-fail 4/7 = 57.1%, above the ~50% gate, caused by **arm-asymmetric apply failure** (WITHOUT 7/7 applicable, WITH 4/7). Binding at the time; superseded by the symmetric `swebench_v2_symmetric` prompt | `scripts/swebench_floor_pilot.py` | 0 of 20 arm-results scored an apply failure as zero (verified) | `docs/BENCHMARK_C_DECISION.md` §5 |

---

## Navigation

| | |
|---|---|
| trace & reproducibility audit | [`TRACE_AVAILABILITY.md`](TRACE_AVAILABILITY.md) |
| coverage, the authoritative universes | [`COVERAGE_MANIFEST.md`](COVERAGE_MANIFEST.md) |
| every headline result, one row each | [`RESULT_INDEX.md`](RESULT_INDEX.md) |
| figure decisions and the generator contract | [`FIGURE_INDEX.md`](FIGURE_INDEX.md), [`FIGURE_PLAN.md`](FIGURE_PLAN.md) |
| published snapshots | [`DATASET_INDEX.md`](DATASET_INDEX.md), [`HF_RELEASE_POLICY.md`](HF_RELEASE_POLICY.md) |
| licences | [`BENCHMARK_LICENSES.md`](BENCHMARK_LICENSES.md) |
| defects, with the pattern list | [`DEFECT_REGISTER.md`](DEFECT_REGISTER.md) |
| current state / entry point | [`HANDOFF_CURRENT.md`](HANDOFF_CURRENT.md) |
| manuscript-side lookup | `overleaf/ARTIFACT_LOOKUP.md` |

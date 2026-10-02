# Trace Availability — can every publication-facing result be reproduced and audited?

**Written 2026-10-01 by SA-PROVENANCE.** Companion to
[`PAPER_ARTIFACT_MAP.md`](PAPER_ARTIFACT_MAP.md).

> **The question this file answers.** For every result the paper shows, which parts of
> the causal chain still exist, and *where*: the source episode, each memory
> representation's text, both arm outputs, the reward, the scorer detail, the
> model/endpoint identity, and the replicate metadata.
>
> **Gaps are recorded, never softened.** Four categories are used and they are not
> interchangeable:
>
> | code | meaning |
> |---|---|
> | **HF-priv** | in the private Hugging Face dataset `AgentsSci/AAMAS2027-ConditionalMemory` (no public tier exists) |
> | **GitHub** | tracked in `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` — a clone has it |
> | **local** | exists only on this machine. A clone does **not** have it. Sha256 pinned in `results/ledgers/repro/MANIFEST.json` where applicable |
> | 🔴 **GONE** | **unavailable forever.** Not slow, not awkward — it does not exist and cannot be made to exist |
>
> **Every path below was `stat`ed on 2026-10-01.**

---

## 1. LongMemEval-V2 — the main measurement

### 1a. The screened run (Table 2, Figures 2b, 3, 4; the headline paired effect)

| trace element | status | where |
|---|---|---|
| source episode / trajectory | **local**, ⚠️ **outside the repo** | `/tmp/lmev2/trajectories.jsonl` (1.20 GB) + `haystacks/`. See §5 |
| segment boundaries | **GitHub** | `data/manifests/lmev2_memory_units_small.jsonl`; per-row `memory_source_span` |
| Raw memory text | **HF-priv** + **local** + **regenerable** | HF `memory_text` real on 4,519/4,519 `raw` rows (v0.1+). Local `results/deltau_screened/cells.jsonl`. Raw IS the segment, so it also regenerates deterministically at zero cost from the trajectory |
| Summary text | — | not in this run (`raw` only) |
| Structured text | — | not in this run |
| WITH output | **HF-priv** + **local** | HF `output_with_memory`; local full rows |
| WITHOUT output | **HF-priv** + **local** | HF `output_without_memory`; local full rows |
| reward detail | **HF-priv** + **GitHub** | HF `reward_with_memory` / `reward_without_memory` / `delta_utility`; slim `results/ledgers/repro/screened_cells_slim.jsonl` |
| scorer detail | **HF-priv** + **GitHub** | HF `verifier_id` / `verifier_version` (`vendored@f8ba659e237c`); the scorer itself is vendored verbatim at `src/p1mem/adapters/vendor/lmev2_qa_eval_metrics.py` (upstream `2cc8c540`) |
| model / endpoint metadata | **HF-priv** + **GitHub** | HF `reader_model`, `reader_cluster`, `reader_endpoint`, `reader_endpoint_sha256` (`7e6b0a4f53fd08e0`), `reader_prompt_version`, `reader_reasoning_effort`, `seed_or_sampling_config`, `provenance.code_sha` / `config_sha256` |
| replicate metadata | **HF-priv** | `replicate_id`, `num_replicates` (2). 0/1,157 cells disagree between replicates |
| full 77-field rows | 🔴 **local only** | `results/deltau_screened/cells.jsonl` (84.9 MB) — gitignored. Clone-reproducible slice is the 20-field slim |
| embeddings | 🔴 **local only** | `results/deltau_screened/embeddings.jsonl` |
| response cache | 🔴 **local only** | `results/deltau_screened/cache.jsonl` + `cache.condition.json` |
| analysis | **GitHub** | `results/ledgers/repro/k3_screened_analysis.json`, `k4_tables.md` |

### 1b. The representation scale-up (Figure 5, Table 3 LongMemEval row)

| trace element | status | where |
|---|---|---|
| source episode | **local**, outside repo | as 1a |
| Raw memory text | **HF-priv** | `memory_text` on 4,519 raw rows |
| **Summary text** | **HF-priv** + **local** | HF: 570 rows, `memory_text` real on 570/570. Local with full writer provenance: `results/repr_scaleup/memories.jsonl` |
| **Structured text** | **HF-priv** + **local** | HF: 554 rows, real on 554/554. 🔴 **8 design cells missing** (554 vs 570): 3 of 60 structured writes hit the 512-token cap → unparseable JSON. Recorded per cell, not dropped |
| WITH / WITHOUT output | **HF-priv** + **local** | real on all 1,124 new rows |
| reward detail | **HF-priv** + **local** | — |
| faithfulness detail | **HF-priv** | `faithfulness_detail` real on 570 summary + 554 structured. 🔴 `faithfulness_check` null on **24 of 554** structured rows. Deterministic **proxy, not a judgment** — high scores are weak evidence, only low scores informative; no LLM judge was run |
| model / endpoint metadata | **HF-priv**, ⚠️ partial | 🔴 **1,124 rows carry `provenance.config_sha256 = null`** with a stated reason: the representation runner never reads `configs/endpoint_primary.json`, so no hash was measured and back-filling one would be a provenance nobody took |
| full rows (94 fields) | 🔴 **local only** | `results/repr_scaleup/cells.jsonl`, `memories.jsonl`, `write_summary.json`, `eval_summary.json`, `analysis/r3_representation_analysis.json`, `write_cache.jsonl`, `eval_cache.jsonl` |
| cross-session drift probe | 🔴 **local only** | `results/repr_scaleup/cross_session_probe.json` (12 cache-disabled calls), `raw_resample.json` (100) |

🔴 **The Raw arm and the two new arms ran on different days and the endpoint moved**
(Raw 2026-09-29, Summary/Structured 2026-09-30). A cache-disabled probe attributes the
difference to a serving change, not sampling. A same-session re-measurement reproduces
the contrast (mean reward 0.3100 → 0.3100), so the conclusion does not rest on the
cross-session join — but **every per-cell Raw-vs-new difference carries extra noise.**

### 1c. The two unscreened arms (Table 2 comparator rows)

Slim rows and summary ledgers **GitHub** (`results/ledgers/repro/pilot_cells_slim.jsonl`,
`official_cells_slim.jsonl`, `results/ledgers/g_deltau_pilot_summary.json`,
`h_*.json`); full rows and caches **local only**
(`results/deltau_pilot/cells.jsonl`, `results/deltau_official/cells.jsonl`). HF carries
both arms' rows inside the 4,519 raw rows (`condition_id`
`lmev2_raw_metis_gptoss120b_v1` and the official-prompt condition).

🔴 **2 HF rows carry `error_code_if_any = "endpoint_error"`** with
`output_with_memory`, both rewards and `delta_utility` all **null** — correctly never
scored 0.0. Both are in the pilot condition and share one `cell_id`. Newly recorded here.

### 1d. Reader transfer — Gemma (Figure 6)

| trace element | status | where |
|---|---|---|
| memory text (byte-identical to the gpt-oss run) | **GitHub** (slim) + **local** | `results/ledgers/repro/gemma_reader/transfer_cells_slim.jsonl`; identity proven on `\smIdentK/\smIdentN` joinable rows |
| WITH / WITHOUT output | **HF (session-matched)** + 🔴 local only (cross-session comparator) | ✅ The **session-matched** arms — `results/raw_session_matched/raw_gemma.jsonl`, `raw_gptoss.jsonl` (~21 MB each) — SHIP IN HF v0.5 with both output fields intact. 🔴 Still local only: the **cross-session comparator** `results/gemma_reader/transfer_cells.jsonl` (30.6 MB), `transfer_cache.jsonl` (7.0 MB) and all caches. The canonical figure rests on the published rows. |
| reward detail | **GitHub** | slim files + `results/ledgers/repro/raw_session_matched/raw_{gptoss,gemma}_slim.jsonl` |
| analysis | **GitHub** | `results/ledgers/gemma_reader/reader_transfer_analysis.json`, `reader_transfer_controls.json`, `results/ledgers/repro/gemma_reader/cache_separation_proof.json`, `results/ledgers/repro/raw_session_matched/raw_session_matched_analysis.json` |
| model / endpoint metadata | **GitHub** | `reader_model` / `reader_cluster` on every slim row; the generator **asserts** the two reader sets are disjoint |
| ✅ **HF** | **PUBLISHED at v0.5** | **`v0.5-reader-generalization` carries 2,818 `gemma-4-31B-it` reader rows**, including all 570+570 session-matched rows (`results/raw_session_matched/raw_gptoss.jsonl` + `raw_gemma.jsonl` → `condition_id LIKE 'lmev2_raw_metis_%_readertransfer_v1'`), plus the 4,496-row Writer × Reader factorial. 🔴 **This row read "ABSENT — no Gemma row is in any published tag" through v0.4 and that was TRUE**: `reader_model == "gpt-oss-120b"` on 5,924/5,924. Figure 6's evidence base was in the paper and not in the release; v0.5 exists to close exactly that. Verified on the DOWNLOADED tag. |

🔴 **A pre-truncation-fix cache and a quarantined-truncation file are kept, not
deleted** (`transfer_cache.PRE_TRUNCATION_FIX.jsonl`,
`transfer_cache_quarantined_truncations.jsonl`) — both local only.
🔴 **`results/raw_session_matched_VOID_mislabelled/`** is a retained void artifact; it is
*not* the live one. The live directory is `results/raw_session_matched/`. Retraction is
labelling, not deletion — do not read the VOID tree as current.

### 1e. Noise floors and the reader probe

| element | status | where |
|---|---|---|
| `F_exec`, `F_judge` | **GitHub** (ledger copy) | `results/ledgers/h_official_noise_floors.json`; live `results/deltau_{pilot,official}/analysis/01_noise_floors.json` **local** |
| 🔴 **`F_empty`** | **UNMEASURED, not zero** | `point: null`, flag `WITHOUT_ARM_REUSED:254 group(s)` — the arm was cached, so its spread is 0 **by construction**. Must be reported UNMEASURED |
| determinism probes | **local only** | `results/noise/determinism_probe_target_regime.json`, `determinism_probe.json`, `determinism_probe_raw.jsonl` |
| reader needle probe | **GitHub** (ledgers) + **local** (`j2_escalation/`) | `results/ledgers/j2b_needle_negative_control.json`, `j2_analysis.json`, `j1_oracle_subgroup.json`, `j1b_discriminative_oracle{,_thr8}.json`, `j3_tractable_slice.json`; `results/j2_escalation/needle_summary.json` + caches **local** |

⚠️ The needle negative control is **0-of-18-rows-of-which-17-scored**. Quote the
denominator you mean.

---

## 2. SciCode

| trace element | status | where |
|---|---|---|
| source / donor episode | **regenerable** | `SciCode1/SciCode` @ `4510f6a6aa27c43fad7b43da2c59602a86e88480`, **Apache-2.0**, public. Donor construction is deterministic: `scicode.py::build_memory_units` → `SolvedSubproblem.episode_text` |
| **Raw memory text** | **HF-priv** + regenerable | 154/154 rows, `memory_text` real. Raw IS the segment, so it reconstructs byte-identically — verified **154/154** against the server's recorded `prompt_tokens` |
| 🔴 **Summary text** | **GONE** | **Never persisted and cannot be regenerated.** Not on HF (those 308 cells are absent entirely, not sentinel-marked). Not in any local artifact as the original |
| 🔴 **Structured text** | **GONE** | same |
| 🔴 **WITH output** | **GONE** | HF ships `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` on **154/154** rows. The runner recorded `response_chars` and discarded content; the client had no `cache=` |
| 🔴 **WITHOUT output** | **GONE** | same, 154/154 |
| reward detail | **HF-priv** + **GitHub** + **local** | HF: `delta_utility` real on 127/154, null on 27; `reward_with_memory` real 135, null 19; `reward_without_memory` real 136, null 18. GitHub slice `results/ledgers/repro/scicode/scaleup_all3_slim.json`, analysis `scaleup_analysis.json`, controls `controls.json`. Full `results/scicode/scaleup_all3.json` **local** (sha in `MANIFEST.json`) |
| scorer detail | **HF-priv** | `verifier_id = "scicode_unit_tests"`, `verifier_version = "scicode_harness@e3158ea0"`; per-row error `kind` and `stderr_tail` in the local artifact |
| model / endpoint metadata | **HF-priv** | `reader_model`, `reader_endpoint_sha256`, `seed_or_sampling_config` (seed 20261008, temp 0, max_tokens 1024, effort low) |
| replicate metadata | **HF-priv** | `num_replicates = 1`. 🔴 **One replicate per cell** — LongMemEval has ≥2 (prereg A1.3) |

### 🔴 The SciCode persistence gap, stated exactly

**The Summary and Structured memory TEXT was never persisted and CANNOT be regenerated.**
Evidence `results/scicode/memory_recovery_report.json` (**local only**):

* **Cross-session reproduction at matched settings: 0/8 byte-identical. Within-session:
  3/3** (defect 22). On the independent 12-memory subject (LongMemEval Summary memories
  whose text is on disk) it is **0/12 byte-identical while the writer prompt matched
  12/12** — `verdict: "REGENERATION CANNOT RECOVER PAST TEXT"`.
* 🔴 **0/8 and 0/12 are DIFFERENT SUBJECTS on different corpora.** They corroborate each
  other *because* they were taken independently. **Never pool them into "0/20".**
* Regeneration against the server's own recorded `prompt_tokens`: raw **154/154**,
  summary **5/154**, structured **0/154**; the 5 sit at the measured coincidence null
  (~5–8%), i.e. chance. False-match null is 0/3,003 substitutions.
* The positive control carries an **honest limit**: a one-character change is **not**
  reliably detected (0/4 one-char perturbations move the token count).

🔴 **THE REWARDS FOR THOSE 308 CELLS REMAIN VALID AND ARE NOT RETRACTED.**
What is gone is the memory whose utility they measure. **Never imply the text is
recoverable.**

🔴 **A LOCAL TRAP, NEWLY RECORDED HERE.** `results/scicode/memories.jsonl` (754 KB,
**untracked, local only**) contains `memory_text` for **34 summary and 34 structured**
memories. **This text is REGENERATED, not the original.** Every row carries
`recovery.method = "regenerated_and_verified_by_prompt_tokens"` and, for the non-raw
representations, `identity_verified: false` and `safe_to_ship: false` with the reason
*"NOT RECOVERED… The regenerated text here is a PLAUSIBLE memory of the right segment,
not the one this run's rewards were measured under."* Counts re-derived 2026-10-01:
raw 34 verified/shippable; **structured 34 and summary 33 not verified and not
shippable; 1 summary `identity_verified: true` but still `safe_to_ship: false`** (it
sits at the coincidence null). **Anyone finding this file will see plausible memory text
beside valid rewards. It must never be shipped or treated as the original**, and that is
exactly why it is untracked.

**What is and is not released:** released = 154 `raw` rows, `license_policy = "scicode"`,
`license_source_reference = "scicode:Apache-2.0"`, `text_fields_withheld = []` on 154/154
(correct — SciCode withholds nothing on licence grounds). Not released = the 308
summary/structured cells, absent from the dataset.

🔴 **SciCode is therefore NOT representation-matched in the release, where LongMemEval
is.** Any cross-benchmark representation comparison must say so.

---

## 3. SWE-bench Verified

| trace element | status | where |
|---|---|---|
| 🔴 source episode / issue text | **EMBARGOED** — exists upstream, may not be redistributed | HF ships `source_episode_metadata = {"__withheld__": true, …}` and `memory_source_span = {"__content_withheld__": true, fields: [problem_statement, patch], instance_id, …}` on 127/127. The **ids** ship, so a licensee can re-fetch `princeton-nlp/SWE-bench_Verified` themselves |
| 🔴 Raw memory text | **EMBARGOED** | `__WITHHELD_SEE_LICENSE__` on 41/41 raw rows |
| 🔴 Summary text | **EMBARGOED** | `__WITHHELD_SEE_LICENSE__` on 43/43 |
| 🔴 Structured text | **EMBARGOED** | `__WITHHELD_SEE_LICENSE__` on 43/43 |
| 🔴 WITH / WITHOUT output | **EMBARGOED** | `__WITHHELD_SEE_LICENSE__` on 127/127 both fields (model output can quote the corpus) |
| reward detail | **HF-priv** + **GitHub** | HF `delta_utility` real on **76/127**, null on 51; values are exactly {−1.0, 0.0, +1.0}; **69 ties, 4 helped, 3 hurt**. GitHub: `results/swebench/representations_multirepo_final.json`, `coverage_table_final.json`, `representations_{v2,v3_django_a,v3_django_b,sympy}.json`, `floor_pilot.json`, `scorer_control_django_ext.json`, `scorer_control_sympy_ext.json` — **all tracked** (`.gitignore` explicitly un-ignores `results/swebench/*.json`) |
| scorer detail | **HF-priv** + **GitHub** | `verifier_id = "swebench_f2p_p2p_pytest"`, `verifier_version = "swebench_harness@SWE-bench:MIT"`; per-cell `test_detail` strings carrying `rc=` and `status_lines=` in the tracked artifacts |
| model / endpoint metadata | **HF-priv** + **GitHub** | HF `reader_*`, `seed_or_sampling_config` (temp 0, max_tokens 2048, effort low), `provenance.adapter_sha` / `code_sha` / `both_arms_fail`; the final artifact pins **13** protocol-identity fields with `disagreements: {}` and `poolable: true` |
| replicate metadata | 🔴 **absent by design** | `num_replicates` null, `replicate_id = 0`. **No A/A replicate exists**: the WITHOUT call is issued **once per cell** and reused across representations (verified byte-identical 96/96 django, 11/11 sympy, one prompt sha each), so `F_exec` is **NOT MEASURABLE and not zero** — a 0 would be a design artefact. `cross_benchmark_without_arm_floor.json` records `rate: null` with that reason and `make_figures.py` fails the build if the benchmark ever acquires a floor |
| memory bodies, unredacted | 🔴 **GONE** | The runner never persisted them. **No unredacted ledger of that text exists anywhere.** Consequently `memory_id` is minted over the **sentinel** and is not a content hash; re-deriving it from upstream text gives a different value **by construction**. Join on the instance ids. The validator emits `id_unverifiable_withheld_input` on 127 rows rather than passing silently |

🔴 **37 manufactured `0.0` rewards were demoted to null before export** (defect 21;
django 27 + sympy 10, touching 25 of 127 cells), verified **independently of the
converter's own count** against the untouched sources: 37 moved, **179 real rewards
unchanged**, 0 discrepancies. **No manufactured `0.0` is in the release.**

---

## 3b. What HF v0.5 added — provenance per new slice

All six files are **LongMemEval-V2** and were already schema v3, so none passed through
`migrate_schema_v2.py`. Exported by `scripts/export_hf.py` at repo commit `57b068f`.

| slice | rows | canonical artifact (generated it) | exported by | paper result it supports | canonical or diagnostic |
|---|---:|---|---|---|---|
| session-matched reader transfer, gpt-oss arm | 570 | `results/raw_session_matched/raw_gptoss.jsonl` | `scripts/export_hf.py` | **Figure 6** `fig:readertransfer` | **CANONICAL** |
| session-matched reader transfer, Gemma arm | 570 | `results/raw_session_matched/raw_gemma.jsonl` | `scripts/export_hf.py` | **Figure 6** `fig:readertransfer` | **CANONICAL** |
| Writer × Reader factorial, gpt-oss writer | 2,248 | `results/writer_factorial/factorial_cells_gptoss.jsonl` | `scripts/export_hf.py` | Story 3 support — four informative nulls | **CANONICAL** |
| Writer × Reader factorial, Gemma writer | 2,248 | `results/writer_factorial/factorial_cells_gemma.jsonl` | `scripts/export_hf.py` | Story 3 support — four informative nulls | **CANONICAL** |
| gold-free screen, **GF-LLM** | 168 | `results/deltau_goldfree_llm/cells.jsonl` | `scripts/prep_v05_inputs.py` → `scripts/export_hf.py` | Story 1 support — the screen that **survives** | **CANONICAL** |
| gold-free screen, **GF-LEX** | 656 | `results/deltau_goldfree/cells.jsonl` | `scripts/prep_v05_inputs.py` → `scripts/export_hf.py` | Story 1 support — the screen that **DISAPPEARS** | **CANONICAL** (published so the surviving screen is not selected on its outcome) |

⚠️ **`prep_v05_inputs.py` changed exactly one field** on the 824 gold-free rows:
`faithfulness_notes`, which was empty because those ledgers were written directly at v3
and so never passed through the migration step that fills it. It writes the project's
own `FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE` **only where the note's premise is verified on
the row**, asserts that `faithfulness_notes` feeds no id, and does not modify the source
ledgers. Verified post-hoc: `faithfulness_notes` is the only field that differs.

## 3c. What HF v0.6 added — the length control

**One file**, LongMemEval-V2, already schema v3. Exported by `scripts/export_hf.py`
after `scripts/prep_v06_inputs.py`.

| slice | rows | canonical artifact (generated it) | exported by | paper result it supports | canonical or diagnostic |
|---|---:|---|---|---|---|
| length control, 8 arms × 554 | **4,432** | `results/length_control/cells.jsonl` (ledger: `results/ledgers/length_control_result.json`) | `scripts/prep_v06_inputs.py` → `scripts/export_hf.py` | **Story 2, the narrowing**: verdict **O2** — at matched length the extractive and model-written arms do not separate (**+0.0519**, CI **[−0.0678, +0.1727]**), so Raw's advantage is an **exposure-budget** effect | **CANONICAL** |

🔴 **One of the eight arms is an A/A CONTROL.** `trunc_last_20000` has a 20,000-token
budget against a longest Raw memory of 19,801, so it renders **byte-identical to `raw`
on 554/554** and reproduces its reward triples and reader outputs on **552/552 scored
pairs**. It is a control with a known correct answer, **not a ninth condition** —
pooling the arms without dropping either it or `raw` double-counts Raw.

🔴 **Read `condition_id` as a MEMORY arm, never as a model.** These ids are
`lmev2_<arm>_lenctl_v1`; the arm slot names how the memory was constructed. The other
multi-arm slice (§3b's factorial) uses `w<writer>_r<reader>`, and reading one convention
under the other produced two false alarms against a correct release (`DEFECT_REGISTER`
MA-3). Verified with a checker whose positive control was proven to fire: **0** of 4,432
rows carry a `condition_id` contradicting their `reader_model` or writer.

⚠️ **`prep_v06_inputs.py` changed exactly three fields**, all on the faithfulness axis,
verified post-hoc by a field-by-field diff: `faithfulness_notes` (4,432),
`faithfulness_check` (1,084) and `faithfulness_detail` (1,108). All 4,432 rows arrived
with an EMPTY note because this ledger was written directly at v3 and so never passed
through the migration that fills a deliberately-null field's reason. The script writes
each note **only where its premise is re-derived true on the row itself** — 1,202
full-span tautology, 2,122 truncated-slice, 1,108 model-written — asserts that
`faithfulness_notes` feeds no id, and does not modify the source ledger. Four planted
premise violations are each refused and clean data is accepted unchanged.

🔴 **The 1,108 model-written rows carry the REAL write-pass score, attached rather than
pointed at.** The length-control arms reuse the frozen Summary/Structured memory text,
so `results/repr_scaleup/memories.jsonl` is the record for those exact memories. The
score reaches each row through **two independent join keys** —
`(memory_unit_locator, memory_representation)` and a sha256 of `memory_text` — verified
to select the **same** record on all 1,108, against a negative control that correctly
resolves nothing. A first attempt wrote a "not scored, see the write pass" pointer and
left the field null; the validator rejected all 1,108 with
`faithfulness_claimed_unscored_on_a_written_memory`, because a model-written memory
**is** scorable and a note denying it is false.

### Intentionally missing from v0.5, by name

| artifact | status | why |
|---|---|---|
| `results/length_control/cells.jsonl` | ✅ **SHIPPED IN v0.6** (§3c) | It was held out of **v0.5** because its rows were not in the audited set that release was gated against; its reason **changed mid-build** — scoped while running, frozen (`O2_EFFECT_DISAPPEARS_AT_MATCHED_LENGTH`, `b750518`) before upload. Named a v0.6 candidate so the exclusion would not be inherited, then **re-decided and published**. |
| `results/swebench/representations_v1.json` | **VOID** | contagion screen false-positived on ASCII table borders |
| `results/raw_session_matched_VOID_mislabelled/` | **VOID (defect 27)** | `condition_id` contradicted `reader_model`. Verified by row id: **0 of 570** reached the release |
| `results/gemma_reader/transfer_cells.jsonl` + caches | **local only** | the **cross-session** comparator, superseded for the quoted number by the session-matched arms above |
| all `*_cache.jsonl`, `embeddings.*` | **local only** | endpoint caches and embedding stores are not part of the release |

## 4. Summary — what a reader can and cannot re-do

| | LongMemEval-V2 | SciCode | SWE-bench Verified |
|---|---|---|---|
| re-score outputs under a corrected verifier | ✅ **yes** (5,641/5,643 rows carry both outputs) | 🔴 **no — GONE** | 🔴 **no — embargoed** |
| inspect the memory that produced a reward | ✅ raw/summary/structured | ⚠️ **raw only** (154 of 462 cells) | 🔴 **no** |
| reproduce the figures from a clone | ⚠️ **partly** — see §5 | ✅ via `results/ledgers/repro/scicode/` | ✅ `results/swebench/*.json` are tracked |
| audit the reward arithmetic | ✅ | ✅ | ✅ |
| audit the second reader (Figure 6) | ⚠️ GitHub slim only; **nothing on HF** | n/a | n/a |

🔴 **A manuscript claim that is false of 281 of the 5,924 shipped rows.** §Reproducibility
(`overleaf/main.tex:1723–1736`) states the released dataset carries *"full output text"*
and that *"the retention of full text rather than a digest, so every cell can be
re-scored under a corrected verifier"* is **enforced by a validator**. Re-derived on the
downloaded `v0.4-swebench-metrics`: **154 SciCode rows carry
`__OUTPUT_NOT_RETAINED_BY_THE_RUN__` on both output fields and 127 SWE-bench rows carry
`__WITHHELD_SEE_LICENSE__` on both** (plus 2 LongMemEval rows with a null WITH output
from an endpoint error) — **283 rows cannot be re-scored, 281 of them structurally.**
The sentence is true of LongMemEval-V2 and false of the other two benchmarks. Note that
the SWE-bench licence embargo *is* disclosed 1,020 lines earlier at `main.tex:698–704`,
and the SciCode persistence gap is **not disclosed anywhere in `main.tex`** (grep for
`not retained` / `withheld` / `never persisted` returns only the SWE-bench paragraph;
positive control: `SciCode` matches 13 times). **A caveat in one paragraph and not the
next reads as endorsement.** Owner: whoever owns §Reproducibility — SA-PROVENANCE does
not edit `main.tex`.

---

## 5. 🔴 The `/tmp/lmev2` hazard — a live, unmitigated reproducibility gate

**`/tmp/lmev2/questions.jsonl` is UNTRACKED, OUTSIDE THE REPO, in SHARED `/tmp`, and it
gates the bearing-scarcity numbers.**

* `scripts/make_figures.py:32` hard-codes `QUESTIONS = Path("/tmp/lmev2/questions.jsonl")`
  and `bearing_breadth()` **`sys.exit`s** without it: *"missing …: needed to exclude
  LLM-judged tasks"*. `scripts/audit_claims.py:74` reads the same path.
* It selects the **75 deterministic discriminative tasks** out of 76, which is the basis
  for Figure 2(a) — 1,889 units, 165 bearing on ≥1, 46 on ≥2, 23 episodes.
* **20 scripts** reference `/tmp/lmev2`.
* The whole tree is 1.33 GB (`trajectories.jsonl` alone 1.20 GB), which is why it is not
  in the repo.
* Integrity *is* checkable: `/tmp/lmev2/checksums.sha256` ships with the corpus and
  `lmev2.verify_checksums()` re-derives rather than trusting it. Re-verified 2026-10-01:
  `questions.jsonl` → `0a3ae5eb…92b7`, **matches**.

**Consequence: a fresh clone cannot regenerate Figure 2(a) or run the full audit.**
Everything else in `figdata.tex` comes from tracked artifacts.

🔴 **The hazard is not theoretical. A live instance occurred this session: a stray
`/tmp/bisect.py` shadowed the stdlib `bisect` module.** Shared `/tmp` is writable by any
process on the machine; a file landing there can silently change what this project's code
imports or reads. A heredoc to a fixed `/tmp` path can also no-op onto another user's
file. **`/tmp` is not storage. Treat anything read from it as unpinned unless a checksum
is verified at read time** — which `make_figures.py` does **not** currently do for
`questions.jsonl` (it only checks `.exists()`).

**Mitigations, none applied, listed so the choice is explicit:**
1. copy `questions.jsonl` (286 KB) into `data/manifests/` and track it — subject to the
   LongMemEval-V2 Apache-2.0 grant, which permits it;
2. have `make_figures.py` verify the sha256 at read time instead of `.exists()`;
3. publish the 75-task id list as a tracked derived manifest, which is the only thing the
   figure actually needs.

---

## 6. Gaps found by this audit that were NOT previously documented

| # | gap | evidence |
|---|---|---|
| **G1** | **The Reproducibility section's "full output text … every cell can be re-scored" is false for 281 of 5,924 shipped rows**, and the SciCode persistence gap appears **nowhere** in `main.tex` while the SWE-bench embargo is disclosed — a caveat beside an uncaveated neighbour | §4 above; counted on the downloaded v0.4 |
| **G2** | **`results/scicode/memories.jsonl` holds REGENERATED summary/structured text beside valid rewards**, untracked and locally indistinguishable from originals except by its own `recovery.safe_to_ship: false` flag | §2 above; 34 structured + 33 summary not verified |
| **G3** | **Figure 3 (`fig:sparsity`) is in neither `FIGURE_INDEX.md` nor `RESULT_INDEX.md`** — grep returns 0 in both (positive controls `bearing`→3, `frontier`→2) | `PAPER_ARTIFACT_MAP.md` §(a) |
| **G4** | ✅ **CLOSED 2026-10-02 by HF v0.5.** Was: *Figure 6's Gemma rows are on no HF tag; the paper's reader-generalization evidence is absent from the dataset* (`reader_model == "gpt-oss-120b"` on 5,924/5,924 of v0.4). v0.5 publishes **2,818** Gemma reader rows. Re-verified on the downloaded tag: per-reader counts are gpt-oss-120b 9,566 / gemma-4-31B-it 2,818 of 12,384 | closed against the downloaded `v0.5-reader-generalization` |
| **G5** | **`COVERAGE_MANIFEST.md` carries none of the paper coverage table's SWE-bench figures** — 321, 141 and 180 each grep to 0 (positive control `107`→6). The manifest reports the **recipient** unit, the table the **rep-cell** unit, and nothing states the conversion | `PAPER_ARTIFACT_MAP.md` §(b) |
| **G6** | ✅ **CLOSED at v0.5.** Was: *the HF data card contains zero GitHub links* — `grep -c github` on the shipped **v0.4** card returned **0**. On the downloaded **v0.5** card it returns **8** (positive control `SciCode` → 40). The links are `<anonymized-for-review>` placeholders for the double-blind cycle, which is the navigable form available now | `grep -c -i github` on the downloaded v0.5 README.md |
| **G7** | **The GitHub README has no Hugging Face URL and no Overleaf URL** — it names `AgentsSci/AAMAS2027-ConditionalMemory` and `git.overleaf.com/6abb…` as bare strings in a status table, not as links, and never links `DATASET_INDEX`/`COVERAGE_MANIFEST` from the Repository map | `README.md:111–114` |
| **G8** | **UPDATED at v0.5, and the count moved.** v0.4 had 2 rows with `error_code_if_any = "endpoint_error"`. v0.5 has **94 error-coded rows across three codes**: `truncated_nonempty_at_token_budget` **88**, `empty_output_finish_length` **4**, `endpoint_error` **2**. The 88+4 come with the new Gemma arms and are the three-observable truncation guard **working** (defect 20). 🔴 **All 94 carry a null reward and a null `delta_utility` — 0 of 94 has a number** — so no refused generation was ever scored. Documented here rather than left as an undocumented count that grew 47× | re-derived on the downloaded `v0.5-reader-generalization` |
| **G9** | **`37` vs `40` for SWE-bench are both live, both correct, and differ by definition** (valid-completed recipients vs matched rep-cells; the 3 extra sit on scorer-invalid django instances). No document stated the reconciliation | `PAPER_ARTIFACT_MAP.md` §(b) |
| **G10** | **`make_figures.py` checks only `.exists()` on `/tmp/lmev2/questions.jsonl`**, not its sha256, while the corpus ships `checksums.sha256` and the project owns `verify_checksums()` | §5 |

---

## Navigation

[`PAPER_ARTIFACT_MAP.md`](PAPER_ARTIFACT_MAP.md) ·
[`COVERAGE_MANIFEST.md`](COVERAGE_MANIFEST.md) ·
[`RESULT_INDEX.md`](RESULT_INDEX.md) ·
[`DATASET_INDEX.md`](DATASET_INDEX.md) ·
[`HF_RELEASE_POLICY.md`](HF_RELEASE_POLICY.md) ·
[`DEFECT_REGISTER.md`](DEFECT_REGISTER.md) ·
[`HANDOFF_CURRENT.md`](HANDOFF_CURRENT.md) ·
`overleaf/ARTIFACT_LOOKUP.md`

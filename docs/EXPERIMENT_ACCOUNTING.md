# Experiment accounting — the canonical count

**Built 2026-10-01 by SA-ARCHIVE.** Every number on this page was **counted from a
logged artifact** by `scripts/count_experiment_accounting.py`. Nothing is estimated.
Where a quantity genuinely cannot be counted it says **`not recoverable from logs`** —
never a plausible zero, which is this project's most common defect shape
(`docs/DEFECT_REGISTER.md` #3, #22, #23).

**Regenerate, do not hand-edit:**

```bash
/Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py
/Users/bellayang/miniconda3/bin/python3 scripts/count_experiment_accounting.py --json
```

**If this page and the script disagree, the SCRIPT is right and this page is stale.**

Counts here are **as of repo `9f835a2`** (2026-10-01 12:21 CDT). SWE-bench is owned by
**SA-SWE-FINAL** and is actively growing; its rows are a snapshot, not a frozen total.
`docs/COVERAGE_MANIFEST.md` is the authority on what *eligible* means for each benchmark;
this page counts what was *executed*.

---

## 0. The four units, and why they differ

Confusing these is the fastest way to publish a wrong total. They are not interchangeable.

| unit | definition | where counted |
|---|---|---|
| **cell** | one `(memory_unit_locator, future_task_id)` under one representation / writer / reader | distinct keys in a `cells.jsonl` |
| **row / replicate** | one scored execution of a cell. LongMemEval runs **2 replicates per cell** (285 screened cells have 3) | lines in a `cells.jsonl` |
| **arm-run** | one WITH-arm or WITHOUT-arm read. One row = two arm-runs | `generation_calls` summed over rows |
| **endpoint call** | one real HTTP POST with its own server-reported usage | lines in a `*cache*.jsonl` |

🔴 **Count cells by `(locator, task)`, never by `cell_id` or `memory_id`.** Both are
**content hashes**. On the writer-Gemma Summary arm, Gemma compressed two different
3,979-token segments to byte-identical 68-token summaries, so **283 content ids cover 285
cells** (`DEFECT_REGISTER` #26). The script prints that collision rather than hiding it.

🔴 **`condition_id` embeds the representation name** (`lmev2_summary_..._v1`). Including
it in a join key returns **zero rows**, and an empty join has already been misread once as
"not measurable".

---

## 1. Headline totals

| quantity | count | basis |
|---|---:|---|
| **real endpoint calls, all benchmarks** | **29,775** | cache rows with snapshot copies removed + SciCode arm-runs + SWE-bench arm-runs |
| cache rows on disk | 28,445 | every `results/**/*cache*.jsonl` line |
| — of which snapshot copies of the same stored call | 642 | identical `(key_hash, written_at_utc)` in two files |
| **LongMemEval real endpoint calls** | **27,803** | distinct `(key_hash, written_at_utc)` |
| distinct request keys | 25,436 | distinct `key_hash` |
| **deliberate re-runs of a byte-identical request** | **2,367** | same key, new timestamp — the session-matching work of defects #25/#28, not duplicates |
| SciCode arm-runs (no response cache kept) | 1,340 | rows in the three SciCode result JSONs |
| SWE-bench arm-runs | 632 | per-cell `arms` dicts across all seven SWE-bench artifacts |
| **approximate prompt/input tokens** | **506,881,063** | LongMemEval 501,850,560 + SciCode 2,994,651 + SWE-bench 2,035,852 |
| **approximate completion/output tokens** | **4,360,644** | LongMemEval 3,147,200 + SciCode 820,978 + SWE-bench 392,466 |
| **reasoning tokens** | **1,787,087** + not recoverable | LongMemEval 1,592,213 + SWE-bench 194,874; **SciCode: not recoverable from logs** (never recorded per row), and Gemma reports none at all — an **absence, not a zero** |
| truncations (`finish_reason == "length"`) | 130 | LongMemEval 19 + SciCode 107 + SWE-bench 4 |
| empty `finish_reason` (quarantined Gemma truncations) | 14 | 7 quarantined + their 7 copies in the pre-fix snapshot |
| calls that needed at least one retry | 47 | `retry_count > 0` in a cache row |
| **hard failures that lost a measurement** | **0** | every retried call returned content; every unscorable arm-read is `reward: None` |

**Token figures are the endpoint's own `prompt_tokens` / `completion_tokens`, summed.**
They are *approximate* for the paper's purposes in exactly one sense: they are a true sum
over stored records, and the 642 snapshot-copy rows are **included** in the per-file token
columns below (they are excluded from the call total). **Cost is never poolable across
models** — Gemma reports no reasoning tokens at all.

---

## 2. LongMemEval-V2 — by benchmark / representation / reader / writer

A **row** is a replicate; a **cell** is `(locator, task)`. Void = a row where either arm
has `reward: None` — correctly never coerced to 0.0.

| run | repr | writer | reader | cells | rows | void rows | arm-runs | pub-facing? |
|---|---|---|---|---:|---:|---:|---:|---|
| screened main | raw | deterministic | gpt-oss-120b | **1,157** | 2,599 | 0 | 5,198 | **publication** |
| repr scale-up | summary | gpt-oss-120b | gpt-oss-120b | 285 | 570 | 0 | 1,140 | **publication** |
| repr scale-up | structured | gpt-oss-120b | gpt-oss-120b | 277 | 554 | 0 | 1,108 | **publication** |
| reader transfer | raw | deterministic | gemma-4-31B-it | 285 | 570 | 18 | 1,110 | superseded for the headline (see §2.1) |
| reader transfer | summary | gpt-oss-120b | gemma-4-31B-it | 285 | 570 | 22 | 1,108 | **publication** |
| reader transfer | structured | gpt-oss-120b | gemma-4-31B-it | 277 | 554 | 16 | 1,076 | **publication** |
| **session-matched** | raw | deterministic | **gemma-4-31B-it** | **285** | 570 | 18 | 1,110 | **publication — canonical** |
| **session-matched** | raw | deterministic | **gpt-oss-120b** | **285** | 570 | 2 | 1,138 | **publication — canonical** |
| factorial W=gemma | summary | gemma-4-31B-it | gpt-oss-120b | 285 | 570 | 0 | 1,140 | **publication** |
| factorial W=gemma | summary | gemma-4-31B-it | gemma-4-31B-it | 285 | 570 | 16 | 1,108 | **publication** |
| factorial W=gemma | structured | gemma-4-31B-it | gpt-oss-120b | 277 | 554 | 0 | 1,108 | **publication** |
| factorial W=gemma | structured | gemma-4-31B-it | gemma-4-31B-it | 277 | 554 | 16 | 1,082 | **publication** |
| factorial W=gptoss | summary | gpt-oss-120b | gpt-oss-120b | 285 | 570 | 0 | 1,140 | **publication** |
| factorial W=gptoss | summary | gpt-oss-120b | gemma-4-31B-it | 285 | 570 | 22 | 1,108 | **publication** |
| factorial W=gptoss | structured | gpt-oss-120b | gpt-oss-120b | 277 | 554 | 2 | 1,106 | **publication** |
| factorial W=gptoss | structured | gpt-oss-120b | gemma-4-31B-it | 277 | 554 | 16 | 1,076 | **publication** |
| unscreened arm 1 (pilot) | raw | deterministic | gpt-oss-120b | 480 | 960 | 2 | 1,918 | comparator only |
| unscreened arm 2 (official prompt) | raw | deterministic | gpt-oss-120b | 480 | 960 | 0 | 1,920 | comparator only |
| **VOID mislabelled arm** | raw | deterministic | gpt-oss-120b | 285 | 570 | 2 | 1,138 | 🔴 **VOID — never quote** |

🔴 **The two factorial summary arms show 285 cells but only 283 distinct `cell_id`s.**
That is defect #26, not a missing pair. The script flags it on every run.

### 2.1 Canonical reader transfer

> **SESSION-MATCHED: +0.0982 [+0.0247, +0.1730], n = 550 matched cells.**
> `results/ledgers/raw_session_matched_analysis.json` · `VERDICT: SURVIVES_SESSION_MATCHING`

The **cross-session +0.1268 [+0.0511, +0.2050]** is **SUPERSEDED**. Its arms were 11 hours
apart and defect #25 makes that a real confound. It stays visible as history — *retraction
is labelling, not deletion* — but **never leads**. The 285-cell session-matched arms ran
14 minutes apart with `memory_text` byte-identical 550/550; 550 of 570 rows matched after
void exclusions.

The **WITHOUT-arm decomposition did not survive**: −0.0364 session-matched vs −0.0688
cross-session. **Do not quote "about half the gain is a weaker reader."**

### 2.2 Eligible vs attempted vs completed — the two universes

🔴 **LongMemEval has two universes and neither percentage alone is honest.** Verified by
re-deriving both from `data/manifests/lmev2_pairs_small_seed20261008.jsonl`:

| universe | eligible | attempted | completed | remaining | excluded |
|---|---:|---:|---:|---:|---:|
| **A** frozen pairing (`tasks_per_memory=8`) | **15,112** | 574 | 574 | 14,538 | 0 |
| **B** screened design — *what the paper reports* | **1,157** | **1,157** | **1,157 (100%)** | 0 | 0 |
| representation sub-universe (285 × 3) | 855 | 847 | 847 | 0 | 8 structured write failures |
| LLM-judged scorer stratum | 156 q | 0 | 0 | 156 | eligible, **not excluded**, blocked on F_judge |

**B is not a subset of A.** B ∩ A = **102**; B \ A = **1,055** (I re-derived both). The
screened design is a **re-pairing** under the content screen, not a sample of A. Always
name the universe.

Across all three raw LongMemEval arms, **1,629** distinct cells were executed, of which
**574** lie inside Universe A.

### 2.3 Endpoint calls and tokens, per cache file

One cache row = one real POST with the server's own usage. Token columns **include** the
642 snapshot-copy rows; the call total in §1 excludes them.

| cache | calls | truncations | empty finish | retried | prompt tok | completion tok | reasoning tok |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deltau_screened/cache.jsonl` | 5,198 | 0 | 0 | 1 | 92,885,375 | 495,044 | 404,393 |
| `deltau_pilot/cache.jsonl` | 1,918 | 8 | 0 | 5 | 40,574,996 | 177,826 | 143,442 |
| `deltau_official/cache.jsonl` | 1,920 | 0 | 0 | 11 | 40,728,664 | 138,006 | 110,928 |
| `repr_scaleup/eval_cache.jsonl` | 2,248 | 0 | 0 | 1 | 31,867,950 | 214,182 | 174,188 |
| `repr_scaleup/write_cache.jsonl` | 120 | **10** | 0 | 0 | 896,910 | 41,620 | 8,443 |
| `gemma_reader/transfer_cache.jsonl` | 3,294 | 0 | 0 | 14 | 61,646,093 | 407,088 | **0** |
| `gemma_reader/transfer_cache.PRE_TRUNCATION_FIX.jsonl` | 642 | 0 | 7 | 14 | 14,295,665 | 80,028 | **0** |
| `gemma_reader/transfer_cache_quarantined_truncations.jsonl` | 7 | 0 | 7 | 0 | 165,768 | 3,584 | **0** |
| `gemma_reader/smoke_cache.jsonl` | 24 | 0 | 0 | 0 | 437,552 | 2,604 | **0** |
| `gemma_reader/cache_separation_cache.jsonl` | 2 | 0 | 0 | 0 | 126 | 28 | 6 |
| `raw_session_matched/raw_gptoss_cache.jsonl` | 1,138 | 0 | 0 | 0 | 20,323,342 | 113,170 | 93,018 |
| `raw_session_matched/raw_gemma_cache.jsonl` | 1,110 | 0 | 0 | 0 | 25,244,228 | 137,090 | **0** |
| `raw_session_matched_VOID_mislabelled/raw_gptoss_cache.jsonl` | 1,138 | 0 | 0 | 0 | 20,323,342 | 113,170 | 93,018 |
| `raw_session_matched_VOID_mislabelled/raw_gemma_cache.jsonl` | 63 | 0 | 0 | 0 | 1,195,906 | 7,314 | **0** |
| `writer_factorial/factorial_cache.jsonl` | 8,860 | 0 | 0 | 0 | 136,079,985 | 973,796 | 358,330 |
| `writer_factorial/write_cache_gemma.jsonl` | 120 | 0 | 0 | 0 | 1,199,367 | 22,166 | **0** |
| `f_judge/reader_cache.jsonl` | 48 | 0 | 0 | 1 | 762,937 | 4,750 | 3,226 |
| `j2_escalation/cache.jsonl` | 396 | 0 | 0 | 0 | 8,789,983 | 181,548 | 176,795 |
| `j2_escalation/needle_cache.jsonl` | 66 | 0 | 0 | 0 | 1,606,143 | 7,224 | 6,366 |
| `j2_escalation/needle_negctrl_cache.jsonl` | 17 | 0 | 0 | 0 | 409,908 | 11,329 | 10,653 |
| `pilot_representations/cache.jsonl` | 24 | 1 | 0 | 0 | 135,852 | 5,882 | 1,351 |
| `runs/noise_floor/cache.jsonl` | 92 | 0 | 0 | 0 | 2,280,468 | 9,751 | 8,056 |
| **total rows** | **28,445** | **19** | **14** | **47** | **501,850,560** | **3,147,200** | **1,592,213** |

**A zero in the reasoning column for a Gemma file is an ABSENCE, not a measurement.**
Gemma reports no `reasoning_tokens` field at all; `reasoning_effort` is accepted but inert.

### 2.4 Failure accounting

| failure mode | count | disposition |
|---|---:|---|
| `429` / `502` / transport, retried and succeeded | 47 | not a lost measurement; content returned |
| `endpoint_error` rows (pilot) | 2 | `reward: None` both arms |
| `empty_output_finish_length` rows | **60** | Gemma transfer 56 · session-matched gpt-oss 2 · factorial gpt-oss-written/gpt-oss-read 2 |
| `truncated_nonempty_at_token_budget` rows | **88** | session-matched Gemma 18 · factorial W=gemma 32 · factorial W=gptoss 38 |
| quarantined Gemma truncations | 7 calls | isolated to their own cache file, excluded from every analysis |
| structured writes that produced malformed JSON | 3 of 60 (gpt-oss); **0 of 57** finished writes; 3 of 3 at the cap | two denominators, both reported |
| summaries truncated mid-sentence yet admitted `ok=True` | 7 of 60 | 🔴 defect #13 — `ok=True` never meant finished |
| cells excluded for a failed write | 8 | listed per cell in `eval_summary.json` |
| **unrecoverable losses** | **0** | no measurement was silently dropped |

---

## 3. SciCode

| run | pairs | arm-runs | runner `n_calls` | reward `None` | truncations | prompt tok | completion tok | pub-facing? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **scale-up (whole eligible pool)** | **154** | **924** | 992 | 106 | 72 | 2,081,498 | 563,225 | **publication (case study)** |
| pilot | 68 | 408 | 476 | 53 | 34 | 897,066 | 251,153 | superseded by the scale-up |
| smoke | — | 8 | 8 | 1 | 1 | 16,087 | 6,600 | diagnostic |

`n_calls` **exceeds** arm-runs because the runner counts writer calls too; arm-runs counts
only scored reads. **Reasoning tokens: not recoverable from logs** — never recorded per row.

| quantity | value |
|---|---:|
| eligible (lexical relatedness, ≥2 tasks/memory) | **154** |
| attempted / completed | **154 / 154 (100%)** |
| excluded from the 3,200 unrestricted pool | 3,046 |
| *sum check* | 154 + 0 + 3,046 = 3,200 ✅ |
| **executed cells** (154 × 3 representations) | **462** |
| **exportable cells** | **154** (`raw` only) |
| **not exportable** | **308** (summary 154 + structured 154) |
| matched analysis set | **122** |
| F_exec (free control, WITHOUT arm across reps) | 5/135 = **0.0370** |

🔴 **SciCode ships raw-only because the Summary/Structured memory TEXT was never
persisted.** `scicode_pilot.py` records `response_chars` and discards `content`, and
`P1Client` was built with no `cache=`. Measured, not assumed: regeneration vs the server's
recorded `prompt_tokens` matches **154/154 raw, 5/154 summary, 0/154 structured**, and the
5 sit at the measured coincidence null. **The rewards remain valid**; what cannot be shown
is the memory behind them. This is a **persistence gap**, never to be conflated with the
SWE-bench licence embargo.

🔴 **+10 eligible pairs are unexecuted.** A `dep OR lex` relatedness union yields 164
rather than 154. Not implemented, recorded as a known alternative — see
`MASTER_TODO` §POST-SUBMISSION.

🔴 **All three matched contrasts cross zero → `ORDERING_VERDICT: NOT_ESTABLISHED`.** The
word *inversion* is forbidden and two guards enforce it, both verified by planting the
sentence.

---

## 4. SWE-bench Verified

**Owned by SA-SWE-FINAL and in flux.** These are counts as of `9f835a2`; cite the artifact
and the commit, never a frozen total.

| run | cells | arm-runs | runner `n_calls` | reward `None` | localizer misses | input tok | output tok | reasoning tok | pub-facing? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| repr v2 (django) | 96 | 192 | 128 | 35 | 33 | 655,791 | 130,878 | 63,577 | **publication** |
| repr sympy | 33 | 64 | 42 | 3 | 18 | 171,900 | 27,808 | 15,247 | **publication** |
| repr v1 (django) | 96 | 190 | 126 | 30 | 33 | 644,623 | 132,151 | 64,377 | **SUPERSEDED by v2** |
| floor pilot #2 | 55 | 110 | n/r | 21 | 23 | 387,026 | 68,862 | 36,287 | gate diagnostic |
| floor pilot #1 | 10 | 20 | n/r | 6 | 3 | n/r | n/r | n/r | 🔴 **VOID** |
| parity v2 | 14 | 28 | n/r | 28 | 6 | 90,136 | 20,138 | 9,561 | harness control |
| parity v1 control | 14 | 28 | n/r | 28 | 6 | 86,376 | 12,629 | 5,825 | harness control |
| **total** | **318** | **632** | — | **151** | — | **2,035,852** | **392,466** | **194,874** |

`n/r` = **not recoverable from logs** (the earlier runners stored no `n_calls` and the floor
pilot #1 stored no per-arm token counts).

`n_calls` is **smaller** than arm-runs by design: the WITHOUT arm is issued **once per cell**
and shared across all three representations, so it cancels exactly in every paired contrast.

### Coverage ledger

| stage | pairs |
|---|---:|
| manifest pairs | 406 |
| survive `is_single_file_solvable` | 303 |
| in a repo with a working runner | 239 |
| **runnable universe** (after dedup-by-recipient) | **107** |
| **executed** | **66** (django 55 + sympy 11) |
| remaining runnable | **41** (django) |
| matched, defect-21 corrected | django 12 · sympy 3 · **pooled 15** |

🔴 **Defect 21 — a pytest collection error is not a wrong answer.** `score_patched_file`
returned `0.0` whenever F2P was not ok, ignoring `n_status_lines`. **37 arm-reads** (django
27 + sympy 10) carried a manufactured `0.0` and are now `None` with detail prefixed
`UNSCORABLE`. Matched n fell 17 → **15**. **Quote the corrected numbers.**

🔴 **`sympy`'s own scorer control is 8/8, not 20/20.** The 20/20 is the union with django's
12/12 — which is what the gate reads, because the default `--scorer-control` names both.

🔴 **No F_exec exists for SWE-bench in either repo**, by design: the WITHOUT arm is
byte-identical across representations (11/11 sympy, 32/32 django), so the design contains
no A/A replicate. A measured `0` would be an artefact. `make_figures.py` **fails the build**
if that number is ever emitted beside the two measured floors.

🔴 **`tasks_per_memory=4` is binding and must not be relaxed in place.** Relaxing grows
pairs 406→552 but the *runnable* universe only 107→117 (**+10, not +146**), and
`select_cells` dedups recipient-first over locator-sorted order, so 26 django recipients
change donor — **13 of them already executed**. Any uncapped universe needs a **new
pre-committed manifest under a new filename**.

🔴 **SWE-bench declares NO licence.** Metrics + instance ids only; enforced in
`p1mem.schema.CONTENT_EMBARGOED_BENCHMARKS` with 4 tests.

---

## 5. Diagnostic artifacts — never publication-facing

| artifact | rows | purpose |
|---|---:|---|
| `j2_escalation/responses.jsonl` | 420 | reader escalation (3 configs) |
| `j2_escalation/needle_responses.jsonl` | 66 | planted-needle probe, 22/22 recovered |
| `f_judge/judge_calls.jsonl` | 408 | F_judge measurement |
| `f_judge/judge_sensitivity_calls.jsonl` | 360 | forced-sampling margin at T=1.0 — **not F_judge** |
| `f_judge/reader_outputs.jsonl` | 48 | reader outputs for the judge stratum |
| `noise/determinism_probe_raw.jsonl` | 30 | 6 prompts × 5 repeats, cache disabled |
| `gemma_probe/liveness_probe.jsonl` | 7 | advertised ≠ live |
| `runs/noise_floor/ledger.jsonl` | 96 | ❌ **superseded** — one arbitrary memory per task, 2/92 |
| `pilot_representations/records.jsonl` | 24 | n=8 pilot — ⚠️ **superseded for every rate**; keep only compression ratios |
| `gemma_reader/smoke_cells.jsonl` | 12 | 2-cell smoke |
| `repr_scaleup/memories.jsonl` | 180 | written memories (gpt-oss) |
| `writer_factorial/memories_gemma.jsonl` | 120 | written memories (Gemma) |
| `scicode/memories.jsonl` | 102 | recovery attempt — **raw only is verified** |
| `gemma_reader/transfer_cache_quarantined_truncations.jsonl` | 7 | quarantined, excluded everywhere |

**Throughput ladders** (concurrency calibration; endpoint behaviour, never a result):

| ladder | rungs | requests | completed ok |
|---|---:|---:|---:|
| `metis_ladder_v2.jsonl` | 7 | 198 | 198 |
| `metis_ladder.jsonl` | 7 | 112 | 112 |
| `metis_confirm.jsonl` | 2 | 168 | 168 |
| `metis_high.jsonl` | 2 | 48 | 42 |
| `gemma_metis_confirm.jsonl` | 2 | 168 | 168 |
| `gemma_metis_high.jsonl` | 2 | 168 | **81** |
| `gemma_metis_ladder.jsonl` | 3 | 84 | 84 |
| `gptoss_metis_24k_control.jsonl` | 1 | 48 | 48 |

---

## 6. Invalid and void — counted, kept, never quoted

| item | rows / calls | verdict |
|---|---:|---|
| `results/raw_session_matched_VOID_mislabelled/` | 570 rows · 1,201 calls | 🔴 **VOID** (defect #27): a hardcoded `CONDITION_ID` labelled gpt-oss rows `gemma4_31B`. The runner's own gate caught it (`VERDICT: RUN_FAILED`). Kept so the numbers cannot re-circulate |
| SWE-bench floor pilot #1 | 20 arm-runs | ❌ **VOID**: the model saw only the first 90 lines; 4 of 5 gold patches edit outside that window |
| SWE-bench repr v1 | 190 arm-runs | ⚠️ **SUPERSEDED by v2** — v1's contagion screen misfired on ASCII table borders |
| `results/runs/noise_floor/` | 96 rows · 92 calls | ❌ **superseded** — one arbitrary memory per task |
| representation pilot n=8 | 24 rows · 24 calls | ⚠️ **superseded for every rate**; compression ratios only |
| both unscreened arms | 960 + 960 rows | ⚠️ **valid but floor-limited** (~78.5% / 83.75% both-arms-fail). Dilution comparator, **never the effect** |
| cross-session reader transfer +0.1268 | — | ⚠️ **SUPERSEDED** by the session-matched +0.0982. History, never the lead |
| "variance shares all 0.0000" | — | 🔴 **RETRACTED — never measured.** A `ZeroDivisionError` crashed the stage while the script exited 0 |
| `F_empty = 0.000` | — | 🔴 **UNMEASURED.** `point: null` with `WITHOUT_ARM_REUSED:254 group(s)` |
| official-prompt "fix" | 1,920 calls | ❌ **refuted its own hypothesis**: 128 correct guesses became abstentions (McNemar p = 1.12e-9). **Do not re-run another prompt wording** |

---

## 7. What cannot be counted, and why

Stated so nobody later fills these with a plausible number.

| quantity | status |
|---|---|
| SciCode reasoning tokens | **not recoverable from logs** — never recorded per row |
| Gemma reasoning tokens (any arm) | **absent by model**, not zero. `reasoning_effort` is accepted but inert |
| SciCode summary/structured memory text | **not recoverable** — `content` discarded, no cache. Rewards remain valid |
| SWE-bench floor pilot #1 token usage | **not recoverable** — the runner stored no per-arm counts |
| SWE-bench `n_calls` for the pilots and parity controls | **not recoverable** — no `summary` block |
| SWE-bench F_exec | **not measurable by design** — no A/A replicate exists |
| LongMemEval `F_empty` | **UNMEASURED** — the WITHOUT arm was cache-served in 254 groups |
| wall-clock per call | **partially recoverable** — `latency_s` is stored per cache row but is not aggregated here; it is endpoint-load dependent and not a cost figure |
| true dollar cost | **not applicable** — the ALCF gateway bills no per-token price |

---

## 8. Cross-references

| for | read |
|---|---|
| what *eligible* means per benchmark | [`COVERAGE_MANIFEST.md`](COVERAGE_MANIFEST.md) (SA-SWE-FINAL owns §3) |
| which model produced which result | [`MODEL_ARMS.md`](MODEL_ARMS.md) |
| result → artifact → script → manuscript | [`RESULT_INDEX.md`](RESULT_INDEX.md) |
| every defect behind a number here | [`DEFECT_REGISTER.md`](DEFECT_REGISTER.md) |
| the released dataset snapshots | [`DATASET_INDEX.md`](DATASET_INDEX.md) (SA-HF owns) |
| current state, paths, commands | [`HANDOFF_CURRENT.md`](HANDOFF_CURRENT.md) |

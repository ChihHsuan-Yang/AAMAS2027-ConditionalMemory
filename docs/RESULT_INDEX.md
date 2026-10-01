# Result Index — every headline result, one row each

**Created 2026-09-30 by SA-ARCHIVE.** This is a **navigation table**, not a source of
truth. Each row points at the artifact, the script that made it, the doc that rules on it,
and where it currently sits in the manuscript.

> **Standing rule.** Nothing here is a number you may quote without re-deriving it.
> `scripts/audit_claims.py` re-derives **218 checks** from tracked artifacts and is proven
> able to fail. Run it before any manuscript edit:
> `/Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py`

**Every path below was checked to exist on 2026-09-30.** A row whose path 404s is a defect;
report it rather than working around it.

**Tracking.** `results/**` is gitignored except `results/ledgers/**`. Full row files
(`results/deltau_screened/cells.jsonl`, `results/repr_scaleup/*`) exist **on this machine
only**; the clone-reproducible copies are the slim slices under `results/ledgers/repro/`,
whose sha256 is pinned in `results/ledgers/repro/MANIFEST.json`. The "tracked?" column says
which.

---

## A. Main measurement — the screened LongMemEval-V2 run

| # | Result | Benchmark | Artifact path | tracked? | Config | Generating script | Manuscript | Figure / table | Verification |
|---|---|---|---|---|---|---|---|---|---|
| **A1** | **Screened main run** — 2,599 rows / 1,157 cells, 5,198 real calls, 0 errors | LongMemEval-V2 | `results/deltau_screened/cells.jsonl` · slim: `results/ledgers/repro/screened_cells_slim.jsonl` | slim only | `p1_deltau_raw_v1`, metis/gpt-oss-120b, T=0, max_tokens 512, effort low, conc. 16 | `scripts/k2_run_screened.py` (design: `scripts/k1_build_screened_design.py`) | §Results, `\subsection{Screening the pairing makes the effect measurable}` (main.tex:1144) | Table `tab:screened` (main.tex:1155) | ✅ `audit_claims.py` §"Screened run" re-derives per-stratum both-arms-fail and mean ΔU |
| **A2** | **Stopping rule** — BEARING Wilson upper below RANDOM's point estimate; verdict `SCREEN BOUGHT MEASUREMENT CAPACITY` | LongMemEval-V2 | `results/deltau_screened/analysis/k3_screened_analysis.json` → key `STOPPING_RULE` | no (repro copy: `results/ledgers/repro/k3_screened_analysis.json`, **tracked**) | committed in code **before** the data existed | `scripts/k3_analyze_screened.py` | main.tex:1171 + the `tab:screened` caption | `tab:screened` | ✅ rule + both bounds re-derived by the audit; verdict string verified to be able to return both outcomes (`docs/RESULTS_READING_RULES.md` §1) |
| **A3** | **Paired within-memory effect** (BEARING − MATCHED_CONTROL), 60 memories, 35 non-zero contributors | LongMemEval-V2 | same as A1; analysis key `paired_within_memory.BEARING_vs_MATCHED_CONTROL` | slim tracked | all three strata are the **identical 60 memories** (verified) | `scripts/k3_analyze_screened.py` | `\paragraph{The paired effect.}` main.tex:1187 | none (in prose) | ✅ mean, contributors-only mean and contributor count re-derived by the audit. ⚠️ **CI disagreement — see §F1 below** |
| **A4** | **Scorer-composition split** of A3 (constant-mix vs changing-mix subsets) | LongMemEval-V2 | derived from A1 | — | — | Master Agent ad-hoc (no committed script) | not yet in manuscript | — | ⚠️ **NOT in `audit_claims.py`.** Cite `docs/SCREENED_RESULT.md` §4b; do not restate the split figures as re-derived |
| **A5** | **Sign reversal by stratum** — the founding-hypothesis negative | LongMemEval-V2 | same as A1; analysis key `FOUNDING_HYPOTHESIS`, table in `results/deltau_screened/analysis/k4_tables.md` §3 | slim + k4 copy tracked | flip-eligible = ≥2 cells in the stratum | `scripts/k3_analyze_screened.py`, `scripts/k4_report_tables.py` | `\subsection{The founding hypothesis is not supported}` main.tex:1093 | Table `tab:flips` (main.tex:1103) **and** Figure 2 panel (b) | ✅ eligible counts and flip counts re-derived for all three strata by the audit; Wilson bounds re-derived by `make_figures.py` |
| **A6** | **Additive-null excess is negative in every stratum** | LongMemEval-V2 | analysis key `per_stratum.<S>.additive_null`; table in `k4_tables.md` §4 | k4 copy tracked | fit `μ + a_m + b_t`, interaction removed | `scripts/k3_analyze_screened.py` | **not yet written into Results** — TODO at main.tex:1323 | — | ⚠️ **NOT in `audit_claims.py`.** Two computations disagree in magnitude, agree in sign — see §F2 and `docs/ADDITIVE_NULL_AND_DECOMPOSITION.md` §1 |
| **A7** | **Decomposition is unidentifiable** (`F_exec = 0` leaves no residual scale) | LongMemEval-V2 | analysis keys `pooled_decomposition`, `shared_grid_decomposition`; pilot/official copies in `results/*/analysis/03_variance_decomposition.json` and `results/ledgers/h_*_variance_decomposition.json` | ledger copies tracked | — | `scripts/k3_analyze_screened.py` | Limitations / Metrics — **no share is quoted anywhere** | none, **and a figure is forbidden** (`docs/FIGURE_PLAN.md`) | ✅ the audit's last check asserts the manuscript quotes **no** variance share |

## B. Structure of the corpus

| # | Result | Benchmark | Artifact path | tracked? | Config | Generating script | Manuscript | Figure / table | Verification |
|---|---|---|---|---|---|---|---|---|---|
| **B1** | **Bearing scarcity** — 165/1,889 units bear on ≥1 task; **46** on ≥2, from **23** episodes; **266** edges on the canonical 75-task basis | LongMemEval-V2 | `data/manifests/lmev2_leakage_small.jsonl` (+ `..._summary.json`); basis pin `results/ledgers/k1_screened_design.json` | **tracked** | deterministic, content-only, **0 endpoint calls**; discriminative = `1 ≤ pool_hits ≤ 8` | `scripts/audit_leakage.py`; screening in `scripts/k1_build_screened_design.py` | `\subsection{Memory--task bearing is scarce}` main.tex:1013 | **Figure 2 panel (a)** (`fig:bearing`) | ✅ discriminative task count, the 75/76 split, the ≥1 and ≥2 counts, the episode count, the 266 edges **and** the per-count histogram all re-derived by the audit, which additionally asserts the manuscript does not quote the 76-basis edge count |
| **B2** | **Leakage audit**, stratified by gold-answer length; FLAG-NEVER-DROP | LongMemEval-V2 | `data/manifests/lmev2_leakage_small_summary.json` (full 423,664-cell matrix); `data/manifests/lmev2_leakage_informative_summary.json` (145,593-cell informative strata); row-level flags in `lmev2_leakage_small.jsonl`, `lmev2_leakage_informative.jsonl`; V1 oracle `lmev1_leakage_oracle.jsonl`, `lmev1_leakage_s.jsonl` | **all tracked** | 17/17 detector controls pass; rates are **lower bounds** (official scorer bug) | `scripts/audit_leakage.py` | `\paragraph{Leakage rates are lower bounds...}` main.tex:856 | none | ⚠️ not in `audit_claims.py`; the summary JSONs carry the counts, so any quote is one division away. **Never quote the pooled rate** — see `docs/LEAKAGE_AUDIT.md` |
| **B3** | **Identifiability status**, predicted before the run | LongMemEval-V2 | `data/manifests/k1_screened_cells.jsonl` | **tracked** | — | `scripts/k1_build_screened_design.py` | Limitations | none | ✅ design facts (60 memories in all three strata, 1:1 stratum join) re-derived by the audit; the margins themselves cite `docs/IDENTIFIABILITY_STATUS.md` |

## C. What locates a useful memory

| # | Result | Benchmark | Artifact path | tracked? | Config | Generating script | Manuscript | Figure / table | Verification |
|---|---|---|---|---|---|---|---|---|---|
| **C1** | **Similarity vs utility** — cosine is nearly uninformative about ΔU; the content screen is not | LongMemEval-V2 | `results/deltau_screened/cells.jsonl` field `semantic_similarity`; embeddings `results/deltau_screened/embeddings.jsonl` | slim tracked | SFR-Embedding-Mistral dim 4096, **2,000-Qwen-token budget**, halving retry; 98.5% of units truncated | `scripts/k3_analyze_screened.py`; figure values `scripts/make_figures.py` | `\paragraph{Semantic similarity does not locate the effect.}` main.tex:1277 | **Figure 3** (`fig:similarity`) | ✅ `make_figures.py` re-derives ρ per stratum and the sextile means and exits non-zero on disagreement; `audit_claims.py` independently asserts \|ρ\| < 0.25. I re-derived ρ myself: per-cell all **+0.0868**, BEARING **+0.1644**, RANDOM **+0.0061** |
| **C2** | **Distance bands** (cosine terciles) | LongMemEval-V2 | same | slim tracked | terciles are a **per-benchmark** post-pass, not per row | `scripts/k3_analyze_screened.py` | `\paragraph{Distance bands.}` main.tex:1290 | none | ⚠️ not in `audit_claims.py`. Far-band BEARING rests on 8 cells and the manuscript already declines to read its sign |
| **C3** | **Embedding truncation limitation** | LongMemEval-V2 | per-row `memory_embedding_reference.input_truncated` / `input_token_budget`; unit tokens `data/manifests/lmev2_memory_unit_tokens.json` | manifest tracked | adopted budget **2,000 Qwen tokens** after 3,400 failed 10/10 on real text | `scripts/pilot_representations.py` probe; recorded per row by the runners | Limitations, and inside the C1 paragraph | none | ✅ ruled on in `docs/EMBEDDING_LIMITATION.md`; ⚠️ **do not quote the withdrawn "120 units / 6.4%"** — that was against the withdrawn 3,400 cap |

## D. Representation and cost — Contribution B

| # | Result | Benchmark | Artifact path | tracked? | Config | Generating script | Manuscript | Figure / table | Verification |
|---|---|---|---|---|---|---|---|---|---|
| **D1** | **Representation comparison** — compression destroys the effect. Raw's paired B−MC interval is the only one excluding zero | LongMemEval-V2 | rows `results/repr_scaleup/cells.jsonl`; written memories `results/repr_scaleup/memories.jsonl`; analysis `results/repr_scaleup/analysis/r3_representation_analysis.json`; write pass `write_summary.json`; eval pass `eval_summary.json` | **none tracked** (all under the `results/**` ignore) | 285 design cells, 60 memories, 126 tasks, 2 replicates; join key is **`memory_unit_locator`**, never `memory_id` | `scripts/r1_write_representations.py` → `scripts/r2_run_representations.py` → `scripts/r3_analyze_representations.py` | `\paragraph{Representation: compression does not preserve usefulness.}` main.tex:1297 | none yet — the frontier figure is P1-C03 | ✅ the audit re-derives the 277 shared pair keys and both efficiency columns from the row files. ⚠️ the three **paired B−MC CIs** are not in the audit; cite `docs/REPRESENTATION_RESULT.md` |
| **D2** | **Cost reversal** — the efficiency ranking inverts once formation cost is charged | LongMemEval-V2 | same as D1 | none tracked | BEARING cells, **ratio of totals**; amortized formation 1,626 tok/cell (summary), 1,715 (structured); reuse factor 4.86 | `scripts/r3_analyze_representations.py` | same paragraph, main.tex:1315–1322 | none yet (this is the frontier figure's content) | ✅ **six** audit checks re-derive both columns per representation, plus three A1.5 correctness checks (raw bit-identical, summary and structured must move) and two direction checks. I reproduced all six independently. ⚠️ **the manuscript's `5.2×` does not match — see §F3** |
| **D3** | **Write-pass instrument facts** — malformed structured JSON has two denominators; 7 truncated summaries were admitted `ok=True` | LongMemEval-V2 | `results/repr_scaleup/memories.jsonl`, `write_summary.json` | none tracked | `finish_reason == "length"`; 8 cells excluded for failed writes, listed per cell | `scripts/r1_write_representations.py` | not in the manuscript | none | ✅ three audit checks (3/60 all writes, 0/57 finished writes, 7 truncated-but-ok summaries) |
| **D4** | **Cross-session endpoint drift** — the Raw arm and the new arms were run on different days and the endpoint moved | LongMemEval-V2 | `results/repr_scaleup/cross_session_probe.json` (12 cache-disabled calls); resample `results/repr_scaleup/raw_resample.json` (100 cache-disabled calls) | none tracked | cache **disabled**, same filler, target position asserted to reproduce k2 on 100/100 | `scripts/r2b_raw_resample.py` | not in the manuscript — **it must be**, as a caveat on every Raw-vs-new comparison | none | ⚠️ not in `audit_claims.py`. Artifacts carry the counts directly; `docs/REPRESENTATION_RESULT.md` rules on the reading |
| **D5** | **Representation pilot (n=8)** — superseded by D1 | LongMemEval-V2 | `results/pilot_representations/summary.json`, `records.jsonl`; ledger copies `results/ledgers/b6_pilot_representations_summary.json`, `b6_pilot_representations_records.jsonl` | **ledger copies tracked** | 8 segments, 24 calls | `scripts/pilot_representations.py` | compression ratios (0.063 / 0.037) are quoted in Method | none | ⚠️ **SUPERSEDED for every rate.** Its "0/8 malformed" did not scale (D3). Keep it for the compression ratios only |

## E. The two unscreened arms, the reader probe, the floors, and Benchmark C

| # | Result | Benchmark | Artifact path | tracked? | Config | Generating script | Manuscript | Figure / table | Verification |
|---|---|---|---|---|---|---|---|---|---|
| **E1** | **Unscreened arm 1 — hand-written prompt** (the pilot). 1,918 calls, 479 cells, both-arms-fail 376/479 | LongMemEval-V2 | `results/deltau_pilot/cells.jsonl` · slim `results/ledgers/repro/pilot_cells_slim.jsonl` · summary `results/ledgers/g_deltau_pilot_summary.json` · analysis `results/deltau_pilot/analysis/*.json` | **slim + ledgers tracked** | `p1_deltau_raw_v1`, hand-written `cells.py::SYSTEM` | `scripts/run_deltau_pilot.py`, `scripts/g_floors_and_flips.py` | `\subsection{Unscreened pairing cannot detect a memory effect}` main.tex:1043; also the bottom rows of `tab:screened` | `tab:screened` rows "prior design, arm 1" | ✅ accuracy WITH/WITHOUT and both-arms-fail re-derived by the audit. **Valid but floor-limited** — keep as the dilution comparator, never as the effect |
| **E2** | **Unscreened arm 2 — official benchmark prompt.** 1,920 calls, 480 cells, both-arms-fail 402/480; accuracy **fell** because abstentions score as wrong | LongMemEval-V2 | `results/deltau_official/cells.jsonl` · slim `results/ledgers/repro/official_cells_slim.jsonl` · `results/ledgers/h_official_arm_run_summary.json`, `h_prompt_arm_comparison.json`, `h_paired_prompt_arm_mcnemar.json`, `h_floor_diagnosis_official.json`, `h_official_noise_floors.json` | **slim + ledgers tracked** | official `DOMAIN_SYSTEM_PROMPTS` from `/tmp/lmev2/harness.py:71`; a **new arm**, never a backfill | `scripts/k2_run_screened.py` lineage + `scripts/h_compare_prompt_arms.py`, `scripts/h_floor_diagnosis.py` | Results-plan negatives (main.tex:766); `tab:screened` row "prior design, arm 2" | `tab:screened` | ✅ accuracy and both-arms-fail re-derived by the audit. The mechanism (128 correct→abstention, McNemar p=1.12e-9) is in the ledger artifacts, **not** in the audit |
| **E3** | **Reader needle probe** — a planted per-cell code in the real ~27k context is recovered by the base config, and stronger readers add nothing | LongMemEval-V2 | `results/j2_escalation/needle_summary.json` (+ `needle_responses.jsonl`, `responses.jsonl`, `summary.json`); negative control `results/ledgers/j2b_needle_negative_control.json`; escalation `results/ledgers/j2_analysis.json`; oracle subgroup `results/ledgers/j1_oracle_subgroup.json`, `j1b_discriminative_oracle.json`, `j1b_discriminative_oracle_thr8.json`; slice `results/ledgers/j3_tractable_slice.json` | **ledgers tracked**, `j2_escalation/` not | 3 configs × 22 cells, 0 errors; negative control has **18 rows** (17 scored 0.0, 1 `None`) | `scripts/j2_escalate_reader.py`, `scripts/j2b_needle_control.py`, `scripts/j1_oracle_subgroup.py`, `scripts/j1b_discriminative_oracle.py`, `scripts/j3_tractable_slice.py` | `\subsection{The bottleneck is the pairing, not the reader}` main.tex:1056 | none | ✅ the **oracle contrast** is in `audit_claims.py` (n=22, +0.1364 vs −0.0109). The 22/22 needle rate is read straight off `needle_summary.json` (`found_rate: 1.0`, n=22, per config) — I verified the file. ⚠️ **the "0/17" negative control is 0-of-18-rows-of-which-17-scored**; quote the denominator you mean |
| **E4** | **Noise floors** — F_exec / F_judge exactly 0.000, each positive-controlled; **F_empty is UNMEASURED, not zero** | LongMemEval-V2 | `results/deltau_pilot/analysis/01_noise_floors.json`, `results/deltau_official/analysis/01_noise_floors.json`, `results/ledgers/h_official_noise_floors.json`; determinism `results/noise/determinism_probe_target_regime.json`, `determinism_probe.json`, `determinism_probe_raw.jsonl` | ledger copy tracked; `results/noise/` not | 2 replicates, T=0 | `scripts/run_noise_floor.py`, `scripts/probe_determinism.py`, `scripts/g_floors_and_flips.py` | Results-plan R1 (main.tex:733); the `NOT_MEASURABLE` rule in Metrics | none | ⚠️ not in `audit_claims.py`. I read the artifacts: `F_exec_delta`, `F_exec_with`, `F_exec_without`, `F_judge`, `F_judge_within_dataset` all `point: 0.0` with CI [0,0]; **`F_empty` has `point: null`** and carries flag `WITHOUT_ARM_REUSED:254 group(s)` — the arm was cached, so its spread is 0 by construction. **F_empty must be reported UNMEASURED.** The screened run's floors are in `k3_screened_analysis.json` / `k4_tables.md` §5 |
| **E5** | **Position effect** — 8/12 cells changed answer when only the memory's position moved | LongMemEval-V2 | cells built for another purpose; per-row `provenance.target_position` on every arm | — | position now seeded by `(task_id, memory_id)`, **never** `replicate_id` | `scripts/run_deltau_pilot.py` (`build_cell_pair`) | `\subsection{Position is a confound...}` main.tex:1081 | none | ⚠️ **PROVISIONAL, n=12.** Not in the audit. A dedicated run is P1-I03. Cite `docs/POSITION_EFFECT.md` |
| **E7** | **SciCode representation scale-up** — full 154-pair candidate pool × 3 representations × 2 arms (924 arm-runs). Matched set n=122 (cells interpretable under ALL three): raw **−0.0082** [−0.0496,+0.0227] · summary **+0.0164** [−0.0370,+0.0833] · structured **+0.0246** [−0.0165,+0.0794] | SciCode | `results/scicode/scaleup_all3.json` (untracked, sha256 in `results/ledgers/repro/MANIFEST.json`); slim slice + analysis **tracked** at `results/ledgers/repro/scicode/scaleup_all3_slim.json`, `scaleup_analysis.json` | **tracked (slice)** | seed 20261008, lexical relatedness, filler_k 2, metis/gpt-oss-120b, temp 0, effort low, 1024 tok. Sampling made **inert** so the design is the whole pool | `scripts/scicode_pilot.py` | `docs/SCICODE_RESULT.md` §SCALE-UP | none yet | 🔴 **ORDERING_VERDICT: NOT_ESTABLISHED.** All three paired contrasts cross zero (structured−raw +0.0328 [−0.0342,+0.1200]). Design pre-committed in `docs/SCICODE_SCALEUP_PRECOMMITMENT.md` **before** the run |
| **E8** | **SciCode F_exec, free control** — the WITHOUT arm carries no memory, so its prompt is byte-identical across representations; disagreement is pure execution/scoring noise. **5/135 = 0.0370** | SciCode | same as E7 | **tracked (slice)** | derived from the WITHOUT arm only | `results/ledgers/repro/scicode/scaleup_analysis.json` | `docs/SCICODE_RESULT.md` §SCALE-UP | none yet | 🔴 **This floor is LARGER than the biggest matched point estimate (+0.0246).** Any SciCode effect claim must be read against it |
| **E6** | **SWE-bench Verified pairing** — 406 cells, 133 distinct donors, **0.0% diagonal**, 0/406 temporal-order violations | SWE-bench Verified | `data/manifests/swebench_pairs_file_seed20261008.jsonl` (+ `..._summary.json`) | **tracked** | `relatedness = file`, seed 20261008, 8 repos, single-file gold fixes only | `src/p1mem/adapters/swebench.py` (31 tests, `tests/test_swebench_adapter.py`) | `\paragraph{BEAM, demoted; SciCode, a case study.}` mentions the axis; **no SWE-bench number is in any table** | none | ⚠️ not in `audit_claims.py`; the manifest carries the pairs so every count is one pass away. Ruled on in `docs/BENCHMARK_C_DECISION.md` |
| **E7** | **SWE-bench floor pilot — NOT CLEARED.** both-arms-fail 4/7 = 57.1%, above the ~50% gate; cause is an **arm-asymmetric apply failure** (WITHOUT 7/7 applicable, WITH 4/7) | SWE-bench Verified | `results/swebench/floor_pilot.json` | **TRACKED** | 10 cells, 20 calls, `max_tokens=1024`, gold-blind top-5 localization, SEARCH/REPLACE edits | `scripts/swebench_floor_pilot.py` | **nothing.** Binding: no SWE-bench number enters a table until WITH-arm apply failure reaches parity | none | ✅ I read the artifact's `summary` block directly and it matches `docs/BENCHMARK_C_DECISION.md` §5 exactly. **Unapplicable edits carry `reward: None`, never 0.0** — verified 0 of 20 arm-results scores an apply failure as zero |

---

## F. Disagreements between sources of truth — flagged, not silently resolved

### F1 🔴 Two different episode-clustered CIs for the headline paired effect

The same quantity is published two ways:

| source | episode-clustered 95% CI |
|---|---|
| `docs/SCREENED_RESULT.md` §4, **and `overleaf/main.tex:1192`** | **[+0.1989, +0.4758]** |
| `docs/THE_HONEST_HEADLINE.md`, `docs/HANDOFF_CURRENT.md`, `README.md`, **and the artifact** `k3_screened_analysis.json` → `episode_clustered_ci` | **[+0.1974, +0.4736]** |

The memory-level bootstrap disagrees the same way: the docs/manuscript say
**[+0.2138, +0.4622]**; the artifact says **[+0.2085, +0.4606]**.

**What I checked.** Both the live analysis file and the tracked repro copy
(`results/ledgers/repro/k3_screened_analysis.json`) carry **[0.1974, 0.4736]** and
**[0.2085, 0.4606]** — they agree with each other, so this is not a stale-copy problem. I
re-ran an episode-clustered bootstrap myself (20,000 resamples over the 35 source episodes,
5 seeds): **[0.1962, 0.4728] … [0.2007, 0.4748]**. That brackets the artifact's interval
and is consistent with seed-to-seed variation; it does **not** reproduce
[+0.1989, +0.4758] as a distinct quantity, but the two intervals differ by ~0.002 and are
within bootstrap noise of each other.

**Reading.** Most likely the same bootstrap at a different seed or draw count. **But the
manuscript currently prints a pair of intervals that no artifact on disk contains**, and
this project's own rule is that a paper number must be re-derivable from an artifact.

> **Action for whoever owns the manuscript:** replace main.tex:1191–1192 with the artifact's
> values, or add the seed/draw count to `k3_analyze_screened.py`'s output so the printed
> interval is reproducible. **Do not** pick one silently. Neither interval changes any
> conclusion: both exclude zero by a wide margin.

**Not in `audit_claims.py`.** The audit checks the paired mean, the contributors-only mean
and the contributor count — **it does not check either CI.** That is why this survived.

### F2 ⚠️ The additive-null excess has two magnitudes (sign agrees)

| source | BEARING | MATCHED_CONTROL | RANDOM |
|---|---|---|---|
| Master Agent's simulation, per `docs/ADDITIVE_NULL_AND_DECOMPOSITION.md` §1 | −0.3854 | −0.5830 | −0.7133 |
| **the artifact** `k3_screened_analysis.json` / `k4_tables.md` §4 (K's audited code) | **−0.2286** | **−0.6857** | **−0.7167** |

I re-read the artifact and confirm the second row (null means 0.2286 / 0.7143 / 1.0000,
`p_value_one_sided` 1.0 in all three). The doc already records the disagreement and rules
that the **sign** is what the claim turns on. **Neither is audited as canonical, and
`audit_claims.py` does not cover this result at all.** If it enters the paper, quote the
artifact row and say the simulation details differ.

### F3 ⚠️ The manuscript's efficiency ratios do not match the audited ones

`overleaf/main.tex:1317–1320` says Summary looks **`5.2×`** more efficient uncharged, and
that charging formation makes Raw more efficient **"by roughly 5×"**, with the other two
moving by **"6–8×"**.

Re-derived by me from the row files (and identically by `audit_claims.py`), on **BEARING**
cells, ratio of totals:

| | uncharged | charged |
|---|---|---|
| Raw | +0.0368 | +0.0368 |
| Summary | +0.2054 | +0.0342 |
| Structured | +0.0622 | +0.0076 |
| **Summary / Raw, uncharged** | **5.58×** | |
| **Raw / Summary, charged** | | **1.08×** |
| **Raw / Structured, charged** | | **4.85×** |

`docs/REPRESENTATION_RESULT.md` states **5.6×** and **0.93×** (= 1/1.08) — consistent with
mine. The manuscript's **5.2×** matches neither. The **"roughly 5×"** claim is true of
Structured (4.85×) but **badly wrong for Summary (1.08×)** — and Summary is the
representation the sentence is about. The **"6–8×"** movement figure *is* right: it matches
`r3`'s `ratio_exposure_over_charged` (summary 6.07, structured 8.04), but note those are
computed over **all common cells**, not BEARING only, so the paragraph mixes two subsets.

> This is the same defect class the project already registered — a ratio quoted without
> re-deriving, and a pooled/subset mismatch inside one sentence. **The paragraph understates
> the correction it is making**: charged, Summary is not "5× worse than Raw", it is
> *indistinguishable* from Raw, which is the actual finding. Flagged to the manuscript owner;
> I did not edit `main.tex`.

### F4 ⚠️ "38 claims" is stale in three places

`README.md`, `docs/HANDOFF_CURRENT.md` and `docs/MASTER_TODO.md` P1-C16 all say
`audit_claims.py` covers **38** claims. It now prints **58** PASS/FAIL checks across 10
sections. Corrected in README and HANDOFF; MASTER_TODO's P1-C16 updated.

### F5 ⚠️ Two views-overlap counts, already recorded

`docs/THE_HONEST_HEADLINE.md` records that K computes views 1 ∩ 3 = **15** and the Master
Agent computes **16**, almost certainly a boundary definition. Left as-is: the doc already
flags it and it changes nothing.

### F6 ⚠️ The 76/75-task basis, already fixed — and now mechanically enforced

Recorded here so it is not re-litigated: two bases exist (**76** discriminative tasks
including one LLM-judged → **267** edges; **75** deterministic → **266** edges). The
executed design and `audit_claims.py` both use **75**, which is canonical. The audit
additionally greps the manuscript body and **fails if "267 bearing" appears**. Nothing to do.

---

## G. Results that must NOT be quoted

| item | why |
|---|---|
| any **variance / interaction share** | the fit is unidentified; `audit_claims.py` fails if the manuscript quotes one |
| a **harmful-memory rate** | the design screened *for* bearing. 2 negative BEARING cells is not a prevalence estimate, and RANDOM's 26/872 is not a natural rate either |
| `F_empty` as **0.000** | it is `null` in the artifact with a `WITHOUT_ARM_REUSED` flag. Report **UNMEASURED** |
| the **robust−naive gap** as 0.000 | `ROBUST_NAIVE_GAP_STATUS = NOT_MEASURABLE`. A gap of zero implies a measurement that cannot be taken |
| the **flip rate as evidence of interaction** | Amendment A1.1. Flips occur at 53–92% with interaction identically zero |
| the pooled **leakage rate** (12.48% or 26.96%) | dominated by short gold answers. Quote the stratified table; the >30-char row is the credible figure |
| the withdrawn **"120 units / 6.4%"** embedding figure | computed against the withdrawn 3,400-token cap. Use 29 units / 1.5% |
| any **SWE-bench** number in a table | the floor pilot is not cleared (E7) |
| the n=8 representation pilot's **"0/8 malformed"** | did not scale; the right figures are D3's two denominators |
| the post-hoc **0.2424** flip rate on "cells that can move" | conditions on an outcome; a diagnostic only |

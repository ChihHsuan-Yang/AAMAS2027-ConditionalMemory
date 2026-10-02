# Paper ↔ Data Synchronization Audit

**Run 2026-10-01 by SA-SYNC.** A number-by-number comparison of every paper-facing claim
across three surfaces — **GITHUB** (README, `docs/`, `results/`), **HF**
(`AgentsSci/AAMAS2027-ConditionalMemory`, verified by **downloading every tag**, not by
reading the local card) and **OVERLEAF** (`main.tex`, `figdata.tex`).

**Method.** Every row was re-derived from the artifact. No document was compared against
another document. Every null is positive-controlled: a check that returns zero is shown
returning non-zero on a known-present case first, and the control is named in the row.

**Audit coverage.** `scripts/audit_claims.py` now runs **218 checks in 21 sections**, up
from 129/16 at the start of this pass. The three sections SA-SYNC added
(*units/universes/counts*, *compression bases*, *the decomposition basis*) were each
**proven able to fail** by planting the exact defect they guard — a stale `\sweMatched{15}`
macro and a collapsed `n_cells = n_matched` — and watching the run exit non-zero.

---

## The table

| CLAIM | CANONICAL ARTIFACT | GITHUB | HF | OVERLEAF | STATUS |
|---|---|---|---|---|---|
| **SWE-bench item funnel** — 107 attempted = 37 valid + 70 excluded | `results/swebench/coverage_table_final.json` → `TOTAL` | ✅ `COVERAGE_MANIFEST.md` §3 (107/37/70, closes per repo) | n/a — HF ships rep-cells, not the item funnel | ✅ not printed (the paper prints rep-cells) | **CONSISTENT** |
| **SWE-bench matched set = 40 CELLS** (django 37 + sympy 3) | `results/swebench/representations_multirepo_final.json` → `pooled.MATCHED_CELL_SET_N` | 🔴 **was 15** in `README.md:187` and `MODEL_ARMS.md` C1–C3 (*"32 cells, django only, 13 matched"*) — **FIXED this pass** | n/a | ✅ `\sweMatched{40}`, `\xbSRSwN{40}`, `\xbTRSwN{40}` | **was STALE IN GITHUB → now CONSISTENT** |
| **SWE-bench cross-benchmark contrasts** Summary−Raw −0.1000 [−0.2250, 0.0000]; Structured−Raw −0.0500 [−0.1750, +0.0750], n=40 | same, `pooled.paired_contrasts` | ✅ | n/a | ✅ `tab:crossbench` via macros | **CONSISTENT** |
| **SWE-bench dominated-by share 92.5%** | same, `pooled.DOMINATED_BY.share` | ✅ | n/a | ✅ `\sweDomRepoPct{92}` | **CONSISTENT** |
| 🔴 **"Demoting those 37 arm-reads moves the matched set from 17 to 40"** | re-derived with the project's own `demote_manufactured_zeros` + `matched_of` over the four final source artifacts | ⚠️ `DEFECT_REGISTER` #21 says 17→15, correct **of the old universe** | n/a | 🔴 `main.tex:580` | **CONTRADICTORY — mixed universes.** 17 is the pre-correction count in the **superseded 15-cell** universe. On the **final** universe the pre-correction count is **42**, not 17. The honest sentence is **42 → 40**. |
| **Reader transfer, session-matched: +0.0982 [+0.0247, +0.1730]** | `results/ledgers/repro/raw_session_matched/raw_session_matched_analysis.json` | ✅ `READER_TRANSFER_RESULT.md`, `EXPERIMENT_ACCOUNTING.md`, README all mark the cross-session figure SUPERSEDED | n/a | ✅ leads the paragraph; `\rgSmDiff/\rgSmLo/\rgSmHi` | **CONSISTENT** |
| **Its unit: 275 CELLS / 123 tasks / 550 REPLICATE ROWS** | same artifact, `_n_matched_UNIT` | ✅ | n/a | ✅ `\rgSmCells{275}`, `\rgSmN{550}`; paper prints "cells" beside the cell count | **CONSISTENT** |
| 🔴 **WITHOUT-arm decomposition `\rgWithoutDelta` = −0.0688, share 54%** | `results/ledgers/gemma_reader/reader_transfer_analysis.json` (**cross-session**, 276 cells, arms 11 h apart) vs the session-matched rows | ⚠️ `MASTER_TODO` P1-C22(2) already flags it; not fixed | n/a | 🔴 `main.tex:1628` — explains the **session-matched** +0.0982 with the **superseded cross-session** decomposition | **CONTRADICTORY — see "worst inconsistency"** |
| **Cross-session +0.1268 [+0.0496/0.0511, +0.2050]** is history only | same cross-session artifact | ✅ labelled SUPERSEDED in README, HANDOFF, EXPERIMENT_ACCOUNTING, SCOPE_FREEZE | n/a | ✅ appears once, correctly framed as *"a first execution a day apart"* | **CONSISTENT** |
| **Embedding truncation 96.6% of executed cells** | per-row `memory_embedding_reference.input_truncated` | ✅ `EMBEDDING_LIMITATION.md` marks 93.6% **withdrawn** and keeps it readable as history | 🔴 **`docs/hf_card/README.md:599` states 93.6% as current** — the withdrawn figure, shipped | ✅ 96.6% only; `audit_claims.py` fails the build if 93.6 appears | **STALE IN HF** |
| **Compression ratios 0.063 / 0.037** | `results/ledgers/b6_pilot_representations_summary.json` (**n=8 pilot**) | ⚠️ `MEMORY_REPRESENTATIONS.md` labels them n=8; `REPRESENTATION_RESULT.md` does not | 🔴 card §12.1 repeats them unlabelled | 🔴 `main.tex:1509` quotes them **in the same sentence as the 277-cell scale-up** | **CONTRADICTORY — mixed basis.** Scale-up medians are **0.0384 / 0.0330** (n=60/57). |
| **HF card §14 "median 0.0162 / 0.0151, roughly 60×"** | no artifact reproduces it | — | 🔴 shipped in v0.2, v0.3 **and v0.4** | not in the paper | **NO CANONICAL ARTIFACT.** A sweep of every subset × every token-field pair under median/mean/ratio-of-totals finds neither value. *Positive control:* the same sweep **does** recover the true 0.0334/0.0384, so the null is real. |
| **Table 2 coverage — LongMemEval 1,157 / 1,157 / 0 / 100%** | `data/manifests/k1_screened_cells.jsonl` + `results/deltau_screened/cells.jsonl` | ✅ `COVERAGE_MANIFEST.md` §1 names both universes (1,157 screened vs 15,112 frozen) | ✅ 5,643 lmev2 rows | ⚠️ correct, but see the unit row below | **CONSISTENT (value)** |
| **Table 2 coverage — SciCode 462 / 391 / 71 / 84.6%** | `results/scicode/scaleup_all3.json`, counted from arm-run rows | ✅ | ✅ 154 rows (raw only; summary/structured text never persisted) | ✅ | **CONSISTENT** |
| **Table 2 coverage — SWE-bench 321 / 141 / 180 / 43.9%** | four `representations_*.json`, counted independently of completed+excluded | ✅ | ✅ 127 rows, metrics+ids only | ✅ | **CONSISTENT** |
| 🔴 **Table 2 MIXES UNITS ACROSS ITS ROWS** | design manifest carries **no** representation field; all 2,599 screened rows are `raw` | ⚠️ `COVERAGE_MANIFEST.md` names the rep sub-universe (855) but the table does not use it | n/a | 🔴 `tab:coverage` | **CONTRADICTORY.** LongMemEval's 1,157 are **(memory, task) cells at ONE representation**; SciCode's 462 and SWE-bench's 321 are **(memory, task, representation) rep-cells**. The matched 3-representation LongMemEval universe is **855**, not 1,157. The caption defines a cell as "(memory, task, representation)" — **true of two rows of three**. *Positive control:* the same field on `repr_scaleup/cells_slim.jsonl` returns >1 representation, so `["raw"]` is a measurement of this universe, not a constant field. |
| **Bearing scarcity: 1,889 units · 165 bear · 46 on ≥2 · 23 episodes · 266 edges on the 75-task basis** | `data/manifests/lmev2_leakage_small.jsonl` + `results/ledgers/k1_screened_design.json` | ✅ `BEARING_SCARCITY.md`, `RESULT_INDEX` B1 | n/a | ✅ all generated; the 76-basis 267 is grep-banned | **CONSISTENT** |
| **Screened run: BEARING 0.5252 [0.4426, 0.6064]; MC 0.7877; RANDOM 0.7007** | `results/deltau_screened/cells.jsonl` | ✅ | ✅ card §12 verified on the downloaded tag | ⚠️ **typed** into `tab:screened` while the mean-ΔU column is generated | **CONSISTENT (value); typed-vs-generated flagged** |
| **Paired within-memory effect +0.3349; contributors +0.5740; CIs [+0.2085,+0.4606] / [+0.1974,+0.4736]** | `k3_screened_analysis.json` | ✅ `RESULT_INDEX` F1 recorded the old mismatch | ✅ | ✅ **F1 is RESOLVED** — `main.tex:1293–1294` now prints the artifact's intervals | **CONSISTENT** (F1 can be closed) |
| **Representation paired B−MC: Raw +0.3174, Summary +0.0613, Structured −0.0498 on 277 cells / 57 memories** | `results/repr_scaleup/cells.jsonl` | ✅ | ✅ card §12.1 verified exactly | ⚠️ `\frRawDU`/`\frSumDU`/`\frStrDU` exist **and** the same values are typed at `main.tex:1507–1508` | **CONSISTENT (value); TYPED WHERE A MACRO EXISTS** |
| **Efficiency: exposure 5.5×, charged 1.10×, formation 1,637 / 1,676 tok, reuse 4.86** | `results/repr_scaleup/*` via `make_figures.py` | ✅ | ✅ | ✅ all generated; the old typed `5.2×` is **gone** | **CONSISTENT** (RESULT_INDEX F3 can be closed) |
| **Writer×reader factorial: 8/8 contrasts span zero; Summary n=274, Structured n=268** | `results/ledgers/writer_factorial/*` | ✅ | n/a | ✅ | **CONSISTENT** |
| **Real endpoint calls = 30,159** (lmev 27,803 + SciCode 1,340 + SWE-bench 1,016) | `scripts/count_experiment_accounting.py` | 🔴 **README said 29,775 and SWE-bench 632** in two places — **FIXED this pass** | n/a | not in the paper | **was STALE IN GITHUB → now CONSISTENT** |
| **`audit_claims.py` coverage** | the script's own output | 🔴 README/HANDOFF/MASTER_TODO said **129 in 16**; RESULT_INDEX said **58** — **all FIXED to 218/21** | n/a | n/a | **was STALE IN GITHUB → now CONSISTENT** |
| **HF current release = v0.4 `swebench-metrics`, 5,924 rows, 98 fields, schema `..._v3`** | downloaded tag `v0.4-swebench-metrics` (commit `83c560e7` (the GitHub commit named in v0.4's own shipped `MANIFEST.json`; HF-side tag object `af273636`)) | 🔴 **README and HANDOFF both said v0.2 / 5,643 rows / "v0.3 being rebuilt now"** while `DATASET_INDEX.md` documented v0.4 as shipped — **FIXED this pass** | ✅ all four tags exist; row counts, schema, composition and withholding all reproduce exactly | n/a | **was STALE IN GITHUB → now CONSISTENT** | 🔴 **Corrected 2026-10-02:** these docs previously said `bc66629f`, which is **not a commit in this repository and not the HF tag object either** — `git log bc66629f` fails with *unknown revision*. The authoritative value is `release_commit` inside the snapshot's own MANIFEST, read from the downloaded tag.
| **HF benchmark composition: 5,643 `longmemeval_v2` + 154 `scicode` + 127 `swebench_verified`** | downloaded `data/cells.jsonl` at v0.4 | ✅ `DATASET_INDEX.md` | ✅ counted from the shipped bytes | n/a | **CONSISTENT.** *Positive control for the spelling trap:* `lmev2` → 0, `swebench` → 0, `swe-bench` → 0, while the correct spellings return 5,643 / 154 / 127. |
| **HF licensing: frontmatter `other` + `mixed-per-row`; 127 rows metrics+ids only, 5 fields withheld** | downloaded v0.4 card + rows | ✅ | ✅ `text_fields_withheld` non-empty on exactly 127 rows; `__WITHHELD_SEE_LICENSE__` and `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` never co-occur | ✅ the paper's withholding paragraph matches | **CONSISTENT** |
| 🔴 **Shipped `DATASET_INDEX.md` at tag v0.3 says "No SciCode row is in any published snapshot"** | the v0.3 tag ships 154 SciCode rows | ✅ repo copy is correct | 🔴 **the published v0.3 tag carries the false statement** (byte-identical to v0.2's copy) | n/a | **STALE IN HF** — fixed in v0.4, left published at v0.3 and now recorded in HANDOFF |
| **HF card §9 bearing-label row table (BEARING 417 / MC 438)** | downloaded rows: BEARING **965**, MC **1,014**, unscreened **2,074** | — | 🔴 stale in v0.2, v0.3 **and v0.4** — true only at v0.1, before the compressed arms landed | n/a | **STALE IN HF** |
| **Figures and tables actually in `main.tex`: 5 figures, 3 tables** | `main.tex` itself | 🔴 `FIGURE_INDEX.md` claimed **3 figures / 2 tables**, called the frontier "not yet in main.tex", never listed Figure 6, and listed `tab:flips` as ✅ DONE when it was **removed** — **FIXED this pass** | n/a | ✅ | **was STALE IN GITHUB → now CONSISTENT** |
| **`figdata.tex` is 368 lines and feeds 5 figures + 2 tables** | the file | 🔴 `FIGURE_INDEX.md` said **120 lines** — **FIXED** | n/a | ✅ | **was STALE IN GITHUB → now CONSISTENT** |
| **Noise floors F_exec = F_judge = 0.000 within session; F_empty UNMEASURED** | `01_noise_floors.json`, `h_official_noise_floors.json` | ✅ `RESULT_INDEX` E4/G rule F_empty UNMEASURED | n/a | ✅ paper reports F_empty only as *"a measured 0 raises"*, never as a result | **CONSISTENT** |
| **Session determinism: 554/1,124 differ at one day; second reader 0/1,124** | `SESSION_DETERMINISM_AUDIT.md` + probes | ✅ | n/a | ✅ | **CONSISTENT** |
| **No variance / interaction share is quoted anywhere** | fit is unidentified (`F_exec = 0`) | ✅ | ✅ | ✅ audited, build fails if one appears | **CONSISTENT** |
| **No harmful-memory rate is quoted** | design screened *for* bearing | ✅ | ✅ | ✅ audited | **CONSISTENT** |
| **Additive-null excess is negative in all three strata** | `k3_screened_analysis.json` §4 | ⚠️ two implementations disagree on magnitude (−0.3854/−0.5830/−0.7133 vs −0.2286/−0.6857/−0.7167) | n/a | ✅ only the **sign** is quoted | **NO CANONICAL ARTIFACT** for the magnitude; the sign (what the claim turns on) is consistent |
| **Position effect 8/12** | per-row `provenance.target_position`; `POSITION_EFFECT.md` | ⚠️ provisional, no committed analysis script, not in the audit | n/a | ✅ labelled provisional at n=12 | **NO CANONICAL ARTIFACT** (ruling doc only) |
| **Scorer-composition split of the paired effect** | derived ad hoc from A1 | ⚠️ `RESULT_INDEX` A4: "no committed script" | ✅ card §19.9 reproduces | not in the paper | **NO CANONICAL ARTIFACT** (not paper-facing) |
| **F_judge comparator "9.35% verdict flip in a prior study"** | an external prior study, not this project | ⚠️ no artifact in this repo | n/a | `main.tex:683` | **NO CANONICAL ARTIFACT** — correctly framed as another group's number, not ours |
| **`/tmp/lmev2/questions.jsonl` gates both generators** | `make_figures.py:32`, `audit_claims.py:74` | 🔴 **untracked, outside the repo, in shared `/tmp`** | n/a | every bearing figure depends on it | **NO CANONICAL ARTIFACT** — see below |

---

## Counts by surface

| surface | stale / contradictory at the start of this pass | fixed this pass | still open |
|---|---:|---:|---:|
| **GITHUB** | **9** | **9** | 0 |
| **HF** | **4** | 0 | **4** (3 require a re-release; 1 is a published tag left as history) |
| **OVERLEAF** | **4** | 0 | **4** (`main.tex` is owned by SA-SCI-PAPER — reported, not edited) |

**GITHUB, fixed:** README call totals (29,775 → 30,159; SWE-bench 632 → 1,016) ×2 sites ·
audit check count (129/16, and RESULT_INDEX's 58) ×4 docs · README SWE-bench matched 15 →
40 · `MODEL_ARMS.md` C1–C3 "PARTIAL, 13 matched" → DONE, 40 matched · README + HANDOFF HF
version v0.2 → v0.4 · `FIGURE_INDEX.md` preamble (3 figures/2 tables, frontier absent,
`tab:flips` alive, 120 lines).

**HF, open:** 93.6% truncation figure in the shipped card · §14 compression 0.0162/0.0151
(reproduces from nothing) · §9 bearing-label table stale since v0.2 · `DATASET_INDEX.md`
published inside tag v0.3 denying the 154 SciCode rows that tag ships.

**OVERLEAF, open:** the `\rgWithoutDelta` basis mix (below) · `tab:coverage` unit mixing ·
compression 0.063/0.037 attributed to the 277-cell scale-up · "matched set from 17 to 40".

---

## The single worst inconsistency

**`main.tex:1628` explains the surviving measurement with the retracted one's
decomposition.**

The reader-transfer paragraph leads correctly with the **session-matched** effect
`\rgSmDiff` = **+0.0982** [+0.0247, +0.1730] over **275 cells / 550 replicate rows**. Three
lines later it accounts for that effect with:

> *"Part of the gain is a weaker reader rather than a better memory — the no-memory arm
> moves `\rgWithoutDelta`"*

`\rgWithoutDelta` is **−0.0688**, read from `reader_transfer_analysis.json` — the
**cross-session** arm, 276 cells, arms **11 hours apart**, which the *same paragraph* calls
superseded two sentences later and which every GitHub doc marks SUPERSEDED.

Re-derived on the 550 session-matched rows the paper is actually reporting:

| quantity | cross-session (what the paper prints) | session-matched (what the paper's effect is) |
|---|---:|---:|
| WITHOUT-arm change | **−0.0688** | **−0.0364** |
| WITH-arm change | +0.0580 | +0.0618 |
| WITHOUT share of the change | **54%** | **37%** |
| cells | 276 | 275 |

**Why it is the worst.** Every other open item is a number that is stale, or right about
the wrong unit. This one is a **retracted number doing live explanatory work inside the
paragraph that retracts it** — and it *overstates the deflationary caveat*: the paper tells
a reviewer that 54% of Gemma's larger Raw effect is a weaker baseline when on its own
measurement it is 37%. The direction is against the authors, which is why no reviewer
would catch it and why no guard fired: `make_figures.py` asserts the share is a fraction in
(0,1) and equals 0.5429 — it verifies the number against **its own artifact**, never
against the artifact the sentence is about. A check inspecting the wrong subject reports
success. `audit_claims.py` now re-derives both and asserts they differ.

**Fix (for SA-SCI-PAPER / Master Agent):** point `\rgWithoutDelta` and `\rgWithoutShare` at
`raw_session_matched_analysis.json` (−0.0364, 37%), or say explicitly that the
decomposition is from the cross-session arm. The second is weaker — the sentence is
explaining a session-matched effect.

---

## Claims with NO canonical artifact

1. 🔴 **`/tmp/lmev2/questions.jsonl` — the most serious.** Both `make_figures.py:32` and
   `audit_claims.py:74` read it by absolute path from **shared `/tmp`**. It is untracked,
   outside the repo, and `git ls-files | grep -i question` returns nothing (*positive
   control:* the same pattern finds tracked manifests under `data/manifests/`). Every
   bearing-scarcity number — the 76/75 task split, 1,889 units, 165/46/23, the Figure 2(a)
   histogram — is gated on a file a reviewer cannot obtain and that any process writing to
   `/tmp` can clobber. This session hit a live instance of that hazard: another agent's
   `/tmp/bisect.py` shadowed the stdlib and broke `huggingface_hub` imports. **Track it
   under `data/manifests/` and repoint both scripts.**
2. **HF card §14 compression "0.0162 / 0.0151, roughly 60×"** — reproduces from no subset
   of the released rows under any aggregation swept. Shipped in three releases.
3. **Additive-null excess magnitudes** — two implementations, neither audited as canonical.
   Only the sign is quoted, which is correct, but the magnitude has no owner.
4. **Position effect 8/12** — no committed analysis script; a ruling doc only. Correctly
   labelled provisional in the paper.
5. **Scorer-composition split (RESULT_INDEX A4)** — ad hoc, no script. Not paper-facing.
6. **"9.35% verdict flip" F_judge comparator** — another group's prior study. Correctly
   attributed, but there is no artifact in this repo and none should be implied.

---

## Standing-rule violations: typed where a macro exists

The rule is that no hand-typed number survives if it can be generated.

| typed in `main.tex` | generated macro | line |
|---|---|---|
| `+0.3174`, `+0.0613`, `-0.0498` | `\frRawDU`, `\frSumDU`, `\frStrDU` | 1507–1508 |
| `277` | `\frCells` | 1506 |
| `0.5252`, `0.4426`, `0.6064`, `0.7877`, `0.7144`, `0.8462`, `0.7007`, `0.6695`, `0.7302` | **no macro yet** — `tab:screened`'s both-arms-fail and Wilson columns are typed; only the mean-ΔU column is generated | 1275–1277 |
| `+0.3349`, `+0.5740`, `[+0.2085,+0.4606]`, `[+0.1974,+0.4736]` | no macro; audited instead | 1291–1294 |

The first two rows are the live hazard: the macro and the typed value are the same number
today and nothing fails the build if one moves. `tab:screened`'s typed columns are covered
by `audit_claims.py`, which is the weaker guarantee `FIGURE_INDEX.md` already names.

---

## Index corrections folded into this pass

* **RESULT_INDEX F1 (two episode-clustered CIs) — RESOLVED.** `main.tex:1293–1294` now
  prints the artifact's `[+0.2085, +0.4606]` and `[+0.1974, +0.4736]`. The row may be
  closed.
* **RESULT_INDEX F3 (the `5.2×` efficiency ratio) — RESOLVED.** The typed ratio is gone;
  the manuscript reads `\frRatioExp` (5.5) and `\frRatioChg` (1.10).
* **RESULT_INDEX F4 ("38 claims" stale) — superseded.** It was 129 in four places and 58 in
  RESULT_INDEX itself; all now read **218 checks in 21 sections**.

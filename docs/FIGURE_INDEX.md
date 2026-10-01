# Figure Index — every figure, its inputs, and whether it is ready

**Created 2026-09-30 by SA-ARCHIVE.** Decisions live in `docs/FIGURE_PLAN.md`; this is the
navigation table.

> 🔴 **RE-CHECKED 2026-10-01 by SA-SYNC against `overleaf/main.tex`. The paragraph that
> stood here was STALE and is replaced.** It said `main.tex` held **3 figures / 2 tables**
> with "no frontier figure and no cross-benchmark placeholder present yet". `main.tex` now
> holds **5 `figure` environments and 3 `table` environments**:
> `fig:pipeline` · `fig:bearing` · `fig:similarity` · **`fig:frontier`** (Figure 4, the
> utility–efficiency frontier — it LANDED) · **`fig:readertransfer`** (Figure 6, reader
> generalization, which this index never listed at all); tables `tab:coverage`,
> **`tab:crossbench`** (the cross-benchmark slot — it was FILLED, as a table rather than a
> forest plot) and `tab:screened`.
> **`tab:flips` NO LONGER EXISTS** — T1 was removed on 2026-09-30 as a duplicate display of
> Figure 2(b); the row below still describing it as ✅ DONE at `main.tex:1109` is wrong.
> Every "in flight" row below is therefore superseded. Re-run
> `grep -n 'begin{figure}\|begin{table}\|label{fig:\|label{tab:' main.tex` before
> trusting any line-number or readiness claim in this file.
>
> **Also stale below:** "120 lines written" for `figdata.tex` — it is now **368 lines**,
> and it feeds all five figures plus `tab:coverage` and `tab:crossbench`.

## The generator contract, which applies to every generated figure

`scripts/make_figures.py` writes `overleaf/figdata.tex` — a file of `\def` macros that
`main.tex` `\input`s at line 39. **No number in any figure or caption is typed by hand.**
The generator recomputes each value **independently of `scripts/audit_claims.py`** and
**exits non-zero if the two disagree**; SA-FIG proved it can fail by planting a sign flip
in a BEARING cell that had a strictly-positive sibling. (SA-FIG's *first* plant could not
fire — the cell had no opposite-sign sibling, so no memory actually gained a flip and the
generator passed. That near-miss is recorded in `docs/DEFECT_REGISTER.md`'s pattern list.)

```
/Users/bellayang/miniconda3/bin/python3 scripts/make_figures.py
```

Re-run 2026-10-01 by SA-SYNC: all checks `ok`, **368 lines** written, and
`git status` in `overleaf/` stayed **clean** — the committed `figdata.tex` is current.

---

## In the paper

| # | Name | Purpose | Input artifacts | Generating script | Output path | Manuscript location | Readiness | Class |
|---|---|---|---|---|---|---|---|---|
| **1** | **The conditional memory utility protocol** (`fig:pipeline`) | Split write-time (task-blind) from read-time, so the leakage invariant is visual; annotate "identical controlled filler in both arms" at the WITH/WITHOUT fork; show cost recorded on the same row as the utility it paid for | **none** — it is a schematic, no data | **none** — hand-drawn TikZ, inline in `main.tex` | inline (`main.tex:330–409`) | Section 3, p. 3 | ✅ **DONE** — committed `0b9b87a` | **publication-facing** |
| **2** | **Bearing scarcity + sign reversal** (`fig:bearing`) | (a) a memory bears on a median of one future task, which caps the reversal denominator; (b) reversals sit where the pairing is meaningless — BEARING's Wilson interval lies entirely below RANDOM's | (a) `data/manifests/lmev2_leakage_small.jsonl`; (b) `results/ledgers/repro/screened_cells_slim.jsonl`; basis pin `results/ledgers/k1_screened_design.json` | `scripts/make_figures.py` → `overleaf/figdata.tex` (`\bear*`, `\flip*` macros) | inline TikZ (`main.tex:934–1016`), data from `figdata.tex` | Section 8, p. 6 | ✅ **DONE** — committed `265908c`; the 76/75 basis error was fixed in the same commit | **publication-facing** |
| **3** | **Embedding similarity vs the content screen** (`fig:similarity`) | (a) mean ΔU by similarity sextile, with a second series excluding BEARING cells so the pooled trend does not credit the embedding with the screen's work; (b) mean ΔU by stratum, which the content screen separates and the embedding does not | `results/ledgers/repro/screened_cells_slim.jsonl` | `scripts/make_figures.py` (`\sim*`, `\strat*` macros) | inline TikZ (`main.tex:1214–1280`), data from `figdata.tex` | Section 8 | ✅ **DONE** — committed `a20f468` | **publication-facing** |

### Why Figure 3 carries two series — do not "simplify" it

BEARING cells concentrate in the high-similarity bins (**54 of 139** in the top sextile
against **5** in the bottom), so the pooled trend is partly the content screen showing
through. The unscreened-only series is the same axis with no bearing cells in it. **The
generator asserts that concentration**, so the confound cannot quietly disappear without
the figure's source comment going stale loudly.

## Tables in the paper

| # | Name | Purpose | Input artifacts | Generating script | Manuscript location | Readiness | Class |
|---|---|---|---|---|---|---|---|
| **T1** | Sign reversal by stratum (`tab:flips`) | The founding-hypothesis negative, with eligible denominators and Wilson intervals | `results/deltau_screened/cells.jsonl` → `analysis/k4_tables.md` §3 | `scripts/k4_report_tables.py`; values re-derived by `audit_claims.py` | `main.tex:1109–1120` | ✅ **DONE** | publication-facing |
| **T2** | Screened run (`tab:screened`) | Both-arms-fail and mean ΔU per stratum, plus the two unscreened arms as comparators | `results/deltau_screened/cells.jsonl`, plus both `results/ledgers/repro/*_cells_slim.jsonl` for the comparator rows | `scripts/k4_report_tables.py`; re-derived by `audit_claims.py` | `main.tex:1161–1177` | ✅ **DONE** | publication-facing |

**T1 and T2 numbers are typed into `main.tex`, not `\input` from a generated file.** That
is a weaker guarantee than the figures have — the protection is `audit_claims.py`, which
re-derives every cell of both tables from the row artifacts. Keep it that way, or move
them into `figdata.tex`.

---

## In flight

| # | Name | Purpose | Input artifacts | Generating script | Output | Manuscript | Readiness | Class |
|---|---|---|---|---|---|---|---|---|
| **4** | **Utility–efficiency frontier** | ΔU against exposed tokens per representation, with formation cost charged — the visual form of the cost reversal (RESULT_INDEX D2) | `results/repr_scaleup/cells.jsonl`, `memories.jsonl`, `analysis/r3_representation_analysis.json`, plus the Raw arm from `results/deltau_screened/cells.jsonl` | to be added to `scripts/make_figures.py` | `overleaf/figdata.tex` + inline TikZ | **not yet in `main.tex`** as of `3c06d3a` | 🟡 **IN PROGRESS** — SA-FIG2, P1-C03. **Unblocked**: SA-R landed the utility axis on 2026-09-30, which is what blocked it in `FIGURE_PLAN.md` | publication-facing |
| **5** | **Cross-benchmark placeholder** | A slot for SWE-bench / SciCode once either produces a *comparable* quantity | none yet | — | — | **not yet in `main.tex`** | 🔴 **STILL EMPTY, and the reason has changed.** Both benchmarks now have representation data — SciCode's is complete (E7/E8), SWE-bench's is running. The blocker is no longer availability but **comparability**: SciCode's matched ΔU (n=122) is measured against a free 0.0370 execution floor that LongMemEval does not have (its F_exec is exactly 0), and the SciCode contrasts all cross zero. Plotting a −0.0082 beside a +0.3349 invites reading a benchmark difference as a representation effect. **It is filled only with quantities that share a definition, a denominator, and a floor** | publication-facing |

> ⚠️ **Space.** `FIGURE_PLAN.md` measured **≈900 pt** of float capacity at baseline and
> reports **~50–80 pt left** after three figures. The AI-assistance section
> (`main.tex:1337`) is **required by AAMAS and still empty**, and will consume part of it.
> A fourth figure is likely to need a cut. **Measure where the body ends, not the total
> page count** — page count is flat here because references are uncapped, and reading it
> as a slack indicator is a registered defect (`docs/DEFECT_REGISTER.md`).

---

## Rejected — with the reason, so they are not re-proposed

| figure | why not |
|---|---|
| Dilution / both-arms-fail | **Restates `tab:screened`.** A figure that re-plots a table spends page budget for no new information |
| Example useful / harmful memories | 🔴 **only 2 negative BEARING cells exist.** Showcasing them is exactly the selected-subgroup reading the paper refuses elsewhere |
| Dataset coverage | a dataset-paper device; this is not a dataset paper |
| Variance decomposition | 🔴 **forbidden.** The fit is unidentified (`F_exec = 0` leaves no residual scale). Plotting it would render an optimizer clip constant as a finding, and `audit_claims.py` fails if any share is quoted |

## Diagnostic-only, never publication-facing

These exist as artifacts and are read during analysis. None is a figure and none should
become one without a new decision:

| what | where | why it stays diagnostic |
|---|---|---|
| noise-floor tables | `results/*/analysis/01_noise_floors.json` | F_exec/F_judge are exactly 0 with F_empty **UNMEASURED**; a plot of three zeros and a null is not a figure |
| k4 report tables | `results/deltau_screened/analysis/k4_tables.md` | the analysis-side rendering that T1/T2 were written from |
| representation analysis | `results/repr_scaleup/analysis/r3_representation_analysis.json` | feeds Figure 4; the JSON itself is not shown |
| cross-session drift probe | `results/repr_scaleup/cross_session_probe.json`, `raw_resample.json` | an instrument caveat, belongs in prose/Limitations |
| SWE-bench floor pilot | `results/swebench/floor_pilot.json` | not cleared; plotting it would give a blocked benchmark visual authority |
| reader needle probe | `results/j2_escalation/needle_summary.json` | a ruling-out, already carried in one prose subsection |

## Caption rule, binding

No caption clause may imply that a **sign flip evidences interaction** (Amendment A1.1,
`docs/LITERATURE_BOUNDARY.md`). Figure 2's caption states the reversal rate as
**descriptive** and says explicitly that no inference about the memory × task interaction
is drawn from it. Preserve that when editing.

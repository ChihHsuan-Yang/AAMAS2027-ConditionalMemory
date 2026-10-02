# Artifact Lookup — from this manuscript to the code and data

**Written 2026-10-01 by SA-PROVENANCE.** This file lives beside `main.tex` so a reader
holding the paper can find the artifact behind any number without leaving the manuscript
repository. **It does not duplicate the maps — it points at them.**

> **Do not edit `main.tex` from here.** Other agents own it. This file is navigation only.

---

## The three repositories

| | |
|---|---|
| 💻 **Code + data** | <https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory> · local clone `../repo` |
| 🤗 **Dataset** | <https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory> — **private**; tags `v0.1-lmev2-derived`, `v0.2-repr-derived`, `v0.3-scicode-derived`, `v0.4-swebench-metrics` |
| ✍️ **This manuscript** | <https://git.overleaf.com/6abbde4a9eb777031afef068> (`main`) |

**Title:** *What Is This Memory Useful For? Measuring Task-Conditioned Utility in
Long-Term Agent Memory* (`main.tex:65`).

## The two maps that answer everything else

| if you want to know | read |
|---|---|
| which script and which input file produced a figure or table; what the **unit** and the **exact universe** of a table row are; how a memory was constructed on each benchmark; what counts as eligible/valid/excluded and **what is never scored as reward zero** | **[`../repo/docs/PAPER_ARTIFACT_MAP.md`](../repo/docs/PAPER_ARTIFACT_MAP.md)** |
| whether a result can still be reproduced and audited — source episode, each memory text, both arm outputs, reward, scorer, endpoint and replicate metadata, each marked HF-private / GitHub / local-only / **unavailable forever** | **[`../repo/docs/TRACE_AVAILABILITY.md`](../repo/docs/TRACE_AVAILABILITY.md)** |

Secondary: [`RESULT_INDEX.md`](../repo/docs/RESULT_INDEX.md) ·
[`FIGURE_INDEX.md`](../repo/docs/FIGURE_INDEX.md) ·
[`DATASET_INDEX.md`](../repo/docs/DATASET_INDEX.md) ·
[`COVERAGE_MANIFEST.md`](../repo/docs/COVERAGE_MANIFEST.md) ·
[`DEFECT_REGISTER.md`](../repo/docs/DEFECT_REGISTER.md) ·
[`HANDOFF_CURRENT.md`](../repo/docs/HANDOFF_CURRENT.md)

---

## Fast index — every float in the paper

Figure and table numbers are the **rendered** ones, read from `main.aux`.

| in the paper | `\label` | `main.tex` | generator / input | map section |
|---|---|---|---|---|
| **Figure 1** protocol schematic (p.3) | `fig:pipeline` | 349–429 | **none** — inline TikZ, no measured number | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Table 1** coverage (p.4) | `tab:coverage` | 674–698 | `make_figures.py::coverage()` ← design manifest + row files + the four SWE-bench source artifacts | [map §(b) Table 1](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Figure 2** bearing scarcity + sign reversal (p.6) | `fig:bearing` | 878–961 | `bearing_breadth()`, `flips_by_stratum()` ← `data/manifests/lmev2_leakage_small.jsonl` **+ `/tmp/lmev2/questions.jsonl`** | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md), [trace §5](../repo/docs/TRACE_AVAILABILITY.md) |
| **Table 2** screened run (p.6) | `tab:screened` | 1014–1038 | `k4_report_tables.py` + `audit_claims.py`; mean-ΔU column reads generated `\strat*` macros | [map §(b) Table 2](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Figure 3** sparsity map (p.7) | `fig:sparsity` | 1067–1129 | `sparsity_map()` ← `results/ledgers/repro/screened_cells_slim.jsonl` | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Figure 4** similarity vs the content screen (p.7) | `fig:similarity` | 1200–1256 | `similarity_vs_bearing()` ← same slim rows | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Figure 5** utility–efficiency frontier (p.8) | `fig:frontier` | 1295–1391 | `frontier()` ← `results/deltau_screened/cells.jsonl`, `results/repr_scaleup/{cells,memories}.jsonl`, `analysis/r3_representation_analysis.json` (**all local-only**) | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md), [trace §1b](../repo/docs/TRACE_AVAILABILITY.md) |
| **Table 3** cross-benchmark contrast (p.8) | `tab:crossbench` | 1459–1490 | `crossbench()` ← `r3_representation_analysis.json` (n=277) · `repro/scicode/scaleup_analysis.json` (n=122) · `repro/swebench/representations_multirepo_final.json` (**n=40**, django 37 + sympy 3) | [map §(b) Table 3](../repo/docs/PAPER_ARTIFACT_MAP.md) |
| **Figure 6** reader transfer (p.9) | `fig:readertransfer` | 1516–1601 | `reader_session_matched()`, `reader_generalization()` ← `repro/raw_session_matched/*`, `repro/gemma_reader/*` | [map §(a)](../repo/docs/PAPER_ARTIFACT_MAP.md), [trace §1d](../repo/docs/TRACE_AVAILABILITY.md) |

## The generator contract

`scripts/make_figures.py` writes `figdata.tex` — a file of `\def` macros `main.tex`
`\input`s at line 39. **No number in any figure or caption is typed by hand.** The
generator recomputes each value **independently of `scripts/audit_claims.py`** and
**exits non-zero if the two disagree**.

```bash
python3  # project interpreter: see docs/DEV_ENVIRONMENT.md scripts/make_figures.py   # from ../repo
python3  # project interpreter: see docs/DEV_ENVIRONMENT.md scripts/audit_claims.py   # 218 re-derived checks
```

Re-run 2026-10-01: all checks `ok`, **455 lines** written, `git status` in `overleaf/`
stayed **clean** — the committed `figdata.tex` is current.

**To change a figure, change the data or the generator — never a number in
`figdata.tex`.**

---

## Five things a reader of this manuscript must not get wrong

1. 🔴 **The HF `benchmark` field spells `longmemeval_v2` / `scicode` /
   `swebench_verified`.** A grep for `lmev2` or `swebench` returns a **false zero**.
2. 🔴 **SciCode's Summary and Structured memory TEXT was never persisted and cannot be
   regenerated** (cross-session 0/8 byte-identical at matched settings; within-session
   3/3). **The rewards remain VALID.** Only the 154 `raw` cells ship.
   [trace §2](../repo/docs/TRACE_AVAILABILITY.md)
3. 🔴 **SWE-bench corpus content is embargoed** — `princeton-nlp/SWE-bench_Verified`
   declares no licence, so all five text fields carry `__WITHHELD_SEE_LICENSE__` on
   127/127 rows. **A persistence gap and a licence withholding are different facts with
   different sentinels; they must never be interchanged.**
   [map §(c)](../repo/docs/PAPER_ARTIFACT_MAP.md)
4. 🔴 **Table 1's three rows have three different units** — LongMemEval cells,
   SciCode rep-cells, SWE-bench rep-cells — and the SWE-bench row's 321/141/180 appear
   nowhere in `COVERAGE_MANIFEST.md`, which reports the *recipient* unit (107/37/70).
   Both are true of different objects. [map §(b)](../repo/docs/PAPER_ARTIFACT_MAP.md)
5. 🔴 **The bearing screen reads the gold answer.** It is a measurement instrument, not
   a deployable retrieval policy; the headline effect is conditional on cells where the
   memory demonstrably carries what the task needs.
   [`BEARING_SCREEN_DISCLOSURE.md`](../repo/docs/BEARING_SCREEN_DISCLOSURE.md)

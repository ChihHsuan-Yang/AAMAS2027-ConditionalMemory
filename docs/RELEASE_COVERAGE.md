# Release coverage: paper to artifact

Checked **2 November 2026** against the release manuscript (`website/paper.pdf`, with the supplement), this repository at the commit that adds this file, and the public
dataset `AgentsSci/AAMAS2027-ConditionalMemory` (snapshot built 2026-10-02; 29 conditions, listed
in the dataset's `docs/CONDITIONS.md`).

**Verification levels.** *Verified here* means the number was recomputed from files in this
repository. *In public data* means the supporting records are in the public dataset or in
tracked ledgers, but this audit did not recompute the figure. *Public (follow-ups)* means the run rows were
checked here against the paper and are published in the dataset folder `followups_package/`.

## Summary

| | Status |
|---|---|
| Primary within-memory contrast (+0.33), Table 2, per-stratum counts | **Verified here**: `python scripts/reproduce_headline.py` |
| Reader transfer, session-matched (+0.0982) | **Verified here** from `results/ledgers/repro/raw_session_matched/` |
| Representations, length control, gold-free screens, writer × reader factorial, SciCode, SWE-bench | In public data (conditions below) and tracked ledgers |
| **Fixed total context** (Table S5, Fig 3b right) | **Public** (dataset `followups_package/`, revision `332cd04`) |
| **Second session with randomized position** (Figs 5a, 6, S11) | **Public** (dataset `followups_package/`, revision `332cd04`) |
| **Retrieval baselines** (Table S6, Fig 4b, Fig S5c) | **Public** (dataset `followups_package/`, revision `332cd04`) (regenerating the scores needs the embedding endpoint, which is new inference) |
| Scripts that draw the **current** figures | **Not in the repository** (see "Figures") |

The three later runs (fixed total context, second session with randomized position, retrieval) were
not in the repository or in the dataset's original 29 conditions. They were located, checked against
the paper (see "Follow-up records") and published on 2026-11-03 in the dataset folder
`followups_package/`, commit `332cd047e9093a948606c4251bf5b294b0664762`. Their condition ids are
`lmev2_metis_gptoss120b_fixedctx_v1` (x2) and `lmev2_raw_metis_gptoss120b_screened_posrand_v1` (x1).

## Paper-to-artifact table

Figure and table numbers are those of the release PDF. "Command" is what regenerates the
number; "none public" means no script in this repository produces it.

### Main text

| Item | Source data | Command | Public location | Status |
|---|---|---|---|---|
| Fig 1 protocol schematic | none (diagram) | n/a | in the paper | no data |
| Table 1 run inventory | per-run row files | counts follow from the dataset conditions | dataset `docs/CONDITIONS.md` | Screened design, representations, length control, second reader, gold-free, SciCode, SWE-bench rows: in public data. "second session 285 × 3", "fixed context 277 × 5 arms" and "retrieval 75 tasks": public in `followups_package/` |
| Fig 2a bearing breadth | `data/manifests/lmev2_leakage_small.jsonl` + upstream `questions.jsonl` | `scripts/make_figures.py` (`bearing_breadth`) | manifests tracked; corpus upstream | Reproducible with the upstream LongMemEval-V2 download |
| Fig 2b screen-cap sweep (4, 8, 16, 32) | same manifests | none public | n/a | **Generator not public** |
| Table 2 screened run | `results/ledgers/repro/screened_cells_slim.jsonl` | `python scripts/reproduce_headline.py` | tracked; dataset condition `lmev2_raw_metis_gptoss120b_screened_v1` | **Verified here** (139 / 146 / 872 cells; mean ΔU +0.345 / +0.027 / +0.064; both-arms-fail 0.525 / 0.788 / 0.701) |
| Fig 3a original run | same slice | `python scripts/reproduce_headline.py --bootstrap 10000` | same | **Verified here** (+0.334861; CI [+0.209, +0.463] over memories) |
| Fig 3a new session, random position | x1 rows | recomputation not yet committed as a script | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Fig 3a second reader (+0.60) | reader-transfer conditions | `scripts/gemma_reader_analyze.py` (needs full rows) | dataset conditions `*_readertransfer_v1`; ledgers in `results/ledgers/repro/gemma_reader/` | In public data; contrast not recomputed here (the paired reader difference +0.0982 is verified) |
| Fig 3b own length | representation conditions | `scripts/r3_analyze_representations.py` (needs full rows) | dataset conditions `*_screened_v1` (Raw, Summary, Structured) | In public data |
| Fig 3b fixed total context | x2 rows | `scripts/x2_analyze_fixed_context.py` | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Fig 4a budget sweep | length-control rows | `scripts/len2_analyze_length_control.py` (needs full rows) | dataset conditions `*_lenctl_v1`; `results/ledgers/length_control_result.json` | In public data |
| Fig 4b retrieval vs screen | x3 outputs; labels from the manifests | `scripts/x3_retrieval_baseline.py` (needs the embedding endpoint) | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Fig 5a labels, original vs new session | x1 rows | recomputation not yet committed as a script | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Fig 5b help and harm by stratum | screened slice | derivable from `screened_cells_slim.jsonl` | tracked | In public data |
| Fig 6 effect by memory position | x1 rows | recomputation not yet committed as a script | dataset `followups_package/` | **Public** (revision `332cd04`) |

### Supplement

| Item | Source data | Command | Public location | Status |
|---|---|---|---|---|
| Table S1, Fig S2 length control | length-control rows | `scripts/len2_analyze_length_control.py` (the paper names `make_lenctl.py`, which is not in the repository) | dataset `*_lenctl_v1`; `results/ledgers/length_control_result.json`, `repro/length_control_cells_slim.jsonl` | In public data; the paper's named generator is not public |
| Fig S1 cell-level sparsity map | screened slice | none public (drawing) | tracked slice | Data public; figure script not public |
| Fig S3 exposure efficiency vs reuse | representation rows, writer token counts | none public | dataset | Data public; script not public |
| Table S2 cross-benchmark contrasts | LongMemEval-V2 representation rows; SciCode and SWE-bench ledgers | `scripts/r3_analyze_representations.py`; ledgers in `results/ledgers/repro/scicode/` and `repro/swebench/representations_multirepo_final.json` | tracked and in dataset | In public data |
| Table S3 transitions | screened slice | derivable from the slice; the paper names `make_reanalysis.py`, which is not in the repository | tracked | In public data; the paper's named generator is not public |
| Fig S4 sign reversal | screened slice | the paper names `make_reanalysis.py` (not in the repository) | `results/ledgers/repro/k3_screened_analysis.json` | In public data; the paper's named generator is not public |
| Table S4 pre-registration record | pre-commitment documents | n/a | `docs/*PRECOMMITMENT*.md`, `docs/ANALYSIS_PREREGISTRATION.md` | Public |
| Table S5 fixed total context | x2 rows | `scripts/x2_analyze_fixed_context.py` | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Table S6 retrieval | x3 outputs | `scripts/x3_retrieval_baseline.py` | dataset `followups_package/` | **Public** (revision `332cd04`) |
| Fig S5 a, b, d, e, f | screened, representation, cross-benchmark, reader-transfer data | see rows above | tracked / dataset | In public data |
| Fig S5 c retrieval | x3 outputs | `scripts/x3_retrieval_baseline.py` | dataset `followups_package/` | **Public** (revision `332cd04`) |

### Numbers stated only in the text (S11)

| Statement | Status |
|---|---|
| Second-session contrast +0.50 [+0.37, +0.63]; 28 of 284 labels change with position, 28 of the 81 that move | Verified here from the x1 rows (+0.497; 28 of 284; 28 of 81) |
| 0.78 / 0.65 label agreement with the original run | Not recomputed (needs a join of x1 to the original run) |
| Position accounts for 11% of the variance of ΔU; the interaction-share decomposition | Not recomputed; no committed script |
| Screen-cap sweep (caps 4, 8, 16, 32) | The paper's generator is not in the repository |

## Figures

The repository's `scripts/make_figures.py` writes `paper/figdata.tex`, the macros of the earlier
all-TikZ manuscript. The release PDF's figures are drawn by other code that is not in the repository (`manuscript/main.tex`
names `tools/make_results_figure.py`); the figure PDFs themselves are in `manuscript/figures/`. So **no command in this repository
regenerates the images of the current release**. The numbers behind most figures are in public
data (table above). To close this gap, add the figure-drawing scripts, or state that the figures
are rendered from the numbers listed here.

## Follow-up records: published

The three runs were located (they executed on ALCF Sophia; the x2 log records
`/lus/eagle/projects/datascience_collab/uhanjir/p1mem/runs/x2_fixedctx_smain`). Nothing was re-run.
They were packaged with `scripts/package_followups.py --validate` and recomputed with the
committed scripts. Every paper number below reproduces.

| Run | Rows | Validator | Paper number | Recomputed |
|---|---:|---|---|---|
| x1 second session, random position (`lmev2_raw_metis_gptoss120b_screened_posrand_v1`) | 855 (285 cells × 3), 2 with a missing reward | 0 errors | contrast +0.50 [+0.37, +0.63] | +0.497 [+0.37, +0.63] over 60 memories; episode-clustered [+0.33, +0.67] |
| | | | labels changed by position: 28 of 284 cells; 28 of the 81 cells that move | 28 of 284; 28 of 81 |
| x2 fixed total context (`lmev2_metis_gptoss120b_fixedctx_v1_*`, four arms) | 2,216 (277 cells × 2 replicates × 4 arms) | 0 errors | cache-key defect: 63 exposed pairs; 77 bearing cells kept, 135 total | 63; 77; 135 |
| | | | Raw +0.35 [+0.23, +0.49]; Summary +0.04; Structured +0.01 (excluding exposed) | +0.351 [+0.225, +0.486]; +0.039; +0.013 |
| | | | Summary − Raw −0.31 [−0.44, −0.18]; Structured − Raw −0.34 [−0.47, −0.21] | −0.312 [−0.441, −0.187]; −0.338 [−0.471, −0.215] |
| | | | all cells: Raw +0.37, Summary +0.03, Structured −0.01, matched truncation +0.11 | +0.370; +0.030; −0.015; +0.111 |
| x3 retrieval (`per_task.jsonl`) | 75 tasks, 266 bearing edges | n/a | recall@10: BM25 0.21, dense prefix 0.35, dense chunks 0.40; MRR 0.41; AUROC 0.86 | 0.206; 0.35; 0.403; 0.405; 0.862 |

Intervals are percentile bootstraps and agree with the paper to its two decimals; one lower bound
differs by 0.01 (Raw, all cells: [+0.240] against [+0.25]).

Published on 2026-11-03 to the dataset's `main` branch, folder `followups_package/`, in a single
commit: `332cd047e9093a948606c4251bf5b294b0664762`. The folder holds `x1/`, `x2/`, `x3/` (result rows and
`summary.json`), `logs/`, `MANIFEST_followups.json` (sha256, bytes, row counts, validator result per run) and
`SHA256SUMS.txt`. The published checksum list matches the files that were checked here. The frozen tag
`v0.6-length-control` is unchanged. Condition ids: x1 `lmev2_raw_metis_gptoss120b_screened_posrand_v1`; x2
`lmev2_metis_gptoss120b_fixedctx_v1_{raw,summary,structured,trunc_last_matched}`.

Regenerate Table S5 from the published revision:

```bash
pip install huggingface_hub
python - <<'PY'
from huggingface_hub import hf_hub_download
print(hf_hub_download("AgentsSci/AAMAS2027-ConditionalMemory", "followups_package/x2/cells.jsonl",
      repo_type="dataset", revision="332cd047e9093a948606c4251bf5b294b0664762"))
PY
python scripts/x2_analyze_fixed_context.py <path printed above>     # ends: VERDICT: COUNTS_MATCH_PAPER
```

Still to do: add the follow-up conditions and counts to the dataset's `docs/CONDITIONS.md`, and
add committed scripts for the x1 and x3 recomputations.

The x1 and x3 analyses used for the checks above are short recomputations; committed scripts for
them (as for `x2_analyze_fixed_context.py`) are still to be added.

## SciCode and SWE-bench gaps

Stated exactly, from `docs/TRACE_AVAILABILITY.md` and `scripts/scicode_recover_memories.py`.

| Record | Recoverable? | Detail |
|---|---|---|
| SciCode **Raw memory text** | **Recovered** | 154 of 154 cells regenerated and verified; shipped in the dataset |
| SciCode **Summary / Structured memory text** | **No** | Never persisted. Regeneration matched 5 of 154 (Summary) and 0 of 154 (Structured), so the original text cannot be reconstructed. The 308 cells are absent, not placeholder rows |
| SciCode **Raw reader outputs** | **No** | Not retained (`__OUTPUT_NOT_RETAINED_BY_THE_RUN__`). A re-run is new inference and `gpt-oss-120b` is not reproducible across sessions |
| SWE-bench Verified **text fields** | Not applicable | Withheld on purpose (`__WITHHELD_SEE_LICENSE__`, fields listed in `text_fields_withheld`) because the corpus declares no license. Derived measurements are public |

Recovering the SciCode Summary and Structured text would require new writer inference, and would
produce a new memory, not the original. It is not needed to keep the documented partial dataset
public.

# What Is This Memory Useful For?

### Measuring Task-Conditioned Utility in Long-Term Agent Memory

[**Project page**](https://chihhsuan-yang.github.io/AAMAS2027-ConditionalMemory/) ·
[**Paper (PDF)**](website/paper.pdf) ·
[**Dataset**](https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory) ·
arXiv (coming soon)

Chih-Hsuan Yang\*, Anjir Ahmed Chowdhury\*, Feng Yan, Rajeev Thakur  
Argonne National Laboratory · University of Houston  
\* equal contribution

---

## Overview

A long-horizon agent keeps more experience than any future task needs, so it must decide
which experiences to retain, retrieve and expose. A single importance score hides how a
memory's effect changes from one future task to the next. This repository measures that
effect directly.

For a memory `m` and a later task `t`, a frozen reader answers `t` twice with identical
context filler, once with `m` and once without. The memory was written by a **task-blind**
writer that never saw `t`. The reward difference is the conditional utility:

```text
ΔU(m, t) = Reward(t | filler + m) − Reward(t | filler)
```

A cost ledger records what each memory cost to form, store, retrieve and expose.

### Main results (LongMemEval-V2, single-call factual recall)

| Finding | Result |
|---|---|
| Effects are task-conditioned | Within the same memory, answer-bearing task pairs gain **+0.33** [+0.21, +0.46] more reward than matched-control pairs (60 memories, 1,157 cells) |
| Direction is robust | Contrast stays positive in a new session with randomized position (+0.50) and under a second reader (+0.60); magnitudes and per-pair labels change |
| Answers are sparse | Of 1,889 memory units, 165 bear on at least one of 75 screened tasks; the median bears on one task at every screen cap |
| Compression gains less | Task-blind Summary and Structured gain less than Raw, including at a fixed total context (Raw +0.35, Summary +0.04, Structured +0.01) |
| Retrieval misses most | Dense retrieval recall@10 of answer-bearing units is 0.40, against about 0.01 by chance |
| No effect on code benchmarks | On SciCode and SWE-bench Verified, memories show no measurable effect even in raw form |

Scope: single-call factual recall with deterministically scored questions. No claim is made
about procedural memory, acting agents, or a trained retention policy. See the paper for the
full list of limitations.

---

## Repository layout

```text
src/p1mem/         Package: benchmark adapters, memory writer and representations,
                   endpoint client and cache, cell schema and validator, analysis code
scripts/           Entry points, named by stage (see "Re-running the experiments")
configs/           Frozen endpoint configuration and the pinned writer prompts
tests/             Test suite (pytest)
cluster/sophia/    Scripts for running the experiments on ALCF Sophia
data/manifests/    Memory-unit, pairing, screen and leakage manifests (small, tracked)
results/ledgers/   Computed analysis outputs and slim data slices (tracked)
paper/             LaTeX source snapshot (AAMAS 2027 class)
website/           Source of the project page
docs/              Protocol decisions, pre-registrations, results ledgers, defect register
```

Raw endpoint outputs and benchmark corpora are **not** in this repository. Benchmark text
carries upstream licenses; model outputs are large. The full per-pair records are released
as the Hugging Face dataset.

---

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory
cd AAMAS2027-ConditionalMemory
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[analysis,dev]"
python -m pytest -q
```

Expected: **617 passed, 37 skipped** (about 50 seconds). The skips are tests that need the
upstream SciCode, SWE-bench or LongMemEval tokenizer files, which are not downloaded.

---

## Reproduce the headline numbers (minutes, no endpoint, no downloads)

`results/ledgers/repro/` contains slim slices of the per-row data. They carry every field the
headline numbers are computed from.

### 1. Answer-bearing versus matched-control contrast

```python
import json, collections
import numpy as np

rows = [json.loads(l) for l in open("results/ledgers/repro/screened_cells_slim.jsonl")]

# One cell = one (memory, task) pair; average its replicates first.
cell = collections.defaultdict(list)
for r in rows:
    cell[(r["memory_id"], r["future_task_id"], r["stratum"])].append(
        r["reward_with_memory"] - r["reward_without_memory"])
cell = {k: np.mean(v) for k, v in cell.items()}

# Within each memory: mean over BEARING cells minus mean over MATCHED_CONTROL cells.
per_memory = collections.defaultdict(lambda: collections.defaultdict(list))
for (m, t, stratum), d in cell.items():
    per_memory[m][stratum].append(d)
contrast = [np.mean(v["BEARING"]) - np.mean(v["MATCHED_CONTROL"])
            for v in per_memory.values() if v["BEARING"] and v["MATCHED_CONTROL"]]

print("memories:", len(contrast))                 # 60
print("contrast: %.4f" % np.mean(contrast))       # 0.3349
for s in ("BEARING", "MATCHED_CONTROL", "RANDOM"):
    d = [x for (m, t, st), x in cell.items() if st == s]
    print(s, "cells:", len(d), "mean ΔU: %.3f" % np.mean(d))
```

Expected output:

```text
memories: 60
contrast: 0.3349
BEARING cells: 139 mean ΔU: 0.345
MATCHED_CONTROL cells: 146 mean ΔU: 0.027
RANDOM cells: 872 mean ΔU: 0.064
```

These are the paper's +0.33 headline and the per-stratum values in Table 2. The confidence
interval is a bootstrap over memories or episodes and is computed by
`scripts/k3_analyze_screened.py` (see below).

### 2. Reader transfer, session-matched

```python
import json, collections
import numpy as np

D = "results/ledgers/repro/raw_session_matched/"

def cells(path):
    c = collections.defaultdict(list)
    for line in open(D + path):
        r = json.loads(line)
        if r["reward_with_memory"] is None or r["reward_without_memory"] is None:
            continue                      # missing rewards are dropped, never scored as 0
        c[(r["memory_id"], r["future_task_id"])].append(
            r["reward_with_memory"] - r["reward_without_memory"])
    return {k: np.mean(v) for k, v in c.items()}

a, b = cells("raw_gptoss_slim.jsonl"), cells("raw_gemma_slim.jsonl")
common = sorted(set(a) & set(b))
print("matched cells:", len(common))                                        # 275
print("gemma − gpt-oss: %.4f" % np.mean([b[k] - a[k] for k in common]))     # 0.0982
```

Expected: **275 matched cells** and a mean change of **+0.0982** (task-clustered 95% interval
[+0.0247, +0.1730], computed in `results/ledgers/repro/raw_session_matched/raw_session_matched_analysis.json`).

### 3. Other computed results

Every other analysis output is a JSON file under `results/ledgers/`. For example:

| Result | File |
|---|---|
| Length control (matched-length arms) | `results/ledgers/length_control_result.json` |
| Gold-free screens | `results/ledgers/gf_llm_effect.json`, `gf_gold_free_effect.json` |
| SciCode and SWE-bench contrasts | `results/ledgers/repro/scicode/`, `results/ledgers/repro/swebench/` |
| Reader transfer controls | `results/ledgers/repro/gemma_reader/` |
| Screened-run analysis | `results/ledgers/repro/k3_screened_analysis.json`, `k4_tables.md` |

`docs/PAPER_ARTIFACT_MAP.md` maps every figure and table in the paper to its generator, input
file and unit.

---

## Use the released dataset

The dataset has 16,816 evaluation records across 3 benchmarks, 2 readers and 29 experimental
conditions. No login is needed.

```python
from datasets import load_dataset
import pandas as pd

df = load_dataset("AgentsSci/AAMAS2027-ConditionalMemory", "overview", split="train").to_pandas()

# The screened primary run, paired within memory.
s = df[df.condition_id == "lmev2_raw_metis_gptoss120b_screened_v1"].dropna(subset=["delta_utility"])
cell = s.groupby(["memory_id", "future_task_id", "bearing_label"]).delta_utility.mean().reset_index()
per_memory = cell.groupby(["memory_id", "bearing_label"]).delta_utility.mean().unstack()
print((per_memory["BEARING"] - per_memory["MATCHED_CONTROL"]).dropna().mean())   # about +0.33
```

Notes before analyzing it:

- `delta_utility = reward_with_memory − reward_without_memory`. Missing rewards are `null`,
  never 0. Use the numeric scores; the `utility_label` column is `undetermined` throughout.
- Select experiments by `condition_id`. Truncation arms keep `memory_representation = raw`,
  so that field alone does not separate them.
- `lmev2_trunclast_20000_lenctl_v1` is an A/A identity control. Do not pool it with Raw.
- Do not deduplicate or join on `row_id`, `cell_id` or `memory_id`: they are content hashes
  and a few collide. `source_line` locates a record uniquely.
- Do not randomly split replicate rows of the same memory or task into train and test sets.
- The `overview` table is on `main`. Pin a dataset revision for reproducible use. The full
  98-field records are in the dataset repository file `data/cells.jsonl` at the
  `v0.6-length-control` tag.

The dataset card describes the schema, coverage, withheld text and reuse terms.

---

## Re-running the experiments

This level needs the upstream benchmarks and access to the model endpoints. Inference
results are deterministic **within** a session and not across sessions, so any comparison
must run its arms in the same session (see `docs/SESSION_DETERMINISM_AUDIT.md`).

### Inputs

| Input | Source | Where the code expects it |
|---|---|---|
| LongMemEval-V2 (Apache-2.0) | [`xiaowu0162/longmemeval-v2`](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2) | `/tmp/lmev2/` (hard-coded in many scripts; verify with `checksums.sha256`) |
| SciCode | upstream repository | see `src/p1mem/adapters/scicode.py` |
| SWE-bench Verified | upstream dataset | see `src/p1mem/adapters/swebench.py` |
| Reader and writer models | ALCF inference service (`gpt-oss-120b`; second reader `gemma-4-31B-it`) | `configs/endpoint_primary.json` |
| Embeddings | `SFR-Embedding-Mistral` (4096-d) | `configs/endpoint_primary.json` |

Frozen configuration: temperature 0, low reasoning effort, `max_tokens` 512, 16 concurrent
workers, seed 20261008. Changing any pinned field defines a new arm, not a backfill. Empty or
truncated completions raise and are re-run, never scored as zero.

### Pipeline

Run from the repository root. Every runner is resumable through the response cache and ends
by printing a verdict; read the verdict and row count, since exit code 0 alone is not success.

| Paper result | Scripts, in order |
|---|---|
| Memory units and pairing (§4) | `build_lmev2_units.py` |
| Screened design and the headline contrast (§5.1, §5.2) | `k1_build_screened_design.py` → `k2_run_screened.py` → `k3_analyze_screened.py` → `k4_report_tables.py` |
| Representations (§5.4) | `r1_write_representations.py` → `r2_run_representations.py` → `r3_analyze_representations.py` |
| Length control (§5.4) | `len1_build_length_control.py` → `len2_analyze_length_control.py` |
| Gold-free screens (§3.2) | `gf1_` … `gf7_` (in order) |
| Second reader and writer × reader factorial (§5.5) | `gemma_reader_run.py` → `gemma_reader_analyze.py`; `w1_` … `w5_`; `raw_session_matched_analysis.py` |
| Second session, fixed total context, retrieval (§5.2–5.4, S11) | `x1_position_session.py`, `x2_fixed_context.py`, `x3_retrieval_baseline.py` |
| SciCode and SWE-bench (S6) | `scicode_pilot.py`, `swebench_representations.py`, `swebench_multirepo_analysis.py` |

To run on ALCF Sophia, use the scripts in `cluster/sophia/`
(`configure.sh` → `setup.sh` → `interactive.sh` → `submit.sh` → `status.sh`).

Regenerating the paper's generated numbers and checking every manuscript claim uses
`scripts/make_figures.py` and `scripts/audit_claims.py`. These read the full per-row
artifacts under `results/` and `/tmp/lmev2/questions.jsonl`, which a fresh clone does not
contain, so they are for the authors' working tree. A fresh clone verifies the numbers through
the slim slices above.

---

## Build the paper source

```bash
cd paper
latexmk -pdf -interaction=nonstopmode main.tex   # run twice: bibtex needs the second pass
```

The first pass reports undefined citations until bibtex has run. The release manuscript is
`website/paper.pdf`.

---

## Documentation

| Read this | For |
|---|---|
| `docs/PAPER_ARTIFACT_MAP.md` | Every figure and table → generator, input, unit |
| `docs/REPRODUCIBILITY.md` | Reproduction levels and assumptions |
| `docs/MEMORY_PROTOCOL.md`, `docs/MEMORY_REPRESENTATIONS.md` | How memories are written and represented |
| `docs/BEARING_SCREEN_DISCLOSURE.md`, `docs/LEAKAGE_AUDIT.md` | The answer-bearing screen and leakage checks |
| `docs/ANALYSIS_PREREGISTRATION.md` | Pre-registered analyses |
| `docs/DEFECT_REGISTER.md` | Instrument defects found and fixed |
| `docs/BENCHMARK_LICENSES.md` | Upstream licenses and the release policy |

The remaining files in `docs/` are working notes kept for provenance.

---

## Citation

```bibtex
@misc{yang2026memoryuseful,
  title  = {What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent Memory},
  author = {Yang, Chih-Hsuan and Chowdhury, Anjir Ahmed and Yan, Feng and Thakur, Rajeev},
  year   = {2026},
  note   = {Preprint}
}
```

Dataset:

```bibtex
@misc{yang2026conditionalmemorydataset,
  author       = {Yang, Chih-Hsuan and Chowdhury, Anjir Ahmed and Yan, Feng and Thakur, Rajeev},
  title        = {Conditional Memory Utility Dataset},
  year         = {2026},
  howpublished = {Hugging Face},
  url          = {https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory}
}
```

## Data terms and acknowledgments

Benchmark text keeps its upstream license; see `docs/BENCHMARK_LICENSES.md` and the dataset
card. Restricted upstream text is withheld from the release.

This research used resources of the Argonne Leadership Computing Facility, a U.S. Department
of Energy (DOE) Office of Science user facility at Argonne National Laboratory operated under
Contract No. DE-AC02-06CH11357, and was supported by the DOE Office of Science's Advanced
Scientific Computing Research Program and by Laboratory Directed Research and Development
(LDRD) funding from Argonne. The University of Houston coauthors were supported in part by the
National Science Foundation under grants CAREER-2305491 and CNS-2504762.

Contact: <bellayang@anl.gov>

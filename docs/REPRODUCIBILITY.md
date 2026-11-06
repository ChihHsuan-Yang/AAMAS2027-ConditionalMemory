# Reproducibility

Commands on this page were run against the current public release (manuscript `website/paper.pdf`;
dataset snapshot built 2026-10-02, follow-up runs added to the dataset). Last
verified **2026-11-02**. Nothing here re-runs model inference.

What can and cannot be reproduced from public artifacts, item by item, is in
[`RELEASE_COVERAGE.md`](RELEASE_COVERAGE.md). Read it before claiming a full reproduction.
In short: the primary result, the representation, length-control, reader-transfer, gold-free and
cross-benchmark results, and the three later runs (fixed total context, second session with randomized
position, retrieval) are reproducible or checkable from public files. The later runs live in the
dataset folder `followups_package/` (revision `332cd047e9093a948606c4251bf5b294b0664762`). The scripts
that draw the release figures are not in this repository.

## 1. Install and test (about one minute)

Python 3.10 or newer (3.9 fails: a vendored scorer uses `str | None`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[analysis,dev]"
python -m pytest -q
```

Expected on a clean machine with no upstream corpora cached: **629 passed, 37 skipped**. The
skipped tests need the SciCode corpus, the SWE-bench parquet or the LongMemEval tokenizer; a
machine that has them cached skips fewer and passes more. A failure is a defect; a skip is not.

## 2. Smallest reproduction of the primary result (seconds)

```bash
python scripts/reproduce_headline.py --bootstrap 10000
```

Reads the tracked slice `results/ledgers/repro/screened_cells_slim.jsonl` and prints:

```text
rows             : 2599
cells            : 1157
  BEARING          cells=139  mean dU=+0.345
  MATCHED_CONTROL  cells=146  mean dU=+0.027
  RANDOM           cells=872  mean dU=+0.064
  BEARING          both-arms-fail share of rows=0.525
  MATCHED_CONTROL  both-arms-fail share of rows=0.788
  RANDOM           both-arms-fail share of rows=0.701
memories (both)  : 60
contrast         : +0.334861   (expected +0.334861)
95% CI memories  : [+0.209, +0.463]   (10000 resamples, seed 20261008)
95% CI episodes  : [+0.196, +0.475]
VERDICT: REPRODUCED
```

These match the paper: contrast +0.33 [+0.21, +0.46] over memories and [+0.20, +0.47] over
episodes, 139 / 146 / 872 cells (Table 2), both-arms-fail 0.53 / 0.79 / 0.70. The point
estimate is exact; the intervals are percentile bootstraps and agree to the paper's two
decimals. The exit status is non-zero on a mismatch.

Units: a *row* is one replicate of one pair, a *cell* one (memory, task) pair with replicates
averaged, and the contrast is taken over memories. Missing rewards are dropped, never scored
as zero.

### The same check on the public dataset

```bash
pip install huggingface_hub pyarrow
python - <<'PY'
from huggingface_hub import hf_hub_download
print(hf_hub_download("AgentsSci/AAMAS2027-ConditionalMemory", "data/overview.parquet",
      repo_type="dataset", revision="332cd047e9093a948606c4251bf5b294b0664762"))
PY
python scripts/reproduce_headline.py --overview <path printed above>
```

The pinned revision is the dataset commit that introduced the overview table. The overview
holds 16,816 records; the script selects the primary condition
`lmev2_raw_metis_gptoss120b_screened_v1` (2,599 records). The expected output is the same as
above. The dataset audit of 2 November reports the same value (+0.334861 over 60 memories).

## 3. Other headline values checkable from tracked files

| Quantity | Expected | Where |
|---|---|---|
| Reader transfer, session-matched (gemma minus gpt-oss, Raw) | **+0.0982**, task-clustered 95% CI [+0.0247, +0.1730]; 275 cells, 123 tasks, 550 replicate rows | `results/ledgers/repro/raw_session_matched/` |
| Gold-free screen, cells the gold screen never selected | 15.6% → 50.0% correct; contrast +0.37 [+0.05, +0.70] | `results/ledgers/gf_llm_effect.json` |
| Length control, extractive vs Summary at matched length | +0.0519 [−0.0678, +0.1727]; verdict `O2_EFFECT_DISAPPEARS_AT_MATCHED_LENGTH` | `results/ledgers/length_control_result.json` |
| SciCode, SWE-bench representation contrasts | every interval includes zero | `results/ledgers/repro/scicode/`, `results/ledgers/repro/swebench/representations_multirepo_final.json` |

Reader transfer recomputed from the slices (the paper's paired difference):

```python
import json, collections, numpy as np
D = "results/ledgers/repro/raw_session_matched/"
def cells(path):
    c = collections.defaultdict(list)
    for line in open(D + path):
        r = json.loads(line)
        if r["reward_with_memory"] is None or r["reward_without_memory"] is None:
            continue
        c[(r["memory_id"], r["future_task_id"])].append(r["reward_with_memory"] - r["reward_without_memory"])
    return {k: np.mean(v) for k, v in c.items()}
a, b = cells("raw_gptoss_slim.jsonl"), cells("raw_gemma_slim.jsonl")
common = sorted(set(a) & set(b))
print(len(common), round(float(np.mean([b[k] - a[k] for k in common])), 4))   # 275 0.0982
```

The SWE-bench figure in the paper is the `_final` ledger above. Re-running
`scripts/swebench_multirepo_analysis.py` writes `results/swebench/representations_multirepo.json`,
which is an older output that lacks the family-wise columns the script now emits; it does not
change the nominal verdict (`NOT_ESTABLISHED`). Do not treat that file as the paper's source.

## 4. What needs files that are not in this repository

These scripts run on the authors' working tree, which holds full per-row artifacts under
`results/` and the upstream corpus at `/tmp/lmev2/`. A fresh clone cannot run them:
`k3_analyze_screened.py`, `r3_analyze_representations.py`, `raw_session_matched_analysis.py`,
`len2_analyze_length_control.py`, `make_figures.py`, `audit_claims.py`.
`make_figures.py` and `audit_claims.py` regenerate the macros of the earlier TikZ manuscript
(`paper/`), not the figures of the current release PDF.

The upstream LongMemEval-V2 corpus (Apache-2.0) is
[`xiaowu0162/longmemeval-v2`](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2).
Many scripts read it from `/tmp/lmev2/` (hard-coded); verify it with the corpus's own
`checksums.sha256`.

## 5. Re-running model inference (not required, not part of this checklist)

Needs access to the ALCF inference service. Entry points and call counts are in
`scripts/` and `cluster/sophia/README.md` (`k2_run_screened.py` 5,198 calls;
`x1_position_session.py` 1,710; `x2_fixed_context.py` 2,770; `x3_retrieval_baseline.py`
embeddings only). Frozen configuration: `configs/endpoint_primary.json` (temperature 0,
low reasoning effort, `max_tokens` 512, seed 20261008).

`gpt-oss-120b` is deterministic **within** a session and not across sessions: re-issuing 1,124
byte-identical memory-free requests a day later changed 82 rewards. Any comparison must run
its arms in one session, and a new run will not reproduce an old session's outputs. Each runner
ends by printing a verdict; read the verdict and row count, since exit code 0 alone is not
success.

## 6. The later runs (fixed total context, second session, retrieval)

Published in the dataset folder `followups_package/`; commands to regenerate Table S5 are in
[`RELEASE_COVERAGE.md`](RELEASE_COVERAGE.md). Checked values: x2 excluding exposed cells, Raw +0.351,
Summary +0.039, Structured +0.013, Summary minus Raw −0.312, with 63 exposed pairs and 77 / 135 bearing cells;
x1 contrast +0.497 [+0.37, +0.63]; x3 recall@10 0.403 for dense chunks.

## 7. Paper source

The release manuscript source is [`../manuscript/`](../manuscript/) and its PDF is `website/paper.pdf`.
The macros under `manuscript/macros/` record the numbers; the scripts named in their comments are not in
this repository. `paper/` is an older snapshot (see `paper/README.md`).

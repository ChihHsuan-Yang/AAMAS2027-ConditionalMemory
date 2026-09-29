# data/

**Nothing in this directory is committed** except this README and `manifests/`.
See `.gitignore`.

## Why

Benchmark corpora carry their own licenses and are large. This repo records *how to
obtain and verify* the data, never the data itself.

| Dataset | License | Obtain | Redistribute here? |
|---|---|---|---|
| LongMemEval V1 (cleaned) | MIT | HF `xiaowu0162/longmemeval-cleaned` | No |
| LongMemEval-V2 | Apache-2.0 | see `docs/EXPERIMENT_PLAN.md` | No |
| MERIT | MIT (repo) | upstream repo | No |

⚠️ LongMemEval V1's filler derives from **ShareGPT and UltraChat**, which carry their own
upstream terms independent of the MIT grant. Check before redistributing any derived
haystack.

## manifests/

Committed. For each dataset actually used: source URL, resolved revision/commit, file
sha256, row count measured locally, and the date measured. **A manifest entry asserts a
number someone actually computed on this machine** — never a number copied from a paper or
from an inherited note.

## Current status

Empty. No dataset has been obtained or verified yet.

> **Known provenance defect (2026-09-29):** the inherited `DATASETS.md` reports counts
> "measured directly" from `lme_v2_small.json`, but that file is not present anywhere on
> this machine. Those numbers are unsourced until reproduced. See `docs/DECISION_LOG.md` D3.

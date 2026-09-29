# Results Ledger

Every number that appears in the manuscript must appear here first, with the artifact path
that produced it and the date it was measured.

**A number in the paper that is not in this ledger is a bug.**

## Rules

1. Every row names an artifact path that can be re-read.
2. Every row names the measurement date. Derived figures go stale when their basis changes
   — check basis dates against intervening changes before reusing a number.
3. Retracted numbers are **labelled retracted, not deleted.** Deleting them kills the
   repair the retraction prescribes.
4. Re-derive before quoting into a durable document. Do not copy from a scratch note.

## Ledger

| # | Quantity | Value | Artifact | Measured | Status |
|---|---|---|---|---|---|
| — | — | — | — | — | *no results yet* |

## Inherited numbers pending re-derivation

These come from the 2026-09-28 notes. **None may be quoted until reproduced locally.**

| Quantity | Inherited value | Source claim | Status |
|---|---|---|---|
| LongMemEval-V2 (memory, task) cells | 45,100 | "measured from `lme_v2_small.json`" | 🔴 **UNSOURCED** — file absent from this machine |
| V2 web questions sharing one haystack | min=median=max=240 | same | 🔴 **UNSOURCED** — same reason |
| V2 no-memory floor | 1.3% | same | 🔴 **UNSOURCED** — same reason |
| V1 natural (m,t) cells | 679 | parsed `longmemeval_s_cleaned.json` (277 MB) | ⚠️ unverified — file not located yet |
| V1 ground-truthed knowledge-update pairs | 72 | same | ⚠️ unverified |
| V1 sessions per question | 38–62, mean 47.7 | same | ⚠️ unverified |
| Full-haystack context cost | ~122k tokens/question | same | ⚠️ unverified |
| `lattice.py` `POOL_SIZE` | 5, hardcoded | code read 2026-09-28 | ⚠️ being re-verified (Sub-agent B) |
| `agentverse/llms/openai.py` | 1,508 lines | code read 2026-09-28 | ⚠️ being re-verified |
| `analyze_conditional_value.py` | 1,079 lines | code read 2026-09-28 | ⚠️ being re-verified |

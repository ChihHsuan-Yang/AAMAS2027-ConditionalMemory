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
| 1 | ALCF Sophia chat model resolved id | requested `openai/gpt-oss-120b` → resolved `openai/gpt-oss-120b` (identical, no aliasing) | live health check | 2026-09-29 | VERIFIED |
| 2 | Fixed prompt-scaffold overhead | 71 prompt tokens for a 3-word message | same health check | 2026-09-29 | VERIFIED — do not charge to memory content when costing |
| 3 | `Salesforce/SFR-Embedding-Mistral` serves | yes, dim **4096** | live POST by Master Agent | 2026-09-29 | VERIFIED |
| 4 | `mistralai/Mistral-7B-Instruct-v0.3-embed` serves | yes, dim **4096** | live POST | 2026-09-29 | VERIFIED |
| 5 | `google/embeddinggemma-300m` serves | **no — 502 Bad Gateway** | live POST | 2026-09-29 | VERIFIED NEGATIVE (advertised but not serving) |
| 6 | SFR embedding determinism | `cos(identical texts) = 1.0` exactly; unrelated pair 0.5458 | live batch POST | 2026-09-29 | VERIFIED — required for NEAR/MID/FAR |
| 7 | Variance/interaction machinery in `analyze_conditional_value.py` | **none** — 0 hits for `varian\|interact\|anova\|decompos\|np.var\|sigma` over 1,079 lines | Master Agent grep | 2026-09-29 | VERIFIED — headline analysis must be written |
| 8 | `replicate_id` support in `analyze_conditional_value.py` | **absent** (0 occurrences); validator raises on duplicate `(problem_id, mask)` at line 130 | Master Agent grep + read | 2026-09-29 | VERIFIED — would reject P1's seeds |
| 9 | `replicate_id` support in `analyze_reliability.py` | **present**, keys on `(problem_id, mask, replicate_id)` | Master Agent read, lines 43/56/68/73/82 | 2026-09-29 | VERIFIED — start here |
| 10 | AAMAS 2027 abstract length rule | "around 100-300 words in plain text" | warwick.ac.uk instructions page | 2026-09-29 | VERIFIED |
| 11 | Drafted abstract length | 268 words | `docs/submission/abstract_v1.txt` | 2026-09-29 | VERIFIED in range |

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
| `lattice.py` `POOL_SIZE` | 5, hardcoded | code read 2026-09-28 | ✅ CONFIRMED (153 lines, exact) |
| `agentverse/llms/openai.py` | 1,508 lines | code read 2026-09-28 | ✅ CONFIRMED exact — but its `get_embedding` is broken 3 ways, and the chat path is NOT tenacity-retried |
| `analyze_conditional_value.py` | 1,079 lines | code read 2026-09-28 | ✅ CONFIRMED exact — but contains NO variance/interaction analysis and rejects `replicate_id` |

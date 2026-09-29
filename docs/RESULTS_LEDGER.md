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
| 12 | Minerva `gpt-oss-120b` serves | **NO — HTTP 503 persistent**, 4 retries over ~2 min, identical body `"not currently live on Minerva"` | Sub-agent C real POST | 2026-09-29 | VERIFIED NEGATIVE |
| 13 | Minerva `inkling-bf16`, `nemotron-3-ultra` serve | yes, resolved ids identical to requested | real POST | 2026-09-29 | VERIFIED |
| 14 | Cluster `tara` | listed but `"frameworks": {}` — unusable | list-endpoints | 2026-09-29 | VERIFIED |
| 15 | Metis vs Sophia latency, `gpt-oss-120b` | 4k: **0.728 s** vs 3.387 s · 16k: **1.082 s** vs 2.500 s | probe, server-counted prompt tokens | 2026-09-29 | VERIFIED |
| 16 | Long-context needle retrieval, 4 models × 16.8k/31.5k | **12/12 correct** (corrected harness) | Sub-agent C | 2026-09-29 | VERIFIED |
| 17 | Sophia reports `reasoning_tokens` | **no** — `completion_tokens_details` absent; Metis does report it | probe | 2026-09-29 | VERIFIED — decided the cluster choice |
| 18 | Reasoning tokens share the `max_tokens` budget | yes — at `max_tokens=64`, content null, `finish_reason=length`, needle found inside `reasoning` | Sub-agent C instrument defect | 2026-09-29 | VERIFIED — binding call constraint |
| 19 | LongMemEval-V2 `trajectories.jsonl` | 1,195,604,539 bytes, sha256 `363cec9a…f3c6` **matches `checksums.sha256`** | Sub-agent A download + verify | 2026-09-29 | VERIFIED (earlier 125MB `traj_head.jsonl` was a truncated prefix, 154 lines, superseded) |
| 20 | V2 `eval_function` DISTINCT SPECS | **8**, not 6 — `norm_phrase_set_match` splits into `separators=,;` (199) and `separators=;` (1); ordered splits 19/7 | Sub-agent A, full spec strings | 2026-09-29 | VERIFIED — adapter must dispatch on the FULL spec, never the function name |
| 21 | V2 deterministic question count | **295** (199+1+68+1+19+7) | Sub-agent A, independently | 2026-09-29 | VERIFIED — agrees with Master Agent's 295 |
| 22 | V2 official scorer provenance | `harness.py` in `/tmp/lmev2` is **byte-identical** to the official repo's (`sha256 93fe5855…bdb9`), HEAD `2cc8c540`, **Apache-2.0** | Sub-agent A | 2026-09-29 | VERIFIED — vendor the scorer, do not reimplement |
| 23 | `norm_phrase_set_match` semantics | **NOT set equality** — gold-phrase containment (recall-only); extra prediction content is unpenalized | Sub-agent A, read from source | 2026-09-29 | VERIFIED — inferring from the name would have been wrong |
| 24 | V2 memory unit = page visit | median **7,261** tok (p25 5,055, p75 13,501, p90 35,994), n=**1,889** units from 200 trajectories / 5,095 states | official `Qwen/Qwen3.5-9B` tokenizer | 2026-09-29 | VERIFIED |
| 25 | V2 whole-trajectory tokens | median **103,886**, p90 646,256, max 2,573,538 | same | 2026-09-29 | VERIFIED — the inherited "~164k" is unrepresentative; distribution is right-skewed |
| 26 | Ablation locality | one unit = median **3.3%** of its episode, **0.058%** of the haystack | Sub-agent A | 2026-09-29 | VERIFIED — the intervention is local, as the protocol requires |
| 27 | Segmentation preserves answerability | **94.2%** of deterministic questions | Sub-agent A | 2026-09-29 | VERIFIED |
| 28 | V2 memory × task pairs | **15,112** rows = **1,889 memories × exactly 8 tasks each** | Master Agent recount of the pair manifest | 2026-09-29 | VERIFIED |
| 29 | BEAM diagonality | **92.6%** of cited turns cited by exactly one question | Sub-agent A | 2026-09-29 | VERIFIED — cannot supply the multi-task axis; BEAM demoted |
| 30 | SciCode usable N | **~8–12** cross-problem donor→recipient pairs | Sub-agent A | 2026-09-29 | VERIFIED — case study, not a main table |
| 31 | V1 leakage detector separation | evidence **471/948 = 49.684%** vs filler **4,492/22,919 = 19.599%**, ratio **2.53×** | Master Agent re-derivation | 2026-09-29 | VERIFIED — ⚠️ manifest holds only FLAGGED rows; using it as the denominator gives a meaningless 76.2/48.3 |
| 32 | Leakage detector controls | **17/17** pass; 2 failed on first run (one exposed a real bug in the OFFICIAL scorer) | Sub-agent A | 2026-09-29 | VERIFIED — all leak rates are LOWER BOUNDS |
| 33 | Representation tokens (8 real segments) | raw median **6,372** (cr 1.000, **0 calls**) · summary **362** (cr 0.0630) · structured **246** (cr 0.0373) | Sub-agent B pilot, 24 calls on Metis | 2026-09-29 | VERIFIED |
| 34 | Structured reasoning cost | **3.8×** the reasoning tokens of summary, for a **shorter** output (829 vs 216) | same | 2026-09-29 | VERIFIED — a real efficiency finding |
| 35 | Structured malformed-JSON rate | **0/8** (95% Jeffreys upper bound ≈ 0.28) | same | 2026-09-29 | VERIFIED — denominator stated; shows only that the rate is not large |
| 36 | `memory_semantic_type` inter-pass agreement | **3/8 = 0.375, Cohen's κ = 0.000** (native pass labelled all 8 `episodic`) | Sub-agent B | 2026-09-29 | VERIFIED — ⚠️ **not safe as an analysis axis** |
| 37 | Structured contradiction rate | 0.667 is a **scope-collision artifact**; **0.000** excluding it | Sub-agent B | 2026-09-29 | VERIFIED — must never be quoted as a hallucination rate |
| 38 | Metis sustained throughput | **5.690 req/s, 341.4 completed/min**, p50 2.588 s, p95 4.392 s, 61,323 tok/s @16 workers | Sub-agent C, 6-wave | 2026-09-29 | VERIFIED |
| 39 | Concurrency ceiling | 0 failures /316 reqs at ≤16; **429s at 24 (12.50%)** and 32 (8.33%); 32 buys +2.6% throughput | Sub-agent C | 2026-09-29 | VERIFIED — ceiling observed, not assumed |
| 40 | REML recovery error vs study size | 30×8: **0.0627** (worst 0.1175) · 60×8: 0.0238 · 120×8: 0.0231 · 240×8: 0.0155 · **120×16: 0.0103** | Master Agent, synthetic with known planted components | 2026-09-29 | VERIFIED — 60 memories minimum; widen the TASK axis |

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

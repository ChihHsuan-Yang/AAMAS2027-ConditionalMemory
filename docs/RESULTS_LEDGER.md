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
| 41 | **FIRST REAL EXECUTION** — noise-floor probe | 96 cells, **92 ok / 4 truncated** | `results/runs/noise_floor/ledger.jsonl` | 2026-09-29 | VERIFIED |
| 42 | Truncation guard fires on real data | 4 cells, `reasoning_tokens=510` consumed the 512 budget → raised, not scored | same | 2026-09-29 | VERIFIED — would otherwise have manufactured false negatives |
| 43 | ~~Replicate disagreement at temp 0 = 4.3%, "endpoint is NOT deterministic"~~ | **RETRACTED** — my replicates were not byte-identical | same | 2026-09-29 | 🔴 **RETRACTED, see rows 43a–43c.** The measurement was real; the *interpretation* was wrong |
| 43a | Why row 43 was wrong | `build_cell_pair` put `replicate_id` into `seed_parts`, so **target position was re-randomized every replicate** (verified: positions `[4,5,4,4]` over 4 replicates) | `src/p1mem/cells.py` | 2026-09-29 | VERIFIED — replicates varied the INPUT, so their spread is not execution noise |
| 43b | The split that proves it | text disagreement **0/11** on the WITHOUT arm (position N/A → prompts byte-identical) vs **8/12** on the WITH arm (position re-seeded) | Master re-derivation of `noise_floor/cache.jsonl` | 2026-09-29 | VERIFIED — zero disagreement wherever the prompt was actually fixed |
| 43c | Endpoint determinism, measured in the target regime | **6/6 prompts byte-identical across 4 repeats**, 24 real calls, cache DISABLED, 23k–27k tokens, concurrency 16 | `results/noise/determinism_probe_target_regime.json` (Sub-agent G) | 2026-09-29 | VERIFIED — **the endpoint IS deterministic at temperature 0** |
| 43d | 🔬 **Position effect (a real finding, not noise)** | **8 of 12** WITH-arm cells changed their answer when ONLY the target memory's position moved | same cache | 2026-09-29 | VERIFIED — a genuine confound; position must be held fixed across replicates, and this deserves its own measurement |
| 43e | Reward vs text disagreement are different quantities | **1/23 groups** disagree on REWARD; **8/23** on TEXT — an 8× gap | same | 2026-09-29 | VERIFIED — F_exec needs reward disagreement, F_judge needs text disagreement. Label which one is meant |
| 44 | Probe accuracy | **2 / 92** | same | 2026-09-29 | VERIFIED — ⚠️ artifact of MY design (one arbitrary target memory per task, 2 distinct memories total), not a model result. Floor measured in an uninformative regime; superseded by the paired run |
| 45 | `select_filler` defect (Master-authored, found by Sub-agent G) | **25/25** exclusions of a NON-drawn memory changed the filler → **0/25** after fix | `tests/test_cells.py` | 2026-09-29 | VERIFIED + regression-tested |
| 46 | V2 leakage, FULL matrix | 423,664 cells, 114,207 flagged: ≤2ch **97.71%** · 3–5 44.74% · 6–12 23.48% · 13–30 6.84% · **>30 4.68%** · pooled 26.96% | Sub-agent A | 2026-09-29 | VERIFIED — **never quote the pooled 26.96%**; the 97.7% row is multiple-choice golds and measures the alphabet. **Credible rate: 4.68%** |
| 47 | **FIRST ΔU PILOT** | 1,918 real calls, **479 cells**, 60 memories, 220 tasks, 2 replicates, 441.8 s @16 | `results/deltau_pilot/cells.jsonl` | 2026-09-29 | VERIFIED — Master recomputed every figure from rows |
| 48 | **F_exec (ΔU scale)** | **0.000** — 0/479 cells disagree across byte-identical replicates | same | 2026-09-29 | VERIFIED; positive control **fires** (0.5098 on a planted defect) |
| 49 | **F_empty** | **0.000** — 774 distinct cache keys AND 774 distinct latencies ⇒ 774 independent real calls | same | 2026-09-29 | VERIFIED — independence proven by call count, not assumed |
| 50 | **F_judge** | **0.000** — 0 disagreements / 1,916 re-scorings | same | 2026-09-29 | VERIFIED; positive control **fires** (0.3175) |
| 50a | `F_judge = 0.1486` (first reported) | **RETRACTED** — estimator grouped byte-identical text WITHOUT the task, so `\boxed{F}` right for one question and wrong for another counted as scorer disagreement; all 18 groups spanned tasks | `analysis/noise.py` | 2026-09-29 | 🔴 RETRACTED — fixed + regression-tested |
| 51 | ΔU distribution (before labelling) | **20 positive · 438 zero · 21 negative** | Master recount | 2026-09-29 | VERIFIED — matches G exactly |
| 52 | Accuracy, hand-written prompt arm | WITH **0.1712** (164/958) · WITHOUT **0.1733** (166/958) | same | 2026-09-29 | VERIFIED |
| 53 | Robust / naive flip rate | both **0.1333** [0.069, 0.242], denominator 60, gap **0.000** | same | 2026-09-29 | VERIFIED — ⚠️ coincide MECHANICALLY (F=0 makes the floor clause vacuous; 2 agreeing replicates give a degenerate CI). **The gap is not measurable at 2 replicates** |
| 54 | Excess over the additive null | observed **0.1333** vs null **0.9667**, p=1.000 | same | 2026-09-29 | VERIFIED |
| 54a | ~~"variance shares all 0.0000"~~ | 🔴 **RETRACTED — never measured.** The value came from `.get(c, 0.0)` over an **empty dict**: a `ZeroDivisionError` (`interaction / F_exec²`, with F_exec = 0.0 — the *expected* value for a deterministic reader) crashed the decomposition stage **while the script exited 0**. I reported it as a measured zero in an hourly report | Sub-agent H | 2026-09-29 | 🔴 RETRACTED. An absent value defaulted to a plausible number |
| 54b | REML fit is **NOT IDENTIFIED** | task and interaction shares **exactly equal to 16 s.f.** in both arms, both pinned at the optimizer's `exp(12)` clip ceiling — yet `converged=True` with a tight CI. The module guarded only the LOWER boundary | Sub-agent H | 2026-09-29 | VERIFIED — new `AT_UPPER_BOUNDARY` flag stable across 7 seeds (convergence itself was seed-dependent, 5/7) |
| 54c | Why it is not identified | **8 tasks per memory** (all 60 memories), and only **127 of 220 tasks** are seen by more than one memory | Master Agent re-derivation | 2026-09-29 | VERIFIED — interaction is identified only by shared (memory, task) coverage. **Widen the TASK axis**, per POWER_ANALYSIS (120×16 beats 240×8) |
| 54d | **No variance shares are reported for either arm** | — | — | 2026-09-29 | Not a sample-size problem (60 memories satisfies POWER_ANALYSIS) but an **identifiability** problem |
| 55 | 🔴 **Why the null is uninformative** | **376 / 479 cells (78.5%) have BOTH arms failing** — structurally incapable of showing a memory benefit | Master diagnostic | 2026-09-29 | VERIFIED — **kill criterion NOT triggered** |
| 56 | Flip rate on cells that CAN move | **8/33 = 0.2424** (vs 0.1333 over all 60) | Master diagnostic | 2026-09-29 | VERIFIED — ⚠️ **post-hoc, conditions on an outcome.** A diagnostic of why the null is uninformative, **never** the result |
| 57 | Root cause of the floor effect | our `SYSTEM` prompt is hand-written; the official `DOMAIN_SYSTEM_PROMPTS` forbids guessing and mandates `\boxed{UNKNOWN}`. Ours abstains **0/958**, official **5/12** | `/tmp/lmev2/harness.py:71` | 2026-09-29 | VERIFIED — re-run queued as a NEW arm |
| 58 | **OFFICIAL-PROMPT ARM** | 1,920 calls, 0 cache hits, 0 errors, 960 rows / 0 rejected | `results/deltau_official/cells.jsonl` | 2026-09-29 | VERIFIED — Master recomputed from rows |
| 59 | Accuracy, official prompt | WITH **110/960 = 0.1146** · WITHOUT **116/960 = 0.1208** | same | 2026-09-29 | VERIFIED — **DOWN 5.7 pts** from the hand-written arm |
| 60 | 🔴 Both-arms-fail, official prompt | **402/480 = 83.75%** (pilot: 376/479 = 78.50%) | same | 2026-09-29 | VERIFIED — **the fix made it WORSE**; cells able to move fell 103 → 78 |
| 61 | Mechanism | **128** responses correct under the hand-written prompt became **abstentions** (378 WITH / 390 WITHOUT vs 0/958). `harness.py:1055` scores an abstention **0**, identical to a wrong answer | Sub-agent H, 1,916 paired responses | 2026-09-29 | VERIFIED — paired McNemar **p = 1.12e-09**. Suppressing guesses can only lower accuracy here |
| 62 | 🔴 **The bottleneck is READER CAPABILITY** | on cells whose memory text **literally contains the gold answer** (defined by content, not outcome — not a selected subgroup), WITH still scores only **0.2288** hand-written / **0.1429** official, and **72–79% still fail both arms** | Sub-agent H | 2026-09-29 | VERIFIED — not the pairing, not the prompt |
| 63 | Excess over additive, official arm | observed **0.13333** vs null **0.96667**, **p = 1.000**; all three floors **0.000000**, each positive-controlled (0.5093 / 0.5445 / 0.2941) | same | 2026-09-29 | VERIFIED — uninformative for the same reason as the pilot |
| 54a | 🔴 **RETRACTION of "variance shares all 0.0000"** | the decomposition **never fit**: `shares={}`, `components={}`, `total_variance=0.0`, `converged=false`, flags `NON_CONVERGENCE` + `FIT_FAILED`; the moments fallback refused with *"balanced sub-design is 0x220; needs >= 2x2"*. The printed 0.0000 comes from `dec.shares.get(c, 0.0)` over an **empty dict** | `results/deltau_pilot/analysis/03_variance_decomposition.json` | 2026-09-29 | 🔴 **RETRACTED — the correct value is UNMEASURED.** Absence defaulted to a plausible zero, and it read as the strongest possible null on the paper's headline quantity |
| 58 | Official-prompt arm, accuracy | WITH **0.1146** (110/960) [0.0960, 0.1363] · WITHOUT **0.1208** (116/960) [0.1017, 0.1430] | `results/ledgers/h_official_arm_run_summary.json`, `h_prompt_arm_comparison.json` | 2026-09-29 | VERIFIED — 1,920 real calls, 0 errors, 960 rows, 0 rejected |
| 59 | 🔴 Official-prompt arm, both-arms-fail | **402/480 = 0.8375** [0.8018, 0.8678], vs 376/479 = 0.7850 hand-written | `results/ledgers/h_floor_diagnosis_official.json` | 2026-09-29 | VERIFIED — the floor got **WORSE**; H4 triggered, no further calls spent |
| 60 | Abstention, official arm | WITH **378/960** · WITHOUT **390/960**; hand-written **0/958** | `h_official_arm_run_summary.json` | 2026-09-29 | VERIFIED — recorded flags agree with recomputation from stored text on 0/1,920 disagreements |
| 61 | **Mechanism: correct answers became abstentions** | **128** responses correct under the hand-written prompt became abstentions under the official one; only **94** moved the other way | `results/ledgers/h_paired_prompt_arm_mcnemar.json` | 2026-09-29 | VERIFIED — `harness.py:1055` scores an abstention 0, identical to a wrong answer, so this can only lower accuracy |
| 62 | Prompt arms compared, PAIRED | hand-written **330/1916** vs official **226/1916**; discordant 198 vs 94; McNemar exact **p = 1.12e-09** | same | 2026-09-29 | VERIFIED — the official prompt is significantly **WORSE** on this benchmark |
| 63 | 🔵 **The floor is reader capability, not pairing** | on cells whose memory text **literally contains the gold answer**, WITH-arm accuracy is only **70/306 = 0.2288** (hand-written) and **44/308 = 0.1429** (official); **72–79%** of those cells still fail both arms | `h_floor_diagnosis_official.json`, `h_floor_diagnosis_handwritten.json` | 2026-09-29 | VERIFIED — subgroup defined by memory CONTENT, not by an outcome, so **not** a selected subgroup |
| 64 | Official arm, three floors | F_exec **0.000000**, F_empty **0.000000**, F_judge **0.000000** (3,486 re-scorings) | `results/ledgers/h_official_noise_floors.json` | 2026-09-29 | VERIFIED — each positive-controlled: fires at 0.5093 / 0.5445 / 0.2941 on planted defects |
| 65 | Official arm, flips + additive null | robust = naive = **0.13333** [0.06914, 0.24165], denominator **60**, gap 0.000; additive null mean 0.96667, **p = 1.000** | `results/deltau_official/analysis/02_labels_and_flips.json` | 2026-09-29 | VERIFIED — **no excess over additive**; robust==naive is MECHANICAL (F=0, 2 agreeing replicates), same caveat as row 53 |
| 66 | ΔU distribution, official arm (before labelling) | **20 positive · 437 zero · 23 negative** (480 cells) | same | 2026-09-29 | VERIFIED |
| 67 | Design has no balanced rectangle | tasks/memory **8/8/8** (min/median/max); memories/task **1/2/36**; only **127 of 220** tasks are shared by ≥2 memories | row artifacts, both arms | 2026-09-29 | VERIFIED — this, not sample size, is why the decomposition cannot fit; widening the **task** axis is the fix |
| 68 | 🔴 `ZeroDivisionError` crashed the decomposition stage **while the script exited 0** | `interaction / F_exec²` at `decomposition.py:595` with F_exec = **0.0** — the expected value for a deterministic reader. PREREG §6's comparator is undefined at zero. **This is what produced the empty `shares` dict of row 54a** | traceback in the stage log; reproduced by re-raising | 2026-09-29 | FIXED — emits `EXEC_FLOOR_COMPARATOR_UNDEFINED`; negative-controlled (reverting the guard fails 2 tests) |
| 69 | 🔴 With the crash fixed, the REML fit is **NOT IDENTIFIED** | task and interaction shares **exactly equal to 16 s.f.** in BOTH arms (official 0.4590691584279404; hand-written 0.4875884835020202), both ratios pinned at `exp(12) = 162754.79141900392` = the optimizer's clip ceiling; `converged=True` with a tight CI [0.444, 0.468] | `03_variance_decomposition.json`, both arms | 2026-09-29 | FIXED — the module guarded only the LOWER boundary; `AT_UPPER_BOUNDARY` added. **Variance decomposition stays UNMEASURED**, now for a diagnosed reason |
| 70 | Variance decomposition, BOTH arms, final | **UNMEASURED.** Official: converged=True but task = interaction = **0.45906915842794044** with **identical CIs** [0.40555, 0.49555], both at the `exp(12)` clip, residual at the lower boundary, **29/200 bootstrap resamples failed**. Hand-written: fallback, `shares={}` | `results/ledgers/h_official_variance_decomposition.json`, `h_handwritten_variance_decomposition.json` | 2026-09-29 | VERIFIED — reporting 0.459 would be reporting a clip constant. **Not a null; not identifiable** |
| 68a | 🔴 The SAME division had a **second site** | `to_dict()` at `decomposition.py:95` guards `None` and `total_variance<=0` but **not `exec_floor_variance == 0`**; it crashed on the very next run. The first fix closed the reported instance, not the defect | stage log `results/logs/h_official_floors.log` | 2026-09-29 | FIXED — plus a **grep-level test** that every `/ exec_floor_variance` and `/ fvar` sits inside a positivity guard, so a third site fails in CI |

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

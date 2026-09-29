# Sub-agent J — Diagnostic: READER or TASK?

**Status: COMPLETE.** Written incrementally; every number cites the artifact it came from.
Python: `/Users/bellayang/miniconda3/bin/python3` (3.13). Repo:
`/Users/bellayang/Documents/2026/p1_memory_utility/repo`.

## 0. Setup verified before any number

- `src/p1mem/adapters/leakage.py` self-test `controls_summary()` → **all_passed=True, 17/17**
  (run 2026-09-29, this session).
- Artifacts: `results/deltau_official/cells.jsonl` (960 rows, 480 live cells),
  `results/deltau_pilot/cells.jsonl` (960 rows, 479 live cells).
- Row-level `leakage_flag`: official 308 True / 652 False; pilot 308 True / 652 False.
  Cell-level: official 154 True / 326 False; pilot 153 True / 326 False. **No `None`
  (undecidable) rows in either arm** — recheck below.

## 1. J1 — the oracle-bearing subgroup, AS SHIPPED (reproduces H exactly)

Script: `repo/scripts/j1_oracle_subgroup.py` → `repo/results/ledgers/j1_oracle_subgroup.json`.
`leakage_flag` was **re-derived from `memory_text` + gold answer**, not trusted:
**0 mismatches against the stored flag** in either arm (480 / 479 live cells).

| arm | subgroup | n cells | acc WITH | acc WITHOUT | both-arms-fail |
|---|---|---:|---:|---:|---:|
| official | **oracle-bearing** | 154 | **0.1429** [0.096,0.207] | 0.1429 | 121/154 = **0.7857** |
| official | clean | 326 | 0.1012 | 0.1104 | 281/326 = 0.8620 |
| official | all | 480 | 0.1146 | 0.1208 | 402/480 = 0.8375 |
| handwritten | **oracle-bearing** | 153 | **0.2288** [0.169,0.301] | 0.2026 | 110/153 = **0.7190** |
| handwritten | clean | 326 | 0.1442 | 0.1595 | 266/326 = 0.8160 |
| handwritten | all | 479 | 0.1712 | 0.1733 | 376/479 = 0.7850 |

This reproduces `docs/OFFICIAL_PROMPT_ARM.md` §3 Cause 1 to 4 decimals. And the subgroup
is genuinely not outcome-selected. **But the subgroup is not what its name says.**

---

## 2. 🔴 INSTRUMENT DEFECT J-1: `leakage_flag` is ~all false positives

### 2a. The tell: 96 of 154 "oracle-bearing" cells have a ONE-CHARACTER gold answer

Gold-answer length distribution inside the official arm's oracle subgroup
(`len(normalize_text(gold))`):

- **len 1: 96 cells** (of 154 = 62.3%), all of them `eval_function = mc_choice_match`
  multiple-choice letters: `A`(13) `C`(13) `D`(9+8) `F`(9) `E`(8) `G`(7) `B`(7+5+3) `H`(2+1)…
- 46 distinct tasks have a gold answer that normalizes to ≤2 chars.

The memory texts are WorkArena/WebArena **AXTree dumps**. Measured over the 60 distinct
memory texts in the run:

| literal | occurs in |
|---|---|
| `A` | **60/60** memory texts |
| `C` | 59/60 |
| `D` | 58/60 |
| `E` | 56/60 |
| `B` | 50/60 |

So for a multiple-choice question whose gold answer is the letter `A`, `exact_leak`
fires on **every memory in the corpus**. The memory does not "contain the answer"; the
letter `A` occurs in English prose. `exact` fires on 138 of the 154 cells.

### 2b. The decisive control — MISMATCH CONTROL (a positive/negative control the
### leakage module's own 17 controls cannot run, because they use planted text)

For every task, run the detector against **every same-domain memory it was never
paired with**. A real leakage detector must fire much more often on the memory that
was actually paired than on an arbitrary unrelated one.

| detector definition | PAIRED cells | UNPAIRED same-domain | ratio |
|---|---|---|---|
| **as shipped (`any_leak`)** | 154/480 = **0.3208** | 2012/6240 = **0.3224** | **0.995** |
| any_leak, non-degenerate gold (>2 chars) | 57/480 = 0.1187 | 857/6240 = 0.1373 | 0.865 |
| official scorer on memory text | 28/480 = 0.0583 | 417/6240 = 0.0668 | 0.873 |

> **The as-shipped flag fires on an unrelated memory at exactly the same rate as on the
> paired one (ratio 0.995).** It carries essentially **zero information about whether
> this memory bears on this task.** Even the strictest variant is only 1.15x enriched on
> the paired memory, which is not distinguishable from noise at these counts.

The 17 in-module controls all pass and are not wrong — they plant text into a synthetic
clean memory. They prove the detector *fires on a plant*. They never asked whether it
also fires on everything else. This is the project's own recorded
*"a verifier only run on its home case is not known to discriminate"* shape.

### 2c. Even the "non-degenerate" subgroup is contaminated

Listing the 57 non-degenerate oracle cells by gold answer: 15 are `false`, 4 `true`,
5 `one`, plus `click`, `goto`, `five`, `300`, `100` — all strings that occur in an AXTree
/ action log for reasons unrelated to the question. Only ~28 cells (the
`official`-scorer-positive ones: `Hardware`, `Incident`, `Products`, `Qty`, `Reset`,
`Subscribe via RSS`, `Eclipse IDE`, `URL, Image`, `Update; Delete`, `relationship, advice`,
`Comment, Post`, `Summary`, `User`) are plausibly real.

### 2d. What this does to H's conclusion

`docs/OFFICIAL_PROMPT_ARM.md` §3 concludes *"even with the answer sitting in the context,
the reader is right ~23% of the time"* and rules out "the memory does not bear on the
task" as the main cause. **That conclusion does not follow from this flag**, because for
~2/3 of the subgroup the answer is not sitting in the context in any meaningful sense.

Recomputed on the tiers (official arm / handwritten arm), cell counts and accuracies:

| subgroup | official n | official accW | hand n | hand accW |
|---|---:|---:|---:|---:|
| as-shipped `any_leak` | 154 | 0.1429 | 153 | 0.2288 |
| …of which degenerate gold (≤2 chars) | 97 | **0.0515** | 96 | 0.1562 |
| non-degenerate `any_leak` | 57 | 0.2982 | 57 | 0.3509 |
| **official-scorer-positive (strictest)** | **28** | **0.3571** [0.207,0.542] | **28** | **0.4286** [0.265,0.609] |

Accuracy rises monotonically as the subgroup is cleaned: **0.14 → 0.30 → 0.36** (official),
**0.23 → 0.35 → 0.43** (handwritten). Both-arms-fail falls 0.786 → 0.596 → 0.536.
So the cleaner the "answer is really present" definition, the better the reader does —
which is the OPPOSITE of the direction H's number suggested, and it weakens the
"reader is hopeless even with the answer in front of it" reading.

**Caveat, stated because it cuts the other way:** the 28-cell strict subgroup is defined
by *the official scorer marking the memory text itself correct*. That is still a content
property, not an outcome. But it is a small n, and the mismatch control says even this
definition is barely enriched on the paired memory (0.058 paired vs 0.067 unpaired) —
i.e. these 28 are cells where the memory happens to contain the gold string, not
necessarily cells where the memory is the evidence for the answer.

---

## 3. J1 REPAIRED — a DISCRIMINATIVE oracle-bearing subgroup

Script: `repo/scripts/j1b_discriminative_oracle.py` →
`repo/results/ledgers/j1b_discriminative_oracle.json`.

The repair is not a stricter string match (the strictest, official-scorer-positive, is
still only 1.15x enriched). It is to make the subgroup **discriminative by construction**:
for each task, run the detector against **every same-domain memory**, and keep the cell
only when the detector singles out THIS memory (fires on at most N of the ~24–36 pool).
A detector that fires on 24 of 24 memories has said nothing about any of them.

**This still uses only CONTENT** (memory text, gold answer). No reward enters. It is not
an outcome-selected subgroup.

How un-discriminating the as-shipped flag is — for each flagged cell, how many pool
memories ALSO fire for that task (official arm):

| pool memories firing | oracle cells |
|---:|---:|
| 1 | 2 |
| 2–5 | 10 |
| 6–12 | 11 |
| 17–24 (of a 24-pool) | 87 |
| 29–36 (of a 36-pool) | 42 |

**129 of 154 cells sit in a task where ≥17 of the pool fire.** For 52 cells the detector
fires on **all 24** same-domain memories.

### The accuracy gradient (official arm; handwritten in parentheses)

| subgroup | n | acc WITH | acc WITHOUT | both-arms-fail |
|---|---:|---:|---:|---:|
| all cells | 480 (479) | 0.1146 (0.1712) | 0.1208 (0.1733) | 0.8375 (0.7850) |
| non-flagged | 326 (326) | 0.1012 (0.1442) | 0.1104 (0.1595) | 0.8620 (0.8160) |
| oracle AS SHIPPED | 154 (153) | 0.1429 (0.2288) | 0.1429 (0.2026) | 0.7857 (0.7190) |
| discriminative ≤12 | 23 (23) | 0.4348 (0.3913) | 0.2609 (0.3043) | 0.4783 (0.5217) |
| discriminative ≤8 | 22 (22) | 0.4545 (0.4091) | 0.2727 (0.3182) | 0.4545 (0.5000) |
| **discriminative ≤5** | **12 (12)** | **0.5000** [0.254,0.746] (0.3333) | 0.0833 (0.0833) | 0.5000 (0.6667) |
| discriminative ≤3 | 7 (7) | 0.4286 (0.4286) | **0.0000** (0.1429) | 0.5714 (0.5714) |
| discriminative ≤2 | 5 (5) | 0.6000 (0.6000) | **0.0000** (0.2000) | 0.4000 (0.4000) |
| discriminative ≤1 | 2 (2) | **1.0000** (1.0000) | 0.0000 (0.0000) | **0.0000** (0.0000) |

Monotone in both arms, and it is the **WITH** arm that moves: at ≤5 the official arm
scores 0.500 WITH against 0.083 WITHOUT — a ΔU of **+0.417** on cells where the memory
demonstrably and *distinctively* carries the answer, versus **−0.006** overall.

> **Reading.** When the memory really does carry the answer and is the only one that does,
> **the reader gets it right about half the time and the memory effect is large and
> positive.** The ~0.14 figure in `OFFICIAL_PROMPT_ARM.md` §3 is an average dominated by
> cells where the "answer" was the letter `A` occurring somewhere in an AXTree.
>
> **This substantially weakens "the reader cannot read".** It does NOT yet prove the
> reader is fine — n=12 and n=22 are small, and 45–50% still fail. J2 tests that directly.

---

## 4. J3 — is any slice tractable? (computed first; it is free)

Script: `repo/scripts/j3_tractable_slice.py` → `repo/results/ledgers/j3_tractable_slice.json`.
All rates PAIRED (WITH and WITHOUT over the same cells within each group).

### By domain — official arm (handwritten in parentheses)

| domain | n cells | acc WITH | acc WITHOUT | Δ | both-arms-fail |
|---|---:|---:|---:|---:|---:|
| web | 288 | 0.1424 (0.1701) | 0.1354 (0.1632) | +0.0069 | 0.812 (0.795) |
| enterprise | 192 (191) | 0.0729 (0.1728) | 0.0990 (0.1885) | −0.0260 | 0.875 (0.770) |

**Domain does not separate difficulty consistently.** Under the official prompt web looks
2x easier than enterprise; under the hand-written prompt they are equal (0.170 vs 0.173)
and enterprise is *better* on both-arms-fail. **The apparent web/enterprise gap is a
prompt×domain interaction, not a stable property of the domain** — reporting "web is
easier" from the official arm alone would be reading one arm as if it were the benchmark.

### By question_type — official arm (handwritten in parentheses)

| question_type | n | acc WITH | Wilson 95% | acc WITHOUT | both-arms-fail |
|---|---:|---:|---|---:|---:|
| static-environment | 153 | 0.1569 (0.2288) | [0.108,0.223] | 0.1373 (0.2157) | 0.817 (0.712) |
| procedure | 146 (145) | 0.1096 (0.2345) | [0.069,0.171] | 0.1575 (0.2276) | 0.808 (0.738) |
| dynamic-environment | 145 | 0.0897 (0.0897) | [0.053,0.147] | 0.0966 (0.1172) | 0.862 (0.855) |
| errors-gotchas | 36 | 0.0556 (0.0000) | [0.015,0.181] | 0.0000 (0.0000) | 0.944 (1.000) |

### By eval_function — official (handwritten)

| eval_function | n | acc WITH | both-arms-fail |
|---|---:|---:|---:|
| `mc_choice_set_match` | **1** | 1.0000 | 0.000 |
| `norm_phrase_set_match_ordered` | 45 | 0.2444 (0.2667) | 0.689 (0.711) |
| `mc_choice_match` | 121 (120) | 0.0992 (0.1583) | 0.835 (0.783) |
| `norm_phrase_set_match` | 313 | 0.0990 (0.1597) | 0.863 (0.799) |

### By task environment — official (handwritten)

| environment | n | acc WITH | both-arms-fail |
|---|---:|---:|---:|
| **webarena-onestopshop** | 67 | **0.2537** (0.2090) | **0.642** (0.746) |
| webarena-reddit | 127 | 0.1102 (0.1496) | 0.858 (0.803) |
| webarena-cms | 94 | 0.1064 (0.1702) | 0.872 (0.819) |
| workarena | 192 (191) | 0.0729 (0.1728) | 0.875 (0.770) |

### J3 verdict: **no slice is tractable.**

The best honest candidate is `webarena-onestopshop` (n=67, 0.254 WITH, 64.2% both-fail)
— but 64% both-arms-fail is still far above the ~50% at which an instrument can move, it
is 67 cells, and it does not replicate across arms (0.209 in the hand-written arm, where
`procedure` and `static-environment` lead instead). `mc_choice_set_match` at 1.000 is
**one cell**, not a slice.

> **Restricting to a slice will not rescue P1.** Every slice with a usable denominator is
> at 0.06–0.25 accuracy and 0.64–1.00 both-arms-fail, and the ordering between slices is
> not stable across the two prompt arms. Choosing the best-looking slice from these tables
> would be picking a window after seeing the data — the error this project has already
> logged twice.

---

## 5. One more control on the leakage flag: permuted gold answers

If the flag were detecting real leakage, giving each task a gold answer belonging to a
DIFFERENT task (permuted within `eval_function`, so the length distribution is preserved)
should collapse the firing rate. Measured on the official arm's 480 cells:

| | rate |
|---|---|
| TRUE pairing | 154/480 = **0.3208** |
| permuted gold, 20 seeds | **0.3015** [0.2896, 0.3146] |
| excess over the permuted null | **+0.0194** |

**94% of the flag's firing rate survives destroying the memory↔answer correspondence
entirely.** Together with the mismatch control (ratio 0.995), the flag's discriminative
content is ~2 percentage points on a base rate of 32%.

---

## 6. J2 — escalating the reader on exactly those cells

### 6a. Endpoint probes, with real POSTs (three "advertised but dead" already on record)

Artifacts: `repo/results/ledgers/j2_probe_metis.jsonl`, `j2_probe_minerva.jsonl`,
`j2_probe_minerva_27k.jsonl`.

| cluster / model | ~4k shape | ~28k shape (the real one) |
|---|---|---|
| metis `gpt-oss-120b` | 200, 4277 prompt_tok | (already the incumbent) |
| metis **`Mistral-Large-3-675B`** | **404 `endpoint_not_found`** — `'metis-api-mistral-large-3-675b' does not exist` | — |
| minerva `nemotron-3-ultra` | 200, 4226 prompt_tok | **200, 29317 prompt_tok** |
| minerva `inkling-bf16` | 200, 4225 prompt_tok | **200, 29316 prompt_tok** |

**`Mistral-Large-3-675B` is dead**, contrary to the task brief's "verified available".
Both minerva models serve, and were re-probed at the **real ~29k shape**, not only at 4k.

### 6b. Design

`repo/scripts/j2_escalate_reader.py`. Four configurations, each a **new arm** (model,
effort, max_tokens all in `condition_id` AND in the cache key, so no config can read
another's row, and nothing is written into the completed arms' artifacts):

| config | cluster/model | effort | max_tokens |
|---|---|---|---|
| `base_replication` | metis `gpt-oss-120b` | low | 512 |
| `high_effort` | metis `gpt-oss-120b` | **high** | **2048** |
| `nemotron` | minerva `nemotron-3-ultra` | high | 2048 |
| `inkling` | minerva `inkling-bf16` | high | 2048 |

Cells, fixed before any call:
- **ORACLE** = the discriminative oracle subgroup at ≤8 pool hits, **22 cells**;
- **CONTROL** = **30** non-flagged cells, drawn at random and stratified to the same
  (domain, question_type) mix — so "accuracy rose" can be told from "these are easier".

`base_replication` is byte-identical to the completed official arm and is the **anchor**:
if it does not reproduce the recorded rewards, every comparison above it is void.

### 6c. 🔴 Three more instrument defects, each caught by a control BEFORE calls were spent

1. **Join key.** Rows carry a derived `memory_id` (`mem-<traj>-<hash>`); the manifest and
   the cache carry a bare content hash. Joining on `memory_id` matched **nothing**.
   Re-joined on `memory_unit_locator`.
2. **Scoring path — would have faked a dead harness.** My positive control scored the
   RAW content; the real runner scores `extract_boxed_answer(content)`. `\boxed{Paris}`
   normalizes to `boxedparis`, so a **correct** answer scored **0.0**. Verified offline
   before any call; after the fix, 6/6 cases score as expected including the abstention.
3. **The context assertion did not discriminate.** Checking only that the memory_text is
   byte-equal and present-in-WITH / absent-from-WITHOUT **PASSES a K=4 rebuild** (target
   present, fillers different) — a different experiment under the same name. Replaced
   with a clause that reproduces the completed run's **own recorded token quantiles**.
   *The first attempt at that clause was itself wrong*: it compared our Qwen count to the
   server's `prompt_tokens` and **rejected a faithful rebuild**, because the server does
   not use the official tokenizer (measured ratio **1.15–1.21** across all 960 prompts).

**Negative controls on the final assertion** (it must fail on a corruption):

| rebuild | verdict |
|---|---|
| K=6, seed 20260929 (correct) | **PASS** — quantiles `{min 20684, p25 25360, median 26891, p75 28408, max 32925}` reproduce `summary.json` exactly |
| K=4 | **FAIL** (median 19092) |
| K=5 | **FAIL** (median 23196) |
| K=7 | **FAIL** (median 30722) |
| seed 20260930 | **FAIL** (cells not reproducible) |

### 6d. Run log

420 planned calls (budget 600), concurrency 8, four configs. Context reproduction
asserted for all 52 cells before any call was issued; qwen/server token ratio
[1.1541, 1.2046] over 104 prompts.


### 6e. Interpretation rule, fixed BEFORE the J2 numbers were read

Written to the report while the run was still executing, so the verdict cannot be
chosen after seeing the result.

Let `L_oracle` = paired accuracy lift of a stronger config over `base_replication` on
the 22 oracle cells (WITH arm), and `L_control` the same on the 30 control cells.

| condition | verdict |
|---|---|
| positive control != 1.0 for a config | that config's null is **void**, not a null |
| `base_replication` disagrees materially with the recorded arm | **all** comparisons void (moving anchor) |
| `L_oracle` large and positive, materially exceeding `L_control` | **READER-limited** — a stronger reader makes P1 measurable |
| `L_oracle` ~= `L_control`, both large | reader improved **everywhere**; the ceiling was reader capability but not specific to memory use |
| `L_oracle` ~= 0 with positive control = 1.0 | **TASK-limited** — no affordable reader change rescues this benchmark |

"Material" is read against the Wilson interval and the McNemar exact p on the
discordant pairs, not against the point estimate alone. With n=22 the study is
**underpowered for a small lift**: it can only detect a large one. That limitation is
stated up front rather than discovered afterwards.
### 6f. Composition of the two J2 groups (matched before any call)

| | ORACLE | CONTROL |
|---|---|---|
| cells | 22 | 30 |
| distinct tasks | 17 | 23 |
| distinct memories | 19 | 24 |
| domain | enterprise 9 / web 13 | enterprise 13 / web 17 |
| question_type | static 11, procedure 4, errors-gotchas 4, dynamic 3 | static 15, errors-gotchas 5, procedure 5, dynamic 5 |
| eval_function | `norm_phrase_set_match` 21, `_ordered` 1 | `norm_phrase_set_match` 26, `_ordered` 3, `mc_choice_match` 1 |

The oracle group's gold answers are real content strings — `Hardware`, `Incident`,
`Qty`, `Reset`, `Summary`, `User`, `Eclipse IDE`, `Subscribe via RSS`, `Comment, Post`,
`Update; Delete`, `relationship, advice` — **not** the bare `A`/`B`/`C` letters that
dominated the as-shipped flag. Neither group is outcome-selected.

---

## 7. J2 RESULTS — 420 calls, 396 real, 24 errors

Artifacts: `repo/results/j2_escalation/responses.jsonl` (420 rows),
`repo/results/j2_escalation/summary.json`, `repo/results/ledgers/j2_analysis.json`.

### 7a. The anchor holds: base_replication reproduces the completed arm EXACTLY

| | |
|---|---|
| agreements | **104 / 104** |
| disagreements | **0** |
| missing | 0 |

`base_replication` was re-issued as a fresh call (0 cache hits) and every reward matched
the recorded official arm on both arms of all 52 cells. **The endpoint has not drifted
and the comparison anchor is sound.**

### 7b. Per-config accuracy (paired, WITH vs WITHOUT over the same cells)

| config | group | n | acc WITH | Wilson | acc WITHOUT | ΔU | both-fail | abstain WITH |
|---|---|---:|---:|---|---:|---:|---:|---:|
| base_replication | **oracle** | 22 | **0.4545** | [0.269,0.653] | 0.2727 | **+0.1818** | 10/22 | 5 |
| base_replication | control | 30 | 0.0333 | [0.006,0.167] | 0.0667 | −0.0333 | 28/30 | 18 |
| high_effort | oracle | 17 | 0.4118 | [0.216,0.640] | 0.1765 | +0.2353 | 10/17 | 6 |
| high_effort | control | 17 | 0.1765 | [0.062,0.410] | 0.0588 | +0.1176 | 14/17 | 9 |
| nemotron | oracle | 22 | 0.2273 | [0.101,0.434] | 0.0000 | +0.2273 | 17/22 | 16 |
| nemotron | control | 30 | 0.0000 | [0.000,0.114] | 0.0000 | +0.0000 | 30/30 | 30 |
| inkling | oracle | 22 | 0.3636 | [0.197,0.570] | 0.0909 | +0.2727 | 13/22 | 9 |
| inkling | control | 28 | 0.0357 | [0.006,0.177] | 0.0357 | +0.0000 | 27/28 | 24 |

### 7c. Paired lift vs base (WITH arm), McNemar exact

| config | group | n | base-only | new-only | both | neither | lift | p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| high_effort | oracle | 21 | 2 | **0** | 8 | 11 | **−0.0952** | 0.5 |
| high_effort | control | 19 | 1 | 3 | 0 | 15 | +0.1053 | 0.625 |
| nemotron | oracle | 22 | 5 | **0** | 5 | 12 | **−0.2273** | 0.0625 |
| nemotron | control | 30 | 1 | 0 | 0 | 29 | −0.0333 | 1 |
| inkling | oracle | 22 | 2 | **0** | 8 | 12 | **−0.0909** | 0.5 |
| inkling | control | 30 | 1 | 1 | 0 | 28 | +0.0000 | 1 |

> **No stronger configuration solved a single oracle cell that the base reader failed.**
> `new-only = 0` in all three. Every difference runs the other way: 2, 5 and 2 cells that
> the base reader got right were LOST. Difference-in-differences: −0.20, −0.19, −0.09.

### 7d. 🔴 Two of the four positive controls returned 0 — and the CONTROL is what is broken

| config | positive control | content | reasoning_tokens |
|---|---|---|---|
| base_replication | **1.0** | `\boxed{Paris}` | 7 |
| high_effort | **0.0** | `\boxed{UNKNOWN}` | 496 |
| nemotron | **0.0** | `\boxed{UNKNOWN}` | 438 |
| inkling | **1.0** | `The capital city of France is Paris.\n\n\boxed{Paris}` | 467 |

Per the rule pre-registered in §6e, a config whose positive control is not 1.0 has a
**void** null, not a null. But the diagnosis is that **the control itself is defective**,
not the harness: it was asked under the benchmark's own system prompt, which says
*"Answer based on your memory of the environment… if you do not know, output exactly
`\boxed{UNKNOWN}`. Do not guess."* **The capital of France is not a fact about the
WorkArena/WebArena environment, so abstaining is the CORRECT behaviour under that
prompt.** The control measured prompt compliance, not harness capability. Reading its 0
as "no gain was detectable" would be this project's own *"a control that cannot exhibit
the behaviour cannot certify its absence"* error — so a replacement was built rather
than the null being reported.

### 7e. 🔴 `high_effort` is not a usable arm: 22 of 24 errors are budget truncation

All 24 errors are `TruncatedResponseError`, 22 of them in `high_effort`:

> `finish_reason='length'` with empty content. `max_tokens=2048` was consumed by
> reasoning (`reasoning_tokens=2046`).

This is the same **reproducible** truncation the pilot hit at 512 tokens, now at 2048.
It is a systematic budget failure, not flakiness, and it is why `high_effort`'s
denominators are 17 rather than 22/30 — the surviving cells are the ones whose reasoning
happened to fit, which is **selection on a property of the response**. `high_effort` is
reported but must not be compared to the others as if its cells were the same cells.

---

## 8. 🟢 THE DECISIVE MEASUREMENT — a planted needle in the real 27k context

Script: `repo/scripts/j2b_needle_control.py` →
`repo/results/j2_escalation/needle_responses.jsonl`, `needle_summary.json`.
66 calls, 0 errors, 41.5 s.

**Design.** Same 22 oracle cells, same real ~27k-token context, same official system
prompt, same scorer. One sentence is planted **inside the target memory**, at its real
position: *"Note for the operator: the internal reference code for this page
configuration is NNNNNN."* The code is a **per-cell unique** 6-digit number. The question
asks for that code. Because the code is phrased as an environment fact, **abstention is
not the correct answer** — which is exactly what was wrong with the capital-of-France
control.

### Result

| config | n | **needle found** | Wilson 95% | code anywhere in response | abstained |
|---|---:|---:|---|---:|---:|
| base_replication (`gpt-oss-120b`, low, 512) | 22 | **22/22 = 1.0000** | [0.851, 1.000] | 22/22 | 0 |
| nemotron (`nemotron-3-ultra`, high, 2048) | 22 | **22/22 = 1.0000** | [0.851, 1.000] | 22/22 | 0 |
| inkling (`inkling-bf16`, high, 2048) | 22 | **22/22 = 1.0000** | [0.851, 1.000] | 22/22 | 0 |

### A result this clean was interrogated before it was believed

| check | result |
|---|---|
| distinct codes | **22** across 66 rows (each reused exactly 3x, once per config) — the reader cannot pass by emitting one constant |
| responses carrying ANOTHER cell's code | **0** |
| scorer on the right code | True |
| scorer on a wrong code (`759572` vs `759571`) | **False** |
| scorer on `\boxed{UNKNOWN}` / empty | **False** / **False** |

### NEGATIVE CONTROL — the same question with NO needle planted
(`repo/results/ledgers/j2b_needle_negative_control.json`, 18 calls, 6 cells × 3 configs;
asserted before sending that the code and sentence were absent from the context)

| config | n | needle "found" | abstained |
|---|---:|---:|---:|
| base_replication | 6 | **0/6** | 0 |
| nemotron | 6 | **0/6** | 2 |
| inkling | 5 | **0/5** | 2 |

**0 of 17.** The readers either say the notes contain no such code, abstain, or return an
unrelated id from the AXTree. **The test can fail, and does, exactly when it should.**

> ### This is the number that decides READER vs TASK.
>
> **The reader — including the base `gpt-oss-120b` at `effort=low` and `max_tokens=512`
> — retrieves a planted fact from the real 27,000-token context with 100% accuracy
> (66/66), under the same prompt, same scorer, same cells, and scores 0/17 when the fact
> is absent.**
>
> **The reader can read. Raw long-context retrieval is not the bottleneck.**

---

## 9. The memory effect itself, pooled across three readers

Within-cell paired WITH vs WITHOUT (this is ΔU), `repo/results/j2_escalation/responses.jsonl`:

| arm | group | n | WITH-only correct | WITHOUT-only | **ΔU** | McNemar exact p |
|---|---|---:|---:|---:|---:|---:|
| base_replication | **oracle** | 22 | 6 | 2 | **+0.1818** | 0.2891 |
| base_replication | control | 30 | 0 | 1 | −0.0333 | 1 |
| **pooled (base + nemotron + inkling)** | **oracle** | **66** | **18** | **3** | **+0.2273** | **0.00149** |
| **pooled (base + nemotron + inkling)** | control | 88 | 0 | 1 | −0.0114 | 1 |

> On cells where the memory demonstrably and distinctively carries the answer, the memory
> is worth **+0.227 accuracy**, p = 0.0015, consistently across three different readers.
> On matched cells where it does not, the effect is **zero** (0 gains in 88 cells).
>
> **The phenomenon P1 exists to measure is present and measurable.** It is not visible in
> the main arms because it lives in ~4.6% of cells (22 of 480) and is diluted to nothing
> by the other 95%.

---

## 10. VERDICT

### (1) Oracle-bearing subgroup accuracy

| definition | n | acc WITH | acc WITHOUT |
|---|---:|---:|---:|
| as shipped (`leakage_flag`) — **the flag is ~uninformative** | 154 | 0.1429 | 0.1429 |
| discriminative (detector singles this memory out, ≤8 of pool) | 22 | **0.4545** | 0.2727 |

The 0.1429 / 0.2288 figures in `docs/OFFICIAL_PROMPT_ARM.md` §3 are correct arithmetic on
a subgroup that is **not** oracle-bearing: the flag fires on a never-paired same-domain
memory at **0.3224** vs **0.3208** on the paired one (ratio **0.995**), and permuting the
gold answers only drops it to 0.3015. 96 of its 154 cells have a one-character
multiple-choice gold answer, and `A` occurs in **60 of 60** memory texts.

### (2) Does a stronger reader lift it? **No — and it does not need to.**

`new-only correct = 0` for all three stronger configs on the 22 oracle cells; lifts
−0.095 / −0.227 / −0.091; DiD −0.20 / −0.19 / −0.09. `Mistral-Large-3-675B` is dead
(404). `high_effort` is not a usable arm (22 of 24 errors are `reasoning_tokens=2046`
consuming the whole 2048 budget).

**But the null is not the finding, because the null is not from an incapable
instrument:** the needle control proves all three readers retrieve a planted fact from
the same 27k context at **66/66 = 100%**, and **0/17** when it is absent.

### (3) READER vs TASK: **NEITHER. It is the PAIRING.**

Neither of the two answers the task framed. The evidence:

| observation | rules out |
|---|---|
| needle found 66/66 in the real 27k context, 0/17 when absent | **reader capability** — the reader reads |
| no stronger reader solves any cell the base misses (0/22 ×3) | **reader capability** — there is no headroom to buy |
| ΔU = **+0.227**, p=0.0015, on discriminative oracle cells, across 3 readers | **task impossibility** — the task is solvable and the memory demonstrably helps |
| ΔU = **−0.011** on 88 matched control cells, 0 gains | — |
| only **22 of 480 cells (4.6%)** are discriminative-oracle | **this is the binding constraint** |
| `select_pairs` samples ANY same-domain question, stratified by `question_type`; `in_official_haystack` is True for 11,384 of 15,112 manifest pairs and so is nearly uninformative | — |
| question ids are **not** trajectory ids (0 of 451) and no gold-evidence field exists in `questions.jsonl` | the benchmark ships **no** memory↔question relevance label |

**The ceiling is the PAIRING.** `select_pairs` pairs each memory with 8 same-domain
questions chosen for `question_type` spread, with no requirement that the memory bears
on the question. ~95% of cells are a memory and an unrelated question. Such a cell
**cannot** show a memory effect no matter how good the reader or how easy the task — and
that, not reader capability, is what produces 84% both-arms-fail.

`docs/OFFICIAL_PROMPT_ARM.md` §3 ruled this cause out ("Cause 1: ruled out as the main
cause") **on the strength of the defective flag.** With a flag that discriminates, Cause
1 is the answer.

### (4) The cheapest tractable slice

**Not a benchmark slice.** J3: every domain/question_type/eval_function/environment slice
sits at 0.06–0.25 accuracy and 0.64–1.00 both-arms-fail, and the ordering is not stable
across the two prompt arms (web is 2x enterprise under the official prompt, equal under
the hand-written one). The best-looking slice, `webarena-onestopshop` (n=67, 0.254), does
not replicate. Picking it would be choosing a window after seeing the data.

**The cheap fix is the pairing, and it costs no new reader and no new benchmark:**
build cells where the memory is *known* to bear on the question. The leakage detector,
made discriminative (fire on this memory and few others in the pool), is a working,
content-only, outcome-blind relevance filter that is already validated here — 17 in-module
controls, plus the mismatch, permutation and needle controls added today. At ≤8 pool hits
it yields 22 of 480 cells at ΔU +0.227; screening a larger candidate pool at the same
criterion would produce a few hundred such cells for **zero endpoint calls** (the
detector is pure and deterministic).

**Recommendation:** do not re-run the main arm on a stronger reader — the money buys
nothing. Do not move benchmark yet. Re-pair, screening candidate (memory, task) cells
with the discriminative detector before spending any reader calls, and report the
as-shipped-flag result as a **retracted** diagnostic with the mismatch control beside it.

### Caveats, stated rather than discovered later

- n=22 oracle cells. The pooled p=0.0015 is over 66 arm-pairs from 3 readers on the
  **same** 22 cells, so the readers are not independent samples of cells — it establishes
  the effect is real and reader-robust, **not** its magnitude to 3 digits.
- The discriminative threshold (≤8 of pool) was chosen from the sweep in §3, which is a
  post-hoc boundary. The **ordering** is monotone at every threshold tried (≤1, ≤2, ≤3,
  ≤5, ≤8, ≤12) in **both** arms, which is what carries the argument; the exact number at
  ≤8 should not be quoted as if the threshold were pre-registered.
- Even the discriminative subgroup is only ~1.15x enriched on the paired memory by the
  mismatch control. It is a better filter than the as-shipped flag, not a proven one.
- `high_effort` is reported with denominators 17/17 rather than 22/30, and those cells are
  selected on a property of the response (whether the reasoning fit in 2048 tokens).

---

## 11. Call ledger

| item | calls |
|---|---:|
| J2 escalation (4 configs × 52 cells × 2 arms + 4 pos-controls) | **420** (396 scored, 24 truncation errors) |
| J2b needle control | 66 |
| J2b needle NEGATIVE control | 18 |
| endpoint probes (metis ×2, minerva 4k ×2, minerva 28k ×2, effort ×4, real-27k ×2) | 12 |
| **total** | **~516** (J2 budget was ≤600; J2 itself used 420) |

## 12. Instrument defects found (6)

| # | defect | how caught |
|---|---|---|
| J-1 | `leakage_flag` fires on a never-paired memory at the same rate (0.995) — 96/154 cells have a 1-char gold answer, `A` in 60/60 memories | mismatch control + permutation control |
| J-2 | Join key: rows use `mem-<traj>-<hash>`, manifest/cache use a bare hash — matched nothing | build failed loudly |
| J-3 | Positive control scored RAW content, not `extract_boxed_answer` — a **correct** answer scored 0.0 | offline control run before any call |
| J-4 | Context assertion passed a K=4 rebuild (different experiment, same name) | deliberate corruption at K=4/5/7 and a wrong seed |
| J-5 | First fix for J-4 compared Qwen counts to server `prompt_tokens` and **rejected a faithful rebuild** (real ratio 1.15–1.21) | reproduced the run's own recorded quantiles instead |
| J-6 | Capital-of-France positive control measured **prompt compliance**, not harness capability — the official prompt mandates abstention for out-of-environment facts | two configs "failed" it by behaving correctly |


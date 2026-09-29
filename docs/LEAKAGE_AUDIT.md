# Leakage audit: method, controls, and results

Owner: Sub-agent A. Measured 2026-09-29.

A cell `(m, t)` **leaks** when the memory `m` literally carries the gold answer of task `t`, so an agent
could score correct by copying the memory instead of using it. Leaky cells inflate `DeltaU` and a reviewer
will look for them first.

## Policy: FLAG, NEVER DROP

Dropping leaky cells conditions the cell set on the outcome variable and silently changes the question
being answered. `LeakVerdict` has no drop/exclude/filter affordance — a test asserts this — and the audit
writes flagged cells to a manifest so analysis can report **both with and without**.

`official = None` means **UNDECIDABLE** (LLM-judged question), never "clean". Counting an undecidable cell
as clean is the absence-becomes-a-plausible-zero failure mode.

## Definition

The sharpest detector reuses the benchmark's own scorer:

> `leak(m, t) := OFFICIAL_SCORER(prediction = rendered_memory_text, answer = gold(t))`

This is valid without reinterpretation because `norm_phrase_set_match` is already **containment, not
equality** — it asks only whether every gold phrase occurs in the prediction, and does not penalize extra
text. Three further variants ship for benchmarks with no scorer: `exact` (raw substring),
`normalized` (benchmark normalization + `\b`, all-phrases and partial), `numeric` (rel/abs tolerance, so
`1,234` / `1234` / `1234.0` all match).

## Prove the detector can fail — 17/17 controls

`leakage.prove_detector_can_fail()`; the audit **aborts** if any control fails. 4 negative controls
(cleanliness *asserted*, not assumed), 11 positive plants, 2 pinned known-false-negatives. Plants are
varied so that no single detector passes all of them.

**Two controls FAILED on the first run. Both were defects in the controls, and one exposed a real bug in
the upstream scorer.**

1. `plant/verbatim` failed. The plant wrote `value='GPS system not functioning correctly'`. The
   benchmark's `normalize_phrase` **strips punctuation without inserting a space**, so `value='GPS`
   becomes `valuegps`, the leading `\b` fails, and the leak is **missed**.
   🔴 This is a property of the **official scorer**. `normalized` and `official` therefore **under-count**
   leakage whenever gold text abuts punctuation — which is constant in accessibility trees, full of
   `'`, `=`, `[`, `]`. Kept as control `known-fn/punctuation-glued` and **pinned as an expected result**,
   so if upstream ever fixes the normalizer this control fails loudly rather than the change passing
   unnoticed. **All reported rates are LOWER BOUNDS**; `exact` is the detector that catches this class.
2. `plant/multiphrase-partial` failed. It planted 2 of 3 gold phrases expecting the all-phrases detector
   not to fire — but the third phrase (`Incidents`) **already occurred in the "clean" baseline**, so the
   partial-leak control was silently testing a full leak. Fixed, plus `_assert_baseline_clean()` which
   **raises** if any gold phrase already occurs in the unplanted memory.

## Results — LongMemEval-V1

Memory unit = one haystack session. Both files, all 500 records.

| file / class | cells | exact | normalized | numeric | ANY |
|---|---|---|---|---|---|
| oracle — labelled evidence | 948 | 34.283% | 37.869% | 33.861% | **49.684%** |
| oracle — filler | **0** | — | — | — | — |
| `_s_cleaned` — labelled evidence | 948 | 34.283% | 37.869% | 33.861% | **49.684%** |
| `_s_cleaned` — filler | 22,919 | 9.699% | 9.464% | 17.710% | **19.599%** |

The oracle's zero filler row is a **true zero, positive-controlled** by counting directly: 948/948 oracle
sessions are labelled evidence. This confirms that ablating in the oracle file removes the whole context
and is **not** a memory ablation.

### The detector separates evidence from filler by 2.5x with no access to labels
And the separation **survives stratification by gold-answer length**, so it is not a composition artifact:

| gold length | evidence n | evidence ANY | filler n | filler ANY | ratio |
|---|---|---|---|---|---|
| <=2 | 189 | 81.48% | 3,517 | 60.16% | 1.35x |
| 3–5 | 136 | 39.71% | 3,295 | 11.29% | 3.52x |
| 6–12 | 199 | 60.80% | 5,181 | 19.20% | 3.17x |
| 13–30 | 116 | 58.62% | 3,280 | 3.23% | **18.14x** |
| >30 | 308 | 24.03% | 7,646 | 11.81% | 2.03x |

Evidence exceeds filler in **every** stratum. The ratio collapses to 1.35x for <=2-character answers, where
filler already fires 60% of the time by coincidence, and peaks at 18x for 13–30 character answers — long
enough to be specific, short enough to be quoted verbatim. This is the strongest evidence that the detector
measures leakage rather than noise.

### 🔴 Why a single pooled rate would be meaningless
Of the 4,492 flagged filler cells, **2,066 (46%) are flagged by the numeric detector alone**, **2,116 have
a gold answer of <=2 characters**, and the median flagged-filler gold answer is **3 characters**. A gold
answer of `3` occurs in almost any 12-turn chat. **Always report stratified by gold-answer length.**

Note: 32 of 500 V1 gold answers are stored as bare `int`, not `str`. These are coerced and flagged
(`gold_answer_not_a_string`), never dropped and never silently stringified.

## Results — LongMemEval-V2

Full cross-product of 1,889 memory units against all same-domain questions. Stratified by gold-answer
length, with a separate undecidable column for the 156 LLM-judged questions. See
`data/manifests/lmev2_leakage_small_summary.json` and the flagged-cell manifest
`data/manifests/lmev2_leakage_small.jsonl`.

Read alongside the degeneracy caveat: **69 of 451 V2 questions are multiple-choice with gold answers of
1–5 characters** (`mc_choice_match` 68, `mc_choice_set_match` 1). Those are **structurally un-auditable**
for leakage and must not be folded into a pooled rate.

## Reproduce
```bash
PY=/Users/bellayang/miniconda3/bin/python3.13   # 3.9 cannot import the vendored scorer
$PY scripts/audit_leakage.py --controls-only
$PY scripts/audit_leakage.py --v1 --v1-which s
$PY scripts/audit_leakage.py --v2 --root /tmp/lmev2 --tier small
```

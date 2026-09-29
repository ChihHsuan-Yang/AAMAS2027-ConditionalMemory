# The LongMemEval-V2 memory unit, future-task unit, and pairing

Owner: Sub-agent A. Measured 2026-09-29. Every number here was computed from the checksum-verified
dataset; none is quoted from a prior document.

Reproduce with:
```bash
/Users/bellayang/miniconda3/bin/python3.13 scripts/build_lmev2_units.py \
    --root /tmp/lmev2 --tier small --seed 20261008
```

## 1. Why the `small` tier

| | `lme_v2_small` | `lme_v2_medium` |
|---|---|---|
| haystack size | 100 for all 451 questions | 500 for 428 q; 387–487 for 23 |
| distinct haystacks **as sets**, per domain | web **1**, enterprise **1** | web **222**, enterprise **211** |
| union of trajectory ids | **200** (web 100, ent 100, disjoint) | 1,473 |

On `small` there is exactly **one** haystack per domain — identical even as an **ordered tuple**, so there
is no per-question ordering confound. Every memory is therefore legitimately available to every question in
its domain, which is exactly the "same memory, multiple future tasks" structure `DeltaU` is defined over,
with no availability confound between arms. Positive control that this test can distinguish: run on
`medium` it returns 222 / 211.

## 2. The memory unit: PAGE VISIT

**Definition.** The maximal run of consecutive trajectory states sharing one `state["url"]`.

**Why this one.** The boundary is drawn by the *past agent's own navigation* — it is a naturally occurring
span, not a window we imposed, and it is computed from the trajectory alone. `segment_page_visits()` takes
a trajectory and nothing else, so it is *structurally* incapable of seeing a future task.
`assert_writer_blind()` re-checks at runtime and has its own positive control in the test suite.

**Measured token distribution** — official `Qwen/Qwen3.5-9B` tokenizer (the one
`harness.py::get_memory_context_processor()` loads), rendering copied verbatim from upstream
`memory_modules/codex.py`. Over 200 trajectories / 5,095 states:

| candidate | n | min | p25 | **median** | p75 | p90 | p99 | max | mean |
|---|---|---|---|---|---|---|---|---|---|
| whole trajectory | 200 | 5,286 | 31,639 | 103,886 | 320,767 | 646,256 | 2,463,354 | 2,573,538 | 258,859 |
| single state | 5,095 | 34 | 3,716 | 5,628 | 12,191 | 15,592 | 72,748 | 127,129 | 10,136 |
| **page visit** | **1,889** | **348** | **5,055** | **7,261** | **13,501** | **35,994** | **487,251** | **2,565,842** | **28,350** |

States per page visit: median 1, p90 4, max 95. Page visits per trajectory: median 4, max 88.
Header duplication overhead across units: **+3.44%**.

**Ablation granularity** — the property that makes this a *memory* ablation rather than a context ablation.
Removing one unit removes (states basis): median **3.33%** of its own trajectory and median **0.058%** of
the whole 100-trajectory domain haystack. Contrast LongMemEval-V1's oracle file, which is 100% evidence, so
ablating there removes the entire context.

⚠️ **23 of 1,889 units (1.2%) are their whole trajectory** (single-page trajectories). Ablating one removes
a whole past episode — a categorically different intervention. Report separately or exclude, explicitly.

**Recommended eligibility cap: 32,768 tokens.** Keeps 1,687 units (89.1%) and 193/200 trajectories.
**NOT applied in the manifest** — all 1,889 units ship with their token counts so the cap stays a reversible
analysis-time filter. It is a real selection: excluded units skew away from web (0.472 → 0.337 web share)
and toward long units (median 7 vs 1 states), though outcome composition is close (failure share 0.686 vs
0.644). Run sensitivity at 16k / 32k / 64k.

## 3. The future-task unit

One question + its `eval_function` spec. **295 of 451 are deterministic**; 156 need an LLM judge.

There are **8 distinct spec strings, not 6** — `norm_phrase_set_match` and its `_ordered` variant each
appear with two different `separators` settings (`,;` and `;`). **Dispatch on the full spec string, never
the function name.**

Scoring uses the **verbatim vendored upstream scorer** (`src/p1mem/adapters/vendor/`,
sha256 `f8ba659e…417ac`, upstream commit `2cc8c540`). Do not reimplement: `norm_phrase_set_match` is **not**
set equality but gold-phrase **containment** (extra prediction text is not penalized), which a name-based
reimplementation gets wrong.

`FutureTask.score()` **raises** for LLM-judged questions rather than returning a default — a silent `False`
would turn "cannot evaluate" into "wrong answer" for 156 of 451 questions in every arm.

## 4. Pairing

`select_pairs(..., seed=20261008, tasks_per_memory=8)` → **15,112 cells** (1,889 × 8).

Within domain (the two trajectory pools are disjoint), stratified by `question_type` — the benchmark's own
memory-ability taxonomy, so the semantic-distance axis is externally authored. Each memory takes at most one
task per stratum before repeating, so every memory faces a spread: measured, all 1,889 memories get exactly
8 tasks drawn from 3 strata (1,024 memories) or 4 (865).

Determinism: `random.Random(f"{seed}:{memory_id}")`, keyed per memory so adding or removing one memory does
not perturb another's draw. The build script asserts **both** that the same seed reproduces byte-identically
**and** that a different seed differs (so reproducibility is not vacuous).

Each cell carries `in_official_haystack` — whether the authors put this trajectory in this question's
medium-tier haystack. A free externally-authored relevance label: 11,384 True / 3,728 False, and crucially
**696 of 1,889 memories have mixed cells**, so it supports a *within-memory* contrast.

⚠️ `same_site` is `None` for web pairs. Question environments are finer-grained
(`webarena-reddit`/`-cms`/`-onestopshop`) than trajectory environments (`webarena`), so site-level match is
**not derivable** from the shipped data. It is recorded as unknown, never as False. An earlier version used
naive equality and silently re-encoded `domain`.

## 5. 🔴 Known structural limits

1. **Exactly one deterministically-scorable `errors-gotchas` question exists** (`626e401e`, web). The other
   28 are LLM-judged and enterprise has none. That one question is 865 of 6,920 web cells (12.5%).
   Per-stratum gotchas results are single-question; cluster standard errors by `task_id`.
2. Deterministic tasks per (domain, stratum): web 60/51/42/1, enterprise 74/35/32/0
   (static / dynamic / procedure / gotchas).
3. V2 ships **no answer-bearing evidence labels** at all — unlike V1's `answer_session_ids`. There is no
   ground truth for "which memory should have helped", so cross-checks must come from
   `in_official_haystack` and from leakage flags.

## 6. Answerability under segmentation: 94.2%

A unit definition is only useful if answers survive it. For each of the 295 deterministic questions,
whether **at least one** page-visit unit in its domain carries the gold answer (normalized containment;
865 web + 1,024 enterprise units):

| question_type | with >=1 carrying unit / total |
|---|---|
| static-environment | 130 / 134 |
| dynamic-environment | 80 / 86 |
| procedure | 67 / 74 |
| errors-gotchas | 1 / 1 |
| **TOTAL** | **278 / 295 = 94.2%** |

The 17 questions with no carrying unit can only ever produce `DeltaU <= 0`. Exclude them from the primary
analysis **explicitly**, as a stated exclusion, not by silent omission.

⚠️ This uses the same containment test as the leakage detector and so inherits its punctuation-glued false
negative (see `leakage.prove_detector_can_fail`, control `known-fn/punctuation-glued`). **94.2% is a lower
bound.**

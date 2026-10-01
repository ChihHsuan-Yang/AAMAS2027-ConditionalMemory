# F_judge for the LLM-judged stratum — measured

**SA-LME-JUDGE, 2026-09-30/10-01.** Measures `F_judge` (prereg §2 row 3: scorer
disagreement on **byte-identical** outputs) for `llm_abstention_checker` and
`llm_gotchas_checker`, the two scorers that gate the **156** LongMemEval-V2
questions currently excluded from the main stratum.

Every number below was re-derived from `results/f_judge/*.json{,l}`. Nothing is
quoted from recall. **The full 156-question arm was NOT run** — measuring the
floor first is the point.

---

## 1. Headline

| scorer | F_judge | disagreements / comparisons | 95% CI (Clopper–Pearson) | units |
|---|---:|---:|---|---:|
| **pooled** | **0.0000** | **0 / 240** | **[0.0000, 0.01525]** | 48 |
| `llm_abstention_checker` | 0.0000 | 0 / 160 | [0.0000, 0.02279] | 32 |
| `llm_gotchas_checker` | 0.0000 | 0 / 80 | [0.0000, 0.04506] | 16 |

48 stored reader outputs, each re-scored **6 times** by the LLM judge, giving
5 comparisons per unit against pass 0 — `noise.judge_floor`'s own convention,
so these sit on the same scale as the ledger's existing **0 / 1,916** (pilot)
and **0 / 3,486** (official) for the deterministic scorers.

The point estimate is 0 on both scorers, and the **identical** number through
the shipped estimator (`noise.judge_floor`, explicit-rescore path, task-aware
key): `point = 0.0` over 55 comparisons.

> ⚠️ **The CI, not the point estimate, is the result.** A bootstrap over an
> all-zero sample returns `[0, 0]` for any n, which reads as a certainty the
> denominator does not support. The honest statement is **F_judge ≤ 1.5%
> (pooled), ≤ 2.3% abstention, ≤ 4.5% gotchas** at 95%. The rule-of-three
> upper bounds agree: 0.01240 / 0.01855 / 0.03675.

---

## 2. 🔴 The zero is endpoint determinism, not rubric robustness

**This is the finding that matters, and it is the opposite of reassuring.**

The judge returned **byte-identical text on every one of the 6 passes** — 408/408
judge calls, **0 units** out of 48 whose judge text differed at all. Not merely
the same label: the same characters, including the free-text `reason` field.

A floor of 0 measured on a scorer whose output never moves is **prereg A1.4's
F_empty failure in a new costume**: the cached WITHOUT arm also had spread
exactly 0.000, and it measured nothing.

**A server-side cache is ruled out**, two ways:
- later passes are **not** faster than pass 0 (median **1.018 s** vs **1.016 s**);
  a cache hit would collapse to near-zero latency;
- the same prompt at `temperature=1.0` returns **8/8 distinct texts**, so the
  gateway is not collapsing six identical requests into one stored response.

So the greedy judge really is re-run each time, and really is deterministic.

> **`F_judge = 0` is a property of (this judge model) × (greedy decoding) ×
> (this reasoning_effort) × (this gateway). It is NOT a property of the
> rubric.** It does not transfer to a sampled judge, a different judge model,
> or a different `reasoning_effort` — each of those is a **new scorer arm**
> whose floor must be re-measured, exactly as `docs/MODEL_ARMS.md` requires for
> readers.

### The margin behind the zero

Forcing the sampler to move (`temperature=1.0`, 6 passes, 360 calls) is a
**different scorer arm** and is **never pooled into F_judge**. It answers the
question the zero cannot:

| stratum | disagreement | rate | 95% CI | text moved |
|---|---:|---:|---|---:|
| real outputs, pooled | 2 / 240 | 0.0083 | [0.0010, 0.0298] | 48/48 |
| `llm_abstention_checker` | 0 / 160 | 0.0000 | [0.0000, 0.0228] | 32/32 |
| `llm_gotchas_checker` | **2 / 80** | **0.0250** | [0.0030, 0.0874] | 16/16 |
| **borderline (constructed)** | **4 / 55** | **0.0727** | [0.0202, 0.1759] | 11/11 |

The judge text moved on **every** unit, and the label still held on all but
two — so the rubric is reasonably stable, but **`llm_gotchas_checker` is where
the instability lives**, and it rises to ~7% on deliberately ambiguous inputs.
The borderline stratum is **constructed to be hard** and is an upper stress
reading, not a floor. One borderline call returned an empty judgement and is
recorded as **`None` — unscorable, dropped from the denominator, never 0.0**.

---

## 3. There were no stored LLM-judged outputs — proven, then generated

The task allowed for this, and it is the case.

| | |
|---|---:|
| cell artifacts scanned | 5 (`deltau_pilot`, `deltau_official`, `deltau_screened`, `repr_scaleup`, `gemma_reader/smoke`) |
| response caches scanned | 16 |
| rows on an **LLM-judged** question | **0** |
| rows on a **deterministic** question | **5,655** |

**Positive control:** the same join, on the same field, against the same file
finds **5,655** deterministic rows and resolves **275/275** executed
`future_task_id`s against `questions.jsonl`. The key is live and the path is
right, so the LLM-judged zero is a **real absence**, not a bad glob. (Both
pair manifests agree: 0 LLM-judged rows in 15,112 frozen pairs and in the
1,157-cell screened design — `select_pairs(deterministic_only=True)` and an
explicit `raise` in `k2_run_screened.py` kept them out by construction.)

So 48 reader outputs were generated first, on the **frozen A1 arm**
(metis / `gpt-oss-120b` / `reasoning_effort=low` / `temperature=0` /
`max_tokens=512` / `p1_deltau_raw_v1`), 24 questions × {with, without} memory,
K=4 filler from the screened design's own band and disjointness rule.
Context: 13,646 / 18,186 / 23,814 tokens (min/median/max). 0 errors.

**Judge configuration = the upstream harness defaults** (`harness.py::parse_args`):
`reasoning_effort="medium"`, `max_completion_tokens=4096`, **no temperature and
no top_p sent**. That is the configuration a real 156-question run would use,
and it is exactly where judge nondeterminism would live.

---

## 4. Controls — every one of which can fail

A null is worthless without proof the instrument can report otherwise.

| # | Control | Result |
|---|---|---|
| 1 | **Estimator fires on a planted disagreement.** Flip one pass of one unit in the REAL artifact | **1/240, FIRES** ✅ |
| 2 | Flip five units | **5/240, FIRES** ✅ |
| 3 | **A `None` label leaves the denominator.** Plant one | scored 48 → **47**, dropped 1, disagreements still 0 ✅ |
| 4 | **The judge is not a degenerate constant.** Both labels must appear | **0: 270, 1: 18** on real outputs ✅ |
| 5 | **Gold-answer positive control.** Feed the judge the gold answer as the response | **48/48 label 1** (vs 18/288 on real outputs) ✅ |
| 6 | **The grouping key includes the TASK** (defect #2) | task-aware **0.0** vs task-free **1/6 = 0.1667** — *the control discriminates* ✅ |
| 7 | **Server cache ruled out** | later passes not faster (1.018 s vs 1.016 s); 8/8 distinct at temp 1.0 ✅ |

Control 6 is defect #2 reproduced on purpose: two rows are given **identical
output text and different rewards on different tasks**. A task-free key calls
that scorer disagreement (0.1667, the same shape as the retracted 0.1486); the
shipped task-aware key correctly ignores it. **The key in use is demonstrated,
not asserted.**

Control 5 matters because of control 4's shape: the judge answers 0 on 270 of
288 real re-scorings. A scorer that *always* said 0 would be trivially
deterministic and its floor meaningless — the gold control shows it flips to 1
on all 48 when the response deserves it.

---

## 5. Can the 156 now form a valid separate stratum?

**Yes — as a separate stratum, under three conditions. They may never be pooled
with the 295.**

**Why a separate stratum is now defensible.** The blocker was that F_judge was
*unmeasured*, and `docs/COVERAGE_MANIFEST.md` §1 is explicit that the exclusion
is for that reason and not for difficulty or outcome. It is now measured:
**0/240, ≤1.5% at 95%**, on a positive-controlled instrument.

**Why they still may not be pooled with the 295.**

1. The deterministic floor is **0 with no upper bound of practical concern**
   (0/3,486 ⇒ ≤0.106%); the LLM floor is **0 with a ≤1.5% upper bound** —
   **14.4× wider**. Pooling adopts the wider uncertainty for all 451 questions
   while reporting one number.
2. The two scorers are **not even equal to each other**: ≤2.3% vs ≤4.5%, and
   under forced sampling `llm_gotchas_checker` is the only one that moves.
3. `verifier_id` and `verifier_version` are in `IDENTITY_GUARD_KEYS`, so
   `require_homogeneous` will refuse the pool anyway — correctly. The judge
   model, cluster, effort and token budget are now part of
   `verifier_version`: `vendored@f8ba659e237c+judge:gpt-oss-120b@metis/effort=medium/max_ct=4096`.

### What running the 156 would require

| | |
|---|---|
| **Cost** | 156 questions × 2 arms × 2 replicates = **624 reader calls**, plus **624 judge calls** (1 per output). At the measured 296/min reader and ~820/min judge, well under an hour. |
| **Pairing** | `select_pairs(deterministic_only=False)` — currently hard-coded `True`, and `k2_run_screened.py` **raises** on an LLM-judged task. Both are deliberate and must be changed explicitly, not bypassed. |
| **Scoring** | `FutureTask.score()` **raises** for LLM-judged questions by design ("Do not substitute a default score"). It needs an LLM-judged path that passes `question_item` / `parsed_prediction` / `model_response` the way `harness.py::score_prediction` does — the reader's **raw** response, not the boxed extract. |
| **`None` discipline** | An unparseable judgement, a truncated judge response, or an endpoint error is **`None`**, never 0.0. One such case already occurred (1/360). |
| **UNKNOWN override** | `harness.py:1055` forces 0 when the boxed answer is UNKNOWN. **0 of 48** outputs parsed to UNKNOWN here, but the official-prompt arm abstained 378/960 — so on the official prompt this override would dominate and must be applied, or the re-scoring measures verifier drift instead of judge noise. |
| **Re-measure the floor if anything changes** | A different judge model, effort, or temperature is a **new scorer arm**. This floor does not transfer. |
| **Report it apart** | Separate table, separate floor, `verifier_version` visible. Never a 451-question pooled accuracy. |

### What this does NOT license

- It does **not** say the LLM judge is reliable in general — only that it is
  **byte-deterministic at this exact configuration**.
- It does **not** make `F_judge = 0` usable as the reference floor. Prereg §2
  sets `F = F_exec`; and `F_exec` for the LLM-judged stratum is **still
  unmeasured** — the 48 outputs here are 1 replicate per (task, arm).
- The 48-unit denominator is **a floor measurement, not the arm**. It bounds
  judge noise; it says nothing about ΔU on these 156 questions.

---

## 6. Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9 and breaks pytest

$PY scripts/sa_lme_judge_floor.py --dry-run   # plan + stage-0 null, no calls
$PY scripts/sa_lme_judge_floor.py             # 48 reader + 408 judge calls
$PY -m pytest tests/test_analysis_noise.py -q # 20 passed
```

| artifact | rows |
|---|---:|
| `results/f_judge/f_judge_measurement.json` | the report, all 9 stages |
| `results/f_judge/judge_calls.jsonl` | **408** (288 floor + 48 gold control + 72 borderline) |
| `results/f_judge/judge_sensitivity_calls.jsonl` | **360** (temperature=1.0 arm) |
| `results/f_judge/reader_outputs.jsonl` | **48** |
| `results/f_judge/reader_cache.jsonl` | **48** |

**Exit code 0 is not success** — the row counts above are the check, and the
script prints them.

---

## 7. For `docs/DEFECT_REGISTER.md`

> **A zero that is a property of the instrument's determinism, not of the
> thing being measured.** `F_judge = 0` over 240 re-scorings looks like
> "the rubric is unambiguous". It is actually "the endpoint is greedy": the
> judge returned **byte-identical text**, `reason` field included, on 408/408
> calls. The number is correct and the inference it invites is wrong. Forcing
> the sampler to move leaves the label intact on 238/240 — so the rubric *is*
> fairly stable — but that is a **second measurement**, not something the zero
> established. Same shape as F_empty's cached WITHOUT arm (prereg A1.4), and
> as defect #1: *a spread of zero is evidence about the apparatus before it is
> evidence about the subject.*

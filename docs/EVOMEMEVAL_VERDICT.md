# EvoMemEval — verdict, verified from the released artifact

**Settled 2026-09-29 by the Master Agent, from data downloaded and counted, not inferred
from an abstract.** This was the project's single highest-priority open question.

---

## 0. Verdict

> **EvoMemEval evaluates the same memory item against multiple distinct future tasks, and
> its released data contains memories whose label flips between `useful` and `harmful`
> across tasks. P1 cannot claim the memory × task counterfactual matrix as a new object.**

**But three things survive, and they are enough for a paper** — see §4.

## 1. How the login wall was bypassed

The OpenReview PDF is 403 anonymously (and the positive control `DT7JyQC3MR` 403s
identically, so that channel says nothing). Sub-agent C found the artifact public on
GitHub: **`github.com/hidyouths/EvoMemEval`** — HTTP 200, positive-controlled against
`xiaowu0162/LongMemEval` which also returned 200.

⚠️ **The repo de-anonymizes an ACL ARR submission under review.** We use it as public
evidence about the state of the art; we do not cite it in a way that turns a
double-blind-review artifact into a target. Cite the OpenReview record.

## 2. What I counted myself

Downloaded the four point-wise payloads and counted:

| Quantity | Sub-agent C | **Master Agent** | Agrees? |
|---|---|---|---|
| Total records | 300 | **300** | ✅ |
| Distinct (dataset, memory_id) | 195 | **195** | ✅ |
| Memories on ≥2 distinct tasks | 48 | **46** | ⚠️ **corrected** |
| Of those, spanning `useful`↔`harmful` | 17 | **17** | ✅ |
| Flip rate among multi-task memories | 35.4% | **37.0%** | follows from the 46 |

The 46/48 difference: memory ids must be scoped **per dataset** (the same id string recurs
across `alfworld`/`babyai`/`scienceworld`/`webshop`). I scope by `(dataset, memory_id)`.
**Use 46 and 37.0%.**

Verified example (`alfworld`, memory `a165d917-…`): `harmful` on
`look_at_obj_in_light-Book-…`, `useful` on `look_at_obj_in_light-Pencil-…` — **a sign flip
between two tasks of the same family.**

Record fields: `selected_memory_id`, `task_name`, `task_idx`, `variation_idx`,
`memory_setting`, `selected_rank`, `memory`, `reward`, `reward_label`, `utility`,
`overall_label`.

## 3. 🔴 Their rate is not a natural base rate — and the metadata proves it

Verified in each payload's own metadata:

```json
"point_balance": {"enabled": true, "seed": 42,
                  "original_label_counts": {"useful": 15, "neutral": 85, "harmful": 45},
                  "target_count_per_label": 15}
```

Final released distribution: **exactly `harmful` 100 / `neutral` 100 / `useful` 100.**
Down-sampled to the minority class with seed 42. **The 37.0% flip rate is inflated by
construction and is not a measurement of anything natural.**

### The gift inside the balancing

The payloads **preserve pre-balance counts**, which is a natural prevalence:

| Dataset | n before balancing | harmful | useful |
|---|---:|---:|---:|
| alfworld | 145 | 45 (**31.0%**) | 15 (10.3%) |
| scienceworld | 88 | 27 (**30.7%**) | 16 (18.2%) |
| webshop | 304 | 46 (**15.1%**) | 42 (13.8%) |
| **pooled (3 of 4)** | **537** | **22.0%** | **13.6%** |

> **Naturally occurring harmful memory is not rare — ~22% pooled.** This is the single most
> useful external number we have, and it **directly answers the TraceRetain hazard**: the
> worry was that a clean benchmark has no real pollution so every arm lands in one CI.
> At a 22% natural harm rate, pollution is present without planting anything.

⚠️ These are **their** per-memory labels over **their** task set, not our measurement.
Quote as external evidence with the source named; never as our result.

`babyai` has `point_balance.enabled: false` (a `fill_sampling` path instead), so it
contributes no pre-balance counts.

## 4. What survives for P1 — three things, and they are load-bearing

1. **The variance decomposition.** Their released code contains **zero** variance,
   interaction, or flip logic (Sub-agent C's grep; consistent with the payloads being
   label lists). They produce categorical labels — `useful`/`neutral`/`harmful` — **not a
   variance decomposition against an execution-noise floor.** Nobody has partitioned memory
   utility into memory / task / interaction components.
2. **A noise floor.** Their labels are single-shot per cell. There is no repeated-seed
   arm, so no execution-noise floor, so **no way to know which of their 17 flips are real.**
   Ours is the first design where a flip must clear a measured floor to count.
3. **A natural base rate.** Theirs is destroyed by seed-42 balancing. The pre-balance
   metadata hints at ~22% harm, but that is prevalence, **not a per-memory cross-task flip
   rate.**

### What P1 must now stop claiming

- ❌ the memory × task counterfactual matrix as a new object — **EvoMemEval's released data
  is one**
- ❌ that no one evaluates the same memory against several future tasks — **they do**
- ❌ any framing implying sign flips have never been observed — **17 are in their file**

### What P1 can claim

> Prior work labels per-(memory, task) utility categorically and reports aggregate
> accuracy. We measure the same object as a **signed, repeated quantity**, decompose its
> variance into memory, task, and interaction components, and evaluate every sign change
> against an execution-noise floor measured from repeated identical conditions.

**One caution.** `reward` in their data ranges **−100 to +100** and `utility` carries
`[{reward}, {completion_tokens}]` — so these are **real execution outcomes**, not LLM
judgments. Their counterfactual is as real as ours. The distinction is **not** measured
vs. judged; it is **signed + replicated + decomposed** vs. **categorical + single-shot +
aggregated.** Do not overstate it.

## 5. Still unresolved

**Whether the paper body reports any cross-task variation statistic.** Abstract, checklist,
README, and released code do not. Settling it needs a logged-in OpenReview view of
`n3GMbobXnc`.

> **Do not let anyone settle this by inference from the abstract.** If the body reports a
> per-memory variance or flip rate, claim (1) in §4 narrows further and the Introduction
> must be rewritten again.

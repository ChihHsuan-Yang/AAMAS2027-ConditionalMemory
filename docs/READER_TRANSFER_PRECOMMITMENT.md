# Reader-transfer replication — PRECOMMITMENT

**Written 2026-09-30 by SA-GEMMA-READER, BEFORE any Gemma reader call was issued
against a design cell.** Nothing below was chosen after seeing a Gemma outcome.
The 12-row smoke test (`results/gemma_reader/smoke_cells.jsonl`) exists and is
explicitly **not** a result; its 2 cells per representation were themselves
picked by the non-outcome rule restated below.

## The question

Does the measured utility of a memory transfer across **reader** backbones, or
is the representation finding an artifact of `gpt-oss-120b` reading memories
that `gpt-oss-120b` wrote?

## What varies, and what does not

**ONE thing varies: the reader model.** `gpt-oss-120b` → `gemma-4-31B-it`, both
on cluster `metis`, both `api` framework, both `system_fingerprint: fastcoe`.
So this is a reader comparison and **not** a reader×cluster comparison.

Held byte-for-byte, and **asserted in code at run time rather than claimed**:

| held | how it is enforced |
|---|---|
| memory text | `results/repr_scaleup/memories.jsonl`, sha256 vs the gpt-oss run's recorded fingerprint (GATE 1) |
| system prompt | sha256 vs the gpt-oss run's recorded fingerprint (GATE 2) |
| filler pool | rebuilt by the same rule, sha256 vs the screened run's recorded value (GATE 3) |
| the actual request bytes | every rendered request's `context_sha256` vs the hash the gpt-oss cache stored for the same cell (GATE 4) |
| target position, K, filler token count | per cell, vs the values the gpt-oss **row** recorded (GATE 5) |
| task prompt, scorer, retrieval method, temperature=0, max_tokens=512 | unchanged constants |

GATE 4 cannot run on `raw`: the screened cache predates `context_sha256` in the
key shape. That is a **real limitation**, recorded as `unverifiable_v1_key`,
never counted as agreement. GATE 5 is added for exactly that reason — it is a
per-cell check on raw that gates 1–3 (which are global) cannot provide.

## Eligibility — fixed here, non-outcome-based

The **representation sub-universe** of `docs/COVERAGE_MANIFEST.md`:

1. stratum ∈ {BEARING, MATCHED_CONTROL} from `data/manifests/k1_screened_cells.jsonl`
   → **285 cells** (139 BEARING + 146 MATCHED_CONTROL), 60 memories, 126 tasks;
2. × representations {raw, summary, structured} → **855 cell-representations**;
3. minus cells whose **write failed** (3 structured memories, 8 cells) → **847**.

Nothing in that list mentions a reward, a delta, a label, or anything either
reader answered. Rule 3 is a property of the **write** pass, which ran before
any reader did.

Join key is **`(memory_unit_locator, future_task_id)`**. Not `memory_id`
(a content hash) and **not `condition_id`** — `condition_id` embeds the
representation *and* the reader name, so a join on it returns zero rows.

## Replicate policy — matched, and why 2 and not 3

`gpt-oss` ran **2** replicates on summary/structured and **3** on raw
BEARING+MATCHED_CONTROL. Prereg §12 makes the **balanced minimum-replicate
subset** the primary estimate. Therefore:

* Gemma runs **2 replicates** on all three representations;
* the gpt-oss comparator uses **replicates 0 and 1 only**, for all three.

Re-derived before committing to this: on all **285** raw BEARING+MC cells the
mean of 3 replicates differs from the mean of the first 2 in **0** cells, so
dropping raw's third replicate changes no gpt-oss number. (This reproduces, on
the cells used here, the independently recorded 0/285 in
`docs/REPRESENTATION_RESULT.md`.)

## Budget

847 cells × 2 replicates × 2 arms = **3,388 calls**. At the measured Gemma
throughput of 74 completions/min at 16 workers that is ≈46 min. The full
sub-universe is affordable, so **no subset rule is invoked**. If the run is
interrupted, the response cache makes it resumable and the artifact check will
report the shortfall rather than analysing a partial set silently.

## Analysis — specified before the data exists

**Matched-set rule.** Per-representation denominators differ (285/285/277).
Every reader comparison is computed on the set of pair keys **interpretable
under both readers and that representation**, and the denominator is printed
beside every number. Cross-representation comparisons additionally restrict to
the keys common to all three (277), as `docs/REPRESENTATION_RESULT.md` does.
Means over different cell sets are never compared.

Reported, per representation:

1. mean ΔU under gpt-oss, mean ΔU under Gemma, both on the same cells;
2. the **paired per-cell difference** ΔU_Gemma − ΔU_OSS, with task-clustered
   and episode-clustered bootstrap CIs (tasks are the clustering unit the
   project already uses: a third of cells sit on ten tasks);
3. the paired within-memory BEARING − MATCHED_CONTROL contrast under each
   reader — the quantity `REPRESENTATION_RESULT.md` actually reports;
4. sign agreement and Pearson/Spearman correlation of per-cell ΔU across
   readers;
5. useful/neutral/harmful agreement under the pre-registered §4 label rule,
   each reader labelled against **its own** measured `F_exec`.

**Null-result handling.** Any of these is a valid, publishable outcome and none
is a failure: same utility; same ordering, different magnitude; a different
representation preference; or no transfer at all. The run is not aimed at
replication.

**reward None.** A call that raises — including the Gemma truncation guard —
yields `reward = None` and an `error_code_if_any`. **Never 0.0.** A 0.0 there
reads as a wrong answer, drives ΔU negative, and manufactures a harmful memory.

**Positive controls that must fire, or the corresponding null means nothing.**

| null to be defended | the control |
|---|---|
| GATE 4 matches | plant a one-character change in `render_memory` and require the gate to abort |
| GATE 5 matches | plant a wrong position/filler and require the gate to abort |
| `F_exec = 0` for Gemma | flip one replicate in a sample of cells; the floor must become > 0 |
| the cache cannot cross readers | a gpt-oss key must HIT before a Gemma key is shown to MISS |
| "zero rows" on any join | the join must be shown to return rows on a key known to exist |

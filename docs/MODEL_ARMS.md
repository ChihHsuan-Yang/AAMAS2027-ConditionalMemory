# Model arms — who wrote each memory, who read it

**Purpose: no future agent should have to infer which model produced which
result.** Every result row carries these identities in its schema fields
(`memory_writer_model`, `memory_writer_cluster`, `reader_model`,
`reader_cluster`, `reader_prompt_version`, `reader_reasoning_effort`); this
table is the human-readable index of them.

> 🔴 **Cluster and serving configuration are experimental identity.** A change
> to any pinned value defines a **new arm**, never additional data for an
> existing one. Do not backfill across a config change.

## Executed arms

| Arm | Writer | Reader | Cluster | Prompt version | Temp | Max output | Workers | Status |
|---|---|---|---|---|---|---|---|---|
| **A1** LongMemEval Raw | deterministic (`RawExtractiveWriter`, 0 model calls) | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 | **DONE** |
| **A2** LongMemEval Summary | `gpt-oss-120b` | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 | **DONE** |
| **A3** LongMemEval Structured | `gpt-oss-120b` | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 | **DONE** |
| **B1–B3** SciCode Raw/Summary/Structured | deterministic / `gpt-oss-120b` | `gpt-oss-120b` | metis | `scicode_deltau_v1` | 0 | 1024 | 16 | **DONE** (154 pairs, full pool) |
| **C1–C3** SWE-bench Raw/Summary/Structured | deterministic / `gpt-oss-120b` | `gpt-oss-120b` | metis | `swebench_v2_symmetric` | 0 | 2048 (reader) / 1024 (writer) | 16 (writer), sequential (reader) | **PARTIAL** — 32 cells, django only, 13 matched |

Structured variant: `procedural` on SciCode, `general` on LongMemEval and
SWE-bench.

## Planned arms — reader-only replication (the second backbone)

🔴 **Not yet executed at scale. No result may be claimed for these until they run.**
Infrastructure is built and proven (2026-09-30); what exists today is a **12-row
smoke test**, which is an infrastructure proof and **not a measurement**.

| Arm | Writer | Reader | Cluster | Status |
|---|---|---|---|---|
| **R1** | deterministic Raw | `gemma-4-31B-it` | **metis — verified live by a real POST** | **READY** — smoke 2/285 cells |
| **R2** | `gpt-oss-120b` Summary | `gemma-4-31B-it` | metis | **READY** — smoke 2/285 cells |
| **R3** | `gpt-oss-120b` Structured | `gemma-4-31B-it` | metis | **READY** — smoke 2/277 cells |

### FROZEN Gemma reader configuration

Pinned 2026-09-30. Every value is a measurement with a named artifact behind
it; changing any of them defines a **new arm**, never additional data.

| Arm | Writer | Reader | Cluster | Prompt version | Temp | Max output | Workers |
|---|---|---|---|---|---|---|---|
| **A1** LongMemEval Raw | deterministic (`RawExtractiveWriter`, 0 calls) | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| **A2** LongMemEval Summary | `gpt-oss-120b` | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| **A3** LongMemEval Structured | `gpt-oss-120b` | `gpt-oss-120b` | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| **R1** LongMemEval Raw | deterministic (`RawExtractiveWriter`, 0 calls) | **`gemma-4-31B-it`** | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| **R2** LongMemEval Summary | `gpt-oss-120b` | **`gemma-4-31B-it`** | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |
| **R3** LongMemEval Structured | `gpt-oss-120b` | **`gemma-4-31B-it`** | metis | `p1_deltau_raw_v1` | 0 | 512 | 16 |

The machine-readable form is `src/p1mem/schema.py::READER_ARMS`; a run script
asks for an arm by name and `reader_row_fields()` splats the five identity
fields into the row, so a script cannot populate four and leave the fifth null.

**`reasoning_effort` on R1–R3: the field is OMITTED, and recorded as
`none:not_applicable`.** Not "low", and not `"none"` (metis 400s on that). It
is accepted by the API but **verifiably inert**: content sha identical across
omitted/low/medium/high, against a within-session determinism control (3/3
identical, one probe run) and a positive control on gpt-oss that *does* move
(reasoning_tokens 58/118/473).
`P1Client.chat` still **defaults to `"low"`**, so every Gemma call must pass
`reasoning_effort=None` explicitly; `READER_ARMS` carries that value so no
caller has to remember.

**Workers = 16, measured for Gemma, not inherited.** 252/252 requests clean at
≤16 at the real 25,176-token shape; **25.00%** 429 at 24 workers; **71.88%** at
32, where the ladder auto-aborted. 74.0/min sustained over 6 waves vs 73.2
burst. The number equals gpt-oss's by coincidence of measurement, not by
transfer — and Gemma degrades far harder past the boundary (25% vs 12.5% at 24).

🔴 **Throughput is NOT comparable between the two readers.** At the same 24k
shape and 16 workers, gpt-oss runs 169.9/min and Gemma 74.0/min: **Gemma is
43.6% of gpt-oss**, so budget ~2.3× the wall clock.

🔴 **`reasoning_tokens` is `None` on every Gemma row, and must stay `None`.**
Metis Gemma returns no `completion_tokens_details` at all (re-measured live
2026-09-30, against a gpt-oss control that returned `{"reasoning_tokens": 5}`
in the same session). Per the house rule, that is "could not be measured" —
coercing it to 0 asserts a measurement nobody made. **A token-cost comparison
between the two readers is therefore not apples-to-apples and must say so.**

> ⚠️ This also **corrects a claim in `docs/CLUSTER_DECISION.md`**: "Metis
> reports reasoning-token counts while Sophia does not" was true *of
> `gpt-oss-120b`*. It is a property of the **model**, not the cluster.
> `CLUSTER_REPORTS_REASONING_TOKENS` is keyed on cluster and so cannot express
> this; the validator now consults `READER_ARMS` first and falls back to that
> map only for models not in the registry.

### Two hazards that are live on this arm

**1. The capital `B` in `gemma-4-31B-it` is load-bearing.** Metis returns
**HTTP 200** for the lowercase `gemma-4-31b-it` and silently resolves it to the
capital form — it is not a 404. `P1Client._assert_model` catches it at call
time, and `KNOWN_SILENT_MODEL_ALIASES` now makes a mis-cased registry entry
raise before any call is made.

**2. 🔴 The truncation guard did not transfer, and has been fixed.** On
gpt-oss an under-budgeted call spends the budget on *reasoning* and returns
`content: null`, so the guard's `not content.strip()` clause fires. Gemma has
no separate reasoning stream: it spends the budget on the **answer** and
returns a plausible fragment. Measured live at `max_tokens=8`:
`finish_reason="length"`, `content="Here is the step-by-step"` — 24 non-blank
characters, which that clause reads as a normal answer. Scored, it is a wrong
answer that drives ΔU negative and **manufactures a harmful memory**.

`P1Client` now takes `truncation_is_always_an_error`, defaulted from the
registry, and the Gemma arms set it. **It is deliberately NOT enabled for
gpt-oss** — doing so would retroactively invalidate 8 already-published pilot
cells, which is a decision about existing results and not a side effect of a
code change. See "Truncation on the gpt-oss arms" below.

### Truncation on the gpt-oss arms — a finding, handed back undecided

The gap above is **not Gemma-specific**. Auditing every shipped cache found
`finish_reason == "length"` with **non-empty** content on gpt-oss too:

| Artifact | rows | `length` + non-empty |
|---|---:|---:|
| `results/deltau_pilot/cache.jsonl` | 1,918 | **8** |
| `results/pilot_representations/cache.jsonl` | 24 | 1 (a write call) |
| `results/repr_scaleup/write_cache.jsonl` | 120 | 10 (write calls) |
| `results/deltau_screened/cache.jsonl` | 5,198 | 0 |
| `results/deltau_official/cache.jsonl` | 1,920 | 0 |
| `results/repr_scaleup/eval_cache.jsonl` | 2,248 | 0 |

The 8 pilot rows reached **8 scored cells** (6 WITHOUT-arm at 3,011 chars; 2
WITH-arm whose entire output was `\boxed{C` — a *truncated answer token*
scored as a wrong answer). **All 8 have ΔU = 0.0 and `utility_label =
undetermined`, so no reported number moves**, and E1's headline is unaffected.
The write-pass rows are a different and already-documented case:
`representations.py` records `truncated` and keeps a truncated-but-parseable
memory on purpose.

**The two main runs (screened, repr_scaleup) have zero.** This is handed back,
not decided: whether to re-run those 8 pilot cells or annotate them is a call
about published results. Recorded in `docs/DEFECT_REGISTER.md`.

### 🔴 CORRECTION (2026-09-30, later): the fix above was INSUFFICIENT

The guard described above still hung off **`finish_reason == "length"`**. Under
16-worker load at the real 15–29k-token cell shape, metis/`gemma-4-31B-it`
returns truncated responses with `finish_reason` **`""`** *and*
`usage.stop_reason` **`""`** — neither says `"length"` — while
`completion_tokens` sits **exactly at `max_tokens`**. The guard was silent and
**7 fragments of 2,034–2,146 characters were returned as answers** before the
run was killed at 600/3,388 calls.

The sentence above — *"Measured live at `max_tokens=8`: `finish_reason="length"`"* —
is **true of a single idle request and false of the run**. A single-request
probe cannot find this; it was found by auditing the in-flight cache.

`P1Client._looks_truncated` now tests **three** observables, on both the fresh
and the cache-hit path:

```text
1. finish_reason == "length"              the documented signal
2. usage.stop_reason == "length"          the same fact, other field
3. completion_tokens >= max_tokens        the ARITHMETIC fact
```

Clause 3 cannot be misreported without the server also misreporting its own
token count. **Verified not to move a published number:** across **11,693**
`gpt-oss-120b` rows in every shipped cache the widened detector flags
**exactly the 19** rows clause 1 already flagged. Full account:
`docs/DEFECT_REGISTER.md` #20.

### A second defect found while fixing the first

`P1Client` enforced its truncation guard on a **fresh** response but **not on
a cache hit** — demonstrated by storing a `finish_reason="length"`,
`content=""` row and reading it back without an exception. The runner's
*resume* path is a cache read, so a killed-and-resumed run could score exactly
the truncations the first run refused. Fixed; both the model-id pin and the
truncation guard now run on both paths. Regression tests in
`tests/test_reader_arms.py`, each verified to fail against the unfixed code.

**Design constraint that makes R1–R3 interpretable:** they reuse the *exact
same memory artifacts* already written by gpt-oss — same source episode, same
future task, **same memory text byte-for-byte**, same controlled filler, same
scorer, same task prompt, same context construction, temperature 0. **Only the
reader changes.** That isolates the reader and answers the reviewer question
directly: *are the findings an artifact of gpt-oss reading memories written by
gpt-oss?*

⚠️ **Prefer the same cluster for both readers.** If Gemma is only reachable on
a different cluster, the reader comparison silently becomes a reader×cluster
comparison and must be reported as such.

⚠️ **Do not assume gpt-oss's 16 workers transfer.** The worker count for Gemma
is set by its own measured throughput ladder, not inherited.

## Writer × Reader factorial — EXECUTED 2026-10-01

Gemma-written memories are an **additional** writer arm; they never replace or
overwrite the gpt-oss-written memories. `results/repr_scaleup/memories.jsonl`
was asserted byte-unchanged (sha256 `b342151c7f3cac5a…`) before **and** after
the Gemma write pass.

| | Reader gpt-oss | Reader Gemma |
|---|---|---|
| **Writer gpt-oss** (Summary, Structured) | A2/A3 — **DONE** | R2/R3 — **DONE** |
| **Writer Gemma** (Summary, Structured) | W1/W2 — **DONE** | W3/W4 — **DONE** |
| **Writer deterministic** (Raw) | A1 — **DONE** | R1 — **DONE** |

🔴 **Raw has no writer axis and is NOT in the factorial.** It is a
deterministic span with **zero model calls**, so "writer gpt-oss raw" and
"writer Gemma raw" are the same bytes. The factorial covers Summary and
Structured only — and raw is the strongest representation under both readers,
so the factorial does not speak to the project's headline representation.

### FROZEN Gemma WRITER configuration

| Arm | Writer | Reader | Cluster | Writer prompt version | Temp | Max output | Workers |
|---|---|---|---|---|---|---|---|
| **W1** Summary | **`gemma-4-31B-it`** | `gpt-oss-120b` | metis | `summary_v1@1.0.0+6ee16b28b818` | 0 | 512 | 16 |
| **W2** Structured | **`gemma-4-31B-it`** | `gpt-oss-120b` | metis | `structured_v1@1.0.0+163d4cd3eb70` | 0 | 512 | 16 |
| **W3** Summary | **`gemma-4-31B-it`** | **`gemma-4-31B-it`** | metis | `summary_v1@1.0.0+6ee16b28b818` | 0 | 512 | 16 |
| **W4** Structured | **`gemma-4-31B-it`** | **`gemma-4-31B-it`** | metis | `structured_v1@1.0.0+163d4cd3eb70` | 0 | 512 | 16 |

The writer prompt versions are **byte-identical** to the gpt-oss arms' — the
version string is a digest of the prompt file, so equality of the string is
equality of the bytes. Only the writing MODEL differs.

🔴 **`truncation_is_always_an_error` is OFF on the WRITE pass for BOTH
writers, deliberately.** `representations.py` records `finish_reason` and keeps
a truncated-but-parseable memory on purpose, and gpt-oss's 7 truncated
summaries and 3 truncated structured writes are in the published arm on that
basis. Enabling the strict guard for Gemma's writes alone would make the two
writer arms differ in their **admission rule** as well as their model — a
second intervention wearing the first one's name. It stays **ON** for every
Gemma *reader* call, as in the published reader arm.

### 🔴 `gpt-oss-120b` is deterministic WITHIN a session, NOT ACROSS sessions

Measured 2026-10-01 by re-issuing the factorial's **WITHOUT** arm — which
contains no memory and whose request bytes were verified byte-identical
(500/500 stored `context_sha256`) — against the published 2026-09-30 run:

| reader | WITHOUT-arm requests | output text DIFFERS | reward differs | mean reward change |
|---|---:|---:|---:|---:|
| `gpt-oss-120b` | 1,124 | **554** | 84 | **−0.0320** |
| `gemma-4-31B-it` | 1,124 | **0** | 0 | 0.0000 |

**This does not contradict the 248/248 A/A result** — that measurement is
within one session and remains correct. Re-derived from the caches'
`written_at_utc`, the two calls in each A/A pair sit **54–178 s** apart
(gpt-oss) and **608–1,699 s** apart (Gemma), all inside one run. It is a
*different quantity*, and the distinction has to be stated every time either
number is quoted. Full sweep: `docs/SESSION_DETERMINISM_AUDIT.md`.

⚠️ **The two figures quoted for this drift are both correct and describe
different row files**, not a discrepancy: the WITHOUT rows of the writer-Gemma
arm (`factorial_cells_gemma.jsonl`, n=1,124) give **84** reward differences and
**−0.0320**; those of the writer-gpt-oss arm (`factorial_cells_gptoss.jsonl`,
1,122 non-null) give **82** and **−0.0303**. Text differs on **554** in both.
The table below is the writer-Gemma file.

Two consequences, both binding:

1. **Arms that will be compared must be executed in the same session.** The
   writer factorial re-ran its gpt-oss comparator arms for exactly this reason
   (`docs/WRITER_FACTORIAL_PRECOMMITMENT.md`, Amendment 1); a cross-session
   comparator would confound the contrast with the day it ran, by about the
   size of the effect.
2. **Cross-session stability is a property of the MODEL, not the cluster.**
   Gemma drifted 0/1,124 on the identical comparison. This is the same shape as
   `reports_reasoning_tokens` (defect #18): a per-model fact that a
   cluster-keyed assumption cannot express.

🔴 **A writer-arm cache key must name the WRITER.** `memory_content_id` is a
hash of `(episode_id, segment text)` and is therefore **identical across
writers** for the same unit. A key built on it would differ from the published
writer-gpt-oss key only in `context_sha256`. `w2_run_factorial.py` uses a hash
of `(writer_model, memory_text)` instead, and the control artifact verifies the
factorial's memory ids are **disjoint** from the published caches'.

This separates four questions that a single combined change would confound:
**reader effect** (same memory, different reader) · **writer effect** (same
experience compressed by different models) · **same-family effect** (writer and
reader from one family) · **interaction** (does writer choice matter differently
per reader).

🔴 **Cost must not be pooled across models.** Gemma formation and generation
tokens are a different currency from gpt-oss's; the frontier figure keeps model
identity explicit.

## What a new agent must check before trusting this table

1. `list-endpoints` and a **real POST** — advertised is not live. Four endpoints
   in this project's history were advertised and dead.
2. The resolved model id returned by the endpoint must equal the id sent
   (`P1Client` enforces this).
3. The response cache must not serve one model's response to another. Verify
   **behaviourally**, not by reading `KEY_FIELDS`.
4. A guard that passed for the incumbent reader is not known to hold for a new
   one. The truncation guard's observable (`content: null`) was a property of
   `gpt-oss-120b`, not of truncation; on Gemma the same failure returns a
   plausible fragment. **Re-measure each guard against the new model rather
   than inheriting it.**
5. `reasoning_effort` defaults to `"low"` in `P1Client.chat`. A reader that
   does not support it must pass `None` explicitly, or every row and cache key
   records a parameter that demonstrably does not describe the request.

---

## How the reader-only replication stays reader-only

R1–R3 reuse the **exact** memory artifacts gpt-oss read. That is asserted by
`scripts/gemma_reader_smoke.py` at run time, not claimed in prose — the run
ABORTS on any disagreement:

| Gate | What it compares | Result on 2026-09-30 |
|---|---|---|
| 1 | `memories.jsonl` sha256 vs the fingerprint the gpt-oss run recorded | `b342151c7f3cac5a` **MATCH** |
| 2 | system prompt sha256 vs the same fingerprint | `cdc9c36ad4266f53` **MATCH** |
| 3 | rebuilt filler pool sha256 vs the screened run's recorded value | `f6d88934516499fa` **MATCH** |
| 4 | **every rendered request's `context_sha256` vs the hash the gpt-oss cache stored for the same cell** | **16 matched, 0 mismatched**, 8 unverifiable |

Gate 4 is the decisive one: it compares the bytes actually sent, which no
amount of "we used the same script" establishes. Run over the whole corpus it
matches **2,248 / 2,248** gpt-oss cache keys with **zero** mismatches.

**Gate 4 is proven able to fail.** Planting a one-character change in
`cells.py::render_memory` (`--- Note 1 ---` → `--- Note 1 ----`) turned
16 matches into 16 mismatches and aborted the run. A gate that has only ever
passed is not known to discriminate.

**The 8 "unverifiable" are a real limitation, stated rather than glossed.** The
raw/screened cache was written under the **v1** cache key shape, which had no
`context_sha256` field at all. For `raw`, byte-identity therefore rests on
gates 1–3 (memory text, prompt, filler pool) and not on a stored request hash.
This is reported in the artifact as `unverifiable_v1_key`, never counted as
agreement — an absent check must not read as a passing one.

### What the smoke test is, and what may not be said about it

`results/gemma_reader/smoke_cells.jsonl` — **12 rows**, 2 cells ×
3 representations × 2 replicates, 24 real calls. Every row carries
`provenance.SMOKE_TEST_NOT_A_RESULT = true`.

🔴 **No ΔU, no `utility_label`, and no reader comparison may be quoted from
it.** `n` is far below the pre-registration's requirements, there is no
measured noise floor for this arm, and all 12 rows are correctly labelled
`undetermined`. It proves the plumbing, nothing else.

Eligibility was fixed **before any Gemma output existed** and is
**non-outcome-based**: stratum ∈ {BEARING, MATCHED_CONTROL}; the write
succeeded; a gpt-oss cached request exists for the cell (its **existence**
only, never its content); then sorted by `(memory_unit_locator, task_id)` and
the first *n* taken. Selecting cells where gpt-oss did well — or badly — would
be exactly the outcome filtering the house rules forbid.

### Cache separation across readers — proven behaviourally

`scripts/gemma_cache_separation_proof.py` →
`results/gemma_reader/cache_separation_proof.json`, **11/11 checks pass**
against the live endpoints:

```text
1. gpt-oss, cold                      MISS
2. gpt-oss again  [POSITIVE CONTROL]  HIT    <-- without this, step 3 is vacuous
3. gemma, SAME key fields             MISS   <-- the separation
4. gemma again                        HIT    (serves GEMMA's text)

2 rows, 2 distinct key_hash, 2 distinct model_id, DIFFERENT response text
```

The positive control is the point: a cache that never hit at all would also
show a "miss" at step 3 and look correct. And the proof is **not vacuous** —
removing `model_id` from `KEY_FIELDS` reproduces the crossing (a Gemma lookup
then HITs and is served `GPT-OSS ANSWER`), and restoring it restores the miss.

> Reading the artifact: `row["key"]` is the key **dict**, `row["key_hash"]` is
> the digest. Three agents have now mis-read this same four-field record.

## Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9 and breaks pytest

$PY scripts/gemma_cache_separation_proof.py          # 11/11, live endpoints
$PY scripts/gemma_reader_smoke.py --dry-run          # gates only, no calls
$PY scripts/gemma_reader_smoke.py                    # 24 calls, 12 rows
$PY -m pytest tests/test_reader_arms.py -q           # 19 passed
$PY -c "import sys;sys.path.insert(0,'src');from p1mem import validate as V;\
r=V.validate_file('results/gemma_reader/smoke_cells.jsonl');\
print(sum(i.severity=='error' for i in r.issues),'errors')"   # 0 errors
```

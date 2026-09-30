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

🔴 **Not yet executed. No result may be claimed for these until they run.**

| Arm | Writer | Reader | Cluster | Status |
|---|---|---|---|---|
| **R1** | deterministic Raw | `gemma-4-31B-it` | TBD — must be verified by `list-endpoints` + a real POST | **PROBING** (SA-GEMMA) |
| **R2** | `gpt-oss-120b` Summary | `gemma-4-31B-it` | as above | **PROBING** |
| **R3** | `gpt-oss-120b` Structured | `gemma-4-31B-it` | as above | **PROBING** |

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

## Planned arms — Writer × Reader factorial

🔴 **Not yet executed.** Gemma-written memories are an **additional** writer
arm; they never replace or overwrite the gpt-oss-written memories.

| | Reader gpt-oss | Reader Gemma |
|---|---|---|
| **Writer gpt-oss** (Summary, Structured) | A2/A3 — **DONE** | R2/R3 — planned |
| **Writer Gemma** (Summary, Structured) | W1/W2 — planned | W3/W4 — planned |
| **Writer deterministic** (Raw) | A1 — **DONE** | R1 — planned |

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

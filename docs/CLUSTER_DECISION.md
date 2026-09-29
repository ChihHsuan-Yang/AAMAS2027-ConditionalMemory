# Primary Model + Cluster Freeze (P1-032)

**Decided 2026-09-29 by the Master Agent on Sub-agent C's measurements.**
Once frozen, this does not change. A different cluster or model is a **new experimental
arm**, never a backfill.

---

## Decision

| Role | Choice |
|---|---|
| **Primary reader (generation)** | **`gpt-oss-120b` on Metis** — `/resource_server/metis/api/v1` |
| **Primary memory writer** | **same** — `gpt-oss-120b` on Metis |
| **Embeddings** | **`Salesforce/SFR-Embedding-Mistral` on Sophia** (dim 4096) |
| **Designated failover arm** | `openai/gpt-oss-120b` on **Sophia** — **a separate arm, never pooled** |
| `reasoning_effort` | **`low`**, pinned |
| `max_tokens` | **≥512** for a ~256-token answer, pinned |

## Why not Minerva, despite the stated preference

The user prefers Minerva. **It cannot host the scientifically right model**, and the
evidence is direct.

`GET /resource_server/minerva/models` advertises three models. A real POST to each:

| Requested | HTTP | Verdict |
|---|---|---|
| `gpt-oss-120b` | **503** | **DOES NOT SERVE** — `"'gpt-oss-120b' is not currently live on Minerva."` |
| `inkling-bf16` | 200 | serves |
| `nemotron-3-ultra` | 200 | serves |

Retried 4× over ~2 minutes: 503 every time, identical body, sub-second failure. **Persistent,
not transient** — the gateway rejects at the router before reaching a model.

> This is the **second** instance today of advertised-but-dead (the first:
> `google/embeddinggemma-300m`, 502 on Sophia). **A capability listing is not a liveness
> signal.** Every model we depend on must be proven with a real POST.

So "Minerva as primary" could only mean **a different model family**, not the same model
on different hardware. That trades a cross-cluster comparability advantage — we have none,
since we run one cluster — for an unfamiliar model with no track record in this project.

`tara` advertises `"frameworks": {}` — listed but unusable.

## Why Metis over Sophia for the same model

Both serve `gpt-oss-120b` and both resolved the requested id **identically** (no silent
substitution anywhere).

| | Metis | Sophia |
|---|---|---|
| 4k-token request | **0.728 s** | 3.387 s |
| 16k-token request | **1.082 s** | 2.500 s |
| 16.8k needle retrieval | **1.23 s** | 1.96 s |
| 31.5k needle retrieval | **1.56 s** | 3.60 s |
| Needle accuracy | 2/2 | 2/2 |
| `reasoning_tokens` reported | **yes** | **no** (`completion_tokens_details` absent) |
| `system_fingerprint` | `fastcoe` | `null` |

Metis is **1.6–2.3× faster** at our request shapes, and — the deciding factor — **it
reports reasoning-token counts while Sophia does not.** Reasoning tokens are drawn from
the same budget as the answer, so on Sophia we could not *verify* that `reasoning_effort`
was honoured, only assume it. For a study whose headline is a cost–utility frontier,
**unmeasurable token accounting on the primary arm is disqualifying.**

Sophia is retained as the designated failover, as a **separate arm**. The name is the same
but the serving stack is not (`fastcoe` vs null fingerprint), and per the standing policy
these are never pooled.

Embeddings stay on Sophia. That is an accepted exception: embedding is a distinct,
independently controlled component, and Sophia is the only cluster serving embeddings.

## Two binding call-level constraints — from an instrument defect C found and reported

C's first long-context test reported failure for **all four** models, including two already
known to work. **A result identical across known-good and unknown subjects is a property
of the instrument, not the subjects** — and that uniformity is what exposed it.

Cause: these are reasoning models, and **reasoning tokens come out of the same `max_tokens`
budget as the answer.** At `max_tokens=64` the model spent all 64 on reasoning and returned
`content: null` with `finish_reason: "length"`. The needle *had* been found, inside
`reasoning`. Checking only `content` scored a correct retrieval as a failure.

That is the "an error value becomes a real number" shape: a truncation scored as a wrong
answer. In a ΔU study it would be far worse than a lost cell — **it would silently push ΔU
negative and manufacture harmful memories.**

Therefore, binding on every run:

1. **`max_tokens` must cover reasoning + answer.** ≥512 for a ~256-token answer, or
   `reasoning_effort` pinned low/none.
2. 🔴 **`finish_reason == "length"` with empty `content` is a hard ERROR**, never a scored
   response. Enforced in `src/p1mem/client.py`; any occurrence is logged with
   `error_code_if_any` and the cell is re-run, not scored.

With the corrected harness, long-context retrieval was **12/12 correct** across all four
candidate models at 16.8k and 31.5k server-counted input tokens. Both surviving Minerva
models exceed our 8–32k requirement comfortably (advertised 1,048,576).

## Pinned identity — every row records all of it

```text
reader_cluster    = metis
reader_endpoint   = https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
reader_model      = gpt-oss-120b        # resolved id verified identical to requested
reasoning_effort  = low
temperature       = 0
max_tokens        = 512
```

⚠️ Metis wants the **bare** `gpt-oss-120b`; Sophia wants `openai/gpt-oss-120b`. The client
must not "helpfully" normalize across clusters — a silent rename would merge two arms.

## Revisit condition

Only if Metis becomes unavailable for a sustained period. Then we move to the Sophia arm
**and label it as a separate arm**, re-running affected cells rather than merging.

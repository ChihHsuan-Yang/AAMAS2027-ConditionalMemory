# Memory Acquisition Protocol (P1-002 … P1-006)

**Frozen 2026-09-29.** Binding on every representation, benchmark, and run.

---

## 0. The invariant everything rests on

> ### The memory writer never observes the future evaluation task.
>
> Memory formation is a function of the past episode alone.

Formally, for a past episode `e` and writer `W` with prompt version `v`:

```text
m = W_v(e)        -- and NOT  W_v(e, t)
```

**Why this is not negotiable.** If the writer sees `t`, then `ΔU(m,t) > 0` shows only that
an LLM can be told the answer and copy it forward. Every conditional claim collapses. This
is the single assumption a reviewer will attack first.

### How it is enforced, not just asserted

1. **Structural:** writing runs as a separate pass over episodes, before any memory×task
   pairing exists. The writer function's signature takes an episode and no task argument.
2. **Ordering:** all memories for a benchmark are written and frozen (content-hashed)
   before the pairing step runs.
3. **Audited:** the leakage detector (P1-022) runs over every (memory, task) cell and
   reports the rate at which a memory contains the gold answer. **Leaky cells are flagged,
   never silently dropped** — dropping them changes the question being answered.
4. **Reported:** the manuscript states the guarantee, the enforcement, and the measured
   residual leak rate.

⚠️ **Residual leakage is expected and is not a bug.** A naturally occurring memory may
contain the answer by coincidence — that *is* a real memory being genuinely useful. What
must be excluded is *task-directed* writing. The audit separates the two.

## 1. The three representations (P1-003 … P1-005)

All three derive from the **same source episode**, so any downstream difference is
attributable to representation and not to content selection.

| | A. Raw / Extractive | B. Abstractive Summary | C. Structured Experience |
|---|---|---|---|
| Content | faithful verbatim span | model-written prose | model-written schema |
| Writer | **none — deterministic** | fixed LLM, pinned | fixed LLM, pinned |
| Faithfulness | highest by construction | must be measured | must be measured |
| Tokens | largest | small | small |
| Extraction cost | ~0 calls | 1 call | 1 call |

### A. Raw / Extractive — deterministic, no model

A contiguous, naturally occurring span of the source episode.

- Selection is **deterministic and documented**, and uses **no future task**.
- Rule: segment the episode at its own structural boundaries (session, step, page, turn —
  whichever the benchmark provides), then take the whole segment as one memory candidate.
- **No "pick the most informative span"** — that smuggles in a value judgment which is
  precisely what we are trying to measure.
- Records `memory_source_span` so the span is re-derivable.

### B. Abstractive Summary — fixed writer

One call per episode segment. Prompt version pinned, temperature pinned, model+cluster
pinned. Measures compression ratio, extraction cost, faithfulness, downstream utility.

### C. Structured Experience — fixed writer, fixed schema

General schema:

```text
memory_type · situation/trigger · action · outcome · lesson · scope
source_episode · confidence/provenance (where meaningful)
```

Procedural / scientific variant (expected to matter most for SciCode):

```text
trigger · procedure · failure_mode · successful_correction · scope
```

Emitted as JSON and validated; a malformed structure is a recorded failure, not a silent
fallback to prose.

## 2. Representation ≠ semantic type (P1-006)

These are **orthogonal axes** and conflating them would make the analysis meaningless.

| Semantic type | What it is |
|---|---|
| `episodic` | a specific past event |
| `semantic_fact` | a durable fact about the world or user |
| `procedural` | how to do something |
| `failure_reflection` | what went wrong and the correction |

**The same procedural experience can be stored raw, summarized, or structured.** The
dataset carries `memory_representation` and `memory_semantic_type` as separate fields.

Labelling: assigned by the writer as part of representation C, and by a separate
classification pass for A and B (which have no natural slot for it). **The label is
derived from the episode only — never from the future task.** Report inter-pass agreement
so a reader can judge label quality.

## 3. Writer control (P1-010 in the handoff's numbering)

One fixed writer configuration per experiment family. Recorded on **every** row:
writer model · cluster · endpoint · prompt version · temperature/decoding · timestamp ·
token usage · latency.

> **If the writer model changes, it is a different experimental condition** — a new arm,
> never a backfill of an existing one. The same rule as for readers: cluster and serving
> configuration are part of experimental identity.

## 4. What the reader sees

Both arms are identical except for the presence of `m`:

| | WITHOUT arm | WITH arm |
|---|---|---|
| Reader model / cluster / endpoint | same | same |
| Decoding + seed | same | same |
| Prompt scaffold | same | same |
| Context budget | same | same |
| Scoring function + version | same | same |
| Target memory `m` | absent | present |
| Surrounding context | **identical controlled filler** | **identical controlled filler** |

🔴 **The filler requirement is load-bearing, and was discovered empirically.** Measured on
LongMemEval V1: the oracle context is **100% evidence**, so ablating "the memory" there
removes the entire context. That is a *no-context* arm, not a memory ablation, and its ΔU
answers a different question. **Every cell must place the target memory inside a
controlled, fixed set of other content**, so removal is a local change.

## 5. Cost accounting at write time

Writing is not free and its cost belongs to the representation being compared:
extraction calls, input/output tokens, latency, retries. Raw costs ~0; summary and
structured each cost one call per segment. **The efficiency frontier must charge each
representation for its own formation cost**, or it flatters the model-written ones.

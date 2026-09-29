# Embedding Truncation — a hard constraint on the semantic-distance analysis

**Found by Sub-agent G while wiring `semantic_similarity`; independently re-verified by the
Master Agent 2026-09-29.**

---

## The limit

`Salesforce/SFR-Embedding-Mistral` on Sophia fails above ~4.1k tokens. Measured directly:

| input | result |
|---|---|
| 3,003 tokens | ✅ OK, dim 4096 |
| **4,003 tokens** | ✅ **OK**, dim 4096 |
| ~5,000 tokens | 🔴 HTTP 500, `internal_endpoint_error` with a server traceback |
| ~8,000 tokens | 🔴 HTTP 500 |

G bisected it to 3,466 OK / 4,249 FAIL. Our working cap is **3,400 tokens**.

Note the failure mode: a **server-side traceback**, not a clean `400 input too long`. A
harness that retried on 5xx would spin here, and one that swallowed the error would record
a missing embedding as an absent value rather than a refusal.

## Why this is a paper-level limitation, not a plumbing detail

Our memory unit is the page visit, **median 7,261 tokens**.

> 🔴 **1,769 of 1,889 units — 93.6% — exceed the embedding cap.**

So for the overwhelming majority of memories, `cos(embed(m), embed(t))` is computed on a
**truncated prefix** of the memory, not the memory that was actually shown to the reader.

This directly touches `ANALYSIS_PREREGISTRATION.md` §7 (NEAR/MID/FAR bands) and §8
(similarity-vs-utility). Both are built on a similarity that, for 93.6% of units, describes
only the first ~3,400 tokens.

## What this does and does not invalidate

**Does not invalidate ΔU.** Utility is measured by execution with the **full** memory in
context. The truncation touches only the *embedding*, never the intervention. The paper's
primary object is unaffected.

**Does weaken the distance analysis**, and the direction is predictable: truncation adds
noise to the similarity estimate, which **attenuates** any similarity–utility relationship
toward zero. So a *weak* observed correlation is partly explainable by measurement error in
the predictor — and since "similarity predicts utility poorly" is a claim adjacent to ours,
**this caveat cuts against our own convenience and must be stated, not buried.**

## How it is handled

1. **Truncation is recorded per row** — `memory_embedding_reference.input_truncated`, with
   the token count used. It is never silently applied.
2. **Report the analysis split by truncation status.** The 120 units (6.4%) that fit whole
   are an unbiased subgroup for similarity-vs-utility; they are small, and the paper says
   so rather than pooling.
3. **State the attenuation direction explicitly** in Limitations.
4. **Do not switch embedding models mid-study.** `embeddinggemma-300m` (502s) and
   `Mistral-7B-v0.3-embed` are alternatives, but one fixed embedding model across the main
   study is a standing constraint. Any change is a new arm.

## Candidate mitigation — NOT adopted without measurement

Chunk-and-pool (embed ≤3,400-token windows, mean-pool, L2-normalize) would cover the whole
unit. **It changes what the vector means**, so it cannot be mixed with whole-text
embeddings in one analysis.

If adopted, it must be validated on the 120 units that fit whole: embed each both ways and
report the cosine between them. If chunk-pooled and whole embeddings disagree substantially
there, the pooled vector is a different quantity and the bands are not comparable across
methods.

**Until that validation exists, truncation-with-disclosure is the honest option.**

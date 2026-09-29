# Embedding Truncation — a hard constraint on the semantic-distance analysis

**Found by Sub-agent G while wiring `semantic_similarity`; independently re-verified by the
Master Agent 2026-09-29.**

---

## The limit — and why my first number was wrong

> 🔴 **CORRECTED 2026-09-29.** This section first stated a working cap of **3,400 Qwen
> tokens**, bisected on synthetic prose. **That cap fails 10 out of 10 real memory units.**
> Sub-agent G flagged it; I re-measured on real text and its correction was, if anything,
> understated.

### There is no single numeric cap, because we cannot count the right tokens

The budget is enforced in **Qwen** tokens (`memory/tokens.py` = `Qwen/Qwen3.5-9B`), but the
server tokenizes with **SFR-Embedding-Mistral**. A Qwen count is only a proxy, and on dense
AXTree text it **under-predicts** the Mistral count enough to cross the limit.

Text density, measured:

| text | chars / Qwen token |
|---|---|
| my synthetic probe (`"word "×3000`) | **5.00** |
| real memory units | **2.58 – 3.18** |

My probe text was ~2× less dense than the data, so every token budget bisected on it was
roughly 2× too generous when applied to real memories. **Bisecting on unrepresentative
text produced a number that did not transfer.**

### Measured on REAL memory units (10 units, each >4,000 Qwen tokens, truncated then sent)

| Qwen-token budget | failures |
|---|---|
| **3,400** (my original doc) | 🔴 **10 / 10 FAILED** |
| 2,400 | ✅ 0 / 10 |
| **2,000** (adopted) | ✅ 0 / 10 |

### For reference, the synthetic-prose numbers that misled me

3,003 OK · 4,003 OK · ~5,000 HTTP 500 · ~8,000 HTTP 500; G bisected 3,466 OK / 4,249 FAIL.
**All on prose. Do not reuse these.**

### The operating rule

The real ceiling is roughly **4k Mistral tokens**, which **we cannot count locally**. We
therefore enforce a conservative **2,000-Qwen-token** budget with **halving retry on 500**
(2,000 → 1,000 → 500), and record the budget actually used per row in
`memory_embedding_reference.input_token_budget` — so a row states what was really embedded
rather than implying a uniform cap.

Note the failure mode: a **server-side traceback**, not a clean `400 input too long`. A
harness that retried blindly on 5xx would spin; one that swallowed it would record a
refusal as an absent value.

Note the failure mode: a **server-side traceback**, not a clean `400 input too long`. A
harness that retried on 5xx would spin here, and one that swallowed the error would record
a missing embedding as an absent value rather than a refusal.

## Why this is a paper-level limitation, not a plumbing detail

Our memory unit is the page visit, **median 7,261 tokens**.

Re-derived by the Master Agent at each candidate budget:

| Qwen-token budget | units that fit whole | truncated |
|---|---:|---:|
| 3,400 (**withdrawn** — fails 10/10 on real text) | 120 / 1,889 = 6.4% | 93.6% |
| 2,400 | 62 / 1,889 = 3.3% | 96.7% |
| **2,000 (adopted)** | **29 / 1,889 = 1.5%** | **98.5%** |

> 🔴 **At the adopted budget, 98.5% of memory units are embedded from a truncated prefix,
> and only 29 units fit whole.**

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
2. **Report the analysis split by truncation status** — but the whole-text subgroup is
   **29 units**, which is too small to carry a similarity-vs-utility claim on its own.
   ⚠️ **Do not quote the earlier "120 units (6.4%)"**: that was computed against the
   withdrawn 3,400 cap. Report 29 / 1.5%, and treat that subgroup as a sanity check on the
   direction of the effect, not as an independent estimate.
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

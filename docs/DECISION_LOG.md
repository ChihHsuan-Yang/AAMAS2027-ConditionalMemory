# Decision Log

Append-only. Each entry: what was decided, why, what evidence supports it, and what would
overturn it. **A decision with no falsifier is not a decision, it is a preference.**

---

## 2026-09-29 — D1: P1 is a measurement paper, not a gate paper

**Decision.** The primary object is the measurement of `DeltaU(m, t)` and its variance
decomposition. A learned gate is a late-stage, conditional follow-up.

**Why.** Three independent adversarial passes judged the gate framing anticipated. UMEM
(arXiv:2602.10652, verified 2026-09-29) already trains a cross-episode memory policy on
`R(t|mem) - R(t|no mem)`, refuses to score a memory on its source query, scores against
other queries, and runs a capacity ladder.

**Overturned by.** Evidence that the measurement is also published — under check as task 1.1
(EvoMemEval) and 1.2 (UMEM dispersion).

---

## 2026-09-29 — D2: `WebSearch` is dead in this environment; all nulls need positive controls

**Decision.** No absence claim enters any document without a positive control against a
known-existing artifact on the same channel.

**Why.** Re-confirmed by direct test: `WebSearch` returns HTTP 400
(`constraints/vertexai.allowedPartnerModelFeatures`), not empty results. This is the same
block that produced five confident false negatives in the 2026-09-28 audit. `WebFetch`
works (verified HTTP 200 against arXiv `abs`).

**Overturned by.** The org policy changing; re-test before trusting any search null.

---

## 2026-09-29 — D3: DATASETS.md V2 measurements are treated as UNSOURCED pending resolution

**Decision.** Every quantitative claim in the inherited `DATASETS.md` about LongMemEval-V2
— including "45,100 cells", "min = median = max = 240", and the "1.3% no-memory floor" —
is marked unverified until the underlying file is located or re-downloaded.

**Why.** `DATASETS.md` states these were measured "directly from `lme_v2_small.json`". The
Master Agent ran `find /Users/bellayang -iname "*lme_v2*"` and
`find ... -iname "*longmemeval*"`: **zero hits.** The file is not on this machine. Either
it was deleted, it was measured elsewhere, or the measurement did not happen.

This is exactly the failure mode recorded in the project's own operating memory: a number
quoted into a durable document without re-derivation.

**Overturned by.** Locating the file, or re-downloading V2 and reproducing the counts.
Sub-agent A owns this as task 1.4.

**Consequence if unresolved.** The dataset choice must be re-justified from files we can
actually open, not from an inherited table.

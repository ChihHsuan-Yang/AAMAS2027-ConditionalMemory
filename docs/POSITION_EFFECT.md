# The Position Effect — a confound found by accident, promoted to a measurement

**Discovered 2026-09-29** while investigating a claim that turned out to be wrong. The
mistake was mine; the finding underneath it is real.

---

## What happened

I reported that the ALCF endpoint is nondeterministic at temperature 0, on the basis of
4.3% disagreement across replicates. Sub-agent G challenged it. The endpoint **is**
deterministic **within a session** — G's probe in the target regime (23k–27k tokens,
cache disabled, concurrency 16) gives **6/6 prompts byte-identical across 4 repeats,
24 real calls**, all issued inside one run.

> 🔴 **Scope, added 2026-10-01.** "The endpoint is deterministic" is true of a
> session and false of a day: re-issuing byte-identical requests 24 h later returned
> different text in **554 of 1,124** cases on `gpt-oss-120b` (**0 of 1,124** on
> `gemma-4-31B-it`, so cross-session stability is a property of the MODEL, not the
> cluster). The retraction above stands — the 4.3% really was a position effect — but
> the replacement claim needs its session scope.
> See `docs/SESSION_DETERMINISM_AUDIT.md`.

My replicates were not byte-identical. `build_cell_pair` seeded the target memory's
**position** with `replicate_id`, so each replicate moved the memory within the context.

**My own data splits exactly along that line:**

| arm | prompts byte-identical? | text disagreement |
|---|---|---|
| WITHOUT | yes (no target to position) | **0 / 11** |
| WITH | no (position re-seeded per replicate) | **8 / 12** |

Zero disagreement wherever the prompt was genuinely fixed.

## The finding

> **8 of 12 cells changed their answer when the *only* thing that moved was the target
> memory's position in the context.**

Same memory. Same question. Same filler. Same model, cluster, decoding, seed. Byte-for-byte
identical content, reordered — and the answer changed two times in three.

## Why this matters to the paper, not just to our harness

A with/without memory comparison that does not control position is measuring **position
plus presence**. If a study inserts the memory at a fixed slot — prepended, appended, or
top-of-retrieval — it has confounded "the memory helped" with "content at that slot helps".

This bears directly on P1's own object. ΔU is a contrast between an arm that contains the
memory and an arm that does not. The WITH arm necessarily has one more item, so **something
must decide where it goes**, and that decision is not neutral.

It also bears on the measurement literature's fair-comparison problem more generally:
Memory-R2 argues trajectory-level comparisons are unfair once rollouts diverge in memory
state. This is a smaller, sharper version — comparisons are unfair once arms differ in
*layout*, even with identical content.

## How P1 handles it

1. **Position is held FIXED across replicates**, seeded by `(task_id, memory_id)` and
   **not** by `replicate_id`. A replicate must vary only the sampling draw, per
   `ANALYSIS_PREREGISTRATION.md` §2's "everything else fixed".
2. **Position still varies across cells**, so no single slot is privileged in aggregate and
   position does not correlate with memory identity.
3. **Position is recorded on every row**, so its effect is estimable after the fact.
4. **It becomes its own reported measurement**: hold everything fixed, vary only position,
   report the answer-change rate with its denominator.

## Status

**Provisional: 8/12 is a 12-cell denominator**, from cells built for a different purpose,
in the uninformative regime described in `RESULTS_LEDGER.md` row 44. It is enough to
justify controlling position; it is **not** yet a publishable rate. A dedicated run at
scale is queued.

## The general lesson

The disagreement I measured was real. My *interpretation* of what varied between the
compared conditions was wrong — I believed I was holding the input fixed, and I was not.

> Before attributing variation to the system under test, verify that the inputs you
> believe are identical **actually are** — byte-for-byte, not by construction-in-principle.

The tell was available in my own data the whole time: the split by arm. A quantity that is
exactly zero in one condition and large in another is rarely "noise".

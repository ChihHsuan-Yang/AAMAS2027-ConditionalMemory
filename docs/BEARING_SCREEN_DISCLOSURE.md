# The bearing screen is gold-conditioned — a measurement instrument, not a retriever

**Opened 2026-10-01 by the Master Agent, after a blind mock review returned
weak reject with this as its deciding objection.** The reviewer could not tell
what the screen sees, suspected an oracle, and was right.

## What the code actually does

`scripts/k1_build_screened_design.py`, lines 11–15, verbatim:

> This screens candidate cells with J's DISCRIMINATIVE detector: the detector
> must single THIS memory out of the same-domain pool (fire on at most
> `--max-pool-hits` of the ~865 web / ~1024 enterprise units). **Content-only
> — memory text and gold answer** — so no reward enters and the strata are NOT
> outcome-selected. No endpoint call is made.

**The detector reads the gold answer.** "Content-only" was never a claim of
gold-freeness; it meant *no model output and no reward enter the screen*, which
is a narrower guarantee than a reader takes from the phrase.

### Inputs, field by field

| input | seen by the screen? |
|---|---|
| memory text | ✅ |
| **gold answer** | ✅ **— this is the privileged input** |
| the same-domain memory pool (~865 web / ~1024 enterprise) | ✅ (the discrimination requirement) |
| question / task text | ✅ |
| reader output under either arm | ❌ |
| reward, ΔU, any outcome | ❌ |
| an endpoint call | ❌ — the screen is offline |

So the strata are **not outcome-selected** — that defence stands and is
genuinely important. But they **are** selected on answer-containment.

## What this does and does not invalidate

🔴 **Not deployable.** No retrieval system can ask "does this memory contain
the gold answer." Any sentence offering the screen as *retrieval guidance* is
unsupportable and must be withdrawn or rewritten. The reviewer identified the
specific sentence: the Discussion's "on retrieval, the criterion that located
the effect asks what a memory contains, not what it resembles."

🔴 **The headline bearing−control effect is a conditional claim.** The defensible
statement is: *among cells where the memory demonstrably carries what the task
needs, the memory is worth +0.3349 to the reader.* It is not "memories help."

✅ **The measured effect is not trivial, and this is checkable.** If the screen
merely re-supplied an answer the reader already had, the WITH arm would be
near-ceiling. Measured on the 417 BEARING rows:

| | correct |
|---|---|
| WITHOUT arm | **48/417 = 11.5%** |
| WITH arm | **192/417 = 46.0%** |

**54% of bearing cells still fail with the memory present.** Answer-containment
is necessary for the benefit here but plainly not sufficient — a reader given a
passage containing the answer gets it right fewer than half the time. That is a
fact about reading, and it is the part of the result that survives.

✅ **The representation comparison is untouched by this.** Raw vs Summary vs
Structured is measured *within* the bearing stratum, so however the stratum was
chosen, the contrast between representations on the same cells is unaffected.
The reviewer said so independently, and it is the result to build on.

✅ **The matched control still does real work** — it rules out "this memory is
an easy one." It does **not** rule out selection on memory–task match, because
by construction the control cells are the non-matching ones. The paper's
current defence rebuts the weaker objection.

## Required changes

1. **State the inputs in the paper**, in a table, where the screen is first used.
2. **Say plainly: this is a measurement instrument, not a deployable retrieval
   policy.** Its purpose is to expose the quantity a future retriever or gate
   would need to approximate.
3. **Withdraw or rewrite the retrieval-guidance sentence** in the Discussion.
4. **Report 11.5% → 46.0%** beside the effect, since it is what distinguishes
   this from "a passage containing the answer helps."
5. Keep the conditional framing in the abstract: *among cells where the memory
   bears on the task*.

## The one experiment that would settle it

A **gold-free variant** of the screen — memory + question + pool, no gold, no
scorer — reporting its overlap with the current bearing set and the
bearing−control effect it produces. Under the scope freeze this qualifies as
closing a **validity-critical gap**, not as new science: it validates an
existing claim rather than opening a branch.


---

# ✅ RESOLVED 2026-10-01 — the oracle objection does not hold

`docs/GOLD_FREE_SCREEN_RESULT.md` · artifacts `results/ledgers/gf_*.json` ·
design pre-committed in `GOLD_FREE_SCREEN_PRECOMMITMENT.md` **before** execution.

Two gold-free screens were built, both reading **memory + question + pool** and
neither reading gold, reward, model output or eval spec. They disagreed, and
the disagreement is itself informative.

| screen | deciding contrast (fires, gold did NOT) | n | verdict |
|---|---|---:|---|
| gold (re-derived) | +0.3179 [+0.174, +0.477] | 139 | — |
| **GF-LEX** lexical | +0.0002 [−0.0713, +0.0758] | 160 | DISAPPEARS |
| **GF-LLM** judge | **+0.3676 [+0.0475, +0.6981]** | 32 | **SURVIVES** |

## The decisive measurement, reproduced independently by the Master Agent

On GF-LLM cells **gold never selected**:

| | WITHOUT | WITH |
|---|---|---|
| bearing, gold-free only (n=64) | **15.6%** | **50.0%** |
| matched control (n=84) | 14.3% | 11.9% |

**A screen that never sees the gold answer finds memories that triple the
reader's success rate on tasks the gold screen did not select.** Answer
containment is therefore *not* what makes a bearing memory useful.

## Why the two screens disagree — settled without reference to the effect

GF-LEX is **unfit**, and the evidence is independent of any ΔU:

- its bearing cells fail in **both arms 244/328 = 0.744**, *worse than
  unscreened RANDOM pairing at 0.701* — a screen whose selections are harder
  than a random draw has not located bearing;
- **95% of its firings rest on one generic anchor** (`five`, `typically`,
  `whenever`).

GF-LLM's bearing cells fail in both arms at **0.310**. Its null is a fact about
that detector, not about memory — and the null is real, not underpowered: the
interval half-width 0.0735 is 4.3× too small to hide the gold effect, and the
4 gold-bearing cells *inside the same run* score ΔU = +1.0.

## What the manuscript may now claim, and what must travel with it

**May:** a gold-free screen reproduces the effect at full size on cells the
gold screen never selected, so the headline is not an artifact of
answer-containment.

**Must travel with it:** n=32 cells / 24 memories / 19 episodes; GF-LLM's
recall stage inherits GF-LEX's weak anchors (it saw 14 of 266 gold cells and
accepted 10); cross-screen comparisons are **cross-session**, so they agree in
sign and significance, not magnitude.

**Report both screens.** Reporting only the one that worked would be selecting
an instrument on its outcome — the exact failure this project screens for.

⚠️ The gold screen remains **a measurement instrument, not a deployable
retrieval policy**; that disclosure stands unchanged. What has changed is that
the *finding* no longer depends on it.

# Gold-free bearing screen — PRE-COMMITMENT

**Written 2026-10-01 by SA-GOLDFREE, BEFORE the screen was run and BEFORE any
gold answer, reward, model output, or the existing BEARING set was consulted
for this purpose.** It closes the one experiment named in
`docs/BEARING_SCREEN_DISCLOSURE.md` §"The one experiment that would settle it".

The question: the current bearing screen reads the **gold answer**
(`LK.detect(memory_text, t.answer, eval_function_spec=...)`). Is the headline
bearing−control effect a *memory-utility* finding, or is it *"a passage
containing the answer helps a model answer"*?

---

## 1. What this document fixes, and what was looked at first

**Frozen here, before running:** the detector, its parameters, the candidate
universe, the analysis, the controls, and the three verdict criteria.

**Disclosed, because it preceded the freeze:** parameters were sized against
**structural yield only** — question text, memory text, and same-domain pool
document frequencies. A sweep over `D ∈ {4,8,16,32,64,128}` × `cover ∈ {1.0,
0.8, 0.6}` was run and its bearing-edge counts were seen. **No gold answer, no
reward, no model output, and no comparison against the existing BEARING set
entered that sizing**, and the chosen setting is **not** the yield-maximising
one (`D=8`/`cover=1.0` yields 218 edges; `D=8`/`cover=0.6` yields 253 and was
rejected). The chosen setting is the one whose constants are **inherited from
the gold screen** rather than selected.

---

## 2. GF-LEX — the primary gold-free detector

Deterministic, pure-Python, no network, no model. It is the **matched
counterfactual** to the gold screen: the gold screen is itself a lexical
containment test, so swapping *which string it looks for* — and nothing else —
isolates the gold answer as the privileged input.

**Normalization.** `p1mem.adapters.leakage.normalize_text` — the *same*
function the gold screen uses. Inherited, not chosen.

**Anchor terms `A(t)`** for deterministic task `t`: the distinct normalized
unigrams of the **question text**, minus

- **question-side boilerplate** — terms occurring in ≥ 50% of the same-domain
  deterministic questions (measured: 22 enterprise, 23 web terms; `am`,
  `boxed`, `servicenow`, `magento`, …). Without it, `am` is an anchor;
- terms whose **same-domain memory-pool document frequency** `df` lies outside
  `[1, 8]`.
  - **Upper bound 8 is the gold screen's own `--max-pool-hits`**, inherited
    rather than tuned.
  - **Lower bound 1** mirrors the gold screen's `1 <= pool_hits`: a term absent
    from the pool can never be matched.

**Fire rule.** The detector fires on `(m, t)` iff `A(t)` is non-empty **and
every** term in `A(t)` occurs in `normalize_text(memory_text(m))`. Requiring
*all* anchors is the analogue of the gold screen's
`normalized_leak(..., require_all_phrases=True)`.

**Discriminativeness — the same constraint, the same shape, the same
threshold.** Task `t` is DISCRIMINATIVE iff the detector fires on
`1 ≤ k ≤ 8` of the **same-domain pool** (865 web / 1,024 enterprise units).
Identical to the gold screen's rule and computed over the identical pools.

**GF-BEARING(m, t)** iff the detector fires on `(m,t)` **and** `t` is
discriminative. Identical in form to the gold screen's BEARING rule.

### Inputs, field by field — the table the disclosure doc demands

| input | GOLD screen | GF-LEX |
|---|---|---|
| memory text | ✅ | ✅ |
| **gold answer** | ✅ **privileged** | ❌ |
| eval-function spec | ✅ | ❌ |
| question text | ❌ | ✅ |
| same-domain memory pool | ✅ | ✅ |
| reward / ΔU / any outcome | ❌ | ❌ |
| reader output | ❌ | ❌ |
| an endpoint call | ❌ | ❌ |

### Why a lexical rule is the right primary choice

An LLM screen introduces a **second** difference — instrument class — beside
the one under test. If the overlap came out low, a low overlap from "gold-free
is different" would be indistinguishable from one caused by "an LLM judge is
different". GF-LEX changes exactly one thing.

## 3. GF-LLM — the secondary, confirmatory detector

A lexical rule can only see surface form. GF-LLM tests whether the verdict
depends on that.

- **Recall stage (exhaustive over the pool, cheap):** anchors at the same
  `df ∈ [1,8]` band, but requiring only `⌈|A(t)|/3⌉` of them present.
- **Content-blind size cap:** memories over **20,000 tokens** never fire. This
  is the design's own `--target-token-cap`, reused. It is an asymmetry versus
  the gold screen (whose detector has no cap) and is **part of the detector's
  definition**, so the composite's full-pool firing set stays exactly
  computable.
- **Precision stage:** one call per surviving candidate asking whether the
  memory contains what the question needs. **Gold is never in the prompt.**
  - model/cluster `metis/gpt-oss-120b`, `temperature=0`, `reasoning_effort=low`,
    prompt version `gf_bearing_judge_v1`, recorded in the artifact.
  - Writer-blindness does not apply (this is a screen, not a writer); temperature
    0, a fixed prompt version and a recorded model/cluster do.
- **Composite fire rule:** recall ∧ under-cap ∧ LLM-yes. Because the recall
  stage is exhaustive over the pool and the LLM stage can only *shrink* its
  output, the composite's full-pool firing set is **exact**, so the
  `1 ≤ k ≤ 8` discriminativeness constraint is enforced in the same shape and
  is not an approximation.

A **full-pool** LLM screen with no recall stage would be **277,594 calls** and
is refused as infeasible, not quietly approximated.

## 4. Candidate universe — identical to the gold screen's

All `(m, t)` with `m` one of the **1,889** memory units and `t` one of the
**295** deterministically-scored tasks **in the same domain**: **277,594**
cells. This is the universe `data/manifests/lmev2_leakage_small.jsonl` was
built over and the universe `k1_build_screened_design.py` screened.

## 5. Analysis, fixed in advance

1. **Overlap.** The full 2×2 confusion matrix of GOLD-BEARING × GF-BEARING over
   all 277,594 cells, plus `|GF ∧ GOLD| / |GOLD|` and `/ |GF|`, and the same at
   the task and memory level.
2. **The gold-free bearing−control effect.** On the **1,157 executed** design
   cells (`results/deltau_screened/cells.jsonl`, 2,599 rows), relabel every cell
   by GF and contrast **GF-BEARING** against a **GF-MATCHED-CONTROL** built by
   the original rule — *same memory, same `question_type` family, detector
   silent* — with a **task-clustered bootstrap CI** and a within-memory paired
   contrast where pairing exists. Report `n` executed and `n` needing new runs.
3. 🔴 **The circularity guard, fixed now because it is the whole experiment.**
   The executed cells were *chosen by the gold screen*, so GF-BEARING ∩ executed
   is enriched for gold-BEARING. A contrast dominated by cells that are *also*
   gold-BEARING re-measures the gold screen. **The deciding quantity is
   therefore the effect on `GF-BEARING ∧ ¬GOLD-BEARING` cells**, reported
   separately with its own `n` and CI, and it governs the verdict. If that `n`
   is too small to estimate, that is reported as such and **not** replaced by
   the pooled figure.
4. New reader runs, if needed and affordable, are **session-matched**: both arms
   of every new cell in one session (defect #25 — `gpt-oss-120b` is
   deterministic within a session and not across).
5. `reward is None` means *could not be scored*; it is **never** coerced to 0.0.

## 6. Controls, fixed in advance

- **C1 — the detector can fire and can stay silent.** Plant a question's exact
  anchors into a memory asserted clean of them and require a FIRE; require
  SILENCE on the unplanted memory. A screen never shown to fire cannot evidence
  absence.
- **C2 — plant the defect.** Break anchor extraction (return `[]`) and require
  the yield to collapse to zero; break the discriminativeness bound and require
  it to inflate. A guard verified only on its home case is not known to
  discriminate.
- **C3 — the join is real.** Measured: joining the design manifest to the
  executed rows on **`memory_id`** returns **0 of 60** (it is a per-representation
  content hash on one side and `mem-<traj>-<hash>` on the other); on
  **`memory_unit_locator`** it returns **60 of 60**. Both are asserted in code so
  an empty overlap can never be a bad join.
- **C4 — the confusion matrix is non-vacuous.** All four cells are emitted and
  both marginals asserted non-zero; a 2×2 with an empty row is reported as
  uninformative rather than as a measured null.
- **C5 — the effect test can detect the gold-sized effect.** Plant a +0.3349
  signal on the GF strata and require the CI to exclude zero. A null from a test
  never shown to fire is not evidence (`positive-control every null`).

## 7. The three verdicts, written before the result is seen

All three are acceptable. **No outcome is being aimed for.**

- **SURVIVES** — the GF bearing−control contrast is positive with a
  task-clustered 95% CI excluding zero **on the `GF-BEARING ∧ ¬GOLD-BEARING`
  cells**. Then the headline is a memory-utility finding about *bearing*, not
  about answer-containment, and the oracle objection dies.
- **DISAPPEARS** — that contrast's CI includes zero while C5 shows the test
  could have detected a gold-sized effect. Then the headline is **conditional on
  answer-containment** and the manuscript must say so in those words.
- **CANNOT BE BUILT TO A COMPARABLE STANDARD** — GF yields too few
  discriminative tasks, or too few executed/affordable cells outside the gold
  set, to estimate the contrast; or its discriminativeness constraint cannot be
  enforced in the same shape. Then that is the finding, stated with its cause,
  and **no effect number is reported from an underpowered stratum as if it were
  one.**

## 8. Artifacts

| path | content |
|---|---|
| `scripts/gf1_gold_free_screen.py` | the screen + controls |
| `scripts/gf2_analyze_gold_free.py` | overlap, effect, CIs |
| `data/manifests/gf_lex_bearing.jsonl` | every GF-LEX firing cell |
| `results/ledgers/gf_gold_free_screen.json` | yield, controls, confusion matrix |
| `results/ledgers/gf_gold_free_effect.json` | the effect, CIs, verdict |

# The gold-free bearing screen — result

**2026-10-01, SA-GOLDFREE.** Closes the one experiment named in
`docs/BEARING_SCREEN_DISCLOSURE.md`: is the headline bearing−control effect a
*memory-utility* finding, or *"a passage containing the answer helps a model
answer"*?

Definition, analysis, controls and all three verdict criteria were frozen in
`docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md` **before** the screen ran. No outcome
was aimed for.

---

## Verdict: **the effect SURVIVES a gold-free screen — but only one of the two gold-free screens can find it**

| screen | what it reads | deciding contrast (gold-free cells only) | verdict |
|---|---|---|---|
| **GOLD** (current paper) | memory + **gold answer** + eval spec + pool | — (re-derived: **+0.3179**, CI [+0.174, +0.477]) | the published effect |
| **GF-LEX** rare question terms | memory + **question** + pool | **+0.0002**, CI [−0.0713, +0.0758] | **DISAPPEARS** |
| **GF-LLM** model judges relevance | memory + **question** + pool | **+0.3676**, CI [+0.0475, +0.6981] | **SURVIVES** |

Both gold-free screens see the question and the pool. **Neither sees the gold
answer, a reward, a model output, or the eval spec.** They differ only in how
they decide that a memory bears on a question — and they disagree.

**The resolution is not a tie.** GF-LEX is a demonstrably bad instrument and
the measurement says so in a way that does not depend on its effect estimate.
GF-LLM is a good one. The honest headline is therefore:

> **Answer-containment is not what makes a bearing memory useful. A gold-free
> judge that reads only the question and the memory finds the same effect, of
> the same size, on cells the gold screen never selected.**

---

## 1. The experiment

Candidate universe for every screen: all **277,594** same-domain
(memory, deterministic-task) cells — 1,889 memory units × 295 tasks, which is
exactly the universe `k1_build_screened_design.py` screened.

### GF-LEX (primary, deterministic, no model)
The matched counterfactual to the gold screen. The gold screen is a lexical
containment test; so is this. **The only thing changed is which string it looks
for:** the gold answer there, the question's rare terms here. The normalizer
(`leakage.normalize_text`), the pool, and the `≤8` discriminativeness threshold
are **inherited, not tuned**.

### GF-LLM (secondary, confirmatory)
One `metis/gpt-oss-120b` call per candidate, `temperature=0`,
`reasoning_effort=low`, prompt version `gf_bearing_judge_v1`, asking whether
the memory contains what the question needs. **The gold answer is absent from
the prompt by construction** — `build_prompt` has no field for it, and every
prompt is verified byte-identical to a rendering of (question, memory) alone.

A full-pool LLM screen is **277,594 calls** and was refused as infeasible, not
quietly approximated. Instead a cheap exhaustive lexical **recall** stage feeds
a **precision** judge. Because recall is exhaustive and the judge can only
shrink its output, the composite's full-pool firing set is **exact**, so
`1 ≤ k ≤ 8` is enforced in the same shape as the gold screen's.

---

## 2. Overlap with the current BEARING set

### GF-LEX × GOLD, over all 277,594 cells

| | gold-BEARING | not gold-BEARING | total |
|---|---|---|---|
| **GF-LEX-BEARING** | **7** | 211 | 218 |
| **not** | 259 | 277,117 | 277,376 |
| total | 266 | 277,328 | 277,594 |

`|GF ∧ gold| / |gold|` = **7/266 = 2.6%** · `/ |GF|` = **7/218 = 3.2%**
Jaccard 0.0147. Task level: 9 of 54 GF-discriminative tasks are also
gold-discriminative (gold has 75). Memory level: 40 of 116 shared.

🔴 **The near-disjointness is real, and it is not independence.** Positive
controls: the key spaces genuinely intersect (40 shared memories, 9 shared
tasks); `GF ∩ GF` = 218; and `GF ∩ gold-with-mangled-locator` = **0**, proving
a bad key reads as zero. Against a uniform null the expected overlap is
**0.209** cells, so 7 is **33.5×** chance (hypergeometric P(X≥7) = 2.4 × 10⁻⁹),
and against a degree-preserving permutation null P < 0.0001. **The two screens
are strongly related and still mostly select different cells.**

### GF-LLM × GOLD

| | gold-BEARING | not | total |
|---|---|---|---|
| **GF-LLM-BEARING** | **10** | 32 | 42 |
| total | 266 | — | 277,594 |

`|LLM ∧ gold| / |gold|` = **3.8%** · `/ |LLM|` = **23.8%** — a **7.4× higher
precision against gold than GF-LEX's 3.2%**, from a screen that never sees gold.

🔴 **Why the gold-side fraction stays low, measured rather than assumed:** the
recall stage only ever showed the judge **14 of the 266** gold-bearing cells
(67 are excluded by the 20,000-token size cap alone). **Of those 14 it accepted
10 — 71%.** So the low overlap is a *recall* limit of the cheap first stage,
not the judge disagreeing with the gold screen. A reader should not read
"3.8%" as "the judge rejects gold-bearing cells".

---

## 3. The gold-free bearing−control effect

### Executed coverage — what already existed, and what had to be run

Of GF-LEX's 218 bearing cells, only **5** had an executed measurement, and only
**4** in the deciding `GF ∧ ¬gold` stratum — because the executed design was
*chosen by the gold screen*. New runs were therefore required and were made.

| run | cells | calls | errors | session |
|---|---|---|---|---|
| GF-LEX arm | 328 (164 bearing / 164 control) | 1,312 | 0 | one (`gf_8e8f862ea5f3`) |
| GF-LLM arm | 84 (42 / 42) | 336 | 0 | one (`gf_c47c812e0513`) |

Both arms of every cell ran **in one session** (defect #25: `gpt-oss-120b` is
deterministic within a session and not across). The guard refusing a
cross-session resume was verified by planting a mismatched session id.
Replicates agreed on **84/84** GF-LLM cells, confirming within-session
determinism. Scoring produced **zero** unscorable rows; no `None` was ever
coerced to 0.0.

### GF-LEX — the effect disappears

```
deciding stratum: 160 gold-free bearing cells vs 164 matched controls, 146 tasks
  task-clustered     +0.0002   95% CI [-0.0713, +0.0758]
  episode-clustered  +0.0002   95% CI [-0.0931, +0.0677]
  paired by memory   -0.0453   95% CI [-0.1247, +0.0328]   n=82 (22 non-zero)
```

### GF-LLM — the effect survives

```
deciding stratum: 32 gold-free bearing cells vs 42 matched controls, 44 tasks
  task-clustered     +0.3676   95% CI [+0.0475, +0.6981]
  episode-clustered  +0.3676   95% CI [+0.1447, +0.6691]
  paired by memory   +0.4896   95% CI [+0.2326, +0.7569]   n=24 (14 non-zero)
                     12 of 14 non-zero memories positive, sign-flip p = 0.0027
```

Arm rates on the gold-free GF-LLM bearing cells: **WITHOUT 10/64 = 15.6% →
WITH 32/64 = 50.0%**. The matched controls move the other way (14.3% → 11.9%).

**Robustness.** Leave-one-task-out keeps the difference in [+0.319, +0.457] and
leave-one-episode-out in [+0.300, +0.421] — the sign is stable under every
single drop, so no one question or episode carries it. No task supplies more
than 4 of the 32 cells.

---

## 4. Why GF-LEX's null is believable, and why it is not the answer

**The null is real, not underpowered.** Four independent checks:

1. **C5** plants +0.3349 on the same strata and the CI excludes zero; the
   control is non-degenerate (146 tasks, 42 episodes) and a label **shuffle**
   does *not* fire.
2. The task-clustered **half-width is 0.0735**. The gold effect, +0.3179, is
   **4.3×** that — it could not have hidden.
3. The **4 also-gold-bearing cells inside the GF-LEX run itself** — same
   pipeline, same session, same scorer — score **dU = +1.0**.
4. GF-LLM, analysed by the **same code**, returns a positive interval.

**But GF-LEX is a bad instrument, and this is measurable without reference to
its effect.** Two diagnostics:

- **95% of its 218 firings rest on a SINGLE anchor term**, and the most
  productive anchors are generic words that happen to be rare in the memory
  pool: `five` (49 firings), `two` (27), `typically` (16), `whenever`,
  `appears`, `without`. Reading the cells shows exactly the predicted failure —
  a question asking what button "appears" fires on a memory where a review
  "appears positive".
- **Both-arms-fail rate**, the measurement-capacity diagnostic:

  | stratum | both-arms-fail |
  |---|---|
  | gold BEARING | **0.525** |
  | unscreened RANDOM | 0.701 |
  | **GF-LEX bearing (gold-free)** | **0.762** |
  | **GF-LLM bearing (gold-free)** | **0.406** |

  GF-LEX's bearing cells behave like **random** cells. GF-LLM's are *better*
  than the gold screen's. A stratum that cannot express an effect cannot
  measure its absence.

So GF-LEX's null is correctly measured and means **"rare-term overlap does not
identify bearing"** — a fact about that detector, not about memory utility.

---

## 5. What the manuscript should now claim

1. **The oracle objection is answered, and the answer is not "trust us".** The
   effect reproduces at full size (+0.3676, CI [+0.0475, +0.6981]
   task-clustered; +0.4896 paired) under a screen that **never sees the gold
   answer**, on **32 cells the gold screen does not select**. Answer-containment
   is sufficient to locate bearing cells but is **not what makes them useful**.
2. **Keep the conditional framing** — "among cells where the memory bears on
   the task" — but it may now be justified by a **deployable-shaped** criterion.
   GF-LLM reads only the question and the memory, which is what a retrieval
   gate has. This does **not** make it a retrieval system (it is applied
   offline to a pool), and the Discussion's withdrawn retrieval-guidance
   sentence should stay withdrawn.
3. **Report 11.5% → 46.0% beside the gold effect, and 15.6% → 50.0% beside the
   gold-free one.** Both show a reader given a bearing memory still fails about
   half the time.
4. **State the disagreement; do not hide GF-LEX.** "A lexical gold-free screen
   finds nothing" is a real result about *detectors*, and reporting only the
   screen that worked would be selecting an instrument on its outcome. The
   paper should say both ran, why GF-LEX is unfit (single-anchor firings;
   both-arms-fail 0.762 ≈ RANDOM), and that the fitness diagnostic is
   independent of the effect estimate.
5. **Three caveats that must travel with the GF-LLM number:**
   - **n is small** — 32 bearing cells, 24 paired memories, 19 episodes. The
     interval is wide ([+0.0475, +0.6981] task-clustered) and the task-clustered
     lower bound is close to zero.
   - **Its recall stage inherits GF-LEX's anchors**, so its coverage of the
     corpus is bounded by a detector shown to be weak. It saw 14 of 266
     gold-bearing cells. A better recall stage would likely find more.
   - **Cross-screen comparisons are cross-session.** Each contrast is internally
     session-matched; the gold +0.3179 and the GF-LLM +0.3676 come from
     different sessions, so they agree in **sign and significance** and their
     numeric difference is confounded with the day.
6. **The inputs table belongs in the paper** (`§2` of the pre-commitment), for
   all three screens side by side.

---

## 6. Instrument defects found, each by planting

| # | defect | how it was caught | what it would have cost |
|---|---|---|---|
| 1 | **C2's first version could not fail.** It removed the `≤8` discriminativeness bound and required the yield to inflate. It did not move — **no GF-LEX task fires on more than 8 pool memories at all** (gold: 205 of 295 exceed the bound). | the control failing, then measuring the hit distribution rather than deleting the bound | the bound is *non-binding at this operating point*, which is a reported property of the screen. Deleting it would have made the two screens incomparable |
| 2 | **The gold-freeness guard tested the wrong proposition** and aborted the run on task `ca8e070b` — question *"…true or false?"*, gold `false`. | the run stopping on a cell that was not a leak | **69 of 295** deterministic questions contain their own gold answer. Gold-free means *the answer is not a privileged input*, not *the string is absent from the question*. Replaced by a byte-exact template reconstruction, verified against two plants |
| 3 | **The judge-cache reader guessed the field names** (`key_fields`/`content` instead of `key`/`response`) and recovered **zero** verdicts. | the non-vacuity guard refusing an empty recovery | every GF-LLM control would have been built from cells **the judge never saw** — a different object from a cell it rejected |
| 4 | **C5 passed on a design that could not fail it.** On a 1-cell-per-stratum synthetic it returned PASS with CI `[0.3349, 0.3349]` — zero width. | running the control against a deliberately degenerate input | a null would have been "positive-controlled" by arithmetic rather than power. C5 now requires a non-degenerate interval, ≥5 tasks, ≥5 episodes, and a shuffle control that must **not** fire |
| 5 | **GF-LLM's controls were missing for most of the stratum.** The judge had only ever seen lexically-similar cells, so **24 of 42** bearing cells had no same-family judge-NO control. | checking control availability per memory×family before building the design | controls would have silently fallen back to unjudged cells. Fixed by `gf7_judge_controls.py`: 126 extra calls, 125 NO, giving all 28 bearing memories a control |

## 7. Artifacts

| path | content |
|---|---|
| `docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md` | the frozen definition |
| `scripts/gf1_gold_free_screen.py` | GF-LEX + controls C1–C4 |
| `scripts/gf2_build_gf_design.py` · `gf3_run_gf_design.py` | GF-LEX design, runner (`--arm lex|llm`) |
| `scripts/gf4_analyze_gold_free.py` | effect, CIs, C5, verdict |
| `scripts/gf5_llm_screen.py` · `gf6_build_llm_design.py` · `gf7_judge_controls.py` | GF-LLM screen, design, control verdicts |
| `data/manifests/gf_lex_bearing.jsonl` (218) · `gf_llm_bearing.jsonl` (42) | firing cells |
| `results/ledgers/gf_gold_free_screen.json` · `gf_llm_screen.json` | yields, controls, confusion matrices |
| `results/ledgers/gf_gold_free_effect.json` · `gf_llm_effect.json` | effects, CIs, verdicts |
| `results/deltau_goldfree/` · `results/deltau_goldfree_llm/` | rows (untracked, per `.gitignore`) |

# The length-controlled representation test — result

**2026-10-02, SA-LENGTH-RUN.** Executes `docs/LENGTH_CONTROL_PRECOMMITMENT.md`,
committed at `f702aaf` **before any reader call had been made against a
truncated memory**. The eight arms, the conditions, the primary contrast, the
estimator, the CI method, the controls, and the meaning of every possible
outcome were fixed in that document. Nothing here was chosen after seeing a
number.

All eight arms ran in **one session**, 8,864 calls in 25.9 minutes.

---

## Verdict: **O2 — the representation effect does not survive a length control**

> At a matched exposed-token budget, a content-blind extractive slice and a
> model-written summary are **indistinguishable**. What Raw buys is the
> **budget to carry the bearing content**, at zero formation cost.

| | Δ = ΔU(T) − ΔU(S) on BEARING | 95% CI (task-clustered) | n | clusters |
|---|---:|---|---:|---:|
| **PRIMARY** `trunc_last_matched` − `summary` | **+0.0519** | **[−0.0672, +0.1704]** | 135 | 55 |

The interval includes zero. Applying §7's precedence exactly:

1. **O5 does not apply.** Every control passed — 11 of 11, including C-AA and
   all 14 C-PLANT guards. §5.
2. **O4 does not apply** (checked *before* O1/O2/O3, as §7 requires). O4 needs
   *all* of: T≈0, S≈0, a flat ladder, and C-POWER passing. The ladder is **not
   flat** — `trunc_last_1024` and `trunc_last_4096` both exclude zero — so the
   condition did not degenerate into a truncation test.
3. **Among O1/O2/O3 the sign and CI of the primary decide.** Δ > 0 but its CI
   includes zero → **O2**.

**All three of O2's clauses are met**, which the precommitment requires before
the exposure-budget reading may be taken:

| O2 clause | status |
|---|---|
| (a) the primary CI includes zero | **yes**, [−0.0672, +0.1704] |
| (b) C-POWER shows the effect was detectable | **yes**, see §3 |
| (c) ΔU(R) − ΔU(T) > 0 with a CI excluding zero | **yes**, **+0.2612** [+0.1554, +0.3876], n=134 |

The verdict is taken from the primary contrast alone — not the sensitivity, not
the secondary, not any subgroup (§7).

---

## 1. The controls, first

A result is only as good as the controls that could have refused it. **11 of
11 passed**, and each was shown able to FAIL by planting the defect it exists
to catch.

| control | what it establishes | measured |
|---|---|---|
| **C-AA** (§5.2) | the identity arm reproduces Raw **exactly** | text byte-identical **554/554**; reward triples identical **552/552 scored pairs**; reader outputs byte-identical **552/552** |
| **C5 POSITION** (§3.2) | target position identical across all eight arms | **0 of 277** pair keys differ |
| **C-SESSION** (§5.1) | one session, one run_id | 1 run_id, 1 session start, 8 arms, **0 pre-existing cache rows**, 25.9 min |
| **C-REPL** | the in-session determinism §5.1 assumes | **2,213/2,213** replicate pairs byte-identical |
| **C-WITHOUT** (§6) | arms differ only in the target | **554/554** WITHOUT generations byte-identical across arms |
| **C-KEY** | no arm served another arm's cached answer | **1,040** context groups span >1 arm, yet **8,834/8,834** key hashes distinct |
| **C-JOIN** (§5.5) | the documented traps | locator join **277**; `memory_id` join **0**; `condition_id` join **0** |
| **C-TOK** (§5.5) | budget matched in the official tokenizer | **0 over budget**; of 217 cells actually cut, **216 exact**, one at −1 |
| **C-DET** (§5.5) | the gold detector discriminates | self-test 17/17; silent on **0/142** MATCHED_CONTROL in every extractive arm |
| **C-PLANT** (§5.3) | each guard fails on a planted defect | **14/14** |
| **C-CELLSET** (§4.1) | the frozen cell set | **277** cells, 135 BEARING + 142 MATCHED_CONTROL |

### C-AA is the one that matters

`trunc_last_20000` renders text byte-identical to Raw in 277/277 (budget 20,000
≥ max Raw 19,801) but travels under a different `condition_id` and a different
content hash, so it is a genuinely separate set of calls with a **known correct
answer**. It exercises the whole new code path end to end.

It reproduced Raw exactly: **552 of 552 scored pairs**, every reward triple and
every reader output byte-identical. Two pairs are excluded because *the same
cell* failed in both arms (see §4); counting `None == None` as agreement would
have inflated the control that exists to detect errors, so unscored pairs are
excluded from both numerator and denominator.

And C-AA is only a control if the two arms really issue separate calls — their
prompts are byte-identical by construction. **C-KEY proves they do**: 1,040
context groups render identical bytes across arms, and all 8,834 stored key
hashes are still distinct.

---

## 2. Every arm, on the same 277 cells, in one session

Mean ΔU on BEARING cells, 95% task-clustered CI:

| arm | median memory tokens | bearing content retained | mean ΔU | 95% CI |
|---|---:|---:|---:|---|
| `raw` | 7,802 | 135/135 = 100% | **+0.3433** | [+0.2117, +0.4860] |
| `trunc_last_20000` (= Raw) | 7,802 | 135/135 = 100% | **+0.3433** | [+0.2117, +0.4860] |
| `trunc_last_4096` | 4,096 | 113/135 = 83.7% | **+0.3111** | [+0.1884, +0.4490] |
| `trunc_last_1024` | 1,024 | 65/135 = 48.1% | **+0.1926** | [+0.0855, +0.3095] |
| `trunc_last_matched` | 356 | 39/135 = 28.9% | +0.0815 | [−0.0072, +0.1818] |
| `summary` | 356 | 24/135 = 17.8% | +0.0296 | [−0.0600, +0.1203] |
| `structured` | 225 | 17/135 = 12.6% | −0.0444 | [−0.1351, +0.0376] |
| `trunc_first_matched` | 356 | 1/135 = 0.7% | −0.0222 | [−0.0833, +0.0362] |

The three short arms — one extractive, two model-written — all sit at zero. The
three long arms all exclude zero. **The split is by budget, not by
representation.**

Note the identity arm reproducing Raw to four decimals: that is C-AA, visible
in the main table.

---

## 3. The null is reportable, because the test could have found the effect

§5.4 binds: *"A reported null is accompanied by this number or it is not
reported."*

* Primary CI half-width: **0.1188**.
* Planting the published cross-session gap (**+0.2741**) into the
  `trunc_last_matched` arm moves the primary to **+0.3260** [+0.2069, +0.4445]
  — **detected**.
* Planting the **in-session** Raw−Summary gap (**+0.3209**, re-derived here, not
  the cross-session figure §5.1 forbids as a comparator) gives **+0.3727**
  [+0.2537, +0.4913] — **detected**.
* Both plants are required to produce a **non-degenerate** interval over **≥5
  task clusters** before counting as detection; both had width 0.238 over 55
  clusters.
* Negative half: planting **zero** reproduces the primary exactly and does
  **not** exclude zero. A detector that fired on a zero plant would be vacuous.

So this design resolves a true difference of roughly 0.12 or larger, and the
measured Δ of +0.0519 is below that. **The null is a measured
indistinguishability, not a failure to look.**

---

## 4. What was excluded, and why

§4.4: `reward is None` means **could not be scored**. Never coerced to 0.0.

**6 rows of 4,432** are unscored, all `empty_output_finish_length` — the
reasoning model spending its `max_tokens` budget before emitting an answer:

| arm | rows | cell |
|---|---:|---|
| `raw` | 2 | `2d00b63d:2-2 \| 4ca9f7d7` |
| `trunc_last_20000` | 2 | `2d00b63d:2-2 \| 4ca9f7d7` |
| `trunc_last_4096` | 2 | `4919aae9:7-7 \| 8e320e42` |

Raw and the identity arm failed on **the same cell, both replicates** — itself
further evidence that the identity arm is reproducing Raw rather than merely
agreeing with it.

No cell lost only one of its two replicates (**0 partial-replicate cells in
every arm**), so no cell mean rests on fewer draws than its neighbours. The
**primary contrast is unaffected**: it compares `trunc_last_matched` against
`summary`, neither of which lost a row, so it keeps the full **n = 135**. The
raw-involving contrasts run on **n = 134**.

---

## 5. The ladder — the pre-registered identification

§4.2 fixes this as the identification, not decoration: *"If utility tracks
**retention** rather than **token count**, the mechanism is content presence;
the budget is instrumental."*

| arm | median tokens | retention | mean ΔU |
|---|---:|---:|---:|
| `trunc_first_matched` | 356 | 0.7% | −0.0222 |
| `trunc_last_matched` | 356 | 28.9% | +0.0815 |
| `trunc_last_1024` | 1,024 | 48.1% | +0.1926 |
| `trunc_last_4096` | 4,096 | 83.7% | +0.3111 |
| `trunc_last_20000` | 7,802 | 100% | +0.3433 |

**Utility tracks retention.** The decisive comparison is the first two rows:
`trunc_first_matched` and `trunc_last_matched` have the **same token budget**
and differ **only** in which end of the segment is kept. Their retention
differs 41× (0.7% vs 28.9%), and the paired contrast between them is
**+0.1037** [+0.0080, +0.2046], excluding zero. **At a fixed token count,
moving content in changes utility.** Tokens are not the mechanism; content
presence is.

Across the five arms, ΔU correlates r = 0.993 with retention and r = 0.957 with
log tokens. *Those two numbers are five points each, carry no CI, and nothing
in the verdict rests on them* — the paired step contrasts below are the part
that has intervals:

| step (paired, BEARING) | Δ | 95% CI | excludes 0 |
|---|---:|---|---|
| first→last at matched budget | +0.1037 | [+0.0080, +0.2046] | **yes** |
| matched → 1,024 | +0.1111 | [+0.0490, +0.1825] | **yes** |
| 1,024 → 4,096 | +0.1185 | [+0.0414, +0.2137] | **yes** |
| 4,096 → 20,000 | +0.0373 | [−0.0205, +0.1048] | no |

Recovery is real and roughly linear in log-budget up to 4,096, then saturates —
the last step is the only one whose interval covers zero, which is what you
expect once 83.7% of the bearing content is already present.

**The budget at which identification becomes possible is ~1,024 tokens**
(2.9× the matched budget), where the extractive arm first excludes zero.

---

## 6. The sensitivity and the secondary — reported, not used for the verdict

**Pre-registered sensitivity** (§4.2), `trunc_last_matched` − `structured` on
BEARING: **+0.1259** [+0.0149, +0.2411], which *does* exclude zero. §7 is
explicit that the verdict comes from the primary and **not** from the
sensitivity, so this does not change the outcome. It is reported because the
precommitment says it always is. Read honestly: extraction at a matched budget
beats the *structured* representation, which is the weakest of the three and is
itself below zero; it does not beat *summary*, which is the comparison that
carries the claim.

**Secondary** (§4.2), within-memory paired B−MC over 57 memories, in the
published Contribution-B table's shape:

| arm | B−MC | 95% CI | excludes 0 |
|---|---:|---|---|
| `raw` | +0.4091 | [+0.2633, +0.5638] | yes |
| `trunc_last_20000` | +0.4091 | [+0.2633, +0.5638] | yes |
| `trunc_last_4096` | +0.3639 | [+0.2179, +0.5177] | yes |
| `trunc_last_1024` | +0.1714 | [+0.0562, +0.2852] | yes |
| `trunc_last_matched` | +0.0584 | [−0.0339, +0.1510] | no |
| `trunc_first_matched` | +0.0319 | [−0.0616, +0.1265] | no |
| `summary` | +0.0240 | [−0.1045, +0.1460] | no |
| `structured` | +0.0049 | [−0.0940, +0.1012] | no |

The same picture: long arms positive, short arms indistinguishable from zero
and from each other.

---

## 7. The subgroup that stays off limits

§4.3 pre-registers the retention-conditioned subgroup as **excluded from the
verdict** — an effect measured on cells selected for retaining the signal is
circular, and n = 9 cannot carry a CI. The 2×2 is **descriptive only**, and it
reproduces the precommitment's predicted counts exactly:

| | summary retained | summary lost |
|---|---:|---:|
| **trunc retained** | 9 | 30 |
| **trunc lost** | 15 | 81 |

Machine-checked, not just promised: the primary used **135 cells = the full
BEARING stratum**, not the 39 trunc-retained or the 9 both-retained.

---

## 8. What the manuscript must now claim about Story 2

The precommitment wrote this before the result existed (§7, O2), and it is now
the required reading.

**Story 2 must narrow to "exposure budget and formation cost", and must say
plainly that the representation comparison does not survive a length control.**

The paragraph at `main.tex:1514` — *"Representation: compression does not
preserve usefulness"* — is **not wrong, but its explanation is**. Its numbers
stand (they are the published cross-session measurement, +0.3174 / +0.0613 /
−0.0498). What must change is the causal claim attached to them: "rewriting the
experience removes the benefit" attributes the loss to *rewriting*, and this
experiment shows the loss is attributable to *length*.

Recommended replacement for the paragraph's final sentences, following O2's own
wording:

> **Compressing to this budget destroys the effect — and an extractive memory
> at the same budget loses it too. What Raw buys is the budget to carry the
> bearing content, at zero formation cost.** At a matched exposed-token budget
> (median 356 tokens in the official tokenizer), a content-blind extractive
> slice scores +0.0519 against the model-written summary (95% CI [−0.0672,
> +0.1704], 135 BEARING cells over 55 task clusters), while the same test
> resolves a true difference of 0.12. Utility recovers monotonically as the
> budget grows — +0.1926 at 1,024 tokens and +0.3111 at 4,096 — and tracks
> **retained bearing content** rather than token count: at a *fixed* budget,
> keeping the end of a page-visit segment rather than the beginning raises
> retention from 0.7% to 28.9% and ΔU by +0.1037 (CI [+0.0080, +0.2046]).

Three further obligations:

1. **The cost-axis result is unaffected and becomes the load-bearing half of
   Story 2.** Raw is not beaten once formation cost is charged; that claim
   never depended on the representation contrast and still stands. A truncated
   memory, like Raw, costs **zero** writer calls — so this result *strengthens*
   the cost argument: the cheap memory is also the one that carries the
   content, and the expensive rewrite buys nothing at equal length.
2. **A new positive finding the paper does not currently have.** Where the
   bearing content *sits* is measurable and matters: at an identical token
   budget, last-N beats first-N by +0.1037. That is a statement about this
   corpus (browsing trajectories put the payload near the end of a segment),
   disclosed as such.
3. **The published Raw-vs-Summary comparison spans two sessions** (Raw
   2026-09-29, compressed 2026-09-30) and `gpt-oss-120b` is not deterministic
   across sessions. The in-session replacement measured here is **+0.3209**
   [+0.1864, +0.4615] — close to the published +0.2741, which is reassuring,
   but the paper should cite the session-matched figure.

### What may NOT be claimed

* Not "compression is as good as extraction **in general**". The claim is
  about **one positional rule on one corpus at one budget** (§3.1).
* Not that the sensitivity rescues the representation story. It does not;
  §7 forbids reading the verdict off it.
* Not any effect conditioned on cells that retained the bearing content (§4.3).

---

## 9. Caveats that belong beside the result

* **Total context is not matched** (§2.5), only exposed *memory* tokens.
  Median WITH-context is ~24.9k tokens for Raw and ~17.0k for the compressed
  arms. This is conservative for the primary — `trunc_last_matched` and
  `summary` are matched on both — and is a caveat only for Raw vs trunc.
* **The reader's tokenizer**, not the one the budget is defined in, is what
  consumes the text. Re-derived per cell: the length-controlled arm is a median
  **4 tokens shorter** than summary in `o200k_harmony` (mean +3.5, p5 −23,
  p95 +69, n=57). So the extractive arm did not buy its (null) result with
  tokens.
* **One cell's slice is 195 tokens against a 196-token budget.** The official
  tokenizer admits no prefix of exactly 196 tokens there (510 chars = 195, 511
  chars = 197). The rule asserts **maximality** — one more character must break
  the budget — which is the property length-matching needs and is well-defined
  where exact equality is not. 216 of 217 cut cells are exact; one is −1; none
  is over budget.
* **The summary arm's writer can emit a gold string the source span never
  contained**: the detector fires on 3 of 142 MATCHED_CONTROL cells for
  `summary`, and on **0 of 142** for every extractive arm. That is a property
  of the writer, not of the detector, and it does not touch the BEARING
  contrasts.
* **§2.2's quartile means do not reproduce** (3 of 27 re-derived figures;
  `results/ledgers/length_control_confound.json`). Everything §2.2 is cited for
  does reproduce — Spearman −0.209/+0.079, Pearson −0.185/+0.067, n=135/142,
  and the shortest-quartile-is-largest claim. The design does not depend on
  §2.2 (§1's own table), and the precommitment was **not** edited to match.

---

## 10. Artifacts

| path | content |
|---|---|
| `docs/LENGTH_CONTROL_PRECOMMITMENT.md` | the frozen design, committed `f702aaf` before execution |
| `scripts/len0_confound_ledger.py` | §2 re-derived |
| `scripts/len1_build_length_control.py` | truncation rule, conditions, all controls |
| `scripts/len2_analyze_length_control.py` | contrasts, CIs, verdict against §7 |
| `scripts/len3_repro_slice.py` | the tracked row slice + its reproduction check |
| `results/ledgers/length_control_confound.json` | §2, machine-readable, with its 3 mismatches |
| `results/ledgers/length_control_run.json` | the run: calls, controls, retention, tokens |
| `results/ledgers/length_control_result.json` | contrasts, CIs, controls, verdict |
| `results/ledgers/repro/length_control_cells_slim.jsonl` | 4,432 rows, every field the numbers come from |
| `results/ledgers/repro/length_control_manifest.json` | sha256 of the full artifact + reproduction check |
| `results/length_control/cells.jsonl` | all 4,432 rows with full model text — **untracked** by repo convention (`.gitignore results/**`); sha256 in the manifest |

The primary contrast was re-derived from the slim slice alone and reproduces
the full artifact exactly (+0.051852, n=135), and that check was shown able to
fail by dropping a required field.

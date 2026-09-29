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

## 2026-09-29 — D3 (RETRACTED, superseded by D4): DATASETS.md V2 measurements treated as UNSOURCED

> 🔴 **RETRACTED the same day. The alarm was mine and it was wrong.** Kept visible, not
> deleted: a retraction is labelling, and deleting the claim would kill the repair it
> prescribes.

**What I claimed.** That every quantitative claim about LongMemEval-V2 in the inherited
`DATASETS.md` was unsourced, because `find /Users/bellayang -iname "*lme_v2*"` returned
zero hits and the file "is not on this machine."

**Why it was wrong.** The data was in `/tmp/lmev2`. On macOS `/tmp` is a **symlink** to
`/private/tmp`, and it is outside `/Users/bellayang` regardless. My `find` could not have
seen it. **This was a search-scope artifact — the exact error class I had instructed both
sub-agents to guard against, committed by me, in the same hour.** I ran a null without a
positive control and wrote the result into a durable document.

**The lesson that generalizes.** A negative from a single search root is a statement about
the root, not about the machine. Validate a negative against an exhaustive or independent
route before escalating it.

---

## 2026-09-29 — D4: LongMemEval-V2 counts are VERIFIED; V1 is the pilot dataset

**Decision.** The inherited V2 structural counts stand. **But V2 is not the Experiment-0
dataset — V1 is** — and the inherited cost table does not transfer.

**Evidence, reproduced by the Master Agent from the files.**

`shasum -a 256 -c checksums.sha256` — running the command the repo itself prescribes:
`haystacks/lme_v2_small.json: OK`, `questions.jsonl: OK`, `DATA_CARD.md: OK`,
`SCHEMA.md: OK`. One mismatch (`README.md`) and 31 unreadable entries, all for files not
present in this partial download. **The two files the counts depend on both verify.**

Recomputed directly from the verified `lme_v2_small.json`:

| Claim | Inherited | Reproduced | Verdict |
|---|---|---|---|
| (question, trajectory) cells | 45,100 | **45,100** | ✅ exact |
| web questions per trajectory | min=med=max=240 | **240/240/240** over 100 trajectories | ✅ exact |
| enterprise questions per trajectory | 211 | **211/211/211** over 100 trajectories | ✅ exact |
| questions | 451 | **451** (240 web, 211 enterprise) | ✅ exact |

**So the matrix is genuinely dense by construction.** Every trajectory is in the haystack
of every question in its domain.

### Three findings that change the plan anyway

1. 🔴 **V2 ships no answer-bearing evidence labels.** I enumerated every field across all
   451 records: `answer, domain, environment, eval_function, id, image, question,
   question_type`. **No `answer_session_ids`, no evidence/gold/support field of any kind.**
   The 45,100 cells are an **unlabelled grid**, not a free labelled matrix. V1 *does* ship
   `answer_session_ids`.
2. 🔴 **Scale.** Sub-agent A measured ~164k tokens per V2 trajectory (n=154). The full
   matrix is ~4.4 × 10¹⁰ tokens — **orders of magnitude beyond the inherited cost table,
   which was computed for V1 and does not transfer.**
3. ⚠️ **Leakage.** A leak probe found the gold answer verbatim in ≥1 haystack trajectory
   for 41 of 55 questions sampled (median 5, max 39). An upper bound, but naive ΔU on V2
   would be contaminated. *(Sub-agent A's measurement; not independently re-run by me.)*

**Consequence.** Run Experiment 0 on **LongMemEval V1**, which ships the evidence labels
the counterfactual needs. Keep V2 as a stratified subsample, restricted to deterministically
scored questions.

**Master Agent's own measurement:** **295** of 451 V2 questions are scored by a
deterministic function (`norm_phrase_set_match` 200, `..._ordered` 26, `mc_choice_match`
68, `mc_choice_set_match` 1); 156 are LLM-judged (`llm_abstention_checker` 128,
`llm_gotchas_checker` 28). Sub-agent A reported 294; I derive **295** and use mine.
Preferring deterministic scoring removes judge nondeterminism from ΔU entirely for those
cells — worth a great deal when the noise floor is the thing being measured.

**Overturned by.** Locating evidence labels for V2, or a cheaper context protocol that
makes the token cost tractable.

---

## 2026-09-29 — D5: The UMEM seam SURVIVES; EMBER must be cited and distinguished

**Decision.** P1's framing holds, with two corrections and one new required citation.

**UMEM (verified from the full PDF by Sub-agent A).** The reward is
`Δu(q′) = G_succ(q′) + R_eff(q′)` with `G_succ(q′) = c(τ^mem) − c(τ^ref)`, then collapsed:
*"the average marginal utility over the neighborhood, r_g = E_{q′∼NN(q)}[Δu(q′)]."*
UMEM computes the per-task values and **keeps only the mean** — no variance, dispersion,
or negative-utility reporting anywhere. **The seam survives: UMEM averages; P1 asks whether
the variation is signal.**

Two corrections to the inherited notes: **N = 3, not 5** (§5.1; N=5 is the too-broad
*ablation* arm), and Appendix C.1 is **Lemma C.1 with a proof**, not an assumption — so it
must be engaged as an argument, not dismissed as an assumption. The ablation is single-run
with no CIs and N=5 *improves* one backbone by 1.6 on HLE — **do not over-quote it.**

**EMBER (arXiv:2606.05894) — a real collision the prior audit missed.** Its MultiQ split
*"tests whether one frozen retained memory can serve multiple future tasks"*, with 5
questions per bundle over 100 bundles. **P1 cannot claim to be first to score one memory
against several future tasks** — that was already on the forbidden list, and EMBER is now
the concrete reason.

It does report a dispersion-like statistic under another name: *coverage balance*, the
**min** over the bundle. But a min over a non-negative Retain-Recall in [0,1] **cannot
express a sign change** — "helped A, harmed B" is structurally inexpressible. EMBER also
has no per-item score (no matrix) and no counterfactual removal. **Distinguish on
granularity and sign, and cite it.**

**Overturned by.** Finding per-memory cross-task dispersion or negative utility reported in
either paper.

---

## 2026-09-29 — D6: EvoMemEval remains UNRESOLVED — a login-gated channel, not an absence

**Decision.** Do not treat EvoMemEval as either a collision or a non-collision. It is the
single highest-value open question, and it needs two minutes in a logged-in browser.

**Evidence.** Sub-agent A got further than the prior audit: the OpenReview search parameter
is `term`, not `query`, and `api2.openreview.net/notes/search?term=EvoMemEval` returns the
full record. The abstract says memory items *"are evaluated on held-out future tasks by
comparing executions with and without the memory"* — plural, but **ambiguous** between
one-item-many-tasks and a pool-vs-pool pairing, and it asserts no per-memory statistic.

**The PDF is CHANNEL-DEAD, not missing.** Every route 403s, and the positive control
(`DT7JyQC3MR`, MemoryAgentBench) **403s identically** — so the 403 says nothing about this
paper. No arXiv or OpenAlex preprint exists (both channels passed their own controls).

**What is already off the table regardless:** EvoMemEval owns the counterfactual
with/without protocol, "predict memory utility before execution", and "retrieval similarity
is not a reliable proxy for utility."

**Resolved by.** One logged-in fetch of `openreview.net/pdf?id=n3GMbobXnc`.

## 2026-09-29 — G1: pool across `verifier_id` on LongMemEval-V2, with the reason

**Decision.** Run the noise floors and the label/flip analysis with
`allow_pooling=True` over `verifier_id`. The pooling is recorded on every estimate as a
flag, and this entry is the reason the guard demands.

**Why the guard fires.** `analysis/common.py::require_homogeneous` treats `verifier_id` as
experimental identity, because a sibling project lost a table to arms scored under
different verifiers. On LongMemEval-V2 the scorer is **a property of the question**, not
of an arm: the 220 sampled tasks carry `norm_phrase_set_match` (145), `mc_choice_match`
(54), `norm_phrase_set_match_ordered` (20) and `mc_choice_set_match` (1). Any sample of
this benchmark spanning more than one question type trips the check.

**Why it is safe here — the three hazards the guard exists to catch, each measured:**

1. *WITH and WITHOUT scored differently within a row* — structurally impossible;
   `verifier_id` is one field per row, shared by both arms by construction.
2. *The same task scored under two verifiers* — **0 of 220 tasks**.
3. *The same cell scored under two verifiers across replicates* — **0 of 480 cells**.

Exactly **one** `verifier_version` (`vendored@f8ba659e237c`) appears across all 960 rows.

**The substantive argument.** ΔU is always a *within-task* contrast: WITH and WITHOUT for
one question, scored by that question's own scorer. **No ΔU ever compares two scorers.**
Pooling ΔU values across tasks is therefore pooling contrasts, not pooling raw scores, and
that is what the analysis is defined on.

**What would change this.** If a task's scorer were ever changed mid-study, or if a future
arm scored the same question two ways, hazards 2 and 3 become live and pooling must stop.
The counts above are re-derivable from `results/deltau_pilot/cells.jsonl` and should be
re-run on every new batch rather than assumed to still hold.

**Not waived, narrowed.** `verifier_version` homogeneity is still enforced and still
holds; only the per-question `verifier_id` axis is pooled.

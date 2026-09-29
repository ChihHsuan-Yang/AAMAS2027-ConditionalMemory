# Dataset Feasibility — measured by the Master Agent, 2026-09-29

Every number here was computed on this machine from a downloaded file. Nothing is
inherited. Reproduce with the snippets in `scripts/` or re-run the counts directly.

---

## 0. Headline

| Question | Answer |
|---|---|
| Is a memory × future-task matrix available for free in LongMemEval V1? | 🔴 **NO — the inherited "679 natural cells" does not exist in the cleaned file** |
| Is it available in V2? | ⚠️ Dense grid (45,100 cells, verified) but **no evidence labels** and ~164k tokens/trajectory |
| Can we build one? | ✅ **Yes** — V1's design supports constructing a dense matrix, and MIT permits it |

## 1. 🔴 The inherited "679 naturally occurring (m,t) cells" is REFUTED

**Inherited claim** (`DATASETS.md`): *"in the S split, **281 session contents are evidence
for ≥1 question and filler for ≥1 other**, spanning 393 questions → **679
naturally-occurring (m,t) cells with ground-truth useful/irrelevant labels, free, no
generation.**"*

**Measured on `longmemeval_s_cleaned.json` (277,383,467 bytes, downloaded from
`xiaowu0162/longmemeval-cleaned` 2026-09-29):**

| Quantity | Inherited | **Measured** |
|---|---|---|
| Contents that are evidence for ≥1 question **and** filler for ≥1 other | 281 | **0** |
| Questions spanned | 393 | **0** |
| Natural (m,t) cells from that construction | 679 | **0** |

### Positive control — the null is real, not a dead test

Per this project's own rule, a zero is worthless without a control. Mine fires:

- distinct session **contents** in the S split: **18,810**, of which **4,123 appear in more
  than one question** — so content *does* repeat across questions and the test *can* fire.
- distinct session **ids**: 19,195, of which **3,932 appear in >1 question**.

So the measurement discriminates. The zero is a property of the data.

### Root cause — evidence and filler are disjoint pools by construction

| | Evidence | Filler |
|---|---|---|
| distinct contents | 926 | 17,884 |
| distinct session ids | 940 | 18,255 |
| **content overlap** | **0** | |
| **id overlap** | **0** | |
| id namespace | **all `answer_*`** (948) | `sharegpt_*` (6,179), `ultrachat_*` (6,008), hashed ids |

Evidence sessions live in a separate `answer_*` namespace from ShareGPT/UltraChat filler.
**A session is never evidence for one question and filler for another.** The inherited
count appears to have matched on something other than session content — most plausibly it
counted *filler reuse across questions* (which is real: 4,123 contents recur) and labelled
it evidence/filler dual-role.

> **Consequence.** The free labelled matrix does not exist. This does **not** kill the
> project — it means the matrix must be **constructed**, which the benchmark explicitly
> supports and which MIT permits.

## 2. What V1 *does* give us — verified

`longmemeval_oracle.json` (15,388,478 bytes) and `longmemeval_s_cleaned.json`, both
measured:

| Property | Measured | Inherited | Match |
|---|---|---|---|
| Records | 500 | 500 | ✅ |
| `question_type` | temporal-reasoning 133, multi-session 133, knowledge-update 78, single-session-user 70, single-session-assistant 56, single-session-preference 30 | identical | ✅ |
| Answer type mix | 468 str / 32 int | 468/32 | ✅ |
| Abstention items (`_abs`) | 30 | 30 | ✅ |
| Sessions per question (S split) | min 38, median 48, max 62, **mean 47.7** | 38–62, mean 47.7 | ✅ |
| Evidence sessions per question | min 1, median 2, max 6 | — | new |
| Distinct evidence contents | 926 | — | new |
| Evidence memories serving >1 question | **22** | — | new |

Fields: `answer`, `answer_session_ids`, `haystack_dates`, `haystack_session_ids`,
`haystack_sessions`, `question`, `question_date`, `question_id`, `question_type`.

> **`answer_session_ids` is the asset.** It names, per question, exactly which sessions
> carry the evidence — so a single memory is individually addressable for ablation. **V2
> has no equivalent field.** That is why the pilot runs on V1.

## 3. ⚠️ The oracle split cannot be used for ablation

Measured: the oracle context is **100% evidence** — median 6,913 tokens of context, of
which median 6,913 is evidence.

Removing "the memory" from an oracle context removes the entire context. That is a
**no-context arm, not a memory ablation**, and ΔU measured that way answers a different
question.

> **Design consequence.** Each cell needs a context containing the target memory **plus a
> controlled set of other sessions**, so that removing one memory is a *local* change.
> Build contexts from the S split's filler pool at a fixed size.

## 4. LongMemEval-V2 — verified, and why it is not the pilot

Files in `/tmp/lmev2`, verified with the repo's own `checksums.sha256`:
`haystacks/lme_v2_small.json: OK`, `questions.jsonl: OK`, `DATA_CARD.md: OK`,
`SCHEMA.md: OK`. (One mismatch, `README.md`; 31 entries unreadable — files absent from
this partial download. **The two files the counts depend on both verify.**)

Reproduced exactly from the verified haystack file:

| Claim | Reproduced |
|---|---|
| (question, trajectory) cells | **45,100** ✅ |
| Questions | **451** — 240 web, 211 enterprise ✅ |
| Trajectories per question | **100/100/100** ✅ |
| Web questions per trajectory | **240/240/240** over 100 trajectories ✅ |
| Enterprise questions per trajectory | **211/211/211** over 100 trajectories ✅ |

**The grid is genuinely dense by construction.** But three blockers:

1. 🔴 **No answer-bearing evidence labels.** Every field across all 451 records:
   `answer, domain, environment, eval_function, id, image, question, question_type`. **No
   `answer_session_ids`, no evidence/gold/support field.** The 45,100 cells are an
   **unlabelled** grid — we would not know which trajectory to ablate.
2. 🔴 **Token cost.** ~164k tokens per trajectory (Sub-agent A, n=154) → the full matrix is
   ~4.4 × 10¹⁰ tokens.
3. ⚠️ **Leakage.** Gold answer found verbatim in ≥1 haystack trajectory for 41 of 55
   sampled questions (Sub-agent A; not independently re-run).

### One V2 asset worth keeping

**295 of 451 questions are scored deterministically** (Master Agent's own count):
`norm_phrase_set_match` 200, `norm_phrase_set_match_ordered` 26, `mc_choice_match` 68,
`mc_choice_set_match` 1. The other 156 are LLM-judged (`llm_abstention_checker` 128,
`llm_gotchas_checker` 28).

> Deterministic scoring **removes judge nondeterminism from ΔU entirely** for those cells —
> valuable when the noise floor is the thing being measured. (Sub-agent A reported 294;
> I derive 295 and use mine.)

⚠️ Also refuted by Sub-agent A: the inherited *"~1.4% of memories useful per task, ~46%
useful to at least one task"* is a misreading — 46% is a **domain share** (211/451) and
1.4% is *"questions require 1.4 trajectories to answer"*. **Strike it.**

## 5. Recommended design

**Pilot on V1**, constructing the matrix rather than harvesting it:

1. Take evidence sessions as candidate memories — **926 distinct, individually addressable
   via `answer_session_ids`**.
2. Build each cell's context as: the target memory + a **fixed-size, fixed-seed** sample of
   filler sessions, so ablation is a local change (§3).
3. Cross each memory against **multiple future tasks**: its own source question, plus
   questions from other episodes at controlled semantic distance (NEAR/MID/FAR by
   `Salesforce/SFR-Embedding-Mistral`, dim 4096, verified serving and deterministic).
4. The **22 memories that naturally serve 2 questions** are a small free validation set —
   naturally occurring multi-task memories against which the constructed matrix can be
   sanity-checked.
5. The **78 knowledge-update** questions are the harmful-memory arm: an old value
   superseded by a new one, so retrieving only the stale session yields a confident wrong
   answer.

**Honest statement for the paper:** the matrix is **constructed**, not harvested. The
*memories* are naturally occurring (real sessions written by the benchmark's user
simulator, not faults we planted), but the *pairing* of memory to future task is our
construction. That distinction must be stated plainly — it is the difference between
"natural base rate of sign flips among naturally co-occurring pairs" and "sign-flip rate
over a constructed task set", and only the second is what we can measure at this scale.

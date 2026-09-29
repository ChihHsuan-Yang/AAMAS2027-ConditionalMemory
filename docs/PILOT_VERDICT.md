# Pilot Verdict — the first ΔU measurement, and why it does not yet answer the question

**Run `g2_deltau_pilot`, 2026-09-29.** 1,918 real endpoint calls, 479 cells, 60 memories,
220 tasks, 2 replicates, 441.8 s at concurrency 16. Artifact:
`results/deltau_pilot/cells.jsonl`; summary `results/ledgers/g_deltau_pilot_summary.json`.

**Every number below was independently recomputed by the Master Agent from the row-level
artifact.** All reproduce exactly.

---

## 1. The three noise floors are all exactly 0.000 — and that is a real measurement

| floor | value | evidence | positive control |
|---|---|---|---|
| **F_exec** (ΔU scale, reference) | **0.000** | 0 of 479 cells disagree across 2 byte-identical replicates | **fires** (0.5098 on a planted defect) |
| **F_empty** | **0.000** | 774 distinct cache keys, 774 distinct latencies → 774 independent real calls returning identical text | independence proven by call count |
| **F_judge** | **0.000** | 0 disagreements over 1,916 re-scorings | **fires** (0.3175 on a planted defect) |

The reader is genuinely deterministic at temperature 0 (separately confirmed: 6/6
byte-identical on real 23k–27k-token prompts, cache disabled, concurrency 16).

> **Consequence: the PREREG §4 floor clause is vacuous.** Everything now rests on the CI
> clause — and with 2 always-agreeing replicates the CI is degenerate. `robust` and `naive`
> flip rates therefore coincide **mechanically, not substantively**, and the gap between
> them that §5 calls a contribution **is not measurable at 2 replicates.**

## 2. The headline numbers, recomputed

| quantity | value |
|---|---|
| cells | 479 (20 positive, **438 zero**, 21 negative) |
| accuracy WITH memory | **0.1712** (164/958) |
| accuracy WITHOUT memory | **0.1733** (166/958) |
| robust flip rate | **0.1333** [0.069, 0.242], denominator 60 |
| additive-null expectation | **0.9667** |
| excess over additive | **none**, p = 1.000 |
| variance shares | 🔴 **RETRACTED — UNMEASURED.** The printed 0.0000 was `dec.shares.get(c, 0.0)` over an **empty** `shares` dict: the REML fit did not converge and the moments fallback refused (*"balanced sub-design is 0x220; needs >= 2x2"*). See `docs/OFFICIAL_PROMPT_ARM.md` §4 and RESULTS_LEDGER row 54a. |

**Per Amendment A1.1, this data shows no evidence of memory × task interaction.**

## 3. 🔴 But the null is dominated by a floor effect, and must not be reported as-is

The Master Agent's own diagnostic:

> **376 of 479 cells (78.5%) have BOTH arms failing.**

A cell where the agent fails with *and* without the memory **cannot exhibit a memory
benefit**. It contributes a structural zero to ΔU regardless of whether the memory is
useful. 91.4% of cells are zero, and 78.5% of all cells are zero *for this reason*.

Restricting to cells where at least one arm ever succeeded:

| restriction | cells | memories with ≥2 such cells | flip rate |
|---|---:|---:|---:|
| all cells | 479 | 60 | 0.1333 |
| **cells capable of showing an effect** | **103 (21.5%)** | **33** | **0.2424** |

> The measured flip rate nearly **doubles** when cells that are structurally incapable of
> showing an effect are excluded. **This is not a finding yet** — the restriction is
> post-hoc and conditions on an outcome, which is exactly the selected-subgroup error this
> project has recorded before. It is reported as a diagnostic of *why the null is
> uninformative*, never as the result.

## 4. The root cause is identified, and it is fixable

`cells.py::SYSTEM` is a **hand-written prompt**, not the benchmark's official
`DOMAIN_SYSTEM_PROMPTS` (in `/tmp/lmev2/harness.py:71`). Verified by reading both.

The official prompt is materially different:

> *"Answer based on your memory of the environment. If you do not know the answer, output
> exactly `\boxed{UNKNOWN}`. **Do not guess. Never attempt to guess an answer if you are
> not sure.**"*

Ours invites an answer in all cases. Measured consequence: the official prompt abstains
**5/12**; ours abstains **0/958**. A model that always guesses on a hard retrieval task
lands near its guessing floor — which is what 17% accuracy is.

**ΔU remains internally valid** (both arms share the prompt, so the contrast is unbiased),
but two things follow:

1. **Absolute accuracy ~17% is not comparable to any published LongMemEval-V2 result**, and
   must not be presented as if it were.
2. **The near-total floor effect plausibly hides any real interaction**, so the null is
   uninformative rather than negative.

## 5. Decision

> 🔵 **SUPERSEDED 2026-09-29 by the run this section ordered.** The re-run was executed
> (`results/deltau_official/`, 1,920 real calls, 0 errors). **It did not remove the floor
> effect — it made it worse:** accuracy fell to 0.1146 WITH / 0.1208 WITHOUT and
> both-arms-fail rose to **402/480 = 83.75%**. The reasoning in §4 below — "a model that
> always guesses lands near its guessing floor, so the official prompt should lift it" —
> is **refuted**: the official prompt scores an abstention 0, identically to a wrong
> answer, so it converted **128 correct guesses into abstentions** and could only lower
> accuracy. Full result and diagnosis: `docs/OFFICIAL_PROMPT_ARM.md`.
> The text below is retained as written, not edited, because the retraction is the point.


**Re-run with the official `DOMAIN_SYSTEM_PROMPTS`.** ~1,920 calls, ~8 minutes.

Per the standing cluster/identity policy this is a **new experimental arm**, not a
backfill: `reader_prompt_version` is pinned experimental identity. The hand-written-prompt
arm is retained, not deleted, and the comparison between the two is itself informative
about prompt sensitivity.

**The kill criterion is NOT triggered.** It requires a null from an instrument capable of
detecting the effect. An instrument in which 78.5% of cells cannot move is not that
instrument. Applying the kill criterion here would be the *"a control that cannot exhibit
the behaviour cannot certify its absence"* error.

## 6. Four instrument defects found in this run

Three were in code the executing agent did **not** write — the reason cross-checking is
mandatory here.

1. **`F_judge = 0.1486` was an artifact.** `judge_floor` grouped byte-identical text
   *without the task*, so `\boxed{F}` correct for one question and wrong for another
   counted as scorer disagreement. All 18 groups spanned multiple tasks. **True rate
   0/1,916.** Fixed, with regression tests proven against a planted defect.
2. **"The endpoint is nondeterministic" was a position effect** (Master Agent's error).
3. **`select_filler` re-randomized on exclusion** (Master Agent's error).
4. **The embedding cap was bisected on unrepresentative text** (Master Agent's error).

The two run errors were a **reproducible** truncation (`reasoning_tokens=510` consuming the
512 budget), re-issued by hand twice — not flakiness.

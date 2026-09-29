# The Official-Prompt Arm — the decisive experiment, and what it decided

**Run `g2_deltau_pilot` / prompt arm `official`, 2026-09-29.** 1,920 real endpoint calls,
0 cache hits, **0 errors**, 474.8 s at concurrency 16, 60 memories, 220 tasks, 480 cells,
2 replicates, **960 rows written / 0 rejected**.
Artifacts: `results/deltau_official/cells.jsonl`; summaries in `results/ledgers/h_*.json`.

`docs/PILOT_VERDICT.md` §5 ordered this run on the reasoning that our hand-written prompt
made the reader always guess, and that a guessing model sits at its guessing floor. **That
reasoning is refuted by the run it ordered.**

---

## 1. Headline: the floor effect got WORSE

| | hand-written | **official** |
|---|---:|---:|
| accuracy **WITH** memory | 164/958 = 0.1712 [0.1487, 0.1963] | **110/960 = 0.1146** [0.0960, 0.1363] |
| accuracy **WITHOUT** memory | 166/958 = 0.1733 [0.1506, 0.1985] | **116/960 = 0.1208** [0.1017, 0.1430] |
| **both arms fail** | 376/479 = **78.50%** | **402/480 = 83.75%** [0.8018, 0.8678] |
| cells that *can* show an effect | 103 | **78** |
| abstentions WITH / WITHOUT | **0 / 0** | **378 / 390** of 960 |

Wilson 95% CIs. **Per H4, no further calls were spent** once both-arms-fail came back
above 50%.

## 2. The mechanism, measured on paired responses

Both arms cover 1,916 comparable responses. Hand-written reward → official reward:

| hand-written | official | official abstained | count |
|---:|---:|:--:|---:|
| 0 | 0 | no | 856 |
| 0 | 0 | **yes** | 636 |
| 0 | 1 | no | 94 |
| 1 | 0 | no | 70 |
| **1** | **0** | **yes** | **128** |
| 1 | 1 | no | 132 |

> **128 responses that were correct under the hand-written prompt became abstentions.**

`harness.py:1055` does `if row["is_unknown"]: score_bool = False` — **an abstention scores
0, identical to a wrong answer.** So suppressing guesses **cannot raise accuracy and can
only lower it**: every guess that happened to be right becomes a zero.

Paired McNemar (exact): hand-written 330/1916 correct, official 226/1916; discordant
198 vs 94; **p = 1.12e-09**. The official prompt is significantly **worse** on this
benchmark under this reader.

This was predicted from the scoring rule and logged at 195/1,920 calls, before the final
numbers existed (`subagent_H_report.md` §3).

## 3. Diagnosis (H4): the floor is READER CAPABILITY, not the pairing and not the prompt

### Cause 1 — "the memory rarely bears on the task": **ruled out as the main cause**

The `leakage_flag=True` subgroup is defined by the memory's **content** — its text
literally contains the gold answer string — **not by any outcome**. It is therefore *not*
a selected subgroup, unlike "cells where at least one arm succeeded".

| arm | WITH-arm accuracy, oracle-bearing | both-arms-fail there |
|---|---|---|
| hand-written | 70/306 = **0.2288** [0.1852, 0.2790] | 110/153 = **0.7190** [0.6430, 0.7841] |
| official | 44/308 = **0.1429** [0.1082, 0.1863] | 121/154 = **0.7857** [0.7144, 0.8432] |

**Even with the answer sitting in the context, the reader is right ~23% of the time, and
~72–79% of those cells still fail both arms.** An irrelevant pairing cannot explain a
floor that survives where relevance is guaranteed.

### Cause 2 — task difficulty / reader capability: **this is the binding constraint**

Official arm, by question type — `errors-gotchas` 0.056 WITH (36 cells, 94.4% both-fail),
`dynamic-environment` 0.090 (86.2%), `procedure` 0.110 (80.8%), `static-environment` 0.157
(81.7%). Every stratum sits at the floor, and the WITHOUT arm is equally low, so this is
not about the memory: **the reader cannot do this task at ~27k tokens of context.**

### Cause 3 — context design: a real but secondary gradient

WITH-accuracy by target position 0→6: 0.100, 0.070, 0.065, 0.132, 0.138, 0.138, 0.158
(recency, consistent with `docs/POSITION_EFFECT.md`). By similarity band: FAR 0.100 /
MID 0.106 / NEAR 0.138 — the expected ordering, all three at the floor. These modulate;
neither lifts the arm off the floor.

## 4. 🔴 Instrument defect: "variance shares all 0.0000" was never measured

`docs/PILOT_VERDICT.md` reported *"variance shares all 0.0000"* and RESULTS_LEDGER row 54
carried it as VERIFIED. Re-derived from
`results/deltau_pilot/analysis/03_variance_decomposition.json`:

```
converged: false · used_fallback: true · shares: {} · components: {} · total_variance: 0.0
flags: NON_CONVERGENCE, FIT_FAILED
extra.info.moments.reason: "balanced sub-design is 0x220; needs >= 2x2"
```

The reporting line is `dec.shares.get(c, 0.0)`, so **an empty dict prints `0.0000` for all
four components.** The shares were never estimated: the REML fit did not converge and the
method-of-moments fallback refused the design.

> "All shares are 0.0000" and "no share could be computed" are different statements, and
> only the second is true. `.get(c, 0.0)` turned a missing measurement into the strongest
> possible null on the paper's headline quantity.

**Retracted and relabelled UNMEASURED** (RESULTS_LEDGER row 54a). Not deleted: the
retraction is what prescribes the repair.

### Why it cannot fit, and what would fix it

Measured on the row artifacts (both arms share the pairing):

- tasks per memory: **8 / 8 / 8** (min / median / max);
- memories per task: **1 / 2 / 36**, over 220 tasks;
- only **127 of 220** tasks are shared by ≥2 memories.

The blocker is the **0×220 balanced sub-design** — a property of the *pairing*, not of the
sample size. `docs/POWER_ANALYSIS.md`'s "minimum 60 memories" is satisfied (60) and does
not help. More memories along this pairing will never produce a balanced rectangle;
**more tasks per memory, shared across memories, would** — which is what POWER_ANALYSIS §3
already recommends ("prefer widening the task axis"), now for a second, independent reason.

**Consequently no variance decomposition is reported for either arm.**

## 4b. 🔴 Two further defects BEHIND the empty `shares` dict

Section 4 said the shares were never estimated. Asking *why* turned up two bugs, not a
hard design.

### (a) A `ZeroDivisionError` killed the stage, and the script still exited 0

```
decomposition.py:595   f"{comps['interaction'] / fvar:.3g}x it. ..."
ZeroDivisionError: float division by zero
```

`fvar = exec_floor_sd ** 2` and `exec_floor_sd` is **F_exec = 0.0** — the *expected,
measured* value for a deterministic reader at temperature 0. PREREG §6 asks for the ratio
`interaction / F_exec²`, undefined at zero. **The pipeline crashed on its own correct
measurement**, wrote no artifact, and the wrapper reported success. (The truncated
traceback named line 588, which does no division; re-raising located the real site at
595.)

Fixed: a zero floor emits `EXEC_FLOOR_COMPARATOR_UNDEFINED`, reports the interaction
**variance**, and states that only the **ratio** is unavailable. Positive-controlled: a
non-zero floor still prints the ratio.

### (b) With the crash fixed, the model converges — and the fit is NOT IDENTIFIED

| arm | memory | task | interaction | residual | converged |
|---|---:|---:|---:|---:|:--:|
| official | 0.0819 | **0.4590691584279404** | **0.4590691584279404** | 2.82e-06 | True |
| hand-written | 0.0248 | **0.4875884835020202** | **0.4875884835020202** | 3.00e-06 | True |

Task and interaction are **exactly equal to 16 significant figures in both arms**, and
both ratios sit at `exp(12) = 162754.79141900392` — **the optimizer's clip ceiling**
(`np.clip(log_ratios, _LOG_FLOOR, 12.0)`).

The module documents that *"a boundary solution is not convergence"* and flags a component
driven to **zero** as `AT_BOUNDARY` — but **guarded only the lower boundary**. A ratio
pinned at the upper clip is equally unidentified, and it returned `converged=True` with a
tight bootstrap CI `[0.444, 0.468]`.

Fixed: `AT_UPPER_BOUNDARY` now fires, and `extra.info.components_at_upper_bound` records
which components. Both arms raise it for `task` and `interaction`.

### Convergence is seed-dependent; the boundary flag is not

Same rows, same estimator, seven seeds:

| seeds | converged | task share |
|---|---|---|
| 1, 2, 7, 42, 100 | **True** (5/7) | 0.4875884835020202, identical every time |
| 3, **20260929** (the project's configured seed) | **False** → fallback (2/7) | — |
| **all 7** | — | **`AT_UPPER_BOUNDARY: ['task','interaction']` every time** |

Whether this fit "converges" is a coin flip, and the configured seed lands on the failing
side — which is why the pilot saw an empty `shares` dict rather than a suspiciously tidy
0.4876/0.4876. **Read `AT_UPPER_BOUNDARY`, not `converged`.**

> **The decomposition remains UNMEASURED — now for a correctly diagnosed reason.** Task
> and interaction are **not separately identifiable** under this pairing. The likelihood
> itself now says so, rather than only a fallback's error message.

Both fixes are negative-controlled: reverting either guard makes the matching test fail.

## 5. Floors and flips — official arm

| floor | value | n_obs | positive control |
|---|---|---:|---|
| **F_exec** (reference F, ΔU scale) | **0.000000** [0, 0] | 960 | **fires**, 0.5093 |
| **F_empty** | **0.000000** [0, 0] | 960 | **fires**, 0.5445 |
| **F_judge** | **0.000000** [0, 0] | 3,486 re-scorings | **fires**, 0.2941 |

`F_empty`'s `WITHOUT_ARM_REUSED` guard fired on 254 groups and is a **false positive**,
re-verified for this arm rather than inherited from the pilot: **1,920 cache rows with
1,920 distinct key hashes; 960 WITHOUT rows with 960 distinct keys and 960 distinct
latencies; `real_endpoint_calls=1920, cache_hits=0`.** The outputs coincide because the
reader is deterministic and the WITHOUT prompt is identical across memories within a task
(in 90 of the 254 groups that identical text is an abstention).

| quantity | official | hand-written |
|---|---|---|
| robust flip rate (PRIMARY, balanced) | **0.13333** [0.06914, 0.24165], denom **60** | 0.13333, denom 60 |
| naive flip rate / gap | 0.13333 / **0.0000** | 0.13333 / 0.0000 |
| labels | 20 useful · 437 neutral · **23 harmful** | 20 · 438 · 21 |
| ΔU before labelling | **20 pos · 437 zero · 23 neg** | 20 · 438 · 21 |
| additive null | observed 0.13333 vs null **0.96667**, **p = 1.000** | same, p = 1.000 |

⚠️ `robust == naive` remains **MECHANICAL** (F = 0 makes the PREREG §4 floor clause
vacuous; 2 always-agreeing replicates give a degenerate CI). The gap is not measurable at
2 replicates, in either arm.

**No excess over the additive null in either arm.** And in both arms the null is
**uninformative**, because most cells cannot move.

## 6. What this means for the project

1. **The kill criterion is still NOT triggered** — and for the same reason as before. It
   requires a null from an instrument *capable* of detecting the effect. An instrument
   where 83.75% of cells cannot move is not that instrument. Two uninformative nulls are
   not one informative null.
2. **The prompt is not the lever.** It was the leading hypothesis and it has been tested
   properly and refuted. Do not re-run it in another wording.
3. **The reader is the lever.** The oracle-bearing subgroup says the ceiling is ~23% even
   when the answer is present in context. Options, in the order their cost suggests:
   raise `max_tokens` / `reasoning_effort` (the pilot already lost 2 cells to a
   reasoning-budget truncation); shrink the context (fewer filler units — K=6 puts the
   median at 26,891 tokens); or use a stronger reader. **Each needs its own small probe
   on the oracle-bearing subgroup before any full arm is spent** — that subgroup is the
   cheapest available capability test, and it is not outcome-selected.
4. **Absolute accuracy (11–17%) is not comparable to any published LongMemEval-V2 number**
   and must not be presented as if it were. Our context is 6 filler page-visits, not the
   benchmark's haystack.
5. **Prompt sensitivity is itself a reportable result**: on this benchmark, swapping to the
   benchmark's own prompt moves accuracy by −5.4 points (paired, p = 1.12e-09), entirely
   through abstention. Under a scoring rule that gives abstention and error the same 0,
   an honesty instruction is a pure accuracy cost.

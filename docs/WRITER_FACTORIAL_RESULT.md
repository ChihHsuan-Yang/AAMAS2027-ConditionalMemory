# Writer × Reader — does it matter which model wrote the memory?

**Generated from `results/ledgers/writer_factorial/writer_factorial_analysis.json` on 2026-10-01T06:22:16.518455+00:00.** Every number here is read out of that artifact at generation time by `scripts/w5_factorial_report.py`; none is typed from recall, so this document cannot drift from the data.

Pre-registered in `docs/WRITER_FACTORIAL_PRECOMMITMENT.md`, written **before any Gemma memory was written** and before any writer-Gemma cell was run.

## The answer, in one paragraph

**It does not matter much which model wrote the memory, and a memory is not worth more to the family that wrote it.** On the cells interpretable under all four writer × reader combinations, **every one of the four pre-registered contrasts spans zero** — writer, reader, same-family and interaction, on both Summary and Structured.

- **summary** (274 matched cells): writer effect -0.0164 [-0.0380, +0.0035], same-family -0.0091 [-0.0308, +0.0121].
- **structured** (268 matched cells): writer effect +0.0112 [-0.0137, +0.0360], same-family +0.0037 [-0.0147, +0.0226].

**These nulls are informative rather than merely underpowered, and that is worth separating.** The intervals are narrow. The largest effect still compatible with the data is **0.0226 to 0.0380** in absolute ΔU for the writer and same-family contrasts (**0.0617** including the wider interaction). For scale, the reader effect this project *did* detect on `raw` is **+0.1268** — about **3.3×** the largest writer or same-family effect these intervals leave room for. So this is not "we could not tell"; it is "an effect of the size this project already measures elsewhere would have been visible here."

That said, **the per-contrast contributor counts are small** (33–51 non-zero cells of 268–274), and `docs/PAIRED_POWER.md` warns that power depends on their spread and not their count. The interval widths above are the honest statement of what is excluded; read them, not the point estimates.

> ⚠️ The **+0.1268** comparison point is on `raw`, which is **not in this factorial** and is a READER effect, not a writer one. It is used here only as a scale reference for what this measurement apparatus has been able to detect — not as a quantity being compared against.

**The direction a reader should take from this:** memory utility here looks like a property of the **experience** being compressed, not of the **compressor**. That is consistent with the project's existing and stronger finding that `raw` — written by **no model at all** — is the best representation under both readers. A same-family advantage was a pre-registered possible outcome and it did not appear.

🔴 **Two limits on that sentence, both structural.** First, `raw` has no writer and is **not in this factorial**, so none of this speaks to the project's strongest representation. Second, two models are a 2×2, not a population: "same-family" here means these two specific checkpoints on one cluster, and nothing is established about model families in general.

## 🔴 Read this first: a control fired, and it changed the design

The first execution compared today's writer-Gemma arms against the **published** writer-gpt-oss arms from 2026-09-30. A pre-registered control caught that this was invalid.

The **WITHOUT** arm contains *no memory at all*. A change of writer cannot reach it, and F-GATE 4 verified its request bytes are identical (500/500 stored context hashes match). It should therefore have been identical. It was not:

| comparison | cells | WITHOUT-arm output text differs | WITHOUT-arm reward differs | mean reward change |
|---|---:|---:|---:|---:|
| published 2026-09-30 → today, reader gpt-oss | 1124 | 554 | 82 | -0.0303 |
| published 2026-09-30 → today, reader Gemma | 1124 | 0 | 0 | +0.0000 |

**`gpt-oss-120b` is deterministic within a session and not across sessions.** 554 of 1124 byte-identical requests returned different text a day later, moving the no-memory baseline by -0.0303. That is **the same order as the effect being measured**, so a writer contrast drawn across the two sessions would have confounded WRITER with SESSION and there would have been no way to tell which produced the number.

**What was done:** the gpt-oss writer arms were **re-run today**, issuing byte-identical requests — F-GATE 5 verified 1124/1124 WITH-arm requests match the published ones exactly. **All four arms in this document come from one session.** The published arms are kept above as a drift *measurement*, never as a comparator.

> This is this project's defect #21 — *a determinism probe measured WITHIN-session repeatability and was read as CROSS-session reproducibility* — surfacing in a new place. The control that caught it cost nothing: it checks a quantity that is **zero by construction** unless something is wrong.

## First: does the published reader effect survive?

The reader effect under writer gpt-oss is the **same contrast** the published reader arm reports (`docs/READER_TRANSFER_RESULT.md`). **Two things differ from the published figure, not one**: the stricter 4-way matched set, *and* a fresh session (see above). So this is a re-**measurement**, not a re-computation, and it is reported before anything else.

| representation | 4-way matched n | ΔU diff (Gemma − gpt-oss) | 95% CI, task-clustered | excludes 0 | published n | published diff | published excludes 0 | **pre-committed verdict** |
|---|---:|---:|---|---|---:|---:|---|---|
| summary | 274 | -0.0036 | [-0.0458, +0.0433] | no | 274 | +0.0036 | no | **FAILS** |
| structured | 268 | -0.0075 | [-0.0547, +0.0418] | no | 269 | +0.0112 | no | **FAILS** |

🔴 **THE PRE-COMMITTED REPLICATION CRITERION FAILS ON BOTH REPRESENTATIONS, and it is reported as failed.** The precommitment required *same sign AND same significance verdict*. The significance verdict matches on both (**both span zero, under both bases**); the **sign flips**.

Look at what flipped:

| representation | published | today | difference | both span zero |
|---|---:|---:|---:|---|
| summary | +0.0036 | -0.0036 | 0.0073 | **yes** |
| structured | +0.0112 | -0.0075 | 0.0186 | **yes** |

**A sign test on a quantity whose true value is near zero is a bad instrument.** On summary the two estimates are **+0.0036** and **-0.0036**: the same null, differing by 0.0073, and the pre-committed rule calls that a replication failure. That is a defect in the criterion, not a finding about the data — but **the criterion is reported as failed anyway**, because a rule rewritten after it fires is not a rule.

A **second criterion, added after seeing this and labelled as such**, asks what the sign test was meant to ask — *are the two estimates compatible?* — and does not degrade as the estimand approaches zero:

| representation | published mean inside today's CI | today's mean inside published CI | compatible |
|---|---|---|---|
| summary | **yes** | **yes** | **yes** |
| structured | **yes** | **yes** | **yes** |

**Each estimate falls inside the other's interval, on both representations.** The honest summary: *the published summary and structured reader effects were nulls, and they are nulls again here; the pre-committed sign criterion was not a good test of that and said so by failing.*

⚠️ **The published arm's one non-null reader effect was on `raw` (+0.1268, excluding zero), and `raw` is not in this factorial at all** — it has no writer axis. So this table re-tests the published arm's **two null rows only**, and agreement between two nulls is weak evidence. It is **not** a replication of the reader-transfer headline.

> ⚠️ **`raw` is not in this factorial and cannot be.** Raw is a deterministic span with **zero model calls**, so "writer gpt-oss raw" and "writer Gemma raw" are the *same bytes*. There is no writer axis for raw. The published reader arm's headline (+0.1268 on raw) is therefore **not** a row in this table — the two representations here are the two that have a writer.

## The 2×2

Mean per-cell ΔU under each writer × reader combination, on the cells interpretable under **all four**. Each row of each table describes the same cells, so the four numbers are comparable.

### summary — 274 matched cells, 124 tasks, 60 memories

| | reader gpt-oss | reader Gemma |
|---|---:|---:|
| **writer gpt-oss** | +0.0584 | +0.0547 |
| **writer Gemma** | +0.0511 | +0.0292 |

Non-zero contributors behind each cell (`docs/ZERO_CONTRIBUTORS.md` — a cell that is 0 under every arm is a **structural** zero, not a measurement of agreement):

| arm | ΔU | 95% CI | non-zero contributors / nominal | conditional mean |
|---|---:|---|---:|---:|
| writer gpt-oss x reader gpt-oss | +0.0584 | [+0.0219, +0.0985] | 30 / 274 | +0.5333 |
| writer gpt-oss x reader Gemma | +0.0547 | [+0.0255, +0.0876] | 19 / 274 | +0.7895 |
| writer Gemma x reader gpt-oss | +0.0511 | [+0.0146, +0.0876] | 28 / 274 | +0.5000 |
| writer Gemma x reader Gemma | +0.0292 | [+0.0036, +0.0584] | 14 / 274 | +0.5714 |

### structured — 268 matched cells, 121 tasks, 57 memories

| | reader gpt-oss | reader Gemma |
|---|---:|---:|
| **writer gpt-oss** | +0.0373 | +0.0299 |
| **writer Gemma** | +0.0448 | +0.0448 |

Non-zero contributors behind each cell (`docs/ZERO_CONTRIBUTORS.md` — a cell that is 0 under every arm is a **structural** zero, not a measurement of agreement):

| arm | ΔU | 95% CI | non-zero contributors / nominal | conditional mean |
|---|---:|---|---:|---:|
| writer gpt-oss x reader gpt-oss | +0.0373 | [+0.0037, +0.0746] | 24 / 268 | +0.4167 |
| writer gpt-oss x reader Gemma | +0.0299 | [+0.0075, +0.0560] | 12 / 268 | +0.6667 |
| writer Gemma x reader gpt-oss | +0.0448 | [+0.0075, +0.0858] | 30 / 268 | +0.4000 |
| writer Gemma x reader Gemma | +0.0448 | [+0.0187, +0.0746] | 16 / 268 | +0.7500 |

## The four contrasts

All intervals are **task-clustered** bootstrap (10,000 resamples), because cells repeat within tasks and a cell-level interval would treat repeated views of one task as independent draws. The task-clustered interval governs.

### summary

| contrast | n cells | non-zero | estimate | 95% CI, task-clustered | excludes 0 |
|---|---:|---:|---:|---|---|
| **WRITER** main effect (Gemma − gpt-oss writer) | 274 | 35 | -0.0164 | [-0.0380, +0.0035] | no |
|   · writer effect, reader gpt-oss | 274 | 28 | -0.0073 | [-0.0409, +0.0245] | no |
|   · writer effect, reader Gemma | 274 | 15 | -0.0255 | [-0.0536, +0.0000] | no |
| **READER** main effect (Gemma − gpt-oss reader) | 274 | 45 | -0.0128 | [-0.0548, +0.0310] | no |
|   · reader effect, writer gpt-oss *(= the published arm)* | 274 | 29 | -0.0036 | [-0.0458, +0.0433] | no |
|   · reader effect, writer Gemma | 274 | 32 | -0.0219 | [-0.0747, +0.0280] | no |
| **SAME-FAMILY** (oss/oss, gem/gem) − (oss/gem, gem/oss) | 274 | 33 | -0.0091 | [-0.0308, +0.0121] | no |
| **INTERACTION** | 274 | 33 | -0.0182 | [-0.0617, +0.0242] | no |

### structured

| contrast | n cells | non-zero | estimate | 95% CI, task-clustered | excludes 0 |
|---|---:|---:|---:|---|---|
| **WRITER** main effect (Gemma − gpt-oss writer) | 268 | 36 | +0.0112 | [-0.0137, +0.0360] | no |
|   · writer effect, reader gpt-oss | 268 | 26 | +0.0075 | [-0.0279, +0.0445] | no |
|   · writer effect, reader Gemma | 268 | 12 | +0.0149 | [-0.0109, +0.0400] | no |
| **READER** main effect (Gemma − gpt-oss reader) | 268 | 51 | -0.0037 | [-0.0496, +0.0462] | no |
|   · reader effect, writer gpt-oss *(= the published arm)* | 268 | 31 | -0.0075 | [-0.0547, +0.0418] | no |
|   · reader effect, writer Gemma | 268 | 38 | +0.0000 | [-0.0543, +0.0549] | no |
| **SAME-FAMILY** (oss/oss, gem/gem) − (oss/gem, gem/oss) | 268 | 34 | +0.0037 | [-0.0147, +0.0226] | no |
| **INTERACTION** | 268 | 34 | +0.0075 | [-0.0293, +0.0451] | no |

🔴 **SAME-FAMILY and INTERACTION are one quantity, not two.** SAME-FAMILY ≡ **+**½ × INTERACTION by construction; verified on these numbers (max absolute difference 0.00e+00, holds=True). They are reported together with two readings and must **never** be cited as two routes that agree — that would be this project's own "two routes converged" defect (`docs/DEFECT_REGISTER.md`).

> ⚠️ **An erratum against this project's own precommitment, recorded rather than smoothed.** `docs/WRITER_FACTORIAL_PRECOMMITMENT.md` stated this identity as "−½ × INTERACTION". **That sign is wrong**; it is +½. Checked against the precommitted minus sign on these same numbers, the residual is 2.0000 (holds=False). **Neither quantity's definition changed** — both are computed exactly as pre-registered; only the prose claim about their relationship was wrong. It was caught by the constructed-ground-truth control below, which predicts same-family from a KNOWN interaction and disagreed with the document. A stated identity that is believed rather than machine-checked is exactly the shape this register keeps catching.

## Reading the result

**summary.** The writer main effect is -0.0164 [-0.0380, +0.0035], which spans zero on 35 non-zero contributors of 274. Same-family is -0.0091 [-0.0308, +0.0121] (spans zero), and the interaction is -0.0182 [-0.0617, +0.0242] (spans zero).

**structured.** The writer main effect is +0.0112 [-0.0137, +0.0360], which spans zero on 36 non-zero contributors of 268. Same-family is +0.0037 [-0.0147, +0.0226] (spans zero), and the interaction is +0.0075 [-0.0293, +0.0451] (spans zero).

### These nulls are defended: the pipeline was made to find a planted effect

Four contrasts spanning zero would mean nothing from an analysis never shown to detect anything. The constructed-array control further down exercises only the arithmetic — not the join, the matched set, the replicate collapse or the bootstrap. So an effect was **planted in a copy of the real rows** and the **full pipeline** was required to find it.

| plant | rows altered | contrast | result | must |
|---|---:|---|---:|---|
| **A** — raise the Gemma-writer arm under *both* readers | 731 | WRITER, summary | +0.3139 | **fires** |
| **A** — raise the Gemma-writer arm under *both* readers | 731 | WRITER, structured | +0.3479 | **fires** |
| **A** (same plant) | — | SAME-FAMILY, summary | +0.0036 | correctly **stays null** |
| **A** (same plant) | — | SAME-FAMILY, structured | +0.0159 | correctly **stays null** |
| **B** — raise *only* the Gemma/Gemma cell | 438 | SAME-FAMILY, summary | +0.1907 | **fires** |
| **B** — raise *only* the Gemma/Gemma cell | 438 | SAME-FAMILY, structured | +0.2080 | **fires** |

**Plant B is the one that matters.** Same-family is the contrast this experiment exists to measure, and plant A leaves it null — correctly, since plant A contains no same-family effect — so plant A alone could never certify it. Under plant B it fires on both representations (**True**).

Plant B also settles the sign erratum on **real data with a real effect**: same-family comes out exactly **+½ × interaction** (**True**). On the actual results both quantities are ~0, where +½ and −½ are nearly indistinguishable — only a large planted effect can tell them apart.

**ALL_SENSITIVITY_CONTROLS_PASS = True** (`results/ledgers/writer_factorial/sensitivity_controls.json`). The four nulls above are therefore measurements, not an instrument that cannot move.

🔴 **A zero-spanning interval here is not proof of no effect.** `docs/PAIRED_POWER.md`: power depends on the spread among contributors, not their count alone. Read the non-zero contributor counts in the tables above **before** reading any interval; where they are small the honest reading is *underpowered*, not *no difference*.

## The most obvious mechanism: how much each writer wrote

A writer effect could be about compression *quality* or simply about compression *amount*. The lengths are reported so the two are not confused.

| representation | gpt-oss mean tokens | Gemma mean tokens | Gemma / gpt-oss |
|---|---:|---:|---:|
| summary | 324.9891 | 150.6752 | 0.4636 |
| structured | 238.0485 | 179.4813 | 0.7540 |

## The control that makes the writer contrast interpretable

The WITHOUT arm contains **no memory**, so a change of writer cannot move it. If it did, something other than the memory differed between the arms — a defect, not a finding.

| representation | reader | mean reward WITH, writer gpt-oss | writer Gemma | mean reward WITHOUT, writer gpt-oss | writer Gemma | WITHOUT-arm change |
|---|---|---:|---:|---:|---:|---:|
| summary | gpt-oss | 0.1350 | 0.1277 | 0.0766 | 0.0766 | +0.0000 |
| summary | Gemma | 0.0949 | 0.0693 | 0.0401 | 0.0401 | +0.0000 |
| structured | gpt-oss | 0.1119 | 0.1194 | 0.0746 | 0.0746 | +0.0000 |
| structured | Gemma | 0.0634 | 0.0784 | 0.0336 | 0.0336 | +0.0000 |

Measured directly on the rows, **both writer arms from the same session**:

| reader | cells compared | WITHOUT-arm reward identical | differing | WITHOUT-arm output text identical | holds |
|---|---:|---:|---:|---:|---|
| gptoss | 1124 | 1122 | 0 | 1124 | **yes** |
| gemma | 1124 | 1086 | 0 | 1124 | **yes** |

**Holds on both readers: True.** This is the control that failed on the first, cross-session attempt and is the reason the gpt-oss arms were re-run. It is a quantity that is zero by construction unless something is wrong, which is exactly what makes it worth checking.

## The malformed-structured rate, per writer — a result, not a problem fixed

No repair, no fallback to summary, no retry. A malformed structure is recorded with its error code and the rate is reported.

| writer | representation | malformed / all writes | malformed / writes that FINISHED | error codes |
|---|---|---:|---:|---|
| Gemma | summary | 0 / 60 | 0 / 60 | — |
| Gemma | structured | 0 / 60 | 0 / 60 | — |
| gpt-oss | summary | 0 / 60 | 0 / 53 | — |
| gpt-oss | structured | 3 / 60 | 0 / 57 | {'structured_malformed_json': 3} |

> **Two denominators, because they answer different questions and disagree.** A write cut off at the token cap is a different failure from a write the model finished and got wrong.

**Truncation at the write cap** (`max_tokens=512`): Gemma {'summary': 0, 'structured': 0}. gpt-oss on the same segments: 7 summary and 3 structured (the 3 structured are exactly its 3 malformed writes). The guard is deliberately **off** on the write pass for both writers — see the precommitment; turning it on for Gemma alone would make the two writer arms differ in their admission rule as well as their model.

🔴 **A rate of 0/60 from a validator never shown to reject is not a measurement.** The validator was made to fire on four planted defects (all rejected: **True**), to accept a valid object (**True**), and was replayed against the 3 gpt-oss outputs it already rejected, reproducing the recorded code in every case (**True**).

## A side effect of Gemma's compression: two episodes, one memory

`memory_id` and `row_id` are **content hashes**. If a writer compresses two different source segments to byte-identical text, those ids collide — and the schema validator reports `duplicate_row_id`. That happened, and it is a property of the **writer**, not a plumbing fault:

| writer | representation | memories | distinct texts | texts shared by >1 segment | segments involved |
|---|---|---:|---:|---:|---:|
| Gemma | summary | 60 | 59 | 1 | 2 |
| Gemma | structured | 60 | 60 | 0 | 0 |
| gpt-oss | summary | 60 | 60 | 0 | 0 |
| gpt-oss | structured | 57 | 57 | 0 | 0 |

The collapsed pair is `06c70de4:13-14` and `06c70de4:17-18` — two distinct segments of the same episode that Gemma rendered as the *same* 68-token summary, where gpt-oss produced 524- and 457-token summaries that differ. **Gemma writes roughly half the tokens, and at that compression two different episodes can land on the same words.**

**It does not move any number here**, and that is checked rather than assumed: the analysis joins on `(memory_unit_locator, future_task_id)`, which is **positional** and cannot collide, so the affected cells stay separate — the matched summary set is 274, not 272. It *would* have corrupted any analysis joining on `memory_id`, which is precisely why this project's join rule forbids that.

> This is a real cost of aggressive compression that the ΔU contrast cannot see: a memory store built on content-addressed ids would silently **merge two experiences into one**. It is reported here because a reviewer asking "what does the terser writer lose?" would not find it in any of the contrasts above.

## Formation cost — two currencies, never pooled

| writer | representation | calls | mean input tokens | mean output tokens | mean latency (s) | reasoning tokens |
|---|---|---:|---:|---:|---:|---:|
| Gemma | summary | 60 | 9684.5667 | 168.0667 | 6.2950 | **None** (absent) |
| Gemma | structured | 60 | 10304.8833 | 201.3667 | 6.5567 | **None** (absent) |
| gpt-oss | summary | 60 | 7377.2500 | 347.2167 | 3.2915 | 1960 |
| gpt-oss | structured | 60 | 7571.2500 | 346.4500 | 3.2987 | 6483 |

🔴 **`reasoning_tokens` is `None` on every Gemma row, and that is an ABSENCE, not a zero.** metis/`gemma-4-31B-it` returns no `completion_tokens_details` at all, while `gpt-oss-120b` on the same cluster does. Writing `0` would assert a measurement nobody made. **A total-token cost comparison between the two writers is therefore not apples-to-apples** and must not be presented as one.

Latencies are wall-clock under this project's own concurrency on a shared gateway. They are a record of what this run cost, **not** a throughput benchmark of either model.

## The quantity the paper reports, under all four arms

`docs/REPRESENTATION_RESULT.md` reports the **within-memory BEARING − MATCHED_CONTROL** contrast. Under each arm, on the matched cells:

| representation | arm | memories | B − MC | 95% CI | non-zero contributors |
|---|---|---:|---:|---|---:|
| summary | writer gpt-oss x reader gpt-oss | 59 | +0.1232 | [+0.0306, +0.2218] | 20 |
| summary | writer gpt-oss x reader Gemma | 59 | +0.0956 | [+0.0144, +0.1791] | 17 |
| summary | writer Gemma x reader gpt-oss | 59 | +0.0644 | [-0.0224, +0.1577] | 18 |
| summary | writer Gemma x reader Gemma | 59 | +0.0784 | [+0.0282, +0.1349] | 11 |
| structured | writer gpt-oss x reader gpt-oss | 56 | +0.0294 | [-0.0359, +0.1048] | 17 |
| structured | writer gpt-oss x reader Gemma | 56 | +0.0389 | [-0.0228, +0.1030] | 12 |
| structured | writer Gemma x reader gpt-oss | 56 | +0.0888 | [+0.0159, +0.1687] | 17 |
| structured | writer Gemma x reader Gemma | 56 | +0.0900 | [+0.0171, +0.1625] | 15 |

## Harm on BEARING cells, under all four arms

| representation | BEARING cells | oss/oss | oss/gem | gem/oss | gem/gem |
|---|---:|---:|---:|---:|---:|
| summary | 132 | 2 | 0 | 4 | 0 |
| structured | 131 | 3 | 0 | 3 | 0 |

> A **count** of negative cells is not a harm claim. The pre-registered label rule requires a cell's CI to exclude zero *and* its magnitude to clear the measured execution floor. This table shows the raw direction only.

## Coverage, and what is NOT covered

| representation | oss/oss | oss/gem | gem/oss | gem/gem | **matched, all four** | union |
|---|---:|---:|---:|---:|---:|---:|
| summary | 285 | 274 | 285 | 277 | **274** | 285 |
| structured | 276 | 269 | 277 | 269 | **268** | 277 |

Loss balance across strata — a loss falling mainly on BEARING would bias the B − MC contrast even though the loss rule is non-outcome-based:

| representation | lost from the matched set | by stratum | kept by stratum |
|---|---:|---|---|
| summary | 11 | {'BEARING': 7, 'MATCHED_CONTROL': 4} | {'BEARING': 132, 'MATCHED_CONTROL': 142} |
| structured | 9 | {'BEARING': 4, 'MATCHED_CONTROL': 5} | {'BEARING': 131, 'MATCHED_CONTROL': 137} |

**Not covered**, stated rather than glossed:

- **`raw`.** It has no writer axis (zero model calls), so it is excluded by construction, not by choice. The factorial speaks to the two model-written representations only — and raw is the strongest representation under both readers, so **the factorial does not speak to the project's headline representation at all.**
- the cells excluded before any call: {'summary': 0, 'structured': 8}. Every structured exclusion is a cell whose **gpt-oss** structured write failed in the published run — a property of a write pass that ran before any model in this factorial read anything, and therefore non-outcome-based. Gemma's own structured writes all succeeded.
- the **872 RANDOM-stratum cells** and the rest of the 15,112-pair frozen universe. This factorial covers the **representation sub-universe**, the basis `docs/REPRESENTATION_RESULT.md` reports.
- the **156 LLM-judged questions**: `F_judge` is unmeasured, so they are a separate scorer stratum under `docs/COVERAGE_MANIFEST.md` and are not pooled.
- **other model families.** Two models is a 2×2, not a population. "Same-family" here means these two specific checkpoints.

## Controls — every null defended

| control | result |
|---|---|
| W-GATE 2: both writers saw byte-identical segments | 60 matched, 0 mismatched |
| W-GATE 2 can FAIL (one byte planted in a segment) | aborts, exit 1 |
| W-GATE 3: identical prompt version digests | True (summary), True (structured) |
| W-GATE 4: the gpt-oss memories file was not touched | True |
| writer blindness: all four barriers made to FIRE | all_fired=True |
| [writer Gemma] F-GATE 3: per-cell target position + filler == the gpt-oss row | {'matched': 562, 'mismatched': 0} |
| [writer Gemma] F-GATE 4: WITHOUT-arm request bytes identical | {'matched': 1124, 'mismatched': 0, 'no_published_reference': 0} |
| [writer Gemma] F-GATE 5, direction **MUST_DIFFER** | {'differs_from_published': 1124, 'matches_published': 0, 'no_published_reference': 0} |
| [writer gpt-oss re-run] F-GATE 3: per-cell target position + filler == the gpt-oss row | {'matched': 562, 'mismatched': 0} |
| [writer gpt-oss re-run] F-GATE 4: WITHOUT-arm request bytes identical | {'matched': 1124, 'mismatched': 0, 'no_published_reference': 0} |
| [writer gpt-oss re-run] F-GATE 5, direction **MUST_MATCH** | {'matches_published': 1124, 'differs_from_published': 0, 'no_published_reference': 0} |
| F-GATE 3 can FAIL (one filler unit dropped) | aborts, exit 1 |
| within a writer, both readers see identical memory text | oss 562/562, gem 562/562 |
| across writers, the memory text DIFFERS (else it is A/A) | 562/562 differ |
| the WRONG joins are RUN and shown to fail | `condition_id` → **0 rows**; `memory_id` → **0 rows**; correct locator+task key → 2 rows |
| the four contrast estimators recover KNOWN values | fires=True (writer/oss 0.0, writer/gem 0.5, interaction 0.5, same-family 0.25) |
| `F_exec` estimator can return non-zero (flip one replicate in 144 cells) | 0.5098, fires=True |
| A/A determinism, gemma_4_31B_it (byte-identical requests, separate calls) | 244/244 identical |
| A/A determinism, gpt_oss_120b (byte-identical requests, separate calls) | 248/248 identical |
| cache separation across writers, **positive control first** | published key HIT → writer-Gemma-shaped key MISS → published key in the factorial cache MISS; VERDICT=True |
| truncations REFUSED by the three-observable guard | 72 rows |
| no truncated response was ever scored | 0 rows carry an error code AND a non-null delta (must be 0) |
| schema validation, `results/writer_factorial/factorial_cells_gemma.jsonl` | 12 errors ({'duplicate_row_id': 8, 'duplicate_replicate_in_cell': 4}), 2 warnings |
| schema validation, `results/writer_factorial/factorial_cells_gptoss.jsonl` | 0 errors (none), 2 warnings |

> ⚠️ **Both error classes on the writer-Gemma file (8 `duplicate_row_id` + 4 `duplicate_replicate_in_cell`) have ONE cause: the segment collapse above — not a double write.** 2248 rows carry 2248 distinct (representation, locator, task, replicate, reader) tuples, so no row is repeated; they yield 2240 distinct ids because `row_id` *and* `cell_id` both derive from `memory_id`, a content hash, and two segments share one Gemma memory text. Affected locators: `06c70de4:13-14`, `06c70de4:17-18`. The rows are real and separate, and the locator-based join is immune — verified, the matched summary set is 274 and not 272.

> 🔴 **Read the cache truncation counts correctly.** `P1Client` raises the truncation guard **before** it writes to the cache, so a refused truncation is never cached at all. "0 truncations in the cache" is therefore true **by construction** on a strict arm and is *not* evidence that none occurred. The number that shows how often truncation DID happen is the refused-row count above (72); the one that shows none was scored is the row beneath it. An absent check must never read as a passing one.

**ALL_CONTROLS_PASS = True** (`results/ledgers/writer_factorial/writer_factorial_controls.json`).

## Unscoreable cells — `reward = None`, never 0.0

| arm : representation | cells | cells with a null replicate | cells all null |
|---|---:|---:|---:|
| gem/gem:structured | 277 | 8 | 8 |
| gem/gem:summary | 285 | 8 | 8 |
| gem/oss:structured | 277 | 0 | 0 |
| gem/oss:summary | 285 | 0 | 0 |
| oss/gem:structured | 277 | 8 | 8 |
| oss/gem:summary | 285 | 11 | 11 |
| oss/oss:structured | 277 | 1 | 1 |
| oss/oss:summary | 285 | 0 | 0 |

Error codes: {'oss/oss:structured': {'empty_output_finish_length': 2}, 'oss/gem:summary': {'truncated_nonempty_at_token_budget': 22}, 'oss/gem:structured': {'truncated_nonempty_at_token_budget': 16}, 'gem/gem:summary': {'truncated_nonempty_at_token_budget': 16}, 'gem/gem:structured': {'truncated_nonempty_at_token_budget': 16}}.

A `None` means **could not be scored** and is excluded from every mean with its count reported. Coercing it to 0.0 would read as a wrong answer, drive ΔU negative, and manufacture a harmful memory.

## Where the artifacts are

`results/**` is gitignored except `results/ledgers/**`, so every number above is read from a **tracked** file.

| artifact | path | tracked? |
|---|---|---|
| the 2×2 analysis every number here is read from | `results/ledgers/writer_factorial/writer_factorial_analysis.json` | **yes** |
| controls | `results/ledgers/writer_factorial/writer_factorial_controls.json` | **yes** |
| schema validation of both row files | `results/ledgers/writer_factorial/schema_validation.json` | **yes** |
| sensitivity controls (planted effects) | `results/ledgers/writer_factorial/sensitivity_controls.json` | **yes** |
| the Gemma write pass: gates, cost, malformed rate | `results/ledgers/writer_factorial/write_summary_gemma.json` | **yes** |
| the writer-Gemma run: gates, coverage, artifact checks | `results/ledgers/writer_factorial/factorial_summary_gemma.json` | **yes** |
| the writer-gpt-oss re-run: gates, coverage, artifact checks | `results/ledgers/writer_factorial/factorial_summary_gptoss.json` | **yes** |
| the Gemma-written memories | `results/writer_factorial/memories_gemma.jsonl` | no |
| the writer-Gemma result rows | `results/writer_factorial/factorial_cells_gemma.jsonl` | no |
| the writer-gpt-oss result rows (re-run, same session) | `results/writer_factorial/factorial_cells_gptoss.jsonl` | no |
| the published gpt-oss writer arm, **unmodified** | `results/repr_scaleup/memories.jsonl` + `cells.jsonl` | no |

## Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9

$PY scripts/w1_write_gemma_memories.py --dry-run                      # gates only
$PY scripts/w1_write_gemma_memories.py --dry-run --plant-segment-defect  # W-GATE 2 must abort
$PY scripts/w1_write_gemma_memories.py                                # 120 write calls
$PY scripts/w2_run_factorial.py --writer gemma --dry-run              # gates only
$PY scripts/w2_run_factorial.py --writer gemma --dry-run --plant-position-defect  # F-GATE 3 must abort
$PY scripts/w2_run_factorial.py --writer gemma                        # writer-Gemma arms
$PY scripts/w2_run_factorial.py --writer gptoss                       # writer-gpt-oss arms,
                                                                      #   SAME SESSION -- see the drift section
$PY scripts/w4_factorial_controls.py                                  # controls
$PY scripts/w3_analyze_factorial.py                                   # analysis
$PY scripts/w6_sensitivity_control.py                                 # plant an effect,
                                                                      #   require detection
$PY scripts/w5_factorial_report.py                                    # this document
```

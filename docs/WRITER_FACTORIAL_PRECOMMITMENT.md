# Writer × Reader factorial — PRECOMMITMENT

**Written 2026-10-01 by SA-WRITER, BEFORE any Gemma WRITE call was issued
against a design memory and before any writer-Gemma reader cell was run.**
Nothing below was chosen after seeing a Gemma-written memory or an outcome
under one. The only Gemma write calls that existed when this was written are
**two synthetic plumbing probes** on a hand-made segment that is not in the
corpus (`synthetic:0-3`); they are not design memories and produce no row.

## The question

`docs/READER_TRANSFER_RESULT.md` answered the **reader** half: Gemma reading
gpt-oss-written memories reproduces the representation ordering, with a larger
raw ΔU (+0.3152 vs +0.1884; paired +0.1268, task-clustered
[+0.0496, +0.2050], excludes zero) of which **54% sits in the WITHOUT arm**.

Only the reader changed there. The reviewer's next question is the writer's:

> Is a memory's measured utility a property of the **experience** it compresses,
> or of the **model that compressed it** — and does a memory work unusually well
> when the model reading it is the model that wrote it?

A single combined change cannot answer that. A 2×2 can.

## The design

Per representation ∈ {summary, structured}:

| | Reader gpt-oss | Reader Gemma |
|---|---|---|
| **Writer gpt-oss** | **A2/A3 — DONE** (`results/repr_scaleup/cells.jsonl`) | **R2/R3 — DONE** (`results/gemma_reader/transfer_cells.jsonl`) |
| **Writer Gemma** | **W1/W2 — THIS RUN** | **W3/W4 — THIS RUN** |

`raw` is **not** in the factorial and must never be drawn into it: raw is a
deterministic span with **zero model calls**, so "writer gpt-oss raw" and
"writer Gemma raw" are the *same bytes*. There is no writer axis for raw. Raw
appears below only as a reference row, never as a factorial cell.

### What varies and what does not

**Exactly one thing varies between the two writer arms: the writing MODEL.**

| held | how it is enforced at run time, not claimed in prose |
|---|---|
| the source segments | the SAME 60 `memory_unit_locator`s, re-rendered from `trajectories.jsonl` and required to reproduce the manifest's recorded `n_tokens` for every unit (**W-GATE 1**) |
| the segment text itself | per-unit sha256 vs the `source_text_sha256` the gpt-oss write pass recorded in its own `source_span` (**W-GATE 2**) |
| the prompts | the SAME `configs/prompts/summary_v1.txt` and `structured_v1.txt`, loaded through the one content-addressed registry; the recorded `prompt_version` digest must equal the gpt-oss run's byte-for-byte (**W-GATE 3**) |
| the JSON schema | the same `STRUCTURED_KEYS`, the same `validate_structured`, the same `render_structured` key order |
| the writer classes | the same `SummaryWriter` / `StructuredWriter`. Only the client's `model` and `reasoning_effort` differ |
| temperature / max_tokens | 0 / 512, unchanged |
| writer blindness | `assert_all_writers_blind()` + `assert_writer_blind()` run before any call and are printed (**W-GATE 0**) |
| reader-side context | filler pool sha256, system prompt sha256, K=4, target position seeded by `(task_id, manifest memory_id)` — all identical to the gpt-oss runs (**R-GATES 1–3**) |

**What necessarily changes, and why it is not a confound:** the memory TEXT.
That is the intervention. Its downstream consequences — a different
`memory_content_id`, a different `memory_id`, a different `cell_id`, a
different `semantic_similarity`, a different `memory_tokens` — are all
*functions of the text*, so each is **re-measured for the Gemma-written
memories and never carried over from gpt-oss**. In particular
`semantic_similarity` is a fresh embedding call: reusing gpt-oss's would put
one memory's similarity on a different memory's row.

🔴 **The target POSITION is held, and this is load-bearing.** It is seeded by
`(task_id, manifest memory_id)` — the positional unit id, not the
per-representation content hash — exactly as every prior run did. So a
Gemma-written memory lands in the same slot its gpt-oss counterpart occupied.
`docs/POSITION_EFFECT.md` measured that moving the target changes the answer in
8 of 12 cells; a writer comparison in which the two memories sat at different
positions would be measuring writer + position.

### Lineage

Every Gemma-written memory carries the **same `memory_unit_locator`** as its
gpt-oss counterpart, and every result row carries
`pair_key = "{locator}|{task_id}"`. That is the join key for the whole
analysis.

🔴 **The three join traps, named here so they cannot be rediscovered as bugs:**

* `memory_id` is a **per-representation content hash** over
  `MEMORY_ID_KEYS` (which includes `memory_text` and `memory_writer_model`).
  A Gemma memory's `memory_id` differs from its gpt-oss counterpart's **by
  construction**. Joining on it returns zero rows and is wrong even when it
  does not.
* `condition_id` **embeds the representation, the writer and the reader**.
  Joining on it across arms returns **zero rows**. The analysis RUNS this join
  and prints the zero, so the rule is evidence rather than a quotation.
* `memory_content_id` (the write-pass cache id) is a hash of
  `(episode_id, segment TEXT)` and is therefore **identical** across writers
  for the same unit — it over-matches across writer arms. It is used as a
  **cache key component only**, never as an analysis join key, and the cache
  key also contains `model_id`, which is what separates the two writers.

Only `(memory_unit_locator, future_task_id)` is correct.

### Nothing is overwritten

The Gemma writer arm is a **new file**, `results/writer_factorial/memories_gemma.jsonl`.
`results/repr_scaleup/memories.jsonl` is opened **read-only** and its sha256 is
asserted equal to `b342151c7f3cac5a…` (the value the gpt-oss run and the reader
arm both recorded) **before and after** this run writes anything. A new writer
arm that mutated the old one would void both published arms at once.

## Malformed structured output is a RESULT, not a problem to be fixed

Per `docs/MEMORY_PROTOCOL.md` §1C and `representations.py`'s existing contract:

* a structured write whose output fails JSON parse or schema validation is
  returned with `ok=False` and a populated `error_code`;
* **no silent repair, no fallback to summary, no retry-until-valid, no
  loosening of `validate_structured`;**
* the malformed text is KEPT in `raw_model_output` so the rate can be checked;
* the **malformed rate is reported per writer**, with the two denominators the
  existing code already distinguishes (all writes; writes the model was allowed
  to finish, i.e. not truncated at the cap).

gpt-oss's measured rate on these same 60 segments is **3/60** (all three
`structured_malformed_json`, all three truncated at `max_tokens=512`), i.e.
**0/57** among writes that finished. Gemma's rate is whatever it is. **A higher
Gemma malformed rate is a finding, not a failure of this run**, and a lower one
is equally publishable.

A memory whose write failed has no text, so its cells are not runnable under
either reader. Those cells are **excluded with their reason recorded**, and the
matched-set rule below removes them from *every* arm, not just the one that
lost them.

## Cost accounting — separate currencies, never pooled

🔴 Gemma formation cost is recorded **in its own file and its own fields** and
is never added to, averaged with, or divided by gpt-oss's.

* `extraction_calls`, `extraction_input_tokens`, `extraction_output_tokens`,
  `extraction_latency_s` — per memory, per writer.
* `extraction_reasoning_tokens` is **`None` on every Gemma row and must stay
  `None`.** metis/`gemma-4-31B-it` returns no `completion_tokens_details` at
  all. Per the house rule that is "could not be measured". Writing `0` would
  assert a measurement nobody made. The run asserts `all(rt is None)` on the
  Gemma writer rows and the gpt-oss comparator's are `int`.
* Because one writer reports reasoning tokens and the other reports **nothing
  at all**, a total-token comparison between the two writers is **not
  apples-to-apples** and the result document must say so in the same table.
* Latency is wall-clock under this project's own concurrency on a shared
  gateway, not a throughput benchmark; it is reported as measured and not
  turned into a cost-per-token.

## Budget, and the pre-committed subset rule

Full factorial cost, counted before spending:

| stage | calls |
|---|---:|
| Gemma WRITE, 60 segments × {summary, structured} | **120** |
| W1/W2 — writer Gemma × reader **gpt-oss**, 2 reps × 2 arms | 285 + 277ish × 4 ≈ **2,248** |
| W3/W4 — writer Gemma × reader **Gemma**, 2 reps × 2 arms | ≈ **2,248** |
| embeddings for the new memory texts + tasks | ≈ 120 + 126 |
| **total new endpoint calls** | **≈ 4,700** |

At the measured throughputs (gpt-oss 169.9/min, Gemma 74.0/min at 16 workers,
`docs/MODEL_ARMS.md`) that is roughly 15 min + 30 min + the writes. **The full
factorial is affordable, so no subset rule is invoked.**

**If it turns out not to be** — a sustained 429 regime, a gateway outage, or a
wall-clock overrun — the subset rule is **fixed here, now, before any outcome
is visible**, and the result document must state which clause fired:

> **SUBSET RULE (pre-committed).** Sort the eligible cells by
> `(memory_unit_locator, task_id)` — a lexicographic sort on identifiers that
> were fixed by the screened design in September and have no relation to any
> reward. Take the first *n* **for every one of the four arms identically**, so
> the subset is BALANCED by construction and the matched set is not reduced
> further. Record *n*, the rule, and the exact cells covered and not covered.
> Never choose cells by ΔU, by stratum outcome, by which cells "worked", or by
> anything either reader or either writer produced.

Both writer-Gemma reader cells (W1/W2 and W3/W4) must be run on the **same**
cell list; running one arm on more cells than the other would make the
interaction term a comparison of different objects.

## The matched set — the only basis for every number

Four arms have four independent ways to lose a cell (a failed write under
either writer; an unscorable read under either reader). **Every factorial
number is computed on the pair keys present under ALL FOUR combinations**, per
representation, with the denominator printed beside it. A cell lost anywhere is
dropped everywhere.

This is stricter than any prior document here and it is deliberate: the reader
arm's 276/274/269 matched sets will shrink, and the writer-effect and
reader-effect estimates below will therefore **not be numerically identical** to
the published reader-arm figures even where they agree. The result document
must report the reader effect on **both** bases — the 4-way matched set, and the
published 2-way set — and say which is which.

## The four quantities, defined before the data exists

Let ΔU(w, r, c) be the mean per-cell utility delta for writer `w` ∈ {oss,
gem}, reader `r` ∈ {oss, gem}, on matched cell `c`, over the first 2
replicates. Nulls are excluded and counted, never coerced to 0.0.

1. **WRITER effect** — same reader, different writer, paired per cell:
   * under reader gpt-oss: `ΔU(gem,oss,c) − ΔU(oss,oss,c)`
   * under reader Gemma:  `ΔU(gem,gem,c) − ΔU(oss,gem,c)`
   * and the average of the two (the main effect).
2. **READER effect** — same writer, different reader, paired per cell:
   * under writer gpt-oss: `ΔU(oss,gem,c) − ΔU(oss,oss,c)` — **this is the
     published reader arm, re-computed on the 4-way matched set. It is the
     replication check.**
   * under writer Gemma:   `ΔU(gem,gem,c) − ΔU(gem,oss,c)`
3. **SAME-FAMILY effect.** Stated precisely, because a vague version of this is
   easy to confirm by accident:
   > mean over matched cells of
   > `½[ΔU(oss,oss,c) + ΔU(gem,gem,c)] − ½[ΔU(oss,gem,c) + ΔU(gem,oss,c)]`
   >
   > i.e. **same-family mean (oss/oss, gem/gem) minus cross-family mean
   > (oss/gem, gem/oss)**, paired within cell.
   >
   > 🔴 This contrast is **numerically identical to the interaction up to a
   > factor of 2** in a 2×2. They are reported as one quantity with two
   > readings, NOT as two independent findings that happen to agree.
   > Presenting them as mutual corroboration would be this project's own
   > "two routes converged" defect (`DEFECT_REGISTER.md`).
   >
   > ⚠️ **ERRATUM, 2026-10-01, before any factorial number was computed.** This
   > paragraph originally read "identical to **the negative of** the
   > interaction" and gave "−½ × INTERACTION". **That sign is wrong.** With
   > `oo, og, go, gg` the four arm means,
   > `INTERACTION = (gg − og) − (go − oo) = gg − og − go + oo` and
   > `SAME_FAMILY = ½(oo + gg) − ½(og + go)`, so
   > **`SAME_FAMILY = +½ × INTERACTION`** — same sign.
   >
   > The original wording is kept above the correction rather than deleted
   > (`retraction is labelling, not deletion`). **Neither quantity's
   > definition changed**; both are implemented exactly as the numbered
   > definitions here specify. What was wrong was only the prose claim about
   > how they relate. It was caught by the constructed-ground-truth positive
   > control in `scripts/w3_analyze_factorial.py`, which predicts the
   > same-family value from a known interaction and disagreed with the sign
   > this document asserted — a worked example of why a stated identity must
   > be machine-checked rather than believed. The analysis artifact reports
   > the residual against **both** signs so the erratum stays visible.
4. **INTERACTION** — does writer choice matter differently per reader:
   `[ΔU(gem,gem,c) − ΔU(oss,gem,c)] − [ΔU(gem,oss,c) − ΔU(oss,oss,c)]`,
   paired per cell.

All four get **task-clustered** bootstrap CIs (10,000 resamples, seed fixed in
code), because cells repeat within tasks; episode-clustered intervals are also
emitted. The task-clustered interval governs, as in every prior arm here.

Alongside every mean: the **non-zero contributor count** (`docs/ZERO_CONTRIBUTORS.md`)
and both the diluted and conditional magnitudes. A CI spanning zero where the
contributor count is small is **underpowered, not null**
(`docs/PAIRED_POWER.md`), and must be read that way.

## What each outcome would mean — fixed now, so no reading is chosen later

**No effect is an equally valid result. This run is not aimed at finding a
same-family advantage.** In fact the project's prior should be *against* one:
raw — written by no model at all — is the strongest representation under both
readers, which is already evidence that compression identity matters less than
content.

| outcome | what it would mean | what it would NOT license |
|---|---|---|
| **Writer effect excludes zero, one sign** | which model compresses an experience changes how useful the memory is, consistently across readers. The *writing* model is part of the measurement | nothing about *why*; a writer effect could be length, faithfulness, or format, and the decomposition below is needed |
| **Writer effect spans zero with many contributors** | memory utility is a property of the experience, not of the compressor. **A clean, publishable negative** that strengthens the representation finding's generality | it is not "the writers are identical" — report the interval width |
| **Writer effect spans zero with FEW contributors** | underpowered. Say so in those words | not a null |
| **Reader effect reproduces (raw-like direction, summary/structured ≈ 0)** | the published arm survives the 4-way restriction | — |
| 🔴 **Reader effect does NOT reproduce** | **stated loudly, at the top of the result document, before anything else.** Either the 4-way restriction changed the cell population materially, or the published arm is fragile. Both must be investigated and neither may be glossed | — |
| **Same-family > 0, excludes zero** | a memory is worth more to the family that wrote it. Interesting and reviewer-relevant | it does **not** establish a mechanism, and it is the same number as −interaction |
| **Same-family ≈ 0** | memories are not model-parochial. Equally publishable, and the *expected* result given raw's dominance | — |
| **Same-family < 0** | cross-family memories do better. Would need a hard look at a confound before being believed | — |
| **Interaction excludes zero** | writer choice matters differently per reader; the two main effects must not be read on their own | — |
| **Gemma malformed rate ≫ gpt-oss's** | structured writing is model-dependent; the structured arm's coverage differs by writer and the matched set already handles it | it does not justify repairing, retrying or relaxing the schema |

## Positive controls — every null defended, each required to FIRE

A null from an instrument never shown to move is not a measurement. Each row
is run and its firing is recorded in the controls artifact; a control that does
not fire **fails the run**.

| null to be defended | the control that must fire |
|---|---|
| "the Gemma memories are different from gpt-oss's" | compare the two texts per locator and require them to **differ**; a byte-identical pair would mean the writer never changed |
| "the segment is the same" (W-GATE 2 passes) | plant one byte in a segment and require the gate to ABORT |
| "the prompt is the same" (W-GATE 3 passes) | compute the digest of a one-byte-altered prompt and require it to differ from the pinned version |
| "the memories file was not overwritten" | sha256 before/after, and a planted mutation must be detected |
| the 4-way join returns rows | run it on a key known to exist; AND run the **`condition_id`** join and show it returns **0** |
| `F_exec = 0` for any arm | flip one replicate in a sample of cells; the floor must become > 0 |
| the cache cannot cross writers | a writer-gpt-oss key must HIT before the writer-Gemma key is shown to MISS (positive control FIRST, or the miss is vacuous) |
| the writer is blind | `assert_all_writers_blind()` + a `TaskLeakageError` must be raised by a deliberately task-shaped metadata key |
| the structured validator still rejects | feed it a known-malformed object and require a non-None error code |
| the interaction estimator is not identically zero | feed it constructed input with a known interaction and require recovery |

## Reward None

A call that raises — including the Gemma truncation guard's three observables
(`finish_reason=='length'`, `usage.stop_reason=='length'`,
`completion_tokens >= max_tokens`) — yields `reward = None` and an
`error_code_if_any`. **Never 0.0.** The Gemma truncation guard
(`truncation_is_always_an_error`) is ON for every Gemma reader call, as in the
published reader arm.

🔴 On the **WRITE** side the guard is deliberately **OFF**, matching gpt-oss's
write pass exactly: `representations.py` records `finish_reason` and keeps a
truncated-but-parseable memory on purpose, and gpt-oss's 7 truncated summaries
and 3 truncated structured writes are in the published arm on that basis.
Turning the guard on for Gemma's writes alone would make the two writer arms
differ in their **admission rule** as well as their model — a second
intervention wearing the first one's name. The truncation counts are reported
per writer instead, and the malformed-rate denominators split on them.

## Artifacts

| artifact | path |
|---|---|
| this precommitment | `docs/WRITER_FACTORIAL_PRECOMMITMENT.md` |
| Gemma-written memories (NEW FILE) | `results/writer_factorial/memories_gemma.jsonl` |
| write-pass summary + cost + malformed rate | `results/writer_factorial/write_summary_gemma.json` |
| W1/W2 + W3/W4 result rows | `results/writer_factorial/factorial_cells.jsonl` |
| the 2×2 analysis every reported number is read from | `results/ledgers/writer_factorial/writer_factorial_analysis.json` |
| controls | `results/ledgers/writer_factorial/writer_factorial_controls.json` |
| the result document | `docs/WRITER_FACTORIAL_RESULT.md` |

`results/**` is gitignored except `results/ledgers/**`, so every number quoted
in the result document is read at generation time from a **tracked** artifact.

---

## AMENDMENT 1 — the comparator arms are RE-RUN, not reused (2026-10-01)

**Made on a failed control, before any contrast was computed or looked at.**
Recorded here rather than silently applied; an amendment made after seeing an
outcome would not be a precommitment, so the timing is the point.

### What the control found

The plan above used the **published** writer-gpt-oss arms
(`results/repr_scaleup/cells.jsonl`, `results/gemma_reader/transfer_cells.jsonl`,
both executed 2026-09-30) as two of the four cells. The precommitted control
*"the WITHOUT arm is writer-invariant"* **failed**:

| | |
|---|---:|
| WITHOUT-arm requests compared, reader gpt-oss | 1,124 |
| request `context_sha256` identical across the two sessions | **500 / 500** |
| **WITHOUT-arm output text that nonetheless DIFFERS** | **554** |
| WITHOUT-arm reward that differs | 84 |
| **mean WITHOUT-arm reward change** | **−0.0320** |

The WITHOUT arm contains **no memory at all**. A change of writer cannot reach
it, and the request bytes are provably identical. The difference is therefore
not the experiment — it is the endpoint. **`gpt-oss-120b` is deterministic
within a session and not across sessions.**

(The Gemma reader shows **0 / 1,124** drift on the same comparison, so this is
a property of one model, not of the gateway. Measured, not assumed — and a
reminder that a stability result for one model is not one for another.)

### Why this invalidates the original plan

−0.0320 on the no-memory baseline is **the same order as the writer effect
being measured**. A contrast drawn between an arm run on 2026-09-30 and one run
on 2026-10-01 confounds **writer** with **session**, and nothing downstream
could separate them. The published numbers are not wrong; they are simply not a
valid *comparator* for a run executed a day later.

### The amendment

1. The gpt-oss writer arms are **re-executed in the same session** as the Gemma
   writer arms, with byte-identical requests. **F-GATE 5 is inverted for that
   arm**: because the memory text is the published one, the WITH-arm bytes must
   **MATCH** the published request rather than differ — verified **1,124 / 1,124**.
   That is a strictly stronger assertion than the differs-check it replaces.
2. **All four cells of the 2×2 now come from one session.** The run id is
   stamped on every row (`provenance.SESSION_MATCHED_RUN_ID`).
3. The published arms are retained as a **drift measurement** and reported in
   the result document, never as a comparator.
4. **Nothing else changes**: the same eligibility rule, the same cells, the same
   four contrast definitions, the same matched-set rule, the same analysis.

### What this costs, stated plainly

The reader-effect figure in the result document is therefore **not** a
re-computation of `docs/READER_TRANSFER_RESULT.md`'s number on fewer cells. It
is a **re-measurement**, differing in two ways at once (cell set *and*
session). Both are reported side by side so neither is hidden, and the
agreement — or disagreement — must be read with that in mind.

> This is this project's defect #21 in a new place: *a determinism probe
> measured WITHIN-session repeatability and was read as CROSS-session
> reproducibility.* The project had already measured 248/248 A/A determinism —
> **within** a session — and the plan above quietly assumed it extended across
> one. The control that caught it checks a quantity that is **zero by
> construction unless something is wrong**, which is the cheapest kind of
> control there is and the reason it was worth running at all.

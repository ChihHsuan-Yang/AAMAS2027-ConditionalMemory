---
pretty_name: "Conditional Memory Utility Dataset (AAMAS 2027)"
license: other
license_name: mixed-per-row-see-data-card
task_categories:
  - question-answering
language:
  - en
tags:
  - agent-memory
  - memory-utility
  - long-term-memory
  - counterfactual-evaluation
  - multi-agent
configs:
  - config_name: cells
    data_files: data/cells.jsonl
---

<!--
  NOTE TO ANY AGENT EDITING THIS FILE
  - `library_name:` is deliberately ABSENT. Declaring one makes the Hub render an
    auto-generated load widget advertising an interface we have not shipped. A platform
    executes metadata; do not add fields whose side effects you have not checked.
  - Every number below is either MEASURED (a command was run on the released file) or
    marked **pending**. Never write a plausible number. If you do not have it, the word
    is "pending".
  - ✅ ANONYMITY, RESOLVED 2026-10-01. A navigation pass added GitHub links
    carrying an author's account handle to this card. Nothing was exposed --
    both repositories were private (unauthenticated GET: GitHub 404, this
    dataset 401, against a 200 positive control) -- but a card ships with the
    release, so the handle would have travelled into a double-blind cycle.
    The links are now `<anonymized-for-review>` placeholders.
    **GATE 2b was blind to this** and is no longer: its pattern list matched
    only home-path shapes (`/Users/<name>/`, `/home/<name>/`, `C:\Users\<name>`),
    and a handle inside a URL is a different shape. It now also matches GitHub
    and Hugging Face account handles in URLs, while deliberately permitting an
    anonymized mirror -- verified by planting both forms. Restore the real
    links only after the review cycle.
  - 🔴 `license:` is `other`, NOT `apache-2.0`, and that changed at v0.4. Through
    v0.3 every row was Apache-2.0 (LongMemEval-V2 5,643 + SciCode 154, verified by
    license_source_reference) and the flat tag was true. v0.4 adds 127 SWE-bench
    Verified rows whose CORPUS DECLARES NO LICENCE; a flat `apache-2.0` would make
    the Hub advertise an Apache grant over rows nobody has granted anything for,
    which is the same class of error as the library_name note above -- a platform
    EXECUTES metadata, and here it would be executing a licence claim we cannot
    make. The per-row truth is in `license_source_reference`; section 17 has the
    table. If a BEAM-derived row is ever added, this file is WRONG regardless and
    the row belongs in a separate CC BY-SA 4.0 dataset.
-->

# Conditional Memory Utility Dataset

> **v0.6 — `length-control`. 16,816 real evaluated rows, 0 fabricated rows.**
>
> Three benchmarks: **LongMemEval-V2 16,535** · **SciCode 154** · **SWE-bench
> Verified 127**. **Two readers**: `gpt-oss-120b` **13,998** · `gemma-4-31B-it`
> **2,818**.
>
> 🔴 **v0.6 adds the pre-registered LENGTH CONTROL — the experiment that
> narrows this project's own representation claim.** 4,432 rows, eight arms over
> one frozen 554-row cell set, run in a single session. At a matched exposed-token
> budget a content-blind extractive slice and a model-written summary do **not**
> separate (**+0.0519**, 95% task-clustered CI **[−0.0678, +0.1727]**), so Raw's
> advantage is an **exposure-budget** effect, not a rewriting effect. The design
> was frozen at commit `f702aaf` **before any reader call was made against a
> truncated memory**. See §21.
>
> 🔴 **One of those eight arms is an A/A CONTROL, not a condition.**
> `trunc_last_20000` is a 20,000-token budget against a maximum Raw length of
> 19,801, so it renders **byte-identical to `raw` on 554/554** and reproduces its
> rewards on **552/552 scored pairs**. **Treating it as a ninth condition would
> double-count Raw.** It is in the release because an identity arm with a known
> correct answer is what proves the new code path; it is not an independent
> measurement. See §21.3.
>
> **As of v0.6 no evaluated row of this project remains unpublished-but-ready.**
> Everything still absent is absent for a stated structural reason — a licence
> (BEAM), a persistence gap (SciCode summary/structured), or a VOID label — and
> each is named in §22.
>
> 🔴 **v0.5 was the first release containing ANY `gemma-4-31B-it` reader row.**
> Through v0.4 `reader_model` was `gpt-oss-120b` on 5,924 of 5,924 rows, so the
> entire reader-generalization evidence base was absent from the release while
> being reported in the paper. v0.5 closed that gap: +6,460 rows, all
> LongMemEval-V2, all schema v3. See §20.
>
> Two benchmarks remain incomplete, in two different ways, and both gaps are
> stated before any result:
>
> 🔴 **SciCode ships `raw` ONLY — 154 of its 462 cells.** The 308 Summary and
> Structured cells are **absent because their memory text was never persisted
> and is NOT recoverable** — a PERSISTENCE gap, not a licence withholding
> (SciCode is Apache-2.0 and withholds nothing); see §19.14.
>
> 🔴 **SWE-bench ships METRICS AND IDS ONLY — no corpus text at all.**
> `princeton-nlp/SWE-bench_Verified` **declares no licence**, so every text
> field on those 127 rows carries `__WITHHELD_SEE_LICENSE__` and is declared in
> `text_fields_withheld`. That is a LICENCE withholding — the text exists and we
> may not redistribute it — and it is **not** the same fact as SciCode's; see
> §19.15. **37 manufactured `0.0` rewards were demoted to null before export**
> (defect 21): a test suite that printed no verdict is not a wrong answer.
>
> A partial export that looks complete is the defect, so the gaps are stated first.
>
> *(v0.2 was: 5,643 rows, LongMemEval-V2 only, three representations.)*
> LongMemEval-V2 only, now in **three matched memory representations**: the 4,519 Raw
> rows of v0.1 plus **1,124 Summary and Structured rows** over the same memories, tasks
> and reader. The headline is a **negative result on the project's own founding
> hypothesis** (§12); v0.2 adds a **second negative result** — compressing the same
> experience with the same writer and reader **destroys the measured benefit** (§12.1),
> and the cost advantage that appears to compensate **disappears once the compression is
> charged for its own formation** (§14.1). The limitations in §18–19 are measured
> constraints, not boilerplate.

---

> # 🧭 START AT THE CODE REPOSITORY
>
> **The project's GitHub README is its canonical entry point**, not this card. It
> carries the three frozen scientific stories, the paper package, the
> paper→artifact map, the trace-availability audit, the reproduction commands and
> the handoff document, and it is updated first whenever anything moves.
>
> This card describes **one released snapshot of the data**. For what the data
> *mean*, which figure each row supports, and what is permanently unavailable,
> start there. The repository link is withheld here only while the submission is
> under double-blind review (see §1).

## 1. Name, purpose, and research goal

**Conditional Memory Utility Dataset**, released with the AAMAS 2027 submission
**"What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent
Memory"**.

### Where everything lives

| | |
|---|---|
| 💻 **Code** | `<anonymized-for-review>/AAMAS2027-ConditionalMemory` (GitHub; de-anonymised link withheld during review) — adapters, writers, runners, scorers, the exporter that built this release, and the full test suite |
| 📄 **Paper** | *What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent Memory*, AAMAS 2027 |
| 📐 **Schema** | `code/p1mem/schema.py` and `code/p1mem/validate.py`, **shipped inside this release**; field-by-field reasons for every null are in §7 below |
| 🗺️ **Paper → artifact map** | `docs/PAPER_ARTIFACT_MAP.md` — every figure and table with its generator, canonical input, and the exact **unit and universe** of each table row |
| 🔍 **Trace availability** | `docs/TRACE_AVAILABILITY.md` — what still exists per result, including what is **unavailable forever** |
| 📊 **Coverage** | `docs/COVERAGE_MANIFEST.md` — the authoritative universes; a bare coverage percentage is false against one of two on LongMemEval |
| 🏷️ **Version notes** | §20 below, and `docs/DATASET_INDEX.md` (one row per snapshot, with its known limitations) — also shipped in this release at `docs/DATASET_INDEX.md` |
| ⚖️ **Licences** | §17 below; authoritative document `docs/BENCHMARK_LICENSES.md`, shipped here |

🔴 **The `benchmark` field spells `longmemeval_v2`, `scicode` and `swebench_verified`.**
A filter on `lmev2` or `swebench` returns a **false zero**, not an empty subset.

The dataset records, for a single stored memory and a single **later, different** task, the
**counterfactual change in task reward caused by that memory being available**:

```
DeltaU(m, t, s) = Reward(t | memory m available; seed s) - Reward(t | m absent; seed s)
```

Both arms live in **one row**, so a WITH score can never drift from the WITHOUT score it is
differenced against. The dataset is a paper deliverable in its own right, not a by-product.

**The research question.** *Is the value of a memory a property of the memory, or of the
(memory, task) pair?* If utility is a property of the memory alone, a single scalar per
memory suffices and existing retention/forgetting policies are well-posed. If it is
conditional, a scalar memory score destroys real structure.

## 2. The conditional-memory-utility concept, as the data actually supports it

The project was designed around conditional **harm**: the same memory helps one task and
harms another, measured as a **task sign-flip rate**. **The data does not support that
framing**, and this release leads with the correction rather than burying it.

What the data supports instead: memory utility here is **sparse and one-sided** — almost
always inert, occasionally strongly positive, rarely harmful. A scalar `Value(memory)` is
still the wrong object, but for a different reason than hypothesized: it **averages a large
effect over overwhelmingly many inert pairs**, not because the sign varies.

## 3. Source benchmarks

| Benchmark | Role in THIS release | Rows | Status |
|---|---|---:|---|
| **LongMemEval-V2** (`xiaowu0162/longmemeval-v2`) | the primary source; the only one with all three representations | **16,535** | released here, Apache-2.0, source text included |
| **SciCode** (`SciCode1/SciCode`) | cross-domain transfer | **154** | released here, Apache-2.0, `raw` only — §19.14 |
| **SWE-bench Verified** (`princeton-nlp/SWE-bench_Verified`) | cross-domain transfer | **127** | released here, 🔴 **metrics and ids ONLY, no corpus text** — §19.15 |
| LongMemEval V1 | not in this release | 0 | annotations only, if ever |
| BEAM | **excluded by license** | 0 | must ship as a separate CC BY-SA 4.0 dataset |

**Only LongMemEval-V2 is representation-matched.** SciCode ships one arm of three
and SWE-bench's three arms rest on 76 scorable cells of 127, so the representation
comparison this schema was built for is a LongMemEval claim and is not a
cross-benchmark one.

Measured, not assumed: **16,535 / 16,816** rows carry
`license_source_reference = 'longmemeval_v2:Apache-2.0'` (re-derived at v0.6, not
inherited). Pinned benchmark revision
`2cc8c540bdb87fe6761629b585e727e1c4704520` — the same revision for both the v0.1 and the
v0.2 arms.

## 4. Source episodes and the memory unit

The memory unit is a **page visit**: one maximal same-URL run of states in a past agent
trajectory. The boundary is drawn by **the past agent's own behaviour** (it navigated
away), so it is a naturally occurring span, not a window we imposed and certainly not one
fitted to any question.

Measured over the released rows. 🔴 **This table is LongMemEval-V2 ONLY** — it
describes the memory-unit construction above, which is a LongMemEval procedure.
The SciCode (154) and SWE-bench (127) rows are counted in §3 and described in
§19.14 / §19.15; adding them to these denominators would pool three different
sampling procedures under one count.

| quantity (LongMemEval-V2 only) | value | of which v0.2's new arms |
|---|---|---|
| rows | **5,643** | 1,124 |
| cells (memory × task × condition) | **2,679** | 562 |
| distinct `memory_id` | **234** | 117 |
| distinct **source memories** (`memory_unit_locator`) | **117** | 60 |
| distinct future tasks | **275** | 126 |
| distinct source trajectories | **77** | — |
| errored rows (no outcome, no reward) | **2** (1 cell) | 0 |

⚠️ **`memory_id` doubles but the number of source memories does not.** `memory_id` is a
**content hash**, so the same span compressed three ways yields three different ids by
design — 234 ids over 117 source spans. **To join representations, use
`memory_unit_locator` (in `source_episode_metadata`), never `memory_id`.** A `memory_id`
join across representations returns **zero rows**, which reads as "no data" rather than
"wrong key"; this project hit that silent zero three times before writing it down.

## 5. Memory representations

**v0.2 ships all three.** Measured on the released file:

| representation | rows | writer | what it is |
|---|---:|---|---|
| `raw` | **4,519** | none (`none:deterministic_span`) | the verbatim source span. No model call. |
| `summary` | **570** | `gpt-oss-120b` on metis | free-prose compression of that same span |
| `structured` | **554** | `gpt-oss-120b` on metis | JSON-schema'd compression of that same span |

The three arms are **matched**: same 60 source memories, same 126 future tasks, same
reader model, cluster, prompt version, reasoning effort and sampling config
(`reader_endpoint_sha256 = 7e6b0a4f53fd08e0` on every row of both releases). 277 design
cells are present in all three representations, over 57 memories.

Raw selection uses no future task and there is deliberately **no "pick the most informative
span" rule** — that would smuggle in the value judgment the dataset exists to measure.
Summary and Structured compress that same span; their `parent_memory_id` points at the raw
memory they were written from (§7).

⚠️ **Structured has 554 rows, not 570.** 8 design cells were dropped because the write
failed: 3 of 60 structured writes hit the 512-token cap and returned JSON cut off
mid-value. The exclusion is recorded per cell, not silently dropped, and the denominators
below say which. **All 3 failures are `finish_reason == 'length'`** — a budget failure,
not a formatting one.

## 6. Memory acquisition and writer blindness

> **The memory writer never observes the future evaluation task.** `m = W(e)`, never `W(e, t)`.

Enforced structurally, not asserted: the writer's signature takes an episode and no task
argument; memories are content-hashed **before** the pairing step exists. For raw there is
no writer model at all (`memory_writer_model = 'none:deterministic_span'`), so
task-directed writing is impossible by construction.

## 7. Fields that are null, and exactly why

**A null here is a documented fact, never an oversight.** **Three** fields are null on
every row. **Two more were null in v0.1 and are now populated** — because their reasons
were contingent on every row being `raw`, and v0.2 ends that.

| field | why it is null |
|---|---|
| `source_episode_completion_timestamp` | **No wall-clock field exists anywhere in LongMemEval-V2.** An exhaustive key scan of all 1,870 trajectories returns only `{domain, environment, goal, id, outcome, start_url, states}`, and states carry only `{accessibility_tree, action, screenshot, state_index, step, thought, url}`. `state_index` is an *order*, not a timestamp. Re-checked at v0.2: same benchmark revision `2cc8c540`. (LongMemEval **V1** does ship real dates, so the field is defined for a future V1 arm.) |
| `context_budget` | **No truncation budget was ever enforced.** `memory_tokens_exposed == memory_tokens_retrieved` on **16,689 of 16,816** rows — re-derived at v0.6, not inherited. 🔴 **This stays true across the length control, and the reason is worth stating**: the length-control arms shorten the MEMORY TEXT ITSELF before the reader sees it, so both fields move together and remain equal. The budget in `provenance.length_budget` is a property of how that memory was CONSTRUCTED, not a cap applied to a longer exposure — `context_budget` is still null on all 16,816 rows. The other **127 are the SWE-bench rows, where BOTH fields are null** (`retrieval_method='none'`: no retriever ran, so there is no retrieved set to count and nothing was truncated — `schema.BENCHMARK_NULLABLE_EXEMPTIONS`). Those 127 are **not** evidence of no-truncation; they are an absence of the measurement, and counting `null == null` as agreement would have turned a 16,689-row fact into a false 16,816-row one. Re-checked for the representation arm specifically: the runner's `truncate_to_tokens` is called **only on the embedding path**, never on the reader's context. (The 20,000-token cap in our design docs is a memory-*selection* rule, not an exposure cap.) |
| `propagation_metadata` | P3-reserved. P1 is single-agent; a value could only be fabricated. The validator rejects a non-null value. Re-checked: `receiver_id`, `receiver_role`, `visibility_mask` and `team_reward` are null on all 1,124 new rows. |

### 7.1 🔴 Two nulls that v0.2 had to fix, because their REASONS were about to become false

This is worth stating plainly, because the failure would have been invisible.

**`faithfulness_check`.** v0.1's reason — "raw *is* the source text, so the proxy returns
1.0 by construction" — is still true for raw, and raw rows still carry null. But the
exporter's other branch wrote, on any non-raw row:
*"NOT SCORED. No faithfulness proxy was run for this representation."*
No non-raw row existed, so that sentence was never false. **It is false for v0.2's 1,124
rows**: the proxy runs at write time and every one of them carries a real score.
A null beside a stated reason that is untrue is worse than a null with no reason, because
the reader has no cue to check it. The validator now rejects that combination outright.

| representation | memories | scored | mean number_support | mean entity_support |
|---|---:|---:|---:|---:|
| summary | 60 | **60** | **0.9968** | **0.9372** |
| structured | 60 | **57** | **1.0000** | **0.8322** |
| raw | 60 | 0 — correctly, it is a tautology | — | — |

**`parent_memory_id`.** "A raw span has no parent memory" is still true, and raw rows
still carry null. Summary and Structured were compressed *from* the raw span at the same
locator, and that raw memory is already a published row — so the parent is a **verified
join, not an invention**. Joined on `memory_unit_locator`, never on `memory_id` (a content
hash that differs across representations *by design*; joining on it returns zero rows and
reads as "no data"). **117 locators, 0 ambiguous; 1,124 joined, 0 unjoined**, and the
exporter refuses to write on a partial join. Positive control: recomputing each raw
`memory_id` from its write-time record reproduces the **published v0.1 id on 60/60**.

### 7.2 One axis is not the score — why `faithfulness_detail` exists

`faithfulness_check` is a single float (`number_support`: numeric literals in the memory
that appear in the source). Shipping only it would have been a **second tautology,
reached by a different route**:

| | `number_support == 1.0` **and** `entity_support < 1.0` |
|---|---|
| structured | **55 of 57 memories** |
| summary | **37 of 60 memories** |

Structured averages number_support **1.0000** against entity_support **0.8322** — a
single-float column would report it as a flat, perfect score. So the **full multi-axis
result ships in `faithfulness_detail`** (schema v3's one added field). Both axes ship or
neither does.

**Read it asymmetrically.** The proxies are blind to recombination, omission, unsupported
inference and negation, so a **high score is weak evidence** of faithfulness while a **low
score is strong evidence** of a problem. `entity_support` is a **lower bound**:
sentence-initial capitalised verbs ("Clicked", "Performed") and the structured renderer's
own key names ("memory_type") are counted as unsupported without being model-invented.

**24 rows carry a null `faithfulness_check` with a non-null `faithfulness_detail`.** Those
memories contain **no numeric literal**, so `number_support` has an empty denominator;
the scorer returns null rather than a perfect 1.0, precisely so a number-free memory
cannot lift the corpus mean. The other axes were measured normally. Their
`faithfulness_notes` says exactly this.

### 7.3 A provenance key the new run never recorded

The 1,124 new rows carry `provenance.config_sha256 = null`, and the validator emits
**1,124 `provenance_incomplete` warnings**. We did **not** back-fill the current hash of
`configs/endpoint_primary.json`: **the representation runner never reads that file**, so a
run cannot be said to have used a config it never opened, and stamping one would be a
provenance field nobody measured. Each affected row instead carries
`provenance.config_sha256_absent_reason`. The configuration itself is not lost — it is on
every row as `reader_model`, `reader_cluster`, `reader_reasoning_effort`,
`seed_or_sampling_config` and `reader_endpoint_sha256`, and that last value is
**`7e6b0a4f53fd08e0` on both v0.1 and v0.2**: the reader arm is identical.

`utility_label` is `undetermined` and `utility_label_threshold` is null on every row — see §11.

## 8. Future-task pairing — **ours, not natural**

🔴 **The memory→task pairing is CONSTRUCTED BY US. The memories are naturally occurring; the
pairing is not.** Nothing in this dataset is a natural base rate, and no rate computed here
should be quoted as one.

Each cell places the target memory inside a fixed-size, fixed-seed set of **filler**
memories (K = 4 for the screened arm), so removing the memory is a **local** change rather
than emptying the context. Filler is drawn from trajectories **disjoint from every bearing
trajectory**, asserted in code so a violation fails the run.

## 9. Bearing and control definitions

`bearing_label` ∈ `BEARING | MATCHED_CONTROL | RANDOM | unscreened`:

| label | definition | rows |
|---|---|---:|
| `BEARING` | a deterministic content detector fires on (m,t) **and** t is discriminative (fires on 1–8 of the same-domain pool) | 417 |
| `MATCHED_CONTROL` | **same memory, same task family**, detector **silent** | 438 |
| `RANDOM` | unscreened draw by the original question_type-spread rule | 1,744 |
| `unscreened` | the two earlier arms, run before the screen existed — **a real value, not a missing one** | 1,920 |

**`bearing_evidence` stores *why*, not just a boolean** — the field a consumer needs to
disagree with our screen without re-running it:

```json
{"detector_fires": true, "task_pool_hits": 6, "task_pool_size": 1024,
 "discriminativeness": 0.005859, "n_bearing_tasks_for_this_memory": 2,
 "why_stratum": "detector fires; task fires on 6 of 1024 same-domain memories",
 "screen_is_content_only": true, "leakage_flag": false, "caveat": "..."}
```

**`screen_is_content_only: true` is asserted per row**: no reward enters the screen, which
is what keeps the BEARING vs MATCHED_CONTROL contrast non-circular. The known weakness of
the instrument is carried **inside the field** so it travels with the number.

🔴 **`leakage_flag` and `bearing_evidence.detector_fires` are the SAME INSTRUMENT** —
verified equal on 2,599/2,599 screened rows. Bearing and leakage are therefore **not
independent signals in this release**, and a "leakage-controlled bearing effect" cannot be
computed from these columns alone.

## 10. WITH / WITHOUT protocol

Both arms are identical except for the presence of `m`: same reader model, cluster,
endpoint, decoding, seed, prompt scaffold, and **the same scoring function and version**
(one `verifier_id`/`verifier_version` per row, covering both arms by construction).

## 11. Replicates, utility labels, and the three noise floors

2 or 3 replicates per cell (872 cells × 2, 285 cells × 3 in the screened arm), differing
**only** in sampling.

🔴 **`F_exec = 0`, measured — and it is a WITHIN-SESSION floor.** All 1,157 screened
cells produced **byte-identical output in both arms across every replicate**
(`confidence_or_stability = 1.0` everywhere). This is real temperature-0 determinism,
**not cache reuse**: the cache holds 5,198 distinct keys (`replicate_id` is a key field)
spread 2,314/2,314/570 over replicate ids 0/1/2, so each replicate was a separate real
endpoint call.

🔴 **Scope, and a consumer must not miss it.** The replicate calls being compared were
issued **0.0–15.7 s apart** (median 0.0 s) inside one 0.81 h run. `F_exec = 0` therefore
means *re-issuing an identical request moments later in the same run returns the same
reward*. It does **NOT** mean a re-run on another day reproduces these rows: on this same
model, byte-identical no-memory requests re-issued 24 h later returned **different text in
554 of 1,124 cases** and different reward in 82–84, moving the no-memory baseline by
≈**−0.03**. A second reader (`gemma-4-31B-it`) drifted **0/1,124** on the identical
comparison, so cross-session stability is a property of the **model**. There is no
measured F_session for any arm in this release.

**Consequences a consumer must not miss:**
- `confidence_or_stability = 1.0` means *re-sampling reveals no variation*. It is **NOT**
  confidence that a delta is real. It is kept in a separate field from
  `robustness_confidence` precisely so the two are not conflated.
- Replicates carry **no information about sampling noise**, so the variance decomposition
  is **unidentifiable** (§19).

The pre-registered label rule (fixed before any data existed) needs a measured noise floor
`F`:

| `utility_label` | condition |
|---|---|
| `robust_useful` | `CI_lower > 0` **and** `mean ΔU > F` |
| `robust_harmful` | `CI_upper < 0` **and** `\|mean ΔU\| > F` |
| `neutral` | `CI` contains 0, **or** `\|mean ΔU\| ≤ F` |
| `undetermined` | a reward is missing, the cell errored, **or `F` is not yet measured** |

> **Every row carries `utility_label = "undetermined"` and `utility_label_threshold = null`,
> because `F` has not been measured.** This is correct, not a defect. The label is
> **recomputable in place** from the stored raw rewards once `F` exists — which is why the
> raw rewards and full output text are stored rather than a digest.

## 12. Results the data supports — including a negative result on our own hypothesis

All numbers re-derived from the released file.

| stratum | cells | both-arms-fail | mean ΔU | pos / zero / neg cells |
|---|---:|---:|---:|---|
| **BEARING** | 139 | 0.5252 | **+0.3453** | 50 / 87 / **2** |
| MATCHED_CONTROL | 146 | 0.7877 | +0.0274 | 10 / 130 / 6 |
| RANDOM | 872 | 0.7007 | +0.0642 | 82 / 764 / 26 |

**The paired within-memory contrast** (all three strata contain the identical 60 memories,
so memory identity cancels):

| quantity | value |
|---|---|
| paired memories | **60** |
| non-zero contributors | **35** |
| all-memories mean (pre-registered) | **+0.3349** |
| contributors-only mean | +0.5740 |

All three are reported together on purpose: the all-memories mean understates the
mechanism, the contributors-only mean conditions on an outcome, and 35-of-60 is stated
beside the nominal denominator.

**The negative result.** The headline was to be a task sign-flip rate. On bearing cells:
**0 sign flips in 35 flip-eligible memories**, versus 17 of 60 in RANDOM. Flips concentrate
where the pairing is **meaningless**. A sign reversal between a memory and a task it has
nothing to do with is not evidence that memory utility is task-conditional — it is evidence
that both outcomes were noise. **The flip rate is largely an artifact of the pairing,
including in our own earlier arms.**

### 12.1 🔴 v0.2: compression destroys the effect

The three representations are **matched** — same 60 source memories, same tasks, same
writer/reader configuration — so this is a clean within-memory comparison. Paired
BEARING − MATCHED_CONTROL, on the **277 design cells present in all three
representations**, **57 memories**, 10,000-sample percentile bootstrap over memories:

| representation | paired B−MC | 95% CI | non-zero contributors |
|---|---:|---|---:|
| **Raw** | **+0.3174** | **[+0.1922, +0.4485]** | 33 / 57 |
| Summary | +0.0613 | [−0.0414, +0.1646] | 26 / 57 |
| Structured | −0.0498 | [−0.1445, +0.0370] | 20 / 57 |

*Point estimates and contributor counts are exact. The intervals are a 10,000-draw
percentile bootstrap over the 57 memories at **seed 20260930**, **iterating the memories
in sorted order** — without the sort the endpoints wander in the third decimal between
runs of the same code on the same bytes, because the unit order comes from set iteration.
That is a reproducibility trap, not a statistical one; the point estimates never move. To
reproduce these exact endpoints, sort the keys. What does not depend on any of it, and is
what the claim rests on: **Raw's interval excludes zero and the other two do not.***

> **Only Raw's interval excludes zero.** Summarizing or structuring the *same* source
> experience, with the same writer, reader and tasks, **removes the measured benefit.**
> Structured's point estimate is negative, but its CI spans zero, so **no harm is
> claimable either** — the honest reading is "the effect is gone", not "it reversed".

This is a **second negative result**, and it is on a mechanism the field assumes: that a
good summary preserves what matters. At these compression ratios (0.063 summary, 0.037
structured) it does not. We tested two points, both ≤ 0.063; **whether a gentler
compression preserves the effect is untested.**

⚠️ **Read this alongside §19.13.** The Raw arm was run on 2026-09-29 and the two new arms
on 2026-09-30, and the serving endpoint moved between those days. The conclusion does not
rest on that join — a same-session re-measurement reproduces it — but every Raw-vs-new
contrast carries a per-cell noise term a same-session comparison would not.

## 13. Harmfulness — what cannot be claimed

🔴 **No harmful-memory rate is claimable from this dataset.** There are 2 negative BEARING
cells. The design **screened for bearing**, which selects toward helpful pairings, so 2
negatives is not a prevalence estimate. RANDOM's 26 negatives are not a natural rate either,
because the pairing is still ours (§8).

## 14. Efficiency fields

Storage (`memory_tokens`, `storage_bytes`), retrieval (`retrieval_latency`,
`memory_tokens_retrieved`), exposure (`memory_tokens_exposed`), generation
(`generation_latency`, `input_tokens`, `output_tokens`, `reasoning_tokens`), extraction
(`memory_extraction_*`, `extraction_cost_proxy`), API calls, end-to-end wall clock.

**Three zeros that are never merged**, because they mean different things:

| value | meaning |
|---|---|
| `extraction_cost_proxy = 0.0` | a **measurement**: raw makes no call, so nothing was billed. Raw's real advantage, and it must survive into the efficiency frontier or model-written representations look free. **4,673 rows** (LongMemEval raw 4,519 + SciCode raw 154). |
| `extraction_cost_proxy = null` | **NOT 0.0.** The 41 SWE-bench raw rows: the runner never persisted a memory body, so no token count exists to bill. An absence, not a free write. |
| `memory_extraction_latency = null` | **no call was made.** Excluded from a mean latency, never averaged in as 0.0. |
| `reasoning_tokens = null` | **not reported by this cluster.** Metis reports it; Sophia omits it. Must be excluded from a denominator, not summed as zero. |

`compression_ratio = 1.0` on **4,673 of the 6,678 raw rows** — re-derived at v0.5, and
the denominator moved: raw **is** the source span, verified by joining the 4,519
LongMemEval rows to the unit manifest (100% join, 0 misses) and re-derived at v0.4 over
SciCode's 154. 🔴 **The other 2,005 raw rows carry `null`, not 1.0**, and at v0.5 that
is no longer only SWE-bench. Measured, by source: **1,140** session-matched reader rows
(570 gpt-oss + 570 Gemma), **824** gold-free screen rows (656 GF-LEX + 168 GF-LLM) and
the **41** SWE-bench raw rows. In every case `memory_tokens` or the source-span token
count was not recorded by that runner, and a ratio needs a numerator; writing 1.0 would
assert a measured identity nobody measured. **This card said "the other 41 raw rows"
through v0.4; that sentence was true then and is false at this denominator, which is why
it is re-derived here rather than inherited.** Raw's
1.0 is the control that makes the new arms' ratios interpretable: **median 0.0162
(summary)** and **0.0151 (structured)** — roughly 60× compression, both LongMemEval
figures.

### 14.1 🔴 v0.2: the cost ranking REVERSES once formation is charged

This is the part most likely to be quoted wrongly, so both columns ship. BEARING cells
common to all three representations (135 cells, 57 memories), ΔU per 1,000 tokens as a
ratio of totals:

| representation | median exposed tok | ΔU / 1k, **exposure only** | ΔU / 1k, **formation charged** |
|---|---:|---:|---:|
| Raw | 8,344 | +0.0368 | **+0.0368** |
| **Summary** | 282 | **+0.2054** | **+0.0340** |
| Structured | 216 | +0.0622 | +0.0077 |

> **Charge nothing for writing the memory, and Summary looks 5.6× more token-efficient
> than Raw. Charge each representation for its own formation cost — which our protocol
> requires — and Summary drops to 0.92× Raw, i.e. no better, while Structured becomes
> 4.8× WORSE.** The ranking does not survive the accounting.

Amortized formation cost is **1,637 tokens/cell (summary)** and **1,676 (structured)**:
the writer read the whole ~7.6k-token source segment to produce a 282-token memory, and
that read is billed. **Raw's figure is identical in both columns** (+0.0368 either way),
which is the correctness test for the attribution — raw makes zero extraction calls, so
if it had moved at all the cost would have been mis-assigned.

⚠️ **Neither Summary column is a superior operating point**, because both rest on a mean
whose CI includes zero (§12.1). The honest statement is that **at this compression ratio
there is no operating point where compression wins**, once its own cost is paid.

⚠️ **Amortization is a design parameter, not a property of the representation.** Each
memory here is reused across **4.86 cells**. A deployment reusing one memory hundreds of
times would drive the formation term toward zero and recover the exposure-only column.
That is exactly why both are reported and neither is called "the" number.

## 15. Retrieval

`retrieval_method = 'oracle'` on every row in this release — the target memory is placed in
context by construction. **Oracle is non-deployable headroom, never a method.** No
`top_k`/`keep_all` arm is present, so no retrieval comparison can be made from this file.

## 16. Provenance

Per row: `provenance = {code_sha, config_sha256, run_id, host, writer, ...}`, plus
`benchmark_version`, `memory_writer_prompt_version`, `reader_prompt_version`,
`embedding_version`, `verifier_id`, `verifier_version`, `utility_label_rule_version`.

`memory_id`, `cell_id` and `row_id` are **content hashes plus the episode id**, and the
validator **recomputes** them — so an id copied between rows, or content edited after the
id was minted, is caught.

🔴 **One exception, and it is declared per row.** On the 127 SWE-bench rows `memory_id` is
**not** a content hash: the runner never persisted the memory body, so the id is minted
over the withheld sentinel and identifies `(memory_instance_id, memory_representation)`.
Re-deriving it from upstream text gives a different value **by construction**. Join on the
instance ids. The validator reports this as `id_unverifiable_withheld_input` (127
warnings) rather than passing silently. See §19.15.

**Every snapshot is reproducible from the GitHub code at a named commit**
(`<anonymized-for-review>/AAMAS2027-ConditionalMemory` (GitHub; de-anonymised link withheld during review)); the authoritative value
is `release_commit` in this snapshot's own `MANIFEST.json`, which travels with the data.

## 17. Licenses and redistribution

**Authoritative document: `docs/BENCHMARK_LICENSES.md`, shipped in this release with its
sha256 in `MANIFEST.json`.** That document governs; this section summarizes.

**Two different regimes in one release, and the row says which.** Read
`license_source_reference` and `text_fields_withheld` per row; do not assume.

| rows | source | licence | source text |
|---:|---|---|---|
| 16,535 | LongMemEval-V2 | Apache-2.0 | ✅ redistributed, with attribution and a NOTICE |
| 154 | SciCode | Apache-2.0 | ✅ redistributed (the memory text; the reader outputs were never persisted — §19.14) |
| **127** | **SWE-bench Verified** | 🔴 **none declared** | ❌ **withheld — metrics and ids only (§19.15)** |

So 16,689 of 16,816 rows carry their source text and **127 do not**. The 127 are
not a subset you can opt into: an absent licence is not a permissive licence.

**Withheld by policy, and absent from this release:**

| source | status |
|---|---|
| LongMemEval **V1** source text | ❌ V1's own grant is MIT, but ~51% of its sessions derive from **ShareGPT/UltraChat**, which carry their own upstream terms MIT does not override. No V1 row is in this release. |
| **BEAM** | ❌ Data is **CC BY-SA 4.0**; ShareAlike is infectious. BEAM-derived rows must ship as their **own** CC BY-SA 4.0 dataset and may never be merged here. The exporter **refuses** to place them in this dataset. |
| SciCode `test_data.h5` | ❌ Distributed via Google Drive with **no licence stated**. |
| LongMemEval-V2 bulk trajectories / screenshots | ⚠️ Permitted but ~1.14 GiB+; we ship ids + spans, not the corpus. |

Withheld fields carry the literal `__WITHHELD_SEE_LICENSE__` with
`text_fields_withheld` and `reconstruction_required` recorded per row — **a withholding is
visible, never silent.** In this release that is **127 SWE-bench rows, 5 fields each**;
`text_fields_withheld` is `[]` on the other 5,797.

### 🔴 Two different sentinels, which must never be read as the same thing

A field can be empty for two unrelated reasons, and this release uses **two
distinct literals** so a consumer can tell them apart without guessing:

| literal | means | appears in v0.4 |
|---|---|---|
| `__WITHHELD_SEE_LICENSE__` | *The text exists and we may not redistribute it.* A **licence** restriction. Always accompanied by the field's name in `text_fields_withheld`. | 5 fields on all **127 SWE-bench** rows (§19.15) |
| `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` | *The text was never written down, by anyone. No licence is involved.* A **persistence** gap in the runner. | `output_with_memory` and `output_without_memory` on all **154 SciCode** rows |

**The two never appear on the same row, and neither is a digest.** A SWE-bench
row's outputs are withheld (we hold them); a SciCode row's outputs are gone (nobody
holds them). Swapping the literals would publish a false stated reason in both
directions at once — asserting a restriction SciCode does not impose, and
asserting an absence that would excuse us from a restriction that does apply.

So on a SciCode row, `memory_text` carries its **real content** (Apache-2.0
permits it) while the two reader-output fields carry
`__OUTPUT_NOT_RETAINED_BY_THE_RUN__`: the SciCode harness scored each completion
and recorded `provenance.response_chars_*` but did not keep the string. The
sentinel is **not** a digest — a digest would claim "here is a fingerprint of the
text", and this claims "there is no text to fingerprint". The validator accepts
it **only** on a row that proves the completion was non-empty by carrying a
measured `response_chars_* > 0`, so it cannot be used to paper over an
empty-output failure.

**Reading `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` as a licence withholding would be
a false statement about SciCode, which withholds nothing.**

## 18. Models, clusters, and version provenance

| Role | Value |
|---|---|
| Reader | `gpt-oss-120b` on **Metis** |
| Memory writer | **none** — `none:deterministic_span` (raw) |
| Embeddings | `Salesforce/SFR-Embedding-Mistral` on **Sophia**, dim 4096 |
| Decoding | `temperature = 0`, `max_tokens = 512`, `reasoning_effort = low` |
| Verifier | the benchmark's own per-question `eval_function`, vendored at `f8ba659e237c` |

⚠️ **The model-name asymmetry across clusters is real and preserved**: the same logical
model is `gpt-oss-120b` on Metis and `openai/gpt-oss-120b` on Sophia. Group by
`(reader_model, reader_cluster)`, never by `reader_model` alone.

### 18.1 🔴 TWO READERS from v0.5, and `reasoning_tokens` means different things on each

🔴 **The length control does NOT add a second reader.** All 4,432 of its rows are
`gpt-oss-120b` on `metis`; the experiment varies the MEMORY, holding the reader fixed.
Its arm names (`trunc_last_matched`, …) name memory constructions, never models — see
§21.2 before parsing any `condition_id`.

| `reader_model` | rows | `reasoning_tokens` |
|---|---:|---|
| `gpt-oss-120b` | **13,998** | an **int** on 13,844; **`null` on 154** |
| `gemma-4-31B-it` | **2,818** | **`null` on all 2,818 — an ABSENCE, never 0** |

Measured per arm, not asserted. Across v0.6's **4,432 new rows** (all gpt-oss):
`int` on **4,432**, `null` 0, `0` **0**. Across all **16,816**: gpt-oss `int` 13,844 /
`null` **154**, Gemma `null` 2,818 / `0` **0**. **`reasoning_tokens` is `0` on zero rows
of this release**, under either reader.

⚠️ The 154 gpt-oss nulls are **SciCode** rows, and they are a *different kind of
absence* from Gemma's — which is exactly why the validator treats them differently:

| | SciCode's 154 nulls | Gemma's 2,818 nulls |
|---|---|---|
| reader | `gpt-oss-120b` on `metis` | `gemma-4-31B-it` on `metis` |
| does that reader report the field? | **yes** | **no** |
| so a null means | the run **did not record** a value the endpoint would have given | the endpoint **never emits** the field |
| validator verdict | `reasoning_tokens_missing` ×**154** | **no warning** — correct behaviour, not a silence |

Verified by running the validator on each slice: SciCode's 154 rows raise 154
`reasoning_tokens_missing`, the 570 Gemma session-matched rows raise **0**, and planting
`reasoning_tokens = 0` on a Gemma row raises **`absent_reported_as_zero`**. The check's
subject is the **(cluster, model) pair**, never the cluster alone.

**Two nulls with different reasons must not be pooled into one count.** An earlier draft
of this very table said gpt-oss carried an int "on every row" (false by 154) and then
explained the 154 as a cluster that does not report the field (also false — metis does;
it is *that run* that did not record it). Both are corrected here rather than quietly
dropped.

🔴 **`reasoning_tokens = 0` would be a fabricated measurement.** metis/`gemma-4-31B-it`
returns no `completion_tokens_details` object at all, while `gpt-oss-120b` on the *same
cluster* does. This is defect 18 in the project's register: the capability was once keyed
on the **cluster**, on a premise measured on one model, which is a property of the model
and not of the cluster. **Never sum `reasoning_tokens` across readers** and never fill a
Gemma null with zero — exclude it from the denominator. A total-token cost comparison
between the two readers is therefore **not** apples-to-apples and this release does not
present one.

⚠️ **`reader_reasoning_effort` is `none:not_applicable` on every Gemma row**, because the
parameter does not exist for that model. It is not `low` and must not be pooled with
gpt-oss's `low` as if both named a setting someone chose.

## 19. 🔴 Limitations and known measurement artifacts

Each of these is a **measured** constraint with a command behind it.

1. **The three arms are not balanced.** Of the **5,643 LongMemEval-V2** rows,
   4,519 are `raw`; Summary and Structured contribute 570 and 554. The representation
   comparison (§12.1, §14.1) is therefore run on the **277 design cells present in all
   three**, over **57 memories** — not on the full corpus — and that is the denominator
   every representation claim should be read against. A Raw-only statistic computed
   over all 5,643 rows is *not* comparable to the matched subset.
   **This limitation is worse on the other two benchmarks, not better:** SciCode has
   only one arm (§19.14) and SWE-bench's three arms rest on 76 scorable cells of 127
   (§19.15). **No representation claim in this card is a cross-benchmark claim.**
2. **93.6% of memories are embedded from a TRUNCATED PREFIX.** The embedding server's real
   ceiling cannot be counted locally (the budget is enforced in Qwen tokens; the server
   tokenizes with Mistral), so a conservative 2,000-Qwen-token budget is used. At that
   budget only **29 of 1,889** units fit whole. In this release, **2,512 of 2,599** screened
   rows have `input_truncated = true` (**4,336 of the 5,643 LongMemEval-V2 rows**;
   the SciCode and SWE-bench rows have no embedding path at all, so they are outside
   this denominator rather than counted as untruncated).
   So `semantic_similarity` describes a **prefix**, not
   the memory the reader saw. Direction of the bias is predictable: truncation **attenuates**
   any similarity–utility relationship toward zero — which **cuts against our own
   convenience**, since "similarity predicts utility poorly" is a claim adjacent to ours.
   **ΔU is unaffected**: utility is measured by execution with the full memory in context.
3. **Leakage rates are LOWER BOUNDS, because of a bug in the benchmark's own scorer.**
   `normalize_phrase` in the official `qa_eval_metrics.py` strips punctuation **without
   inserting a space**, so `value='GPS…` collapses to `valuegps…` and a genuine leak goes
   undetected; 594 cells were caught by our detector and missed by the official one. Also:
   never quote the pooled leak rate alone — it falls monotonically with gold-answer length
   (23.98% at 6–12 chars → 7.43% → **3.33%** above 30 chars), which is a **degeneracy
   signature** of short answers appearing by chance, not a property of memory.
4. **The variance decomposition is UNIDENTIFIABLE, and it was predicted before the run.**
   Two reasons, both structural: `F_exec = 0` (§11), and **38% of tasks are seen by exactly
   one memory** (83 of 218), contributing nothing to separating the task main effect from
   the interaction. **No share is quoted from a clipped ratio.** Adding compute does not
   fix this; it would need a corpus where memories and tasks overlap more densely.
5. **No harmful-memory rate is claimable** (§13).
6. **The memory→task pairing is ours, so nothing here is a natural base rate** (§8).
7. **Bearing is scarce, and that caps the headline's precision.** A memory bears on a median
   of **one** future task out of hundreds. The flip-rate denominator is 46 memories on only
   **23 distinct trajectories** — six page visits from one browsing episode are six views of
   one episode, not six independent memories — so a Wilson interval treating them as
   independent is **too narrow**. Report the episode-clustered reading as the governing one.
8. **`leakage_flag` and the bearing detector are the same instrument on `raw`, and
   v0.2 shows they come apart on the compressed arms.** On the **1,979 screened rows**
   (the only rows where both are populated):

   | arm | `leakage_flag == detector_fires` |
   |---|---|
   | raw | **855 / 855** — identical, as in v0.1 |
   | summary | 334 / 570 |
   | structured | 318 / 554 |

   On raw they are **not independent signals**, so a "leakage-controlled bearing effect"
   cannot be computed from these two columns (§9). On the compressed arms they diverge
   in a specific direction: in **466 of the 472** disagreements the detector fires while
   `leakage_flag` does not — i.e. the screen singled the *source span* out for this task,
   but the compressed memory no longer contains the leaking string. **That is a
   consequence of compression, not a second opinion about bearing**, and it is measured
   here rather than interpreted: we do not claim it explains §12.1.
9. 🔴 **A scorer-composition confound in the paired contrast — and it acts AGAINST the
   effect.** Each task keeps the benchmark's own `eval_function`, so this is *not*
   arm-dependence (which the protocol forbids) — but **25 of 60** memories draw on a
   different set of scorers in BEARING than in MATCHED_CONTROL, so the pooled contrast
   differences two scorer mixes as well as two strata. Re-derived from the v0.2 file:

   | subset | memories | paired B−MC |
   |---|---:|---:|
   | scorer mix **constant** | 35 | **+0.3786** |
   | scorer mix **changed** | 25 | **+0.2737** |
   | pooled | 60 | **+0.3349** |

   **The direction matters and is easy to get backwards.** The clean subset — the 35
   memories where the confound cannot operate — shows the **LARGER** effect. So the
   confound is *diluting* the pooled estimate, not manufacturing it: correcting for it
   would move the headline **up**, not down. That makes it a caveat on the precision of
   +0.3349, not a threat to the finding. It is still reported, because a confound that
   happens to work in your favour is still a confound, and the reader should not have to
   take our word for which way it points.
10. **Single reader model, single cluster, one corpus.** Cross-model generality is untested.
11. **Constructed filler contexts** (K = 4 memories) are smaller than a realistic agent store.
12. **English only**, web/enterprise GUI trajectories only.
13. 🔴 **v0.2: the Raw arm and the two new arms were run on DIFFERENT DAYS, and the
    serving endpoint moved between them.** Raw was collected 2026-09-29, Summary and
    Structured on 2026-09-30. Found by a control that had no reason to fail: the WITHOUT
    arm renders byte-identical context in all three representations, so its answers must
    agree. **Within** the 09-30 run they do exactly — summary-WITHOUT vs
    structured-WITHOUT identical on **554/554**, and replicate-to-replicate identical on
    **285/285** and **277/277**. Against the 09-29 Raw run, on prompts re-derived and
    hash-matched byte-identical, they do not: **text differs on 302 of 570 rows (53.0%)**
    and **reward on 14 (2.46%)**.

    A cache-disabled probe settles which side moved: same-minute repeats **6/6**
    identical, reproduces the 09-30 answer **6/6**, reproduces the 09-29 answer **2/6**.
    So this is a **serving change between the two days**, not temperature-0 sampling
    noise.

    **Sized, not assumed.** Raw's WITH arm was re-measured on 100 cells on 09-30 with the
    cache disabled and the target position asserted to reproduce the original on 100/100:
    reward identical on **86/100**, changed on 14 (**7 up, 7 down**), **mean reward
    0.3100 → 0.3100, difference +0.0000**. The drift is symmetric and mean-preserving on
    that sample, and a fully same-session Raw ΔU reproduces the contrast (summary−raw
    −0.1515 same-session vs −0.1616 cross-session, n=99).

    **The §12.1 conclusion does not rest on the cross-session join.** But every
    Raw-vs-new comparison in this release carries a per-cell noise term a same-session
    comparison would not, and a user computing a per-cell Raw-vs-Summary difference
    should know that before treating it as signal.
14. **`faithfulness_detail` is a proxy, not a judgment** (§7.2). High scores are weak
    evidence; only low scores are informative. `entity_support` is a lower bound with a
    measured false-alarm floor. No LLM judge was run, deliberately — a judge score
    silently entering a table labelled "deterministic proxy" is the failure being
    avoided.

## 19.14 🔴 SciCode ships 154 of 462 cells — the other 308 are NOT recoverable

> 🔴 **SciCode ships RAW ONLY — 154 of 462 cells.** The summary/structured memory
> TEXT was never persisted (the runner recorded `response_chars` and discarded
> content; the client had no `cache=`). It **CANNOT be reconstructed**:
> cross-session regeneration at fully matched settings is **0/8 byte-identical**
> while within-session is **3/3** (defect 22). Their reward measurements remain
> **VALID and are not retracted**. No text was fabricated or regenerated and
> presented as the original. **SciCode is therefore NOT representation-matched
> where LongMemEval is.**

**v0.3 adds SciCode, and it adds only its `raw` arm. State this before using the
benchmark comparison: the SciCode rows are not representation-matched, and the
LongMemEval rows are.**

| SciCode | cells | shipped |
|---|---:|---|
| `raw` | 154 | ✅ all 154 |
| `summary` | 154 | ❌ none |
| `structured` | 154 | ❌ none |
| **total** | **462** | **154 (33.3%)** |

**This is not a licence withholding.** SciCode is Apache-2.0 on both code and
data and its content may ship — which is why these rows carry their real
`memory_text` rather than a `__WITHHELD_SEE_LICENSE__` sentinel. It is a
**persistence gap**: `scripts/scicode_pilot.py` held the written memories in
process memory, passed no cache to the client, and recorded `len(content)` while
discarding the text. There is no write cache (verified by reading the
`benchmark` field of all 16,016 cache rows across 16 files: 16,014
`longmemeval_v2`, 2 `cache_separation_proof`, **0 `scicode`**).

### Why the text was not simply regenerated

The writers run at temperature 0, so regenerating them and proving identity
looked straightforward. It was attempted, with an independent proof available:
every WITH arm-run recorded the server's `prompt_tokens`, which is a function of
the exact prompt bytes and therefore of the memory text inside them.

**The proof ran, and it refused the text.**

| representation | cells whose recomputed `prompt_tokens` matched the recorded value |
|---|---|
| `raw` | **154 / 154** ✅ |
| `summary` | 5 / 154 ❌ |
| `structured` | 0 / 154 ❌ |

`raw` matches because it involves **no model call at all**: the raw memory *is*
the source segment, verbatim, so it is re-derived deterministically from the
benchmark corpus.

The reason the other two fail is that **the endpoint is not reproducible across
sessions**, which was measured directly rather than inferred:
`results/repr_scaleup/memories.jsonl` stores 60 Summary memories written by the
same writers, on the same model, *with their text*. Re-running them reproduces
**0 of 12 byte-identically**, while the writer's own `prompt_tokens` matches
**12 of 12** — the same prompt was sent and a different answer came back. Within
a single session the same segment gives the same bytes (4/4 draws). So
*within-session determinism is real and is not the property recovery needs.*

The 5 matching Summary cells are **chance, not partial recovery**: two
independent regenerations of the same segment differ in text, and their token
counts coincide anyway ~5–8% of the time, which predicts ~2–3 spurious
per-memory matches over 34 memories. That is what was observed.

### What this means for a reader

* **Do not compare SciCode across representations.** Only one exists here.
* **Do not treat SciCode's 154 as 462 with some rows missing.** The 308 absent
  cells were executed and scored — their rewards exist — but the memory whose
  utility they measure cannot be shown to anyone, so no row can honestly carry
  it.
* A regenerated memory would have been fluent, correct about the right segment,
  and **wrong**. Nothing downstream would have objected. The `prompt_tokens`
  check is the only reason this is a documented gap rather than 308 plausible
  rows.

Evidence: `results/scicode/memory_recovery_report.json` (per-cell verdicts, the
positive control, and both nulls).

### The two cross-session numbers are two measurements, not one quoted twice

`0/8` and `0/12` appear above and they are **different subjects measured on
different corpora**. They corroborate each other only because they were taken
independently; neither is a restatement of the other, and they must not be
pooled into "0/20".

| figure | subject | settings | source |
|---|---|---|---|
| **0/8** byte-identical, vs **3/3** within-session | 8 ground-truth LongMemEval summaries | fully matched: `max_tokens=512`, temp 0, `reasoning_effort=low`, segments rebuilt with `r1`'s own `load_segments` | `docs/DEFECT_REGISTER.md` defect 22 (not re-run for this release; quoted with its date) |
| **0/12** byte-identical, `prompt_tokens` matching **12/12**, vs **4/4** within-session | 12 Summary memories in `results/repr_scaleup/memories.jsonl` whose text is on disk | the writers' own production settings | `results/scicode/memory_recovery_report.json` → `cross_session_reproduction_control` |

The first was the measurement that **stopped** the regeneration; the second is
the control the recovery script runs and **raises on** if reproduction ever
succeeds, because a control that has stopped discriminating cannot support a
refusal.

### Honest limit of the identity check

A token count is not a hash. On the real subject, **0 of 4 one-character
perturbations** moved the count (appending a period, appending a space, deleting
the last character, changing a digit) — BPE re-tokenises the neighbourhood to the
same length. Two larger edits (one word, one sentence) were detected. So "matched"
means *same token count under every one of that memory's prompts*, which is strong
evidence and not proof of byte identity. The opposite null is clean: substituting a
**different** memory matched **0 of 3,003** times.

## 19.15 🔴 SWE-bench Verified ships METRICS AND IDS ONLY — no corpus text

**v0.4 adds 127 SWE-bench Verified cells, and not one byte of SWE-bench
content.** This is the strictest embargo in the release and it has a different
cause from SciCode's gap, so the two must not be read as the same situation.

| | SciCode (v0.3) | SWE-bench Verified (v0.4) |
|---|---|---|
| why text is absent | **PERSISTENCE** — never written down | **LICENCE** — exists, may not be redistributed |
| sentinel in the row | `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` | `__WITHHELD_SEE_LICENSE__` |
| `text_fields_withheld` | `[]` — nothing withheld | 5 fields, listed per row |
| upstream licence | Apache-2.0, permits redistribution | 🔴 **none declared** |
| could we ship it if we chose? | **no** — it does not exist | **no** — we have it and may not |

### Why nothing textual ships

`princeton-nlp/SWE-bench_Verified` **declares no licence.** The HF API returns
`cardData.license: None`, the tag list carries no `license:*` entry, and the
card text states none. The MIT grant covers the **harness code**, not the
corpus, and the underlying issue text and patches belong to the upstream
projects — every instance here is `django/django` or `sympy/sympy`, both
BSD-3-Clause, neither Princeton's to relicense nor ours.

> **An absent licence is not a permissive licence, and `gated: false` means
> *fetchable*, not *redistributable*.**

So five fields carry `__WITHHELD_SEE_LICENSE__` on all 127 rows and are named in
each row's `text_fields_withheld`: `memory_text`, `future_task_text`,
`output_with_memory`, `output_without_memory`, `source_episode_metadata`. **A
withholding is declared, never silent** — a blanked field a row does not admit
to blanking would let a consumer filtering on that list silently get the wrong
rows, and `schema.assert_content_redistributable` (export GATE 6) refuses it.

### What ships, because it is ours or is a pointer

Upstream `instance_id` values (identifiers, not content) in
`provenance.memory_instance_id` / `task_instance_id`; our derived measurements —
reward, `delta_utility`, both-arms-fail, edit status, contagion diagnostics,
localizer recall, token counts, representation label; and model/config metadata.
`provenance.prompt_sha256_*` identifies each prompt **without redistributing a
byte of it**, and `provenance.reconstruct_from` names the upstream parquet with
its sha256 so any cell can be rebuilt from the source dataset.

### 🔴 `memory_id` on these rows is NOT a content hash

On every other benchmark here `memory_id` hashes the memory text. It cannot
here: the SWE-bench runner holds memory bodies in a local dict and **never
persists them**, so no unredacted ledger of that text exists anywhere — this is
not text withheld from you, it is text nobody has. `memory_id` is therefore
minted over the sentinel and identifies
`(memory_instance_id, memory_representation)`. **Rebuilding the text from
upstream and re-deriving the hash gives a DIFFERENT value, and that is expected,
not corruption.** Join on the instance ids. Every row says so in
`provenance.memory_id_basis`, and the validator flags it per row as
`id_unverifiable_withheld_input` rather than passing silently — a check that
did not run is reported, not claimed.

### 🔴 Defect 21: 37 manufactured `0.0` rewards were demoted before export

`status_lines=0` in an arm's test detail means the suite **printed no verdict at
all** — an import error, a collection error, a missing test id. The harness
never asked the question, so a stored `0.0` records *"the model's fix was
wrong"* where the truth is *"no evidence exists"*. On this benchmark that
**manufactures harm out of a collection error**.

The scorer is fixed; these artifacts were written before the fix, so the
correction is applied on read:

| | |
|---|---:|
| arm-reads with `status_lines=0`, demoted to `null` | **37** (django 27 · sympy 10) |
| cells touched by at least one demotion | **25** of 127 |
| real `0.0` rewards (suite ran and failed) left untouched | **110** |
| rewards with a real verdict, preserved unchanged | **179** |

**No manufactured `0.0` is in this release.** Each affected row records which
arm moved, in `provenance.reward_demoted_manufactured_zero_{with,without}`, with
the rule in `provenance.manufactured_zero_rule`. A demoted read is `null` —
*could not be scored* — and never `0.0`.

The demotion is **not reimplemented** by the exporter: it is the same function
the analysis uses, which carries a positive control proving it moves a
manufactured zero, **leaves a real `0.0` untouched**, and is idempotent. Two
copies of a correction are two chances to correct differently.

### Composition and the caveats that go with it

| | raw | summary | structured | total |
|---|---:|---:|---:|---:|
| `django/django` | 32 | 32 | 32 | 96 |
| `sympy/sympy` | 9 | 11 | 11 | 31 |
| **total** | **41** | **43** | **43** | **127** |

Two `sympy` raw cells were **excluded for memory contagion** (diff syntax
leaking into a representation that must be compared against raw on equal
footing), which is why the raw column is 2 short. They are excluded in the
source run, not dropped silently here.

* **51 of 127 cells have a null `delta_utility`**, because at least one arm
  could not be scored. That is the honest denominator, and it is large.
* **Only 76 cells are scorable**, of which **69 are ties** — 4 helped, 3 hurt.
  Nothing here supports a claim about representation on SWE-bench, and none is
  made.
* **40 cells are both-arms-fail.** As elsewhere in this project, that rate is a
  property of the *pairing*, not a base rate of anything.
* `localizer_recall` is `False` on 50 of 127 cells: the memory's file was not in
  the localizer's output, so those cells test a harder condition than the rest.
  Split on it before pooling.
* **15 fields are null by benchmark exemption, each with its own stated reason**
  in `schema.BENCHMARK_NULLABLE_EXEMPTIONS['swebench_verified']` — no embedding
  path exists, no semantic type is derivable, latencies and retries were
  discarded by the runner. `embedding_calls` and `retry_count` are `null` and
  **not `0`**: zero would be a measured count of something never attempted.

## 20. Version history

| version | date | contents |
|---|---|---|
| **v0.1 `lmev2-derived`** | 2026-09-30 | First upload. 4,519 rows / 2,117 cells from three LongMemEval-V2 arms (screened, pilot, official-prompt). All `raw`. Schema v2, 97 fields. |
| **v0.3 `scicode-derived`** | 2026-09-30 | **+154 rows**: SciCode `raw` only (Apache-2.0, content ships). **5,797 rows total**, 98 fields, two benchmarks. 🔴 SciCode's Summary and Structured arms (308 cells) are **absent as unrecoverable** — a PERSISTENCE gap, never a licence withholding: the memory text was never persisted and regeneration is NOT byte-reproducible across sessions (measured: 0/8 at fully matched settings, and 0/12 against ground truth on disk). Adds §19.14 and GATE 5b. |
| **v0.2 `repr-derived`** | 2026-09-30 | **+1,124 rows**: the matched Summary (570) and Structured (554) arms over the same memories, tasks and reader. **5,643 rows total.** Schema **v3**, **98 fields** (`faithfulness_detail` added). `faithfulness_check` and `parent_memory_id` are now populated on the new rows (§7.1). Adds §12.1 (compression destroys the effect), §14.1 (the cost ranking reverses once formation is charged) and §19.13 (cross-session drift between the arms). |
| **v0.4 `swebench-metrics`** | 2026-10-01 | **+127 rows**: SWE-bench Verified, **metrics and ids ONLY** — the corpus declares no licence, so all 5 text fields are withheld per row and declared in `text_fields_withheld`. **5,924 rows total**, 98 fields, three benchmarks. 🔴 **37 manufactured `0.0` rewards demoted to null** before export (defect 21: a suite that printed no verdict is not a wrong answer). Adds §19.15. |

| **v0.5 `reader-generalization`** | 2026-10-02 | **+6,460 rows**, all LongMemEval-V2, all already schema v3. **12,384 rows total.** 🔴 **The first release with ANY `gemma-4-31B-it` reader row** — through v0.4 `reader_model` was `gpt-oss-120b` on 5,924/5,924, so the reader-generalization evidence base was reported in the paper and absent from the release. Four slices: the **session-matched reader transfer** (570+570), the **Writer × Reader factorial** (2,248+2,248), and **both** gold-free bearing screens (GF-LEX 656, GF-LLM 168). Adds §20.1 and two new validator warning codes (`id_collision_writer_collapse`, `cell_collision_writer_collapse`). |
| **v0.6 `length-control`** *(current)* | 2026-10-02 | **+4,432 rows**, all LongMemEval-V2, all `gpt-oss-120b`, all already schema v3. **16,816 rows total.** The pre-registered **length control** (§21): eight arms over one frozen 554-row cell set in a single session, design frozen at `f702aaf` **before execution**. Verdict **O2** — at a matched exposed-token budget the extractive and model-written arms do **not** separate, so Raw's advantage is an **exposure-budget** effect. 🔴 One arm (`trunc_last_20000`) is an **A/A control**, not a condition. Adds §21 and §22. **No evaluated row of this project remains unpublished-but-ready** (§22). |

### 20.1 🔴 What v0.5 adds, and what it deliberately does not

| slice | rows | canonical artifact | what it supports |
|---|---:|---|---|
| session-matched reader transfer | **1,140** (570 gpt-oss + 570 Gemma) | `results/raw_session_matched/raw_gptoss.jsonl`, `raw_gemma.jsonl` | The **canonical** reader-generalization result: paired ΔU difference **+0.0982**, task-clustered 95% CI **[+0.0247, +0.1730]**, over **275 cells / 123 tasks / 550 replicate rows**. Both arms were re-executed **in one session**, so the published figure is not confounded with a day-to-day endpoint shift. |
| Writer × Reader factorial | **4,496** (2,248 per writer) | `results/writer_factorial/factorial_cells_gptoss.jsonl`, `factorial_cells_gemma.jsonl` | Four **informative nulls**: no same-family writer–reader advantage is detectable; every contrast spans zero. |
| gold-free screen, **GF-LLM** | **168** | `results/deltau_goldfree_llm/cells.jsonl` | The gold-free bearing screen that **survives**: 15.6% → 50.0% on cells gold never selected. |
| gold-free screen, **GF-LEX** | **656** | `results/deltau_goldfree/cells.jsonl` | The gold-free screen that **disappears**. 🔴 **Published deliberately.** Reporting only the screen that worked would select an instrument on its own outcome — the one move that makes the surviving screen uninterpretable. |

**Deliberately NOT in v0.5**, verified by name rather than by a glob:

| excluded | why |
|---|---|
| the length-control experiment | **was excluded from v0.5, and the reason CHANGED while v0.5 was being built.** It was still running when that release was scoped; it reached a frozen verdict (`O2_EFFECT_DISAPPEARS_AT_MATCHED_LENGTH`) before upload. It was held out because its rows were **not in the audited set v0.5 was built and gated against**, not because the result was provisional — and that distinction was written down so the exclusion would not be silently inherited. ✅ **It was re-decided and SHIPS IN v0.6** (§21). This row is kept because it describes v0.5, which remains a published tag; it is not a statement about the current release. |
| `results/swebench/representations_v1.json` | **VOIDED** — its contagion screen false-positived on ASCII table borders (`+---+`) in issue text. Retained on disk as a record, never as an input. |
| `results/raw_session_matched_VOID_mislabelled/` | **VOID (defect 27)**: a runner hardcoded one arm's `condition_id`, so 570 rows claimed `gemma4_31B` while `reader_model` said `gpt-oss-120b`. Verified by row id: **0 of its 570** rows appear in this release. |
| calibration / debug / probe rows, superseded arms | not results. |

🔴 **No Gemma reader row existed in any prior tag**, so nothing in v0.5 supersedes a
published number; it adds the rows a reader needed to check one. The v0.4 rows are
re-shipped **byte-identical** — the migration that produced them reproduces its v0.4
inputs md5-for-md5, which was checked rather than assumed.

**Every v0.1 row is re-shipped under v3**, not left at v2: presence is the contract, so a
v2 row lacks `faithfulness_detail` and would fail the validator published beside it. The
re-migration was checked to reproduce v0.1's 4,519 rows **field-for-field**, with the sole
intended exception of `faithfulness_notes` — the sentence being corrected. The `v0.1`
tag keeps its own pinned copy of the v2 data and the v2 validator, so v0.1 remains
verifiable on its own terms.

Schema `p1mem_conditional_memory_utility_v3`, **98 fields**. **v3 added exactly one
field over v2**, `faithfulness_detail` (§7.2) — a bump rather than a cosmetic change,
because presence is the contract and a v2 row lacking the key fails v3 validation. v2 had
added 20 fields over v1: 17 from the required field list (chronology, lineage, quality,
bearing, efficiency, P3 groups), of which **3 remain null by design** with the reasons in
§7; plus 3 **export-provenance** fields (`license_policy`, `text_fields_withheld`, `reconstruction_required`) written by the
exporter rather than the runner. Those three were previously added to published rows
*without* being in the schema, which made every published row fail the validator published
beside it — caught by downloading the release and running its own documented command, and
now prevented by GATE 4, which re-reads and re-validates the written file before it ships.

The authoritative definition is `code/schema.py`; the validator is `code/validate.py`, and
it is tested by **deliberate corruption** — each test breaks a good row in one specific way
and asserts the specific issue code, because a check whose verdict is right for the wrong
reason is harder to catch than a wrong verdict.

**Verify this release yourself**, exactly as we do:

```python
import sys; sys.path.insert(0, "code")          # the shipped schema.py + validate.py
from p1mem import schema as S, validate as V
rows = S.load_jsonl("data/cells.jsonl", strict=True)
print(V.validate_dataset(rows).summary())        # expect: 16816 rows | 0 errors
```

Expected output, exactly — **0 errors and 6,160 warnings**, every warning intended and
documented:

```
16816 rows | 0 errors | 6160 warnings
  all_labels_undetermined: 1
  cell_collision_writer_collapse: 11
  id_collision_writer_collapse: 26
  id_unverifiable_withheld_input: 127
  provenance_incomplete: 5837
  reasoning_tokens_missing: 154
  scorer_composition_differs_across_strata: 1
  unknown_error_code: 2
  zero_execution_noise: 1
```

🔴 **The warning total rose from 1,703 at v0.5 to 6,160, and 4,432 of the increase is
one code on one new slice.** `provenance_incomplete` fires once per length-control row
because `provenance.config_sha256` is empty on that runner — the field is a
*completeness* flag, not a defect in the measurement, and it is reported rather than
suppressed. The remaining increase is 7 more `cell_collision_writer_collapse` and 18
more `id_collision_writer_collapse`: the length control reuses the frozen Summary and
Structured memory text, so it inherits the same byte-identical-rendering collisions
described below, on its own rows. **No new warning CODE appears at v0.6**, and the error
count stays 0.

🔴 **The two `*_writer_collapse` codes are new at v0.5 and are WARNINGS on purpose.**
`row_id` and `cell_id` are content hashes keyed (transitively) on `memory_text`. The
Gemma writer rendered two *different* source segments of episode `06c70de4`
(`13-14` and `17-18`) as **byte-identical** 68-token summaries, so 16 genuinely
separate rows mint 8 shared `row_id`s and 4 shared `cell_id`s. They are **not**
restated rows: different source spans, separate model calls, different outputs.
Through v0.4 the validator raised a hard `duplicate_row_id` whose own message —
*"append-only ledgers must not restate a row"* — is **false** on this case, and a
right verdict with a wrong stated reason is harder to catch than a wrong verdict, so
the collapse now gets its own code. The relaxation is narrow in four ways (every
colliding row must carry a positional locator; their positional units must be
pairwise distinct; `memory_text` must be byte-identical; counts must match) and five
planted defects — a true duplicate, a collision with differing text, a missing
locator, a repeated positional unit, and a double write hidden inside a collapse —
are each verified to **still** raise the hard error.

🔴 **Never join on `memory_id`, `cell_id` or `row_id`.** Join on the positional unit
`(memory_unit_locator, future_task_id, replicate_id, reader_model)`. A
content-addressed join would silently merge two experiences into one — which is the
measured cost of aggressive compression this release exists to expose.

`id_unverifiable_withheld_input` fires once per SWE-bench row and is **correct**:
those rows' `memory_id` was minted over text this release withholds, so the
validator declines to re-derive it and **says so** instead of passing silently
(§19.15).

**A warning here is a finding, not lint.** None of them is suppressed, and none should be
"fixed" by loosening the check that raises it.

`unknown_error_code` fires on 2 rows whose cell hit an `endpoint_error`: an operational
code outside the enum. Those rows correctly carry **no reward**, so no result was
fabricated to fill the gap.

## 21. 🔴 The length control — v0.6's new slice, and what it takes AWAY from our own claim

**4,432 rows. Eight arms. One frozen 554-row cell set. One session.** This is the
experiment that narrows this project's own representation result, and it is published
with the arms that produced the narrowing, not only the ones that survived it.

The design — the arms, the primary contrast, the estimator, the CI method, the controls,
and the meaning of **every possible outcome** — was frozen at repo commit `f702aaf`
**before a single reader call had been made against a truncated memory**. Nothing in it
was chosen after seeing a number.

### 21.1 The verdict: O2 — the representation effect does not survive a length control

| | Δ = ΔU(trunc_last_matched) − ΔU(summary), BEARING | 95% CI (task-clustered) | n |
|---|---:|---|---:|
| **PRIMARY** | **+0.0519** | **[−0.0678, +0.1727]** | 135 cells / 55 clusters |

The interval includes zero. At a matched exposed-token budget, a **content-blind
extractive slice** and a **model-written summary** are indistinguishable.

> **What Raw buys is the budget to carry the bearing content, at zero formation cost** —
> an **exposure-budget** effect, not a rewriting effect.

🔴 **This supersedes the causal reading of §12.1, not its numbers.** §12.1's measured
values stand. What changes is the explanation attached to them: "rewriting the
experience removes the benefit" attributes the loss to *rewriting*, and this experiment
attributes it to *length*. A reader using this dataset to check §12.1 should read §21
alongside it.

**The null is reportable because the test could have found the effect.** Planting the
published cross-session Raw−Summary gap (+0.2741) into the matched arm moves the primary
to **+0.3260 [+0.2069, +0.4445]** — detected; planting the in-session gap (+0.3209) gives
**+0.3727 [+0.2537, +0.4913]** — detected; planting **zero** reproduces the primary
exactly and does not exclude zero, so the detector is not vacuous. The design resolves a
true difference of about **0.12**, and the measured +0.0519 is below that. **This is a
measured indistinguishability, not a failure to look.**

**Utility tracks retained content, not token count.** At a *fixed* budget, keeping the
**end** of a page-visit segment rather than the beginning raises bearing-content
retention from 0.7% to 28.9% and ΔU by **+0.1037 [+0.0080, +0.2046]** — a contrast that
excludes zero while holding tokens constant.

### 21.2 🔴 Read `condition_id` as a MEMORY arm, never as a model

Every length-control `condition_id` has the form `lmev2_<arm>_lenctl_v1`. **The arm slot
names how the memory was CONSTRUCTED. It never names a model.** The reader is
`gpt-oss-120b` on all 4,432 rows and the writer is in `memory_writer_model`.

This warning is here because the *other* multi-arm slice in this dataset uses
`w<writer>_r<reader>` factorial ids (§20.1), and reading one convention under the other
produced two false alarms against a correct release. **A row's models are in its model
fields.** Verified on this slice, with a positive control proving the checker could fail:
**0 rows** carry a `condition_id` contradicting their `reader_model` or writer.

| arm | `condition_id` | `memory_representation` | rows | budget |
|---|---|---|---:|---|
| `raw` | `lmev2_raw_lenctl_v1` | `raw` | 554 | — (full span) |
| `summary` | `lmev2_summary_lenctl_v1` | `summary` | 554 | that cell's own summary length |
| `structured` | `lmev2_structured_lenctl_v1` | `structured` | 554 | that cell's own structured length |
| `trunc_last_matched` | `lmev2_trunclast_matched_lenctl_v1` | **`raw`** | 554 | matched to summary |
| `trunc_first_matched` | `lmev2_truncfirst_matched_lenctl_v1` | **`raw`** | 554 | matched to summary |
| `trunc_last_1024` | `lmev2_trunclast_1024_lenctl_v1` | **`raw`** | 554 | 1,024 |
| `trunc_last_4096` | `lmev2_trunclast_4096_lenctl_v1` | **`raw`** | 554 | 4,096 |
| **`trunc_last_20000`** | `lmev2_trunclast_20000_lenctl_v1` | **`raw`** | 554 | 20,000 — **A/A CONTROL, see §21.3** |

⚠️ **`memory_representation` is `raw` on all five truncated arms, and that is correct.**
It is a closed enum describing **how the memory was written down** — a truncated segment
is extractive verbatim text with **zero writer calls** — not which arm it belongs to. The
arm identity lives in `condition_id` and `provenance.arm`. Group by **`condition_id`**,
never by `memory_representation`, when you want the eight arms.

### 21.3 🔴 `trunc_last_20000` is an A/A CONTROL, not a ninth condition

**Do not count it as a condition. Doing so double-counts Raw.**

Its budget of 20,000 tokens exceeds the longest Raw memory in the cell set (19,801), so
the truncation rule removes nothing:

| check | measured |
|---|---|
| `memory_text` byte-identical to the `raw` arm | **554 / 554** |
| reward triples reproduced | **552 / 552 scored pairs** |
| reader outputs byte-identical | **552 / 552** |
| mean ΔU on BEARING | **+0.3433**, identical to `raw` to four decimals |

The two excluded pairs are *the same cell* failing in **both** arms — itself further
evidence the identity arm reproduces Raw rather than merely agreeing with it. Counting
`None == None` as agreement would have inflated the very control that exists to detect
errors, so unscored pairs are excluded from both numerator and denominator.

**It is in the release because an identity arm with a KNOWN CORRECT ANSWER is what
proves the new code path end to end** — it travels under a different `condition_id` and
a different content hash, so it is a genuinely separate set of 1,108 calls. All 8,834
stored cache keys remain distinct even though 1,040 context groups render identical
bytes across arms, so the two arms really did issue separate calls.

Any analysis that pools arms must therefore either **drop `trunc_last_20000`** or
**drop `raw`** — never both.

### 21.4 Rows that could not be scored, and the 0.0 that is not there

**6 rows of 4,432** carry a null reward, all `empty_output_finish_length` — the reasoning
model spending its `max_tokens` budget before emitting an answer. They are **2 in `raw`,
2 in `trunc_last_20000` (the same cell, both replicates — see §21.3), and 2 in
`trunc_last_4096`.**

🔴 **`reward is None` means COULD NOT BE SCORED and is never coerced to 0.0** (defect
21). Verified on this slice with a positive control: **every** null reward sits beside a
non-null `error_code_if_any`, and **every** non-null reward sits beside a null error
code — so there is no 0.0 standing in for an absence and no silent absence standing in
for a measurement. The primary contrast is unaffected: it compares `trunc_last_matched`
against `summary`, neither of which lost a row.

`reasoning_tokens` is an **int on all 4,432** of these rows and is **0 on none** of them.

### 21.5 Faithfulness on this slice — three different reasons for one null

This ledger was written directly at schema v3 and never passed through the migration
that fills a deliberately-null field's reason, so all 4,432 rows arrived with an empty
`faithfulness_notes`. `scripts/prep_v06_inputs.py` fills it **only where each note's
premise is re-derived as true on the row itself**, and refuses otherwise:

| rows | situation | what ships |
|---:|---|---|
| **1,202** | full-span extractive — text **is** the source span | `FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE`, unchanged. A source-grounded proxy would compare the text with itself and return 1.0 by construction. |
| **2,122** | truncated extractive — text is a verbatim **slice** of that span | a note that says exactly that. 🔴 The project's raw constant is **not** reused, because its own sentence ("the memory text IS the source span, verbatim") would be **false** here. Truncation removes content, and a tautological 1.0 says nothing about how much; `provenance.bearing_content_retained` is the field that does. |
| **1,108** | model-written (`summary` / `structured`) | the **real score**, attached: `faithfulness_check` (number_support) plus the full multi-axis `faithfulness_detail`, measured on the WRITE pass. |

🔴 **The 1,202/2,122 split is MEASURED, not read off a field.** Which rows are full-span
is decided by comparing each row's text with its own cell's full span; the
`provenance.identical_to_raw_text` flag is then **cross-checked against that
measurement** and a disagreement is a refusal. A planted row that set the flag true while
carrying truncated text was *accepted* by an earlier version of that script — it would
have shipped "the memory text IS the source span, verbatim" onto a row where it is false.
Four planted premise violations are now each refused and clean data is accepted
unchanged.

🔴 **The 1,108 scores are ATTACHED, not pointed at.** The first version of the fill wrote
a note saying "not scored here, see the write pass" and left the field null; the
validator rejected all 1,108 with `faithfulness_claimed_unscored_on_a_written_memory` —
a model-written memory **is** scorable, so a note denying it is false. That rule's own
comment warns against rewording a note until the guard's substring disappears, so the
note was not reworded: the measurement was attached, exactly as `migrate_schema_v2.py`
does for the §20.1 arms. The score reaches the row through **two independent join keys**
— `(memory_unit_locator, memory_representation)` and a sha256 of `memory_text` — which
were verified to select the **same** record on all 1,108 rows, against a negative control
that correctly resolves nothing. **24** of them carry a null `faithfulness_check` with a
non-null detail: those memories contain no numeric literal, so `number_support` has an
empty denominator, which `faithfulness.py` returns as `None` rather than a perfect 1.0
precisely so a number-free memory cannot lift a corpus mean.

### 21.6 Caveats that travel with this result

* **Total context is not matched**, only exposed *memory* tokens — median with-context
  is ~24.9k tokens for Raw and ~17.0k for the compressed arms. This is **conservative
  for the primary** (`trunc_last_matched` and `summary` are matched on both) and is a
  caveat only for Raw vs trunc.
* **The reader's tokenizer is not the budget's tokenizer.** Re-derived per cell, the
  length-controlled arm is a median **4 tokens shorter** than summary in `o200k_harmony`
  (n=57), so the extractive arm did not buy its null with tokens.
* **One cell's slice is 195 tokens against a 196-token budget.** The official tokenizer
  admits no prefix of exactly 196 tokens there. The rule asserts **maximality** — one
  more character must break the budget — which is well-defined where exact equality is
  not. **216 of 217** cut cells are exact, one is −1, **none is over budget**.
* **The summary writer can emit a gold string its source span never contained**: the
  detector fires on 3 of 142 MATCHED_CONTROL cells for `summary` and on **0 of 142** for
  every extractive arm. That is a property of the writer, not the detector, and it does
  not touch the BEARING contrasts.
* **"One session" is asserted from the rows, and the run ledger's own boolean says
  `false`.** That flag requires zero cache hits; there were **14**, against a cache that
  began **empty** (`n_preexisting_cache_rows: 0`), so those 14 were served from this
  run's own earlier calls and not from another session. All 4,432 rows carry **one**
  `run_id` and **one** `session_start_utc`, spanning 25.9 minutes. The flag is
  conservative, not contradicted — and it is reported here rather than quietly re-derived.
* **Not claimable**: that compression is as good as extraction *in general* (this is one
  positional rule, one corpus, one budget); that the pre-registered sensitivity rescues
  the representation story (it does not, and the precommitment forbids reading the
  verdict off it); or any effect conditioned on cells that retained the bearing content
  (**circular** — an effect measured on cells selected for it, pre-registered as excluded
  from the verdict and descriptive only).

**Artifacts**: `docs/LENGTH_CONTROL_PRECOMMITMENT.md` (frozen `f702aaf`),
`docs/LENGTH_CONTROL_RESULT.md`, `results/ledgers/length_control_result.json`
(canonical), `length_control_run.json`, `length_control_confound.json`.

## 22. 🔴 What is still NOT in this release, by name

**As of v0.6, no evaluated row of this project is unpublished-but-ready.** Every
exclusion below is structural — a licence, a persistence gap, or a VOID label — and none
of them is "a dataset we have not got around to publishing".

| excluded | rows | why — and why it cannot simply be added |
|---|---:|---|
| **BEAM**-derived rows | — | **Licence.** BEAM's data is **CC BY-SA 4.0** and ShareAlike is **infectious**: a dataset adapted from it must itself be CC BY-SA 4.0, which would silently relicense everything else here. It must ship as its **own** CC BY-SA 4.0 release attributing the BEAM authors. The exporter **refuses** BEAM rows outright, and that refusal is exercised with a positive control on every build. Aggregate statistics over BEAM are not adaptations and remain safe to report in the paper. |
| SciCode **Summary / Structured** | 308 cells | **Persistence, not licence.** The memory text was never written to disk and is **not recoverable**: regeneration is not byte-reproducible across sessions (0/8 at fully matched settings). SciCode is Apache-2.0 and withholds nothing. §19.14. |
| SWE-bench **corpus text** | 127 rows' 5 fields | **Licence.** `princeton-nlp/SWE-bench_Verified` declares none. The metrics and ids ship; the text carries `__WITHHELD_SEE_LICENSE__` and is declared in `text_fields_withheld`. §19.15. |
| `results/swebench/representations_v1.json` | — | **VOID.** Its contagion screen false-positived on ASCII table borders (`+---+`) in issue text. Kept on disk as a record, never as an input. |
| `results/raw_session_matched_VOID_mislabelled/` | 570 | **VOID (defect 27).** A runner hardcoded one arm's `condition_id`, so those rows claimed `gemma4_31B` while `reader_model` said `gpt-oss-120b`. Verified **by row id**: 0 of 570 appear in any release. |
| LongMemEval **V1** source text | — | V1's own grant is MIT, but ~51% of its sessions derive from **ShareGPT/UltraChat**, whose upstream terms MIT does not override. |
| SciCode `test_data.h5` | — | Distributed with **no licence stated**; a per-field carve-out the exporter enforces separately (GATE 3c). |
| endpoint caches, embedding stores, bulk trajectories | — | Not results. Permitted but large (~1.14 GiB+); we ship ids and spans. |
| the **cross-session** reader-transfer comparator | 1,140 | **Superseded, not hidden.** `results/gemma_reader/transfer_cells.jsonl` measured the two readers on different days; the **session-matched** arms that replace it for the quoted number ARE published (§20.1). Publishing both would invite citing the confounded one. |
| calibration, debug and probe rows | — | Not results. |

## 23. Relation to P3

`receiver_id`, `receiver_role`, `visibility_mask`, `team_reward` and `propagation_metadata`
are **P3-reserved and null in P1**, enforced by the validator. They exist now so a
multi-agent P3 row and a single-agent P1 row share one schema instead of forking it. P1
measures whether a memory helps **its own** future task; P3 asks whether it helps **another
agent's**, which needs a receiver identity P1 has no value for.

## 24. Citation and attribution

**Cite the paper:** *What Is This Memory Useful For? Measuring Task-Conditioned Utility in
Long-Term Agent Memory* (AAMAS 2027). **Code:**
`<anonymized-for-review>/AAMAS2027-ConditionalMemory` (GitHub; de-anonymised link withheld during review).

Derived from **LongMemEval-V2** (Wu, Ji, Kawatkar, Kwan, Gu, Peng, Chang; UCLA; arXiv
2605.12493), used under Apache-2.0 at commit `2cc8c540bdb87fe6761629b585e727e1c4704520`.
Our derived annotations are released under the same terms. The vendored scorer
`qa_eval_metrics.py` is redistributed verbatim with its Apache-2.0 header.

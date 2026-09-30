---
pretty_name: "Conditional Memory Utility Dataset (AAMAS 2027)"
license: apache-2.0
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
  - `license: apache-2.0` is correct for THIS release because every row derives from
    LongMemEval-V2 only (verified: 4,519/4,519 rows carry
    license_source_reference='longmemeval_v2:Apache-2.0'). If a BEAM-derived row is ever
    added, this file is WRONG and the row belongs in a separate CC BY-SA 4.0 dataset.
-->

# Conditional Memory Utility Dataset

> **v0.1 — `lmev2-derived`. 4,519 real evaluated cells, 0 fabricated rows.**
> This release contains the LongMemEval-V2 arms only. The headline result is a
> **negative result on the project's own founding hypothesis** (§12), and the
> limitations in §18–19 are measured constraints, not boilerplate.

---

## 1. Name, purpose, and research goal

**Conditional Memory Utility Dataset**, released with the AAMAS 2027 submission
*Measuring task-conditional value in long-term agent memory*.

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

| Benchmark | Role in THIS release | Status |
|---|---|---|
| **LongMemEval-V2** (`xiaowu0162/longmemeval-v2`) | **the only source of every row** | released here |
| LongMemEval V1 | not in this release | annotations only, if ever |
| BEAM | **excluded by license** | must ship as a separate CC BY-SA 4.0 dataset |
| SciCode | not run | — |

Measured, not assumed: **4,519 / 4,519** rows carry
`license_source_reference = 'longmemeval_v2:Apache-2.0'`. Pinned benchmark revision
`2cc8c540bdb87fe6761629b585e727e1c4704520`.

## 4. Source episodes and the memory unit

The memory unit is a **page visit**: one maximal same-URL run of states in a past agent
trajectory. The boundary is drawn by **the past agent's own behaviour** (it navigated
away), so it is a naturally occurring span, not a window we imposed and certainly not one
fitted to any question.

Measured over the released rows:

| quantity | value |
|---|---|
| rows | **4,519** |
| cells (memory × task × condition) | **2,117** |
| distinct memories | **117** |
| distinct future tasks | **275** |
| distinct source trajectories | **77** |
| errored cells (no outcome, no reward) | **2** |

## 5. Memory representations

**This release contains `raw` only** — 4,519/4,519 rows. Raw is the verbatim source span:
deterministic, no writer model, no extraction call. Summary and structured representations
are defined in the schema but **not present here**, and several fields are null *because*
of that (§7).

Raw selection uses no future task and there is deliberately **no "pick the most informative
span" rule** — that would smuggle in the value judgment the dataset exists to measure.

## 6. Memory acquisition and writer blindness

> **The memory writer never observes the future evaluation task.** `m = W(e)`, never `W(e, t)`.

Enforced structurally, not asserted: the writer's signature takes an episode and no task
argument; memories are content-hashed **before** the pairing step exists. For raw there is
no writer model at all (`memory_writer_model = 'none:deterministic_span'`), so
task-directed writing is impossible by construction.

## 7. Fields that are null, and exactly why

**A null here is a documented fact, never an oversight.** Five fields are null on every row:

| field | why it is null |
|---|---|
| `source_episode_completion_timestamp` | **No wall-clock field exists anywhere in LongMemEval-V2.** An exhaustive key scan of all 1,870 trajectories returns only `{domain, environment, goal, id, outcome, start_url, states}`, and states carry only `{accessibility_tree, action, screenshot, state_index, step, thought, url}`. `state_index` is an *order*, not a timestamp. (LongMemEval **V1** does ship real dates, so the field is defined for a future V1 arm.) |
| `parent_memory_id` | Every row is `raw`. A raw span has no parent *memory*; its parent is the episode, already in `source_episode_id`. |
| `faithfulness_check` | **There is no valid automatic score for raw.** Raw *is* the source text, so a source-grounded proxy compares the text with itself and returns 1.0 by construction. A column of 1.0s would assert that every memory was checked and passed. See `faithfulness_notes` on each row. |
| `context_budget` | **No truncation budget was ever enforced.** `memory_tokens_exposed == memory_tokens_retrieved` on 2,599/2,599 screened rows and the runner has no context cap. (The 20,000-token cap in our design docs is a memory-*selection* rule, not an exposure cap.) |
| `propagation_metadata` | P3-reserved. P1 is single-agent; a value could only be fabricated. The validator rejects a non-null value. |

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

🔴 **`F_exec = 0`, measured.** All 1,157 screened cells produced **byte-identical output in
both arms across every replicate** (`confidence_or_stability = 1.0` everywhere). This is
real temperature-0 determinism, **not cache reuse**: the cache holds 5,198 distinct keys
(`replicate_id` is a key field) spread 2,314/2,314/570 over replicate ids 0/1/2, so each
replicate was a separate real endpoint call.

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
| `extraction_cost_proxy = 0.0` | a **measurement**: raw makes no call, so nothing was billed. Raw's real advantage, and it must survive into the efficiency frontier or model-written representations look free. |
| `memory_extraction_latency = null` | **no call was made.** Excluded from a mean latency, never averaged in as 0.0. |
| `reasoning_tokens = null` | **not reported by this cluster.** Metis reports it; Sophia omits it. Must be excluded from a denominator, not summed as zero. |

`compression_ratio = 1.0` on every row: raw **is** the source span, verified by joining all
2,599 screened rows to the unit manifest (`memory_tokens == n_tokens`, 2,599/2,599). It is
stored anyway because raw's 1.0 is the control that makes a future summary arm's 0.2
interpretable.

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

## 17. Licenses and redistribution

**Authoritative document: `docs/BENCHMARK_LICENSES.md`, shipped in this release with its
sha256 in `MANIFEST.json`.** That document governs; this section summarizes.

Every row here derives from **LongMemEval-V2, Apache-2.0** (verified on 4,519/4,519 rows),
so source text **is** redistributed, with attribution and a NOTICE of modifications.

**Withheld by policy, and absent from this release:**

| source | status |
|---|---|
| LongMemEval **V1** source text | ❌ V1's own grant is MIT, but ~51% of its sessions derive from **ShareGPT/UltraChat**, which carry their own upstream terms MIT does not override. No V1 row is in this release. |
| **BEAM** | ❌ Data is **CC BY-SA 4.0**; ShareAlike is infectious. BEAM-derived rows must ship as their **own** CC BY-SA 4.0 dataset and may never be merged here. The exporter **refuses** to place them in this dataset. |
| SciCode `test_data.h5` | ❌ Distributed via Google Drive with **no licence stated**. |
| LongMemEval-V2 bulk trajectories / screenshots | ⚠️ Permitted but ~1.14 GiB+; we ship ids + spans, not the corpus. |

Withheld fields would carry the literal `__WITHHELD_SEE_LICENSE__` with
`text_fields_withheld` and `reconstruction_required` recorded per row — **a withholding is
visible, never silent.** In this release nothing is withheld, because everything is
Apache-2.0.

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

## 19. 🔴 Limitations and known measurement artifacts

Each of these is a **measured** constraint with a command behind it.

1. **Raw representation only, at scale.** 4,519/4,519 rows are `raw`. Nothing here supports
   a claim about summary or structured memories, and the representation comparison the
   schema is built for is **not in this release**.
2. **93.6% of memories are embedded from a TRUNCATED PREFIX.** The embedding server's real
   ceiling cannot be counted locally (the budget is enforced in Qwen tokens; the server
   tokenizes with Mistral), so a conservative 2,000-Qwen-token budget is used. At that
   budget only **29 of 1,889** units fit whole. In this release, **2,512 of 2,599** screened
   rows have `input_truncated = true`. So `semantic_similarity` describes a **prefix**, not
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
8. **`leakage_flag` is the same instrument as the bearing detector** (2,599/2,599), so the
   two are not independent signals here (§9).
9. **A scorer-composition confound in the paired contrast.** Each task keeps the benchmark's
   own `eval_function`, so this is *not* arm-dependence — but **25 of 60** memories draw on a
   different set of scorers in BEARING than in MATCHED_CONTROL. Split: **+0.3786** on the 35
   memories whose scorer mix is constant, **+0.2737** on the 25 where it changes, **+0.3349**
   pooled. The effect survives in both, but the pooled number differences two scorer mixes
   as well as two strata.
10. **Single reader model, single cluster, one corpus.** Cross-model generality is untested.
11. **Constructed filler contexts** (K = 4 memories) are smaller than a realistic agent store.
12. **English only**, web/enterprise GUI trajectories only.

## 20. Version history

| version | date | contents |
|---|---|---|
| **v0.1 `lmev2-derived`** | 2026-09-30 | First upload. 4,519 rows / 2,117 cells from three LongMemEval-V2 arms (screened, pilot, official-prompt). Schema v2, 97 fields. |

Schema `p1mem_conditional_memory_utility_v2`, **97 fields**. v2 added 20 fields over v1:
17 from the required field list (chronology, lineage, quality, bearing, efficiency, P3
groups), of which 5 are null by design with the reasons in §7; plus 3 **export-provenance**
fields (`license_policy`, `text_fields_withheld`, `reconstruction_required`) written by the
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
print(V.validate_dataset(rows).summary())        # expect: 4519 rows | 0 errors
```

The warnings it prints are **intended** and each is documented above:
`zero_execution_noise` (§11), `all_labels_undetermined` (§11),
`scorer_composition_differs_across_strata` (§19.9), and two `unknown_error_code` rows
(§4 — 2 errored cells carrying no reward).

## 21. Relation to P3

`receiver_id`, `receiver_role`, `visibility_mask`, `team_reward` and `propagation_metadata`
are **P3-reserved and null in P1**, enforced by the validator. They exist now so a
multi-agent P3 row and a single-agent P1 row share one schema instead of forking it. P1
measures whether a memory helps **its own** future task; P3 asks whether it helps **another
agent's**, which needs a receiver identity P1 has no value for.

## 22. Citation and attribution

Derived from **LongMemEval-V2** (Wu, Ji, Kawatkar, Kwan, Gu, Peng, Chang; UCLA; arXiv
2605.12493), used under Apache-2.0 at commit `2cc8c540bdb87fe6761629b585e727e1c4704520`.
Our derived annotations are released under the same terms. The vendored scorer
`qa_eval_metrics.py` is redistributed verbatim with its Apache-2.0 header.

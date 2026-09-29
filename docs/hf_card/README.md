---
pretty_name: "Conditional Memory Utility Dataset (AAMAS 2027)"
license: other
license_name: mixed-see-data-card
license_link: docs/BENCHMARK_LICENSES.md
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
  - Every number below is either MEASURED (a command was run) or marked **pending**.
    Never write a plausible number. If you do not have it, the word is "pending".
-->

# Conditional Memory Utility Dataset

> **STATUS: PRE-RELEASE SKELETON. NO EXPERIMENTAL ROWS EXIST YET.**
> Every quantitative field in this card is marked **pending** until the corresponding run
> completes. The schema, validator and export gates are final; the data is not collected.

---

## 1. Name and purpose

**Conditional Memory Utility Dataset**, released with the AAMAS 2027 submission
*Measuring task-conditional value in long-term agent memory*.

The dataset records, for a single stored memory and a single **later, different** task, the
**counterfactual change in task reward caused by that memory being available**:

```
DeltaU(m, t, s) = Reward(t | memory m available; seed s) - Reward(t | m absent; seed s)
```

Both arms live in **one row**, so a WITH score can never drift away from the WITHOUT score it is
differenced against. The dataset is a paper deliverable in its own right, not a by-product: to our
knowledge no existing resource records the same memory's utility across multiple future tasks with
full cost accounting and replication.

## 2. The P1 research question

**Is the value of a memory a property of the memory, or a property of the (memory, task) pair?**

If utility is a property of the memory alone, a single scalar per memory suffices and existing
retention/forgetting policies are well-posed. If it is conditional, then the same memory helps one
task and harms another, and any scalar memory score destroys real structure.

The headline measurement is the **robust task sign-flip rate**: the fraction of memories for which
there exist tasks `t1`, `t2` with `label(m,t1) = robust_useful` and `label(m,t2) = robust_harmful`,
where both cells independently clear a measured noise floor. A raw sign difference is **not** a flip.

**Result: pending.** The dataset contains no outcomes yet.

## 3. Source benchmarks

| Benchmark | Role | Status |
|---|---|---|
| **LongMemEval V1** (`xiaowu0162/longmemeval-cleaned`) | primary pilot | selected |
| **LongMemEval V2** (`xiaowu0162/longmemeval-v2`) | main run candidate | adapter in progress |
| BEAM | secondary | obtainability unresolved |
| SciCode | secondary, procedural memories | obtainability unresolved |

**Why V1 for the pilot.** V1 carries `answer_session_ids`, naming per question exactly which
sessions hold the evidence, so a single memory is **individually addressable for ablation**. V2 has
no equivalent field: its 45,100 (question, trajectory) cells are a dense but **unlabelled** grid.

Measured properties of V1 (500 records, from the downloaded file):
question types temporal-reasoning 133 / multi-session 133 / knowledge-update 78 /
single-session-user 70 / single-session-assistant 56 / single-session-preference 30;
30 abstention items; 926 distinct evidence-session contents; sessions per question min 38,
median 48, max 62.

⚠️ **The memory-to-task pairing is CONSTRUCTED by us; the memories are naturally occurring.**
An earlier inherited claim of "679 naturally occurring (m,t) cells" in V1 was **refuted by
measurement**: evidence sessions (`answer_*`) and filler sessions (`sharegpt_*`, `ultrachat_*`) are
**disjoint pools by construction** — zero content overlap — so no session is evidence for one
question and filler for another. A positive control confirms the zero is real and not a dead test
(4,123 of 18,810 distinct contents DO recur across questions, so the test can fire). We therefore
report a **sign-flip rate over a defined task set**, never an unqualified "natural base rate".

## 4. Memory acquisition

> **The memory writer never observes the future evaluation task.** `m = W_v(e)`, never `W_v(e, t)`.

This is the assumption a reviewer attacks first, so it is enforced structurally rather than
asserted: the writer's signature takes an episode and no task argument; all memories are written and
content-hashed **before** the pairing step exists; a leakage detector then reports the rate at which
a memory contains the gold answer.

**Leaky cells are flagged (`leakage_flag`), never dropped.** Dropping them changes the question
being answered. Residual leakage is expected and is not a bug — a naturally occurring memory may
contain the answer by coincidence, and that *is* a real memory being genuinely useful. What is
excluded is *task-directed* writing.

Measured leakage rate: **pending** (detector P1-022 not yet run).

## 5. The three memory representations

All three derive from the **same source episode**, so any downstream difference is attributable to
representation and not to content selection.

| | A. Raw / extractive | B. Abstractive summary | C. Structured experience |
|---|---|---|---|
| Content | verbatim contiguous span | model-written prose | model-written JSON schema |
| Writer | **none — deterministic** | fixed LLM, pinned | fixed LLM, pinned |
| Extraction cost | ~0 calls | 1 call/segment | 1 call/segment |
| Tokens | largest | small | small |

Raw selection is deterministic and uses no future task: segment at the benchmark's own structural
boundaries and take the whole segment. There is deliberately **no "pick the most informative span"**
rule — that would smuggle in the value judgment the dataset exists to measure.

Structured schema: `memory_type · situation/trigger · action · outcome · lesson · scope`, with a
procedural variant `trigger · procedure · failure_mode · successful_correction · scope`.

**Each representation is charged its own formation cost** in the efficiency analysis, via
`memory_extraction_latency` / `_input_tokens` / `_output_tokens`. Omitting that would flatter the
model-written representations.

## 6. Semantic types

`memory_semantic_type` ∈ `episodic | semantic_fact | procedural | failure_reflection`.

**Orthogonal to representation.** The same procedural experience can be stored raw, summarized or
structured; conflating the two axes would make the comparison meaningless. The label is derived from
the episode only, never from the future task.

Inter-pass labelling agreement: **pending**.

## 7. WITH / WITHOUT protocol

Both arms are identical except for the presence of `m`: same reader model, cluster, endpoint,
decoding, seed, prompt scaffold, context budget, **and the same scoring function and version**.

🔴 **The controlled-filler requirement is load-bearing and was discovered empirically.** On
LongMemEval V1 the oracle context is **100% evidence** (median 6,913 tokens of context, of which
median 6,913 is evidence), so ablating "the memory" there removes the entire context. That is a
**no-context arm, not a memory ablation**, and its ΔU answers a different question. Every cell
therefore places the target memory inside a fixed-size, fixed-seed set of other sessions, so removal
is a **local** change.

## 8. Replication and robustness

Multiple replicates per cell, differing **only** in sampling; the validator rejects a cell whose
replicates disagree on anything else.

Three distinct noise floors, which are not interchangeable:

| Floor | Definition |
|---|---|
| `F_exec` | outcome variation across seeds, everything else fixed |
| `F_empty` | variation of the no-memory arm — **free**, since the WITHOUT arm is identical across every memory condition for a given task |
| `F_judge` | scorer disagreement on **byte-identical** outputs |

⚠️ `F_judge` must be measured, never assumed zero: a sibling project measured a **9.35% flip rate on
byte-identical inputs at temperature 0**.

All three floors: **pending** (P1-051 not yet run).

⚠️ Replication is **adaptive** — replicates are allocated preferentially to near-zero effects and
apparent sign flips. This makes replicate count non-random and biases naive pooling. `replicate_count`
is therefore recorded per cell, and headline rates are computed on the **balanced minimum-replicate
subset** as the primary number.

## 9. Usefulness and harmfulness

Pre-registered in `docs/ANALYSIS_PREREGISTRATION.md` **before any data existed** (git history proves
the ordering). Let `CI(m,t)` be the 95% bootstrap CI of mean ΔU over the cell's replicates and `F`
the reference floor:

| `utility_label` | Condition |
|---|---|
| `robust_useful` | `CI_lower > 0` **and** `mean ΔU > F` |
| `robust_harmful` | `CI_upper < 0` **and** `\|mean ΔU\| > F` |
| `neutral` | `CI` contains 0, **or** `\|mean ΔU\| ≤ F` |
| `undetermined` | a reward is missing, the cell errored, **or `F` is not yet measured** |

Both clauses are required: statistical separation from zero **and** practical magnitude above
execution noise. A cell may be statistically nonzero yet inside the floor; that is neutral.

> **Every row currently released carries `utility_label = "undetermined"` and
> `utility_label_threshold = null`, because `F` has not been measured.** This is correct, not a
> defect. The label is **recomputable in place** from the stored raw rewards once `F` exists — which
> is precisely why the raw rewards, the CI bounds and the cell mean are all stored and why full
> output text is stored rather than a digest.

## 10. Efficiency metrics

Storage (`memory_tokens`), retrieval (`retrieval_latency`, `memory_tokens_retrieved`), **exposure**
(`memory_tokens_exposed` — what actually reached the reader after budget truncation; the gap from
`_retrieved` is the truncation loss), generation (`generation_latency`, `input_tokens`,
`output_tokens`, `reasoning_tokens`), extraction (`memory_extraction_*`), API calls
(`embedding_calls`, `generation_calls`, `retry_count`), and end-to-end wall clock.

The headline figure is a **utility–efficiency frontier**: x = memory tokens exposed, y = task reward,
with No-Memory / Keep-All / Top-k / Oracle crossed with representation. **Oracle is labelled
non-deployable headroom, never a method.**

Measured values: **pending**.

## 11. Schema

`data/cells.jsonl`, one JSON object per line, one row = **one evaluated cell**.
`schema_version = p1mem_conditional_memory_utility_v1`, **77 fields** in 13 groups: structural,
benchmark, memory, embedding, task, retrieval, execution, outcome, cost, provenance, verifier,
label_rule, and P3-reserved. The authoritative definition with per-field documentation is
`code/schema.py`; the validator is `code/validate.py`.

Four properties are enforced in code, not merely documented:

1. **Full output text, never a digest.** A hash blocks every later re-scoring under a corrected
   verifier. The validator rejects a text field holding a bare hash.
2. **Rewards are continuous** wherever the benchmark provides partial credit, never coerced to {0,1}.
3. **`reader_cluster` and `memory_writer_cluster` are experimental identity** and are never null. The
   validator flags any condition containing rows from more than one cluster.
4. **Deterministic ids** — `memory_id`, `cell_id`, `row_id` are content hashes plus the episode id,
   and the validator **recomputes** them, so an id copied between rows or content edited after the id
   was minted is caught.

Embeddings are stored by reference (`{store, index, dim, sha256}`) into a side `.npy`, not inline.

## 12. Licenses and redistribution restrictions

**Authoritative document: `docs/BENCHMARK_LICENSES.md`** (shipped in this release with its sha256
recorded in `MANIFEST.json`). This section summarizes; that document governs.

| Source | Source text redistributed here? | Why |
|---|---|---|
| **LongMemEval V1** | ❌ **No** | V1's own release is MIT, but its **filler** sessions derive from **ShareGPT and UltraChat, which carry their own upstream terms independent of V1's MIT grant**. A downstream consumer cannot distinguish evidence from filler inside a redistributed blob. |
| **LongMemEval V2** | ✅ Yes | Apache-2.0, LICENSE file present in the release. |
| BEAM, SciCode, anything unlisted | ❌ **No — fails closed** | No recorded policy means no redistribution. |

**Where redistribution is forbidden, this release publishes**: benchmark ids, `source_episode_id`,
`memory_source_span` offsets, derived annotations, ΔU and raw rewards, utility labels, semantic
similarity and bands, complete cost/latency accounting, provenance — **and the code to reconstruct
the withheld text from your own copy of the original benchmark.**

Withheld fields carry the literal string `__WITHHELD_SEE_LICENSE__` and the row records
`text_fields_withheld` and `reconstruction_required`. **A withholding is visible, never silent** —
an absent field and a withheld field are different facts.

Our own model generations are ours, but a generation can quote its prompt, so an output is released
only when its input is.

## 13. Generation and evaluation models

| Role | Value |
|---|---|
| Reader (generation) | `gpt-oss-120b` on **Metis** |
| Memory writer | `gpt-oss-120b` on **Metis** |
| Embeddings | `Salesforce/SFR-Embedding-Mistral` on **Sophia**, dim 4096 |
| Decoding | `temperature = 0`, `max_tokens = 512`, `reasoning_effort = low` |
| Designated failover | `openai/gpt-oss-120b` on **Sophia** — **a separate arm, never pooled** |

⚠️ **The model-name asymmetry across clusters is real and is preserved in the data**: the same
logical model is `gpt-oss-120b` on Metis and `openai/gpt-oss-120b` on Sophia. Nothing normalizes
these together; doing so would merge two experimental arms. Consumers should group by
`(reader_model, reader_cluster)`, never by `reader_model` alone.

🔴 **`max_tokens` must cover reasoning + answer.** These are reasoning models and reasoning tokens
are drawn from the **same budget as the answer**. At a small `max_tokens` the model spends the whole
budget reasoning and returns `content: null` with `finish_reason: "length"`. Scoring that as a wrong
answer would drive ΔU negative and **manufacture a harmful memory**. It is therefore a hard error
(`error_code_if_any = "empty_output_finish_length"`) and the cell is re-run, never scored — enforced
by the validator, which rejects any row with an empty output and a non-null reward.

## 14. ALCF endpoint and cluster provenance

Every row records `reader_cluster`, `reader_endpoint` (a credential-free alias — the validator
rejects any endpoint containing userinfo, a query string, or a token-shaped substring),
`reader_endpoint_sha256` (a hash of the full base URL so provenance is verifiable without ever
storing a value that could embed a credential), `memory_writer_cluster`, and `embedding_model` /
`embedding_version`.

**`reasoning_tokens` is nullable, and `null` means "not reported by this cluster", NOT zero.** Metis
reports `completion_tokens_details.reasoning_tokens`; Sophia omits the field entirely. The validator
**rejects `reasoning_tokens = 0` on a cluster known not to report it**, because writing an absence as
a measurement is a defect this project has been burned by. Any aggregate over this column must
exclude nulls from the denominator rather than summing them as zeros.

⚠️ A capability listing is not a liveness signal: two models advertised by the ALCF gateway during
this project's audit returned 503/502 to a real POST. Every model dependency was proven with an
actual request.

## 15. Prompt and version provenance

Per row: `memory_writer_prompt_version`, `reader_prompt_version`, `embedding_version`,
`benchmark_version`, `verifier_id`, `verifier_version`, `utility_label_rule_version`, and
`provenance = {code_sha, config_sha256, run_id, host}`.

⚠️ **One verifier version per row, covering both arms by construction.** Arm-dependent verifier
versions invalidated a table on a sibling project; the validator additionally rejects a condition
whose rows were scored by more than one verifier.

## 16. Known biases and limitations

1. **The pairing is constructed, not harvested.** Memories are naturally occurring; which future
   task each is evaluated against is our seeded, deterministic construction. This is a sign-flip rate
   over a defined task set.
2. **Adaptive replication biases naive pooling** (§8). Use `replicate_count`.
3. **Residual leakage.** Some memories contain the gold answer by coincidence. Flagged, not dropped.
4. **Single reader model on a single cluster** for the main arm. Cross-model generality is untested.
5. **Constructed filler contexts** are smaller than a realistic agent's memory store.
6. **English only**, and the source conversations are LLM-user-simulator dialogues, not organic
   human logs.
7. **`F_judge` is nonzero for LLM-judged items**, so ΔU on those cells is noisier than on
   deterministically-scored ones.
8. **Abstention items behave differently** — 30 in V1 — and should be analysed separately.
9. **No outcomes yet.** Everything above marked *pending* is genuinely unmeasured.

## 17. Intended uses

- Studying whether memory utility is conditional on the task rather than intrinsic.
- Benchmarking memory retention, forgetting, and retrieval policies against a **measured** utility
  signal with a **measured noise floor** rather than a heuristic proxy.
- Cost-aware memory research: every row carries token, call and latency accounting.
- Re-scoring under a corrected or different verifier — **full output text is retained precisely so
  this stays possible.**
- Methodological reference for counterfactual WITH/WITHOUT evaluation design.

## 18. Out-of-scope uses

- **Training a model to imitate the reader outputs.** They are single-sample generations at
  temperature 0 from one model, not curated targets.
- **Treating `utility_label` as ground truth about memory quality.** It is a thresholded statistical
  statement relative to a specific noise floor, model, cluster and task set.
- **Pooling rows across clusters or across `reader_model` spellings.** They are different arms (§13).
- **Reconstructing the source benchmarks.** Withheld text is withheld; obtain V1/V2 from their own
  releases under their own terms.
- **Claiming a natural base rate of harmful memories** from these numbers (§16.1).
- **Any use requiring the ShareGPT/UltraChat-derived filler content**, which is not redistributed.
- Deployment decisions about a production memory system without re-measuring on that system.

## 19. P3 compatibility and reserved fields

A successor project (P3) studies **receiver-conditional** utility: the same message or memory valued
differently by different receivers in a multi-agent team. Four fields are reserved now so P3 rows and
P1 rows share one schema instead of forking it:

`receiver_id` · `receiver_role` · `visibility_mask` · `team_reward`

**All four are `null` in every P1 row, and the row builder forces them null even if a caller passes a
value.** The validator rejects any P1 row in which one is populated. In P1 there is a single reader
and a single task reward, so no honest value exists for them — a plausible-looking placeholder would
be worse than a null.

## 20. Version and changelog

| Version | Date | Change |
|---|---|---|
| `0.0.1-skeleton` | 2026-09-29 | Schema (`p1mem_conditional_memory_utility_v1`, 77 fields), validator, export gates and this card. **No experimental rows.** Noise floor unmeasured, so all labels are `undetermined`. |

Planned: `0.1.0-pilot` (pilot cells + measured noise floor + recomputed labels),
`1.0.0` (main run, camera-ready).

**Citation: pending** (paper under review at AAMAS 2027).

---

*Generated by `scripts/export_hf.py`. Every number here was measured or is marked pending; none was
estimated. `MANIFEST.json` records the sha256 of every shipped file, the license document it was
built against, and whether the export gate self-test ran.*

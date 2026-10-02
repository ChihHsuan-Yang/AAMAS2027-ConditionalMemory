# Dataset Index — `<anonymized-for-review>/AAMAS2027-ConditionalMemory`

One row per published snapshot. **Every figure here was produced by a command on the
released artifact**, not copied from a plan. A snapshot that is not in this table has not
shipped.

> 🔴 **This file SHIPS INSIDE the snapshot it describes, and that made it lie.** The
> copy inside **v0.3** (and the first upload of v0.4) still carried the row *"v0.3 |
> SciCode-derived rows | **No SciCode row is in any published snapshot** (verified:
> `benchmark` is `longmemeval_v2` on 5,643/5,643)"* — inside a snapshot holding 154
> SciCode rows. The sentence was **true when written at v0.2** and was published
> unchanged into the two releases that falsified it. A consumer reading the shipped
> docs would have concluded their download was wrong.
>
> No gate could see it: every gate reads `data/cells.jsonl`, which was correct, and the
> false statement was in a document beside it. **GATE 5b checks the card's validator
> line and nothing checks the prose of an auxiliary doc.** It was found by diffing the
> *downloaded* tree against the repo after release — the same move that found v0.1's
> seam defect.
>
> **The general shape: a document that describes a release cannot be fully correct
> inside that release**, because its own entry is written before the release exists.
> That is why the current version's release-commit row is never transcribed here. v0.3's
> tag is left as published, with the defect recorded, exactly as v0.1's broken first
> upload was left and recorded rather than retconned.

Repository: `<anonymized-for-review>/AAMAS2027-ConditionalMemory` (dataset, **private**). The owning org is anonymised here because **this file ships inside the release**, exactly as the data card's links are; restore it after the review cycle.
Policy: `docs/HF_RELEASE_POLICY.md`. Licence findings: `docs/BENCHMARK_LICENSES.md`.

> **On the "release commit" rows.** A hash is transcribed here only once the release
> it names is **published and frozen**, so the value is a fact about another object:
> that is true of v0.1, v0.3 and v0.4. v0.2's is **not transcribed**, because a commit
> cannot contain its own hash — writing one would mean either naming an earlier tree
> than the one that shipped or starting an endless correction chain, and this file went
> through three before saying so. In every case the authoritative value is computed at
> build time into the snapshot's own `MANIFEST.json`, which travels *with* the data.
> Read it there; the transcriptions are a convenience and the manifest is the record.

---

## Snapshots

### v0.1 — tag `v0.1-lmev2-derived`

| | |
|---|---|
| **released** | 2026-09-30 |
| **benchmarks** | LongMemEval-V2 only, rev `2cc8c540bdb87fe6761629b585e727e1c4704520` |
| **representations** | `raw` only (4,519 / 4,519) |
| **rows** | **4,519** — screened 2,599 + pilot 960 + official-prompt 960 |
| **cells** | 2,117 |
| **schema version** | `p1mem_conditional_memory_utility_v2`, **97 fields** |
| **release commit** | `743d2e2` (`export: add gates 4-5 after a defect that shipped`) |
| **files** | 13 |
| **size** | 126.0 MB (`data/cells.jsonl` 126,007,765 B) |
| **validation** | **0 errors**, 5 warnings, verified **on the downloaded snapshot** by the card's own command |
| **licence** | Apache-2.0 throughout; nothing withheld (4,519/4,519 redistributable) |

**Known limitations at v0.1**
- `raw` only, so the representation comparison the schema was built for was absent.
- 5 fields null by design (`source_episode_completion_timestamp`, `parent_memory_id`,
  `faithfulness_check`, `context_budget`, `propagation_metadata`).
- 🔴 **Its FIRST upload shipped broken and passing.** Gates 1–3 passed and `hf upload`
  exited 0, yet all 4,519 published rows failed the validator published beside them
  (13,557 `unknown_field` errors), because `redact_row` adds three export-provenance
  fields *after* gate 1 validates. Found only by downloading the release and running its
  own documented command. Gates 4 and 5 exist because of this, and gate 5 immediately
  caught a second seam defect.
- 🔴 **Two of its five documented nulls carried reasons that were true only because
  every row was `raw`** — corrected in v0.2, see below. This was not visible at v0.1.

---

### v0.2 — tag `v0.2-repr-derived`

| | |
|---|---|
| **released** | 2026-09-30 |
| **benchmarks** | LongMemEval-V2 only, same rev `2cc8c540` |
| **representations** | `raw` **4,519** · `summary` **570** · `structured` **554** |
| **rows** | **5,643** (v0.1's 4,519 re-migrated + 1,124 new) |
| **cells** | 2,679 (562 new) |
| **source memories** | 117 locators (234 distinct `memory_id` — a content hash, so one span yields a different id per representation) |
| **future tasks** | 275 |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** |
| **release commit** | recorded at build time in the snapshot's own `MANIFEST.json` → `release_commit` (with `release_tree_dirty`) |
| **validation** | **0 errors**, 1,129 warnings, verified **on the downloaded snapshot** |
| **licence** | Apache-2.0 throughout; nothing withheld (5,643/5,643 redistributable) |

**What v0.2 adds**
- The matched Summary and Structured arms: same 60 source memories, same 126 tasks, same
  reader model/cluster/prompt/effort/sampling (`reader_endpoint_sha256 7e6b0a4f53fd08e0`
  on both releases). 277 design cells present in all three representations, 57 memories.
- **`faithfulness_detail`** (the one field v3 adds): the full multi-axis proxy score.
- **`faithfulness_check` and `parent_memory_id` are now populated** on the new rows.

**Known limitations at v0.2**
- **The arms are not balanced.** Every representation claim rests on the **277-cell /
  57-memory matched subset**, not on all 5,643 rows.
- **8 structured design cells are missing** (554 vs 570): 3 of 60 structured writes hit
  the 512-token cap and returned JSON cut off mid-value. Recorded per cell, not dropped.
- 🔴 **The Raw arm and the two new arms ran on different days and the endpoint moved.**
  Raw 2026-09-29, Summary/Structured 2026-09-30; a cache-disabled probe attributes the
  difference to a serving change, not sampling. A same-session re-measurement reproduces
  the contrast (mean reward 0.3100 → 0.3100), so the conclusion does not rest on the
  cross-session join — but every per-cell Raw-vs-new difference carries extra noise.
- **1,124 rows carry `provenance.config_sha256 = null`** with a stated reason: the
  representation runner never reads `configs/endpoint_primary.json`, so no hash of it was
  measured and back-filling one would be a provenance nobody took.
- **3 fields remain null by design**: `source_episode_completion_timestamp`,
  `context_budget`, `propagation_metadata`.
- **`faithfulness_detail` is a deterministic proxy, not a judgment.** High scores are
  weak evidence; only low scores are informative. No LLM judge was run.
- Carried over from v0.1: leakage rates are lower bounds; the variance decomposition is
  unidentifiable; no harmful-memory rate is claimable; the pairing is ours, so nothing
  here is a natural base rate; single reader model and cluster; English only.

---

### v0.3 — tag `v0.3-scicode-derived`

| | |
|---|---|
| **released** | 2026-10-01 |
| **benchmarks** | LongMemEval-V2 rev `2cc8c540` **+ SciCode** (`hf@4510f6a6aa27`, Apache-2.0) |
| **representations** | LongMemEval: `raw` 4,519 · `summary` 570 · `structured` 554 · **SciCode: `raw` 154 ONLY** |
| **rows** | **5,797** (v0.2's 5,643 + 154 SciCode) |
| **cells** | 2,833 (154 new, over 34 SciCode memories and 40 tasks) |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** |
| **release commit** | `e549c09` (recorded in the snapshot's own `MANIFEST.json`; transcribed here because the release is now frozen) |
| **files** | 17 + `.gitattributes` |
| **size** | 138.7 MB (`data/cells.jsonl` 138,705,594 B) |
| **validation** | **5,797 rows / 0 errors / 1,437 warnings**, verified **on the downloaded tag** by the card's own command |
| **licence** | Apache-2.0 throughout; nothing withheld (`text_fields_withheld` is `[]` on 5,797/5,797) |

**Known limitations at v0.3**
- 🔴 **SciCode ships RAW ONLY — 154 of 462 cells.** The summary/structured memory
  TEXT was never persisted (the runner recorded `response_chars` and discarded
  content; the client had no `cache=`). It **cannot be reconstructed**:
  cross-session regeneration at fully matched settings is **0/8 byte-identical**
  while within-session is **3/3** (defect 22). Their **reward measurements remain
  VALID and are not retracted.** No text was fabricated or regenerated and
  presented as the original. **SciCode is therefore NOT representation-matched
  where LongMemEval is.**
- 🔴 This is a **PERSISTENCE** gap, never a licence withholding. SciCode is
  Apache-2.0 and withholds nothing. The two are spelled differently in the data —
  `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` on both SciCode output fields, and
  `__WITHHELD_SEE_LICENSE__` nowhere in v0.3 — and the card's prose keeps them
  distinct too.
- The card's own v0.3 defect: **GATE 5b** was added because GATE 5 ran the card's
  verification command and checked only its **exit code**, so a card promising
  v0.2's "5,643 rows" sailed through a 5,797-row release.
- All v0.2 limitations carry over unchanged.

---

### v0.4 — tag `v0.4-swebench-metrics`

| | |
|---|---|
| **released** | 2026-10-01 |
| **benchmarks** | LongMemEval-V2 **+ SciCode + SWE-bench Verified** (`swebench_verified@princeton-nlp`) |
| **representations** | LongMemEval `raw` 4,519 / `summary` 570 / `structured` 554 · SciCode `raw` 154 · **SWE-bench `raw` 41 / `summary` 43 / `structured` 43** |
| **rows** | **5,924** (v0.3's 5,797 + 127 SWE-bench) |
| **cells** | 2,960 (127 new, over 20 memory instances and 43 task instances; django 96 · sympy 31) |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** |
| **release commit** | `83c560e7` — transcribable now that v0.4 is **frozen and superseded**; it was deliberately left blank while v0.4 was current, because this file ships *inside* the snapshot it describes. 🔴 Read from **v0.4's own downloaded `MANIFEST.json`**, not from a doc: `README.md` had carried `bc66629f`, which is a different commit. The manifest travels with the data and is the record. |
| **files** | 17 + `.gitattributes` |
| **size** | 139.7 MB (`data/cells.jsonl` 139,676,660 B) |
| **validation** | **5,924 rows / 0 errors / 1,691 warnings**, verified **on the downloaded tag** by the card's own command |
| **licence** | 🔴 **MIXED.** 5,797 rows Apache-2.0 with source text; **127 SWE-bench rows metrics-and-ids only.** Frontmatter is `license: other`, not `apache-2.0`. |

**Known limitations at v0.4**
- 🔴 **SWE-bench Verified ships METRICS AND IDS ONLY.** The corpus
  (`princeton-nlp/SWE-bench_Verified`) **declares no licence** — HF API
  `cardData.license` is `None`, no `license:*` tag, no statement in the card — and
  the MIT grant covers the harness, not the corpus. Five fields carry
  `__WITHHELD_SEE_LICENSE__` on all 127 rows and are **declared** in
  `text_fields_withheld`: `memory_text`, `future_task_text`, `output_with_memory`,
  `output_without_memory`, `source_episode_metadata`. **An absent licence is not a
  permissive licence**, and `gated: false` means fetchable, not redistributable.
- 🔴 **This is a LICENCE withholding and SciCode's is a PERSISTENCE gap.** Different
  facts, different sentinels, and the converter's self-test **refuses**
  `OUTPUT_NOT_RETAINED` on a SWE-bench field — the generic embargo check cannot see
  that swap, and it would publish a false stated reason in the one field a consumer
  checks.
- 🔴 **37 manufactured `0.0` rewards were demoted to null before export** (defect 21:
  a pytest suite that printed no verdict, `status_lines=0`, is not a wrong answer).
  django 27 · sympy 10, touching 25 of 127 cells. Verified **independently of the
  converter's own count** by re-deriving the `status_lines=0` set from the untouched
  source artifacts: 37 demoted, **179 real rewards preserved unchanged**, 0
  discrepancies. No manufactured `0.0` is in the release.
- **Only 76 of 127 SWE-bench cells are scorable** (51 have a null `delta_utility`
  because an arm could not be scored), and **69 of those 76 are ties** — 4 helped, 3
  hurt. **No representation claim is made on this benchmark**, and the release does
  not support one.
- 🔴 **`memory_id` on a SWE-bench row is NOT a content hash.** The runner never
  persisted memory bodies, so no unredacted ledger of that text exists anywhere; the
  id is minted over the sentinel and identifies
  `(memory_instance_id, memory_representation)`. Re-deriving it from upstream text
  gives a **different** value by construction. Join on the instance ids. The
  validator reports this per row as `id_unverifiable_withheld_input` (127 warnings)
  rather than passing silently.
- 2 sympy cells were **excluded for memory contagion** upstream, which is why the raw
  column is 41 and not 43.
- **Four card claims had decayed** and were re-derived rather than inherited: the
  `apache-2.0` frontmatter (false for 127 rows — a platform executes metadata), "every
  row derives from a source whose licence permits redistribution", `context_budget`'s
  reason (it counted 127 `null == null` pairs as a measured equality), and
  "`compression_ratio = 1.0` on every raw row" (the 41 SWE-bench raw rows are `null`).
- All v0.2 and v0.3 limitations carry over unchanged.

---

### v0.5 — tag `v0.5-reader-generalization` *(current)*

| | |
|---|---|
| **released** | 2026-10-02 |
| **benchmarks** | LongMemEval-V2 **12,103** + SciCode 154 + SWE-bench Verified 127 |
| **readers** | 🔴 **TWO for the first time** — `gpt-oss-120b` **9,566** · `gemma-4-31B-it` **2,818** |
| **representations** | LongMemEval `raw` 6,483 / `summary` 2,850 / `structured` 2,770 · SciCode `raw` 154 · SWE-bench `raw` 41 / `summary` 43 / `structured` 43 |
| **rows** | **12,384** (v0.4's 5,924 + **6,460** new, all LongMemEval-V2, all already schema v3) |
| **cells** | 6,186 · 571 distinct memories · 370 distinct tasks |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** (unchanged) |
| **release commit** | **not transcribed** — v0.5 is the current release and this file ships *inside* it, so a hash written here cannot be the hash of the tree containing it. Read `release_commit` in the snapshot's own `MANIFEST.json`. |
| **files** | 17 + `.gitattributes` |
| **size** | 243.1 MB (`data/cells.jsonl` 243,060,962 B) |
| **validation** | **12,384 rows / 0 errors / 1,703 warnings**, verified **on the downloaded tag** by the card's own command, matching the card's printed expectation exactly |
| **licence** | 🔴 **MIXED, unchanged.** 12,257 rows Apache-2.0 with source text; 127 SWE-bench rows metrics-and-ids only. Frontmatter stays `license: other`. |

**What v0.5 adds** — the four slices, each with the artifact behind it:

| slice | rows | canonical artifact |
|---|---:|---|
| session-matched reader transfer | 1,140 | `results/raw_session_matched/raw_gptoss.jsonl` · `raw_gemma.jsonl` |
| Writer × Reader factorial | 4,496 | `results/writer_factorial/factorial_cells_gptoss.jsonl` · `factorial_cells_gemma.jsonl` |
| gold-free screen GF-LLM | 168 | `results/deltau_goldfree_llm/cells.jsonl` |
| gold-free screen GF-LEX | 656 | `results/deltau_goldfree/cells.jsonl` |

**Known limitations at v0.5**
- 🔴 **Through v0.4 the release contained NO Gemma reader row** (`reader_model` was
  `gpt-oss-120b` on 5,924/5,924) while the paper reported a reader-transfer result.
  That gap is what v0.5 exists to close; it is recorded rather than quietly fixed.
- 🔴 **Ids are not join keys on the factorial.** `memory_id`/`cell_id`/`row_id` are
  content hashes, and the Gemma writer rendered two different segments of episode
  `06c70de4` (`13-14`, `17-18`) as **byte-identical** 68-token summaries. 16 real rows
  therefore share 8 `row_id`s and 4 `cell_id`s. Reported as
  `id_collision_writer_collapse` (8) and `cell_collision_writer_collapse` (4), both
  **warnings**: they are not restated rows, and through v0.4 the validator raised a hard
  `duplicate_row_id` whose own message ("must not restate a row") was **false** on them.
  Join on `(memory_unit_locator, future_task_id, replicate_id, reader_model)`.
- 🔴 **`reasoning_tokens` carries two different nulls.** Gemma's 2,818 nulls are an
  endpoint that never emits the field; SciCode's 154 are a run that did not record a
  field metis *does* report. **Do not pool them**, and `0` appears on no row.
- **GF-LEX is the screen that DISAPPEARS and it ships anyway.** Publishing only GF-LLM
  would select an instrument on its own outcome.
- **The length-control experiment is absent from v0.5**, and its stated reason changed
  during that build: it was still running when v0.5 was scoped and reached a frozen
  verdict before upload. Held out because its rows were not in the audited set that
  release was gated against — named a v0.6 candidate so the exclusion would not be
  inherited by default. ✅ **Re-decided and SHIPPED in v0.6.**
- 🔴 **The v0.5 tag was MOVED once.** Its first upload carried three
  `code/p1mem/__pycache__/*.pyc` deposited by a pre-upload verification step that
  imported the shipped package without `-B`, three minutes after a clean build. They
  were never in `MANIFEST.json`, no data byte changed, and the tag now points at the
  commit that removes them. Found by diffing the **downloaded** tag against staging —
  the same move that found v0.1's seam defect and v0.3's doc defect.
- All v0.2, v0.3 and v0.4 limitations carry over unchanged.

---

### v0.6 — tag `v0.6-length-control` *(current)*

| | |
|---|---|
| **released** | 2026-10-02 |
| **benchmarks** | LongMemEval-V2 **16,535** + SciCode 154 + SWE-bench Verified 127 |
| **readers** | `gpt-oss-120b` **13,998** · `gemma-4-31B-it` **2,818** (v0.6's 4,432 new rows are all gpt-oss) |
| **representations** | LongMemEval `raw` 9,807 / `summary` 3,404 / `structured` 3,324 · SciCode `raw` 154 · SWE-bench `raw` 41 / `summary` 43 / `structured` 43 |
| **rows** | **16,816** (v0.5's 12,384 + **4,432** new, all LongMemEval-V2, all already schema v3) |
| **cells** | 8,393 · 839 distinct memories · 370 distinct tasks · 29 distinct `condition_id`s |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** (unchanged) |
| **release commit** | **not transcribed** — v0.6 is the current release and this file ships *inside* it, so a hash written here cannot be the hash of the tree containing it. Read `release_commit` in the snapshot's own `MANIFEST.json`. |
| **validation** | **16,816 rows / 0 errors / 6,160 warnings**, verified **on the downloaded tag** by the card's own command, matching the card's printed expectation exactly |
| **licence** | 🔴 **MIXED, unchanged.** 16,689 rows Apache-2.0 with source text; 127 SWE-bench rows metrics-and-ids only. Frontmatter stays `license: other`. |

**What v0.6 adds** — the pre-registered **length control**, one slice:

| slice | rows | canonical artifact |
|---|---:|---|
| length-controlled representation test, 8 arms × 554 | **4,432** | `results/length_control/cells.jsonl` · ledger `results/ledgers/length_control_result.json` |

**Verdict O2.** At a matched exposed-token budget the extractive and model-written arms
do **not** separate: **+0.0519**, task-clustered 95% CI **[−0.0678, +0.1727]**, 135
BEARING cells over 55 clusters. Raw's advantage is an **exposure-budget** effect, not a
rewriting effect. Design frozen at `f702aaf` **before execution**;
`docs/LENGTH_CONTROL_PRECOMMITMENT.md` and `docs/LENGTH_CONTROL_RESULT.md` now ship
**inside** the snapshot so a consumer can check the result against its own precommitment
without leaving the download.

**Known limitations at v0.6**
- 🔴 **`trunc_last_20000` is an A/A CONTROL, not a ninth condition.** Its 20,000-token
  budget exceeds the longest Raw memory (19,801), so it renders **byte-identical to
  `raw` on 554/554** and reproduces its reward triples and reader outputs on **552/552
  scored pairs**. Pooling the arms without dropping either it or `raw` **double-counts
  Raw**. The data card says so in §21.3 before any number.
- 🔴 **`memory_representation` is `raw` on all five truncated arms**, because the enum
  describes how a memory was written down (extractive, zero writer calls) and not which
  arm it belongs to. **Group by `condition_id`, never by `memory_representation`**, to
  recover the eight arms.
- 🔴 **Length-control `condition_id`s are `lmev2_<arm>_lenctl_v1` and the arm slot never
  names a model** — unlike the factorial's `w<writer>_r<reader>` ids. Reading one
  convention under the other produced two false alarms against a correct release
  (`DEFECT_REGISTER` MA-3). Verified with a checker whose positive control was proven to
  fire: **0** rows contradict their `reader_model` or writer.
- **Warnings rose 1,703 → 6,160 and NO new warning code appeared.** 4,432 of the
  increase is `provenance_incomplete` (that runner leaves `provenance.config_sha256`
  empty — a completeness flag, reported rather than suppressed); the remaining +7
  `cell_collision_writer_collapse` and +18 `id_collision_writer_collapse` are the
  already-documented byte-identical-rendering collisions appearing on the new rows,
  which reuse the frozen Summary/Structured text. Errors stay **0**.
- **6 of 4,432 rows carry a null reward** (`empty_output_finish_length`), never a
  manufactured 0.0 (defect 21). Verified both directions: every null reward sits beside
  a non-null error code and every non-null reward beside a null one.
- `scripts/prep_v06_inputs.py` filled `faithfulness_notes` on all 4,432 rows, which
  arrived empty because this ledger was written directly at v3 and never passed through
  the migration that fills a null's reason. Three different reasons, each written only
  where its premise was **re-derived true on the row**: 1,202 full-span tautology, 2,122
  truncated-slice, and 1,108 model-written rows that carry the **real** write-pass score
  (attached, not pointed at — the validator rejects a "not scored" note on a scorable
  memory). Four planted premise violations are each refused.
- All v0.2, v0.3, v0.4 and v0.5 limitations carry over unchanged.

---

## Planned, NOT released

🔴 **Nothing is queued. As of v0.6 no evaluated row of this project is
unpublished-but-ready**, which is a stronger statement than "nothing is planned": the
only things still out are out for a **structural** reason — a licence, a persistence
gap, or a VOID label — each named in the data card's §22 and in
[`TRACE_AVAILABILITY.md`](TRACE_AVAILABILITY.md). The v0.6 candidate this table named
at v0.5 (the length control) **shipped**.

**BEAM will never appear in this dataset.** Its data is CC BY-SA 4.0 and ShareAlike is
infectious, so BEAM-derived records must ship as a **separate CC BY-SA 4.0 release**
attributing the BEAM authors. Folding them in would either violate ShareAlike or silently
relicense everything else. The exporter's gate that refuses them is exercised with a
positive control on every build.

---

## How a snapshot is admitted to this table

A release is complete only after **all eight steps**, in order:

1. build a staging directory **outside the repo**
2. run the schema validator
3. run the **secret** scan
4. run the **identity / de-anonymisation** scan (GATE 2b) over the whole tree
5. upload, and tag
6. **download the remote tag** to a fresh directory
7. **run the validator on the DOWNLOADED BYTES, and run the data card's own
   documented verification command from the downloaded root**
8. only then mark DONE

Steps 6 and 7 exist because v0.1's first upload passed its gates, exited 0, and was
broken: `redact_row` added three fields *after* validation, so all 4,519 published rows
failed the validator published beside them. **An exit code is not a verification, and a
gate that inspects rows in memory cannot see a defect introduced by writing them out.**

Step 4 is a **separate step from step 3** because a credential scanner is structurally
blind to a de-anonymising string: an absolute home path has no entropy signature and
reads as an ordinary file path. v0.3 staged with `/Users/<name>/` inside
`code/p1mem/schema.py` and **all nine gates passed** (defect 23). At v0.3 and v0.4 the
identity gate was re-proven able to fail, against a planted macOS path, a planted Linux
path, and a clean negative control.

**A gate that has only ever been shown to pass is not known to work.** Every release
runs its gates against planted defects in both directions, and a clean scan whose needle
occurs nowhere is recorded as vacuous rather than as evidence.

# Dataset Index — `AgentsSci/AAMAS2027-ConditionalMemory`

One row per published snapshot. **Every figure here was produced by a command on the
released artifact**, not copied from a plan. A snapshot that is not in this table has not
shipped.

Repository: `AgentsSci/AAMAS2027-ConditionalMemory` (dataset, **private**).
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

### v0.4 — tag `v0.4-swebench-metrics` *(current)*

| | |
|---|---|
| **released** | 2026-10-01 |
| **benchmarks** | LongMemEval-V2 **+ SciCode + SWE-bench Verified** (`swebench_verified@princeton-nlp`) |
| **representations** | LongMemEval `raw` 4,519 / `summary` 570 / `structured` 554 · SciCode `raw` 154 · **SWE-bench `raw` 41 / `summary` 43 / `structured` 43** |
| **rows** | **5,924** (v0.3's 5,797 + 127 SWE-bench) |
| **cells** | 2,960 (127 new, over 20 memory instances and 43 task instances; django 96 · sympy 31) |
| **schema version** | `p1mem_conditional_memory_utility_v3`, **98 fields** |
| **release commit** | `1741c80` |
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

## Planned, NOT released

| version | contents | status |
|---|---|---|
| — | nothing is currently queued | v0.3 (SciCode) and v0.4 (SWE-bench, metrics-only) have **both shipped** and are listed above with figures measured on their downloaded tags. |

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

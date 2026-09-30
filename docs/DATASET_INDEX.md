# Dataset Index — `AgentsSci/AAMAS2027-ConditionalMemory`

One row per published snapshot. **Every figure here was produced by a command on the
released artifact**, not copied from a plan. A snapshot that is not in this table has not
shipped.

Repository: `AgentsSci/AAMAS2027-ConditionalMemory` (dataset, **private**).
Policy: `docs/HF_RELEASE_POLICY.md`. Licence findings: `docs/BENCHMARK_LICENSES.md`.

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

### v0.2 — tag `v0.2-repr-derived` *(current)*

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
| **release commit** | see `MANIFEST.json` → `provenance` / the tag |
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

## Planned, NOT released

| version | contents | status |
|---|---|---|
| v0.3 | SciCode-derived rows | run in flight at v0.2. **No SciCode row is in any published snapshot** (verified: `benchmark` is `longmemeval_v2` on 5,643/5,643). |
| v0.4 | SWE-bench Verified rows | run in flight; a localized pilot found an arm asymmetry that must be resolved before any row ships. |

**BEAM will never appear in this dataset.** Its data is CC BY-SA 4.0 and ShareAlike is
infectious, so BEAM-derived records must ship as a **separate CC BY-SA 4.0 release**
attributing the BEAM authors. Folding them in would either violate ShareAlike or silently
relicense everything else. The exporter's gate that refuses them is exercised with a
positive control on every build.

---

## How a snapshot is admitted to this table

A release is complete only after **all seven steps**, in order:

1. build a staging directory **outside the repo**
2. run the validator
3. redact restricted content
4. **run the validator AGAIN, after redaction**
5. upload
6. **download the remote snapshot**
7. **run the published validator against the downloaded data**

Steps 4, 6 and 7 exist because v0.1's first upload passed steps 1–3 and 5, exited 0, and
was broken. **An exit code is not a verification, and a gate that inspects rows in memory
cannot see a defect introduced by writing them out.**

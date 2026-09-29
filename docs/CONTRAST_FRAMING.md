# Which Contrast Carries the Claim

**Fixed 2026-09-29, BEFORE the screened run's results exist.** Design facts verified by the
Master Agent from `data/manifests/k1_screened_cells.jsonl` (1,157 cells).

---

## The confound, found by Sub-agent K during design

BEARING and MATCHED_CONTROL are **disjoint in tasks by construction**: a bearing task is
one the detector singles this memory out on; a control task is one it does not. Verified:

| stratum | cells | distinct tasks |
|---|---:|---:|
| BEARING | 139 | **56** |
| MATCHED_CONTROL | 146 | **100** |
| RANDOM | 872 | 147 |

BEARING ∩ MATCHED_CONTROL = **30 tasks**.

> So a raw **accuracy** comparison between strata would confound "the memory bears on the
> task" with "which tasks these are". ΔU is immune — it is a within-task, within-memory
> contrast, so task difficulty cancels inside the cell.

## Composition, measured

| stratum | dynamic-env | procedure | static-env | errors-gotchas |
|---|---:|---:|---:|---:|
| BEARING | 0.259 | 0.216 | **0.525** | — |
| MATCHED_CONTROL | 0.274 | 0.219 | **0.507** | — |
| **RANDOM** | 0.335 | 0.336 | **0.283** | 0.046 |

**BEARING ↔ MATCHED_CONTROL match to within 0.02 on every family. RANDOM does not** —
static-environment is 0.283 against BEARING's 0.525, and RANDOM carries an
errors-gotchas slice the other two lack.

⚠️ Exactly **one** deterministically-scorable `errors-gotchas` question exists
benchmark-wide (`626e401e`, of 29 such questions). Verified: it sits **only in RANDOM** and
alone generates **40 cells = 4.6% of that stratum**.

### 🔴 But task concentration is structural, not one question

Verified by the Master Agent over all 1,157 design cells:

| | |
|---|---|
| tasks with **≥20 cells** | **24** |
| max cells on a single task | **40** |
| **top 10 tasks** | **400 / 1,157 = 34.6% of all cells** |
| half of all cells sit on | **17 of 218 tasks** |

### The pooled figure hides the part that matters — concentration is NOT uniform

Verified per stratum by the Master Agent:

| stratum | cells | tasks | max cells on one task | top-10 share |
|---|---:|---:|---:|---:|
| BEARING | 139 | 56 | 6 | 38.8% |
| **MATCHED_CONTROL** | 146 | **100** | **4** | **19.9%** |
| **RANDOM** | 872 | 147 | **40** | **44.6%** |

> **The stratum that carries the claim is the least concentrated**, and the stratum most
> exposed to single-task leverage is the one used only for the dilution diagnostic.

MATCHED_CONTROL has **no task with ≥20 cells and a maximum of 4** — it is **2.2× less
concentrated** than RANDOM. So BEARING↔MC is robust to task clustering close to by
construction, while BEARING↔RANDOM is precisely where the jackknife earns its place.

⚠️ **Quoting the pooled 34.6% alone would have made MATCHED_CONTROL look as fragile as
RANDOM.** Report per stratum. (My own earlier note did quote it pooled; corrected here.)

`626e401e` is not special; it is the most quotable instance of a property the **shared task
grid deliberately creates** — reusing tasks across memories is exactly what fixes
identifiability, and it is exactly what concentrates cells on few tasks.

> **Therefore `task_id` clustering is required for EVERY contrast, not only the dilution
> one.** With a third of all cells on ten tasks, a cell-level *p* can be persuasively small
> while one question carries the whole difference.

Sub-agent K implemented this as a task-clustered bootstrap (resampling whole tasks) plus a
leave-one-task-out jackknife on every contrast, and proved both against constructed cases:

| constructed case | cell-level p | task-clustered CI | drop-one effect | sign stable |
|---|---|---|---|---|
| effect driven **entirely by one task** | **0.0015** | **includes zero** | **+0.0000** | **False** |
| effect spread across many tasks | — | excludes zero | [+0.4545, +0.5455] | True |

**The first row is the argument.** A cell-level p of 0.0015 would have read as convincing.
Both the clustered CI and the jackknife appear in every results table, so the cell-level p
is never the only number a reader sees.

## Ruling

| contrast | status | what it answers |
|---|---|---|
| **BEARING vs MATCHED_CONTROL** | ✅ **the clean causal contrast — carries the claim** | does a memory that bears on a task help more than one that does not? |
| BEARING vs RANDOM | ⚠️ reported, **labelled as composition-mismatched** | how much did the unscreened design dilute the measurement? |

Both are reported; they answer different questions and are never presented as
interchangeable. The dilution figure is a *diagnostic* of our earlier design, not evidence
about memory.

## Denominators, fixed before results

Pre-computed from the design so the analysis must **reproduce** them rather than read them
off its own output:

- **BEARING flip denominator: 35 memory units / 21 source episodes** (verified by the
  Master Agent from the design manifest; the locator→memory_id map is 1:1).
- Report both, with the **episode-clustered interval governing** where the two readings
  differ (`docs/BEARING_SCARCITY.md`).

## The stopping rule, written before the data

> **If BEARING's both-arms-fail rate is not materially below RANDOM's (~0.78), that is the
> headline and nothing else gets dressed up.**

A screened design that does not lift the floor has failed to make the phenomenon
measurable, and the paper says so plainly.

## F_exec will be 0.000, and that is not a defect

K checked A1.4 live on the running cache: all 264 (task, replicate) WITHOUT-arm groups
returned byte-identical text across memories — the A1.4 caching signature. **It is not the
hazard:** 642 distinct cache keys, 642 distinct latencies, **zero cache hits**, and 81
groups contain more than one memory, so the check is not vacuous. This is genuine
determinism at temperature 0, the same resolution reached on the pilot.

The consequence still binds: `F_exec = 0.000` makes prereg §4's floor clause vacuous and
forces `robust == naive` **mechanically**.

> **Report the robust/naive gap as NOT MEASURABLE, never as zero.** A gap of zero implies a
> measurement was taken; this one cannot be taken at all under a deterministic reader.

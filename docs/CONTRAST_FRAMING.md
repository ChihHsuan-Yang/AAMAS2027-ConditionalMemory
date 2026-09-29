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

⚠️ Recall that exactly **one** deterministically-scorable `errors-gotchas` question exists
benchmark-wide, and it alone was 12.5% of web cells in an earlier run. RANDOM is the only
stratum exposed to it. **Cluster SEs by `task_id`.**

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

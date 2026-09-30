# SciCode representation scale-up — pre-commitment

Written **before** the scaled run executed. Committed to git before any scaled
number existed. The pilot's direction is already known to me (summary and
structured carry the only positive point estimates, all intervals crossing
zero), which is exactly why every design knob below is fixed *mechanically*
rather than chosen.

## 1. Why this run exists

The user's instruction: *"Scale/complete the SciCode representation arm so the
cross-benchmark comparison is better powered."*

The pilot ran **68 of 163 candidate pairs**. The subsample was a cost decision,
not a scientific one. Scaling it is therefore not a new experiment — it is the
completion of a design that was truncated.

## 2. The design is the WHOLE pool — no sampling knob

`tasks_per_memory` is set so that sampling is **inert**: every candidate pair on
every multi-task memory is run. This yields **154 pairs** (from 43 memories with
≥2 candidate tasks; 9 single-task memories excluded by the pre-existing
`min_tasks_per_memory=2` rule, which restricts on the *pairing*, never on an
outcome).

This is deliberate. Had I chosen `tasks_per_memory=4` or `=6` I would be
selecting a design parameter *after* seeing the pilot's direction. Taking the
entire pool removes that degree of freedom: there is no value I could have
tuned. **154 is not a number I picked; it is the number the pool contains.**

## 3. Everything else is inherited, not re-chosen

Frozen identically to the pilot (`scicode_deltau_v1`):
seed 20261008 · relatedness `lexical` · filler_k 2 · `min_tasks_per_memory` 2 ·
metis/gpt-oss-120b · temperature 0 · reasoning_effort low · reader/writer
max_tokens 1024 · concurrency 16 · representations raw,summary,structured.

The per-memory RNG is keyed by `memory_unit_locator`, so the 68 pilot pairs are
a **subset** of these 154 — the scale-up adds cells, it does not resample them.

## 4. What this run may and may not conclude

- The gate remains the pre-committed both-arms-fail rule. It is re-evaluated on
  the scaled cell set; it is **not** assumed to carry over from the pilot.
- **SciCode remains a case study, never a main table.** Scaling improves power;
  it does not promote the benchmark.
- 🔴 **The word "inversion" stays forbidden unless the scaled intervals
  separate.** Wider N narrows intervals; it does not by itself license the
  stronger claim. If the intervals still cross zero the language remains *"the
  point-estimate ordering differs across benchmarks."* `scripts/audit_claims.py`
  enforces this mechanically and has been verified able to fail.

## 5. Stated in advance: what would make this run uninformative

If the scaled both-arms-fail rate stays near the pilot's 0.38–0.46, most cells
remain unable to express a delta in either direction, and the added N buys less
power than the cell count suggests. That is a property of SciCode's difficulty,
not a result — and it will be reported as such rather than absorbed into a
wider interval.

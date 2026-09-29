# Experiment Plan

**Status: DRAFT — blocked on Phase 1 audits.** Nothing here authorizes an inference run.
Sections marked 🔒 cannot be filled until Sub-agent A resolves the dataset and Sub-agent B
resolves the endpoint and analyzer questions.

---

## 0. The order is non-negotiable

1. Experiment 0 — data and feasibility audit (no inference)
2. Experiment 1 — noise floor
3. Experiment 2 — memory x task pilot
4. Analysis — variance decomposition against the noise floor
5. **Kill criterion**
6. Learning stage, only if (5) passes

Starting at 6 is the failure mode this plan exists to prevent.

## 1. The unit

```text
DeltaU(m, t, s) = R(t | m available; seed s) - R(t | m absent; seed s)
```

- `m` — a memory written during a **past episode**
- `t` — a **later, different** future task
- everything else held fixed between arms: model, decoding, prompt scaffold, context
  budget, item order policy

🔒 **The concrete definition of `m` and `t` is not yet fixed.** It follows from the dataset
audit (task 1.5), not from what is convenient to implement.

## 2. Experiment 0 — feasibility audit (owner: Sub-agent A)

Must answer, from files we can open:

1. What exactly is a memory item? Give the JSON field path.
2. Can naturally occurring past trajectories be isolated as candidate memories? How many?
3. Can the SAME memory be injected into several different future tasks? How many tasks per
   memory, **measured**?
4. Can with/without be run with everything else fixed?
5. Expected endpoint-call cost and token cost per call.
6. **Which cells leak** — where the memory literally contains the gold answer — and how do
   we detect that automatically?
7. How are tasks partitioned into NEAR / MID / FAR semantic bands?

## 3. Experiment 1 — noise floor (the cheapest and most important run)

**Nothing downstream is interpretable without this.**

Repeat *identical* conditions — same memory, same task, same prompt, same model, controlled
decoding — across seeds, and measure the spread of the outcome.

Two floors, and they are different:

| Floor | What it measures | Why it is nearly free |
|---|---|---|
| **Execution floor** | variance of `R` across seeds under a fixed arm | — |
| **Empty-memory floor** | variance of the no-memory arm | the no-memory arm is **identical across every memory condition**, so its disagreement rate *is* the scoring noise floor, at no extra cost |
| **Judge floor** | disagreement when re-scoring **byte-identical** outputs | catches verifier nondeterminism at temperature 0, which has produced a 9.35% flip rate on a previous project |

⚠️ All three are needed. A `DeltaU` smaller than the relevant floor is not evidence.

🔒 Size and cost: pending 1.5 and 1.7.

## 4. Experiment 2 — memory x task pilot

Deliberately small. Indicative starting shape, **to be re-costed, not treated as fixed**:

- 20–30 naturally occurring candidate memories
- ~6 future tasks per memory (target ~2 NEAR / 2 MID / 2 FAR)
- 2–3 repeats per condition
- both WITH and WITHOUT arms

The one hard requirement: **multiple future tasks must be evaluated for the SAME memory.**
Everything else is negotiable on cost.

🔒 Exact matrix and cost: pending.

## 5. Analysis — pre-registered before any result is seen

Decompose `DeltaU(m, t, s)`:

```text
overall mean + memory main effect + task main effect + memory x task INTERACTION + noise
```

Report the **interaction's variance share** with the seed-noise floor as an explicit
comparator. Method chosen on data properties — mixed-effects, variance components,
bootstrap CIs, permutation — not fixed in advance, but **the choice and the sign-flip
definition are recorded before results are inspected.**

### Headline metric — Task Sign-Flip Rate

The same memory with `DeltaU(m,t1) > 0` and `DeltaU(m,t2) < 0`.

⚠️ **Confidence matters.** A change inside the execution-noise interval is not a sign flip.
The definition must require both deltas to clear the floor, and that threshold is fixed
before results are seen.

Report as a function of: semantic distance band, task family, memory type, and baseline
memory utility.

⚠️ These must be **naturally occurring** memories. Planted-fault benchmarks make harm
prevalence a design parameter rather than a measurement — which is precisely why the
natural base rate is the defensible number.

### Semantic distance

Partition future tasks by embedding distance from the memory's source episode. Ask:

1. Does utility variance grow with distance?
2. **Do sign flips occur even among NEAR tasks?** ← the sharpest question. A flip inside
   the retrieval neighbourhood shows averaging destroys structure on UMEM's own terms.
3. How predictive is cosine similarity of actual `DeltaU`?
4. Does neighbourhood averaging erase conditional structure?

## 6. 🔴 Kill criterion

Stop or radically reframe if **all** hold:

- the memory x task interaction term is tiny;
- natural sign flips are near the stochastic noise floor;
- a single memory main-effect scalar explains most variation.

**This is an acceptable result and must be reported plainly.** Do not build a system to
rescue a null. Do not continue into a large learned system because infrastructure exists.

## 7. Learning stage — conditional

Only if §6 passes. Compare `G(memory)` against `G(memory, future_task)` at matched budget.
Start linear. The model is not the contribution; the question is whether measured structure
is exploitable.

⚠️ Counter-evidence on record: a [16,16] MLP **ties** a four-feature linear scorer in
2606.12945, and UMEM found 4B beats 1B. **Do not assume headroom exists.**

## 8. Design hazards that bind this plan

1. **Pollution.** TraceRetain shows bounded retention policies fall inside the same Wilson
   95% CI on clean benchmarks. Without real memory pollution every arm lands in one CI.
   Justify the stress condition **before** running.
2. **Fair comparison.** Memory-R2: rollouts that write different memories no longer share
   an intermediate state, making trajectory comparisons unfair. P1 ablates a single memory
   against a **fixed** set, which is closer to their fix — **argue it explicitly.**
3. **Leakage.** Any memory containing the gold answer inflates `DeltaU` trivially. Detect
   and report; do not silently drop (dropping changes the question being answered).
4. **Verifier drift.** WITH and WITHOUT arms must be scored by the *same* verifier version.
   Arm-dependent verifier versions have already invalidated a table on a sibling project.

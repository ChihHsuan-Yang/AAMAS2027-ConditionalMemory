# Pre-commitment as Instrumentation

**2026-09-29.** A short record of a practice this project arrived at by necessity, and
which belongs in the paper's methods.

---

## The failure mode being guarded against

Not dishonesty. The realistic failure is that **someone who has invested effort in a design
reads an ambiguous number generously.** By the time the screened run's results existed,
this project had spent ~6,900 endpoint calls and most of a day on the design that produces
them. That is precisely the condition under which a marginal result gets talked past.

## What was committed before the numbers existed

Each of these is in git history **preceding** the artifact it governs:

| commitment | where | governs |
|---|---|---|
| noise-floor estimators, robust-label thresholds, sign-flip definition | `ANALYSIS_PREREGISTRATION.md` | all labels and rates |
| a flip is **not** evidence of interaction; excess over the additive null is required | Amendment A1.1 | the headline claim |
| BEARING↔MC carries the claim; BEARING↔RANDOM is composition-mismatched | `CONTRAST_FRAMING.md` | which contrast is quoted |
| flip denominators **35 units / 21 episodes**, clustered interval governs | `BEARING_SCARCITY.md` | the headline CI |
| the decomposition will likely fail identifiability; quote **no** share from a clipped ratio | `IDENTIFIABILITY_STATUS.md` | the variance result |
| **the stopping rule** | `CONTRAST_FRAMING.md` + `k3_analyze_screened.py` | whether there is a paper |

## The stopping rule, and why it is code

> If BEARING's both-arms-fail is not **materially** below RANDOM's, the instrument cannot
> detect anything, and **that** is the headline.

"Materially" is the weak point in any such rule — it is exactly the word that gets
reinterpreted after the fact. So it is defined in committed code, not prose:

```text
separated := BEARING_wilson_upper < RANDOM_point_estimate
```

A separation the interval itself supports, not an eyeballed gap. The analysis emits
`STOPPING_RULE.VERDICT` into the artifact either way.

### Verified to return BOTH answers

A rule that always passes is not a rule. Exercised by the Master Agent on three worlds:

| world | BEARING (upper) vs RANDOM | verdict |
|---|---|---|
| screen fails | 0.7604 (0.8100) vs 0.7798 | **DID NOT MATERIALLY REDUCE** |
| marginal | 0.7000 (0.7900) vs 0.7800 | **DID NOT MATERIALLY REDUCE** |
| screen works | 0.4000 (0.4900) vs 0.7800 | BOUGHT CAPACITY |

It is conservative at the margin, which is the correct direction.

## The general form

A ruling a human must remember at reporting time is a ruling that will eventually be
forgotten — or read generously. Prefer, in this order:

```text
a field emitted into the artifact
  > an assertion in code
    > a line in a document
      > an agreement between two parties who must remember it
```

Sub-agent K's `GOVERNING: task_clustered` field is the model: when the task-clustered CI
and the cell-level *p* disagree, the artifact says which one governs. **The artifact
refuses to be misread**, rather than relying on the reader to recall a policy.

## Why this is a methods contribution, not housekeeping

The paper reports a measurement whose instrument was rebuilt four times in one day (two
prompt arms, a reader escalation, a screened redesign). A reader is entitled to ask whether
the analysis was tuned until it produced an effect.

The answer is checkable rather than asserted: **the definitions, denominators, contrast
choice, and stopping rule are all in git history that predates the data**, and the rule
that could kill the paper is executable code with a verified negative branch.

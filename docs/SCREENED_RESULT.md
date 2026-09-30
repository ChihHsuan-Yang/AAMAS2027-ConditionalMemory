# The Screened Result

**Run `k2_screened`, 2026-09-29. 5,198 real endpoint calls, 0 errors, 2,599 cells.**
Every number below was computed by the Master Agent from
`results/deltau_screened/cells.jsonl`.

---

## 1. Artifact integrity, checked before any result was read

| check | result |
|---|---|
| cache rows | **5,198 / 5,198** planned |
| arms | `with_memory` 2,599 / `without_memory` 2,599 — exactly balanced |
| empty responses | **0** |
| rows carrying `provenance.stratum` natively | **2,599 / 2,599** |
| rows unjoinable to the design | **0** |

The stratum was available natively *and* via the design join, and **both routes give
identical numbers** — an unplanned but useful cross-check.

## 2. 🟢 STOPPING RULE: the screen bought measurement capacity

| stratum | cells | both-arms-fail | rate | 95% Wilson |
|---|---:|---:|---:|---|
| **BEARING** | 139 | 73 | **0.5252** | [0.4426, **0.6064**] |
| MATCHED_CONTROL | 146 | 115 | 0.7877 | [0.7144, 0.8462] |
| RANDOM | 872 | 611 | **0.7007** | [0.6695, 0.7302] |

Criterion, committed in code before the data existed: BEARING's Wilson **upper** bound
below RANDOM's point estimate.

```text
0.6064  <  0.7007   →   SCREEN BOUGHT MEASUREMENT CAPACITY
```

Both-arms-fail falls from **0.70 → 0.53**. The instrument can now exhibit the phenomenon
it was built to measure, which the two earlier arms (0.785, 0.8375) could not.

## 3. Mean ΔU by stratum

| stratum | cells | mean ΔU |
|---|---:|---:|
| **BEARING** | 139 | **+0.3453** |
| MATCHED_CONTROL | 146 | +0.0274 |
| RANDOM | 872 | +0.0642 |

## 4. The headline: the paired within-memory contrast

All three strata contain the **identical 60 memories**, so this is paired — memory identity
cancels, and per-memory quality is arithmetically incapable of producing a difference
(verified bit-identical across quality sd 0→500).

```text
BEARING − MATCHED_CONTROL, per memory
```

| quantity | value |
|---|---|
| paired memories | **60** |
| **non-zero contributors** | **35** |
| source episodes | 35 |
| **all-memories mean** (pre-registered; significance comes from this) | **+0.3349** |
| contributors-only mean (conditional; conditions on an outcome) | +0.5740 |
| memory bootstrap 95% CI | [+0.2138, +0.4622] |
| **episode-clustered 95% CI — GOVERNS** | **[+0.1989, +0.4758]** |

> **The governing interval excludes zero.** A memory that bears on a task raises task
> reward by ≈ **0.33** on the population measure, and by ≈ **0.57** among the memories
> where any effect could be observed.

Per the standing rule, all three numbers are reported together: the all-memories mean
understates the mechanism, the contributors-only mean overstates the confidence, and the
contributor count (35 of 60) is stated beside the nominal denominator.

## 4b. 🔴 A scorer-composition confound in the headline — found by SA-HF, verified

BEARING and MATCHED_CONTROL are disjoint in tasks by construction, and different tasks
carry **different `eval_function` scorers**. So for some memories the *mix of scorers*
differs between the two strata, and the paired contrast then differences two scorer mixes
as well as two strata.

Master Agent's independent split:

| memories | paired B−MC |
|---|---:|
| scorer mix **constant** across strata (35) | **+0.3786** |
| scorer mix **changes** (25) | **+0.2737** |
| pooled (60) | **+0.3349** |

> **The effect survives in both subsets**, so the confound does not overturn it — but the
> pooled number is not purely a bearing contrast.

**Reporting rule:** quote the pooled **+0.3349** as the headline and the constant-mix
**+0.3786** beside it as the confound-free subset. The constant-mix figure is *larger*, so
the confound works **against** us and correcting for it strengthens the result.

## 5. Sign structure

| stratum | positive cells | zero | negative |
|---|---:|---:|---:|
| BEARING | 50 | 87 | 2 |
| MATCHED_CONTROL | 10 | 130 | 6 |
| RANDOM | 82 | 764 | 26 |

⚠️ **Harm is rare in this design** — 2 negative cells in BEARING. The paper must not claim
a harmful-memory rate from it; the design screened *for* bearing, which selects toward
helpful pairings.

## 6. What still must be run before this is written up

- excess over the fitted additive null (A1.1) — **a flip rate is not evidence of
  interaction**
- task-clustered CIs and the leave-one-task-out jackknife on every contrast
- `PAIRED_POWER_STATUS`
- the identifiability verdict (predicted `AT_UPPER_BOUNDARY`; quote no share if so)
- extension of `scripts/audit_claims.py` to cover every number above

**Nothing here enters the manuscript until `audit_claims.py` re-derives it.**

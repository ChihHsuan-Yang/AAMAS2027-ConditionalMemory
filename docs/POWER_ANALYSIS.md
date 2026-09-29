# Power Analysis — how many memories the headline analysis needs

**Measured 2026-09-29 by the Master Agent** on synthetic data with **known** planted
variance components, using the committed estimator
(`src/p1mem/analysis/decomposition.py`). Reproduce with the snippet at the bottom.

---

## The finding

A failing test surfaced this, and it is a **design constraint, not a flaky test**. The
REML variance decomposition recovers the planted memory / task / interaction shares to
this accuracy:

| memories × tasks | mean max share error (6 seeds) | worst seed |
|---:|---:|---:|
| **30 × 8** | **0.0627** | **0.1175** |
| 60 × 8 | 0.0238 | 0.0365 |
| 120 × 8 | 0.0231 | 0.0310 |
| 240 × 8 | 0.0155 | 0.0200 |
| 120 × 16 | **0.0103** | 0.0184 |

## What it means for the experiment

> **At 30 memories the estimator can be wrong about an interaction share by up to 11.75
> percentage points.** The paper's central claim is *the size of the interaction share*.
> An 11-point error bar on the headline number is not a result.

The inherited pilot sketch — "20–30 candidate memories, ~6 future tasks" — is **too small
for the decomposition**, and this is measurable in advance rather than discoverable in
October.

### Binding design decisions

1. **Minimum 60 memories** for any reported variance decomposition. Error drops 2.6× from
   30→60 (0.0627 → 0.0238), and the worst-seed case improves 3.2×.
2. **Target 120 × 8** for the main table. Beyond that, returns diminish sharply: 120→240
   buys only 0.008.
3. **More tasks per memory beats more memories.** 120 × 16 (0.0103) beats 240 × 8 (0.0155)
   with **half the memories** — because the interaction term is estimated from *cells*, and
   tasks-per-memory is what identifies it. **Prefer widening the task axis.**
4. **30 memories remains fine for the pilot** — its job is to prove the pipeline, not to
   estimate a share. The pilot must simply not report a decomposition as a result.

## Why the test stays strict

The failing assertion (`mean error < 0.06` at 30×8) is **kept**, not relaxed. It encodes a
real property: at that size the estimator is not trustworthy for our headline. Loosening
the threshold to make the suite green would delete the only automated warning that the
study is underpowered.

It is now marked `xfail(strict=True)` with this document referenced, so that if someone
later improves the estimator enough to pass at 30×8, **the suite fails and forces this
page to be revisited** rather than silently keeping a stale constraint.

## Caveats — what this does NOT establish

- Synthetic data drawn from **the model the estimator assumes**. Real ΔU may be
  heteroscedastic, non-Gaussian, or have structure the model omits; real recovery will be
  **no better than this, and plausibly worse**.
- Recovery error is measured against the **realized** shares of each simulated draw, not
  the population parameters — the right target, but it means these numbers are a floor on
  estimator error, not a total error budget.
- Says nothing about the sign-flip rate's power, which is a separate binomial question
  driven by tasks-per-memory and the noise floor.

## Reproduce

```bash
cd repo && /Users/bellayang/miniconda3/bin/python3 - <<'PY'
import sys, numpy as np; sys.path.insert(0,'src'); sys.path.insert(0,'tests')
from test_analysis_decomposition import make_dataset, _realized_shares
from p1mem.analysis import decomposition as dc
for nm, nt in [(30,8),(60,8),(120,8),(240,8),(120,16)]:
    errs = [dc.recovery_error(
                dc.variance_decomposition(make_dataset(seed=s, n_memories=nm, n_tasks=nt).rows, n_boot=0),
                _realized_shares(make_dataset(seed=s, n_memories=nm, n_tasks=nt)))["max_abs_share_error"]
            for s in range(85, 91)]
    print(nm, nt, round(float(np.mean(errs)), 4))
PY
```

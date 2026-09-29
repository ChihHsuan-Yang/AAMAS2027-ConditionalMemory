"""Shared primitives for the P1 analysis package.

Everything in ``p1mem.analysis`` consumes rows in the canonical schema
(``p1mem.schema.FIELD_ORDER``) and nothing else. This module holds the pieces every
estimator needs: row admission, grouping, pooling, clustered bootstrap, Wilson
intervals, and Benjamini-Hochberg.

Three rules are enforced here rather than restated in every estimator:

1. **An errored row has no outcome.** ``error_code_if_any`` set, or a null reward, means
   the cell produced nothing. Scoring it as 0 would manufacture a harmful memory
   (``schema.py`` ERROR_CODES). ``admit_rows`` drops those and *reports the count*.
2. **Cluster is experimental identity** (PROJECT_GOAL invariant 3). Pooling rows from two
   ``reader_cluster`` values is a silent merge of two arms. ``require_homogeneous``
   refuses unless the caller passes ``allow_pooling=True``, which is then recorded in the
   estimate's flags so it appears in the output rather than only in the call site.
3. **One verifier per pooled set.** Arm-dependent or drifting verifier versions have
   already invalidated a sibling project's table. The same guard covers it.

Nothing here imports matplotlib, so importing the estimators never needs a display.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

# Default RNG seed. Fixed so every reported number is reproducible; changing it is a
# change to the analysis and belongs in docs/DECISION_LOG.md.
DEFAULT_SEED = 20260929
DEFAULT_N_BOOT = 2000
DEFAULT_ALPHA = 0.05


# ==========================================================================  estimate
@dataclass
class Estimate:
    """A point estimate with an interval, its provenance, and its caveats.

    ``flags`` is not decoration. Every condition that would make a reader interpret the
    number differently -- a boundary solution, a fallback method, a pooled arm, a
    denominator too small to mean anything -- lands here and travels with the number into
    the report, because a caveat that stays in the call site is a caveat nobody reads.
    """

    point: float | None
    ci_lower: float | None = None
    ci_upper: float | None = None
    n_units: int = 0
    n_obs: int = 0
    method: str = ""
    scale: str = ""
    flags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "n_units": self.n_units,
            "n_obs": self.n_obs,
            "method": self.method,
            "scale": self.scale,
            "flags": list(self.flags),
            "extra": _jsonable(self.extra),
        }

    def __str__(self) -> str:  # pragma: no cover - display only
        if self.point is None:
            return f"{self.method}: UNDETERMINED ({'; '.join(self.flags) or 'no data'})"
        ci = ""
        if self.ci_lower is not None and self.ci_upper is not None:
            ci = f" [95% CI {self.ci_lower:.4g}, {self.ci_upper:.4g}]"
        return f"{self.method}: {self.point:.4g}{ci}  (n_units={self.n_units}, n_obs={self.n_obs})"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Estimate):
        return value.to_dict()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def jsonable(value: Any) -> Any:
    """Public alias -- used by the scripts that serialize a whole analysis run."""
    return _jsonable(value)


# =====================================================================  row admission
#: Fields whose nullity means "this row produced no scored outcome".
OUTCOME_FIELDS: tuple[str, ...] = (
    "reward_with_memory",
    "reward_without_memory",
    "delta_utility",
)


@dataclass
class Admission:
    """The result of screening rows, with the reason for every exclusion."""

    rows: list[dict[str, Any]]
    n_input: int
    n_errored: int
    n_missing_reward: int
    n_leakage_flagged: int
    error_codes: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_input": self.n_input,
            "n_admitted": len(self.rows),
            "n_errored": self.n_errored,
            "n_missing_reward": self.n_missing_reward,
            "n_leakage_flagged_admitted": self.n_leakage_flagged,
            "error_codes": dict(self.error_codes),
        }


def admit_rows(rows: Iterable[Mapping[str, Any]]) -> Admission:
    """Keep only rows that carry a real scored outcome in BOTH arms.

    Leakage-flagged rows are **kept and counted**, never dropped: EXPERIMENT_PLAN 8.3 is
    explicit that dropping them changes the question being answered.
    """
    kept: list[dict[str, Any]] = []
    n_input = 0
    n_err = 0
    n_missing = 0
    n_leak = 0
    codes: dict[str, int] = defaultdict(int)
    for row in rows:
        n_input += 1
        code = row.get("error_code_if_any")
        if code:
            n_err += 1
            codes[str(code)] += 1
            continue
        if any(row.get(f) is None for f in OUTCOME_FIELDS):
            n_missing += 1
            continue
        if row.get("leakage_flag"):
            n_leak += 1
        kept.append(dict(row))
    return Admission(kept, n_input, n_err, n_missing, n_leak, dict(codes))


# ==========================================================================  guards
#: Pooling across any of these silently merges two experimental conditions.
IDENTITY_GUARD_KEYS: tuple[str, ...] = (
    "reader_cluster",
    "reader_model",
    "reader_prompt_version",
    "reader_reasoning_effort",
    "verifier_id",
    "verifier_version",
)


class HeterogeneousPoolError(ValueError):
    """Raised when an estimator is asked to pool across experimental identities."""


def homogeneity_report(
    rows: Sequence[Mapping[str, Any]],
    keys: Sequence[str] = IDENTITY_GUARD_KEYS,
) -> dict[str, list[Any]]:
    """Distinct values per identity key, for keys with more than one value."""
    seen: dict[str, set] = {k: set() for k in keys}
    for row in rows:
        for k in keys:
            seen[k].add(row.get(k))
    return {k: sorted(v, key=lambda x: (x is None, str(x))) for k, v in seen.items() if len(v) > 1}


def require_homogeneous(
    rows: Sequence[Mapping[str, Any]],
    *,
    keys: Sequence[str] = IDENTITY_GUARD_KEYS,
    allow_pooling: bool = False,
) -> list[str]:
    """Refuse to pool across experimental identity unless told to, in writing.

    Returns a list of flags (empty when homogeneous). With ``allow_pooling=True`` the
    heterogeneity becomes a flag on the estimate instead of an exception -- it is still
    visible in the output, which is the point.
    """
    bad = homogeneity_report(rows, keys)
    if not bad:
        return []
    detail = "; ".join(f"{k}={v}" for k, v in bad.items())
    if not allow_pooling:
        raise HeterogeneousPoolError(
            "refusing to pool rows spanning multiple experimental identities: "
            f"{detail}. PROJECT_GOAL invariant 3: cluster is part of the experimental "
            "unit. Pass allow_pooling=True only with a recorded reason."
        )
    return [f"POOLED_ACROSS_IDENTITY:{detail}"]


# =========================================================================  grouping
def group_by(
    rows: Iterable[Mapping[str, Any]], key: str | Sequence[str]
) -> dict[Any, list[dict[str, Any]]]:
    """Group rows by one field or a tuple of fields, preserving insertion order."""
    keys = (key,) if isinstance(key, str) else tuple(key)
    out: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        k = row.get(keys[0]) if len(keys) == 1 else tuple(row.get(x) for x in keys)
        out.setdefault(k, []).append(dict(row))
    return out


def values(rows: Iterable[Mapping[str, Any]], field_name: str) -> list[float]:
    """Non-null numeric values of a field.

    Nulls are *excluded from the denominator*, never summed as zeros. ``reasoning_tokens``
    is null on a cluster that does not report it, and treating that as 0 has burned this
    project before (schema.py, CLUSTER_REPORTS_REASONING_TOKENS).
    """
    out = []
    for row in rows:
        v = row.get(field_name)
        if v is None:
            continue
        out.append(float(v))
    return out


# ==========================================================================  pooling
def pooled_variance(groups: Sequence[Sequence[float]]) -> tuple[float | None, int, int]:
    """Within-group variance pooled by degrees of freedom.

    Returns ``(variance, df, n_groups_contributing)``. ``variance`` is None when no group
    has 2+ observations -- which is an honest "not measurable", NOT zero. A floor reported
    as 0.0 because nothing was repeated would make every effect clear it.
    """
    ss = 0.0
    df = 0
    used = 0
    for g in groups:
        arr = np.asarray([x for x in g if x is not None], dtype=float)
        if arr.size < 2:
            continue
        ss += float(((arr - arr.mean()) ** 2).sum())
        df += arr.size - 1
        used += 1
    if df == 0:
        return None, 0, 0
    return ss / df, df, used


def pooled_sd(groups: Sequence[Sequence[float]]) -> tuple[float | None, int, int]:
    var, df, used = pooled_variance(groups)
    return (None if var is None else math.sqrt(max(var, 0.0))), df, used


# ========================================================================  bootstrap
def percentile_ci(
    samples: Sequence[float], alpha: float = DEFAULT_ALPHA
) -> tuple[float | None, float | None]:
    arr = np.asarray([s for s in samples if s is not None and np.isfinite(s)], dtype=float)
    if arr.size == 0:
        return None, None
    lo = float(np.quantile(arr, alpha / 2.0))
    hi = float(np.quantile(arr, 1.0 - alpha / 2.0))
    return lo, hi


def cluster_bootstrap(
    units: Sequence[Any],
    stat_fn: Callable[[Sequence[Any]], float | None],
    *,
    strata: Mapping[Any, Any] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
) -> tuple[float | None, float | None, float | None, int]:
    """Cluster bootstrap, optionally stratified. Returns (point, lo, hi, n_effective).

    Resampling is WITH replacement over ``units`` -- the unit of generalization, which for
    this project is the memory (ANALYSIS_PREREGISTRATION section 6), not the row. When
    ``strata`` is given, each stratum's unit count is preserved, following
    ``domain_stratified_bootstrap`` in the sibling analyzer.

    ``stat_fn`` may return None for a degenerate resample (e.g. every drawn unit has one
    replicate); those draws are dropped and counted, rather than coerced to a number.
    """
    units = list(units)
    point = stat_fn(units)
    if not units:
        return point, None, None, 0
    rng = np.random.default_rng(seed)
    if strata is None:
        pools = [units]
    else:
        by: dict[Any, list[Any]] = defaultdict(list)
        for u in units:
            by[strata.get(u)].append(u)
        pools = [by[k] for k in sorted(by, key=lambda x: (x is None, str(x)))]
    draws: list[float] = []
    for _ in range(n_boot):
        sample: list[Any] = []
        for pool in pools:
            if not pool:
                continue
            idx = rng.integers(0, len(pool), size=len(pool))
            sample.extend(pool[i] for i in idx)
        v = stat_fn(sample)
        if v is not None and np.isfinite(v):
            draws.append(float(v))
    lo, hi = percentile_ci(draws, alpha)
    return point, lo, hi, len(draws)


def bootstrap_mean_ci(
    xs: Sequence[float],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Percentile bootstrap of a mean. Returns (mean, lo, hi, two_sided_p).

    The p-value is the bootstrap two-sided tail probability at zero, kept alongside the
    interval because ANALYSIS_PREREGISTRATION section 11 asks for Benjamini-Hochberg over
    cell-level labels and BH needs a p-value. The pre-registration defines the LABEL by a
    CI, not by a p-value, so this quantity is an addition for the multiple-comparison
    step only; it never overrides the CI rule in section 4.
    """
    arr = np.asarray([x for x in xs if x is not None], dtype=float)
    if arr.size == 0:
        return None, None, None, None
    mean = float(arr.mean())
    if arr.size == 1:
        # One replicate cannot separate an effect from noise. Report the value with no
        # interval rather than a zero-width interval that would read as certainty.
        return mean, None, None, None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    draws = arr[idx].mean(axis=1)
    lo, hi = percentile_ci(draws, alpha)
    frac_le = float((draws <= 0).mean())
    frac_ge = float((draws >= 0).mean())
    p = min(1.0, 2.0 * min(frac_le, frac_ge))
    return mean, lo, hi, p


# =====================================================================  proportions
def wilson_ci(
    successes: int, n: int, *, alpha: float = DEFAULT_ALPHA
) -> tuple[float | None, float | None, float | None]:
    """Wilson score interval. Returns (rate, lo, hi); (None, None, None) when n == 0.

    Required by ANALYSIS_PREREGISTRATION section 5 for the sign-flip rate. A zero
    denominator is None, not 0.0 -- "no memories qualified" and "no memories flipped" are
    different statements.
    """
    if n <= 0:
        return None, None, None
    from scipy.stats import norm  # local import keeps module import cheap

    z = float(norm.ppf(1.0 - alpha / 2.0))
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, centre - half), min(1.0, centre + half)


def benjamini_hochberg(pvalues: Sequence[float | None], q: float = 0.10) -> list[bool]:
    """BH step-up at level ``q``. Entries with p=None are never rejected.

    ANALYSIS_PREREGISTRATION section 11 fixes q = 0.10 and requires the raw uncorrected
    count be reported alongside; the callers here do that.
    """
    idx = [i for i, p in enumerate(pvalues) if p is not None]
    out = [False] * len(pvalues)
    m = len(idx)
    if m == 0:
        return out
    order = sorted(idx, key=lambda i: float(pvalues[i]))  # type: ignore[arg-type]
    k_max = 0
    for rank, i in enumerate(order, start=1):
        if float(pvalues[i]) <= q * rank / m:  # type: ignore[arg-type]
            k_max = rank
    for rank, i in enumerate(order, start=1):
        if rank <= k_max:
            out[i] = True
    return out


# ==========================================================  balanced replicate subset
def balanced_replicate_subset(
    rows: Sequence[Mapping[str, Any]],
    *,
    n_replicates: int | None = None,
    cell_key: str = "cell_id",
) -> tuple[list[dict[str, Any]], int, int]:
    """The balanced minimum-replicate subset (ANALYSIS_PREREGISTRATION section 12).

    Adaptive replication (P1-058) sends extra replicates to near-zero effects and apparent
    sign flips, which makes replicate count non-random and biases naive pooling. The
    pre-registration fixes the mitigation: headline rates are computed on the balanced
    subset as the PRIMARY number.

    Takes the first ``n`` replicates of every cell, ordered by ``replicate_id`` so the
    choice does not depend on file order -- and therefore not on which replicates happened
    to be written first, which under adaptive replication is itself informative.

    Returns ``(subset_rows, n_replicates_used, n_cells_dropped)``. Cells with fewer than
    ``n`` replicates are dropped whole; a partially-included cell would reintroduce the
    imbalance.
    """
    by_cell = group_by(rows, cell_key)
    counts = [len(v) for v in by_cell.values()]
    if not counts:
        return [], 0, 0
    n = n_replicates if n_replicates is not None else min(counts)
    n = max(1, int(n))
    out: list[dict[str, Any]] = []
    dropped = 0
    for _cell, group in by_cell.items():
        if len(group) < n:
            dropped += 1
            continue
        ordered = sorted(group, key=lambda r: (r.get("replicate_id") is None, r.get("replicate_id")))
        out.extend(ordered[:n])
    return out, n, dropped


# ================================================================  tercile banding
def tercile_bands(
    similarities: Sequence[float],
) -> tuple[float, float]:
    """The two cut points of the observed similarity distribution.

    ANALYSIS_PREREGISTRATION section 7: bands are terciles OF THE OBSERVED DISTRIBUTION,
    computed per benchmark, because cosine scales are not comparable across corpora.
    """
    arr = np.asarray(list(similarities), dtype=float)
    if arr.size == 0:
        raise ValueError("no similarities to band")
    return float(np.quantile(arr, 1.0 / 3.0)), float(np.quantile(arr, 2.0 / 3.0))


def assign_band(similarity: float, cuts: tuple[float, float]) -> str:
    """NEAR = top third, MID = middle, FAR = bottom third (prereg section 7)."""
    lo, hi = cuts
    if similarity > hi:
        return "NEAR"
    if similarity > lo:
        return "MID"
    return "FAR"


def assign_bands_by_tercile(
    rows: Sequence[Mapping[str, Any]],
    *,
    per: str = "benchmark",
    similarity_field: str = "semantic_similarity",
) -> dict[Any, str]:
    """row_id -> band, recomputed from the data rather than trusting the stored field.

    The stored ``semantic_distance_band`` is written upstream; recomputing lets the
    analysis check the two agree instead of assuming it.
    """
    out: dict[Any, str] = {}
    for _key, group in group_by(rows, per).items():
        sims = [r.get(similarity_field) for r in group if r.get(similarity_field) is not None]
        if not sims:
            continue
        cuts = tercile_bands(sims)
        for r in group:
            s = r.get(similarity_field)
            if s is None:
                continue
            out[r.get("row_id")] = assign_band(float(s), cuts)
    return out


__all__ = [
    "DEFAULT_SEED", "DEFAULT_N_BOOT", "DEFAULT_ALPHA",
    "Estimate", "Admission", "admit_rows", "jsonable",
    "IDENTITY_GUARD_KEYS", "HeterogeneousPoolError", "homogeneity_report",
    "require_homogeneous", "group_by", "values",
    "pooled_variance", "pooled_sd", "percentile_ci", "cluster_bootstrap",
    "bootstrap_mean_ci", "wilson_ci", "benjamini_hochberg",
    "balanced_replicate_subset", "tercile_bands", "assign_band", "assign_bands_by_tercile",
]

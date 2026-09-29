"""D2 -- robust labels (prereg section 4) and sign flips (section 5).

Section 4, verbatim:

    robust_useful  : CI_lower > 0  AND  mean dU  > F
    robust_harmful : CI_upper < 0  AND |mean dU| > F
    neutral        : CI contains 0  OR  |mean dU| <= F

Section 5, verbatim:

    A memory m exhibits a ROBUST SIGN FLIP iff there exist tasks t1, t2 with
        label(m, t1) == robust_useful  AND  label(m, t2) == robust_harmful
    Both cells must independently clear section 4. A raw sign difference is NOT a flip.
    Reported as #(memories with >=1 robust flip) / #(memories evaluated on >=2 tasks),
    denominator stated explicitly, plus a Wilson 95% CI.
    ALSO REPORTED, ALWAYS: the naive rate using raw sign differences with no floor.

The rule itself already lives in ``p1mem.schema.derive_utility_label`` -- written by
Sub-agent E straight out of section 4. This module **calls that function** rather than
restating the inequalities. Two copies of a pre-registered rule is two places for it to
drift, and the stored ``utility_label`` on every row is produced by the schema copy, so a
second implementation here would let the analysis and the dataset disagree about what the
pre-registration says.

What this module adds on top of the rule: the cell statistics the rule consumes (mean and
bootstrap CI over the cell's replicates), the memory-level flip logic, the naive
comparator, the Wilson interval, Benjamini-Hochberg (section 11), and the balanced
minimum-replicate primary estimate (section 12).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from p1mem.schema import derive_utility_label

from .common import (
    DEFAULT_ALPHA,
    DEFAULT_N_BOOT,
    DEFAULT_SEED,
    Estimate,
    admit_rows,
    balanced_replicate_subset,
    benjamini_hochberg,
    bootstrap_mean_ci,
    group_by,
    require_homogeneous,
    wilson_ci,
)

ROBUST_USEFUL = "robust_useful"
ROBUST_HARMFUL = "robust_harmful"
NEUTRAL = "neutral"
UNDETERMINED = "undetermined"


@dataclass
class CellStat:
    """Per-cell statistics and the pre-registered label derived from them."""

    cell_id: Any
    memory_id: Any
    task_id: Any
    benchmark: Any
    representation: Any
    mean_delta: float | None
    ci_lower: float | None
    ci_upper: float | None
    n_replicates: int
    p_value: float | None
    label: str
    naive_sign: int  # sign of mean dU with NO floor and NO CI: -1, 0, +1
    semantic_similarity: float | None = None
    band: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["extra"] = dict(self.extra)
        return d


def cell_statistics(
    rows: Iterable[Mapping[str, Any]],
    floor: float | None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    allow_pooling: bool = False,
    delta_field: str = "delta_utility",
) -> list[CellStat]:
    """Mean dU, bootstrap CI over replicates, and the section-4 label, per cell.

    ``floor`` is F from section 2. Passing ``None`` is legitimate and yields
    ``undetermined`` for every cell -- which is the correct state of the project until
    P1-051 runs, and is what ``schema.derive_utility_label`` already does. It is NOT a
    reason to substitute 0.

    The CI is a percentile bootstrap over the cell's OWN replicates. A cell with one
    replicate gets no interval and is ``undetermined``: prereg section 4 needs a CI, and
    PROJECT_GOAL invariant 4 is that a single-shot label cannot distinguish a real effect
    from execution noise.
    """
    adm = admit_rows(rows)
    data = adm.rows
    require_homogeneous(data, allow_pooling=allow_pooling)
    out: list[CellStat] = []
    for cell, group in group_by(data, "cell_id").items():
        deltas = [float(r[delta_field]) for r in group if r.get(delta_field) is not None]
        mean, lo, hi, p = bootstrap_mean_ci(deltas, n_boot=n_boot, seed=seed, alpha=alpha)
        label = derive_utility_label(lo, hi, mean, floor)
        head = group[0]
        naive = 0 if mean is None else (1 if mean > 0 else (-1 if mean < 0 else 0))
        out.append(
            CellStat(
                cell_id=cell,
                memory_id=head.get("memory_id"),
                task_id=head.get("future_task_id"),
                benchmark=head.get("benchmark"),
                representation=head.get("memory_representation"),
                mean_delta=mean,
                ci_lower=lo,
                ci_upper=hi,
                n_replicates=len(deltas),
                p_value=p,
                label=label,
                naive_sign=naive,
                semantic_similarity=head.get("semantic_similarity"),
                band=head.get("semantic_distance_band"),
                extra={
                    "source_episode_id": head.get("source_episode_id"),
                    "future_task_family": head.get("future_task_family"),
                    "retrieval_method": head.get("retrieval_method"),
                    "leakage_flag": any(bool(r.get("leakage_flag")) for r in group),
                },
            )
        )
    return out


def apply_bh_correction(
    cells: Sequence[CellStat], q: float = 0.10
) -> tuple[list[CellStat], dict[str, int]]:
    """Section 11: per-family BH at q=0.10 over the cell-level labels feeding a rate.

    A cell whose bootstrap p-value survives BH keeps its label; one that does not is
    demoted to ``neutral`` and the demotion is recorded. The family is the benchmark, so
    two benchmarks are not corrected against each other.

    Returns ``(bh_labelled_cells, counts)`` where ``counts`` carries BOTH the raw
    uncorrected non-neutral count and the corrected one -- section 11 requires the raw
    number be reported alongside, and the pair is only informative together.
    """
    out: list[CellStat] = []
    counts = {"raw_useful": 0, "raw_harmful": 0, "bh_useful": 0, "bh_harmful": 0,
              "demoted": 0}
    for _fam, group in group_by(
        [{"_c": c, "benchmark": c.benchmark} for c in cells], "benchmark"
    ).items():
        members = [g["_c"] for g in group]
        rejected = benjamini_hochberg([c.p_value for c in members], q=q)
        for c, keep in zip(members, rejected):
            if c.label == ROBUST_USEFUL:
                counts["raw_useful"] += 1
            elif c.label == ROBUST_HARMFUL:
                counts["raw_harmful"] += 1
            new = c.label
            if c.label in (ROBUST_USEFUL, ROBUST_HARMFUL) and not keep:
                new = NEUTRAL
                counts["demoted"] += 1
            if new == ROBUST_USEFUL:
                counts["bh_useful"] += 1
            elif new == ROBUST_HARMFUL:
                counts["bh_harmful"] += 1
            c2 = CellStat(**{**c.to_dict(), "label": new})
            c2.extra = {**c.extra, "bh_q": q, "bh_rejected": bool(keep),
                        "label_before_bh": c.label}
            out.append(c2)
    return out, counts


# ==========================================================================  sign flips
@dataclass
class FlipReport:
    """Section 5's two rates, side by side, with the denominator stated."""

    robust: Estimate
    naive: Estimate
    n_memories_total: int
    n_memories_eligible: int
    robust_flip_memories: list[Any]
    naive_flip_memories: list[Any]
    per_memory: dict[Any, dict[str, Any]]
    label_counts: dict[str, int]
    flags: list[str] = field(default_factory=list)

    @property
    def gap(self) -> float | None:
        """naive rate - robust rate. Prereg section 5: 'the gap IS a contribution'."""
        if self.robust.point is None or self.naive.point is None:
            return None
        return self.naive.point - self.robust.point

    def to_dict(self) -> dict[str, Any]:
        return {
            "robust": self.robust.to_dict(),
            "naive": self.naive.to_dict(),
            "gap_naive_minus_robust": self.gap,
            "n_memories_total": self.n_memories_total,
            "n_memories_eligible_denominator": self.n_memories_eligible,
            "denominator_definition":
                "memories evaluated on >=2 distinct future tasks (prereg section 5)",
            "n_robust_flip_memories": len(self.robust_flip_memories),
            "n_naive_flip_memories": len(self.naive_flip_memories),
            "robust_flip_memories": list(self.robust_flip_memories),
            "label_counts": dict(self.label_counts),
            "flags": list(self.flags),
        }

    def __str__(self) -> str:  # pragma: no cover - display only
        def fmt(e: Estimate) -> str:
            if e.point is None:
                return "n/a"
            ci = ("" if e.ci_lower is None
                  else f" [{e.ci_lower:.3f}, {e.ci_upper:.3f}]")
            return f"{e.point:.4f}{ci}"
        return (
            f"robust sign-flip rate = {len(self.robust_flip_memories)}/"
            f"{self.n_memories_eligible} = {fmt(self.robust)}\n"
            f"naive  sign-flip rate = {len(self.naive_flip_memories)}/"
            f"{self.n_memories_eligible} = {fmt(self.naive)}\n"
            f"gap (naive - robust)  = "
            f"{'n/a' if self.gap is None else f'{self.gap:+.4f}'}"
        )


def sign_flip_report(
    cells: Sequence[CellStat], *, alpha: float = DEFAULT_ALPHA
) -> FlipReport:
    """Section 5. Robust flip rate + the naive no-floor comparator, on one denominator.

    **Denominator.** "#(memories evaluated on >=2 tasks)", counted over DISTINCT
    ``future_task_id`` per memory. A memory measured on one task twice cannot flip and is
    not in the denominator; counting cells instead of distinct tasks would put it there
    and deflate the rate.

    **Both rates use the SAME denominator.** They have to, or the gap between them mixes a
    change of numerator with a change of denominator and stops being interpretable -- and
    section 5 says the gap is the contribution.

    **Naive rate.** Raw sign difference, no floor and no CI: a memory with at least one
    mean dU > 0 and at least one < 0. That is deliberately the weakest possible rule,
    because it is the rule prior work's categorical single-shot reporting amounts to.
    """
    by_mem: dict[Any, list[CellStat]] = defaultdict(list)
    for c in cells:
        by_mem[c.memory_id].append(c)

    eligible: list[Any] = []
    robust_flip: list[Any] = []
    naive_flip: list[Any] = []
    per_memory: dict[Any, dict[str, Any]] = {}
    label_counts: dict[str, int] = defaultdict(int)
    for c in cells:
        label_counts[c.label] += 1

    for mem, group in by_mem.items():
        tasks = {c.task_id for c in group}
        n_tasks = len(tasks)
        has_useful = any(c.label == ROBUST_USEFUL for c in group)
        has_harmful = any(c.label == ROBUST_HARMFUL for c in group)
        # Naive: raw sign difference over the SAME cells, no floor, no CI.
        has_pos = any(c.naive_sign > 0 for c in group)
        has_neg = any(c.naive_sign < 0 for c in group)
        is_eligible = n_tasks >= 2
        r_flip = bool(is_eligible and has_useful and has_harmful)
        n_flip = bool(is_eligible and has_pos and has_neg)
        if is_eligible:
            eligible.append(mem)
            if r_flip:
                robust_flip.append(mem)
            if n_flip:
                naive_flip.append(mem)
        per_memory[mem] = {
            "n_distinct_tasks": n_tasks,
            "n_cells": len(group),
            "eligible": is_eligible,
            "robust_flip": r_flip,
            "naive_flip": n_flip,
            "labels": {c.task_id: c.label for c in group},
            "mean_deltas": {c.task_id: c.mean_delta for c in group},
        }

    n_elig = len(eligible)
    r_rate, r_lo, r_hi = wilson_ci(len(robust_flip), n_elig, alpha=alpha)
    n_rate, n_lo, n_hi = wilson_ci(len(naive_flip), n_elig, alpha=alpha)

    flags: list[str] = []
    if n_elig == 0:
        flags.append("EMPTY_DENOMINATOR:no memory was evaluated on 2+ distinct tasks -- "
                     "the sign-flip rate is undefined, not zero")
    elif n_elig < 10:
        flags.append(f"THIN_DENOMINATOR:{n_elig} memories; a Wilson interval on this "
                     "denominator spans most of [0,1] and should be read as such")
    if label_counts.get(UNDETERMINED, 0):
        flags.append(
            f"UNDETERMINED_CELLS:{label_counts[UNDETERMINED]} cells could not be labelled "
            "(missing floor, or <2 replicates). They can never contribute a robust flip, "
            "so the robust rate here is a LOWER BOUND."
        )
    flags.append(
        "CONSTRUCTED_PAIRING:prereg section 5 -- the memory->task pairing is constructed "
        "by us, so this is a sign-flip rate OVER A DEFINED TASK SET, never an unqualified "
        "natural base rate."
    )

    return FlipReport(
        robust=Estimate(
            r_rate, r_lo, r_hi, n_units=n_elig, n_obs=len(cells),
            method="robust sign-flip rate (prereg section 5)", scale="rate",
            flags=list(flags),
            extra={"numerator": len(robust_flip), "denominator": n_elig,
                   "interval": "Wilson 95%"},
        ),
        naive=Estimate(
            n_rate, n_lo, n_hi, n_units=n_elig, n_obs=len(cells),
            method="naive sign-flip rate (raw sign difference, NO floor, NO CI)",
            scale="rate", flags=list(flags),
            extra={"numerator": len(naive_flip), "denominator": n_elig,
                   "interval": "Wilson 95%",
                   "note": "the honesty comparator required by prereg section 5"},
        ),
        n_memories_total=len(by_mem),
        n_memories_eligible=n_elig,
        robust_flip_memories=sorted(robust_flip, key=str),
        naive_flip_memories=sorted(naive_flip, key=str),
        per_memory=per_memory,
        label_counts=dict(label_counts),
        flags=flags,
    )


# =====================================================================  whole analysis
def label_analysis(
    rows: Iterable[Mapping[str, Any]],
    floor: float | None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    bh_q: float = 0.10,
    allow_pooling: bool = False,
    balanced_primary: bool = True,
) -> dict[str, Any]:
    """Sections 4, 5, 11 and 12 in one call -- what a report or a script asks for.

    Section 12 fixes the primary/secondary split: adaptive replication makes replicate
    count non-random, so the headline rate is computed on the **balanced
    minimum-replicate subset** (primary) with the adaptively-augmented estimate as
    secondary. Both are returned, labelled, with the replicate count per cell available in
    ``cells``.
    """
    rows = list(rows)
    cells_all = cell_statistics(rows, floor, n_boot=n_boot, seed=seed, alpha=alpha,
                               allow_pooling=allow_pooling)
    full = sign_flip_report(cells_all, alpha=alpha)
    bh_cells, bh_counts = apply_bh_correction(cells_all, q=bh_q)
    bh_flips = sign_flip_report(bh_cells, alpha=alpha)

    result: dict[str, Any] = {
        "floor_used": floor,
        "n_rows": len(rows),
        "cells": [c.to_dict() for c in cells_all],
        "replicate_counts": sorted({c.n_replicates for c in cells_all}),
        "secondary_all_replicates": full.to_dict(),
        "bh_corrected": {**bh_flips.to_dict(), "bh_counts": bh_counts, "q": bh_q},
    }

    if balanced_primary:
        subset, n_rep, n_dropped = balanced_replicate_subset(rows)
        if subset:
            cells_bal = cell_statistics(subset, floor, n_boot=n_boot, seed=seed,
                                        alpha=alpha, allow_pooling=allow_pooling)
            bal = sign_flip_report(cells_bal, alpha=alpha)
            bal.flags.append(
                f"BALANCED_SUBSET:{n_rep} replicates per cell, {n_dropped} cells dropped "
                "for having fewer. Prereg section 12 makes this the PRIMARY number."
            )
            result["primary_balanced"] = {
                **bal.to_dict(),
                "n_replicates_per_cell": n_rep,
                "n_cells_dropped": n_dropped,
            }
        else:
            result["primary_balanced"] = {
                "flags": ["NO_BALANCED_SUBSET:no cell had the minimum replicate count"]
            }
    return result


__all__ = [
    "ROBUST_USEFUL", "ROBUST_HARMFUL", "NEUTRAL", "UNDETERMINED",
    "CellStat", "FlipReport", "cell_statistics", "apply_bh_correction",
    "sign_flip_report", "label_analysis", "additive_null_flip_rate",
]


# ==============================================  ADDITIVE NULL (supplementary, NOT prereg)
# 🔴 NOT in docs/ANALYSIS_PREREGISTRATION.md. Added by D and reported as supplementary,
# because a synthetic control exposed a gap between what section 5 measures and what
# section 5 is *read* as meaning. Flagged everywhere it appears; it never replaces the
# pre-registered rate.
#
# THE GAP. Section 5's flip is a property of dU's SIGN. Section 6's interaction is a
# property of dU's VARIANCE. They are different quantities, and a sign flip does not
# require an interaction:
#
#     dU(m,t) = mu + a_m + b_t          (interaction identically ZERO)
#
# still flips sign whenever b_t crosses -(mu + a_m) between two tasks. On synthetic data
# with sd_interaction = 0 and the main effects left intact, the TRUE flip rate is 0.60 and
# the robust estimator recovers 0.285 of it. Those are real sign changes in dU, correctly
# detected -- but they are a TASK effect, identical for every memory, and reading them as
# "this memory is useful here and harmful there" implies a memory-specific conditionality
# the data does not contain.
#
# So "the memory x task structure is real" needs a null that removes ONLY the
# interaction. Permuting memory labels is the obvious move and is WRONG here: it destroys
# the memory main effect at the same time, so it breaks more than the claim asserts and
# would make any main effect look like interaction.
#
# What is done instead: fit the additive model by least squares, then regenerate each
# cell's replicates from its ADDITIVE fit plus residuals resampled from the pooled
# within-cell residuals. Memory main effect, task main effect, replicate counts, the
# cell structure and the noise distribution all survive; only (ab)_mt is removed.


def additive_null_flip_rate(
    rows: Iterable[Mapping[str, Any]],
    floor: float | None,
    *,
    n_null: int = 200,
    n_boot: int = 300,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    delta_field: str = "delta_utility",
) -> dict[str, Any]:
    """Flip rate expected from main effects alone. SUPPLEMENTARY -- not pre-registered.

    Returns the observed robust rate, the null distribution of that rate under an
    additive (interaction-free) model matched on everything else, and a one-sided
    permutation-style p-value.

    A p-value near 1 means the observed flips are fully explained by memory and task main
    effects -- which is exactly the reading the kill criterion (EXPERIMENT_PLAN section 6)
    calls for, and is a result, not a failure.
    """
    import numpy as np

    adm = admit_rows(rows)
    data = adm.rows
    if not data:
        return {"observed": None, "flags": ["NO_ADMITTED_ROWS"]}

    cells = cell_statistics(data, floor, n_boot=n_boot, seed=seed, alpha=alpha)
    observed = sign_flip_report(cells, alpha=alpha)

    by_cell = group_by(data, "cell_id")
    mems = sorted({r.get("memory_id") for r in data}, key=str)
    tasks = sorted({r.get("future_task_id") for r in data}, key=str)
    mi = {m: i for i, m in enumerate(mems)}
    ti = {t: i for i, t in enumerate(tasks)}

    # Cell means and the pooled within-cell residuals (the noise to resample).
    cell_meta: list[tuple[Any, int, int, float, int]] = []
    residuals: list[float] = []
    for cell, group in by_cell.items():
        ds_ = [float(r[delta_field]) for r in group if r.get(delta_field) is not None]
        if not ds_:
            continue
        arr = np.asarray(ds_)
        m = float(arr.mean())
        cell_meta.append((cell, mi[group[0].get("memory_id")],
                          ti[group[0].get("future_task_id")], m, arr.size))
        if arr.size > 1:
            residuals.extend((arr - m).tolist())
    if not cell_meta:
        return {"observed": observed.to_dict(), "flags": ["NO_CELLS"]}
    if len(residuals) < 2:
        return {"observed": observed.to_dict(),
                "flags": ["NO_RESIDUALS:no cell has 2+ replicates; an additive null "
                          "cannot be simulated without a noise distribution"]}

    # Least-squares additive fit on the cell means: y ~ mu + a_m + b_t.
    n_c = len(cell_meta)
    X = np.zeros((n_c, 1 + len(mems) + len(tasks)))
    y = np.zeros(n_c)
    for i, (_c, m_i, t_i, mean, _n) in enumerate(cell_meta):
        X[i, 0] = 1.0
        X[i, 1 + m_i] = 1.0
        X[i, 1 + len(mems) + t_i] = 1.0
        y[i] = mean
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta

    resid_arr = np.asarray(residuals, dtype=float)
    rng = np.random.default_rng(seed)
    null_rates: list[float] = []
    for _ in range(n_null):
        synth_cells: list[CellStat] = []
        for i, (cell, _m_i, _t_i, _mean, n_rep) in enumerate(cell_meta):
            draws = fitted[i] + rng.choice(resid_arr, size=n_rep, replace=True)
            mean, lo, hi, p = bootstrap_mean_ci(draws.tolist(), n_boot=n_boot,
                                                seed=int(rng.integers(1, 2 ** 31)),
                                                alpha=alpha)
            head = by_cell[cell][0]
            synth_cells.append(CellStat(
                cell_id=cell, memory_id=head.get("memory_id"),
                task_id=head.get("future_task_id"), benchmark=head.get("benchmark"),
                representation=head.get("memory_representation"),
                mean_delta=mean, ci_lower=lo, ci_upper=hi, n_replicates=n_rep,
                p_value=p, label=derive_utility_label(lo, hi, mean, floor),
                naive_sign=0 if mean is None else (1 if mean > 0 else (-1 if mean < 0 else 0)),
            ))
        r = sign_flip_report(synth_cells, alpha=alpha)
        if r.robust.point is not None:
            null_rates.append(r.robust.point)

    obs = observed.robust.point
    arr = np.asarray(null_rates, dtype=float)
    p_val = None
    if obs is not None and arr.size:
        p_val = float(((arr >= obs).sum() + 1) / (arr.size + 1))
    return {
        "observed": observed.to_dict(),
        "observed_robust_rate": obs,
        "null_mean": float(arr.mean()) if arr.size else None,
        "null_q025": float(np.quantile(arr, 0.025)) if arr.size else None,
        "null_q975": float(np.quantile(arr, 0.975)) if arr.size else None,
        "n_null_draws": int(arr.size),
        "p_value_one_sided": p_val,
        "flags": [
            "NOT_PREREGISTERED:supplementary diagnostic added by D. The pre-registered "
            "headline remains the section-5 rate; this only asks whether that rate "
            "exceeds what memory and task MAIN EFFECTS alone would produce.",
            "NULL_IS_MATCHED:memory main effect, task main effect, replicate counts and "
            "the residual distribution are all preserved; only (ab)_mt is removed.",
        ],
    }

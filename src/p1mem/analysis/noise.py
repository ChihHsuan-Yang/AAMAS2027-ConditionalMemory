"""D1 -- the three noise floors of ANALYSIS_PREREGISTRATION section 2.

    | F_exec  | outcome variation across seeds with everything else fixed
    |         |   -> repeated identical cells, per arm
    | F_empty | variation of the no-memory arm
    |         |   -> FREE: the WITHOUT arm is identical across every memory condition for
    |         |      a given task, so its spread across memories IS a floor
    | F_judge | scorer disagreement on BYTE-IDENTICAL outputs
    |         |   -> re-score stored outputs without regenerating

    Reference floor F = F_exec, per benchmark, pooled across tasks, with a bootstrap CI.

Nothing downstream is interpretable without these (EXPERIMENT_PLAN section 3), so three
failure modes are guarded explicitly rather than left to the caller:

1. **A floor of 0.0 that was never measured.** If no cell has two replicates, or no two
   outputs are byte-identical, the estimator returns ``point=None`` with a flag, never
   0.0. A floor of zero is cleared by every effect, so an unmeasured floor silently
   reported as zero would validate the whole paper's headline. The project's own record
   carries the counterexample: a 9.35% judge flip rate at temperature 0 that a "judges are
   deterministic" assumption would have set to zero.
2. **A free floor that is free because it is fake.** F_empty is free only when the WITHOUT
   arm was *independently executed* per cell. If the harness cached one WITHOUT generation
   and copied it into every memory's row, the spread across memories is identically zero
   by construction and measures nothing. ``empty_floor`` detects that from byte-identical
   ``output_without_memory`` and refuses to count the group.
3. **Two floors in different units.** ``F_exec`` on the WITH arm and ``F_exec`` on dU are
   different numbers (``var(dU) = var_with + var_without - 2 cov``), and section 4 compares
   ``|mean dU|`` against F. Every estimate here carries the scale it was measured on in
   ``Estimate.scale``; ``reference_floor`` computes both and states which one it returned.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .common import (
    DEFAULT_ALPHA,
    DEFAULT_N_BOOT,
    DEFAULT_SEED,
    Estimate,
    admit_rows,
    cluster_bootstrap,
    group_by,
    pooled_variance,
    require_homogeneous,
)

#: Which arm / contrast a floor was measured on. Section 4 compares |mean dU| to F, so
#: "delta" is the scale that clause needs; the per-arm scales are what section 2 names.
SCALES = ("delta", "with", "without")

_ARM_FIELD = {
    "delta": "delta_utility",
    "with": "reward_with_memory",
    "without": "reward_without_memory",
}


def _sd_from_groups(groups: Sequence[Sequence[float]]) -> tuple[float | None, int, int]:
    var, df, used = pooled_variance(groups)
    if var is None:
        return None, df, used
    return math.sqrt(max(var, 0.0)), df, used


def _memory_of(row: Mapping[str, Any]) -> Any:
    return row.get("memory_id")


# ============================================================================  F_exec
def exec_floor(
    rows: Iterable[Mapping[str, Any]],
    *,
    scale: str = "delta",
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    allow_pooling: bool = False,
    bootstrap_unit: str = "memory_id",
) -> Estimate:
    """F_exec: pooled within-cell SD across replicates. Prereg section 2, row 1.

    A "repeated identical cell" is a ``cell_id`` with 2+ replicates -- replicates differ
    only in sampling (``schema.py``: "Replicates differ ONLY in sampling"), so their spread
    is execution noise by construction.

    The statistic is the SD of a SINGLE observation, not of the cell mean. Section 4
    compares ``mean dU`` against F, and dividing by sqrt(n) would make F shrink as
    replicates are added -- which, under adaptive replication (section 12), means the floor
    would fall fastest exactly on the cells chosen for being near zero. That is the
    circularity section 12 exists to prevent, so the conservative reading is used.
    """
    if scale not in SCALES:
        raise ValueError(f"scale must be one of {SCALES}, got {scale!r}")
    adm = admit_rows(rows)
    data = adm.rows
    flags = require_homogeneous(data, allow_pooling=allow_pooling)
    if not data:
        return Estimate(None, method="F_exec", scale=scale,
                        flags=flags + ["NO_ADMITTED_ROWS"],
                        extra={"admission": adm.to_dict()})

    field = _ARM_FIELD[scale]
    by_cell = group_by(data, "cell_id")
    # Unit of generalization for the CI. Prereg section 6 names the memory; a cell-level
    # bootstrap would treat the many cells of one memory as independent.
    unit_of: dict[Any, Any] = {}
    cells_by_unit: dict[Any, list[Any]] = defaultdict(list)
    for cell, group in by_cell.items():
        u = group[0].get(bootstrap_unit)
        unit_of[cell] = u
        cells_by_unit[u].append(cell)

    def stat(units: Sequence[Any]) -> float | None:
        groups = []
        for u in units:
            for cell in cells_by_unit[u]:
                groups.append([r.get(field) for r in by_cell[cell]
                               if r.get(field) is not None])
        sd, _df, _used = _sd_from_groups(groups)
        return sd

    all_units = list(cells_by_unit.keys())
    point, lo, hi, n_draws = cluster_bootstrap(
        all_units, stat, n_boot=n_boot, seed=seed, alpha=alpha
    )

    repeated = [c for c, g in by_cell.items() if len(g) >= 2]
    _sd, df, used_cells = _sd_from_groups(
        [[r.get(field) for r in by_cell[c]] for c in by_cell]
    )
    if point is None:
        flags.append("NOT_MEASURED:no cell has 2+ replicates -- F_exec is UNMEASURED, "
                     "which is not the same as zero")
    if used_cells and used_cells < 5:
        flags.append(f"THIN:only {used_cells} repeated cells contribute")
    if n_draws < n_boot:
        flags.append(f"BOOTSTRAP_DEGENERATE_DRAWS:{n_boot - n_draws}")

    return Estimate(
        point=point, ci_lower=lo, ci_upper=hi,
        n_units=len(all_units), n_obs=len(data),
        method="F_exec", scale=scale, flags=flags,
        extra={
            "n_cells": len(by_cell),
            "n_cells_with_replicates": len(repeated),
            "n_cells_contributing": used_cells,
            "df": df,
            "bootstrap_unit": bootstrap_unit,
            "admission": adm.to_dict(),
            "definition": "pooled within-cell SD of a single observation across replicates",
        },
    )


# ===========================================================================  F_empty
#: A group whose WITHOUT outputs are byte-identical was not independently executed.
EMPTY_ARM_REUSED = "WITHOUT_ARM_REUSED"


def empty_floor(
    rows: Iterable[Mapping[str, Any]],
    *,
    across: str = "memory",
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    allow_pooling: bool = False,
    require_independent_execution: bool = True,
) -> Estimate:
    """F_empty: spread of the no-memory arm. Prereg section 2, row 2 -- the FREE floor.

    The WITHOUT arm is, by the design in ``docs/MEMORY_PROTOCOL.md`` section 4, the same
    condition for every memory evaluated on a given task: the target memory is absent and
    the surrounding filler is fixed and identical. So all the WITHOUT observations sharing
    a ``(benchmark, future_task_id, replicate_id)`` are repeated identical executions, and
    their spread is a floor that costs nothing extra to obtain.

    ``across``:
      * ``"memory"`` (default, and what section 2 says) -- group by
        ``(benchmark, future_task_id, replicate_id)`` so only the memory varies inside a
        group.
      * ``"memory_and_replicate"`` -- drop ``replicate_id`` from the key, pooling seed
        variation in as well. A larger number measuring a different thing; offered because
        it is the natural question to ask next, never as the default.

    **The free floor's failure mode, guarded here.** Free is only free if the WITHOUT arm
    was really re-run. A harness that generates the no-memory answer once per task and
    copies it into every row produces a spread of exactly 0.0 -- an apparent perfect floor
    that every effect then clears. With ``require_independent_execution=True`` any group
    whose ``output_without_memory`` values are all byte-identical is excluded and counted,
    and if that removes every group the estimate is ``None`` with a flag, not zero.
    """
    if across not in ("memory", "memory_and_replicate"):
        raise ValueError(f"unknown across={across!r}")
    adm = admit_rows(rows)
    data = adm.rows
    flags = require_homogeneous(data, allow_pooling=allow_pooling)
    if not data:
        return Estimate(None, method="F_empty", scale="without",
                        flags=flags + ["NO_ADMITTED_ROWS"],
                        extra={"admission": adm.to_dict()})

    key = ("benchmark", "future_task_id", "replicate_id")
    if across == "memory_and_replicate":
        key = ("benchmark", "future_task_id")
    by_group = group_by(data, key)

    reused: list[Any] = []
    usable: dict[Any, list[dict[str, Any]]] = {}
    for gkey, group in by_group.items():
        if len(group) < 2:
            continue
        outs = {r.get("output_without_memory") for r in group}
        n_distinct_mem = len({_memory_of(r) for r in group})
        if require_independent_execution and len(outs) == 1 and n_distinct_mem > 1:
            reused.append(gkey)
            continue
        usable[gkey] = group

    units = sorted({_memory_of(r) for r in data}, key=lambda x: (x is None, str(x)))

    def stat(sample_units: Sequence[Any]) -> float | None:
        keep = set(sample_units)
        # Multiplicity matters in a bootstrap: a unit drawn twice must count twice.
        mult: dict[Any, int] = defaultdict(int)
        for u in sample_units:
            mult[u] += 1
        groups = []
        for _gkey, group in usable.items():
            vals: list[float] = []
            for r in group:
                u = _memory_of(r)
                if u not in keep:
                    continue
                v = r.get("reward_without_memory")
                if v is None:
                    continue
                vals.extend([float(v)] * mult[u])
            if len(vals) >= 2:
                groups.append(vals)
        sd, _df, _used = _sd_from_groups(groups)
        return sd

    point, lo, hi, n_draws = cluster_bootstrap(
        units, stat, n_boot=n_boot, seed=seed, alpha=alpha
    )

    _sd, df, used_groups = _sd_from_groups(
        [[r.get("reward_without_memory") for r in g] for g in usable.values()]
    )
    if point is None:
        if reused:
            flags.append(
                f"{EMPTY_ARM_REUSED}:{len(reused)} group(s) had byte-identical WITHOUT "
                "outputs across memories -- the arm was cached, not re-executed, so its "
                "spread is 0 by construction and measures nothing. F_empty is UNMEASURED."
            )
        else:
            flags.append("NOT_MEASURED:no task/replicate group has 2+ memories")
    elif reused:
        flags.append(f"{EMPTY_ARM_REUSED}:{len(reused)} group(s) excluded as cached")
    if used_groups and used_groups < 5:
        flags.append(f"THIN:only {used_groups} groups contribute")

    return Estimate(
        point=point, ci_lower=lo, ci_upper=hi,
        n_units=len(units), n_obs=len(data),
        method="F_empty", scale="without", flags=flags,
        extra={
            "across": across,
            "group_key": list(key),
            "n_groups": len(by_group),
            "n_groups_contributing": used_groups,
            "n_groups_excluded_as_reused": len(reused),
            "df": df,
            "admission": adm.to_dict(),
            "definition": "pooled SD of reward_without_memory across memories within "
                          "a (benchmark, task, replicate) group",
        },
    )


# ===========================================================================  F_judge
def judge_floor(
    rows: Iterable[Mapping[str, Any]],
    rescored: Mapping[Any, Mapping[str, float]] | None = None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
) -> Estimate:
    """F_judge: scorer disagreement on BYTE-IDENTICAL outputs. Prereg section 2, row 3.

    Two sources, both supported, neither assumed:

    * ``rescored`` -- an explicit re-scoring pass, ``row_id -> {"reward_with_memory": x,
      "reward_without_memory": y}``. This is the section 2 estimator: re-score stored
      outputs without regenerating. Disagreement is measured per (row, arm).
    * ``rescored=None`` -- the free variant: find outputs that are byte-identical *within
      the dataset* under the same ``(verifier_id, verifier_version)`` and check whether
      they received the same reward. Identical bytes through the same verifier version
      must give the same score; any difference is verifier nondeterminism.

    Reported point estimate is the **disagreement rate** -- the fraction of byte-identical
    comparisons whose rewards differ -- because that is the quantity the 9.35% prior figure
    is on. The magnitude scale (mean absolute reward difference, and its SD) is in
    ``extra``; the magnitude is what section 4's floor clause would need if F_judge were
    ever used as the reference floor, and the two are not interchangeable.

    ⚠️ Returns ``point=None`` with ``NOT_MEASURED`` when nothing byte-identical exists.
    Prereg: "Do not assume F_judge = 0 without measuring it."
    """
    adm = admit_rows(rows)
    data = adm.rows
    flags: list[str] = []
    if not data:
        return Estimate(None, method="F_judge", scale="rate",
                        flags=["NO_ADMITTED_ROWS"], extra={"admission": adm.to_dict()})

    # (output_text, verifier_id, verifier_version) -> list of (memory_id, reward)
    obs: dict[tuple[Any, Any, Any], list[tuple[Any, float]]] = defaultdict(list)
    if rescored is not None:
        for r in data:
            rid = r.get("row_id")
            if rid not in rescored:
                continue
            new = rescored[rid]
            for arm, field in (("with", "reward_with_memory"),
                               ("without", "reward_without_memory")):
                old_v = r.get(field)
                new_v = new.get(field)
                if old_v is None or new_v is None:
                    continue
                text = r.get(f"output_{arm}_memory")
                k = (text, r.get("verifier_id"), r.get("verifier_version"))
                obs[k].append((_memory_of(r), float(old_v)))
                obs[k].append((_memory_of(r), float(new_v)))
        source = "explicit_rescore"
    else:
        for r in data:
            for arm, field in (("with", "reward_with_memory"),
                               ("without", "reward_without_memory")):
                v = r.get(field)
                text = r.get(f"output_{arm}_memory")
                if v is None or text is None:
                    continue
                k = (text, r.get("verifier_id"), r.get("verifier_version"))
                obs[k].append((_memory_of(r), float(v)))
        source = "within_dataset_duplicates"

    dup = {k: v for k, v in obs.items() if len(v) >= 2}
    if not dup:
        return Estimate(
            None, method="F_judge", scale="rate",
            n_obs=len(data),
            flags=["NOT_MEASURED:no byte-identical output was scored twice. "
                   "F_judge is UNMEASURED -- NOT zero. Prereg section 2 forbids "
                   "assuming a deterministic scorer without measuring it."],
            extra={"source": source, "n_duplicate_groups": 0,
                   "admission": adm.to_dict()},
        )

    # Comparisons are within a group, against the group's first observation, so a group of
    # n contributes n-1 comparisons rather than n choose 2 (which would let one large group
    # dominate quadratically).
    comparisons: list[tuple[Any, int, float]] = []  # (memory_id, disagree, abs_diff)
    for _k, vals in dup.items():
        ref_mem, ref = vals[0]
        for mem, v in vals[1:]:
            comparisons.append((mem, int(v != ref), abs(v - ref)))

    units = sorted({c[0] for c in comparisons}, key=lambda x: (x is None, str(x)))
    by_unit: dict[Any, list[tuple[int, float]]] = defaultdict(list)
    for mem, dis, mag in comparisons:
        by_unit[mem].append((dis, mag))

    def stat(sample_units: Sequence[Any]) -> float | None:
        n = 0
        k = 0
        for u in sample_units:
            for dis, _mag in by_unit[u]:
                n += 1
                k += dis
        return (k / n) if n else None

    point, lo, hi, _n = cluster_bootstrap(units, stat, n_boot=n_boot, seed=seed, alpha=alpha)

    mags = np.asarray([c[2] for c in comparisons], dtype=float)
    n_dis = int(sum(c[1] for c in comparisons))
    if point is not None and point > 0:
        flags.append(
            f"NONZERO_JUDGE_FLOOR:{n_dis}/{len(comparisons)} byte-identical comparisons "
            "disagreed -- the scorer is not deterministic on this data"
        )
    return Estimate(
        point=point, ci_lower=lo, ci_upper=hi,
        n_units=len(units), n_obs=len(comparisons),
        method="F_judge", scale="rate", flags=flags,
        extra={
            "source": source,
            "n_duplicate_groups": len(dup),
            "n_comparisons": len(comparisons),
            "n_disagreements": n_dis,
            "mean_abs_reward_difference": float(mags.mean()) if mags.size else None,
            "max_abs_reward_difference": float(mags.max()) if mags.size else None,
            "sd_of_differences": float(mags.std(ddof=1)) if mags.size > 1 else None,
            "admission": adm.to_dict(),
        },
    )


# ==================================================================  reference floor
def reference_floor(
    rows: Iterable[Mapping[str, Any]],
    *,
    per_benchmark: bool = True,
    scale: str = "delta",
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    allow_pooling: bool = False,
) -> dict[Any, Estimate]:
    """The reference floor F, per benchmark: ``F = F_exec``, pooled across tasks.

    Prereg section 2: "Reference floor F = F_exec estimated per benchmark, pooled across
    tasks, reported with a bootstrap CI."

    ⚠️ **One pre-registration ambiguity, resolved here in the open.** Section 2 defines
    F_exec "per arm", but section 4 compares it to ``mean dU``, which is a contrast of two
    arms. The two are numerically different. This function returns the dU-scale floor by
    default, because that is the only scale on which section 4's inequality is
    dimensionally meaningful, and it puts the per-arm floors in ``extra["per_arm"]`` so
    the section-2 reading is always visible alongside. Pass ``scale="with"`` for the
    literal per-arm number.
    """
    adm = admit_rows(rows)
    data = adm.rows
    out: dict[Any, Estimate] = {}
    groups = group_by(data, "benchmark") if per_benchmark else {"__all__": data}
    for bench, group in groups.items():
        est = exec_floor(group, scale=scale, n_boot=n_boot, seed=seed,
                         allow_pooling=allow_pooling)
        est.method = f"F (reference) = F_exec[{scale}]"
        per_arm = {}
        for s in ("with", "without"):
            e = exec_floor(group, scale=s, n_boot=n_boot, seed=seed,
                           allow_pooling=allow_pooling)
            per_arm[s] = e.to_dict()
        est.extra["per_arm"] = per_arm
        est.extra["benchmark"] = bench
        est.flags.append(
            "SCALE_NOTE:prereg section 2 names F_exec 'per arm'; section 4 compares it to "
            f"mean dU. Returned on the '{scale}' scale; per-arm values in extra.per_arm."
        )
        out[bench] = est
    return out


def all_floors(
    rows: Iterable[Mapping[str, Any]],
    *,
    rescored: Mapping[Any, Mapping[str, float]] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    allow_pooling: bool = False,
) -> dict[str, Any]:
    """All three floors plus the reference floor, in one dict, for the report."""
    rows = list(rows)
    return {
        "F_exec_delta": exec_floor(rows, scale="delta", n_boot=n_boot, seed=seed,
                                   allow_pooling=allow_pooling).to_dict(),
        "F_exec_with": exec_floor(rows, scale="with", n_boot=n_boot, seed=seed,
                                  allow_pooling=allow_pooling).to_dict(),
        "F_exec_without": exec_floor(rows, scale="without", n_boot=n_boot, seed=seed,
                                     allow_pooling=allow_pooling).to_dict(),
        "F_empty": empty_floor(rows, n_boot=n_boot, seed=seed,
                               allow_pooling=allow_pooling).to_dict(),
        "F_judge": judge_floor(rows, rescored, n_boot=n_boot, seed=seed).to_dict(),
        "reference": {
            str(k): v.to_dict()
            for k, v in reference_floor(rows, n_boot=n_boot, seed=seed,
                                        allow_pooling=allow_pooling).items()
        },
    }


__all__ = [
    "SCALES", "EMPTY_ARM_REUSED",
    "exec_floor", "empty_floor", "judge_floor", "reference_floor", "all_floors",
]

"""D3 -- variance decomposition. ANALYSIS_PREREGISTRATION section 6.

    dU(m,t,s) = mu + a_m + b_t + (ab)_mt + eps_s

    random effects for memory, task, and their interaction. Report each component's
    SHARE OF TOTAL VARIANCE, with F_exec as an explicit comparator, and bootstrap CIs
    over memories (the unit of generalization).

    Fallback if the model does not converge (fixed now, not later): a two-way
    variance-components estimate by method of moments on the balanced sub-design,
    reported as such. Non-convergence is disclosed, never silently swapped.

**statsmodels is not installed in this environment**, and `statsmodels.MixedLM` cannot fit
crossed random effects without the `vc_formula` contortion anyway. The primary estimator
is therefore implemented directly: REML for a crossed two-way random-effects model, by
derivative-free maximization of the profiled restricted log-likelihood over the three
variance ratios. The likelihood is the standard one:

    y = X mu + Z_m a + Z_t b + Z_mt (ab) + eps,
    V = sigma^2 (Z_m Z_m' r_m + Z_t Z_t' r_t + Z_mt Z_mt' r_mt + I),   r = sigma_*^2/sigma^2

    -2 logL_REML = log|V| + log|X' V^-1 X| + (n - p) log(y' P y / (n - p)) + const

profiled over sigma^2. Optimization is ``scipy.optimize.minimize(method="Nelder-Mead")``
on log-ratios, which keeps every variance non-negative by construction. Non-convergence
is a real possibility and is exactly what the pre-registered fallback is for -- it is
detected and reported, never patched over.

⚠️ **A boundary solution is not convergence.** A variance ratio driven to ~0 is the
likelihood saying "this component is not identified from this design", and reporting a
share of 0.000 with a tight CI would read as a measurement. Any component within
``BOUNDARY_TOL`` of zero is flagged ``AT_BOUNDARY``.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .common import (
    DEFAULT_ALPHA,
    DEFAULT_SEED,
    Estimate,
    admit_rows,
    group_by,
    percentile_ci,
    require_homogeneous,
)

COMPONENTS = ("memory", "task", "interaction", "residual")
BOUNDARY_TOL = 1e-6
#: Log-ratio floor: exp(-18) ~ 1.5e-8, i.e. "this component is zero" without -inf.
_LOG_FLOOR = -18.0


@dataclass
class Decomposition:
    """Variance components, their shares, and everything needed to distrust them."""

    components: dict[str, float]
    shares: dict[str, float]
    share_ci: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    component_ci: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    method: str = ""
    converged: bool = False
    used_fallback: bool = False
    n_memories: int = 0
    n_tasks: int = 0
    n_cells: int = 0
    n_obs: int = 0
    exec_floor_variance: float | None = None
    flags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_variance(self) -> float:
        return float(sum(self.components.values()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "converged": self.converged,
            "used_fallback": self.used_fallback,
            "components": dict(self.components),
            "shares": dict(self.shares),
            "share_ci": {k: list(v) for k, v in self.share_ci.items()},
            "component_ci": {k: list(v) for k, v in self.component_ci.items()},
            "total_variance": self.total_variance,
            "exec_floor_variance_comparator": self.exec_floor_variance,
            "interaction_share_vs_exec_floor": (
                None if self.exec_floor_variance is None or self.total_variance <= 0
                else self.components.get("interaction", 0.0) / self.exec_floor_variance
            ),
            "n_memories": self.n_memories,
            "n_tasks": self.n_tasks,
            "n_cells": self.n_cells,
            "n_obs": self.n_obs,
            "flags": list(self.flags),
            "extra": dict(self.extra),
        }

    def __str__(self) -> str:  # pragma: no cover - display only
        lines = [f"{self.method} (converged={self.converged}, "
                 f"fallback={self.used_fallback})"]
        for c in COMPONENTS:
            ci = self.share_ci.get(c)
            cis = ("" if not ci or ci[0] is None
                   else f"  share CI [{ci[0]:.3f}, {ci[1]:.3f}]")
            # A component the fit never produced prints UNMEASURED, never 0.0000.
            # `.get(c, 0.0)` here reported "variance shares all 0.0000" for a fit
            # that had FAILED (shares={}), which reads as the strongest possible
            # null on this project's headline quantity. See
            # docs/OFFICIAL_PROMPT_ARM.md section 4 and RESULTS_LEDGER row 54a.
            if c not in self.shares:
                lines.append(f"  {c:<12} var=UNMEASURED  share=UNMEASURED{cis}")
                continue
            lines.append(f"  {c:<12} var={self.components.get(c, float('nan')):.6f}  "
                         f"share={self.shares[c]:.4f}{cis}")
        for f in self.flags:
            lines.append(f"  ! {f}")
        return "\n".join(lines)


# ==========================================================================  design
@dataclass
class _Design:
    y: np.ndarray
    mem_idx: np.ndarray
    task_idx: np.ndarray
    cell_idx: np.ndarray
    n_mem: int
    n_task: int
    n_cell: int
    memories: list[Any]
    tasks: list[Any]
    cell_ids: list[Any]
    cell_memory: np.ndarray


def _build_design(
    rows: Sequence[Mapping[str, Any]], delta_field: str
) -> _Design:
    mems = sorted({r.get("memory_id") for r in rows}, key=str)
    tasks = sorted({r.get("future_task_id") for r in rows}, key=str)
    cells = sorted({r.get("cell_id") for r in rows}, key=str)
    mi = {m: i for i, m in enumerate(mems)}
    ti = {t: i for i, t in enumerate(tasks)}
    ci = {c: i for i, c in enumerate(cells)}
    y = np.asarray([float(r[delta_field]) for r in rows], dtype=float)
    m_idx = np.asarray([mi[r.get("memory_id")] for r in rows], dtype=int)
    t_idx = np.asarray([ti[r.get("future_task_id")] for r in rows], dtype=int)
    c_idx = np.asarray([ci[r.get("cell_id")] for r in rows], dtype=int)
    cell_mem = np.zeros(len(cells), dtype=int)
    for r in rows:
        cell_mem[ci[r.get("cell_id")]] = mi[r.get("memory_id")]
    return _Design(y, m_idx, t_idx, c_idx, len(mems), len(tasks), len(cells),
                   mems, tasks, cells, cell_mem)


def _indicator(idx: np.ndarray, n_levels: int) -> np.ndarray:
    Z = np.zeros((idx.size, n_levels))
    Z[np.arange(idx.size), idx] = 1.0
    return Z


# ==============================================================  REML (primary)
def _cell_reduce(d: _Design) -> tuple[np.ndarray, np.ndarray, float, int, int]:
    """Reduce to sufficient statistics: cell means, cell sizes, and within-cell SS.

    mu, a_m, b_t and (ab)_mt are all CONSTANT within a cell, so the within-cell contrasts
    are orthogonal to every fixed and random effect except eps. The restricted likelihood
    therefore factorizes into (i) a within-cell piece that depends only on sigma^2 and
    (ii) a model on the C cell means. This is an exact reduction, not an approximation,
    and it turns an n x n determinant into a C x C one -- which is what makes the
    bootstrap over memories affordable.
    """
    C = d.n_cell
    sums = np.zeros(C)
    counts = np.zeros(C)
    sqs = np.zeros(C)
    np.add.at(sums, d.cell_idx, d.y)
    np.add.at(counts, d.cell_idx, 1.0)
    np.add.at(sqs, d.cell_idx, d.y ** 2)
    means = sums / counts
    ssw = float((sqs - counts * means ** 2).sum())
    return means, counts, ssw, int(d.y.size), C


def _cell_level_matrices(d: _Design) -> tuple[np.ndarray, np.ndarray]:
    """Cell -> memory and cell -> task indicator columns, stacked as U (C x (a+b))."""
    C = d.n_cell
    cell_task = np.zeros(C, dtype=int)
    for k in range(d.y.size):
        cell_task[d.cell_idx[k]] = d.task_idx[k]
    U = np.zeros((C, d.n_mem + d.n_task))
    U[np.arange(C), d.cell_memory] = 1.0
    U[np.arange(C), d.n_mem + cell_task] = 1.0
    return U, cell_task


def _profiled_neg2_reml(
    log_ratios: np.ndarray,
    means: np.ndarray,
    counts: np.ndarray,
    ssw: float,
    n_obs: int,
    U: np.ndarray,
    n_mem: int,
    n_task: int,
) -> float:
    """-2 x profiled restricted log-likelihood over the three variance RATIOS.

    Scaling every variance by sigma^2 makes W = sigma^2 Wt with
    ``Wt = r_m Z_m Z_m' + r_t Z_t Z_t' + diag(r_ab + 1/n_i)``, and sigma^2 profiles out in
    closed form as ``(SSW + qt) / (n - 1)``. Wt is inverted by Woodbury against
    ``U = [Z_m, Z_t]`` of width (a+b), in the form that stays finite as a ratio goes to
    zero -- a component being driven to the boundary is an expected outcome here, not an
    error, so the likelihood must remain evaluable there.
    """
    r = np.exp(np.clip(log_ratios, _LOG_FLOOR, 12.0))
    r_m, r_t, r_ab = float(r[0]), float(r[1]), float(r[2])
    C = means.size
    dvec = r_ab + 1.0 / counts                      # diagonal of Wt
    if not np.all(np.isfinite(dvec)) or np.any(dvec <= 0):
        return 1e12
    Dinv = 1.0 / dvec
    g = np.concatenate([np.full(n_mem, r_m), np.full(n_task, r_t)])

    DiU = U * Dinv[:, None]                          # C x k
    A = U.T @ DiU                                    # k x k  = U' D^-1 U
    k = A.shape[0]
    M = np.eye(k) + (g[:, None] * A)                 # I + G A
    try:
        sign, logdetM = np.linalg.slogdet(M)
        if sign <= 0:
            return 1e12
        Minv = np.linalg.inv(M)
    except np.linalg.LinAlgError:
        return 1e12
    N1 = Minv * g[None, :]                           # (I + G A)^-1 G

    def winv(v: np.ndarray) -> np.ndarray:
        t = DiU.T @ v
        return Dinv * v - DiU @ (N1 @ t)

    one = np.ones(C)
    Wi1 = winv(one)
    Wiy = winv(means)
    denom = float(one @ Wi1)
    if denom <= 0 or not np.isfinite(denom):
        return 1e12
    mu = float(one @ Wiy) / denom
    resid = means - mu
    qt = float(resid @ winv(resid))
    logdetW = float(np.log(dvec).sum()) + logdetM
    rss = ssw + qt
    if rss <= 0 or not np.isfinite(rss) or not np.isfinite(logdetW):
        return 1e12
    return (n_obs - 1) * math.log(rss / (n_obs - 1)) + logdetW + math.log(denom)


def _reml_sigma2(
    log_ratios: np.ndarray,
    means: np.ndarray,
    counts: np.ndarray,
    ssw: float,
    n_obs: int,
    U: np.ndarray,
    n_mem: int,
    n_task: int,
) -> tuple[float, float]:
    """(sigma^2, mu) at the given ratios -- the pieces profiled out of the likelihood."""
    r = np.exp(np.clip(log_ratios, _LOG_FLOOR, 12.0))
    r_m, r_t, r_ab = float(r[0]), float(r[1]), float(r[2])
    C = means.size
    dvec = r_ab + 1.0 / counts
    Dinv = 1.0 / dvec
    g = np.concatenate([np.full(n_mem, r_m), np.full(n_task, r_t)])
    DiU = U * Dinv[:, None]
    A = U.T @ DiU
    M = np.eye(A.shape[0]) + (g[:, None] * A)
    N1 = np.linalg.inv(M) * g[None, :]

    def winv(v):
        return Dinv * v - DiU @ (N1 @ (DiU.T @ v))

    one = np.ones(C)
    mu = float(one @ winv(means)) / float(one @ winv(one))
    resid = means - mu
    qt = float(resid @ winv(resid))
    return (ssw + qt) / (n_obs - 1), mu


def _fit_reml(
    d: _Design, *, maxiter: int = 3000, seed: int = DEFAULT_SEED, n_random_starts: int = 4
) -> tuple[dict[str, float], bool, dict[str, Any]]:
    """REML fit of the crossed two-way random-effects model.

    Multiple starts, because the profiled surface for crossed effects has flat regions
    and a single start can stop on one and report success. Convergence requires at least
    two starts to reach the same optimum, so "converged" means reproducible, not just
    "the optimizer returned".
    """
    from scipy.optimize import minimize

    means, counts, ssw, n_obs, C = _cell_reduce(d)
    U, _ = _cell_level_matrices(d)
    args = (means, counts, ssw, n_obs, U, d.n_mem, d.n_task)

    if n_obs <= 1 or C < 2:
        return {}, False, {"reason": f"degenerate design: n={n_obs}, cells={C}"}
    if ssw <= 0 and n_obs > C:
        pass  # exactly-zero within-cell spread is legal; the fit will drive sigma^2 low

    rng = np.random.default_rng(seed)
    starts = [np.array([0.0, 0.0, 0.0]), np.array([-2.0, -2.0, -2.0]),
              np.array([1.0, -1.0, 0.0]), np.array([-1.0, 1.0, 1.0])]
    starts += [rng.normal(0.0, 1.5, size=3) for _ in range(n_random_starts)]

    best = None
    n_ok = 0
    finite_vals: list[float] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for s0 in starts:
            res = minimize(_profiled_neg2_reml, s0, args=args, method="Nelder-Mead",
                           options={"maxiter": maxiter, "xatol": 1e-7, "fatol": 1e-9})
            if not np.isfinite(res.fun) or res.fun >= 1e11:
                continue
            n_ok += 1
            finite_vals.append(float(res.fun))
            if best is None or res.fun < best.fun:
                best = res
    if best is None:
        return {}, False, {"reason": "every REML start failed to produce a finite "
                                     "objective"}

    sigma2, mu = _reml_sigma2(best.x, *args)
    clipped = np.clip(best.x, _LOG_FLOOR, 12.0)
    # A ratio pinned at the UPPER clip is as much a boundary solution as one
    # driven to zero: the likelihood is saying the component is unbounded
    # relative to the residual, i.e. not identified. The module already
    # guarded the LOWER boundary and not this one, so an unidentified fit
    # reported converged=True with a tight bootstrap CI. Recorded here and
    # flagged below.
    at_upper = [COMPONENTS[i] for i in range(3) if clipped[i] >= 12.0 - 1e-9]
    ratios = np.exp(clipped)
    comps = {
        "memory": float(ratios[0] * sigma2),
        "task": float(ratios[1] * sigma2),
        "interaction": float(ratios[2] * sigma2),
        "residual": float(sigma2),
    }
    # Reproducible optimum: at least two independent starts within 1e-4 of the best.
    agree = sum(1 for v in finite_vals if abs(v - best.fun) < 1e-4)
    converged = bool(best.success) and agree >= 2
    info = {
        "neg2_reml": float(best.fun),
        "nit": int(best.get("nit", -1)),
        "n_successful_starts": n_ok,
        "n_starts": len(starts),
        "n_starts_at_optimum": agree,
        "ratios": ratios.tolist(),
        "log_ratios_raw": [float(v) for v in best.x],
        "components_at_upper_bound": at_upper,
        "sigma2": sigma2,
        "intercept_mu": mu,
        "n_cells_reduced": C,
        "optimizer": "Nelder-Mead on log variance ratios; profiled REML on cell-mean "
                     "sufficient statistics with Woodbury inverse",
        "scipy_success": bool(best.success),
        "scipy_message": str(best.message),
    }
    return comps, converged, info


# ======================================================  method of moments (fallback)
def _fit_moments(
    d: _Design, rows: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, float], bool, dict[str, Any]]:
    """Pre-registered fallback: two-way variance components by method of moments.

    Requires a BALANCED sub-design -- the pre-registration says so, and unbalanced MoM
    needs Henderson coefficients that are not what section 6 names. The balanced
    sub-design is built by keeping the memories and tasks that are fully crossed with a
    common replicate count, and the trimming is reported.

    Balanced two-way random effects with n replicates per cell, a memories, b tasks:
        E[MS_A]  = s2 + n s2_ab + n b s2_a
        E[MS_B]  = s2 + n s2_ab + n a s2_b
        E[MS_AB] = s2 + n s2_ab
        E[MS_E]  = s2
    Negative solutions are truncated at 0 AND flagged: MoM can return a negative variance,
    which is not a variance -- it is the estimator saying the component is indistinguishable
    from zero at this design size.
    """
    by_cell: dict[tuple[Any, Any], list[float]] = {}
    for r in rows:
        k = (r.get("memory_id"), r.get("future_task_id"))
        by_cell.setdefault(k, []).append(float(r["delta_utility"]))

    counts = [len(v) for v in by_cell.values()]
    if not counts:
        return {}, False, {"reason": "no cells"}
    n = min(counts)
    if n < 2:
        return {}, False, {"reason": f"min replicate count is {n}; MoM needs >= 2 to "
                                     "separate residual from interaction"}

    mems = sorted({k[0] for k in by_cell}, key=str)
    tasks = sorted({k[1] for k in by_cell}, key=str)
    keep_m = [m for m in mems if all((m, t) in by_cell for t in tasks)]
    keep_t = [t for t in tasks if all((m, t) in by_cell for m in keep_m)]
    a, b = len(keep_m), len(keep_t)
    if a < 2 or b < 2:
        return {}, False, {"reason": f"balanced sub-design is {a}x{b}; needs >= 2x2"}

    Y = np.zeros((a, b, n))
    for i, m in enumerate(keep_m):
        for j, t in enumerate(keep_t):
            vals = sorted(by_cell[(m, t)])[:n]
            Y[i, j, :] = vals

    grand = Y.mean()
    mean_a = Y.mean(axis=(1, 2))
    mean_b = Y.mean(axis=(0, 2))
    mean_ab = Y.mean(axis=2)

    ss_a = n * b * float(((mean_a - grand) ** 2).sum())
    ss_b = n * a * float(((mean_b - grand) ** 2).sum())
    ss_ab = n * float(
        ((mean_ab - mean_a[:, None] - mean_b[None, :] + grand) ** 2).sum()
    )
    ss_e = float(((Y - mean_ab[:, :, None]) ** 2).sum())

    df_a, df_b, df_ab, df_e = a - 1, b - 1, (a - 1) * (b - 1), a * b * (n - 1)
    ms_a, ms_b = ss_a / df_a, ss_b / df_b
    ms_ab = ss_ab / df_ab
    ms_e = ss_e / df_e if df_e > 0 else 0.0

    s2_e = ms_e
    s2_ab = (ms_ab - ms_e) / n
    s2_a = (ms_a - ms_ab) / (n * b)
    s2_b = (ms_b - ms_ab) / (n * a)

    negatives = {k: v for k, v in
                 {"memory": s2_a, "task": s2_b, "interaction": s2_ab}.items() if v < 0}
    comps = {
        "memory": max(0.0, float(s2_a)),
        "task": max(0.0, float(s2_b)),
        "interaction": max(0.0, float(s2_ab)),
        "residual": max(0.0, float(s2_e)),
    }
    info = {
        "balanced_sub_design": {"a_memories": a, "b_tasks": b, "n_replicates": n},
        "trimmed": {"memories_dropped": len(mems) - a, "tasks_dropped": len(tasks) - b},
        "mean_squares": {"MS_A": ms_a, "MS_B": ms_b, "MS_AB": ms_ab, "MS_E": ms_e},
        "df": {"a": df_a, "b": df_b, "ab": df_ab, "e": df_e},
        "negative_estimates_truncated": {k: float(v) for k, v in negatives.items()},
    }
    return comps, True, info


# ==============================================================  public entry point
def variance_decomposition(
    rows: Iterable[Mapping[str, Any]],
    *,
    exec_floor_sd: float | None = None,
    n_boot: int = 200,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    allow_pooling: bool = False,
    force_fallback: bool = False,
    delta_field: str = "delta_utility",
    max_obs_for_reml: int = 4000,
) -> Decomposition:
    """Section 6. Mixed-effects primary, method-of-moments fallback, both disclosed.

    ``exec_floor_sd`` is F_exec on the dU scale (``noise.exec_floor(scale="delta")``). It
    is squared and carried as the explicit comparator section 6 requires: the interaction
    component means nothing without knowing how it compares to execution noise. It is NOT
    used in the fit.

    Bootstrap CIs are over MEMORIES -- the unit of generalization, named in section 6.
    Resampling rows would treat one memory's six cells as six independent observations
    and produce intervals several times too tight.
    """
    adm = admit_rows(rows)
    data = [r for r in adm.rows if r.get(delta_field) is not None]
    flags = require_homogeneous(data, allow_pooling=allow_pooling)
    if len(data) < 4:
        return Decomposition({}, {}, method="none", converged=False,
                             flags=flags + ["INSUFFICIENT_DATA"], n_obs=len(data),
                             extra={"admission": adm.to_dict()})

    d = _build_design(data, delta_field)
    if d.n_mem < 2 or d.n_task < 2:
        return Decomposition(
            {}, {}, method="none", converged=False, n_obs=len(data),
            n_memories=d.n_mem, n_tasks=d.n_task,
            flags=flags + [f"DEGENERATE_DESIGN:{d.n_mem} memories x {d.n_task} tasks; "
                           "a memory x task interaction is not identifiable"],
            extra={"admission": adm.to_dict()},
        )

    used_fallback = False
    if force_fallback:
        comps, ok, info = _fit_moments(d, data)
        method = "method of moments (two-way, balanced sub-design) [FORCED]"
        used_fallback = True
        flags.append("FALLBACK_FORCED:caller requested the fallback; this is NOT the "
                     "pre-registered primary estimator")
    elif len(data) > max_obs_for_reml:
        comps, ok, info = _fit_moments(d, data)
        method = "method of moments (two-way, balanced sub-design)"
        used_fallback = True
        flags.append(
            f"FALLBACK_USED:{len(data)} observations exceeds max_obs_for_reml="
            f"{max_obs_for_reml}; the dense REML likelihood builds an n x n matrix. "
            "Section 6 requires non-convergence be disclosed -- so is this."
        )
    else:
        comps, ok, info = _fit_reml(d, seed=seed)
        method = "REML crossed random effects (memory + task + memory:task)"
        if not ok or not comps:
            flags.append(
                "NON_CONVERGENCE:the mixed model did not converge; falling back to the "
                "PRE-REGISTERED method-of-moments estimator (section 6). "
                f"reason={info.get('reason') or info.get('scipy_message')}"
            )
            comps, ok, mom_info = _fit_moments(d, data)
            info = {"reml_attempt": info, "moments": mom_info}
            method = "method of moments (two-way, balanced sub-design) [FALLBACK]"
            used_fallback = True

    if not comps:
        return Decomposition({}, {}, method=method, converged=False,
                             used_fallback=used_fallback, n_obs=len(data),
                             n_memories=d.n_mem, n_tasks=d.n_task, n_cells=d.n_cell,
                             flags=flags + ["FIT_FAILED"],
                             extra={"info": info, "admission": adm.to_dict()})

    total = sum(comps.values())
    shares = {k: (v / total if total > 0 else 0.0) for k, v in comps.items()}

    for k in COMPONENTS:
        if comps.get(k, 0.0) <= BOUNDARY_TOL:
            flags.append(
                f"AT_BOUNDARY:{k} variance is ~0. The likelihood is saying this component "
                "is not identified from this design -- read it as 'not distinguishable "
                "from zero', not as a measured zero."
            )
    # The UPPER boundary is just as much a non-identification, and was not
    # guarded. Measured on both P1 arms: task and interaction both pinned at
    # exp(12) (the clip ceiling) and their shares came out EXACTLY equal to 16
    # significant figures -- the likelihood cannot tell them apart under a
    # pairing where each memory has its own 8 tasks.
    # `info` is the REML info dict on the direct path but the NESTED
    # {"reml_attempt": ..., "moments": ...} dict on the fallback path, so look
    # in both rather than silently finding nothing on one of them.
    _upper = (info.get("components_at_upper_bound")
              or info.get("reml_attempt", {}).get("components_at_upper_bound")
              or [])
    for k in _upper:
        flags.append(
            f"AT_UPPER_BOUNDARY:{k} variance ratio is pinned at the optimizer's clip "
            f"ceiling (exp(12)). The likelihood is saying this component is unbounded "
            f"relative to the residual, i.e. NOT IDENTIFIED from this design. Its share "
            f"and CI are artifacts of the clip, not measurements."
        )

    # ---- bootstrap over memories
    share_ci: dict[str, tuple[float | None, float | None]] = {}
    comp_ci: dict[str, tuple[float | None, float | None]] = {}
    if n_boot > 0:
        by_mem = group_by(data, "memory_id")
        mem_keys = list(by_mem.keys())
        rng = np.random.default_rng(seed)
        draws: dict[str, list[float]] = {k: [] for k in COMPONENTS}
        cdraws: dict[str, list[float]] = {k: [] for k in COMPONENTS}
        for _ in range(n_boot):
            pick = rng.integers(0, len(mem_keys), size=len(mem_keys))
            sample: list[dict[str, Any]] = []
            for j, i in enumerate(pick):
                # Re-key duplicated memories: a memory drawn twice must be two distinct
                # levels, or the "random effect" is silently given twice the replicates.
                for r in by_mem[mem_keys[i]]:
                    r2 = dict(r)
                    r2["memory_id"] = f"{r['memory_id']}#boot{j}"
                    r2["cell_id"] = f"{r['cell_id']}#boot{j}"
                    sample.append(r2)
            try:
                dd = _build_design(sample, delta_field)
                if used_fallback:
                    c, okb, _ = _fit_moments(dd, sample)
                else:
                    c, okb, _ = _fit_reml(dd, seed=int(rng.integers(1, 2 ** 31)))
            except Exception:  # pragma: no cover - a degenerate resample
                continue
            if not okb or not c:
                continue
            tot = sum(c.values())
            if tot <= 0:
                continue
            for k in COMPONENTS:
                draws[k].append(c[k] / tot)
                cdraws[k].append(c[k])
        for k in COMPONENTS:
            share_ci[k] = percentile_ci(draws[k], alpha)
            comp_ci[k] = percentile_ci(cdraws[k], alpha)
        n_ok = len(draws["memory"])
        if n_ok < n_boot:
            flags.append(f"BOOTSTRAP_DROPPED:{n_boot - n_ok}/{n_boot} resamples failed "
                         "to fit and were discarded")

    fvar = None if exec_floor_sd is None else float(exec_floor_sd) ** 2
    if fvar is not None and fvar > 0:
        flags.append(
            f"EXEC_FLOOR_COMPARATOR:F_exec^2 = {fvar:.6g}; interaction variance is "
            f"{comps['interaction'] / fvar:.3g}x it. Section 6 requires this comparator."
        )
    elif fvar is not None:
        # F_exec = 0 is the EXPECTED result on a deterministic reader at
        # temperature 0 with byte-identical replicates -- it is measured, not
        # missing. But section 6's comparator is a RATIO to F_exec^2, and that
        # ratio is undefined at zero. Dividing here raised ZeroDivisionError and
        # killed the whole decomposition stage, which is how the pilot's shares
        # came back empty and then printed as "all 0.0000".
        flags.append(
            f"EXEC_FLOOR_COMPARATOR_UNDEFINED:F_exec^2 = {fvar:.6g}, so the section-6 "
            f"ratio interaction/F_exec^2 is undefined (division by zero). The "
            f"interaction VARIANCE is still reported as "
            f"{comps['interaction']:.6g}; only the ratio is unavailable. A zero "
            f"execution floor is the expected result for a deterministic reader."
        )

    return Decomposition(
        components=comps, shares=shares, share_ci=share_ci, component_ci=comp_ci,
        method=method, converged=bool(ok), used_fallback=used_fallback,
        n_memories=d.n_mem, n_tasks=d.n_task, n_cells=d.n_cell, n_obs=len(data),
        exec_floor_variance=fvar, flags=flags,
        extra={"info": info, "admission": adm.to_dict(),
               "note": "residual here is the REML/MoM residual, which estimates the same "
                       "quantity as F_exec[delta]^2 by a different route; their agreement "
                       "is a consistency check, not a coincidence"},
    )


def recovery_error(
    fitted: Decomposition, truth_shares: Mapping[str, float]
) -> dict[str, Any]:
    """Absolute and relative share-recovery error against a planted truth.

    Only meaningful on synthetic data. Kept in the module (rather than in the tests) so
    the report can regenerate the recovery table with one call.
    """
    out: dict[str, Any] = {}
    errs = []
    for k in COMPONENTS:
        t = float(truth_shares.get(k, 0.0))
        if k not in fitted.shares:
            # A failed fit recovers NOTHING. Substituting 0.0 would score a
            # non-existent estimate as an error of exactly the planted share,
            # making a crashed fit look like a merely inaccurate one.
            out[k] = {"planted_share": t, "recovered_share": None,
                      "abs_error": None, "rel_error": None,
                      "ci_covers_truth": None,
                      "_note": "component absent from the fit: UNMEASURED, not 0.0"}
            continue
        f = float(fitted.shares[k])
        abs_err = f - t
        errs.append(abs(abs_err))
        ci = fitted.share_ci.get(k)
        out[k] = {
            "planted_share": t,
            "recovered_share": f,
            "abs_error": abs_err,
            "rel_error": (abs_err / t) if t > 0 else None,
            "ci_covers_truth": (
                None if not ci or ci[0] is None else bool(ci[0] <= t <= ci[1])
            ),
        }
    out["max_abs_share_error"] = max(errs) if errs else None
    out["mean_abs_share_error"] = float(np.mean(errs)) if errs else None
    return out


__all__ = [
    "COMPONENTS", "BOUNDARY_TOL", "Decomposition", "variance_decomposition",
    "recovery_error",
]

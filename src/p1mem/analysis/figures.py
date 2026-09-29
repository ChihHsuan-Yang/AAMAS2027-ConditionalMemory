"""D5 -- figure generators for Figures 2, 3 and 4.

    Fig 2  Utility-Efficiency Frontier (prereg section 10, PROJECT_GOAL C, P1-074)
           x = memory tokens exposed to the reader; y = task reward.
           Curves: No-Memory / Keep-All / Top-k (several k) / Oracle, x representation.
           Oracle is labelled NON-DEPLOYABLE HEADROOM, never a method.
    Fig 3  Conditional usefulness / harmfulness (contribution A, sections 4-5)
    Fig 4  Similarity vs utility with NEAR / MID / FAR (sections 7-8)

Each generator is split into ``<fig>_data`` and ``<fig>_figure``. The data function returns
the plotted numbers and, critically, a ``missing_fields`` list naming every schema field
it needed and could not find. **That split is the point of running these now**: the brief's
warning is not to discover in October that the schema cannot produce Figure 2, and a
function that only draws pixels cannot report what it lacked. ``check_schema_support``
runs all three data functions and returns one verdict.

matplotlib is imported lazily inside the plotting functions, so the data functions -- the
part that answers "can the schema do this?" -- run with no display and no matplotlib.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .common import (
    DEFAULT_ALPHA,
    DEFAULT_N_BOOT,
    DEFAULT_SEED,
    admit_rows,
    assign_bands_by_tercile,
    bootstrap_mean_ci,
    cluster_bootstrap,
    group_by,
    tercile_bands,
)
from .labels import ROBUST_HARMFUL, ROBUST_USEFUL, CellStat

ORACLE_LABEL = "Oracle (NON-DEPLOYABLE HEADROOM)"
BANDS = ("NEAR", "MID", "FAR")

#: Fields each figure reads. Checked for presence AND for being non-null somewhere --
#: a field that exists in the schema but is null on every row cannot produce a figure,
#: and a presence-only check would pass it.
FIG2_FIELDS = (
    "memory_tokens_exposed", "reward_with_memory", "reward_without_memory",
    "retrieval_method", "retrieval_k", "memory_representation", "cell_id",
)
FIG3_FIELDS = (
    "delta_utility", "memory_id", "future_task_id", "memory_representation",
    "future_task_family",
)
FIG4_FIELDS = (
    "semantic_similarity", "delta_utility", "memory_id", "benchmark",
    "semantic_distance_band",
)


def _missing(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[str]:
    """Fields absent from the schema, or present-but-null on every admitted row."""
    out: list[str] = []
    if not rows:
        return list(fields)
    for f in fields:
        if f not in rows[0]:
            out.append(f"{f} (ABSENT FROM SCHEMA)")
        elif all(r.get(f) is None for r in rows):
            out.append(f"{f} (present but NULL on every row)")
    return out


# =============================================================  Figure 2 -- frontier
def figure2_data(
    rows: Iterable[Mapping[str, Any]],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Frontier points: one per (representation, retrieval arm).

    x = mean ``memory_tokens_exposed``, y = mean ``reward_with_memory``, both with
    bootstrap CIs over MEMORIES.

    ⚠️ **y is the absolute reward, not dU.** Section 10 says "y = task reward". For the
    No-Memory arm dU is identically 0 by construction, so a dU axis would collapse that
    arm onto the origin and destroy the baseline the frontier is measured against. dU is
    carried in ``extra`` for each point so the other reading is one field away.

    ⚠️ **Oracle is not a method.** Its point is tagged ``non_deployable=True`` and named
    ``ORACLE_LABEL``; ``figure2_figure`` draws it detached from the deployable curve.
    """
    adm = admit_rows(rows)
    data = adm.rows
    missing = _missing(data, FIG2_FIELDS)
    if not data:
        return {"points": [], "missing_fields": missing, "flags": ["NO_ADMITTED_ROWS"],
                "admission": adm.to_dict()}

    flags: list[str] = []
    methods = {str(r.get("retrieval_method")) for r in data}
    for needed in ("none", "keep_all", "top_k", "oracle"):
        if needed not in methods:
            flags.append(f"MISSING_ARM:{needed} -- Figure 2 needs all four retrieval "
                         "arms (prereg section 10); this run has "
                         f"{sorted(methods)}")

    points: list[dict[str, Any]] = []
    for (rep, method, k), group in group_by(
        data, ("memory_representation", "retrieval_method", "retrieval_k")
    ).items():
        mems = sorted({r.get("memory_id") for r in group}, key=str)
        by_mem: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
        for r in group:
            by_mem[r.get("memory_id")].append(r)

        def mk(field: str):
            def stat(sample: Sequence[Any]) -> float | None:
                vals = [float(r[field]) for u in sample for r in by_mem[u]
                        if r.get(field) is not None]
                return float(np.mean(vals)) if vals else None
            return stat

        x, x_lo, x_hi, _ = cluster_bootstrap(mems, mk("memory_tokens_exposed"),
                                             n_boot=n_boot, seed=seed, alpha=alpha)
        y, y_lo, y_hi, _ = cluster_bootstrap(mems, mk("reward_with_memory"),
                                             n_boot=n_boot, seed=seed, alpha=alpha)
        d, d_lo, d_hi, _ = cluster_bootstrap(mems, mk("delta_utility"),
                                             n_boot=n_boot, seed=seed, alpha=alpha)
        base = [float(r["reward_without_memory"]) for r in group
                if r.get("reward_without_memory") is not None]
        is_oracle = str(method) == "oracle"
        label = ORACLE_LABEL if is_oracle else (
            f"Top-k (k={k})" if str(method) == "top_k" else
            {"none": "No-Memory", "keep_all": "Keep-All"}.get(str(method), str(method))
        )
        points.append({
            "representation": str(rep),
            "retrieval_method": str(method),
            "retrieval_k": k,
            "label": label,
            "non_deployable": is_oracle,
            "x_tokens_exposed": x, "x_ci": [x_lo, x_hi],
            "y_reward": y, "y_ci": [y_lo, y_hi],
            "n_memories": len(mems), "n_rows": len(group),
            "extra": {
                "mean_delta_utility": d, "delta_ci": [d_lo, d_hi],
                "mean_reward_without_memory": float(np.mean(base)) if base else None,
            },
        })

    points.sort(key=lambda p: (p["representation"], p["non_deployable"],
                               p["x_tokens_exposed"] if p["x_tokens_exposed"] is not None
                               else -1.0))
    if any(p["non_deployable"] for p in points):
        flags.append("ORACLE_PRESENT:the oracle arm is headroom, not a method "
                     "(prereg section 10); it must never be drawn as part of the "
                     "deployable frontier")
    return {
        "points": points,
        "missing_fields": missing,
        "flags": flags,
        "x_label": "memory tokens exposed to the reader",
        "y_label": "task reward",
        "admission": adm.to_dict(),
    }


def figure2_figure(data: Mapping[str, Any], path: str | None = None):
    """Draw Figure 2. Returns the matplotlib Figure; saves when ``path`` is given."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    reps = sorted({p["representation"] for p in data["points"]})
    markers = ["o", "s", "^", "D", "v"]
    for i, rep in enumerate(reps):
        pts = [p for p in data["points"] if p["representation"] == rep
               and p["x_tokens_exposed"] is not None and p["y_reward"] is not None]
        dep = [p for p in pts if not p["non_deployable"]]
        orc = [p for p in pts if p["non_deployable"]]
        if dep:
            ax.errorbar(
                [p["x_tokens_exposed"] for p in dep], [p["y_reward"] for p in dep],
                yerr=_yerr(dep), marker=markers[i % len(markers)], capsize=2,
                linewidth=1.4, markersize=5, label=f"{rep} (deployable)",
            )
        for p in orc:
            ax.scatter([p["x_tokens_exposed"]], [p["y_reward"]],
                       marker="*", s=190, zorder=5,
                       label=f"{rep} — {ORACLE_LABEL}")
            ax.annotate("NON-DEPLOYABLE\nHEADROOM",
                        (p["x_tokens_exposed"], p["y_reward"]),
                        textcoords="offset points", xytext=(6, -18), fontsize=7,
                        color="0.25")
    ax.set_xlabel(data["x_label"])
    ax.set_ylabel(data["y_label"])
    ax.set_title("Fig 2 — Memory Utility–Efficiency Frontier")
    ax.grid(alpha=0.25, linewidth=0.5)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=200)
    return fig


def _yerr(pts: Sequence[Mapping[str, Any]]):
    lo, hi = [], []
    for p in pts:
        c = p.get("y_ci") or [None, None]
        if c[0] is None:
            lo.append(0.0); hi.append(0.0)
        else:
            lo.append(max(0.0, p["y_reward"] - c[0]))
            hi.append(max(0.0, c[1] - p["y_reward"]))
    return [lo, hi]


# ==============================================  Figure 3 -- conditional usefulness
def figure3_data(
    cells: Sequence[CellStat], rows: Sequence[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Per-memory label profile across tasks + the label mix by representation.

    Panel A is a memory x task label grid -- the picture of contribution A, which is that
    a memory does NOT reduce to one global importance score. Memories are ordered by
    (has a robust flip, then spread of mean dU) so flipping memories are at the top and
    the structure is visible rather than buried in alphabetical order.
    """
    missing = _missing(rows or [], FIG3_FIELDS) if rows else []
    by_mem: dict[Any, list[CellStat]] = defaultdict(list)
    for c in cells:
        by_mem[c.memory_id].append(c)
    tasks = sorted({c.task_id for c in cells}, key=str)

    profiles = []
    for mem, group in by_mem.items():
        labs = {c.task_id: c.label for c in group}
        deltas = {c.task_id: c.mean_delta for c in group}
        vals = [v for v in deltas.values() if v is not None]
        flip = (any(c.label == ROBUST_USEFUL for c in group)
                and any(c.label == ROBUST_HARMFUL for c in group)
                and len({c.task_id for c in group}) >= 2)
        profiles.append({
            "memory_id": mem,
            "representation": group[0].representation,
            "labels": labs,
            "mean_deltas": deltas,
            "robust_flip": flip,
            "spread": (max(vals) - min(vals)) if len(vals) > 1 else 0.0,
            "n_tasks": len({c.task_id for c in group}),
        })
    profiles.sort(key=lambda p: (not p["robust_flip"], -p["spread"]))

    by_rep: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in cells:
        by_rep[str(c.representation)][c.label] += 1
    by_fam: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in cells:
        by_fam[str(c.extra.get("future_task_family"))][c.label] += 1

    return {
        "profiles": profiles,
        "tasks": tasks,
        "label_counts_by_representation": {k: dict(v) for k, v in by_rep.items()},
        "label_counts_by_task_family": {k: dict(v) for k, v in by_fam.items()},
        "n_memories": len(by_mem),
        "n_flipping": sum(1 for p in profiles if p["robust_flip"]),
        "missing_fields": missing,
        "flags": (["ALL_UNDETERMINED:every cell is unlabelled -- the floor has not been "
                   "measured, so Figure 3 has no content yet"]
                  if cells and all(c.label == "undetermined" for c in cells) else []),
    }


def figure3_figure(data: Mapping[str, Any], path: str | None = None, *, max_rows: int = 30):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    order = ["robust_useful", "neutral", "robust_harmful", "undetermined"]
    cmap = ListedColormap(["#2c7fb8", "#e8e8e8", "#d7301f", "#ffffff"])
    profiles = data["profiles"][:max_rows]
    tasks = data["tasks"]
    grid = np.full((len(profiles), len(tasks)), 3.0)
    for i, p in enumerate(profiles):
        for j, t in enumerate(tasks):
            lab = p["labels"].get(t)
            if lab in order:
                grid[i, j] = order.index(lab)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.6),
                             gridspec_kw={"width_ratios": [2.1, 1]})
    ax = axes[0]
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=3, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels([str(t)[:12] for t in tasks], rotation=60, ha="right", fontsize=6)
    ax.set_yticks(range(len(profiles)))
    ax.set_yticklabels([f"{str(p['memory_id'])[-10:]}{' *FLIP' if p['robust_flip'] else ''}"
                        for p in profiles], fontsize=6)
    ax.set_title("A — memory x task robust labels\n(* = robust sign flip)", fontsize=9)
    ax.legend(handles=[Patch(facecolor=cmap(i), edgecolor="0.6", label=l)
                       for i, l in enumerate(order)],
              fontsize=6, loc="upper left", bbox_to_anchor=(1.01, 1.0))

    ax2 = axes[1]
    reps = sorted(data["label_counts_by_representation"])
    bottom = np.zeros(len(reps))
    for i, lab in enumerate(order):
        vals = np.array([data["label_counts_by_representation"][r].get(lab, 0)
                         for r in reps], dtype=float)
        ax2.bar(reps, vals, bottom=bottom, label=lab, color=cmap(i),
                edgecolor="0.5", linewidth=0.4)
        bottom += vals
    ax2.set_ylabel("cells")
    ax2.set_title("B — label mix by representation", fontsize=9)
    ax2.tick_params(labelsize=7)
    ax2.legend(fontsize=6)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=200)
    return fig


# =========================================  Figure 4 -- similarity vs utility + bands
def figure4_data(
    cells: Sequence[CellStat],
    rows: Sequence[Mapping[str, Any]],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Section 7 bands + section 8 Spearman rho, overall and per band.

    Bands are recomputed from the observed distribution per benchmark (section 7:
    terciles, because cosine scales are not comparable across corpora) rather than read
    off the stored ``semantic_distance_band``; the two are then compared and any
    disagreement is reported. Trusting the stored field would make the check vacuous.

    Also computed, because section 8 asks for it explicitly: the fraction of
    high-similarity (NEAR) cells that are robustly harmful, and -- section 7's "primary
    question" -- whether robust sign flips occur within the NEAR band.
    """
    from scipy.stats import spearmanr

    missing = _missing(rows, FIG4_FIELDS)
    band_of_row = assign_bands_by_tercile(rows, per="benchmark")
    row_by_cell: dict[Any, Mapping[str, Any]] = {}
    for r in rows:
        row_by_cell.setdefault(r.get("cell_id"), r)

    recomputed: dict[Any, str] = {}
    disagree = 0
    for cell, r in row_by_cell.items():
        b = band_of_row.get(r.get("row_id"))
        if b is None:
            continue
        recomputed[cell] = b
        stored = r.get("semantic_distance_band")
        if stored is not None and stored != b:
            disagree += 1

    pts = []
    for c in cells:
        s = c.semantic_similarity
        if s is None or c.mean_delta is None:
            continue
        pts.append({
            "memory_id": c.memory_id, "task_id": c.task_id, "cell_id": c.cell_id,
            "similarity": float(s), "mean_delta": float(c.mean_delta),
            "label": c.label, "band": recomputed.get(c.cell_id, c.band),
            "representation": c.representation,
        })

    def rho_ci(subset: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if len(subset) < 3:
            return {"rho": None, "p": None, "ci": [None, None], "n": len(subset),
                    "flags": ["TOO_FEW_POINTS"]}
        by_mem: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
        for p in subset:
            by_mem[p["memory_id"]].append(p)
        mems = list(by_mem)

        def stat(sample: Sequence[Any]) -> float | None:
            xs, ys = [], []
            for u in sample:
                for p in by_mem[u]:
                    xs.append(p["similarity"]); ys.append(p["mean_delta"])
            if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
                return None
            return float(spearmanr(xs, ys).statistic)

        point, lo, hi, _n = cluster_bootstrap(mems, stat, n_boot=n_boot, seed=seed,
                                              alpha=alpha)
        res = spearmanr([p["similarity"] for p in subset],
                        [p["mean_delta"] for p in subset])
        return {"rho": point, "p": float(res.pvalue), "ci": [lo, hi],
                "n": len(subset), "n_memories": len(mems), "flags": []}

    per_band = {b: rho_ci([p for p in pts if p["band"] == b]) for b in BANDS}

    near = [p for p in pts if p["band"] == "NEAR"]
    near_harm = sum(1 for p in near if p["label"] == ROBUST_HARMFUL)
    near_by_mem: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for p in near:
        near_by_mem[p["memory_id"]].append(p)
    near_flips = sum(
        1 for _m, g in near_by_mem.items()
        if any(p["label"] == ROBUST_USEFUL for p in g)
        and any(p["label"] == ROBUST_HARMFUL for p in g)
        and len({p["task_id"] for p in g}) >= 2
    )

    sims = [float(r["semantic_similarity"]) for r in rows
            if r.get("semantic_similarity") is not None]
    flags: list[str] = []
    if disagree:
        flags.append(
            f"BAND_DISAGREEMENT:{disagree}/{len(recomputed)} cells' recomputed tercile "
            "band differs from the stored semantic_distance_band. The recomputed band is "
            "used (prereg section 7 defines bands by the OBSERVED distribution); the "
            "stored field's populator should be reconciled."
        )
    return {
        "points": pts,
        "tercile_cuts": list(tercile_bands(sims)) if sims else None,
        "band_counts": {b: sum(1 for p in pts if p["band"] == b) for b in BANDS},
        "overall": rho_ci(pts),
        "per_band": per_band,
        "near_band": {
            "n_cells": len(near),
            "n_robustly_harmful": near_harm,
            "fraction_robustly_harmful": (near_harm / len(near)) if near else None,
            "n_memories_with_robust_flip_inside_NEAR": near_flips,
            "question": "prereg section 7 primary question: do robust sign flips occur "
                        "INSIDE the NEAR band, where neighbourhood averaging is assumed "
                        "safe?",
        },
        "n_band_disagreements_with_stored_field": disagree,
        "missing_fields": missing,
        "flags": flags,
        "framing_note": "prereg section 8: frame as MEASUREMENT, not discovery. "
                        "'Relevance is not utility' is stated in prior abstracts; cite "
                        "them (docs/LITERATURE_BOUNDARY.md).",
    }


def figure4_figure(data: Mapping[str, Any], path: str | None = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"robust_useful": "#2c7fb8", "robust_harmful": "#d7301f",
              "neutral": "#9e9e9e", "undetermined": "#d9d9d9"}
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6),
                             gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    for lab, col in colors.items():
        sub = [p for p in data["points"] if p["label"] == lab]
        if sub:
            ax.scatter([p["similarity"] for p in sub], [p["mean_delta"] for p in sub],
                       s=16, alpha=0.75, color=col, label=lab, edgecolors="none")
    cuts = data.get("tercile_cuts")
    if cuts:
        for c, name in zip(cuts, ("FAR|MID", "MID|NEAR")):
            ax.axvline(c, color="0.4", linestyle="--", linewidth=0.9)
            ax.annotate(name, (c, ax.get_ylim()[1]), fontsize=6, color="0.35",
                        rotation=90, va="top", ha="right")
    ax.axhline(0.0, color="0.2", linewidth=0.8)
    ax.set_xlabel("cos(embed(memory), embed(task))")
    ax.set_ylabel("mean ΔU")
    o = data["overall"]
    rho = "n/a" if o["rho"] is None else f"{o['rho']:.3f}"
    ax.set_title(f"Fig 4 — similarity vs utility (Spearman ρ = {rho})", fontsize=9)
    ax.legend(fontsize=6)
    ax.grid(alpha=0.2, linewidth=0.5)

    ax2 = axes[1]
    bands = [b for b in BANDS if data["per_band"][b]["rho"] is not None]
    vals = [data["per_band"][b]["rho"] for b in bands]
    errs = [[max(0.0, data["per_band"][b]["rho"] - (data["per_band"][b]["ci"][0] or 0))
             for b in bands],
            [max(0.0, (data["per_band"][b]["ci"][1] or 0) - data["per_band"][b]["rho"])
             for b in bands]]
    ax2.bar(bands, vals, yerr=errs, capsize=3, color="#7fa8c9", edgecolor="0.4")
    ax2.axhline(0.0, color="0.2", linewidth=0.8)
    ax2.set_ylabel("Spearman ρ (similarity vs ΔU)")
    ax2.set_title("per band, bootstrap CI over memories", fontsize=9)
    ax2.tick_params(labelsize=7)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=200)
    return fig


# ====================================================================  schema check
def check_schema_support(
    rows: Sequence[Mapping[str, Any]], cells: Sequence[CellStat] | None = None,
    *, n_boot: int = 50,
) -> dict[str, Any]:
    """Can the schema actually produce Figures 2-4? Run this BEFORE October.

    Every figure is generated end to end, so a field that is missing, always-null, or
    present-but-not-discriminating shows up now instead of at submission.
    """
    out: dict[str, Any] = {}
    f2 = figure2_data(rows, n_boot=n_boot)
    out["figure2"] = {
        "producible": bool(f2["points"]) and not f2["missing_fields"],
        "n_points": len(f2["points"]),
        "missing_fields": f2["missing_fields"],
        "flags": f2["flags"],
    }
    if cells:
        f3 = figure3_data(cells, rows)
        out["figure3"] = {
            "producible": bool(f3["profiles"]) and not f3["missing_fields"],
            "n_memories": f3["n_memories"], "n_flipping": f3["n_flipping"],
            "missing_fields": f3["missing_fields"], "flags": f3["flags"],
        }
        f4 = figure4_data(cells, rows, n_boot=n_boot)
        out["figure4"] = {
            "producible": bool(f4["points"]) and not f4["missing_fields"],
            "n_points": len(f4["points"]), "band_counts": f4["band_counts"],
            "missing_fields": f4["missing_fields"], "flags": f4["flags"],
        }
    else:
        out["figure3"] = {"producible": None,
                          "note": "needs labelled cells from labels.cell_statistics"}
        out["figure4"] = {"producible": None,
                          "note": "needs labelled cells from labels.cell_statistics"}
    out["all_producible"] = all(
        v.get("producible") for v in out.values() if isinstance(v, dict)
    )
    return out


__all__ = [
    "ORACLE_LABEL", "BANDS", "FIG2_FIELDS", "FIG3_FIELDS", "FIG4_FIELDS",
    "figure2_data", "figure2_figure", "figure3_data", "figure3_figure",
    "figure4_data", "figure4_figure", "check_schema_support",
]

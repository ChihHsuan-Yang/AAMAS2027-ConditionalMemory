"""D4 -- efficiency metrics. ANALYSIS_PREREGISTRATION section 10 + PROJECT_GOAL C.

Seven families (MASTER_TODO P1-067..073, PROJECT_GOAL contribution C):

    storage . retrieval . exposure . latency . API/compute . selectivity . extraction

and the derived metrics the frontier needs: utility per exposed token, Useful/Harmful
Exposure Rate, Useful Retrieval Precision, compression ratio.

🔴 **Formation cost is charged to the representation that incurred it.**
``docs/MEMORY_PROTOCOL.md`` section 5: "Raw costs ~0; summary and structured each cost one
call per segment. The efficiency frontier must charge each representation for its own
formation cost, or it flatters the model-written ones." Summary and Structured buy their
small token footprint with a writer call that Raw never makes; an exposure-only comparison
hands them that discount for free. ``formation_cost`` measures it and
``amortized_formation_cost`` divides it over the number of cells the memory is actually
reused across -- because a write paid once and reused fifty times is not the same cost as
one paid per use, and reporting only the un-amortized figure would flatter Raw in the
opposite direction. **Both are reported.** Neither is the single right answer; the
reuse count is an experimental design parameter, so the frontier states it.

Three null-handling rules, each a recorded prior failure:

* ``memory_extraction_latency = None`` means NO CALL WAS MADE (raw), not 0.0 seconds.
  ``schema.py`` says so explicitly. Nulls are excluded from means and counted separately.
* ``reasoning_tokens = None`` means NOT REPORTED BY THIS CLUSTER, not zero. Sophia omits
  ``completion_tokens_details`` entirely. Any aggregate excludes nulls from the
  denominator rather than summing them as zeros.
* ``retry_count = 0`` IS a measurement and is never a stand-in for unknown.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
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
    require_homogeneous,
    wilson_ci,
)
from .labels import ROBUST_HARMFUL, ROBUST_USEFUL, CellStat

FAMILIES = (
    "storage", "retrieval", "exposure", "latency", "api_compute",
    "selectivity", "extraction",
)

#: Fields whose null means "not applicable / no call", never zero.
NULL_IS_NOT_ZERO = (
    "memory_extraction_latency",
    "memory_extraction_input_tokens",
    "memory_extraction_output_tokens",
    "write_latency",
    "retrieval_latency",
    "reasoning_tokens",
)


def _agg(vals: Sequence[float | None]) -> dict[str, Any]:
    """Mean/median/sum over non-null values, with the null count kept beside them."""
    present = [float(v) for v in vals if v is not None]
    n_null = len(vals) - len(present)
    if not present:
        return {"n": 0, "n_null": n_null, "mean": None, "median": None,
                "sum": None, "min": None, "max": None, "sd": None}
    arr = np.asarray(present, dtype=float)
    return {
        "n": int(arr.size),
        "n_null": n_null,
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "sum": float(arr.sum()),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "sd": float(arr.std(ddof=1)) if arr.size > 1 else None,
    }


def _col(rows: Sequence[Mapping[str, Any]], name: str) -> list[float | None]:
    return [r.get(name) for r in rows]


# =========================================================  the seven cost families
def storage_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 1 -- what the memory costs to KEEP. Per distinct memory, not per row.

    Per-row aggregation would weight a memory by how many tasks it was evaluated on,
    which is a property of the experimental design, not of the memory.
    """
    per_mem: dict[Any, dict[str, Any]] = {}
    for r in rows:
        mid = r.get("memory_id")
        if mid not in per_mem:
            per_mem[mid] = {
                "memory_tokens": r.get("memory_tokens"),
                "memory_representation": r.get("memory_representation"),
                "memory_chars": len(r.get("memory_text") or ""),
                "source_episode_id": r.get("source_episode_id"),
            }
    mems = list(per_mem.values())
    return {
        "family": "storage",
        "unit": "distinct memory",
        "n_memories": len(mems),
        "memory_tokens": _agg([m["memory_tokens"] for m in mems]),
        "memory_chars": _agg([m["memory_chars"] for m in mems]),
        "total_corpus_tokens": sum(
            m["memory_tokens"] for m in mems if m["memory_tokens"] is not None
        ),
    }


def retrieval_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 2 -- what retrieval costs and returns."""
    return {
        "family": "retrieval",
        "unit": "cell",
        "retrieval_latency_s": _agg(_col(rows, "retrieval_latency")),
        "memory_tokens_retrieved": _agg(_col(rows, "memory_tokens_retrieved")),
        "retrieval_rank": _agg(_col(rows, "retrieval_rank")),
        "by_method": {
            str(k): {"n_rows": len(v),
                     "tokens_retrieved": _agg(_col(v, "memory_tokens_retrieved")),
                     "latency_s": _agg(_col(v, "retrieval_latency"))}
            for k, v in group_by(rows, "retrieval_method").items()
        },
        "note": "retrieval_latency is null when retrieval_method == 'none'; nulls are "
                "excluded from the mean, never summed as zero",
    }


def exposure_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 3 -- what actually reached the reader's context.

    ``memory_tokens_exposed`` is the frontier's x-axis (section 10). The gap to
    ``memory_tokens_retrieved`` is truncation loss -- retrieved-but-never-seen tokens,
    which cost retrieval time and buy nothing.
    """
    retrieved = [r.get("memory_tokens_retrieved") for r in rows]
    exposed = [r.get("memory_tokens_exposed") for r in rows]
    pairs = [(a, b) for a, b in zip(retrieved, exposed) if a is not None and b is not None]
    trunc = [a - b for a, b in pairs]
    trunc_frac = [(a - b) / a for a, b in pairs if a > 0]
    over = sum(1 for a, b in pairs if b > a)
    out = {
        "family": "exposure",
        "unit": "cell",
        "memory_tokens_exposed": _agg(exposed),
        "memory_tokens_retrieved": _agg(retrieved),
        "truncation_loss_tokens": _agg(trunc),
        "truncation_loss_fraction": _agg(trunc_frac),
        "n_rows_exposed_exceeds_retrieved": over,
    }
    if over:
        out["flags"] = [
            f"IMPOSSIBLE_EXPOSURE:{over} rows have exposed > retrieved. Exposure is what "
            "survives truncation of the retrieved set, so this is a populator bug, not a "
            "measurement."
        ]
    return out


def latency_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 4 -- wall clock, split by stage.

    ``generation_latency`` is BOTH arms summed (schema). A WITH-arm-only latency is not
    recoverable from the schema; see the schema-gap list in the report.
    """
    e2e = [r.get("end_to_end_latency") for r in rows]
    gen = [r.get("generation_latency") for r in rows]
    accounted = [
        (r.get("generation_latency") or 0.0) + (r.get("retrieval_latency") or 0.0)
        for r in rows if r.get("end_to_end_latency") is not None
    ]
    total_e2e = sum(v for v in e2e if v is not None)
    return {
        "family": "latency",
        "unit": "cell",
        "end_to_end_s": _agg(e2e),
        "generation_s_both_arms": _agg(gen),
        "retrieval_s": _agg(_col(rows, "retrieval_latency")),
        "write_s": _agg(_col(rows, "write_latency")),
        "unaccounted_fraction_of_e2e": (
            None if total_e2e <= 0 else max(0.0, 1.0 - sum(accounted) / total_e2e)
        ),
        "note": "generation_latency covers BOTH arms; write_latency is null for raw "
                "(no call made), which is not 0.0 seconds",
    }


def api_compute_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 5 -- calls and tokens billed at READ time (formation is family 7)."""
    rt = [r.get("reasoning_tokens") for r in rows]
    n_rt_null = sum(1 for v in rt if v is None)
    out = {
        "family": "api_compute",
        "unit": "cell",
        "generation_calls": _agg(_col(rows, "generation_calls")),
        "embedding_calls": _agg(_col(rows, "embedding_calls")),
        "input_tokens": _agg(_col(rows, "input_tokens")),
        "output_tokens": _agg(_col(rows, "output_tokens")),
        "reasoning_tokens": _agg(rt),
        "retry_count": _agg(_col(rows, "retry_count")),
        "n_rows_reasoning_tokens_null": n_rt_null,
        "note": "reasoning_tokens null = NOT REPORTED BY THIS CLUSTER (Sophia omits "
                "completion_tokens_details), never zero. Nulls are out of the "
                "denominator; the null count is reported so a mean over a partly-"
                "reporting set is not mistaken for a mean over all of it.",
    }
    if n_rt_null and n_rt_null < len(rows):
        out["flags"] = [
            f"MIXED_REASONING_REPORTING:{n_rt_null}/{len(rows)} rows have null "
            "reasoning_tokens. The mean is over the reporting subset only, and that "
            "subset is a CLUSTER, so it is not a random sample of the rows."
        ]
    return out


def selectivity_metrics(
    rows: Sequence[Mapping[str, Any]], cells: Sequence[CellStat] | None = None
) -> dict[str, Any]:
    """Family 6 -- is what we exposed the thing that helped?

    Needs labels, so it takes the cell statistics from ``labels.cell_statistics``. Without
    them only the retrieval-shape part is computable, and the label-dependent rates are
    ``None`` rather than guessed.
    """
    out: dict[str, Any] = {
        "family": "selectivity",
        "unit": "cell",
        "by_retrieval_method": {
            str(k): len(v) for k, v in group_by(rows, "retrieval_method").items()
        },
    }
    if not cells:
        out["note"] = ("label-dependent selectivity needs cell labels; pass `cells` from "
                       "labels.cell_statistics. Not computed, not guessed.")
        return out

    n = len(cells)
    n_useful = sum(1 for c in cells if c.label == ROBUST_USEFUL)
    n_harmful = sum(1 for c in cells if c.label == ROBUST_HARMFUL)
    n_exposed = sum(1 for c in cells if (c.extra.get("retrieval_method") or "") != "none")

    # Useful Retrieval Precision: of the cells where a memory WAS exposed, how many were
    # robustly useful. Denominator is exposed cells, not all cells -- a no-memory cell
    # cannot be a retrieval hit or a miss.
    urp, urp_lo, urp_hi = wilson_ci(n_useful, n_exposed)
    uer, uer_lo, uer_hi = wilson_ci(n_useful, n)
    her, her_lo, her_hi = wilson_ci(n_harmful, n)
    out.update({
        "n_cells": n,
        "n_cells_with_memory_exposed": n_exposed,
        "useful_retrieval_precision": {
            "point": urp, "ci_lower": urp_lo, "ci_upper": urp_hi,
            "numerator": n_useful, "denominator": n_exposed,
            "definition": "robust_useful cells / cells where a memory was exposed",
        },
        "useful_exposure_rate": {
            "point": uer, "ci_lower": uer_lo, "ci_upper": uer_hi,
            "numerator": n_useful, "denominator": n,
        },
        "harmful_exposure_rate": {
            "point": her, "ci_lower": her_lo, "ci_upper": her_hi,
            "numerator": n_harmful, "denominator": n,
        },
        "neutral_fraction": (
            sum(1 for c in cells if c.label == "neutral") / n if n else None
        ),
        "undetermined_fraction": (
            sum(1 for c in cells if c.label == "undetermined") / n if n else None
        ),
        "wasted_exposed_tokens": None,
    })
    if any(c.label == "undetermined" for c in cells):
        out["flags"] = [
            "UNDETERMINED_IN_DENOMINATOR:some cells are unlabelled (no floor, or <2 "
            "replicates). They sit in the denominator and can never be in a numerator, "
            "so useful/harmful rates here are LOWER BOUNDS."
        ]
    return out


def extraction_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Family 7 -- FORMATION cost, per distinct memory, per representation.

    The family the frontier must not omit (MEMORY_PROTOCOL section 5).
    """
    per_mem: dict[Any, Mapping[str, Any]] = {}
    for r in rows:
        per_mem.setdefault(r.get("memory_id"), r)
    mems = list(per_mem.values())
    out: dict[str, Any] = {
        "family": "extraction",
        "unit": "distinct memory",
        "n_memories": len(mems),
        "by_representation": {},
    }
    for rep, group in group_by(mems, "memory_representation").items():
        lat = [g.get("memory_extraction_latency") for g in group]
        it = [g.get("memory_extraction_input_tokens") for g in group]
        ot = [g.get("memory_extraction_output_tokens") for g in group]
        n_no_call = sum(1 for v in lat if v is None)
        out["by_representation"][str(rep)] = {
            "n_memories": len(group),
            "n_with_no_writer_call": n_no_call,
            "writer_calls": len(group) - n_no_call,
            "extraction_latency_s": _agg(lat),
            "extraction_input_tokens": _agg(it),
            "extraction_output_tokens": _agg(ot),
            "memory_tokens": _agg([g.get("memory_tokens") for g in group]),
            "writer_model": sorted({str(g.get("memory_writer_model")) for g in group}),
        }
    return out


# ============================================================  formation cost + reuse
@dataclass
class FormationCost:
    """Per-representation formation cost, un-amortized AND amortized over reuse."""

    representation: str
    n_memories: int
    writer_calls_total: int
    writer_calls_per_memory: float
    input_tokens_per_memory: float | None
    output_tokens_per_memory: float | None
    latency_s_per_memory: float | None
    n_cells_using: int
    reuse_factor: float
    amortized_calls_per_cell: float
    amortized_tokens_per_cell: float | None
    amortized_latency_per_cell: float | None
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def formation_cost(rows: Sequence[Mapping[str, Any]]) -> dict[str, FormationCost]:
    """Charge each representation for its own formation cost (MEMORY_PROTOCOL section 5).

    Two numbers per representation, both reported, because neither alone is honest:

    * **Un-amortized** (per memory written). Raw ~0 calls, summary/structured 1 call each
      per segment. This is what the writer pass actually costs.
    * **Amortized** over the cells the memory is reused across. A memory written once and
      evaluated on 6 tasks costs 1/6 of a call per cell.

    Which is right depends on the deployment being argued about, and the reuse factor is
    an experimental design parameter here (how many future tasks we chose to pair), not a
    property of the representation. So the frontier states it rather than picking one.
    """
    out: dict[str, FormationCost] = {}
    by_rep = group_by(rows, "memory_representation")
    for rep, group in by_rep.items():
        per_mem: dict[Any, Mapping[str, Any]] = {}
        cells: set = set()
        for r in group:
            per_mem.setdefault(r.get("memory_id"), r)
            cells.add(r.get("cell_id"))
        mems = list(per_mem.values())
        n_mem = len(mems)
        calls = sum(0 if m.get("memory_extraction_latency") is None else 1 for m in mems)
        it = [m.get("memory_extraction_input_tokens") for m in mems]
        ot = [m.get("memory_extraction_output_tokens") for m in mems]
        lat = [m.get("memory_extraction_latency") for m in mems]
        # Nulls here mean "no call": for a TOTAL cost they legitimately contribute 0
        # tokens, because no tokens were billed. That is different from the null-is-not-
        # zero rule for a MEAN, where a null means "unknown for this row".
        tot_tok = sum((v or 0) for v in it) + sum((v or 0) for v in ot)
        tot_lat = sum((v or 0.0) for v in lat)
        n_cells = len(cells)
        reuse = (n_cells / n_mem) if n_mem else 0.0
        flags: list[str] = []
        if calls == 0:
            flags.append("NO_WRITER_CALL:deterministic representation; formation cost is "
                         "~0 API calls by construction (MEMORY_PROTOCOL section 1A)")
        if n_mem and calls not in (0, n_mem):
            flags.append(f"PARTIAL_WRITER_CALLS:{calls}/{n_mem} memories record a writer "
                         "call; the protocol says one call per segment")
        out[str(rep)] = FormationCost(
            representation=str(rep),
            n_memories=n_mem,
            writer_calls_total=calls,
            writer_calls_per_memory=(calls / n_mem) if n_mem else 0.0,
            input_tokens_per_memory=(sum((v or 0) for v in it) / n_mem) if n_mem else None,
            output_tokens_per_memory=(sum((v or 0) for v in ot) / n_mem) if n_mem else None,
            latency_s_per_memory=(tot_lat / n_mem) if n_mem else None,
            n_cells_using=n_cells,
            reuse_factor=reuse,
            amortized_calls_per_cell=(calls / n_cells) if n_cells else 0.0,
            amortized_tokens_per_cell=(tot_tok / n_cells) if n_cells else None,
            amortized_latency_per_cell=(tot_lat / n_cells) if n_cells else None,
            flags=flags,
        )
    return out


def compression_ratio(
    rows: Sequence[Mapping[str, Any]], *, baseline_representation: str = "raw"
) -> dict[str, Any]:
    """Compression of each representation against Raw, paired ON THE SOURCE EPISODE.

    Section 9: the three representations are matched by construction, so the comparison
    is WITHIN-EPISODE. An unpaired ratio-of-means would confound compression with which
    episodes happened to be written in which representation.
    """
    tok: dict[tuple[Any, Any], list[float]] = defaultdict(list)
    for r in rows:
        ep, rep = r.get("source_episode_id"), r.get("memory_representation")
        if r.get("memory_tokens") is not None:
            tok[(ep, rep)].append(float(r["memory_tokens"]))
    per: dict[tuple[Any, Any], float] = {
        k: float(np.mean(v)) for k, v in tok.items()
    }
    reps = sorted({k[1] for k in per}, key=str)
    episodes = sorted({k[0] for k in per}, key=str)
    out: dict[str, Any] = {
        "baseline": baseline_representation,
        "definition": "baseline_tokens / representation_tokens, paired per source "
                      "episode; >1 means smaller than baseline",
        "by_representation": {},
        "n_episodes": len(episodes),
    }
    for rep in reps:
        ratios = []
        for ep in episodes:
            b = per.get((ep, baseline_representation))
            v = per.get((ep, rep))
            if b is None or v is None or v <= 0:
                continue
            ratios.append(b / v)
        out["by_representation"][str(rep)] = {
            "n_paired_episodes": len(ratios),
            **_agg(ratios),
        }
        if not ratios and str(rep) != baseline_representation:
            out["by_representation"][str(rep)]["flags"] = [
                "NO_PAIRED_EPISODE:this representation shares no source episode with the "
                "baseline, so no within-episode compression ratio exists"
            ]
    return out


# =========================================================  utility per exposed token
def utility_per_exposed_token(
    cells: Sequence[CellStat],
    rows: Sequence[Mapping[str, Any]],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    include_formation: bool = True,
) -> dict[str, Estimate]:
    """Mean dU per 1000 exposed tokens, per representation, with a bootstrap CI.

    **A ratio of means, not a mean of ratios.** Per-cell dU/tokens is unbounded as
    exposure goes to zero and its mean is dominated by the smallest-exposure cells;
    the ratio of the two totals is the quantity a frontier reads off its axes.

    ``include_formation=True`` adds the amortized formation tokens to the denominator, so
    Summary and Structured are charged the writer tokens that bought their small
    footprint. With it False the comparison is exposure-only -- which is the comparison
    MEMORY_PROTOCOL section 5 warns "flatters the model-written ones". Both are returned
    by ``efficiency_report`` so the difference is visible rather than assumed away.
    """
    tokens_by_cell: dict[Any, float] = {}
    rep_by_cell: dict[Any, Any] = {}
    for r in rows:
        c = r.get("cell_id")
        t = r.get("memory_tokens_exposed")
        if t is not None:
            tokens_by_cell[c] = float(t)
        rep_by_cell[c] = r.get("memory_representation")

    fc = formation_cost(rows) if include_formation else {}

    by_rep: dict[Any, list[CellStat]] = defaultdict(list)
    for c in cells:
        by_rep[rep_by_cell.get(c.cell_id, c.representation)].append(c)

    out: dict[str, Estimate] = {}
    for rep, group in by_rep.items():
        extra_tok = 0.0
        if include_formation and str(rep) in fc:
            extra_tok = float(fc[str(rep)].amortized_tokens_per_cell or 0.0)

        def stat(sample: Sequence[CellStat]) -> float | None:
            num = 0.0
            den = 0.0
            for c in sample:
                if c.mean_delta is None:
                    continue
                t = tokens_by_cell.get(c.cell_id)
                if t is None:
                    continue
                num += c.mean_delta
                den += t + extra_tok
            if den <= 0:
                return None
            return 1000.0 * num / den

        point, lo, hi, _n = cluster_bootstrap(
            group, stat, n_boot=n_boot, seed=seed, alpha=alpha
        )
        flags = []
        if include_formation and extra_tok > 0:
            flags.append(f"FORMATION_CHARGED:+{extra_tok:.1f} amortized formation tokens "
                         "per cell in the denominator (MEMORY_PROTOCOL section 5)")
        elif include_formation:
            flags.append("FORMATION_CHARGED:0 formation tokens (no writer call)")
        else:
            flags.append("FORMATION_NOT_CHARGED:exposure-only denominator. "
                         "MEMORY_PROTOCOL section 5 warns this flatters model-written "
                         "representations; reported only as a comparator.")
        out[str(rep)] = Estimate(
            point, lo, hi, n_units=len(group), n_obs=len(group),
            method="mean dU per 1000 exposed tokens (ratio of totals)",
            scale="delta_per_1k_tokens", flags=flags,
            extra={"representation": str(rep),
                   "amortized_formation_tokens_per_cell": extra_tok,
                   "include_formation": include_formation},
        )
    return out


# ==============================================================  the whole report
def efficiency_report(
    rows: Iterable[Mapping[str, Any]],
    cells: Sequence[CellStat] | None = None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    allow_pooling: bool = False,
) -> dict[str, Any]:
    """All seven families plus the derived metrics, in one dict."""
    adm = admit_rows(rows)
    data = adm.rows
    flags = require_homogeneous(data, allow_pooling=allow_pooling)
    if not data:
        return {"flags": flags + ["NO_ADMITTED_ROWS"], "admission": adm.to_dict()}

    report: dict[str, Any] = {
        "admission": adm.to_dict(),
        "flags": flags,
        "families": {
            "storage": storage_metrics(data),
            "retrieval": retrieval_metrics(data),
            "exposure": exposure_metrics(data),
            "latency": latency_metrics(data),
            "api_compute": api_compute_metrics(data),
            "selectivity": selectivity_metrics(data, cells),
            "extraction": extraction_metrics(data),
        },
        "formation_cost": {k: v.to_dict() for k, v in formation_cost(data).items()},
        "compression_ratio": compression_ratio(data),
    }
    if cells:
        report["utility_per_exposed_token_with_formation"] = {
            k: v.to_dict() for k, v in utility_per_exposed_token(
                cells, data, n_boot=n_boot, seed=seed, include_formation=True).items()
        }
        report["utility_per_exposed_token_exposure_only"] = {
            k: v.to_dict() for k, v in utility_per_exposed_token(
                cells, data, n_boot=n_boot, seed=seed, include_formation=False).items()
        }
        report["formation_cost_note"] = (
            "The two utility-per-token tables differ ONLY by whether amortized formation "
            "tokens are in the denominator. MEMORY_PROTOCOL section 5 requires the "
            "charged version; the exposure-only version is shown so the size of the "
            "discount an uncharged comparison would hand the model-written "
            "representations is visible rather than argued about."
        )
    else:
        report["flags"].append(
            "NO_CELL_LABELS:selectivity and utility-per-token need labels from "
            "labels.cell_statistics; those metrics are omitted, not estimated"
        )
    return report


__all__ = [
    "FAMILIES", "NULL_IS_NOT_ZERO",
    "storage_metrics", "retrieval_metrics", "exposure_metrics", "latency_metrics",
    "api_compute_metrics", "selectivity_metrics", "extraction_metrics",
    "FormationCost", "formation_cost", "compression_ratio",
    "utility_per_exposed_token", "efficiency_report",
]

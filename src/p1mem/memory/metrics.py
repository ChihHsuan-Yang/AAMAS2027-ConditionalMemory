"""Compression and formation-cost accounting per representation (B5).

``docs/MEMORY_PROTOCOL.md`` §5: "Writing is not free and its cost belongs to
the representation being compared. ... The efficiency frontier must charge
each representation for its own formation cost, or it flatters the
model-written ones."

**Raw's zero is a measurement, and it must survive into the table.** Raw costs
0 calls and 0 extraction tokens. That is its real advantage and the honest
counterweight to its token bulk: summary and structured buy their small
context footprint with a call apiece, and a frontier that omits the call makes
them look free.

Three separate zeros, never merged
----------------------------------
``extraction_calls = 0``
    a measured fact about raw. Summed, averaged, and reported as 0.
``extraction_latency_s = None``
    NO CALL WAS MADE. Excluded from the denominator of a mean latency, never
    averaged in as 0.0. A mean latency over raw+summary that treats raw as 0.0
    reports a number that describes nothing.
``reasoning_tokens = None``
    NOT REPORTED BY THIS CLUSTER (Sophia omits ``completion_tokens_details``).
    Also excluded, for a different reason, and the two reasons are kept
    distinct in the output so a reader can tell "no call" from "no telemetry".

Every mean in :class:`RepresentationStats` therefore carries its own ``n``, so
a reader can see what each average was taken over instead of assuming it was
taken over everything.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = ["RepresentationStats", "summarise", "frontier_table", "quantiles"]


def quantiles(values: Sequence[float]) -> dict[str, float] | None:
    """Distribution summary. Same shape as ``scripts/build_lmev2_units.py``'s."""
    xs = sorted(float(v) for v in values if v is not None)
    if not xs:
        return None

    def q(p: float) -> float:
        if len(xs) == 1:
            return xs[0]
        i = p * (len(xs) - 1)
        lo, hi = math.floor(i), math.ceil(i)
        return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)

    return {"n": len(xs), "min": xs[0], "p10": q(0.10), "p25": q(0.25),
            "median": q(0.50), "p75": q(0.75), "p90": q(0.90), "max": xs[-1],
            "mean": sum(xs) / len(xs), "total": sum(xs)}


def _mean_with_n(vals: Sequence[float | None]) -> tuple[float | None, int]:
    """Mean over the NON-NULL values, plus how many there were.

    Returning the n alongside is the point: a mean whose denominator is
    invisible invites the reader to assume it covers every item.
    """
    xs = [float(v) for v in vals if v is not None]
    return ((sum(xs) / len(xs)) if xs else None), len(xs)


@dataclass(slots=True)
class RepresentationStats:
    representation: str
    n_segments: int
    n_ok: int
    n_failed: int
    failure_codes: dict[str, int] = field(default_factory=dict)

    memory_tokens: dict[str, float] | None = None
    source_tokens: dict[str, float] | None = None
    compression_ratio: dict[str, float] | None = None

    extraction_calls_total: int = 0
    extraction_calls_mean: float = 0.0
    extraction_input_tokens_total: int | None = None
    extraction_output_tokens_total: int | None = None
    extraction_reasoning_tokens_total: int | None = None
    n_with_reasoning_tokens: int = 0

    latency_mean_s: float | None = None
    latency_n: int = 0
    latency_total_s: float | None = None
    retry_total: int = 0
    cache_hits: int = 0

    semantic_types: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "representation": self.representation,
            "n_segments": self.n_segments,
            "n_ok": self.n_ok,
            "n_failed": self.n_failed,
            "failure_rate": (self.n_failed / self.n_segments) if self.n_segments else None,
            "failure_codes": self.failure_codes,
            "memory_tokens": self.memory_tokens,
            "source_tokens": self.source_tokens,
            "compression_ratio": self.compression_ratio,
            "extraction_calls_total": self.extraction_calls_total,
            "extraction_calls_mean": self.extraction_calls_mean,
            "extraction_input_tokens_total": self.extraction_input_tokens_total,
            "extraction_output_tokens_total": self.extraction_output_tokens_total,
            "extraction_reasoning_tokens_total": self.extraction_reasoning_tokens_total,
            "n_with_reasoning_tokens": self.n_with_reasoning_tokens,
            "latency_mean_s": self.latency_mean_s,
            "latency_n": self.latency_n,
            "_latency_n_note": (
                "mean is over latency_n calls, NOT over n_segments. Raw makes no call, "
                "so its latency is null and excluded -- averaging it in as 0.0 would "
                "report a number describing nothing."
            ),
            "latency_total_s": self.latency_total_s,
            "retry_total": self.retry_total,
            "cache_hits": self.cache_hits,
            "semantic_types": self.semantic_types,
        }


def summarise(records: Iterable[Any]) -> dict[str, RepresentationStats]:
    """Group :class:`MemoryRecord`s by representation and summarise each.

    Failed writes are INCLUDED in ``n_segments`` and in the cost totals: a
    write that failed after burning a call still cost that call, and dropping
    it would under-charge the representation whose failures are most expensive.
    Their token/compression figures are excluded, because a failed write has
    no memory text to measure.
    """
    by_rep: dict[str, list[Any]] = {}
    for r in records:
        by_rep.setdefault(r.representation, []).append(r)

    out: dict[str, RepresentationStats] = {}
    for rep, rs in by_rep.items():
        ok = [r for r in rs if r.ok]
        failed = [r for r in rs if not r.ok]
        lat_mean, lat_n = _mean_with_n([r.extraction_latency_s for r in rs])
        in_toks = [r.extraction_input_tokens for r in rs if r.extraction_input_tokens is not None]
        out_toks = [r.extraction_output_tokens for r in rs if r.extraction_output_tokens is not None]
        rsn = [r.extraction_reasoning_tokens for r in rs
               if r.extraction_reasoning_tokens is not None]
        lat_vals = [r.extraction_latency_s for r in rs if r.extraction_latency_s is not None]
        calls = sum(r.extraction_calls for r in rs)

        out[rep] = RepresentationStats(
            representation=rep,
            n_segments=len(rs), n_ok=len(ok), n_failed=len(failed),
            failure_codes=dict(Counter(r.error_code for r in failed if r.error_code)),
            memory_tokens=quantiles([r.memory_tokens for r in ok
                                     if r.memory_tokens is not None]),
            source_tokens=quantiles([r.source_tokens for r in ok
                                     if r.source_tokens is not None]),
            compression_ratio=quantiles([r.compression_ratio for r in ok
                                         if r.compression_ratio is not None]),
            extraction_calls_total=calls,
            extraction_calls_mean=(calls / len(rs)) if rs else 0.0,
            # None, not 0, when no call was made at all: "no calls" and
            # "calls that billed zero tokens" are different facts.
            extraction_input_tokens_total=sum(in_toks) if in_toks else (0 if calls else None),
            extraction_output_tokens_total=sum(out_toks) if out_toks else (0 if calls else None),
            extraction_reasoning_tokens_total=sum(rsn) if rsn else None,
            n_with_reasoning_tokens=len(rsn),
            latency_mean_s=lat_mean, latency_n=lat_n,
            latency_total_s=sum(lat_vals) if lat_vals else None,
            retry_total=sum(r.retry_count for r in rs),
            cache_hits=sum(1 for r in rs if r.cache_hit),
            semantic_types=dict(Counter(r.native_semantic_type for r in ok
                                        if r.native_semantic_type)),
        )
    return out


def frontier_table(stats: Mapping[str, RepresentationStats]) -> str:
    """Human-readable cost/compression table, raw first as the reference row."""
    order = [r for r in ("raw", "summary", "structured") if r in stats]
    order += [r for r in sorted(stats) if r not in order]

    head = (f"{'representation':<14}{'n':>5}{'ok':>5}{'memtok p50':>12}"
            f"{'compr p50':>11}{'calls':>7}{'in tok':>9}{'out tok':>9}"
            f"{'lat mean':>10}{'lat n':>7}{'retries':>9}")
    lines = [head, "-" * len(head)]
    for rep in order:
        s = stats[rep]
        mt = s.memory_tokens["median"] if s.memory_tokens else float("nan")
        cr = s.compression_ratio["median"] if s.compression_ratio else float("nan")
        it = s.extraction_input_tokens_total
        ot = s.extraction_output_tokens_total
        lm = s.latency_mean_s
        lines.append(
            f"{rep:<14}{s.n_segments:>5}{s.n_ok:>5}{mt:>12.0f}{cr:>11.3f}"
            f"{s.extraction_calls_total:>7}"
            f"{('-' if it is None else str(it)):>9}"
            f"{('-' if ot is None else str(ot)):>9}"
            f"{('  -' if lm is None else f'{lm:>10.3f}')}"
            f"{s.latency_n:>7}{s.retry_total:>9}")
    lines.append("")
    lines.append("'-' means NO CALL WAS MADE (raw), which is not the same as zero.")
    lines.append("lat n is the denominator of lat mean: raw contributes 0 calls, so its")
    lines.append("latency is excluded rather than averaged in as 0.0.")
    return "\n".join(lines)

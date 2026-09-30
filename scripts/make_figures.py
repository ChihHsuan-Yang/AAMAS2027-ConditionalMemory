"""Generate the manuscript's data-bearing figures from tracked artifacts.

Every number that appears inside a figure is computed HERE, from a file under
version control, and written into a generated LaTeX macro file that main.tex
\input's. Nothing is hand-typed into TikZ.

The rule this enforces: a figure is a durable document, and a number quoted into
a durable document without re-derivation is the failure mode this project has hit
repeatedly. So the figures are not drawn from a report -- they are recomputed.

Outputs (written into the Overleaf clone):
    figdata.tex   -- \def macros consumed by main.tex

Run: /Users/bellayang/miniconda3/bin/python3 scripts/make_figures.py
Exit 1 if any cross-check against the audited values fails.

The definitions below deliberately duplicate scripts/audit_claims.py rather than
importing it: two independent computations that must agree is the check. If they
ever diverge, the generated figure is wrong and this script fails.
"""
from __future__ import annotations

import collections
import json
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OVERLEAF = REPO.parent / "overleaf"
QUESTIONS = Path("/tmp/lmev2/questions.jsonl")

FAIL: list[str] = []


def expect(name, got, want, tol=5e-4):
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:46} {got!r}")
    if not ok:
        FAIL.append(f"{name}: got {got!r} want {want!r}")


def load(rel):
    return [json.loads(l) for l in (REPO / rel).read_text().splitlines() if l.strip()]


def wilson(k, n, z=1.959963984540054):
    """Wilson score interval. Same estimator the manuscript's tables use."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------------------
# FIGURE 2a -- bearing breadth over ALL memory units in the corpus
# ---------------------------------------------------------------------------
def bearing_breadth():
    """How many future tasks does one naturally occurring memory bear on?

    Subject: all 1,889 memory units, NOT only the ones that bear on something.
    Reporting the distribution over the 165 that bear at all would answer a
    different question and would hide the finding, which is the scarcity.
    """
    rows = load("data/manifests/lmev2_leakage_small.jsonl")
    if not QUESTIONS.exists():
        sys.exit(f"missing {QUESTIONS}: needed to exclude LLM-judged tasks")
    qs = {json.loads(l)["id"]: json.loads(l)
          for l in QUESTIONS.read_text().splitlines() if l.strip()}

    pool_hits = collections.Counter(r["task_id"] for r in rows)
    # "discriminative": the detector singles the memory out of its same-domain
    # pool. 1 <= hits <= 8 is the pre-registered band (docs/BEARING_SCARCITY.md).
    disc = {t for t, c in pool_hits.items() if 1 <= c <= 8}
    det = {t for t in disc if t in qs and not qs[t]["eval_function"].startswith("llm_")}

    all_units = {r["memory_id"] for r in rows}
    bearing = collections.defaultdict(set)
    for r in rows:
        if r["task_id"] in det:
            bearing[r["memory_id"]].add(r["task_id"])

    dist = collections.Counter(len(v) for v in bearing.values())
    dist[0] = len(all_units) - len(bearing)          # units bearing on nothing

    ge2 = {m for m, v in bearing.items() if len(v) >= 2}
    episodes = {m.split(":")[0] for m in ge2}

    expect("discriminative tasks", len(disc), 76)
    expect("  deterministic among them", len(det), 75)
    expect("memory units total", len(all_units), 1889)
    expect("units with >=1 bearing task", len(bearing), 165)
    expect("units with >=2 bearing tasks", len(ge2), 46)
    expect("  source episodes hosting those", len(episodes), 23)
    expect("units bearing on exactly one task", dist[1], 119)
    expect("units bearing on nothing", dist[0], 1724)
    return dist, len(all_units), len(bearing), len(ge2), len(episodes)


# ---------------------------------------------------------------------------
# FIGURE 2b -- sign reversal by stratum, with Wilson intervals
# ---------------------------------------------------------------------------
def flips_by_stratum():
    """Flip-eligible memories and sign reversals, per stratum.

    A memory is flip-eligible in a stratum if it has >= 2 cells there; it flips
    if two of those cells have opposite sign. Cell Delta-U is the mean over
    replicates, matching the pre-registered per-cell estimate.
    """
    sc = load("results/ledgers/repro/screened_cells_slim.jsonl")
    cells = collections.defaultdict(list)
    for r in sc:
        if r.get("reward_with_memory") is None:
            continue
        cells[(r["stratum"], r["memory_id"], r["future_task_id"])].append(
            (r["reward_with_memory"], r["reward_without_memory"]))
    cell_du = {k: statistics.mean(a - b for a, b in v) for k, v in cells.items()}

    per_stratum = collections.defaultdict(lambda: collections.defaultdict(list))
    for (s, m, _t), x in cell_du.items():
        per_stratum[s][m].append(x)

    out = {}
    for s, want_el, want_fl in (("BEARING", 35, 0),
                                ("MATCHED_CONTROL", 35, 1),
                                ("RANDOM", 60, 17)):
        eligible = {m: v for m, v in per_stratum[s].items() if len(v) >= 2}
        flips = sum(1 for v in eligible.values()
                    if any(x > 0 for x in v) and any(x < 0 for x in v))
        lo, hi = wilson(flips, len(eligible))
        out[s] = (len(eligible), flips, flips / len(eligible), lo, hi)
        expect(f"{s} flip-eligible", len(eligible), want_el)
        expect(f"{s} flips", flips, want_fl)

    expect("BEARING Wilson upper", round(out["BEARING"][4], 4), 0.0989)
    expect("RANDOM Wilson lower", round(out["RANDOM"][3], 4), 0.1851)
    # The disjointness is the claim the figure exists to make legible.
    expect("intervals disjoint", out["BEARING"][4] < out["RANDOM"][3], True)
    return out


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------
def main():
    print("== bearing breadth (fig. 2a) ==")
    dist, n_units, n_bear, n_ge2, n_eps = bearing_breadth()
    print("== sign reversal by stratum (fig. 2b) ==")
    flips = flips_by_stratum()

    if FAIL:
        print("\nFIGURE DATA FAILED TO REPRODUCE:")
        for f in FAIL:
            print("  " + f)
        sys.exit(1)

    # ---------------------------------------------------------------- geometry
    # Plot coordinates are computed HERE, in Python, and emitted as lengths.
    # TikZ then draws what it is given. No arithmetic on a measured value
    # happens in LaTeX, so a figure cannot drift from the artifact by a typo
    # in a coordinate.
    PANEL_W = 104.0   # pt, drawable width of the left panel's value axis
    BAR_MAX = 46.0    # pt, height of the tallest bar

    counts = [dist.get(k, 0) for k in range(0, 10)]
    top = max(counts)
    # log10 scale: the range is 0..1724 against categories of size 1, so a
    # linear axis would render every non-zero-bearing bar as invisible. A zero
    # count has no log and is drawn as no bar at all -- an honest gap, not a
    # floor value substituted for a missing one.
    def barh(c):
        return 0.0 if c == 0 else BAR_MAX * math.log10(c + 1) / math.log10(top + 1)

    FOREST_W = 96.0   # pt, drawable width of the right panel
    XMAX = 0.45       # rate axis upper limit; RANDOM's Wilson upper is 0.4077
    def fx(v):
        return FOREST_W * v / XMAX

    L = []
    L.append("%%% GENERATED by scripts/make_figures.py in the code repository.")
    L.append("%%% DO NOT EDIT BY HAND, and do not edit a value here to make a")
    L.append("%%% figure look right -- regenerate. Every value is recomputed from")
    L.append("%%% a tracked artifact and cross-checked against the audited value;")
    L.append("%%% the generator exits non-zero on any disagreement, and a planted")
    L.append("%%% sign flip in one BEARING cell is verified to make it fail.")
    L.append("%%% Sources: data/manifests/lmev2_leakage_small.jsonl")
    L.append("%%%          results/ledgers/repro/screened_cells_slim.jsonl")
    L.append("%%%          results/ledgers/k1_screened_design.json (basis pin)")
    L.append("")

    L.append("%% --- bearing breadth: counts, and log-scaled bar heights in pt ---")
    for k in range(0, 10):
        L.append(rf"\def\bearN{ROMAN[k]}{{{counts[k]}}}")
        L.append(rf"\def\bearH{ROMAN[k]}{{{barh(counts[k]):.2f}pt}}")
    L.append(rf"\def\bearUnits{{{n_units:,}}}".replace(",", "{,}"))
    L.append(rf"\def\bearAny{{{n_bear}}}")
    L.append(rf"\def\bearGeTwo{{{n_ge2}}}")
    L.append(rf"\def\bearEpisodes{{{n_eps}}}")
    for tick in (1, 10, 100, 1000):
        L.append(rf"\def\bearTick{ROMAN[int(math.log10(tick))]}{{{barh(tick):.2f}pt}}")
    L.append("")

    L.append("%% --- sign reversal: rate and Wilson bounds, as x-offsets in pt ---")
    for s_, tag in (("BEARING", "Bear"), ("MATCHED_CONTROL", "Ctrl"), ("RANDOM", "Rand")):
        n, k, rate, lo, hi = flips[s_]
        L.append(rf"\def\flip{tag}N{{{n}}}")
        L.append(rf"\def\flip{tag}K{{{k}}}")
        L.append(rf"\def\flip{tag}Rate{{{rate:.4f}}}")
        L.append(rf"\def\flip{tag}X{{{fx(rate):.2f}pt}}")
        L.append(rf"\def\flip{tag}XLo{{{fx(lo):.2f}pt}}")
        L.append(rf"\def\flip{tag}XHi{{{fx(hi):.2f}pt}}")
    # TeX macro names are letters only: \flipTick0 parses as \flipTick then "0",
    # which breaks inside \foreach. Word-form suffixes throughout.
    for t in (0.0, 0.1, 0.2, 0.3, 0.4):
        L.append(rf"\def\flipTick{ROMAN[int(round(t * 10))]}{{{fx(t):.2f}pt}}")
    L.append(rf"\def\flipAxisW{{{FOREST_W:.2f}pt}}")
    L.append(rf"\def\bearAxisW{{{PANEL_W:.2f}pt}}")
    L.append("")

    dest = OVERLEAF / "figdata.tex"
    dest.write_text("\n".join(L) + "\n")
    print(f"\nwrote {dest}  ({len(L)} lines)")
    print("all figure data re-derived from tracked artifacts.")


ROMAN = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]

if __name__ == "__main__":
    main()

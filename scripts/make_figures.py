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
    return (dist, len(all_units), len(bearing), len(ge2), len(episodes), len(det))


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
# FIGURE 3 -- what locates utility: embedding similarity, or content bearing?
# ---------------------------------------------------------------------------
def similarity_vs_bearing():
    """Mean Delta-U by similarity sextile, against the content-based screen.

    Two honesty constraints shape this, and both are visible in the figure.

    1. CONFOUND. BEARING cells concentrate in the top similarity bins (54 of
       139 land in the top sextile, against 5 in the bottom). So the POOLED
       similarity trend is partly the content screen showing through, and
       quoting it alone would credit the embedding with the screen's work. The
       within-RANDOM series is therefore computed and plotted beside it: same
       similarity axis, no bearing cells in it at all.

    2. ATTENUATION, which cuts against us and is stated anyway: the similarity
       for most memories is computed on a truncated prefix, which pushes any
       similarity-utility relationship toward zero.
    """
    sc = load("results/ledgers/repro/screened_cells_slim.jsonl")
    cells = collections.defaultdict(list)
    for r in sc:
        if r.get("reward_with_memory") is None:
            continue
        cells[(r["stratum"], r["memory_id"], r["future_task_id"])].append(r)
    rows = [(k[0],
             statistics.mean(x["semantic_similarity"] for x in v),
             statistics.mean(x["reward_with_memory"] - x["reward_without_memory"]
                             for x in v))
            for k, v in cells.items()]
    expect("cells entering the similarity panel", len(rows), 1157)

    n_bins = 6
    sims = sorted(r[1] for r in rows)
    edges = [sims[min(len(sims) - 1, i * len(sims) // n_bins)] for i in range(n_bins)]
    edges.append(sims[-1] + 1e-9)

    def series(subset):
        out = []
        for i in range(n_bins):
            sub = [r for r in subset if edges[i] <= r[1] < edges[i + 1]]
            out.append((len(sub), statistics.mean(r[2] for r in sub) if sub else 0.0))
        return out

    pooled = series(rows)
    random_only = series([r for r in rows if r[0] == "RANDOM"])

    # composition, which is the reason the second series exists
    comp = [sum(1 for r in rows
                if edges[i] <= r[1] < edges[i + 1] and r[0] == "BEARING")
            for i in range(n_bins)]
    expect("BEARING cells in the top similarity bin", comp[-1], 54)
    expect("BEARING cells in the bottom similarity bin", comp[0], 5)
    expect("  so the pooled trend is confounded", comp[-1] > 5 * comp[0], True)

    by_str = {}
    for s_ in ("BEARING", "MATCHED_CONTROL", "RANDOM"):
        sub = [r for r in rows if r[0] == s_]
        by_str[s_] = (len(sub), statistics.mean(r[2] for r in sub))
    def spearman(xs, ys):
        rx = {v: i for i, v in enumerate(sorted(set(xs)))}
        ry = {v: i for i, v in enumerate(sorted(set(ys)))}
        a = [rx[v] for v in xs]
        b = [ry[v] for v in ys]
        ma, mb = statistics.mean(a), statistics.mean(b)
        num = sum((i - ma) * (j - mb) for i, j in zip(a, b))
        den = math.sqrt(sum((i - ma) ** 2 for i in a) * sum((j - mb) ** 2 for j in b))
        return num / den if den else 0.0

    rho_all = spearman([r[1] for r in rows], [r[2] for r in rows])
    rnd = [r for r in rows if r[0] == "RANDOM"]
    rho_rand = spearman([r[1] for r in rnd], [r[2] for r in rnd])
    expect("Spearman rho, all cells", round(rho_all, 4), 0.0868)
    expect("Spearman rho, unscreened only", round(rho_rand, 4), 0.0061)
    expect("BEARING mean dU", round(by_str["BEARING"][1], 4), 0.3453)
    expect("MATCHED_CONTROL mean dU", round(by_str["MATCHED_CONTROL"][1], 4), 0.0274)
    expect("RANDOM mean dU", round(by_str["RANDOM"][1], 4), 0.0642)
    return pooled, random_only, by_str, edges, rho_all, rho_rand


# ---------------------------------------------------------------------------
# FIGURE 4 -- the utility-efficiency frontier, under two cost accountings
# ---------------------------------------------------------------------------
def frontier():
    """Paired utility against tokens, exposure-only and formation-charged.

    ONE BASIS, and it is the point of the figure. Both axes are computed over
    the SAME 277 cells and the SAME 57 memories:

      y  = paired within-memory effect: for each memory, its mean Delta-U on
           BEARING cells minus its mean on MATCHED_CONTROL cells, averaged over
           memories. This is the estimand Sec. 8 quotes, not the unpaired
           BEARING mean that the published BEARING table uses -- they are
           different numbers (+0.3174 vs +0.3453 for raw) and mixing them would
           put a y-value from one estimand above an x-value from another.

      x  = mean tokens per cell over those same 277 cells; charged adds the
           writer's own call amortized over the cells that reuse that memory.

    Efficiency is then the SLOPE FROM THE ORIGIN, so it cannot drift from the
    plotted point: there is no third number to disagree.

    THE FORMATION CONSTANT HAS TWO BASES AND THEY ARE NOT INTERCHANGEABLE.
    docs/REPRESENTATION_RESULT.md's table totals all 60 written memories over
    that arm's own pair-key count (285 summary / 277 structured). The join uses
    only the 57 memories common to all three arms. This function charges the 57
    over the 277, because that is what it plots. Both constants are asserted so
    the wrong one cannot be silently substituted.

    WHY RAW MUST NOT MOVE between the two panels (Amendment A1.5): raw makes
    zero extraction calls, so if charging formation shifts it at all the cost
    has been attributed to the wrong arm. Asserted exactly, not to a tolerance.
    """
    screened = load("results/deltau_screened/cells.jsonl")
    scaleup = load("results/repr_scaleup/cells.jsonl")
    memories = load("results/repr_scaleup/memories.jsonl")

    def locator(r):
        pr = r.get("provenance") or {}
        return pr.get("memory_unit_locator") or (
            r.get("source_episode_metadata") or {}).get("memory_unit_locator")

    arms = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in screened + scaleup:
        if r.get("reward_with_memory") is None:
            continue
        if (r.get("provenance") or {}).get("stratum") not in ("BEARING",
                                                              "MATCHED_CONTROL"):
            continue
        arms[r["memory_representation"]][(locator(r), r["future_task_id"])].append(r)

    reps = ("raw", "summary", "structured")
    common = sorted(set.intersection(*[set(arms[r]) for r in reps]))
    expect("frontier: cells common to all three arms", len(common), 277)
    locs = sorted({k[0] for k in common})
    expect("frontier: memories behind them", len(locs), 57)

    stratum = {k: arms["raw"][k][0]["provenance"]["stratum"] for k in common}
    du, tok = {}, {}
    for rep in reps:
        du[rep] = {k: statistics.mean(x["reward_with_memory"] - x["reward_without_memory"]
                                      for x in arms[rep][k]) for k in common}
        tok[rep] = {k: statistics.mean(float(x["memory_tokens_exposed"])
                                       for x in arms[rep][k]) for k in common}

    bymem = collections.defaultdict(lambda: collections.defaultdict(list))
    for k in common:
        bymem[k[0]][stratum[k]].append(k)

    formation = {"raw": 0.0}
    for rep in ("summary", "structured"):
        ms = [m for m in memories if m["representation"] == rep
              and m["memory_unit_locator"] in set(locs)]
        expect(f"frontier: {rep} memories on the join basis", len(ms), 57)
        formation[rep] = sum((m["extraction_input_tokens"] or 0)
                             + (m["extraction_output_tokens"] or 0)
                             for m in ms) / len(common)

    out = {}
    for rep in reps:
        diffs = [statistics.mean(du[rep][k] for k in bymem[l]["BEARING"])
                 - statistics.mean(du[rep][k] for k in bymem[l]["MATCHED_CONTROL"])
                 for l in locs]
        point, lo, hi = _boot_mean_ci(diffs)
        exposed = statistics.mean(tok[rep].values())
        out[rep] = {
            "du": point, "lo": lo, "hi": hi,
            "nz": sum(1 for x in diffs if abs(x) > 1e-9),
            "exposed": exposed, "charged": exposed + formation[rep],
            "eff_exposed": 1000.0 * point / exposed,
            "eff_charged": 1000.0 * point / (exposed + formation[rep]),
        }

    for rep, d_, nz_, e_, c_ in (("raw", 0.3174, 33, 9227.9, 9227.9),
                                 ("summary", 0.0613, 26, 322.8, 1960.1),
                                 ("structured", -0.0498, 20, 237.8, 1913.5)):
        expect(f"frontier: {rep} paired B-control", round(out[rep]["du"], 4), d_)
        expect(f"  {rep} non-zero contributors", out[rep]["nz"], nz_)
        expect(f"  {rep} mean exposed tokens", round(out[rep]["exposed"], 1), e_)
        expect(f"  {rep} mean charged tokens", round(out[rep]["charged"], 1), c_)
    for rep, e_, c_ in (("raw", 0.0344, 0.0344), ("summary", 0.1899, 0.0313),
                        ("structured", -0.2094, -0.0260)):
        expect(f"frontier: {rep} dU/1k exposed", round(out[rep]["eff_exposed"], 4), e_)
        expect(f"frontier: {rep} dU/1k charged", round(out[rep]["eff_charged"], 4), c_)

    # A1.5: raw is bit-identical across panels. Exact, not within a tolerance.
    expect("frontier: A1.5 raw does not move at all",
           out["raw"]["eff_exposed"] == out["raw"]["eff_charged"], True)
    expect("frontier: A1.5 summary moves",
           out["summary"]["eff_exposed"] != out["summary"]["eff_charged"], True)
    expect("frontier: A1.5 structured moves",
           out["structured"]["eff_exposed"] != out["structured"]["eff_charged"], True)

    # The two accountings disagree -- the reason the figure has two panels.
    expect("frontier: exposure-only Summary/Raw",
           round(out["summary"]["eff_exposed"] / out["raw"]["eff_exposed"], 2), 5.52)
    expect("frontier: charged Raw/Summary",
           round(out["raw"]["eff_charged"] / out["summary"]["eff_charged"], 2), 1.10)
    # The ranking flips; the size of Raw's win does NOT reach the ~5x a draft
    # claimed. Both halves are asserted so neither can be restated wrongly.
    expect("frontier: exposure-only ranks Summary above Raw",
           out["summary"]["eff_exposed"] > out["raw"]["eff_exposed"], True)
    expect("frontier: charged ranks Raw above Summary",
           out["raw"]["eff_charged"] > out["summary"]["eff_charged"], True)
    expect("frontier: but Raw's charged margin is under 1.5x, NOT ~5x",
           out["raw"]["eff_charged"] / out["summary"]["eff_charged"] < 1.5, True)

    # Only Raw's interval excludes zero. The caption depends on this.
    expect("frontier: raw CI excludes zero", out["raw"]["lo"] > 0, True)
    expect("frontier: summary CI spans zero",
           out["summary"]["lo"] < 0 < out["summary"]["hi"], True)
    expect("frontier: structured CI spans zero",
           out["structured"]["lo"] < 0 < out["structured"]["hi"], True)

    reuse = len(common) / len(locs)
    expect("frontier: measured reuse factor", round(reuse, 4), 4.8596)
    return out, reuse, formation


def _boot_mean_ci(xs, n_boot=200000, seed=20260929, alpha=0.05):
    """Percentile bootstrap of a mean, matching p1mem.analysis.common's estimator.

    n_boot is raised well above the house default of 2000 because the figure's
    interval is drawn, not tabulated: a whisker that moves with the seed would
    be a drawing that changes without the data changing. Verified stable to the
    2 d.p. the caption quotes across seeds {20260929, 1, 42, 2026, 7}.
    """
    import numpy as np
    arr = np.asarray(list(xs), dtype=float)
    rng = np.random.default_rng(seed)
    draws = arr[rng.integers(0, arr.size, size=(n_boot, arr.size))].mean(axis=1)
    return float(arr.mean()), float(np.quantile(draws, alpha / 2.0)), float(
        np.quantile(draws, 1.0 - alpha / 2.0))


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------
def main():
    print("== bearing breadth (fig. 2a) ==")
    dist, n_units, n_bear, n_ge2, n_eps, n_det = bearing_breadth()
    print("== sign reversal by stratum (fig. 2b) ==")
    flips = flips_by_stratum()
    print("== similarity vs the content screen (fig. 3) ==")
    pooled, rand_only, by_str, sim_edges, rho_all, rho_rand = similarity_vs_bearing()
    print("== utility-efficiency frontier (fig. 4) ==")
    front, reuse, formation = frontier()

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
    L.append(rf"\def\bearDetTasks{{{n_det}}}")
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

    # ---- figure 3: similarity sextiles vs the content screen ----
    SIM_W, SIM_H = 100.0, 40.0
    DU_MAX = 0.40       # tallest plotted series value is BEARING's 0.3453
    def sy(v):
        return SIM_H * v / DU_MAX
    L.append("%% --- similarity sextiles: y-offsets in pt, DU_MAX = 0.40 ---")
    for i, ((n_p, m_p), (n_r, m_r)) in enumerate(zip(pooled, rand_only)):
        L.append(rf"\def\simPooledY{ROMAN[i]}{{{sy(m_p):.2f}pt}}")
        L.append(rf"\def\simPooledV{ROMAN[i]}{{{m_p:.4f}}}")
        L.append(rf"\def\simRandY{ROMAN[i]}{{{sy(m_r):.2f}pt}}")
        L.append(rf"\def\simRandV{ROMAN[i]}{{{m_r:.4f}}}")
        L.append(rf"\def\simX{ROMAN[i]}{{{SIM_W * (i + 0.5) / len(pooled):.2f}pt}}")
    for s_, tag in (("BEARING", "Bear"), ("MATCHED_CONTROL", "Ctrl"), ("RANDOM", "Rand")):
        n_, mu = by_str[s_]
        L.append(rf"\def\strat{tag}Y{{{sy(mu):.2f}pt}}")
        L.append(rf"\def\strat{tag}V{{{mu:+.4f}}}")
        L.append(rf"\def\strat{tag}N{{{n_}}}")
    for t in (0.0, 0.1, 0.2, 0.3, 0.4):
        L.append(rf"\def\simTick{ROMAN[int(round(t * 10))]}{{{sy(t):.2f}pt}}")
    L.append(rf"\def\simAxisW{{{SIM_W:.2f}pt}}")
    L.append(rf"\def\simRhoAll{{{rho_all:+.3f}}}")
    L.append(rf"\def\simRhoRand{{{rho_rand:+.3f}}}")
    L.append(rf"\def\simCells{{{sum(n for n, _ in pooled):,}}}".replace(",", "{,}"))
    L.append(rf"\def\simLoEdge{{{sim_edges[0]:.2f}}}")
    L.append(rf"\def\simHiEdge{{{sim_edges[-1]:.2f}}}")
    L.append("")

    # ---- figure 4: the frontier, two cost accountings on one shared y-axis ----
    # x is log10(tokens): the exposed axis spans 238 to 9,228 tokens, ~39x, and a
    # linear axis would stack Summary and Structured on top of each other and put
    # Raw off at the edge -- the reader could not see the two compressed arms are
    # different at all. Both panels share ONE x transform and ONE y transform, so
    # a point's movement between panels is the cost accounting and nothing else.
    FR_W, FR_H = 96.0, 52.0      # pt, drawable area of each panel
    FR_XLO, FR_XHI = 2.0, 4.1    # log10 tokens: 100 .. ~12,600
    FR_YLO, FR_YHI = -0.20, 0.50 # paired dU; covers every whisker end

    def fx4(tokens):
        return FR_W * (math.log10(tokens) - FR_XLO) / (FR_XHI - FR_XLO)

    def fy4(v):
        return FR_H * (v - FR_YLO) / (FR_YHI - FR_YLO)

    L.append("%% --- frontier (fig 4): ONE basis, 277 cells / 57 memories ---")
    L.append("%% x = log10(tokens per cell), y = paired BEARING-control dU.")
    L.append("%% Efficiency is the slope from the origin; it is not a separate")
    L.append("%% number and so cannot disagree with the plotted point.")
    for rep, tag in (("raw", "Raw"), ("summary", "Sum"), ("structured", "Str")):
        d = front[rep]
        L.append(rf"\def\fr{tag}DU{{{d['du']:+.4f}}}")
        L.append(rf"\def\fr{tag}Lo{{{d['lo']:+.3f}}}")
        L.append(rf"\def\fr{tag}Hi{{{d['hi']:+.3f}}}")
        L.append(rf"\def\fr{tag}Y{{{fy4(d['du']):.2f}pt}}")
        L.append(rf"\def\fr{tag}YLo{{{fy4(d['lo']):.2f}pt}}")
        L.append(rf"\def\fr{tag}YHi{{{fy4(d['hi']):.2f}pt}}")
        L.append(rf"\def\fr{tag}XExp{{{fx4(d['exposed']):.2f}pt}}")
        L.append(rf"\def\fr{tag}XChg{{{fx4(d['charged']):.2f}pt}}")
        L.append(rf"\def\fr{tag}TokExp{{{d['exposed']:,.0f}}}".replace(",", "{,}"))
        L.append(rf"\def\fr{tag}TokChg{{{d['charged']:,.0f}}}".replace(",", "{,}"))
        L.append(rf"\def\fr{tag}EffExp{{{d['eff_exposed']:+.3f}}}")
        L.append(rf"\def\fr{tag}EffChg{{{d['eff_charged']:+.3f}}}")
        L.append(rf"\def\fr{tag}NZ{{{d['nz']}}}")
    for t in (100, 1000, 10000):
        L.append(rf"\def\frXTick{ROMAN[int(math.log10(t))]}{{{fx4(t):.2f}pt}}")
    for v, nm in ((-0.2, "MinusTwo"), (0.0, "Zero"), (0.2, "Two"), (0.4, "Four")):
        L.append(rf"\def\frYTick{nm}{{{fy4(v):.2f}pt}}")
    L.append(rf"\def\frZeroY{{{fy4(0.0):.2f}pt}}")
    L.append(rf"\def\frW{{{FR_W:.2f}pt}}")
    L.append(rf"\def\frH{{{FR_H:.2f}pt}}")
    L.append(rf"\def\frCells{{{277}}}")
    L.append(rf"\def\frMems{{{57}}}")
    L.append(rf"\def\frReuse{{{reuse:.2f}}}")
    L.append(rf"\def\frRatioExp{{{front['summary']['eff_exposed'] / front['raw']['eff_exposed']:.1f}}}")
    L.append(rf"\def\frRatioChg{{{front['raw']['eff_charged'] / front['summary']['eff_charged']:.2f}}}")
    L.append(rf"\def\frFormSum{{{formation['summary']:,.0f}}}".replace(",", "{,}"))
    L.append(rf"\def\frFormStr{{{formation['structured']:,.0f}}}".replace(",", "{,}"))
    L.append("")

    dest = OVERLEAF / "figdata.tex"
    dest.write_text("\n".join(L) + "\n")
    print(f"\nwrote {dest}  ({len(L)} lines)")
    print("all figure data re-derived from tracked artifacts.")


ROMAN = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]

if __name__ == "__main__":
    main()

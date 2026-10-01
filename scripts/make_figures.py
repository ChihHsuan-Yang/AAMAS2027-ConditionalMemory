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
# FIGURE 1b -- THE CENTRAL CLAIM: utility is sparse across future tasks
# ---------------------------------------------------------------------------
def sparsity_map():
    """Per-cell measured utility for every screened cell, laid out by stratum.

    THE PAPER'S CENTRAL CLAIM HAD NO FIGURE. "A global memory score is
    insufficient because utility is sparse across future tasks" was carried
    only by table rows. This draws the cell-level evidence directly: one small
    square per MEASURED cell, 1,157 of them, grouped into the three strata.

    FOUR DESIGN CONSTRAINTS, each forced by a property of the real data that
    was checked before the figure was drawn rather than assumed.

    1. dU TAKES EXACTLY THREE VALUES, -1, 0 and +1. Both replicates of every
       cell agree (0/1157 disagree), and the reward is binary, so the cell
       mean cannot land between them. A continuous colour ramp would therefore
       be a ramp over three levels and would imply a precision the measurement
       does not have. Three discrete marks instead. ASSERTED below: if a
       fourth level ever appears the build fails, because the legend would
       then be describing a scale the data no longer has.

    2. UNMEASURED SLOTS MUST NOT BE DRAWN, AND THE REASON IS ARITHMETIC. The
       strata have different per-memory widths (max 9 / 9 / 15 cells), so a
       memory's row is RAGGED. Pad the rows to a rectangle and the eye reads
       dark marks per unit AREA, which is 9.3% for BEARING against 9.1% for
       RANDOM -- indistinguishable, and the opposite of the finding. The
       honest quantity is dark marks per DRAWN square: 36.0% against 9.4%.
       The ratio of the two readings is asserted below, so a later edit that
       pads the grid cannot pass silently.

    3. A MEASURED ZERO IS DRAWN, AN ABSENT CELL IS NOT. This project's own
       recorded defect shape is an absence rendered as a value. A measured
       zero is a real finding -- the reader scored the same with and without
       the memory -- and gets a visible light square; a cell that was never
       run gets nothing at all. The two must not share an appearance.

    4. THE ROW ORDER IS FIXED BY THE DATA, NOT CHOSEN. Memories are sorted by
       their BEARING-stratum positive count, descending. Sorting rows by a
       quantity the figure then displays is circular IF the claim were about
       which memories rank highest; it is not -- the claim is about the
       CONTRAST BETWEEN STRATUM BLOCKS, and the sort is applied identically to
       all three blocks of every row. The sort is therefore disclosed in the
       caption and the stratum contrast is also reported as a number the sort
       cannot touch (positive RATE per stratum, with Wilson intervals).
    """
    sc = load("results/ledgers/repro/screened_cells_slim.jsonl")

    # One representation, one reader: this figure is about memory x task, and
    # pooling representations or readers here would make the sparsity a mix of
    # three different measurements.
    reps = {r["memory_representation"] for r in sc}
    readers = {r["reader_model"] for r in sc}
    if reps != {"raw"}:
        FAIL.append(f"sparsity: the screened rows carry representations {reps}; "
                    "the figure's caption says one representation (raw)")
    if readers != {GPTOSS_READER_ID}:
        FAIL.append(f"sparsity: the screened rows carry readers {readers}; the "
                    "caption says a single frozen reader")

    cells = collections.defaultdict(list)
    for r in sc:
        if r.get("reward_with_memory") is None:
            continue
        cells[(r["stratum"], r["memory_id"], r["future_task_id"])].append(r)
    du = {k: statistics.mean(x["reward_with_memory"] - x["reward_without_memory"]
                             for x in v) for k, v in cells.items()}
    expect("sparsity: measured cells", len(du), 1157)

    # ---- constraint 1: the scale really is three-valued.
    levels = sorted({round(v, 6) for v in du.values()})
    expect("sparsity: distinct dU levels", levels, [-1.0, 0.0, 1.0])
    if len(levels) != 3:
        FAIL.append(f"sparsity: dU now takes {len(levels)} distinct values "
                    f"{levels}; the figure draws THREE discrete marks and its "
                    "legend would be describing a scale the data no longer has")
    # The three-valuedness is a consequence of replicate agreement. If
    # replicates ever disagree the cell mean lands between levels, so assert
    # the cause as well as the effect -- a figure whose premise has changed is
    # wrong even while its current numbers still render.
    disagree = sum(1 for v in cells.values()
                   if len({x["reward_with_memory"] - x["reward_without_memory"]
                           for x in v}) > 1)
    expect("sparsity: cells whose replicates disagree", disagree, 0)

    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for (s, m, t), v in du.items():
        per[m][s].append(v)
    mems = sorted(per)
    expect("sparsity: memories", len(mems), 60)
    # Every memory appears in every stratum -- that is what makes the three
    # blocks a paired within-memory comparison rather than three samples.
    if any(len(per[m]) != 3 for m in mems):
        FAIL.append("sparsity: some memory is missing a stratum; the figure's "
                    "three blocks are drawn as a within-memory comparison")

    STRATA = ("BEARING", "MATCHED_CONTROL", "RANDOM")
    width = {s: max(len(per[m][s]) for m in mems) for s in STRATA}
    expect("sparsity: block widths", [width[s] for s in STRATA], [9, 9, 15])

    stats = {}
    for s in STRATA:
        vals = [v for m in mems for v in per[m][s]]
        k = sum(1 for v in vals if v > 0)
        lo, hi = wilson(k, len(vals))
        stats[s] = {"n": len(vals), "pos": k,
                    "neg": sum(1 for v in vals if v < 0),
                    "zero": sum(1 for v in vals if v == 0),
                    "rate": k / len(vals), "lo": lo, "hi": hi,
                    "slots": len(mems) * width[s]}
    for s, n_, k_ in (("BEARING", 139, 50), ("MATCHED_CONTROL", 146, 10),
                      ("RANDOM", 872, 82)):
        expect(f"sparsity {s}: measured cells", stats[s]["n"], n_)
        expect(f"sparsity {s}: positive cells", stats[s]["pos"], k_)

    # ---- constraint 2: the padding trap, asserted as a number.
    # Per DRAWN square BEARING is ~3.8x RANDOM; per BLOCK AREA it is ~1.0x.
    # If a later edit pads the grid, the figure stops showing the finding
    # while still containing every correct value. That is this project's
    # "true about the wrong subject" shape, so both readings are computed and
    # the gap between them is required to persist.
    drawn_ratio = stats["BEARING"]["rate"] / stats["RANDOM"]["rate"]
    area_b = stats["BEARING"]["pos"] / stats["BEARING"]["slots"]
    area_r = stats["RANDOM"]["pos"] / stats["RANDOM"]["slots"]
    area_ratio = area_b / area_r
    expect("sparsity: BEARING/RANDOM positive rate, per DRAWN cell",
           round(drawn_ratio, 2), 3.83)
    expect("sparsity: BEARING/RANDOM, per padded BLOCK AREA",
           round(area_ratio, 2), 1.02)
    if drawn_ratio < 2.0 * area_ratio:
        FAIL.append(
            f"sparsity: the per-drawn-cell ratio {drawn_ratio:.2f} is no "
            f"longer well above the per-area ratio {area_ratio:.2f}. The "
            "figure draws ONLY measured cells precisely because padding the "
            "ragged rows to a rectangle collapses the contrast; if these two "
            "readings have converged the design rationale in the caption is "
            "false and the layout must be re-argued")

    # ---- the stratum contrast, in a form the row sort cannot manufacture.
    if not (stats["BEARING"]["lo"] > stats["RANDOM"]["hi"]):
        FAIL.append(
            f"sparsity: BEARING's positive-rate interval "
            f"[{stats['BEARING']['lo']:.4f},{stats['BEARING']['hi']:.4f}] no "
            f"longer sits entirely above RANDOM's "
            f"[{stats['RANDOM']['lo']:.4f},{stats['RANDOM']['hi']:.4f}]; the "
            "caption states the blocks separate, and the row ordering must "
            "never be what carries that claim")
    expect("sparsity: BEARING Wilson lower", round(stats["BEARING"]["lo"], 4),
           0.2847)
    expect("sparsity: RANDOM Wilson upper", round(stats["RANDOM"]["hi"], 4),
           0.1152)

    # ---- constraint 5: A COLUMN IS NOT A TASK, and the caption must say so.
    # Within a block a memory's cells are laid out left to right in its OWN
    # task order. Column 3 of row 7 and column 3 of row 8 are DIFFERENT tasks.
    # This is forced by the data -- a shared task axis is not drawable here,
    # because the strata span 56/100/147 distinct tasks against block widths
    # of 9/9/15, and bearing tasks are nearly private to one memory (20 of 56
    # belong to a single memory). A reader who took a column for a task would
    # read vertical streaks as "this task is easy", which the layout cannot
    # support. Asserted so the caption's disclaimer cannot quietly stop being
    # necessary -- if a block ever becomes narrow enough to BE a task axis,
    # the figure should be redrawn as one and the caption rewritten.
    ntask = {s_: len({t for (ss, _m, t) in du if ss == s_}) for s_ in STRATA}
    expect("sparsity: distinct tasks per stratum",
           [ntask[s_] for s_ in STRATA], [56, 100, 147])
    for s_ in STRATA:
        if ntask[s_] <= width[s_]:
            FAIL.append(
                f"sparsity: {s_} now spans {ntask[s_]} tasks against a block "
                f"{width[s_]} columns wide, so a column COULD be a task. The "
                "caption states columns are per-memory task slots and NOT a "
                "shared task axis; redraw against a real task axis instead")

    # ---- constraint 4: the row order, computed here so TikZ chooses nothing.
    order = sorted(mems, key=lambda m: (-sum(1 for v in per[m]["BEARING"] if v > 0),
                                        -sum(1 for v in per[m]["BEARING"]), m))

    # Sparsity stated as the headline number the caption quotes.
    nonzero = sum(1 for v in du.values() if v != 0)
    expect("sparsity: cells with ANY measured effect", nonzero, 176)
    # How many memories help at all, per stratum. The claim is about WHERE a
    # memory helps, so "a memory helps somewhere" must not be confused with
    # "a memory helps on this task": 32 of 60 memories help on some bearing
    # task, but only 50 of 139 bearing CELLS move.
    helps = {s_: sum(1 for m in mems if any(v > 0 for v in per[m][s_]))
             for s_ in STRATA}
    expect("sparsity: memories helping on >=1 BEARING task", helps["BEARING"], 32)
    expect("sparsity: memories helping on >=1 control task",
           helps["MATCHED_CONTROL"], 9)
    expect("sparsity: share of cells that are exactly zero",
           round(100.0 * (len(du) - nonzero) / len(du), 1), 84.8)

    marks = []
    for row, m in enumerate(order):
        for s in STRATA:
            for col, v in enumerate(sorted(per[m][s], reverse=True)):
                marks.append((row, s, col, v))
    expect("sparsity: marks to draw equals measured cells", len(marks), len(du))
    return {"marks": marks, "order": order, "width": width, "stats": stats,
            "n_cells": len(du), "nonzero": nonzero, "n_mems": len(mems),
            "drawn_ratio": drawn_ratio, "area_ratio": area_ratio,
            "ntask": ntask, "helps": helps}




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


def crossbench():
    """Figure 5: the ONE quantity both benchmarks define identically.

    The comparable quantity is the **paired representation contrast** --
    per cell, deltaU(rep A) minus deltaU(rep B) for the same memory against
    the same task -- with a task-clustered interval. Both analyses compute
    exactly this, on cells interpretable under all representations.

    What is deliberately NOT plotted: per-representation mean deltaU. Those
    are not comparable across these benchmarks, because LongMemEval's
    execution floor is exactly 0 while SciCode's is 0.0370, so equal bar
    heights would mean different things. The contrast differences the floor
    out -- both terms carry it -- which is why it, and only it, is drawn.
    """
    lm = json.loads((REPO / "results/repr_scaleup/analysis"
                     / "r3_representation_analysis.json").read_text())
    sc = json.loads((REPO / "results/ledgers/repro/scicode"
                     / "scaleup_analysis.json").read_text())
    # 🔴 The MULTI-REPO, DEFECT-21-CORRECTED analysis, not the django-only
    # v2 one. Two changes land together and both must: sympy ran (so the
    # figure is no longer single-repo), and a pytest collection error was
    # being scored as a wrong answer (DEFECT_REGISTER #21), which demoted 37
    # arm-reads and moved the pooled matched set 17 -> 15. Reading the older
    # artifact would publish numbers a correction has already superseded.
    _swm = json.loads((REPO / "results/ledgers/repro/swebench"
                       / "representations_multirepo_final.json").read_text())
    sw = _swm["pooled"]
    fl = json.loads((REPO / "results/ledgers/repro"
                     / "cross_benchmark_without_arm_floor.json").read_text())
    lpc = lm["Q1_paired_delta_utility"]["paired_contrasts"]
    spc = sc["paired_contrasts"]
    out = {}
    for key, lkey, skey in (("SR", "summary_minus_raw", "summary_minus_raw"),
                            ("TR", "structured_minus_raw", "structured_minus_raw")):
        lv = lpc[lkey]
        lt = lv.get("task_clustered", lv)
        sv = spc[skey]
        wv = sw["paired_contrasts"][skey]
        out[key] = {
            "lmev": (lv["mean"], lt["ci_lower"], lt["ci_upper"], lv["n"]),
            "scicode": (sv["mean"], sv["ci95_task_clustered"][0],
                        sv["ci95_task_clustered"][1], sc["MATCHED_CELL_SET_N"]),
            "swebench": (wv["mean"], wv["ci95_task_clustered"][0],
                         wv["ci95_task_clustered"][1], sw["MATCHED_CELL_SET_N"]),
        }
    # Guard: the defect-21 correction must still be applied. If the artifact
    # is ever regenerated without it, 37 manufactured zeros re-enter and the
    # matched set returns to 17 -- a retracted number back in a figure.
    expect("crossbench: SWE-bench defect-21 correction applied",
           _swm["defect21_manufactured_zero_correction"]["arm_reads_demoted"],
           37)
    expect("crossbench: SWE-bench matched set, corrected", sw["MATCHED_CELL_SET_N"], 40)
    expect("crossbench: SWE-bench repositories", len(sw["cells_per_repo"]), 2)
    # A pooled figure must state its composition. One repo supplies 80% here,
    # so the caption says so; if that stops being true the caption is wrong
    # in the other direction and must still be rewritten.
    if sw.get("DOMINATED_BY") is None:
        FAIL.append("crossbench: SWE-bench is no longer dominated by one "
                    "repo; the caption discloses that it is and must be "
                    "rewritten")
    # Guard: the two analyses must agree on what the contrast MEANS.
    expect("crossbench: LongMemEval contrast basis is the common-cell join",
           lm["Q1_paired_delta_utility"]["n_common_cells"], 277)
    expect("crossbench: SciCode contrast basis is the matched cell set",
           sc["MATCHED_CELL_SET_N"], 122)
    # Guard: never plot a SciCode contrast as separated while the artifact
    # says the ordering is not established.
    if sc["ORDERING_VERDICT"] != "NOT_ESTABLISHED":
        FAIL.append("crossbench: SciCode ORDERING_VERDICT changed -- the "
                    "figure's caption asserts every SciCode interval crosses "
                    "zero and must be rewritten before this passes")
    # The session-matched reader transfer is the CANONICAL reader-generalization
    # result and had no machine check of any kind: planting +0.5000 left both
    # audit_claims.py and make_figures.py green. These live HERE, inside a
    # function called before the `if FAIL:` exit -- a first version appended to
    # FAIL from the emit block at line ~1144, long AFTER that exit at line 955,
    # so two of the three guards were unreachable and passed every plant.
    _smg = json.loads((REPO / "results/ledgers/repro/raw_session_matched"
                       / "raw_session_matched_analysis.json").read_text())
    expect("session-matched reader arms: matched cell count",
           _smg["n_matched"], 550)
    if _smg.get("VERDICT") != "SURVIVES_SESSION_MATCHING":
        FAIL.append("session-matched verdict changed to "
                    f"{_smg.get('VERDICT')!r} -- the manuscript says the "
                    "effect survives session matching")
    _slo, _shi = _smg["ci95_task_clustered"]
    if not (_slo > 0 or _shi < 0):
        FAIL.append(f"session-matched interval [{_slo}, {_shi}] no longer "
                    "excludes zero; the reader-transfer claim is now false")

    if sw["ORDERING_VERDICT"] != "NOT_ESTABLISHED":
        FAIL.append("crossbench: SWE-bench ORDERING_VERDICT changed -- the "
                    "caption asserts its intervals cross zero too")
    for k, v in out.items():
        for bench in ("scicode", "swebench"):
            lo, hi = v[bench][1], v[bench][2]
            if not (lo <= 0.0 <= hi):
                FAIL.append(f"crossbench: {bench} {k} interval [{lo},{hi}] no "
                            "longer crosses zero; caption is now false")
    # The caption quotes both floors. They are emitted from the artifact, never
    # typed: a floor is a measurement and a typed one cannot be re-derived.
    out["_floors"] = {
        "lmev": fl["benchmarks"]["longmemeval_v2"],
        "scicode": fl["benchmarks"]["scicode"],
    }
    # SWE-bench reuses ONE WITHOUT call across representations by design, so
    # its cross-representation disagreement is 0 by construction. Emitting it
    # beside two measured floors would read as "cleanest benchmark".
    if fl["benchmarks"]["swebench_verified"]["rate"] is not None:
        FAIL.append("crossbench: SWE-bench now reports a WITHOUT-arm floor; it "
                    "is 0 by construction (one shared call) and must not be "
                    "quoted beside measured floors")
    return out


# ---------------------------------------------------------------------------
# FIGURE 6 -- READER GENERALIZATION: does memory utility survive a new reader?
# ---------------------------------------------------------------------------
# PLANT-VERIFIED GUARDS. Each `_rg_guard` below was checked by planting its
# defect in a COPY of the artifact and confirming the build fails. A guard
# only ever observed passing is not known to discriminate -- three of this
# project's defects were in guards.
GEMMA_READER_ID = "gemma-4-31B-it"      # capital B: the lowercase id resolves
GPTOSS_READER_ID = "gpt-oss-120b"       # silently at the endpoint (defect #19)


def _rg_cell_mean(rows, n_rep=2):
    """Mean dU over the first n_rep replicates, or None if any is unscorable.

    reward None means COULD NOT BE SCORED and is never 0.0. A cell with an
    unscorable replicate drops out rather than contributing a fabricated zero.
    """
    rows = sorted(rows, key=lambda r: r.get("replicate_id", 0))[:n_rep]
    vals = []
    for r in rows:
        w, o = r.get("reward_with_memory"), r.get("reward_without_memory")
        if w is None or o is None:
            return None
        vals.append(w - o)
    return statistics.mean(vals) if vals else None


def _rg_boot_cluster(units, n_boot=10000, seed=20260930):
    """Task-clustered percentile bootstrap, resampling CLUSTERS not rows.

    Deliberately re-implements scripts/gemma_reader_analyze.py::boot_cluster
    rather than importing it: two independent computations that must agree
    bit-for-bit is the check. n_boot and seed match the analysis exactly, so
    the comparison below is an equality, not a tolerance.
    """
    import numpy as np
    keys = sorted(units, key=str)
    flat = [v for k in keys for v in units[k]]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        pick = [keys[i] for i in rng.integers(0, len(keys), size=len(keys))]
        vals = [v for k in pick for v in units[k]]
        if vals:
            draws.append(float(np.mean(vals)))
    return (float(np.mean(flat)),
            float(np.percentile(draws, 2.5)),
            float(np.percentile(draws, 97.5)))


def _rg_pearson(x, y):
    import numpy as np
    a, b = np.asarray(x, float), np.asarray(y, float)
    if a.size < 2 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _rg_locator(r):
    pr = r.get("provenance") or {}
    return pr.get("memory_unit_locator") or (
        r.get("source_episode_metadata") or {}).get("memory_unit_locator")


def reader_generalization(_gemma_rows=None, _analysis=None):
    """Figure 6 + the cross-model correlation element.

    THE JOIN IS THE WHOLE DIFFICULTY, and the house rules name all three traps:
      * `memory_id` is a per-representation CONTENT HASH -> joins to nothing;
      * `condition_id` EMBEDS the representation AND the reader -> zero rows
        across readers, by construction;
      * the only key that crosses is
        (memory_unit_locator, future_task_id, memory_representation).
    Each wrong join is RUN below and asserted to return zero, so the non-empty
    matched set is evidence the key is right rather than a hope.

    MATCHED-SET RULE: a cell enters only if it is interpretable under BOTH
    readers at the same replicate depth. Denominators differ per reader
    (Gemma loses 9/11/8 cells to truncation), and a mean over different cells
    compares different cells.
    """
    import numpy as np
    gem = _gemma_rows if _gemma_rows is not None else load(
        "results/ledgers/repro/gemma_reader/transfer_cells_slim.jsonl")
    oss = load("results/deltau_screened/cells.jsonl") + load(
        "results/repr_scaleup/cells.jsonl")
    ana = _analysis if _analysis is not None else json.loads(
        (REPO / "results/ledgers/gemma_reader"
         / "reader_transfer_analysis.json").read_text())

    # ---- guard A: reader identity. The whole experiment is "only the reader
    # changed", so a row carrying the wrong reader invalidates the figure.
    g_readers = {r.get("reader_model") for r in gem}
    if g_readers != {GEMMA_READER_ID}:
        FAIL.append(f"reader-gen: Gemma rows carry reader_model {g_readers}, "
                    f"expected exactly {{{GEMMA_READER_ID!r}}} -- the figure's "
                    "caption says only the reader changed")
    o_readers = {r.get("reader_model") for r in oss}
    if o_readers != {GPTOSS_READER_ID}:
        FAIL.append(f"reader-gen: comparator rows carry reader_model "
                    f"{o_readers}, expected exactly {{{GPTOSS_READER_ID!r}}}")
    if g_readers & o_readers:
        FAIL.append("reader-gen: the two reader sets OVERLAP; this is not a "
                    "reader comparison")

    # ---- guard B: reasoning_tokens is None on every Gemma row, NEVER 0.
    # Metis/Gemma returns no completion_tokens_details at all. A 0 would be an
    # absence written as a measurement, and would make the frontier figure's
    # cost axis silently poolable across models. It must not be.
    bad_rt = sum(1 for r in gem if r.get("reasoning_tokens") is not None)
    if bad_rt:
        FAIL.append(f"reader-gen: {bad_rt} Gemma rows carry a non-null "
                    "reasoning_tokens; the model reports none, so a value "
                    "there is an absence written as a measurement (and the "
                    "frontier's cost axis must stay model-separated)")

    # ---- guard C: the WRONG joins must return ZERO. Positive-control every
    # null -- an empty join has to be PROVEN an artefact of the key.
    o_by_cond = {(r.get("condition_id"), r["future_task_id"]) for r in oss}
    g_by_cond = {(r.get("provenance", {}).get("gptoss_comparator_condition_id"),
                  r["future_task_id"]) for r in gem}
    # the Gemma rows' OWN condition_id, which is the trap:
    g_own_cond = {(r.get("condition_id"), r["future_task_id"]) for r in gem}
    n_cond_join = len(o_by_cond & g_own_cond)
    if n_cond_join != 0:
        FAIL.append(f"reader-gen: the condition_id join returned {n_cond_join} "
                    "rows; it embeds the reader and MUST return zero, so this "
                    "demonstration of the trap is no longer valid")
    o_mem = {r["memory_id"] for r in oss}
    g_mem = {r["memory_id"] for r in gem}
    n_mem_join = len(o_mem & g_mem)

    # ---- the correct join
    O, G = collections.defaultdict(list), collections.defaultdict(list)
    for r in oss:
        pr = r.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        O[(_rg_locator(r), r["future_task_id"],
           r["memory_representation"])].append(r)
    for r in gem:
        pr = r.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        G[(pr.get("memory_unit_locator"), r["future_task_id"],
           r["memory_representation"])].append(r)

    out, corr = {}, {}
    for rep in ("raw", "summary", "structured"):
        ko = {k for k in O if k[2] == rep}
        kg = {k for k in G if k[2] == rep}
        a = {k: _rg_cell_mean(O[k]) for k in ko}
        b = {k: _rg_cell_mean(G[k]) for k in kg}
        matched = sorted(k for k in (ko & kg)
                         if a[k] is not None and b[k] is not None)
        bt = collections.defaultdict(list)
        for k in matched:
            bt[k[1]].append(b[k] - a[k])
        point, lo, hi = _rg_boot_cluster(bt)
        xs = [a[k] for k in matched]
        ys = [b[k] for k in matched]
        nz = [i for i in range(len(matched)) if xs[i] != 0 or ys[i] != 0]
        both = [i for i in range(len(matched)) if xs[i] != 0 and ys[i] != 0]
        agree = sum(1 for i in both
                    if (xs[i] > 0) == (ys[i] > 0) and (xs[i] < 0) == (ys[i] < 0))
        out[rep] = {
            "n": len(matched), "n_tasks": len(bt),
            "oss": statistics.mean(xs), "gem": statistics.mean(ys),
            "diff": point, "lo": lo, "hi": hi,
            "excl0": bool(lo > 0 or hi < 0),
            "nz": sum(1 for k in matched if abs(b[k] - a[k]) > 1e-12),
        }
        corr[rep] = {
            "label_k": ana["label_agreement"][rep]["agreement"]["k"],
            "label_n": ana["label_agreement"][rep]["agreement"]["n"],
            "r_all": _rg_pearson(xs, ys), "n_all": len(matched),
            "r_nz": _rg_pearson([xs[i] for i in nz], [ys[i] for i in nz]),
            "n_nz": len(nz),
            "zero_both": len(matched) - len(nz),
            "sign_k": agree, "sign_n": len(both),
        }
        # ---- guard D: the correct join must be NON-EMPTY, and the wrong ones
        # above were just shown to be empty. Together that is evidence.
        if not matched:
            FAIL.append(f"reader-gen: the locator join returned ZERO cells for "
                        f"{rep}; with the wrong joins also at zero this cannot "
                        "distinguish a key error from a real absence")

    # ---- guard E: every value must EQUAL the analysis artifact bit-for-bit.
    # The computation above is independent (own loader, own estimator, same
    # seed), so equality is the cross-check; a tolerance would hide a drift.
    for rep in ("raw", "summary", "structured"):
        ref = ana["per_representation_matched"][rep]
        rtc = ref["paired_difference_task_clustered"]
        expect(f"reader-gen {rep}: matched cells", out[rep]["n"],
               ref["n_matched_cells"])
        expect(f"reader-gen {rep}: tasks", out[rep]["n_tasks"], ref["n_tasks"])
        expect(f"reader-gen {rep}: dU gpt-oss", round(out[rep]["oss"], 6),
               round(ref["deltaU_gptoss"]["mean"], 6))
        expect(f"reader-gen {rep}: dU Gemma", round(out[rep]["gem"], 6),
               round(ref["deltaU_gemma"]["mean"], 6))
        expect(f"reader-gen {rep}: paired diff", round(out[rep]["diff"], 6),
               round(rtc["mean"], 6))
        expect(f"reader-gen {rep}: clustered CI lower",
               round(out[rep]["lo"], 6), round(rtc["ci_lower"], 6))
        expect(f"reader-gen {rep}: clustered CI upper",
               round(out[rep]["hi"], 6), round(rtc["ci_upper"], 6))
        la = ana["label_agreement"][rep]["agreement"]
        expect(f"reader-gen {rep}: label-agreement denominator", la["n"],
               ref["n_matched_cells"])
        sc = ana["sign_and_correlation"][rep]
        expect(f"reader-gen {rep}: r over ALL cells",
               round(corr[rep]["r_all"], 6),
               round(sc["correlation"]["pearson"], 6))
        expect(f"reader-gen {rep}: r over non-zero-under-either",
               round(corr[rep]["r_nz"], 6),
               round(sc["correlation_on_cells_nonzero_under_either"]["pearson"], 6))
        expect(f"reader-gen {rep}: n non-zero under either",
               corr[rep]["n_nz"],
               sc["correlation_on_cells_nonzero_under_either"]["n"])
        expect(f"reader-gen {rep}: sign agreement, both non-zero",
               f"{corr[rep]['sign_k']}/{corr[rep]['sign_n']}",
               f"{sc['sign_agreement_both_nonzero']['k']}/"
               f"{sc['sign_agreement_both_nonzero']['n']}")

    # ---- guard F0: the figure draws the interval on the DIFFERENCE anchored
    # at the gpt-oss point. That is only legitimate because the mean of the
    # per-cell differences equals the difference of the means on a paired
    # set. Asserted EXACTLY, not to a tolerance: if the matched sets ever
    # stop being identical between the two readers the identity breaks and
    # the drawing would silently misplace every whisker.
    for rep in ("raw", "summary", "structured"):
        gap = out[rep]["gem"] - out[rep]["oss"]
        if abs(gap - out[rep]["diff"]) > 1e-12:
            FAIL.append(
                f"reader-gen {rep}: the paired difference {out[rep]['diff']!r} "
                f"is not the gap between the reader means {gap!r}; the figure "
                "anchors the interval at the gpt-oss point and that drawing "
                "is only valid while the two are the same number")

    # ---- guard F: the CAPTION's claims, asserted against the data.
    # Each of these is a sentence in the figure caption. If the artifact stops
    # supporting it the BUILD FAILS rather than the caption going quietly
    # false -- which is this project's named "derived figures go stale" shape.
    if not out["raw"]["excl0"]:
        FAIL.append("reader-gen: Raw's paired interval no longer excludes "
                    "zero -- the caption and the prose call Raw a POSITIVE "
                    "transfer result and must be rewritten before this passes")
    if out["raw"]["diff"] <= 0:
        FAIL.append("reader-gen: Raw's paired difference is no longer "
                    "positive; the caption says Gemma measures a LARGER "
                    "effect on Raw")
    for rep in ("summary", "structured"):
        if out[rep]["excl0"]:
            FAIL.append(f"reader-gen: {rep}'s interval now EXCLUDES zero; the "
                        "caption says only Raw separates, and the prose "
                        "forbids stating summary/structured as findings")
    # the ordering claim
    order_o = sorted(("raw", "summary", "structured"),
                     key=lambda r: -out[r]["oss"])
    order_g = sorted(("raw", "summary", "structured"),
                     key=lambda r: -out[r]["gem"])
    expect("reader-gen: gpt-oss ordering", order_o,
           ["raw", "summary", "structured"])
    expect("reader-gen: Gemma ordering", order_g,
           ["raw", "summary", "structured"])
    if order_o != order_g:
        FAIL.append("reader-gen: the representation orderings no longer "
                    "agree; the caption states they do")

    # ---- guard G: the correlation honesty claim. The caption says the
    # all-cells r is INFLATED by tied zeros and the non-zero r is the honest
    # one. That is only true while the tied zeros dominate and r actually
    # falls. Assert BOTH halves.
    if corr["raw"]["zero_both"] <= corr["raw"]["n_nz"]:
        FAIL.append("reader-gen: tied zeros no longer dominate the raw cell "
                    "set, so the caption's explanation of why the all-cells r "
                    "is inflated no longer holds")
    if not (corr["raw"]["r_nz"] < corr["raw"]["r_all"]):
        FAIL.append("reader-gen: restricting to non-zero cells no longer "
                    "LOWERS r on raw; the caption says the all-cells figure "
                    "is the inflated one")

    # ---- guard H: the decomposition. Roughly half of Gemma's larger raw dU
    # is a weaker no-memory baseline, not a more useful memory. The caption
    # says so; if the artifact stops saying it, fail.
    dec = ana["deltaU_decomposed_by_arm"]["raw"]
    share = dec["share_of_deltaU_change_from_the_WITHOUT_arm"]
    if share is None or not (0.0 < share < 1.0):
        FAIL.append("reader-gen: the WITHOUT-arm share of raw's dU change is "
                    f"{share!r}; the caption quotes it as a fraction")
    expect("reader-gen: WITHOUT-arm share of raw's change", round(share, 4),
           0.5429)
    if dec["change_in_WITHOUT_arm"] >= 0:
        FAIL.append("reader-gen: Gemma's raw WITHOUT arm no longer sits BELOW "
                    "gpt-oss's; the caption attributes half the gap to a "
                    "weaker unaided reader")

    # ---- guard I: the design invariant. 1,694 rows, memory text byte-
    # identical to the gpt-oss run. Without this the figure is not a reader
    # comparison at all, and the number is quoted in the caption.
    bi = ana["memory_text_byte_identity"]
    expect("reader-gen: memory text compared", bi["compared"], 1694)
    expect("reader-gen: memory text byte-identical", bi["identical"], 1694)
    expect("reader-gen: memory text differing", bi["differ"], 0)
    if not bi["_positive_control"]["detects_one_byte_change"]:
        FAIL.append("reader-gen: the byte-identity check's own positive "
                    "control does not fire, so 1694/1694 proves only that the "
                    "comparison ran")

    return out, corr, {"n_mem_join": n_mem_join, "n_cond_join": n_cond_join,
                       "n_gemma_rows": len(gem)}




# ---------------------------------------------------------------------------
# FIGURE 6 (CANONICAL PANEL) -- the SESSION-MATCHED reader contrast
# ---------------------------------------------------------------------------
def reader_session_matched():
    """The canonical reader-transfer result, recomputed from the slim rows.

    WHY THIS FUNCTION EXISTS. Figure 6 drew `\\rgRawDiff`, which is the
    SUPERSEDED cross-session contrast (+0.1268, arms 11 hours apart), while
    the prose beside it quoted the canonical session-matched +0.0982. A reader
    comparing the figure's marker to the paragraph's number found two
    different results for one claim, and nothing failed. The canonical
    quantity is now computed here and is what the figure draws.

    THE ESTIMATOR IS REIMPLEMENTED, NOT IMPORTED. scripts/raw_session_matched_
    analysis.py uses random.Random(5), 20,000 task-clustered resamples and an
    index-based percentile. That is reproduced here exactly so the comparison
    against the artifact is an EQUALITY, not a tolerance -- two independent
    computations that must agree is the check this file is built on.

    WHAT THE FIGURE MUST NOT DRAW, and it is a measurement not a preference:
    the two readers' own 95% intervals OVERLAP heavily (gpt-oss tops out at
    about +0.30, Gemma starts at about +0.23). Drawing them side by side
    invites "the intervals overlap, so there is no difference", which is
    false -- the cells are PAIRED and the paired interval excludes zero. So
    the figure draws the per-reader POINTS and exactly one interval, the
    paired one. The overlap is asserted below so that this stays a documented
    property of the data rather than a drafting choice.
    """
    D = "results/ledgers/repro/raw_session_matched"
    oss = load(f"{D}/raw_gptoss_slim.jsonl")
    gem = load(f"{D}/raw_gemma_slim.jsonl")
    ana = json.loads((REPO / D / "raw_session_matched_analysis.json").read_text())

    # ---- guard SM-A: the arms are the two readers and nothing else.
    mo = {r["reader_model"] for r in oss}
    mg = {r["reader_model"] for r in gem}
    if mo != {GPTOSS_READER_ID} or mg != {GEMMA_READER_ID}:
        FAIL.append(f"session-matched: arms carry readers {mo} and {mg}; the "
                    f"figure says only the reader changed")
    clusters = {r["reader_cluster"] for r in oss} | {r["reader_cluster"] for r in gem}
    if clusters != {"metis"}:
        FAIL.append(f"session-matched: arms span clusters {clusters}; pooling "
                    "serving configurations would confound the reader contrast")
    # ---- guard SM-B: ONE SESSION. This arm exists BECAUSE the published one
    # was 11 hours split; if the dates ever diverge it has become the thing it
    # replaced, and the word "session-matched" in the caption is false.
    dates = ({r["created_at_utc"][:10] for r in oss}
             | {r["created_at_utc"][:10] for r in gem})
    if len(dates) != 1:
        FAIL.append(f"session-matched: the arms ran on {sorted(dates)} -- more "
                    "than one date. This contrast exists because the "
                    "superseded one was split across sessions; the caption "
                    "calls it session-matched")
    # ---- guard SM-C: an errored row must never carry a score.
    bad = sum(1 for r in oss + gem
              if r.get("error_code_if_any") and r.get("delta_utility") is not None)
    if bad:
        FAIL.append(f"session-matched: {bad} errored rows carry a delta_utility; "
                    "an error is an absence and must never be scored")

    def _key(r):
        p = r.get("provenance") or {}
        return (p.get("memory_unit_locator"), r["future_task_id"],
                r.get("replicate_id"))

    O = {_key(r): r["delta_utility"] for r in oss if r["delta_utility"] is not None}
    G = {_key(r): r["delta_utility"] for r in gem if r["delta_utility"] is not None}
    matched = sorted(set(O) & set(G))
    # ---- guard SM-D: positive-control the join. An empty matched set must be
    # distinguishable from a key error, so the WRONG key is run and required
    # to return zero -- condition_id embeds the reader, by construction.
    wrong = {(r.get("condition_id"), r["future_task_id"]) for r in oss} & {
        (r.get("condition_id"), r["future_task_id"]) for r in gem}
    if wrong:
        FAIL.append(f"session-matched: the condition_id join returned "
                    f"{len(wrong)} rows; it embeds the reader and MUST return "
                    "zero, so the locator join below is no longer evidenced")
    if not matched:
        FAIL.append("session-matched: the locator join returned ZERO rows")
        return None

    def _boot(vals, tasks, n=20000, seed=5):
        """random.Random(5), 20k task-clustered resamples, index percentile.

        Byte-for-byte the estimator in scripts/raw_session_matched_analysis.py.
        """
        import random
        rng = random.Random(seed)
        byt = collections.defaultdict(list)
        for v, t in zip(vals, tasks):
            byt[t].append(v)
        keys = list(byt)
        out = []
        for _ in range(n):
            s = []
            for _ in keys:
                s += byt[rng.choice(keys)]
            out.append(sum(s) / len(s))
        out.sort()
        return round(out[int(0.025 * n)], 4), round(out[int(0.975 * n)], 4)

    diffs = [G[k] - O[k] for k in matched]
    tasks = [k[1] for k in matched]
    lo, hi = _boot(diffs, tasks)
    mean = sum(diffs) / len(diffs)
    m_oss = sum(O[k] for k in matched) / len(matched)
    m_gem = sum(G[k] for k in matched) / len(matched)
    cells = {(k[0], k[1]) for k in matched}
    n_tasks = len({k[1] for k in matched})

    # ---- guard SM-E: EQUALITY with the artifact, not a tolerance.
    expect("session-matched: replicate rows", len(matched), ana["n_matched"])
    expect("session-matched: cells", len(cells), ana["n_cells"])
    expect("session-matched: tasks", n_tasks, ana["n_tasks"])
    expect("session-matched: dU gpt-oss", round(m_oss, 4), ana["deltaU_gptoss"])
    expect("session-matched: dU Gemma", round(m_gem, 4), ana["deltaU_gemma"])
    expect("session-matched: paired reader effect", round(mean, 4),
           ana["paired_diff_gemma_minus_gptoss"])
    expect("session-matched: CI lower", lo, ana["ci95_task_clustered"][0])
    expect("session-matched: CI upper", hi, ana["ci95_task_clustered"][1])
    # The canonical values the manuscript prints, pinned independently of the
    # artifact as well -- an artifact regenerated wrongly would otherwise move
    # the figure and the equality check above would still pass.
    expect("session-matched: the canonical point estimate", round(mean, 4),
           0.0982)
    expect("session-matched: the canonical interval", [lo, hi], [0.0247, 0.173])
    expect("session-matched: the canonical cell count", len(cells), 275)

    # ---- guard SM-F: the UNIT. 550 is REPLICATE ROWS; 275 is cells. A caption
    # that calls 550 "cells" is this project's named units defect, and the
    # artifact itself carries the warning. Assert the arithmetic that makes
    # them different numbers so neither can be substituted for the other.
    if len(matched) != 2 * len(cells):
        FAIL.append(f"session-matched: {len(matched)} rows is not 2x the "
                    f"{len(cells)} cells; the caption distinguishes replicate "
                    "rows from cells and the factor-of-two is why")

    # ---- guard SM-G: the superseded figure must stay superseded. The
    # published cross-session contrast is a DIFFERENT number on DIFFERENT
    # cells; if the figure ever draws it again, this fires.
    pub = ana["published_cross_session"]
    expect("session-matched: the superseded cross-session mean", pub["mean"],
           0.1268)
    if abs(pub["mean"] - mean) < 1e-9:
        FAIL.append("session-matched: the canonical and superseded estimates "
                    "are now identical, so the figure can no longer be shown "
                    "to draw the canonical one")
    if ana.get("VERDICT") != "SURVIVES_SESSION_MATCHING":
        FAIL.append(f"session-matched: VERDICT is {ana.get('VERDICT')!r}; the "
                    "caption says the effect survives session matching")
    if not (lo > 0):
        FAIL.append(f"session-matched: the interval [{lo}, {hi}] no longer "
                    "excludes zero on the positive side; the caption calls "
                    "this a positive reader-transfer result")

    # ---- guard SM-J: the memory text and the whole rendered request must be
    # IDENTICAL across the two arms, or this is not a reader-only contrast and
    # the caption's "same memory text" is false. The rows carry four hashes;
    # all four are compared on EVERY matched row rather than sampled, and the
    # count is emitted so the caption quotes a measurement rather than a
    # recollection. Note the unit: these are the 570 joinable replicate rows
    # BEFORE the scorability filter, which is the right denominator for a
    # question about what was SENT -- an unscorable row was still rendered.
    _O_all = {_key(r): r for r in oss}
    _G_all = {_key(r): r for r in gem}
    _ident = sorted(set(_O_all) & set(_G_all))
    hashes = ("memories_sha256", "context_sha256", "config_sha256",
              "filler_pool_sha256")
    same = {h: sum(1 for k in _ident
                   if (_O_all[k].get("provenance") or {}).get(h)
                   == (_G_all[k].get("provenance") or {}).get(h))
            for h in hashes}
    expect("session-matched: rows compared for request identity", len(_ident),
           570)
    for h in hashes:
        expect(f"session-matched: {h} identical", same[h], len(_ident))
        if same[h] != len(_ident):
            FAIL.append(
                f"session-matched: {h} differs on "
                f"{len(_ident) - same[h]} of {len(_ident)} rows; the caption "
                "says the two readers saw the same memory text in the same "
                "request, so this would not be a reader-only contrast")
    # POSITIVE-CONTROL the identity check itself. 570/570 equal is only
    # evidence if an unequal pair would have been counted -- otherwise the
    # number proves the comparison ran, not that it discriminates. This is
    # the defect shape the Gemma figure's own byte-identity check records.
    _probe = dict(_O_all[_ident[0]].get("provenance") or {})
    _probe["memories_sha256"] = "0" * 64
    if _probe["memories_sha256"] == (_G_all[_ident[0]].get("provenance")
                                     or {}).get("memories_sha256"):
        FAIL.append("session-matched: the identity check's positive control "
                    "does not discriminate -- a changed hash still compares "
                    "equal, so 570/570 proves only that it ran")

    # ---- the matched per-cell agreement, Panel B. Cell means over the two
    # replicates; three-valued for the same reason the sparsity figure is.
    cd = collections.defaultdict(lambda: [[], []])
    for k in matched:
        cd[(k[0], k[1])][0].append(O[k])
        cd[(k[0], k[1])][1].append(G[k])
    cm = {k: (statistics.mean(v[0]), statistics.mean(v[1])) for k, v in cd.items()}

    def sgn(x):
        return 0 if abs(x) < 1e-9 else (1 if x > 0 else -1)

    conf = collections.Counter((sgn(a), sgn(b)) for a, b in cm.values())
    both = [(a, b) for a, b in cm.values() if sgn(a) and sgn(b)]
    agree = sum(1 for a, b in both if sgn(a) == sgn(b))
    zero_both = conf[(0, 0)]
    expect("session-matched: cells in the agreement panel", sum(conf.values()),
           275)
    expect("session-matched: zero under BOTH readers", zero_both, 170)
    expect("session-matched: non-zero under both, signs agreeing",
           f"{agree}/{len(both)}", "55/58")
    # ---- guard SM-H: the tied zeros dominate, which is WHY the panel reports
    # agreement on the cells that could move rather than a raw agreement rate.
    # A 245/275 "agreement" would be mostly cells that cannot move at all.
    if zero_both <= len(both):
        FAIL.append(f"session-matched: tied zeros ({zero_both}) no longer "
                    f"dominate the movable cells ({len(both)}); the panel's "
                    "caption explains the agreement rate is quoted on movable "
                    "cells FOR that reason")

    # ---- guard SM-I: the per-reader intervals OVERLAP, which is exactly why
    # the figure draws one paired interval and not two marginal ones. If they
    # ever separate, the drawing rationale in the caption is wrong even though
    # every plotted value would still be right.
    olo, ohi = _boot([O[k] for k in matched], tasks)
    glo, ghi = _boot([G[k] for k in matched], tasks)
    if not (ohi > glo):
        FAIL.append(
            f"session-matched: the per-reader intervals [{olo},{ohi}] and "
            f"[{glo},{ghi}] no longer overlap. The figure deliberately draws "
            "ONE paired interval because two overlapping marginal intervals "
            "would invite the false reading 'no difference'; that rationale "
            "is stated in the caption and must be re-argued")
    expect("session-matched: marginal intervals overlap (why one is drawn)",
           round(ohi - glo, 4), 0.0689)

    return {"n_rows": len(matched), "n_cells": len(cells), "n_tasks": n_tasks,
            "oss": m_oss, "gem": m_gem, "diff": mean, "lo": lo, "hi": hi,
            "conf": conf, "agree": agree, "both": len(both),
            "zero_both": zero_both, "pub": pub,
            "n_ident": len(_ident), "same_hashes": same,
            "marg": {"oss": (olo, ohi), "gem": (glo, ghi)}}


# ---------------------------------------------------------------------------
# TABLE 2 -- coverage: eligible / attempted / completed / exclusions
# ---------------------------------------------------------------------------
def coverage():
    """Per-benchmark coverage, every figure recomputed from the artifacts.

    THE UNIVERSE MUST BE NAMED. docs/COVERAGE_MANIFEST.md's central finding is
    that a bare coverage percentage is FALSE against one of two universes on
    LongMemEval (15,112 frozen pairs vs the 1,157-cell screened design the
    paper reports). The table therefore reports the design the paper reports
    and names it, and the identity

        eligible = completed + excluded

    is ASSERTED per row rather than described, so a row that stops summing
    fails the build.
    """
    rows = {}

    # ---- LongMemEval-V2: the screened design (the universe the paper reports)
    #
    # 🔴 EVERY TERM IS COUNTED FROM ITS OWN SOURCE. `eligible` comes from the
    # pre-committed design MANIFEST (one line per planned cell), `attempted`
    # and `completed` from the executed ROW file, and `excluded` from the rows
    # that could not be scored. Deriving any of the three from the others
    # makes the closing identity VACUOUS: it cannot then fail, and a silently
    # lost cell closes as neatly as a complete run. An earlier version of this
    # function derived `excluded = eligible - completed` and was found vacuous
    # by planting a changed eligible count and watching the identity hold.
    scr = load("results/deltau_screened/cells.jsonl")
    cells = collections.defaultdict(list)
    for r in scr:
        cells[(_rg_locator(r), r["future_task_id"])].append(r)
    done = sum(1 for v in cells.values()
               if all(x.get("reward_with_memory") is not None for x in v))
    unscored = sum(1 for v in cells.values()
                   if any(x.get("reward_with_memory") is None for x in v))
    manifest = load("data/manifests/k1_screened_cells.jsonl")
    planned = {(x["memory_unit_locator"], x["task_id"]) for x in manifest}
    eligible = len(planned)
    never_run = len(planned - set(cells))
    design = json.loads((REPO / "results/ledgers"
                         / "k1_screened_design.json").read_text())["design"]
    rows["lmev"] = {"eligible": eligible, "attempted": len(cells),
                    "completed": done, "excluded": unscored + never_run,
                    "excl_detail": {"unscorable": unscored,
                                    "never attempted": never_run}}
    expect("coverage lmev: eligible cells (from the design manifest)",
           eligible, 1157)
    expect("coverage lmev: attempted (from the row file)", len(cells), 1157)
    expect("coverage lmev: completed", done, 1157)
    expect("coverage lmev: unscorable", unscored, 0)
    expect("coverage lmev: planned but never attempted", never_run, 0)
    expect("coverage lmev: the design artifact agrees with the manifest",
           design["n_cells"], eligible)
    expect("coverage lmev: strata sum to the design",
           sum(design["strata"].values()), eligible)

    # ---- SciCode: the lexical-relatedness pool, run whole
    sca = json.loads((REPO / "results/ledgers/repro/scicode"
                      / "scaleup_analysis.json").read_text())
    scd = json.loads((REPO / "results/scicode"
                      / "scaleup_all3.json").read_text())
    n_pairs = scd["design"]["n_pairs"]
    reps = ("raw", "summary", "structured")
    sc_elig = n_pairs * len(reps)
    sc_done = sum(sca["per_representation_interpretable"][r] for r in reps)
    # Counted from the arm-run ROWS, not inferred as eligible - completed.
    # reward None is COULD NOT BE SCORED; a cell is excluded if EITHER arm is
    # None, which is the same rule the analysis applies.
    _scells = collections.defaultdict(dict)
    for _row in scd["rows"]:
        _scells[(_row["memory_id"], _row["task_id"],
                 _row["representation"])][_row["arm"]] = _row.get("reward")
    sc_attempted = len(_scells)
    sc_unscored = sum(1 for v in _scells.values()
                      if any(x is None for x in v.values())
                      or len(v) < 2)
    rows["scicode"] = {
        "eligible": sc_elig, "attempted": sc_attempted, "completed": sc_done,
        "excluded": sc_unscored,
        "excl_detail": {"unscorable execution": sc_unscored},
        "matched": sca["MATCHED_CELL_SET_N"]}
    expect("coverage scicode: eligible rep-cells (pairs x representations)",
           sc_elig, 462)
    expect("coverage scicode: attempted (counted from the arm-run rows)",
           sc_attempted, 462)
    expect("coverage scicode: completed", sc_done, 391)
    expect("coverage scicode: unscorable (counted from the rows)",
           sc_unscored, 71)
    expect("coverage scicode: matched set", sca["MATCHED_CELL_SET_N"], 122)

    # ---- SWE-bench Verified: the representation arm, defect-21 corrected
    swm = json.loads((REPO / "results/ledgers/repro/swebench"
                      / "representations_multirepo_final.json").read_text())
    pooled = swm["pooled"]
    sw_done = sum(pooled["per_representation_interpretable"][r] for r in reps)
    sw_excl = sum(pooled["exclusions"].values())
    # 🔴 ELIGIBLE IS COUNTED FROM THE SOURCE ARTIFACTS, not from
    # completed + excluded. Deriving it from the two terms it is checked
    # against makes the closing identity VACUOUS -- it could never fail, and
    # a vanished exclusion category would close just as neatly as a complete
    # one. Found by planting exactly that (an exclusion key deleted) and
    # watching the identity still pass. A control that cannot bind is not a
    # control; this counts the rows independently so the identity can fail.
    sw_elig = sum(len(json.loads(
        (REPO / src).read_text())["cells"])
        for src in pooled["source_artifacts"])
    rows["swebench"] = {
        "eligible": sw_elig, "attempted": sw_elig,
        "completed": sw_done, "excluded": sw_excl,
        "excl_detail": pooled["exclusions"],
        "matched": pooled["MATCHED_CELL_SET_N"],
        "repos": len(pooled["cells_per_repo"])}
    # Values are the FINAL universe (representations_multirepo_final.json,
    # 107/107 recipients attempted across django+sympy). The previous
    # expectations -- 129 rep-cells, 56 completed, matched 15 -- were the
    # pre-scale-up artifact; they FAILED loudly when the generator was
    # repointed at the final file, which is what they are for.
    expect("coverage swebench: eligible rep-cells (counted from source)",
           sw_elig, 321)
    expect("coverage swebench: attempted rep-cells", sw_done + sw_excl, 321)
    expect("coverage swebench: completed", sw_done, 141)
    expect("coverage swebench: matched set (defect-21 corrected)",
           pooled["MATCHED_CELL_SET_N"], 40)
    expect("coverage swebench: repositories", len(pooled["cells_per_repo"]), 2)
    expect("coverage swebench: defect-21 arm-reads demoted",
           swm["defect21_manufactured_zero_correction"]["arm_reads_demoted"], 37)

    # ---- the identity, asserted per row. A table whose rows do not close is
    # a table that has lost cells silently.
    for name, r in rows.items():
        if r["completed"] + r["excluded"] != r["eligible"]:
            FAIL.append(f"coverage {name}: completed {r['completed']} + "
                        f"excluded {r['excluded']} != eligible "
                        f"{r['eligible']}; the row does not close")
        if r["attempted"] > r["eligible"]:
            FAIL.append(f"coverage {name}: attempted exceeds eligible")

    # ---- the ordering verdicts the caption depends on
    if sca["ORDERING_VERDICT"] != "NOT_ESTABLISHED":
        FAIL.append("coverage: SciCode ORDERING_VERDICT changed; the caption "
                    "calls both secondary benchmarks boundary evidence")
    if pooled["ORDERING_VERDICT"] != "NOT_ESTABLISHED":
        FAIL.append("coverage: SWE-bench ORDERING_VERDICT changed; the caption "
                    "calls both secondary benchmarks boundary evidence")
    return rows


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
    print("== sparsity map (fig. 1b -- the central claim) ==")
    sp = sparsity_map()
    print("== bearing breadth (fig. 2a) ==")
    dist, n_units, n_bear, n_ge2, n_eps, n_det = bearing_breadth()
    print("== sign reversal by stratum (fig. 2b) ==")
    flips = flips_by_stratum()
    print("== similarity vs the content screen (fig. 3) ==")
    pooled, rand_only, by_str, sim_edges, rho_all, rho_rand = similarity_vs_bearing()
    print("== utility-efficiency frontier (fig. 4) ==")
    front, reuse, formation = frontier()
    print("== cross-benchmark paired contrasts (fig. 5) ==")
    xb = crossbench()
    print("== reader generalization (fig. 6) ==")
    rg, rgcorr, rgmeta = reader_generalization()
    print("== reader transfer, SESSION-MATCHED (fig. 6, canonical) ==")
    sm = reader_session_matched()
    print("== coverage table (tab. 2) ==")
    cov = coverage()

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
    BAR_MAX = 33.0    # pt, height of the tallest bar

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

    # ---- figure 1b: the sparsity map --------------------------------------
    # One square per MEASURED cell; nothing is drawn where no cell was run.
    # The three strata are three blocks on a shared row of 60 memories, so a
    # row is one memory read across its own bearing, matched-control and
    # unscreened tasks. Geometry is computed HERE; TikZ places what it is
    # given and performs no arithmetic on a measurement.
    SP_CW, SP_RH = 4.20, 2.55     # pt per column, pt per row
    SP_GAP = 9.0                  # pt between stratum blocks
    SP_ORDER = ("BEARING", "MATCHED_CONTROL", "RANDOM")
    _x0, SP_X0 = 0.0, {}
    for _s in SP_ORDER:
        SP_X0[_s] = _x0
        _x0 += sp["width"][_s] * SP_CW + SP_GAP
    SP_TOTW = _x0 - SP_GAP
    SP_TOTH = sp["n_mems"] * SP_RH

    L.append("%% --- sparsity map (fig 1b): one square per MEASURED cell ---")
    L.append("%% The paper's central claim, drawn at cell level. dU is exactly")
    L.append("%% three-valued (-1/0/+1) and the generator FAILS if a fourth")
    L.append("%% level appears. Unmeasured slots are drawn as NOTHING: the")
    L.append("%% rows are ragged, and padding them to a rectangle collapses")
    L.append("%% the BEARING/RANDOM contrast from 3.83x to 1.02x -- both")
    L.append("%% readings are asserted so a padded redraw cannot pass.")
    _pos, _neg, _zero = [], [], []
    for row, s_, col, v in sp["marks"]:
        x = SP_X0[s_] + col * SP_CW
        y = -row * SP_RH
        (_pos if v > 0 else _neg if v < 0 else _zero).append(f"{x:.2f}/{y:.2f}")
    # Emitted as \foreach lists: TikZ iterates coordinates, it computes none.
    L.append(r"\def\spPos{" + ",".join(_pos) + "}")
    L.append(r"\def\spNeg{" + ",".join(_neg) + "}")
    L.append(r"\def\spZero{" + ",".join(_zero) + "}")
    L.append(rf"\def\spCW{{{SP_CW:.2f}pt}}")
    L.append(rf"\def\spRH{{{SP_RH:.2f}pt}}")
    L.append(rf"\def\spTotW{{{SP_TOTW:.2f}pt}}")
    L.append(rf"\def\spTotH{{{SP_TOTH:.2f}pt}}")
    for s_, tag in (("BEARING", "Bear"), ("MATCHED_CONTROL", "Ctrl"),
                    ("RANDOM", "Rand")):
        st = sp["stats"][s_]
        L.append(rf"\def\sp{tag}X{{{SP_X0[s_]:.2f}pt}}")
        L.append(rf"\def\sp{tag}W{{{sp['width'][s_] * SP_CW:.2f}pt}}")
        L.append(rf"\def\sp{tag}Mid{{{SP_X0[s_] + sp['width'][s_] * SP_CW / 2:.2f}pt}}")
        L.append(rf"\def\sp{tag}N{{{st['n']}}}")
        L.append(rf"\def\sp{tag}Pos{{{st['pos']}}}")
        L.append(rf"\def\sp{tag}Neg{{{st['neg']}}}")
        L.append(rf"\def\sp{tag}Rate{{{100.0 * st['rate']:.1f}}}")
        L.append(rf"\def\sp{tag}Lo{{{100.0 * st['lo']:.1f}}}")
        L.append(rf"\def\sp{tag}Hi{{{100.0 * st['hi']:.1f}}}")
    L.append(rf"\def\spCells{{{sp['n_cells']:,}}}".replace(",", "{,}"))
    L.append(rf"\def\spMems{{{sp['n_mems']}}}")
    L.append(rf"\def\spNonzero{{{sp['nonzero']}}}")
    L.append(rf"\def\spZeroPct{{{100.0 * (sp['n_cells'] - sp['nonzero']) / sp['n_cells']:.1f}}}")
    L.append(rf"\def\spDrawnRatio{{{sp['drawn_ratio']:.1f}}}")
    for s_, tag in (("BEARING", "Bear"), ("MATCHED_CONTROL", "Ctrl"),
                    ("RANDOM", "Rand")):
        L.append(rf"\def\sp{tag}Tasks{{{sp['ntask'][s_]}}}")
        L.append(rf"\def\sp{tag}Helps{{{sp['helps'][s_]}}}")
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
    SIM_W, SIM_H = 100.0, 28.0
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
    FR_W, FR_H = 88.0, 38.0      # pt, drawable area of each panel
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

    # ---- figure 5: cross-benchmark paired representation contrasts -------
    for key in ("SR", "TR"):
        for bench, tag in (("lmev", "Lm"), ("scicode", "Sc"), ("swebench", "Sw")):
            m, lo, hi, n = xb[key][bench]
            L.append(rf"\def\xb{key}{tag}M{{{m:+.4f}}}")
            L.append(rf"\def\xb{key}{tag}Lo{{{lo:+.4f}}}")
            L.append(rf"\def\xb{key}{tag}Hi{{{hi:+.4f}}}")
            L.append(rf"\def\xb{key}{tag}N{{{n}}}")
    # Plot geometry, computed here so LaTeX does no arithmetic on a measurement.
    _XBW = 64.0    # pt, half-width of the value axis (column is 241pt; row
                   # labels take ~55pt, so a wider axis overflows)
    _XBS = 0.45    # value at the axis end
    for key in ("SR", "TR"):
        for bench, tag in (("lmev", "Lm"), ("scicode", "Sc"), ("swebench", "Sw")):
            m, lo, hi, _ = xb[key][bench]
            for nm, v in (("M", m), ("Lo", lo), ("Hi", hi)):
                L.append(rf"\def\xb{key}{tag}X{nm}{{{max(-_XBW, min(_XBW, v / _XBS * _XBW)):.2f}pt}}")
    # Benchmark-maturity macros for the prose. Typed numbers in a paragraph
    # drift from the artifact silently; these cannot.
    _scd = json.loads((REPO / "results/scicode/scaleup_all3.json").read_text())["design"]
    _sca = json.loads((REPO / "results/ledgers/repro/scicode"
                       / "scaleup_analysis.json").read_text())
    _swa = json.loads((REPO / "results/ledgers/repro/swebench"
                       / "representations_multirepo_final.json").read_text())["pooled"]
    L.append(rf"\def\sciPairs{{{_scd['n_pairs']}}}")
    L.append(rf"\def\sciMems{{{_scd['n_memories']}}}")
    L.append(rf"\def\sciTasks{{{_scd['n_tasks']}}}")
    L.append(rf"\def\sciArmRuns{{{_sca['n_arm_runs']}}}")
    L.append(rf"\def\sciMatched{{{_sca['MATCHED_CELL_SET_N']}}}")
    L.append(rf"\def\sciDiag{{{_scd['pct_diagonal']:.1f}}}")
    L.append(rf"\def\sciMedTasks{{{_scd['median_tasks_per_memory']}}}")
    L.append(rf"\def\sweMatched{{{_swa['MATCHED_CELL_SET_N']}}}")
    L.append(rf"\def\sweLocMiss{{{_swa['exclusions'].get('raw:localizer_miss', 0)}}}")
    _sr = _swa["both_arms_fail_matched"]["raw"]
    L.append(rf"\def\sweBafRaw{{{_sr['k']}/{_sr['n']}}}")
    L.append(rf"\def\sweRepos{{{len(_swa['cells_per_repo'])}}}")
    L.append(rf"\def\sweDomRepoPct{{{100.0 * _swa['DOMINATED_BY']['share']:.0f}}}")
    # Session-matched reader transfer -- the CANONICAL reader-generalization
    # result. It was typed into main.tex and no guard read it: planting
    # +0.5000 left both audit_claims.py and make_figures.py green, because
    # the former never read that paragraph and the latter never reads prose.
    _sm = json.loads((REPO / "results/ledgers/repro/raw_session_matched"
                      / "raw_session_matched_analysis.json").read_text())
    _lo, _hi = _sm["ci95_task_clustered"]
    L.append(rf"\def\rgSmDiff{{{_sm['paired_diff_gemma_minus_gptoss']:+.4f}}}")
    L.append(rf"\def\rgSmLo{{{_lo:+.4f}}}")
    L.append(rf"\def\rgSmHi{{{_hi:+.4f}}}")
    L.append(rf"\def\rgSmN{{{_sm['n_matched']}}}")        # REPLICATE ROWS
    L.append(rf"\def\rgSmCells{{{_sm['n_cells']}}}")      # cells -- the honest unit
    L.append(rf"\def\rgSmTasks{{{_sm['n_tasks']}}}")
    # The decomposition ON THE SESSION-MATCHED ROWS. Never mix this with
    # \rgWithoutDelta, which is the superseded cross-session figure.
    L.append(rf"\def\rgSmWithout{{{_sm['without_arm_change']:+.4f}}}")
    L.append(rf"\def\rgSmWith{{{_sm['with_arm_change']:+.4f}}}")
    L.append(rf"\def\rgSmWithoutShare{{{round(abs(_sm['without_arm_change'])/abs(_sm['with_arm_change'])*100)}}}")
    L.append(rf"\def\rgSmOss{{{_sm['deltaU_gptoss']:+.4f}}}")
    L.append(rf"\def\rgSmGem{{{_sm['deltaU_gemma']:+.4f}}}")

    for tag, bk in (("Lm", "lmev"), ("Sc", "scicode")):
        f = xb["_floors"][bk]
        L.append(rf"\def\xbFloor{tag}{{{f['rate']:.3f}}}")
        L.append(rf"\def\xbFloor{tag}K{{{f['disagreeing']}}}")
        L.append(rf"\def\xbFloor{tag}N{{{f['denominator']}}}")
    L.append(rf"\def\xbAxisW{{{_XBW:.1f}pt}}")
    L.append(rf"\def\xbAxisMax{{{_XBS:.2f}}}")
    L.append("")

    # ---- figure 6: reader generalization ---------------------------------
    # Per representation, the two readers' dU side by side with the paired
    # interval. The geometry is computed HERE; TikZ draws what it is given.
    RG_W, RG_H = 104.0, 36.0     # pt, drawable area
    RG_LO, RG_HI = -0.10, 0.70   # dU axis; covers every whisker end

    def rgx(v):
        return RG_W * (v - RG_LO) / (RG_HI - RG_LO)

    L.append("%% --- reader generalization (fig 6): gpt-oss vs Gemma readers ---")
    L.append("%% Matched cells only: interpretable under BOTH readers at the")
    L.append("%% same replicate depth. Memory text is byte-identical across")
    L.append("%% the two runs (1694/1694 verified), so only the reader differs.")
    for rep, tag in (("raw", "Raw"), ("summary", "Sum"), ("structured", "Str")):
        d = rg[rep]
        L.append(rf"\def\rg{tag}N{{{d['n']}}}")
        L.append(rf"\def\rg{tag}Tasks{{{d['n_tasks']}}}")
        L.append(rf"\def\rg{tag}Oss{{{d['oss']:+.4f}}}")
        L.append(rf"\def\rg{tag}Gem{{{d['gem']:+.4f}}}")
        L.append(rf"\def\rg{tag}Diff{{{d['diff']:+.4f}}}")
        L.append(rf"\def\rg{tag}Lo{{{d['lo']:+.4f}}}")
        L.append(rf"\def\rg{tag}Hi{{{d['hi']:+.4f}}}")
        L.append(rf"\def\rg{tag}XOss{{{rgx(d['oss']):.2f}pt}}")
        L.append(rf"\def\rg{tag}XGem{{{rgx(d['gem']):.2f}pt}}")
        L.append(rf"\def\rg{tag}XLo{{{rgx(d['lo']):.2f}pt}}")
        L.append(rf"\def\rg{tag}XHi{{{rgx(d['hi']):.2f}pt}}")
        L.append(rf"\def\rg{tag}XDiff{{{rgx(d['diff']):.2f}pt}}")
        # The paired difference is EXACTLY the gap between the two readers'
        # means -- the mean of per-cell differences equals the difference of
        # means on a paired set -- which is asserted, not assumed, below. So
        # the interval on the difference can be drawn on the SAME dU axis,
        # anchored at the gpt-oss point: it then excludes zero precisely when
        # the whisker does not cover that point. One panel, nothing dropped.
        L.append(rf"\def\rg{tag}XCiLo{{{rgx(d['oss'] + d['lo']):.2f}pt}}")
        L.append(rf"\def\rg{tag}XCiHi{{{rgx(d['oss'] + d['hi']):.2f}pt}}")
        L.append(rf"\def\rg{tag}Excl{{{'yes' if d['excl0'] else 'no'}}}")
        c = rgcorr[rep]
        L.append(rf"\def\rg{tag}RAll{{{c['r_all']:+.3f}}}")
        L.append(rf"\def\rg{tag}RNz{{{c['r_nz']:+.3f}}}")
        L.append(rf"\def\rg{tag}NNz{{{c['n_nz']}}}")
        L.append(rf"\def\rg{tag}ZeroBoth{{{c['zero_both']}}}")
        L.append(rf"\def\rg{tag}SignK{{{c['sign_k']}}}")
        L.append(rf"\def\rg{tag}SignN{{{c['sign_n']}}}")
        L.append(rf"\def\rg{tag}LabK{{{c['label_k']}}}")
        L.append(rf"\def\rg{tag}LabN{{{c['label_n']}}}")
    for v, nm in ((0.0, "Zero"), (0.2, "Two"), (0.4, "Four"), (0.6, "Six")):
        L.append(rf"\def\rgTick{nm}{{{rgx(v):.2f}pt}}")
    L.append(rf"\def\rgZeroX{{{rgx(0.0):.2f}pt}}")
    L.append(rf"\def\rgW{{{RG_W:.2f}pt}}")
    L.append(rf"\def\rgH{{{RG_H:.2f}pt}}")
    L.append(rf"\def\rgRows{{{rgmeta['n_gemma_rows']:,}}}".replace(",", "{,}"))
    # the within-memory BEARING-control contrast, the quantity Sec. 8 reports
    _bmc = json.loads((REPO / "results/ledgers/gemma_reader"
                       / "reader_transfer_analysis.json").read_text())
    for rep, tag in (("raw", "Raw"),):
        _r = _bmc["per_representation_matched"][rep]
        for who, wtag in (("gptoss", "Oss"), ("gemma", "Gem")):
            _b = _r[f"within_memory_bearing_minus_control_{who}"]
            L.append(rf"\def\rgBmc{tag}{wtag}{{{_b['mean']:+.4f}}}")
            L.append(rf"\def\rgBmc{tag}{wtag}Lo{{{_b['ci_lower']:+.4f}}}")
            L.append(rf"\def\rgBmc{tag}{wtag}Hi{{{_b['ci_upper']:+.4f}}}")
            L.append(rf"\def\rgBmc{tag}{wtag}Mem{{{_b['n_memories']}}}")
    _dec = _bmc["deltaU_decomposed_by_arm"]["raw"]
    L.append(rf"\def\rgWithoutShare{{{100.0 * _dec['share_of_deltaU_change_from_the_WITHOUT_arm']:.0f}}}")
    L.append(rf"\def\rgWithDelta{{{_dec['change_in_WITH_arm']:+.4f}}}")
    L.append(rf"\def\rgWithoutDelta{{{_dec['change_in_WITHOUT_arm']:+.4f}}}")
    L.append("")

    # ---- figure 6: the CANONICAL session-matched reader contrast ---------
    # The figure previously drew \rgRawDiff, the SUPERSEDED cross-session
    # value, beside prose quoting the canonical session-matched one. The
    # geometry below is the canonical arm's, and reader_session_matched()
    # fails the build if the two ever become the same number -- the drawing
    # could then no longer be shown to use the canonical one.
    SM_W = 92.0                     # pt, drawable width of panel A
    SM_LO, SM_HI = 0.00, 0.40       # dU axis; covers both points and the CI
    def smx(v):
        return SM_W * (v - SM_LO) / (SM_HI - SM_LO)

    L.append("%% --- reader transfer, SESSION-MATCHED (fig 6a) ------------")
    L.append("%% CANONICAL. 275 cells / 123 tasks / 550 replicate rows, both")
    L.append("%% arms in ONE session. The superseded cross-session +0.1268 is")
    L.append("%% NOT drawn. Exactly ONE interval is drawn, the PAIRED one:")
    L.append("%% the two readers' marginal intervals overlap by 0.0689, so")
    L.append("%% drawing them would invite a false 'no difference' reading.")
    L.append(rf"\def\smXOss{{{smx(sm['oss']):.2f}pt}}")
    L.append(rf"\def\smXGem{{{smx(sm['gem']):.2f}pt}}")
    # The paired interval is anchored at the gpt-oss point, which is exact:
    # on a paired set the mean of the differences IS the gap between means.
    L.append(rf"\def\smXCiLo{{{smx(sm['oss'] + sm['lo']):.2f}pt}}")
    L.append(rf"\def\smXCiHi{{{smx(sm['oss'] + sm['hi']):.2f}pt}}")
    for v, nm in ((0.0, "Zero"), (0.1, "One"), (0.2, "Two"), (0.3, "Three"),
                  (0.4, "Four")):
        L.append(rf"\def\smTick{nm}{{{smx(v):.2f}pt}}")
    L.append(rf"\def\smW{{{SM_W:.2f}pt}}")
    # Panel B: the matched per-cell agreement table, every count from the join.
    _c = sm["conf"]
    for so, st in ((1, "Pos"), (0, "Zero"), (-1, "Neg")):
        for sg, gt in ((1, "Pos"), (0, "Zero"), (-1, "Neg")):
            L.append(rf"\def\smC{st}{gt}{{{_c.get((so, sg), 0)}}}")
    L.append(rf"\def\smAgree{{{sm['agree']}}}")
    L.append(rf"\def\smBoth{{{sm['both']}}}")
    L.append(rf"\def\smZeroBoth{{{sm['zero_both']}}}")
    # Request-identity, in its own unit: JOINABLE REPLICATE ROWS (570),
    # which is a different number from the 550 scorable rows and the 275
    # cells. All three appear in this figure and must not be interchanged.
    L.append(rf"\def\smIdentN{{{sm['n_ident']:,}}}".replace(",", "{,}"))
    L.append(rf"\def\smIdentK{{{sm['same_hashes']['context_sha256']:,}}}".replace(",", "{,}"))
    L.append("")

    # ---- table 2: coverage ------------------------------------------------
    L.append("%% --- coverage (tab 2): eligible / attempted / completed ---")
    for bk, tag in (("lmev", "Lm"), ("scicode", "Sc"), ("swebench", "Sw")):
        c = cov[bk]
        L.append(rf"\def\cov{tag}Elig{{{c['eligible']:,}}}".replace(",", "{,}"))
        L.append(rf"\def\cov{tag}Att{{{c['attempted']:,}}}".replace(",", "{,}"))
        L.append(rf"\def\cov{tag}Done{{{c['completed']:,}}}".replace(",", "{,}"))
        L.append(rf"\def\cov{tag}Excl{{{c['excluded']:,}}}".replace(",", "{,}"))
        L.append(rf"\def\cov{tag}Pct{{{100.0 * c['completed'] / c['eligible']:.1f}}}")
    L.append(rf"\def\covScMatched{{{cov['scicode']['matched']}}}")
    L.append(rf"\def\covSwMatched{{{cov['swebench']['matched']}}}")
    L.append(rf"\def\covSwRepos{{{cov['swebench']['repos']}}}")
    _swx = cov["swebench"]["excl_detail"]
    L.append(rf"\def\covSwLocMiss{{{sum(v for k, v in _swx.items() if 'localizer' in k)}}}")
    L.append(rf"\def\covSwUnscored{{{sum(v for k, v in _swx.items() if 'unapplicable' in k)}}}")
    L.append(rf"\def\covSwUnavail{{{sum(v for k, v in _swx.items() if 'unavailable' in k)}}}")
    L.append("")

    dest = OVERLEAF / "figdata.tex"
    dest.write_text("\n".join(L) + "\n")
    print(f"\nwrote {dest}  ({len(L)} lines)")
    print("all figure data re-derived from tracked artifacts.")


ROMAN = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]

if __name__ == "__main__":
    main()

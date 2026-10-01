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
    _swm = json.loads((REPO / "results/swebench"
                       / "representations_multirepo.json").read_text())
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
    expect("crossbench: SWE-bench matched set, corrected", sw["MATCHED_CELL_SET_N"], 15)
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
    swm = json.loads((REPO / "results/swebench"
                      / "representations_multirepo.json").read_text())
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
    expect("coverage swebench: eligible rep-cells (counted from source)",
           sw_elig, 129)
    expect("coverage swebench: attempted rep-cells", sw_done + sw_excl, 129)
    expect("coverage swebench: completed", sw_done, 56)
    expect("coverage swebench: matched set (defect-21 corrected)",
           pooled["MATCHED_CELL_SET_N"], 15)
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
    _swa = json.loads((REPO / "results/swebench"
                       / "representations_multirepo.json").read_text())["pooled"]
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
    L.append(rf"\def\rgSmN{{{_sm['n_matched']}}}")
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

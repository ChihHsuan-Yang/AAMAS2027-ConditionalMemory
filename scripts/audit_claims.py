"""Claim-to-evidence audit: re-derive every headline number from tracked artifacts.

Not a text search of the manuscript -- a re-computation. A number that matches
the paper but was never recomputed is exactly the failure this project has hit
repeatedly (a value quoted into a durable document without re-derivation).

Run: /Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py
Exit 1 if any claim fails to reproduce.
"""
from __future__ import annotations
import collections, json, math, re, statistics, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FAIL = []


def check(name, got, want, tol=5e-4):
    ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
    print(f"  {'PASS' if ok else 'FAIL'}  {name:52} got {got!r}  want {want!r}")
    if not ok:
        FAIL.append(name)


def load(p):
    return [json.loads(l) for l in (REPO / p).read_text().splitlines() if l.strip()]


def arm_stats(rows):
    w = [r["reward_with_memory"] for r in rows if r["reward_with_memory"] is not None]
    o = [r["reward_without_memory"] for r in rows if r["reward_without_memory"] is not None]
    cells = collections.defaultdict(list)
    for r in rows:
        if r["reward_with_memory"] is None:
            continue
        cells[(r["memory_id"], r["future_task_id"])].append(
            (r["reward_with_memory"], r["reward_without_memory"]))
    bf = sum(1 for v in cells.values() if all(a == 0 and b == 0 for a, b in v))
    return sum(w) / len(w), sum(o) / len(o), bf, len(cells)


print("== Arms (from tracked slim artifacts) ==")
p_w, p_o, p_bf, p_n = arm_stats(load("results/ledgers/repro/pilot_cells_slim.jsonl"))
check("pilot accuracy WITH", round(p_w, 4), 0.1712)
check("pilot accuracy WITHOUT", round(p_o, 4), 0.1733)
check("pilot both-arms-fail", f"{p_bf}/{p_n}", "376/479")
o_w, o_o, o_bf, o_n = arm_stats(load("results/ledgers/repro/official_cells_slim.jsonl"))
check("official accuracy WITH", round(o_w, 4), 0.1146)
check("official accuracy WITHOUT", round(o_o, 4), 0.1208)
check("official both-arms-fail", f"{o_bf}/{o_n}", "402/480")

print("== Oracle contrast (pooled over both arms) ==")
keys = {tuple(k) for k in json.loads(
    (REPO / "results/ledgers/j1b_discriminative_oracle_thr8.json").read_text()
)["arms"]["handwritten"]["DISCRIMINATIVE_ORACLE"]["cell_keys"]}
allc = {}
for f in ("pilot", "official"):
    for r in load(f"results/ledgers/repro/{f}_cells_slim.jsonl"):
        if r["reward_with_memory"] is None:
            continue
        allc.setdefault((r["memory_id"], r["future_task_id"]), []).append(
            r["reward_with_memory"] - r["reward_without_memory"])
m = {k: statistics.mean(v) for k, v in allc.items()}
ins = [v for k, v in m.items() if k in keys]
out = [v for k, v in m.items() if k not in keys]
check("oracle cells n", len(ins), 22)
check("oracle mean dU", round(statistics.mean(ins), 4), 0.1364)
check("non-oracle mean dU", round(statistics.mean(out), 4), -0.0109)
check("difference", round(statistics.mean(ins) - statistics.mean(out), 4), 0.1473)

print("== Bearing scarcity (from the leakage manifest) ==")
rows = load("data/manifests/lmev2_leakage_small.jsonl")
qs = {json.loads(l)["id"]: json.loads(l)
      for l in Path("/tmp/lmev2/questions.jsonl").read_text().splitlines() if l.strip()}
pt = collections.Counter(r["task_id"] for r in rows)
disc = {t for t, c in pt.items() if 1 <= c <= 8}
det = {t for t in disc if t in qs and not qs[t]["eval_function"].startswith("llm_")}
check("discriminative tasks", len(disc), 76)
check("  of which deterministic", len(det), 75)
pm = collections.defaultdict(set)
for r in rows:
    if r["task_id"] in det:
        pm[r["memory_id"]].add(r["task_id"])
ge2 = {k: v for k, v in pm.items() if len(v) >= 2}
check("memories with >=1 bearing task", len(pm), 165)
check("memories with >=2 bearing tasks", len(ge2), 46)
check("  source episodes hosting them", len({k.split(":")[0] for k in ge2}), 23)
# BASIS PIN. The 76-task and 75-task bases give DIFFERENT edge counts and
# histograms (267 / {3:17,4:5} vs 266 / {3:18,4:4}). A draft of Sec. 8.1 mixed
# them. The executed design uses 75 (results/ledgers/k1_screened_design.json:
# n_discriminative_tasks=75, n_bearing_edges_total=266), so the paper must too.
check("bearing edges, on the 75-task basis", sum(len(v) for v in pm.values()), 266)
hist = collections.Counter(len(v) for v in pm.values())
check("  bear on exactly one task", hist[1], 119)
check("  bear on exactly two", hist[2], 18)
check("  bear on exactly three", hist[3], 18)
check("the executed design used the same basis",
      json.loads((REPO / "results/ledgers/k1_screened_design.json").read_text()
                 )["screening_yield_and_scarcity"]["n_bearing_edges_total"], 266)
_tex = (REPO.parent / "overleaf" / "main.tex").read_text()
_body = _tex[_tex.index("\\begin{document}"):]
_body = "\n".join(l for l in _body.split("\n") if not l.lstrip().startswith("%"))
check("the paper does not quote the other basis's edge count",
      "267 bearing" in _body, False)

print("== Screened design ==")
d = load("data/manifests/k1_screened_cells.jsonl")
mem = collections.defaultdict(set)
for r in d:
    mem[r["stratum"]].add(r["memory_id"])
check("all three strata are the same memories",
      mem["BEARING"] == mem["MATCHED_CONTROL"] == mem["RANDOM"], True)
check("  that memory count", len(mem["BEARING"]), 60)
pairs = collections.Counter((r["memory_id"], r["task_id"]) for r in d)
check("stratum join is 1:1", max(pairs.values()), 1)

print("== Screened run (the headline) ==")
sc = load("results/deltau_screened/cells.jsonl")
cell = collections.defaultdict(list)
for r in sc:
    if r.get("reward_with_memory") is None:
        continue
    cell[(r["provenance"]["stratum"], r["memory_id"], r["future_task_id"])].append(
        (r["reward_with_memory"], r["reward_without_memory"]))
for s_, want_bf, want_n, want_du in [("BEARING", 73, 139, 0.3453),
                                     ("MATCHED_CONTROL", 115, 146, 0.0274),
                                     ("RANDOM", 611, 872, 0.0642)]:
    sub = {k: v for k, v in cell.items() if k[0] == s_}
    bf = sum(1 for v in sub.values() if all(a == 0 and b == 0 for a, b in v))
    du = [statistics.mean(a - b for a, b in v) for v in sub.values()]
    check(f"{s_} both-arms-fail", f"{bf}/{len(sub)}", f"{want_bf}/{want_n}")
    check(f"{s_} mean dU", round(statistics.mean(du), 4), want_du)

cm = {k: statistics.mean(a - b for a, b in v) for k, v in cell.items()}
bym = collections.defaultdict(lambda: {"BEARING": [], "MATCHED_CONTROL": []})
for (s_, m_, t_), x in cm.items():
    if s_ in ("BEARING", "MATCHED_CONTROL"):
        bym[m_][s_].append(x)
paired = {m_: statistics.mean(d["BEARING"]) - statistics.mean(d["MATCHED_CONTROL"])
          for m_, d in bym.items() if d["BEARING"] and d["MATCHED_CONTROL"]}
nz = [x for x in paired.values() if abs(x) > 1e-9]
check("paired memories", len(paired), 60)
check("non-zero contributors", len(nz), 35)
check("paired all-memories mean", round(statistics.mean(paired.values()), 4), 0.3349)
check("paired contributors-only mean", round(statistics.mean(nz), 4), 0.5740)
# the false-convergence guard: these two 35s are DIFFERENT sets
nbear = collections.Counter(m_ for (s_, m_, t_) in cm if s_ == "BEARING")
ge2 = {m_ for m_, c in nbear.items() if c >= 2}
check("the two 35s overlap on only 25 (NOT convergence)",
      len({m_ for m_, x in paired.items() if abs(x) > 1e-9} & ge2), 25)

print("== Sign reversal and the additive null ==")
per_s = collections.defaultdict(lambda: collections.defaultdict(list))
for k, v in cm.items():
    per_s[k[0]][k[1]].append(statistics.mean(v) if isinstance(v, list) else v)
for s_, want_el, want_fl in [("BEARING", 35, 0), ("MATCHED_CONTROL", 35, 1), ("RANDOM", 60, 17)]:
    el = {m: v for m, v in per_s[s_].items() if len(v) >= 2}
    fl = sum(1 for v in el.values() if any(x > 0 for x in v) and any(x < 0 for x in v))
    check(f"{s_} flip-eligible", len(el), want_el)
    check(f"{s_} flips", fl, want_fl)

print("== Similarity is weakly informative ==")
import math as _m
sims, dus = [], []
for r in sc:
    if r.get("reward_with_memory") is None or r.get("semantic_similarity") is None:
        continue
    sims.append(r["semantic_similarity"])
    dus.append(r["reward_with_memory"] - r["reward_without_memory"])
def _rho(x, y):
    rx = {v: i for i, v in enumerate(sorted(set(x)))}
    ry = {v: i for i, v in enumerate(sorted(set(y)))}
    a = [rx[v] for v in x]; b = [ry[v] for v in y]
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((i - ma) * (j - mb) for i, j in zip(a, b))
    den = _m.sqrt(sum((i - ma) ** 2 for i in a) * sum((j - mb) ** 2 for j in b))
    return num / den if den else 0.0
check("similarity rho is small (<0.25)", abs(_rho(sims, dus)) < 0.25, True)

print("== Representation scale-up: the frontier, CHARGED for formation ==")
# The uncharged column was published first and read as "Summary is 5.5x more
# token-efficient". MEMORY_PROTOCOL section 5 requires the charge; A1.5
# pre-registers the asymmetry as the correctness test. Both columns are
# re-derived here so the corrected reading cannot silently revert.
_rsr = load("results/repr_scaleup/cells.jsonl")
_rawr = [r for r in load("results/deltau_screened/cells.jsonl")
         if (r.get("provenance") or {}).get("stratum") in ("BEARING", "MATCHED_CONTROL")]
_memr = load("results/repr_scaleup/memories.jsonl")

def _loc(r):
    pr = r.get("provenance") or {}
    return pr.get("memory_unit_locator") or (
        r.get("source_episode_metadata") or {}).get("memory_unit_locator")

def _pk(r):
    return f"{_loc(r)}|{r['future_task_id']}"

_byrep = {"raw": _rawr}
for _r in _rsr:
    _byrep.setdefault(_r["memory_representation"], []).append(_r)
_common = set.intersection(*[{_pk(r) for r in v} for v in _byrep.values()])
check("representation arms share 277 pair keys", len(_common), 277)

# amortized formation tokens per cell, per representation
_form = {"raw": 0.0}
for _rep in ("summary", "structured"):
    _ms = [m for m in _memr if m["representation"] == _rep]
    _tot = sum((m["extraction_input_tokens"] or 0) + (m["extraction_output_tokens"] or 0)
               for m in _ms)
    _form[_rep] = _tot / len({_pk(r) for r in _byrep[_rep]})

def _per1k(rep, stratum, charged):
    cell, tok = collections.defaultdict(list), {}
    for r in _byrep[rep]:
        k = _pk(r)
        if k not in _common or r.get("delta_utility") is None:
            continue
        if stratum and (r["provenance"] or {})["stratum"] != stratum:
            continue
        cell[k].append(float(r["delta_utility"]))
        tok[k] = float(r["memory_tokens_exposed"])
    num = sum(statistics.mean(v) for v in cell.values())
    den = sum(tok[k] + (_form[rep] if charged else 0.0) for k in tok)
    return 1000.0 * num / den

# BEARING cells, the table in docs/REPRESENTATION_RESULT.md
for _rep, _unch, _ch in (("raw", 0.0368, 0.0368),
                         ("summary", 0.2054, 0.0342),
                         ("structured", 0.0622, 0.0076)):
    check(f"{_rep} dU/1k BEARING exposure-only",
          round(_per1k(_rep, "BEARING", False), 4), _unch)
    check(f"{_rep} dU/1k BEARING formation-charged",
          round(_per1k(_rep, "BEARING", True), 4), _ch)

# A1.5: raw must be EXACTLY unchanged, the model-written arms must move.
check("A1.5 raw is bit-identical when formation is charged",
      _per1k("raw", "BEARING", False) == _per1k("raw", "BEARING", True), True)
check("A1.5 summary MOVES when formation is charged",
      _per1k("summary", "BEARING", False) != _per1k("summary", "BEARING", True), True)
check("A1.5 structured MOVES when formation is charged",
      _per1k("structured", "BEARING", False) != _per1k("structured", "BEARING", True), True)
# The correction itself: uncharged Summary beats Raw, charged it does not.
check("uncharged Summary beats Raw (the flattering reading)",
      _per1k("summary", "BEARING", False) > _per1k("raw", "BEARING", False), True)
check("CHARGED Summary does NOT beat Raw (the protocol's reading)",
      _per1k("summary", "BEARING", True) > _per1k("raw", "BEARING", True), False)

print("== Representation scale-up: the PAIRED frontier (Fig. 4's y-axis) ==")
# The figure plots the PAIRED within-memory effect (BEARING minus MATCHED_CONTROL,
# one difference per memory), not the unpaired BEARING mean above. Both are
# legitimate; they are DIFFERENT estimands and the figure must not mix them.
# Pinned here so the figure's y-axis cannot drift from the prose in Sec. 8.
_cellrep = collections.defaultdict(lambda: collections.defaultdict(list))
for _rep, _rows in _byrep.items():
    for _r in _rows:
        if _pk(_r) not in _common or _r.get("reward_with_memory") is None:
            continue
        _cellrep[_rep][_pk(_r)].append(
            _r["reward_with_memory"] - _r["reward_without_memory"])
_stratof, _tokof = {}, collections.defaultdict(dict)
for _rep, _rows in _byrep.items():
    for _r in _rows:
        if _pk(_r) not in _common:
            continue
        _stratof[_pk(_r)] = (_r["provenance"] or {})["stratum"]
        _tokof[_rep][_pk(_r)] = float(_r["memory_tokens_exposed"])
_locof = {k: k.split("|")[0] for k in _common}
check("the joined frontier basis is 57 memories", len(set(_locof.values())), 57)

def _paired(rep):
    """One difference per memory: mean dU on its BEARING cells minus its control."""
    bymem = collections.defaultdict(lambda: {"BEARING": [], "MATCHED_CONTROL": []})
    for k, v in _cellrep[rep].items():
        bymem[_locof[k]][_stratof[k]].append(statistics.mean(v))
    return [statistics.mean(d["BEARING"]) - statistics.mean(d["MATCHED_CONTROL"])
            for d in bymem.values() if d["BEARING"] and d["MATCHED_CONTROL"]]

for _rep, _want, _wantnz in (("raw", 0.3174, 33), ("summary", 0.0613, 26),
                             ("structured", -0.0498, 20)):
    _d = _paired(_rep)
    check(f"{_rep} paired B-control (57 memories)",
          round(statistics.mean(_d), 4), _want)
    check(f"  {_rep} non-zero contributors", sum(1 for x in _d if abs(x) > 1e-9),
          _wantnz)

# Mean tokens on the SAME 277 cells -- the figure's x-axis. Quoting a token count
# from a different cell set than the utility it is divided by is the mixed-basis
# defect; pinning both here on one basis makes that impossible to reintroduce.
for _rep, _want in (("raw", 9227.9), ("summary", 322.8), ("structured", 237.8)):
    check(f"{_rep} mean exposed tokens over the 277",
          round(statistics.mean(_tokof[_rep].values()), 1), _want)
# FORMATION ON THE FIGURE'S OWN BASIS. _form above is the constant behind the
# already-published BEARING table: it totals all 60 written memories and divides
# by that representation's own pair-key count (285 summary / 277 structured).
# The figure is drawn on the 277-cell join, which uses only the 57 memories
# common to all three arms -- so it must charge those 57, over those 277 cells,
# or the numerator and denominator again describe different objects. The two
# constants differ, and pinning both is what stops one being used for the other.
_joinlocs = set(_locof.values())
_formfig = {"raw": 0.0}
for _rep in ("summary", "structured"):
    _ms = [m for m in _memr if m["representation"] == _rep
           and m["memory_unit_locator"] in _joinlocs]
    if len(_ms) != 57:
        FAIL.append(f"{_rep} formation basis is {len(_ms)} memories, expected 57")
    _formfig[_rep] = sum((m["extraction_input_tokens"] or 0)
                         + (m["extraction_output_tokens"] or 0) for m in _ms) / len(_common)
for _rep, _want in (("summary", 1637.2996), ("structured", 1675.6173)):
    check(f"{_rep} formation tok/cell, FIGURE basis (57 mem / 277 cells)",
          round(_formfig[_rep], 4), _want)
for _rep, _want in (("summary", 1626.2035), ("structured", 1715.0253)):
    check(f"  {_rep} formation tok/cell, published-table basis (differs)",
          round(_form[_rep], 4), _want)
check("the two formation bases are NOT interchangeable",
      round(_form["structured"], 1) != round(_formfig["structured"], 1), True)

def _paired_per1k(rep, charged):
    return 1000.0 * statistics.mean(_paired(rep)) / (
        statistics.mean(_tokof[rep].values()) + (_formfig[rep] if charged else 0.0))

for _rep, _we, _wc in (("raw", 0.0344, 0.0344), ("summary", 0.1899, 0.0313),
                       ("structured", -0.2094, -0.0260)):
    check(f"{_rep} paired dU/1k exposed", round(_paired_per1k(_rep, False), 4), _we)
    check(f"{_rep} paired dU/1k charged", round(_paired_per1k(_rep, True), 4), _wc)

# The figure's whole point, as two pinned inequalities.
check("exposure-only, Summary looks >5x Raw",
      round(_paired_per1k("summary", False) / _paired_per1k("raw", False), 2), 5.52)
check("charged, Raw does NOT beat Summary by anything like 5x",
      round(_paired_per1k("raw", True) / _paired_per1k("summary", True), 2), 1.10)
# GUARD. A draft of Sec. 8 said charging formation "makes Raw the more efficient
# representation by roughly 5x". That is Raw vs STRUCTURED, or Raw vs Summary only
# if the writer call is charged to every read instead of amortized over the 4.86
# cells that reuse it. Charged and amortized, Raw's margin over Summary is 1.10x.
check("Raw's charged margin over Summary is under 1.5x (NOT ~5x)",
      _paired_per1k("raw", True) / _paired_per1k("summary", True) < 1.5, True)
check("the paper does not claim a ~5x Raw win over Summary",
      "more efficient representation by" in _body and "roughly $5\\times$" in _body,
      False)
check("measured reuse factor", round(len(_common) / len(set(_locof.values())), 4),
      4.8596)

print("== Representation scale-up: write-pass instrument facts ==")
_ns = sum(1 for m in _memr if m["representation"] == "structured")
_nbad = sum(1 for m in _memr if m["representation"] == "structured" and not m["ok"])
_nbad_fin = sum(1 for m in _memr if m["representation"] == "structured"
                and not m["ok"] and not m["truncated"])
_nfin = sum(1 for m in _memr if m["representation"] == "structured" and not m["truncated"])
check("malformed structured, all writes", f"{_nbad}/{_ns}", "3/60")
check("malformed structured, writes that FINISHED", f"{_nbad_fin}/{_nfin}", "0/57")
check("truncated summaries admitted as ok=True",
      sum(1 for m in _memr if m["representation"] == "summary"
          and m["truncated"] and m["ok"]), 7)

print("== No variance share is quoted as a result ==")
# P1-I13: this check was VOID. The exemption ("not identif" in body) was tested
# over the WHOLE BODY, so a single occurrence anywhere -- there are two, both in
# comments -- disarmed it for every banned term. Verified by planting
# "a variance share of 0.41 (95% CI [0.33, 0.49])" in body prose: the old check
# returned PASS. The defect class is a guard whose exemption is not scoped to
# the thing it exempts.
#
# What actually matters is not the PHRASE but a NUMBER attached to it. The paper
# must be able to say "we quote no variance share"; it must not be able to say
# "the interaction's variance share is 0.41". So: strip comments, then flag a
# banned phrase only when a numeral sits within 60 characters of it.
tex = (REPO.parent / "overleaf" / "main.tex").read_text()
body = tex[tex.index("\\begin{document}"):]
body = "\n".join(l for l in body.split("\n") if not l.lstrip().startswith("%"))
banned = ["variance share", "interaction share", "share of variance",
          "variance shares", "interaction shares"]
hits = []
for b in banned:
    for m in re.finditer(re.escape(b), body.lower()):
        near = body[max(0, m.start() - 60): m.end() + 60]
        if re.search(r"\d*\.\d+|\b\d+\s*%|\b0\.\d", near):
            hits.append(f"{b}: ...{' '.join(near.split())}...")
check("no variance share quoted as a number in the manuscript", hits, [])

print("== Benchmark maturity wording ==")
# The SciCode pilot's intervals ALL cross zero. Calling the cross-benchmark
# difference an "inversion" or "reversal" of the representation ranking
# overstates it. Permitted: "the point-estimate ordering differs", or
# "LongMemEval's Raw-dominant ordering is not reproduced in the SciCode pilot".
_tex3 = REPO.parent / "overleaf" / "main.tex"
if _tex3.is_file():
    _b3 = "\n".join(l for l in _tex3.read_text().split("\n")
                    if not l.lstrip().startswith("%"))
    _low = _b3.lower()
    _bad = []
    for _w in ("invert", "inversion", "reversal of the representation",
               "ranking reverses", "ranking is reversed"):
        for _m in re.finditer(re.escape(_w), _low):
            _near = _low[max(0, _m.start() - 160): _m.end() + 160]
            if "scicode" in _near or "cross-benchmark" in _near:
                _ctx = ' '.join(_low[max(0, _m.start() - 55): _m.end() + 85].split())
                _bad.append(f"{_w!r} @char {_m.start()}: ...{_ctx}...")
    check("manuscript does not call the SciCode difference an inversion", _bad, [])

print("== Efficiency ratios stated in the manuscript ==")
# P1-I13: the paper said the charged reversal is "roughly 5x". True of
# Structured (4.84x); for SUMMARY it is 1.08x -- indistinguishable -- and the
# sentence is about Summary. Formation is amortised per MEMORY, not per cell.
_rr = {"raw": (0.0368, 0.0368), "summary": (0.2054, 0.0342),
       "structured": (0.0622, 0.0076)}
check("uncharged Summary/Raw ratio", round(_rr["summary"][0] / _rr["raw"][0], 2), 5.58)
check("charged Raw/Summary ratio is ~1, NOT ~5",
      round(_rr["raw"][1] / _rr["summary"][1], 2), 1.08)
check("charged Raw/Structured ratio", round(_rr["raw"][1] / _rr["structured"][1], 2), 4.84)
_tex2 = REPO.parent / "overleaf" / "main.tex"
if _tex2.is_file():
    _b2 = _tex2.read_text()
    check("manuscript does NOT claim a ~5x charged reversal for Summary",
          ("more efficient representation by roughly $5" not in _b2), True)

print("== SWE-bench: the arm-symmetry blocker and its controls ==")
# The standing rule is "no SWE-bench number enters any table until WITH-arm
# apply failure reaches parity". These checks re-derive BOTH halves of that
# sentence from the artifacts, so a doc claiming parity while the artifact
# disagrees fails here rather than in review.
_sw = REPO / "results/swebench"
_par2 = _sw / "parity_v2.json"
_par1 = _sw / "parity_v1_control.json"
_ctl = [_sw / "scorer_control.json", _sw / "scorer_control_sympy.json"]

if all(f.is_file() for f in [_par2, _par1, *_ctl]):
    _s2 = json.loads(_par2.read_text())["summary"]
    _s1 = json.loads(_par1.read_text())["summary"]

    # -- the scorer positive control, BOTH runners, BOTH directions ---------
    _tot = _pas = _neg_ok = _neg_n = 0
    _kinds: set = set()
    for f in _ctl:
        c = json.loads(f.read_text())["summary"]
        _tot += c["n_attempted"]; _pas += c["n_pass"]
        _neg_n += c.get("negative_control_attempted", 0)
        _neg_ok += c.get("negative_control_pass", 0)
        _kinds.update(c.get("runner_kinds", []))
    check("scorer control passes on every attempted cell", f"{_pas}/{_tot}", "20/20")
    check("scorer control negative control fires", f"{_neg_ok}/{_neg_n}", "20/20")
    # A control run on only one runner is not known to discriminate: it was
    # django-only, passed 10/10, and the pytest runner behind it was 0/5.
    check("scorer control covers BOTH runners", sorted(_kinds), ["django", "pytest"])

    # -- parity ------------------------------------------------------------
    check("v2 apply-failure gap is zero", _s2["apply_fail_gap"], 0.0)
    check("v2 WITH apply failures", _s2["apply_fail_WITH"], 0)
    check("v2 WITHOUT apply failures", _s2["apply_fail_WITHOUT"], 0)
    check("v2 every cell passed the arm-symmetry check",
          _s2["all_cells_arm_symmetric"], True)
    check("v2 WITH arm shows no diff contagion",
          _s2["diff_contagion_WITH"]["total_diff_marker_lines"], 0)

    # -- the control that makes the repair a measurement, not a hope -------
    # Same cells, same budget, only the prompt differs.
    check("v1 control reproduces the asymmetry", _s1["apply_fail_gap"], 0.375)
    check("v1 control WITH apply failures", _s1["apply_fail_WITH"], 3)
    check("v1 control WITHOUT apply failures", _s1["apply_fail_WITHOUT"], 0)
    check("v1 control shows the diff contagion v2 removes",
          _s1["diff_contagion_WITH"]["total_diff_marker_lines"], 5)
    check("parity comparison has no budget confound",
          _s1["max_tokens"] == _s2["max_tokens"], True)
    check("parity comparison is on the same interpretable denominator",
          _s1["n_interpretable"] == _s2["n_interpretable"] == 8, True)

    _c1 = {c["task_id"]: c for c in json.loads(_par1.read_text())["cells"]}
    _c2 = {c["task_id"]: c for c in json.loads(_par2.read_text())["cells"]}
    check("parity arms compared the same cells", sorted(_c1) == sorted(_c2), True)
    check("parity arms were shown identical regions",
          all(_c1[k]["region_lines"] == _c2[k]["region_lines"] for k in _c1), True)
else:
    print("  SKIP  SWE-bench parity/control artifacts not present")

_floor2 = _sw / "floor_pilot_v2.json"
if _floor2.is_file():
    _f = json.loads(_floor2.read_text())["summary"]
    _fc = json.loads(_floor2.read_text())["cells"]
    # THE non-negotiable. An unapplicable edit is None, never 0.0: scoring
    # those as zero on the v1 data would have shown memory HARMING (2/7 vs
    # 3/7), harm manufactured entirely by an edit-format artifact.
    _viol = [(c["task_id"], a) for c in _fc for a in ("WITH", "WITHOUT")
             if c["arms"].get(a, {}).get("edit_status") not in (None, "ok")
             and c["arms"][a].get("reward") is not None]
    check("NO apply-failure is scored as a reward", _viol, [])
    check("summary agrees: no apply failure scored zero",
          _f["no_apply_failure_scored_zero"], True)
    check("floor pilot ran the symmetric prompt",
          _f["prompt_version"], "swebench_v2_symmetric")
    check("floor pilot: every cell arm-symmetric", _f["all_cells_arm_symmetric"], True)
    # both-arms-fail must be re-derivable from the cells, not just asserted
    _interp = [c for c in _fc if c["interpretable"] and c["arms"]]
    _bf = sum(1 for c in _interp
              if (c["arms"]["WITH"].get("reward") or 0.0) == 0.0
              and (c["arms"]["WITHOUT"].get("reward") or 0.0) == 0.0)
    check("both-arms-fail re-derives from the cells", _bf, _f["both_arms_fail"])
    check("both-arms-fail denominator is the interpretable count",
          len(_interp), _f["both_arms_fail_denominator"])
    check("floor pilot both-arms-fail is BELOW the 50% stop threshold",
          f"{_f['both_arms_fail']}/{_f['both_arms_fail_denominator']}", "12/32")
    check("floor pilot both-arms-fail pct", _f["both_arms_fail_pct"], 37.5)
    # Parity must hold UNDER MEASUREMENT, not only on the screen.
    check("floor pilot apply-failure gap stays at parity",
          abs(_f["apply_fail_gap"]) <= 0.10, True)
    check("floor pilot solve rates", (_f["solve_WITHOUT"], _f["solve_WITH"]), (15, 17))
    # no_block is the diff-contagion signature; it must be gone from WITH.
    check("no_block is absent from the WITH arm",
          _f["edit_status_WITH"].get("no_block", 0), 0)
    check("floor pilot WITH arm shows no diff contagion",
          _f["diff_contagion_WITH"]["total_diff_marker_lines"], 0)

    # 🔴 The paired interval is NOT quoted as evidence. With 25 pairs of which
    # only 4 are discordant and all 4 the same sign, a donor-clustered
    # resample can only go non-positive by drawing none of the 4 discordant
    # donors -- p = (13/17)^17 = 0.0105. The bootstrap lower bound is bounded
    # away from zero almost by construction. The exact test is the honest one.
    _b = sum(1 for c in _interp
             if c["arms"]["WITH"].get("reward") == 1.0
             and c["arms"]["WITHOUT"].get("reward") == 0.0)
    _c = sum(1 for c in _interp
             if c["arms"]["WITH"].get("reward") == 0.0
             and c["arms"]["WITHOUT"].get("reward") == 1.0)
    _n = _b + _c
    _p = (sum(math.comb(_n, i) for i in range(min(_b, _c) + 1)) * 2 / 2 ** _n
          if _n else 1.0)
    check("discordant pairs (WITH-better, WITHOUT-better)", (_b, _c), (4, 0))
    check("McNemar exact p does NOT reach significance", round(min(_p, 1.0), 4), 0.125)
    check("no significance is claimed for DeltaU in the decision doc",
          "p = 0.125" in _bc if (_bc := (REPO / "docs/BENCHMARK_C_DECISION.md").read_text()
                                 if (REPO / "docs/BENCHMARK_C_DECISION.md").is_file()
                                 else "") else False, True)
    # Coverage: the floor number is a django number and must say so.
    _repos = sorted({c["repo"] for c in _fc})
    check("floor pilot repositories covered", _repos, ["django/django"])
else:
    print("  SKIP  floor_pilot_v2.json not present")

print("== CIs printed in the manuscript must match the artifact ==")
# P1-I12: the paper once printed an episode-clustered CI no artifact contained,
# because the audit checked the point estimate and never the interval.
_k3 = REPO / "results/deltau_screened/analysis/k3_screened_analysis.json"
_tex = REPO.parent / "overleaf" / "main.tex"
if _k3.is_file() and _tex.is_file():
    _p = json.loads(_k3.read_text())["paired_within_memory"]["BEARING_vs_MATCHED_CONTROL"]
    _body = _tex.read_text()
    for _name, _key in [("episode-clustered", "episode_clustered_ci"),
                        ("memory bootstrap", "memory_bootstrap_ci")]:
        lo, hi = _p[_key]
        want = f"[+{lo:.4f}, +{hi:.4f}]"
        check(f"manuscript prints the artifact's {_name} CI {want}", want in _body, True)
else:
    print("  SKIP  artifact or manuscript not present")

print()
if FAIL:
    print(f"AUDIT FAILED: {len(FAIL)} claim(s) did not reproduce: {FAIL}")
    sys.exit(1)
print(f"AUDIT PASSED: all {len(FAIL) == 0 and 'checked'} claims re-derived from tracked artifacts.")

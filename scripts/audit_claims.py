"""Claim-to-evidence audit: re-derive every headline number from tracked artifacts.

Not a text search of the manuscript -- a re-computation. A number that matches
the paper but was never recomputed is exactly the failure this project has hit
repeatedly (a value quoted into a durable document without re-derivation).

Run: /Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py
Exit 1 if any claim fails to reproduce.
"""
from __future__ import annotations
import collections, json, math, random, re, statistics, sys
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

# The benchmarks must stay asymmetric: LongMemEval is the primary positive
# result; SciCode and SWE-bench are boundary evidence whose contrasts cross
# zero. Language implying all three establish the same effect is forbidden.
if _tex3.is_file():
    _b4 = "\n".join(l for l in _tex3.read_text().split("\n")
                    if not l.lstrip().startswith("%"))
    _l4 = _b4.lower()
    _sym = []
    for _p in ("all three benchmarks show", "all three benchmarks confirm",
               "all three benchmarks establish", "replicated across all three",
               "consistent across all three benchmarks",
               "confirmed on all three", "holds on all three"):
        if _p in _l4:
            _sym.append(_p)
    check("manuscript does not claim all three benchmarks show the same effect",
          _sym, [])
    # The limits sentence must actually be present: a caveat that is deleted
    # is not detectable by a ban-list, so require the positive statement too.
    _has_limit = ("does not generalize" in _l4 or "not reproduced" in _l4
                  or "do not generalize" in _l4)
    check("manuscript states the cross-benchmark ordering does NOT generalize",
          _has_limit, True)
    # SWE-bench redistribution. TWO independent markers are required, because
    # a single licence-absence phrase is satisfiable incidentally: a first
    # version of this check passed a planted document where the ruling had
    # been reversed to "declares a permissive licence", because the unrelated
    # clause "no license field in its hub metadata" still matched.
    # Match against whitespace-normalised text with LaTeX markup stripped:
    # the sentence wraps across lines and contains \emph{...}, so a regex
    # written against the on-screen wording fails on the file as stored.
    _flat = re.sub(r"\\emph\{([^}]*)\}", r"\1", _l4)
    _flat = re.sub(r"\\texttt\{([^}]*)\}", r"\1", _flat)
    _flat = re.sub(r"[\s\\]+", " ", _flat)
    _m1 = bool(re.search(
        r"corpus declares no licen[cs]e|licen[cs]e is undeclared",
        _flat))
    _m2 = bool(re.search(
        r"absent licen[cs]e is not a permissive", _flat))
    _m3 = bool(re.search(
        r"(instance identifiers|instance ids)[^.]{0,140}"
        r"(derived measurements|measurements only)", _flat))
    check("manuscript states the SWE-bench corpus licence is undeclared "
          f"(markers declares-no={_m1} absent-not-permissive={_m2} ids-only={_m3}; "
          "2 of 3 required)",
          sum((_m1, _m2, _m3)) >= 2, True)

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

print("== no tracked artifact or doc may de-anonymise the submission ==")
# DEFECT_REGISTER #23 recurring: GATE 2b's pattern was right but its SUBJECT
# was the HF staging tree only. results/ledgers/ is git-tracked and the README
# advertises results/ledgers/repro/ as the reviewer-facing slice; nine of those
# files carried an absolute /Users/<name>/ path and no gate looked. A scanner
# aimed at one tree certifies nothing about another.
_ID_RX = [(re.compile(r"/Users/[A-Za-z0-9._-]+/"), "absolute macOS home path"),
          (re.compile(r"/home/[A-Za-z0-9._-]+/"), "absolute Linux home path")]
#: Paths a reviewer is pointed at, or that ship. Docs are included because the
#: manuscript's sources live beside them and a copied path travels.
_SCAN_ROOTS = ["results/ledgers", "docs/hf_card", "docs/submission"]
_leaks, _scanned = [], 0
for _root in _SCAN_ROOTS:
    _rp = REPO / _root
    if not _rp.is_dir():
        continue
    for _f in sorted(_rp.rglob("*")):
        if not _f.is_file() or _f.suffix in {".png", ".pdf", ".npy"}:
            continue
        _scanned += 1
        try:
            _t = _f.read_text(errors="replace")
        except Exception:
            continue
        for _rx, _why in _ID_RX:
            for _m in _rx.finditer(_t):
                _leaks.append(f"{_f.relative_to(REPO)}: {_why} {_m.group(0)!r}")
# A clean scan over zero files is not a pass -- it is a dead glob.
check("identity scan actually opened files (not a vacuous glob)",
      _scanned > 20, True)
check("no absolute home path in any tracked/reviewer-facing artifact",
      _leaks[:5], [])
# The manuscript itself.
_mt = REPO.parent / "overleaf" / "main.tex"
if _mt.is_file():
    _mb = _mt.read_text()
    check("manuscript carries no absolute home path",
          [m.group(0) for rx, _ in _ID_RX for m in rx.finditer(_mb)][:5], [])

print("== Reader transfer: the SESSION-MATCHED result must lead ==")
# SA-FINAL-AUDIT. The reader-transfer paragraph was the ONLY headline with no
# check at all: planting "+0.5000 [+0.4000, +0.6000]" as the session-matched
# effect left this audit green and make_figures.py green, because the former
# never read the paragraph and the latter never reads main.tex prose.
#
# The superseded CROSS-SESSION figure (+0.1268, arms 11 h apart) is still the
# macro the paragraph leads with. The session-matched arms (14 min apart,
# memory_text byte-identical 550/550) are the current measurement and are
# TYPED. These checks re-derive the session-matched contrast from the tracked
# slim rows -- an independent loader, not a re-read of the analysis file --
# and then require the manuscript to print it.
_rsm = REPO / "results/ledgers/repro/raw_session_matched"
_mtex = REPO.parent / "overleaf" / "main.tex"
if (_rsm / "raw_gptoss_slim.jsonl").is_file() and _mtex.is_file():
    def _sm_load(n):
        return [json.loads(l) for l in (_rsm / n).read_text().splitlines() if l.strip()]

    def _sm_key(r):
        pr = r.get("provenance") or {}
        return (pr.get("memory_unit_locator"), r["future_task_id"], r.get("replicate_id"))

    _o = _sm_load("raw_gptoss_slim.jsonl")
    _g = _sm_load("raw_gemma_slim.jsonl")
    # The arms must differ in the READER and in nothing else that names an arm.
    check("session-matched arms are the two readers",
          (sorted({r["reader_model"] for r in _o}),
           sorted({r["reader_model"] for r in _g})),
          (["gpt-oss-120b"], ["gemma-4-31B-it"]))
    check("session-matched arms share one cluster (not a cluster comparison)",
          sorted({r["reader_cluster"] for r in _o} | {r["reader_cluster"] for r in _g}),
          ["metis"])
    check("session-matched condition_ids are disjoint",
          set({r["condition_id"] for r in _o}).isdisjoint(
              {r["condition_id"] for r in _g}), True)
    # 🔴 The whole point of this arm: BOTH executed on the same date. A
    # comparator from another day is defect #25 and this contrast exists
    # because the published one had it.
    check("both session-matched arms ran in ONE session (same UTC date)",
          sorted({r["created_at_utc"][:10] for r in _o}
                 | {r["created_at_utc"][:10] for r in _g}),
          ["2026-10-01"])
    # Gemma reports no reasoning tokens; a 0 there would be an absence written
    # as a measurement (defect #18's shape).
    check("Gemma rows never coerce reasoning_tokens to 0",
          sum(1 for r in _g if r["reasoning_tokens"] == 0), 0)
    check("no errored row was scored instead of left null",
          sum(1 for r in _o + _g
              if r["error_code_if_any"] and r["delta_utility"] is not None), 0)

    _O = {_sm_key(r): r["delta_utility"] for r in _o if r["delta_utility"] is not None}
    _G = {_sm_key(r): r["delta_utility"] for r in _g if r["delta_utility"] is not None}
    _mk = sorted(set(_O) & set(_G), key=str)
    check("session-matched n", len(_mk), 550)
    _sm_mean = statistics.mean(_G[k] - _O[k] for k in _mk)
    check("session-matched dU gpt-oss",
          round(statistics.mean(_O[k] for k in _mk), 4), 0.2182)
    check("session-matched dU Gemma",
          round(statistics.mean(_G[k] for k in _mk), 4), 0.3164)
    check("session-matched paired reader effect", round(_sm_mean, 4), 0.0982)

    # Task-clustered bootstrap, recomputed here rather than read back.
    _bt = collections.defaultdict(list)
    for k in _mk:
        _bt[k[1]].append(_G[k] - _O[k])
    _tl = list(_bt.values())
    _rng = random.Random(5)
    _bs = []
    for _ in range(4000):
        _s = []
        for _ in _tl:
            _s += _rng.choice(_tl)
        _bs.append(sum(_s) / len(_s))
    _bs.sort()
    _lo, _hi = _bs[int(0.025 * len(_bs))], _bs[int(0.975 * len(_bs))]
    # Seed-to-seed drift is ~0.002, so the ASSERTION is that the interval
    # excludes zero and brackets the published endpoints -- not equality.
    check("session-matched interval EXCLUDES zero", _lo > 0, True)
    check("session-matched CI lower is near the published +0.0247",
          abs(_lo - 0.0247) < 0.005, True)
    check("session-matched CI upper is near the published +0.1730",
          abs(_hi - 0.1730) < 0.005, True)

    # Reader-only means the bytes did not change. Vacuous unless the
    # comparison is shown able to see a one-byte edit, so plant one.
    _full = REPO / "results/raw_session_matched"
    if (_full / "raw_gptoss.jsonl").is_file():
        _fo = {_sm_key(r): r.get("memory_text")
               for r in (json.loads(l) for l in (_full / "raw_gptoss.jsonl").open())}
        _fg = {_sm_key(r): r.get("memory_text")
               for r in (json.loads(l) for l in (_full / "raw_gemma.jsonl").open())}
        _same = sum(1 for k in _mk if _fo.get(k) == _fg.get(k) is not None)
        check("memory_text byte-identical across the two readers",
              f"{_same}/{len(_mk)}", "550/550")
        _fg2 = dict(_fg)
        _fg2[_mk[0]] = (_fg2[_mk[0]] or "") + "X"
        check("  that check's OWN positive control fires on a 1-byte edit",
              sum(1 for k in _mk if _fo.get(k) == _fg2.get(k) is not None) < _same,
              True)
    else:
        print("  SKIP  full session-matched rows absent (memory_text unverifiable here)")

    # ---- what the MANUSCRIPT must say about all of the above ----
    _mb2 = _mtex.read_text()
    _mp = "\n".join(l for l in _mb2.split("\n") if not l.lstrip().startswith("%"))
    # 🔴 Check the RENDERED PDF, not the .tex source. A first version grepped
    # main.tex for the literal digits and broke the moment the numbers were
    # correctly converted from typed text to generated \rgSm* macros -- it was
    # testing the authoring layer when the claim is about what a READER sees.
    # Reading the PDF also covers both forms at once: a typed number and a
    # macro-expanded one are indistinguishable here, which is the point.
    import subprocess as _sp
    _pdf = _mtex.parent / "main.pdf"
    _rend = ""
    if _pdf.is_file():
        _rend = _sp.run(["pdftotext", str(_pdf), "-"],
                        capture_output=True, text=True).stdout
    _flat = " ".join(_rend.replace("$", " ").split())
    if not _rend.strip():
        print("  SKIP  main.pdf absent or unreadable -- cannot check rendered text")
    else:
        check("RENDERED paper prints the session-matched effect +0.0982",
              "+0.0982" in _flat, True)
        check("RENDERED paper prints the session-matched interval",
              ("[+0.0247, +0.1730]" in _flat
               or "[+0.0247 , +0.1730]" in _flat), True)
    # 🔴 The superseded figure may appear, but it must NOT be the only one and
    # the paragraph must name the confound. These two markers are what stop
    # +0.1268 reading as the current measurement.
    check("manuscript names the session confound beside the reader effect",
          ("deterministic within a session" in _mp
           and "-0.0327" in _mp.replace("$", "")), True)
    check("the session-matched decomposition is present, not the 54% share",
          ("-0.0364" in _mp.replace("$", "")), True)
    # The WITHOUT-arm share macro is the CONTAMINATED quantity. If the
    # manuscript ever prints it as a clean reader attribution, fail.
    _bad_share = re.search(
        r"(about|roughly)\s+half[^.]{0,80}(weaker reader|a weaker reader)[^.]{0,40}\.",
        " ".join(_mp.split()))
    check("manuscript does not state the WITHOUT share as a clean reader attribution",
          _bad_share.group(0) if _bad_share else None, None)
else:
    print("  SKIP  session-matched artifacts or manuscript not present")

print("== Writer x Reader factorial: four nulls, and no same-family claim ==")
# SA-FINAL-AUDIT. The factorial EXECUTED (2026-10-01, all four arms in one
# session) and every one of its eight contrasts spans zero. Nothing checked
# that the manuscript's description of it stayed true.
_wf = REPO / "results/ledgers/writer_factorial/writer_factorial_analysis.json"
if _wf.is_file() and _mtex.is_file():
    _wfa = json.loads(_wf.read_text())
    _spans = []
    for _rep, _blk in _wfa["CONTRASTS"].items():
        for _cname in ("WRITER_main_effect", "READER_main_effect",
                       "SAME_FAMILY_effect", "INTERACTION"):
            _tc = _blk[_cname]["task_clustered"]
            _spans.append((f"{_rep}/{_cname}", _tc["excludes_zero"]))
    check("every factorial contrast spans zero (no same-family advantage)",
          [n for n, e in _spans if e], [])
    check("all eight factorial contrasts were read", len(_spans), 8)
    # The four arms must be ONE session, or the contrast is confounded by day.
    check("the factorial's four arms are session-matched",
          bool(_wfa.get("_all_four_arms_are_session_matched")), True)
    # The estimators must recover a KNOWN planted effect, else a zero is
    # uninterpretable (this project's own "positive-control every null").
    check("the factorial's contrast estimators are positive-controlled",
          _wfa["_positive_control_contrast_estimators"]["fires"], True)
    # 🔴 The manuscript currently calls this experiment unrun. It ran.
    _mp2 = "\n".join(l for l in _mtex.read_text().split("\n")
                     if not l.lstrip().startswith("%"))
    _flat2 = " ".join(_mp2.split())
    _unrun = re.search(r"writer\s*\$?\\?times\$?\s*reader factorial[^.]{0,90}"
                       r"(unrun|not run|planned and unrun)", _flat2)
    check("manuscript does NOT call the executed factorial unrun",
          _unrun.group(0) if _unrun else None, None)
    _onewriter = re.search(r"(the writer is still one|writer is still one model)", _flat2)
    check("manuscript does not say the writer is still one model",
          _onewriter.group(0) if _onewriter else None, None)
else:
    print("  SKIP  writer-factorial artifact not present")

print("== Withdrawn / superseded figures must not reappear ==")
# SA-FINAL-AUDIT. docs/RESULT_INDEX.md section G lists figures that may not be
# quoted. Only one was mechanically enforced (the 267-edge basis). These are
# the rest, each pinned to the artifact that supersedes it.
if _mtex.is_file():
    _mp3 = "\n".join(l for l in _mtex.read_text().split("\n")
                     if not l.lstrip().startswith("%"))
    _flat3 = " ".join(_mp3.split())
    # The 93.6% truncation share was computed against the WITHDRAWN 3,400-token
    # cap. At the ADOPTED 2,000-token budget it is 98.5% of units, and on the
    # executed cells it is 96.6%. Re-derived here so the right number has a
    # source rather than only the wrong one having a ban.
    _scr = REPO / "results/deltau_screened/cells.jsonl"
    if _scr.is_file():
        _cellt = {}
        for _l in _scr.read_text().splitlines():
            if not _l.strip():
                continue
            _r = json.loads(_l)
            _cellt[(_r["memory_id"], _r["future_task_id"])] = (
                _r.get("memory_embedding_reference") or {}).get("input_truncated")
        _tr = sum(1 for v in _cellt.values() if v)
        check("truncated-prefix share, re-derived on the executed cells",
              round(100.0 * _tr / len(_cellt), 1), 96.6)
    check("manuscript does not quote the WITHDRAWN 93.6% truncation share",
          "93.6" in _flat3, False)
    check("manuscript does not quote the withdrawn 120-unit embedding figure",
          bool(re.search(r"120 (memory )?units", _flat3)), False)
    # F_empty is null in the artifact with a WITHOUT_ARM_REUSED flag.
    _fe = None
    for _m in re.finditer(r"F_\{?\\?mathrm\{?empty\}?\}?[^.]{0,70}?(?:=|\{=\})\s*0",
                          _flat3):
        _tail = _flat3[_m.end(): _m.end() + 70]
        # "a measured F_empty = 0 RAISES rather than passes" is the protocol
        # rule (the artifact's value is null with a WITHOUT_ARM_REUSED flag),
        # not a reported measurement. Only a reporting use is forbidden.
        if re.match(r"[\s$]*(raises|aborts|must raise)", _tail):
            continue
        _fe = _m.group(0)
        break
    check("manuscript does not report F_empty as a measured zero", _fe, None)
    # A harmful-memory RATE is forbidden: the design screened FOR bearing.
    _hr = re.search(r"harmful[- ]memory rate of\s*[\d.]+|"
                    r"harm(ful)? rate (of|is|was)\s*[\d.]+", _flat3)
    check("manuscript quotes no harmful-memory rate",
          _hr.group(0) if _hr else None, None)

print("== Captions: counts must be named by the unit they are in ==")
# SA-FINAL-AUDIT. \rgRows is a ROW count (1,694 = 847 cells x 2 replicates).
# Figure 6's caption called it "cells". Re-derived from the slim rows so the
# distinction is a measurement, not a reading of the caption.
_gslim = REPO / "results/ledgers/repro/gemma_reader/transfer_cells_slim.jsonl"
if _gslim.is_file() and _mtex.is_file():
    _gr = [json.loads(l) for l in _gslim.read_text().splitlines() if l.strip()]
    _gcells = {((r.get("provenance") or {}).get("memory_unit_locator"),
                r["future_task_id"], r["memory_representation"]) for r in _gr}
    check("Gemma transfer ROW count (what \\rgRows holds)", len(_gr), 1694)
    check("Gemma transfer CELL count (what it is NOT)", len(_gcells), 847)
    check("rows are not cells here (the caption must not conflate them)",
          len(_gr) != len(_gcells), True)
    _cap = re.search(r"Mean \$\\Delta U\$\s*\n?per reader over the \$\\rgRows\$ (\w+)",
                     _mtex.read_text())
    check("Figure 6 caption calls \\rgRows rows, not cells",
          _cap.group(1) if _cap else "NOT-FOUND", "rows")

print()
if FAIL:
    print(f"AUDIT FAILED: {len(FAIL)} claim(s) did not reproduce: {FAIL}")
    sys.exit(1)
print(f"AUDIT PASSED: all {len(FAIL) == 0 and 'checked'} claims re-derived from tracked artifacts.")

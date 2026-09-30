"""Claim-to-evidence audit: re-derive every headline number from tracked artifacts.

Not a text search of the manuscript -- a re-computation. A number that matches
the paper but was never recomputed is exactly the failure this project has hit
repeatedly (a value quoted into a durable document without re-derivation).

Run: /Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py
Exit 1 if any claim fails to reproduce.
"""
from __future__ import annotations
import collections, json, statistics, sys
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

print("== No variance share is quoted as a result ==")
tex = (REPO.parent / "overleaf" / "main.tex").read_text()
body = tex[tex.index("\\begin{document}"):]
banned = ["variance share", "interaction share", "share of variance"]
hits = [b for b in banned if b in body.lower() and "not identif" not in body.lower()]
check("no variance share quoted in the manuscript", hits, [])

print()
if FAIL:
    print(f"AUDIT FAILED: {len(FAIL)} claim(s) did not reproduce: {FAIL}")
    sys.exit(1)
print(f"AUDIT PASSED: all {len(FAIL) == 0 and 'checked'} claims re-derived from tracked artifacts.")

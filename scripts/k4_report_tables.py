#!/usr/bin/env python3
"""Emit the report's results tables from the K3 artifact. No recomputation.

Every number printed is READ from results/deltau_screened/analysis/
k3_screened_analysis.json. This script exists so the report's tables cannot
drift from the artifact: if a number is not in the artifact, it does not get
printed, rather than being filled in from memory.
"""
import json, sys
from pathlib import Path
A=Path('/Users/bellayang/Documents/2026/p1_memory_utility/repo/results/deltau_screened/analysis/k3_screened_analysis.json')
S=Path('/Users/bellayang/Documents/2026/p1_memory_utility/repo/results/deltau_screened/summary.json')
if not A.exists(): sys.exit(f"MISSING {A}")
j=json.loads(A.read_text()); summ=json.loads(S.read_text()) if S.exists() else {}
def f(x,n=4):
    return "—" if x is None else (f"{x:.{n}f}" if isinstance(x,(int,float)) else str(x))
STR=("BEARING","MATCHED_CONTROL","RANDOM")

print("### Run\n")
for k in ("planned_calls","real_endpoint_calls","cache_hits","errors","rows_written",
          "n_cells","n_memories","n_source_episodes","n_tasks","wall_clock_s"):
    if k in summ: print(f"- {k}: **{summ[k]}**")
ctx=summ.get("context_tokens_with_arm") or {}
if ctx: print(f"- context tokens: min {ctx.get('min')} median **{ctx.get('median')}** max {ctx.get('max')}")

print("\n### 1. both-arms-fail per stratum (instrument capacity)\n")
print("| stratum | both-arms-fail | n cells | Wilson 95% CI |")
print("|---|---|---|---|")
for s in STR:
    b=(j["per_stratum"].get(s) or {}).get("both_arms_fail") or {}
    ci=b.get("wilson_ci") or [None,None]
    print(f"| {s} | **{f(b.get('rate'))}** | {b.get('n_cells')} | [{f(ci[0])}, {f(ci[1])}] |")
c=j.get("_unscreened_comparator") or {}
print(f"\nUnscreened comparator: handwritten **{c.get('handwritten_all_cells')}**, official **{c.get('official_all_cells')}**")

print("\n### 2. ΔU distribution before labelling, per stratum\n")
print("| stratum | n cells | positive | zero | negative | mean ΔU over cells |")
print("|---|---|---|---|---|---|")
for s in STR:
    d=(j["per_stratum"].get(s) or {}).get("delta_u_distribution_before_labelling") or {}
    p=d.get("per_cell_mean") or {}
    print(f"| {s} | {p.get('n_cells')} | {p.get('positive')} | {p.get('zero')} | "
          f"{p.get('negative')} | **{f(d.get('mean_delta_over_cells'))}** |")

print("\n### 3. Flip rates per stratum (unit-level and episode-clustered)\n")
print("| stratum | robust | naive | denom (units) | Wilson CI | episodes | clustered CI |")
print("|---|---|---|---|---|---|---|")
for s in STR:
    ps=j["per_stratum"].get(s) or {}
    fl=(ps.get("labels_and_flips") or {}).get("flips") or {}
    ec=(ps.get("flip_episode_clustered") or {}).get("robust_flip") or {}
    rb=fl.get("robust") if not isinstance(fl.get("robust"),dict) else (fl["robust"] or {}).get("point")
    nv=fl.get("naive") if not isinstance(fl.get("naive"),dict) else (fl["naive"] or {}).get("point")
    ci=fl.get("robust_ci") or [None,None]
    cc=ec.get("ci") or [None,None]
    print(f"| {s} | {f(rb)} | {f(nv)} | {fl.get('denominator')} | [{f(ci[0])},{f(ci[1])}] | "
          f"{ec.get('n_clusters')} | [{f(cc[0])},{f(cc[1])}] |")

print("\n### 4. Excess over the additive null (prereg A1.1)\n")
print("| stratum | observed | additive-null mean | p (one-sided) | excess |")
print("|---|---|---|---|---|")
for s in STR:
    a=(j["per_stratum"].get(s) or {}).get("additive_null") or {}
    ob=a.get("observed"); ob=ob.get("robust") if isinstance(ob,dict) else ob
    if isinstance(ob,dict): ob=ob.get("point")
    nm=a.get("null_mean")
    ex=(ob-nm) if isinstance(ob,(int,float)) and isinstance(nm,(int,float)) else None
    print(f"| {s} | {f(ob)} | {f(nm)} | {f(a.get('p_one_sided'))} | {f(ex)} |")

print("\n### 5. Floors per stratum (all positive-controlled)\n")
print("| stratum | F_exec[ΔU] (diag) | F_empty | F_judge | pc F_exec fires | pc F_judge fires |")
print("|---|---|---|---|---|---|")
for s in STR:
    fl=(j["per_stratum"].get(s) or {}).get("floors") or {}
    pc=fl.get("positive_controls") or {}
    print(f"| {s} | {f((fl.get('F_exec_delta') or {}).get('point'))} | "
          f"{f((fl.get('F_empty') or {}).get('point'))} | {f((fl.get('F_judge') or {}).get('point'))} | "
          f"{(pc.get('F_exec') or {}).get('fires')} | {(pc.get('F_judge') or {}).get('fires')} |")
rf=j.get("reference_floor_pooled") or {}
print(f"\nPOOLED reference floor used for all labels: **{f(rf.get('point'))}**")

print("\n### 6. Contrasts\n")
print("| contrast | mean A | mean B | difference | p (two-sided) | n cells A / B |")
print("|---|---|---|---|---|---|")
for k,v in (j.get("contrasts") or {}).items():
    print(f"| {k} | {f(v.get('mean_a'))} | {f(v.get('mean_b'))} | **{f(v.get('observed_difference'))}** | "
          f"**{f(v.get('p_two_sided'))}** | {v.get('n_cells_a')} / {v.get('n_cells_b')} |")

print("\n### 7. Variance decomposition identifiability\n")
pd_=j.get("pooled_decomposition") or {}
print(f"- POOLED identified: **{pd_.get('identified')}**")
for fg in (pd_.get("at_upper_boundary_flags") or []): print(f"  - ⚠️ {fg[:150]}")
sh=(pd_.get("decomposition") or {}).get("shares") or {}
for k2,v2 in sh.items(): print(f"  - {k2}: {f(v2,6)}")
cr=pd_.get("crossing") or {}
print(f"- tasks/memory mean **{f((cr.get('tasks_per_memory') or {}).get('mean'),1)}** "
      f"(prior 8); memories/task mean {f((cr.get('memories_per_task') or {}).get('mean'),1)}")
print(f"- tasks seen by 1 memory: **{cr.get('n_tasks_seen_by_1_memory')}** of {cr.get('n_tasks')} "
      f"(prior 93 of 220); by >=10 memories: **{cr.get('n_tasks_seen_by_ge10_memories')}**")
for d,e in (j.get("shared_grid_decomposition") or {}).items():
    print(f"- shared grid {d}: {e.get('n_memories')}x{e.get('n_core_tasks')} crossed, "
          f"identified=**{e.get('identified')}**")
    for fg in (e.get("at_upper_boundary_flags") or []): print(f"    ⚠️ {fg[:120]}")
    ms=(e.get("method_of_moments") or {}).get("shares") or {}
    if ms: print(f"    MoM shares: { {k3: round(v3,4) for k3,v3 in ms.items()} }")

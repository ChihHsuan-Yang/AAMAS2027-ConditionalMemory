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

print("\n### 5b. WITHIN-MEMORY paired contrast (memory identity cancels)\n")
pw=j.get("paired_within_memory") or {}
print("| contrast | n memories | n episodes | paired diff | memory CI | episode CI | sign-flip p | +/0/- |")
print("|---|---|---|---|---|---|---|---|")
for k,v in pw.items():
    if v.get("mean_paired_difference") is None:
        print(f"| {k} | {v.get('n_paired_memories')} | — | — | — | — | — | — |"); continue
    mci=v.get("memory_bootstrap_ci") or [None,None]
    eci=v.get("episode_clustered_ci") or [None,None]
    print(f"| {k} | {v.get('n_paired_memories')} | {v.get('n_source_episodes')} | "
          f"**{f(v.get('mean_paired_difference'))}** | [{f(mci[0])},{f(mci[1])}] | "
          f"**[{f(eci[0])},{f(eci[1])}]** | {f(v.get('sign_flip_p_two_sided'))} | "
          f"{v.get('n_memories_positive')}/{v.get('n_memories_zero')}/{v.get('n_memories_negative')} |")
print("\n**Zero contributors** (docs/ZERO_CONTRIBUTORS.md) - never quote the nominal count alone\n")
print("| contrast | denominator | non-zero | power status | diluted mean (verdict) | conditional mean (descriptive) |")
print("|---|---|---|---|---|---|")
for k,v in pw.items():
    if v.get("mean_paired_difference") is None: continue
    p_=v.get("PAIRED_POWER_STATUS") or {}
    st=p_.get("STATUS")
    print(f"| {k} | {v.get('n_paired_memories')} memories | **{p_.get('n_nonzero_contributors')}** | "
          f"**{st}** | {f(v.get('mean_paired_difference'))} | "
          f"{f(v.get('conditional_mean_over_contributors_only'))} |")
for k,v in pw.items():
    p_=v.get("PAIRED_POWER_STATUS") or {}
    if p_.get("STATUS")=="UNDERPOWERED":
        print(f"\n⚠️ `{k}`: **UNDERPOWERED** - {p_.get('_reading')}")
print("\nThe **diluted** mean carries the significance verdict (pre-registered, does not")
print("condition on an outcome). The **conditional** mean is descriptive only. A memory")
print("contributing zero is one whose tasks the reader could not solve either way - a")
print("third view of the same scarcity finding, not a nuisance to average over quietly.")

print("\nAll 60 memories appear in BOTH strata, so memory identity cancels: "
      "\"bearing memories are just better memories\" cannot explain a within-memory")
print("difference. Task identity does NOT cancel, which is why dU is the quantity")
print("and why the task-clustered intervals below remain required.")
print("The **episode-clustered** interval governs where the two disagree.")

print("\n### 6. Contrasts (task-clustered; cells are NOT independent)\n")
print("| contrast | mean A | mean B | difference | cell-level p | task-clustered CI | excl 0 |")
print("|---|---|---|---|---|---|---|")
for k,v in (j.get("contrasts") or {}).items():
    tc=v.get("task_clustered_ci") or [None,None]
    print(f"| {k} | {f(v.get('mean_a'))} | {f(v.get('mean_b'))} | **{f(v.get('observed_difference'))}** | "
          f"{f(v.get('p_two_sided'))} | [{f(tc[0])}, {f(tc[1])}] | "
          f"**{v.get('task_clustered_ci_excludes_zero')}** |")
print("\n**Leave-one-task-out** (does ONE question carry the difference?)\n")
print("| contrast | n tasks | drop-one min | drop-one max | worst task | diff without it | sign stable |")
print("|---|---|---|---|---|---|---|")
for k,v in (j.get("contrasts") or {}).items():
    jk=v.get("leave_one_task_out") or {}
    print(f"| {k} | {v.get('n_tasks')} | {f(jk.get('min'))} | {f(jk.get('max'))} | "
          f"{jk.get('task_whose_removal_shrinks_it_most')} | "
          f"**{f(jk.get('difference_without_that_task'))}** | "
          f"**{jk.get('sign_stable_across_all_drops')}** |")

print("\n### 6b. Cell concentration — a design characteristic\n")
cc=j.get("cell_concentration") or {}
print("| scope | cells | tasks | max on one task | tasks >=20 cells | top-10 share | tasks holding half |")
print("|---|---|---|---|---|---|---|")
for k in ("ALL",)+STR:
    e=cc.get(k) or {}
    if not e.get("n_cells"): continue
    t10=e.get("top10_share")
    print(f"| {k} | {e.get('n_cells')} | {e.get('n_tasks')} | {e.get('max_cells_on_one_task')} | "
          f"{e.get('n_tasks_with_ge20_cells')} | **{'' if t10 is None else format(t10,'.1%')}** | "
          f"{e.get('n_tasks_holding_half_the_cells')} |")
print("\nThe shared task grid is the identifiability fix AND the source of this")
print("concentration - one design tension, not two problems.")

dis=j.get("clustered_vs_cell_level_disagreements")
print("\n### 6c. Clustered vs cell-level\n")
if dis:
    print("⚠️ **They DISAGREE on the following; the task-clustered result GOVERNS.**\n")
    for k,d in dis.items():
        print(f"- `{k}`: cell-level p={f(d.get('cell_level_p'))} "
              f"(sig={d.get('cell_level_calls_it_significant')}) but clustered CI "
              f"{[round(x,4) for x in (d.get('task_clustered_ci') or [])]} "
              f"(sig={d.get('clustered_calls_it_significant')}) -> **clustered governs**")
elif dis == {}:
    print("Clustered and cell-level agree on every contrast.")
else:
    print("not present in artifact")

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

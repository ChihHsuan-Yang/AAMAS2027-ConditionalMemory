"""Analyse the SWE-bench representation arm on the SAME basis as Figure 5.

The basis is not negotiable and is enforced here rather than described:

* **matched cells only** -- a cell enters only if it is interpretable under
  ALL THREE representations. The SciCode scale-up had to adopt this when its
  per-representation denominators diverged (127/134/130); comparing means over
  different cell sets compares different cells.
* **interpretable** = the localizer hit the region AND both arms produced an
  applicable edit, so a reward exists. An unapplicable edit is ``None``, never
  0.0 -- scoring it as zero manufactures harm out of an edit-format artifact,
  which is the defect that voided the v1 pilot.
* the reported quantity is the **paired contrast** dU(rep) - dU(raw) per cell,
  with a **task-clustered** bootstrap, because that is the one quantity
  LongMemEval and SciCode also define, and it differences out each benchmark's
  execution floor.

It also re-derives the both-arms-fail gate on the matched set rather than
inheriting the presence pilot's 37.5%: a different cell set is a different
gate.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path

REPS = ("raw", "summary", "structured")


def _boot(vals, tasks, n=20000, seed=7):
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
    return [round(out[int(0.025 * n)], 4), round(out[int(0.975 * n)], 4)]


def _boot_diff(A, B, tasks, n=20000, seed=11):
    rng = random.Random(seed)
    byt = collections.defaultdict(list)
    for x, y, t in zip(A, B, tasks):
        byt[t].append((x, y))
    keys = list(byt)
    out = []
    for _ in range(n):
        s = []
        for _ in keys:
            s += byt[rng.choice(keys)]
        out.append(sum(p[0] for p in s) / len(s) - sum(p[1] for p in s) / len(s))
    out.sort()
    return [round(out[int(0.025 * n)], 4), round(out[int(0.975 * n)], 4)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/swebench/representations_v1.json")
    ap.add_argument("--out", default="results/swebench/representations_analysis.json")
    a = ap.parse_args()

    d = json.loads(Path(a.src).read_text())
    cells = d["cells"]

    du: dict[str, dict] = {r: {} for r in REPS}
    baf: dict[str, list] = {r: [] for r in REPS}
    excluded = collections.Counter()
    for c in cells:
        if c.get("excluded"):
            excluded[c["representation"]] += 1
            continue
        if not c["localizer_recall"]:
            excluded[f"{c['representation']}:localizer_miss"] += 1
            continue
        arms = c["arms"]
        w, wo = arms.get("WITH", {}), arms.get("WITHOUT", {})
        if w.get("reward") is None or wo.get("reward") is None:
            excluded[f"{c['representation']}:unapplicable_or_unscored"] += 1
            continue
        k = (c["memory_id"], c["task_id"])
        du[c["representation"]][k] = w["reward"] - wo["reward"]
        baf[c["representation"]].append(w["reward"] == 0.0 and wo["reward"] == 0.0)

    matched = sorted(set.intersection(*[set(du[r]) for r in REPS])) if all(du[r] for r in REPS) else []
    tasks = [k[1] for k in matched]

    out = {
        "analysis_version": "swebench_representation_v1",
        "source_artifact": a.src,
        "GOVERNING": "task_clustered",
        "basis": ("matched cells only -- interpretable under ALL THREE "
                  "representations; reward None (unapplicable edit) is an "
                  "exclusion, never 0.0"),
        "per_representation_interpretable": {r: len(du[r]) for r in REPS},
        "exclusions": dict(excluded),
        "MATCHED_CELL_SET_N": len(matched),
        "repos_present": sorted({c["repo"] for c in cells}),
        "contagion_dirty_excluded": d["summary"]["contagion_dirty_excluded"],
        "write_failures": d["summary"]["write_failures"],
        "delta_u_matched": {},
        "paired_contrasts": {},
        "both_arms_fail_matched": {},
    }
    if not matched:
        out["VERDICT"] = "NO_MATCHED_CELLS"
        out["_what_this_means"] = (
            "No cell is interpretable under all three representations, so no "
            "representation comparison can be made on this run. This is a "
            "reportable outcome, not a failure to analyse: it says the arm is "
            "underpowered at this cell count, and it must NOT be patched by "
            "falling back to unmatched per-representation means.")
        Path(a.out).write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1)[:1200])
        return 0

    for r in REPS:
        v = [du[r][k] for k in matched]
        out["delta_u_matched"][r] = {
            "mean": round(sum(v) / len(v), 4),
            "ci95_task_clustered": _boot(v, tasks),
            "helped": sum(1 for z in v if z > 0),
            "hurt": sum(1 for z in v if z < 0),
            "tied": sum(1 for z in v if z == 0), "n": len(v)}
    # both-arms-fail on the matched set
    bafm = {r: 0 for r in REPS}
    denom = {r: 0 for r in REPS}
    for c in cells:
        if c.get("excluded") or not c["localizer_recall"]:
            continue
        k = (c["memory_id"], c["task_id"])
        if k not in matched:
            continue
        w, wo = c["arms"].get("WITH", {}), c["arms"].get("WITHOUT", {})
        if w.get("reward") is None or wo.get("reward") is None:
            continue
        denom[c["representation"]] += 1
        if w["reward"] == 0.0 and wo["reward"] == 0.0:
            bafm[c["representation"]] += 1
    out["both_arms_fail_matched"] = {
        r: {"k": bafm[r], "n": denom[r],
            "rate": round(bafm[r] / denom[r], 4) if denom[r] else None}
        for r in REPS}

    for x, y in (("structured", "raw"), ("summary", "raw"),
                 ("structured", "summary")):
        A = [du[x][k] for k in matched]
        B = [du[y][k] for k in matched]
        ci = _boot_diff(A, B, tasks)
        out["paired_contrasts"][f"{x}_minus_{y}"] = {
            "mean": round(sum(p - q for p, q in zip(A, B)) / len(A), 4),
            "ci95_task_clustered": ci,
            "separates_from_zero": bool(ci[0] > 0 or ci[1] < 0)}

    anysep = any(v["separates_from_zero"] for v in out["paired_contrasts"].values())
    out["ORDERING_VERDICT"] = "SEPARATED" if anysep else "NOT_ESTABLISHED"
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in (
        "MATCHED_CELL_SET_N", "per_representation_interpretable",
        "both_arms_fail_matched", "delta_u_matched", "paired_contrasts",
        "ORDERING_VERDICT")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

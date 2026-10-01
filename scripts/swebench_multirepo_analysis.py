"""Multi-repo SWE-bench representation analysis: per-repo AND pooled.

WHY THIS SCRIPT EXISTS
----------------------
Every SWE-bench number shipped so far is django-only. ``sympy`` has a working
runner and a passing scorer control and had never been run, so "django-heavy"
was a fact about the campaign, not about the harness. This pools the two runs.

THE RULES IT ENFORCES RATHER THAN DESCRIBES
-------------------------------------------
* **Matched-set rule.** A cell enters only if it is interpretable under ALL
  THREE representations. Per-representation denominators differ (sympy
  4/5/5, django 16/15/18), and a mean over different cell sets compares
  different cells.
* **reward None is an exclusion, never 0.0.** An unapplicable edit or a
  truncated completion is "could not be scored". Coercing it to 0.0
  manufactures harm out of an edit-format artefact.
* **A pooled number must state its composition.** Every pooled figure here
  carries ``n_repos`` and a per-repo cell count, and a ``DOMINATED_BY`` field
  fires when one repo supplies >=60% of the pooled cells. A pooled mean whose
  composition is hidden is the defect this project has already named.
* **Protocol identity is checked, not assumed.** Two artifacts are poolable
  only if every pinned protocol field agrees. A disagreement ABORTS.

POSITIVE CONTROLS (``--self-test``)
-----------------------------------
A null here would otherwise be indistinguishable from a bad key, a bad path,
or a bootstrap that cannot move. Four controls, each of which must FAIL the
thing it guards:

1. the pooled loader must notice a dropped source file;
2. the protocol-identity gate must ABORT on a planted field mismatch;
3. the bootstrap must SEPARATE from zero on a planted signal (a CI that never
   separates would report every real effect as "not established");
4. the matched-set rule must SHRINK when a representation loses a cell.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
import sys
from pathlib import Path
from typing import Any

REPS = ("raw", "summary", "structured")

# Pinned fields that must agree before two runs may be pooled. A change to any
# of them defines a new arm (docs/MODEL_ARMS.md), never additional data.
PROTOCOL_FIELDS = (
    "mode", "prompt_version", "patch_format", "prompt_variant", "model",
    "cluster", "temperature", "reasoning_effort", "max_tokens",
    "writer_max_tokens", "structured_variant", "benchmark_version",
    "WITHOUT_shared_across_representations",
)

DOMINANCE_THRESHOLD = 0.60


# -------------------------------------------------------------------------
# estimators
# -------------------------------------------------------------------------

def _boot(vals: list[float], tasks: list[str], n: int = 20000,
          seed: int = 7) -> list[float]:
    """Task-clustered bootstrap of a mean. Resamples TASKS, not cells."""
    if not vals:
        return [float("nan"), float("nan")]
    rng = random.Random(seed)
    byt: dict[str, list[float]] = collections.defaultdict(list)
    for v, t in zip(vals, tasks):
        byt[t].append(v)
    keys = list(byt)
    out = []
    for _ in range(n):
        s: list[float] = []
        for _ in keys:
            s += byt[rng.choice(keys)]
        out.append(sum(s) / len(s))
    out.sort()
    return [round(out[int(0.025 * n)], 4), round(out[int(0.975 * n)], 4)]


def _boot_diff(A: list[float], B: list[float], tasks: list[str],
               n: int = 20000, seed: int = 11, alpha: float = 0.05) -> list[float]:
    """Task-clustered bootstrap of a PAIRED difference of means."""
    if not A:
        return [float("nan"), float("nan")]
    rng = random.Random(seed)
    byt: dict[str, list[tuple[float, float]]] = collections.defaultdict(list)
    for x, y, t in zip(A, B, tasks):
        byt[t].append((x, y))
    keys = list(byt)
    out = []
    for _ in range(n):
        s: list[tuple[float, float]] = []
        for _ in keys:
            s += byt[rng.choice(keys)]
        out.append(sum(p[0] for p in s) / len(s) - sum(p[1] for p in s) / len(s))
    out.sort()
    return [round(out[int(alpha / 2 * n)], 4), round(out[int((1 - alpha / 2) * n)], 4)]


def _wilson(k: int, n: int, z: float = 1.959963985) -> list[float] | None:
    """Wilson score interval. Correct at k=0 and k=n, where Wald is degenerate."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


# -------------------------------------------------------------------------
# loading
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
# defect #21: a test suite that printed NO verdict was scored 0.0
# -------------------------------------------------------------------------

# ``status_lines=N`` is written into every arm's ``test_detail`` by
# ``score_patched_file``. ``N == 0`` means the suite printed no verdict at all
# -- an import error, a collection error, a missing test id. The harness never
# asked the question, so 0.0 records "the model's fix was wrong" where the
# truth is "no evidence exists". That is an ERROR VALUE BECOMING A REAL NUMBER,
# and on this benchmark it manufactures harm out of a collection error.
#
# The scorer is fixed (DEFECT_REGISTER #21), but these artifacts were WRITTEN
# BEFORE the fix. Re-running them is days of compute; the detail string records
# the fact, so the correction is applied on read. Any artifact produced after
# the scorer fix already carries ``reward: None`` on these arm-reads and this
# pass is a no-op on it -- which is itself asserted by control [7].
_STATUS_LINES_ZERO = re.compile(r"status_lines=0\b")


def demote_manufactured_zeros(cells: list[dict]) -> dict[str, Any]:
    """Set ``reward = None`` on any arm-read whose suite printed no verdict.

    Returns a ledger of what moved. NEVER the reverse: a real 0.0 (the tests
    ran and failed, ``status_lines >= 1``) is left exactly as it is.
    """
    n = 0
    by_repo: collections.Counter = collections.Counter()
    for c in cells:
        for arm in c.get("arms", {}).values():
            if arm.get("reward") is None:
                continue
            if _STATUS_LINES_ZERO.search(arm.get("test_detail") or ""):
                arm["reward"] = None
                arm["_demoted_manufactured_zero"] = True
                n += 1
                by_repo[c.get("repo", "?")] += 1
    return {"_what": ("DEFECT_REGISTER #21: an arm-read whose test suite "
                      "printed no verdict (status_lines=0) carried a "
                      "manufactured 0.0. Demoted to None = could not be "
                      "scored. A real 0.0 is untouched."),
            "arm_reads_demoted": n,
            "by_repo": dict(sorted(by_repo.items()))}


def load_source(path: str) -> dict[str, Any]:
    f = Path(path)
    if not f.exists():
        raise SystemExit(f"ABORT: source artifact missing: {path}")
    d = json.loads(f.read_text())
    if "cells" not in d or "summary" not in d:
        raise SystemExit(f"ABORT: {path} is not a representation artifact")
    if not d["cells"]:
        raise SystemExit(f"ABORT: {path} has zero cells")
    return d


def assert_poolable(sources: dict[str, dict]) -> dict[str, Any]:
    """Every pinned protocol field must agree, or these are different arms."""
    report: dict[str, Any] = {"fields_checked": list(PROTOCOL_FIELDS),
                              "disagreements": {}}
    names = list(sources)
    base = sources[names[0]]["summary"]
    for k in PROTOCOL_FIELDS:
        vals = {n: sources[n]["summary"].get(k) for n in names}
        if len(set(map(repr, vals.values()))) > 1:
            report["disagreements"][k] = vals
    report["poolable"] = not report["disagreements"]
    if not report["poolable"]:
        print("ABORT: sources differ on pinned protocol fields -- these are "
              "different arms and must not be pooled:")
        print(json.dumps(report["disagreements"], indent=1))
        raise SystemExit(3)
    report["pinned_values"] = {k: base.get(k) for k in PROTOCOL_FIELDS}
    return report


def extract(cells: list[dict]) -> tuple[dict, collections.Counter, dict]:
    """Per-representation dU keyed by (memory_id, task_id), plus exclusions.

    reward None -> EXCLUDED. Never 0.0.
    """
    du: dict[str, dict] = {r: {} for r in REPS}
    excl: collections.Counter = collections.Counter()
    meta: dict[tuple[str, str], str] = {}
    for c in cells:
        rep = c["representation"]
        k = (c["memory_id"], c["task_id"])
        meta[k] = c["repo"]
        if c.get("excluded"):
            excl[f"{rep}:memory_unavailable_or_contagion_dirty"] += 1
            continue
        if not c["localizer_recall"]:
            excl[f"{rep}:localizer_miss"] += 1
            continue
        w = c["arms"].get("WITH", {})
        wo = c["arms"].get("WITHOUT", {})
        if w.get("reward") is None or wo.get("reward") is None:
            excl[f"{rep}:unapplicable_or_unscored"] += 1
            continue
        du[rep][k] = w["reward"] - wo["reward"]
    return du, excl, meta


def matched_of(du: dict[str, dict]) -> list[tuple[str, str]]:
    if not all(du[r] for r in REPS):
        return []
    return sorted(set.intersection(*[set(du[r]) for r in REPS]))


def describe(du: dict[str, dict], matched: list, label: str,
             excl: collections.Counter, meta: dict) -> dict[str, Any]:
    tasks = [k[1] for k in matched]
    comp = collections.Counter(meta[k] for k in matched)
    out: dict[str, Any] = {
        "label": label,
        "n_repos": len(comp),
        "cells_per_repo": dict(sorted(comp.items())),
        "MATCHED_CELL_SET_N": len(matched),
        "distinct_tasks_matched": len(set(tasks)),
        "distinct_memories_matched": len({k[0] for k in matched}),
        "per_representation_interpretable": {r: len(du[r]) for r in REPS},
        "exclusions": dict(sorted(excl.items())),
        "delta_u_matched": {},
        "paired_contrasts": {},
        "both_arms_fail_matched": {},
    }
    if len(comp) > 1:
        top, n_top = comp.most_common(1)[0]
        share = n_top / len(matched)
        out["DOMINATED_BY"] = (
            {"repo": top, "cells": n_top, "share": round(share, 4)}
            if share >= DOMINANCE_THRESHOLD else None)
        out["_composition_sentence"] = (
            f"pooled over {len(comp)} repos, "
            + ", ".join(f"{r} {n}" for r, n in sorted(comp.items()))
            + f" = {len(matched)} matched cells"
            + (f"; {top} supplies {share:.1%} -- this pooled number is "
               f"dominated by one repo" if share >= DOMINANCE_THRESHOLD else ""))
    if not matched:
        out["VERDICT"] = "NO_MATCHED_CELLS"
        out["_what_this_means"] = (
            "No cell is interpretable under all three representations. That is "
            "a reportable outcome -- the arm is underpowered at this cell count "
            "-- and must NOT be patched with unmatched per-representation means.")
        return out

    for r in REPS:
        v = [du[r][k] for k in matched]
        out["delta_u_matched"][r] = {
            "mean": round(sum(v) / len(v), 4),
            "ci95_task_clustered": _boot(v, tasks),
            "helped": sum(1 for z in v if z > 0),
            "hurt": sum(1 for z in v if z < 0),
            "tied": sum(1 for z in v if z == 0),
            "n": len(v),
        }
    for x, y in (("structured", "raw"), ("summary", "raw"),
                 ("structured", "summary")):
        A = [du[x][k] for k in matched]
        B = [du[y][k] for k in matched]
        ci = _boot_diff(A, B, tasks)
        # 🔴 THREE contrasts are tested on one matched set, so a nominal 95%
        # interval is a per-contrast statement, not a family-wise one. The
        # Bonferroni-adjusted interval is emitted BESIDE it so a single
        # separating contrast cannot be read as a finding without the reader
        # having to remember how many were tried. This is the project's rule
        # that a selected subgroup inflates, applied to a selected CONTRAST.
        ci_fw = _boot_diff(A, B, tasks, alpha=0.05 / 3)
        out["paired_contrasts"][f"{x}_minus_{y}"] = {
            "mean": round(sum(p - q for p, q in zip(A, B)) / len(A), 4),
            "ci95_task_clustered": ci,
            "n_pairs": len(A),
            "separates_from_zero": bool(ci[0] > 0 or ci[1] < 0),
            "ci_familywise_bonferroni_3": ci_fw,
            "separates_familywise": bool(ci_fw[0] > 0 or ci_fw[1] < 0),
            "n_nonzero_cells": sum(1 for p, q in zip(A, B) if p != q),
        }
    anysep = any(v["separates_from_zero"]
                 for v in out["paired_contrasts"].values())
    anysep_fw = any(v["separates_familywise"]
                    for v in out["paired_contrasts"].values())
    # The governing verdict is the FAMILY-WISE one. A contrast that separates
    # nominally but not family-wise is recorded as exactly that -- neither
    # promoted to a finding nor hidden.
    out["ORDERING_VERDICT"] = "SEPARATED" if anysep_fw else "NOT_ESTABLISHED"
    out["ORDERING_VERDICT_nominal_uncorrected"] = (
        "SEPARATED" if anysep else "NOT_ESTABLISHED")
    if anysep and not anysep_fw:
        out["_multiplicity_note"] = (
            "At least one contrast separates at a nominal 95% interval but "
            "NOT after Bonferroni correction for the three contrasts tested "
            "on this one matched set. The governing verdict is "
            "NOT_ESTABLISHED. Reporting the nominal result alone would be "
            "selecting the contrast after seeing it.")
    return out


def both_arms_fail(cells: list[dict], matched: set) -> dict[str, Any]:
    k = {r: 0 for r in REPS}
    n = {r: 0 for r in REPS}
    for c in cells:
        if c.get("excluded") or not c["localizer_recall"]:
            continue
        key = (c["memory_id"], c["task_id"])
        if key not in matched:
            continue
        w, wo = c["arms"].get("WITH", {}), c["arms"].get("WITHOUT", {})
        if w.get("reward") is None or wo.get("reward") is None:
            continue
        n[c["representation"]] += 1
        if w["reward"] == 0.0 and wo["reward"] == 0.0:
            k[c["representation"]] += 1
    return {r: {"k": k[r], "n": n[r],
                "rate": round(k[r] / n[r], 4) if n[r] else None,
                "ci95_wilson": _wilson(k[r], n[r])} for r in REPS}


# -------------------------------------------------------------------------
# positive controls -- a null must be proven a real absence
# -------------------------------------------------------------------------

def self_test() -> int:
    import copy
    print("POSITIVE CONTROLS -- each must FAIL the thing it guards\n")
    ok = True

    def mkcell(mid, tid, rep, repo, wo, wi, recall=True, excl=False):
        return {"memory_id": mid, "task_id": tid, "repo": repo,
                "representation": rep, "localizer_recall": recall,
                "excluded": excl,
                "arms": {"WITHOUT": {"reward": wo}, "WITH": {"reward": wi}}}

    # --- control 1: the matched-set rule must SHRINK on a lost cell --------
    base = []
    for i in range(6):
        for r in REPS:
            base.append(mkcell(f"m{i}", f"t{i}", r, "x/x", 0.0, 1.0))
    du, _, _ = extract(base)
    n_full = len(matched_of(du))
    hurt = copy.deepcopy(base)
    for c in hurt:
        if c["task_id"] == "t0" and c["representation"] == "summary":
            c["arms"]["WITH"]["reward"] = None      # unapplicable -> exclusion
    du2, _, _ = extract(hurt)
    n_lost = len(matched_of(du2))
    good = (n_full == 6 and n_lost == 5)
    ok &= good
    print(f"  [1] matched set shrinks when one rep loses a cell : "
          f"{n_full} -> {n_lost}  {'PASS' if good else 'FAIL'}")

    # a reward None must NOT become a 0.0 anywhere
    has = ("m0", "t0") in du2["summary"]
    ok &= not has
    print(f"  [1b] reward None excluded, never coerced to 0.0     : "
          f"{'PASS' if not has else 'FAIL'}")

    # --- control 2: bootstrap must SEPARATE on a planted signal -----------
    flat = [0.0] * 12
    sig = [1.0] * 12
    tasks = [f"t{i}" for i in range(12)]
    ci_flat = _boot(flat, tasks)
    ci_sig = _boot(sig, tasks)
    ci_diff = _boot_diff(sig, flat, tasks)
    good = (ci_flat == [0.0, 0.0] and ci_sig == [1.0, 1.0]
            and ci_diff[0] > 0)
    ok &= good
    print(f"  [2] bootstrap separates on a planted +1.0 signal   : "
          f"flat{ci_flat} signal{ci_sig} diff{ci_diff}  "
          f"{'PASS' if good else 'FAIL'}")

    # a half-signal must NOT separate (the estimator is not trigger-happy)
    half = [1.0] * 6 + [-1.0] * 6
    ci_half = _boot_diff(half, flat, tasks)
    good2 = not (ci_half[0] > 0 or ci_half[1] < 0)
    ok &= good2
    print(f"  [2b] a symmetric +1/-1 mix does NOT separate        : "
          f"{ci_half}  {'PASS' if good2 else 'FAIL'}")

    # --- control 3: protocol gate must ABORT on a planted mismatch --------
    s1 = {"summary": {k: "v" for k in PROTOCOL_FIELDS}, "cells": [1]}
    s2 = json.loads(json.dumps(s1))
    s2["summary"]["max_tokens"] = "DIFFERENT"
    try:
        assert_poolable({"a": s1, "b": s2})
        aborted = False
    except SystemExit:
        aborted = True
    ok &= aborted
    print(f"  [3] protocol gate aborts on planted field mismatch : "
          f"{'PASS' if aborted else 'FAIL'}")
    same_ok = assert_poolable({"a": s1, "b": json.loads(json.dumps(s1))})["poolable"]
    ok &= same_ok
    print(f"  [3b] and PASSES when the fields agree               : "
          f"{'PASS' if same_ok else 'FAIL'}")

    # --- control 4: a bad join key must produce an EMPTY matched set ------
    # This is the trap named in the house rules: memory_id is a per-
    # representation content hash in some artifacts. If the key were wrong the
    # intersection would be empty -- so an empty intersection must be
    # DISTINGUISHABLE from a real absence. Plant the bad key and confirm it
    # yields 0, which is why a NON-zero matched set is evidence of a good key.
    badkey = copy.deepcopy(base)
    for c in badkey:
        c["memory_id"] = f"{c['memory_id']}::{c['representation']}"  # per-rep hash
    du3, _, _ = extract(badkey)
    n_bad = len(matched_of(du3))
    good = (n_bad == 0)
    ok &= good
    print(f"  [4] a per-representation key collapses matched to 0: "
          f"{n_bad}  {'PASS' if good else 'FAIL'}")
    print(f"      => a NON-zero matched set proves the key joins across reps")

    # --- control 5: dominance flag must fire and must not over-fire -------
    lop = [mkcell(f"m{i}", f"t{i}", r, "big/big" if i < 9 else "small/small",
                  0.0, 0.0) for i in range(10) for r in REPS]
    du4, e4, meta4 = extract(lop)
    m4 = matched_of(du4)
    d4 = describe(du4, m4, "lopsided", e4, meta4)
    fired = d4.get("DOMINATED_BY") is not None
    bal = [mkcell(f"m{i}", f"t{i}", r, "a/a" if i < 5 else "b/b", 0.0, 0.0)
           for i in range(10) for r in REPS]
    du5, e5, meta5 = extract(bal)
    d5 = describe(du5, matched_of(du5), "balanced", e5, meta5)
    quiet = d5.get("DOMINATED_BY") is None
    ok &= fired and quiet
    print(f"  [5] dominance flag fires at 9/10, silent at 5/10   : "
          f"fired={fired} silent={quiet}  {'PASS' if fired and quiet else 'FAIL'}")

    # --- control 6: Wilson interval is non-degenerate at k=0 and k=n ------
    w0, wn = _wilson(0, 13), _wilson(13, 13)
    good = (w0 is not None and w0[1] > 0 and wn is not None and wn[0] < 1
            and _wilson(0, 0) is None)
    ok &= good
    print(f"  [6] Wilson non-degenerate at k=0 and k=n, None at n=0: "
          f"0/13{w0} 13/13{wn}  {'PASS' if good else 'FAIL'}")

    # --- control 7: the defect-21 demotion must MOVE a manufactured zero,
    # must NOT move a real one, and must be IDEMPOTENT -------------------
    # Verified by planting the defect in both directions. A pass that only
    # ever saw a clean input would not be known to discriminate.
    plant = [
        # (a) the defect: suite printed no verdict, reward is a 0.0
        mkcell("mA", "tA", "raw", "x/x", 0.0, 0.0),
        # (b) the look-alike: tests RAN and failed. 0.0 is real. Must survive.
        mkcell("mB", "tB", "raw", "x/x", 0.0, 0.0),
        # (c) a 1.0 that happens to carry status_lines=0 in a P2P tail: the
        # rule is about evidence, not about the value, so it must move too.
        mkcell("mC", "tC", "raw", "x/x", 1.0, 1.0),
    ]
    plant[0]["arms"]["WITH"]["test_detail"] = "F2P rc=1 status_lines=0 :: ImportError"
    plant[0]["arms"]["WITHOUT"]["test_detail"] = "F2P rc=1 status_lines=4 :: FAILED"
    plant[1]["arms"]["WITH"]["test_detail"] = "F2P rc=1 status_lines=3 :: FAILED"
    plant[1]["arms"]["WITHOUT"]["test_detail"] = "F2P rc=1 status_lines=12 :: FAILED"
    plant[2]["arms"]["WITH"]["test_detail"] = (
        "F2P rc=0 status_lines=2 :: P2P rc=1 status_lines=0 collection error")
    plant[2]["arms"]["WITHOUT"]["test_detail"] = "F2P rc=0 status_lines=9 :: ok"

    led = demote_manufactured_zeros(plant)
    moved_defect = plant[0]["arms"]["WITH"]["reward"] is None
    kept_real = (plant[1]["arms"]["WITH"]["reward"] == 0.0
                 and plant[1]["arms"]["WITHOUT"]["reward"] == 0.0)
    moved_one = plant[2]["arms"]["WITH"]["reward"] is None
    kept_clean = plant[2]["arms"]["WITHOUT"]["reward"] == 1.0
    good = (led["arm_reads_demoted"] == 2 and moved_defect and kept_real
            and moved_one and kept_clean)
    ok &= good
    print(f"  [7] defect-21 demotion moves the manufactured 0.0 ({moved_defect}), "
          f"leaves a REAL 0.0 ({kept_real}), moves a 1.0 with no P2P verdict "
          f"({moved_one}), leaves a clean read ({kept_clean}) : "
          f"{'PASS' if good else 'FAIL'}")
    # idempotent: a second pass over already-corrected cells must move nothing,
    # so running this on a post-fix artifact cannot double-count.
    led2 = demote_manufactured_zeros(plant)
    idem = led2["arm_reads_demoted"] == 0
    ok &= idem
    print(f"  [7b] and is idempotent on an already-corrected artifact      : "
          f"{'PASS' if idem else 'FAIL'}")
    # the correction must CHANGE a reported number, or applying it is vacuous
    pre = [mkcell(f"n{i}", f"u{i}", r, "x/x", 0.0, 1.0)
           for i in range(4) for r in REPS]
    for c in pre:
        for arm in c["arms"].values():
            arm["test_detail"] = "F2P rc=0 status_lines=5 :: ok"
    pre[0]["arms"]["WITH"]["test_detail"] = "F2P rc=1 status_lines=0 :: ImportError"
    n_before = len(matched_of(extract(pre)[0]))
    demote_manufactured_zeros(pre)
    n_after = len(matched_of(extract(pre)[0]))
    moved_n = (n_before == 4 and n_after == 3)
    ok &= moved_n
    print(f"  [7c] and SHRINKS the matched set it governs: {n_before} -> "
          f"{n_after}  {'PASS' if moved_n else 'FAIL'}")

    print(f"\n{'ALL CONTROLS PASS' if ok else 'CONTROL FAILURE'}")
    return 0 if ok else 1


# -------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", default=[],
                    help="representation artifact; repeatable")
    ap.add_argument("--out", default="results/swebench/representations_multirepo.json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    srcs = a.src or ["results/swebench/representations_v2.json",
                     "results/swebench/representations_sympy.json"]
    sources = {p: load_source(p) for p in srcs}
    prot = assert_poolable(sources)
    print(f"GATE protocol identity : PASS -- {len(PROTOCOL_FIELDS)} pinned "
          f"fields agree across {len(sources)} artifacts")

    # DEFECT #21 correction, applied on read because these artifacts predate
    # the scorer fix. Runs BEFORE extract(), so a demoted arm-read becomes an
    # exclusion rather than a 0.0 entering a mean.
    demotion = demote_manufactured_zeros(
        [c for d in sources.values() for c in d["cells"]])
    print(f"GATE defect-21 demotion: {demotion['arm_reads_demoted']} arm-reads "
          f"with status_lines=0 -> reward None  {demotion['by_repo']}")

    # per-repo: a source may in principle contain >1 repo, so group by the
    # cell's OWN repo field rather than by which file it came from.
    by_repo: dict[str, list[dict]] = collections.defaultdict(list)
    provenance: dict[str, set] = collections.defaultdict(set)
    for p, d in sources.items():
        for c in d["cells"]:
            by_repo[c["repo"]].append(c)
            provenance[c["repo"]].add(p)
    print(f"  repos found: {dict((r, len(v)) for r, v in sorted(by_repo.items()))}")

    per_repo: dict[str, Any] = {}
    all_du: dict[str, dict] = {r: {} for r in REPS}
    all_excl: collections.Counter = collections.Counter()
    all_meta: dict = {}
    all_cells: list[dict] = []
    for repo, cells in sorted(by_repo.items()):
        du, excl, meta = extract(cells)
        m = matched_of(du)
        blk = describe(du, m, repo, excl, meta)
        blk["source_artifacts"] = sorted(provenance[repo])
        blk["rep_cells_in_source"] = len(cells)
        blk["both_arms_fail_matched"] = both_arms_fail(cells, set(m))
        blk["localizer_recall_rep_cells"] = {
            "k": sum(1 for c in cells if c["localizer_recall"]),
            "n": len(cells)}
        per_repo[repo] = blk
        for r in REPS:
            all_du[r].update(du[r])
        all_excl.update(excl)
        all_meta.update(meta)
        all_cells += cells

    pooled_matched = matched_of(all_du)
    pooled = describe(all_du, pooled_matched, "POOLED", all_excl, all_meta)
    pooled["both_arms_fail_matched"] = both_arms_fail(all_cells, set(pooled_matched))
    pooled["source_artifacts"] = sorted(sources)

    # the matched set is a per-cell property and cells never cross repos, so
    # the pooled matched set must equal the union of the per-repo ones. Check
    # it rather than assume it.
    union = sorted(set().union(*[set(matched_of(extract(c)[0]))
                                 for c in by_repo.values()]))
    pooled["_pooled_equals_union_of_per_repo_matched"] = (
        sorted(pooled_matched) == union)

    out = {
        "analysis_version": "swebench_multirepo_v2_defect21_corrected",
        "GOVERNING": "task_clustered",
        "defect21_manufactured_zero_correction": demotion,
        "basis": ("matched cells only -- interpretable under ALL THREE "
                  "representations. reward None (unapplicable edit / truncated "
                  "completion) is an EXCLUSION, never 0.0. Per-repo and pooled "
                  "figures are reported together and every pooled figure "
                  "states its per-repo composition."),
        "protocol_identity": prot,
        "per_repo": per_repo,
        "pooled": pooled,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))

    print(f"\n--- PER REPO ---")
    for repo, b in per_repo.items():
        print(f"\n{repo}: matched {b['MATCHED_CELL_SET_N']} cells "
              f"({b['distinct_memories_matched']} memories, "
              f"{b['distinct_tasks_matched']} tasks) from "
              f"{b['rep_cells_in_source']} rep-cells; "
              f"localizer recall {b['localizer_recall_rep_cells']['k']}/"
              f"{b['localizer_recall_rep_cells']['n']}")
        print(f"  per-rep interpretable: {b['per_representation_interpretable']}")
        for r in REPS:
            d = b["delta_u_matched"].get(r)
            if d:
                print(f"    dU {r:11s} {d['mean']:+.4f} "
                      f"CI{d['ci95_task_clustered']} "
                      f"(+{d['helped']}/-{d['hurt']}/={d['tied']}, n={d['n']})")
        for k, v in b["paired_contrasts"].items():
            print(f"    {k:26s} {v['mean']:+.4f} CI{v['ci95_task_clustered']} "
                  f"sep={v['separates_from_zero']}")
        print(f"    ORDERING: {b.get('ORDERING_VERDICT', b.get('VERDICT'))}")

    print(f"\n--- POOLED ---")
    print(f"  {pooled.get('_composition_sentence')}")
    print(f"  DOMINATED_BY: {pooled.get('DOMINATED_BY')}")
    print(f"  pooled == union of per-repo matched sets: "
          f"{pooled['_pooled_equals_union_of_per_repo_matched']}")
    for r in REPS:
        d = pooled["delta_u_matched"].get(r)
        if d:
            print(f"    dU {r:11s} {d['mean']:+.4f} CI{d['ci95_task_clustered']} "
                  f"(+{d['helped']}/-{d['hurt']}/={d['tied']}, n={d['n']})")
    for k, v in pooled["paired_contrasts"].items():
        print(f"    {k:26s} {v['mean']:+.4f} CI{v['ci95_task_clustered']} "
              f"sep={v['separates_from_zero']}")
    print(f"    ORDERING: {pooled.get('ORDERING_VERDICT', pooled.get('VERDICT'))}")
    print(f"\nwritten: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

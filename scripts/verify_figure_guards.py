"""Plant every reader-generalization and coverage defect; require the guard to FAIL.

WHY THIS EXISTS. `scripts/make_figures.py` refuses to emit a figure whose
caption the artifacts no longer support. That refusal is only worth something
if each guard has been shown to DISCRIMINATE -- three of this project's own
recorded defects were *in guards*, and one printed a correct verdict from an
empty input. So every guard here is exercised by planting the exact defect it
exists to catch.

THREE ORDERS OF PLANT, because the first two were not enough:

  1. plant in the ROWS. Most defects are caught, but several are caught by the
     equality-to-artifact cross-check rather than by the caption guard they
     were aimed at. A guard whose firing is always preempted by another has
     not been shown to work.
  2. plant CONSISTENTLY in rows AND artifact, recomputing the artifact through
     the same estimator, so the equality check passes and only the caption
     guard can fail.
  3. plant guard G in isolation, which orders 1 and 2 both left masked.

Each order also runs an UNPLANTED control first: without it, a "FAIL" could be
the harness being broken rather than the guard firing.

WHAT THE COVERAGE IDENTITY CAN AND CANNOT CATCH is derived, not assumed:
    completed + excluded = attempted + |planned - attempted|,  eligible = |planned|
so the identity binds on an executed cell that was never planned. A
planned-but-unrun cell is correctly absorbed into `excluded`, and the pinned
`never attempted` expectation is what catches that. Both are tested.

Run: /Users/bellayang/miniconda3/bin/python3 scripts/verify_figure_guards.py
Exit 1 if any guard fails to fire on its own defect.
"""
from __future__ import annotations

import collections
import contextlib
import copy
import importlib.util
import io
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

_spec = importlib.util.spec_from_file_location("mf", HERE / "make_figures.py")
mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mf)

GEMMA_SLIM = "results/ledgers/repro/gemma_reader/transfer_cells_slim.jsonl"
ANALYSIS = "results/ledgers/gemma_reader/reader_transfer_analysis.json"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, fired: bool, msg: str = "") -> None:
    RESULTS.append((name, bool(fired), msg))


def _run_rg(rows, ana) -> list[str]:
    mf.FAIL.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            mf.reader_generalization(_gemma_rows=rows, _analysis=ana)
        except Exception as exc:                       # noqa: BLE001
            return [f"raised {type(exc).__name__}: {exc}"]
    return list(mf.FAIL)


def _run_cov() -> list[str]:
    mf.FAIL.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            mf.coverage()
        except Exception as exc:                       # noqa: BLE001
            return [f"raised {type(exc).__name__}: {exc}"]
    return list(mf.FAIL)


def recompute_into(rows, ana):
    """Recompute the artifact's fields FROM the planted rows.

    This is what makes an order-2 plant meaningful: the equality-to-artifact
    guard is satisfied by construction, so if the build still fails it is a
    CAPTION guard that failed and nothing else.
    """
    oss = (mf.load("results/deltau_screened/cells.jsonl")
           + mf.load("results/repr_scaleup/cells.jsonl"))
    O, G = collections.defaultdict(list), collections.defaultdict(list)
    for r in oss:
        pr = r.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        O[(mf._rg_locator(r), r["future_task_id"],
           r["memory_representation"])].append(r)
    for r in rows:
        pr = r.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        G[(pr.get("memory_unit_locator"), r["future_task_id"],
           r["memory_representation"])].append(r)
    for rep in ("raw", "summary", "structured"):
        ko = {k for k in O if k[2] == rep}
        kg = {k for k in G if k[2] == rep}
        a = {k: mf._rg_cell_mean(O[k]) for k in ko}
        b = {k: mf._rg_cell_mean(G[k]) for k in kg}
        m = sorted(k for k in (ko & kg) if a[k] is not None and b[k] is not None)
        bt = collections.defaultdict(list)
        for k in m:
            bt[k[1]].append(b[k] - a[k])
        pt, lo, hi = mf._rg_boot_cluster(bt)
        xs = [a[k] for k in m]
        ys = [b[k] for k in m]
        nz = [i for i in range(len(m)) if xs[i] != 0 or ys[i] != 0]
        both = [i for i in range(len(m)) if xs[i] != 0 and ys[i] != 0]
        ref = ana["per_representation_matched"][rep]
        ref["n_matched_cells"], ref["n_tasks"] = len(m), len(bt)
        ref["deltaU_gptoss"]["mean"] = statistics.mean(xs)
        ref["deltaU_gemma"]["mean"] = statistics.mean(ys)
        tc = ref["paired_difference_task_clustered"]
        tc["mean"], tc["ci_lower"], tc["ci_upper"] = pt, lo, hi
        sc = ana["sign_and_correlation"][rep]
        sc["correlation"]["pearson"] = mf._rg_pearson(xs, ys)
        sub = sc["correlation_on_cells_nonzero_under_either"]
        sub["pearson"] = mf._rg_pearson([xs[i] for i in nz], [ys[i] for i in nz])
        sub["n"] = len(nz)
        agree = sum(1 for i in both if (xs[i] > 0) == (ys[i] > 0)
                    and (xs[i] < 0) == (ys[i] < 0))
        sc["sign_agreement_both_nonzero"]["k"] = agree
        sc["sign_agreement_both_nonzero"]["n"] = len(both)
    return ana


# ---------------------------------------------------------------- order 1
def order_one(rows, ana):
    print("\n-- ORDER 1: plant in the ROWS / the artifact --")
    record("[0] an UNPLANTED run PASSES (the harness is not simply broken)",
           not _run_rg(copy.deepcopy(rows), copy.deepcopy(ana)))

    r = copy.deepcopy(rows)
    r[0]["reader_model"] = mf.GPTOSS_READER_ID
    record("[A] a gpt-oss reader_model planted on a Gemma row",
           bool(_run_rg(r, copy.deepcopy(ana))))

    r = copy.deepcopy(rows)
    for x in r[:5]:
        x["reasoning_tokens"] = 0
    f = _run_rg(r, copy.deepcopy(ana))
    record("[B] reasoning_tokens coerced None -> 0 (an absence written as a "
           "measurement)", any("non-null reasoning_tokens" in x for x in f),
           "; ".join(f)[:150])

    r = copy.deepcopy(rows)
    for x in r:
        x["condition_id"] = "lmev2_raw_metis_gptoss120b_screened_v1"
    f = _run_rg(r, copy.deepcopy(ana))
    record("[C] the condition_id join starts returning rows (the trap stops "
           "being a trap)", any("condition_id join" in x for x in f),
           "; ".join(f)[:150])

    r = copy.deepcopy(rows)
    for x in r:
        if x["memory_representation"] == "raw" and x["reward_with_memory"] == 1.0:
            x["reward_with_memory"] = 0.0
            break
    record("[D] ONE raw cell's reward flipped", bool(_run_rg(r, copy.deepcopy(ana))))

    a = copy.deepcopy(ana)
    a["memory_text_byte_identity"]["differ"] = 3
    a["memory_text_byte_identity"]["identical"] = 1691
    record("[E] the memory text is no longer byte-identical",
           bool(_run_rg(copy.deepcopy(rows), a)))

    a = copy.deepcopy(ana)
    a["memory_text_byte_identity"]["_positive_control"][
        "detects_one_byte_change"] = False
    f = _run_rg(copy.deepcopy(rows), a)
    record("[F] the byte-identity check's OWN positive control stops firing",
           any("positive control does not fire" in x for x in f),
           "; ".join(f)[:150])

    a = copy.deepcopy(ana)
    a["deltaU_decomposed_by_arm"]["raw"]["change_in_WITHOUT_arm"] = 0.05
    f = _run_rg(copy.deepcopy(rows), a)
    record("[G] Gemma's raw WITHOUT arm no longer sits below gpt-oss's",
           any("WITHOUT arm no longer" in x for x in f), "; ".join(f)[:150])


# ---------------------------------------------------------------- order 2
def _identity_plant(rows, ana):
    """Guard F0: the figure draws the interval on the DIFFERENCE anchored at
    the gpt-oss point, which is only legitimate while the mean of per-cell
    differences equals the gap between the reader means. Break that and the
    whiskers would be silently misplaced on every row."""
    real = mf._rg_boot_cluster

    def broken(units, n_boot=10000, seed=20260930):
        pt, lo, hi = real(units, n_boot, seed)
        return pt + 0.05, lo, hi

    mf._rg_boot_cluster = broken
    try:
        f = _run_rg(copy.deepcopy(rows), copy.deepcopy(ana))
    finally:
        mf._rg_boot_cluster = real
    record("[W] the paired difference stops equalling the gap between the "
           "reader means -- the anchored-whisker drawing would misplace "
           "every interval", bool(f), "; ".join(f)[:150])


def order_two(rows, ana):
    print("\n-- ORDER 2: plant CONSISTENTLY, so only a CAPTION guard can fire --")
    a0 = recompute_into(copy.deepcopy(rows), copy.deepcopy(ana))
    record("[0] recomputing the artifact from UNPLANTED rows still passes "
           "(the plant harness is sound)",
           not _run_rg(copy.deepcopy(rows), a0))

    r = copy.deepcopy(rows)
    n = 0
    for x in r:
        if x["memory_representation"] == "summary" and x["reward_with_memory"] == 0.0:
            x["reward_with_memory"] = 1.0
            n += 1
            if n >= 200:
                break
    f = _run_rg(r, recompute_into(copy.deepcopy(r), copy.deepcopy(ana)))
    record(f"[H] summary pushed to SEPARATE from zero ({n} rows) -- only the "
           "'only Raw separates' caption guard can catch it",
           any("EXCLUDES zero" in x for x in f), "; ".join(f)[:150])

    r = copy.deepcopy(rows)
    n = 0
    for x in r:
        if x["memory_representation"] == "raw" and x["reward_with_memory"] == 1.0:
            x["reward_with_memory"] = 0.0
            n += 1
            if n >= 90:
                break
    f = _run_rg(r, recompute_into(copy.deepcopy(r), copy.deepcopy(ana)))
    record(f"[I] Raw pushed to SPAN zero ({n} rows) -- the POSITIVE-finding "
           "caption guard must catch it",
           any("no longer excludes zero" in x or "no longer\npositive" in x
               or "no longer positive" in x for x in f), "; ".join(f)[:150])

    r = copy.deepcopy(rows)
    n = 0
    for x in r:
        if x["memory_representation"] == "structured" and x["reward_with_memory"] == 0.0:
            x["reward_with_memory"] = 1.0
            n += 1
            if n >= 300:
                break
    f = _run_rg(r, recompute_into(copy.deepcopy(r), copy.deepcopy(ana)))
    record(f"[J] the representation ordering changed under Gemma ({n} rows)",
           any("ordering" in x.lower() for x in f), "; ".join(f)[:150])


# ---------------------------------------------------------------- order 3
def order_three(rows, ana):
    print("\n-- ORDER 3: guard G, which orders 1 and 2 both left MASKED --")
    oss = (mf.load("results/deltau_screened/cells.jsonl")
           + mf.load("results/repr_scaleup/cells.jsonl"))
    O = collections.defaultdict(list)
    for x in oss:
        pr = x.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        O[(mf._rg_locator(x), x["future_task_id"],
           x["memory_representation"])].append(x)

    # G clause 1: tied zeros stop dominating, WITHOUT disturbing Raw's sign.
    r = copy.deepcopy(rows)
    G = collections.defaultdict(list)
    for x in r:
        pr = x.get("provenance") or {}
        if pr.get("stratum") not in ("BEARING", "MATCHED_CONTROL"):
            continue
        G[(pr["memory_unit_locator"], x["future_task_id"],
           x["memory_representation"])].append(x)
    moved = 0
    for k in sorted(G):
        if k[2] != "raw" or k not in O:
            continue
        if mf._rg_cell_mean(O[k]) != 0 or mf._rg_cell_mean(G[k]) != 0:
            continue
        for x in G[k]:
            x["reward_with_memory"], x["reward_without_memory"] = 1.0, 0.0
        moved += 1
        if moved >= 40:
            break
    f = _run_rg(r, recompute_into(copy.deepcopy(r), copy.deepcopy(ana)))
    record(f"[K] tied zeros no longer dominate raw ({moved} cells) -- guard "
           "G's FIRST clause, in isolation",
           any("tied zeros no longer dominate" in x for x in f),
           "; ".join(f)[:150])

    # G clause 2: the non-zero r stops sitting below the all-cells r. Planted
    # at the estimator so every other quantity is untouched.
    real = mf._rg_pearson
    calls = {"n": 0}

    def swapped(x, y):
        calls["n"] += 1
        v = real(x, y)
        return None if v is None else (v * 0.1 if calls["n"] % 2 else v)

    mf._rg_pearson = swapped
    try:
        a2 = recompute_into(copy.deepcopy(rows), copy.deepcopy(ana))
        calls["n"] = 0
        f = _run_rg(copy.deepcopy(rows), a2)
    finally:
        mf._rg_pearson = real
    record("[L] the non-zero r no longer sits BELOW the all-cells r -- guard "
           "G's SECOND clause, in isolation",
           any("LOWERS r" in x for x in f), "; ".join(f)[:150])


# ---------------------------------------------------------------- coverage
def _patch_json(path: Path, mutate):
    orig = path.read_text()
    d = json.loads(orig)
    mutate(d)
    path.write_text(json.dumps(d, indent=1))
    try:
        return _run_cov()
    finally:
        path.write_text(orig)


def coverage_plants():
    print("\n-- COVERAGE TABLE: every row must close, and the identity must "
          "be able to FAIL --")
    record("[0] an UNPLANTED coverage run PASSES", not _run_cov())

    # 🔴 RE-POINTED by SA-FIGURE-STORY. commit a09385b moved make_figures.py
    # onto results/ledgers/repro/swebench/representations_multirepo_final.json
    # (the n=40 artifact) but left these plants writing to the OLD
    # results/swebench/representations_multirepo.json, which nothing reads any
    # more. Five plants [M][N][O][P][R] therefore corrupted a file the
    # generator never opens and reported "a guard did not fire" -- an
    # instrument aimed at nothing, and the voided guards were the ones
    # protecting the defect-21 correction and the two-repo composition.
    # The plants must land in the file the generator actually reads.
    sw = REPO / ("results/ledgers/repro/swebench/"
                 "representations_multirepo_final.json")
    sc = REPO / "results/ledgers/repro/scicode/scaleup_analysis.json"
    man = REPO / "data/manifests/k1_screened_cells.jsonl"
    rowf = REPO / "results/deltau_screened/cells.jsonl"

    def drop_excl(d):
        d["pooled"]["exclusions"].pop(sorted(d["pooled"]["exclusions"])[0])
    f = _patch_json(sw, drop_excl)
    record("[M] a SWE-bench exclusion category vanishes -- the row must stop "
           "closing. 🔴 This plant FOUND a real defect: `eligible` had been "
           "derived as completed+excluded, so the identity was VACUOUS",
           any("does not close" in x for x in f), "; ".join(f)[:150])

    f = _patch_json(sw, lambda d: d["pooled"].__setitem__(
        "MATCHED_CELL_SET_N", 17))
    # The label said "15 -> 17", which was the matched set of the OLD
    # django-only artifact. On the final multi-repo artifact it is 40. A
    # check's message is part of the check: a right verdict under a wrong
    # stated reason is harder to catch than a wrong verdict.
    record("[N] the SWE-bench matched set silently moves off 40",
           bool(f), "; ".join(f)[:150])

    f = _patch_json(sw, lambda d: d["defect21_manufactured_zero_correction"]
                    .__setitem__("arm_reads_demoted", 0))
    record("[O] the defect-21 demotion count reverts to 0", bool(f),
           "; ".join(f)[:150])

    f = _patch_json(sw, lambda d: d["pooled"].__setitem__(
        "ORDERING_VERDICT", "SEPARATED"))
    record("[P] SWE-bench's verdict becomes SEPARATED while the prose calls "
           "it boundary evidence",
           any("ORDERING_VERDICT changed" in x for x in f), "; ".join(f)[:150])

    f = _patch_json(sc, lambda d: d.__setitem__("ORDERING_VERDICT", "SEPARATED"))
    record("[Q] SciCode's verdict becomes SEPARATED",
           any("ORDERING_VERDICT changed" in x for x in f), "; ".join(f)[:150])

    f = _patch_json(sw, lambda d: d["pooled"].__setitem__(
        "cells_per_repo", {"django/django": 12}))
    record("[R] SWE-bench drops back to ONE repository", bool(f),
           "; ".join(f)[:150])

    f = _patch_json(sc, lambda d: d["per_representation_interpretable"]
                    .__setitem__("raw", 120))
    record("[S] a SciCode per-representation count drifts -- the row must "
           "stop closing", any("does not close" in x for x in f),
           "; ".join(f)[:150])

    # the identity's own failure mode, derived above: a cell EXECUTED that was
    # never planned.
    orig = rowf.read_text()
    try:
        rl = orig.splitlines()
        d = json.loads(rl[0])
        d["future_task_id"] = "OFF_DESIGN_TASK"
        rowf.write_text("\n".join(rl + [json.dumps(d)]) + "\n")
        f = _run_cov()
    finally:
        rowf.write_text(orig)
    record("[T] a LongMemEval cell EXECUTED that was never in the design "
           "manifest -- the identity itself must break",
           any("does not close" in x for x in f), "; ".join(f)[:150])

    # and the mode the identity correctly absorbs, caught by a pinned check
    orig = man.read_text()
    try:
        ml = [l for l in orig.splitlines() if l.strip()]
        e = json.loads(ml[0])
        e["task_id"] = "PLANNED_NEVER_RUN"
        man.write_text("\n".join(ml + [json.dumps(e)]) + "\n")
        f = _run_cov()
    finally:
        man.write_text(orig)
    record("[U] a planned cell never run -- the identity correctly CLOSES, "
           "so the pinned never-attempted check must be what fires",
           any("never attempted" in x for x in f)
           and not any("does not close" in x for x in f), "; ".join(f)[:150])

    # an unscorable replicate must move completed AND unscorable
    orig = rowf.read_text()
    try:
        rl = orig.splitlines()
        d = json.loads(rl[0])
        d["reward_with_memory"] = None
        rl[0] = json.dumps(d)
        rowf.write_text("\n".join(rl) + "\n")
        f = _run_cov()
    finally:
        rowf.write_text(orig)
    record("[V] one replicate becomes unscorable -- completed must FALL and "
           "unscorable must RISE (reward None is never 0.0)",
           any("completed" in x for x in f) and any("unscorable" in x for x in f),
           "; ".join(f)[:150])


def main() -> int:
    rows = [json.loads(l) for l in (REPO / GEMMA_SLIM).read_text().splitlines()
            if l.strip()]
    ana = json.loads((REPO / ANALYSIS).read_text())
    print("PLANT-THE-DEFECT VERIFICATION FOR THE FIGURE GUARDS")
    print("Each guard must FAIL on the defect it exists to catch.")
    order_one(rows, ana)
    _identity_plant(rows, ana)
    order_two(rows, ana)
    order_three(rows, ana)
    coverage_plants()

    print("\n" + "=" * 72)
    ok = True
    for name, fired, msg in RESULTS:
        ok &= fired
        print(f"  {'PASS' if fired else 'FAIL'}  {name}")
        if msg and fired:
            print(f"          -> {msg}")
    print("=" * 72)
    print("ALL GUARDS DISCRIMINATE" if ok else "A GUARD DID NOT FIRE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

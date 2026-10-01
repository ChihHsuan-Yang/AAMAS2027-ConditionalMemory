"""Plant every SESSION-MATCHED reader guard's defect; require it to FIRE.

The canonical reader-transfer result (+0.0982 on 275 cells) is the headline
the figure now draws. It had NO machine check of its own geometry until this
pass: the figure drew the SUPERSEDED +0.1268 while the prose quoted +0.0982,
and nothing could fail.

Both orders are run:
  order 1 -- plant in the rows; most guards fire, some via an `expect` pin.
  order 2 -- `expect` neutralised so ONLY the structural caption guard can
             fire. A guard always preempted by another has not been shown
             to work.
An UNPLANTED control opens each order.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path("/Users/bellayang/Documents/2026/p1_memory_utility/repo")
_spec = importlib.util.spec_from_file_location("mf", REPO / "scripts/make_figures.py")
mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mf)

SM = "results/ledgers/repro/raw_session_matched"
RESULTS = []
_real_expect = mf.expect
_real_load = mf.load


def _quiet(name, got, want, tol=5e-4):
    return None


def _run(patch_load=None, patch_ana=None, isolate=False):
    mf.FAIL.clear()
    if isolate:
        mf.expect = _quiet
    if patch_load is not None:
        def fake_load(rel):
            rows = _real_load(rel)
            out = patch_load(rel, rows)
            return rows if out is None else out
        mf.load = fake_load
    real_rt = Path.read_text
    if patch_ana is not None:
        def fake_rt(self, *a, **k):
            txt = real_rt(self, *a, **k)
            if self.name == "raw_session_matched_analysis.json":
                d = json.loads(txt)
                patch_ana(d)
                return json.dumps(d)
            return txt
        Path.read_text = fake_rt
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                mf.reader_session_matched()
            except Exception as exc:                    # noqa: BLE001
                return [f"raised {type(exc).__name__}: {exc}"]
        return list(mf.FAIL)
    finally:
        mf.load = _real_load
        mf.expect = _real_expect
        Path.read_text = real_rt


def rec(n, fired, msg=""):
    RESULTS.append((n, bool(fired), msg))


print("=" * 72)
print("SESSION-MATCHED READER (fig 6) -- order 1: plant in the rows")
print("=" * 72)

rec("[0] UNPLANTED session-matched run PASSES", not _run(), "")

# --- SM-A: a wrong reader id on one row. The whole experiment is "only the
# reader changed", so a stray reader invalidates the figure.
def p_reader(rel, rows):
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["reader_model"] = "gpt-oss-120b"
    return rows

f = _run(p_reader)
rec("[A] a gpt-oss reader id appears on a Gemma row",
    any("arms carry readers" in x for x in f), "; ".join(f[:1]))

# --- SM-A2: the arms span two serving clusters, which would confound.
def p_cluster(rel, rows):
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["reader_cluster"] = "aurora"
    return rows

f = _run(p_cluster)
rec("[A2] the arms span two serving clusters",
    any("span clusters" in x for x in f), "; ".join(f[:1]))

# --- SM-B: THE ARMS SPLIT ACROSS SESSIONS. This contrast exists precisely
# because the superseded one was 11 hours apart; if the dates diverge the
# word "session-matched" in the caption is false.
def p_session(rel, rows):
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["created_at_utc"] = "2026-10-02T08:34:16.664409+00:00"
    return rows

f = _run(p_session)
rec("[B] the two arms ran on DIFFERENT DATES -- no longer session-matched",
    any("more than one date" in x for x in f), "; ".join(f[:1]))

# --- SM-C: an errored row carries a score. An error is an absence.
def p_errscore(rel, rows):
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    rows[0]["error_code_if_any"] = "timeout"
    return rows

f = _run(p_errscore)
rec("[C] an ERRORED row still carries a delta_utility",
    any("errored rows carry" in x for x in f), "; ".join(f[:1]))

# --- SM-E: the measurement itself moves. One cell flipped must break the
# bit-for-bit equality with the artifact.
def p_flip(rel, rows):
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        if r["delta_utility"] == 0.0:
            r["delta_utility"] = 1.0
            r["reward_with_memory"] = 1.0
            r["reward_without_memory"] = 0.0
            break
    return rows

f = _run(p_flip)
rec("[E] ONE cell's reward flipped -- equality with the artifact breaks",
    any("paired reader effect" in x or "dU Gemma" in x for x in f),
    "; ".join(f[:1]))

# --- SM-G: the artifact's VERDICT changes.
f = _run(patch_ana=lambda d: d.update(VERDICT="DOES_NOT_SURVIVE"))
rec("[G] the artifact's VERDICT no longer says the effect survives",
    any("VERDICT is" in x for x in f), "; ".join(f[:1]))

# --- SM-G2: the interval stops excluding zero.
f = _run(patch_ana=lambda d: d.update(ci95_task_clustered=[-0.02, 0.19]))
rec("[G2] the interval stops excluding zero",
    any("excludes zero" in x or "CI lower" in x for x in f), "; ".join(f[:1]))

# --- SM-G3: THE SUPERSEDED FIGURE RETURNS. If the canonical estimate is
# edited to equal the published cross-session one, the figure can no longer
# be shown to draw the canonical arm.
f = _run(patch_ana=lambda d: d["published_cross_session"].update(mean=0.0982))
rec("[G3] the canonical and SUPERSEDED estimates become identical",
    any("superseded" in x and "identical" in x for x in f)
    or any("superseded cross-session mean" in x for x in f),
    "; ".join(f[:1]))

print()
print("=" * 72)
print("ORDER 2 -- expect() neutralised; ONLY a caption guard can fire")
print("=" * 72)
rec("[0b] UNPLANTED with guards isolated PASSES", not _run(isolate=True), "")

f = _run(p_session, isolate=True)
rec("[B-iso] arms split across sessions, pins off",
    any("more than one date" in x for x in f), "; ".join(f[:1]))

f = _run(patch_ana=lambda d: d.update(VERDICT="DOES_NOT_SURVIVE"), isolate=True)
rec("[G-iso] VERDICT changed, pins off",
    any("VERDICT is" in x for x in f), "; ".join(f[:1]))

# The guard compares the artifact's published mean to the RECOMPUTED one, so
# the plant must set it to the value the rows actually produce
# (0.09818181818...), not to the 4-dp display form 0.0982. A first version
# used the rounded figure and the guard correctly did not fire -- the two
# were not in fact identical. Planting the exact value is the real defect
# shape: a published block edited to match the current arm.
_EXACT = 0.09818181818181818
f = _run(patch_ana=lambda d: d["published_cross_session"].update(mean=_EXACT),
         isolate=True)
rec("[G3-iso] superseded == canonical (exactly), pins off",
    any("identical" in x for x in f), "; ".join(f[:1]))

# --- SM-H: the tied zeros stop dominating, so quoting agreement on movable
# cells loses its stated reason.
def p_allmove(rel, rows):
    """Collapse the tied zeros by moving the GEMMA arm on those cells only.

    A first version flipped gpt-oss zeros to +1, which drove the paired
    difference strongly NEGATIVE and was caught by the excludes-zero guard
    instead -- a plant that trips a different guard has not exercised this
    one. Moving Gemma upward on tied cells keeps the difference positive and
    changes only the quantity guard H reads: how many cells are zero under
    both."""
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        if r["delta_utility"] == 0.0:
            r["delta_utility"] = 1.0
            r["reward_with_memory"] = 1.0
            r["reward_without_memory"] = 0.0
    return rows

f = _run(p_allmove, isolate=True)
rec("[H-iso] tied zeros stop dominating the movable cells",
    any("no longer" in x and "dominate" in x for x in f), "; ".join(f[:1]))

# --- SM-I: the two readers' MARGINAL intervals separate, so the stated
# reason for drawing only the paired interval is gone.
def p_separate(rel, rows):
    """Push Gemma above gpt-oss until the two MARGINAL intervals separate.

    A first version overwrote every field including on rows carrying an
    error_code, which tripped the errored-row guard instead. This touches
    only clean rows and only their reward/dU, so the single quantity that
    changes is the marginal overlap."""
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    # CALIBRATED: lift 30% of Gemma's zero cells. Enough that the two
    # marginal intervals separate (gpt-oss tops at +0.3025, Gemma then
    # starts at +0.471), but NOT so many that the tied zeros stop dominating
    # -- at 30% it is 78 tied against 65 movable, so guard H's precondition
    # still holds and only guard I can fire. Earlier versions lifted every
    # cell and were caught by H or by the errored-row guard instead; a plant
    # preempted by another guard proves nothing about the one it targets.
    rng = __import__("random").Random(7)
    for r in rows:
        if r.get("error_code_if_any") or r.get("delta_utility") is None:
            continue
        if r["delta_utility"] == 0.0 and rng.random() < 0.3:
            r["delta_utility"] = 1.0
            r["reward_with_memory"] = 1.0
            r["reward_without_memory"] = 0.0
    return rows

f = _run(p_separate, isolate=True)
rec("[I-iso] the readers' marginal intervals SEPARATE -- the one-interval "
    "drawing rationale is void",
    any("no longer overlap" in x for x in f), "; ".join(f[:1]))

# --- SM-D: positive-control the join. The condition_id join must stay empty.
def p_badjoin(rel, rows):
    """Give the Gemma rows the gpt-oss arm's OWN condition_id.

    A first version used a condition_id string that appears nowhere in the
    gpt-oss arm, so the intersection stayed empty and the plant proved
    nothing -- the plant has to be in the SHAPE of the defect, which is the
    two arms sharing a condition id."""
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for r in rows:
        r["condition_id"] = "lmev2_raw_metis_gptoss120b_readertransfer_v1"
    return rows

f = _run(p_badjoin, isolate=True)
rec("[D-iso] the condition_id join starts returning rows",
    any("condition_id join" in x for x in f), "; ".join(f[:1]))

# --- SM-F: the row/cell factor of two breaks -- the units defect.
def p_units(rel, rows):
    """Drop one replicate of one cell: 550 rows is no longer 2x275 cells."""
    if not rel.endswith("raw_gemma_slim.jsonl"):
        return None
    rows = copy.deepcopy(rows)
    for i, r in enumerate(rows):
        if r.get("replicate_id") == 1:
            return rows[:i] + rows[i + 1:]
    return rows

f = _run(p_units, isolate=True)
rec("[F-iso] rows stop being exactly 2x cells (the units defect)",
    any("is not 2x the" in x for x in f), "; ".join(f[:1]))

print()
for n, fired, msg in RESULTS:
    print(f"  {'PASS' if fired else 'FAIL'}  {n}")
    if msg:
        print(f"          -> {msg[:150]}")
bad = [n for n, fired, _ in RESULTS if not fired]
print()
if bad:
    print("A GUARD DID NOT FIRE:", bad)
    sys.exit(1)
print("every planted session-matched defect was caught.")

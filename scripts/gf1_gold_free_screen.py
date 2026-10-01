#!/usr/bin/env python3
"""GF1: the GOLD-FREE bearing screen. Definition frozen in
``docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md`` BEFORE this ran.

WHY THIS EXISTS
---------------
``k1_build_screened_design.py`` screens with
``LK.detect(memory_text, t.answer, eval_function_spec=t.eval_function)`` --
it reads the **gold answer**. "Content-only" meant no reward and no model
output, NOT gold-free. A blind reviewer's deciding objection: is the headline
bearing-control effect a memory-utility finding, or "a passage containing the
answer helps a model answer"?

GF-LEX answers it by changing exactly ONE thing. The gold screen is a lexical
containment test; so is this. What differs is WHICH STRING is looked for:
the gold answer there, the question's rare terms here. Normalization
(``leakage.normalize_text``), the pool (865 web / 1,024 enterprise), and the
discriminativeness threshold (<=8 pool hits) are all INHERITED, not chosen.

An LLM screen would introduce a second difference -- instrument class --
beside the one under test, so a low overlap could not be attributed. GF-LLM
exists as a secondary check (``scripts/gf3_llm_screen.py``) for exactly the
question GF-LEX cannot answer: whether the verdict is an artefact of surface
form.

NO endpoint call is made here. No gold answer, no reward, no model output and
no outcome of any kind enters.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.leakage import normalize_text  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402

UNITS = REPO / "data/manifests/lmev2_memory_units_small.jsonl"
#: Rendered unit text. The units manifest stores only counts, so text is
#: re-derived from trajectories.jsonl through lmev2.segment_page_visits --
#: the SAME renderer the gold screen's own positive control uses -- and each
#: unit's rendered length is asserted against the manifest's ``text_chars``.
TEXTS = REPO / ".sa_goldfree_scratch/unit_texts.jsonl"

#: Inherited from k1's --max-pool-hits. NOT tuned here.
MAX_POOL_HITS = 8
#: Inherited from k1's `1 <= pool_hits` floor, and from the detector's own
#: requirement that an anchor be matchable at all.
MIN_DF = 1
MAX_DF = 8
#: Question-side boilerplate: terms in >=50% of SAME-DOMAIN deterministic
#: questions. Measured, not listed: 22 enterprise / 23 web terms.
BOILERPLATE_Q_FRAC = 0.5


def log(m: str) -> None:
    print(m, flush=True)


def _rel_to_repo(p) -> str:
    """Repo-relative path for an artifact field (DEFECT_REGISTER #23/#29)."""
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except Exception:
        return Path(p).name


# --------------------------------------------------------------------------
# the detector
# --------------------------------------------------------------------------


def question_anchors(question: str, df: dict[str, int], boiler: set[str],
                     *, min_df: int = MIN_DF, max_df: int = MAX_DF) -> list[str]:
    """Rare, non-boilerplate question terms. The gold-free analogue of a gold
    answer's phrase set.

    GOLD-FREE BY CONSTRUCTION: the signature takes a QUESTION and a POOL
    STATISTIC. There is no parameter through which a gold answer, a reward or
    a model output could enter -- the same structural argument
    ``lmev2.assert_writer_blind`` makes for the writer.
    """
    out, seen = [], set()
    for w in normalize_text(question).split():
        if w in seen:
            continue
        seen.add(w)
        if w in boiler:
            continue
        if min_df <= df.get(w, 0) <= max_df:
            out.append(w)
    return out


def gf_detect(memory_terms: set[str], anchors: list[str]) -> bool:
    """Fire iff EVERY anchor occurs in the memory.

    ``require_all`` mirrors the gold screen's
    ``normalized_leak(..., require_all_phrases=True)``. An empty anchor set
    NEVER fires: vacuous truth over an empty conjunction would make every
    memory bear on an anchorless question.
    """
    if not anchors:
        return False
    return all(a in memory_terms for a in anchors)


# --------------------------------------------------------------------------
# controls -- "prove the screen can fire, and plant the defect"
# --------------------------------------------------------------------------


def control_c1_can_fire_and_can_stay_silent(df, boiler) -> dict:
    """C1. A screen never shown to FIRE cannot evidence absence; one never
    shown to STAY SILENT cannot evidence presence.

    The baseline is ASSERTED clean rather than assumed -- the exact trap
    ``leakage._assert_baseline_clean`` exists for.
    """
    dom = "enterprise"
    q = ("I am working with our ServiceNow portal. What is the "
         "zzqxanchoralpha value for the zzqxanchorbeta record?")
    d = dict(df[dom]); d["zzqxanchoralpha"] = 3; d["zzqxanchorbeta"] = 2
    anc = question_anchors(q, d, boiler[dom])
    clean_terms = set(normalize_text(
        "State 4 (step 4)\n- URL: https://example.invalid/incident_list.do\n"
        "- Action: click('221')\n[221] button 'Submit'").split())
    if any(a in clean_terms for a in anc):
        raise RuntimeError("C1 baseline is NOT clean: an anchor already occurs")
    silent = gf_detect(clean_terms, anc)
    planted = clean_terms | set(anc)
    fires = gf_detect(planted, anc)
    # partial plant: all but one anchor -> require_all must NOT fire
    partial = clean_terms | set(anc[:-1])
    fires_partial = gf_detect(partial, anc) if len(anc) > 1 else None
    # an EMPTY anchor set must never fire (no vacuous truth)
    empty_vacuous = gf_detect(planted, [])
    ok = (len(anc) >= 2 and fires and not silent and fires_partial is False
          and not empty_vacuous)
    return {"_what": "C1: detector must FIRE on a plant and STAY SILENT on a "
                     "baseline asserted clean; a partial plant must NOT fire; "
                     "an empty anchor set must NOT fire vacuously",
            "anchors": anc, "n_anchors": len(anc),
            "fires_on_plant": fires, "fires_on_clean_baseline": silent,
            "fires_on_partial_plant": fires_partial,
            "fires_on_empty_anchor_set": empty_vacuous, "PASS": bool(ok)}


def control_c2_plant_the_defect(tasks, df, boiler, unit_terms, by_dom) -> dict:
    """C2. Break the screen on purpose and require the yield to MOVE.

    A guard verified only on its home case is not known to discriminate. Three
    mutations, because a yield insensitive to its parameters is not measuring
    them:

      m1  anchor extraction returns []            -> yield MUST collapse to 0
      m2  df band widened 8 -> 100000              -> yield MUST change
      m3  discriminativeness bound, under a relaxed
          fire rule that makes it BIND               -> MUST exclude tasks

    🔴 **m3 exists because the first version of this control FAILED, and the
    failure was a finding.** It removed the ``<=8`` bound and required the
    yield to inflate. It did not move -- because under the all-anchors fire
    rule **no task fires on more than 8 pool memories at all** (measured: max
    8; the GOLD screen, by contrast, has 205 of 295 tasks over the bound). So
    the bound is *non-binding at the operating point*, and a mutation of it is
    unobservable there. That is a PROPERTY OF THE SCREEN, not a bug, and it is
    reported in the ledger: GF-LEX's discriminativeness comes from the
    conjunction of rare anchors, not from the threshold.

    Deleting the bound would have been the wrong repair -- it must stay, in the
    same shape as the gold screen's, or the two screens are not comparable. So
    m3 proves the bound is IMPLEMENTED AND ABLE TO FIRE by exercising it where
    it does bind: under a relaxed >=50%-of-anchors fire rule, 20 tasks exceed
    8 pool hits and are excluded. A bound that cannot be shown to exclude
    anything is not known to be enforced.
    """
    def yield_at(anchor_fn, max_hits, max_df=MAX_DF, cover=1.0):
        edges = 0
        ntask = 0
        exceeded = 0
        for t in tasks:
            anc = anchor_fn(t, max_df)
            if not anc:
                continue
            need = int(math.ceil(cover * len(anc)))
            hits = [m for m in by_dom[t.domain]
                    if sum(1 for w in anc if w in unit_terms[m]) >= need]
            if len(hits) > max_hits:
                exceeded += 1
            if 1 <= len(hits) <= max_hits:
                ntask += 1
                edges += len(hits)
        return ntask, edges, exceeded

    def base_fn(t, max_df):
        return question_anchors(t.question, df[t.domain], boiler[t.domain],
                                max_df=max_df)

    b_tasks, b_edges, b_exc = yield_at(base_fn, MAX_POOL_HITS)
    m1_tasks, m1_edges, _ = yield_at(lambda t, _d: [], MAX_POOL_HITS)
    m2_tasks, m2_edges, _ = yield_at(base_fn, MAX_POOL_HITS, max_df=100_000)
    m3_tasks, m3_edges, m3_exc = yield_at(base_fn, MAX_POOL_HITS, cover=0.5)
    ok = (b_edges > 0 and m1_edges == 0 and m2_edges != b_edges and m3_exc > 0)
    return {"_what": "C2: planted defects must MOVE the yield; and the "
                     "discriminativeness bound must be shown ABLE to exclude",
            "baseline": {"tasks": b_tasks, "edges": b_edges,
                         "tasks_excluded_by_the_bound": b_exc},
            "mutation_anchors_emptied": {"tasks": m1_tasks, "edges": m1_edges,
                                         "must_be_zero": True},
            "mutation_df_band_widened": {"tasks": m2_tasks, "edges": m2_edges,
                                         "must_differ_from_baseline": True},
            "mutation_bound_exercised_under_relaxed_fire_rule": {
                "cover": 0.5, "tasks": m3_tasks, "edges": m3_edges,
                "tasks_excluded_by_the_bound": m3_exc,
                "must_exceed_zero": True},
            "_finding_the_bound_is_non_binding_here": (
                f"at the operating point the bound excludes {b_exc} tasks: under "
                f"the all-anchors fire rule NO task fires on more than "
                f"{MAX_POOL_HITS} pool memories. The GOLD screen has 205 of 295 "
                f"tasks over the same bound. GF-LEX's discriminativeness comes "
                f"from the conjunction of rare anchors, not from the threshold. "
                f"The bound is KEPT (same shape as the gold screen's) and shown "
                f"able to fire by the relaxed-rule mutation."),
            "PASS": bool(ok)}


def control_c3_join_keys(units: list[dict]) -> dict:
    """C3. Prove the join this analysis depends on is REAL.

    Measured, not assumed: ``memory_id`` in the design manifest is a
    per-representation CONTENT HASH; in the executed rows it is
    ``mem-<traj>-<hash>``. Joining on it returns ZERO. The locator joins 60/60.
    An empty overlap must never be a bad join.
    """
    rows_path = REPO / "results/deltau_screened/cells.jsonl"
    design = [json.loads(l) for l in
              (REPO / "data/manifests/k1_screened_cells.jsonl").read_text().splitlines()
              if l.strip()]
    row_mid, row_loc = set(), set()
    for line in rows_path.open():
        if not line.strip():
            continue
        r = json.loads(line)
        row_mid.add(r["memory_id"])
        row_loc.add(r["source_episode_metadata"]["memory_unit_locator"])
    d_mid = {c["memory_id"] for c in design}
    d_loc = {c["memory_unit_locator"] for c in design}
    on_mid = len(d_mid & row_mid)
    on_loc = len(d_loc & row_loc)
    uloc = {u["memory_unit_locator"] for u in units}
    ok = (on_mid == 0 and on_loc == len(d_loc) and d_loc <= uloc)
    return {"_what": "C3: the locator join is the real one; memory_id returns zero",
            "n_design_memories": len(d_loc),
            "join_on_memory_id_matches": on_mid,
            "join_on_memory_unit_locator_matches": on_loc,
            "design_locators_all_in_units_manifest": bool(d_loc <= uloc),
            "_trap": "memory_id is a per-representation content hash in the design "
                     "manifest and mem-<traj>-<hash> in the rows; an overlap of 0 "
                     "from that key would be a BAD JOIN, not a finding",
            "PASS": bool(ok)}


def control_c4_gold_recompute(tasks, units_text, fire_manifest, n_sample, seed) -> dict:
    """C4. Re-derive the GOLD screen's manifest from raw text on a sample.

    The overlap matrix is only as good as BOTH screens. k1 runs this control
    for its own use; it is re-run here because this analysis consumes the gold
    manifest as an instrument. Asserts a NON-ZERO number of recomputed fires:
    an all-negative recomputation agreeing with an all-negative manifest proves
    nothing.
    """
    import random as _r
    from p1mem.adapters import leakage as LK
    ok_ctrl, ctrl = LK.controls_summary()
    samp = _r.Random(seed).sample(sorted(units_text), n_sample)
    by_dom = collections.defaultdict(list)
    for t in tasks:
        by_dom[t.domain].append(t)
    agree = dis = fires = 0
    for loc in samp:
        u = units_text[loc]
        for t in by_dom[u["domain"]]:
            got = bool(LK.detect(u["text"], t.answer,
                                 eval_function_spec=t.eval_function).any_leak)
            exp = loc in fire_manifest.get(t.id, ())
            fires += got
            agree += (got == exp)
            dis += (got != exp)
    return {"_what": "C4: the GOLD manifest re-derived from raw text on a sample",
            "detector_self_controls_pass": bool(ok_ctrl),
            "n_self_controls": len(ctrl),
            "n_units_sampled": len(samp), "n_cells_checked": agree + dis,
            "n_agree": agree, "n_disagree": dis, "n_recomputed_fires": fires,
            "_why_fires_reported": "a control with zero positives cannot fail",
            "PASS": bool(ok_ctrl and dis == 0 and fires > 0)}


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--verify-units", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_gold_free_screen.json")
    ap.add_argument("--fires-out", type=Path,
                    default=REPO / "data/manifests/gf_lex_bearing.jsonl")
    args = ap.parse_args()

    t0 = time.time()
    units = [json.loads(l) for l in UNITS.read_text().splitlines() if l.strip()]
    units_text = {}
    for line in TEXTS.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            units_text[d["memory_unit_locator"]] = d
    if set(units_text) != {u["memory_unit_locator"] for u in units}:
        raise SystemExit("unit text set != units manifest")
    uloc = {u["memory_unit_locator"]: u for u in units}
    tasks = [t for t in lmev2.load_tasks(args.root) if t.deterministic]
    log(f"[input] {len(units)} units, {len(tasks)} deterministic tasks")

    by_dom: dict[str, list[str]] = collections.defaultdict(list)
    for u in units:
        by_dom[u["domain"]].append(u["memory_unit_locator"])
    for v in by_dom.values():
        v.sort()
    pool_size = {d: len(v) for d, v in by_dom.items()}
    log(f"[pool] {pool_size}")

    # ---- term sets, document frequencies, boilerplate ----
    unit_terms = {loc: set(normalize_text(d["text"]).split())
                  for loc, d in units_text.items()}
    df: dict[str, collections.Counter] = {}
    for dom, locs in by_dom.items():
        c: collections.Counter = collections.Counter()
        for l in locs:
            c.update(unit_terms[l])
        df[dom] = c
    qn: collections.Counter = collections.Counter()
    qdf: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for t in tasks:
        qn[t.domain] += 1
        qdf[t.domain].update(set(normalize_text(t.question).split()))
    boiler = {d: {w for w, c in qdf[d].items() if c >= BOILERPLATE_Q_FRAC * qn[d]}
              for d in qdf}
    log(f"[boilerplate] " + ", ".join(f"{d}:{len(v)}" for d, v in sorted(boiler.items())))

    # ---- gold manifest, for the overlap and for C4 ----
    gold_fire: dict[str, set[str]] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if line.strip():
            d = json.loads(line)
            gold_fire[d["task_id"]].add(d["memory_id"])   # value IS the locator
    unknown = set().union(*gold_fire.values()) - set(uloc)
    if unknown:
        raise SystemExit(f"gold manifest names {len(unknown)} unknown locators")

    # ---- CONTROLS, before any yield is reported ----
    log("\n[controls]")
    c1 = control_c1_can_fire_and_can_stay_silent(df, boiler)
    log(f"  C1 can-fire/can-stay-silent: PASS={c1['PASS']} "
        f"(anchors={c1['n_anchors']}, plant={c1['fires_on_plant']}, "
        f"clean={c1['fires_on_clean_baseline']}, partial={c1['fires_on_partial_plant']})")
    c2 = control_c2_plant_the_defect(tasks, df, boiler, unit_terms, by_dom)
    log(f"  C2 plant-the-defect: PASS={c2['PASS']} base_edges={c2['baseline']['edges']} "
        f"emptied={c2['mutation_anchors_emptied']['edges']} "
        f"df-widened={c2['mutation_df_band_widened']['edges']} "
        f"bound-excludes-under-relaxed-rule="
        f"{c2['mutation_bound_exercised_under_relaxed_fire_rule']['tasks_excluded_by_the_bound']}")
    log(f"     NOTE: at the operating point the bound excludes "
        f"{c2['baseline']['tasks_excluded_by_the_bound']} tasks -- non-binding, "
        f"and that is a reported property of the screen")
    c3 = control_c3_join_keys(units)
    log(f"  C3 join keys: PASS={c3['PASS']} on memory_id={c3['join_on_memory_id_matches']} "
        f"on locator={c3['join_on_memory_unit_locator_matches']}")
    c4 = control_c4_gold_recompute(tasks, units_text, gold_fire,
                                   args.verify_units, args.seed)
    log(f"  C4 gold manifest re-derivation: PASS={c4['PASS']} "
        f"{c4['n_agree']}/{c4['n_cells_checked']} agree, {c4['n_recomputed_fires']} fires")
    failed = [k for k, v in (("C1", c1), ("C2", c2), ("C3", c3), ("C4", c4)) if not v["PASS"]]
    if failed:
        raise SystemExit(f"CONTROLS FAILED: {failed}. No yield is reportable.")

    # ---- the screen, over the FULL candidate universe ----
    log("\n[screen] running GF-LEX over the full same-domain universe")
    rows: list[dict] = []
    per_task_hits: dict[str, int] = {}
    anchors_by_task: dict[str, list[str]] = {}
    universe = 0
    for t in tasks:
        anc = question_anchors(t.question, df[t.domain], boiler[t.domain])
        anchors_by_task[t.id] = anc
        universe += pool_size[t.domain]
        hits = [m for m in by_dom[t.domain] if gf_detect(unit_terms[m], anc)] if anc else []
        per_task_hits[t.id] = len(hits)
        if 1 <= len(hits) <= MAX_POOL_HITS:
            for m in hits:
                rows.append({
                    "task_id": t.id, "memory_unit_locator": m,
                    "domain": t.domain, "question_type": t.question_type,
                    "eval_name": t.eval_name,
                    "trajectory_id": uloc[m]["trajectory_id"],
                    "memory_tokens": uloc[m]["n_tokens"],
                    "n_anchors": len(anc), "anchors": anc,
                    "task_pool_hits_gf": len(hits),
                    "task_pool_size": pool_size[t.domain],
                    "gold_detector_fires": m in gold_fire.get(t.id, ()),
                })
    disc = [tid for tid, k in per_task_hits.items() if 1 <= k <= MAX_POOL_HITS]
    bear: dict[str, list[str]] = collections.defaultdict(list)
    for r in rows:
        bear[r["memory_unit_locator"]].append(r["task_id"])
    log(f"[screen] universe {universe} cells; {len(disc)}/{len(tasks)} tasks "
        f"discriminative; {len(rows)} bearing edges on {len(bear)} memories "
        f"({sum(1 for v in bear.values() if len(v) >= 2)} with >=2)")

    # ---- overlap with the GOLD screen, over the SAME universe ----
    gold_ph = {t.id: len(gold_fire.get(t.id, ())) for t in tasks}
    gold_disc = {tid for tid, k in gold_ph.items() if 1 <= k <= MAX_POOL_HITS}
    gold_bearing = {(m, tid) for tid in gold_disc for m in gold_fire[tid]}
    gf_bearing = {(r["memory_unit_locator"], r["task_id"]) for r in rows}
    both = gf_bearing & gold_bearing
    cm = {
        "n_universe_cells": universe,
        "both_bearing": len(both),
        "gf_only": len(gf_bearing - gold_bearing),
        "gold_only": len(gold_bearing - gf_bearing),
        "neither": universe - len(gf_bearing | gold_bearing),
        "n_gf_bearing": len(gf_bearing),
        "n_gold_bearing": len(gold_bearing),
        "jaccard": (len(both) / len(gf_bearing | gold_bearing)
                    if (gf_bearing | gold_bearing) else None),
        "frac_of_gold_also_gf": (len(both) / len(gold_bearing)) if gold_bearing else None,
        "frac_of_gf_also_gold": (len(both) / len(gf_bearing)) if gf_bearing else None,
    }
    # C4b: the matrix must be non-vacuous -- an empty marginal is uninformative
    cm["_nonvacuous"] = bool(cm["n_gf_bearing"] > 0 and cm["n_gold_bearing"] > 0)
    log(f"\n[overlap] both={cm['both_bearing']} gf_only={cm['gf_only']} "
        f"gold_only={cm['gold_only']} | of gold {cm['frac_of_gold_also_gf']:.4f} "
        f"| of gf {cm['frac_of_gf_also_gold']:.4f}")

    task_cm = {
        "gf_discriminative": len(disc), "gold_discriminative": len(gold_disc),
        "both": len(set(disc) & gold_disc), "gf_only": len(set(disc) - gold_disc),
        "gold_only": len(gold_disc - set(disc)),
    }
    gold_bear_mem = {m for m, _ in gold_bearing}
    mem_cm = {
        "gf_memories": len(bear), "gold_memories": len(gold_bear_mem),
        "both": len(set(bear) & gold_bear_mem),
        "gf_only": len(set(bear) - gold_bear_mem),
        "gold_only": len(gold_bear_mem - set(bear)),
    }
    log(f"[overlap/task] {task_cm}")
    log(f"[overlap/memory] {mem_cm}")

    args.fires_out.parent.mkdir(parents=True, exist_ok=True)
    with args.fires_out.open("w") as fh:
        for r in sorted(rows, key=lambda r: (r["memory_unit_locator"], r["task_id"])):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    log(f"[wrote] {args.fires_out} ({len(rows)} rows)")

    write_json_atomic(args.out, {
        "_what": "GF1 gold-free bearing screen (GF-LEX). NO gold answer, NO reward, "
                 "NO model output, NO endpoint call.",
        "_precommitment": "docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md",
        "config": {"max_pool_hits": MAX_POOL_HITS, "min_df": MIN_DF, "max_df": MAX_DF,
                   "boilerplate_q_frac": BOILERPLATE_Q_FRAC, "seed": args.seed,
                   "normalizer": "p1mem.adapters.leakage.normalize_text (INHERITED "
                                 "from the gold screen)"},
        "controls": {"C1_can_fire_can_stay_silent": c1, "C2_plant_the_defect": c2,
                     "C3_join_keys": c3, "C4_gold_manifest_rederived": c4},
        "pool_size_per_domain": pool_size,
        "boilerplate_terms": {d: sorted(v) for d, v in sorted(boiler.items())},
        "yield": {
            "n_universe_cells": universe,
            "n_deterministic_tasks": len(tasks),
            "n_discriminative_tasks": len(disc),
            "n_bearing_edges": len(rows),
            "n_memories_with_any_bearing_task": len(bear),
            "n_memories_with_ge2": sum(1 for v in bear.values() if len(v) >= 2),
            "n_source_episodes_with_ge2": len(
                {uloc[m]["trajectory_id"] for m, v in bear.items() if len(v) >= 2}),
            "anchors_per_task": {
                "min": min(len(v) for v in anchors_by_task.values()),
                "max": max(len(v) for v in anchors_by_task.values()),
                "n_tasks_with_zero_anchors": sum(
                    1 for v in anchors_by_task.values() if not v)},
            "_gold_screen_for_contrast": {
                "n_discriminative_tasks": len(gold_disc),
                "n_bearing_edges": len(gold_bearing),
                "n_memories_with_any_bearing_task": len(gold_bear_mem)},
        },
        "overlap_cell_level": cm,
        "overlap_task_level": task_cm,
        "overlap_memory_level": mem_cm,
        "fires_artifact": _rel_to_repo(args.fires_out),
        "wall_clock_s": round(time.time() - t0, 1),
    })
    log(f"[wrote] {args.out}  ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

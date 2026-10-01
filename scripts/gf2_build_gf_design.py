#!/usr/bin/env python3
"""GF2: build the GOLD-FREE two-stratum design. ZERO endpoint calls.

Per ``docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md`` §5.2. Only **5** of the 218
GF-BEARING cells have an executed measurement (and only **4** in the deciding
``GF-BEARING AND NOT GOLD-BEARING`` stratum), because the executed design was
chosen by the GOLD screen. So the contrast needs its own cells.

STRATA
------
GF_BEARING          GF-LEX fires on (m,t) AND t is GF-discriminative.
GF_MATCHED_CONTROL  SAME memory, SAME task family (question_type within
                    domain), GF-LEX SILENT -- and additionally NOT
                    gold-bearing, so the control arm cannot be contaminated
                    by the very property under test.

The size cap (20,000 target-memory tokens) is the design's own
``--target-token-cap``, reused unchanged: a content-blind size rule fixed
before any outcome is seen.

🔴 THE DECIDING STRATUM. The executed cells were chosen by the gold screen, so
any GF stratum intersected with them is enriched for gold-BEARING. Every cell
here is labelled ``also_gold_bearing`` so the analysis can report the
``GF AND NOT GOLD`` contrast separately -- that is the quantity the
pre-commitment names as governing the verdict.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from gf1_gold_free_screen import (BOILERPLATE_Q_FRAC, MAX_POOL_HITS,  # noqa: E402
                                  gf_detect, question_anchors)
from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.leakage import normalize_text  # noqa: E402
from p1mem.schema import write_json_atomic  # noqa: E402

TEXTS = REPO / ".sa_goldfree_scratch/unit_texts.jsonl"


def log(m: str) -> None:
    print(m, flush=True)


def _rel_to_repo(p) -> str:
    """Repo-relative path for an artifact field (DEFECT_REGISTER #23/#29).

    An absolute /Users/<name>/ path in a tracked ledger de-anonymises a
    double-blind submission and is invisible to a credential scanner. Never
    write str(path) into an artifact -- including via a `vars(args)` dump,
    which is how it got in here.
    """
    p = Path(p)
    try:
        return str(p.resolve().relative_to(REPO))
    except Exception:
        # Outside the repo. Returning only `.name` would turn "/tmp/lmev2" into
        # "lmev2" -- losing the fact that it is a scratch root, which a reader
        # needs to reproduce the run. Keep non-home absolute paths whole and
        # redact only a home directory, which is the actual anonymity hazard.
        s = str(p)
        home = str(Path.home())
        return s.replace(home, "~") if s.startswith(home) else s



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--target-token-cap", type=int, default=20000)
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/gf_design.json")
    ap.add_argument("--cells-out", type=Path,
                    default=REPO / "data/manifests/gf_cells.jsonl")
    args = ap.parse_args()

    units = {u["memory_unit_locator"]: u for u in
             (json.loads(l) for l in
              (REPO / "data/manifests/lmev2_memory_units_small.jsonl"
               ).read_text().splitlines() if l.strip())}
    ut = {}
    for line in TEXTS.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            ut[d["memory_unit_locator"]] = d
    tasks = {t.id: t for t in lmev2.load_tasks(args.root) if t.deterministic}

    unit_terms = {loc: set(normalize_text(d["text"]).split()) for loc, d in ut.items()}
    by_dom: dict[str, list[str]] = collections.defaultdict(list)
    for loc, d in ut.items():
        by_dom[d["domain"]].append(loc)
    df: dict[str, collections.Counter] = {}
    for dom, locs in by_dom.items():
        c: collections.Counter = collections.Counter()
        for l in locs:
            c.update(unit_terms[l])
        df[dom] = c
    qn: collections.Counter = collections.Counter()
    qdf: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for t in tasks.values():
        qn[t.domain] += 1
        qdf[t.domain].update(set(normalize_text(t.question).split()))
    boiler = {d: {w for w, c in qdf[d].items() if c >= BOILERPLATE_Q_FRAC * qn[d]}
              for d in qdf}
    anchors = {t.id: question_anchors(t.question, df[t.domain], boiler[t.domain])
               for t in tasks.values()}

    gf_rows = [json.loads(l) for l in
               (REPO / "data/manifests/gf_lex_bearing.jsonl"
                ).read_text().splitlines() if l.strip()]
    GF = {(r["memory_unit_locator"], r["task_id"]) for r in gf_rows}
    gf_hits = {r["task_id"]: r["task_pool_hits_gf"] for r in gf_rows}

    gold: dict[str, set[str]] = collections.defaultdict(set)
    for line in (REPO / "data/manifests/lmev2_leakage_small.jsonl").open():
        if line.strip():
            d = json.loads(line)
            gold[d["task_id"]].add(d["memory_id"])
    gold_disc = {tid for tid in tasks if 1 <= len(gold.get(tid, ())) <= MAX_POOL_HITS}
    GOLD = {(m, tid) for tid in gold_disc for m in gold[tid]}
    log(f"[input] GF-bearing {len(GF)}, GOLD-bearing {len(GOLD)}, "
        f"overlap {len(GF & GOLD)}")

    cap = args.target_token_cap
    keep = sorted([(m, t) for m, t in GF if units[m]["n_tokens"] <= cap])
    dropped = sorted([(m, t) for m, t in GF if units[m]["n_tokens"] > cap])
    log(f"[cap] {cap} tokens: kept {len(keep)}/{len(GF)} GF-bearing cells "
        f"(dropped {len(dropped)} on size alone)")

    cells: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(m, tid, stratum, why):
        if (m, tid) in seen:
            return False
        seen.add((m, tid))
        t = tasks[tid]
        u = units[m]
        cells.append({
            "memory_unit_locator": m, "memory_id": u["memory_id"],
            "trajectory_id": u["trajectory_id"], "domain": u["domain"],
            "memory_tokens": u["n_tokens"], "task_id": tid,
            "question_type": t.question_type, "eval_name": t.eval_name,
            "stratum": stratum, "why_stratum": why,
            "gf_detector_fires": (m, tid) in GF,
            "also_gold_bearing": (m, tid) in GOLD,
            "gold_detector_fires_any": m in gold.get(tid, ()),
            "task_pool_hits_gf": gf_hits.get(tid),
            "task_pool_hits_gold": len(gold.get(tid, ())),
            "task_pool_size": len(by_dom[u["domain"]]),
            "replicates": args.replicates,
        })
        return True

    for m, tid in keep:
        add(m, tid, "GF_BEARING",
            f"GF-LEX fires; task fires on {gf_hits[tid]} of "
            f"{len(by_dom[units[m]['domain']])} same-domain memories")

    # MATCHED CONTROL: same memory, same family, GF SILENT, and NOT gold-bearing.
    by_domfam: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for tid, t in tasks.items():
        by_domfam[(t.domain, t.question_type)].append(tid)
    for v in by_domfam.values():
        v.sort()
    need: collections.Counter = collections.Counter()
    for m, tid in keep:
        need[(m, tasks[tid].question_type)] += 1
    n_short = 0
    for (m, fam), k in sorted(need.items()):
        dom = units[m]["domain"]
        pool = [tid for tid in by_domfam[(dom, fam)]
                if not gf_detect(unit_terms[m], anchors[tid])
                and (m, tid) not in GOLD and (m, tid) not in GF
                and (m, tid) not in seen]
        random.Random(f"{args.seed}:mc:{m}:{fam}").shuffle(pool)
        got = 0
        for tid in pool:
            if got >= k:
                break
            if add(m, tid, "GF_MATCHED_CONTROL",
                   f"same memory, same task family '{fam}', GF-LEX SILENT, "
                   f"and not gold-bearing"):
                got += 1
        if got < k:
            n_short += 1
    log(f"[controls] {sum(1 for c in cells if c['stratum']=='GF_MATCHED_CONTROL')} "
        f"matched controls ({n_short} memory x family groups short)")

    # every GF_BEARING memory MUST have >=1 control, or the pairing is broken
    bm = {c["memory_unit_locator"] for c in cells if c["stratum"] == "GF_BEARING"}
    cm = {c["memory_unit_locator"] for c in cells if c["stratum"] == "GF_MATCHED_CONTROL"}
    if bm - cm:
        raise SystemExit(f"{len(bm-cm)} GF_BEARING memories have ZERO matched control")

    strat = collections.Counter(c["stratum"] for c in cells)
    calls = sum(c["replicates"] for c in cells) * 2
    dec = [c for c in cells
           if c["stratum"] == "GF_BEARING" and not c["also_gold_bearing"]]
    log(f"\n[design] {len(cells)} cells, {len(bm)} memories, "
        f"{len({c['trajectory_id'] for c in cells})} episodes, "
        f"{len({c['task_id'] for c in cells})} tasks")
    log(f"[design] strata {dict(strat)}")
    log(f"[design] DECIDING stratum (GF-bearing AND NOT gold-bearing): {len(dec)} cells "
        f"on {len({c['memory_unit_locator'] for c in dec})} memories / "
        f"{len({c['trajectory_id'] for c in dec})} episodes")
    log(f"[design] also-gold-bearing GF_BEARING cells: "
        f"{sum(1 for c in cells if c['stratum']=='GF_BEARING' and c['also_gold_bearing'])}")
    log(f"[design] PLANNED CALLS {calls} (budget {args.max_calls})")
    if calls > args.max_calls:
        raise SystemExit(f"planned {calls} exceeds budget {args.max_calls}")

    args.cells_out.parent.mkdir(parents=True, exist_ok=True)
    with args.cells_out.open("w") as fh:
        for c in sorted(cells, key=lambda c: (c["memory_unit_locator"], c["task_id"])):
            fh.write(json.dumps(c, sort_keys=True) + "\n")
    log(f"[wrote] {args.cells_out}")

    write_json_atomic(args.out, {
        "_what": "GF2 gold-free two-stratum design. ZERO endpoint calls.",
        "_precommitment": "docs/GOLD_FREE_SCREEN_PRECOMMITMENT.md",
        "config": {k: (_rel_to_repo(v) if isinstance(v, Path) else v)
                   for k, v in vars(args).items()},
        "n_cells": len(cells), "strata": dict(strat),
        "n_memories": len(bm),
        "n_source_episodes": len({c["trajectory_id"] for c in cells}),
        "n_tasks": len({c["task_id"] for c in cells}),
        "deciding_stratum_gf_and_not_gold": {
            "n_cells": len(dec),
            "n_memories": len({c["memory_unit_locator"] for c in dec}),
            "n_source_episodes": len({c["trajectory_id"] for c in dec}),
            "_why": "the executed cells were chosen by the GOLD screen, so a pooled "
                    "GF contrast is enriched for gold-bearing cells and would "
                    "re-measure the gold screen. This stratum governs the verdict.",
        },
        "n_gf_bearing_also_gold": sum(
            1 for c in cells if c["stratum"] == "GF_BEARING" and c["also_gold_bearing"]),
        "size_cap_dropped": {"n": len(dropped), "cap_tokens": cap},
        "planned_calls": calls,
        "cells_artifact": _rel_to_repo(args.cells_out),
    })
    log(f"[wrote] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

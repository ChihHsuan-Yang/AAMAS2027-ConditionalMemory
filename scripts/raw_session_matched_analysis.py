#!/usr/bin/env python3
"""Is the raw reader effect real, or was it session drift?

WHY THIS EXISTS
---------------
The published reader-transfer headline (+0.1268 on raw, CI excluding zero) was
computed from a Gemma arm run 2026-10-01T03:05 against a gpt-oss comparator run
2026-09-30T16:47 -- ELEVEN HOURS APART. DEFECT_REGISTER #25 then established
that gpt-oss-120b is deterministic WITHIN a session and not ACROSS one:
re-issuing byte-identical MEMORY-FREE requests a day later returned different
text in 554/1124 cases, moving the no-memory baseline by -0.0303, the same
order as the effect itself.

So the published figure confounds READER with SESSION. The Writer x Reader
factorial cannot settle it -- raw has no writer axis, so it contains no raw
rows. This script compares the two arms re-run BACK-TO-BACK IN ONE SESSION.

WHAT WOULD FALSIFY THE PUBLISHED CLAIM
--------------------------------------
Stated before the numbers are read:

* the session-matched effect is materially SMALLER and its interval now
  contains zero  -> the published effect was substantially session drift;
* it is comparable and still excludes zero                -> the effect is real
  and the published point estimate was approximately right;
* it REVERSES sign                                        -> a finding, loudly.

The point estimate will not match exactly even in the best case, because the
cell set and the session both differ. Mutual CI containment is the test, not
equality.
"""
from __future__ import annotations

import collections
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D = REPO / "results/raw_session_matched"


def du(r: dict) -> float | None:
    a, b = r.get("reward_with_memory"), r.get("reward_without_memory")
    return None if a is None or b is None else a - b


def key(r: dict) -> tuple:
    p = r.get("provenance") or {}
    loc = (p.get("memory_unit_locator")
           or (r.get("source_episode_metadata") or {}).get("memory_unit_locator"))
    return (loc, r["future_task_id"], r.get("replicate_id"))


def boot(vals, tasks, n=20000, seed=5):
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
    return round(out[int(0.025 * n)], 4), round(out[int(0.975 * n)], 4)


def main() -> int:
    oss = [json.loads(l) for l in (D / "raw_gptoss.jsonl").open()]
    gem = [json.loads(l) for l in (D / "raw_gemma.jsonl").open()]

    # The arms must be the two readers, and nothing else may differ.
    mo, mg = {r["reader_model"] for r in oss}, {r["reader_model"] for r in gem}
    assert mo == {"gpt-oss-120b"}, mo
    assert mg == {"gemma-4-31B-it"}, mg
    co = {r["condition_id"] for r in oss}
    cg = {r["condition_id"] for r in gem}
    assert co.isdisjoint(cg), f"arms share a condition id: {co & cg}"

    O = {key(r): du(r) for r in oss if du(r) is not None}
    G = {key(r): du(r) for r in gem if du(r) is not None}
    matched = sorted(set(O) & set(G))
    if not matched:
        print("NO MATCHED CELLS -- check the join key before believing this")
        return 2

    # The memory text must be byte-identical across arms: only the reader changed.
    to = {key(r): r.get("memory_text") for r in oss}
    tg = {key(r): r.get("memory_text") for r in gem}
    same_text = sum(1 for k in matched if to.get(k) == tg.get(k))
    print(f"memory_text byte-identical across arms: {same_text}/{len(matched)}")
    if same_text != len(matched):
        print("REFUSING: the arms do not share their memory text, so this is "
              "not a reader-only contrast")
        return 2

    diffs = [G[k] - O[k] for k in matched]
    tasks = [k[1] for k in matched]
    lo, hi = boot(diffs, tasks)
    mean = sum(diffs) / len(diffs)
    mo_ = sum(O[k] for k in matched) / len(matched)
    mg_ = sum(G[k] for k in matched) / len(matched)
    nz = [(O[k], G[k]) for k in matched if O[k] != 0 and G[k] != 0]
    agree = sum(1 for a, b in nz if (a > 0) == (b > 0))

    PUB = (0.1268, 0.0511, 0.2050)
    out = {
        "_what": ("raw reader effect, BOTH ARMS RE-RUN IN ONE SESSION. Replaces "
                  "the published cross-session figure for this contrast."),
        "n_matched": len(matched),
        "_n_matched_UNIT": ("REPLICATE ROWS, not cells. The 550 are 275 cells x 2 "
                            "replicates; the join key includes replicate_id. "
                            "Averaging replicates within a cell first gives "
                            "n=275 cells over 123 tasks and the IDENTICAL point "
                            "estimate and interval, because the bootstrap "
                            "resamples by TASK and both replicates of a cell "
                            "always travel together. Quote 275 cells / 550 "
                            "replicate rows -- never '550 cells'."),
        "n_cells": len({(k[0], k[1]) for k in matched}),
        "n_tasks": len({k[1] for k in matched}),
        "deltaU_gptoss": round(mo_, 4),
        "deltaU_gemma": round(mg_, 4),
        "paired_diff_gemma_minus_gptoss": round(mean, 4),
        "ci95_task_clustered": [lo, hi],
        "excludes_zero": bool(lo > 0 or hi < 0),
        "sign_agreement_nonzero_under_both": f"{agree}/{len(nz)}",
        "published_cross_session": {"mean": PUB[0], "ci": [PUB[1], PUB[2]],
                                    "arms_hours_apart": 11},
        "published_mean_inside_session_matched_CI": bool(lo <= PUB[0] <= hi),
        "session_matched_mean_inside_published_CI": bool(PUB[1] <= mean <= PUB[2]),
    }
    out["VERDICT"] = (
        "REVERSED_SIGN" if (mean > 0) != (PUB[0] > 0) else
        "SURVIVES_SESSION_MATCHING" if out["excludes_zero"] else
        "DOES_NOT_SURVIVE_SESSION_MATCHING")
    dest = REPO / "results/ledgers/raw_session_matched_analysis.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

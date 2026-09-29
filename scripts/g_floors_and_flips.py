#!/usr/bin/env python3
"""G1+G3: the three noise floors and the flip rates, from D's analysis layer.

No estimator is reimplemented here. This script loads the real rows, calls
``p1mem.analysis.{noise,labels,decomposition}``, and adds the two things those
modules cannot supply on their own:

* **positive controls for every zero.** A floor of 0.000 is reported only when
  the estimator that produced it has been shown to return non-zero on data
  that should produce non-zero. PROJECT rule: prove the detector can fire.
* **F_judge by explicit re-scoring**, re-running the vendored official scorer
  over the stored output text. Prereg section 2 says "re-score stored outputs
  without regenerating"; the free within-dataset variant is reported too.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.adapters import lmev2  # noqa: E402
from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: E402
    extract_boxed_answer,
    is_unknown,
)
from p1mem.analysis import decomposition as dc, labels as lb, noise as nz  # noqa: E402
from p1mem.analysis.common import jsonable  # noqa: E402
from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402


def rescore(rows: list[dict], root: Path) -> dict:
    """Re-score every stored output with the official scorer. F_judge, section 2.

    The re-scoring must apply the SAME rule the run applied, or F_judge measures
    verifier drift between the two code paths rather than scorer nondeterminism.
    The official rule (harness.py:1055) forces a score of False when the parsed
    answer is UNKNOWN; the official-prompt arm abstains, so omitting the override
    here would manufacture a judge-floor disagreement on every abstained row.
    """
    tasks = {t.id: t for t in lmev2.load_tasks(root)}
    out = {}
    for r in rows:
        if r.get("error_code_if_any"):
            continue
        t = tasks[r["future_task_id"]]
        new = {}
        for arm, of, rf in (("with", "output_with_memory", "reward_with_memory"),
                            ("without", "output_without_memory", "reward_without_memory")):
            txt = r.get(of)
            if txt is None:
                continue
            parsed = extract_boxed_answer(txt)
            new[rf] = 0.0 if is_unknown(parsed) else float(t.score(parsed))
        out[r["row_id"]] = new
    return out


def positive_control_exec(rows: list[dict], n_boot: int) -> dict:
    """Prove exec_floor CAN return non-zero.

    Corrupt a copy in the shape of the defect we fear -- perturb one replicate
    of some cells -- and require the estimator to notice. A floor of 0.000 from
    an estimator never shown to fire is not a measurement.
    """
    import copy
    import random
    mutated = copy.deepcopy(rows)
    rng = random.Random(7)
    n = 0
    seen = set()
    for r in mutated:
        if r.get("error_code_if_any") or r.get("delta_utility") is None:
            continue
        cid = r["cell_id"]
        if r.get("replicate_id") == 1 and cid not in seen and rng.random() < 0.5:
            seen.add(cid)
            r["reward_with_memory"] = 1.0 - float(r["reward_with_memory"])
            r["delta_utility"] = r["reward_with_memory"] - r["reward_without_memory"]
            n += 1
    est = nz.exec_floor(mutated, scale="delta", n_boot=n_boot, allow_pooling=True)
    return {"_what": "F_exec recomputed after flipping one replicate in "
                     f"{n} cells; MUST be > 0 or the estimator cannot fire",
            "n_cells_perturbed": n, "point": est.point,
            "fires": bool(est.point is not None and est.point > 0)}


def positive_control_judge(rows: list[dict], n_boot: int) -> dict:
    """Prove judge_floor CAN return non-zero: plant a disagreement."""
    import copy
    mutated = copy.deepcopy(rows)
    live = [r for r in mutated if not r.get("error_code_if_any")
            and r.get("reward_with_memory") is not None]
    fake = {}
    for r in live[:20]:
        fake[r["row_id"]] = {
            "reward_with_memory": 1.0 - float(r["reward_with_memory"]),
            "reward_without_memory": float(r["reward_without_memory"]),
        }
    est = nz.judge_floor(mutated, fake, n_boot=n_boot)
    return {"_what": "F_judge recomputed against a re-scoring that DISAGREES on "
                     f"{len(fake)} rows; MUST be > 0 or the estimator cannot fire",
            "n_rows_planted": len(fake), "point": est.point,
            "fires": bool(est.point is not None and est.point > 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path,
                    default=REPO / "results/deltau_pilot/cells.jsonl")
    ap.add_argument("--root", type=Path, default=Path("/tmp/lmev2"))
    ap.add_argument("--out", type=Path, default=REPO / "results/deltau_pilot/analysis")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260929)
    # Pooling across verifier_id is REQUIRED on this benchmark and justified in
    # docs/DECISION_LOG.md (2026-09-29, G1): the scorer is a property of the
    # QUESTION, not of an arm, and every dU is a within-task contrast, so no dU
    # ever compares two scorers. verifier_VERSION homogeneity still holds and is
    # still enforced. The flag lands on every estimate.
    ap.add_argument("--allow-pooling", action="store_true", default=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(args.rows)
    print(f"[rows] {len(rows)} from {args.rows}")
    live = [r for r in rows if not r.get("error_code_if_any")]
    print(f"       {len(live)} without an error code; "
          f"{len(rows) - len(live)} errored")

    # ---------------------------------------------------------------- floors
    print("\n[1] noise floors (prereg section 2)")
    rs = rescore(rows, args.root)
    floors = nz.all_floors(rows, rescored=rs, n_boot=args.n_boot, seed=args.seed,
                           allow_pooling=args.allow_pooling)
    floors["F_judge_within_dataset"] = nz.judge_floor(
        rows, None, n_boot=args.n_boot, seed=args.seed).to_dict()
    floors["positive_controls"] = {
        "F_exec": positive_control_exec(rows, args.n_boot),
        "F_judge": positive_control_judge(rows, args.n_boot),
    }
    write_json_atomic(args.out / "01_noise_floors.json", jsonable(floors))
    for k in ("F_exec_delta", "F_exec_with", "F_exec_without", "F_empty",
              "F_judge", "F_judge_within_dataset"):
        e = floors[k]
        pt = "UNMEASURED" if e["point"] is None else f"{e['point']:.6f}"
        ci = ("" if e["ci_lower"] is None
              else f"  [95% CI {e['ci_lower']:.6f}, {e['ci_upper']:.6f}]")
        print(f"    {k:26s} {pt}{ci}   n_obs={e['n_obs']}")
        for f in e["flags"]:
            print(f"        ! {f[:150]}")
    for name, pc in floors["positive_controls"].items():
        print(f"    positive control {name}: fires={pc['fires']} point={pc['point']}")

    F = floors["F_exec_delta"]["point"]
    print(f"\n    reference floor F (dU scale) = {F}")

    # ---------------------------------------------------------- labels/flips
    print("\n[2] robust labels and sign flips (sections 4, 5, 11, 12)")
    lab = lb.label_analysis(rows, F, n_boot=args.n_boot, seed=args.seed, bh_q=0.10,
                            allow_pooling=args.allow_pooling)
    if F is not None:
        lab["supplementary_additive_null"] = lb.additive_null_flip_rate(
            rows, F, n_null=200, n_boot=max(200, args.n_boot // 10), seed=args.seed,
            allow_pooling=args.allow_pooling)
    cells = lb.cell_statistics(rows, F, n_boot=args.n_boot, seed=args.seed,
                               allow_pooling=args.allow_pooling)
    write_json_atomic(args.out / "02_labels_and_flips.json", jsonable(lab))
    write_json_atomic(args.out / "02b_cell_statistics.json",
                      jsonable([c.to_dict() for c in cells]))

    # ------------------------------------------------------- decomposition
    print("\n[3] variance decomposition (section 6)")
    dec = dc.variance_decomposition(rows, exec_floor_sd=F,
                                    n_boot=min(200, args.n_boot), seed=args.seed,
                                    allow_pooling=args.allow_pooling)
    write_json_atomic(args.out / "03_variance_decomposition.json",
                      jsonable(dec.to_dict()))
    print(f"    {dec.method} converged={dec.converged} fallback={dec.used_fallback}")
    for c in dc.COMPONENTS:
        print(f"      {c:<12} share {dec.shares.get(c, 0.0):.4f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

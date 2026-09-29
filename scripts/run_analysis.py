#!/usr/bin/env python3
"""Run the full pre-registered analysis over a JSONL of canonical rows.

    python3 scripts/run_analysis.py --rows results/cells.jsonl --out results/analysis
    python3 scripts/run_analysis.py --synthetic --out /tmp/p1_analysis_demo

Order is not arbitrary and is enforced: the floors (prereg section 2) are measured FIRST,
because nothing downstream is interpretable without them (EXPERIMENT_PLAN section 3), and
the labels in sections 4-5 take F as an input. If F cannot be measured the run does not
substitute a zero -- it labels every cell ``undetermined`` and says so, which is the
correct state of this project until P1-051 executes.

Everything lands in one JSON per stage plus a human-readable summary, so a number in the
paper can be traced to the file that produced it (PROJECT_GOAL invariant 6).

**No endpoint calls, no inference.** Reads artifacts, writes artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem.schema import load_jsonl, write_json_atomic  # noqa: E402
from p1mem.analysis import (  # noqa: E402
    decomposition as dc,
    efficiency as eff,
    figures as fg,
    labels as lb,
    noise as nz,
)
from p1mem.analysis.common import jsonable  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--rows", type=Path, help="JSONL of canonical schema rows")
    src.add_argument("--synthetic", action="store_true",
                     help="generate synthetic rows from a KNOWN model and validate "
                          "recovery; use to smoke-test the pipeline with no data")
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--bh-q", type=float, default=0.10)
    ap.add_argument("--allow-pooling", action="store_true",
                    help="pool rows spanning multiple clusters/verifiers. Records the "
                         "heterogeneity as a flag on every estimate. Needs a reason in "
                         "docs/DECISION_LOG.md.")
    ap.add_argument("--figures", action="store_true", help="also render PNGs")
    args = ap.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    truth = None
    if args.synthetic:
        from p1mem.analysis.synthetic import make_dataset, retrieval_sweep_rows
        ds = make_dataset(seed=args.seed)
        rows = ds.rows
        sweep_rows = retrieval_sweep_rows(ds)
        truth = {"variance_shares": ds.spec.variance_shares(),
                 "variance_components": ds.spec.variance_components(),
                 "realized_components": ds.realized_components(),
                 "sd_exec_with": ds.spec.sd_exec_with,
                 "sd_exec_without": ds.spec.sd_exec_without,
                 "sd_delta_noise": ds.spec.sd_delta_noise()}
        print(f"[synthetic] {len(rows)} rows from a known generative model")
    else:
        rows = load_jsonl(args.rows)
        sweep_rows = rows
        print(f"[rows] {len(rows)} loaded from {args.rows}")

    kw = {"n_boot": args.n_boot, "seed": args.seed, "allow_pooling": args.allow_pooling}

    # ---- 1. floors FIRST (prereg section 2)
    print("[1/5] noise floors ...")
    floors = nz.all_floors(rows, **kw)
    write_json_atomic(out / "01_noise_floors.json", jsonable(floors))
    F = floors["F_exec_delta"]["point"]
    if F is None:
        print("      ! F is UNMEASURED. Every label will be 'undetermined'. "
              "This is correct, not a defect: prereg section 2 forbids assuming a floor.")
    else:
        print(f"      F (F_exec on the dU scale) = {F:.5f}")

    # ---- 2. labels + sign flips (sections 4, 5, 11, 12)
    print("[2/5] robust labels and sign flips ...")
    lab = lb.label_analysis(rows, F, n_boot=args.n_boot, seed=args.seed,
                            bh_q=args.bh_q, allow_pooling=args.allow_pooling)
    cells = lb.cell_statistics(rows, F, n_boot=args.n_boot, seed=args.seed,
                               allow_pooling=args.allow_pooling)
    if F is not None:
        lab["supplementary_additive_null"] = lb.additive_null_flip_rate(
            rows, F, n_null=200, n_boot=max(200, args.n_boot // 10), seed=args.seed
        )
    write_json_atomic(out / "02_labels_and_flips.json", jsonable(lab))
    prim = lab.get("primary_balanced", {})
    if prim.get("robust", {}).get("point") is not None:
        print(f"      robust flip rate (balanced, PRIMARY) = "
              f"{prim['robust']['point']:.4f}  "
              f"[{prim['robust']['ci_lower']:.3f}, {prim['robust']['ci_upper']:.3f}]  "
              f"n={prim['n_memories_eligible_denominator']}")
        print(f"      naive  flip rate (comparator)        = "
              f"{prim['naive']['point']:.4f}   "
              f"gap = {prim['gap_naive_minus_robust']:+.4f}")

    # ---- 3. variance decomposition (section 6)
    print("[3/5] variance decomposition ...")
    dec = dc.variance_decomposition(rows, exec_floor_sd=F,
                                    n_boot=min(200, args.n_boot),
                                    seed=args.seed, allow_pooling=args.allow_pooling)
    payload = dec.to_dict()
    if truth:
        payload["synthetic_recovery_vs_population"] = dc.recovery_error(
            dec, truth["variance_shares"])
        rc = truth["realized_components"]; tot = sum(rc.values())
        payload["synthetic_recovery_vs_realized"] = dc.recovery_error(
            dec, {k: v / tot for k, v in rc.items()})
    write_json_atomic(out / "03_variance_decomposition.json", jsonable(payload))
    print(f"      {dec.method}  converged={dec.converged} fallback={dec.used_fallback}")
    for c in dc.COMPONENTS:
        share = ("UNMEASURED" if c not in dec.shares
                 else f"{dec.shares[c]:.4f}")
        print(f"        {c:<12} share {share}")

    # ---- 4. efficiency (section 10)
    print("[4/5] efficiency ...")
    ef = eff.efficiency_report(rows, cells, n_boot=args.n_boot, seed=args.seed,
                               allow_pooling=args.allow_pooling)
    write_json_atomic(out / "04_efficiency.json", jsonable(ef))

    # ---- 5. figures (schema support checked whether or not PNGs are drawn)
    print("[5/5] figures ...")
    support = fg.check_schema_support(sweep_rows, cells,
                                      n_boot=min(200, args.n_boot))
    figdata = {
        "schema_support": support,
        "figure2": fg.figure2_data(sweep_rows, n_boot=min(500, args.n_boot),
                                   seed=args.seed),
        "figure3": fg.figure3_data(cells, rows),
        "figure4": fg.figure4_data(cells, rows, n_boot=min(500, args.n_boot),
                                   seed=args.seed),
    }
    write_json_atomic(out / "05_figures.json", jsonable(figdata))
    for k in ("figure2", "figure3", "figure4"):
        s = support.get(k, {})
        print(f"      {k}: producible={s.get('producible')} "
              f"missing={s.get('missing_fields') or []}")
    if args.figures:
        fg.figure2_figure(figdata["figure2"], str(out / "fig2_frontier.png"))
        fg.figure3_figure(figdata["figure3"], str(out / "fig3_conditional.png"))
        fg.figure4_figure(figdata["figure4"], str(out / "fig4_similarity.png"))
        print(f"      PNGs written to {out}")

    if truth:
        write_json_atomic(out / "00_synthetic_truth.json", jsonable(truth))

    manifest = {
        "n_rows": len(rows),
        "source": "synthetic" if args.synthetic else str(args.rows),
        "reference_floor_F": F,
        "n_boot": args.n_boot,
        "seed": args.seed,
        "bh_q": args.bh_q,
        "allow_pooling": args.allow_pooling,
        "prereg": "docs/ANALYSIS_PREREGISTRATION.md",
        "stages": ["01_noise_floors", "02_labels_and_flips",
                   "03_variance_decomposition", "04_efficiency", "05_figures"],
    }
    write_json_atomic(out / "manifest.json", jsonable(manifest))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

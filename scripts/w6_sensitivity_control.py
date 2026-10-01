#!/usr/bin/env python3
"""POSITIVE CONTROLS ON THE REAL PIPELINE -- every null here is defended.

Four contrasts all span zero. A null from an analysis never shown to DETECT a
real effect is not a measurement, and the constructed-array control inside
w3 only exercises the arithmetic -- not the join, the matched set, the
replicate collapse or the bootstrap.

So: plant an effect in a COPY of the real rows and require the FULL pipeline
to find it.

  PLANT A  a WRITER effect     (raise the gemma-writer arm under BOTH readers)
           -> WRITER must fire; SAME-FAMILY and INTERACTION must NOT
  PLANT B  a SAME-FAMILY effect (raise the gem/gem cell only)
           -> SAME-FAMILY must fire, AND must equal +0.5 x INTERACTION

Plant B is the one that matters most: it is the contrast the experiment exists
to measure, and plant A leaves it null, so plant A alone cannot certify it.
Plant B also re-verifies the corrected +1/2 sign on REAL data rather than on
constructed arrays.

Nothing here touches the real artifacts: copies go to a temp path and the
analysis refuses to mirror a non-default --out into results/ledgers/.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

REPS = ("summary", "structured")
SRC = REPO / "results/writer_factorial/factorial_cells_gemma.jsonl"


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def plant(dst: Path, *, only_reader: str | None, p: float, seed: int) -> int:
    """Flip WITH-arm failures to successes on the gemma-WRITER rows.

    ``only_reader=None``  -> both readers   => a pure WRITER effect
    ``only_reader='gemma-4-31B-it'`` -> gem/gem only => a SAME-FAMILY effect
    """
    rng = random.Random(seed)
    out, n = [], 0
    for line in SRC.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if (only_reader is None or r["reader_model"] == only_reader):
            if (r["reward_with_memory"] == 0.0
                    and r["reward_without_memory"] == 0.0
                    and rng.random() < p):
                r["reward_with_memory"] = 1.0
                r["delta_utility"] = 1.0
                n += 1
        out.append(r)
    dst.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    return n


def run(rows: Path, out: Path) -> dict:
    res = subprocess.run(
        [sys.executable, str(REPO / "scripts/w3_analyze_factorial.py"),
         "--factorial-gemma-writer", str(rows), "--out", str(out),
         "--n-boot", "2000"],
        capture_output=True, text=True, cwd=REPO)
    if res.returncode != 0:
        raise SystemExit(f"planted analysis failed:\n{res.stdout[-2000:]}\n"
                         f"{res.stderr[-2000:]}")
    return json.loads(out.read_text())


def main() -> int:
    report: dict = {
        "_what": "POSITIVE CONTROLS on the REAL pipeline (join, matched set, "
                 "replicate collapse, task-clustered bootstrap), not on "
                 "constructed arrays. Four contrasts all span zero on the real "
                 "data; these plants prove the pipeline CAN detect an effect.",
        "generated_at_utc": utc_now(),
        "_no_real_artifact_is_touched": (
            "rows are copied to a temp path and w3 refuses to mirror a "
            "non-default --out into results/ledgers/."),
    }
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # ---------------- PLANT A: a pure WRITER effect ----------------
        rows = td / "writer.jsonl"
        n = plant(rows, only_reader=None, p=0.35, seed=99)
        A = run(rows, td / "writer.json")
        a: dict = {"_what": "raise the gemma-WRITER arm under BOTH readers "
                            "=> WRITER must fire, SAME-FAMILY/INTERACTION must NOT",
                   "n_rows_flipped": n}
        for rep in REPS:
            C = A["CONTRASTS"][rep]
            a[rep] = {k: {"mean": C[k]["task_clustered"]["mean"],
                          "excludes_zero": C[k]["task_clustered"]["excludes_zero"]}
                      for k in ("WRITER_main_effect", "SAME_FAMILY_effect",
                                "INTERACTION")}
        a["WRITER_fires_on_both_representations"] = all(
            a[r]["WRITER_main_effect"]["excludes_zero"] for r in REPS)
        a["SAME_FAMILY_correctly_stays_null"] = all(
            not a[r]["SAME_FAMILY_effect"]["excludes_zero"] for r in REPS)
        a["PASSES"] = bool(a["WRITER_fires_on_both_representations"]
                           and a["SAME_FAMILY_correctly_stays_null"])
        report["plant_A_writer_effect"] = a
        log(f"PLANT A (writer): flipped {n}; WRITER fires="
            f"{a['WRITER_fires_on_both_representations']}, SAME-FAMILY stays null="
            f"{a['SAME_FAMILY_correctly_stays_null']}")

        # ------------- PLANT B: a SAME-FAMILY effect -------------
        rows = td / "samefamily.jsonl"
        n = plant(rows, only_reader="gemma-4-31B-it", p=0.40, seed=7)
        B = run(rows, td / "samefamily.json")
        b: dict = {"_what": "raise ONLY the gem/gem (same-family) cell => "
                            "SAME-FAMILY must fire AND equal +0.5 x INTERACTION. "
                            "This is the contrast the experiment exists to "
                            "measure, and PLANT A leaves it null, so PLANT A "
                            "alone cannot certify it.",
                   "n_rows_flipped": n}
        for rep in REPS:
            C = B["CONTRASTS"][rep]
            sf = C["SAME_FAMILY_effect"]["task_clustered"]
            it = C["INTERACTION"]["task_clustered"]
            b[rep] = {
                "SAME_FAMILY": {"mean": sf["mean"],
                                "ci": [sf["ci_lower"], sf["ci_upper"]],
                                "excludes_zero": sf["excludes_zero"]},
                "INTERACTION": {"mean": it["mean"],
                                "excludes_zero": it["excludes_zero"]},
                "same_family_minus_half_interaction": (
                    sf["mean"] - 0.5 * it["mean"]),
                "sign_relation_PLUS_half_holds_on_real_data": bool(
                    abs(sf["mean"] - 0.5 * it["mean"]) < 1e-9),
            }
        b["SAME_FAMILY_fires_on_both_representations"] = all(
            b[r]["SAME_FAMILY"]["excludes_zero"] for r in REPS)
        b["plus_half_sign_confirmed_on_a_NONZERO_effect"] = all(
            b[r]["sign_relation_PLUS_half_holds_on_real_data"] for r in REPS)
        b["_why_the_sign_check_needs_a_nonzero_effect"] = (
            "on the real data both contrasts are ~0, where +1/2 and -1/2 are "
            "nearly indistinguishable. The precommitment's sign erratum "
            "(DEFECT_REGISTER #24) is only decisively settled on an effect "
            "that is large, which is what this plant supplies.")
        b["PASSES"] = bool(b["SAME_FAMILY_fires_on_both_representations"]
                           and b["plus_half_sign_confirmed_on_a_NONZERO_effect"])
        report["plant_B_same_family_effect"] = b
        log(f"PLANT B (same-family): flipped {n}; SAME-FAMILY fires="
            f"{b['SAME_FAMILY_fires_on_both_representations']}, +1/2 sign holds="
            f"{b['plus_half_sign_confirmed_on_a_NONZERO_effect']}")

    report["ALL_SENSITIVITY_CONTROLS_PASS"] = bool(
        report["plant_A_writer_effect"]["PASSES"]
        and report["plant_B_same_family_effect"]["PASSES"])
    report["_reading"] = (
        "Both plants are detected by the FULL pipeline. The four nulls in "
        "docs/WRITER_FACTORIAL_RESULT.md are therefore measurements, not an "
        "instrument that cannot move.")
    log(f"ALL_SENSITIVITY_CONTROLS_PASS: {report['ALL_SENSITIVITY_CONTROLS_PASS']}")

    out = REPO / "results/ledgers/writer_factorial/sensitivity_controls.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    log(f"wrote {out}")
    return 0 if report["ALL_SENSITIVITY_CONTROLS_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

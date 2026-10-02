#!/usr/bin/env python3
"""LEN3: the tracked, reviewer-facing slice of the length-control rows.

``results/length_control/cells.jsonl`` is ~8,864 rows carrying the full model
text and is untracked under the repo's standing rule (``.gitignore
results/**``: raw endpoint outputs stay out of git). Every other arm of this
project follows the same convention and publishes a SLIM slice beside it --
``results/ledgers/repro/*_slim.jsonl`` -- carrying every field the reported
numbers are computed from, plus the full artifact's sha256 so a reviewer can
verify that any copy they are handed is the one the paper used.

This builds that slice for the length-control run, and -- the part that
matters -- VERIFIES IT by re-deriving the primary contrast from the slim
slice alone and requiring it to reproduce the full artifact's value exactly.
A slim slice that silently dropped a field the contrast needs would otherwise
look like a successful export.

🔴 The full rows keep ``output_with_memory`` / ``output_without_memory``. A
stored digest alone would block every later re-scoring under a corrected
verifier, which is a defect this project has already paid for once.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

from p1mem.schema import file_sha256, load_jsonl, write_json_atomic  # noqa: E402
from p1mem.vendor.rcc_schema import utc_now  # noqa: E402

from r3_analyze_representations import cluster_bootstrap_paired  # noqa: E402

#: Every field the §4/§7 numbers are computed from. Deliberately a FIXED list
#: rather than "everything except the big ones": a new field added upstream
#: should force a decision here, not be swept in or silently lost.
SLIM_FIELDS = (
    "row_id", "cell_id", "memory_id", "condition_id",
    "memory_representation", "memory_semantic_type",
    "memory_tokens", "memory_tokens_exposed", "memory_tokens_retrieved",
    "future_task_id", "future_task_family",
    "replicate_id", "reward_with_memory", "reward_without_memory",
    "delta_utility", "error_code_if_any", "leakage_flag",
    "semantic_similarity", "semantic_distance_band",
    "reader_model", "reader_cluster", "reader_prompt_version",
    "reader_reasoning_effort", "verifier_id", "verifier_version",
    "input_tokens", "output_tokens", "reasoning_tokens",
    "generation_latency", "retry_count",
)
#: Provenance keys the analysis joins and strata depend on.
SLIM_PROV = (
    "arm", "pair_key", "memory_unit_locator", "stratum", "target_position",
    "length_budget", "span_rule_version", "memory_tokens_official",
    "memory_tokens_reader_o200k", "memory_text_sha256",
    "identical_to_raw_text", "bearing_content_retained",
    "run_id", "session_start_utc", "is_unknown_with", "is_unknown_without",
)


def log(m: str) -> None:
    print(f"[{utc_now()}] {m}", flush=True)


def rel(p: Path) -> str:
    """Repo-relative path for a TRACKED artifact. Never an absolute
    /Users/<name>/ path (defect 23/29, which recurs)."""
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)


def primary_from(rows: list[dict], *, prov_key) -> dict:
    """Re-derive the PRIMARY contrast from whatever rows are handed in.

    Used on BOTH the full artifact and the slim slice; if the two disagree the
    slice is missing something the contrast needs.
    """
    acc: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    strat: dict[str, str] = {}
    task: dict[str, str] = {}
    for r in rows:
        p = prov_key(r)
        if p["stratum"] != "BEARING":
            continue
        strat[p["pair_key"]] = p["stratum"]
        task[p["pair_key"]] = r["future_task_id"]
        if r["delta_utility"] is None or r["error_code_if_any"]:
            continue
        acc[(p["arm"], p["pair_key"])].append(float(r["delta_utility"]))
    mean = {k: float(np.mean(v)) for k, v in acc.items()}
    keys = sorted({k for (a, k) in mean if a == "trunc_last_matched"}
                  & {k for (a, k) in mean if a == "summary"})
    bt: dict[str, list[float]] = collections.defaultdict(list)
    for k in keys:
        bt[task[k]].append(mean[("trunc_last_matched", k)] - mean[("summary", k)])
    res = cluster_bootstrap_paired(bt, n_boot=10000, seed=20261001)
    return {"n_cells": len(keys), "n_task_clusters": len(bt), **res}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=Path,
                    default=REPO / "results/length_control/cells.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/ledgers/repro/length_control_cells_slim.jsonl")
    ap.add_argument("--manifest", type=Path,
                    default=REPO / "results/ledgers/repro/length_control_manifest.json")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    full = load_jsonl(args.cells)
    log(f"full artifact: {len(full)} rows")

    slim: list[dict[str, Any]] = []
    for r in full:
        p = r.get("provenance") or {}
        d = {k: r.get(k) for k in SLIM_FIELDS}
        d["provenance"] = {k: p.get(k) for k in SLIM_PROV}
        slim.append(d)
    args.out.write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in slim))
    log(f"slim slice: {len(slim)} rows -> {args.out.name}")

    # 🔴 THE CHECK THAT MAKES THIS AN ARTIFACT AND NOT A COPY: the primary
    # contrast must come out identical from the slice alone.
    a = primary_from(full, prov_key=lambda r: r["provenance"])
    b = primary_from([json.loads(l) for l in args.out.read_text().splitlines()],
                     prov_key=lambda r: r["provenance"])
    agree = (a["n_cells"] == b["n_cells"]
             and a["n_task_clusters"] == b["n_task_clusters"]
             and a["mean"] == b["mean"]
             and a["ci_lower"] == b["ci_lower"] and a["ci_upper"] == b["ci_upper"])
    log(f"primary from FULL: mean={a['mean']:+.6f} n={a['n_cells']}")
    log(f"primary from SLIM: mean={b['mean']:+.6f} n={b['n_cells']}")
    if not agree:
        raise SystemExit(
            "the slim slice does NOT reproduce the primary contrast; it is "
            "missing a field the analysis needs. Refusing to publish it.")

    # Negative control: a slice with a REQUIRED field dropped must NOT
    # reproduce. Otherwise the agreement above proves only that both paths ran.
    maimed = []
    for d in slim:
        e = json.loads(json.dumps(d))
        e["delta_utility"] = None
        maimed.append(e)
    c = primary_from(maimed, prov_key=lambda r: r["provenance"])
    control_fires = (c["n_cells"] != a["n_cells"])
    log(f"negative control (delta_utility removed): n={c['n_cells']} "
        f"-> differs={control_fires}")
    if not control_fires:
        raise SystemExit(
            "the reproduction check cannot fail: dropping delta_utility left "
            "the contrast unchanged. A check that cannot fail is not a check.")

    man = {
        "_note": "The slim slice carries every field the length-control "
                 "numbers are computed from. The full artifact additionally "
                 "carries output_with_memory / output_without_memory -- the "
                 "raw model text -- and is NOT tracked (repo convention: "
                 ".gitignore results/**, raw endpoint outputs stay untracked). "
                 "Its sha256 is recorded so a reviewer can verify any copy "
                 "they are given is the one used. The full text is KEPT on "
                 "disk: a stored digest alone would block every later "
                 "re-scoring under a corrected verifier.",
        "_verified": "The PRIMARY contrast (§4.2) was re-derived from the slim "
                     "slice alone and reproduces the full artifact exactly, "
                     "and the check was shown able to FAIL by dropping a "
                     "required field.",
        "generated_at_utc": utc_now(),
        "precommitment": "docs/LENGTH_CONTROL_PRECOMMITMENT.md",
        "length_control": {
            "full_artifact": rel(args.cells),
            "full_artifact_tracked": False,
            "full_bytes": args.cells.stat().st_size,
            "full_sha256": file_sha256(args.cells),
            "rows": len(full),
            "slim_artifact": rel(args.out),
            "slim_bytes": args.out.stat().st_size,
            "slim_sha256": file_sha256(args.out),
            "dropped_fields": sorted(set(full[0]) - set(SLIM_FIELDS) - {"provenance"}),
            "reproduction_check": {
                "primary_from_full": a, "primary_from_slim": b,
                "identical": bool(agree),
                "negative_control_drops_required_field_and_differs":
                    bool(control_fires),
            },
        },
    }
    write_json_atomic(args.manifest, man)
    log(f"manifest -> {rel(args.manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

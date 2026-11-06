#!/usr/bin/env python3
"""Package the later follow-up runs (x1 position/session, x2 fixed context, x3 retrieval)
for public release, with checksums, counts and condition definitions.  No inference.

These runs executed on ALCF Sophia.  Where the Sophia scripts put them (see
cluster/sophia/env.sh, job.pbs and submit.sh): ``$ROOT/runs/<run>`` with
``ROOT=/lus/eagle/projects/datascience_collab/uhanjir/p1mem`` and run names
``x1_position_smain``, ``x2_fixedctx_smain``, ``x3_retrieval_smain``.  A finished run has
``summary.json`` (the done marker).  Run this on Sophia, where the directories are:

    python scripts/package_followups.py \\
        --x1 $ROOT/runs/x1_position_smain \\
        --x2 $ROOT/runs/x2_fixedctx_smain \\
        --x3 $ROOT/runs/x3_retrieval_smain \\
        --out followups_package --validate

What it does, per run: refuses a run without ``summary.json``; copies the result rows
(``cells.jsonl`` for x1 and x2, ``per_task.jsonl`` for x3) and ``summary.json``; records
sha256, byte size and row counts (by condition, arm, stratum, replicate, and rows with a
missing reward); records the distinct code revisions and run configuration found in the
rows; optionally runs the repository validator on the cell rows; scans for credential-like
strings and refuses to package if it finds any.  It does not copy ``cache.jsonl`` (a
response cache) or ``embeddings.jsonl``.  It writes ``MANIFEST_followups.json``.

Nothing is invented: absent fields stay absent, and a run that is missing is reported as
missing, not skipped silently.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

RUNS = {
    "x1": {"rows": "cells.jsonl", "role": "second session, randomized memory position (paper S11, Figs 5a, 6)"},
    "x2": {"rows": "cells.jsonl", "role": "fixed total context, Raw/Summary/Structured (paper S11, Table S5, Fig 3b)"},
    "x3": {"rows": "per_task.jsonl", "role": "retrieval baselines vs the screen (paper Table S6, Fig 4b)"},
}
SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|"
                    r"Bearer\s+[A-Za-z0-9._-]{20,}|api[_-]?key\s*[=:]\s*\S{12,}|"
                    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_secrets(path: Path) -> list[int]:
    hits = []
    with path.open(errors="replace") as f:
        for i, line in enumerate(f, 1):
            if SECRET.search(line):
                hits.append(i)
    return hits


def summarize_rows(path: Path) -> dict:
    n = 0
    by = {k: collections.Counter() for k in ("condition_id", "arm", "stratum", "replicate_id", "reader_model")}
    null_reward, codes, prompts = 0, set(), set()
    for line in path.open():
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        prov = r.get("provenance") or {}
        by["condition_id"][str(r.get("condition_id"))] += 1
        by["arm"][str(prov.get("arm", r.get("memory_representation")))] += 1
        by["stratum"][str(prov.get("stratum", r.get("bearing_label")))] += 1
        by["replicate_id"][str(r.get("replicate_id"))] += 1
        by["reader_model"][str(r.get("reader_model"))] += 1
        if r.get("reward_with_memory") is None or r.get("reward_without_memory") is None:
            null_reward += 1
        if prov.get("code_sha"):
            codes.add(prov["code_sha"])
        if r.get("reader_prompt_version"):
            prompts.add(r["reader_prompt_version"])
    return {"rows": n, "rows_with_missing_reward": null_reward,
            "counts": {k: dict(v) for k, v in by.items()},
            "code_revisions_in_rows": sorted(codes), "reader_prompt_versions": sorted(prompts)}


def package_run(name: str, run_dir: Path, out: Path, validate: bool) -> dict:
    spec = RUNS[name]
    info = {"run": name, "source_dir": f"runs/{run_dir.name}", "role": spec["role"]}
    if not run_dir.is_dir():
        return {**info, "status": "MISSING: directory not found"}
    if not (run_dir / "summary.json").exists():
        return {**info, "status": "INCOMPLETE: no summary.json (done marker)"}
    rows = run_dir / spec["rows"]
    if not rows.exists():
        return {**info, "status": f"MISSING: {spec['rows']} not found"}
    for f in (rows, run_dir / "summary.json"):
        hits = scan_secrets(f)
        if hits:
            raise SystemExit(f"REFUSING: credential-like text in {f} at lines {hits[:5]}")
    dest = out / name
    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    for f in (rows, run_dir / "summary.json"):
        shutil.copy2(f, dest / f.name)
        files[f.name] = {"sha256": sha256(dest / f.name), "bytes": (dest / f.name).stat().st_size}
    info.update(status="PACKAGED", files=files, summary_json=json.loads((run_dir / "summary.json").read_text()))
    if spec["rows"] == "cells.jsonl":
        info.update(summarize_rows(dest / "cells.jsonl"))
        if validate:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
            from p1mem.validate import validate_file
            rep = validate_file(str(dest / "cells.jsonl"))
            info["validator"] = {"rows": rep.n_rows, "errors": len(rep.errors), "warnings": len(rep.warnings),
                                 "warning_codes": sorted(rep.codes())}
    else:
        info["rows"] = sum(1 for l in (dest / spec["rows"]).open() if l.strip())
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for k in RUNS:
        ap.add_argument(f"--{k}", type=Path, help=f"{k} run directory")
    ap.add_argument("--out", type=Path, default=Path("followups_package"))
    ap.add_argument("--logs", type=Path, help="directory with <run>.log and jobs.log to include as provenance")
    ap.add_argument("--validate", action="store_true", help="run the repository validator on cell rows")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = {"_what": "Follow-up runs packaged for public release; see docs/RELEASE_COVERAGE.md",
                "runs": {}}
    for k in RUNS:
        d = getattr(a, k)
        manifest["runs"][k] = package_run(k, d, a.out, a.validate) if d else {"run": k, "status": "NOT PROVIDED"}
        print(f"{k}: {manifest['runs'][k]['status']}"
              + (f"  rows={manifest['runs'][k].get('rows')}" if manifest["runs"][k]["status"] == "PACKAGED" else ""))
    if a.logs:
        manifest["logs"] = {}
        (a.out / "logs").mkdir(exist_ok=True)
        for f in sorted(a.logs.glob("*.log")):
            hits = scan_secrets(f)
            if hits:
                raise SystemExit(f"REFUSING: credential-like text in {f} at lines {hits[:5]}")
            shutil.copy2(f, a.out / "logs" / f.name)
            manifest["logs"][f.name] = {"sha256": sha256(f), "bytes": f.stat().st_size}
    (a.out / "MANIFEST_followups.json").write_text(json.dumps(manifest, indent=2))
    ok = all(v["status"] == "PACKAGED" for v in manifest["runs"].values())
    print("VERDICT:", "ALL_RUNS_PACKAGED" if ok else "SOME_RUNS_NOT_PACKAGED (see manifest)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

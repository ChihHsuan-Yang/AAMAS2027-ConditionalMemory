"""Synthetic tests for the follow-up packager (logic only; not evidence about the real runs)."""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pkg", REPO / "scripts/package_followups.py")
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


def make_run(d: Path, rows, name="cells.jsonl", done=True):
    d.mkdir(parents=True)
    (d / name).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    if done:
        (d / "summary.json").write_text(json.dumps({"rows_written": len(rows)}))
    return d


ROW = {"condition_id": "c", "reader_model": "gpt-oss-120b", "replicate_id": 0, "memory_representation": "raw",
       "reward_with_memory": 1.0, "reward_without_memory": 0.0,
       "provenance": {"arm": "raw", "stratum": "BEARING", "code_sha": "abc123"}}


def test_packages_and_checksums(tmp_path):
    run = make_run(tmp_path / "x2", [ROW, {**ROW, "reward_with_memory": None}])
    info = pkg.package_run("x2", run, tmp_path / "out", validate=False)
    assert info["status"] == "PACKAGED" and info["rows"] == 2 and info["rows_with_missing_reward"] == 1
    assert info["code_revisions_in_rows"] == ["abc123"]
    dest = tmp_path / "out/x2/cells.jsonl"
    assert info["files"]["cells.jsonl"]["sha256"] == pkg.sha256(dest)


def test_run_without_done_marker_is_not_packaged(tmp_path):
    run = make_run(tmp_path / "x1", [ROW], done=False)
    assert pkg.package_run("x1", run, tmp_path / "out", False)["status"].startswith("INCOMPLETE")


def test_missing_directory_is_reported_not_skipped(tmp_path):
    assert pkg.package_run("x3", tmp_path / "nope", tmp_path / "out", False)["status"].startswith("MISSING")


def test_credentials_block_packaging(tmp_path):
    run = make_run(tmp_path / "x2", [{**ROW, "note": "api_key=sk-abcdefghijklmnopqrstuvwxyz0123"}])
    with pytest.raises(SystemExit):
        pkg.package_run("x2", run, tmp_path / "out", False)

"""Gate tests for the HF exporter, especially GATE 4 (re-validate the WRITTEN file).

GATE 4 exists because of a defect that actually shipped on 2026-09-30. Gates 1-3 all
passed, the upload succeeded, and every published row still failed the validator
published beside it -- 13,557 ``unknown_field`` errors over 4,519 rows.

The cause: ``redact_row`` adds three export-provenance fields AFTER gate 1 has validated
the in-memory rows, and those fields were not in ``FIELD_SPEC``. Both components were
individually correct. **The defect lived in the seam**, and no local check could see it,
because no check ever read the emitted artifact back. It was found only by downloading
the release and running its own documented verification command.

So these tests do what the gates did not: build the artifact, then read it from disk and
validate it as a consumer would.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from p1mem import schema as S     # noqa: E402
from p1mem import validate as V   # noqa: E402


def _load_exporter():
    """Import scripts/export_hf.py by path, registered so dataclasses resolve."""
    spec = importlib.util.spec_from_file_location("export_hf", REPO / "scripts" / "export_hf.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["export_hf"] = mod
    spec.loader.exec_module(mod)
    return mod


EH = _load_exporter()


def _exported_rows(n_cells: int = 4):
    """Whole CELLS only. Slicing mid-cell would trip num_replicates_mismatch, which is
    that check working correctly on a truncated corpus, not an export defect."""
    rows = []
    for cell in range(n_cells):
        for rep in range(2):
            r = S.new_row(
                benchmark="longmemeval_v2", benchmark_version="testrev",
                source_episode_id=f"traj{cell}",
                source_episode_metadata={"domain": "web", "outcome": "success"},
                memory_representation="raw", memory_semantic_type="episodic",
                memory_text=f"memory body for cell {cell}", memory_tokens=6,
                memory_source_span={"trajectory_id": f"traj{cell}", "n_states": 1},
                memory_writer_model="none:deterministic_span",
                memory_writer_cluster="none:deterministic_span",
                memory_writer_prompt_version="page_visit_segmentation_v1",
                embedding_model="Salesforce/SFR-Embedding-Mistral",
                embedding_version="testemb",
                memory_embedding_reference={"store": "e.npy", "index": cell, "dim": 4096},
                future_task_id=f"task{cell}", future_task_family="procedure",
                future_task_text="a question",
                task_embedding_reference={"store": "t.npy", "index": cell, "dim": 4096},
                semantic_similarity=0.4, semantic_distance_band="MID",
                retrieval_method="oracle",
                memory_tokens_retrieved=6, memory_tokens_exposed=6,
                replicate_id=rep,
                seed_or_sampling_config={"temperature": 0.0, "max_tokens": 512},
                reader_model="gpt-oss-120b", reader_cluster="metis",
                reader_endpoint="metis:/resource_server/metis/api/v1",
                reader_prompt_version="p1_deltau_raw_v1", reader_reasoning_effort="low",
                output_without_memory="no", output_with_memory="yes",
                reward_without_memory=0.0, reward_with_memory=1.0,
                generation_latency=1.0, end_to_end_latency=1.0,
                embedding_calls=0, generation_calls=2, input_tokens=10, output_tokens=2,
                reasoning_tokens=1, retry_count=0,
                provenance={"code_sha": "t", "config_sha256": "0" * 64, "run_id": "t"},
                license_source_reference="longmemeval_v2:Apache-2.0",
                verifier_id="norm_phrase_set_match", verifier_version="vendored@test",
                reward_is_continuous=False, condition_id="test_condition",
                reader_endpoint_sha256=S.sanitized_base_url_hash("x"),
                source_span_tokens=6, compression_ratio=1.0, extraction_cost_proxy=0.0,
                faithfulness_notes=S.FAITHFULNESS_RAW_IS_TAUTOLOGY_NOTE,
                storage_bytes=len(f"memory body for cell {cell}".encode("utf-8")),
                num_replicates=2, confidence_or_stability=1.0,
                memory_type_coarse="experience",
                memory_type_fine="episodic.page_visit.success.single_state",
            )
            rows.append(r)
    return [EH.redact_row(r)[0] for r in rows]


def _write(rows, tmp: Path) -> Path:
    p = tmp / "cells.jsonl"
    S.write_jsonl_atomic(p, rows)
    return p


def test_gate4_control_a_correct_export_revalidates():
    """NEGATIVE CONTROL. If this fails, every 'caught' below is uninterpretable."""
    rows = _exported_rows()
    with tempfile.TemporaryDirectory() as d:
        EH.gate_exported_file_revalidates(_write(rows, Path(d)), len(rows))


def test_gate4_catches_the_defect_that_actually_shipped():
    """An export-added field absent from FIELD_SPEC. This is the real 2026-09-30 bug."""
    rows = _exported_rows()
    rows[0]["some_unplanned_export_field"] = 1
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(EH.GateFailure):
            EH.gate_exported_file_revalidates(_write(rows, Path(d)), len(rows))


def test_gate4_catches_a_row_count_mismatch():
    rows = _exported_rows()
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(EH.GateFailure):
            EH.gate_exported_file_revalidates(_write(rows[:2], Path(d)), len(rows))


def test_export_provenance_fields_are_in_the_schema():
    """The three fields redact_row adds must be part of the contract, not bolted on."""
    for f in ("license_policy", "text_fields_withheld", "reconstruction_required"):
        assert f in S.FIELD_SPEC, f
        assert f in S.FIELD_ORDER, f


def test_reconstruction_flag_must_agree_with_the_withheld_list():
    rows = _exported_rows()
    rows[0]["reconstruction_required"] = True      # but nothing was withheld
    assert "reconstruction_flag_mismatch" in {i.code for i in V.validate_row(rows[0])}


def test_a_field_declared_withheld_must_not_still_hold_its_text():
    """The withholding must be real. Declaring it while shipping the text is worse than
    not declaring it, because the row asserts a protection it does not provide."""
    rows = _exported_rows()
    rows[0]["text_fields_withheld"] = ["memory_text"]
    rows[0]["reconstruction_required"] = True
    assert "declared_withheld_but_present" in {i.code for i in V.validate_row(rows[0])}


def test_withheld_empty_list_and_null_are_different_facts():
    """[] means 'a policy ran and withheld nothing'; null means 'no policy has run'."""
    rows = _exported_rows()
    assert rows[0]["text_fields_withheld"] == []
    assert rows[0]["reconstruction_required"] is False
    unexported = S.blank_row()
    assert unexported["text_fields_withheld"] is None


def test_v1_source_text_is_actually_withheld_and_the_gate_agrees():
    """End-to-end on the licence that matters: a V1 row must lose its source text."""
    rows = _exported_rows()
    v1 = dict(rows[0])
    v1["license_source_reference"] = "longmemeval_v1:MIT+sharegpt_upstream"
    v1["memory_text"] = "verbatim ShareGPT filler that may not be redistributed"
    out, withheld = EH.redact_row(v1)
    assert out["memory_text"] == EH.WITHHELD
    assert "memory_text" in withheld
    assert out["reconstruction_required"] is True
    EH.gate_license_exclusion([out])          # must now pass

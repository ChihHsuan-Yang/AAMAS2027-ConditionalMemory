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


# ===================================================================== v0.2 / schema v3
# The representation arm made faithfulness measurable for the first time. Two v0.1
# behaviours were correct only because every row was raw, and would have shipped as
# FALSE the moment a model-written row existed. These tests pin the repair.


def _written_row():
    """A summary row carrying a real multi-axis faithfulness score."""
    r = _exported_rows(1)[0]
    r["memory_representation"] = "summary"
    r["memory_writer_model"] = "gpt-oss-120b"
    r["memory_writer_cluster"] = "metis"
    r["memory_writer_prompt_version"] = "summary_v1@1.0.0"
    r["memory_extraction_latency"] = 1.5
    r["memory_extraction_output_tokens"] = 200
    r["extraction_cost_proxy"] = 200.0
    r["compression_ratio"] = None
    r["source_span_tokens"] = None
    r["faithfulness_check"] = 1.0
    r["faithfulness_notes"] = "SCORED by the deterministic proxy."
    r["faithfulness_detail"] = {
        "rule_version": "deterministic_proxy@1.0.0", "representation": "summary",
        "number_support": 1.0, "entity_support": 0.9,
        "n_numbers": 4, "n_numbers_supported": 4,
        "n_entities": 10, "n_entities_supported": 9,
    }
    # memory_representation and the writer fields are MEMORY_ID_KEYS, so the ids must
    # be re-minted or the row trips id_mismatch -- which is that check working, not a
    # faithfulness problem. Re-mint in dependency order: memory -> cell -> row.
    r["memory_id"] = S.compute_memory_id(r)
    r["cell_id"] = S.compute_cell_id(r)
    r["row_id"] = S.compute_row_id(r)
    return r


def test_the_v01_note_would_now_be_rejected_on_a_written_memory():
    """🔴 THE REGRESSION THIS FILE EXISTS FOR.

    v0.1's migration wrote "NOT SCORED. No faithfulness proxy was run for this
    representation." onto every non-raw row. There were no non-raw rows, so it was
    never false -- and 1,124 arrived carrying real scores (mean number_support 0.9968
    summary / 1.0000 structured). A null beside a reason that is untrue is worse than
    a null with no reason, because the reader has no cue to check it.
    """
    r = _written_row()
    r["faithfulness_check"] = None
    r["faithfulness_detail"] = None
    r["faithfulness_notes"] = ("NOT SCORED. No faithfulness proxy was run for this "
                               "representation.")
    codes = {i.code for i in V.validate_row(r)}
    assert "faithfulness_claimed_unscored_on_a_written_memory" in codes


def test_a_failed_write_is_a_different_fact_from_an_unmeasured_one():
    """3 of 60 structured writes hit the token cap. Their null is a failed write."""
    r = _written_row()
    r["faithfulness_check"] = None
    r["faithfulness_detail"] = None
    r["faithfulness_notes"] = ("NOT SCORED. The write that produced this memory did "
                               "not complete (finish_reason='length').")
    codes = {i.code for i in V.validate_row(r)}
    assert "faithfulness_claimed_unscored_on_a_written_memory" not in codes


def test_raw_still_refuses_both_the_score_and_the_detail():
    """The tautology argument is unchanged for raw; v3 must not have loosened it."""
    r = _exported_rows(1)[0]
    assert r["memory_representation"] == "raw"
    r["faithfulness_detail"] = {"rule_version": "x", "representation": "raw",
                                "number_support": 1.0, "entity_support": 1.0}
    assert "faithfulness_detail_on_raw" in {i.code for i in V.validate_row(r)}


def test_one_axis_is_not_the_score():
    """MEASURED: structured averages number_support 1.0000 and entity_support 0.8322;
    55 of 57 structured memories have number_support==1.0 with entity_support<1.0.
    Shipping the headline float alone would report a clean bill of health."""
    r = _written_row()
    r["faithfulness_detail"] = {"rule_version": "x", "representation": "summary",
                                "number_support": 1.0}
    assert "faithfulness_detail_incomplete" in {i.code for i in V.validate_row(r)}


def test_the_headline_float_must_be_one_of_its_own_axes():
    r = _written_row()
    r["faithfulness_detail"]["number_support"] = 0.5      # check still says 1.0
    assert "faithfulness_check_detail_disagree" in {i.code for i in V.validate_row(r)}


def test_a_score_joined_from_the_wrong_representation_is_caught():
    """memory_id is a content hash and differs across representations by design, so
    the join is on the locator -- and a locator join can still pick the wrong arm."""
    r = _written_row()
    r["faithfulness_detail"]["representation"] = "structured"
    assert "faithfulness_detail_wrong_representation" in {
        i.code for i in V.validate_row(r)}


def test_a_clean_written_row_passes(  ):
    """Negative control: the checks must not reject every scored row."""
    errs = [i for i in V.validate_row(_written_row()) if i.severity == V.SEVERITY_ERROR]
    assert errs == [], errs


def test_faithfulness_detail_quotations_are_redacted_under_a_closed_licence():
    """faithfulness_detail QUOTES SOURCE TEXT in three keys. A field added after the
    licence gate was written is exactly the one the gate cannot see."""
    r = _written_row()
    r["license_source_reference"] = "longmemeval_v1:MIT+sharegpt_upstream"
    r["faithfulness_detail"] = {
        **r["faithfulness_detail"],
        "contradictions": [{"key": "action", "source": ["click('287')"],
                            "memory": ["clicked the link"]}],
        "unsupported_entities": ["http://localhost:9080/f/AskReddit/10224/thread"],
    }
    with pytest.raises(EH.GateFailure):
        EH.gate_license_exclusion([r])                    # un-redacted must fail
    out, withheld = EH.redact_row(r)
    EH.gate_license_exclusion([out])                      # redacted must pass
    assert "faithfulness_detail.quoted_fragments" in withheld
    # and the MEASUREMENT survives -- withholding the whole object would destroy a
    # number over a licence question that only bites on the quotations.
    assert out["faithfulness_detail"]["number_support"] == 1.0
    assert out["faithfulness_detail"]["entity_support"] == 0.9
    assert not out["faithfulness_detail"].get("contradictions")


def test_apache_rows_keep_their_faithfulness_quotations():
    """Negative control: over-redaction would strip every contradiction example in the
    release for a licence reason that does not apply."""
    r = _written_row()
    r["license_source_reference"] = "longmemeval_v2:Apache-2.0"
    r["faithfulness_detail"] = {**r["faithfulness_detail"],
                                "contradictions": [{"key": "a", "source": ["x"]}]}
    out, _ = EH.redact_row(r)
    assert out["faithfulness_detail"]["contradictions"]


def test_schema_version_was_bumped_and_the_old_one_is_still_recognised():
    """A v2 row lacks faithfulness_detail, so presence-is-the-contract means it fails
    v3 validation -- the bump is required. But a v2 artifact must still be NAMEABLE,
    or a reader cannot migrate what they cannot identify."""
    assert S.SCHEMA_VERSION.endswith("_v3")
    assert "faithfulness_detail" in S.FIELD_ORDER
    assert S.SCHEMA_VERSION_V2 in S.KNOWN_SCHEMA_VERSIONS
    assert S.SCHEMA_VERSION_V1 in S.KNOWN_SCHEMA_VERSIONS


# ===================================================== v0.3 (SciCode) / v0.4 (SWE-bench)
# These pin the licence RULINGS in code. Changing a ruling must mean deleting a failing
# test as the receipt, not quietly editing a table.

def _row(**over):
    import export_hf as EH
    return {**EH._synthetic_row(), **over}


def _scicode_row(**over):
    return _row(benchmark="scicode",
                license_source_reference="scicode:Apache-2.0", **over)


def _swebench_row(**over):
    return _row(benchmark="swebench_verified",
                license_source_reference="swebench_verified:none_declared", **over)


def test_scicode_policy_permits_text_both_code_and_data_are_apache2():
    """BENCHMARK_LICENSES.md section 4. The stale PENDING entry over-redacted."""
    import export_hf as EH
    pol = EH.policy_for("scicode:Apache-2.0")
    assert pol.key == "scicode", "policy key must match the prefix converted rows carry"
    assert pol.redistribute_source_text and pol.redistribute_model_output
    out, withheld = EH.redact_row(_scicode_row(memory_text="Fermi energy problem"))
    assert withheld == [], f"SciCode is Apache-2.0 but redaction withheld {withheld}"
    assert out["memory_text"] == "Fermi energy problem"


def test_swebench_policy_is_an_explicit_refusal_not_a_default():
    """An absent entry and a dated refusal are different facts (section 5)."""
    import export_hf as EH
    pol = EH.policy_for("swebench_verified:none_declared")
    assert pol.key == "swebench_verified", "must not fall through to __unknown__"
    assert not pol.redistribute_source_text and not pol.redistribute_model_output
    note = pol.note.lower()
    for token in ("undeclared", "carddata.license", "harness", "section 5"):
        assert token in note, f"the ruling's note must state {token!r}"


def test_swebench_text_is_withheld_and_both_guards_agree():
    import export_hf as EH
    from p1mem import schema as S
    out, withheld = EH.redact_row(_swebench_row(memory_text="django issue body"))
    assert out["memory_text"] == EH.WITHHELD
    assert set(withheld) >= {"memory_text", "future_task_text"}
    EH.gate_license_exclusion([out])      # keyed on license_source_reference
    S.assert_content_redistributable([out])   # keyed independently on `benchmark`


def test_a_redacted_row_still_passes_the_validator_gate4_runs():
    """The v0.4 blocker: memory_text is a MEMORY_ID_KEY, so blanking it broke the id."""
    import export_hf as EH
    from p1mem import validate as V
    out, _ = EH.redact_row(_swebench_row(memory_text="django issue body"))
    rep = V.validate_dataset([out])
    assert rep.ok, [f"{e.code}:{e.field}" for e in rep.errors]


def test_id_mismatch_still_fires_on_a_non_sentinel_edit():
    """POSITIVE CONTROL: the withholding exemption must not swallow real corruption."""
    from p1mem import validate as V
    bad = _row(memory_text="an ordinary edit, not a withholding")
    assert "id_mismatch" in {e.code for e in V.validate_dataset([bad]).errors}


def test_declaring_a_withholding_that_did_not_happen_buys_no_exemption():
    from p1mem import validate as V
    bad = _row(memory_text="real text", text_fields_withheld=["memory_text"],
               reconstruction_required=True)
    assert "id_mismatch" in {e.code for e in V.validate_dataset([bad]).errors}


def test_copied_cell_id_is_caught_even_on_a_withheld_row():
    """The exemption narrows per-id: cell_id keys on memory_id, not memory_text."""
    import export_hf as EH
    from p1mem import validate as V
    out, _ = EH.redact_row(_swebench_row(memory_text="django issue body"))
    out["cell_id"] = "cell-someoneelse-000000000000000000000000"
    assert "id_mismatch" in {e.code for e in V.validate_dataset([out]).errors}


def test_undeclared_withholding_is_rejected_by_the_schema_helper():
    import pytest as _pt
    import export_hf as EH
    from p1mem import schema as S
    out, _ = EH.redact_row(_swebench_row(memory_text="django issue body"))
    out["text_fields_withheld"] = []
    with _pt.raises(ValueError, match="WITHOUT declaring"):
        S.assert_content_redistributable([out])


def test_beam_rows_are_refused_outright_not_merely_redacted():
    """Three docs asserted this control; measured 2026-09-30, it did not exist."""
    import pytest as _pt
    import export_hf as EH
    beam = _row(benchmark="beam", license_source_reference="beam:CC-BY-SA-4.0")
    with _pt.raises(EH.GateFailure, match="refusal"):
        EH.gate_benchmark_refusal([beam])
    # negative control: the gate is not a blanket refusal
    EH.gate_benchmark_refusal([_scicode_row(), _swebench_row(), _row()])


def test_benchmark_and_license_reference_must_name_the_same_source():
    """The measured bypass: 'swebench' (no _verified) matched no embargo entry."""
    import pytest as _pt
    import export_hf as EH
    with _pt.raises(EH.GateFailure, match="GATE 0"):
        EH.gate_benchmark_license_agreement(
            [_row(benchmark="swebench",
                  license_source_reference="swebench_verified:none_declared")])
    # a recognised benchmark pointed at the wrong reference (the prefix comparison)
    with _pt.raises(EH.GateFailure, match="GATE 0"):
        EH.gate_benchmark_license_agreement(
            [_row(benchmark="scicode",
                  license_source_reference="longmemeval_v2:Apache-2.0")])
    EH.gate_benchmark_license_agreement([_scicode_row(), _swebench_row(), _row()])


def test_scicode_eval_targets_are_refused_despite_a_permissive_row_policy():
    """test_data.h5 is outside the Apache-2.0 grant: a per-FIELD carve-out."""
    import pytest as _pt
    import export_hf as EH
    with _pt.raises(EH.GateFailure, match="GATE 3c"):
        EH.gate_scicode_eval_targets([_scicode_row(
            memory_text="expected = [0.4472135954999579, 1.2247448713915890, "
                        "3.1415926535897931]")])
    EH.gate_scicode_eval_targets([_scicode_row(memory_text="Compute the Fermi energy.")])


def test_secret_scan_still_matches_real_django_source():
    """Do not relax assigned_secret to quiet a false positive on real code."""
    import export_hf as EH
    for real in EH.SECRET_SCAN_REAL_SOURCE_MATCHES:
        assert EH.scan_text_for_secrets(real, "t"), (
            f"assigned_secret no longer matches {real!r}; a genuine credential "
            f"assignment would now be invisible too")


def test_a_secret_in_a_withheld_field_is_recorded_but_one_that_ships_fails():
    import pytest as _pt
    import export_hf as EH
    payload = EH.SECRET_SCAN_REAL_SOURCE_MATCHES[0]
    sw = _swebench_row(output_with_memory=payload)
    _, withheld = EH.redact_row(sw)
    notes = EH.gate_secret_scan_rows([sw], withheld_fields=[withheld])
    assert notes, "a match in a withheld field must be recorded, not silently dropped"
    # the same class of string in a field that SHIPS is still a hard failure
    sc = _scicode_row(output_with_memory="api_key=sk-abcdefghijklmnopqrstuvwxyz0123")
    _, sc_withheld = EH.redact_row(sc)
    with _pt.raises(EH.GateFailure):
        EH.gate_secret_scan_rows([sc], withheld_fields=[sc_withheld])

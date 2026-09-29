"""Deliberate-corruption tests for the P1 dataset validator.

The point of this file is NOT to show the validator passing. A validator only ever run on
good data detects nothing known. Each test here takes a known-good row, breaks it in ONE
specific way, and asserts the SPECIFIC issue code that should catch it.

Asserting on the code rather than on "something failed" matters: a check whose verdict is
right for the wrong reason is harder to catch than a wrong verdict.

Two controls guard the harness itself:
  * ``test_control_good_row_passes``    -- the good row must be clean, or every "caught"
                                            below could be the same background error.
  * ``test_control_harness_can_observe`` -- a nonsense corruption must be caught too, so a
                                            green suite cannot mean "the validator rejects
                                            everything".
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem import schema as S
from p1mem import validate as V


# ------------------------------------------------------------------ good row
def _good_row(**over):
    """A row that must validate clean. Matches the pinned Metis arm."""
    base = dict(
        benchmark="longmemeval_v1",
        benchmark_version="xiaowu0162/longmemeval-cleaned@sha256:deadbeef",
        source_episode_id="answer_0f3c11",
        source_episode_metadata={"question_type": "knowledge-update", "date": "2023-05-02"},
        memory_representation="summary",
        memory_semantic_type="semantic_fact",
        memory_text="The user switched from a Pixel 6 to a Pixel 8 in April 2023.",
        memory_tokens=17,
        memory_source_span={"session_id": "answer_0f3c11", "turn_start": 2, "turn_end": 5},
        memory_writer_model="gpt-oss-120b",
        memory_writer_cluster="metis",
        memory_writer_prompt_version="summary_v1",
        memory_extraction_latency=0.84,
        memory_extraction_input_tokens=612,
        memory_extraction_output_tokens=41,
        embedding_model="Salesforce/SFR-Embedding-Mistral",
        embedding_version="sophia@2026-09-29",
        memory_embedding_reference={"store": "emb/mem_000.npy", "index": 0, "dim": 4096,
                                    "sha256": "a" * 64},
        future_task_id="q_2f7b90",
        future_task_family="temporal-reasoning",
        future_task_text="Which phone was the user using in June 2023?",
        task_embedding_reference={"store": "emb/task_000.npy", "index": 0, "dim": 4096,
                                  "sha256": "b" * 64},
        semantic_similarity=0.71,
        semantic_distance_band="NEAR",
        retrieval_method="top_k",
        retrieval_rank=2,
        retrieval_k=5,
        memory_tokens_retrieved=430,
        memory_tokens_exposed=430,
        replicate_id=0,
        seed_or_sampling_config={"temperature": 0, "max_tokens": 512, "seed": 7},
        reader_model="gpt-oss-120b",
        reader_cluster="metis",
        reader_endpoint="metis:/resource_server/metis/api/v1",
        reader_prompt_version="reader_v1",
        reader_reasoning_effort="low",
        output_without_memory="I do not have enough information to say.",
        output_with_memory="A Pixel 8.",
        reward_without_memory=0.0,
        reward_with_memory=1.0,
        robustness_confidence=None,
        write_latency=0.84,
        retrieval_latency=0.11,
        generation_latency=1.92,
        end_to_end_latency=3.04,
        embedding_calls=0,
        generation_calls=2,
        input_tokens=5120,
        output_tokens=96,
        reasoning_tokens=48,
        retry_count=0,
        error_code_if_any=None,
        provenance={"code_sha": "abc1234", "config_sha256": "c" * 64, "run_id": "pilot-001",
                    "host": "local"},
        license_source_reference="longmemeval_v1:MIT+sharegpt_upstream",
        verifier_id="norm_phrase_set_match",
        verifier_version="lmev2_harness@1.0.0",
        reward_is_continuous=False,
        leakage_flag=False,
        condition_id="pilot_metis_summary_topk5",
        reader_endpoint_sha256=S.sanitized_base_url_hash(
            "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1"),
    )
    base.update(over)
    return S.new_row(**base)


def _codes(row):
    return {i.code for i in V.validate_row(row)}


# =========================================================== CONTROLS
def test_control_good_row_passes():
    """If this fails, every 'caught' assertion below is uninterpretable."""
    issues = V.validate_row(_good_row())
    errs = [i for i in issues if i.severity == V.SEVERITY_ERROR]
    assert errs == [], f"the control row is not clean: {[str(e) for e in errs]}"


def test_control_harness_can_observe_a_failure():
    """A nonsense corruption must be caught -- proves the harness is not blind."""
    row = _good_row()
    row["benchmark"] = None
    assert "null_in_non_nullable" in _codes(row)


def test_control_validator_is_not_a_blanket_rejecter():
    """Legal variation must NOT be rejected, or 'caught' means nothing."""
    for variant in (
        _good_row(memory_representation="raw",
                  memory_writer_model="none:deterministic_span",
                  memory_writer_cluster="none:deterministic_span",
                  memory_writer_prompt_version="span_rule_v1",
                  memory_extraction_latency=None,
                  memory_extraction_input_tokens=None,
                  memory_extraction_output_tokens=None,
                  write_latency=None),
        _good_row(retrieval_method="none", retrieval_rank=None, retrieval_k=None,
                  memory_tokens_retrieved=0, memory_tokens_exposed=0,
                  retrieval_latency=None),
        # Sophia failover arm: other model spelling, and no reasoning-token reporting.
        _good_row(reader_cluster="sophia", reader_model="openai/gpt-oss-120b",
                  memory_writer_cluster="sophia",
                  memory_writer_model="openai/gpt-oss-120b",
                  reader_endpoint="sophia:/resource_server/sophia/vllm/v1",
                  reasoning_tokens=None, condition_id="failover_sophia_summary_topk5"),
        # continuous reward, partial credit
        _good_row(reward_with_memory=0.625, reward_without_memory=0.25,
                  reward_is_continuous=True, verifier_id="partial_credit"),
        # an errored cell: no outputs, no rewards, an error code
        _good_row(output_with_memory=None, output_without_memory=None,
                  reward_with_memory=None, reward_without_memory=None,
                  error_code_if_any=S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH),
    ):
        errs = [i for i in V.validate_row(variant) if i.severity == V.SEVERITY_ERROR]
        assert errs == [], f"legal variant rejected: {[str(e) for e in errs]}"


# ============================================ THE DELIBERATE CORRUPTIONS
# 1 -------------------------------------------------------------------
def test_corruption_01_output_replaced_by_digest():
    """Design req 1: a hash instead of the text blocks every later re-scoring."""
    row = _good_row()
    row["output_with_memory"] = S.sha256_text(row["output_with_memory"])
    assert "output_is_digest" in _codes(row)


def test_corruption_01b_digest_detector_does_not_eat_real_text():
    """The digest check must not fire on an answer that merely MENTIONS a hash."""
    row = _good_row(output_with_memory=f"The commit is {'a'*64}, which fixes it.")
    assert "output_is_digest" not in _codes(row)


# 2 -------------------------------------------------------------------
def test_corruption_02_delta_does_not_match_its_components():
    row = _good_row()
    row["delta_utility"] = 0.5          # true value is 1.0
    assert "delta_mismatch" in _codes(row)


def test_corruption_02b_delta_tolerance_accepts_float_noise():
    row = _good_row()
    row["delta_utility"] = row["delta_utility"] + 1e-12
    assert "delta_mismatch" not in _codes(row)


# 3 -------------------------------------------------------------------
def test_corruption_03_cluster_identity_blanked():
    """Design req 3: cluster is never optional."""
    for f in ("reader_cluster", "memory_writer_cluster"):
        row = _good_row()
        row[f] = ""
        assert "identity_field_empty" in _codes(row), f
        row[f] = None
        assert _codes(row) & {"identity_field_empty", "null_in_non_nullable"}, f


# 4 -------------------------------------------------------------------
def test_corruption_04_p3_field_populated_in_p1():
    row = _good_row()
    row["receiver_id"] = "receiver_3"
    assert "p3_field_populated" in _codes(row)


# 5 -------------------------------------------------------------------
def test_corruption_05_bad_enum_value():
    row = _good_row()
    row["memory_representation"] = "paraphrase"
    assert "bad_enum" in _codes(row)
    row = _good_row()
    row["semantic_distance_band"] = "near"       # case matters
    assert "bad_enum" in _codes(row)


# 6 -------------------------------------------------------------------
def test_corruption_06_wrong_type():
    row = _good_row()
    row["memory_tokens"] = "17"
    assert "wrong_type" in _codes(row)
    row = _good_row()
    row["reward_with_memory"] = True             # bool is not a float here
    assert "wrong_type" in _codes(row)


# 7 -------------------------------------------------------------------
def test_corruption_07_missing_field_entirely():
    row = _good_row()
    del row["semantic_similarity"]
    assert "missing_field" in _codes(row)


# 8 -------------------------------------------------------------------
def test_corruption_08_empty_output_scored_as_zero_reward():
    """The manufactured-harmful-memory trap.

    finish_reason='length' with content=null must be an ERROR. Scored as 0.0 it drives
    delta_utility negative and invents a harmful memory.
    """
    row = _good_row()
    row["output_with_memory"] = ""
    row["reward_with_memory"] = 0.0
    row["delta_utility"] = 0.0 - row["reward_without_memory"]
    assert "scored_empty_output" in _codes(row)

    row = _good_row()
    row["output_with_memory"] = None
    row["reward_with_memory"] = 0.0
    row["delta_utility"] = 0.0 - row["reward_without_memory"]
    assert "scored_empty_output" in _codes(row)


def test_corruption_08b_empty_output_with_no_error_code():
    row = _good_row()
    row["output_without_memory"] = ""
    row["reward_without_memory"] = None
    row["reward_with_memory"] = None
    row["delta_utility"] = None
    assert "empty_output_no_error" in _codes(row)


def test_corruption_08c_errored_row_carrying_a_reward():
    row = _good_row()
    row["error_code_if_any"] = S.ERROR_EMPTY_OUTPUT_FINISH_LENGTH
    assert "reward_on_errored_row" in _codes(row)


# 9 -------------------------------------------------------------------
def test_corruption_09_absent_reasoning_tokens_written_as_zero():
    """Sophia does not report reasoning tokens. 0 there is an absence, not a measurement."""
    row = _good_row(reader_cluster="sophia", reader_model="openai/gpt-oss-120b",
                    memory_writer_cluster="sophia",
                    memory_writer_model="openai/gpt-oss-120b",
                    reader_endpoint="sophia:/resource_server/sophia/vllm/v1")
    row["reasoning_tokens"] = 0
    assert "absent_reported_as_zero" in _codes(row)


def test_corruption_09b_null_is_accepted_where_absence_is_real():
    row = _good_row(reader_cluster="sophia", reader_model="openai/gpt-oss-120b",
                    memory_writer_cluster="sophia",
                    memory_writer_model="openai/gpt-oss-120b",
                    reader_endpoint="sophia:/resource_server/sophia/vllm/v1",
                    reasoning_tokens=None)
    errs = [i for i in V.validate_row(row) if i.severity == V.SEVERITY_ERROR]
    assert errs == []


# 10 ------------------------------------------------------------------
def test_corruption_10_cross_cluster_model_name_normalized():
    """The naming asymmetry is real; merging it merges two arms."""
    row = _good_row()
    row["reader_model"] = "openai/gpt-oss-120b"   # Sophia's spelling on a Metis row
    assert "cross_cluster_model_naming" in _codes(row)


# 11 ------------------------------------------------------------------
def test_corruption_11_id_copied_from_another_row():
    row = _good_row()
    row["row_id"] = _good_row(replicate_id=3)["row_id"]
    assert "id_mismatch" in _codes(row)


def test_corruption_11b_content_edited_after_id_was_minted():
    row = _good_row()
    row["memory_text"] = row["memory_text"] + " (edited)"
    assert "id_mismatch" in _codes(row)


# 12 ------------------------------------------------------------------
def test_corruption_12_endpoint_carries_a_credential():
    for bad in (
        "https://user:hunter2@inference-api.alcf.anl.gov/resource_server/metis/api/v1",
        "https://inference-api.alcf.anl.gov/v1?api_key=sk-abc123",
        "https://inference-api.alcf.anl.gov/v1#token=abc",
    ):
        row = _good_row()
        row["reader_endpoint"] = bad
        assert "endpoint_may_carry_credential" in _codes(row), bad


# 13 ------------------------------------------------------------------
def test_corruption_13_label_hand_set_and_not_recomputable():
    """Design req 2: the label must follow from the row's own stored statistics."""
    row = _good_row()
    row["utility_label"] = "robust_useful"        # F is null -> rule gives 'undetermined'
    codes = _codes(row)
    assert "label_not_recomputable" in codes
    assert "label_without_floor" in codes


def test_corruption_13b_label_inside_the_floor_is_not_useful():
    """Statistically nonzero but inside the noise floor is NEUTRAL (prereg section 4)."""
    row = _good_row(delta_utility_ci_lower=0.02, delta_utility_ci_upper=0.08,
                    delta_utility_cell_mean=0.05, utility_label_threshold=0.20,
                    replicate_count=3)
    assert row["utility_label"] == "neutral"
    row["utility_label"] = "robust_useful"
    assert "label_not_recomputable" in _codes(row)


def test_corruption_13c_label_recomputes_when_the_floor_exists():
    row = _good_row(delta_utility_ci_lower=0.30, delta_utility_ci_upper=0.90,
                    delta_utility_cell_mean=0.60, utility_label_threshold=0.10,
                    replicate_count=5)
    assert row["utility_label"] == "robust_useful"
    assert "label_not_recomputable" not in _codes(row)


# 14 ------------------------------------------------------------------
def test_corruption_14_retrieval_bookkeeping_impossible():
    row = _good_row()
    row["memory_tokens_exposed"] = row["memory_tokens_retrieved"] + 1
    assert "exposed_exceeds_retrieved" in _codes(row)

    row = _good_row(retrieval_method="none", retrieval_rank=None, retrieval_k=None,
                    retrieval_latency=None)
    row["memory_tokens_exposed"] = 300
    assert "tokens_exposed_without_retrieval" in _codes(row)


def test_corruption_14b_negative_counter():
    row = _good_row()
    row["input_tokens"] = -1
    assert "negative_quantity" in _codes(row)


# 15 ------------------------------------------------------------------
def test_corruption_15_unknown_field_smuggled_in():
    row = _good_row()
    row["reward_hash"] = "deadbeef"
    assert "unknown_field" in _codes(row)


def test_corruption_15b_new_row_rejects_unknown_kwargs():
    with pytest.raises(KeyError):
        S.new_row(benchmark="x", not_a_field=1)


# ===================================================== DATASET-LEVEL
def test_dataset_01_cluster_varies_inside_one_condition():
    """E2's named requirement."""
    a = _good_row()
    b = _good_row(replicate_id=1, reader_cluster="sophia",
                  reader_model="openai/gpt-oss-120b",
                  reader_endpoint="sophia:/resource_server/sophia/vllm/v1",
                  reasoning_tokens=None)
    rep = V.validate_dataset([a, b])
    assert "cluster_heterogeneous_condition" in rep.codes()


def test_dataset_01b_same_cluster_is_not_flagged():
    rep = V.validate_dataset([_good_row(), _good_row(replicate_id=1)])
    assert "cluster_heterogeneous_condition" not in rep.codes()


def test_dataset_01c_check_fires_without_a_declared_condition_id():
    """It must work off the implicit condition tuple too, or the writer can evade it."""
    a = _good_row(condition_id=None)
    b = _good_row(condition_id=None, replicate_id=1, reader_cluster="sophia",
                  reader_model="openai/gpt-oss-120b",
                  reader_endpoint="sophia:/resource_server/sophia/vllm/v1",
                  reasoning_tokens=None)
    # condition_id is NOT-NULL so both rows also raise null_in_non_nullable -- the point
    # is that the heterogeneity check still fires rather than silently splitting.
    rep = V.validate_dataset([a, b])
    assert "cluster_heterogeneous_condition" in rep.codes()


def test_dataset_02_writer_cluster_varies_inside_one_condition():
    a = _good_row()
    b = _good_row(replicate_id=1, memory_writer_cluster="sophia",
                  memory_writer_model="openai/gpt-oss-120b")
    rep = V.validate_dataset([a, b])
    assert "writer_cluster_heterogeneous_condition" in rep.codes()


def test_dataset_03_verifier_drift_inside_one_condition():
    """This defect class already invalidated a table on a sibling project."""
    a = _good_row()
    b = _good_row(replicate_id=1, verifier_version="lmev2_harness@1.1.0")
    rep = V.validate_dataset([a, b])
    assert "verifier_drift_in_condition" in rep.codes()


def test_dataset_04_duplicate_row_id():
    a = _good_row()
    rep = V.validate_dataset([a, copy.deepcopy(a)])
    assert "duplicate_row_id" in rep.codes()


def test_dataset_05_replicates_disagree_on_something_that_is_not_sampling():
    a = _good_row()
    b = _good_row(replicate_id=1)
    b["future_task_text"] = "A different question entirely."
    b["cell_id"] = a["cell_id"]          # force them into one cell
    rep = V.validate_dataset([a, b])
    assert "cell_inconsistent_across_replicates" in rep.codes()


def test_dataset_06_continuous_flag_but_binary_values():
    rows = [_good_row(replicate_id=i, reward_is_continuous=True) for i in range(25)]
    rep = V.validate_dataset(rows)
    assert "continuous_reward_is_binary" in rep.codes()


def test_dataset_07_all_undetermined_is_surfaced_not_hidden():
    rep = V.validate_dataset([_good_row(), _good_row(replicate_id=1)])
    assert "all_labels_undetermined" in rep.codes()
    assert rep.ok, "unmeasured floor is a warning, not an error"


# ===================================================== ROUND TRIP / IO
def test_append_only_jsonl_roundtrip_and_validate():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ledger.jsonl"
        S.append_jsonl_atomic(p, [_good_row()])
        S.append_jsonl_atomic(p, [_good_row(replicate_id=1)])
        rows = S.load_jsonl(p)
        assert len(rows) == 2
        rep = V.validate_dataset(rows)
        assert rep.ok, rep.summary()


def test_ids_are_deterministic_across_processes():
    """A hash that depends on PYTHONHASHSEED would break cross-run cell identity."""
    row = _good_row()
    code = (
        "import sys; sys.path.insert(0,%r);"
        "from p1mem import schema as S; import json;"
        "print(S.compute_row_id(json.loads(sys.stdin.read())))"
        % str(Path(__file__).resolve().parents[1] / "src")
    )
    env = dict(os.environ, PYTHONHASHSEED="12345")
    out = subprocess.run([sys.executable, "-c", code], input=json.dumps(row),
                         capture_output=True, text=True, env=env, check=True)
    assert out.stdout.strip() == row["row_id"]


def test_p3_fields_are_forced_null_even_if_a_caller_passes_them():
    row = _good_row(receiver_id="r1", team_reward=0.5)
    assert row["receiver_id"] is None and row["team_reward"] is None


# ====================================== EXHAUSTIVE BLIND-SPOT SWEEP
# The corruption tests above are cases I thought of. Controls drawn only from failures you
# imagined close the instances, not the defect class. These sweep EVERY field.
def test_sweep_every_non_nullable_field_is_actually_guarded():
    blind = []
    for f, spec in S.FIELD_SPEC.items():
        if spec["nullable"]:
            continue
        row = _good_row()
        row[f] = None
        if not [i for i in V.validate_row(row) if i.severity == V.SEVERITY_ERROR]:
            blind.append(f)
    assert blind == [], f"nulling these NOT-NULL fields raises nothing: {blind}"


def test_sweep_every_typed_field_rejects_a_wrong_type():
    blind = []
    for f, spec in S.FIELD_SPEC.items():
        if spec["kind"] == "any":
            continue
        row = _good_row()
        row[f] = "not-an-object" if spec["kind"] == "obj" else {"x": 1}
        if not [i for i in V.validate_row(row) if i.severity == V.SEVERITY_ERROR]:
            blind.append(f)
    assert blind == [], f"a wrong type in these fields raises nothing: {blind}"


def test_sweep_validator_never_raises_on_a_corrupt_row():
    """A validator that crashes turns one bad row into a dead run and hides the rest."""
    for f, spec in S.FIELD_SPEC.items():
        for bad in (None, {"x": 1}, "not-an-object", -1, [], True, float("nan")):
            row = _good_row()
            row[f] = bad
            try:
                V.validate_row(row)
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"validator raised on {f}={bad!r}: {exc!r}")
    V.validate_dataset([_good_row(), {"junk": 1}, "not a row", None])


# ===================================================== WRITER (P1-043)
def test_writer_refuses_a_malformed_row_and_writes_nothing():
    from p1mem.writer import CellWriter, RowRejected
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cells.jsonl"
        w = CellWriter(p)
        bad = _good_row(); bad["reader_cluster"] = ""
        with pytest.raises(RowRejected):
            w.write_row(bad)
        assert not p.exists(), "a rejected row must not create or touch the ledger"
        w.write_row(_good_row())
        assert len(S.load_jsonl(p)) == 1


def test_writer_quarantines_instead_of_dying_when_not_strict():
    from p1mem.writer import CellWriter
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cells.jsonl"
        w = CellWriter(p, strict=False)
        bad = _good_row(); bad["reader_cluster"] = ""
        assert w.write_row(bad) is None
        assert w.write_row(_good_row()) is not None
        assert len(S.load_jsonl(p)) == 1
        q = S.load_jsonl(w.rejected_path)
        assert len(q) == 1 and q[0]["issues"][0]["code"] == "identity_field_empty"

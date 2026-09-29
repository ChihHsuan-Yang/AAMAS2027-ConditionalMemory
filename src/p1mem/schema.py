"""Canonical row schema for the **Conditional Memory Utility Dataset** (P1, AAMAS 2027).

One row = one evaluated cell:

    DeltaU(m, t, s) = Reward(t | memory m available) - Reward(t | m absent)

for a single memory ``m``, a single *future* task ``t``, and a single replicate ``s``.
Both arms of the contrast live in the SAME row, so a WITH score can never drift away
from the WITHOUT score it is differenced against.

This module is the single source of truth for the on-disk contract. Everything
downstream -- the writer, the validator, the exporter, and the data card -- reads
``FIELD_SPEC`` from here rather than restating field names.

Design requirements, each enforced in code (see the named guard):

1. **Full output text, never a digest.** ``output_with_memory`` / ``output_without_memory``
   hold the model's complete response. A hash blocks every later re-scoring under a
   corrected verifier, which has already cost this project a table.
   Guard: ``looks_like_bare_digest`` + ``validate.py::_check_outputs_are_text``.
2. **Continuous rewards.** ``reward_*`` are floats, never coerced to {0, 1}. A benchmark
   that gives partial credit must be allowed to express it. ``utility_label`` is DERIVED
   and must be recomputable from the raw rewards -- which is why the threshold and rule
   version that produced it are stored alongside it.
   Guard: ``derive_utility_label`` + ``validate.py::_check_label_recomputable``.
3. **Cluster is experimental identity.** ``reader_cluster`` and ``memory_writer_cluster``
   are NEVER optional and never nullable. Two generations from different ALCF clusters
   are different experimental conditions and must not pool by accident.
   Guard: ``NON_NULLABLE_IDENTITY`` + ``validate.py::_check_cluster_homogeneity``.
4. **Deterministic ids.** Content hash + episode id, via ``canonical_json`` / ``sha256_text``.
5. **Atomic, append-only JSONL.** ``append_jsonl_atomic`` writes one whole line under an
   exclusive advisory lock; ``write_jsonl_atomic`` rewrites via tmp + ``os.replace``.

----------------------------------------------------------------------------------
``canonical_json``, ``sha256_text``, ``file_sha256``, ``sanitized_base_url_hash``,
``write_json_atomic``, ``write_jsonl_atomic``, ``load_jsonl`` and ``utc_now`` below are
COPIED (with minor edits) from a sibling project, deliberately rather than imported,
so that the two repos can never drift each other's on-disk contracts:

    /Users/bellayang/Documents/2026/iclr_receiver_conditional_communication/
        agentverse/metrics/receiver_conditional_communication/schema.py

Original author: the ICLR receiver-conditional-communication milestone. Reused here
with attribution per the P1 cross-repo rule (copy in, do not import across repos).
----------------------------------------------------------------------------------
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # POSIX only; used for append-only locking. Absent on Windows.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

# Bumped whenever the row contract changes in a way that invalidates written rows.
SCHEMA_VERSION = "p1mem_conditional_memory_utility_v1"

# Version of the rule that maps replicate rewards -> utility_label. Stored per row so a
# relabelled dataset is distinguishable from the original. The rule itself is
# docs/ANALYSIS_PREREGISTRATION.md section 4, fixed before any data existed.
UTILITY_LABEL_RULE_VERSION = "prereg_v1_ci_and_floor"

# Canonical operational error codes. A reasoning model can spend its whole max_tokens
# budget on reasoning and return content=null with finish_reason="length". That is an
# ERROR, never a scored outcome: scoring it would read as a wrong answer, drive
# delta_utility negative, and MANUFACTURE a harmful memory. See docs/CLUSTER_DECISION.md.
ERROR_EMPTY_OUTPUT_FINISH_LENGTH = "empty_output_finish_length"
ERROR_CODES: tuple[str, ...] = (
    ERROR_EMPTY_OUTPUT_FINISH_LENGTH,
    "empty_output_other",
    "http_error",
    "timeout",
    "refusal",
    "parse_failure",
    "endpoint_unavailable",
)

# docs/CLUSTER_DECISION.md: the SAME logical model is named differently per cluster, and
# the naming asymmetry is REAL. A client or validator that "helpfully" normalizes these
# together would merge two experimental arms. This table is used to DETECT normalization,
# never to perform it.
CLUSTER_MODEL_NAMING: dict[str, tuple[str, ...]] = {
    "metis": ("gpt-oss-120b",),
    "sophia": ("openai/gpt-oss-120b", "Salesforce/SFR-Embedding-Mistral"),
}

# Float tolerance for delta_utility == reward_with - reward_without.
DELTA_TOLERANCE = 1e-9


# --------------------------------------------------------------------- time
def utc_now() -> str:
    """ISO-8601 UTC timestamp. [copied: sibling schema.py]"""
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------- hashing
# [copied: sibling schema.py] -- see module docstring for provenance.
def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitized_base_url_hash(base_url: str | None) -> str:
    """Stable fingerprint of an endpoint URL.

    Stored INSTEAD OF a raw URL that might carry an embedded credential. Never store
    the raw URL or any token alongside this. [copied: sibling schema.py]
    """
    return hashlib.sha256(str(base_url or "").encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------- atomic I/O
def write_json_atomic(path: str | Path, payload: Any) -> None:
    """[copied: sibling schema.py]"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def write_jsonl_atomic(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    """Whole-file rewrite via tmp + rename. [copied: sibling schema.py]

    Use for snapshots/exports. For accumulating results use ``append_jsonl_atomic``,
    which never rewrites and therefore cannot truncate existing rows on a crash.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
    os.replace(tmp, path)


def append_jsonl_atomic(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    """Append-only, crash-safe writer. Returns the number of rows appended.

    Each row is serialized to a complete single line and the whole buffer is handed to
    one ``os.write`` under an exclusive ``flock``. Concurrent writers therefore never
    interleave a partial line, and an interrupted process can only lose whole rows it
    had not yet handed to the kernel -- it can never corrupt a row already on disk.

    Rows are NEVER rewritten or deleted: a correction is a new row with a new
    ``row_id``, not an edit. That is what makes the ledger auditable.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows
    )
    if not payload:
        return 0
    n = payload.count("\n")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        data = payload.encode("utf-8")
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover
                pass
        os.close(fd)
    return n


def load_jsonl(path: str | Path, *, strict: bool = True) -> list[dict[str, Any]]:
    """[copied: sibling schema.py]"""
    rows: list[dict[str, Any]] = []
    with open(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError(f"Malformed JSON at {path}:{line_number}: {exc}") from exc
                continue
            if not isinstance(row, dict):
                if strict:
                    raise ValueError(f"Non-object JSON at {path}:{line_number}")
                continue
            rows.append(row)
    return rows


# =====================================================================  ENUMS
MEMORY_REPRESENTATIONS: tuple[str, ...] = ("raw", "summary", "structured")

MEMORY_SEMANTIC_TYPES: tuple[str, ...] = (
    "episodic",
    "semantic_fact",
    "procedural",
    "failure_reflection",
)

SEMANTIC_DISTANCE_BANDS: tuple[str, ...] = ("NEAR", "MID", "FAR")

# Retrieval arms from MASTER_TODO P1-010.
RETRIEVAL_METHODS: tuple[str, ...] = ("none", "keep_all", "top_k", "oracle")

# Derived label, exactly as fixed in docs/ANALYSIS_PREREGISTRATION.md section 4.
# It is a CELL-level property (over the cell's replicates), carried on every row of the
# cell so a single row is self-describing.
#   robust_useful : CI_lower > 0  AND  mean dU >  F
#   robust_harmful: CI_upper < 0  AND |mean dU| >  F
#   neutral       : CI contains 0  OR  |mean dU| <= F
#   undetermined  : a reward is missing, the cell errored, or F is not yet measured
UTILITY_LABELS: tuple[str, ...] = (
    "robust_useful",
    "robust_harmful",
    "neutral",
    "undetermined",
)

ENUMS: dict[str, tuple[str, ...]] = {
    "memory_representation": MEMORY_REPRESENTATIONS,
    "memory_semantic_type": MEMORY_SEMANTIC_TYPES,
    "semantic_distance_band": SEMANTIC_DISTANCE_BANDS,
    "retrieval_method": RETRIEVAL_METHODS,
    "utility_label": UTILITY_LABELS,
}


# ===============================================================  FIELD SPEC
# The authoritative field list. ``group`` mirrors the brief's required groups.
# ``kind`` is a coarse type tag checked by validate.py.
# ``req`` True  = named in the brief's required list (the Master Agent checks these).
# ``req`` False = ADDED by E; every added field has a stated reason and a named
#                 populator, per "do not invent fields no one can populate".
#
# (name, group, kind, nullable, req, description)
_SPEC: tuple[tuple[str, str, str, bool, bool, str], ...] = (
    # ---------------------------------------------------------------- structural (ADDED)
    ("schema_version", "structural", "str", False, False,
     "ADDED (populator: writer). Row contract version; without it a re-read cannot tell "
     "which contract a row was written under."),
    ("row_id", "structural", "str", False, False,
     "ADDED (populator: compute_row_id). Deterministic content hash of the identity "
     "fields; required by design requirement 4 (deterministic ids)."),
    ("cell_id", "structural", "str", False, False,
     "ADDED (populator: compute_cell_id). Deterministic id of the (memory, task, "
     "condition) cell, shared across replicates -- the key replicates aggregate over."),
    ("condition_id", "structural", "str", False, False,
     "ADDED (populator: writer/config). The declared experimental condition a row belongs "
     "to. Required by E2: 'reader_cluster differs within one condition' has no meaning "
     "without a condition key. If the writer leaves it null the validator falls back to "
     "the implicit condition tuple (see IMPLICIT_CONDITION_KEYS)."),
    ("created_at_utc", "structural", "str", False, False,
     "ADDED (populator: writer). ISO-8601 UTC write time."),
    # ---------------------------------------------------------------- benchmark
    ("benchmark", "benchmark", "str", False, True,
     "Benchmark family, e.g. 'longmemeval_v1', 'longmemeval_v2', 'beam', 'scicode'."),
    ("benchmark_version", "benchmark", "str", False, True,
     "Exact release/revision of that benchmark (HF revision sha, tag, or file sha256)."),
    ("source_episode_id", "benchmark", "str", False, True,
     "Id of the PAST episode the memory was written during (e.g. a LongMemEval "
     "answer_session_id). The memory's origin, never the future task."),
    ("source_episode_metadata", "benchmark", "obj", True, True,
     "Free-form dict of benchmark-native metadata for that episode (dates, question_type, "
     "session index, ...). Nullable: some benchmarks carry none."),
    # ---------------------------------------------------------------- memory
    ("memory_id", "memory", "str", False, True,
     "Deterministic id of the memory item: content hash + source episode id. Stable "
     "across runs, so the same memory in two runs is provably the same memory."),
    ("memory_representation", "memory", "str", False, True,
     "One of raw|summary|structured. HOW the memory is written down."),
    ("memory_semantic_type", "memory", "str", False, True,
     "One of episodic|semantic_fact|procedural|failure_reflection. WHAT the memory is "
     "about. Deliberately orthogonal to memory_representation (MASTER_TODO P1-006)."),
    ("memory_text", "memory", "str", False, True,
     "The FULL rendered memory text exactly as it is placed in the reader's context. "
     "Never a digest, never truncated."),
    ("memory_tokens", "memory", "int", False, True,
     "Token count of memory_text under the reader's tokenizer."),
    ("memory_source_span", "memory", "obj", True, True,
     "Where in the source episode the memory came from: e.g. "
     "{'session_id':..., 'turn_start':i, 'turn_end':j, 'char_start':a, 'char_end':b}. "
     "Nullable ONLY for representations with no contiguous span (structured)."),
    ("memory_writer_model", "memory", "str", False, True,
     "Model that produced the memory. For raw extraction this is the literal string "
     "'none:deterministic_span' -- raw has no writer model but the field is not optional."),
    ("memory_writer_cluster", "memory", "str", False, True,
     "ALCF cluster the writer ran on. EXPERIMENTAL IDENTITY -- never null. For raw, "
     "'none:deterministic_span'."),
    ("memory_writer_prompt_version", "memory", "str", False, True,
     "Version tag of the extraction prompt. For raw, the deterministic span-rule version."),
    ("memory_extraction_latency", "memory", "float", True, True,
     "Wall-clock seconds to write the memory. Null for raw (no call made) -- null means "
     "'no call', which is NOT the same as 0.0."),
    ("memory_extraction_input_tokens", "memory", "int", True, True,
     "Prompt tokens billed to the extraction call. Null for raw (no call)."),
    ("memory_extraction_output_tokens", "memory", "int", True, True,
     "Completion tokens billed to the extraction call. Null for raw (no call)."),
    # ---------------------------------------------------------------- embedding
    ("embedding_model", "embedding", "str", False, True,
     "Embedding model id. Frozen for P1: Salesforce/SFR-Embedding-Mistral (P1-033)."),
    ("embedding_version", "embedding", "str", False, True,
     "Revision/serving fingerprint of that embedding model."),
    ("memory_embedding_reference", "embedding", "obj", False, True,
     "REFERENCE to the stored vector, not the vector: "
     "{'store': relpath, 'index': int, 'dim': int, 'sha256': hex}. Vectors live in a "
     "side .npy so the JSONL stays greppable and diffable."),
    # ---------------------------------------------------------------- task
    ("future_task_id", "task", "str", False, True,
     "Id of the LATER task the memory is evaluated against. Must differ from the memory's "
     "own source episode for a genuine cross-task cell; same-episode cells are allowed "
     "but must be identifiable (source_episode_id appears in the task's own provenance)."),
    ("future_task_family", "task", "str", False, True,
     "Benchmark-native task family/type, e.g. 'knowledge-update', 'temporal-reasoning'."),
    ("future_task_text", "task", "str", False, True,
     "FULL task/question text as presented to the reader."),
    ("task_embedding_reference", "task", "obj", False, True,
     "Same reference shape as memory_embedding_reference."),
    ("semantic_similarity", "task", "float", False, True,
     "Cosine similarity between the memory embedding and the task embedding, under "
     "embedding_model. The continuous quantity; the band below is its discretization."),
    ("semantic_distance_band", "task", "str", False, True,
     "NEAR|MID|FAR. Discretized from semantic_similarity by a pre-registered rule."),
    # ---------------------------------------------------------------- retrieval
    ("retrieval_method", "retrieval", "str", False, True,
     "none|keep_all|top_k|oracle (P1-010)."),
    ("retrieval_rank", "retrieval", "int", True, True,
     "1-based rank at which THIS memory was retrieved. Null when the method does not "
     "rank (keep_all, oracle, none)."),
    ("retrieval_k", "retrieval", "int", True, True,
     "k for top_k. Null for methods with no k."),
    ("memory_tokens_retrieved", "retrieval", "int", False, True,
     "Total tokens across ALL memories the retriever returned for this cell."),
    ("memory_tokens_exposed", "retrieval", "int", False, True,
     "Tokens that actually reached the reader's context after budget truncation. "
     "Deliberately distinct from _retrieved: the gap is the truncation loss and is one of "
     "the efficiency metrics (P1-067..073)."),
    # ---------------------------------------------------------------- execution
    ("replicate_id", "execution", "int", False, True,
     "0-based replicate index within the cell. Replicates differ ONLY in sampling."),
    ("seed_or_sampling_config", "execution", "obj", False, True,
     "The decoding config actually forwarded to the API: "
     "{'seed':..., 'temperature':..., 'top_p':..., 'max_tokens':...}. Stored as what was "
     "sent, not what was requested."),
    ("reader_model", "execution", "str", False, True,
     "Model that answered the future task. Same in both arms of the row, by construction."),
    ("reader_cluster", "execution", "str", False, True,
     "ALCF cluster the reader ran on. EXPERIMENTAL IDENTITY -- never null."),
    ("reader_endpoint", "execution", "str", False, True,
     "Non-secret endpoint ALIAS or credential-free base path, e.g. "
     "'sophia:/resource_server/sophia/vllm/v1'. A URL with credentials, a query string, "
     "or userinfo is REJECTED by the validator; the hashed form lives in "
     "reader_endpoint_sha256."),
    ("reader_prompt_version", "execution", "str", False, True,
     "Version tag of the reader prompt scaffold. Identical across both arms."),
    ("reader_reasoning_effort", "execution", "str", False, False,
     "ADDED at Master Agent request (populator: client, from the pinned config). "
     "reasoning_effort actually sent, e.g. 'low' (pinned, docs/CLUSTER_DECISION.md). "
     "EXPERIMENTAL IDENTITY and cost driver in one: reasoning tokens are drawn from the "
     "SAME max_tokens budget as the answer, so effort changes both what the model can say "
     "and what the cell costs. Never null; a model with no effort control records "
     "'none:not_applicable'."),
    # ---------------------------------------------------------------- outcome
    ("output_without_memory", "outcome", "str", True, True,
     "FULL reader output text for the WITHOUT arm. Never a digest (design req 1). "
     "Nullable ONLY when error_code_if_any is set -- i.e. no output exists."),
    ("output_with_memory", "outcome", "str", True, True,
     "FULL reader output text for the WITH arm. Never a digest. Same null rule."),
    ("reward_without_memory", "outcome", "float", True, True,
     "CONTINUOUS reward for the WITHOUT arm. Never coerced to {0,1}; a binary benchmark "
     "simply yields 0.0/1.0 floats. Null only on error."),
    ("reward_with_memory", "outcome", "float", True, True,
     "CONTINUOUS reward for the WITH arm. Null only on error."),
    ("delta_utility", "outcome", "float", True, True,
     "reward_with_memory - reward_without_memory. Stored redundantly AND checked against "
     "the components by the validator, so a corrupted arm cannot hide in a plausible delta."),
    ("utility_label", "outcome", "str", False, True,
     "DERIVED: useful|harmful|neutral|undetermined. Recomputable from the raw rewards "
     "plus utility_label_threshold (design req 2)."),
    ("robustness_confidence", "outcome", "float", True, True,
     "Per-cell confidence that the sign of delta_utility is real, in [0,1], computed from "
     "the replicates of this cell against the measured noise floor. Null until the noise "
     "floor (P1-051) exists -- and it does not yet."),
    # ---------------------------------------------------------------- cost
    ("write_latency", "cost", "float", True, True,
     "Seconds to write the memory (mirrors memory_extraction_latency at cell scope; null "
     "for raw)."),
    ("retrieval_latency", "cost", "float", True, True,
     "Seconds spent in retrieval. Null when retrieval_method == 'none'."),
    ("generation_latency", "cost", "float", False, True,
     "Seconds of reader generation, BOTH arms summed."),
    ("end_to_end_latency", "cost", "float", False, True,
     "Wall-clock seconds for the whole cell."),
    ("embedding_calls", "cost", "int", False, True,
     "Embedding API calls charged to this cell (0 when vectors were cached)."),
    ("generation_calls", "cost", "int", False, True,
     "Reader generation calls for this cell, both arms, retries included."),
    ("input_tokens", "cost", "int", False, True,
     "Prompt tokens billed across both arms."),
    ("output_tokens", "cost", "int", False, True,
     "Completion tokens billed across both arms."),
    ("reasoning_tokens", "cost", "int", True, False,
     "ADDED at Master Agent request (populator: client, from "
     "completion_tokens_details.reasoning_tokens). Reasoning tokens consumed, both arms. "
     "NULL MEANS 'NOT REPORTED BY THIS CLUSTER', NOT ZERO -- Metis reports it, Sophia "
     "omits completion_tokens_details entirely (docs/CLUSTER_DECISION.md). Conflating "
     "absent with zero has burned this project before; the validator rejects 0 on a "
     "cluster known not to report, and any aggregate must exclude nulls from the "
     "denominator rather than summing them as zeros."),
    ("retry_count", "cost", "int", False, True,
     "Retries performed. 0 is a measurement; it is never a stand-in for 'unknown'."),
    ("error_code_if_any", "cost", "str", True, True,
     "Operational error code from ERROR_CODES, or null on success. A row with an error "
     "code keeps its partial measurements rather than being deleted -- but it must NOT "
     "carry rewards: an errored cell has no outcome, and scoring one would fabricate a "
     "result. In particular 'empty_output_finish_length' (content=null with "
     "finish_reason='length') is an ERROR, never a wrong answer."),
    # ---------------------------------------------------------------- provenance
    ("provenance", "provenance", "obj", False, True,
     "How this row was produced: {'code_sha':..., 'config_sha256':..., 'run_id':..., "
     "'host':..., 'writer':...}. The audit trail back to a commit."),
    ("license_source_reference", "provenance", "str", False, True,
     "Pointer into docs/BENCHMARK_LICENSES.md naming the terms this row's SOURCE content "
     "falls under, e.g. 'longmemeval_v1:MIT+sharegpt_upstream'. Drives the exporter's "
     "redistribution decision -- see REDISTRIBUTABLE_TEXT_FIELDS."),
    # ---------------------------------------------------------------- verifier (ADDED)
    ("verifier_id", "verifier", "str", False, False,
     "ADDED (populator: A's scorer adapter). Name of the scoring function, e.g. "
     "'norm_phrase_set_match'. Required because EXPERIMENT_PLAN 8.4 forbids arm-dependent "
     "verifiers, and a sibling project lost a table to exactly that; without the field "
     "the prohibition is unverifiable."),
    ("verifier_version", "verifier", "str", False, False,
     "ADDED (populator: A's scorer adapter). Version of that scorer. ONE value per row, "
     "so WITH and WITHOUT are scored by the same verifier by construction."),
    ("reward_is_continuous", "verifier", "bool", False, False,
     "ADDED (populator: A's scorer adapter). Whether this verifier can emit intermediate "
     "values. Lets the dataset-level validator distinguish 'binary benchmark' from "
     "'continuous reward wrongly rounded' (design req 2)."),
    ("leakage_flag", "verifier", "bool", True, False,
     "ADDED (populator: A's leakage detector, P1-022). True when the gold answer appears "
     "in memory_text. EXPERIMENT_PLAN 8.3: flag and report, do NOT drop -- dropping "
     "changes the question. Null until the detector runs."),
    # ---------------------------------------------------------------- label rule (ADDED)
    ("utility_label_threshold", "label_rule", "float", True, False,
     "ADDED (populator: D). The reference noise floor F from "
     "docs/ANALYSIS_PREREGISTRATION.md section 2, as used for THIS row's label. REQUIRED "
     "to satisfy design req 2: without F the stored label is not recomputable. "
     "NULL UNTIL P1-051 MEASURES F -- and it has not, so every row written today carries "
     "null here and label 'undetermined' by construction. The labels are recomputed in "
     "place once F exists."),
    ("delta_utility_ci_lower", "label_rule", "float", True, False,
     "ADDED (populator: D). Lower bound of the 95% bootstrap CI of mean dU over the "
     "cell's replicates. Required by prereg section 4: the label needs BOTH a CI clause "
     "and a floor clause, so a row storing only a threshold cannot reproduce its label."),
    ("delta_utility_ci_upper", "label_rule", "float", True, False,
     "ADDED (populator: D). Upper bound of that CI."),
    ("delta_utility_cell_mean", "label_rule", "float", True, False,
     "ADDED (populator: D). Mean dU over the cell's replicates -- the quantity the floor "
     "clause compares against. Distinct from this ROW's delta_utility, which is one "
     "replicate."),
    ("replicate_count", "label_rule", "int", True, False,
     "ADDED (populator: D). Replicates contributing to the cell mean and CI. Prereg "
     "section 12 REQUIRES this be reported per cell, because adaptive replication makes "
     "replicate count non-random and biases naive pooling."),
    ("utility_label_rule_version", "label_rule", "str", False, False,
     "ADDED (populator: derive_utility_label). Version of the labelling rule, so a "
     "relabelled release is distinguishable from the original."),
    # ---------------------------------------------------------------- endpoint hash (ADDED)
    ("reader_endpoint_sha256", "execution_aux", "str", False, False,
     "ADDED (populator: sanitized_base_url_hash). Credential-safe fingerprint of the full "
     "reader base URL. Lets provenance be verified without ever storing a URL that could "
     "embed a token."),
    # ---------------------------------------------------------------- P3 reserved
    ("receiver_id", "p3_reserved", "any", True, True,
     "P3 RESERVED. Must be null in P1."),
    ("receiver_role", "p3_reserved", "any", True, True,
     "P3 RESERVED. Must be null in P1."),
    ("visibility_mask", "p3_reserved", "any", True, True,
     "P3 RESERVED. Must be null in P1."),
    ("team_reward", "p3_reserved", "any", True, True,
     "P3 RESERVED. Must be null in P1."),
)

FIELD_SPEC: dict[str, dict[str, Any]] = {
    name: {
        "group": group,
        "kind": kind,
        "nullable": nullable,
        "required_by_brief": req,
        "description": desc,
    }
    for (name, group, kind, nullable, req, desc) in _SPEC
}

FIELD_ORDER: tuple[str, ...] = tuple(name for (name, *_r) in _SPEC)
REQUIRED_FIELDS: tuple[str, ...] = FIELD_ORDER  # every field must be PRESENT (may be null)

BRIEF_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    n for n, s in FIELD_SPEC.items() if s["required_by_brief"]
)
ADDED_FIELDS: tuple[str, ...] = tuple(
    n for n, s in FIELD_SPEC.items() if not s["required_by_brief"]
)

GROUPS: tuple[str, ...] = tuple(dict.fromkeys(s["group"] for s in FIELD_SPEC.values()))

P3_RESERVED_FIELDS: tuple[str, ...] = tuple(
    n for n, s in FIELD_SPEC.items() if s["group"] == "p3_reserved"
)

# Design requirement 3: cluster is experimental identity. These may never be null and
# may never be the empty string, whatever else is missing.
NON_NULLABLE_IDENTITY: tuple[str, ...] = (
    "reader_cluster",
    "memory_writer_cluster",
    "reader_model",
    "memory_writer_model",
    "reader_reasoning_effort",
)

# Which clusters report completion_tokens_details.reasoning_tokens (measured by C,
# frozen in docs/CLUSTER_DECISION.md). Used ONLY to tell "absent" from "zero":
#   reasoning_tokens is null  and cluster reports     -> suspicious, flagged
#   reasoning_tokens is 0     and cluster does NOT report -> REJECTED (absent as zero)
CLUSTER_REPORTS_REASONING_TOKENS: dict[str, bool] = {
    "metis": True,
    "sophia": False,
}

# The frozen main arm (docs/CLUSTER_DECISION.md). Recorded here so a row can be checked
# against the decision without a human re-reading the doc. Rows OUTSIDE this identity are
# legal -- Sophia is a designated failover arm -- but they are a DIFFERENT arm and the
# validator says so rather than silently pooling them.
PINNED_IDENTITY: dict[str, Any] = {
    "reader_cluster": "metis",
    "reader_endpoint": "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1",
    "reader_model": "gpt-oss-120b",
    "reader_reasoning_effort": "low",
    "temperature": 0,
    "max_tokens": 512,
    "embedding_model": "Salesforce/SFR-Embedding-Mistral",
    "embedding_cluster": "sophia",
}

# Fields that jointly define an experimental condition when condition_id is absent.
#
# reader_cluster is deliberately NOT here: the whole point of the E2 check is to catch a
# cluster varying inside something claiming to be one condition. If cluster were part of
# the key, every heterogeneous group would silently split into two homogeneous ones and
# the check could never fire.
#
# reader_model is NOT here either, and that omission was found by a failing test rather
# than by design. The model NAME co-varies with the cluster ('gpt-oss-120b' on Metis,
# 'openai/gpt-oss-120b' on Sophia), so keying on the raw name reintroduces exactly the
# split that keying on cluster would have caused: a cluster switch that also renames the
# model would land in a different implicit group and escape the check. The LOGICAL model
# is keyed instead, via ``logical_model_id``.
IMPLICIT_CONDITION_KEYS: tuple[str, ...] = (
    "benchmark",
    "memory_representation",
    "retrieval_method",
    "reader_prompt_version",
)

# Full model outputs and source text. The exporter consults the license reference before
# emitting any of these; where redistribution is forbidden they are replaced by ids and
# derived annotations only (E3).
REDISTRIBUTABLE_TEXT_FIELDS: tuple[str, ...] = (
    "memory_text",
    "future_task_text",
    "output_with_memory",
    "output_without_memory",
    "source_episode_metadata",
)


# ============================================================  DETERMINISTIC IDS
# Identity of a MEMORY: what it says + where it came from + how it was written.
MEMORY_ID_KEYS: tuple[str, ...] = (
    "benchmark",
    "benchmark_version",
    "source_episode_id",
    "memory_representation",
    "memory_semantic_type",
    "memory_text",
    "memory_writer_model",
    "memory_writer_cluster",
    "memory_writer_prompt_version",
)

# Identity of a CELL: a memory against a task under one condition. Replicates share it.
CELL_ID_KEYS: tuple[str, ...] = (
    "memory_id",
    "future_task_id",
    "retrieval_method",
    "retrieval_k",
    "reader_model",
    "reader_cluster",
    "reader_prompt_version",
    "condition_id",
)

# Identity of a ROW: a cell plus its replicate and the exact decoding used.
ROW_ID_KEYS: tuple[str, ...] = ("cell_id", "replicate_id", "seed_or_sampling_config")


def _digest(prefix: str, payload: dict[str, Any], *, episode_id: str | None = None) -> str:
    """Deterministic id: ``prefix`` + sha256 of the canonical payload (+ episode id).

    The episode id is appended in the clear so an id is human-traceable to its source
    without a lookup table -- design requirement 4 ("content hash + episode id").
    """
    core = sha256_text(payload)[:24]
    if episode_id is None:
        return f"{prefix}-{core}"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(episode_id))[:48]
    return f"{prefix}-{safe}-{core}"


def compute_memory_id(row: dict[str, Any]) -> str:
    return _digest(
        "mem",
        {k: row.get(k) for k in MEMORY_ID_KEYS},
        episode_id=row.get("source_episode_id"),
    )


def compute_cell_id(row: dict[str, Any]) -> str:
    return _digest(
        "cell",
        {k: row.get(k) for k in CELL_ID_KEYS},
        episode_id=row.get("source_episode_id"),
    )


def compute_row_id(row: dict[str, Any]) -> str:
    return _digest("row", {k: row.get(k) for k in ROW_ID_KEYS})


# ==============================================================  DERIVED LABEL
def derive_utility_label(
    ci_lower: float | None,
    ci_upper: float | None,
    cell_mean: float | None,
    noise_floor: float | None,
) -> str:
    """THE label rule. docs/ANALYSIS_PREREGISTRATION.md section 4, verbatim.

        robust_useful  : CI_lower > 0  and   mean dU  > F
        robust_harmful : CI_upper < 0  and  |mean dU| > F
        neutral        : CI contains 0  or  |mean dU| <= F
        undetermined   : any input missing

    BOTH clauses are required: statistical separation from zero AND practical magnitude
    above execution noise. A cell may be statistically nonzero yet inside the floor; the
    pre-registration calls that neutral, not useful.

    This takes CELL-level statistics, not one replicate's rewards, because the
    pre-registered rule is defined over the cell's bootstrap CI. A single replicate cannot
    produce a robust label, and this function will not pretend otherwise.

    ``noise_floor`` is F from prereg section 2. **It has not been measured yet (P1-051).**
    Until it is, every call here returns "undetermined", which is the correct answer --
    not a defect. The labels are recomputed from the stored raw rewards once F exists;
    that recomputability is design requirement 2.
    """
    if None in (ci_lower, ci_upper, cell_mean, noise_floor):
        return "undetermined"
    if noise_floor < 0:  # type: ignore[operator]
        raise ValueError(f"noise floor F must be >= 0, got {noise_floor}")
    lo, hi, mean, F = float(ci_lower), float(ci_upper), float(cell_mean), float(noise_floor)  # type: ignore[arg-type]
    if lo > 0.0 and mean > F:
        return "robust_useful"
    if hi < 0.0 and abs(mean) > F:
        return "robust_harmful"
    return "neutral"


def derive_utility_label_from_row(row: dict[str, Any]) -> str:
    """Recompute a row's label from its OWN stored statistics.

    This is the recomputability guarantee of design requirement 2, and what
    ``validate.py`` calls to check that a stored label was not hand-set.
    """
    return derive_utility_label(
        row.get("delta_utility_ci_lower"),
        row.get("delta_utility_ci_upper"),
        row.get("delta_utility_cell_mean"),
        row.get("utility_label_threshold"),
    )


def compute_delta_utility(
    reward_with: float | None, reward_without: float | None
) -> float | None:
    if reward_with is None or reward_without is None:
        return None
    return float(reward_with) - float(reward_without)


# =====================================================  DIGEST-IN-TEXT DETECTOR
_BARE_DIGEST = re.compile(r"^\s*(?:sha256:|sha1:|md5:|0x)?[0-9a-fA-F]{32,128}\s*$")


def looks_like_bare_digest(value: Any) -> bool:
    """True when a text field holds a hash instead of the text (design requirement 1).

    Deliberately narrow: it fires only on a value that is ENTIRELY hex (optionally with a
    ``sha256:``-style prefix). A real model answer that happens to contain a hash is not
    caught, and should not be -- the failure being guarded against is substituting the
    digest FOR the output, not mentioning one.
    """
    if not isinstance(value, str):
        return False
    return bool(_BARE_DIGEST.match(value))


# Rejected in reader_endpoint: userinfo, a query string, or anything token-shaped.
_ENDPOINT_FORBIDDEN = re.compile(
    r"(@)|(\?)|(#)|(key=)|(token=)|(secret)|(bearer)|(password)|(api[_-]?key)",
    re.IGNORECASE,
)


def endpoint_is_credential_safe(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return _ENDPOINT_FORBIDDEN.search(value) is None


# ==================================================================  ROW BUILDER
def blank_row() -> dict[str, Any]:
    """A row with every field present and null. Presence is the contract; null is a value."""
    return {name: None for name in FIELD_ORDER}


def new_row(**values: Any) -> dict[str, Any]:
    """Build a row, filling in every derived field. Unknown keys raise.

    Derivation order matters: memory_id -> cell_id -> row_id, because each feeds the next.
    """
    unknown = sorted(set(values) - set(FIELD_ORDER))
    if unknown:
        raise KeyError(
            f"Unknown schema field(s): {unknown}. Add them to _SPEC with a stated "
            f"populator, or fix the caller."
        )
    row = blank_row()
    row.update(values)

    row["schema_version"] = row.get("schema_version") or SCHEMA_VERSION
    row["created_at_utc"] = row.get("created_at_utc") or utc_now()

    if row.get("delta_utility") is None:
        row["delta_utility"] = compute_delta_utility(
            row.get("reward_with_memory"), row.get("reward_without_memory")
        )
    if row.get("utility_label") is None:
        row["utility_label"] = derive_utility_label_from_row(row)
    row["utility_label_rule_version"] = (
        row.get("utility_label_rule_version") or UTILITY_LABEL_RULE_VERSION
    )

    if not row.get("memory_id"):
        row["memory_id"] = compute_memory_id(row)
    if not row.get("cell_id"):
        row["cell_id"] = compute_cell_id(row)
    if not row.get("row_id"):
        row["row_id"] = compute_row_id(row)

    # P3 fields are null in P1, always, whatever a caller passed.
    for name in P3_RESERVED_FIELDS:
        row[name] = None

    return {name: row[name] for name in FIELD_ORDER}


def logical_model_id(model: Any) -> str:
    """Cluster-independent identity of a model name.

    ⚠️ USED ONLY FOR GROUPING INSIDE THE VALIDATOR. It is never written to a row and never
    applied to data. Collapsing 'gpt-oss-120b' and 'openai/gpt-oss-120b' in the DATA would
    merge two experimental arms -- which is precisely the defect the heterogeneity check
    exists to catch. Collapsing them in the CHECK'S OWN GROUPING KEY is the opposite: it
    is what lets a Metis row and a Sophia row land in the same group so the difference in
    ``reader_cluster`` can be seen at all.
    """
    if not isinstance(model, str):
        return ""
    name = model.strip()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return name.lower()


def implicit_condition_key(row: dict[str, Any]) -> str:
    payload = {k: row.get(k) for k in IMPLICIT_CONDITION_KEYS}
    payload["_logical_reader_model"] = logical_model_id(row.get("reader_model"))
    return sha256_text(payload)[:16]


def condition_key(row: dict[str, Any]) -> str:
    """The grouping key the cluster-homogeneity check runs over."""
    declared = row.get("condition_id")
    if isinstance(declared, str) and declared.strip():
        return f"declared:{declared.strip()}"
    return f"implicit:{implicit_condition_key(row)}"


def field_report() -> str:
    """Human-readable field inventory. Used by tests and the data card."""
    lines = [
        f"SCHEMA_VERSION = {SCHEMA_VERSION}",
        f"total fields = {len(FIELD_ORDER)} "
        f"({len(BRIEF_REQUIRED_FIELDS)} required-by-brief + {len(ADDED_FIELDS)} added)",
        "",
    ]
    for group in GROUPS:
        names = [n for n in FIELD_ORDER if FIELD_SPEC[n]["group"] == group]
        lines.append(f"[{group}]  ({len(names)})")
        for n in names:
            s = FIELD_SPEC[n]
            tag = "" if s["required_by_brief"] else "  (ADDED)"
            null = "null-ok" if s["nullable"] else "NOT-NULL"
            lines.append(f"  - {n}: {s['kind']}, {null}{tag}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION", "UTILITY_LABEL_RULE_VERSION", "DELTA_TOLERANCE",
    "FIELD_SPEC", "FIELD_ORDER", "REQUIRED_FIELDS", "BRIEF_REQUIRED_FIELDS",
    "ADDED_FIELDS", "GROUPS", "P3_RESERVED_FIELDS", "NON_NULLABLE_IDENTITY",
    "IMPLICIT_CONDITION_KEYS", "REDISTRIBUTABLE_TEXT_FIELDS", "ENUMS",
    "MEMORY_REPRESENTATIONS", "MEMORY_SEMANTIC_TYPES", "SEMANTIC_DISTANCE_BANDS",
    "RETRIEVAL_METHODS", "UTILITY_LABELS",
    "canonical_json", "sha256_text", "file_sha256", "sanitized_base_url_hash",
    "utc_now", "write_json_atomic", "write_jsonl_atomic", "append_jsonl_atomic",
    "load_jsonl",
    "compute_memory_id", "compute_cell_id", "compute_row_id",
    "derive_utility_label", "derive_utility_label_from_row", "compute_delta_utility",
    "ERROR_CODES", "ERROR_EMPTY_OUTPUT_FINISH_LENGTH", "CLUSTER_MODEL_NAMING",
    "CLUSTER_REPORTS_REASONING_TOKENS", "PINNED_IDENTITY",
    "looks_like_bare_digest", "endpoint_is_credential_safe",
    "blank_row", "new_row", "condition_key", "implicit_condition_key",
    "logical_model_id", "field_report",
]

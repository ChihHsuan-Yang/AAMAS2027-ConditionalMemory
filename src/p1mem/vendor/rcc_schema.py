"""Provenance, hashing, and I/O helpers for the receiver-conditional lattice.

This module centralizes the small, dependency-free primitives shared by the
subset-lattice runner, the manifest builder, the auditor, and their tests. It
intentionally imports nothing from the heavyweight ``agentverse`` agent stack so
that offline schedule/schema/dry-run tooling stays usable without a live client
or an API key.

The scientific object of this milestone is the receiver-conditional add-one
utility

    Delta(m | H, q) = U(H union {m}; q) - U(H; q)

measured by replaying a frozen receiver on every subset ``H`` of a frozen
five-message pool. Each subset is a fresh, stateless receiver call. This file
defines the on-disk contract for one such state row and the hashes that freeze
the source, pool, prompt, config, and code the row was produced under.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Bumped whenever the state-row contract changes in a way that invalidates
# previously written rows.
SCHEMA_VERSION = "rcc_subset_lattice_v1"
POOL_VERSION = "dhd_canonical_20260723_gpt_oss_120b"

# Fields of a cached hypothesis that are rendered to the receiver. These mirror
# the DHD replay contract: only render text and immutable source labels are kept;
# gold and proposal-correctness labels are never surfaced as controller input.
RENDER_KEYS = (
    "role",
    "proposed_answer",
    "reasoning_direction",
    "key_idea",
    "critical_assumption",
    "what_to_check",
    "confidence",
)


# --------------------------------------------------------------------- time
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------- hashing
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


def problem_hash(problem: str) -> str:
    """SHA-1[:12] of the problem text — matches the cached-source convention."""
    return hashlib.sha1(str(problem).encode("utf-8")).hexdigest()[:12]


def sanitized_base_url_hash(base_url: str | None) -> str:
    """Stable fingerprint of an endpoint base URL.

    Stored instead of the raw URL so provenance is verifiable without recording
    a value that could carry an embedded credential. Never store the raw URL or
    any token alongside this.
    """
    return hashlib.sha256(str(base_url or "").encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------- atomic I/O
def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def write_jsonl_atomic(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
    os.replace(tmp, path)


def load_jsonl(path: str | Path, *, strict: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError(
                        f"Malformed JSON at {path}:{line_number}: {exc}"
                    ) from exc
                continue
            if not isinstance(row, dict):
                if strict:
                    raise ValueError(f"Non-object JSON at {path}:{line_number}")
                continue
            rows.append(row)
    return rows


# --------------------------------------------------- state-row field contract
# The minimum set of keys every SUCCESSFUL state row must carry (brief section 7).
# The auditor checks presence of these on each valid row.
REQUIRED_STATE_FIELDS = (
    "schema_version",
    "run_contract_hash",
    "benchmark",
    "problem_id",
    "problem_hash",
    "pool_version",
    "pool_hash",
    "prompt_version",
    "domain_hint_hash",
    "subset_mask_integer",
    "subset_mask_5bit",
    "replicate_id",
    # Logical terminal outcome of the state: "scored_answer" (a parseable boxed
    # answer was graded) or "receiver_no_answer" (endpoint returned 200 but the
    # receiver produced no parseable answer within budget; U=0, a real model
    # outcome, not an operational error). Operational errors never reach a valid
    # row -- they are quarantined and rerun.
    "terminal_outcome",
    "visible_message_ids",
    "receiver_model",
    "receiver_effective_model",
    "receiver_endpoint_alias",
    "receiver_base_url_hash",
    "evaluator_model",
    "evaluator_effective_model",
    "evaluator_endpoint_alias",
    "evaluator_base_url_hash",
    # Effective per-role config actually forwarded to the API (replaces the old
    # misleading single "temperature"/"max_tokens" fields).
    "receiver_effective_max_tokens",
    "evaluator_effective_max_tokens",
    "receiver_effective_temperature",
    "evaluator_effective_temperature",
    "receiver_prompt_hash",
    "raw_answer",
    "parsed_answer",
    "correct",
    "evaluator_mode",
    "receiver_call_status",
    "evaluator_call_status",
    "started_at_utc",
    "finished_at_utc",
    "latency_sec",
    "code_sha",
    "config_sha256",
)

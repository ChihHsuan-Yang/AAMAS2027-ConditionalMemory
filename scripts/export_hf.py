#!/usr/bin/env python3
"""Build the Hugging Face staging directory for the Conditional Memory Utility Dataset.

    python3 scripts/export_hf.py --results results/cells/*.jsonl --staging <dir>

The staging directory is built OUTSIDE the repository. The repo root is never uploaded:
it contains a git history, endpoint benchmark logs, and configs, none of which belong in
a public dataset release.

**Gates 1-3 run BEFORE a single byte is emitted.** If any fails the script writes
nothing at all -- it does not write a partial export and warn:

  GATE 1  schema validation      -- every row conforms (scripts cannot fix data)
  GATE 2  secret scan            -- no token, key, credential or bearer string anywhere,
                                    including inside model outputs and metadata
  GATE 3  license exclusion      -- no text field is emitted whose source license forbids
                                    redistribution

**Gates 4-5 run AFTER the directory is written, on the artifact itself**, because gates
1-3 inspect rows held in memory and cannot see a defect introduced by the writing:

  GATE 4  re-validate the FILE   -- load data/cells.jsonl back from disk and run the
                                    shipped validator on it
  GATE 5  run the card's command -- execute the verification snippet the README tells a
                                    consumer to run, in a subprocess, from the staging
                                    root, with no repo paths available

Both exist because of a defect that shipped on 2026-09-30: ``redact_row`` adds three
export-provenance fields AFTER gate 1 validates, and they were not in ``FIELD_SPEC``, so
all 4,519 published rows failed the validator published beside them. Every component was
individually correct; the defect lived in the SEAM, and no check read the emitted
artifact back. It was found by downloading the release and running its own documented
command -- which is now gate 5.

A gate that has never rejected anything is not known to work, so ``--self-test`` plants a
secret and a non-redistributable payload into a copy of the data and asserts each gate
fires. ``--self-test`` runs automatically before every real export unless
``--skip-self-test`` is passed, which is itself recorded in the manifest.

NOTHING HERE UPLOADS. This script only builds a directory. Upload is a separate,
explicitly authorized step (see ``--print-upload-command``).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from p1mem import schema as S            # noqa: E402
from p1mem import validate as V          # noqa: E402

HF_REPO_ID = "AgentsSci/AAMAS2027-ConditionalMemory"
HF_REPO_TYPE = "dataset"

# The doc that OWNS the license determinations. Sub-agent A writes it; this script does
# not restate its conclusions, it requires and records it.
LICENSE_DOC = REPO_ROOT / "docs" / "BENCHMARK_LICENSES.md"

# The data card source. Copied to <staging>/README.md, which is what HF renders.
CARD_SRC = REPO_ROOT / "docs" / "hf_card" / "README.md"


# ======================================================== LICENSE POLICY
@dataclass(frozen=True)
class LicensePolicy:
    key: str
    redistribute_source_text: bool   # memory_text / future_task_text / episode metadata
    redistribute_model_output: bool  # OUR generations -- a different question
    note: str


# Keyed by the row's ``license_source_reference`` prefix (before the first ':').
#
# The distinction that matters: OUR MODEL OUTPUTS ARE OURS. A benchmark whose *inputs*
# cannot be redistributed does not thereby own our generations -- but a generation can
# quote its input, so an output is only released when the input is (see
# ``_output_may_quote_source``).
#
# ⚠️ These flags are a MECHANISM, not a legal finding. The findings live in
# docs/BENCHMARK_LICENSES.md (Sub-agent A). If that doc and this table disagree, the doc
# wins and this table is wrong. The script refuses to run if the doc is absent.
LICENSE_POLICIES: dict[str, LicensePolicy] = {
    "longmemeval_v1": LicensePolicy(
        "longmemeval_v1", False, False,
        "V1 is MIT, but its FILLER sessions derive from ShareGPT and UltraChat, which "
        "carry their own upstream terms independent of V1's MIT grant. ShareGPT content "
        "is scraped OpenAI conversations of contested provenance. Evidence sessions "
        "(answer_* namespace) are the benchmark's own, but a downstream user cannot tell "
        "one from the other in a redistributed blob. Withhold source text; publish ids, "
        "offsets and derived annotations plus the code to reconstruct."),
    "longmemeval_v2": LicensePolicy(
        "longmemeval_v2", True, True,
        "Apache-2.0 with a LICENSE file in the release (verified by Sub-agent A). "
        "Redistribution permitted with attribution."),
    "beam": LicensePolicy("beam", False, False, "PENDING Sub-agent A. Fail closed."),
    "scicode": LicensePolicy("scicode", False, False, "PENDING Sub-agent A. Fail closed."),
}

# Fail closed: a benchmark with no policy entry is treated as non-redistributable.
DEFAULT_POLICY = LicensePolicy(
    "__unknown__", False, False,
    "No license policy recorded for this source. Failing closed: publish ids and derived "
    "annotations only until docs/BENCHMARK_LICENSES.md covers it.")

# Replacement written into a withheld text field, so a consumer sees a withholding rather
# than silence. An absent key and a withheld key are different facts.
WITHHELD = "__WITHHELD_SEE_LICENSE__"


def policy_for(license_ref: Any) -> LicensePolicy:
    if not isinstance(license_ref, str) or not license_ref.strip():
        return DEFAULT_POLICY
    return LICENSE_POLICIES.get(license_ref.split(":", 1)[0].strip(), DEFAULT_POLICY)


def _output_may_quote_source(pol: LicensePolicy) -> bool:
    """A model output can quote its prompt, so it inherits the input's restriction."""
    return pol.redistribute_model_output and pol.redistribute_source_text


# ============================================================ SECRET SCAN
# Each pattern is paired with a benign near-miss in ``SECRET_SCAN_NEGATIVES`` so the
# scanner is known to discriminate rather than merely to alarm.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hf_token",        re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("openai_key",      re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("aws_access_key",  re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token",    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack_token",     re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key",  re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("private_key",     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt",             re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("bearer_header",   re.compile(r"[Aa]uthorization\s*:\s*[Bb]earer\s+\S{12,}")),
    ("url_userinfo",    re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
    ("assigned_secret", re.compile(
        r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret"
        r"|password|passwd|globus[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-./+]{12,}")),
    ("globus_refresh",  re.compile(r"\bAg[A-Za-z0-9]{40,}")),
)

# Strings that must NOT trip the scanner. A scanner that flags these is unusable and the
# team will start ignoring it.
SECRET_SCAN_NEGATIVES: tuple[str, ...] = (
    "Set HUGGINGFACE_TOKEN in your environment before running.",
    "reader_endpoint: https://inference-api.alcf.anl.gov/resource_server/metis/api/v1",
    "The api_key field is required.",
    "password reset instructions were sent",
    "sha256: " + "a" * 64,
    "See docs/BENCHMARK_LICENSES.md for the token accounting.",
    "hf_hub_download('AgentsSci/AAMAS2027-ConditionalMemory')",
)

# Files never copied into staging regardless of content.
EXCLUDE_NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(re.compile(p) for p in (
    r"(^|/)\.git(/|$)", r"(^|/)\.env$", r"\.env$", r"(^|/)\.globus(/|$)",
    r"(?i)token", r"(?i)credential", r"(?i)secret", r"(?i)\bkey\b",
    r"\.pem$", r"\.key$", r"\.p12$", r"\.pfx$", r"(^|/)\.ssh(/|$)",
    r"(^|/)\.netrc$", r"(^|/)id_rsa", r"(^|/)\.aws(/|$)",
    r"(^|/)__pycache__(/|$)", r"\.pyc$", r"(^|/)\.DS_Store$",
    r"(^|/)cache(/|$)", r"(^|/)\.cache(/|$)", r"(^|/)endpoint_cache(/|$)",
    r"(?i)\.log$", r"(?i)(^|/)logs?(/|$)", r"(^|/)\.venv(/|$)", r"(^|/)venv(/|$)",
    r"(^|/)\.ipynb_checkpoints(/|$)", r"(^|/)\.pytest_cache(/|$)",
))

MAX_FILE_BYTES = 200 * 1024 * 1024   # a transient log, not a dataset shard


def scan_text_for_secrets(text: str, where: str) -> list[str]:
    hits = []
    for name, pat in SECRET_PATTERNS:
        m = pat.search(text)
        if m:
            found = m.group(0)
            shown = found[:6] + "..." + f"[{len(found)} chars]"   # never echo a secret
            hits.append(f"{where}: {name} matched ({shown})")
    return hits


def scan_obj_for_secrets(obj: Any, where: str) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out += scan_text_for_secrets(obj, where)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += scan_obj_for_secrets(k, f"{where}.<key>")
            out += scan_obj_for_secrets(v, f"{where}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += scan_obj_for_secrets(v, f"{where}[{i}]")
    return out


def path_is_excluded(rel: str) -> str | None:
    for pat in EXCLUDE_NAME_PATTERNS:
        if pat.search(rel):
            return pat.pattern
    return None


# ============================================================ ROW EXPORT
def redact_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply the license policy. Returns (exported row, list of withheld field names)."""
    pol = policy_for(row.get("license_source_reference"))
    out = dict(row)
    withheld: list[str] = []

    if not pol.redistribute_source_text:
        for f in ("memory_text", "future_task_text"):
            if out.get(f) is not None:
                out[f] = WITHHELD
                withheld.append(f)
        if out.get("source_episode_metadata") is not None:
            out["source_episode_metadata"] = {"__withheld__": True, "license": pol.key}
            withheld.append("source_episode_metadata")
        # v0.2: faithfulness_detail QUOTES SOURCE TEXT. Three of its keys carry
        # verbatim fragments -- ``contradictions[].source`` holds the source-side
        # binding ("click('287')"), and the unsupported_* lists hold tokens and URLs
        # lifted out of the memory, which for a raw-derived memory IS source text.
        # The numeric axes are ours and stay; the quoted fragments follow the same
        # rule as memory_text. Withholding the WHOLE object would destroy the
        # measurement over a licence question that only bites on the quotations.
        fd = out.get("faithfulness_detail")
        if isinstance(fd, dict):
            quoting = ("unsupported_numbers", "unsupported_entities", "contradictions")
            if any(fd.get(k) for k in quoting):
                trimmed = {k: v for k, v in fd.items() if k not in quoting}
                trimmed["__quoted_fragments_withheld__"] = True
                trimmed["__license__"] = pol.key
                out["faithfulness_detail"] = trimmed
                withheld.append("faithfulness_detail.quoted_fragments")

    if not _output_may_quote_source(pol):
        for f in ("output_with_memory", "output_without_memory"):
            if out.get(f) is not None:
                out[f] = WITHHELD
                withheld.append(f)

    # Derived annotations always ship: they are ours and they are the dataset's point.
    out["license_policy"] = pol.key
    out["text_fields_withheld"] = sorted(set(withheld))
    out["reconstruction_required"] = bool(withheld)
    return out, withheld


# ============================================================== GATES
class GateFailure(Exception):
    pass


def gate_validate(rows: Sequence[dict[str, Any]]) -> V.Report:
    rep = V.validate_dataset(rows)
    if not rep.ok:
        raise GateFailure(
            "GATE 1 (schema validation) FAILED -- nothing was written.\n" + rep.summary()
            + "\n" + "\n".join("  " + str(i) for i in rep.errors[:20]))
    return rep


def gate_secret_scan_rows(rows: Sequence[dict[str, Any]]) -> None:
    hits: list[str] = []
    for i, r in enumerate(rows):
        hits += scan_obj_for_secrets(r, f"row[{i}]")
        if len(hits) > 50:
            break
    if hits:
        raise GateFailure(
            "GATE 2 (secret scan) FAILED -- nothing was written.\n"
            + "\n".join("  " + h for h in hits[:50]))


def gate_secret_scan_tree(root: Path) -> None:
    hits: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        why = path_is_excluded(rel)
        if why:
            hits.append(f"{rel}: excluded path pattern present in staging ({why})")
            continue
        if p.stat().st_size > MAX_FILE_BYTES:
            hits.append(f"{rel}: {p.stat().st_size} bytes exceeds {MAX_FILE_BYTES}")
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        hits += scan_text_for_secrets(text, rel)
    if hits:
        raise GateFailure(
            "GATE 2 (secret scan, staging tree) FAILED.\n" + "\n".join("  " + h for h in hits[:50]))


def gate_license_exclusion(exported: Sequence[dict[str, Any]]) -> dict[str, int]:
    """No text field may survive whose source license forbids redistribution."""
    leaks: list[str] = []
    counts: Counter = Counter()
    for i, r in enumerate(exported):
        pol = policy_for(r.get("license_source_reference"))
        counts[pol.key] += 1
        if not pol.redistribute_source_text:
            for f in ("memory_text", "future_task_text"):
                v = r.get(f)
                if v is not None and v != WITHHELD:
                    leaks.append(f"row[{i}].{f}: {len(str(v))} chars survived under "
                                 f"non-redistributable policy {pol.key!r}")
            md = r.get("source_episode_metadata")
            if isinstance(md, dict) and not md.get("__withheld__"):
                leaks.append(f"row[{i}].source_episode_metadata survived under {pol.key!r}")
            fd = r.get("faithfulness_detail")
            if isinstance(fd, dict):
                for k in ("unsupported_numbers", "unsupported_entities",
                          "contradictions"):
                    if fd.get(k):
                        leaks.append(
                            f"row[{i}].faithfulness_detail.{k} carries verbatim source "
                            f"fragments under non-redistributable policy {pol.key!r}")
        if not _output_may_quote_source(pol):
            for f in ("output_with_memory", "output_without_memory"):
                v = r.get(f)
                if v is not None and v != WITHHELD:
                    leaks.append(f"row[{i}].{f} survived under {pol.key!r}")
    if leaks:
        raise GateFailure(
            "GATE 3 (license exclusion) FAILED -- nothing was written.\n"
            + "\n".join("  " + x for x in leaks[:50]))
    return dict(counts)


def gate_exported_file_revalidates(path: Path, expected_rows: int) -> None:
    """GATE 4: re-read the file we are about to ship and validate IT.

    🔴 Added 2026-09-30 after this exact defect shipped. Gate 1 validates the rows we
    hold in memory BEFORE redaction; ``redact_row`` then ADDS three export-provenance
    fields. Those fields were not in ``FIELD_SPEC``, so every published row failed the
    validator published beside it -- 13,557 ``unknown_field`` errors on 4,519 rows.

    Both components were individually correct. The defect lived in the SEAM, and no
    local check could see it because no local check ever read the emitted artifact back.
    It was found by downloading the release and running its own documented command.

    So this gate validates the FILE, after writing, exactly as a consumer would: load it
    from disk, run the shipped validator, and require zero errors. A release whose own
    documented verification fails is not a release.
    """
    if not path.exists():
        return                                     # structure-only build, no data
    rows = S.load_jsonl(path, strict=True)
    if len(rows) != expected_rows:
        raise GateFailure(
            f"GATE 4 (re-validation) FAILED: wrote {expected_rows} rows but the file on "
            f"disk holds {len(rows)}.")
    rep = V.validate_dataset(rows)
    if not rep.ok:
        raise GateFailure(
            "GATE 4 (re-validation of the WRITTEN file) FAILED. The exported artifact "
            "does not pass the validator shipped beside it, so the release would fail "
            "its own documented check.\n" + rep.summary()
            + "\n" + "\n".join("  " + str(i) for i in rep.errors[:20]))


def gate_license_doc_present() -> str:
    if not LICENSE_DOC.exists():
        raise GateFailure(
            f"GATE 3 (license exclusion) FAILED: {LICENSE_DOC.relative_to(REPO_ROOT)} does "
            f"not exist. That document (Sub-agent A, P1-027) is the authority on what may "
            f"be redistributed; this script only enforces it. Refusing to export a dataset "
            f"whose license determinations have not been written down.")
    return S.file_sha256(LICENSE_DOC)


# ============================================================ SELF-TEST
def self_test(rows: Sequence[dict[str, Any]]) -> list[str]:
    """Prove each gate can FAIL, by planting the defect it exists to catch.

    A gate that has never rejected anything is not known to work. Returns a list of
    human-readable PASS lines; raises if any gate failed to fire.
    """
    log: list[str] = []
    sample = dict(rows[0]) if rows else _synthetic_row()

    # -- GATE 2 positive: a token planted inside a MODEL OUTPUT, not in a filename.
    #    A path-based scan would miss this entirely.
    planted = dict(sample)
    planted["output_with_memory"] = (
        (sample.get("output_with_memory") or "answer") +
        "\n[debug] Authorization: Bearer hf_" + "A" * 34)
    try:
        gate_secret_scan_rows([planted])
        raise AssertionError("SELF-TEST FAILED: secret scan did not catch a planted "
                             "bearer token inside a model output field")
    except GateFailure:
        log.append("PASS gate2: planted bearer token in output_with_memory was caught")

    # second shape: a key-looking assignment in a nested metadata dict
    planted2 = dict(sample)
    planted2["provenance"] = dict(sample.get("provenance") or {})
    planted2["provenance"]["note"] = "api_key=sk-abcdefghijklmnopqrstuvwxyz012345"
    try:
        gate_secret_scan_rows([planted2])
        raise AssertionError("SELF-TEST FAILED: secret scan did not catch a nested key")
    except GateFailure:
        log.append("PASS gate2: planted api_key in nested provenance dict was caught")

    # -- GATE 2 negative: benign strings must NOT trip it, or the scan is noise.
    for s in SECRET_SCAN_NEGATIVES:
        if scan_text_for_secrets(s, "neg"):
            raise AssertionError(f"SELF-TEST FAILED: scanner false-positives on {s!r}")
    log.append(f"PASS gate2-negative: {len(SECRET_SCAN_NEGATIVES)} benign strings not flagged")

    # -- GATE 3 positive: non-redistributable text that escaped redaction.
    leaky = dict(sample)
    leaky["license_source_reference"] = "longmemeval_v1:MIT+sharegpt_upstream"
    leaky["memory_text"] = "verbatim ShareGPT filler content that may not be redistributed"
    try:
        gate_license_exclusion([leaky])
        raise AssertionError("SELF-TEST FAILED: license gate passed verbatim source text "
                             "under a non-redistributable policy")
    except GateFailure:
        log.append("PASS gate3: un-redacted longmemeval_v1 source text was caught")

    # -- GATE 3 positive #2: an UNKNOWN benchmark must fail closed, not open.
    unknown = dict(sample)
    unknown["license_source_reference"] = "some_new_benchmark:unknown"
    unknown["memory_text"] = "text from a benchmark nobody has licensed yet"
    try:
        gate_license_exclusion([unknown])
        raise AssertionError("SELF-TEST FAILED: unknown license failed OPEN")
    except GateFailure:
        log.append("PASS gate3: an unrecognized license reference fails CLOSED")

    # -- GATE 3 positive #3 (v0.2): faithfulness_detail quotes SOURCE TEXT in three of
    #    its keys. A new field added late is exactly the one a licence gate written
    #    before it existed cannot see, so the plant goes INSIDE the new field.
    quoting = dict(sample)
    quoting["license_source_reference"] = "longmemeval_v1:MIT+sharegpt_upstream"
    quoting["faithfulness_detail"] = {
        "rule_version": "deterministic_proxy@1.0.0", "representation": "summary",
        "number_support": 1.0, "entity_support": 0.9,
        "contradictions": [{"key": "action", "source": ["click('287')"],
                            "memory": ["clicked the link"]}],
        "unsupported_entities": ["http://localhost:9080/f/AskReddit/10224/some-thread"],
    }
    try:
        gate_license_exclusion([quoting])
        raise AssertionError("SELF-TEST FAILED: license gate passed verbatim source "
                             "fragments inside faithfulness_detail")
    except GateFailure:
        log.append("PASS gate3: source fragments quoted inside faithfulness_detail "
                   "were caught")

    # -- GATE 3 negative #3: redaction must keep the NUMERIC axes. Stripping the whole
    #    object would destroy a measurement to answer a question about quotations.
    red, _ = redact_row(dict(quoting))
    gate_license_exclusion([red])
    fdr = red["faithfulness_detail"]
    if fdr.get("number_support") != 1.0 or fdr.get("entity_support") != 0.9:
        raise AssertionError(
            f"SELF-TEST FAILED: redaction destroyed the faithfulness measurement "
            f"rather than only its quoted fragments: {fdr}")
    if not fdr.get("__quoted_fragments_withheld__"):
        raise AssertionError("SELF-TEST FAILED: redaction did not mark the withholding")
    log.append("PASS gate3-negative: redaction removes the quotes and KEEPS the "
               "numeric faithfulness axes")

    # -- GATE 3 negative #4: an Apache-2.0 row KEEPS its quoted fragments, or every
    #    contradiction example in the release is destroyed for no licence reason.
    keep, _ = redact_row({**sample,
                          "license_source_reference": "longmemeval_v2:Apache-2.0",
                          "faithfulness_detail": quoting["faithfulness_detail"]})
    if not keep["faithfulness_detail"].get("contradictions"):
        raise AssertionError(
            "SELF-TEST FAILED: Apache-2.0 row lost its faithfulness quotations")
    log.append("PASS gate3-negative: Apache-2.0 keeps faithfulness quotations")

    # -- GATE 3 negative: a properly redacted row must pass, or the gate rejects all.
    ok_row, _ = redact_row({**sample,
                            "license_source_reference": "longmemeval_v1:MIT+sharegpt_upstream"})
    gate_license_exclusion([ok_row])
    log.append("PASS gate3-negative: a correctly redacted row is accepted")

    # -- GATE 3 negative #2: an Apache-2.0 source KEEPS its text (else we withhold all).
    v2, withheld = redact_row({**sample, "license_source_reference": "longmemeval_v2:Apache-2.0"})
    if withheld:
        raise AssertionError(f"SELF-TEST FAILED: Apache-2.0 source wrongly withheld {withheld}")
    log.append("PASS gate3-negative: Apache-2.0 source text is retained, not over-redacted")

    # -- GATE 1 positive: a malformed row must be rejected.
    bad = dict(sample); bad["reader_cluster"] = None
    try:
        gate_validate([bad])
        raise AssertionError("SELF-TEST FAILED: schema gate passed a row with no cluster")
    except GateFailure:
        log.append("PASS gate1: a row with a blanked reader_cluster was rejected")

    return log


def _synthetic_row() -> dict[str, Any]:
    """Minimal valid row so --self-test works before any results exist."""
    return S.new_row(
        benchmark="longmemeval_v1", benchmark_version="selftest",
        source_episode_id="answer_selftest",
        source_episode_metadata={"note": "synthetic"},
        memory_representation="summary", memory_semantic_type="semantic_fact",
        memory_text="synthetic memory", memory_tokens=2,
        memory_source_span={"session_id": "answer_selftest"},
        memory_writer_model="gpt-oss-120b", memory_writer_cluster="metis",
        memory_writer_prompt_version="summary_v1",
        memory_extraction_latency=0.1, memory_extraction_input_tokens=10,
        memory_extraction_output_tokens=5,
        embedding_model="Salesforce/SFR-Embedding-Mistral", embedding_version="selftest",
        memory_embedding_reference={"store": "emb/x.npy", "index": 0, "dim": 4096},
        future_task_id="q_selftest", future_task_family="temporal-reasoning",
        future_task_text="synthetic task",
        task_embedding_reference={"store": "emb/t.npy", "index": 0, "dim": 4096},
        semantic_similarity=0.5, semantic_distance_band="MID",
        retrieval_method="top_k", retrieval_rank=1, retrieval_k=5,
        memory_tokens_retrieved=10, memory_tokens_exposed=10,
        replicate_id=0, seed_or_sampling_config={"temperature": 0, "max_tokens": 512},
        reader_model="gpt-oss-120b", reader_cluster="metis",
        reader_endpoint="metis:/resource_server/metis/api/v1",
        reader_prompt_version="reader_v1", reader_reasoning_effort="low",
        output_without_memory="no", output_with_memory="yes",
        reward_without_memory=0.0, reward_with_memory=1.0,
        write_latency=0.1, retrieval_latency=0.1, generation_latency=1.0,
        end_to_end_latency=1.2, embedding_calls=0, generation_calls=2,
        input_tokens=100, output_tokens=10, reasoning_tokens=5, retry_count=0,
        provenance={"code_sha": "selftest", "config_sha256": "0" * 64, "run_id": "selftest"},
        license_source_reference="longmemeval_v1:MIT+sharegpt_upstream",
        verifier_id="selftest", verifier_version="0", reward_is_continuous=False,
        condition_id="selftest",
        reader_endpoint_sha256=S.sanitized_base_url_hash("selftest"),
    )


# ============================================================ BUILD
def build(results: Sequence[Path], staging: Path, *, extra_docs: Sequence[Path],
          skip_self_test: bool, force: bool) -> dict[str, Any]:
    if staging.resolve() == REPO_ROOT.resolve() or REPO_ROOT.resolve() in staging.resolve().parents:
        raise GateFailure(
            f"Refusing to stage inside the repository ({staging}). The repo root carries "
            f"git history, endpoint logs and configs and is never uploaded. Use a "
            f"directory outside {REPO_ROOT}.")

    license_doc_sha = gate_license_doc_present()

    rows: list[dict[str, Any]] = []
    for p in results:
        rows.extend(S.load_jsonl(p, strict=True))
    if not rows and not force:
        raise GateFailure(
            "No result rows found. Pass --force to build a structure-only staging "
            "directory (card + schema + scripts, no data).")

    selftest_log: list[str] = []
    if not skip_self_test:
        selftest_log = self_test(rows)

    report = gate_validate(rows) if rows else V.Report()
    gate_secret_scan_rows(rows)
    exported = [redact_row(r)[0] for r in rows]
    license_counts = gate_license_exclusion(exported)

    if staging.exists():
        shutil.rmtree(staging)
    (staging / "data").mkdir(parents=True)
    (staging / "docs").mkdir(parents=True)
    (staging / "code").mkdir(parents=True)

    if exported:
        S.write_jsonl_atomic(staging / "data" / "cells.jsonl", exported)

    # Reconstruction code: how to rebuild withheld text from the original benchmark.
    #
    # Shipped as an IMPORTABLE PACKAGE (code/p1mem/), not as two loose modules. The data
    # card tells a consumer to run `sys.path.insert(0, "code"); from p1mem import ...`,
    # and validate.py does `from .schema import ...` -- a relative import that only
    # resolves inside a package. Two loose files would make the card's own documented
    # verification command fail with ImportError on the consumer's first try.
    # Run the command the doc prescribes, rather than a hand-rolled equivalent.
    pkg = staging / "code" / "p1mem"
    pkg.mkdir(parents=True, exist_ok=True)
    for src in (REPO_ROOT / "src" / "p1mem" / "schema.py",
                REPO_ROOT / "src" / "p1mem" / "validate.py"):
        shutil.copy2(src, pkg / src.name)
    (pkg / "__init__.py").write_text(
        '"""Schema and validator for the Conditional Memory Utility Dataset.\n\n'
        'Shipped so a consumer can verify the release with the command in the data\n'
        'card. See README.md, "Verify this release yourself".\n"""\n'
        "from . import schema, validate  # noqa: F401\n")
    shutil.copy2(LICENSE_DOC, staging / "docs" / LICENSE_DOC.name)
    if not CARD_SRC.exists():
        raise GateFailure(f"data card missing: {CARD_SRC}")
    shutil.copy2(CARD_SRC, staging / "README.md")
    for d in extra_docs:
        if d.exists():
            shutil.copy2(d, staging / "docs" / d.name)

    withheld_counter: Counter = Counter()
    for r in exported:
        for f in r.get("text_fields_withheld", []):
            withheld_counter[f] += 1

    manifest = {
        "hf_repo_id": HF_REPO_ID,
        "hf_repo_type": HF_REPO_TYPE,
        "schema_version": S.SCHEMA_VERSION,
        "built_at_utc": S.utc_now(),
        "n_rows": len(exported),
        "n_fields": len(S.FIELD_ORDER),
        "source_files": [str(p) for p in results],
        "license_doc": str(LICENSE_DOC.relative_to(REPO_ROOT)),
        "license_doc_sha256": license_doc_sha,
        "license_policy_counts": license_counts,
        "text_fields_withheld_counts": dict(withheld_counter),
        "validation": {"errors": len(report.errors), "warnings": len(report.warnings),
                       "codes": sorted(report.codes())},
        # Gates 4 and 5 run AFTER this dict is built (they need the written file), so
        # they are recorded as PENDING here and stamped PASS by build() once they have
        # actually run. A manifest that claimed PASS before the check ran would be a
        # provenance field nobody measured -- and the build raises rather than reaching
        # the stamp if either fails, so PENDING can never survive into a shipped file.
        "gates": {"schema_validation": "PASS", "secret_scan": "PASS",
                  "license_exclusion": "PASS",
                  "written_file_revalidates": "PENDING",
                  "data_card_command_runs": "PENDING"},
        "self_test": ("SKIPPED -- gates are not known to fire for this build"
                      if skip_self_test else selftest_log),
        "files": {},
    }
    # manifest written last so its hashes cover everything else
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            manifest["files"][str(p.relative_to(staging))] = {
                "bytes": p.stat().st_size, "sha256": S.file_sha256(p)}

    S.write_json_atomic(staging / "MANIFEST.json", manifest)
    gate_secret_scan_tree(staging)     # final sweep over what will actually ship

    # Post-write gates: these read the ARTIFACT, not the rows in memory.
    gate_exported_file_revalidates(staging / "data" / "cells.jsonl", len(exported))
    manifest["gates"]["written_file_revalidates"] = "PASS"
    gate_card_command_actually_runs(staging)
    manifest["gates"]["data_card_command_runs"] = "PASS"

    # Rewrite the manifest now that gates 4-5 have genuinely run, then re-hash it.
    # MANIFEST.json's own entry is dropped rather than self-referentially hashed: a
    # file cannot contain its own digest, and a stale one is worse than an absent one.
    manifest["files"].pop("MANIFEST.json", None)
    S.write_json_atomic(staging / "MANIFEST.json", manifest)

    # FINAL sweep, after everything that touches the tree. The first tree scan ran
    # before gates 4-5, so anything THEY deposited would have escaped it -- gate 5
    # imports the shipped package and did, briefly, leave __pycache__ behind. A check
    # placed before the last writer is not a check on what ships.
    gate_secret_scan_tree(staging)

    # Belt and braces: the manifest must name exactly the files present, or a consumer
    # verifying hashes finds files nobody vouched for.
    on_disk = {str(p.relative_to(staging)) for p in staging.rglob("*") if p.is_file()}
    unlisted = sorted(on_disk - set(manifest["files"]) - {"MANIFEST.json"})
    if unlisted:
        raise GateFailure(
            f"files present in staging but absent from MANIFEST.json: {unlisted}. "
            f"Something wrote into the tree after the manifest was built.")
    return manifest


def gate_card_command_actually_runs(staging: Path) -> None:
    """GATE 5: run the verification command the DATA CARD prescribes, as written.

    The card tells a consumer to do exactly this, from the release root:

        sys.path.insert(0, "code")
        from p1mem import schema as S, validate as V
        rows = S.load_jsonl("data/cells.jsonl", strict=True)
        V.validate_dataset(rows)

    Hand-verifying the same property a different way is a DIFFERENT TEST. Shipping two
    loose modules instead of a package, for instance, leaves every documented claim true
    while the printed command dies on ``ImportError`` -- because validate.py imports
    ``.schema`` relatively. This gate runs the documented command in a subprocess, from
    the staging root, with no repo paths available, so a consumer's experience is what
    is actually checked.
    """
    data = staging / "data" / "cells.jsonl"
    if not data.exists():
        return
    script = (
        "import sys; sys.path.insert(0, 'code')\n"
        "from p1mem import schema as S, validate as V\n"
        "rows = S.load_jsonl('data/cells.jsonl', strict=True)\n"
        "rep = V.validate_dataset(rows)\n"
        "print(rep.summary())\n"
        "raise SystemExit(0 if rep.ok else 3)\n"
    )
    # -B / PYTHONDONTWRITEBYTECODE: importing the shipped package would otherwise leave
    # code/p1mem/__pycache__/*.pyc INSIDE the staging tree -- and this gate runs AFTER
    # gate_secret_scan_tree, the one check that rejects __pycache__. A verification step
    # must not deposit artifacts into the thing it is verifying.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-B", "-c", script], cwd=str(staging), env=env,
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise GateFailure(
            "GATE 5 (the data card's own verification command) FAILED. The release "
            "would not survive a consumer following its README.\n"
            f"  exit={proc.returncode}\n"
            f"  stdout: {proc.stdout.strip()[:800]}\n"
            f"  stderr: {proc.stderr.strip()[:800]}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="*", default=[], type=Path)
    ap.add_argument("--staging", type=Path,
                    default=Path.home() / "Documents" / "2026" / "p1_memory_utility"
                    / "hf_staging" / "AAMAS2027-ConditionalMemory")
    ap.add_argument("--extra-docs", nargs="*", default=[], type=Path)
    ap.add_argument("--self-test", action="store_true",
                    help="run the gate self-test and exit without building")
    ap.add_argument("--skip-self-test", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="build a structure-only staging dir with no result rows")
    ap.add_argument("--print-upload-command", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        rows = []
        for p in args.results:
            rows.extend(S.load_jsonl(p, strict=True))
        try:
            for line in self_test(rows):
                print("  " + line)
        except AssertionError as exc:
            print(f"SELF-TEST FAILED: {exc}", file=sys.stderr)
            return 2
        print("self-test OK: every gate fired on its planted defect and stayed quiet on "
              "its negative control")
        return 0

    try:
        manifest = build(args.results, args.staging, extra_docs=args.extra_docs,
                         skip_self_test=args.skip_self_test, force=args.force)
    except GateFailure as exc:
        print(str(exc), file=sys.stderr)
        print("\nNOTHING WAS WRITTEN.", file=sys.stderr)
        return 1

    print(f"staged {manifest['n_rows']} rows -> {args.staging}")
    print(json.dumps({k: manifest[k] for k in
                      ("n_rows", "n_fields", "license_policy_counts",
                       "text_fields_withheld_counts", "gates")}, indent=2))
    if args.print_upload_command:
        print("\n--- UPLOAD IS A SEPARATE, AUTHORIZED STEP. This script does not upload. ---")
        print(f"  set -a; . ~/Documents/note/paths-and-authentication/.hf_token_bella.env; set +a")
        print(f"  HF_TOKEN=\"$HUGGINGFACE_TOKEN_bella\" hf upload {HF_REPO_ID} \\")
        print(f"      {args.staging} . --repo-type={HF_REPO_TYPE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

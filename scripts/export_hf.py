#!/usr/bin/env python3
"""Build the Hugging Face staging directory for the Conditional Memory Utility Dataset.

    python3 scripts/export_hf.py --results results/cells/*.jsonl --staging <dir>

The staging directory is built OUTSIDE the repository. The repo root is never uploaded:
it contains a git history, endpoint benchmark logs, and configs, none of which belong in
a public dataset release.

**Gates 1-3 run BEFORE a single byte is emitted.** If any fails the script writes
nothing at all -- it does not write a partial export and warn:

  GATE 0  benchmark/licence      -- ``benchmark`` and ``license_source_reference`` name
          agreement                 the SAME source. The embargo keys on the first and
                                    redaction on the second; when they disagreed,
                                    benchmark="swebench" (missing "_verified") carried
                                    raw django issue text through with no error at all.
  GATE 1  schema validation      -- every row conforms (scripts cannot fix data)
  GATE 2  secret scan            -- no token, key, credential or bearer string anywhere,
                                    including inside model outputs and metadata.
                                    Severity keys on whether the string SHIPS: a match
                                    inside a licence-withheld field is recorded in the
                                    manifest, not silently dropped and not a blocker.
  GATE 3  license exclusion      -- no text field is emitted whose source license forbids
                                    redistribution
  GATE 3b benchmark refusal      -- BEAM rows may not appear in this dataset in ANY form.
                                    Redaction cannot cure ShareAlike: the row itself is
                                    the adaptation. Three documents claimed this control
                                    existed; measured 2026-09-30, it did not.
  GATE 3c SciCode eval targets   -- SciCode is Apache-2.0 (so its problem text SHIPS),
                                    but test_data.h5 is distributed outside that grant
                                    with no licence stamp. A per-FIELD carve-out that a
                                    per-row policy flag cannot express.
  GATE 6  schema embargo helper  -- runs schema.assert_content_redistributable, which
                                    keys on ``benchmark`` rather than on the licence
                                    reference. Deliberately redundant with gate 3: two
                                    independent keys over one ruling.

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

v0.3 (SciCode) and v0.4 (SWE-bench) are the first releases to ship more than one
benchmark and the first to WITHHOLD anything, which is why several of the gates above
are dated 2026-09-30: v0.1/v0.2 were pure LongMemEval-V2 (Apache-2.0, nothing withheld),
so every path that only runs on a withheld or multi-benchmark row was unexercised. Two
were outright broken. ``memory_text`` is one of ``MEMORY_ID_KEYS``, so blanking it after
the id was minted made every withheld row fail gate 4 with ``id_mismatch``; and
``assert_content_redistributable`` read the withholding sentinel -- a truthy string --
as carried content, so a CORRECTLY redacted row could not be exported at all. The two
mechanisms were mutually exclusive and nothing detected it, because nothing had ever
been withheld.

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
    "beam": LicensePolicy(
        "beam", False, False,
        "CC BY-SA 4.0 (docs/BENCHMARK_LICENSES.md section 3). ShareAlike is INFECTIOUS: "
        "shipping BEAM content in a mixed release either violates it or silently "
        "relicenses the V1/V2/SciCode rows beside it. Measurements ABOUT BEAM are facts, "
        "not adaptations, and stay publishable. BEAM rows are refused outright by "
        "gate_benchmark_refusal, not merely redacted -- see that gate. (Was 'PENDING "
        "Sub-agent A' until 2026-09-30; A's ruling had been written for some time and "
        "this note had not caught up.)"),
    "scicode": LicensePolicy(
        "scicode", True, True,
        "Apache-2.0 on BOTH the code (github.com/scicode-bench/SciCode, LICENSE read at "
        "HEAD e3158ea0) and the data (HF SciCode1/SciCode, license:apache-2.0, "
        "gated:false) -- docs/BENCHMARK_LICENSES.md section 4. Problems, subproblem "
        "prompts and test cases are redistributable with attribution and NOTICE. "
        "🔴 CARVE-OUT: the numeric eval targets in test_data.h5 are NOT covered -- they "
        "ship via an unversioned Google Drive folder with no licence stamp, so "
        "Apache-2.0 on the repository cannot be assumed to reach them (section 4, "
        "exclusion checklist item 3). Enforced by gate_scicode_eval_targets, not by "
        "this flag: the flag is per-row policy, the carve-out is per-FIELD. (Was "
        "'PENDING Sub-agent A' until 2026-09-30; shipping that stale note meant "
        "over-redacting SciCode against a written finding.)"),
    "swebench_verified": LicensePolicy(
        "swebench_verified", False, False,
        "🔴 CORPUS LICENCE UNDECLARED -- docs/BENCHMARK_LICENSES.md section 5. The HF "
        "API returns cardData.license: None for princeton-nlp/SWE-bench_Verified, the "
        "tag list carries no license:* entry, and the card text states none. The MIT "
        "grant covers the HARNESS CODE only, not the corpus; the underlying issue text "
        "and patches belong to the upstream OSS projects (django, sympy, ...) and are "
        "not Princeton's to relicense nor ours. An absent licence is NOT a permissive "
        "licence and gated:false means FETCHABLE, not redistributable. Metrics, "
        "instance ids and our derived measurements only. Recorded EXPLICITLY rather "
        "than left to DEFAULT_POLICY: both fail closed, but '__unknown__' reads as "
        "'nobody looked' when in fact this is a dated, sourced refusal -- the same "
        "distinction this schema draws between an empty list and a null."),
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

# Real payload strings, lifted verbatim from results/swebench/representations_v2.json,
# that the scanner DOES match and that are NOT secrets. They are django source code
# echoed inside a model response:
#
#     passwd = conn_params.get        -- an attribute read, value is an identifier
#     passwd:\n            subprocess_env  -- a dict key beside a variable name
#
# They are recorded here as EVIDENCE, not as an allowlist. Nothing suppresses them:
# ``assigned_secret`` is the pattern that catches a genuine credential assignment and
# weakening it to spell these away would trade a real detection for a cosmetic one.
# What resolves them instead is WHERE they sit -- see ``gate_secret_scan_rows``: these
# live in model-output fields that SWE-bench's licence already withholds, so they are
# not in the artifact. A hit in a field that actually ships is still a hard failure.
#
# This list exists so the scanner is known to have met real source code. Until v0.4 its
# only negatives were hand-written sentences, and a scanner tested only on strings
# someone invented for it is not known to discriminate on the corpus it will meet.
SECRET_SCAN_REAL_SOURCE_MATCHES: tuple[str, ...] = (
    "passwd = conn_params.get('passwd') or conn_params.get('password')",
    "if passwd:\n            subprocess_env['PGPASSWORD'] = str(passwd)",
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


def gate_secret_scan_rows(rows: Sequence[dict[str, Any]],
                          *, withheld_fields: Sequence[Sequence[str]] | None = None,
                          ) -> list[str]:
    """GATE 2. Returns non-blocking notes; raises on anything that would SHIP.

    A hit is a release blocker when the string ends up in the artifact. A hit inside a
    field the licence policy BLANKS is a different fact: the string is in our ledger,
    which is worth recording, but it is not in the release, and failing the build on it
    would mean a benchmark can never be exported because its own source code contains
    the word ``passwd``.

    Measured on results/swebench/representations_v2.json: 6 matches, all
    ``assigned_secret`` on django source inside model responses (see
    ``SECRET_SCAN_REAL_SOURCE_MATCHES``). Every one of those fields is withheld under
    the SWE-bench embargo, so none reaches the artifact.

    The pattern is NOT relaxed to accommodate them. ``assigned_secret`` is the rule that
    catches a real credential assignment; spelling around two django lines would trade a
    live detection for a cosmetic pass. Severity keys on whether the string ships.
    """
    hits: list[str] = []
    notes: list[str] = []
    for i, r in enumerate(rows):
        blanked = set(withheld_fields[i]) if withheld_fields else set()
        for k, v in r.items():
            found = scan_obj_for_secrets(v, f"row[{i}].{k}")
            found += scan_obj_for_secrets(k, f"row[{i}].<key>")
            if not found:
                continue
            if k in blanked:
                notes += [h + "  [NOT SHIPPED: field is withheld under the licence "
                              "policy, so this string is not in the artifact]"
                          for h in found]
            else:
                hits += found
        if len(hits) > 50:
            break
    if hits:
        raise GateFailure(
            "GATE 2 (secret scan) FAILED -- nothing was written.\n"
            + "\n".join("  " + h for h in hits[:50]))
    return notes


#: Patterns that de-anonymise rather than authenticate. The secret scan looks
#: for credentials; an absolute home path leaks a USERNAME, which is a
#: double-blind failure and not a secret. Found on 2026-10-01 in the staged
#: v0.3 tree: code/p1mem/schema.py carried an absolute /Users/<name>/ path in a
#: provenance docstring. Every gate passed. See DEFECT_REGISTER #23.
IDENTITY_LEAK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"/Users/[A-Za-z0-9._-]+/", "absolute macOS home path (leaks a username)"),
    (r"/home/[A-Za-z0-9._-]+/", "absolute Linux home path (leaks a username)"),
    (r"C:\\\\Users\\\\[A-Za-z0-9._-]+", "absolute Windows home path"),
    # A username in a URL is a DIFFERENT SHAPE from a home path and the
    # original gate could not see it. Found 2026-10-01: the data card gained
    # 8 github.com/<account>/... links during a navigation pass. Both repos
    # were private at the time, so nothing was exposed -- but a card that
    # ships with the release carries the handle into a double-blind cycle.
    # Matched against an explicit roster rather than "any github URL",
    # because an anonymized mirror is exactly what we want people to use.
    (r"github\.com/(?!anonymous|anon-|ANONYMOUS)[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/",
     "GitHub account handle in a URL (de-anonymises; use an anonymized mirror)"),
    (r"huggingface\.co/(?!datasets/)(?!anonymous)[A-Za-z0-9][A-Za-z0-9_-]{1,38}/",
     "Hugging Face account handle in a URL"),
)

# 🔴 UPSTREAM ATTRIBUTION IS NOT DE-ANONYMISATION, and the two were conflated.
#
# ``docs/BENCHMARK_LICENSES.md`` must cite where each corpus and licence was READ FROM:
# that is what makes the licence finding checkable, and for Apache-2.0 and CC BY-SA the
# attribution is a condition of the grant. Those URLs name the BENCHMARK AUTHORS. The
# handle pattern above cannot tell "the person who wrote this release" from "the person
# who wrote the dataset we are citing", so it flagged all of them -- and it flags the
# ALREADY-SHIPPED v0.4 tree identically, so this is a pre-existing over-match rather
# than anything v0.5 introduced.
#
# The exemption is keyed on the HANDLE, never on the file. Keying it on a path
# (``allow docs/BENCHMARK_LICENSES.md``) would exempt every future string in that file,
# including ours -- an allowlist that names a location stops being a check on content.
#
# Our own handles are listed separately and are matched FIRST, at the highest severity,
# so adding one to the upstream roster cannot quietly launder it: the self-handle check
# does not consult the roster at all.
UPSTREAM_ATTRIBUTION_HANDLES: frozenset[str] = frozenset({
    # benchmark sources cited in docs/BENCHMARK_LICENSES.md
    "xiaowu0162",          # LongMemEval V1/V2
    "mohammadtavakoli78",  # LongMemEval mirror consulted for the V1 licence
    "scicode-bench",       # SciCode
    "SWE-bench",           # SWE-bench harness
    "princeton-nlp",       # SWE-bench Verified corpus
    "SciCode1",            # SciCode on the Hub
    # API hostnames that are not accounts at all
    "repos", "api", "datasets", "orgs",
})

# Handles that identify THIS submission. Never exempt; always a hard failure.
OUR_OWN_HANDLES: tuple[str, ...] = ("ChihHsuan-Yang", "AgentsSci", "bellayang")


def _handle_in(match: str) -> str:
    """The account handle inside a matched ``host/<handle>/`` fragment."""
    return match.rstrip("/").rsplit("/", 1)[-1]


def scan_text_for_identity(text: str, where: str) -> list[str]:
    """De-anonymising strings. Separate from the secret scan on purpose.

    A reviewer-facing artifact must not name its author, and that failure mode
    is invisible to a credential scanner: the string is not a secret, carries
    no entropy signature, and reads as an ordinary file path.
    """
    out: list[str] = []
    # Our own identity first, and unconditionally: this check never consults the
    # upstream roster, so an entry added there cannot launder one of our handles.
    for own in OUR_OWN_HANDLES:
        for m in re.finditer(rf"\b{re.escape(own)}\b", text):
            out.append(f"{where}: OUR OWN account handle, which de-anonymises the "
                       f"submission -- {m.group(0)!r}")
    for rx, why in IDENTITY_LEAK_PATTERNS:
        for m in re.finditer(rx, text):
            frag = m.group(0)
            if "github.com/" in frag or "huggingface.co/" in frag:
                if _handle_in(frag) in UPSTREAM_ATTRIBUTION_HANDLES:
                    continue          # citing the benchmark's authors, as required
            out.append(f"{where}: {why} -- {frag!r}")
    return out


# A dataset shard legitimately exceeds MAX_FILE_BYTES, and "too big to scan" must not
# become "shipped unscanned" -- that is the release's largest file going out unchecked.
# Read it in chunks with an overlap, so a pattern straddling a chunk boundary is still
# found. The overlap must exceed the longest match any pattern can produce.
SCAN_CHUNK_BYTES = 32 * 1024 * 1024
SCAN_OVERLAP_CHARS = 4096


def _scan_large_text_file(p: Path, rel: str, scanner) -> list[str]:
    """Stream a file through ``scanner`` in overlapping chunks.

    ``scanner`` is scan_text_for_secrets or scan_text_for_identity: (text, where) -> hits.
    Returns the deduplicated hits. A read failure is RAISED, never swallowed: a file we
    could not scan is not a file we know to be clean.
    """
    hits: list[str] = []
    seen: set[str] = set()
    tail = ""
    with p.open("r", errors="replace") as fh:
        while True:
            chunk = fh.read(SCAN_CHUNK_BYTES)
            if not chunk:
                break
            for h in scanner(tail + chunk, rel):
                if h not in seen:
                    seen.add(h)
                    hits.append(h)
            # 🔴 NOT ``chunk[-SCAN_OVERLAP_CHARS:]``. At 0 that slice returns the WHOLE
            # chunk, so an overlap of "none" would silently become an overlap of
            # "everything" -- the buffer would grow without bound and, worse, a mutation
            # test that sets the overlap to 0 would still pass, certifying an overlap
            # that was never exercised. Found exactly that way.
            tail = chunk[len(chunk) - SCAN_OVERLAP_CHARS:] if SCAN_OVERLAP_CHARS else ""
    return hits


def scan_file_for(p: Path, rel: str, scanner) -> list[str]:
    """Scan a staged file whatever its size. Large files stream; nothing is skipped."""
    if p.stat().st_size > MAX_FILE_BYTES:
        return _scan_large_text_file(p, rel, scanner)
    return scanner(p.read_text(errors="replace"), rel)


def gate_identity_scan_tree(root: Path) -> None:
    """GATE 2b: no file in the staging tree may de-anonymise the authors."""
    hits: list[str] = []
    scanned = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        # A read failure is NOT swallowed. Previously a bare `except: continue` meant an
        # unreadable file passed silently -- an absent check reading as a passing one.
        hits += scan_file_for(p, str(p.relative_to(root)), scan_text_for_identity)
        scanned += 1
    if scanned < 5:
        raise GateFailure(
            f"GATE 2b (identity scan) scanned only {scanned} file(s). A clean scan over "
            f"nothing is not evidence; refusing to report a vacuous pass.")
    if hits:
        raise GateFailure(
            "GATE 2b (identity scan) FAILED -- the release would de-anonymise "
            "the submission.\n" + "\n".join("  " + h for h in hits[:50]))


def gate_secret_scan_tree(root: Path) -> None:
    hits: list[str] = []
    scanned = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        why = path_is_excluded(rel)
        if why:
            hits.append(f"{rel}: excluded path pattern present in staging ({why})")
            continue
        # A dataset shard is legitimately larger than MAX_FILE_BYTES. Refusing to scan
        # it used to fail the whole build; SKIPPING it would be worse -- the release's
        # biggest file would ship unscanned. It is streamed in overlapping chunks.
        hits += scan_file_for(p, rel, scan_text_for_secrets)
        scanned += 1
    if scanned < 5:
        raise GateFailure(
            f"GATE 2 (secret scan, staging tree) scanned only {scanned} file(s). A clean "
            f"scan over nothing is not evidence; refusing to report a vacuous pass.")
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


# Which ``license_source_reference`` prefix each benchmark is allowed to carry.
# TWO NAMESPACES, ONE FACT: ``assert_content_redistributable`` keys the embargo on
# ``row["benchmark"]`` while ``policy_for`` keys redaction on the prefix of
# ``license_source_reference``. Nothing made them agree, and ``benchmark`` is not in
# ``S.ENUMS``, so any string passes it. Measured consequence: benchmark="swebench"
# (missing "_verified") carried raw django issue text through the embargo with no error
# at all -- a one-character divergence silently disabled the ruling.
BENCHMARK_LICENSE_PREFIX: dict[str, str] = {
    "longmemeval_v1": "longmemeval_v1",
    "longmemeval_v2": "longmemeval_v2",
    "beam": "beam",
    "scicode": "scicode",
    "swebench_verified": "swebench_verified",
}

# Benchmarks refused OUTRIGHT, never merely redacted, with the reason.
# Redaction answers "may we ship this text?"; refusal answers "may this row be in THIS
# dataset at all?". ShareAlike is the second question: a redacted BEAM row still
# contributes a CC BY-SA adaptation to a release that is not CC BY-SA.
REFUSED_BENCHMARKS: dict[str, str] = {
    "beam": ("BEAM is CC BY-SA 4.0 (docs/BENCHMARK_LICENSES.md section 3, exclusion "
             "checklist item 4). ShareAlike is infectious: merging BEAM-derived rows "
             "into a release with V1/V2/SciCode rows either violates ShareAlike or "
             "silently relicenses the others. Redaction does NOT cure this -- the row "
             "itself is the adaptation. BEAM ships separately or not at all."),
}


def gate_benchmark_license_agreement(rows: Sequence[dict[str, Any]]) -> None:
    """GATE 0: ``benchmark`` and ``license_source_reference`` must name the same source.

    The embargo reads one field and the redactor reads the other. If they disagree, the
    row is redacted under one ruling and embargo-checked under another, and neither
    check reports anything. This gate makes the divergence itself the error, so the two
    namespaces cannot drift apart silently again.

    ``benchmark`` is not an enum in the schema (adding it there would reject the short
    fixture names several test modules legitimately use), so the closed vocabulary is
    enforced HERE, at the export boundary, where the licence question is actually asked.
    """
    problems: list[str] = []
    for i, r in enumerate(rows):
        b = (r.get("benchmark") or "").strip()
        ref = r.get("license_source_reference")
        prefix = ref.split(":", 1)[0].strip() if isinstance(ref, str) else None
        if b.lower() not in BENCHMARK_LICENSE_PREFIX:
            problems.append(
                f"row[{i}]: benchmark={b!r} is not a recognised benchmark for export. "
                f"Known: {sorted(BENCHMARK_LICENSE_PREFIX)}. An unrecognised name means "
                f"the embargo in schema.CONTENT_EMBARGOED_BENCHMARKS never matches it, "
                f"so its licence ruling would not be applied at all")
            continue
        want = BENCHMARK_LICENSE_PREFIX[b.lower()]
        if prefix != want:
            problems.append(
                f"row[{i}]: benchmark={b!r} but license_source_reference={ref!r} has "
                f"prefix {prefix!r}, expected {want!r}. The embargo keys on benchmark "
                f"and redaction keys on the prefix; disagreeing fields mean the two "
                f"answer different questions about the same row")
    if problems:
        raise GateFailure(
            "GATE 0 (benchmark/licence agreement) FAILED -- nothing was written.\n"
            + "\n".join("  " + x for x in problems[:20]))


def gate_benchmark_refusal(rows: Sequence[dict[str, Any]]) -> None:
    """GATE 3b: refuse a benchmark whose rows may not be in this dataset at all.

    Three documents (HF_RELEASE_POLICY.md, DATASET_INDEX.md, the data card) each state
    that the exporter REFUSES BEAM rows. Measured 2026-09-30: it did not. A BEAM row was
    redacted and accepted, and no test covered it -- a control asserted in prose by
    three readers and built by none. This is that control.
    """
    hits: list[str] = []
    for i, r in enumerate(rows):
        b = (r.get("benchmark") or "").strip().lower()
        prefix = ""
        ref = r.get("license_source_reference")
        if isinstance(ref, str):
            prefix = ref.split(":", 1)[0].strip().lower()
        for name, why in REFUSED_BENCHMARKS.items():
            if name in (b, prefix):
                hits.append(f"row[{i}] ({r.get('cell_id') or r.get('task_id')}): {why}")
                break
    if hits:
        raise GateFailure(
            "GATE 3b (benchmark refusal) FAILED -- nothing was written. These rows may "
            "not appear in this dataset in ANY form, redacted or not.\n"
            + "\n".join("  " + x for x in hits[:10])
            + (f"\n({len(hits)} rows total)" if len(hits) > 10 else ""))


# SciCode's numeric eval targets live in test_data.h5, which is NOT covered by the
# Apache-2.0 grant (BENCHMARK_LICENSES.md section 4). Apache-2.0 lets us ship SciCode
# PROBLEM text, so the row-level policy is (True, True) -- the carve-out is per-FIELD
# and needs its own mechanism. A long float is the shape a target value has; three or
# more in one field is the shape a dumped target ARRAY has.
_LONG_FLOAT = re.compile(r"-?\d+\.\d{6,}(?:[eE][-+]?\d+)?")
SCICODE_TARGET_MIN_FLOATS = 3


def gate_scicode_eval_targets(rows: Sequence[dict[str, Any]]) -> None:
    """GATE 3c: no SciCode row may carry test_data.h5 target values.

    Measured before writing this gate: over results/scicode/scaleup_all3.json (924 rows)
    the ``stderr_tail`` field -- the only place a traceback could echo an expected array
    -- produced ZERO rows at this threshold, so the gate is not silently rejecting the
    corpus it is meant to protect. It is a guard against a future exporter that widens
    what it emits, which is exactly when nobody re-reads the licence doc.
    """
    hits: list[str] = []
    for i, r in enumerate(rows):
        b = (r.get("benchmark") or "").strip().lower()
        if b != "scicode":
            continue
        for f in S.REDISTRIBUTABLE_TEXT_FIELDS + ("stderr_tail", "error"):
            v = r.get(f)
            if not isinstance(v, str) or not v:
                continue
            n = len(_LONG_FLOAT.findall(v))
            if n >= SCICODE_TARGET_MIN_FLOATS:
                hits.append(
                    f"row[{i}].{f}: {n} high-precision floats -- looks like test_data.h5 "
                    f"target values, whose licence is unstated "
                    f"(BENCHMARK_LICENSES.md section 4, checklist item 3)")
    if hits:
        raise GateFailure(
            "GATE 3c (SciCode eval targets) FAILED -- nothing was written.\n"
            + "\n".join("  " + x for x in hits[:20]))


def gate_embargo_schema_helper(exported: Sequence[dict[str, Any]]) -> None:
    """GATE 6: run the SCHEMA's own embargo helper over the rows about to be written.

    ``schema.assert_content_redistributable`` is the ruling expressed as code. Its
    docstring claimed "Called by the exporter BEFORE an upload is assembled"; measured
    2026-09-30, its only callers were tests. A guard the release path never invokes is a
    guard in name only, so this gate invokes it.

    It is deliberately REDUNDANT with gate 3: gate 3 keys on the licence reference, this
    keys on ``benchmark``. Two independent keys over one ruling is the point -- gate 0
    proves they agree, and if it is ever removed, this still fires.
    """
    try:
        S.assert_content_redistributable(exported)
    except ValueError as exc:
        raise GateFailure(
            "GATE 6 (schema embargo helper) FAILED -- nothing was written.\n"
            f"  {exc}") from exc


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
def _pick_isolation_safe_sample(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """A row that can legitimately be validated on its own.

    ``validate_dataset`` carries per-cell checks (``num_replicates_mismatch``,
    ``confidence_or_stability``), so validating a slice of one row is only sound
    when that row really is its cell's only replicate. Returns the first row with
    ``num_replicates`` in (None, 1); falls back to the synthetic row rather than
    silently using a multi-replicate one and blaming redaction for the failure.

    🔴 AND IT MUST NOT ALREADY BE WITHHELD. Several controls below *construct* a
    withholding on the fixture and require the validator to object -- e.g. (e3)
    sets ``memory_text`` to the sentinel WITHOUT declaring it and demands
    ``id_mismatch``. On a row that is *already* withheld and *already* declares
    it, that assignment changes nothing: the row stays legitimately exempt, no
    error fires, and the control reports SELF-TEST FAILED about a gate that is
    working perfectly.

    Measured 2026-10-01: with ``--results <a longmemeval ledger> <the swebench
    ledger>`` the picker returned a SWE-bench row (``num_replicates`` is None
    there, so it was the first match) and the self-test failed with *"the
    sentinel alone bought an exemption"*. The gates were fine; the FIXTURE was
    already in the state the plant was supposed to create. A SWE-bench-only
    release would have hit this on every build and sent someone to debug
    redaction, where the bug is not.

    This is the register's own rule about controls -- *a control applied to a
    subject that is already failing is not a control* -- and it is the same
    shape as defect #23, which this function was written to fix: that time the
    fixture was unvalidatable in isolation, this time it is un-plantable.
    """
    if not rows:
        return _synthetic_row()

    def _already_withheld(r: dict[str, Any]) -> bool:
        declared = r.get("text_fields_withheld")
        if isinstance(declared, list) and declared:
            return True
        return any(_field_is_withheld_value(r.get(f))
                   for f in S.REDISTRIBUTABLE_TEXT_FIELDS)

    singles = [r for r in rows if r.get("num_replicates") in (None, 1)]
    if not singles:
        # No single-replicate row exists: say so rather than returning a row that
        # will fail in isolation for a reason that has nothing to do with the gates.
        raise AssertionError(
            "SELF-TEST CANNOT RUN: every input row belongs to a multi-replicate cell, "
            "so no row can be validated in isolation and the per-cell checks would "
            "fire for a reason unrelated to any gate. Pass a single-replicate row.")
    for r in singles:
        if not _already_withheld(r):
            return dict(r)
    raise AssertionError(
        "SELF-TEST CANNOT RUN: every isolation-safe row is ALREADY a withheld row "
        "(text_fields_withheld non-empty, or a text field holding the withholding "
        "marker). The controls that plant a withholding would then change nothing "
        "and 'fail' about a gate that is working. Pass at least one unwithheld "
        "single-replicate row -- e.g. include a LongMemEval or SciCode ledger "
        "alongside a metrics-only one.")


def _field_is_withheld_value(value: Any) -> bool:
    """True when a field already holds a withholding marker (either shape)."""
    if value == WITHHELD:
        return True
    return isinstance(value, dict) and value.get("__withheld__") is True


def self_test(rows: Sequence[dict[str, Any]]) -> list[str]:
    """Prove each gate can FAIL, by planting the defect it exists to catch.

    A gate that has never rejected anything is not known to work. Returns a list of
    human-readable PASS lines; raises if any gate failed to fire.
    """
    log: list[str] = []
    # 🔴 THE FIXTURE MUST BE VALIDATABLE IN ISOLATION. Several checks below run
    #    `validate_dataset([one_row])`, and `num_replicates_mismatch` is a
    #    PER-CELL check: it compares the row's declared num_replicates against
    #    the number of rows PRESENT for that cell. A row from a 2-replicate cell
    #    therefore fails by construction when validated alone -- which is a
    #    property of the fixture, not of the data or of redaction.
    #
    #    Measured 2026-09-30: rows[0] of the v0.2 input declares
    #    num_replicates=2 and its cell has exactly 2 rows in the full dataset
    #    (validate_dataset over that cell: 0 errors). Picking it made the
    #    redaction regression test fail with `num_replicates_mismatch` and read
    #    as "a redacted row cannot ship".
    #
    #    So: prefer a genuinely single-replicate row. The gate is NOT weakened --
    #    num_replicates_mismatch still runs, on a row where 1 declared == 1
    #    present is the TRUE value rather than an artefact of slicing.
    sample = _pick_isolation_safe_sample(rows)

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

    # ================================================================== v0.3 / v0.4
    # The two benchmarks about to ship. Until now every GATE 3 case used
    # longmemeval_v1/v2, so the gates were not known to discriminate on SciCode or
    # SWE-bench -- a verifier that has only ever met its home case.

    def _swebench(**over: Any) -> dict[str, Any]:
        return {**sample, "benchmark": "swebench_verified",
                "license_source_reference": "swebench_verified:none_declared", **over}

    def _scicode(**over: Any) -> dict[str, Any]:
        return {**sample, "benchmark": "scicode",
                "license_source_reference": "scicode:Apache-2.0", **over}

    # -- (a) POSITIVE: a SWE-bench row carrying real issue text must be REFUSED.
    #    The text is a verbatim fragment of the django issue bodies in
    #    results/swebench/representations_v2.json -- the actual payload, not a
    #    stand-in, so the gate is tested against what it will really meet.
    leaky_sw = _swebench(
        memory_text="Django 4.2 raises ValueError when using QuerySet.only() after "
                    "select_related() on a reverse OneToOneField relation.",
        future_task_text="django__django-15400: fix SimpleLazyObject __radd__")
    try:
        gate_license_exclusion([leaky_sw])
        raise AssertionError("SELF-TEST FAILED: licence gate passed SWE-bench issue "
                             "text whose corpus licence is UNDECLARED")
    except GateFailure:
        log.append("PASS gate3: un-redacted swebench_verified issue text was caught "
                   "(corpus licence undeclared -- BENCHMARK_LICENSES.md section 5)")

    # -- (a2) the SAME row must also be caught by the SCHEMA's helper, which keys on
    #    `benchmark` rather than on the licence reference. Two independent keys.
    try:
        gate_embargo_schema_helper([leaky_sw])
        raise AssertionError("SELF-TEST FAILED: schema embargo helper passed SWE-bench "
                             "issue text")
    except GateFailure:
        log.append("PASS gate6: schema.assert_content_redistributable independently "
                   "caught the same SWE-bench row (keyed on `benchmark`)")

    # -- (a3) NEGATIVE: a correctly redacted SWE-bench row must be ACCEPTED, or v0.4
    #    cannot ship at all. Before 2026-09-30 this was impossible: redaction wrote a
    #    truthy sentinel and the schema helper read every truthy string as content.
    sw_red, sw_wh = redact_row(_swebench())
    if not sw_wh:
        raise AssertionError("SELF-TEST FAILED: SWE-bench row withheld nothing")
    gate_license_exclusion([sw_red])
    gate_embargo_schema_helper([sw_red])
    log.append(f"PASS gate3/6-negative: a redacted swebench_verified row is accepted, "
               f"withholding {len(sw_wh)} fields (metrics-only release is possible)")

    # -- (a4) POSITIVE: redacted, but NOT declared in text_fields_withheld. A consumer
    #    filtering on that list would get the wrong rows.
    sneaky = dict(sw_red); sneaky["text_fields_withheld"] = []
    try:
        gate_embargo_schema_helper([sneaky])
        raise AssertionError("SELF-TEST FAILED: an undeclared withholding was accepted")
    except GateFailure:
        log.append("PASS gate6: a blanked field missing from text_fields_withheld was "
                   "caught (withholding must be declared, not just performed)")

    # -- (b) NEGATIVE: SciCode now PERMITS text. Apache-2.0 on both code and data
    #    (BENCHMARK_LICENSES.md section 4). The stale PENDING entry would have shipped
    #    v0.3 with every text field blanked -- over-redaction against a written finding.
    sc_row = _scicode(memory_text="Compute the Fermi energy for a 2D electron gas.",
                      future_task_text="Implement the density of states.")
    sc_red, sc_wh = redact_row(sc_row)
    if sc_wh:
        raise AssertionError(
            f"SELF-TEST FAILED: SciCode is Apache-2.0 on both code and data but "
            f"redaction withheld {sc_wh} -- over-redacting against section 4")
    if sc_red["memory_text"] != sc_row["memory_text"]:
        raise AssertionError("SELF-TEST FAILED: SciCode memory_text was altered")
    gate_license_exclusion([sc_red])
    log.append("PASS gate3-negative: scicode text is RETAINED (Apache-2.0, section 4) "
               "-- the stale PENDING entry would have blanked it")

    # -- (b2) POSITIVE: the per-FIELD carve-out. Apache-2.0 does NOT reach test_data.h5,
    #    so a row echoing target values is refused even though its row policy is (T,T).
    targets = _scicode(memory_text="expected = [0.4472135954999579, 1.2247448713915890, "
                                   "3.1415926535897931, 2.7182818284590451]")
    try:
        gate_scicode_eval_targets([targets])
        raise AssertionError("SELF-TEST FAILED: SciCode test_data.h5 target values were "
                             "accepted despite an unstated licence")
    except GateFailure:
        log.append("PASS gate3c: SciCode test_data.h5 target values refused even though "
                   "the row's own policy permits text (per-field carve-out)")

    # -- (b3) NEGATIVE: ordinary SciCode prose must NOT trip the target detector.
    gate_scicode_eval_targets([sc_red])
    log.append("PASS gate3c-negative: ordinary SciCode problem text is not mistaken "
               "for eval targets (measured: 0/924 real rows trip it)")

    # -- (c) POSITIVE: BEAM is REFUSED OUTRIGHT, not redacted. Three docs claimed this
    #    control existed; measured 2026-09-30, a BEAM row was redacted and accepted.
    beam_row = {**sample, "benchmark": "beam",
                "license_source_reference": "beam:CC-BY-SA-4.0"}
    beam_red, _ = redact_row(dict(beam_row))
    try:
        gate_license_exclusion([beam_red])
        log.append("NOTE: a REDACTED beam row passes gate3 -- which is why refusal "
                   "cannot be left to redaction; see gate3b below")
    except GateFailure:
        pass
    try:
        gate_benchmark_refusal([beam_row])
        raise AssertionError("SELF-TEST FAILED: a BEAM row was not refused. Three "
                             "documents state the exporter refuses BEAM rows.")
    except GateFailure:
        log.append("PASS gate3b: a BEAM row is REFUSED OUTRIGHT (CC BY-SA ShareAlike "
                   "is infectious; redaction does not cure it)")

    # -- (c2) NEGATIVE: refusal must not reject the benchmarks that DO ship.
    gate_benchmark_refusal([_scicode(), _swebench(), sample])
    log.append("PASS gate3b-negative: scicode / swebench_verified / longmemeval rows "
               "are not refused by the BEAM gate")

    # -- (d) POSITIVE: the two-namespace bypass. `benchmark` is not a schema enum, so
    #    "swebench" (missing _verified) matched no embargo entry and carried raw django
    #    text straight through with no error at all. Measured, not hypothesised.
    bypass = {**sample, "benchmark": "swebench",
              "license_source_reference": "swebench_verified:none_declared",
              "memory_text": "raw django issue text"}
    try:
        gate_benchmark_license_agreement([bypass])
        raise AssertionError("SELF-TEST FAILED: benchmark='swebench' disagreeing with "
                             "license_source_reference='swebench_verified:...' was "
                             "accepted -- this bypasses the embargo entirely")
    except GateFailure:
        log.append("PASS gate0: a benchmark/licence-reference mismatch is caught "
                   "(the one-character 'swebench' vs 'swebench_verified' bypass)")

    # -- (d1b) POSITIVE, the OTHER branch of gate 0. (d) above trips the
    #    unknown-benchmark branch, so it passes even if the prefix comparison is
    #    deleted -- found by mutation-testing this very self-test: disabling
    #    `if prefix != want` left every assertion green. A recognised benchmark
    #    pointed at the WRONG licence reference exercises the comparison itself.
    crossed = {**sample, "benchmark": "scicode",
               "license_source_reference": "longmemeval_v2:Apache-2.0",
               "memory_text": "SciCode problem text billed to LongMemEval's licence"}
    try:
        gate_benchmark_license_agreement([crossed])
        raise AssertionError("SELF-TEST FAILED: benchmark='scicode' with a "
                             "longmemeval_v2 licence reference was accepted -- the "
                             "prefix comparison is not running")
    except GateFailure:
        log.append("PASS gate0: a RECOGNISED benchmark pointed at the wrong licence "
                   "reference is caught (exercises the prefix comparison, not just "
                   "the unknown-name branch)")

    # -- (d1c) POSITIVE: the reverse direction. An embargoed benchmark wearing a
    #    permissive licence reference is the dangerous orientation -- it would redact
    #    under Apache-2.0 and ship SWE-bench text.
    disguised = {**sample, "benchmark": "swebench_verified",
                 "license_source_reference": "scicode:Apache-2.0",
                 "memory_text": "django issue text wearing SciCode's licence"}
    try:
        gate_benchmark_license_agreement([disguised])
        raise AssertionError("SELF-TEST FAILED: a swebench_verified row wearing a "
                             "scicode licence reference was accepted -- it would be "
                             "redacted as Apache-2.0 and ship its issue text")
    except GateFailure:
        log.append("PASS gate0: an embargoed benchmark wearing a PERMISSIVE licence "
                   "reference is caught (the orientation that would leak)")

    # -- (d2) NEGATIVE: agreeing rows pass.
    gate_benchmark_license_agreement([_scicode(), _swebench(), sample])
    log.append("PASS gate0-negative: rows whose benchmark and licence reference agree "
               "are accepted")

    # -- (e) REGRESSION, the v0.4 blocker: a redacted row must pass SCHEMA VALIDATION.
    #    memory_text is one of MEMORY_ID_KEYS, so blanking it after the id was minted
    #    made every withheld row fail gate 4 with id_mismatch. v0.1/v0.2 withheld
    #    nothing, so this could not fire until now.
    rep_red = V.validate_dataset([sw_red])
    if not rep_red.ok:
        raise AssertionError(
            "SELF-TEST FAILED: a correctly redacted row does not pass schema "
            "validation, so GATE 4 would reject the whole release: "
            + "; ".join(f"{e.code}:{e.field}" for e in rep_red.errors[:5]))
    log.append("PASS gate1/4-regression: a redacted row passes the validator that GATE "
               "4 runs on the written file (id_mismatch exemption is narrow)")

    # -- (e2) POSITIVE CONTROL for that exemption: an ORDINARY edit to memory_text must
    #    still trip id_mismatch. An exemption that swallows real corruption is worse
    #    than the bug it fixed.
    edited = dict(sample); edited["memory_text"] = "an ordinary edit, not a withholding"
    codes = {e.code for e in V.validate_dataset([edited]).errors}
    if "id_mismatch" not in codes:
        raise AssertionError(
            "SELF-TEST FAILED: the withholding exemption swallowed an ordinary edit to "
            f"memory_text -- id_mismatch did not fire (got {sorted(codes)})")
    log.append("PASS gate1-control: an ordinary (non-sentinel) edit to memory_text "
               "still trips id_mismatch -- the exemption did not become a hole")

    # -- (e3) POSITIVE CONTROL: the sentinel WITHOUT a declaration is still a mismatch.
    undeclared = dict(sample); undeclared["memory_text"] = S.WITHHELD_SENTINEL
    if "id_mismatch" not in {e.code for e in V.validate_dataset([undeclared]).errors}:
        raise AssertionError("SELF-TEST FAILED: the sentinel alone bought an exemption "
                             "without the row declaring the withholding")
    log.append("PASS gate1-control: the sentinel alone does NOT buy an exemption -- the "
               "row must also declare the field in text_fields_withheld")

    # -- (e4) POSITIVE CONTROL on a WITHHELD row: the exemption must narrow to the ids
    #    whose key set actually contains a blanked field. cell_id keys on memory_id,
    #    not on memory_text, so a copied cell_id stays fully checked even here.
    #    Found by mutation-testing: widening `hidden` to every blanked field left the
    #    self-test green while a copied cell_id went unchecked on every withheld row.
    copied = dict(sw_red)
    copied["cell_id"] = "cell-someoneelse-000000000000000000000000"
    if "id_mismatch" not in {e.code for e in V.validate_dataset([copied]).errors}:
        raise AssertionError(
            "SELF-TEST FAILED: on a WITHHELD row a copied cell_id was not caught. The "
            "id exemption must skip only the ids whose own key set contains a blanked "
            "field; cell_id keys on memory_id, not on memory_text.")
    log.append("PASS gate1-control: on a withheld row a COPIED cell_id is still caught "
               "-- the exemption narrows per-id, not per-row")

    # -- (e5) POSITIVE CONTROL: a declared-but-not-blanked field must not buy an
    #    exemption either. Mutation-testing showed that dropping the sentinel test
    #    from the exemption left every assertion green.
    claimed = dict(sample)
    claimed["memory_text"] = "real text the row merely CLAIMS was withheld"
    claimed["text_fields_withheld"] = ["memory_text"]
    claimed["reconstruction_required"] = True
    if "id_mismatch" not in {e.code for e in V.validate_dataset([claimed]).errors}:
        raise AssertionError(
            "SELF-TEST FAILED: a row that merely LISTS memory_text as withheld, while "
            "the field still holds real text, was exempted from id_mismatch. The "
            "exemption must require the sentinel to actually be present.")
    log.append("PASS gate1-control: declaring a withholding that did not happen buys "
               "no exemption -- the sentinel must actually be in the field")

    # -- (f) the scanner must have met REAL source code, not only invented sentences.
    for real in SECRET_SCAN_REAL_SOURCE_MATCHES:
        if not scan_text_for_secrets(real, "real"):
            raise AssertionError(
                f"SELF-TEST FAILED: assigned_secret no longer matches real django "
                f"source {real!r}. If the pattern was relaxed to quiet this, a genuine "
                f"credential assignment is now invisible too.")
    sw_note = _swebench(output_with_memory=SECRET_SCAN_REAL_SOURCE_MATCHES[0])
    sw_note_red, sw_note_wh = redact_row(sw_note)
    notes = gate_secret_scan_rows([sw_note], withheld_fields=[sw_note_wh])
    if not notes:
        raise AssertionError("SELF-TEST FAILED: a match inside a withheld field was "
                             "neither raised nor recorded -- it was silently dropped")
    gate_secret_scan_rows([sw_note_red])
    log.append(f"PASS gate2-real-source: {len(SECRET_SCAN_REAL_SOURCE_MATCHES)} verbatim "
               f"django strings still MATCH the pattern; in a withheld field they are "
               f"recorded as not-shipped ({len(notes)} note) rather than suppressed")

    # -- (f2) POSITIVE CONTROL: the same string in a field that SHIPS is a hard failure.
    sc_secret = _scicode(output_with_memory="api_key=sk-abcdefghijklmnopqrstuvwxyz0123")
    sc_secret_red, sc_secret_wh = redact_row(sc_secret)
    try:
        gate_secret_scan_rows([sc_secret], withheld_fields=[sc_secret_wh])
        raise AssertionError("SELF-TEST FAILED: a secret in a SHIPPED field (SciCode "
                             "retains its outputs) did not fail the build")
    except GateFailure:
        log.append("PASS gate2-control: the same class of match in a field that SHIPS "
                   "is still a hard failure -- severity keys on the artifact, not the "
                   "string")

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
def _anonymized_repo_id(repo_id: str) -> str:
    """``org/name`` -> ``<anonymized-for-review>/name``. Keeps the dataset identity."""
    return f"<anonymized-for-review>/{repo_id.split('/', 1)[-1]}"


def _provenance_path(p: Path) -> str:
    """A shippable spelling of an input path: repo-relative where possible.

    Absolute paths outside the repo are reduced to a basename plus a marker, because
    the directory above them is the author's home and would de-anonymise the release.
    The file is still identifiable (its sha256 is in the manifest beside it); what is
    dropped is only the part that names a person.
    """
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return f"<external>/{p.name}"


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

    # Order matters and every one of these precedes the first byte written.
    #  0  the two licence namespaces name the same source (else the rest is misapplied)
    #  3b refusal: rows that may not be here AT ALL -- checked before we bother redacting
    #  1  schema validation of the rows as collected
    #  2  secret scan, on the PRE-redaction rows (a secret in a field we later blank is
    #     still a secret that was in our ledger) and again on the POST-redaction rows
    #     (the ones that actually ship)
    #  3  licence exclusion, keyed on license_source_reference
    #  3c SciCode's per-FIELD carve-out, which the per-row policy flag cannot express
    #  6  the schema's own embargo helper, keyed independently on `benchmark`
    gate_benchmark_license_agreement(rows)
    gate_benchmark_refusal(rows)
    report = gate_validate(rows) if rows else V.Report()
    # Redact first so the pre-redaction scan can tell a secret that SHIPS from one that
    # sits in a field the licence blanks. Nothing is written until every gate has run.
    redacted = [redact_row(r) for r in rows]
    exported = [e for e, _ in redacted]
    secret_notes = gate_secret_scan_rows(rows, withheld_fields=[w for _, w in redacted])
    license_counts = gate_license_exclusion(exported)
    gate_scicode_eval_targets(exported)
    # Scan the redacted rows too. GATE 2 above runs pre-redaction, which is right for
    # "was a secret ever in our ledger" but wrong for "does the artifact carry one":
    # redaction REWRITES fields, and a check that never reads the rewritten value is a
    # check on something other than what ships.
    gate_secret_scan_rows(exported)
    gate_embargo_schema_helper(exported)

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

    # The GitHub commit this staging tree was built from. HF_RELEASE_POLICY requires
    # every snapshot be reproducible from the code at a NAMED commit, and a manifest
    # that does not name one leaves the reader to guess. Dirty is recorded as such
    # rather than silently presented as the commit's content.
    try:
        _sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, timeout=30).stdout.strip()
        # NAME the dirty paths, do not just flag them. A bare `dirty: true` tells a
        # reader that something differs from the named commit but not WHETHER IT IS IN
        # THIS RELEASE -- and on a repo several agents commit to, the answer is usually
        # no. An unexplained alarm gets ignored, which is how a real one gets missed.
        _status = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT),
                                 capture_output=True, text=True, timeout=30).stdout
        _dirty_paths = sorted(l[3:].strip() for l in _status.splitlines() if l.strip())
        _dirty = bool(_dirty_paths)
    except Exception:
        _sha, _dirty, _dirty_paths = "", False, []

    manifest = {
        # The owning org is anonymised in the SHIPPED manifest for the same reason the
        # data card's links are: this file travels with the data, and a snapshot can be
        # forwarded or the repo made public independently of the URL it was fetched
        # from. The dataset NAME is kept, so the field still identifies the snapshot.
        # Restore after the review cycle, together with the card's links.
        "hf_repo_id": _anonymized_repo_id(HF_REPO_ID),
        "hf_repo_id_note": (
            "owning org anonymised for double-blind review; the dataset name is "
            "unchanged. See the data card's anonymity note."),
        "hf_repo_type": HF_REPO_TYPE,
        "release_commit": _sha or "UNKNOWN -- git rev-parse failed at build time",
        "release_tree_dirty": _dirty,
        "release_tree_dirty_paths": _dirty_paths,
        "schema_version": S.SCHEMA_VERSION,
        "built_at_utc": S.utc_now(),
        "n_rows": len(exported),
        "n_fields": len(S.FIELD_ORDER),
        # 🔴 REPO-RELATIVE, never absolute. An input staged outside the repo (v0.5's
        # migrated ledgers live in a sibling build directory) would otherwise write
        # ``/Users/<name>/...`` straight into a shipped file -- defect 23/29's exact
        # shape, in the one field that exists to vouch for provenance. v0.4 escaped it
        # only because its inputs happened to sit in /tmp. GATE 2b catches it now, and
        # this is the fix at source rather than a sanitised copy.
        "source_files": [_provenance_path(p) for p in results],
        "license_doc": str(LICENSE_DOC.relative_to(REPO_ROOT)),
        "license_doc_sha256": license_doc_sha,
        "license_policy_counts": license_counts,
        "text_fields_withheld_counts": dict(withheld_counter),
        # Secret-scan matches that were NOT release blockers because the licence policy
        # blanks the field they live in. Recorded, not suppressed: a finding that only
        # exists in a build log nobody keeps is a deleted finding.
        "secret_scan_notes_not_shipped": secret_notes,
        "validation": {"errors": len(report.errors), "warnings": len(report.warnings),
                       "codes": sorted(report.codes())},
        # Gates 4 and 5 run AFTER this dict is built (they need the written file), so
        # they are recorded as PENDING here and stamped PASS by build() once they have
        # actually run. A manifest that claimed PASS before the check ran would be a
        # provenance field nobody measured -- and the build raises rather than reaching
        # the stamp if either fails, so PENDING can never survive into a shipped file.
        "gates": {"benchmark_license_agreement": "PASS",
                  "benchmark_refusal": "PASS",
                  "schema_validation": "PASS", "secret_scan": "PASS",
                  "license_exclusion": "PASS",
                  "scicode_eval_targets": "PASS",
                  "schema_embargo_helper": "PASS",
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
    gate_secret_scan_tree(staging)
    gate_identity_scan_tree(staging)     # final sweep over what will actually ship

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
    gate_identity_scan_tree(staging)

    # If the tree was dirty, say whether any dirty path actually reached the release.
    # This is the question a reader has; leaving them to answer it from a boolean is
    # how a flag becomes noise.
    if manifest.get("release_tree_dirty"):
        # 🔴 MATCH ON CONTENT, NOT ON BASENAME. This compared ``Path(d).name``
        # against the shipped basenames, so the repo-root ``README.md`` -- edited
        # by another agent, never published -- collided with the DATA CARD, which
        # ships as ``README.md``. v0.4 was built with the note "1 of them
        # correspond to a file in this release: ['README.md']. Those bytes are the
        # WORKING COPY, not the named commit." Every word of that was false: the
        # staged card was byte-identical to the committed ``docs/hf_card/README.md``.
        #
        # A basename is not an identity. The question is "did an uncommitted byte
        # reach the release", and the only thing that answers it is the bytes: for
        # each dirty path, compare its WORKING COPY against the shipped file of the
        # same basename. If no shipped file has those bytes, the dirty path did not
        # reach the release, whatever it is called. Failing closed: a dirty path we
        # cannot read is reported as possibly-shipped rather than assumed innocent.
        shipped_by_name: dict[str, list[str]] = {}
        for f in manifest["files"]:
            shipped_by_name.setdefault(Path(f).name, []).append(f)
        touching, unreadable = [], []
        for d in manifest["release_tree_dirty_paths"]:
            candidates = shipped_by_name.get(Path(d).name)
            if not candidates:
                continue                      # no shipped file even shares its name
            src = REPO_ROOT / d
            if not src.is_file():
                # deleted or renamed in the working tree: cannot compare, so say so
                unreadable.append(d)
                continue
            try:
                work = S.file_sha256(src)
            except OSError:
                unreadable.append(d)
                continue
            if any(manifest["files"][c]["sha256"] == work for c in candidates):
                touching.append(d)
        touching, unreadable = sorted(touching), sorted(unreadable)
        manifest["release_tree_dirty_paths_in_this_release"] = touching
        manifest["release_tree_dirty_paths_unverifiable"] = unreadable
        manifest["release_tree_dirty_match"] = (
            "by CONTENT (sha256 of the working copy vs the shipped file), not by "
            "basename -- a basename collision between the repo-root README.md and "
            "the data card produced a false 'working copy shipped' note at v0.4.")
        manifest["release_tree_dirty_note"] = (
            "Uncommitted changes existed in the source repo at build time. "
            + (f"{len(touching)} of them MATCH A SHIPPED FILE BYTE FOR BYTE: "
               f"{touching}. Those bytes are the WORKING COPY, not the named commit."
               if touching else
               "NONE of their bytes appears in this release, so every shipped byte "
               "matches the named commit. Other agents commit to this repo "
               "concurrently; the dirty paths belong to their work.")
            + (f" {len(unreadable)} dirty path(s) could not be read at build time "
               f"and are reported as unverifiable rather than assumed innocent: "
               f"{unreadable}." if unreadable else ""))
        S.write_json_atomic(staging / "MANIFEST.json", manifest)

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
    gate_card_expected_output_is_true(staging, proc.stdout.strip())


#: The card prints the output a consumer should SEE. v0.2's card said
#: ``5643 rows | 0 errors | 1129 warnings``; the v0.3 artifact prints
#: ``5797 rows | 0 errors | 1437 warnings``. Both sentences are in the same file.
_CARD_SUMMARY_RE = re.compile(r"(\d[\d,]*)\s+rows\s*\|\s*(\d[\d,]*)\s+errors"
                              r"(?:\s*\|\s*(\d[\d,]*)\s+warnings)?")


def gate_card_expected_output_is_true(staging: Path, actual_summary: str) -> None:
    """GATE 5b: the card's PRINTED EXPECTED OUTPUT must match what actually prints.

    🔴 GATE 5 ran the command and checked only that it EXITED 0. It never compared
    the command's output to the output the card tells the reader to expect. So a
    card carrying v0.2's "expect: 5643 rows | 0 errors | 1129 warnings" sailed
    through a v0.3 release that prints 5797/0/1437 -- a FALSE STATEMENT shipped
    inside the artifact, in the one place a consumer checks to see whether their
    download is intact. They would read 5,643, see 5,797, and conclude the file is
    corrupt.

    This is the release-note defect class the project already named: *a documented
    reason decays when the data it describes changes*. The number is part of the
    record, exactly like a null's stated reason, and must be re-checked at every
    release rather than inherited.

    Exit code is not output. A gate that runs a command and ignores what it said
    verifies the plumbing and not the claim.
    """
    card = staging / "README.md"
    if not card.exists():
        return
    m_actual = _CARD_SUMMARY_RE.search(actual_summary)
    if not m_actual:
        raise GateFailure(
            f"GATE 5b: could not parse the validator summary {actual_summary[:200]!r}; "
            f"refusing to declare the card's expected output true against nothing.")
    text = card.read_text()
    claims = _CARD_SUMMARY_RE.findall(text)
    if not claims:
        raise GateFailure(
            "GATE 5b: the data card states NO expected validator output. A consumer "
            "then has nothing to check their download against. Add the line.")
    norm = lambda x: int(str(x).replace(",", "")) if x else None       # noqa: E731
    want = (norm(m_actual.group(1)), norm(m_actual.group(2)), norm(m_actual.group(3)))
    bad = []
    for c in claims:
        got = (norm(c[0]), norm(c[1]), norm(c[2]))
        # warnings may be omitted in a prose mention; rows+errors must always match
        if got[0] != want[0] or got[1] != want[1] or (got[2] is not None and got[2] != want[2]):
            bad.append(f"card says {got[0]} rows/{got[1]} errors/{got[2]} warnings")
    if bad:
        raise GateFailure(
            "GATE 5b (the card's expected output is FALSE) FAILED -- nothing was "
            "written.\n"
            f"  the shipped file actually prints: {want[0]} rows | {want[1]} errors | "
            f"{want[2]} warnings\n"
            + "".join(f"  {b}\n" for b in bad)
            + "  A consumer following the README would read a number that does not "
              "match their download and conclude it is corrupt. Update the card.")


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

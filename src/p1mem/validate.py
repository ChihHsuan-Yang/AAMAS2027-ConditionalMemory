"""Validator for the Conditional Memory Utility Dataset.

Two levels, because they catch different things:

* ``validate_row``     -- everything checkable from one row in isolation.
* ``validate_dataset`` -- everything that only exists ACROSS rows: duplicate row ids,
  cluster heterogeneity inside a single declared condition, verifier drift, and a
  reward column that is continuous in name only.

Every check returns structured ``Issue`` objects rather than raising, so a bad corpus is
reported in full instead of one line at a time.

**This validator is tested by deliberate corruption.** ``tests/test_validate.py`` takes a
known-good row and breaks it in fifteen distinct ways, asserting each is caught by the
specific check that should catch it. A validator only ever run on good data detects
nothing known -- and a check whose verdict is right for the wrong reason is harder to
catch than a wrong verdict, which is why the tests assert on the issue CODE, not just on
"something failed".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .schema import (
    CLUSTER_MODEL_NAMING,
    CLUSTER_REPORTS_REASONING_TOKENS,
    DELTA_TOLERANCE,
    ENUMS,
    ERROR_CODES,
    FIELD_ORDER,
    FIELD_SPEC,
    IMPLICIT_CONDITION_KEYS,
    NON_NULLABLE_IDENTITY,
    P3_RESERVED_FIELDS,
    SCHEMA_VERSION,
    compute_cell_id,
    compute_compression_ratio,
    compute_memory_id,
    compute_row_id,
    condition_key,
    derive_utility_label_from_row,
    endpoint_is_credential_safe,
    looks_like_bare_digest,
)

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str
    field: str | None = None
    row_id: str | None = None
    row_index: int | None = None

    def __str__(self) -> str:  # pragma: no cover - display only
        loc = f"row {self.row_index}" if self.row_index is not None else "dataset"
        fld = f" [{self.field}]" if self.field else ""
        return f"{self.severity.upper()} {self.code} @{loc}{fld}: {self.message}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    n_rows: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARN]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}

    def summary(self) -> str:
        counts: dict[str, int] = defaultdict(int)
        for i in self.issues:
            counts[i.code] += 1
        head = (
            f"{self.n_rows} rows | {len(self.errors)} errors | "
            f"{len(self.warnings)} warnings"
        )
        if not counts:
            return head + "\n  (no issues)"
        body = "\n".join(f"  {c}: {n}" for c, n in sorted(counts.items()))
        return head + "\n" + body


# ------------------------------------------------------------------ type checks
_KIND_TYPES: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "int": (int,),
    "float": (int, float),  # an int is a valid float value; bool is excluded below
    "bool": (bool,),
    "obj": (dict,),
    "any": (object,),
}


def _type_ok(kind: str, value: Any) -> bool:
    if kind == "any":
        return True
    # bool is a subclass of int in Python; a bool in an int/float field is a real bug.
    if kind in ("int", "float") and isinstance(value, bool):
        return False
    return isinstance(value, _KIND_TYPES[kind])


# ================================================================= ROW CHECKS
def validate_row(row: Any, *, row_index: int | None = None) -> list[Issue]:
    out: list[Issue] = []

    def add(code: str, msg: str, fld: str | None = None, sev: str = SEVERITY_ERROR) -> None:
        out.append(
            Issue(
                code=code,
                severity=sev,
                message=msg,
                field=fld,
                row_id=row.get("row_id") if isinstance(row, dict) else None,
                row_index=row_index,
            )
        )

    if not isinstance(row, dict):
        return [
            Issue("row_not_object", SEVERITY_ERROR, f"row is {type(row).__name__}, not a dict",
                  row_index=row_index)
        ]

    # --- presence: every field must exist as a key. Null is a value; absent is not. ---
    missing = [f for f in FIELD_ORDER if f not in row]
    for f in missing:
        add("missing_field", f"required field absent from the row", f)
    unknown = sorted(set(row) - set(FIELD_ORDER))
    for f in unknown:
        add("unknown_field", "field is not in the schema", f)

    # --- schema version ---
    if row.get("schema_version") not in (None, SCHEMA_VERSION):
        add("schema_version_mismatch",
            f"row written under {row.get('schema_version')!r}, validator is {SCHEMA_VERSION!r}",
            "schema_version")

    # --- nullability + types ---
    for name, spec in FIELD_SPEC.items():
        if name not in row:
            continue
        value = row[name]
        if value is None:
            if not spec["nullable"]:
                add("null_in_non_nullable", "field may not be null", name)
            continue
        if not _type_ok(spec["kind"], value):
            add("wrong_type",
                f"expected {spec['kind']}, got {type(value).__name__} ({value!r:.60})", name)

    # --- enums ---
    for name, allowed in ENUMS.items():
        v = row.get(name)
        if v is not None and v not in allowed:
            add("bad_enum", f"{v!r} not in {allowed}", name)

    # --- design requirement 3: cluster/model identity is never absent or blank ---
    for name in NON_NULLABLE_IDENTITY:
        v = row.get(name)
        if v is None or (isinstance(v, str) and not v.strip()):
            add("identity_field_empty",
                "experimental identity field is empty; rows from different clusters/models "
                "must never be poolable by accident", name)

    # --- P3 reserved: null in P1 ---
    for name in P3_RESERVED_FIELDS:
        if row.get(name) is not None:
            add("p3_field_populated",
                f"P3-reserved field must be null in P1, got {row[name]!r}", name)

    # --- design requirement 1: FULL text, never a digest ---
    for name in ("output_with_memory", "output_without_memory", "memory_text",
                 "future_task_text"):
        v = row.get(name)
        if isinstance(v, str) and looks_like_bare_digest(v):
            add("output_is_digest",
                "field holds a bare hash instead of the text; a digest blocks every later "
                "re-scoring under a corrected verifier", name)

    # --- delta_utility must equal the difference of its own components ---
    # A wrong-typed reward is already reported by the type pass above; the arithmetic
    # below must not CRASH on it. A validator that raises instead of reporting turns one
    # bad row into a dead run and hides every other issue in the file.
    def _num(v: Any) -> float | None:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    rw, ro, du = (_num(row.get("reward_with_memory")), _num(row.get("reward_without_memory")),
                  _num(row.get("delta_utility")))
    raw_du = row.get("delta_utility")
    if rw is not None and ro is not None:
        if du is None:
            if raw_du is None:
                add("delta_missing", "both rewards present but delta_utility is null",
                    "delta_utility")
        else:
            expected = rw - ro
            if abs(du - expected) > DELTA_TOLERANCE:
                add("delta_mismatch",
                    f"delta_utility={du!r} but reward_with - reward_without = {expected!r} "
                    f"(tol {DELTA_TOLERANCE})", "delta_utility")
    elif raw_du is not None:
        add("delta_without_rewards",
            "delta_utility is set but a reward is missing or unusable; the delta is not "
            "derivable", "delta_utility")

    # --- label must be recomputable from the row's own stored statistics ---
    stored = row.get("utility_label")
    if stored is not None:
        recomputed = derive_utility_label_from_row(row)
        if stored != recomputed:
            add("label_not_recomputable",
                f"stored utility_label={stored!r} but the pre-registered rule applied to "
                f"this row's own CI/mean/floor gives {recomputed!r}", "utility_label")
    if stored in ("robust_useful", "robust_harmful") and row.get("utility_label_threshold") is None:
        add("label_without_floor",
            f"label {stored!r} asserted with no noise floor stored; the pre-registration "
            f"requires |mean dU| > F and F is not recorded", "utility_label_threshold")

    # --- errored rows must not carry an outcome ---
    err = row.get("error_code_if_any")
    if err is not None:
        if err not in ERROR_CODES:
            add("unknown_error_code", f"{err!r} not in {ERROR_CODES}", "error_code_if_any",
                sev=SEVERITY_WARN)
        if rw is not None or ro is not None:
            add("reward_on_errored_row",
                f"row carries error {err!r} but also a reward; an errored cell has no "
                f"outcome and scoring one fabricates a result", "error_code_if_any")

    # --- THE empty-output trap: content=null with finish_reason=length ---
    # A truncated reasoning response scored as a wrong answer drives delta_utility
    # negative and manufactures a harmful memory. It must be an error, never an outcome.
    for out_f, rew_f in (("output_with_memory", "reward_with_memory"),
                         ("output_without_memory", "reward_without_memory")):
        o, r = row.get(out_f), row.get(rew_f)
        empty = o is None or (isinstance(o, str) and not o.strip())
        if empty and r is not None:
            add("scored_empty_output",
                f"{out_f} is empty but {rew_f}={r!r} was recorded. An empty completion "
                f"(e.g. finish_reason='length' with content=null) is a hard ERROR, not a "
                f"zero-reward answer; set error_code_if_any and re-run the cell.", out_f)
        if empty and r is None and err is None:
            add("empty_output_no_error",
                f"{out_f} is empty and no error code is set; the cell has neither an "
                f"outcome nor a recorded failure", out_f)

    # --- endpoint must be credential-free ---
    ep = row.get("reader_endpoint")
    if ep is not None and not endpoint_is_credential_safe(ep):
        add("endpoint_may_carry_credential",
            "reader_endpoint contains userinfo, a query string, or a token-shaped "
            "substring; store an alias and keep the hash in reader_endpoint_sha256",
            "reader_endpoint")

    # --- reasoning_tokens: absent is not zero ---
    cl = row.get("reader_cluster")
    rt = row.get("reasoning_tokens")
    if isinstance(cl, str) and cl in CLUSTER_REPORTS_REASONING_TOKENS:
        reports = CLUSTER_REPORTS_REASONING_TOKENS[cl]
        if not reports and rt == 0:
            add("absent_reported_as_zero",
                f"cluster {cl!r} does not report completion_tokens_details, so "
                f"reasoning_tokens=0 is an absent value written as a measurement; use null",
                "reasoning_tokens")
        if reports and rt is None and err is None:
            add("reasoning_tokens_missing",
                f"cluster {cl!r} does report reasoning tokens but this successful row has "
                f"none recorded", "reasoning_tokens", sev=SEVERITY_WARN)

    # --- cluster/model naming asymmetry must survive ---
    # The same logical model is 'gpt-oss-120b' on Metis and 'openai/gpt-oss-120b' on
    # Sophia. A row using the other cluster's spelling is evidence that something
    # normalized the name and merged two arms.
    for cl_f, md_f in (("reader_cluster", "reader_model"),
                       ("memory_writer_cluster", "memory_writer_model")):
        c, m = row.get(cl_f), row.get(md_f)
        if not (isinstance(c, str) and isinstance(m, str)):
            continue
        if c not in CLUSTER_MODEL_NAMING or m.startswith("none:"):
            continue
        if m in CLUSTER_MODEL_NAMING[c]:
            continue
        others = [k for k, v in CLUSTER_MODEL_NAMING.items() if k != c and m in v]
        if others:
            add("cross_cluster_model_naming",
                f"{md_f}={m!r} is the spelling used on {others} but {cl_f}={c!r}. The "
                f"naming asymmetry is real; normalizing it merges two experimental arms",
                md_f)
        else:
            add("unknown_model_for_cluster",
                f"{md_f}={m!r} is not a known model id for cluster {c!r}", md_f,
                sev=SEVERITY_WARN)

    # --- deterministic ids must actually be the hash of the content ---
    for name, fn in (("memory_id", compute_memory_id),
                     ("cell_id", compute_cell_id),
                     ("row_id", compute_row_id)):
        v = row.get(name)
        if not isinstance(v, str) or not v:
            continue
        try:
            expected = fn(row)
        except Exception as exc:  # pragma: no cover
            add("id_not_computable", f"could not recompute {name}: {exc}", name)
            continue
        if v != expected:
            add("id_mismatch",
                f"{name}={v!r} does not match the hash of its own content ({expected!r}); "
                f"either the id was copied from another row or a content field changed "
                f"after the id was minted", name)

    # --- internal consistency of retrieval bookkeeping ---
    method = row.get("retrieval_method")
    if method == "top_k" and row.get("retrieval_k") is None:
        add("missing_k_for_topk", "retrieval_method='top_k' with no retrieval_k",
            "retrieval_k")
    if method == "none" and row.get("memory_tokens_exposed") not in (None, 0):
        add("tokens_exposed_without_retrieval",
            f"retrieval_method='none' but memory_tokens_exposed="
            f"{row.get('memory_tokens_exposed')!r}", "memory_tokens_exposed")
    ex, ret = row.get("memory_tokens_exposed"), row.get("memory_tokens_retrieved")
    if isinstance(ex, int) and isinstance(ret, int) and not isinstance(ex, bool) and ex > ret:
        add("exposed_exceeds_retrieved",
            f"memory_tokens_exposed={ex} > memory_tokens_retrieved={ret}; a reader cannot "
            f"see more than the retriever returned", "memory_tokens_exposed")

    # --- non-negative counters ---
    for name in ("memory_tokens", "memory_tokens_retrieved", "memory_tokens_exposed",
                 "embedding_calls", "generation_calls", "input_tokens", "output_tokens",
                 "retry_count", "reasoning_tokens", "replicate_id",
                 "memory_extraction_input_tokens", "memory_extraction_output_tokens",
                 "write_latency", "retrieval_latency", "generation_latency",
                 "end_to_end_latency", "memory_extraction_latency"):
        v = row.get(name)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0:
            add("negative_quantity", f"{name}={v!r} must be >= 0", name)

    # --- similarity/confidence ranges ---
    sim = row.get("semantic_similarity")
    if isinstance(sim, (int, float)) and not isinstance(sim, bool) and not (-1.0001 <= sim <= 1.0001):
        add("similarity_out_of_range", f"cosine similarity {sim!r} outside [-1, 1]",
            "semantic_similarity")
    rc = row.get("robustness_confidence")
    if isinstance(rc, (int, float)) and not isinstance(rc, bool) and not (0.0 <= rc <= 1.0):
        add("confidence_out_of_range", f"robustness_confidence {rc!r} outside [0, 1]",
            "robustness_confidence")

    # ---------------- user-field checks (schema v2, added 2026-09-30) ----------------
    # Each of these guards a way the new fields could carry a FABRICATED value. A field
    # added "because the user asked for it" is exactly the field most likely to be
    # filled with something plausible, so each one that cannot be populated is checked
    # to be null, and each one that can is checked to be recomputable from the row.

    # compression_ratio must equal its own components, like delta_utility does.
    cr = row.get("compression_ratio")
    if cr is not None:
        expected_cr = compute_compression_ratio(
            row.get("memory_tokens"), row.get("source_span_tokens"))
        if expected_cr is None:
            add("compression_ratio_not_derivable",
                "compression_ratio is set but memory_tokens / source_span_tokens cannot "
                "produce it; the ratio is not recomputable from this row",
                "compression_ratio")
        elif abs(float(cr) - expected_cr) > 1e-9:
            add("compression_ratio_mismatch",
                f"compression_ratio={cr!r} but memory_tokens/source_span_tokens = "
                f"{expected_cr!r}", "compression_ratio")

    # A raw memory IS its source span, so its ratio is exactly 1.0. Anything else means
    # the span denominator was joined from the wrong unit.
    if row.get("memory_representation") == "raw" and isinstance(cr, (int, float)) \
            and not isinstance(cr, bool) and abs(float(cr) - 1.0) > 1e-9:
        add("raw_compression_not_unity",
            f"representation='raw' but compression_ratio={cr!r}. Raw is the source span "
            f"verbatim, so the ratio must be 1.0; a different value means the span "
            f"denominator came from a different unit", "compression_ratio")

    # THE faithfulness trap: a score on raw can only be the 1.0 tautology.
    fc = row.get("faithfulness_check")
    if fc is not None and row.get("memory_representation") == "raw":
        add("faithfulness_scored_on_raw",
            f"faithfulness_check={fc!r} on a raw memory. Raw IS the source text, so any "
            f"source-grounded proxy returns 1.0 by construction (raw_control is that "
            f"comparison and is a POSITIVE CONTROL). Storing it asserts a check that "
            f"measured nothing; leave it null and say why in faithfulness_notes.",
            "faithfulness_check")
    # A null with no stated reason is indistinguishable from a forgotten field.
    if fc is None and not (isinstance(row.get("faithfulness_notes"), str)
                           and row["faithfulness_notes"].strip()):
        add("faithfulness_null_without_reason",
            "faithfulness_check is null and faithfulness_notes is empty. An unexplained "
            "null cannot be told apart from an unpopulated field; record WHY there is no "
            "score", "faithfulness_notes", sev=SEVERITY_WARN)

    # extraction cost: raw made no call, so its billable cost is a measured 0.0 -- but
    # the LATENCY must stay null, because "no call" has no duration.
    if row.get("memory_writer_model") == "none:deterministic_span":
        ecp = row.get("extraction_cost_proxy")
        if ecp is not None and float(ecp) != 0.0:
            add("raw_extraction_cost_nonzero",
                f"extraction_cost_proxy={ecp!r} for a deterministic-span memory, which "
                f"makes no extraction call", "extraction_cost_proxy")
        if row.get("memory_extraction_latency") == 0.0:
            add("absent_latency_reported_as_zero",
                "memory_extraction_latency=0.0 for a memory written with no call. No "
                "call has no duration; use null. A 0.0 here is averaged into a mean "
                "latency and describes nothing", "memory_extraction_latency")

    # bearing_evidence must not claim more than the screen did.
    be = row.get("bearing_evidence")
    bl = row.get("bearing_label")
    if isinstance(be, dict):
        if not be.get("caveat"):
            add("bearing_evidence_without_caveat",
                "bearing_evidence carries no caveat. The screen's known weakness must "
                "travel WITH the evidence, not only in a doc", "bearing_evidence",
                sev=SEVERITY_WARN)
        if be.get("screen_is_content_only") is not True:
            add("bearing_screen_not_content_only",
                "bearing_evidence.screen_is_content_only is not True. If a reward ever "
                "entered the screen, the BEARING vs CONTROL contrast is circular and the "
                "headline is void", "bearing_evidence")
        h, s = be.get("task_pool_hits"), be.get("task_pool_size")
        d = be.get("discriminativeness")
        if (isinstance(h, int) and isinstance(s, int) and not isinstance(h, bool)
                and not isinstance(s, bool) and s > 0 and isinstance(d, (int, float))
                and not isinstance(d, bool) and abs(float(d) - h / s) > 1e-9):
            add("discriminativeness_mismatch",
                f"discriminativeness={d!r} but task_pool_hits/task_pool_size = {h/s!r}",
                "bearing_evidence")
    if bl == "BEARING" and isinstance(be, dict) and be.get("detector_fires") is False:
        add("bearing_label_contradicts_evidence",
            "bearing_label='BEARING' but bearing_evidence.detector_fires is False",
            "bearing_label")
    if bl == "MATCHED_CONTROL" and isinstance(be, dict) and be.get("detector_fires") is True:
        add("control_label_contradicts_evidence",
            "bearing_label='MATCHED_CONTROL' but the detector fired; a matched control "
            "is defined by the detector being SILENT", "bearing_label")

    # candidate_pool_size must agree with the evidence it was copied from.
    cps = row.get("candidate_pool_size")
    if (cps is not None and isinstance(be, dict) and be.get("task_pool_size") is not None
            and cps != be["task_pool_size"]):
        add("candidate_pool_size_mismatch",
            f"candidate_pool_size={cps!r} but bearing_evidence.task_pool_size="
            f"{be['task_pool_size']!r}", "candidate_pool_size")

    # storage_bytes must be the actual byte length, not an estimate.
    sb, mt = row.get("storage_bytes"), row.get("memory_text")
    if (sb is not None and isinstance(mt, str) and mt != "__WITHHELD_SEE_LICENSE__"
            and sb != len(mt.encode("utf-8"))):
        add("storage_bytes_mismatch",
            f"storage_bytes={sb!r} but len(memory_text.encode('utf-8'))="
            f"{len(mt.encode('utf-8'))}", "storage_bytes")

    # stability is a sampling-noise measurement, NOT a confidence. Guard the conflation.
    cos = row.get("confidence_or_stability")
    if isinstance(cos, (int, float)) and not isinstance(cos, bool) and not (0.0 <= cos <= 1.0):
        add("stability_out_of_range", f"confidence_or_stability {cos!r} outside [0, 1]",
            "confidence_or_stability")

    # context_budget: a budget that was never enforced must not be recorded as one.
    cb = row.get("context_budget")
    ex2, ret2 = row.get("memory_tokens_exposed"), row.get("memory_tokens_retrieved")
    if cb is not None and ex2 == ret2 and isinstance(ex2, int) and not isinstance(ex2, bool):
        add("context_budget_never_bound",
            f"context_budget={cb!r} but memory_tokens_exposed == memory_tokens_retrieved "
            f"({ex2}), so no truncation ever occurred. Recording a cap that never bound "
            f"states a control the run did not have", "context_budget", sev=SEVERITY_WARN)

    # --- export provenance must be internally consistent (schema v2) ---
    tfw, rr = row.get("text_fields_withheld"), row.get("reconstruction_required")
    if tfw is not None and not isinstance(tfw, list):
        add("withheld_list_wrong_type",
            f"text_fields_withheld must be a list, got {type(tfw).__name__}",
            "text_fields_withheld")
    elif isinstance(tfw, list) and rr is not None and bool(tfw) != bool(rr):
        add("reconstruction_flag_mismatch",
            f"reconstruction_required={rr!r} but text_fields_withheld={tfw!r}. The flag "
            f"must be True exactly when something was withheld, or a consumer filtering "
            f"on it silently gets the wrong rows", "reconstruction_required")
    # A field the policy says to withhold must not survive with its text intact.
    if isinstance(tfw, list):
        for f in tfw:
            v = row.get(f)
            if isinstance(v, str) and v and v != "__WITHHELD_SEE_LICENSE__":
                add("declared_withheld_but_present",
                    f"{f!r} is listed in text_fields_withheld but still holds "
                    f"{len(v)} characters of text", f)

    # --- a successful row must not be missing its provenance ---
    prov = row.get("provenance")
    if isinstance(prov, dict):
        for key in ("code_sha", "config_sha256", "run_id"):
            if not prov.get(key):
                add("provenance_incomplete", f"provenance.{key} is empty", "provenance",
                    sev=SEVERITY_WARN)

    return out


# ============================================================= DATASET CHECKS
def validate_dataset(rows: Sequence[dict[str, Any]]) -> Report:
    report = Report(n_rows=len(rows))
    for i, row in enumerate(rows):
        report.issues.extend(validate_row(row, row_index=i))

    good = [r for r in rows if isinstance(r, dict)]

    # --- duplicate row ids ---
    seen: dict[str, int] = {}
    for i, r in enumerate(good):
        rid = r.get("row_id")
        if not isinstance(rid, str) or not rid:
            continue
        if rid in seen:
            report.issues.append(Issue(
                "duplicate_row_id", SEVERITY_ERROR,
                f"row_id {rid!r} already used at row {seen[rid]}; append-only ledgers must "
                f"not restate a row -- a correction is a NEW row", "row_id", rid, i))
        else:
            seen[rid] = i

    # --- E2's named check: reader_cluster must not vary inside one condition ---
    # NOTE: the grouping key deliberately EXCLUDES reader_cluster. If cluster were part of
    # the key, every heterogeneous group would split into homogeneous ones and this check
    # could never fire. It is the one check whose key must not contain its own subject.
    by_cond: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    by_cond_writer: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    by_cond_verifier: dict[str, dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i, r in enumerate(good):
        key = condition_key(r)
        rc = r.get("reader_cluster")
        if isinstance(rc, str) and rc:
            by_cond[key][rc].append(i)
        wc = r.get("memory_writer_cluster")
        if isinstance(wc, str) and wc:
            by_cond_writer[key][wc].append(i)
        vk = (r.get("verifier_version"),)
        if vk != (None,):
            by_cond_verifier[key][vk].append(i)

    for key, clusters in by_cond.items():
        if len(clusters) > 1:
            detail = ", ".join(
                f"{c}: {len(ix)} rows (first at {ix[0]})" for c, ix in sorted(clusters.items())
            )
            report.issues.append(Issue(
                "cluster_heterogeneous_condition", SEVERITY_ERROR,
                f"condition {key} contains rows from {len(clusters)} different "
                f"reader_clusters -- {detail}. Cluster is experimental identity; these are "
                f"different arms and must not be pooled.", "reader_cluster"))

    for key, clusters in by_cond_writer.items():
        real = {c: ix for c, ix in clusters.items() if not c.startswith("none:")}
        if len(real) > 1:
            detail = ", ".join(f"{c}: {len(ix)} rows" for c, ix in sorted(real.items()))
            report.issues.append(Issue(
                "writer_cluster_heterogeneous_condition", SEVERITY_ERROR,
                f"condition {key} mixes memory_writer_clusters -- {detail}. Memories "
                f"written on different clusters are different memories.",
                "memory_writer_cluster"))

    # --- verifier drift: WITH and WITHOUT already share a row, but arms across a
    #     condition must also share a verifier. This has invalidated a sibling table. ---
    #
    # 🔴 CORRECTED 2026-09-30 (Sub-agent HF). This check previously keyed on
    # ``(verifier_id, verifier_version)`` and fired on all three P1 result arms. It was
    # measuring the wrong subject, and its MESSAGE named a third thing again:
    #
    #   * It reported "scored under different verifier VERSIONS". Measured: there is
    #     exactly ONE version in the entire corpus, ``vendored@f8ba659e237c``, on all
    #     4,519 rows. The stated reason was false while the verdict looked plausible.
    #   * What actually varied was ``verifier_id`` -- and that is the BENCHMARK'S OWN
    #     per-question ``eval_function``, not a choice of ours. Verified: for all 275
    #     tasks, ``verifier_id`` equals the head of that question's ``eval_function`` in
    #     LongMemEval-V2's ``questions.jsonl``, 275/275, zero disagreements. A
    #     multiple-choice question is scored by ``mc_choice_match`` and a phrase
    #     question by ``norm_phrase_set_match`` because the benchmark says so.
    #   * A condition spans many questions, so requiring one scorer per condition
    #     demands that every question in a benchmark be scored the same way. That is
    #     not the prohibition EXPERIMENT_PLAN 8.4 states; 8.4 forbids an ARM-DEPENDENT
    #     verifier -- scoring WITH and WITHOUT differently.
    #
    # The repair keys the drift check on ``verifier_version`` alone (the thing that can
    # actually change under us, e.g. a re-vendored scorer), and adds a SEPARATE, tighter
    # check below for the arm-dependence 8.4 really prohibits. This is strictly stronger
    # than what it replaces: the old check could not see a scorer that varied ACROSS a
    # paired contrast, which is the only place the difference can bias a result.
    for key, vs in by_cond_verifier.items():
        if len(vs) > 1:
            detail = ", ".join(f"{v}: {len(ix)} rows" for v, ix in sorted(map(
                lambda kv: (str(kv[0]), kv[1]), vs.items())))
            report.issues.append(Issue(
                "verifier_drift_in_condition", SEVERITY_ERROR,
                f"condition {key} was scored by more than one verifier VERSION -- "
                f"{detail}. A scorer that changed under us makes arms incomparable.",
                "verifier_version"))

    # --- the prohibition EXPERIMENT_PLAN 8.4 actually states: one task must not be
    #     scored by two different scorers. This is where arm-dependence would show. ---
    by_task_verifier: dict[Any, dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i, r in enumerate(good):
        tid = r.get("future_task_id")
        vk = (r.get("verifier_id"), r.get("verifier_version"))
        if tid is not None and vk != (None, None):
            by_task_verifier[tid][vk].append(i)
    for tid, vs in by_task_verifier.items():
        if len(vs) > 1:
            detail = ", ".join(f"{v}: {len(ix)} rows" for v, ix in sorted(map(
                lambda kv: (str(kv[0]), kv[1]), vs.items())))
            report.issues.append(Issue(
                "verifier_varies_within_task", SEVERITY_ERROR,
                f"task {tid!r} was scored by more than one verifier -- {detail}. One "
                f"question has one correct-answer criterion; two scorers on one task "
                f"means the criterion depended on something other than the question, "
                f"which is the arm-dependence EXPERIMENT_PLAN 8.4 forbids.",
                "verifier_id"))

    # --- scorer composition must not differ across a PAIRED contrast ---
    # The headline is BEARING minus MATCHED_CONTROL within a memory. If the two strata
    # draw on different scorers, part of that difference is scorer difficulty rather
    # than bearing. This is not a validity error -- the design is composition-matched on
    # question family, not on scorer -- but it is a confound a consumer must be able to
    # see, so it is reported rather than left for them to discover.
    by_mem_stratum: dict[Any, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for r in good:
        prov = r.get("provenance")
        st = prov.get("stratum") if isinstance(prov, dict) else None
        if st and r.get("memory_id") and r.get("verifier_id"):
            by_mem_stratum[r["memory_id"]][st].add(r["verifier_id"])
    mismatched = [m for m, s in by_mem_stratum.items()
                  if len(s) > 1 and len({frozenset(v) for v in s.values()}) > 1]
    if mismatched:
        report.issues.append(Issue(
            "scorer_composition_differs_across_strata", SEVERITY_WARN,
            f"{len(mismatched)} of {len(by_mem_stratum)} memories draw on a DIFFERENT "
            f"set of verifiers in different strata. Each task keeps the benchmark's own "
            f"scorer, so this is not arm-dependence -- but a paired stratum contrast on "
            f"these memories differences two scorer mixes as well as two strata, and the "
            f"contrast should be reported split by whether the mix is constant.",
            "verifier_id"))

    # --- a cell's replicates must agree on everything except sampling ---
    by_cell: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for i, r in enumerate(good):
        cid = r.get("cell_id")
        if isinstance(cid, str) and cid:
            by_cell[cid].append((i, r))
    for cid, items in by_cell.items():
        reps = [r.get("replicate_id") for _, r in items]
        dupes = {x for x in reps if reps.count(x) > 1 and x is not None}
        if dupes:
            report.issues.append(Issue(
                "duplicate_replicate_in_cell", SEVERITY_ERROR,
                f"cell {cid} has repeated replicate_id(s) {sorted(dupes)}", "replicate_id"))
        for fname in ("memory_text", "future_task_text", "reader_prompt_version",
                      "reader_reasoning_effort", "verifier_version"):
            vals = {_hashable(r.get(fname)) for _, r in items}
            if len(vals) > 1:
                report.issues.append(Issue(
                    "cell_inconsistent_across_replicates", SEVERITY_ERROR,
                    f"cell {cid} replicates disagree on {fname}; replicates must differ "
                    f"ONLY in sampling", fname))

    # --- num_replicates must equal the replicates actually present (schema v2) ---
    # This is the check that makes num_replicates a MEASUREMENT rather than a copy of
    # the planned count. A design can plan 3 replicates and deliver 2; if the field
    # restates the plan, every per-cell average silently uses the wrong denominator.
    for cid, items in by_cell.items():
        actual = len(items)
        for i, r in items:
            declared = r.get("num_replicates")
            if declared is None:
                continue
            if declared != actual:
                report.issues.append(Issue(
                    "num_replicates_mismatch", SEVERITY_ERROR,
                    f"row declares num_replicates={declared!r} but cell {cid} has "
                    f"{actual} rows present. A planned count written where a measured "
                    f"one belongs biases every per-cell mean.", "num_replicates",
                    r.get("row_id"), i))
                break

    # --- confidence_or_stability must match the replicates it summarises (schema v2) ---
    # Stability is the fraction of a cell's replicates agreeing on delta_utility. If it
    # were stored without this check, a 1.0 could mean "we did not look".
    for cid, items in by_cell.items():
        deltas = [r.get("delta_utility") for _, r in items
                  if isinstance(r.get("delta_utility"), (int, float))
                  and not isinstance(r.get("delta_utility"), bool)]
        if len(deltas) < 2:
            continue
        modal = max(set(deltas), key=deltas.count)
        expected = deltas.count(modal) / len(deltas)
        for i, r in items:
            got = r.get("confidence_or_stability")
            if got is None:
                continue
            if abs(float(got) - expected) > 1e-9:
                report.issues.append(Issue(
                    "stability_mismatch", SEVERITY_ERROR,
                    f"confidence_or_stability={got!r} but cell {cid}'s replicates agree "
                    f"on delta_utility at rate {expected!r}", "confidence_or_stability",
                    r.get("row_id"), i))
                break

    # --- a stability of 1.0 everywhere means F_exec = 0, and that must be VISIBLE ---
    # Reported as a warning, not hidden: it is the reason the variance decomposition is
    # unidentifiable, and a consumer who reads stability as "confidence" would draw the
    # opposite conclusion from the one the data supports.
    stab = [r.get("confidence_or_stability") for r in good
            if isinstance(r.get("confidence_or_stability"), (int, float))
            and not isinstance(r.get("confidence_or_stability"), bool)]
    if len(stab) >= 20 and all(s == 1.0 for s in stab):
        report.issues.append(Issue(
            "zero_execution_noise", SEVERITY_WARN,
            f"all {len(stab)} rows have confidence_or_stability=1.0: every replicate of "
            f"every cell agreed exactly, so measured execution noise F_exec = 0. This is "
            f"real temperature-0 determinism, NOT a defect -- but replicates therefore "
            f"carry NO information about sampling noise, the variance decomposition is "
            f"unidentifiable, and this field must not be read as confidence that a delta "
            f"is real.", "confidence_or_stability"))

    # --- "continuous reward" that is binary in fact ---
    cont = [r for r in good if r.get("reward_is_continuous") is True]
    vals = {float(r[k]) for r in cont for k in ("reward_with_memory", "reward_without_memory")
            if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)}
    if len(cont) >= 20 and vals and vals <= {0.0, 1.0}:
        report.issues.append(Issue(
            "continuous_reward_is_binary", SEVERITY_WARN,
            f"{len(cont)} rows declare reward_is_continuous=True but every reward is in "
            f"{{0.0, 1.0}}; either the flag is wrong or a continuous score was rounded",
            "reward_is_continuous"))

    # --- the labels are undetermined en masse: expected until P1-051, flagged not hidden
    labels = [r.get("utility_label") for r in good]
    if labels and all(l == "undetermined" for l in labels):
        report.issues.append(Issue(
            "all_labels_undetermined", SEVERITY_WARN,
            f"all {len(labels)} rows are labelled 'undetermined'. Expected while the noise "
            f"floor F (P1-051) is unmeasured; recompute the labels once it exists.",
            "utility_label"))

    return report


def _hashable(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        from .schema import canonical_json
        return canonical_json(v)
    return v


def validate_file(path: str) -> Report:
    from .schema import load_jsonl
    return validate_dataset(load_jsonl(path, strict=True))


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Validate a P1 conditional-memory JSONL ledger.")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--warnings-are-errors", action="store_true")
    ap.add_argument("--max-print", type=int, default=40)
    args = ap.parse_args(argv)

    rc = 0
    for p in args.paths:
        rep = validate_file(p)
        print(f"\n=== {p} ===")
        print(rep.summary())
        for issue in rep.issues[: args.max_print]:
            print("  " + str(issue))
        if len(rep.issues) > args.max_print:
            print(f"  ... {len(rep.issues) - args.max_print} more")
        if not rep.ok or (args.warnings_are_errors and rep.warnings):
            rc = 1
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

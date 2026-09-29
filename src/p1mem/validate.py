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
        vk = (r.get("verifier_id"), r.get("verifier_version"))
        if vk != (None, None):
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
    for key, vs in by_cond_verifier.items():
        if len(vs) > 1:
            detail = ", ".join(f"{v}: {len(ix)} rows" for v, ix in sorted(map(
                lambda kv: (str(kv[0]), kv[1]), vs.items())))
            report.issues.append(Issue(
                "verifier_drift_in_condition", SEVERITY_ERROR,
                f"condition {key} was scored by more than one verifier -- {detail}. Arms "
                f"scored under different verifier versions are not comparable.",
                "verifier_version"))

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

#!/usr/bin/env python3
"""Convert the SWE-bench representation runs into p1mem schema v3 rows.

    python3 scripts/swebench_to_schema.py \
        --src results/swebench/representations_v2.json \
        --src results/swebench/representations_sympy.json \
        --out results/ledgers/swebench/cells_v3.jsonl

``scripts/scicode_to_schema.py`` is the house pattern and this file follows it: it
**derives; it never invents.** A value is written only when it is computed from the
artifact or recomputed from the adapter the run actually used. Everything else is an
explicit ``None`` with a stated reason, because an unexplained null cannot be told
apart from a forgotten one.

🔴 THIS BENCHMARK IS METRICS-ONLY, AND THE REASON IS AN *ABSENT* LICENCE
------------------------------------------------------------------------
``princeton-nlp/SWE-bench_Verified`` declares **no licence**: the HF API returns
``cardData.license: None``, the tag list carries no ``license:*`` entry, and the card
text states none. The MIT grant covers the **harness code**, not the corpus, and the
underlying issue text and patches belong to the upstream OSS projects (django BSD-3,
sympy BSD-3) -- not Princeton's to relicense, and not ours.
``docs/BENCHMARK_LICENSES.md`` section 5 is the ruling; this script implements it.

**An absent licence is not a permissive licence, and ``gated: false`` means
FETCHABLE, not redistributable.**

So this converter emits, per cell:

* the upstream ``instance_id`` values (identifiers, not content),
* our derived measurements -- reward, deltaU, both-arms-fail, edit status,
  contagion diagnostics, token counts, representation label,
* model/config metadata and allowable provenance.

and it emits **no** issue text, **no** problem statement, **no** patch and **no**
model response text. The text fields that the schema requires to be present carry
``schema.WITHHELD_SENTINEL`` and are declared in ``text_fields_withheld``, which is
what ``schema.assert_content_redistributable`` (export GATE 6) checks: a blanked field
the row does not admit to blanking is an *undeclared* withholding, and a consumer
filtering on that list would silently get the wrong rows.

🔴 WITHHELD IS NOT THE SAME WORD AS NOT-RETAINED
-------------------------------------------------
SciCode's rows carry ``OUTPUT_NOT_RETAINED_SENTINEL`` -- *the text was never written
down, by anyone, and no licence is involved.* These rows carry
``WITHHELD_SENTINEL`` -- *the text exists, we have it on disk, and we may not
redistribute it.* The two are different facts and this repo spells them differently
on purpose. Conflating them would publish a false stated reason in the one field a
consumer checks to find out why a field is empty. Here the response text **does**
exist in ``results/swebench/representations_*.json``; it is withheld, not lost.

DEFECT #21: A MANUFACTURED 0.0 MUST NEVER SHIP
-----------------------------------------------
``status_lines=0`` in an arm's ``test_detail`` means the test suite printed **no
verdict at all** -- an import error, a collection error, a missing test id. The
harness never asked the question, so a stored ``0.0`` records "the model's fix was
wrong" where the truth is "no evidence exists". That is an error value becoming a real
number, and on this benchmark it manufactures *harm* out of a collection error.

The scorer is fixed; these artifacts were written before the fix. The correction is
applied on read by ``swebench_multirepo_analysis.demote_manufactured_zeros``, which is
**imported, not reimplemented** -- it already carries a positive control proving it
moves a manufactured zero, leaves a real one, and is idempotent. Two copies of a
correction are two chances to correct differently.

WHAT A ROW IS
-------------
One row = one **cell** = (memory instance, task instance, representation), with the
WITH and WITHOUT arms paired INTO that row, so a WITH score can never drift away from
the WITHOUT score it is differenced against.

THREE THINGS THIS SCRIPT REFUSES TO DO
--------------------------------------
1. **It will not emit benchmark content.** Not the problem statement, not the patch,
   not the model's response. The withholding is declared per row.
2. **It will not ship a manufactured 0.0.** See defect #21 above. The count of
   demoted arm-reads is recorded in the stats and in every affected row's provenance.
3. **It will not coerce a null reward to 0.0.** ``None`` means "could not be scored";
   ``0.0`` means "ran and got the wrong answer". Collapsing them manufactures harm and
   has shipped in this project twice.
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from p1mem import schema as S                                    # noqa: E402
from p1mem import validate as V                                  # noqa: E402
from p1mem.adapters import swebench as SW                        # noqa: E402
from p1mem.adapters import swebench_prompt as SWP                # noqa: E402

# 🔴 IMPORTED, NOT REIMPLEMENTED. This function already has a positive control
#    (swebench_multirepo_analysis self-test, control 7/7b/7c) proving it moves a
#    manufactured zero, leaves a REAL 0.0 untouched, and is idempotent. A second
#    copy here would be a second chance to correct differently.
from swebench_multirepo_analysis import demote_manufactured_zeros   # noqa: E402

BENCHMARK = "swebench_verified"

#: 🔴 The reason this release is metrics-only. Keyed to the audit, with its date.
LICENSE_REF = "swebench_verified:NO-LICENCE-DECLARED"

#: Per-run parameters cross-checked against each artifact's own ``summary`` block.
#: NOT defaults to fall back on: a mismatch raises, because a converter that accepts
#: a differently-configured artifact stamps one run's identity onto another run's data.
EXPECTED_SUMMARY: dict[str, Any] = {
    "mode": "representation",
    "prompt_version": "swebench_v2_symmetric",
    "patch_format": "defanged",
    "prompt_variant": "v2_symmetric",
    "model": "gpt-oss-120b",
    "cluster": "metis",
    "temperature": 0.0,
    "reasoning_effort": "low",
    "max_tokens": 2048,
    "writer_max_tokens": 1024,
    "benchmark_version": "swebench_verified@princeton-nlp",
    "WITHOUT_shared_across_representations": True,
}

READER_ARM = "gptoss_metis"
RUN_ID = "swebench_representations_v2"
CONDITION_ID_FMT = "swebench_{rep}_metis_gptoss120b_v2symmetric"

VERIFIER_ID = "swebench_f2p_p2p_pytest"
VERIFIER_VERSION = f"swebench_harness@{SW.HARNESS_REPO.rsplit('/', 1)[-1]}:MIT"

#: Every text field this schema requires that a SWE-bench row may not carry.
#: ``redact_row`` in the exporter would blank these anyway; doing it HERE means the
#: ledger on disk never holds the content either, so the embargo does not depend on
#: one downstream script being run.
WITHHELD_TEXT_FIELDS: tuple[str, ...] = (
    "memory_text", "future_task_text",
    "output_with_memory", "output_without_memory",
)

NO_EMBEDDING_REASON = (
    "NOT EMBEDDED. The SWE-bench runner has no embedding code path at all "
    "(grep over scripts/swebench_representations.py, scripts/swebench_pilot_v2.py "
    "and src/p1mem/adapters/swebench*.py returns zero hits for 'embedding'). The "
    "donor/recipient pairing is by REPOSITORY and file path, not by vector "
    "similarity. This is an absence of the measurement, not a lost artifact: there "
    "is no .npy to point at."
)


class ConversionRefused(RuntimeError):
    """Raised instead of writing a row this script cannot justify."""


def _git_sha_for(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)
        return (out.stdout or "").strip() or None
    except Exception:
        return None


def _sha256_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load_source(path: Path) -> dict[str, Any]:
    """Load one representation artifact and check it is the shape we expect."""
    if not path.is_file():
        raise ConversionRefused(f"REFUSING TO WRITE: source artifact missing: {path}")
    d = json.loads(path.read_text())
    if "cells" not in d or "summary" not in d:
        raise ConversionRefused(
            f"REFUSING TO WRITE: {path} is not a representation artifact "
            f"(no 'cells'/'summary').")
    if not d["cells"]:
        raise ConversionRefused(f"REFUSING TO WRITE: {path} has zero cells.")
    for k, want in EXPECTED_SUMMARY.items():
        got = d["summary"].get(k)
        if got != want:
            raise ConversionRefused(
                f"REFUSING TO WRITE: {path} summary[{k!r}]={got!r} but this converter "
                f"stamps {want!r} onto every row. A converter that accepts a "
                f"differently-configured artifact writes one run's identity onto "
                f"another run's data.")
    d["_source_path"] = str(path.relative_to(REPO_ROOT))
    d["_source_sha256"] = _sha256_file(path)
    return d


def convert(sources: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                        dict[str, Any]]:
    """Return (schema-v3 rows, stats). Pure with respect to its inputs."""
    now = S.utc_now()
    reader = S.reader_row_fields(READER_ARM)
    code_sha = _git_sha_for(REPO_ROOT / "scripts/swebench_representations.py")
    adapter_sha = _git_sha_for(REPO_ROOT / "src/p1mem/adapters/swebench_prompt.py")

    stats: dict[str, Any] = {
        "sources": [],
        "cells_in_artifacts": 0,
        "rows_emitted": 0,
        "excluded_contagion_dirty": 0,
        "by_repo": collections.Counter(),
        "by_representation": collections.Counter(),
        "arms_with_null_reward": 0,
        "cells_with_null_delta": 0,
        "both_arms_fail": 0,
        "edit_status": collections.Counter(),
        "demoted_manufactured_zeros": {"arm_reads": 0, "by_repo": {}, "cells": 0},
    }

    out: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for src in sources:
        cells = src["cells"]
        stats["cells_in_artifacts"] += len(cells)

        # ---- DEFECT #21, applied BEFORE any row is built. A manufactured 0.0 must
        #      never reach a row, not even to be corrected later: the correction has
        #      to happen upstream of every number derived from the reward.
        before = sum(1 for c in cells for a in c["arms"].values()
                     if a.get("reward") is not None)
        demotion = demote_manufactured_zeros(cells)
        after = sum(1 for c in cells for a in c["arms"].values()
                    if a.get("reward") is not None)
        if demotion["arm_reads_demoted"] != before - after:
            raise ConversionRefused(
                f"REFUSING TO WRITE: the defect-21 demotion reports "
                f"{demotion['arm_reads_demoted']} arm-reads moved but the count of "
                f"non-null rewards fell by {before - after}. The ledger and the data "
                f"disagree, so neither can be published.")
        stats["demoted_manufactured_zeros"]["arm_reads"] += demotion["arm_reads_demoted"]
        for k, v in demotion["by_repo"].items():
            stats["demoted_manufactured_zeros"]["by_repo"][k] = (
                stats["demoted_manufactured_zeros"]["by_repo"].get(k, 0) + v)
        stats["demoted_manufactured_zeros"]["cells"] += sum(
            1 for c in cells
            if any(a.get("_demoted_manufactured_zero") for a in c["arms"].values()))
        stats["sources"].append({
            "path": src["_source_path"], "sha256": src["_source_sha256"],
            "cells": len(cells),
            "manufactured_zeros_demoted": demotion["arm_reads_demoted"]})

        for c in cells:
            mem_instance = c["memory_id"]      # an upstream instance_id, NOT schema's
            task_instance = c["task_id"]       # an upstream instance_id
            rep = c["representation"]
            repo = c["repo"]

            if c.get("excluded"):
                # The run excluded it for memory contagion -- diff syntax leaking into
                # a representation that must be compared against raw on equal footing.
                # Recorded, not silently dropped.
                stats["excluded_contagion_dirty"] += 1
                continue

            key = (mem_instance, task_instance, rep)
            if key in seen_keys:
                raise ConversionRefused(
                    f"REFUSING TO WRITE: cell {key} appears in two source artifacts. "
                    f"Keeping one and dropping the other would silently pick a run.")
            seen_keys.add(key)

            arms = c["arms"]
            if set(arms) != {"WITH", "WITHOUT"}:
                raise ConversionRefused(
                    f"REFUSING TO WRITE: cell {key} has arms {sorted(arms)}; a cell IS "
                    f"the paired contrast and half of one is not a row.")
            w, wo = arms["WITH"], arms["WITHOUT"]

            rw, rwo = w.get("reward"), wo.get("reward")
            delta = S.compute_delta_utility(rw, rwo)
            if rw is None or rwo is None:
                stats["cells_with_null_delta"] += 1
            stats["arms_with_null_reward"] += sum(1 for x in (rw, rwo) if x is None)
            if rw == 0.0 and rwo == 0.0:
                stats["both_arms_fail"] += 1
            stats["edit_status"][w.get("edit_status")] += 1
            stats["by_repo"][repo] += 1
            stats["by_representation"][rep] += 1

            in_tok = (_num(w.get("input_tokens")) or 0) + (_num(wo.get("input_tokens")) or 0)
            out_tok = (_num(w.get("output_tokens")) or 0) + (_num(wo.get("output_tokens")) or 0)
            rsn = [_num(w.get("reasoning_tokens")), _num(wo.get("reasoning_tokens"))]
            reasoning = None if any(x is None for x in rsn) else int(sum(rsn))

            row = S.blank_row()
            row.update(
                # ------------------------------------------------------ structural
                schema_version=S.SCHEMA_VERSION,
                condition_id=CONDITION_ID_FMT.format(rep=rep),
                created_at_utc=now,
                # ------------------------------------------------------ benchmark
                benchmark=BENCHMARK,
                benchmark_version=src["summary"]["benchmark_version"],
                # An upstream INSTANCE ID. An identifier, not content.
                source_episode_id=mem_instance,
                # 🔴 WITHHELD: episode metadata would carry repo/problem detail from
                #    an undeclared-licence corpus. The exporter's redact_row writes
                #    this same shape; writing it here means the LEDGER never holds it.
                source_episode_metadata={"__withheld__": True,
                                         "license": BENCHMARK},
                # ------------------------------------------------------ memory
                memory_representation=rep,
                memory_semantic_type=None,   # exempted: see BENCHMARK_NULLABLE_EXEMPTIONS
                memory_text=S.WITHHELD_SENTINEL,
                memory_tokens=None,          # exempted: bodies never persisted
                memory_source_span={"instance_id": mem_instance,
                                    "fields": ["problem_statement", "patch"],
                                    "patch_encoding": "defanged",
                                    "__content_withheld__": True},
                memory_writer_model=src["summary"]["model"] if rep != "raw" else
                                    "none:deterministic_render",
                memory_writer_cluster=src["summary"]["cluster"] if rep != "raw" else
                                      "none:deterministic_render",
                memory_writer_prompt_version=SWP.REPRESENTATION_SEGMENT_VERSION,
                memory_extraction_latency=None,
                memory_extraction_input_tokens=None,
                memory_extraction_output_tokens=None,
                # ------------------------------------------------------ embedding
                embedding_model=None,        # exempted: no embedding path exists
                embedding_version=None,
                memory_embedding_reference=None,
                # ------------------------------------------------------ task
                future_task_id=task_instance,
                future_task_family=None,     # exempted: benchmark declares none
                future_task_text=S.WITHHELD_SENTINEL,
                task_embedding_reference=None,
                semantic_similarity=None,    # exempted: needs two embeddings
                semantic_distance_band=None,
                # ------------------------------------------------------ retrieval
                retrieval_method="none",     # the pair is chosen, never retrieved
                retrieval_rank=None,
                retrieval_k=None,
                memory_tokens_retrieved=None,
                memory_tokens_exposed=None,
                # ------------------------------------------------------ execution
                replicate_id=0,
                seed_or_sampling_config={
                    "temperature": src["summary"]["temperature"],
                    "max_tokens": src["summary"]["max_tokens"],
                    "reasoning_effort": src["summary"]["reasoning_effort"]},
                reader_prompt_version=src["summary"]["prompt_version"],
                **reader,
                # ------------------------------------------------------ outcome
                # 🔴 WITHHELD, NOT not-retained. The response text EXISTS in
                #    results/swebench/representations_*.json. We may not redistribute
                #    it, because it can quote an undeclared-licence corpus.
                output_with_memory=S.WITHHELD_SENTINEL,
                output_without_memory=S.WITHHELD_SENTINEL,
                reward_with_memory=rw,
                reward_without_memory=rwo,
                delta_utility=delta,
                utility_label="undetermined",   # F (noise floor) unmeasured
                robustness_confidence=None,
                # ------------------------------------------------------ cost
                write_latency=None,
                retrieval_latency=None,
                generation_latency=None,     # exempted: runner discards latency_s
                end_to_end_latency=None,     # exempted
                embedding_calls=None,        # exempted: NOT 0 -- no path was attempted
                generation_calls=2,
                input_tokens=int(in_tok),
                output_tokens=int(out_tok),
                reasoning_tokens=reasoning,
                retry_count=None,            # exempted: NOT 0 -- never read
                error_code_if_any=None,
                # ------------------------------------------------------ provenance
                provenance={
                    "code_sha": code_sha,
                    "adapter_sha": adapter_sha,
                    "config_sha256": None,
                    "config_sha256_absent_reason":
                        "NOT RECORDED BY THE RUN. scripts/swebench_representations.py "
                        "takes its parameters as CLI arguments and reads no config "
                        "file, so no hash of one was measured. The parameters "
                        "themselves are on the row (reader_model, reader_cluster, "
                        "reader_reasoning_effort, seed_or_sampling_config) and were "
                        "cross-checked against the artifact's own summary block "
                        "before any row was written.",
                    "run_id": RUN_ID,
                    "host": "laptop",
                    "writer": "scripts/swebench_representations.py",
                    "converter": "scripts/swebench_to_schema.py",
                    # THE join keys: upstream instance ids. Identifiers, not content.
                    "memory_instance_id": mem_instance,
                    "task_instance_id": task_instance,
                    "repo": repo,
                    "upstream_repo_license": SW.UPSTREAM_LICENSES.get(repo),
                    # ---- our derived diagnostics, which ARE the point of the release
                    "edit_status_with": w.get("edit_status"),
                    "edit_status_without": wo.get("edit_status"),
                    "n_blocks_with": w.get("n_blocks"),
                    "n_blocks_without": wo.get("n_blocks"),
                    "localizer_recall": c.get("localizer_recall"),
                    "memory_contagion": c.get("memory_contagion"),
                    "contagion_with": w.get("contagion"),
                    "contagion_without": wo.get("contagion"),
                    "both_arms_fail": (rw == 0.0 and rwo == 0.0),
                    "finish_reason_with": w.get("finish_reason"),
                    "finish_reason_without": wo.get("finish_reason"),
                    "input_tokens_with": w.get("input_tokens"),
                    "input_tokens_without": wo.get("input_tokens"),
                    "output_tokens_with": w.get("output_tokens"),
                    "output_tokens_without": wo.get("output_tokens"),
                    "reasoning_tokens_with": w.get("reasoning_tokens"),
                    "reasoning_tokens_without": wo.get("reasoning_tokens"),
                    # A prompt HASH is not prompt text: it identifies the prompt
                    # without redistributing a byte of it.
                    "prompt_sha256_with": w.get("prompt_sha256"),
                    "prompt_sha256_without": wo.get("prompt_sha256"),
                    # ---- defect #21, per arm, so a consumer can see WHICH reads moved
                    "reward_demoted_manufactured_zero_with":
                        bool(w.get("_demoted_manufactured_zero")),
                    "reward_demoted_manufactured_zero_without":
                        bool(wo.get("_demoted_manufactured_zero")),
                    "manufactured_zero_rule":
                        "DEFECT_REGISTER #21: an arm-read whose test suite printed no "
                        "verdict (status_lines=0 in test_detail -- an import error, a "
                        "collection error, a missing test id) had a stored reward of "
                        "0.0 that the harness never measured. Those reads are demoted "
                        "to null ('could not be scored') BEFORE any derived number is "
                        "computed. A real 0.0 (the tests ran and failed, "
                        "status_lines >= 1) is untouched.",
                    # 🔴 The text embargo, stated on the row rather than only in a doc.
                    "text_withheld_reason":
                        "princeton-nlp/SWE-bench_Verified declares NO licence (HF API "
                        "cardData.license is None; no license:* tag; the card text "
                        "states none). The MIT grant covers the harness code, not the "
                        "corpus, and the issue text and patches belong to the upstream "
                        "OSS projects. An absent licence is NOT a permissive licence "
                        "and gated:false means FETCHABLE, not redistributable. This is "
                        "a LICENCE withholding -- the text exists on our disk in "
                        "results/swebench/representations_*.json -- and is therefore "
                        "spelled with WITHHELD_SENTINEL, never with "
                        "OUTPUT_NOT_RETAINED_BY_THE_RUN, which asserts the opposite "
                        "(that no text was ever written down). See "
                        "docs/BENCHMARK_LICENSES.md section 5.",
                    "reconstruct_from":
                        f"{SW.DATASET_REPO} :: {SW.DATASET_FILE} "
                        f"(sha256 {SW.DATASET_SHA256}, {SW.DATASET_N_ROWS} rows); "
                        f"join on provenance.memory_instance_id / task_instance_id.",
                    # 🔴 READ THIS BEFORE RECOMPUTING AN ID. On every other benchmark
                    # in this dataset memory_id is a CONTENT HASH of the memory text.
                    # Here it is not, and cannot be: the SWE-bench runner holds memory
                    # bodies in a local dict and never persists them, so no unredacted
                    # ledger of this text exists anywhere -- not withheld from the
                    # release, simply never written down. memory_id is therefore minted
                    # over WITHHELD_SENTINEL and is a stable identifier of
                    # (instance_id, representation), NOT a fingerprint of the memory.
                    # A consumer who rebuilds the text from upstream and re-derives the
                    # hash will get a DIFFERENT value; that is expected and is not
                    # corruption. Join on memory_instance_id / task_instance_id, which
                    # are the real keys, and never on memory_id across releases. The
                    # validator says so per row as id_unverifiable_withheld_input.
                    "memory_id_basis":
                        "minted over WITHHELD_SENTINEL; NOT a content hash of the "
                        "memory text (never persisted by the runner). Identifies "
                        "(memory_instance_id, memory_representation).",
                    "source_artifact": src["_source_path"],
                    "source_artifact_sha256": src["_source_sha256"],
                },
                license_source_reference=LICENSE_REF,
                # ------------------------------------------------------ verifier
                verifier_id=VERIFIER_ID,
                verifier_version=VERIFIER_VERSION,
                reward_is_continuous=False,   # the harness returns exactly {0.0, 1.0}
                leakage_flag=False,
                # ------------------------------------------------------ label rule
                utility_label_threshold=None,
                delta_utility_ci_lower=None,
                delta_utility_ci_upper=None,
                delta_utility_cell_mean=None,
                replicate_count=None,
                utility_label_rule_version=S.UTILITY_LABEL_RULE_VERSION,
                # ------------------------------------------------------ chronology
                source_episode_completion_timestamp=None,
                # ------------------------------------------------------ lineage
                parent_memory_id=None,
                # ------------------------------------------------------ quality
                compression_ratio=None,
                source_span_tokens=None,
                extraction_cost_proxy=None,
                faithfulness_check=None,
                faithfulness_notes=(
                    "NOT SCORED. The faithfulness proxy does not run on this "
                    "benchmark's write path (schema.FAITHFULNESS_PROXY_RUNS_AT_WRITE["
                    "'swebench_verified'] is False, measured: zero 'faithfulness' hits "
                    "in scripts/swebench_representations.py). The runner holds memory "
                    "bodies in a local dict and never persists them, so the proxy "
                    "cannot be run retroactively either."),
                faithfulness_detail=None,
                # ------------------------------------------------------ bearing
                bearing_label=None,
                bearing_evidence=None,
                # ------------------------------------------------------ embargo
                context_budget=None,
                propagation_metadata=None,
            )

            row["memory_id"] = S.compute_memory_id(row)
            row["cell_id"] = S.compute_cell_id(row)
            row["row_id"] = S.compute_row_id(row)

            # ---- the withholding must be DECLARED, not merely performed. GATE 6
            #      checks exactly this, and an undeclared blank is its own failure.
            row["license_policy"] = BENCHMARK
            row["text_fields_withheld"] = sorted(
                set(WITHHELD_TEXT_FIELDS) | {"source_episode_metadata"})
            row["reconstruction_required"] = True

            out.append(row)
            stats["rows_emitted"] += 1

    stats["by_repo"] = dict(stats["by_repo"])
    stats["by_representation"] = dict(stats["by_representation"])
    stats["edit_status"] = dict(stats["edit_status"])
    return out, stats


def assert_no_content(rows: Sequence[dict[str, Any]]) -> None:
    """Independent of the exporter: no row may carry text from this corpus.

    ``export_hf`` runs GATE 0/2b/6 over the same rows later. This is NOT a
    duplicate of that: a ledger that holds the content is a leak the moment
    anybody reads it with a different script, so the embargo is enforced where
    the bytes are written, not only where they are published.
    """
    bad: list[str] = []
    for i, r in enumerate(rows):
        for f in S.REDISTRIBUTABLE_TEXT_FIELDS:
            v = r.get(f)
            if v in (None, "", [], {}):
                continue
            if v == S.WITHHELD_SENTINEL:
                continue
            if isinstance(v, dict) and v.get("__withheld__") is True:
                continue
            if v == S.OUTPUT_NOT_RETAINED_SENTINEL:
                bad.append(
                    f"row {i} ({r.get('cell_id')}): {f} carries "
                    f"OUTPUT_NOT_RETAINED, which asserts the text was never written "
                    f"down. It WAS: this is a licence withholding and must use "
                    f"WITHHELD_SENTINEL.")
                continue
            bad.append(f"row {i} ({r.get('cell_id')}): {f} carries content "
                       f"({str(v)[:60]!r})")
    if bad:
        raise ConversionRefused(
            "REFUSING TO WRITE: SWE-bench rows carry redistributable text:\n  "
            + "\n  ".join(bad[:10]) + f"\n({len(bad)} total)")
    # And the schema's own helper, which is what the exporter will run.
    S.assert_content_redistributable(rows)


def self_test() -> list[str]:
    """Prove each refusal fires on a planted defect and stays quiet on a control."""
    lines: list[str] = []

    def ok(msg: str) -> None:
        lines.append(f"PASS {msg}")

    # -- the content embargo must catch a planted problem statement.
    base = {"benchmark": BENCHMARK, "cell_id": "c1",
            "text_fields_withheld": ["memory_text", "future_task_text",
                                     "output_with_memory", "output_without_memory",
                                     "source_episode_metadata"],
            "memory_text": S.WITHHELD_SENTINEL,
            "future_task_text": S.WITHHELD_SENTINEL,
            "output_with_memory": S.WITHHELD_SENTINEL,
            "output_without_memory": S.WITHHELD_SENTINEL,
            "source_episode_metadata": {"__withheld__": True, "license": BENCHMARK}}
    assert_no_content([dict(base)])
    ok("embargo-negative: a correctly withheld SWE-bench row is accepted")

    leaked = dict(base, memory_text="QuerySet.none() raises on django 2.1 ...")
    try:
        assert_no_content([leaked])
        raise AssertionError("a planted problem statement was NOT caught")
    except ConversionRefused:
        ok("embargo: a planted issue/problem statement in memory_text was caught")

    leaked2 = dict(base, output_with_memory="<<<<<<< SEARCH\n def foo():\n")
    try:
        assert_no_content([leaked2])
        raise AssertionError("a planted model response was NOT caught")
    except ConversionRefused:
        ok("embargo: a planted model response in output_with_memory was caught")

    # -- the WRONG SENTINEL must be caught. This is the distinction the card and the
    #    code both have to keep: not-retained says 'never written down'; this text
    #    exists and is withheld for licence. A silent swap would publish a false
    #    stated reason, and the generic embargo check would NOT see it.
    wrong = dict(base, output_with_memory=S.OUTPUT_NOT_RETAINED_SENTINEL)
    try:
        assert_no_content([wrong])
        raise AssertionError("OUTPUT_NOT_RETAINED on a withheld field was NOT caught")
    except ConversionRefused as exc:
        assert "WITHHELD_SENTINEL" in str(exc)
        ok("sentinel: OUTPUT_NOT_RETAINED is refused where the text EXISTS and is "
           "withheld for licence (the two reasons must not be spelled the same way)")

    # -- an UNDECLARED withholding must be caught by the schema helper.
    undeclared = dict(base, text_fields_withheld=["memory_text"])
    try:
        S.assert_content_redistributable([undeclared])
        raise AssertionError("an undeclared withholding was NOT caught")
    except ValueError:
        ok("gate6: a blanked field missing from text_fields_withheld was caught")

    # -- defect #21: the imported demotion must move a manufactured zero, keep a real
    #    one, and be idempotent. Re-asserted HERE because this script depends on it.
    def mk(detail_w: str, detail_wo: str, rw: float, rwo: float) -> dict[str, Any]:
        return {"repo": "x/x", "arms": {
            "WITH": {"reward": rw, "test_detail": detail_w},
            "WITHOUT": {"reward": rwo, "test_detail": detail_wo}}}

    plant = [
        mk("F2P rc=1 status_lines=0 :: ImportError", "F2P rc=1 status_lines=4 :: F", 0.0, 0.0),
        mk("F2P rc=1 status_lines=3 :: FAILED", "F2P rc=1 status_lines=9 :: F", 0.0, 0.0),
    ]
    led = demote_manufactured_zeros(plant)
    assert led["arm_reads_demoted"] == 1, led
    assert plant[0]["arms"]["WITH"]["reward"] is None, "manufactured 0.0 not demoted"
    assert plant[0]["arms"]["WITHOUT"]["reward"] == 0.0, "a REAL 0.0 was demoted"
    assert plant[1]["arms"]["WITH"]["reward"] == 0.0, "a REAL 0.0 was demoted"
    ok("defect21: a manufactured 0.0 (status_lines=0) is demoted to null and a REAL "
       "0.0 is left untouched")
    assert demote_manufactured_zeros(plant)["arm_reads_demoted"] == 0
    ok("defect21: the demotion is idempotent (a post-fix artifact is a no-op)")

    # -- a converter that accepts a mis-configured artifact is the defect.
    try:
        load_source_dict({"summary": dict(EXPECTED_SUMMARY, model="gpt-4o"),
                          "cells": [{}]})
        raise AssertionError("a mismatched model was NOT caught")
    except ConversionRefused:
        ok("config: an artifact whose model differs from this converter's is refused")

    return lines


def load_source_dict(d: dict[str, Any]) -> dict[str, Any]:
    """The summary cross-check, factored out so self_test can exercise it."""
    for k, want in EXPECTED_SUMMARY.items():
        got = d["summary"].get(k)
        if got != want:
            raise ConversionRefused(
                f"REFUSING TO WRITE: summary[{k!r}]={got!r} but this converter stamps "
                f"{want!r} onto every row.")
    return d


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", action="append", default=[], type=Path,
                    help="representation artifact; repeatable")
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "results/ledgers/swebench/cells_v3.jsonl")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        try:
            for line in self_test():
                print("  " + line)
        except AssertionError as exc:
            print(f"SELF-TEST FAILED: {exc}", file=sys.stderr)
            return 2
        print("self-test OK: every refusal fired on its planted defect and stayed "
              "quiet on its negative control")
        return 0

    if not args.src:
        print("ABORT: no --src given", file=sys.stderr)
        return 2

    try:
        sources = [load_source(p if p.is_absolute() else REPO_ROOT / p)
                   for p in args.src]
        rows, stats = convert(sources)
        assert_no_content(rows)
    except ConversionRefused as exc:
        print(str(exc), file=sys.stderr)
        print("\nNOTHING WAS WRITTEN.", file=sys.stderr)
        return 1

    rep = V.validate_dataset(rows)
    print(rep.summary())
    if rep.errors:
        print("\nREFUSING TO WRITE: the rows do not validate.", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    S.write_jsonl_atomic(args.out, rows)
    print()
    print(json.dumps(stats, indent=2, default=str))
    print(f"\nwrote {len(rows)} {S.SCHEMA_VERSION} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

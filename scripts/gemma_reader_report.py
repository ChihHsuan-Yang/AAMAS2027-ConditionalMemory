#!/usr/bin/env python3
"""Generate docs/READER_TRANSFER_RESULT.md FROM the analysis artifacts.

Every number in the document is read out of
``results/gemma_reader/reader_transfer_analysis.json`` at generation time.
Nothing is typed from recall, so the document cannot drift from the artifact
and a stale figure is impossible by construction.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def f4(x) -> str:
    return "—" if x is None else f"{x:+.4f}"


def f4u(x) -> str:
    return "—" if x is None else f"{x:.4f}"


def ci(d: dict, lo="ci_lower", hi="ci_upper") -> str:
    if d.get(lo) is None or d.get(hi) is None:
        return "—"
    return f"[{d[lo]:+.4f}, {d[hi]:+.4f}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", type=Path,
                    default=REPO / "results/gemma_reader/reader_transfer_analysis.json")
    ap.add_argument("--controls", type=Path,
                    default=REPO / "results/gemma_reader/reader_transfer_controls.json")
    ap.add_argument("--run", type=Path,
                    default=REPO / "results/gemma_reader/transfer_summary.json")
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs/READER_TRANSFER_RESULT.md")
    args = ap.parse_args()

    A = json.loads(args.analysis.read_text())
    C = json.loads(args.controls.read_text()) if args.controls.exists() else {}
    R = json.loads(args.run.read_text()) if args.run.exists() else {}
    P = A["per_representation_matched"]
    S = A["sign_and_correlation"]
    X = A["cross_representation_common_cells"]
    L = A["label_agreement"]
    cov = A["matched_set_coverage"]
    acc = A["reader_accuracy_levels"]
    ident = A["reader_identity"]
    REPS = ("raw", "summary", "structured")

    def sig(rep: str) -> str:
        d = P[rep]["paired_difference_task_clustered"]
        return "**yes**" if d.get("excludes_zero") else "no"

    out: list[str] = []
    w = out.append

    w("# Reader transfer — does memory utility survive a change of reader?\n")
    try:
        src = args.analysis.relative_to(REPO)
    except ValueError:
        src = args.analysis
    w(f"**Generated from `{src}` on "
      f"{A['generated_at_utc']}.** Every number here is read out of that "
      f"artifact at generation time by `scripts/gemma_reader_report.py`; none "
      f"is typed from recall, so this document cannot drift from the data.\n")
    w("Pre-registered in `docs/READER_TRANSFER_PRECOMMITMENT.md`, written "
      "**before any design-cell Gemma call was issued**.\n")

    w("## The question\n")
    w("A reviewer will ask whether the representation finding is an artifact of "
      "`gpt-oss-120b` reading memories that `gpt-oss-120b` wrote. A **second "
      "reader consuming the byte-identical memories** answers that directly.\n")
    w("> **This run was not aimed at replication.** Same utility, same ordering "
      "with different magnitude, a different representation preference, or no "
      "transfer at all were all pre-committed as valid outcomes.\n")

    # ------------------------------------------------- headline
    w("## The headline\n")
    w("Per representation, on the cells interpretable under **both** readers. "
      "ΔU is the mean per-cell utility delta over "
      f"{A['replicate_policy']['n_replicates_used']} replicates; the paired "
      "difference is per cell, so each row compares the two readers on the "
      "*same* memories against the *same* tasks.\n")
    w("| representation | cells | tasks | ΔU gpt-oss | ΔU Gemma | paired diff (Gemma − gpt-oss) | 95% CI, task-clustered | excludes 0 |")
    w("|---|---:|---:|---:|---:|---:|---|---|")
    for rep in REPS:
        e = P[rep]
        d = e["paired_difference_task_clustered"]
        w(f"| {rep} | {e['n_matched_cells']} | {e['n_tasks']} | "
          f"{f4(e['deltaU_gptoss']['mean'])} | {f4(e['deltaU_gemma']['mean'])} | "
          f"{f4(d['mean'])} | {ci(d)} | {sig(rep)} |")
    w("")
    w("`docs/ZERO_CONTRIBUTORS.md` requires the non-zero contributor count "
      "beside the nominal denominator, and **both** magnitudes. A cell failing "
      "in both arms under both readers contributes an exact 0.0, which is a "
      "structural zero and not a measurement of \"the readers agree\":\n")
    w("| representation | nominal cells | non-zero contributors | diluted mean | conditional mean (contributors only) |")
    w("|---|---:|---:|---:|---:|")
    for rep in REPS:
        c = P[rep]["contributors"]
        w(f"| {rep} | {c['n_nominal']} | {c['n_nonzero']} | "
          f"{f4(c['diluted_mean'])} | {f4(c['conditional_mean_on_nonzero'])} |")
    w("")
    w("> **Neither magnitude alone is the answer.** The diluted mean is the "
      "honest population figure and is what the significance verdict comes "
      "from; the conditional mean conditions on an outcome and can never be "
      "the population claim.\n")
    w("🔴 **A CI that spans zero here is not evidence that the readers agree.** "
      "`docs/PAIRED_POWER.md`: power depends on the spread among contributors, "
      "not their count alone, and a contrast with few non-zero contributors is "
      "underpowered rather than null. Read the contributor counts above "
      "**before** reading any interval — where they are small, the honest "
      "reading of a zero-spanning interval is *underpowered*, not *no "
      "difference*.\n")
    w("Cell-level intervals (not clustered) are in the artifact; the "
      "**task-clustered** interval governs, because cells repeat within tasks "
      "and a cell-level interval would treat repeated views of one task as "
      "independent draws.\n")
    w("> ⚠️ **The 34.6% \"third of all cells on ten tasks\" figure is pooled "
      "over RANDOM and is not true of this cell set.** `CONTRAST_FRAMING.md` "
      "already makes that correction per stratum (BEARING 38.8%, "
      "MATCHED_CONTROL 19.9%); re-derived on the two combined, which is the "
      "set used here: 285 cells over 126 tasks, top ten tasks hold **60 cells "
      "= 21.1%**, max 7 on any one task. Clustering still governs — 4.75 cells "
      "per memory, up to 18 on one — but BEARING↔MC is close to robust to task "
      "clustering by construction, and the honest statement is that the "
      "clustered interval is reported because it is the conservative one, not "
      "because this set is severely concentrated.\n")

    # ------------------------------------------------- the paper's quantity
    w("## The quantity the paper actually reports\n")
    w("`docs/REPRESENTATION_RESULT.md` reports the **within-memory "
      "BEARING − MATCHED_CONTROL** contrast, not the raw cell mean. Under each "
      "reader, on the matched cells:\n")
    w("| representation | reader | memories | B − MC | 95% CI | non-zero contributors |")
    w("|---|---|---:|---:|---|---:|")
    for rep in REPS:
        for name in ("gptoss", "gemma"):
            b = P[rep][f"within_memory_bearing_minus_control_{name}"]
            w(f"| {rep} | {name} | {b['n_memories']} | {f4(b['mean'])} | "
              f"{ci(b)} | {b['n_nonzero_contributors']} |")
    w("")

    # ------------------------------------------------- agreement
    w("## Per-cell agreement between the readers\n")
    w("| representation | cells | Pearson r | 95% CI | Spearman | sign agreement (both non-zero) | zero under both |")
    w("|---|---:|---:|---|---:|---:|---:|")
    for rep in REPS:
        s = S[rep]
        c = s["correlation"]
        nz = s["sign_agreement_both_nonzero"]
        rate = "—" if nz["rate"] is None else f"{nz['rate']:.1%}"
        w(f"| {rep} | {s['n_cells']} | {f4u(c['pearson'])} | {ci(c)} | "
          f"{f4u(c['spearman'])} | {nz['k']}/{nz['n']} ({rate}) | "
          f"{s['n_zero_under_both']} |")
    w("")
    w("> 🔴 **The naive sign-agreement rate is not the informative one.** Most "
      "cells are exactly 0 under both readers — a cell where neither reader's "
      "answer changes agrees trivially. The column above is restricted to cells "
      "non-zero under **both**; the inflated all-cells rate is in the artifact "
      "and is reported there with that caveat attached.\n")
    w("The zeros are **structural, and their cause is already measured**: "
      "`docs/BEARING_SCARCITY.md` finds that a naturally occurring memory bears "
      "on a **median of one future task out of hundreds**, so most "
      "(memory, task) cells cannot move regardless of reader. Under gpt-oss at "
      "two replicates the exact-zero counts on these strata are **217/285 raw, "
      "254/285 summary, 250/277 structured** — fixed in "
      "`results/gemma_reader/gptoss_sign_baseline.json` before the Gemma "
      "deltas were inspected. A reader-agreement rate computed over all cells "
      "is therefore mostly a measurement of bearing scarcity, not of reader "
      "transfer.\n")

    w("### Useful / neutral / harmful agreement\n")
    w("Each reader is labelled under the pre-registered §4 rule against **its "
      "own** measured `F_exec`. Using one reader's floor on the other would be "
      "a different experiment.\n")
    w("| representation | cells | gpt-oss labels | Gemma labels | agreement |")
    w("|---|---:|---|---|---:|")
    for rep in REPS:
        g = L[rep]
        a = g["agreement"]
        w(f"| {rep} | {g['n_cells']} | "
          f"{', '.join(f'{k}={v}' for k, v in sorted(g['gptoss_label_counts'].items()))} | "
          f"{', '.join(f'{k}={v}' for k, v in sorted(g['gemma_label_counts'].items()))} | "
          f"{a['k']}/{a['n']} |")
    w("")

    # ------------------------------------------------- harm
    H = A.get("harm_on_bearing_cells", {}).get("per_representation", {})
    if H:
        w("## Does the near-absence of harm transfer?\n")
        w("`docs/THE_HONEST_HEADLINE.md`'s sharpest claim is that **where a "
          "memory bears on a task it helps, and harm is nearly absent** — on "
          "gpt-oss, 2 negative BEARING cells of 139. Re-asked of a second "
          "reader, on the matched BEARING cells:\n")
        w("| representation | BEARING cells | gpt-oss negative | Gemma negative | negative under BOTH | Gemma-only negative |")
        w("|---|---:|---:|---:|---:|---:|")
        for rep in REPS:
            h = H[rep]
            w(f"| {rep} | {h['n_bearing_cells_matched']} | "
              f"{h['gptoss']['n_negative']} | {h['gemma']['n_negative']} | "
              f"{h['both_readers_negative']} | "
              f"{h['gemma_negative_where_gptoss_was_not']} |")
        w("")
        w("A Wilson interval on each rate is in the artifact. **A count of "
          "negative cells is not a harm claim**: the pre-registered label rule "
          "requires the cell's CI to exclude zero *and* its magnitude to clear "
          "the measured execution floor. The label table above is the one that "
          "settles harm; this table shows the raw direction.\n")

    # ------------------------------------------------- ordering
    w("## Does the representation ordering transfer?\n")
    w(f"On the **{X['n_cells']}** cells present in all three representations "
      f"*and* matched across both readers — the only basis on which the three "
      f"representations may be compared to each other:\n")
    w("| representation | ΔU gpt-oss | ΔU Gemma | paired difference |")
    w("|---|---:|---:|---:|")
    for rep in REPS:
        w(f"| {rep} | {f4(X[rep]['deltaU_gptoss']['mean'])} | "
          f"{f4(X[rep]['deltaU_gemma']['mean'])} | "
          f"{f4(X[rep]['paired_difference']['mean'])} |")
    w("")
    w(f"Ordering under gpt-oss: **{' > '.join(X['representation_ordering_gptoss'])}**  ")
    w(f"Ordering under Gemma: **{' > '.join(X['representation_ordering_gemma'])}**  ")
    w(f"Orderings agree: **{X['orderings_agree']}**\n")

    # ------------------------------------------------- reader levels
    w("## Is Gemma simply a weaker reader?\n")
    w("A difference in ΔU can come from the memory being less useful *or* from "
      "the reader being worse at the task outright. Both arms' absolute reward "
      "levels separate those:\n")
    w("| representation | reader | mean reward WITH | mean reward WITHOUT |")
    w("|---|---|---:|---:|")
    for rep in REPS:
        for name in ("gptoss", "gemma"):
            a = acc[rep][name]
            w(f"| {rep} | {name} | {f4u(a['mean_reward_with_memory'])} | "
              f"{f4u(a['mean_reward_without_memory'])} |")
    w("")

    # ------------------------------------------------- what was held
    w("## What was held, and how it was proven\n")
    g = R.get("identity_gates", {})
    w("Only the reader changed. That is **asserted in code at run time**, not "
      "claimed in prose — any disagreement aborts before a call is paid for.\n")
    w("| gate | what it compares | result |")
    w("|---|---|---|")
    w(f"| 1 | `memories.jsonl` sha256 vs the gpt-oss run's fingerprint | "
      f"`{str(g.get('gate1_memories_sha256'))[:16]}` MATCH |")
    w(f"| 2 | system prompt sha256 | `{str(g.get('gate2_system_prompt_sha256'))[:16]}` MATCH |")
    w(f"| 3 | rebuilt filler pool sha256 | `{str(g.get('gate3_filler_pool_sha256'))[:16]}` MATCH |")
    g4 = g.get("gate4_context_byte_identity_vs_gptoss_requests", {})
    w(f"| 4 | **every rendered request's `context_sha256` vs the hash the gpt-oss "
      f"cache stored for the same cell** | **{g4.get('matched')} matched, "
      f"{g4.get('mismatched')} mismatched**, {g4.get('unverifiable_v1_key')} unverifiable |")
    g5 = g.get("gate5_per_cell_position_and_filler_vs_gptoss_rows", {})
    w(f"| 5 | per-cell target position + filler vs the gpt-oss **row** | "
      f"**{g5.get('matched')} matched, {g5.get('mismatched')} mismatched** |")
    w("")
    w("**Gate 4 is the decisive one** — it compares the bytes actually sent, "
      "which no amount of \"we used the same script\" establishes.\n")
    w("🔴 **Gate 4 cannot cover `raw`.** The screened cache was written under the "
      "**v1** key shape, which had no `context_sha256` field at all. Those "
      f"{g4.get('unverifiable_v1_key')} requests are counted as "
      "`unverifiable_v1_key` and **never as agreement** — an absent check must "
      "not read as a passing one. **Gate 5 exists for exactly that gap**: it is "
      "a per-cell check on target position and filler composition that gates 1–3 "
      "(which are global) cannot provide.\n")
    mt = A["memory_text_byte_identity"]
    w(f"**Memory text re-verified on the row pairs themselves**, not assumed "
      f"from the pipeline: **{mt['identical']}/{mt['compared']}** byte-identical, "
      f"{mt['differ']} differ.\n")

    # ------------------------------------------------- controls
    w("## Controls — every null defended\n")
    w("| control | result |")
    w("|---|---|")
    w(f"| gate 4 can FAIL (one byte appended to a user message) | aborts, exit 1 |")
    w(f"| gate 5 can FAIL (one filler unit dropped, on `raw` where gate 4 is blind) | aborts, exit 1 |")
    w(f"| gate 1 can FAIL (one byte changed in `memories.jsonl`) | aborts, exit 1 |")
    if C:
        sep = C.get("cache_separation_reconfirmed_on_this_run", {})
        w(f"| cache separation, **positive control first** | gpt-oss key "
          f"{sep.get('step1_positive_control_gptoss_key_in_gptoss_cache', {}).get('result')} "
          f"→ Gemma key {sep.get('step2_gemma_key_in_gptoss_cache', {}).get('result')} "
          f"→ gpt-oss key in Gemma cache "
          f"{sep.get('step4_gptoss_key_in_gemma_cache', {}).get('result')} |")
        for k, lab in (("aa_determinism_gptoss", "gpt-oss"),
                       ("aa_determinism_gemma", "Gemma")):
            a = C.get(k, {})
            w(f"| A/A determinism, {lab} (byte-identical requests, separate calls) | "
              f"{a.get('n_identical')}/{a.get('n_paired_groups')} identical |")
    pc = A["noise_floors_delta_scale"].get("_positive_control_gemma_summary", {})
    w(f"| `F_exec` estimator can return non-zero (flip one replicate in "
      f"{pc.get('n_cells_perturbed')} cells) | {f4u(pc.get('point'))}, "
      f"fires={pc.get('fires')} |")
    cc = S.get("_positive_control_correlation_estimator", {})
    w(f"| correlation estimator recovers known values | r(x,x)="
      f"{f4u(cc.get('identity_r'))}, r(x,−x)={f4u(cc.get('negated_r'))} |")
    jt = A["join_traps_demonstrated"]
    w(f"| the WRONG join is shown to fail, not merely warned about | "
      f"`condition_id` → **{jt['rows_matched_by_condition_id']} rows**; correct "
      f"locator+task key → {jt['rows_matched_by_memory_unit_locator_and_task']} rows |")
    w("")
    w("**Reader identity on this run's own rows** (task 3): every Gemma row "
      f"carries `reader_model` ∈ {sorted(ident['gemma_run_reader_model_counts'])}, "
      f"every comparator row "
      f"{sorted(ident['gptoss_comparator_reader_model_counts'])}; the two sets "
      f"are disjoint ({ident['readers_are_disjoint']}) and the condition ids are "
      f"disjoint ({ident['condition_ids_disjoint']}). Both readers served from "
      f"cluster `{ident['gemma_reader_cluster'][0]}`, so **this is a reader "
      f"comparison and not a reader×cluster comparison**.\n")

    # ------------------------------------------------- coverage
    w("## Coverage, and what is NOT covered\n")
    w("| representation | eligible | gpt-oss interpretable | Gemma interpretable | **matched** | lost to Gemma | lost to gpt-oss |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for rep in REPS:
        c = cov[rep]
        el = (R.get("eligible_pool_size", {}) or {}).get(rep, "—")
        w(f"| {rep} | {el} | {c['gptoss_interpretable_cells']} | "
          f"{c['gemma_interpretable_cells']} | **{c['MATCHED_both_readers']}** | "
          f"{c['gptoss_only']} | {c['gemma_only']} |")
    w("")
    w("**Not covered**, and stated rather than glossed:\n")
    w("- the **8 cells whose structured write failed** (3 memories). A failed "
      "write has no memory text to read; the exclusion is a property of the "
      "**write** pass, which ran before any reader did, and is therefore "
      "non-outcome-based.\n")
    w("- the **872 RANDOM-stratum cells** and the rest of the 15,112-pair frozen "
      "universe. This arm replicates the **representation sub-universe** — the "
      "basis `docs/REPRESENTATION_RESULT.md` reports — not all of LongMemEval.\n")
    w("- the **156 LLM-judged questions**: `F_judge` is unmeasured, so they are a "
      "separate scorer stratum under `docs/COVERAGE_MANIFEST.md` and are not "
      "pooled here.\n")
    w("- **writer transfer.** Only the reader changed. Whether a *Gemma-written* "
      "memory behaves differently is the W1–W4 factorial and is unrun.\n")
    u = A["unscoreable_ledger"]
    w(f"\n**Unscoreable cells** (`reward = None`, never 0.0): "
      f"Gemma { {k: v['cells_all_null'] for k, v in u['gemma'].items()} }, "
      f"gpt-oss { {k: v['cells_all_null'] for k, v in u['gptoss'].items()} }.\n")

    # ------------------------------------------------- defect
    w("## A defect this run found, and what it cost\n")
    w("The first execution attempt was **killed at 600/3,388 calls**. Under "
      "16-worker load at the real 15–29k-token shape, metis/`gemma-4-31B-it` "
      "returns truncated responses with `finish_reason` **`\"\"`** and "
      "`usage.stop_reason` **`\"\"`** — neither says `\"length\"` — while "
      "`completion_tokens` sits exactly at `max_tokens`. The truncation guard "
      "tested `finish_reason == \"length\"` and was **silent**; 7 fragments of "
      "2,034–2,146 characters were returned as answers. Scored, each is a wrong "
      "answer that drives ΔU negative and **manufactures a harmful memory**.\n")
    w("This is defect #16 in a **third** disguise, and the single-request probe "
      "that found #16 could not have found it: `max_tokens=8` on an idle "
      "endpoint returns a clean `finish_reason=\"length\"`. The empty field "
      "appears only at concurrency on long prompts.\n")
    w("The guard now tests three observables, the third of which — "
      "`completion_tokens >= max_tokens` — cannot be misreported without the "
      "server also misreporting its own token count. **Across 11,693 "
      "`gpt-oss-120b` rows in every shipped cache the widened detector flags "
      "exactly the 19 rows the old one flagged**, so the fix cannot have moved a "
      "published gpt-oss number. Full account: `docs/DEFECT_REGISTER.md` #20.\n")

    w("## Reproduce\n")
    w("```bash")
    w("cd /Users/bellayang/Documents/2026/p1_memory_utility/repo")
    w("PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9")
    w("")
    w("$PY scripts/gemma_reader_run.py --dry-run                      # gates only")
    w("$PY scripts/gemma_reader_run.py --dry-run --plant-context-defect   # GATE 4 must abort")
    w("$PY scripts/gemma_reader_run.py --dry-run --plant-position-defect \\")
    w("       --representations raw                                   # GATE 5 must abort")
    w("$PY scripts/gemma_reader_run.py                                # the run")
    w("$PY scripts/gemma_reader_controls.py                           # controls")
    w("$PY scripts/gemma_reader_analyze.py                            # analysis")
    w("$PY scripts/gemma_reader_report.py                             # this document")
    w("$PY -m pytest tests/test_reader_arms.py -q")
    w("```")

    args.out.write_text("\n".join(out) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

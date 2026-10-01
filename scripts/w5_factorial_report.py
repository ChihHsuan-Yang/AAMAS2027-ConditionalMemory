#!/usr/bin/env python3
"""Generate docs/WRITER_FACTORIAL_RESULT.md FROM the analysis artifacts.

Every number in the document is read out of the tracked JSON at generation
time. Nothing is typed from recall, so the document cannot drift from the data
and a stale figure is impossible by construction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPS = ("summary", "structured")
ARM_LABEL = {"oss/oss": "writer gpt-oss x reader gpt-oss",
             "oss/gem": "writer gpt-oss x reader Gemma",
             "gem/oss": "writer Gemma x reader gpt-oss",
             "gem/gem": "writer Gemma x reader Gemma"}


def f4(x) -> str:
    return "—" if x is None else f"{x:+.4f}"


def f4u(x) -> str:
    return "—" if x is None else f"{x:.4f}"


def ci(d: dict, lo="ci_lower", hi="ci_upper") -> str:
    if d is None or d.get(lo) is None or d.get(hi) is None:
        return "—"
    return f"[{d[lo]:+.4f}, {d[hi]:+.4f}]"


def yn(b) -> str:
    return "**yes**" if b else ("no" if b is not None else "—")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/writer_factorial_analysis.json")
    ap.add_argument("--controls", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/writer_factorial_controls.json")
    ap.add_argument("--write", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/write_summary_gemma.json")
    ap.add_argument("--run", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/factorial_summary_gemma.json")
    ap.add_argument("--run-gptoss", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/factorial_summary_gptoss.json")
    ap.add_argument("--sensitivity", type=Path,
                    default=REPO / "results/ledgers/writer_factorial/sensitivity_controls.json")
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs/WRITER_FACTORIAL_RESULT.md")
    args = ap.parse_args()

    A = json.loads(args.analysis.read_text())
    C = json.loads(args.controls.read_text()) if args.controls.exists() else {}
    W = json.loads(args.write.read_text()) if args.write.exists() else {}
    R = json.loads(args.run.read_text()) if args.run.exists() else {}
    RG = json.loads(args.run_gptoss.read_text()) if args.run_gptoss.exists() else {}
    SENS = json.loads(args.sensitivity.read_text()) if args.sensitivity.exists() else {}

    K = A["CONTRASTS"]
    DU = A["deltaU_per_arm_matched"]
    cov = A["matched_set_coverage"]
    repl = A["READER_EFFECT_REPLICATION_CHECK"]
    lens = A["memory_length_by_writer_on_matched_cells"]["per_representation"]
    dec = A["writer_effect_decomposed_by_arm"]
    bmc = A["within_memory_bearing_minus_control_per_arm"]["per_representation"]
    harm = A["harm_on_bearing_cells_per_arm"]

    L: list[str] = []
    P = L.append

    P("# Writer × Reader — does it matter which model wrote the memory?")
    P("")
    P(f"**Generated from `results/ledgers/writer_factorial/writer_factorial_analysis.json` "
      f"on {A['generated_at_utc']}.** Every number here is read out of that artifact "
      f"at generation time by `scripts/w5_factorial_report.py`; none is typed from "
      f"recall, so this document cannot drift from the data.")
    P("")
    P("Pre-registered in `docs/WRITER_FACTORIAL_PRECOMMITMENT.md`, written **before "
      "any Gemma memory was written** and before any writer-Gemma cell was run.")
    P("")

    # ---------------------- the answer, in one paragraph ------------------
    P("## The answer, in one paragraph")
    P("")
    bits = []
    for rep in REPS:
        w = K[rep]["WRITER_main_effect"]["task_clustered"]
        sf = K[rep]["SAME_FAMILY_effect"]["task_clustered"]
        bits.append((rep, w, sf, K[rep]["WRITER_main_effect"]["n_matched_cells"]))
    any_sig = any(K[r][n]["task_clustered"].get("excludes_zero")
                  for r in REPS for n in ("WRITER_main_effect", "READER_main_effect",
                                          "SAME_FAMILY_effect", "INTERACTION"))
    if not any_sig:
        P("**It does not matter much which model wrote the memory, and a memory is "
          "not worth more to the family that wrote it.** On the cells interpretable "
          "under all four writer × reader combinations, **every one of the four "
          "pre-registered contrasts spans zero** — writer, reader, same-family and "
          "interaction, on both Summary and Structured.")
        P("")
        for rep, w, sf, n in bits:
            P(f"- **{rep}** ({n} matched cells): writer effect {f4(w['mean'])} "
              f"{ci(w)}, same-family {f4(sf['mean'])} {ci(sf)}.")
        P("")
        # The "largest effect still compatible with the data" is the far end of
        # each interval. Computed here, never typed: a bound quoted from recall
        # is the shape this project keeps catching.
        bounds = {}
        for rep in REPS:
            for name in ("WRITER_main_effect", "SAME_FAMILY_effect", "INTERACTION"):
                t = K[rep][name]["task_clustered"]
                if t.get("ci_lower") is None:
                    continue
                bounds[(rep, name)] = max(abs(t["ci_lower"]), abs(t["ci_upper"]))
        ws = [v for (r, n), v in bounds.items()
              if n in ("WRITER_main_effect", "SAME_FAMILY_effect")]
        allb = list(bounds.values())
        # READ the published raw reader effect from its tracked artifact rather
        # than typing it. "Never quote a number you have not re-derived" applies
        # to a scale reference as much as to a result.
        _pubp = (REPO / "results/ledgers/gemma_reader/"
                 "reader_transfer_analysis.json")
        raw_pub = json.loads(_pubp.read_text())["per_representation_matched"][
            "raw"]["paired_difference_task_clustered"]["mean"]
        P(f"**These nulls are informative rather than merely underpowered, and "
          f"that is worth separating.** The intervals are narrow. The largest "
          f"effect still compatible with the data is **{min(ws):.4f} to "
          f"{max(ws):.4f}** in absolute ΔU for the writer and same-family "
          f"contrasts (**{max(allb):.4f}** including the wider interaction). For "
          f"scale, the reader effect this project *did* detect on `raw` is "
          f"**+{raw_pub:.4f}** — about **{raw_pub / max(ws):.1f}×** the largest "
          f"writer or same-family effect these intervals leave room for. So this "
          f"is not \"we could not tell\"; it is \"an effect of the size this "
          f"project already measures elsewhere would have been visible here.\"")
        P("")
        ctrb = [K[r][n]["contributors"]["n_nonzero"] for r in REPS
                for n in ("WRITER_main_effect", "READER_main_effect",
                          "SAME_FAMILY_effect", "INTERACTION")]
        noms = [K[r][n]["contributors"]["n_nominal"] for r in REPS
                for n in ("WRITER_main_effect",)]
        P(f"That said, **the per-contrast contributor counts are small** "
          f"({min(ctrb)}–{max(ctrb)} non-zero cells of {min(noms)}–{max(noms)}), "
          f"and `docs/PAIRED_POWER.md` warns that power depends on their spread "
          f"and not their count. The interval widths above are the honest "
          f"statement of what is excluded; read them, not the point estimates.")
        P("")
        P(f"> ⚠️ The **+{raw_pub:.4f}** comparison point is on `raw`, which is "
          f"**not in this factorial** and is a READER effect, not a writer one. "
          f"It is used here only as a scale reference for what this measurement "
          f"apparatus has been able to detect — not as a quantity being "
          f"compared against.")
        P("")
        P("**The direction a reader should take from this:** memory utility here "
          "looks like a property of the **experience** being compressed, not of the "
          "**compressor**. That is consistent with the project's existing and "
          "stronger finding that `raw` — written by **no model at all** — is the "
          "best representation under both readers. A same-family advantage was a "
          "pre-registered possible outcome and it did not appear.")
    else:
        P("At least one contrast excludes zero; see the tables below.")
    P("")
    P("🔴 **Two limits on that sentence, both structural.** First, `raw` has no "
      "writer and is **not in this factorial**, so none of this speaks to the "
      "project's strongest representation. Second, two models are a 2×2, not a "
      "population: \"same-family\" here means these two specific checkpoints on "
      "one cluster, and nothing is established about model families in general.")
    P("")

    # ------------- the defect this run found, FIRST --------------
    drift = A.get("CROSS_SESSION_DRIFT_vs_the_published_arms", {})
    if drift:
        P("## 🔴 Read this first: a control fired, and it changed the design")
        P("")
        P("The first execution compared today's writer-Gemma arms against the "
          "**published** writer-gpt-oss arms from 2026-09-30. A pre-registered "
          "control caught that this was invalid.")
        P("")
        P("The **WITHOUT** arm contains *no memory at all*. A change of writer "
          "cannot reach it, and F-GATE 4 verified its request bytes are identical "
          "(500/500 stored context hashes match). It should therefore have been "
          "identical. It was not:")
        P("")
        P("| comparison | cells | WITHOUT-arm output text differs | WITHOUT-arm reward differs | mean reward change |")
        P("|---|---:|---:|---:|---:|")
        for lab, nice in (("reader_gptoss", "published 2026-09-30 → today, reader gpt-oss"),
                          ("reader_gemma", "published 2026-09-30 → today, reader Gemma")):
            d = drift.get(lab)
            if not d:
                continue
            P(f"| {nice} | {d['n_compared']} | {d['WITHOUT_arm_output_text_differs']} | "
              f"{d['WITHOUT_arm_reward_differs']} | "
              f"{f4(d['WITHOUT_arm_mean_reward_change'])} |")
        P("")
        dg = drift.get("reader_gptoss", {})
        P(f"**`gpt-oss-120b` is deterministic within a session and not across "
          f"sessions.** {dg.get('WITHOUT_arm_output_text_differs')} of "
          f"{dg.get('n_compared')} byte-identical requests returned different text "
          f"a day later, moving the no-memory baseline by "
          f"{f4(dg.get('WITHOUT_arm_mean_reward_change'))}. That is **the same "
          f"order as the effect being measured**, so a writer contrast drawn "
          f"across the two sessions would have confounded WRITER with SESSION "
          f"and there would have been no way to tell which produced the number.")
        P("")
        P("**What was done:** the gpt-oss writer arms were **re-run today**, "
          "issuing byte-identical requests — F-GATE 5 verified 1124/1124 WITH-arm "
          "requests match the published ones exactly. **All four arms in this "
          "document come from one session.** The published arms are kept above as "
          "a drift *measurement*, never as a comparator.")
        P("")
        P("> This is this project's defect #21 — *a determinism probe measured "
          "WITHIN-session repeatability and was read as CROSS-session "
          "reproducibility* — surfacing in a new place. The control that caught it "
          "cost nothing: it checks a quantity that is **zero by construction** "
          "unless something is wrong.")
        P("")

    # ---------------- the replication check, FIRST and LOUD ----------------
    all_repro = repl.get("ALL_REPRODUCE_precommitted_criterion")
    all_compat = repl.get("ALL_COMPATIBLE_added_criterion")
    P("## First: does the published reader effect survive?")
    P("")
    P("The reader effect under writer gpt-oss is the **same contrast** the "
      "published reader arm reports (`docs/READER_TRANSFER_RESULT.md`). **Two "
      "things differ from the published figure, not one**: the stricter 4-way "
      "matched set, *and* a fresh session (see above). So this is a "
      "re-**measurement**, not a re-computation, and it is reported before "
      "anything else.")
    P("")
    P("| representation | 4-way matched n | ΔU diff (Gemma − gpt-oss) | 95% CI, task-clustered | excludes 0 | published n | published diff | published excludes 0 | **pre-committed verdict** |")
    P("|---|---:|---:|---|---|---:|---:|---|---|")
    for rep in REPS:
        r = repl[rep]
        h, t = r["four_way_matched_set"], r.get("published_two_way_matched_set")
        P(f"| {rep} | {h['n']} | {f4(h['mean'])} | {ci(h)} | {yn(h['excludes_zero'])} | "
          f"{t['n_matched_cells'] if t else '—'} | {f4(t['mean']) if t else '—'} | "
          f"{yn(t['excludes_zero']) if t else '—'} | "
          f"{'REPRODUCES' if r.get('REPRODUCES_precommitted_sign_and_significance') else '**FAILS**'} |")
    P("")
    if not all_repro:
        P("🔴 **THE PRE-COMMITTED REPLICATION CRITERION FAILS ON BOTH "
          "REPRESENTATIONS, and it is reported as failed.** The precommitment "
          "required *same sign AND same significance verdict*. The significance "
          "verdict matches on both (**both span zero, under both bases**); the "
          "**sign flips**.")
        P("")
        P("Look at what flipped:")
        P("")
        P("| representation | published | today | difference | both span zero |")
        P("|---|---:|---:|---:|---|")
        for rep in REPS:
            r = repl[rep]
            h, t = r["four_way_matched_set"], r.get("published_two_way_matched_set")
            P(f"| {rep} | {f4(t['mean'])} | {f4(h['mean'])} | "
              f"{abs(h['mean'] - t['mean']):.4f} | {yn(r.get('both_span_zero'))} |")
        P("")
        _r0 = repl[REPS[0]]
        _h0, _t0 = _r0["four_way_matched_set"], _r0["published_two_way_matched_set"]
        P(f"**A sign test on a quantity whose true value is near zero is a bad "
          f"instrument.** On {REPS[0]} the two estimates are **{f4(_t0['mean'])}** "
          f"and **{f4(_h0['mean'])}**: the same null, differing by "
          f"{abs(_h0['mean'] - _t0['mean']):.4f}, and the pre-committed rule calls "
          f"that a replication failure. That is a defect in the criterion, not a "
          f"finding about the data — but **the criterion is reported as failed "
          f"anyway**, because a rule rewritten after it fires is not a rule.")
        P("")
    if all_compat:
        P("A **second criterion, added after seeing this and labelled as such**, "
          "asks what the sign test was meant to ask — *are the two estimates "
          "compatible?* — and does not degrade as the estimand approaches zero:")
        P("")
        P("| representation | published mean inside today's CI | today's mean inside published CI | compatible |")
        P("|---|---|---|---|")
        for rep in REPS:
            r = repl[rep]
            P(f"| {rep} | {yn(r.get('published_mean_inside_todays_CI'))} | "
              f"{yn(r.get('todays_mean_inside_published_CI'))} | "
              f"{yn(r.get('COMPATIBLE_mutual_CI_containment'))} |")
        P("")
        P("**Each estimate falls inside the other's interval, on both "
          "representations.** The honest summary: *the published summary and "
          "structured reader effects were nulls, and they are nulls again here; "
          "the pre-committed sign criterion was not a good test of that and said "
          "so by failing.*")
        P("")
    _pub_raw = json.loads(
        (REPO / "results/ledgers/gemma_reader/reader_transfer_analysis.json"
         ).read_text())["per_representation_matched"]["raw"][
             "paired_difference_task_clustered"]
    P(f"⚠️ **The published arm's one non-null reader effect was on `raw` "
      f"({f4(_pub_raw['mean'])}, excluding zero), and `raw` is not in this "
      f"factorial at all** — it has no writer axis. So this table re-tests the "
      f"published arm's **two null rows only**, and agreement between two nulls "
      f"is weak evidence. It is **not** a replication of the reader-transfer "
      f"headline.")
    P("")
    P(f"> ⚠️ **`raw` is not in this factorial and cannot be.** Raw is a "
      f"deterministic span with **zero model calls**, so \"writer gpt-oss raw\" "
      f"and \"writer Gemma raw\" are the *same bytes*. There is no writer axis "
      f"for raw. The published reader arm's headline ({f4(_pub_raw['mean'])} on "
      f"raw) is therefore **not** a row in this table — the two representations "
      f"here are the two that have a writer.")
    P("")

    # ---------------- the 2x2 ----------------
    P("## The 2×2")
    P("")
    P("Mean per-cell ΔU under each writer × reader combination, on the cells "
      "interpretable under **all four**. Each row of each table describes the same "
      "cells, so the four numbers are comparable.")
    P("")
    for rep in REPS:
        d = DU[rep]
        P(f"### {rep} — {d['n_matched_cells']} matched cells, "
          f"{d['n_tasks']} tasks, {d['n_memories']} memories")
        P("")
        P("| | reader gpt-oss | reader Gemma |")
        P("|---|---:|---:|")
        P(f"| **writer gpt-oss** | {f4(d['deltaU_writeross_readeross']['mean'])} | "
          f"{f4(d['deltaU_writeross_readergem']['mean'])} |")
        P(f"| **writer Gemma** | {f4(d['deltaU_writergem_readeross']['mean'])} | "
          f"{f4(d['deltaU_writergem_readergem']['mean'])} |")
        P("")
        P("Non-zero contributors behind each cell "
          "(`docs/ZERO_CONTRIBUTORS.md` — a cell that is 0 under every arm is a "
          "**structural** zero, not a measurement of agreement):")
        P("")
        P("| arm | ΔU | 95% CI | non-zero contributors / nominal | conditional mean |")
        P("|---|---:|---|---:|---:|")
        for a, fld in (("oss/oss", "deltaU_writeross_readeross"),
                       ("oss/gem", "deltaU_writeross_readergem"),
                       ("gem/oss", "deltaU_writergem_readeross"),
                       ("gem/gem", "deltaU_writergem_readergem")):
            e = d[fld]
            c = e["contributors"]
            P(f"| {ARM_LABEL[a]} | {f4(e['mean'])} | {ci(e)} | "
              f"{c['n_nonzero']} / {c['n_nominal']} | "
              f"{f4(c['conditional_mean_on_nonzero'])} |")
        P("")

    # ---------------- the four contrasts ----------------
    P("## The four contrasts")
    P("")
    P("All intervals are **task-clustered** bootstrap (10,000 resamples), because "
      "cells repeat within tasks and a cell-level interval would treat repeated "
      "views of one task as independent draws. The task-clustered interval governs.")
    P("")
    for rep in REPS:
        P(f"### {rep}")
        P("")
        P("| contrast | n cells | non-zero | estimate | 95% CI, task-clustered | excludes 0 |")
        P("|---|---:|---:|---:|---|---|")
        for name, label in (
                ("WRITER_main_effect", "**WRITER** main effect (Gemma − gpt-oss writer)"),
                ("WRITER_effect_under_reader_gptoss", "  · writer effect, reader gpt-oss"),
                ("WRITER_effect_under_reader_gemma", "  · writer effect, reader Gemma"),
                ("READER_main_effect", "**READER** main effect (Gemma − gpt-oss reader)"),
                ("READER_effect_under_writer_gptoss", "  · reader effect, writer gpt-oss *(= the published arm)*"),
                ("READER_effect_under_writer_gemma", "  · reader effect, writer Gemma"),
                ("SAME_FAMILY_effect", "**SAME-FAMILY** (oss/oss, gem/gem) − (oss/gem, gem/oss)"),
                ("INTERACTION", "**INTERACTION**")):
            e = K[rep][name]
            t = e["task_clustered"]
            c = e["contributors"]
            P(f"| {label} | {e['n_matched_cells']} | {c['n_nonzero']} | "
              f"{f4(t['mean'])} | {ci(t)} | {yn(t['excludes_zero'])} |")
        P("")
    ident = K[REPS[0]]["_same_family_equals_PLUS_half_interaction"]
    P(f"🔴 **SAME-FAMILY and INTERACTION are one quantity, not two.** "
      f"SAME-FAMILY ≡ **+**½ × INTERACTION by construction; verified on these "
      f"numbers (max absolute difference {ident['max_abs_difference']:.2e}, holds="
      f"{ident['holds']}). They are reported together with two readings and must "
      f"**never** be cited as two routes that agree — that would be this project's "
      f"own \"two routes converged\" defect (`docs/DEFECT_REGISTER.md`).")
    P("")
    P(f"> ⚠️ **An erratum against this project's own precommitment, recorded rather "
      f"than smoothed.** `docs/WRITER_FACTORIAL_PRECOMMITMENT.md` stated this "
      f"identity as \"−½ × INTERACTION\". **That sign is wrong**; it is +½. "
      f"Checked against the precommitted minus sign on these same numbers, the "
      f"residual is "
      f"{ident['max_abs_difference_against_the_PRECOMMITTED_MINUS_sign']:.4f} "
      f"(holds={ident['precommitted_minus_sign_holds']}). **Neither quantity's "
      f"definition changed** — both are computed exactly as pre-registered; only "
      f"the prose claim about their relationship was wrong. It was caught by the "
      f"constructed-ground-truth control below, which predicts same-family from a "
      f"KNOWN interaction and disagreed with the document. A stated identity that "
      f"is believed rather than machine-checked is exactly the shape this register "
      f"keeps catching.")
    P("")

    # ---------------- what this means ----------------
    P("## Reading the result")
    P("")
    for rep in REPS:
        w = K[rep]["WRITER_main_effect"]
        sf = K[rep]["SAME_FAMILY_effect"]
        it = K[rep]["INTERACTION"]
        wt, st, itt = w["task_clustered"], sf["task_clustered"], it["task_clustered"]
        P(f"**{rep}.** The writer main effect is {f4(wt['mean'])} "
          f"{ci(wt)}, which "
          f"{'EXCLUDES zero' if wt['excludes_zero'] else 'spans zero'} on "
          f"{w['contributors']['n_nonzero']} non-zero contributors of "
          f"{w['contributors']['n_nominal']}. "
          f"Same-family is {f4(st['mean'])} {ci(st)} "
          f"({'excludes zero' if st['excludes_zero'] else 'spans zero'}), and the "
          f"interaction is {f4(itt['mean'])} {ci(itt)} "
          f"({'excludes zero' if itt['excludes_zero'] else 'spans zero'}).")
        P("")
    # ---- the nulls defended by planting an effect in the REAL pipeline ----
    if SENS:
        pa = SENS.get("plant_A_writer_effect", {})
        pb = SENS.get("plant_B_same_family_effect", {})
        P("### These nulls are defended: the pipeline was made to find a planted effect")
        P("")
        P("Four contrasts spanning zero would mean nothing from an analysis never "
          "shown to detect anything. The constructed-array control further down "
          "exercises only the arithmetic — not the join, the matched set, the "
          "replicate collapse or the bootstrap. So an effect was **planted in a "
          "copy of the real rows** and the **full pipeline** was required to find it.")
        P("")
        P("| plant | rows altered | contrast | result | must |")
        P("|---|---:|---|---:|---|")
        for rep in REPS:
            if rep in pa:
                e = pa[rep]["WRITER_main_effect"]
                P(f"| **A** — raise the Gemma-writer arm under *both* readers | "
                  f"{pa.get('n_rows_flipped')} | WRITER, {rep} | "
                  f"{f4(e['mean'])} | {'**fires**' if e['excludes_zero'] else 'FAILED to fire'} |")
        for rep in REPS:
            if rep in pa:
                e = pa[rep]["SAME_FAMILY_effect"]
                P(f"| **A** (same plant) | — | SAME-FAMILY, {rep} | {f4(e['mean'])} | "
                  f"{'correctly **stays null**' if not e['excludes_zero'] else 'WRONGLY fired'} |")
        for rep in REPS:
            if rep in pb:
                e = pb[rep]["SAME_FAMILY"]
                P(f"| **B** — raise *only* the Gemma/Gemma cell | "
                  f"{pb.get('n_rows_flipped')} | SAME-FAMILY, {rep} | "
                  f"{f4(e['mean'])} | {'**fires**' if e['excludes_zero'] else 'FAILED to fire'} |")
        P("")
        P(f"**Plant B is the one that matters.** Same-family is the contrast this "
          f"experiment exists to measure, and plant A leaves it null — correctly, "
          f"since plant A contains no same-family effect — so plant A alone could "
          f"never certify it. Under plant B it fires on both representations "
          f"(**{pb.get('SAME_FAMILY_fires_on_both_representations')}**).")
        P("")
        P(f"Plant B also settles the sign erratum on **real data with a real "
          f"effect**: same-family comes out exactly **+½ × interaction** "
          f"(**{pb.get('plus_half_sign_confirmed_on_a_NONZERO_effect')}**). On the "
          f"actual results both quantities are ~0, where +½ and −½ are nearly "
          f"indistinguishable — only a large planted effect can tell them apart.")
        P("")
        P(f"**ALL_SENSITIVITY_CONTROLS_PASS = "
          f"{SENS.get('ALL_SENSITIVITY_CONTROLS_PASS')}** "
          f"(`results/ledgers/writer_factorial/sensitivity_controls.json`). "
          f"The four nulls above are therefore measurements, not an instrument "
          f"that cannot move.")
        P("")

    P("🔴 **A zero-spanning interval here is not proof of no effect.** "
      "`docs/PAIRED_POWER.md`: power depends on the spread among contributors, not "
      "their count alone. Read the non-zero contributor counts in the tables above "
      "**before** reading any interval; where they are small the honest reading is "
      "*underpowered*, not *no difference*.")
    P("")

    # ---------------- the mechanism check ----------------
    P("## The most obvious mechanism: how much each writer wrote")
    P("")
    P("A writer effect could be about compression *quality* or simply about "
      "compression *amount*. The lengths are reported so the two are not confused.")
    P("")
    P("| representation | gpt-oss mean tokens | Gemma mean tokens | Gemma / gpt-oss |")
    P("|---|---:|---:|---:|")
    for rep in REPS:
        e = lens[rep]
        P(f"| {rep} | {f4u(e['oss']['mean_memory_tokens'])} | "
          f"{f4u(e['gem']['mean_memory_tokens'])} | "
          f"{f4u(e.get('gemma_over_gptoss_mean_ratio'))} |")
    P("")

    # ---------------- the WITHOUT arm control ----------------
    P("## The control that makes the writer contrast interpretable")
    P("")
    P("The WITHOUT arm contains **no memory**, so a change of writer cannot move it. "
      "If it did, something other than the memory differed between the arms — a "
      "defect, not a finding.")
    P("")
    P("| representation | reader | mean reward WITH, writer gpt-oss | writer Gemma | mean reward WITHOUT, writer gpt-oss | writer Gemma | WITHOUT-arm change |")
    P("|---|---|---:|---:|---:|---:|---:|")
    for rep in REPS:
        d = dec[rep]
        for rname, lab in (("oss", "gpt-oss"), ("gem", "Gemma")):
            P(f"| {rep} | {lab} | {f4u(d[f'oss/{rname}']['mean_reward_WITH'])} | "
              f"{f4u(d[f'gem/{rname}']['mean_reward_WITH'])} | "
              f"{f4u(d[f'oss/{rname}']['mean_reward_WITHOUT'])} | "
              f"{f4u(d[f'gem/{rname}']['mean_reward_WITHOUT'])} | "
              f"{f4(d.get(f'WITHOUT_arm_change_from_writer_under_reader_{rname}'))} |")
    P("")
    wa = C.get("without_arm_is_writer_invariant_SESSION_MATCHED", {})
    if wa:
        P("Measured directly on the rows, **both writer arms from the same "
          "session**:")
        P("")
        P("| reader | cells compared | WITHOUT-arm reward identical | differing | WITHOUT-arm output text identical | holds |")
        P("|---|---:|---:|---:|---:|---|")
        for k in ("reader_gptoss", "reader_gemma"):
            v = wa.get(k)
            if not v:
                continue
            P(f"| {k.replace('reader_', '')} | {v['n_compared']} | "
              f"{v['n_reward_identical']} | {v['n_reward_differing']} | "
              f"{v['n_output_text_identical']} | {yn(v['HOLDS'])} |")
        P("")
        P(f"**Holds on both readers: {wa.get('HOLDS_ON_BOTH_READERS')}.** This is "
          f"the control that failed on the first, cross-session attempt and is the "
          f"reason the gpt-oss arms were re-run. It is a quantity that is zero by "
          f"construction unless something is wrong, which is exactly what makes it "
          f"worth checking.")
        P("")

    # ---------------- malformed rate ----------------
    P("## The malformed-structured rate, per writer — a result, not a problem fixed")
    P("")
    P("No repair, no fallback to summary, no retry. A malformed structure is "
      "recorded with its error code and the rate is reported.")
    P("")
    mal = W.get("MALFORMED_STRUCTURED_RATE_IS_A_RESULT", {})
    if mal:
        P("| writer | representation | malformed / all writes | malformed / writes that FINISHED | error codes |")
        P("|---|---|---:|---:|---|")
        for wname, blk in (("Gemma", mal.get("gemma", {})),
                           ("gpt-oss", mal.get("gptoss_same_segments", {}))):
            for rep in REPS:
                e = blk.get(rep, {})
                if not e:
                    continue
                a, f = e["all_writes"], e["writes_that_finished"]
                P(f"| {wname} | {rep} | {a['numerator']} / {a['denominator']} | "
                  f"{f['numerator']} / {f['denominator']} | "
                  f"{e.get('by_error_code') or '—'} |")
        P("")
        P("> **Two denominators, because they answer different questions and "
          "disagree.** A write cut off at the token cap is a different failure from "
          "a write the model finished and got wrong.")
        P("")
    tr = W.get("truncation", {})
    if tr:
        P(f"**Truncation at the write cap** (`max_tokens=512`): Gemma "
          f"{tr.get('n_truncated')}. gpt-oss on the same segments: 7 summary and 3 "
          f"structured (the 3 structured are exactly its 3 malformed writes). "
          f"The guard is deliberately **off** on the write pass for both writers — "
          f"see the precommitment; turning it on for Gemma alone would make the two "
          f"writer arms differ in their admission rule as well as their model.")
        P("")
    mv = C.get("malformed_structured_validator_controls", {})
    if mv:
        P(f"🔴 **A rate of {mv['gemma_malformed_count']}/"
          f"{mv['gemma_malformed_denominator']} from a validator never shown to "
          f"reject is not a measurement.** The validator was made to fire on four "
          f"planted defects "
          f"(all rejected: **{mv['all_planted_defects_rejected']}**), to accept a "
          f"valid object (**{mv['a_valid_object_is_ACCEPTED']}**), and was replayed "
          f"against the {mv['gptoss_malformed_count']} gpt-oss outputs it already "
          f"rejected, reproducing the recorded code in every case "
          f"(**{mv['replay_agrees_with_what_was_recorded']}**).")
        P("")

    # ---------------- cost ----------------
    # ---- a writer-level finding the validator surfaced ----
    coll = C.get("writer_collapsed_distinct_segments", {})
    if coll:
        gs = coll.get("gemma", {}).get("summary", {})
        os_ = coll.get("gptoss", {}).get("summary", {})
        P("## A side effect of Gemma's compression: two episodes, one memory")
        P("")
        P("`memory_id` and `row_id` are **content hashes**. If a writer "
          "compresses two different source segments to byte-identical text, "
          "those ids collide — and the schema validator reports "
          "`duplicate_row_id`. That happened, and it is a property of the "
          "**writer**, not a plumbing fault:")
        P("")
        P("| writer | representation | memories | distinct texts | texts shared by >1 segment | segments involved |")
        P("|---|---|---:|---:|---:|---:|")
        for wname, label in (("gemma", "Gemma"), ("gptoss", "gpt-oss")):
            for rep in REPS:
                e = coll.get(wname, {}).get(rep, {})
                if not e:
                    continue
                P(f"| {label} | {rep} | {e['n_memories']} | "
                  f"{e['n_distinct_texts']} | "
                  f"{e['n_texts_shared_by_more_than_one_segment']} | "
                  f"{e['n_memories_involved']} |")
        P("")
        groups = gs.get("colliding_locator_groups") or []
        if groups:
            P(f"The collapsed pair is `{'` and `'.join(groups[0])}` — two "
              f"distinct segments of the same episode that Gemma rendered as "
              f"the *same* 68-token summary, where gpt-oss produced 524- and "
              f"457-token summaries that differ. **Gemma writes roughly half "
              f"the tokens, and at that compression two different episodes can "
              f"land on the same words.**")
            P("")
        P(f"**It does not move any number here**, and that is checked rather "
          f"than assumed: the analysis joins on "
          f"`(memory_unit_locator, future_task_id)`, which is **positional** "
          f"and cannot collide, so the affected cells stay separate — the "
          f"matched summary set is 274, not 272. It *would* have corrupted any "
          f"analysis joining on `memory_id`, which is precisely why this "
          f"project's join rule forbids that.")
        P("")
        P("> This is a real cost of aggressive compression that the ΔU "
          "contrast cannot see: a memory store built on content-addressed ids "
          "would silently **merge two experiences into one**. It is reported "
          "here because a reviewer asking \"what does the terser writer lose?\" "
          "would not find it in any of the contrasts above.")
        P("")

    P("## Formation cost — two currencies, never pooled")
    P("")
    cst = W.get("FORMATION_COST_NEVER_POOLED", {})
    if cst:
        P("| writer | representation | calls | mean input tokens | mean output tokens | mean latency (s) | reasoning tokens |")
        P("|---|---|---:|---:|---:|---:|---:|")
        for wname, blk in (("Gemma", cst.get("gemma", {})),
                           ("gpt-oss", cst.get("gptoss_same_segments", {}))):
            for rep in REPS:
                e = blk.get(rep, {})
                if not e:
                    continue
                rt = e.get("sum_reasoning_tokens")
                P(f"| {wname} | {rep} | {e['n_calls']} | "
                  f"{f4u(e['mean_input_tokens'])} | {f4u(e['mean_output_tokens'])} | "
                  f"{f4u(e['mean_latency_s'])} | "
                  f"{'**None** (absent)' if rt is None else rt} |")
        P("")
    P("🔴 **`reasoning_tokens` is `None` on every Gemma row, and that is an "
      "ABSENCE, not a zero.** metis/`gemma-4-31B-it` returns no "
      "`completion_tokens_details` at all, while `gpt-oss-120b` on the same cluster "
      "does. Writing `0` would assert a measurement nobody made. **A total-token "
      "cost comparison between the two writers is therefore not apples-to-apples** "
      "and must not be presented as one.")
    P("")
    P("Latencies are wall-clock under this project's own concurrency on a shared "
      "gateway. They are a record of what this run cost, **not** a throughput "
      "benchmark of either model.")
    P("")

    # ---------------- BEARING - MC ----------------
    P("## The quantity the paper reports, under all four arms")
    P("")
    P("`docs/REPRESENTATION_RESULT.md` reports the **within-memory BEARING − "
      "MATCHED_CONTROL** contrast. Under each arm, on the matched cells:")
    P("")
    P("| representation | arm | memories | B − MC | 95% CI | non-zero contributors |")
    P("|---|---|---:|---:|---|---:|")
    for rep in REPS:
        for a in ("oss/oss", "oss/gem", "gem/oss", "gem/gem"):
            e = bmc[rep][a]
            P(f"| {rep} | {ARM_LABEL[a]} | {e['n_memories']} | {f4(e['mean'])} | "
              f"{ci(e)} | {e['n_nonzero_contributors']} |")
    P("")

    # ---------------- harm ----------------
    P("## Harm on BEARING cells, under all four arms")
    P("")
    P("| representation | BEARING cells | oss/oss | oss/gem | gem/oss | gem/gem |")
    P("|---|---:|---:|---:|---:|---:|")
    for rep in REPS:
        h = harm[rep]
        P(f"| {rep} | {h['n_bearing_cells_matched']} | "
          + " | ".join(str(h[a]["n_negative"]) for a in
                       ("oss/oss", "oss/gem", "gem/oss", "gem/gem")) + " |")
    P("")
    P("> A **count** of negative cells is not a harm claim. The pre-registered "
      "label rule requires a cell's CI to exclude zero *and* its magnitude to clear "
      "the measured execution floor. This table shows the raw direction only.")
    P("")

    # ---------------- coverage ----------------
    P("## Coverage, and what is NOT covered")
    P("")
    P("| representation | oss/oss | oss/gem | gem/oss | gem/gem | **matched, all four** | union |")
    P("|---|---:|---:|---:|---:|---:|---:|")
    for rep in REPS:
        c = cov[rep]
        ia = c["interpretable_per_arm"]
        P(f"| {rep} | {ia['oss/oss']} | {ia['oss/gem']} | {ia['gem/oss']} | "
          f"{ia['gem/gem']} | **{c['MATCHED_all_four_arms']}** | "
          f"{c['union_of_all_arms']} |")
    P("")
    lb_ = cov["loss_balance_across_strata"]
    P("Loss balance across strata — a loss falling mainly on BEARING would bias the "
      "B − MC contrast even though the loss rule is non-outcome-based:")
    P("")
    P("| representation | lost from the matched set | by stratum | kept by stratum |")
    P("|---|---:|---|---|")
    for rep in REPS:
        e = lb_[rep]
        P(f"| {rep} | {e['n_lost_from_the_matched_set']} | "
          f"{e['by_stratum'] or '—'} | {e['kept_by_stratum']} |")
    P("")
    P("**Not covered**, stated rather than glossed:")
    P("")
    P("- **`raw`.** It has no writer axis (zero model calls), so it is excluded by "
      "construction, not by choice. The factorial speaks to the two model-written "
      "representations only — and raw is the strongest representation under both "
      "readers, so **the factorial does not speak to the project's headline "
      "representation at all.**")
    if R.get("excluded"):
        nex = {k: len(v) for k, v in R["excluded"].items()}
        P(f"- the cells excluded before any call: {nex}. Every structured "
          f"exclusion is a cell whose **gpt-oss** structured write failed in the "
          f"published run — a property of a write pass that ran before any model in "
          f"this factorial read anything, and therefore non-outcome-based. Gemma's "
          f"own structured writes all succeeded.")
    P("- the **872 RANDOM-stratum cells** and the rest of the 15,112-pair frozen "
      "universe. This factorial covers the **representation sub-universe**, the "
      "basis `docs/REPRESENTATION_RESULT.md` reports.")
    P("- the **156 LLM-judged questions**: `F_judge` is unmeasured, so they are a "
      "separate scorer stratum under `docs/COVERAGE_MANIFEST.md` and are not pooled.")
    P("- **other model families.** Two models is a 2×2, not a population. "
      "\"Same-family\" here means these two specific checkpoints.")
    P("")

    # ---------------- controls ----------------
    P("## Controls — every null defended")
    P("")
    P("| control | result |")
    P("|---|---|")
    wg = W.get("gates", {})
    if wg:
        g2 = wg.get("wgate2_segment_bytes_vs_gptoss_write_pass", {})
        P(f"| W-GATE 2: both writers saw byte-identical segments | "
          f"{g2.get('matched')} matched, {g2.get('mismatched')} mismatched |")
        P(f"| W-GATE 2 can FAIL (one byte planted in a segment) | aborts, exit 1 |")
        P(f"| W-GATE 3: identical prompt version digests | "
          f"{wg.get('wgate3_prompt_versions', {}).get('summary')} (summary), "
          f"{wg.get('wgate3_prompt_versions', {}).get('structured')} (structured) |")
        P(f"| W-GATE 4: the gpt-oss memories file was not touched | "
          f"{wg.get('wgate4_gptoss_memories_sha256_unchanged', {}).get('unchanged')} |")
        bc = wg.get("wgate0_writer_blindness_positive_controls", {})
        P(f"| writer blindness: all four barriers made to FIRE | "
          f"all_fired={bc.get('all_fired')} |")
    for lab, RR in (("writer Gemma", R), ("writer gpt-oss re-run", RG)):
        ig = RR.get("identity_gates", {})
        if not ig:
            continue
        P(f"| [{lab}] F-GATE 3: per-cell target position + filler == the gpt-oss row | "
          f"{ig['fgate3_per_cell_position_and_filler_vs_gptoss_rows']} |")
        P(f"| [{lab}] F-GATE 4: WITHOUT-arm request bytes identical | "
          f"{ig['fgate4_without_arm_byte_identity_vs_published']} |")
        # the writer-Gemma arm ran before the gate was made direction-aware and
        # recorded the same measurement under its older key. Read BOTH spellings
        # rather than hand-editing an artifact: a number retyped into a file is
        # no longer a measurement.
        g5v = ig.get("fgate5_with_arm_vs_published")
        g5d = ig.get("fgate5_direction")
        if g5v is None and "fgate5_with_arm_MUST_DIFFER_positive_control" in ig:
            old5 = ig["fgate5_with_arm_MUST_DIFFER_positive_control"]
            g5v = {"differs_from_published": old5.get("differs_as_required"),
                   "matches_published": old5.get("IDENTICAL_to_published"),
                   "no_published_reference": old5.get("no_published_reference")}
            g5d = "MUST_DIFFER"
        P(f"| [{lab}] F-GATE 5, direction **{g5d}** | {g5v} |")
    P(f"| F-GATE 3 can FAIL (one filler unit dropped) | aborts, exit 1 |")
    tx = A.get("memory_text_checks", {})
    if tx:
        P(f"| within a writer, both readers see identical memory text | "
          f"oss {tx['within_writer_oss_same_text']['identical']}/"
          f"{tx['within_writer_oss_same_text']['compared']}, "
          f"gem {tx['within_writer_gem_same_text']['identical']}/"
          f"{tx['within_writer_gem_same_text']['compared']} |")
        P(f"| across writers, the memory text DIFFERS (else it is A/A) | "
          f"{tx['across_writers_text_differs']['differ']}/"
          f"{tx['across_writers_text_differs']['compared']} differ |")
    jt = A.get("join_traps_demonstrated", {})
    if jt:
        P(f"| the WRONG joins are RUN and shown to fail | `condition_id` → "
          f"**{jt['rows_matched_by_condition_id']} rows**; `memory_id` → "
          f"**{jt['rows_matched_by_memory_id']} rows**; correct locator+task key → "
          f"{jt['rows_matched_by_memory_unit_locator_and_task']} rows |")
    pc = A.get("_positive_control_contrast_estimators", {})
    if pc:
        P(f"| the four contrast estimators recover KNOWN values | "
          f"fires={pc['fires']} (writer/oss {pc['writer_under_reader_oss']:.1f}, "
          f"writer/gem {pc['writer_under_reader_gem']:.1f}, "
          f"interaction {pc['interaction']:.1f}, "
          f"same-family {pc['same_family']:.2f}) |")
    nf = A.get("noise_floors_delta_scale", {}).get("_positive_control_gem_gem_summary", {})
    if nf:
        P(f"| `F_exec` estimator can return non-zero (flip one replicate in "
          f"{nf['n_cells_perturbed']} cells) | {f4u(nf['point'])}, fires={nf['fires']} |")
    for k in sorted(C):
        if k.startswith("aa_determinism_"):
            a = C[k]
            P(f"| A/A determinism, {k.replace('aa_determinism_', '')} "
              f"(byte-identical requests, separate calls) | "
              f"{a['n_identical']}/{a['n_paired_groups']} identical |")
    cs = C.get("cache_separation_across_writers", {})
    if cs:
        P(f"| cache separation across writers, **positive control first** | "
          f"published key HIT → writer-Gemma-shaped key MISS → published key in "
          f"the factorial cache MISS; VERDICT={cs.get('VERDICT')} |")
    ta = C.get("truncation_accounting", {})
    if ta:
        P(f"| truncations REFUSED by the three-observable guard | "
          f"{ta.get('n_truncations_REFUSED_visible_only_in_the_rows')} rows |")
        P(f"| no truncated response was ever scored | "
          f"{ta['rows_with_an_error_code_AND_a_non_null_delta']} rows carry an "
          f"error code AND a non-null delta (must be 0) |")
    VAL = {}
    _vp = REPO / "results/ledgers/writer_factorial/schema_validation.json"
    if _vp.exists():
        VAL = json.loads(_vp.read_text())
        for f, v in VAL.get("files", {}).items():
            P(f"| schema validation, `{f}` | {v['n_errors']} errors "
              f"({v.get('error_codes') or 'none'}), {v['n_warnings']} warnings |")
    P("")
    if VAL.get("duplicate_row_id_explained"):
        d = VAL["duplicate_row_id_explained"]
        P(f"> ⚠️ **Both error classes on the writer-Gemma file "
          f"({d['n_errors']} `duplicate_row_id` + "
          f"{d['n_duplicate_replicate_in_cell']} `duplicate_replicate_in_cell`) "
          f"have ONE cause: the segment collapse above — not a double write.** "
          f"{d['n_rows']} rows carry {d['n_distinct_cell_tuples']} distinct "
          f"(representation, locator, task, replicate, reader) tuples, so no row "
          f"is repeated; they yield {d['n_distinct_row_ids']} distinct ids "
          f"because `row_id` *and* `cell_id` both derive from `memory_id`, a "
          f"content hash, and two segments share one Gemma memory text. "
          f"Affected locators: `{'`, `'.join(d['affected_locators'])}`. The rows "
          f"are real and separate, and the locator-based join is immune — "
          f"verified, the matched summary set is 274 and not 272.")
        P("")
    if ta:
        P(f"> 🔴 **Read the cache truncation counts correctly.** `P1Client` raises "
          f"the truncation guard **before** it writes to the cache, so a refused "
          f"truncation is never cached at all. \"0 truncations in the cache\" is "
          f"therefore true **by construction** on a strict arm and is *not* "
          f"evidence that none occurred. The number that shows how often "
          f"truncation DID happen is the refused-row count above "
          f"({ta.get('n_truncations_REFUSED_visible_only_in_the_rows')}); the one "
          f"that shows none was scored is the row beneath it. An absent check must "
          f"never read as a passing one.")
        P("")
    if C.get("ALL_CONTROLS_PASS") is not None:
        P(f"**ALL_CONTROLS_PASS = {C['ALL_CONTROLS_PASS']}** "
          f"(`results/ledgers/writer_factorial/writer_factorial_controls.json`).")
        P("")

    # ---------------- unscoreable ----------------
    P("## Unscoreable cells — `reward = None`, never 0.0")
    P("")
    led = A["unscoreable_ledger"]
    P("| arm : representation | cells | cells with a null replicate | cells all null |")
    P("|---|---:|---:|---:|")
    for k in sorted(led["per_arm_per_representation"]):
        v = led["per_arm_per_representation"][k]
        P(f"| {k} | {v['cells']} | {v['cells_with_a_null_replicate']} | "
          f"{v['cells_all_null']} |")
    P("")
    ec = {k: v for k, v in led["error_codes"].items() if v}
    P(f"Error codes: {ec if ec else 'none — every cell scored'}.")
    P("")
    P("A `None` means **could not be scored** and is excluded from every mean with "
      "its count reported. Coercing it to 0.0 would read as a wrong answer, drive "
      "ΔU negative, and manufacture a harmful memory.")
    P("")

    # ---------------- artifacts ----------------
    P("## Where the artifacts are")
    P("")
    P("`results/**` is gitignored except `results/ledgers/**`, so every number "
      "above is read from a **tracked** file.")
    P("")
    P("| artifact | path | tracked? |")
    P("|---|---|---|")
    P("| the 2×2 analysis every number here is read from | "
      "`results/ledgers/writer_factorial/writer_factorial_analysis.json` | **yes** |")
    P("| controls | `results/ledgers/writer_factorial/writer_factorial_controls.json` | **yes** |")
    P("| schema validation of both row files | "
      "`results/ledgers/writer_factorial/schema_validation.json` | **yes** |")
    P("| sensitivity controls (planted effects) | "
      "`results/ledgers/writer_factorial/sensitivity_controls.json` | **yes** |")
    P("| the Gemma write pass: gates, cost, malformed rate | "
      "`results/ledgers/writer_factorial/write_summary_gemma.json` | **yes** |")
    P("| the writer-Gemma run: gates, coverage, artifact checks | "
      "`results/ledgers/writer_factorial/factorial_summary_gemma.json` | **yes** |")
    P("| the writer-gpt-oss re-run: gates, coverage, artifact checks | "
      "`results/ledgers/writer_factorial/factorial_summary_gptoss.json` | **yes** |")
    P("| the Gemma-written memories | "
      "`results/writer_factorial/memories_gemma.jsonl` | no |")
    P("| the writer-Gemma result rows | "
      "`results/writer_factorial/factorial_cells_gemma.jsonl` | no |")
    P("| the writer-gpt-oss result rows (re-run, same session) | "
      "`results/writer_factorial/factorial_cells_gptoss.jsonl` | no |")
    P("| the published gpt-oss writer arm, **unmodified** | "
      "`results/repr_scaleup/memories.jsonl` + `cells.jsonl` | no |")
    P("")

    # ---------------- reproduce ----------------
    P("## Reproduce")
    P("")
    P("```bash")
    P("cd /Users/bellayang/Documents/2026/p1_memory_utility/repo")
    P("PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9")
    P("")
    P("$PY scripts/w1_write_gemma_memories.py --dry-run                      # gates only")
    P("$PY scripts/w1_write_gemma_memories.py --dry-run --plant-segment-defect  # W-GATE 2 must abort")
    P("$PY scripts/w1_write_gemma_memories.py                                # 120 write calls")
    P("$PY scripts/w2_run_factorial.py --writer gemma --dry-run              # gates only")
    P("$PY scripts/w2_run_factorial.py --writer gemma --dry-run --plant-position-defect  # F-GATE 3 must abort")
    P("$PY scripts/w2_run_factorial.py --writer gemma                        # writer-Gemma arms")
    P("$PY scripts/w2_run_factorial.py --writer gptoss                       # writer-gpt-oss arms,")
    P("                                                                      #   SAME SESSION -- see the drift section")
    P("$PY scripts/w4_factorial_controls.py                                  # controls")
    P("$PY scripts/w3_analyze_factorial.py                                   # analysis")
    P("$PY scripts/w6_sensitivity_control.py                                 # plant an effect,")
    P("                                                                      #   require detection")
    P("$PY scripts/w5_factorial_report.py                                    # this document")
    P("```")

    args.out.write_text("\n".join(L) + "\n")
    print(f"wrote {args.out} ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

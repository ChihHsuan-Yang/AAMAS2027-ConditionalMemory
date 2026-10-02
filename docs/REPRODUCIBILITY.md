# Reproducibility

Three levels, cheapest first. **Do not re-run inference to regenerate a figure
or table — the canonical rows already exist.**

Working directory is the repository root unless stated. Interpreter and
environment: [`DEV_ENVIRONMENT.md`](DEV_ENVIRONMENT.md) — **the system
`python3` is 3.9 and aborts test collection on a vendored file, which makes a
healthy suite look broken.** Use the project interpreter.

Last verified: **2026-10-02**.

---

## A · Regenerate figures and tables — seconds, no endpoint

Every figure is **TikZ drawn inline** in `main.tex` from macros in
`paper/figdata.tex`. There are no image files, so a figure cannot drift from
its artifact.

| step | command | expected |
|---|---|---|
| regenerate every number | `python3 scripts/make_figures.py` | rewrites `paper/figdata.tex`; **exits non-zero** if a value disagrees with its artifact |
| prove the figure guards discriminate | `python3 scripts/verify_figure_guards.py` | `ALL GUARDS DISCRIMINATE` |
| prove the story-figure guards discriminate | `python3 scripts/verify_story_figure_guards.py` | `ALL STORY-FIGURE GUARDS DISCRIMINATE` |
| verify every manuscript claim | `python3 scripts/audit_claims.py` | `AUDIT PASSED` |
| build the paper | `cd paper && latexmk -pdf -interaction=nonstopmode main.tex` **twice** | `main.pdf`, 11 pages, 0 undefined |

> The second LaTeX pass is required: a first build reports ~40 undefined
> citations because bibtex has not run. That is not a defect.

Both guard harnesses **plant the defect each guard forbids** and require it to
fire. A guard that has never been seen to fail is not known to work.

---

## B · Reproduce the analysis from existing data — minutes, no endpoint

| script | reproduces |
|---|---|
| `scripts/k3_analyze_screened.py` | **Story 1** — bearing vs matched control |
| `scripts/r3_analyze_representations.py` | **Story 2** — representation and cost |
| `scripts/raw_session_matched_analysis.py` | **Story 3** — reader transfer, session-matched |
| `scripts/swebench_multirepo_analysis.py` | the cross-benchmark boundary |
| `python3 -m pytest -q` | 645 tests |

**Expected headline values. If one of these does not reproduce, stop and
investigate rather than continuing.**

| quantity | expected | unit |
|---|---|---|
| bearing − matched control, LongMemEval | **+0.3349** [+0.1974, +0.4736] | cells, episode-clustered |
| reader transfer, session-matched | **+0.0982** [+0.0247, +0.1730] | 275 cells / 123 tasks / 550 replicate rows |
| gold-free screen, cells gold never selected | **15.6% → 50.0%** | arm-level success rate |
| SciCode and SWE-bench representation contrasts | **all cross zero** | matched cells |

---

## C · Re-run model inference — expensive

| experiment | entry point | calls | notes |
|---|---|---:|---|
| LongMemEval screened | `scripts/k2_run_screened.py` | 5,198 | the primary arm |
| Representation scale-up | `scripts/r2_run_representations.py` | 2,368 | **refuses** without `--memory-records` and `--parents`; both refusals are correct |
| Reader transfer | `scripts/gemma_reader_run.py --reader-arm {gptoss_metis,gemma_metis}` | 1,140/arm | 🔴 **both arms in ONE session** |
| SciCode, full pool | `scripts/scicode_pilot.py --n-cells 999 --tasks-per-memory 99` | 924 | sampling made inert deliberately |
| SWE-bench | `scripts/swebench_representations.py --repo <r> --cells <n>` | ~4/cell | gates read from disk and refuse without them |

### Assumptions these runs depend on

- **Endpoint.** `metis/gpt-oss-120b` and `metis/gemma-4-31B-it` via the ALCF
  gateway. Model names are sent **verbatim** and the resolved id must come back
  equal. Advertised ≠ live: only a real POST establishes availability.
- **Decoding.** temperature 0, `reasoning_effort` low (**inert on Gemma** —
  verified byte-identical output across low/medium/high), per-arm `max_tokens`
  in [`MODEL_ARMS.md`](MODEL_ARMS.md).
- **Concurrency.** 16 workers, *measured* per model — gpt-oss 169.9 completions/min
  at 24k context, Gemma 74.0. Do not transfer one model's ceiling to another.
- **Seeds.** Pairing and filler are seeded (20261008) and assert both that the
  same seed reproduces byte-identically **and that a different seed differs**,
  so reproducibility is not vacuous.

### 🔴 Determinism is within-session only

`gpt-oss-120b` is deterministic **within** a session and **not across** one:
re-issuing byte-identical *memory-free* requests a day later returned different
text in **554/1,124** cases and moved the baseline by −0.0303, the same order as
the effects measured. Gemma drifted **0/1,124**, so this is a property of the
model, not the cluster.

**Consequence:** comparators must be re-run in the same session as their arms.
A comparison spanning sessions is confounded, and
[`SESSION_DETERMINISM_AUDIT.md`](SESSION_DETERMINISM_AUDIT.md) scopes every
determinism claim in the project accordingly.

### Resume and completion

All runs are idempotent through the response cache, keyed on 13 fields
including `context_sha256`, so a killed run resumes by re-issuing the same
command. Each runner prints `VERDICT: RUN_PASSED` or `RUN_FAILED` from its own
artifact checks — **exit code 0 is not success**; read the verdict and the row
count.

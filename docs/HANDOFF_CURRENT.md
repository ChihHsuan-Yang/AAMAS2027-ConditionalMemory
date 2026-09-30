# P1 — Current Handoff

**Updated 2026-09-30 16:25 CDT by SA-ARCHIVE.** The detailed state.
`README.md` §Current Project State is the short version;
[`docs/RESULT_INDEX.md`](RESULT_INDEX.md) and [`docs/FIGURE_INDEX.md`](FIGURE_INDEX.md)
are the lookup tables. **Update this at every milestone.**

---

## Paths and remotes

| what | where |
|---|---|
| code repo | `/Users/bellayang/Documents/2026/p1_memory_utility/repo` → `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` (`main`) |
| **repo HEAD** | **`70426bd`** "Open Phase 3: autonomous execution to a terminal state", 2026-09-30 16:06 CDT · **151 commits** |
| Overleaf | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` → `git.overleaf.com/6abbde4a9eb777031afef068` (`main`) |
| **Overleaf HEAD** | **`3c06d3a`** "Abstract v5: lead with conditional utility and sparsity", 2026-09-30 16:16 CDT · working tree clean |
| HF dataset | `AgentsSci/AAMAS2027-ConditionalMemory` (**private**) |
| **HF version** | **v0.1 `lmev2-derived`**, tag `v0.1-lmev2-derived` — 4,519 rows / 2,117 cells, schema `p1mem_conditional_memory_utility_v2`, **97 fields**, 13 files, 126.0 MB, **Raw only**. Remote verified by fresh download: 13/13 sha256 match, the card's own load command runs clean, headline re-derives to +0.3349 from the remote copy |
| HF staging (**never committed, never uploaded from the repo**) | `/Users/bellayang/Documents/2026/p1_memory_utility/hf_staging/AAMAS2027-ConditionalMemory/` |
| data card | `docs/hf_card/README.md` (byte-identical to the uploaded card) |
| LongMemEval-V2 | `/tmp/lmev2` (checksum-verified; `trajectories.jsonl` ~1.1 GiB, `questions.jsonl` 451 rows) |
| LongMemEval V1 | `data/lmev1/` |
| ALCF auth | `/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication/inference_auth_token.py` |
| sub-agent reports | `../subagent_*_report.md` (A, A2, B, C, C2, D, E, FIG, G, H, HF, J, K, N, R, ARCHIVE) |

**Python: `/Users/bellayang/miniconda3/bin/python3` (3.13). The system `python3` is 3.9 and
aborts pytest collection on a vendored file — a healthy suite looks broken.**

## Frozen configuration — do not drift

```text
reader + writer : metis / gpt-oss-120b (BARE name; Sophia wants openai/gpt-oss-120b)
endpoint        : https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
reasoning_effort: low      temperature: 0      max_tokens: 512      concurrency: 16
embeddings      : Salesforce/SFR-Embedding-Mistral on Sophia, dim 4096
                  ⚠️ 2,000-Qwen-token budget with halving retry; 98.5% of units truncated
memory unit     : page visit (maximal run of states sharing one URL), median 7,261 tok
prompt version  : p1_deltau_raw_v1
```

Cluster and prompt version are **experimental identity**. A change is a new arm, never a
backfill.

## Result artifacts

Full per-result provenance is in [`docs/RESULT_INDEX.md`](RESULT_INDEX.md); every path
there was checked to exist on 2026-09-30.

| run | path | calls | tracked? |
|---|---|---|---|
| **screened main** | `results/deltau_screened/cells.jsonl` (2,599 rows / 1,157 cells) | 5,198, 0 errors | no |
| screened analysis | `results/deltau_screened/analysis/k3_screened_analysis.json`, `k4_tables.md` | — | via repro copy |
| **representation scale-up** | `results/repr_scaleup/cells.jsonl`, `memories.jsonl`, `analysis/r3_representation_analysis.json`, `write_summary.json`, `eval_summary.json` | 2,368 | **no — nothing tracked** |
| drift probes | `results/repr_scaleup/cross_session_probe.json` (12), `raw_resample.json` (100) | 112 | no |
| pilot arm | `results/deltau_pilot/cells.jsonl` | 1,918 | via slim slice |
| official-prompt arm | `results/deltau_official/cells.jsonl` | 1,920 | via slim slice |
| reader diagnostic | `results/j2_escalation/needle_summary.json` + `results/ledgers/j2*.json` | ~516 | ledgers only |
| **SWE-bench floor pilot** | `results/swebench/floor_pilot.json` | 20 | **yes** |
| tracked slim slices | `results/ledgers/repro/` (+ `MANIFEST.json` with sha256) | — | **yes** |
| design manifest | `data/manifests/k1_screened_cells.jsonl` | — | **yes** |
| bearing structure | `data/manifests/lmev2_leakage_small.jsonl` | — | **yes** |
| SWE-bench pairs | `data/manifests/swebench_pairs_file_seed20261008.jsonl` | — | **yes** |

**`results/**` is gitignored except `results/ledgers/**`.** ⚠️ **The whole representation
scale-up — Contribution B's evidence base — is currently untracked and exists on this
laptop only.** Slim slices for it should be force-added the way the ΔU arms were.

## Scripts

| script | what |
|---|---|
| `scripts/audit_claims.py` | **re-derives 58 checks in 10 sections; proven able to fail.** Run before any manuscript edit |
| `scripts/make_figures.py` | recomputes every figure/caption number → `overleaf/figdata.tex`; **exits non-zero if it disagrees with the audit** |
| `scripts/k1_build_screened_design.py` → `k2_run_screened.py` → `k3_analyze_screened.py` → `k4_report_tables.py` | the screened main run |
| `scripts/r1_write_representations.py` → `r2_run_representations.py` → `r3_analyze_representations.py`, `r2b_raw_resample.py` | the representation scale-up |
| `scripts/swebench_floor_pilot.py`, `src/p1mem/adapters/swebench.py` | Benchmark C |
| `scripts/audit_leakage.py`, `scripts/run_deltau_pilot.py`, `scripts/h_compare_prompt_arms.py`, `scripts/j2_escalate_reader.py`, `scripts/export_hf.py`, `scripts/migrate_schema_v2.py` | audits, earlier arms, reader probe, release |

## Last verified conclusions

Re-derived on 2026-09-30 unless noted.

- **Screen worked:** both-arms-fail **0.7007 → 0.5252**; the pre-committed rule passed.
- **Paired within-memory effect +0.3349** over 60 memories (**35 non-zero contributors**;
  contributors-only **+0.5740**), p = 5e-5, episode-clustered interval excludes zero.
  ⚠️ **Two CI values circulate** — `docs/RESULT_INDEX.md` §F1. The artifact says
  **[+0.1974, +0.4736]**; `SCREENED_RESULT.md` and the manuscript say **[+0.1989, +0.4758]**.
- **Founding hypothesis unsupported:** 0 sign flips / 35 bearing memories, bounded ≤9.9%;
  flips concentrate in RANDOM (17/60); **the additive-null excess is negative in all strata**.
- **Bearing is scarce:** 165/1,889 units bear on any task, **46** on ≥2, from **23** episodes.
- **Compression destroys the effect:** only Raw's paired B−MC interval excludes zero.
- **The cost ranking reverses once formation is charged:** uncharged Summary ≈5.6× Raw;
  charged, Raw/Summary ≈1.08× — **no advantage** — and Structured 4.85× worse. Raw is
  bit-identical across both columns (the A1.5 correctness test).
- **Similarity barely predicts utility:** per-cell ρ = **+0.0868** overall, **+0.0061** in
  RANDOM, **+0.1644** in BEARING (I recomputed all three).
- **The reader is not the bottleneck:** 22/22 on a planted needle in the real ~27k context.
- **Decomposition unidentifiable** — cause is **`F_exec = 0`**, not the crossing defect.
- **SWE-bench not cleared:** floor pilot 4/7 = 57.1%, above the gate, from an
  arm-asymmetric apply failure rather than task difficulty.

## 🔴 Known traps — do not repeat

**The original ten, kept verbatim in substance:**

1. **Advertised ≠ live.** 4 endpoints were advertised and dead. Prove with a real POST.
2. **HF `auth-check` returns 200 for repos you cannot write.** Only an empty-body commit POST discriminates; always use a negative control.
3. **`memory_id` means two things.** Rows use a content hash; some manifests use a positional locator. Join on the **locator**, or check the referent. Two agents hit this independently.
4. **A guard only observed passing is not known to fail.** Three defects were *in guards*. One printed a correct verdict from an empty input.
5. **A zero from `.get(default)` is not a measurement.**
6. **Exit code 0 is not success** — a stage crashed while a script exited 0.
7. **Pooled rates hide the structure that matters** — leakage by answer length, both-arms-fail by stratum, concentration by stratum. Split before quoting.
8. **Matching counts are not corroboration.** Two 35s named different sets (overlap 25).
9. **Throughput is prompt-length dependent** — 341/min at 4k is ~106/min at 24k.
10. `datascience_collab` expires **2026-10-01**; use AuroraGPT. Aurora is allocated but unused (gateway-bound).

**Added since, from the docs:**

11. **`F_empty` is `null`, not 0.000.** Both `01_noise_floors.json` artifacts carry
    `point: null` with flag `WITHOUT_ARM_REUSED:254 group(s)` — the WITHOUT arm was served
    from cache, so its spread is zero **by construction**. Report **UNMEASURED**. Same
    rule as the robust−naive gap (`ROBUST_NAIVE_GAP_STATUS = NOT_MEASURABLE`).
12. **The endpoint drifted between 2026-09-29 and 2026-09-30.** Byte-identical prompts
    differ in text on 53% of rows across days, in reward on 2.46%. A cache-disabled probe
    settles it as a serving change, not sampling noise: same-minute repeats 6/6 identical,
    reproducing 09-30 6/6 and 09-29 2/6. It is **mean-preserving** on a 100-cell resample
    (0.3100 → 0.3100, 7 up / 7 down), but **every cross-day comparison carries a per-cell
    noise term a same-session one would not.**
13. **`ok=True` did not mean the writer finished.** 7 of 60 summaries were truncated
    mid-sentence and admitted as valid; the module's own docstring named the hazard and the
    guard it pointed at checked a different condition.
14. **Malformed-JSON rates need two denominators.** 3/60 over all structured writes,
    **0/57** over writes that finished, 3/3 over writes that hit the cap. The n=8 pilot
    never met the cap, so "0/8 malformed" could not have observed this.
15. **Unapplicable edits must be `reward: None`, never `0.0`.** On SWE-bench, scoring the
    three WITH-arm apply failures as zeros would have shown memory *harming* (2/7 vs 3/7),
    manufactured entirely by an edit-format artifact.
16. **A positive control on the scorer caught four harness defects that each produced a
    plausible `0.0`.** The gold-patch control went 0/6 → 3/6 → 10/10. Without it, SWE-bench
    would have been killed on bugs in its own harness.
17. **`git add -A` is a mis-attribution generator in this repo.** Concurrent agents; it has
    already swept other agents' in-progress files into the wrong commit, in both directions.
    **Stage explicit paths, then check `git show --stat`.**
18. **The screened cache is readable only by the pre-`5330158` 12-field key shape.**
19. **A post-hoc restriction is not a result.** The 0.2424 flip rate on "cells that can
    move" conditions on an outcome; it is a diagnostic of why a null is uninformative.
20. **Do not quote the withdrawn embedding figure.** "120 units / 6.4%" was computed against
    the withdrawn 3,400-token cap; the adopted 2,000-token budget gives **29 units / 1.5%**.

## Invalid / superseded runs

- `results/runs/noise_floor/` — an early probe, one arbitrary memory per task, 2/92 accuracy. **Superseded.**
- Both unscreened arms are **valid but floor-limited** (~78.5% / 83.75% both-arms-fail) — keep as the dilution comparator, never quote as the effect.
- The official-prompt arm **refuted its own hypothesis**: accuracy fell 5.7 pts because 128 correct guesses became abstentions. Do **not** re-run another prompt wording.
- "variance shares all 0.0000" — 🔴 **RETRACTED, never measured.**
- SWE-bench floor pilot **#1 is VOID** (the model was shown the wrong 90 lines); **#2 stopped at the gate.**
- The n=8 representation pilot is **superseded for every rate**; keep only its compression ratios.

## Currently running (2026-09-30 16:25 CDT)

Phase 3, six sub-agents, no pausing at milestones:

| agent | task | state |
|---|---|---|
| SA-WRITE | abstract / story reframe (P1-C01) | landed Overleaf `3c06d3a` |
| SA-FIG2 | utility–efficiency frontier + figure/table set (P1-C03, C13) | running |
| SA-HF2 | HF v0.2 representation release + data card (P1-C04, C15) | running |
| SA-SWE | SWE-bench harness parity fix, then pilot (P1-C05 → C06) | running |
| SA-SCI | SciCode adapter, then pilot (P1-C08 → C09) | running |
| SA-ARCHIVE | result/figure indices, README, this file, TODO (P1-C14) | this document |

**No batch or cluster job is queued.** Everything has run on this laptop against the ALCF
gateway. Aurora is allocated but gateway-bound and unused.

## Active TODOs

Authoritative, with terminal states: [`docs/MASTER_TODO.md`](MASTER_TODO.md).

Submission-critical and **not yet DONE**: P1-C01 (abstract, in review), P1-C03 (frontier
figure), P1-C04/C15 (HF v0.2 + card), P1-C05→C07 (SWE-bench parity → pilot → run),
P1-C08→C10 (SciCode), P1-C11 (cross-benchmark synthesis, blocked), P1-C13 (figures/tables),
P1-C16 (claim audit, ongoing), P1-C17 (manuscript sync), **P1-C18 (AI-assistance
disclosure — AAMAS requires it and the section is still empty)**.

## Handoff instructions

1. Read this file, then [`docs/RESULT_INDEX.md`](RESULT_INDEX.md) §F (the open
   disagreements), then [`docs/THE_HONEST_HEADLINE.md`](THE_HONEST_HEADLINE.md), then
   [`docs/DEFECT_REGISTER.md`](DEFECT_REGISTER.md).
2. Run `/Users/bellayang/miniconda3/bin/python3 scripts/audit_claims.py` — **if it fails,
   stop and find out why before anything else.**
3. Run the suite with the 3.13 interpreter (`pytest -q`, 487 tests).
4. Before touching a figure, run `scripts/make_figures.py`; a stale `figdata.tex` cannot
   silently ship, but a *missing* regeneration can leave you editing the wrong number.
5. **Never quote a number you have not re-derived from an artifact.**
6. **Never `git add -A`.** Stage explicit paths and verify with `git show --stat`.

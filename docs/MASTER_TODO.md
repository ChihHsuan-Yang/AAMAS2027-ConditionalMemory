# P1 Master TODO — authoritative

**Terminalized 2026-09-30, re-terminalized 2026-10-01 by SA-ARCHIVE.** Every task on this
page carries one of six terminal states. **No task is ever silently removed**; anything dropped carries `KILLED`
and its measured reason. Legacy IDs from Phases 1–2 are retained in §4 with the Phase 3
item that absorbed them.

```text
DONE · RUNNING · BLOCKED · TODO · DEFERRED · KILLED
```

**AAMAS 2027 main track. Abstract 1 Oct AoE · Paper 8 Oct AoE.**

**Contract (Phase 3):** the Master Agent does not pause at milestones for authorization.
Execution continues until the active list is terminal. Author list, reciprocal reviewer,
OpenReview logistics and submission administration are **user-owned and off the scientific
critical path** — they are not blockers and are not reported as such. Overleaf stays in
standard double-blind form: `Anonymous Author(s)`, no affiliations, no acknowledgements, no
identifying paths.

**Counts (mechanically re-derived 2026-10-01, see §5):** DONE 134 · DEFERRED 38 ·
KILLED 16 · TODO 7 · RUNNING 2 · BLOCKED 1 — **198 distinct IDs**, every one carrying
exactly one terminal state.

🔴 **The agent-actionable open set is SIX IDs:** `P1-C17` (final manuscript sync),
`P1-C19` (SWE-bench coverage), `P1-C21` (HF v0.3/v0.4), `P1-C22` (three `main.tex` ↔
artifact inconsistencies), `P1-I11` (🔴 the representation scale-up slices are still
untracked), `P1-I13` (the efficiency ratios). `P1-C20` (page budget) is **blocked on the
author by design**. §5 lists all ten open rows with what each waits on; §3 holds
POST-SUBMISSION / FUTURE WORK.

---

## 1. Level 1 — submission-critical

| ID | Task | Owner | Status | Evidence / blocker |
|---|---|---|---|---|
| **P1-C01** | Abstract / story reframe — lead with conditional utility + sparsity, drop the sign-flip framing | SA-WRITE | **DONE** | abstract v5, 299 words, in the manuscript; sign-flip and decomposition framing removed |
| **P1-C02** | Overleaf figure audit — ranked plan, 3 in / 4 rejected / 1 blocked | SA-FIG | **DONE** | `docs/FIGURE_PLAN.md`; repo `eb4deb3` |
| **P1-C03** | **Utility–efficiency frontier figure** | SA-FIG2 | **DONE** | ✅ **shipped as `fig:frontier`** in `main.tex` (verified present 2026-10-01 by SA-ARCHIVE). Inputs `results/repr_scaleup/`. Was blocked because `memory_representation` was `{'raw'}` on all 2,599 screened rows |
| **P1-C04** | HF **v0.2** — add Summary/Structured rows | SA-HF2 | **DONE** | tag `v0.2-repr-derived`, **5,643 rows** (raw 4,519 / summary 570 / structured 554), schema v3, verified by downloading the tag |
| **P1-C05** | **SWE-bench harness parity fix** — make the prompt arm-symmetric so the memory's own diff cannot be mistaken for the editable region | SA-SWE | **DONE** | apply-gap **0.375 → 0.000**; cause was the reader imitating the memory's diff fence, not the editable region |
| **P1-C06** | SWE-bench valid pilot at 30–40 cells | SA-SWE | **DONE** | both-arms-fail **37.5%** [22.9, 54.8], below threshold; 0 apply-failures scored as rewards. **django-only** |
| **P1-C07** | SWE-bench representation arm (Raw/Summary/Structured) | Master → **SA-SWE-FINAL** | **DONE** (coverage extension continues under C19) | v1 (126 calls) **superseded** by **v2** (128 calls, 96 cells, 0 dirty, matched n=13 django) + **sympy** (42 calls, 33 cells, matched n=3 after defect 21). Pooled matched **15**. Every contrast `NOT_ESTABLISHED` per-repo and pooled. Gates re-checked from disk: scorer control 20/20 (**union** of django 12/12 + sympy 8/8 — sympy's own is **8/8**), apply parity gap +0.000 |
| **P1-C08** | SciCode adapter | SA-SCI | **DONE** | adapter + 45 tests, mutation-checked 4/4 |
| **P1-C09** | SciCode pilot | SA-SCI | **DONE** | both-arms-fail 0.370–0.456 across three representations, all below threshold; errors symmetric across arms |
| **P1-C10** | SciCode procedural-memory evaluation (a **case study**, never a main table) | SA-SCI → Master | **DONE** | **Scaled to the full 154-pair pool** (924 arm-runs), design pre-committed in `docs/SCICODE_SCALEUP_PRECOMMITMENT.md`. Matched set n=122: raw −0.0082 · summary +0.0164 · structured +0.0246. 🔴 **All three paired contrasts cross zero → `ORDERING_VERDICT: NOT_ESTABLISHED`.** The point-estimate ordering differs across benchmarks; LongMemEval's Raw-dominant ordering is **not reproduced**. **NOT an established inversion** — `audit_claims.py` and `make_figures.py` both forbid that wording and both are verified able to fail. Free control: F_exec = 5/135 = 0.0370, **larger than the biggest point estimate** |
| **P1-C11** | Cross-benchmark synthesis | Master | **DONE** | Figure 5 populated with the one quantity both benchmarks define identically (paired per-cell representation contrast, task-clustered). LongMemEval + SciCode rows are real; the SWE-bench row is **visibly empty and labelled**, pending C07 analysis. Per-representation mean ΔU is deliberately **not** compared across benchmarks — different execution floors (0 vs 0.0370) |
| **P1-C12** | Final representation comparison (Contribution B) | Master | **DONE** | `docs/REPRESENTATION_RESULT.md`; 9 audit checks re-derive both cost columns |
| **P1-C13** | Main figures and tables | SA-FIG2 → **SA-PAGE** | **DONE** (placement continues under C20) | **5 figures + 3 tables** at Overleaf `1961825`, counted from `main.tex` by SA-ARCHIVE: `fig:pipeline`, `fig:bearing`, `fig:similarity`, `fig:frontier`, `fig:readertransfer`; `tab:coverage`, `tab:crossbench`, `tab:screened`. ⚠️ the "2 tables" in every earlier doc was **stale** — `tab:coverage` was added later. 10 pages total; the body runs ~5,400 chars onto p9 and closing it now costs content (`docs/PAGE_BUDGET_DECISION.md`) |
| **P1-C14** | GitHub handoff documentation — result index, figure index, README hub, handoff, terminal TODO | SA-ARCHIVE | **DONE** | RESULT_INDEX, FIGURE_INDEX, README hub, HANDOFF_CURRENT |
| **P1-C15** | HF data card update for v0.2 | SA-HF2 → **SA-HF** | **DONE** | `docs/hf_card/README.md` carries the v0.2 figures (5,643 rows, three representations) and already anticipates v0.3/v0.4. v0.3 itself is **C21** |
| **P1-C16** | Claim/evidence audit | Master → **SA-FINAL-AUDIT** | **DONE** as a milestone; **standing** thereafter | `scripts/audit_claims.py` now prints **129 PASS / 0 FAIL across 16 sections** (counted 2026-10-01; the "38"/"58"/"123" in older docs are all stale). 638 tests pass. Proven able to fail: each guard is verified by planting the defect it forbids. Guards include the SciCode "inversion" wording, the absolute-home-path identity scan (with its own non-vacuity check), both printed CIs, and `make_figures.py`'s five Figure-5/SWE-bench guards |
| **P1-C17** | Final manuscript sync + compile + anonymity + citation check | **SA-PAGE** | **TODO** | 🔴 **the one genuinely open submission-critical item.** Absorbs legacy P1-095 and P1-100. Overleaf `1961825` compiles to 10 pages; anonymity is audit-enforced (no absolute home path in `main.tex` or any tracked artifact). Blocking sub-items: the page budget (C20) and the three inconsistencies in C22 |
| **P1-C18** | **AI-assistance disclosure section** (prompt + tool + version) | Master | **DONE** | ✅ `\section*{Use of AI-Assisted Technologies}` is **written** at `main.tex:1678` (~2,400 chars; verified non-stub by SA-ARCHIVE 2026-10-01). Discloses under the **stronger clause** because AI shaped experimental design, names the tool and version, and points prompts + defect register to supplementary. Source `docs/AI_ASSISTANCE_DISCLOSURE.md` |
| **P1-C19** | **SWE-bench coverage completion** — run the remaining valid cells under the FROZEN eligible universe; mark the rest excluded with reasons | **SA-SWE-FINAL** | **RUNNING** | split out of C07 by SA-ARCHIVE so a growing arm does not keep an otherwise-finished item open. Executed **66 of 107** runnable (django 55 + sympy 11); **41 django remain**. 🔴 **Do not redefine "eligible" after seeing outcomes**, and do not relax `tasks_per_memory=4` in place — see §Killed, and `docs/COVERAGE_MANIFEST.md` §3 |
| **P1-C20** | **Page budget** — the body runs ~5,400 chars onto p9 against an 8-page limit | **user decision**, executed by SA-PAGE | **BLOCKED** (on the author) | `docs/PAGE_BUDGET_DECISION.md` measures five options and their costs. Closing the gap now **removes content**, which is not an agent's call. Recommended: **C** (AI disclosure → supplementary, explicitly policy-permitted, loses no science) then **A** (Figure 1 → supplementary). 🔴 **B, D and E delete evidence and must not be used to buy space**, and no `\vspace` / geometry / font change — that is format gaming and reviewers check |
| **P1-C21** | **HF v0.3** (SciCode, Apache-2.0, content OK) and **v0.4** (SWE-bench, 🔴 **metrics + ids ONLY**) | **SA-HF** | **RUNNING** | v0.3 staging rebuild in flight 2026-10-01 12:23 CDT. 🔴 **`export_hf.py` does NOT migrate schemas** — the ledgers are v1/v2 and it needs v3. The exporter must call `assert_content_redistributable` for SWE-bench. SciCode ships **raw-only, 154 of 462 cells**: the summary/structured memory text was never persisted |
| **P1-C22** | **Three documented inconsistencies between `main.tex` and the artifacts** | **SA-PAGE** / SA-FINAL-AUDIT | **TODO** | found by SA-ARCHIVE 2026-10-01, each re-derived: (1) `main.tex:1664` quotes the **superseded** cross-session `+0.1268` as "the reader effect this apparatus did detect" three lines after the same paragraph correctly reports the session-matched `\rgSmDiff` = +0.0982 — a **retracted number still circulating in its own correction's paragraph**; (2) `\rgWithoutDelta` = −0.0688 is the **withdrawn** cross-session decomposition, printed at `main.tex:1640` and in Figure 6's caption constraint; (3) the efficiency ratios of **P1-I13**. None changes a conclusion; all three are retracted-number-still-circulating, this project's registered defect shape |

### Level-1 items that will consume the remaining page budget

C03 (a figure), C13 (its placement) and C18 (required prose) all draw on the same
~50–80 pt. **Measure where the body ends, not the total page count** — page count is flat
here because references are uncapped, and reading it as slack is a registered defect.

---

## 2. Level 2 — important if feasible (none blocks submission)

| ID | Task | Status | Note |
|---|---|---|---|
| **P1-I01** | Top-k retrieval baseline | **DEFERRED** | 🔴 **closed by `docs/SCOPE_FREEZE.md` §3/§4**: `retrieval_k` is `None` on every existing row, so this is a **new arm**, not a completion of approved coverage. Absorbs half of legacy P1-010. → POST-SUBMISSION |
| **P1-I02** | Keep-all / no-memory retrieval baselines | **DEFERRED** | same reason as I01: a new arm under a frozen scope. Absorbs the other half of P1-010. → POST-SUBMISSION |
| **P1-I03** | Position-effect expansion | **DEFERRED** | the n=12 result is already labelled **PROVISIONAL** in `docs/POSITION_EFFECT.md` and in the manuscript, so the paper does not rest on it. Expanding it is a new arm. Absorbs legacy P1-132. → POST-SUBMISSION |
| **P1-I04** | Cross-benchmark representation ranking | **KILLED** | C07 and C10 both landed and **both returned `NOT_ESTABLISHED`**, so the ranking the item asked for **cannot be produced from this evidence** — that is the answer, not a blocker. The paper reports the heterogeneity as a limit (`SCOPE_FREEZE` result **G**) and `main.tex` carries `tab:crossbench`. Two guards forbid the word "inversion" |
| **P1-I05** | Representation-induced harmfulness | **KILLED** | 🔴 the design **screened FOR bearing**, so any harm rate computed on it is a **selected-subgroup estimate** and the unscreened 26/872 is not a natural base rate either (the pairing is still ours). `RESULT_INDEX.md` §G forbids quoting a harm rate. Not a measurement this design can take; the study version is **P1-H08** |
| **P1-I06** | Domain utility/cost comparison | **KILLED** | 🔴 **not computable as specified.** Cost is **not poolable across models** (Gemma reports no reasoning tokens at all — an absence, not a zero) and the three benchmarks have different execution floors, which is exactly why Figure 5 plots *contrasts* rather than per-representation ΔU. A cross-domain cost comparison would mix currencies |
| **P1-I07** | Extra retrieval-budget points for the frontier | **DEFERRED** | depends on I01, now DEFERRED. The shipped `fig:frontier` has one budget point per representation and says so. → POST-SUBMISSION |
| **P1-I08** | Benchmark-native memory baseline | **DEFERRED** | a new arm under the frozen scope; no existing row carries a benchmark-native memory. → POST-SUBMISSION |
| **P1-I09** | Dataset example notebook | **DEFERRED** | `notebooks/` is empty and this is release polish, not a submission dependency. The data card already carries a runnable load+validate command. → POST-SUBMISSION |
| **P1-I10** | Public reproduction script | **DONE** *(as served)* | `scripts/audit_claims.py` re-derives **129 checks** from the tracked slim slices alone, `scripts/count_experiment_accounting.py` re-derives every count, and `results/ledgers/repro/MANIFEST.json` pins each sha256. A reviewer can clone and re-derive every headline number. A separate one-command wrapper would add convenience, not capability → **POST-SUBMISSION** |
| **P1-I11** | **Track the representation scale-up artifacts** — force-add slim slices + a `MANIFEST.json` for `results/repr_scaleup/` | **TODO** | 🔴 **STILL OPEN, re-verified 2026-10-01 by SA-ARCHIVE:** `git ls-files results/ledgers/` returns **nothing** for `repr_scaleup`, so Contribution B's entire evidence base (1,124 rows, 2,368 calls) exists on this laptop only. Every other arm got a slim slice — screened, pilot, official, gemma_reader, raw_session_matched, scicode, swebench. **The representation arm is the one gap**, and it is the arm the compression finding rests on. Owner should be whoever ships the release (SA-HF) |
| **P1-I12** | **Resolve the paired-CI disagreement** | **DONE** | ✅ closed in the **artifact's** direction: `audit_claims.py` now asserts `main.tex` prints **[+0.1974, +0.4736]** (episode-clustered) and **[+0.2085, +0.4606]** (memory bootstrap) — both PASS, verified by SA-ARCHIVE 2026-10-01, and the audit covers them where it previously covered neither. ⚠️ `docs/SCREENED_RESULT.md` still prints the older **[+0.1989, +0.4758]** / **[+0.2138, +0.4622]** pair, which **no artifact on disk contains**; `RESULT_INDEX.md` §F1 keeps the history. Neither interval changes a conclusion |
| **P1-I13** | **Correct the efficiency ratios in `main.tex`** | **TODO** | 🔴 **still open.** `RESULT_INDEX.md` §F3: the paper says `5.2×` (audited **5.58×**) and "roughly 5×" for the charged reversal — true of Structured (4.85×) but **wrong for Summary (1.08×)**, the representation the sentence is about. The paragraph **understates its own correction**: charged, Summary is not 5× worse than Raw, it is *indistinguishable* from Raw, which is the actual finding. Folded into **C22**; owner SA-PAGE |

---

## 3. Level 3 — HOLD / post-submission

Recorded so they are not lost; none is in scope now.

| ID | Task | Status | Absorbs / note |
|---|---|---|---|
| **P1-H01** | Jev decision baseline | **DEFERRED** | legacy D-01 |
| **P1-H02** | Learned conditional memory gate | **DEFERRED** | legacy D-03 |
| **P1-H03** | LLM memory-manager comparison | **DEFERRED** | legacy D-02 |
| **P1-H04** | Cross-model replication | **DEFERRED** | legacy D-05 |
| **P1-H05** | Vector DB / production store | **DEFERRED** | legacy D-06 |
| **P1-H06** | More benchmarks | **DEFERRED** | legacy D-04 |
| **P1-H07** | Semantic-type taxonomy redesign | **DEFERRED** | legacy P1-006, P1-129 |
| **P1-H08** | Harmful-memory prevalence study | **DEFERRED** | the current design cannot support a harm rate |
| **P1-H09** | Full P3 receiver integration | **DEFERRED** | 4 reserved schema fields already present and null-enforced |
| **P1-H10** | Training a retention policy | **DEFERRED** | forbidden until the main paper is complete |
| **P1-H11** | **RL memory manager** | **DEFERRED** | named in `SCOPE_FREEZE.md` §4. Distinct from H02 (a learned *gate*) and H03 (an *LLM* manager): this is a trained policy with a reward signal |
| **P1-H12** | **New retrieval architectures** | **DEFERRED** | `SCOPE_FREEZE.md` §4. `retrieval_k` is `None` on every existing row, so every retrieval variant is a new arm. Absorbs P1-I01, P1-I02, P1-I07 |
| **P1-H13** | **New representation families** beyond raw / summary / structured | **DEFERRED** | `SCOPE_FREEZE.md` §4 |
| **P1-H14** | **Additional backbones** beyond `gpt-oss-120b` and `gemma-4-31B-it` | **DEFERRED** | `SCOPE_FREEZE.md` §6 freezes the model scope. Distinct from H04, which is replication on the *same* two |
| **P1-H15** | **The cross-session floor, measured as its own quantity** | **DEFERRED** | 🔴 **nobody has measured this.** We know the endpoint drifts (554/1,124 WITHOUT-arm texts differ across sessions, reward on 82, mean −0.0303) and we worked around it by session-matching every arm. What does **not** exist is a *floor*: a pre-committed estimate of the per-cell noise a cross-session comparison carries. Defects #25 and #28 are both this gap surfacing. Cheap to run and the most scientifically interesting of the deferrals |
| **P1-H16** | **SciCode `dep OR lex` relatedness union** — +10 eligible pairs, **unexecuted** | **DEFERRED** | `COVERAGE_MANIFEST.md` §2.2: 7 of the 12 dependency-relatedness pairs are never admitted by lexical, so a union yields **164** eligible rather than 154. Not implemented. These 10 are an *eligible set under a different defensible relatedness definition*, recorded rather than quietly absent. 🔴 Running it means a **new pre-committed manifest**, not an extension of the shipped one — the shipped 154 is "the whole pool" **only under `relatedness=lexical`** |

### What POST-SUBMISSION / FUTURE WORK holds, in one list

Every item below is **DEFERRED, not killed**, and each is a good idea that is
**not a reason to delay submission** (`SCOPE_FREEZE.md` §4):

**Jev baseline** (H01) · **learned memory gate** (H02) · **LLM memory-manager
comparison** (H03) · **RL memory manager** (H11) · **new retrieval
architectures** (H12, absorbing I01/I02/I07) · **semantic-type redesign**
(H07) · **new representation families** (H13) · **additional benchmarks**
(H06) · **additional backbones** (H14) · **the cross-session floor nobody has
measured** (H15) · **the SciCode dep-OR-lex union, +10 eligible pairs,
unexecuted** (H16) · cross-model replication (H04) · production vector store
(H05) · harmful-memory prevalence (H08) · full P3 receiver integration (H09) ·
retention policy (H10) · position-effect expansion (I03) · benchmark-native
memory baseline (I08) · dataset example notebook (I09) · a one-command public
reproduction wrapper (I10).

🔴 **Four storylines are NOT to be resurrected** (`SCOPE_FREEZE.md` §5), each
demoted for a measured reason already in `docs/`: the **sign-flip headline**,
the **variance-decomposition headline**, the **semantic-type taxonomy** as a
live axis, and **harmful-memory prevalence** on this design. *Demotion is not
an oversight for a later agent to correct.*

---

## 4. Legacy ledger — every Phase-1/2 ID, terminalized

Nothing here is dropped. Where a Phase-3 item took over, it is named.

### 4.1 Scientific / design

| ID | Task | Status | Reason / successor |
|---|---|---|---|
| P1-001 | Freeze storyline | **DONE** | `docs/PROJECT_GOAL.md` |
| P1-002 | Memory acquisition protocol (writer never sees the future task) | **DONE** | `docs/MEMORY_PROTOCOL.md` |
| P1-003 | Define Raw | **DONE** | deterministic, 0 calls |
| P1-004 | Define Summary | **DONE** | median 362 tok, cr 0.063 |
| P1-005 | Define Structured | **DONE** | median 246 tok, cr 0.037 |
| P1-006 | Memory semantic-type labels | **KILLED** | κ = 0.000 — the native pass labelled all 8 segments `episodic`. Not safe as an axis; a redesign is held as P1-H07 |
| P1-007 | WITH/WITHOUT intervention definition | **DONE** | controlled filler required in both arms |
| P1-008 | Robust useful/harmful definition vs the noise floor | **DONE** | committed before any data |
| P1-009 | Efficiency metric definitions | **DONE** | partial by design: exposure, formation, latency and API-call families are defined and reported in `r3_representation_analysis.json`. Storage, retrieval and selectivity are killed separately as P1-067 / P1-068 / P1-072 |
| P1-010 | Retrieval baselines None / Keep-All / Top-k / Oracle | **DEFERRED** | `retrieval_k` is `None` on every row; this is a new arm, now owned by P1-I01 / P1-I02 |
| P1-011 | Figure/table targets + schema support check | **DONE** | `docs/FIGURE_INDEX.md`; schema v2 carries the fields |

### 4.2 Benchmark / data

| ID | Task | Status | Reason / successor |
|---|---|---|---|
| P1-020 | LongMemEval-V2 adapter + official scorers | **DONE** | 8 distinct eval specs, dispatched on the full spec string |
| P1-021 | V2 memory unit + pairing | **DONE** | page visit, median 7,261 tok, 1,889 units |
| P1-022 | Leakage audit + detector | **DONE** | 17/17 controls; rates are **lower bounds** |
| P1-023 | BEAM adapter | **KILLED** | **92.6% of cited turns are cited by exactly one question** — cannot supply the multi-task axis. Also CC BY-SA 4.0 (ShareAlike) |
| P1-024 | BEAM task/domain mapping | **KILLED** | depends on P1-023 |
| P1-025 | SciCode adapter | **DEFERRED** | superseded — scoped down to a case study; now owned by P1-C08 |
| P1-026 | SciCode transfer mapping | **DEFERRED** | superseded — now owned by P1-C08 / P1-C09 |
| P1-027 | Licence / provenance audit | **DONE** | `docs/BENCHMARK_LICENSES.md`; it unblocked the HF export gate |
| P1-028* | Benchmark C selection (BEAM replacement) | **DONE** | SWE-bench Verified selected, **conditionally** — `docs/BENCHMARK_C_DECISION.md`. (Tracked as P2-06; given an ID here so the selection itself is not orphaned) |

### 4.3 Infrastructure

| ID | Task | Status | Note |
|---|---|---|---|
| P1-030 | Runtime ALCF discovery | **DONE** | 4 clusters incl. undocumented `tara` |
| P1-031 | Minerva feasibility | **DONE** | `gpt-oss-120b` **503 persistent** on Minerva |
| P1-032 | Freeze primary model + cluster | **DONE** | gpt-oss-120b on **Metis** |
| P1-033 | Freeze embedding model | **DONE** | SFR-Embedding-Mistral, 2,000-Qwen budget |
| P1-034 | Concurrency benchmark | **DONE** | 16 workers, 0 failures / 316 requests |
| P1-035 | Aurora orchestration runner | **KILLED** | allocated but **gateway-bound**; the laptop path carried every run. Not a submission dependency |
| P1-036 | Response cache | **DONE** | isolation verified behaviourally |
| P1-037 | Retry / resume / checkpoint | **DONE** | 12 cells re-ran with 0 calls |
| P1-038 | Cost / token / latency logger | **DONE** | every call logged |

### 4.4 Data / release

| ID | Task | Status | Note |
|---|---|---|---|
| P1-040 | Canonical dataset schema | **DONE** | **94 fields → 97 released**, schema `p1mem_conditional_memory_utility_v2` |
| P1-041 | HF staging dir, never the repo root | **DONE** | `../hf_staging/`, gitignored |
| P1-042 | HF data card | **DONE** | `docs/hf_card/README.md`, byte-identical to the uploaded card |
| P1-043 | Derived-data writer | **DONE** | export gates, now 5 of them after one shipped a defect |
| P1-044 | Dataset validation script | **DONE** | 66 tests; 15 deliberate corruptions all caught |
| P1-045 | HF upload / version process | **DONE** | v0.1 only: tag `v0.1-lmev2-derived`, remote verified by fresh download. v0.2 is P1-C04 |
| P1-046 | P3 reserved fields | **DONE** | 4 reserved fields, validator enforces null |

### 4.5 Experiments

| ID | Task | Status | Note |
|---|---|---|---|
| P1-050 | Extraction pilot | **DONE** | 8 segments, 24 calls. ⚠️ **superseded for every rate** by the scale-up |
| P1-051 | Noise / reliability pilot | **DONE** | F_exec / F_judge = 0.000, each positive-controlled. **F_empty = UNMEASURED** (cached WITHOUT arm), never 0 |
| P1-052 | LongMemEval-V2 pilot | **DONE** | 1,918 calls. Valid but **floor-limited** |
| P1-052b | Official-prompt arm | **DONE** | accuracy fell 5.7 pts; 128 correct guesses became abstentions. **Do not re-run another prompt wording** |
| P1-053 | LongMemEval-V2 main run | **DONE** | the screened run: 5,198 calls, 0 errors |
| P1-054 | BEAM pilot | **KILLED** | BEAM dropped |
| P1-055 | BEAM main run | **KILLED** | BEAM dropped |
| P1-056 | SciCode pilot | **DONE** | superseded — absorbed by **P1-C09**, which is DONE. (Was BLOCKED only because it predated the Phase-3 item that took it over) |
| P1-057 | SciCode main run | **DONE** | superseded — absorbed by **P1-C10**, which is DONE (154 pairs, 924 arm-runs, whole eligible pool) |
| P1-058 | Targeted replication queue | **KILLED** | **`F_exec = 0`** — 0 of 1,157 cells have replicates that disagree. Re-running a deterministic reader buys nothing |
| P1-059 | Missing-cell recovery | **KILLED** | 0 errors and 0 missing cells across 9,036 calls. Nothing to recover |

### 4.6 Analysis

| ID | Task | Status | Note |
|---|---|---|---|
| P1-060 | Continuous ΔU analysis | **DONE** | `k3_screened_analysis.json` |
| P1-061 | Robust useful/harmful labels | **DONE** | with the `NOT_MEASURABLE` rule on the robust−naive gap |
| P1-062 | Breadth vs specialization | **DONE** | Figure 2(a); `docs/BEARING_SCARCITY.md` |
| P1-063 | Sign-flip analysis | **DONE** | Table `tab:flips`; **descriptive only** per A1.1 |
| P1-064 | NEAR / MID / FAR bands | **DONE** | `\paragraph{Distance bands.}`; far band is 8 cells and no sign is read from it |
| P1-065 | Similarity vs utility | **DONE** | Figure 3 |
| P1-066 | Representation comparison (Contribution B) | **DONE** | reported as P1-C12 |
| P1-067 | Storage efficiency | **KILLED** | not measured and not needed; nothing in the paper rests on it |
| P1-068 | Retrieval efficiency | **KILLED** | no retrieval arm exists; reinstating it means the new arm in P1-I01 / P1-I07 |
| P1-069 | Exposure efficiency | **DONE** | ΔU per 1k exposed tokens, both columns |
| P1-070 | Latency efficiency | **DONE** | amortized per cell in `r3` |
| P1-071 | API / compute efficiency | **DONE** | writer calls per memory, amortized |
| P1-072 | Selectivity efficiency | **KILLED** | requires a retrieval arm |
| P1-073 | Extraction efficiency | **DONE** | formation cost, charged — the finding in `docs/REPRESENTATION_RESULT.md` |
| P1-074 | Utility–efficiency frontier | **DONE** | superseded — **P1-C03** shipped `fig:frontier` |
| P1-075 | Variance decomposition | **KILLED** | 🔴 **unidentifiable.** Cause is **`F_exec = 0`** — a deterministic reader leaves no residual scale — not the task-crossing defect that *was* fixed. Shares came back equal to 16 s.f. at the optimizer's clip while reporting `converged=True`. **No share may be quoted**; `audit_claims.py` fails if one appears; a figure is forbidden |

### 4.7 Manuscript

| ID | Task | Status | Note |
|---|---|---|---|
| P1-080 | Abstract v3 | **DONE** | superseded — P1-C01 landed v5 |
| P1-081…087 | Intro · Related Work · Method · Representations · Benchmarks · Utility · Efficiency | **DONE** | 0 undefined citations, CCS added |
| P1-088…090 | Results · Analysis · Limitations | **DONE** | all three written against verified sources |
| P1-091…092 | Figures · Tables | **DONE** | superseded — **P1-C13** is DONE (5 figures + 3 tables). Remaining placement work is **P1-C20** |
| P1-093 | Reproducibility statement | **DONE** | — |
| P1-094 | Claim/evidence audit | **DONE** | superseded — **P1-C16**, 129 checks / 0 FAIL, standing thereafter |
| P1-095 | Final compile + anonymity + citation check | **TODO** | superseded — owned by **P1-C17**, which is the one genuinely open submission-critical item. Counted separately per the §5 counting rule |
| P1-096 | AI-assistance disclosure | **DONE** | superseded — **P1-C18** is DONE: the section is written at `main.tex:1678`, no longer a stub |

### 4.8 Release

| ID | Task | Status | Note |
|---|---|---|---|
| P1-100 | GitHub cleanup | **TODO** | folds into **P1-C17**. The one concrete sub-item is **P1-I11** (the untracked representation scale-up slices) |
| P1-101 | README reproduction instructions | **DONE** | README §Setup + §Handoff |
| P1-102 | HF snapshot | **DONE** | v0.1 + tag |
| P1-103 | Data card | **DONE** | 20 sections |
| P1-104 | Licence verification | **DONE** | `docs/BENCHMARK_LICENSES.md`; the exporter fails closed on unknown licences |
| P1-105 | Results ledger | **DONE** | `docs/RESULTS_LEDGER.md` + `docs/RESULT_INDEX.md` |
| P1-106 | Final consistency audit | **TODO** | folds into **P1-C16** (standing, green at 129/129) and **P1-C17**. The open findings are enumerated in **P1-C22** |

### 4.9 Findings recorded as IDs (§32 requires the trigger be kept)

These are **triggers**, not work items. Each is terminal.

| ID | Status | Disposition |
|---|---|---|
| P1-110 | **DONE** | V2 ships no evidence labels → the memory unit is defined without them and utility is purely counterfactual |
| P1-111 | **DONE** | Oracle context is 100% evidence → every cell carries controlled filler |
| P1-112 | **DONE** | EvoMemEval's 46 multi-task / 17 flipping memories → conceded in Related Work |
| P1-113 | **DEFERRED** | EvoMemEval's 22.0% natural harm rate; useful external evidence, not cited yet |
| P1-114 | **DONE** | the headline analysis was written from scratch (`k3_analyze_screened.py`) |
| P1-115 | **DONE** | `get_embedding` and `vectorstore.py` were written, not reused |
| P1-116 | **DONE** | the "679 free natural cells" claim was **refuted**; the matrix is constructed and the paper says so |
| P1-117 | **DONE** | advertised ≠ live → every model dependency needs a real POST. Trap #1 |
| P1-118 | **DONE** | reasoning tokens eat `max_tokens` → hard error in the client, never scored |
| P1-119 | **DONE** | 8 eval specs not 6 → the adapter keys on the full spec string |
| P1-120 | **DONE** | HF `auth-check` always says yes → trap #2 |
| P1-121 | **DONE** | Python 3.9 aborts collection → 3.13 pinned everywhere |
| P1-122 | **DONE** | `memory_id` collision → locator ruling. ⚠️ the ruling has **failed three times downstream**; trap #3 |
| P1-123 | **DONE** | `semantic_distance_band` is a per-benchmark tercile, computed as a post-pass |
| P1-124 | **DONE** | labels emit `undetermined` until the floor exists, then recompute |
| P1-125 | **DONE** | REML recovery error at 30 memories → 60 minimum adopted |
| P1-126 | **DONE** | BEAM diagonality → P1-023 KILLED |
| P1-127 | **DONE** | one `errors-gotchas` question = 4.6% of RANDOM → task-clustered SEs on **every** contrast |
| P1-128 | **DONE** | official scorer bug → all leakage rates are lower bounds, pinned as an expected-failure control |
| P1-129 | **KILLED** | semantic-type κ = 0.000; axis dropped, redesign held as P1-H07 |
| P1-130 | **DONE** | structured contradiction 0.667 is a scope-collision artifact → **never quote as a hallucination rate** |
| P1-131 | **DONE** | V2 pairs are stratified by question type, not distance → separate cosine post-pass |
| P1-132 | **DEFERRED** | position effect 8/12, provisional at n=12; expansion owned by P1-I03 |
| P1-133 | **DONE** | "endpoint is nondeterministic" **RETRACTED** — it was a position effect |
| P1-134 | **DONE** | reward vs text disagreement differ 8× → label which floor is meant |
| P1-135 | **DONE** | 3,400-token embedding cap fails 10/10 on real text → 2,000 adopted |
| P1-136 | **DONE** | 29 of 1,889 units fit whole → attenuation stated in Limitations |
| P1-137 | **DONE** | page-budget premise was wrong; the instrument (page count) was flat where it mattered |
| P1-138 | **DONE** | "variance shares all 0.0000" **RETRACTED**; the reporter now prints UNMEASURED and a test forbids a number from a failed fit |
| P1-139 | **DONE** | 0×220 balanced sub-design → the task axis was widened (8 → 19.3 tasks/memory). **The fix worked and the conclusion still did not follow** — see P1-075 |
| P1-140 | **DONE** | the official prompt is not the lever; reportable as prompt sensitivity |
| P1-141 | **DONE** (verdict retracted) | "the floor is reader capability" rested on a **non-discriminative** leakage flag (ratio 0.995). The needle probe (22/22) settled it: the reader is **not** the constraint |
| P1-142 | **DONE** | exit code 0 is not success → every analysis stage asserts its own artifact |
| P1-143 | **DONE** | `AT_UPPER_BOUNDARY` flag added; a tight CI on a clipped ratio is an artifact of the clip |

### 4.10 Phase 2 IDs

| ID | Status | Successor |
|---|---|---|
| P2-01 representation scale-up | **DONE** | → P1-C12 |
| P2-02 HF v0.1 + schema audit | **DONE** | → P1-C04 for v0.2 |
| P2-03 pipeline figure + figure plan | **DONE** | → P1-C02 |
| P2-04 freeze the four-axis story | **DONE** | — |
| P2-05 README + handoff | **DONE** | redone as P1-C14 |
| P2-06 BEAM replacement | **DONE** | conditional: SWE-bench selected but not cleared; clearing it is P1-C05 → C07 |
| P2-07 frontier | **DONE** | → P1-C03, shipped as `fig:frontier` |
| P2-08 bearing-breadth figure | **DONE** | Figure 2(a) |
| P2-09 similarity figure | **DONE** | Figure 3 |
| P2-10 abstract v5 | **DONE** | → P1-C01 |
| P2-11 SciCode | **DONE** | → P1-C08/C09/C10, all DONE |
| P2-12 HF v0.2 | **DONE** | → P1-C04, tag `v0.2-repr-derived` verified by downloading it. v0.3/v0.4 are **P1-C21** |
| P2-13 cross-benchmark synthesis | **DONE** | → P1-C11, DONE. All three benchmark rows in `tab:crossbench` are real data |
| P2-14 final figure selection + page management | **DONE** (selection) | → P1-C13. Page **management** is **P1-C20**, which is blocked on the author by design |
| P2-15 claim/evidence audit at freeze | **DONE** | → P1-C16, standing |

### 4.11 User-owned (the Master Agent does not spend cycles here)

| ID | Task | Status |
|---|---|---|
| U-01 | Author list | **DEFERRED** (user-owned) | off the scientific critical path; not a blocker and not reported as one |
| U-02 | Reciprocal reviewer designation (1 Oct) + acceptance (8 Oct) | **DEFERRED** (user-owned) | deadline-bearing but user-owned |
| U-03 | OpenReview profiles / account logistics | **DEFERRED** (user-owned) | — |
| U-04 | Submission administration | **DEFERRED** (user-owned) | — |
| U-05 | *Optional:* logged-in read of OpenReview `n3GMbobXnc` | **DEFERRED** |

### 4.12 Legacy deferrals

| ID | Task | Status | Successor |
|---|---|---|---|
| D-01 | Jev baseline | **DEFERRED** | P1-H01 |
| D-02 | Large LLM-manager comparison | **DEFERRED** | P1-H03 |
| D-03 | Learned retriever / gate | **DEFERRED** | P1-H02 |
| D-04 | Scientific OOD beyond SciCode | **DEFERRED** | P1-H06 |
| D-05 | Model scaling ladder | **DEFERRED** | P1-H04 |
| D-06 | Production vector DB | **DEFERRED** | P1-H05 |

---

## 5. State counts

**Every one of the 188 distinct task IDs on this page carries exactly one bold terminal
state.** Counted mechanically, not by hand — re-derive with:

```python
import re, collections
t = open("docs/MASTER_TODO.md").read()
body = t[t.index("## 1. Level 1"):t.index("## 5. State counts")]
STATES = ["DONE","RUNNING","BLOCKED","TODO","DEFERRED","KILLED"]
ID = re.compile(r"\b(P1-\d{3}[a-z]?|P1-C\d{2}|P1-I\d{2}|P1-H\d{2}|P2-\d{2}|U-\d{2}|D-\d{2})\b")
seen = {}
for ln in body.split("\n"):
    s = ln.strip()
    if not s.startswith("|"): continue
    cells = [c.strip() for c in s.strip("|").split("|")]
    if not ID.findall(cells[0]): continue
    m = re.search(r"P1-(\d{3})…(\d{3})", cells[0])
    ids = ([f"P1-{i:03d}" for i in range(int(m.group(1)), int(m.group(2))+1)]
           if m else [ID.findall(cells[0])[0]])
    bold = [x for x in STATES if f"**{x}**" in " | ".join(cells[1:])]
    assert len(bold) == 1, (ids, bold)          # every row states exactly one
    for i in ids: seen.setdefault(i, bold[0])
print(len(seen), collections.Counter(seen.values()))
```

| state | count |
|---|---:|
| **DONE** | **134** |
| **DEFERRED** | **38** |
| **KILLED** | **16** |
| **TODO** | **7** |
| **RUNNING** | **2** |
| **BLOCKED** | **1** |
| **total distinct IDs** | **198** |

**Re-derived mechanically on 2026-10-01 by SA-ARCHIVE**, by running the snippet above.
Every one of the 198 rows carries exactly one bold state (the snippet asserts it; 0 rows
fail). The previous counts — DONE 106 / RUNNING 16 / BLOCKED 10 / TODO 21 / DEFERRED 22 /
KILLED 13 over 188 IDs — are **superseded**, not deleted: 10 IDs were added (C19–C22,
H11–H16) and the terminalization pass closed the rest.

**Counting rule.** A legacy ID whose work was taken over by a Phase-3 item is counted
**separately, under its own state**, with the successor named in its row. That is
deliberate: collapsing them would make a legacy ID stop being mentioned, which this page
forbids. So `P1-095` (TODO) and its successor `P1-C17` (TODO) are two rows and two counts.

### The entire open set — 10 IDs, and what each is waiting on

| ID | state | owner | waiting on |
|---|---|---|---|
| **P1-C17** | **TODO** | SA-PAGE | 🔴 the one genuinely open submission-critical item: final sync + compile + anonymity + citations |
| **P1-C19** | **RUNNING** | SA-SWE-FINAL | 41 runnable django cells remain under the frozen universe |
| **P1-C20** | **BLOCKED** | **the author** | removing content is not an agent's decision (`PAGE_BUDGET_DECISION.md`) |
| **P1-C21** | **RUNNING** | SA-HF | HF v0.3 staging rebuild in flight; v0.4 after it |
| **P1-C22** | **TODO** | SA-PAGE | three `main.tex` ↔ artifact inconsistencies, all retracted-number-still-circulating |
| **P1-I11** | **TODO** | SA-HF | 🔴 the representation scale-up slices are **still untracked** |
| **P1-I13** | **TODO** | SA-PAGE | the efficiency ratios; folded into C22 |
| P1-095 | TODO | — | duplicate of C17, kept per the counting rule |
| P1-100 | TODO | — | folds into C17; its concrete sub-item is I11 |
| P1-106 | TODO | — | folds into C16 (green) and C17 |

**Three of those ten are duplicate legacy IDs and one is a user decision**, so the real
agent-actionable set is **six**: C17, C19, C21, C22, I11, I13. 🔴 **I11 is the only one
that risks losing evidence** — Contribution B's row files exist on one laptop.

## 6. Killed this project, with the measured reason

| item | verdict |
|---|---|
| **BEAM as a benchmark** | ❌ **92.6% of cited turns are cited by exactly one question** — cannot supply the multi-task-per-memory axis. Secondary: CC BY-SA 4.0 ShareAlike |
| **DS-1000 as the replacement** | ❌ CC BY-SA 4.0 — the same ShareAlike trap |
| **SWE-Gym as the replacement** | ⏸ held in reserve — MIT and far larger (1,868 multi-recipient donors), but it is agent *training* data, so contamination argues against it as primary |
| **τ-bench** | ⚠️ **UNRESOLVED, not absent** — HF API 401 on this channel. Do not record it as rejected |
| **Semantic-type axis** | ❌ κ = 0.000; the native pass labelled everything `episodic` |
| **Variance decomposition as a headline** | ❌ unidentifiable; `F_exec = 0` leaves no residual scale. **No share may be quoted** |
| **Sign-flip rate as the paper's identity** | ❌ **demoted, not deleted.** 0/35 in bearing cells and the excess over the additive null is negative in every stratum. It survives as *analysis*: unrelated pairings manufacture apparent reversals (17/60 in RANDOM) |
| **Storage / retrieval / selectivity efficiency** | ❌ no retrieval arm exists on any row; reinstating them means a new arm (P1-I01) |
| **Targeted replication queue** | ❌ 0 of 1,157 cells have replicates that disagree. A deterministic reader makes replication uninformative |
| **Missing-cell recovery** | ❌ 0 errors, 0 missing cells across 9,036 calls |
| **Aurora as the execution path** | ❌ allocated but gateway-bound; the laptop path carried every run |

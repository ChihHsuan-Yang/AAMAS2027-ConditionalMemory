# P1 Master TODO — authoritative

---

## ⏩ PHASE 3 (opened 2026-09-30) — finish the paper, autonomous execution

**Contract change:** the Master Agent no longer pauses at milestones for authorization.
Execution continues until the active list reaches a terminal state. Author list, reciprocal
reviewer, OpenReview logistics and submission administration are **user-owned and off the
scientific critical path** — they are not blockers and are not reported as such.

Overleaf stays in standard double-blind form: `Anonymous Author(s)`, no affiliations, no
acknowledgements, no identifying paths.

### Level 1 — submission-critical

| ID | Task | Owner | Status |
|---|---|---|---|
| P1-C01 | Abstract / story reframe (drop sign-flip + decomposition emphasis) | SA-WRITE | **RUNNING** |
| P1-C02 | Overleaf figure audit | SA-FIG | **DONE** |
| P1-C03 | **Utility–Efficiency Frontier** | SA-FIG2 | **RUNNING** |
| P1-C04 | HF v0.2 representation release | SA-HF2 | **RUNNING** |
| P1-C05 | SWE-bench harness parity fix | SA-SWE | **RUNNING** |
| P1-C06 | SWE-bench valid pilot | SA-SWE | BLOCKED on C05 |
| P1-C07 | SWE-bench main run *if* pilot passes | SA-SWE | BLOCKED on C06 |
| P1-C08 | SciCode adapter | SA-SCI | **RUNNING** |
| P1-C09 | SciCode pilot | SA-SCI | BLOCKED on C08 |
| P1-C10 | SciCode procedural-memory evaluation | SA-SCI | BLOCKED on C09 |
| P1-C11 | Cross-benchmark synthesis | Master | BLOCKED on C07/C10 |
| P1-C12 | Final representation comparison | Master | **DONE** — `docs/REPRESENTATION_RESULT.md` |
| P1-C13 | Main figures/tables | SA-FIG2 | RUNNING (3 figures + 2 tables in) |
| P1-C14 | GitHub handoff documentation | SA-ARCHIVE | **RUNNING** |
| P1-C15 | HF data card update | SA-HF2 | RUNNING |
| P1-C16 | Claim/evidence audit | Master | ongoing — `audit_claims.py`, 38 claims, proven able to fail |
| P1-C17 | Final manuscript sync | Master | ongoing |

### Level 2 — important if feasible

P1-I01 top-k retrieval baseline · P1-I02 keep-all baseline · P1-I03 position-effect
expansion (currently n=12) · P1-I04 cross-benchmark representation ranking ·
P1-I05 representation-induced harmfulness · P1-I06 domain utility/cost comparison ·
P1-I07 extra retrieval-budget points for the frontier · P1-I08 benchmark-native memory
baseline · P1-I09 dataset example notebook · P1-I10 public reproduction script.
**All TODO.** None blocks submission.

### Level 3 — HOLD / post-submission

P1-H01 Jev decision baseline · P1-H02 learned conditional memory gate · P1-H03 LLM memory
manager comparison · P1-H04 cross-model replication · P1-H05 vector DB / production store ·
P1-H06 more benchmarks · P1-H07 semantic-type taxonomy redesign · P1-H08 harmful-memory
prevalence study · P1-H09 full P3 receiver integration · P1-H10 training a retention policy.
**All HOLD.** Recorded so they are not lost.

### Demoted this phase, with evidence

| item | verdict |
|---|---|
| **Variance decomposition** | **DEMOTED from headline** — unidentifiable: `F_exec = 0` on a deterministic reader leaves no residual scale. Methodology to supplement; **no share quoted**. No further compute |
| **Sign-flip story** | **DEMOTED from paper identity** — 0/35 in bearing cells, and the excess over the additive null is *negative* in every stratum. Retained as analysis: unrelated pairings manufacture apparent reversals (17/60 in RANDOM) |

---

---

## ⏩ PHASE 2 (opened 2026-09-30) — complete the four axes

Story frozen as **Memory × Task × Representation × Cost**. The task axis is measured; the
representation and cost axes are not. That imbalance is this phase's target.

| ID | Pri | Task | Owner | Status | Unblocks |
|---|---|---|---|---|---|
| **P2-01** | **P0** | **Summary + Structured at scale on BEARING/control** | SA-R | **RUNNING** | Contribution B **and** the frontier figure |
| **P2-02** | **P0** | **HF v0.1 + schema audit vs the required field list** | SA-HF | **RUNNING** | the dataset contribution |
| **P2-03** | **P0** | **Pipeline figure + ranked figure plan** | SA-FIG | **RUNNING** | the paper has 0 figures at the page limit |
| **P2-04** | **P0** | Freeze the four-axis story | Master | **DONE** | `docs/PROJECT_GOAL.md` |
| **P2-05** | **P0** | README current-state + `HANDOFF_CURRENT.md` | Master | **DONE** | `a80ba7a` |
| P2-06 | P1 | BEAM replacement: bounded selection, then implement | SA-N | **RUNNING** | benchmark diversity |
| P2-07 | P1 | Utility–Efficiency Frontier | SA-EFF | BLOCKED on P2-01 | only 1 point exists today |
| P2-08 | P1 | Bearing-breadth figure | SA-FIG | TODO — **data exists now** | — |
| P2-09 | P1 | Similarity-vs-utility figure | SA-FIG | TODO — **data exists now** | — |
| P2-10 | P1 | **Abstract v5** — drop the obsolete sign-flip framing | Master | TODO | — |
| P2-11 | P2 | SciCode: scoped → built | SA-S | TODO | procedural memory; N≈8–12, a case study |
| P2-12 | P2 | HF v0.2 (add Summary/Structured) | SA-HF | BLOCKED on P2-01 | — |
| P2-13 | P3 | Cross-benchmark synthesis | — | BLOCKED | — |
| P2-14 | P3 | Final figure selection + page management | Master | BLOCKED | — |
| P2-15 | P3 | Claim/evidence audit at freeze | Master | TODO | `audit_claims.py` is at 38 claims |

### Killed / deferred this phase, with measured reasons

| item | verdict |
|---|---|
| **BEAM as a core benchmark** | ❌ **KILLED** — 92.6% of cited turns cited by exactly one question, so it cannot supply the multi-task axis. Also CC BY-SA 4.0 |
| **Semantic-type axis** | ❌ **KILLED** — κ = 0.000; the native pass labelled everything `episodic` |
| **Variance decomposition as a headline** | ❌ **KILLED** — unidentifiable; `F_exec = 0` leaves no residual scale. **No share may be quoted** |
| **Jev** | ⏸ DEFERRED — explicitly not required for the core paper |

---

**AAMAS 2027 main track. Abstract 1 Oct AoE · Paper 8 Oct AoE.**
Statuses: `TODO` `RUNNING` `BLOCKED` `REVIEW` `DONE` `DEFERRED` `KILLED`.
Tasks are never silently removed. Last updated 2026-09-29.

Columns: ID · Pri · Task · Owner · Status · Dep · Evidence · Next action · Sub? · Done-when
(**Sub?** = required for the AAMAS submission, or deferrable.)

---

## USER-OWNED (Master Agent does not spend cycles here)

| ID | Task | Status |
|---|---|---|
| U-01 | Author list | USER |
| U-02 | Reciprocal reviewer designation (1 Oct) + acceptance (8 Oct) | USER |
| U-03 | OpenReview profiles/account logistics | USER |
| U-04 | Submission administration | USER |
| U-05 | *Optional, 2 min:* logged-in read of OpenReview `n3GMbobXnc` — does EvoMemEval's paper **body** report a cross-task variance statistic? | USER |

---

## Scientific / design

| ID | Pri | Task | Owner | Status | Dep | Evidence | Next action | Sub? | Done-when |
|---|---|---|---|---|---|---|---|---|---|
| P1-001 | P0 | Freeze storyline in repo + Overleaf | Master | DONE | — | `docs/PROJECT_GOAL.md` | — | yes | frozen doc + abstract agree |
| P1-002 | P0 | Memory acquisition protocol (writer never sees future task) | Master+B | **DONE** | 001 | `docs/MEMORY_PROTOCOL.md` | B implements | yes | invariant + enforcement stated |
| P1-003 | P0 | Define Raw representation | B | **DONE** — deterministic, 0 calls | 002 | — | deterministic span rule | yes | spec + code |
| P1-004 | P0 | Define Summary representation | B | **DONE** — median 362 tok, cr 0.063 | 002 | — | fixed writer + prompt vN | yes | spec + code |
| P1-005 | P0 | Define Structured representation | B | **DONE** — median 246 tok, cr 0.037, 0/8 malformed | 002 | — | schema incl. procedural variant | yes | spec + code |
| P1-006 | P1 | Memory semantic-type labels | B | ⚠️ **NOT SAFE AS AN AXIS** — κ=0.000, native pass called all 8 `episodic` | 002 | — | keep distinct from representation | yes | labelling rule + agreement check |
| P1-007 | P0 | WITH/WITHOUT intervention definition | Master | **DONE** | 002 | `docs/MEMORY_PROTOCOL.md` §4 | — | yes | controlled filler required in both arms |
| P1-008 | P0 | Robust useful/harmful definition vs noise floor | Master | **DONE** | — | `docs/ANALYSIS_PREREGISTRATION.md` §4-5, committed **before any data** | — | yes | thresholds fixed pre-hoc |
| P1-009 | P0 | Efficiency metric definitions | D | TODO | 001 | — | 7 families, §17 | yes | each metric has a field |
| P1-010 | P1 | Retrieval baselines: None / Keep-All / Top-k / Oracle | D | TODO | 001 | — | — | yes | 4 arms specified |
| P1-011 | P1 | Figure/table targets + schema support check | D | TODO | 040 | — | verify schema can produce Fig 2 | yes | each fig maps to fields |

## Benchmark / data — Sub-agent A

| ID | Pri | Task | Owner | Status | Dep | Evidence | Next action | Sub? | Done-when |
|---|---|---|---|---|---|---|---|---|---|
| P1-020 | P0 | LongMemEval-V2 adapter + official scorers | A | **DONE** | — | `/tmp/lmev2` checksum-verified | extract scorers from `harness.py` | yes | unit tests pass |
| P1-021 | P0 | V2 memory unit + memory×task pairing | A | **DONE** — page visit, median 7,261 tok; **1,889 mem × 8 tasks** | 020 | 164k tok/trajectory → must subdivide | measured token distribution | yes | unit fixed + seeded pairing |
| P1-022 | P0 | Leakage audit + detector | A | **DONE** — 17/17 controls; rates are LOWER BOUNDS | 020 | — | must prove detector can fail | yes | rate reported, cells flagged not dropped |
| P1-023 | P1 | BEAM adapter | A | **DEFERRED** — 92.6% of cited turns cited by exactly 1 question; cannot supply the multi-task axis | — | — | obtainability first | yes | adapter or documented exception |
| P1-024 | P1 | BEAM task/domain mapping | A | BLOCKED | 023 | — | — | yes | — |
| P1-025 | P1 | SciCode adapter | A | **SCOPED DOWN** — ~8–12 cross-problem pairs; case study, not a main table | — | — | obtainability first | yes | adapter or documented exception |
| P1-026 | P1 | SciCode source→future transfer mapping | A | BLOCKED | 025 | — | — | yes | — |
| P1-027 | P0 | License/provenance audit | A | **DONE** — BEAM CC BY-SA 4.0 ShareAlike forces a separate release | — | — | `docs/BENCHMARK_LICENSES.md` | yes | redistribution rules explicit |

## Infrastructure — Sub-agent C

| ID | Pri | Task | Owner | Status | Dep | Evidence | Next action | Sub? | Done-when |
|---|---|---|---|---|---|---|---|---|---|
| P1-030 | P0 | Runtime ALCF discovery | C | DONE | — | 4 clusters incl. undocumented `tara`; `/v1/models` 404s on Sophia | — | yes | live list recorded |
| P1-031 | P0 | Minerva primary-model feasibility | C | **DONE** | 030 | `gpt-oss-120b` **503 persistent** on Minerva; inkling/nemotron serve | — | yes | evidence recorded |
| P1-032 | P0 | **Freeze primary generation model+cluster** | Master | **DONE** | 031 | `docs/CLUSTER_DECISION.md` — gpt-oss-120b on **Metis** | — | yes | pinned |
| P1-033 | P0 | Freeze embedding model | Master | **DONE** | — | `SFR-Embedding-Mistral` dim 4096 — ⚠️ **2,000-Qwen-token budget**, 98.5% of units truncated | — | yes | pinned |
| P1-034 | P0 | Concurrency benchmark | C | **DONE** — **16 workers**, 0 failures /316 reqs; 429s at 24 | 032 | — | `docs/ENDPOINT_THROUGHPUT.md` | yes | chosen value justified by table |
| P1-035 | P1 | Aurora orchestration runner | C | **DONE (not used)** — allocated, but gateway-bound; laptop path | 034 | — | check allocation first | no* | resumable job or documented fallback |
| P1-036 | P0 | Response cache | C | **DONE** — isolation verified behaviourally by Master | — | — | test: cross-cluster keys differ | yes | tests pass |
| P1-037 | P0 | Retry/resume/checkpoint | C | **DONE** — 12 cells re-ran with 0 calls | 036 | — | — | yes | restart re-pays nothing |
| P1-038 | P0 | Cost/token/latency logger | C | **DONE** | 036 | — | — | yes | every call logged |

\* Aurora is an execution convenience; a gateway-driven run is an acceptable fallback at our scale.

## Data / release — Sub-agent E

| ID | Pri | Task | Owner | Status | Dep | Evidence | Next action | Sub? | Done-when |
|---|---|---|---|---|---|---|---|---|---|
| P1-040 | P0 | Canonical dataset schema (+P3 reserved fields) | E | **DONE** | 001 | `src/p1mem/schema.py` — **77 fields**, all 59 required present (Master-verified) | — | yes | schema + validator |
| P1-041 | P0 | HF staging dir (clean, never the repo root) | E | **BLOCKED** | **P1-027** | exporter hard-refuses without `BENCHMARK_LICENSES.md` | A to deliver licenses | yes | staging isolated |
| P1-042 | P1 | HF data card (20 sections) | E | TODO | 040 | — | — | yes | card current |
| P1-043 | P0 | Derived-data writer | E | **DONE** | 040 | committed with export gates 8/8 | — | yes | emits conforming rows |
| P1-044 | P0 | Dataset validation script | E | **DONE** | 040 | 45 tests, 15 deliberate corruptions all caught; **2 real defects found by failing tests** | — | yes | rejects malformed |
| P1-045 | P1 | HF upload/version process | E | TODO | 041 | `AgentsSci/AAMAS2027-ConditionalMemory` | — | yes | snapshot uploaded |
| P1-046 | P0 | P3 receiver-compatible reserved fields | E | **DONE** | 040 | 4 reserved fields, validator enforces null | — | yes | present + null |

## Experiments

| ID | Pri | Task | Owner | Status | Dep | Evidence | Next action | Sub? | Done-when |
|---|---|---|---|---|---|---|---|---|---|
| P1-050 | P0 | Extraction pilot | B | **DONE** — 8 segments, 24 calls | 003-005, 032 | — | — | yes | 3 reps for N episodes |
| P1-051 | P0 | **Noise/reliability pilot** | G | **RUNNING** | 032, 036 | free no-memory arm | — | yes | floor measured |
| P1-052 | P0 | LongMemEval-V2 pilot | G | **RUNNING** | 020, 050, 051 | — | — | yes | pipeline end-to-end |
| P1-052b | P0 | **Official-prompt arm (the decisive re-run)** | H | **DONE — REFUTED the hypothesis** | 052 | `docs/OFFICIAL_PROMPT_ARM.md`; `results/deltau_official/`; ledger rows 58-67; TODO P1-138..143 | do NOT re-run another prompt wording; probe the READER | yes | ✅ 1,920 calls, 0 errors; both-arms-fail rose 78.5% → **83.75%** |
| P1-053 | P0 | LongMemEval-V2 main run | D | BLOCKED | 052 | — | — | yes | main table cells filled |
| P1-054 | P1 | BEAM pilot | D | BLOCKED | 023 | — | — | yes | — |
| P1-055 | P1 | BEAM main run | D | BLOCKED | 054 | — | — | no | — |
| P1-056 | P1 | SciCode pilot | D | BLOCKED | 025 | — | — | yes | — |
| P1-057 | P1 | SciCode main run | D | BLOCKED | 056 | — | — | no | — |
| P1-058 | P0 | Targeted replication queue (adaptive) | D | BLOCKED | 051 | — | prioritize near-zero + sign flips | yes | flips replicated |
| P1-059 | P1 | Missing-cell recovery (same cluster only) | D | BLOCKED | 053 | — | — | yes | no cross-cluster merge |

## Analysis — Sub-agent D

| ID | Pri | Task | Owner | Status | Sub? |
|---|---|---|---|---|---|
| P1-060 | P0 | Continuous ΔU analysis | D | BLOCKED | yes |
| P1-061 | P0 | Robust useful/harmful labels | D | BLOCKED | yes |
| P1-062 | P1 | Breadth vs specialization | D | BLOCKED | yes |
| P1-063 | P0 | Sign-flip analysis (must clear floor) | D | BLOCKED | yes |
| P1-064 | P1 | NEAR/MID/FAR | D | BLOCKED | yes |
| P1-065 | P1 | Similarity-vs-utility | D | BLOCKED | yes |
| P1-066 | P0 | Representation comparison (Contribution B) | D | BLOCKED | yes |
| P1-067..073 | P0 | Efficiency: storage/retrieval/exposure/latency/API/selectivity/extraction | D | BLOCKED | yes |
| P1-074 | P0 | **Utility–Efficiency Frontier (Fig 2)** | D | BLOCKED | yes |
| P1-075 | P1 | Variance decomposition (memory/task/interaction) — ~200 new lines, none exists | D | BLOCKED | yes |

## Manuscript — Sub-agent F

| ID | Pri | Task | Owner | Status | Sub? |
|---|---|---|---|---|---|
| P1-080 | P0 | Abstract → frozen story (v3) | Master | **DONE** — 271 words, scan clean, in Overleaf | yes |
| P1-081..087 | P1 | Intro · Related Work · Method · Representations · Benchmarks · Utility · Efficiency | F | **DONE** — 6 pp, 0 undefined citations, CCS added, bibliography rebuilt + spot-checked vs primary sources | yes |
| P1-088..090 | P0 | Results · Analysis · Limitations | F | BLOCKED | yes |
| P1-091..092 | P0 | Figures · Tables | F | BLOCKED | yes |
| P1-093 | P1 | Reproducibility statement | F | **DONE** | yes |
| P1-094 | P0 | Claim/evidence audit | Master | BLOCKED | yes |
| P1-095 | P0 | Final compile + anonymity + citation check | Master | BLOCKED | yes |
| P1-096 | P0 | **AI-assistance disclosure** (prompt + tool + version) — AAMAS requires it | Master | TODO | yes |

## Release

| ID | Pri | Task | Owner | Status | Sub? |
|---|---|---|---|---|---|
| P1-100..106 | P1 | GitHub cleanup · README repro · HF snapshot · data card · license verify · results ledger · final consistency audit | Master+E | TODO | yes |

---

## Newly added from findings (§32 requires recording the trigger)

| ID | Trigger | Why it matters | Pri | Sub? |
|---|---|---|---|---|
| P1-110 | V2 ships **no evidence labels** (verified over all 451 records) | We cannot know which trajectory holds the answer, so "ablate the evidence" is undefined. The memory unit must be defined without evidence labels, and utility measured purely counterfactually | P0 | yes |
| P1-111 | Oracle ctx is **100% evidence** | Ablating there removes the whole context — a no-context arm, not a memory ablation. Every cell needs controlled filler | P0 | yes |
| P1-112 | EvoMemEval's artifact already contains 46 multi-task memories, 17 flipping | Related Work must concede this; our claim is signed+replicated+decomposed, not "we found it first" | P0 | yes |
| P1-113 | EvoMemEval pre-balance metadata: **22.0% natural harm rate** (n=537) | Directly answers the TraceRetain "no pollution → all arms in one CI" hazard. Cite as external evidence | P1 | yes |
| P1-114 | `analyze_conditional_value.py` has **zero** variance/interaction code and **rejects `replicate_id`** | The headline analysis must be written (~200 lines); start from `analyze_reliability.py`, which does key on replicate_id | P0 | yes |
| P1-115 | `get_embedding` broken 3 ways; `vectorstore.py` has no retrieval or persistence | Both must be written, not reused | P0 | yes |
| P1-116 | Inherited "679 free natural cells" **refuted** (0 overlap, positive-controlled) | The matrix is **constructed**, not harvested. The paper must say so | P0 | yes |

| P1-138 | 🔴 "variance shares all 0.0000" was `dec.shares.get(c, 0.0)` over an **empty** dict — the fit never converged and the moments fallback refused (*"balanced sub-design is 0x220"*) | The paper's headline quantity was reported as a hard zero when it was UNMEASURED. Retracted in ledger row 54a. **Make the decomposition reporter print UNMEASURED rather than defaulting**, and add a test that a failed fit cannot print a number | P0 | yes |
| P1-139 | The pairing gives **0×220** balanced sub-design: tasks/memory 8/8/8, memories/task 1/2/36, only 127 of 220 tasks shared by ≥2 memories | No variance decomposition is estimable at ANY number of memories under this pairing. Re-pair so memories **share** tasks — POWER_ANALYSIS §3's "widen the task axis", now for a second reason | P0 | yes |
| P1-140 | The official prompt made accuracy **worse** (paired McNemar p=1.12e-09) by converting **128 correct guesses into abstentions**; `harness.py:1055` scores an abstention 0, same as a wrong answer | The prompt is NOT the lever and must not be re-run in another wording. Reportable as a prompt-sensitivity result in its own right | P0 | yes |
| P1-142 | 🔴 A stage crashed with `ZeroDivisionError` **while the script exited 0** — the wrapper reported success and the artifact was simply absent | "Exit code 0 is not success" now has a concrete instance in THIS pipeline. **Every analysis stage must assert its own artifact exists before the script returns 0** | P0 | yes |
| P1-143 | 🔴 The REML fit is **not identified**: task and interaction shares exactly equal to 16 s.f., both ratios pinned at the `exp(12)` clip ceiling, yet `converged=True` with a tight CI | The module guarded only the LOWER variance boundary. `AT_UPPER_BOUNDARY` added. **Any future decomposition must be read with this flag checked** — a tight CI on a clipped ratio is an artifact of the clip | P0 | yes |
| P1-141 | On cells whose memory text **contains the gold answer**, WITH-arm accuracy is only 0.2288 / 0.1429 and 72–79% still fail both arms | The floor is **reader capability**, not pairing or prompt. Probe max_tokens / reasoning_effort / smaller K / stronger reader — each on the oracle-bearing subgroup first, which is the cheapest non-outcome-selected capability test | P0 | yes |

## Added this hour (trigger recorded)

| ID | Trigger | Why it matters | Pri | Sub? |
|---|---|---|---|---|
| P1-117 | Minerva advertises `gpt-oss-120b` but returns **503 persistently**; Sophia advertises an embedding model that **502s** | Two advertised-but-dead cases in one day. **A capability listing is not a liveness signal** — every model dependency needs a real POST before use, with a negative control | P0 | yes |
| P1-118 | Reasoning tokens share the `max_tokens` budget; a truncated empty completion was scored as a wrong answer | Would push ΔU negative and **manufacture harmful memories** — fabricating the phenomenon we measure. Hard error in the client, never scored | P0 | yes |
| P1-119 | V2 has **8 distinct eval specs, not 6** — two `norm_phrase_set_match` variants differ only in `separators` | Dispatching on function name silently applies the wrong scorer. Adapter must key on the FULL spec string | P0 | yes |
| P1-120 | HF `auth-check?accessLevel=write` returns **200 for a repo we cannot write**, and 200 unauthenticated | A readiness probe that always says yes is not a test. Only an empty-body commit POST discriminates (400 vs 403); requires a negative control | P0 | yes |
| P1-121 | System `python3` is 3.9; the vendored scorer's `str \| None` is a TypeError at import, aborting pytest collection | **A healthy suite looks broken.** Pin 3.10+; never edit the vendored scorer to satisfy 3.9 — that would silently change our measurements | P0 | yes |
| P1-122 | `memory_id` collision: A emits a positional locator, E a content hash | Every row would be rejected at validation. Ruling: A renames to `memory_unit_locator`; a positional id is unstable under re-segmentation | P0 | yes |
| P1-123 | `semantic_distance_band` looks per-row but is defined as a per-benchmark tercile | A row-by-row writer produces bands that depend on **write order**. Needs a post-pass after all similarities exist | P0 | yes |
| P1-124 | `utility_label`/`robustness_confidence` depend on the unmeasured floor `F` | They must emit `undetermined` until the noise floor exists, and be **recomputed** afterwards. Filling them now would fabricate | P0 | yes |

## Added (trigger recorded) — third batch

| ID | Trigger | Why it matters | Pri | Sub? |
|---|---|---|---|---|
| P1-132 | **Position effect**: 8/12 cells changed their answer when ONLY the memory's position moved | Any with/without study that does not control position measures position + presence. Position now fixed across replicates, varied across cells, recorded per row. **Promote to its own measurement at scale** | P0 | yes |
| P1-133 | My "endpoint is nondeterministic" claim **RETRACTED** — replicates were not byte-identical (position seeded by `replicate_id`) | Endpoint IS deterministic (6/6 identical, 24 calls, target regime). F_exec ≈ 0 is the expected correct result, not a failure | P0 | yes |
| P1-134 | Reward disagreement (1/23) vs text disagreement (8/23) differ **8×** | F_exec needs reward, F_judge needs text. Label which is meant everywhere | P0 | yes |
| P1-135 | Embedding cap of 3,400 tok **fails 10/10 on real text**; my probe prose was 2× sparser than the data | No single numeric cap exists — we count Qwen, the server counts Mistral. Adopted 2,000 + halving retry, recorded per row | P0 | yes |
| P1-136 | At 2,000 tok only **29 of 1,889 units (1.5%)** fit whole | 98.5% of similarity values come from a truncated prefix. Attenuates similarity-utility toward zero — **cuts against our own claim**, must be stated | P0 | yes |
| P1-137 | Manuscript at 6 pages with Results empty | ~2 pages of headroom. F's proposed cuts to writer-blindness barriers and infra justifications are **NOT needed** — they are reviewer defences | P1 | yes |

## Added (trigger recorded) — second batch

| ID | Trigger | Why it matters | Pri | Sub? |
|---|---|---|---|---|
| P1-125 | REML recovery error **0.0627 at 30 memories** (worst seed 0.1175) | 30 memories gives an 11-point error bar on the headline share. **60 minimum, 120×8 target**; 120×16 beats 240×8, so widen the TASK axis | P0 | yes |
| P1-126 | BEAM: **92.6% of cited turns cited by exactly one question** | Cannot supply multi-task-per-memory. Demoted to secondary; documented scientific exception to the 3-benchmark target | P0 | yes |
| P1-127 | Exactly **one** deterministically-scorable `errors-gotchas` question exists, = **12.5% of web cells** | One question could drive an apparent effect. **Cluster SEs by `task_id`** | P0 | yes |
| P1-128 | Official scorer bug: `normalize_phrase` strips punctuation without a space (`value='GPS`→`valuegps`) | **All leakage rates are LOWER BOUNDS.** Pinned as an expected-failure control | P0 | yes |
| P1-129 | `memory_semantic_type` agreement **3/8, κ=0.000** — native pass labelled everything `episodic` | Not safe as an analysis axis. Either widen the labelling run or drop the axis and say why | P1 | yes |
| P1-130 | Structured contradiction rate 0.667 is a **scope-collision artifact** (schema's per-segment `action` vs source's per-state `- Action:`); 0.000 excluding it | Must never be quoted as a hallucination rate | P1 | yes |
| P1-131 | V2 pairs are stratified by **question type**, not embedding distance | NEAR/MID/FAR needs a separate cosine-tercile post-pass. Two different strata; do not conflate | P0 | yes |

## Deferred

| ID | Task | Reason |
|---|---|---|
| D-01 | Jev baseline | §12: optional extension, never a blocker |
| D-02 | Large LLM-manager comparison | optional extension |
| D-03 | Learned retriever / gate | only if the main paper is complete |
| D-04 | Scientific OOD beyond SciCode | optional |
| D-05 | Model scaling ladder | optional |
| D-06 | Production vector DB | explicitly out of scope |

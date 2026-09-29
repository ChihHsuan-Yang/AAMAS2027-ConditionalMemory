# P1 Master TODO — authoritative

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
| P1-033 | P0 | Freeze embedding model | Master | DONE | — | `SFR-Embedding-Mistral` dim 4096, deterministic cos=1.0, batches | — | yes | pinned |
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
| P1-081..087 | P1 | Intro · Related Work · Method · Representations · Benchmarks · Utility · Efficiency | F | TODO | yes |
| P1-088..090 | P0 | Results · Analysis · Limitations | F | BLOCKED | yes |
| P1-091..092 | P0 | Figures · Tables | F | BLOCKED | yes |
| P1-093 | P1 | Reproducibility statement | F | TODO | yes |
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

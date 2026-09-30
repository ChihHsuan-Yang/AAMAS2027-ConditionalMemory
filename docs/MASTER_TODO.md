# P1 Master TODO — authoritative

**Terminalized 2026-09-30 by SA-ARCHIVE.** Every task on this page carries one of six
terminal states. **No task is ever silently removed**; anything dropped carries `KILLED`
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

**Counts (mechanically re-derived, see §5):** DONE 106 · RUNNING 16 · BLOCKED 10 ·
TODO 21 · DEFERRED 22 · KILLED 13 — **188 distinct IDs**.

---

## 1. Level 1 — submission-critical

| ID | Task | Owner | Status | Evidence / blocker |
|---|---|---|---|---|
| **P1-C01** | Abstract / story reframe — lead with conditional utility + sparsity, drop the sign-flip framing | SA-WRITE | **DONE** | abstract v5, 299 words, in the manuscript; sign-flip and decomposition framing removed |
| **P1-C02** | Overleaf figure audit — ranked plan, 3 in / 4 rejected / 1 blocked | SA-FIG | **DONE** | `docs/FIGURE_PLAN.md`; repo `eb4deb3` |
| **P1-C03** | **Utility–efficiency frontier figure** | SA-FIG2 | **RUNNING** | unblocked by the representation scale-up; inputs in `results/repr_scaleup/`. Was blocked because `memory_representation` was `{'raw'}` on all 2,599 screened rows |
| **P1-C04** | HF **v0.2** — add Summary/Structured rows | SA-HF2 | **DONE** | tag `v0.2-repr-derived`, **5,643 rows** (raw 4,519 / summary 570 / structured 554), schema v3, verified by downloading the tag |
| **P1-C05** | **SWE-bench harness parity fix** — make the prompt arm-symmetric so the memory's own diff cannot be mistaken for the editable region | SA-SWE | **DONE** | apply-gap **0.375 → 0.000**; cause was the reader imitating the memory's diff fence, not the editable region |
| **P1-C06** | SWE-bench valid pilot at 30–40 cells | SA-SWE | **DONE** | both-arms-fail **37.5%** [22.9, 54.8], below threshold; 0 apply-failures scored as rewards. **django-only** |
| **P1-C07** | SWE-bench main run *if* the pilot passes | SA-SWE | **BLOCKED** on C06 | **no SWE-bench number enters any table before this** |
| **P1-C08** | SciCode adapter | SA-SCI | **DONE** | adapter + 45 tests, mutation-checked 4/4 |
| **P1-C09** | SciCode pilot | SA-SCI | **DONE** | both-arms-fail 0.370–0.456 across three representations, all below threshold; errors symmetric across arms |
| **P1-C10** | SciCode procedural-memory evaluation (a **case study**, N ≈ 8–12, never a main table) | SA-SCI | **DONE** | all three representations run. **The point-estimate ordering differs across benchmarks**: LongMemEval's Raw-dominant ordering is **not reproduced** in the SciCode pilot (raw +0.0000 here). ⚠️ **Every SciCode CI crosses zero — this is NOT an established inversion** |
| **P1-C11** | Cross-benchmark synthesis | Master | **TODO** | **UNBLOCKED** — all three benchmarks are past their gate |
| **P1-C12** | Final representation comparison (Contribution B) | Master | **DONE** | `docs/REPRESENTATION_RESULT.md`; 9 audit checks re-derive both cost columns |
| **P1-C13** | Main figures and tables | SA-FIG2 | **RUNNING** | 3 figures + 2 tables in `main.tex` at `3c06d3a`; Figure 4 pending C03. ⚠️ only **~50–80 pt** of float slack remains |
| **P1-C14** | GitHub handoff documentation — result index, figure index, README hub, handoff, terminal TODO | SA-ARCHIVE | **DONE** | RESULT_INDEX, FIGURE_INDEX, README hub, HANDOFF_CURRENT |
| **P1-C15** | HF data card update for v0.2 | SA-HF2 | **RUNNING** | v0.1 card is live and byte-identical to `docs/hf_card/README.md` |
| **P1-C16** | Claim/evidence audit | Master | **RUNNING** (standing) | `scripts/audit_claims.py`, **58 checks**, proven able to fail. ⚠️ previously recorded as "38 claims" — stale |
| **P1-C17** | Final manuscript sync + compile + anonymity + citation check | Master | **TODO** | absorbs legacy P1-095 |
| **P1-C18** | **AI-assistance disclosure section** (prompt + tool + version) | Master | **TODO** | 🔴 **AAMAS requires it and `main.tex:1337` is an empty stub.** Added by SA-ARCHIVE because legacy P1-096 had no Phase-3 owner and would otherwise have stopped being mentioned |

### Level-1 items that will consume the remaining page budget

C03 (a figure), C13 (its placement) and C18 (required prose) all draw on the same
~50–80 pt. **Measure where the body ends, not the total page count** — page count is flat
here because references are uncapped, and reading it as slack is a registered defect.

---

## 2. Level 2 — important if feasible (none blocks submission)

| ID | Task | Status | Note |
|---|---|---|---|
| **P1-I01** | Top-k retrieval baseline | **TODO** | absorbs half of legacy P1-010. `retrieval_k` is `None` on every existing row, so this is a new arm |
| **P1-I02** | Keep-all / no-memory retrieval baselines | **TODO** | absorbs the other half of P1-010 |
| **P1-I03** | Position-effect expansion | **TODO** | currently **n = 12** and explicitly provisional (`docs/POSITION_EFFECT.md`). Absorbs legacy P1-132 |
| **P1-I04** | Cross-benchmark representation ranking | **BLOCKED** on C07/C10 | one benchmark cannot rank representations across domains |
| **P1-I05** | Representation-induced harmfulness | **TODO** | no representation shows robust harm; structured's point estimate is negative with a CI spanning zero |
| **P1-I06** | Domain utility/cost comparison | **TODO** | — |
| **P1-I07** | Extra retrieval-budget points for the frontier | **BLOCKED** on I01 | the frontier currently has one budget point per representation |
| **P1-I08** | Benchmark-native memory baseline | **TODO** | — |
| **P1-I09** | Dataset example notebook | **TODO** | `notebooks/` is empty |
| **P1-I10** | Public reproduction script | **TODO** | partially served by `audit_claims.py` + `results/ledgers/repro/MANIFEST.json` |
| **P1-I11** | **Track the representation scale-up artifacts** — force-add slim slices + a `MANIFEST.json` for `results/repr_scaleup/` | **TODO** | 🔴 **found by SA-ARCHIVE:** Contribution B's entire evidence base is untracked and exists on this laptop only. The ΔU arms got this treatment; the repr arm did not |
| **P1-I12** | **Resolve the paired-CI disagreement** — the manuscript prints an episode-clustered interval no artifact contains | **TODO** | `docs/RESULT_INDEX.md` §F1. Fix by emitting the bootstrap seed/draw count from `k3_analyze_screened.py`, or by quoting the artifact. **Extend `audit_claims.py` to cover both CIs** — it currently checks neither, which is why this survived |
| **P1-I13** | **Correct the efficiency ratios in `main.tex`** | **TODO** | `docs/RESULT_INDEX.md` §F3: the paper says `5.2×` (audited: **5.58×**) and "roughly 5×" for the charged reversal, which is true of Structured (4.85×) but wrong for Summary (**1.08×**) — the representation the sentence is about |

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
| P1-056 | SciCode pilot | **BLOCKED** | superseded — now owned by P1-C09 |
| P1-057 | SciCode main run | **BLOCKED** | superseded — now owned by P1-C10 |
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
| P1-074 | Utility–efficiency frontier | **RUNNING** | superseded — now owned by P1-C03 |
| P1-075 | Variance decomposition | **KILLED** | 🔴 **unidentifiable.** Cause is **`F_exec = 0`** — a deterministic reader leaves no residual scale — not the task-crossing defect that *was* fixed. Shares came back equal to 16 s.f. at the optimizer's clip while reporting `converged=True`. **No share may be quoted**; `audit_claims.py` fails if one appears; a figure is forbidden |

### 4.7 Manuscript

| ID | Task | Status | Note |
|---|---|---|---|
| P1-080 | Abstract v3 | **DONE** | superseded — P1-C01 landed v5 |
| P1-081…087 | Intro · Related Work · Method · Representations · Benchmarks · Utility · Efficiency | **DONE** | 0 undefined citations, CCS added |
| P1-088…090 | Results · Analysis · Limitations | **DONE** | all three written against verified sources |
| P1-091…092 | Figures · Tables | **RUNNING** | superseded — now owned by P1-C13 |
| P1-093 | Reproducibility statement | **DONE** | — |
| P1-094 | Claim/evidence audit | **RUNNING** | superseded — now owned by P1-C16 |
| P1-095 | Final compile + anonymity + citation check | **TODO** | superseded — now owned by P1-C17 |
| P1-096 | AI-assistance disclosure | **TODO** | superseded — now owned by P1-C18. 🔴 still an empty stub and required by AAMAS |

### 4.8 Release

| ID | Task | Status | Note |
|---|---|---|---|
| P1-100 | GitHub cleanup | **TODO** | folds into P1-C17 |
| P1-101 | README reproduction instructions | **DONE** | README §Setup + §Handoff |
| P1-102 | HF snapshot | **DONE** | v0.1 + tag |
| P1-103 | Data card | **DONE** | 20 sections |
| P1-104 | Licence verification | **DONE** | `docs/BENCHMARK_LICENSES.md`; the exporter fails closed on unknown licences |
| P1-105 | Results ledger | **DONE** | `docs/RESULTS_LEDGER.md` + `docs/RESULT_INDEX.md` |
| P1-106 | Final consistency audit | **TODO** | folds into P1-C16 / P1-C17 |

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
| P2-07 frontier | **RUNNING** | → P1-C03 |
| P2-08 bearing-breadth figure | **DONE** | Figure 2(a) |
| P2-09 similarity figure | **DONE** | Figure 3 |
| P2-10 abstract v5 | **DONE** | → P1-C01 |
| P2-11 SciCode | **RUNNING** | → P1-C08 |
| P2-12 HF v0.2 | **RUNNING** | → P1-C04 |
| P2-13 cross-benchmark synthesis | **BLOCKED** | → P1-C11 |
| P2-14 final figure selection + page management | **RUNNING** | → P1-C13 |
| P2-15 claim/evidence audit at freeze | **RUNNING** | → P1-C16 |

### 4.11 User-owned (the Master Agent does not spend cycles here)

| ID | Task | Status |
|---|---|---|
| U-01 | Author list | **TODO** (user) |
| U-02 | Reciprocal reviewer designation (1 Oct) + acceptance (8 Oct) | **TODO** (user) |
| U-03 | OpenReview profiles / account logistics | **TODO** (user) |
| U-04 | Submission administration | **TODO** (user) |
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
| **DONE** | **106** |
| **RUNNING** | **16** |
| **BLOCKED** | **10** |
| **TODO** | **21** |
| **DEFERRED** | **22** |
| **KILLED** | **13** |
| **total distinct IDs** | **188** |

**Counting rule.** A legacy ID whose work was taken over by a Phase-3 item is counted
**separately, under its own state**, with the successor named in its row. That is
deliberate: collapsing them would make a legacy ID stop being mentioned, which this page
forbids. So `P1-095` (TODO) and its successor `P1-C17` (TODO) are two rows and two counts.

**Active work is the RUNNING + BLOCKED + TODO block (47 IDs), and it is smaller than it
looks** — 21 of those are user-owned, duplicated legacy IDs, or Level-2 nice-to-haves. The
submission-critical open set is **P1-C03, C04, C05→C07, C08→C10, C11, C13, C15, C16, C17,
C18** — 14 IDs, of which 6 are blocked behind two benchmark bring-ups.

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

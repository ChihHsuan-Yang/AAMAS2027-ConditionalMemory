# P1 Master TODO — AAMAS 2027 Main Track deadline mode

**Abstract: 1 Oct 2026 AoE. Paper: 8 Oct 2026 AoE.** Structured around the critical path.
Maintained by the Master Agent; sub-agent conclusions are not accepted until audited.

Last updated: 2026-09-29.

`TODO` · `WIP` · `REVIEW` (returned, awaiting audit) · `DONE` (audited, accepted) ·
`BLOCKED` · `USER` (needs the user) · `REJECTED`

---

## 🔴 CRITICAL PATH — anything marked USER can stop the submission

| # | Task | Owner | Status | Due | Evidence |
|---|---|---|---|---|---|
| **E1** | **Fix the author list** | **USER** | 🔴 USER | 1 Oct | no P1 author list exists in any local record; candidates in `submission/ELIGIBILITY.md` §6 |
| **E2** | **Confirm every author has an active OpenReview profile** | **USER** | 🔴 USER | 1 Oct | **cannot be automated** — API login-gated, positive control failed; see `ELIGIBILITY.md` §5 |
| **E3** | **Designate the reciprocal reviewer** | **USER** | 🔴 USER | 1 Oct | desk-rejectable; must be a qualified *author*; later changes need PC approval |
| **E4** | Reciprocal reviewer **accepts** the OpenReview invitation | USER | BLOCKED on E3 | 8 Oct | *"Nomination alone is not sufficient"* |
| **E5** | Submit the abstract | USER | READY | 1 Oct | package complete: title, 268-word abstract, keywords, area |

## Now → 1 Oct — registration and design

| # | Task | Owner | Status | Evidence | Next action |
|---|---|---|---|---|---|
| 0.1 | Clone GitHub | Master | DONE | `p1_memory_utility/repo`, pushed to `main` | — |
| 0.2 | Clone + inspect Overleaf | Master | DONE | 1 commit, bare 224-byte template, nothing to preserve | install AAMAS template |
| 0.5 | Verify search-channel health | Master | DONE | `WebSearch` HTTP 400 org-block; `WebFetch` 200 | positive-control all nulls |
| 0.6 | Verify UMEM | Master | DONE | arXiv:2602.10652, Ye et al., 11 Feb 2026 | seam check → A2 |
| 0.7 | Repo scaffold | Master | DONE | 3 commits pushed | — |
| **A1** | **Verify AAMAS policy from primary sources** | Master | DONE | dates, areas, abstract length, reciprocal policy, page limit — all re-fetched 2026-09-29 | `submission/ELIGIBILITY.md` |
| **A2** | **Draft the abstract package** | Master | DONE | 268 words, forbidden-claim scan clean, 5 title options, keywords, LEARN | `submission/ABSTRACT_PACKAGE.md` |
| 1.1 | 🔴 EvoMemEval: same memory × multiple future tasks? | Sub-agent A | WIP | — | if YES → reframe the Introduction, not the experiment |
| 1.2 | 🔴 UMEM: does it report per-task utility **dispersion** or only the mean? | Sub-agent A | WIP | — | decides how the seam is stated |
| 1.3 | Fresh adversarial search (matrix / sign flips) | Sub-agent A | WIP | — | needed before any novelty sentence |
| 1.4 | 🔴 Resolve DATASETS.md provenance defect | Sub-agent A | WIP | `find` → 0 hits for `lme_v2*` on this machine | does **not** block the abstract |
| 1.5 | LongMemEval-V2 feasibility from ACTUAL files | Sub-agent A | WIP | — | gates the memory/task unit |
| 1.6 | Lattice analyzer: how much analysis is free? | Sub-agent B | REVIEW | agent stalled at ~90%, resumed with narrowed scope | audit on return |
| 1.7 | Live ALCF model list + resolved ids | Sub-agent B | REVIEW | token valid ~30 h at 11:05 | audit on return |
| 2.1 | **Freeze the memory unit and future-task unit** | Master | BLOCKED on 1.5 | — | — |
| 2.2 | Leakage/confound review (memory containing the gold) | Master | BLOCKED on 2.1 | — | — |
| 2.3 | Noise-floor protocol + cost | Master | BLOCKED on 1.7, 2.1 | — | empty-memory arm is a free floor |
| 2.4 | Pilot matrix + cost | Master | BLOCKED on 2.3 | — | — |
| 2.5 | **Pre-register analysis + sign-flip definition** | Master | BLOCKED on 2.4 | — | fix definitions BEFORE seeing data |
| 2.6 | Install AAMAS LaTeX template in Overleaf | Master | TODO | — | `\documentclass[sigconf,anonymous]{aamas}` |

## 1 Oct → 3 Oct — first evidence

| # | Task | Status | Note |
|---|---|---|---|
| 3.1 | Memory bank (deterministic JSONL, **not** a vector DB) | BLOCKED on 2.5 | |
| 3.2 | LLM response cache | BLOCKED on 2.5 | the one genuine infra gap |
| 3.3 | **Experiment 1 — noise floor** | BLOCKED on 3.1–3.2 | execution + empty-memory + judge floors |
| 3.4 | **Experiment 2 — pilot matrix** | BLOCKED on 3.3 | multiple future tasks per memory is the hard requirement |
| 3.5 | First interaction + sign-flip result | BLOCKED on 3.4 | |

## 3 Oct → 5 Oct — scale or stop

| # | Task | Status | Note |
|---|---|---|---|
| 4.1 | **Apply the kill criterion** | BLOCKED on 3.5 | a null is a legitimate result; it changes the paper, it does not end the submission |
| 4.2 | Scale the matrix **only if** the phenomenon survives | BLOCKED on 4.1 | |
| 4.3 | NEAR/MID/FAR semantic-distance analysis | BLOCKED on 4.1 | the direct answer to UMEM |
| 4.4 | **Freeze main tables and figures** | BLOCKED on 4.2 | |

## 5 Oct → 8 Oct — manuscript

| # | Task | Status | Note |
|---|---|---|---|
| 5.1 | Full manuscript, ≤8 pages **including any appendix** | BLOCKED on 4.4 | differs from AAMAS 2026 |
| 5.2 | Every citation human-verified against a fetched source | TODO | hallucinated citations are a named desk-reject trigger |
| 5.3 | AI-assistance disclosure (prompts + tool + version) | TODO | **required** where AI shaped hypotheses or experimental design |
| 5.4 | Anonymization check incl. supplementary | BLOCKED on 5.1 | desk-rejectable |
| 5.5 | Findings opt-in/opt-out; final validation; submit | BLOCKED on 5.1 | |

## Scope freeze — per the user, these are NOT submission blockers

Jev · large LLM-manager comparisons · scientific OOD · elaborate memory storage ·
extensive model scaling. Optional extensions only.

**Paper priority order:** (1) execution noise floor → (2) natural memory × task matrix →
(3) memory/task/interaction decomposition → (4) natural sign-flip rate →
(5) NEAR/MID/FAR → (6) *time permitting* scalar vs task-conditioned predictor.

**Do not begin with gate training.**

## Standing constraints

- No endpoint calls beyond health checks until 2.5 is accepted.
- No "first" claims — `docs/LITERATURE_BOUNDARY.md`.
- No secrets in repo, logs, Overleaf, or reports.
- No unverified number in Overleaf or the manuscript; ledger first.
- Positive-control every null. `WebSearch` is blocked; OpenReview profile search is
  login-gated and returns **misleading empty results** anonymously.

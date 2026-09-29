# P1 Master TODO — authoritative

Maintained by the Master Agent. **This is the single source of truth for task state.**
Sub-agent conclusions are not accepted until the Master Agent audits them.

Last updated: 2026-09-29 (session start)

## Legend

`TODO` not started · `WIP` in progress · `REVIEW` sub-agent returned, awaiting audit ·
`DONE` audited and accepted · `BLOCKED` · `REJECTED` sub-agent result failed audit

---

## Phase 0 — setup and audit

| # | Task | Owner | Status | Dependency | Evidence | Next action |
|---|---|---|---|---|---|---|
| 0.1 | Clone GitHub repo | Master | DONE | — | `p1_memory_utility/repo`, empty upstream, branch `main` | — |
| 0.2 | Clone Overleaf `6abbde4a9eb777031afef068` | Master | DONE | — | `p1_memory_utility/overleaf`, 1 commit `60b3cf9`, bare `article` template, 224 bytes | nothing to preserve beyond title |
| 0.3 | Read auth/paths notes | Master | DONE | — | `note/paths-and-authentication/` | Overleaf token env verified; no secrets in repo |
| 0.4 | Read full P1 handoff package | Master | DONE | — | handoff, README §4b, LITERATURE §3a–c, DATASETS, JEV_AUDIT, Shared Infra §14/§14a | — |
| 0.5 | Verify search-channel health | Master | DONE | — | `WebSearch` = HTTP 400 org-policy block (re-confirmed); `WebFetch` = 200 on arXiv | all nulls need positive controls |
| 0.6 | Verify UMEM exists + get abstract | Master | DONE | 0.5 | arXiv:2602.10652, Ye et al., 11 Feb 2026, CC BY 4.0 | full-PDF seam check → A2 |
| 0.7 | Repo scaffold | Master | WIP | 0.1 | `docs/`, `.gitignore` | finish + first commit |
| 0.8 | Sub-agent A: literature + dataset audit | Sub-agent A | WIP | 0.4, 0.5 | — | await; then audit |
| 0.9 | Sub-agent B: infrastructure + ALCF audit | Sub-agent B | WIP | 0.4 | — | await; then audit |

## Phase 1 — the decisive checks (gate everything downstream)

| # | Task | Owner | Status | Dependency | Evidence | Next action |
|---|---|---|---|---|---|---|
| 1.1 | 🔴 EvoMemEval `n3GMbobXnc`: is the SAME memory scored against MULTIPLE future tasks? | A | WIP | 0.8 | — | if YES, P1's last component is at risk → reframe |
| 1.2 | 🔴 UMEM seam: does it report per-task utility VARIANCE, or only the mean? | A | WIP | 0.8 | — | if it reports dispersion, seam narrows → restate |
| 1.3 | Fresh adversarial search for memory x task utility matrix / sign flips | A | WIP | 0.8 | — | working channel required; positive-control nulls |
| 1.4 | 🔴 Resolve DATASETS.md provenance defect | A | WIP | 0.8 | `find` returned ZERO hits for `lme_v2*` / `longmemeval*` on this machine | every V2 "measured" number is currently unsourced |
| 1.5 | LongMemEval-V2 Experiment-0 feasibility from ACTUAL files | A | WIP | 1.4 | — | memory unit, tasks/memory, leakage, token cost |
| 1.6 | Lattice state-file schema: how much analysis is free? | B | WIP | 0.9 | — | determines build cost of the core analysis |
| 1.7 | Live ALCF model list + resolved model ids | B | WIP | 0.9 | token valid ~109ks at 2026-09-29 11:0x | pin resolved ids, not aliases |

## Phase 2 — design (blocked on Phase 1)

| # | Task | Owner | Status | Dependency | Evidence | Next action |
|---|---|---|---|---|---|---|
| 2.1 | Define the memory unit and the future-task unit, exactly | Master | BLOCKED | 1.5 | — | — |
| 2.2 | Leakage / confound review of the cell design | Master | BLOCKED | 2.1 | — | detect memories containing the gold answer |
| 2.3 | Noise-floor protocol (Experiment 1) + cost | Master | BLOCKED | 1.7, 2.1 | — | empty-memory arm is identical across conditions → free floor |
| 2.4 | Memory x task pilot matrix (Experiment 2) + cost | Master | BLOCKED | 2.3 | — | multiple future tasks per memory is the hard requirement |
| 2.5 | Pre-register the analysis (variance decomposition + sign-flip definition) | Master | BLOCKED | 2.4 | — | fix definitions BEFORE seeing results |
| 2.6 | `docs/EXPERIMENT_PLAN.md` final | Master | BLOCKED | 2.5 | — | — |

## Phase 3 — execution (blocked on 2.6 review)

| # | Task | Owner | Status | Dependency | Evidence | Next action |
|---|---|---|---|---|---|---|
| 3.1 | Build memory bank (deterministic JSONL, no vector DB) | TBD | BLOCKED | 2.6 | — | — |
| 3.2 | Build LLM response cache (the one real infra gap) | TBD | BLOCKED | 2.6 | — | — |
| 3.3 | Run Experiment 1 (noise floor) | TBD | BLOCKED | 3.1, 3.2 | — | — |
| 3.4 | Run Experiment 2 (pilot matrix) | TBD | BLOCKED | 3.3 | — | — |
| 3.5 | Variance decomposition vs noise floor | TBD | BLOCKED | 3.4 | — | — |
| 3.6 | **Apply the kill criterion** | Master | BLOCKED | 3.5 | — | a null here is a legitimate result, report it plainly |

## Phase 4 — only if P1 survives

| # | Task | Owner | Status |
|---|---|---|---|
| 4.1 | `G(memory)` vs `G(memory, future_task)` at matched budget | TBD | BLOCKED on 3.6 |
| 4.2 | Baseline spectrum incl. Jev (Jev must never block the core) | TBD | BLOCKED on 3.6 |

## Standing constraints

- **No inference endpoint calls** beyond health checks until 2.6 is reviewed and accepted.
- **No "first" claims** — see `docs/LITERATURE_BOUNDARY.md`.
- **No secrets** in repo, logs, Overleaf, or progress reports.
- **No unverified results** in Overleaf.
- Positive-control every null; `WebSearch` is blocked in this environment.

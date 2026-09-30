# P1 — Current Handoff

**Updated 2026-09-30.** The detailed state. `README.md` §Current Project State is the short
version. Update this at every milestone.

---

## Paths and remotes

| what | where |
|---|---|
| code repo | `/Users/bellayang/Documents/2026/p1_memory_utility/repo` → `github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory` (`main`) |
| Overleaf | `/Users/bellayang/Documents/2026/p1_memory_utility/overleaf` → `git.overleaf.com/6abbde4a9eb777031afef068` (`main`) |
| LongMemEval-V2 | `/tmp/lmev2` (checksum-verified; `trajectories.jsonl` 1.14 GiB) |
| LongMemEval V1 | `data/lmev1/` |
| HF dataset | `AgentsSci/AAMAS2027-ConditionalMemory` (private) |
| ALCF auth | `/Users/bellayang/Documents/2026/iclr_receiver_conditional_communication/inference_auth_token.py` |

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

| run | path | calls |
|---|---|---|
| **screened main** | `results/deltau_screened/cells.jsonl` (2,599 rows / 1,157 cells) | 5,198, 0 errors |
| analysis | `results/deltau_screened/analysis/k3_screened_analysis.json`, `k4_tables.md` | — |
| pilot arm | `results/deltau_pilot/cells.jsonl` | 1,918 |
| official-prompt arm | `results/deltau_official/cells.jsonl` | 1,920 |
| reader diagnostic | `results/j2_escalation/needle_summary.json` | ~516 |
| tracked slim slices | `results/ledgers/repro/` | — |
| design manifest | `data/manifests/k1_screened_cells.jsonl` | — |
| bearing structure | `data/manifests/lmev2_leakage_small.jsonl` | — |

**`results/**` is gitignored except `results/ledgers/`.** The slim slices + K3 JSON are
force-added so headline numbers are clone-reproducible.

## Scripts

`scripts/audit_claims.py` — **re-derives 38 headline claims; proven able to fail.** Run it
before any manuscript edit. · `scripts/k3_analyze_screened.py` (analysis, carries the
mechanical verdict fields) · `scripts/k2_run_screened.py` · `scripts/run_deltau_pilot.py` ·
`scripts/audit_leakage.py` · `scripts/export_hf.py`.

## Last verified conclusions

- Screen worked: both-arms-fail **0.7007 → 0.5252**, pre-committed rule passed.
- Paired within-memory **+0.3349**, episode-clustered CI **[0.1974, 0.4736]**, p = 5e-5.
- **Founding hypothesis unsupported**: 0 sign flips / 35 bearing memories, bound ≤9.9%;
  flips concentrate in RANDOM (17/60); **additive-null excess is negative in all strata**.
- Bearing is scarce: a memory bears on a **median of one** future task.
- Similarity barely predicts utility (ρ = +0.087 overall, +0.006 in RANDOM).
- **Decomposition unidentifiable** — cause is `F_exec = 0`, not the crossing defect.

## 🔴 Known traps — do not repeat

1. **Advertised ≠ live.** 4 endpoints today were advertised and dead. Prove with a real POST.
2. **HF `auth-check` returns 200 for repos you cannot write.** Only an empty-body commit POST discriminates; always use a negative control.
3. **`memory_id` means two things.** Rows use a content hash; some manifests use a positional locator. Join on the **locator**, or check the referent. Two agents hit this independently.
4. **A guard only observed passing is not known to fail.** Three defects today were *in guards*. One printed a correct verdict from an empty input.
5. **A zero from `.get(default)` is not a measurement.**
6. **Exit code 0 is not success** — a stage crashed while a script exited 0.
7. **Pooled rates hide the structure that matters** — leakage by answer length, both-arms-fail by stratum, concentration by stratum. Split before quoting.
8. **Matching counts are not corroboration.** Two 35s named different sets (overlap 25).
9. **Throughput is prompt-length dependent** — 341/min at 4k is ~106/min at 24k.
10. `datascience_collab` expires **2026-10-01**; use AuroraGPT. Aurora is allocated but unused (gateway-bound).

## Invalid / superseded runs

- `results/runs/noise_floor/` — my own probe, one arbitrary memory per task, 2/92 accuracy. Superseded.
- Both unscreened arms are **valid but floor-limited** (~80% both-arms-fail) — keep as the dilution comparator, do not quote as the effect.
- The screened cache is readable **only** by the pre-`5330158` 12-field key shape.

## Currently running (2026-09-30)

**SA-R** representation scale-up (Summary + Structured on BEARING/control) · **SA-HF**
dataset v0.1 + schema audit · **SA-FIG** pipeline figure + ranked figure plan.

## Next TODO

P0: representation scale-up; HF v0.1; pipeline figure. P1: frontier figure; bearing-breadth
and similarity figures; abstract v5. P2: SciCode; BEAM replacement. P3: cross-benchmark
synthesis; claim/evidence audit.

## Handoff instructions

1. Read this file, then `docs/THE_HONEST_HEADLINE.md`, then `docs/DEFECT_REGISTER.md`.
2. Run `scripts/audit_claims.py` — if it fails, stop and find out why before anything else.
3. Run the suite with the 3.13 interpreter.
4. **Never quote a number you have not re-derived from an artifact.**

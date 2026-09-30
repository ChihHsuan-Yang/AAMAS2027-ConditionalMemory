# BEAM replacement: SWE-bench Verified — feasibility verdict

**Sub-agent N, 2026-09-30.** Full evidence and reproduction: `subagent_N_report.md`
(project root). Every number computed on this machine from
`princeton-nlp/SWE-bench_Verified` `data/test-00000-of-00001.parquet`,
sha256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`, 500 rows.

## Verdict: ✅ SELECTED. Seven of seven checks pass.

| # | check | verdict | evidence |
|---|---|---|---|
| 1 | multi-task per memory | ✅ | **133** donors with ≥2 recipients (same-file), **316** (same-dir). **40.9% diagonal vs BEAM's 92.6%** |
| 2 | temporal ordering | ✅ | 2013-01-25 → 2023-08-07, **500/500 distinct** timestamps |
| 3 | leakage | ✅ | **0.000% full**, ≤1.25% partial; 3 positive controls fire |
| 4 | objective reward | ✅ | real pytest FAIL_TO_PASS/PASS_TO_PASS, **executed natively without Docker** |
| 5 | licence | ✅ | **98.0% permissive upstream, no ShareAlike**; pylint (GPL, 10) droppable at 0.34% of pairs |
| 6 | cell fits 131k ctx | ✅ | **0/300 over**; median 4,597 tok at K=4 (LongMemEval's is 24,144) |
| 7 | Raw/Summary/Structured | ✅ | Raw = 0 model calls, median 637 tok |

**End-to-end paired cell executed:** donor `sympy__sympy-16766` → recipient
`sympy__sympy-22914`. WITHOUT = fail (0.0), WITH = pass (1.0), 17/17 PASS_TO_PASS green in
both. **ΔU = +1.0**, by unit tests, no LLM judge.

## Binding design constraints, discovered by measurement

1. 🔴 **SEARCH/REPLACE, never `git apply`.** At `max_tokens=512` the reader cannot emit a
   line-accurate unified diff: 4/4 attempts produced `@@` hunks with no line numbers and
   failed `git apply --check` (rc=128). Shown the exact editable region, it produced an
   applicable SEARCH/REPLACE edit that passed the real test.
2. **Restrict to pure-Python repos** (412/500) so tests run natively — no Docker on this
   host, and the official harness demands Docker + x86_64 + 120 GB.
3. **Drop `pylint-dev/pylint`** (GPL-2.0, 10 instances) — costs 0.34% of pairs.
4. Prefer instances whose gold patch is ≤512 reader tokens (414/500 = 82.8%).

## The one open risk

**Floor effect.** In the probe the WITHOUT arm produced no applicable edit. If both arms
fail on most cells, ΔU is unmeasurable — the same both-arms-fail problem that forced
screening on LongMemEval (0.7007 → 0.5252). **Pilot before committing.**

## Rejected alternatives

- **DS-1000** — CC BY-SA 4.0. The exact ShareAlike trap that killed BEAM.
- **SWE-Gym** — MIT, 2,438 instances, **1,868** donors with ≥2 recipients. Better licensed
  and far larger, but it is agent *training* data (contamination) and not human-validated.
  **Held as the scale reserve** if N binds.
- **τ-bench** — HF API 401, not reachable on this channel. UNRESOLVED.

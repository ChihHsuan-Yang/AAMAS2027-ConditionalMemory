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

## Floor-effect pilot: UNRESOLVED, and my first attempt was void

5 cells x 2 arms gave 1/5 (WITHOUT) and 0/5 (WITH) applicable edits — which looks fatal.
It is not interpretable: I showed the model **the first 90 lines of the file**, and in
**4 of 5 cells the gold patch edits code outside that window** (hunks at lines 278, 152,
106, 1386 of files up to 7,079 lines). A byte-exact SEARCH for unseen code is impossible,
so `search_miss` was the only reachable outcome. Same defect class as
`test-the-mechanism-not-a-comparator`.

**Consequence for the design: retrieval/localization is a REQUIRED pipeline stage.** The
adapter must show the region around the recipient's relevant code, not the file head.

**Floor effect therefore remains the one open risk.** Re-run the pilot with correct
localization (~20 calls) before committing SWE-bench to a main table.

---

# Floor-effect pilot #2 — correctly localized. STOPPED at the gate.

**2026-09-30. 20 model calls, 10 cells, `max_tokens=1024`, top-5 gold-blind regions.**
Artifact: `results/swebench/floor_pilot.json`. Runner: `scripts/swebench_floor_pilot.py`.

## The gate number, reported first

> ## **both-arms-fail = 4/7 = 57.1%** — **above the ~50% stop threshold.**
> Per instruction I **stopped and diagnosed instead of spending more calls.**

For comparison: LongMemEval unscreened was ~80%, and screening brought 0.7007 → 0.5252.

## What is binding: NOT task difficulty — an arm-asymmetric apply failure

| | WITHOUT | WITH |
|---|---:|---:|
| applicable edit produced | **7/7 = 100%** | **4/7 = 57.1%** |
| apply failures (denominator 7) | **0** | **3** (2 `no_block`, 1 `search_miss`) |
| solved, of interpretable (n=7) | 3 = 42.9% | 2 = 28.6% |
| solved, of cells with an applicable edit | 3/7 = 42.9% | **2/4 = 50.0%** |

**The floor is not difficulty.** The reader solves **42.9%** of these tasks unaided — a
perfectly healthy, non-degenerate solve rate, far from a floor. What produces the 57.1% is
that **the WITH arm fails to emit an applicable edit 42.9% of the time while the WITHOUT
arm never does (0/7).**

Restricted to the cells where **both** arms produced an applicable edit — the only cells
where the reward difference means anything — **both-arms-fail is 1/4 = 25.0%**.

### The asymmetry is a confound, not a result

An unapplicable edit is an **error, not a reward of 0**, and `reward` is `None` for those
cells, never 0.0. This matters: scoring the 3 WITH failures as zeros would show memory
*hurting* (2/7 vs 3/7) and **manufacture a harmful memory** — the exact defect class
`p1mem.client`'s truncation guard exists to prevent.

**Tested and rejected:** that the WITH arm's failures are an output-budget artifact of the
longer prompt. Failed WITH cells average **4,051** prompt tokens vs **3,728** for
successful ones — no meaningful separation, and the memory block adds a median of only
1,185 tokens. So prompt length does not explain it. The likelier mechanism is that the
memory's own diff text competes with the shown region for the model's attention when it
composes the SEARCH block — **untested, and the next thing to test.**

## Paired 2x2, on the 4 cells where both arms applied

| | WITH=0 | WITH=1 |
|---|---:|---:|
| **WITHOUT=0** | 1 | 0 |
| **WITHOUT=1** | 1 | 2 |

**1 discordant pair, exact binomial p = 1.0.** No evidence of any effect in either
direction. **n=4 carries essentially no information** — as expected from a pilot sized to
test feasibility, not to detect an effect.

## Four harness defects found during bring-up — each would have faked a floor

The scorer's positive control (gold patch must score 1.0, base must score 0.0) went
**0/6 → 3/6 → 10/10**. Every defect produced a *plausible* 0.0, not a crash:

1. **Multi-file gold fixes are unsolvable by a single-file harness.** 31 of 176 recipients
   (17.6%). Now excluded by an eligibility gate; including them guarantees a 0.0.
2. **The worktree was not reset to each recipient's own base commit**, so gold patches
   legitimately failed to apply.
3. **Django records a test's DOCSTRING instead of its id** when it has one (e.g.
   `"F expressions can be used in Meta.ordering."` as a `PASS_TO_PASS` entry). Passing
   that to the runner errored, which read as the gold patch failing.
4. **`OK (skipped=5)` / `OK (expected failures=1)` are passes** and trailing
   `Destroying test database...` lines mean the status is not the last line.

> Without the gold-patch positive control, this pilot would have reported a ~100%
> both-arms-fail rate and I would have recommended killing the benchmark on four bugs in
> my own harness.

## Verdict

**SWE-bench is NOT shown to floor.** Unaided solve rate is **42.9%**, and both-arms-fail on
the measurable subset is **25.0%**. But the headline **57.1% is above the gate**, and the
cause is a **WITH-arm-specific edit-format failure (0/7 vs 3/7)** that is a confound rather
than a property of the benchmark.

**Recommendation: do NOT put SWE-bench in any table yet** (already the standing
instruction). The next step is **not more cells** — it is removing the asymmetry:

1. Make the edit format arm-symmetric — separate the memory from the editable region
   (e.g. a distinct message, or a strict "emit the SEARCH block first" template) so the
   memory's diff cannot be mistaken for the region to edit.
2. Re-check that `no_block` is not a reasoning-budget effect at 1024 by re-running the
   3 failures at 2048 — ~6 calls.
3. Only once WITH-arm apply failure is at parity with WITHOUT should the floor rate be
   re-measured, at 30-40 cells.

**Localizer:** recall@5 = **7/10** here and **66.4%** over 116 django recipients
(recall@1 31.0%, @3 52.6%). Uninterpretable cells are excluded from the floor statistic
rather than counted as failures. The localizer is **gold-blind by signature**
(`assert_gold_blind`), so the pilot cannot be void for the original reason.

# Benchmark C — SWE-bench Verified selected to replace BEAM

**Decided 2026-09-30 by the Master Agent on SA-N's evidence, independently re-verified.**

---

## The decision

**SWE-bench Verified** replaces BEAM as P1's third benchmark, **conditional on one
unresolved risk** (§4). Memory = a past solved issue's fix experience; future task = a
later issue touching the same source file in the same repository.

## Why — it passes the check BEAM failed, by a wide margin

| | BEAM | SWE-bench Verified (file-level) |
|---|---:|---:|
| diagonality (memories meeting exactly 1 task) | **92.6%** | **0.0%** |
| memories meeting ≥2 future tasks | — | **133** |
| licence | CC BY-SA 4.0 (ShareAlike forces a separate release) | 98.0% permissive upstream, **no ShareAlike** |

**Master Agent's independent verification** of
`data/manifests/swebench_pairs_file_seed20261008.jsonl`:

- 406 cells, **133 distinct donors**, recipients-per-donor {2: 50, 3: 26, 4: 57}
- **every donor meets ≥2 tasks — 0.0% diagonal**
- **0 of 406 pairs violate `donor_created_at < recipient_created_at`** — the temporal
  ordering that makes this a memory setting rather than a retrieval setting
- 8 repositories; `relatedness = file` throughout

SA-N's fuller table (same repo 32,050 pairs / 2.3% diagonal → same file 644 / 40.9%) shows
the axis survives at every relatedness level; we take the **tightest** definition.

## The other checks

| check | verdict |
|---|---|
| **Leakage** | **0.000% full, ≤1.25% partial** — positive-controlled three ways (self-pair fires 493/493, planted leaks 10/10, project detector 17/17). Structural reason: two merged PRs do not add the same lines to the same file |
| **Reward** | **real unit tests, no LLM judge.** A complete paired cell was executed: WITHOUT fails, WITH passes, 17/17 regression green, **ΔU = +1.0** |
| **Context fit** | **0 of 300 sampled cells exceed 131k**; median **4,597** tokens — *smaller* than LongMemEval's 24,144. We never ship a checkout |
| **Representations** | Raw + Structured implemented |
| **Licence caveat** | the HF dataset carries **no licence tag**; the verdict rests on upstream repo terms + MIT on the harness. pylint (GPL-2.0, 10 instances) is droppable at a cost of 0.34% of pairs |

## 🔴 §4 — The unresolved risk, stated before it becomes a surprise

SA-N's first pilot returned **1/5 and 0/5** applicable edits. **That measurement is void
and SA-N said so unprompted:** the model was shown only the first 90 lines of each file,
and in 4 of 5 cells the gold patch edits code *outside that window* (hunks at lines 278,
152, 106, 1386, in files up to 7,079 lines). `search_miss` was the **only reachable
outcome** — the pilot could not have succeeded regardless of the model.

The numbers are kept in the report rather than deleted, so they cannot later circulate as
evidence against the benchmark.

**What survives is a design requirement: retrieval/localization is a mandatory pipeline
stage for SWE-bench.** That is a real finding about the setting, not a defect.

> **Binding: SWE-bench does not enter a main table until a correctly-localized pilot
> establishes a non-degenerate solve rate.** We have been here before — two LongMemEval
> arms were floor-limited at ~80% both-arms-fail, and the instrument could not exhibit the
> effect. Do not repeat that with a second benchmark.

**Also binding:** the output limit, not the input, is the constraint. At `max_tokens = 512`
the reader cannot emit line-accurate unified diffs (**4/4 failed `git apply --check`**), so
the adapter uses SEARCH/REPLACE.

## §5 — The localized pilot: NOT cleared, and the reason is not what we expected

**Gate: both-arms-fail 4/7 = 57.1%**, above the ~50% threshold. SA-N stopped and diagnosed
rather than spending more calls, as instructed. Verified by the Master Agent from
`results/swebench/floor_pilot.json`.

### The reader is NOT the constraint

**The reader solves 42.9% (3/7) of these tasks unaided** — a healthy, non-degenerate rate,
and better than LongMemEval's ~17%. SWE-bench is not too hard.

### The floor is an ARM-ASYMMETRIC edit-format failure

| | WITHOUT | WITH |
|---|---:|---:|
| applicable edit | **7/7 = 100%** | **4/7 = 57.1%** |
| apply failures | **0** | **3** (2 `no_block`, 1 `search_miss`) |
| solved (of 7 interpretable) | 3 = 42.9% | 2 = 28.6% |
| solved, of cells with an applicable edit | 3/7 | **2/4 = 50.0%** |

On the both-applicable subset both-arms-fail is **1/4 = 25.0%** — but n = 4 carries no
information (1 discordant pair, exact binomial p = 1.0) and **no effect is claimed in
either direction.**

> 🔴 **The memory arm fails to produce an applicable edit three times as often.** The
> likely mechanism — the memory's own diff competing with the editable region when the
> model composes its SEARCH block — is **untested**. Prompt length was tested and
> **rejected** as the explanation (failed WITH cells average 4,051 prompt tokens vs 3,728
> for successful ones).

### The discipline that prevented a fabricated result

**Unapplicable edits are recorded as `reward: None`, never `0.0`.** Verified: **0 of 20
arm-results** scores an apply-failure as zero; 6 carry `None`.

Had they been scored as zeros, WITH would read 2/7 against WITHOUT's 3/7 — **memory
appearing to harm**, manufactured entirely by an edit-format artifact. This is the
error class already registered from the LongMemEval truncation guard, caught again in a
new benchmark.

### 🔴 Four harness defects that nearly faked a total floor

The scorer's positive control — gold patch must score 1.0, base 0.0 — went
**0/6 → 3/6 → 10/10** as SA-N fixed:

1. multi-file gold fixes are unsolvable by a single-file harness (31/176 recipients, now gated out);
2. the worktree was not reset to each recipient's base commit;
3. **django records a test's docstring instead of its id** — one `PASS_TO_PASS` entry was literally `"F expressions can be used in Meta.ordering."`;
4. `OK (skipped=5)` is a pass, and trailing "Destroying test database…" lines mean the status is not the last line.

**Every one produced a plausible `0.0` rather than a crash.** Without that control SA-N
would have reported ~100% both-arms-fail and recommended **killing the benchmark on four
bugs in its own harness.**

### Localizer is gold-blind by construction

`localize()` has **no parameter through which a patch can arrive**; `assert_gold_blind`
enforces it, and a control proves the assertion fires on a localizer that *does* accept
one. Recall@5 = 7/10 here, **66.4%** across 116 django recipients (@1 31.0%, @3 52.6%).
Cells where the localizer misses are **excluded**, not counted as failures.

### Verdict

**[SUPERSEDED by §6 — kept so the retracted reading cannot recirculate.]**
**SWE-bench is not shown to floor, but it is not cleared.** Next step is *not* more cells —
it is removing the asymmetry: make the prompt arm-symmetric so the memory cannot be
mistaken for the editable region, re-run the 3 failures at `max_tokens=2048` (~6 calls) to
rule out a reasoning-budget effect, and only then re-measure at 30–40 cells.

**No SWE-bench number enters any table until WITH-arm apply failure reaches parity.**
→ **RESOLVED 2026-09-30 in §6: parity reached (gap +0.000), floor re-measured at
12/32 = 37.5%. §5's numbers are kept as the superseded measurement, not deleted.**

## §6 — The blocker is CLEARED: parity reached, floor re-measured

**Updated 2026-09-30 by SA-SWE. Every number below re-derives from a tracked artifact
under `results/swebench/`, and `scripts/audit_claims.py` checks 32 of them.**

### The cause was diff-format contagion, not region confusion

§5 hypothesised that "the memory's own diff competes with the editable region when the
model composes its SEARCH block". Re-eliciting the three failures **with the response
text captured** — v1 recorded only the status, so the mechanism was unreadable from the
artifact — refines that:

| task | what the WITH response actually did | status |
|---|---|---|
| django-11555 | `+`-prefixed diff lines **inside** SEARCH; `=======` and `>>>>>>> REPLACE` never emitted | `no_block` |
| django-15375 | a `-`/`+` diff pair inside SEARCH; `=======` never emitted | `no_block` |
| django-11239 | **every** SEARCH line prefixed with a diff context space — the text matches the source exactly after removing one leading character | `search_miss` |

The WITHOUT arm at the same three cells emitted **0** diff-marker lines and all three
envelope markers, 3/3. The memory competes for the **output format**, not for the target
region. `render_raw_memory` wraps the donor patch in a ```` ```diff ```` fence and the
reader answers in that syntax.

**Re-run at `max_tokens=2048` (§5's step 2): all three still fail, identically.** Every
call finished on `stop`, none near its cap (103–646 output tokens). **A reasoning-budget
effect is ruled out.**

### The repair, and the constraint it must not break

`src/p1mem/adapters/swebench_prompt.py`. The memory's patch is re-encoded as an annotated
listing (`[added]` / `[removed]` / `[context]`) with **no line dropped** — a change of
encoding, not content, pinned by a losslessness test. The target region moves **last**,
under an explicit `### TARGET FILE` header, nearest the instruction.

🔴 The obvious repair — telling the WITH arm not to copy the diff — is **forbidden by
MEMORY_PROTOCOL §4**: an instruction in one arm and not the other is a second difference
between arms and would confound memory with instruction. So **the WITHOUT arm carries the
memory section too**, with body `(none available for this task)`, and
`assert_arm_symmetric` proves the two renderings are byte-identical outside the memory
slot. **It runs on every cell of every run**, not once in a test.

### 🟢 Parity — same 8 interpretable cells, same budget, only the prompt differs

| | v1 legacy (raw diff) | **v2 symmetric (defanged)** |
|---|---:|---:|
| apply failures, WITHOUT | 0/8 | **0/8** |
| apply failures, WITH | **3/8** (2 `no_block`, 1 `search_miss`) | **0/8** |
| **apply-failure gap** | **+0.375** | **0.000** |
| WITH responses with diff-marker lines | 2 (5 lines) | **0** |

Verified paired, not two runs side by side: identical cell set, identical localizer
recall, **identical shown regions**, identical `max_tokens=2048` (the v1 control was
re-run at 2048 to remove a budget confound). On the WITH arm **3 of 3 failures repaired,
0 regressions** (McNemar b=3, c=0, exact p=0.25; over all 14 cells b=5, c=0, p=0.0625).
n=8, so this is *parity reached on this screen*, not a significant improvement.

### 🔴 The scorer control was django-only, and the other runner was 0/5

Re-running the inherited control reproduced **10/10 on django**. Run on the **pytest
runner it scored 0/5 — every correct gold patch read as `0.0`** — through four further
defects, each of the same "plausible zero, never a crash" shape:

| # | defect | fix |
|---|---|---|
| 5a | sympy stores **bare function names**; pytest reads them as file paths (`ERROR: file or directory not found`) | qualify against the instance's own `test_patch` files |
| 5b | venv was Python 3.13; sympy here imports `distutils`, removed in 3.12 | Python 3.9 venv |
| 5c | `py` 1.11 dropped `py.test`, which `sympy/utilities/pytest.py` reads → every collection errored | pin `py==1.10.0` |
| 5d | a bare name fanned out to a file that does not define it; pytest fails the **whole invocation** on an unresolvable id | filter the fan-out to files that define it |
| 5e | `mpmath` 1.4.1 changed `Float` behaviour → a P2P test failed under correct gold | pin `mpmath==1.2.1` |

Also: with `--continue-on-collection-errors`, pytest can exit **0 having collected
nothing**, so a gold patch would have scored **1.0 for running zero tests**. The runner
now requires a literal `N passed`.

**The negative control also had to be escalated.** sympy-20801's corrupted gold scored
1.0 — but that patch is a pure two-line **move**, so the *deletion* is the fix and
removing the re-inserted copy leaves a passing program. **The scorer was right; the
control was blind.** A level-3 corruption that restores a deleted line was added.

| runner | cells | gold=1.0 | base=0.0 | **PASS** | negative control |
|---|---:|---:|---:|---:|---:|
| django | 12 | 12 | 12 | **12/12** | **12/12** |
| sympy (pytest) | 8 | 8 | 8 | **8/8** | **8/8** |
| **total** | **20** | **20** | **20** | **20/20** | **20/20** |

### 🟢 The localized pilot, re-measured: 55 cells, 110 calls

> # **both-arms-fail = 12/32 = 37.5%** (95% CI 22.9–54.8%) — **below the ~50% threshold**

| | WITHOUT | WITH |
|---|---:|---:|
| **solve rate** (of 32 interpretable) | 15 = **46.9%** | 17 = **53.1%** |
| **apply-failure rate** | **3/32 = 9.4%** | **4/32 = 12.5%** |
| edit statuses | ok 29, search_miss 2, no_block 1 | ok 28, **search_miss 4, no_block 0** |
| diff-marker lines in responses | 0 | **0** |

**Apply-failure gap +0.031: parity holds under measurement, not only on the screen.**
`no_block` — the contagion signature — is **absent from the WITH arm** across 32 cells.

**The `reward: None` discipline holds: 7 `None`, and zero apply-failures scored as a
reward**, re-derived cell-by-cell by the audit rather than read off the summary.

### Paired ΔU — reported, and explicitly NOT claimed

| | |
|---|---|
| both-applicable pairs | 25 (17 donor clusters) |
| mean paired ΔU | +0.160 |
| donor-clustered bootstrap 95% CI | [+0.040, +0.296] |
| discordant pairs | **4 WITH-better, 0 WITHOUT-better** |
| **McNemar exact, two-sided** | **p = 0.125** |

🔴 **The bootstrap interval excludes zero and the exact test does not. The exact test is
the honest one and no effect is claimed.** With 25 pairs of which only 4 are nonzero and
all 4 the same sign, a donor-clustered resample can only go non-positive by drawing none
of the 4 discordant donors — probability **(13/17)^17 = 0.0105**. The lower bound is
bounded away from zero **almost by construction**, so it is not independent evidence. The
direction is consistently positive (4–0, leave-one-donor-out minimum +0.125), which is
worth recording and is not significance.

### 🔴 Coverage limit that must travel with the floor number

**All 55 pilot cells are `django/django`.** The manifest's first eligible sympy cell sits
at position 118, and `--cells 55` never reaches it. The pilot exercises **one repository
and one test runner**, even though the scorer control now covers both. **The 37.5% is a
django number.** Fixing this is manifest-ordering work, not a gate blocker.

### Verdict: KEEP, and SWE-bench may now enter a table

The §5 binding — *no SWE-bench number enters any table until WITH-arm apply failure
reaches parity* — is **satisfied**: gap +0.000 on the screen, +0.031 under measurement.
`scripts/swebench_pilot_v2.py --mode floor` **refuses to run** (exit 2, no artifact
written) unless a parity artifact for the current prompt version and a passing scorer
control both exist on disk.

**What may be quoted:** both-arms-fail 37.5%, the per-arm solve and apply-failure rates
with their denominators, and the parity result. **What may not:** any ΔU effect claim,
and any figure presented as covering more than django.

## Rejected alternatives

| candidate | verdict |
|---|---|
| **BEAM** | dropped: 92.6% diagonality + ShareAlike |
| **DS-1000** | rejected on licence: **CC BY-SA 4.0** — the exact trap that killed BEAM |
| **SWE-Gym** | held in reserve: MIT, 2,438 instances, **1,868** donors with ≥2 recipients — but it is agent *training* data, so contamination argues against it as primary |
| **τ-bench** | **UNRESOLVED**, not absent — 401 on this channel |

## Implementation state

`src/p1mem/adapters/swebench.py` (memory/task units, `Relatedness` enum, deterministic
pairing, Raw + Structured, SEARCH/REPLACE applier) · `tests/test_swebench_adapter.py`
(**31 tests, mutation-proven able to fail** — removing the time-ordering guard fails 6) ·
the pair manifest.

Added for §6: `src/p1mem/adapters/swebench_prompt.py` (arm-symmetric scaffold, defanged
patch encoding, `assert_arm_symmetric`) · `src/p1mem/adapters/swebench_harness.py` (the
shared scorer both the control and the pilot call) · `scripts/swebench_scorer_control.py`
· `scripts/swebench_pilot_v2.py` · `tests/test_swebench_prompt.py` (**22 tests**) ·
`tests/test_swebench_harness.py` (**29 tests**). Both new suites are mutation-proven able
to fail: reverting any one of the defect fixes, or turning `assert_arm_symmetric` into a
no-op, fails between 1 and 6 tests.

**Full suite 593 passing; `audit_claims.py` green (32 SWE-bench claims, each
plant-tested).**

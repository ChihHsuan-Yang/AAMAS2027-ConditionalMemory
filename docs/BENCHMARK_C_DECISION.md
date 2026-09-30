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

**SWE-bench is not shown to floor, but it is not cleared.** Next step is *not* more cells —
it is removing the asymmetry: make the prompt arm-symmetric so the memory cannot be
mistaken for the editable region, re-run the 3 failures at `max_tokens=2048` (~6 calls) to
rule out a reasoning-budget effect, and only then re-measure at 30–40 cells.

**No SWE-bench number enters any table until WITH-arm apply failure reaches parity.**

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
the pair manifest. **Full suite 447 passing; `audit_claims.py` green.**

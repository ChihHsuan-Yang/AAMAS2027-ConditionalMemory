# Reader transfer — does memory utility survive a change of reader?

**Generated from `results/ledgers/gemma_reader/reader_transfer_analysis.json` on 2026-10-01T03:15:15.544544+00:00.** Every number here is read out of that artifact at generation time by `scripts/gemma_reader_report.py`; none is typed from recall, so this document cannot drift from the data.

Pre-registered in `docs/READER_TRANSFER_PRECOMMITMENT.md`, written **before any design-cell Gemma call was issued**.

## The question

A reviewer will ask whether the representation finding is an artifact of `gpt-oss-120b` reading memories that `gpt-oss-120b` wrote. A **second reader consuming the byte-identical memories** answers that directly.

> **This run was not aimed at replication.** Same utility, same ordering with different magnitude, a different representation preference, or no transfer at all were all pre-committed as valid outcomes.

## The answer, in one paragraph

**Memory utility transfers.** On 265 cells matched across both readers and present in all three representations, the representation ordering is **raw > summary > structured** under gpt-oss and **raw > summary > structured** under Gemma — identical. Raw is the only representation whose within-memory BEARING − MATCHED_CONTROL interval excludes zero under gpt-oss (+0.3462), and it also does under Gemma (+0.6002). The finding is **not** an artifact of gpt-oss reading its own memories.

**The magnitude is not the same.** The per-cell paired difference excludes zero on raw (+0.1268 on raw, task-clustered [+0.0496, +0.2050]) — Gemma measures a **larger** ΔU on raw than gpt-oss does.

🔴 **But roughly half of that larger ΔU is a weaker baseline, not a more useful memory.** Decomposed, Gemma's raw WITH arm is +0.0580 against gpt-oss and its WITHOUT arm is -0.0688 — **54%** of the change sits in the arm with no memory in it. Gemma is the weaker reader unaided and recovers more of the gap from the same memory. Reporting "Gemma gets more out of memory" without this decomposition would overstate the result.

**Harm stays nearly absent under the second reader**: across all three representations, 0 of 398 matched BEARING cells are negative under Gemma, against 12 under gpt-oss.

**Per-cell agreement is weaker than the headline correlation suggests, and on structured there is none.** Over all matched cells Pearson r is 0.5196 (raw) and -0.0084 (structured) — but a cell that is 0 under both readers counts as perfect agreement there, and most cells are such zeros. Restricted to cells non-zero under either reader, raw falls to 0.2129 (n=109) and structured is -0.0699 (n=35). **The two readers agree on the ORDERING and the DIRECTION, not cell by cell.** That is reported as a limitation, not smoothed: a reviewer asking "is it the same memories that help?" does not yet have a clean yes.

## The headline

Per representation, on the cells interpretable under **both** readers. ΔU is the mean per-cell utility delta over 2 replicates; the paired difference is per cell, so each row compares the two readers on the *same* memories against the *same* tasks.

| representation | cells | tasks | ΔU gpt-oss | ΔU Gemma | paired diff (Gemma − gpt-oss) | 95% CI, task-clustered | excludes 0 |
|---|---:|---:|---:|---:|---:|---|---|
| raw | 276 | 124 | +0.1884 | +0.3152 | +0.1268 | [+0.0496, +0.2050] | **yes** |
| summary | 274 | 124 | +0.0511 | +0.0547 | +0.0036 | [-0.0484, +0.0612] | no |
| structured | 269 | 122 | +0.0186 | +0.0297 | +0.0112 | [-0.0536, +0.0833] | no |

`docs/ZERO_CONTRIBUTORS.md` requires the non-zero contributor count beside the nominal denominator, and **both** magnitudes. A cell failing in both arms under both readers contributes an exact 0.0, which is a structural zero and not a measurement of "the readers agree":

| representation | nominal cells | non-zero contributors | diluted mean | conditional mean (contributors only) |
|---|---:|---:|---:|---:|
| raw | 276 | 60 | +0.1268 | +0.5833 |
| summary | 274 | 26 | +0.0036 | +0.0385 |
| structured | 269 | 33 | +0.0112 | +0.0909 |

> **Neither magnitude alone is the answer.** The diluted mean is the honest population figure and is what the significance verdict comes from; the conditional mean conditions on an outcome and can never be the population claim.

🔴 **A CI that spans zero here is not evidence that the readers agree.** `docs/PAIRED_POWER.md`: power depends on the spread among contributors, not their count alone, and a contrast with few non-zero contributors is underpowered rather than null. Read the contributor counts above **before** reading any interval — where they are small, the honest reading of a zero-spanning interval is *underpowered*, not *no difference*.

Cell-level intervals (not clustered) are in the artifact; the **task-clustered** interval governs, because cells repeat within tasks and a cell-level interval would treat repeated views of one task as independent draws.

> ⚠️ **The 34.6% "third of all cells on ten tasks" figure is pooled over RANDOM and is not true of this cell set.** `CONTRAST_FRAMING.md` already makes that correction per stratum (BEARING 38.8%, MATCHED_CONTROL 19.9%); re-derived on the two combined, which is the set used here: 285 cells over 126 tasks, top ten tasks hold **60 cells = 21.1%**, max 7 on any one task. Clustering still governs — 4.75 cells per memory, up to 18 on one — but BEARING↔MC is close to robust to task clustering by construction, and the honest statement is that the clustered interval is reported because it is the conservative one, not because this set is severely concentrated.

## The quantity the paper actually reports

`docs/REPRESENTATION_RESULT.md` reports the **within-memory BEARING − MATCHED_CONTROL** contrast, not the raw cell mean. Under each reader, on the matched cells:

| representation | reader | memories | B − MC | 95% CI | non-zero contributors |
|---|---|---:|---:|---|---:|
| raw | gptoss | 59 | +0.3462 | [+0.2210, +0.4761] | 36 |
| raw | gemma | 59 | +0.6002 | [+0.4787, +0.7144] | 45 |
| summary | gptoss | 59 | +0.0640 | [-0.0372, +0.1643] | 25 |
| summary | gemma | 59 | +0.0956 | [+0.0165, +0.1813] | 17 |
| structured | gptoss | 56 | -0.0462 | [-0.1438, +0.0451] | 20 |
| structured | gemma | 56 | +0.0389 | [-0.0256, +0.1038] | 12 |

## Per-cell agreement between the readers

| representation | cells | r, all cells | r, cells non-zero under EITHER | n for that subset | sign agreement (both non-zero) | zero under both |
|---|---:|---:|---:|---:|---:|---:|
| raw | 276 | 0.5196 | 0.2129 | 109 | 49/50 (98.0%) | 167 |
| summary | 274 | 0.3697 | 0.1867 | 36 | 10/11 (90.9%) | 238 |
| structured | 269 | -0.0084 | -0.0699 | 35 | 2/4 (50.0%) | 234 |

🔴 **The all-cells r is inflated and the second column is the one to quote.** A cell that is exactly 0 under both readers counts as perfect agreement, and most cells are such zeros. On raw the correlation falls from 0.5196 to 0.2129 once the tied zeros are removed — **agreement on cells that could not move is not evidence of reader transfer.**

The correlation restricted to cells non-zero under **both** readers is `None` for every representation, and that is itself the finding: ΔU ∈ {−1, 0, +1} and **every cell whose Gemma mean is non-zero is +1**, so Gemma has zero variance on that subset and a correlation is undefined rather than small.

> 🔴 **The naive sign-agreement rate is not the informative one.** Most cells are exactly 0 under both readers — a cell where neither reader's answer changes agrees trivially. The column above is restricted to cells non-zero under **both**; the inflated all-cells rate is in the artifact and is reported there with that caveat attached.

The zeros are **structural, and their cause is already measured**: `docs/BEARING_SCARCITY.md` finds that a naturally occurring memory bears on a **median of one future task out of hundreds**, so most (memory, task) cells cannot move regardless of reader. Under gpt-oss at two replicates the exact-zero counts on these strata are **217/285 raw, 254/285 summary, 250/277 structured** — fixed in `results/gemma_reader/gptoss_sign_baseline.json` before the Gemma deltas were inspected. A reader-agreement rate computed over all cells is therefore mostly a measurement of bearing scarcity, not of reader transfer.

### Useful / neutral / harmful agreement

Each reader is labelled under the pre-registered §4 rule against **its own** measured `F_exec`. Using one reader's floor on the other would be a different experiment.

| representation | cells | gpt-oss labels | Gemma labels | agreement |
|---|---:|---|---|---:|
| raw | 276 | neutral=208, robust_harmful=8, robust_useful=60 | neutral=185, robust_harmful=2, robust_useful=89 | 216/276 |
| summary | 274 | neutral=246, robust_harmful=7, robust_useful=21 | neutral=255, robust_harmful=2, robust_useful=17 | 248/274 |
| structured | 269 | neutral=242, robust_harmful=11, robust_useful=16 | neutral=257, robust_harmful=2, robust_useful=10 | 236/269 |

## Does the near-absence of harm transfer?

`docs/THE_HONEST_HEADLINE.md`'s sharpest claim is that **where a memory bears on a task it helps, and harm is nearly absent** — on gpt-oss, 2 negative BEARING cells of 139. Re-asked of a second reader, on the matched BEARING cells:

| representation | BEARING cells | gpt-oss negative | Gemma negative | negative under BOTH | Gemma-only negative |
|---|---:|---:|---:|---:|---:|
| raw | 135 | 2 | 0 | 0 | 0 |
| summary | 132 | 3 | 0 | 0 | 0 |
| structured | 131 | 7 | 0 | 0 | 0 |

And **where** the negatives fall. On gpt-oss harm appears in both strata; under Gemma every negative cell is MATCHED_CONTROL:

| representation | gpt-oss negatives | Gemma negatives |
|---|---|---|
| raw | BEARING 2, MATCHED_CONTROL 6 | MATCHED_CONTROL 2 |
| summary | BEARING 3, MATCHED_CONTROL 4 | MATCHED_CONTROL 2 |
| structured | BEARING 7, MATCHED_CONTROL 4 | MATCHED_CONTROL 2 |

> The counts are small — 2 per representation under Gemma — so this is a **pattern worth stating, not a tested claim**. It is consistent with the project's own finding that where a memory bears on a task it helps, and it is the direction a reviewer would want checked.

A Wilson interval on each rate is in the artifact. **A count of negative cells is not a harm claim**: the pre-registered label rule requires the cell's CI to exclude zero *and* its magnitude to clear the measured execution floor. The label table above is the one that settles harm; this table shows the raw direction.

## Does the representation ordering transfer?

On the **265** cells present in all three representations *and* matched across both readers — the only basis on which the three representations may be compared to each other:

| representation | ΔU gpt-oss | ΔU Gemma | paired difference |
|---|---:|---:|---:|
| raw | +0.1849 | +0.3094 | +0.1245 |
| summary | +0.0528 | +0.0566 | +0.0038 |
| structured | +0.0189 | +0.0264 | +0.0075 |

Ordering under gpt-oss: **raw > summary > structured**  
Ordering under Gemma: **raw > summary > structured**  
Orderings agree: **True**

## Is Gemma simply a weaker reader?

A difference in ΔU can come from the memory being less useful *or* from the reader being worse at the task outright. Both arms' absolute reward levels separate those:

| representation | reader | mean reward WITH | mean reward WITHOUT |
|---|---|---:|---:|
| raw | gptoss | 0.2971 | 0.1087 |
| raw | gemma | 0.3551 | 0.0399 |
| summary | gptoss | 0.1496 | 0.0985 |
| summary | gemma | 0.0949 | 0.0401 |
| structured | gptoss | 0.1190 | 0.1004 |
| structured | gemma | 0.0669 | 0.0372 |

ΔU = reward(WITH) − reward(WITHOUT), so a **larger ΔU under the second reader can mean the memory helps more, or that the reader is worse without it.** Those are different claims and the means above cannot separate them. Decomposed on the matched cells:

| representation | cells | Δ in the WITH arm | Δ in the WITHOUT arm | share of the ΔU change from the WITHOUT arm |
|---|---:|---:|---:|---|
| raw | 276 | +0.0580 | -0.0688 | 54.3% |
| summary | 274 | -0.0547 | -0.0584 | — |
| structured | 269 | -0.0520 | -0.0632 | — |

> A dash means the share is **undefined, not missing**: both arms moved in the same direction, so the paired difference is their small residual and "a share of" it would be a ratio with a near-zero denominator dressed as a proportion. Read the two arm changes directly in those rows.

## What was held, and how it was proven

Only the reader changed. That is **asserted in code at run time**, not claimed in prose — any disagreement aborts before a call is paid for.

| gate | what it compares | result |
|---|---|---|
| 1 | `memories.jsonl` sha256 vs the gpt-oss run's fingerprint | `b342151c7f3cac5a` MATCH |
| 2 | system prompt sha256 | `cdc9c36ad4266f53` MATCH |
| 3 | rebuilt filler pool sha256 | `f6d88934516499fa` MATCH |
| 4 | **every rendered request's `context_sha256` vs the hash the gpt-oss cache stored for the same cell** | **2248 matched, 0 mismatched**, 1140 unverifiable |
| 5 | per-cell target position + filler vs the gpt-oss **row** | **847 matched, 0 mismatched** |

**Gate 4 is the decisive one** — it compares the bytes actually sent, which no amount of "we used the same script" establishes.

**Gate 5 is not a formality.** `docs/POSITION_EFFECT.md` measured that moving the target memory's position — same memory, same question, same filler, same decoding — changed the answer in **8 of 12 cells**. A reader comparison in which the two readers saw the memory at different positions would be measuring position plus reader. Gate 5 checks the recorded position and filler composition per cell against the gpt-oss row, and is the only per-cell check `raw` has.

🔴 **Gate 4 cannot cover `raw`.** The screened cache was written under the **v1** key shape, which had no `context_sha256` field at all. Those 1140 requests are counted as `unverifiable_v1_key` and **never as agreement** — an absent check must not read as a passing one. **Gate 5 exists for exactly that gap**: it is a per-cell check on target position and filler composition that gates 1–3 (which are global) cannot provide.

**Memory text re-verified on the row pairs themselves**, not assumed from the pipeline: **1694/1694** byte-identical, 0 differ.

## Controls — every null defended

| control | result |
|---|---|
| gate 4 can FAIL (one byte appended to a user message) | aborts, exit 1 |
| gate 5 can FAIL (one filler unit dropped, on `raw` where gate 4 is blind) | aborts, exit 1 |
| gate 1 can FAIL (one byte changed in `memories.jsonl`) | aborts, exit 1 |
| cache separation, **positive control first** | gpt-oss key HIT → Gemma key MISS → gpt-oss key in Gemma cache MISS |
| A/A determinism, gpt-oss (byte-identical requests, separate calls) | 248/248 identical |
| A/A determinism, Gemma (byte-identical requests, separate calls) | 248/248 identical |
| `F_exec` estimator can return non-zero (flip one replicate in 144 cells) | 0.5126, fires=True |
| correlation estimator recovers known values | r(x,x)=1.0000, r(x,−x)=-1.0000 |
| the WRONG join is shown to fail, not merely warned about | `condition_id` → **0 rows**; correct locator+task key → 7 rows |

**Reader identity on this run's own rows** (task 3): every Gemma row carries `reader_model` ∈ ['gemma-4-31B-it'], every comparator row ['gpt-oss-120b']; the two sets are disjoint (True) and the condition ids are disjoint (True). Both readers served from cluster `metis`, so **this is a reader comparison and not a reader×cluster comparison**.

## Coverage, and what is NOT covered

| representation | eligible | gpt-oss interpretable | Gemma interpretable | **matched** | lost to Gemma | lost to gpt-oss |
|---|---:|---:|---:|---:|---:|---:|
| raw | 285 | 285 | 276 | **276** | 9 | 0 |
| summary | 285 | 285 | 274 | **274** | 11 | 0 |
| structured | 277 | 277 | 269 | **269** | 8 | 0 |

**Not covered**, and stated rather than glossed:

- the **8 cells whose structured write failed** (3 memories). A failed write has no memory text to read; the exclusion is a property of the **write** pass, which ran before any reader did, and is therefore non-outcome-based.

- the **872 RANDOM-stratum cells** and the rest of the 15,112-pair frozen universe. This arm replicates the **representation sub-universe** — the basis `docs/REPRESENTATION_RESULT.md` reports — not all of LongMemEval.

- the **156 LLM-judged questions**: `F_judge` is unmeasured, so they are a separate scorer stratum under `docs/COVERAGE_MANIFEST.md` and are not pooled here.

- **writer transfer.** Only the reader changed. Whether a *Gemma-written* memory behaves differently is the W1–W4 factorial and is unrun.


**Unscoreable cells** (`reward = None`, never 0.0): Gemma {'raw': 9, 'summary': 11, 'structured': 8}, gpt-oss {'raw': 0, 'summary': 0, 'structured': 0}.

## A defect this run found, and what it cost

The first execution attempt was **killed at 600/3,388 calls**. Under 16-worker load at the real 15–29k-token shape, metis/`gemma-4-31B-it` returns truncated responses with `finish_reason` **`""`** and `usage.stop_reason` **`""`** — neither says `"length"` — while `completion_tokens` sits exactly at `max_tokens`. The truncation guard tested `finish_reason == "length"` and was **silent**; 7 fragments of 2,034–2,146 characters were returned as answers. Scored, each is a wrong answer that drives ΔU negative and **manufactures a harmful memory**.

This is defect #16 in a **third** disguise, and the single-request probe that found #16 could not have found it: `max_tokens=8` on an idle endpoint returns a clean `finish_reason="length"`. The empty field appears only at concurrency on long prompts.

The guard now tests three observables, the third of which — `completion_tokens >= max_tokens` — cannot be misreported without the server also misreporting its own token count. **Across 11,693 `gpt-oss-120b` rows in every shipped cache the widened detector flags exactly the 19 rows the old one flagged**, so the fix cannot have moved a published gpt-oss number. Full account: `docs/DEFECT_REGISTER.md` #20.

## Where the artifacts are

`results/**` is gitignored — raw endpoint outputs are large and the project tracks only ledgers. So:

| artifact | path | tracked? |
|---|---|---|
| the analysis every number here is read from | `results/ledgers/gemma_reader/reader_transfer_analysis.json` | **yes** |
| controls (A/A, cache separation, truncation) | `results/ledgers/gemma_reader/reader_transfer_controls.json` | **yes** |
| run summary + the five gates | `results/ledgers/gemma_reader/transfer_summary.json` | **yes** |
| the gpt-oss comparator anchor, fixed first | `results/ledgers/gemma_reader/gptoss_comparator_anchor.json` | **yes** |
| the gpt-oss sign baseline, fixed first | `results/ledgers/gemma_reader/gptoss_sign_baseline.json` | **yes** |
| the claims this arm was read against | `results/ledgers/gemma_reader/claims_under_test.json` | **yes** |
| sha256 of the untracked row files | `results/ledgers/gemma_reader/row_file_digests.json` | **yes** |
| 1,694 result rows | `results/gemma_reader/transfer_cells.jsonl` | no (30 MB) |
| 3,294 cached responses | `results/gemma_reader/transfer_cache.jsonl` | no (7 MB) |
| the 7 quarantined truncations + pre-fix cache | `results/gemma_reader/transfer_cache_quarantined_truncations.jsonl`, `…PRE_TRUNCATION_FIX.jsonl` | no |

> ⚠️ **A digest verifies a file; it does not recover one.** The row files are not redistributed here, so an outside reader can check that a local copy is the one the analysis read, but cannot re-derive these numbers without re-running the arm.

## Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9

$PY scripts/gemma_reader_run.py --dry-run                      # gates only
$PY scripts/gemma_reader_run.py --dry-run --plant-context-defect   # GATE 4 must abort
$PY scripts/gemma_reader_run.py --dry-run --plant-position-defect \
       --representations raw                                   # GATE 5 must abort
$PY scripts/gemma_reader_run.py                                # the run
$PY scripts/gemma_reader_controls.py                           # controls
$PY scripts/gemma_reader_analyze.py                            # analysis
$PY scripts/gemma_reader_report.py                             # this document
$PY -m pytest tests/test_reader_arms.py -q
```

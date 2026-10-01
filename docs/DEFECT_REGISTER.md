# Defect Register — 2026-09-29

Every instrument defect found on the project's first execution day, with who found it and
what it would have cost. **Kept because the pattern matters more than any single entry:
each one produced a plausible-looking number.**

Nothing here is a process complaint. It is the evidence base for the paper's methods
section and for the claim that the measurement is trustworthy.

---

## Defects that reached a reported number before being caught

| # | Defect | Reported as | Caught by | Would have cost |
|---|---|---|---|---|
| 1 | Replicates were not byte-identical — position seeded by `replicate_id` | "endpoint is nondeterministic, 4.3%" | Sub-agent G | a fabricated execution-noise floor |
| 2 | `judge_floor` grouped byte-identical text **without the task** | "F_judge = 0.1486" | Sub-agent H | a fabricated judge floor; 18/18 groups spanned tasks |
| 3 | `ZeroDivisionError` crashed the decomposition **while the script exited 0**; caller read an empty dict through `.get(c, 0.0)` | "variance shares all 0.0000" | Sub-agent H | **a null reported as measured** |
| 4 | `leakage_flag` is not discriminative — fires on unpaired memories at ratio **0.995** | "the bottleneck is reader capability" | Sub-agent J | **the wrong scientific conclusion**, and a benchmark change |
| 5 | Embedding cap bisected on prose 2× sparser than real data | "working cap 3,400 tokens" | Sub-agent G | 10/10 embedding failures at run time |

## Defects caught before they reached a number

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 6 | `select_filler` re-randomized on exclusion (25/25 non-drawn exclusions changed the draw) | Sub-agent G | corrupted `F_empty`: the WITHOUT arm would differ between memories |
| 7 | WITHOUT arm servable from cache across memories | Master (pre-registered as A1.4) | `F_empty = 0` ⇒ **every ΔU trivially "significant"** |
| 8 | Sign flips occur at 53–92% with **zero** interaction | Sub-agent D | **the headline claim**: a flip rate reported as evidence of conditionality |
| 9 | REML not identified — shares equal to 16 s.f. at the clip ceiling, `converged=True` | Sub-agent H | a fabricated variance decomposition |
| 10 | Truncation scored as a wrong answer (`reasoning_tokens` eats `max_tokens`) | Sub-agent C | ΔU pushed negative ⇒ **manufactured harmful memories** |
| 11 | HF `auth-check` returns 200 for repos we cannot write | Sub-agent E | a failed upload believed pre-verified |
| 12 | `reader_model` in the condition key defeated the cluster-homogeneity check | Sub-agent E | silent pooling of two clusters |
| 13 | Cache-lock test vacuous (distinct keys never exercised check-then-act) | Sub-agent C, by mutation testing | an unprotected race believed tested |
| 14 | Concurrency ladder measured one wave at the top level | Sub-agent C | a wrong throughput ceiling |
| 15 | Python 3.9 aborts pytest collection on a vendored file | Master | **a healthy suite looking broken** |

## Added 2026-09-30 — found while building the Gemma reader arm (SA-GEMMA-READER)

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 16 | **The truncation guard's observable was a property of gpt-oss, not of truncation.** `finish_reason=="length" AND not content.strip()` fires on gpt-oss because reasoning tokens eat the budget and the answer comes back null. Gemma has no separate reasoning stream, spends the budget on the ANSWER, and returns a grammatical FRAGMENT (`"Here is the step-by-step"` at `max_tokens=8`). The clause is False; the fragment is returned as a normal answer | SA-GEMMA (flagged), SA-GEMMA-READER (fixed + regression-tested) | a fragment scored as a wrong answer ⇒ ΔU negative ⇒ **a manufactured harmful memory** — defect #10 recurring in a new disguise |
| 17 | **The truncation guard and the model-id pin ran on a FRESH response but NOT on a cache hit.** Demonstrated: store `finish_reason="length"` + `content=""`, read it back, no exception | SA-GEMMA-READER, by trying the cache path on purpose | the runner's RESUME path is a cache read, so a killed-and-resumed run would score exactly the truncations the first run refused — and the first run's refusal is what makes the ledger trustworthy |
| 18 | **`CLUSTER_REPORTS_REASONING_TOKENS` is keyed on CLUSTER, on a premise measured on one model.** "Metis reports reasoning tokens" is true of `gpt-oss-120b` and FALSE of `gemma-4-31B-it` on the same cluster (no `completion_tokens_details` at all) | SA-GEMMA-READER, by validating a Gemma row before writing one | two failures at once: a spurious `reasoning_tokens_missing` warning on every correct Gemma row (training a reader to ignore it), and **silence on the real corruption** — `reasoning_tokens=0`, an absence written as a measurement |
| 19 | **A case-variant model id returns HTTP 200 and is silently corrected.** `gemma-4-31b-it` (lowercase b) is not a 404; metis resolves it to `gemma-4-31B-it` | SA-GEMMA | `_assert_model` catches it at call time, but a mis-cased config would pass every dry run and every liveness check |
| 20 | **I claimed an artifact retained model text without opening it.** My commit `53a21f8` stated the full SciCode artifact "keeps the raw model text on disk rather than being reduced to a digest, so re-scoring under a corrected verifier stays possible", and `MANIFEST.json` said the same. Measured: FULL minus SLIM keys is `['stderr_tail']` — there is **no model-text key anywhere**. `scicode_pilot.py` records `response_chars=len(content)` and discards `content`; `P1Client` was built with no `cache=`, so no completion was persisted. I was reasoning from the LongMemEval artifact's shape, which does retain text | SA-HF-CONVERT, then confirmed by me | **SciCode could never be re-scored under a corrected verifier** — the exact failure the retention policy exists to prevent, recorded in the register as prevented while being untrue. Note the shape: this is [#]'a stamp you did not measure' applied to a provenance claim rather than a number |
| 21 | **A pytest collection error was scored as a wrong answer.** `score_patched_file` ended its F2P branch with `if not f2p.ok: return 0.0`. `TestOutcome.n_status_lines` exists *precisely* to separate "the tests ran and failed" from "the tests never ran" — it was computed, written into the detail string, and then **never consulted**. Measured across both repos: **27 django + 10 sympy arm-runs** carried `reward 0.0` with `status_lines=0`, i.e. an import/collection error recorded as the model's fix being wrong | Master, by checking that sympy's first-ever rewards came from real test runs rather than trusting `reward is not None` | this is defect #10's family again — **an error value becoming a real number** — and it ran in the opposite direction from the apply-failure guard the harness was *built* to prevent. Corrected denominators: django matched 13→12, sympy 4→3, pooled 17→15. The conclusion did not change (every contrast still crosses zero), which is why it had to be found by looking rather than by a surprising result |
| 22 | **I measured within-session repeatability and called it reproducibility.** On finding the SciCode memory text was never persisted, I probed the writer twice *in one process*, got byte-identical output, and concluded the text was "reproducible, not lost" — then dispatched a recovery on that premise. The two draws shared a session; the question was whether a draw TODAY equals a draw from a RUN LAST WEEK. **Measured at fully matched settings** (`max_tokens=512`, temp 0, `reasoning_effort=low`, segments rebuilt with r1's own `load_segments`) against 8 ground-truth LongMemEval summaries: **0/8 byte-identical**, while a within-session triple draw is **3/3 identical**. Same prompt, same decoding, different day, different text | SA-RECOVER found it; its own disproof used `max_tokens=1024` against a 512 corpus and was caught by the verifier; I then settled it at matched settings | **308 SciCode cells would have shipped carrying regenerated text presented as the memory whose utility was measured** — a different memory wearing this run's rewards. The general rule: *temperature 0 is not a persistence strategy.* Any arm that discards model-written text is unrecoverable by construction |
| 23 | **An absolute home path in a shipped file would have de-anonymised the submission, and every gate passed.** The staged v0.3 tree carried `/Users/<name>/Documents/...` in a provenance docstring in `code/p1mem/schema.py`. Nine export gates, a credential scanner and 32 self-tests all said PASS: the string is **not a secret** — no entropy signature, no key prefix, and it reads as an ordinary file path | Master, scanning the staging tree by hand before approving upload | a **double-blind failure in a reviewer-facing artifact**, from the one class of leak a credential scanner is structurally blind to. Fixed at source and gated: GATE 2b `gate_identity_scan_tree`, verified against a planted macOS path, a planted Linux path, and a clean negative control |

## Added 2026-09-30 (later) — found while RUNNING the reader-transfer arm

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 20 | **The truncation guard's observable was a property of the SERVER'S REPORTING, not of truncation.** Under 16-worker load at the real 15–29k-token cell shape, metis/`gemma-4-31B-it` returned responses sitting **exactly at `max_tokens`** with `finish_reason` **`""`** and `usage.stop_reason` **`""`** — neither says `"length"`. The guard tested `finish_reason == "length"`, so it was silent, and seven 2,034–2,146-character **fragments** were returned as if they were answers | SA-GEMMA-READER, by auditing the in-flight cache rather than waiting for the run to finish | each fragment scored as a wrong answer ⇒ ΔU negative ⇒ **a manufactured harmful memory**. Defect #10/#16 in a **third** disguise |

### Why #16's fix did not prevent #20

#16 widened the guard from "empty content" to "any content, on an arm that
declares it". Both clauses still hung off **`finish_reason == "length"`**. #16's
lesson was recorded as *"the observable was a property of the **model**"*; the
true generalisation is **"the observable was a property of something other than
truncation"**, and the next layer that could vary was the **server's reporting
of that model, under load**.

🔴 **The single-request probe could not have found it.** `max_tokens=8` on an
idle endpoint returns a clean `finish_reason="length"` — re-measured during this
session, three times, at both 48k and short prompts. The empty field appears
only at concurrency on long prompts. **A guard probed in a quieter environment
than the run is not known to hold in the run** — the same shape as measuring
throughput at the wrong prompt length.

### The fix: three observables, one of which cannot be misreported

```text
1. finish_reason == "length"              the documented signal
2. usage.stop_reason == "length"          the same fact, other field
3. completion_tokens >= max_tokens        the ARITHMETIC fact
```

Clause 3 is **sound, not merely sufficient**: a model stopping on its own must
emit EOS, so a complete answer cannot consume the entire budget. No server can
misreport it without also misreporting its own token count.

**Proven not to move a published number.** Across **11,693** `gpt-oss-120b` rows
in every shipped cache the widened detector flags **exactly the 19** rows clause
1 already flagged — zero additions — so a fix for a Gemma hazard cannot silently
alter a gpt-oss table. That equality is itself a test
(`test_arithmetic_clause_flags_exactly_what_clause_one_flags_on_shipped_caches`),
with a `n_checked > 1000` assertion so an empty scan cannot pass it vacuously.

**Seven regression tests, four of which were verified to FAIL against the
unfixed code**, plus a second mutation (`>=` → `>`) that fails three — the
off-by-one is the near-miss that still misses the exactly-at-cap case, which is
the only case actually observed.

**The error message was part of the fix.** It previously hardcoded
`finish_reason='length'`; on the measured case that string is **false** — the
field was `""` and only the arithmetic clause fired. A right verdict with a
wrong stated reason would have hidden this defect from the next reader, so the
message now names the clause that actually fired.

### What this cost, and what was done with it

The first execution attempt was **killed at 600/3,388 calls** on finding it. The
7 contaminated cache rows are **quarantined, not deleted**
(`results/gemma_reader/transfer_cache_quarantined_truncations.jsonl`, with the
pre-fix cache preserved whole) — a resumed run reads the cache, so leaving them
in place would have re-served exactly what the first run should have refused.
**All 7 were `raw`, and all 7 were on a single task (`40758d8b`)**, so the
contamination was concentrated rather than diffuse — which is also why a
spot-check of a few cells would have missed it.

### Pre-existing truncation exposure on the gpt-oss arms — a finding, not a fix

Auditing the shipped caches for defect #16's shape found it is **not
Gemma-specific**: `results/deltau_pilot/cache.jsonl` has **8** rows with
`finish_reason=="length"` and non-empty content, and those 8 reached **8
scored cells** — 6 WITHOUT-arm fragments of 3,011 chars, and 2 WITH-arm rows
whose entire output was `\boxed{C`, a truncated answer token scored as a wrong
answer.

**All 8 have ΔU = 0.0 and `utility_label = undetermined`, so no reported
number moves.** The two main runs (`deltau_screened`, `repr_scaleup`) have
**zero**. Handed back undecided in `docs/MODEL_ARMS.md`: re-running or
annotating those cells is a decision about published results, not a code
change, and the strict guard was deliberately NOT switched on for the gpt-oss
arms so that fixing a Gemma hazard could not silently alter a shipped table.

### The shape, again

Three of the four are the same shape in a new costume:

> **A check that was verified on its home case is not known to discriminate on
> an unfamiliar one.** #16 and #18 each passed every test for an entire
> project because the only reader was the one they were written against. The
> new reader did not break them; it revealed that their subject had always
> been the model, not the thing they claimed to measure.

#17 is the adjacent shape: **a guard enforced on one path and not its
alternative**, where the unguarded path is the one a resumed run takes.

What caught them: not reading the code. Running the new model against the old
assumption, and — for #17 — deliberately constructing the stored row the guard
was supposed to reject. Each fix carries a regression test **verified to fail
against the unfixed code** (three mutations, each caught).

## Added 2026-09-30 (SciCode memory recovery) — a probe of the wrong quantity, and a gate that read the exit code

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 21 | **A determinism probe measured WITHIN-SESSION repeatability and was read as CROSS-SESSION reproducibility.** Drawing the same memory twice in one session returned 6/6 byte-identical, which licensed "the text is regenerable". It is not: the endpoint is stable inside a session and NOT across sessions | the `prompt_tokens` identity check, then a direct control against memories whose text is on disk | **308 regenerated SciCode memories published as the ones the run scored** — fluent, about the right segment, and wrong, with nothing downstream able to object |
| 22 | **GATE 5 ran the data card's verification command and checked only its EXIT CODE.** The card's printed "expect: 5643 rows / 1129 warnings" was false against a 5,797-row release and the gate passed | building v0.3 and reading the card beside the output | a consumer following the README reads 5,643, sees 5,797, and concludes their download is **corrupt** |
| 23 | **The export self-test's fixture could not be validated in isolation.** It took `rows[0]` and ran `validate_dataset([one_row])`; `num_replicates_mismatch` is a PER-CELL check, so a row from a 2-replicate cell fails by construction | running the self-test on the v0.2 input **as a control** before blaming the new rows | a true "a correctly redacted row cannot ship" alarm, chased in redaction where the bug was not |

### Why #21 is the register's own shape in a new costume

> **A check that was verified on its home case is not known to discriminate on an
> unfamiliar one.** The determinism probe's home case is one session. The question
> was about two.

The premise was testable against ground truth the whole time and nobody looked:
`results/repr_scaleup/memories.jsonl` stores 60 Summary memories written by the
same writers, on the same model, **with their text**. Re-running them reproduces
**0 of 12** byte-identically while the writer's own `prompt_tokens` matches
**12 of 12** — the same prompt went out and a different answer came back.

**What made this findable was a number the lost run had written down.** Every WITH
arm-run recorded the server's `prompt_tokens`, which is a function of the exact
prompt bytes and so of the memory text inside them. That is the difference between
"the text is gone" and "the text is gone and here is how to tell whether you have
got it back":

| representation | cells matched | verdict |
|---|---|---|
| `raw` | **154/154** | recovered — and it involves **no model call**, so it was never at risk |
| `summary` | 5/154 | not recovered |
| `structured` | 0/154 | not recovered |

**The 5 summary matches are chance and were shown to be.** Two independent
regenerations of one segment differ in text, and their token counts coincide anyway
~5–8% — predicting ~2–3 spurious per-memory "verifications" over 34 memories.
Observed: 2. *A per-memory verdict at its own null rate is not evidence*, and the
per-cell counts do not rescue it: the difference is CONSTANT across a memory's cells
(0 of 68 varied), so a memory with 17 cells supplies **one** comparison, not 17.

### The check's limits, measured rather than assumed

Both directions were run, because a check is only informative if it can fail *and* pass:

| control | result | reading |
|---|---|---|
| perturb a MATCHING memory | **2 of 6 detected**; **0 of 4 one-character** edits | a token count is **not a hash** — appending a period or changing a digit re-tokenises to the same length |
| substitute a DIFFERENT memory | **0 of 3,003** matched | a match is genuinely informative |

So "matched" means *same token count under every one of that memory's prompts*,
which is strong evidence and **not** proof of byte identity — stated in the artifact
rather than left for a reader to infer.

⚠️ The positive control initially **refused to run**: its first subject was a
`summary` cell that already mismatched, and it reported *"the unperturbed subject
does not match, so a perturbation that 'fails' proves nothing."* That refusal was
correct and is kept. **A control applied to a subject that is already failing is
not a control.**

### #22 and #23 share one shape with #3

> **A check that inspects the wrong subject reports confidently.** #3 read an exit
> code while a `ZeroDivisionError` ate the result; #22 read an exit code while the
> card's own numbers were false; #23 read a per-cell check through a one-row window.

#23 also carries the register's standing instruction about blame: the self-test
failed on the v0.3 input, and the **first** action was to re-run it on the v0.2 input
that had already shipped. It failed identically. Without that control the hour would
have gone into the new SciCode rows, which were innocent.

## The pattern

**Eleven of these produced a plausible number.** None announced itself as an error. The
recurring shape, in one line:

> A check that inspects the wrong subject reports confidently.

Sub-shapes, each seen more than once today:
- **an absent value defaulting to a plausible one** (#3, #11, and a near-miss in J's own
  verification script);
- **a null with no positive control** (#4, #6, and my own leakage-denominator error);
- **a measurement made on unrepresentative material** (#5, #14);
- **a crash inside a pipeline whose exit code stayed 0** (#3).

## What actually caught them

Not review-by-reading. In every case: **re-running the measurement against a control that
should behave differently.**

- mismatch control on an unpaired memory (#4)
- planted defect that the estimator must flag (#2, #3)
- mutation testing (#13)
- comparison against a no-exclusion baseline rather than between two exclusions (#6)
- exercising the same probe on real data rather than synthetic (#5)
- a positive control on a known-good case (#15)

## The same defect, found independently by two agents within minutes

**Joining on a field that shares a NAME rather than a REFERENT.**

`results/deltau_screened/cells.jsonl` carries `memory_id` as a canonical content hash
(`mem-013696c4-eae1...`). `data/manifests/k1_screened_cells.jsonl` carries a *different*
upstream `memory_id` (`cc470fce0740eb16`) plus the locator. **Same field name, different
referent.**

| who | symptom | what it would have cost |
|---|---|---|
| Sub-agent K | verification reported **all 2,599 rows disagree** with the design on stratum | a false integrity alarm on a clean run |
| Master Agent | paired test returned **0 memories** | reporting the headline contrast as empty |

Both re-joined on the locator and got **2,599/2,599 agreement, zero mismatches**.

Two things worth keeping:

1. **The 100% disagreement rate was the tell.** As K put it, a *partial* mismatch would
   have been far more dangerous — it would have looked like a data problem worth
   investigating rather than an obviously broken join. A result that is uniformly extreme
   is usually a property of the instrument.
2. **This is the `memory_id` collision from this morning, resurfacing.** It was ruled on
   (`memory_id` = content hash, `memory_unit_locator` = positional) and the ruling was
   applied — but only in the manifests I rewrote, not in the upstream file K's design was
   built from. **A naming ruling enforced in some artifacts and not others is worse than
   no ruling**, because downstream code then joins on a name that is authoritative in one
   file and misleading in another.

## 🔴 The most dangerous defect of the session: a correct verdict derived from no data

Sub-agent K's `FOUNDING_HYPOTHESIS` field printed:

```text
SIGN-REVERSAL COMPONENT NOT SUPPORTED: 0 of 0 flip-eligible BEARING memories
```

**0 of 0.** It read `labels_and_flips["flips"]`, a key that does not exist — the emitter
produces `primary_balanced` / `secondary_all_replicates` / `bh_corrected`. A `.get()` chain
defaulted to `{}`, the denominator came out zero, and the verdict string was assembled from
nothing.

### Why this is worse than every other defect here

**The verdict was correct.** The true value is 0 of 35, the conclusion the paper will
publish is the one the data supports, and the sentence would have survived every review —
including mine.

> **It was not derived from the data.** Had the truth been "17 flips", the field would have
> printed the identical verdict. A guard that reaches the right conclusion from an empty
> input **has not been tested by agreeing with you.**

Every other defect in this register announced itself by producing a *wrong* number. This
one produced a right one.

### What actually caught it

Not review, not a test, not the verdict looking odd. **K had hand-computed 0 of 35 from the
rows an hour earlier, and the printed denominator disagreed.** Without that prior
independent number, nothing in the pipeline would have flagged it.

### The two rules this yields

1. **A verdict must print the evidence it rests on.** `0 of 0` and `0 of 35` give the same
   conclusion and are distinguishable only because the denominator is shown. A verdict
   string without its denominator cannot be checked by anyone, including its author.
2. **A zero denominator must raise, never report.** Fixed to read `primary_balanced`
   (prereg §12: the balanced minimum-replicate subset is primary) and to raise on a missing
   block or an empty denominator.

This generalizes past this project: **the last defect you find is the one whose output you
agreed with.**

## Two published numbers the audit could not see — found by SA-ARCHIVE

Both were mine, both were in the manuscript, and both survived because **the audit checked
the point estimate and never the quantity the sentence actually asserted.**

### 1. A confidence interval no artifact contained

The paper printed the episode-clustered CI as **[+0.1989, +0.4758]**; the analysis artifact
says **[+0.1974, +0.4736]**. The printed values were my own one-off bootstrap, not the
audited ones — close enough to look right, different enough to be wrong.

> **The audit verified `mean_paired_difference` and never either interval.** A number can
> be adjacent to an audited one and still be unaudited.

Fixed in the paper and in `SCREENED_RESULT.md`; the audit now checks **both** intervals
against the artifact, and I verified the check fires by restoring the wrong value.

### 2. "Roughly 5×" was true of the wrong representation

The paper said charging formation cost makes Raw more efficient **by roughly 5×**. On the
audited basis — formation amortised **per memory**, not per cell — that is:

| | ratio |
|---|---:|
| uncharged, Summary / Raw | 5.58× |
| **charged, Raw / Summary** | **1.08×** |
| charged, Raw / Structured | 4.84× |

**4.84× is Structured. The sentence was about Summary, where the true figure is 1.08×.**
So charging *erases* Summary's advantage rather than reversing it — a weaker and more
accurate claim. Corrected, with audit guards on all three ratios plus a check that the
manuscript no longer contains the overclaiming phrase.

⚠️ Note the near-miss underneath: my own re-derivation gave **4.88×**, agreeing with the
paper, because I amortised formation **per cell** while the audit amortises **per memory**.
Two defensible bases, one of which made a wrong sentence look verified. Same shape as the
76/75-task basis error.

## A single table column built on two different bases (mine)

I handed SA-FIG2 a three-column efficiency table. It verified the numbers before drawing
and **two of the three columns did not hold up.**

**The exposed column mixed bases.** Verified by the Master Agent:

| | all BEARING (n=139) | common-277 join (n=135) |
|---|---:|---:|
| raw | **+0.0380** | +0.0368 |
| summary | +0.1987 | **+0.2054** |
| structured | +0.0622 | +0.0622 |

My table took Raw's **+0.038** from the 139-cell basis and Structured's **+0.062** from the
135-cell join. Both correct; **they do not describe the same objects**, and they sat in one
column as if they did.

**The charged column silently changed amortization.** My figures charged the whole ~7.9k
writer call to *every read* (reuse = 1); the audited accounting amortizes over the measured
**4.86** reuse. That is the same per-cell vs per-memory split that made my "roughly 5×"
claim look verified.

> **A column is a claim that its entries are comparable.** Mine was not, and nothing in the
> audit checked *comparability* — only individual values. The generator now refuses a
> mixed-basis substitution, verified by planting exactly that defect.

### SA-FIG2's own tell, worth keeping

A naive string replace hit **Figure 3's** geometry instead of Figure 4's — both used
`xshift=124pt`. It caught this because **the overfull box stayed at 10.87727pt after an edit
that should have moved it.** *An unchanged measurement after a change is the tell.*

## A named pattern: the pooled number hides the structure that matters

Three times in one day, a correctly-computed pooled figure led to a wrong reading, and each
time the fix was to split it by the variable that actually varied:

| pooled figure | what it hid |
|---|---|
| V2 leakage **26.96%** | 97.71% at ≤2-char golds (multiple choice — measuring the alphabet) vs **4.68%** at >30 chars. The pooled rate tracks answer length, not memory |
| both-arms-fail **~80%** | that the rate is a property of the *pairing*, and collapses on cells where the memory bears on the task |
| task concentration **34.6%** | that MATCHED_CONTROL — the stratum carrying the claim — is **2.2× less concentrated** than RANDOM (max 4 cells/task vs 40) |

None of these was a computation error. Each was a real number that answered a question
nobody had asked, and in two of the three the pooled version pointed the *opposite* way
from the truth.

> **Rule: before quoting a rate, ask what it is an average over, and split it by that.**
> If the split changes the reading, the pooled number does not go in the paper alone.

### Fourth instance, and the subtlest: a matching COUNT read as convergence

Sub-agent K observed that the paired test's **35 non-zero contributors** equalled the
**35-unit flip denominator** pre-computed from the design manifest hours earlier, and was
about to report it as two routes converging.

Checked by the Master Agent: **they are different sets.**

| | |
|---|---|
| non-zero paired contributors | 35 |
| memories with ≥2 BEARING cells | 35 |
| **overlap** | **25** |
| in one set only | 10 each way |

The cardinality matches; the membership does not. *"Two routes agree"* implies mutual
corroboration, and here **neither corroborates the other.**

It also fails an obvious mechanism check: a memory with ≥2 bearing cells can contribute
exactly zero (if all its cells fail both arms), and a memory with one bearing cell can
contribute non-zero. There is no reason for the sets to coincide — and they don't.

> **The subtlest form of the pattern: the number was right, the count was right, and only
> the identity of what was counted was wrong.** Before reporting two measurements as
> agreeing, check that they are measurements *of the same objects*, not merely of the same
> size.

**The mechanism is visible in the rows**, and it is the scarcity finding again:

| case | count | in the executed run |
|---|---|---|
| memories with **≥3** bearing cells contributing **exactly zero** | **4** | all their cells fail both arms |
| memories with **exactly 1** bearing cell contributing **non-zero** | **10** | one bearing cell is enough |

So both directions of non-membership are populated by real, inspectable cases. A memory
with four bearing cells contributing exactly zero *is* the scarcity result — the mechanism
was already written down elsewhere in the report and still was not applied to the sentence
in question.

⚠️ Note when quoting individual examples: the short `mem-…` prefixes are **not unique** —
two distinct memories share each 8-hex prefix in this run. Quote the full id.

K's own framing of why this instance is worse than the pooled-number cases is worth
keeping: those *answered a well-posed question badly*, whereas this one **asserted
corroboration that did not exist** — the kind of sentence that makes a reviewer trust a
table they should check.

## A measurement insensitive to the thing it was measuring (mine)

I reported the manuscript had "roughly zero slack" for further figures, from the **total
page count**: 8 pages before Figure 1, 9 after.

**Total page count cannot answer that question here.** References are uncapped and absorb
the change, so the count stays at 9 across a wide range of added float height. SA-FIG
measured the right observable — **where the body ends** — by inserting dummy floats of
known height and bisecting:

| added float height | body still ends p8? |
|---|---|
| +100pt / +250pt / +290pt / +310pt | ✅ yes |
| +330pt / +400pt | ❌ spills to p9 |

**≈310pt of single-column float height remains free** — about another figure's worth.
Figure 2 went in at ~171pt and the body still ends on page 8, which I confirmed
independently.

> I used the *right criterion in words* — "where does the body end" — and then read the
> **wrong instrument** for it. Page count is a proxy that is flat in the region of
> interest. The same shape as measuring throughput at the wrong prompt length, or reading
> a rate off the wrong denominator.

**Rule: when a quantity must guide a decision, check that the instrument actually moves
when the quantity does.** A bisection against the real observable takes minutes and
replaces an estimate with a bound.

## Make the ruling mechanical where you can

A ruling a human must remember at reporting time is a ruling that will eventually be
forgotten. Sub-agent K's `GOVERNING: task_clustered` field — emitted into the analysis
artifact whenever the clustered CI and the cell-level p disagree — is the better form: the
artifact refuses to be misread, rather than relying on the reader to recall a policy.

Prefer: a field in the artifact > an assertion in code > a line in a doc > an agreement.

## Three of these were mine

Defects #1, #4, #5 were in code or reasoning I authored, and #3 I reported to the user as a
measured result. Each was found by an agent I had asked to check my work. That is the
argument for the cross-checking discipline, and the reason none of them is in the paper.

## Added 2026-10-01 (SA-WRITER, the Writer × Reader factorial)

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 24 | **A stated algebraic identity, asserted in a precommitment and wrong in its sign.** `docs/WRITER_FACTORIAL_PRECOMMITMENT.md` defined the SAME-FAMILY contrast correctly, defined INTERACTION correctly, and then claimed SAME-FAMILY ≡ **−**½ × INTERACTION. With the four arm means `oo, og, go, gg`: `INTERACTION = (gg−og)−(go−oo) = gg−og−go+oo` and `SAME_FAMILY = ½(oo+gg)−½(og+go)`, so the relation is **+**½ | the constructed-ground-truth positive control in `scripts/w3_analyze_factorial.py`, which predicts same-family from a KNOWN interaction and **refused to fire** against the documented sign | the two quantities were computed correctly, so no reported number was wrong. What would have shipped is a **methods sentence that contradicts its own table** — and a reader checking the algebra would be entitled to distrust everything else in the document |

### Why this one is worth keeping even though no number moved

It is the register's standing shape in its mildest costume. The quantities were
right; only the **claim about how they relate** was wrong, and that claim was the
one thing in the section nobody had machine-checked, *because it looked like
algebra rather than like a measurement*.

> **An identity stated in prose is an unverified assertion no matter how
> derivable it is.** It earns the same treatment as a number: compute it, and
> report the residual.

The analysis now emits the residual against **both** signs
(`_same_family_equals_PLUS_half_interaction`, with
`max_abs_difference_against_the_PRECOMMITTED_MINUS_sign` beside it), so the
erratum is visible in the artifact rather than living only in a document
someone has to remember to re-read.

**What caught it was a control built from a known ground truth, not a review.**
The control constructs four arms with an interaction of exactly +0.5, so it knows
what same-family must be. Reading the precommitment would never have caught this:
the sentence is fluent, the surrounding definitions are correct, and the error is
one character.

**The erratum is labelled, not deleted.** The precommitment keeps the original
wording with the correction beneath it, per `retraction is labelling, not
deletion`. A precommitment silently edited after the fact is no longer a
precommitment.

### A near-miss recorded at the same time: a count that is zero by construction

The factorial's cache contains **zero** truncated responses under both readers. That
is true and it is **not** evidence that no truncation occurred: `P1Client` raises
the truncation guard **before** `cache.store`, so a refused truncation is never
written to the cache at all. On a strict arm the cache count is 0 *by construction*.

This was caught before it reached a sentence, by asking what the number was an
average over. The control now states the mechanism in the artifact, reports the
**refused** count from the rows (where truncation is actually visible), and keeps
"none was scored" as a separate line. **A denominator that cannot be non-zero is
not a measurement**, and the previous phrasing would have let a 0 read as a
property of the model rather than of where the guard sits in the call path.

### A second, larger one from the same session: a comparator from a different day

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 25 | **`gpt-oss-120b` is deterministic WITHIN a session and NOT ACROSS sessions, and the factorial's comparator arms were from the previous day.** Re-issuing the **WITHOUT** arm — which contains *no memory*, and whose request bytes were verified byte-identical (500/500 stored `context_sha256`) — returned **different text in 554 of 1,124 cases** a day later, moving the no-memory baseline by **−0.0320** | the pre-registered control *"the WITHOUT arm is writer-invariant"*, which checks a quantity that is **zero by construction unless something is wrong** | the writer contrast would have been **confounded with the session**, by about the size of the effect being measured, with nothing downstream able to separate them. Every writer, same-family and interaction number would have been uninterpretable while looking entirely normal |

**The fix was a re-run, not a caveat.** Both gpt-oss writer arms were
re-executed in the same session as the Gemma arms. F-GATE 5 was **inverted**
for that arm — same memory text means the WITH-arm bytes must *match* the
published request, verified **1,124/1,124**, a strictly stronger assertion than
the differs-check it replaced. Recorded as Amendment 1 in
`docs/WRITER_FACTORIAL_PRECOMMITMENT.md`, made **before any contrast was
computed**, so the design change cannot have been chosen on an outcome.

### Why the project's existing evidence pointed the wrong way

This project had measured A/A determinism at **248/248 identical** and recorded
it as "the endpoint is deterministic at temperature 0". That measurement is
**correct and it is within a single session** — the paired WITHOUT-arm calls it
compares are issued minutes apart in one run. The factorial's original plan
quietly extended it across a day.

> **This is defect #21 exactly, in a new place.** #21 was *"a determinism probe
> measured WITHIN-session repeatability and was read as CROSS-session
> reproducibility"*, found on SciCode memory regeneration. It was written down,
> the register named the shape, and the next arm reproduced it anyway — because
> the stale assumption was not in any one line of code, it was in the choice of
> which files to use as a comparator.

**The asymmetry is itself a finding.** On the identical comparison the Gemma
reader drifted **0 / 1,124**. So cross-session stability is a property of the
**model**, not of the gateway or the cluster — the same shape as
`reports_reasoning_tokens` (defect #18), which was keyed on cluster on a premise
measured on one model. **A stability result for one model is not one for
another**, and `docs/MODEL_ARMS.md`'s A/A rows must now say which session they
describe.

### A third from the same session: a terser writer collapsed two episodes into one memory

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 26 | **Gemma compressed two DIFFERENT 3,979-token segments to byte-identical 68-token summaries.** `memory_id` and `row_id` are content hashes, so the two memories got the **same id** and the schema validator reported 12 `duplicate_row_id` errors on an otherwise clean 2,248-row file. gpt-oss kept the same two segments distinct (524 and 457 tokens) | `validate_file` on the new rows — a step that is easy to skip once the run's own artifact checks have all passed | on this analysis, **nothing**: the join is on `(memory_unit_locator, future_task_id)`, which is positional and cannot collide, and the matched set is 274 rather than 272 — verified, not assumed. On any analysis joining by `memory_id` it would have **silently merged two experiences into one cell** |
| 27 | **A runner hardcoded one arm's identity, so a second arm produced rows whose label contradicted their own measurement.** `gemma_reader_run.py` held a constant `CONDITION_ID` table spelling `gemma4_31B`, and an artifact check asserting `"gemma" in condition_id`. Run with `--reader-arm gptoss_metis` it emitted 570 rows reading `condition_id=lmev2_raw_metis_gemma4_31B_...` beside `reader_model=gpt-oss-120b`. A sibling check, `reasoning_tokens_is_null_never_zero`, asserted Gemma's behaviour as universal and **correctly FAILED the run** — gpt-oss legitimately reports counts | the runner's own artifact gate (`VERDICT: RUN_FAILED`), then me, tracing why | **the 570 rows were VOID and are kept as `results/raw_session_matched_VOID_mislabelled/`.** Had only the condition-id bug existed, the run would have passed and the mislabelled arm could have been pooled with Gemma's. Fixed: `condition_id_for(rep, arm)` derives the label and **fails closed on an unknown arm**; the reasoning-tokens check now keys on `READER_ARMS[...].reports_reasoning_tokens` — defect #18's shape a third time, a model property asserted as a universal one |
| 28 | **The paper's largest recent correction had no machine check, and my first attempt to add one was unreachable code.** SA-FINAL-AUDIT planted `+0.5000 [+0.4000, +0.6000]` as the session-matched reader effect and **both** `audit_claims.py` and `make_figures.py` stayed green: the former never read that paragraph, the latter never reads `main.tex` prose. I then added three guards to `make_figures.py` — and appended to `FAIL` from the **emit block at line ~1144, after the `if FAIL:` exit at line 955**. Two of the three were dead code and passed every plant silently; only the one using `expect()` fired | SA-FINAL-AUDIT found the missing guard; I found the dead code by planting all three defects rather than assuming the new guards worked | the canonical reader-generalization number was **typed and unverifiable**, and a repair that *looks* present is worse than a known gap. Now generated as `\rgSmDiff` etc. from the artifact, with the guards inside `crossbench()` which runs before the exit; all three re-verified by planting |

**It is a result, not only a defect.** The ΔU contrasts cannot see it: both
cells scored identically, so no mean moved. But "the terser writer sometimes
cannot tell two episodes apart" is exactly the kind of cost a reviewer asking
*what does aggressive compression lose?* wants, and it is invisible in every
contrast the factorial reports. It is now measured per writer in the controls
artifact (`writer_collapsed_distinct_segments`) and reported in the result
document.

> **The run's own artifact checks all passed.** They checked row counts,
> identity fields, null handling and replicate balance — everything the script
> knew to look for. The uniqueness invariant lived only in the *shared*
> validator, and a run that never calls it gets a clean verdict from a complete
> set of the wrong checks. **A per-run check list is not a schema.**

Note also the near-miss in the opposite direction: the first instinct on seeing
`duplicate_row_id` is to look for a bug in the writer loop. The rows were
**not** duplicated — 2,248 distinct `(locator, task, replicate, reader)` tuples
produced 2,240 distinct ids. Checking *which field* collided, rather than
assuming a double-write, is what turned an apparent plumbing bug into a finding
about the model.

## Added 2026-10-01 (session-scope sweep) — one assumption surviving two corrections

| # | Defect | Caught by | Would have cost |
|---|---|---|---|
| 28 | **The reader-transfer arm compared two readers executed in DIFFERENT SESSIONS, and no document said so.** `READER_TRANSFER_RESULT.md` and `READER_TRANSFER_PRECOMMITMENT.md` do not contain the word *session*. Re-derived from each cache's `written_at_utc`: the gpt-oss **raw** comparator is **2026-09-29**, gpt-oss **summary/structured** are **2026-09-30**, every Gemma cell is **2026-10-01**. The published decomposition — *"about half of the gain is a weaker reader"*, `\rgWithoutDelta = -0.0688`, printed in the manuscript — rests on a WITHOUT-arm change whose session component was never separated | the session-scope sweep, after defect #25 | the manuscript attributed to *the reader* a baseline shift that is **half the day**. Settled by a session-matched re-run: WITHOUT splits **−0.0327 session / −0.0364 reader**, and ΔU still rises **+0.0982** of the published **+0.1236** — so **the headline survives and only its decomposition was inflated**, by about 2× |
| 29 | **The fix for #25 reproduced #23.** Recording *which row file* a drift figure came from wrote `str(args.oss_rows)` — an absolute `/Users/<name>/` path — into `results/ledgers/`, which is git-tracked and which `README.md` advertises as the reviewer-facing repro slice. Re-scanning found **9 tracked ledger files already carrying 15 such paths**, one inside `results/ledgers/repro/` itself | writing the fix, then scanning the tree the fix wrote into | a **double-blind failure in the artifact tree a reviewer is explicitly pointed at** — #23's exact cost from #23's exact blind spot, one day after #23 was closed |

### #28: a defect closed where it was noticed is not closed

#25 was found, named here, and fixed **by re-running the factorial's comparator
arms in one session**. This register recorded the shape as *"the stale
assumption was not in any one line of code, it was in the choice of which files
to use as a comparator."* The reader-transfer arm had made exactly that choice
two days earlier, and the repair never reached it.

> **#21 → #25 → #28 is one assumption surviving two corrections**, each locally
> complete. The fix for a defect of *scope* has to be a sweep, not a patch at
> the site.

What makes #28 recoverable rather than fatal is that the re-run was cheap and
the result is **reassuring in the direction that matters**: the Gemma arm
reproduced its published numbers to four decimals (expected — Gemma is the
cross-session-stable model), so only the gpt-oss column moved, and the transfer
effect is 79% reader. **A confound that is sized is a caveat; a confound that
is unnamed is a wrong sentence.**

### #29: the pattern was right, its SUBJECT was too narrow

#23's lesson was recorded as *"a credential scanner is structurally blind to a
home path"* and the fix was a **new pattern**. The pattern was never the
problem — re-verified: `scan_text_for_identity` **fires** on all the real
pre-fix strings and is **silent** on every sanitised one.
`gate_identity_scan_tree` had simply only ever been pointed at the HF staging
tree.

> **Same shape as #16 and #18 — a check verified on its home case is not known
> to discriminate elsewhere. For a *scanner*, "elsewhere" is a different TREE,
> not a different string.**

Fixed at source (7 emitters now write repo-relative paths; `tokenizer_provenance`
redacts the home prefix), in the 9 existing artifacts, and in the gate:
`audit_claims.py` now scans `results/ledgers`, `docs/hf_card`, `docs/submission`
and the manuscript. **All four are 0 hits.**

🔴 **The fix is bounded and the remainder is counted, not glossed.** A full-tree
scan still finds **47** occurrences in internal working documents (30 `docs/`,
16 `scripts/`, 1 `src/`), nearly all `PY=/Users/<name>/...` lines in
`Reproduce:` blocks. They do not reach the release or the manuscript, but they
are in the repository and would de-anonymise it if the repo were handed to a
reviewer. Recorded as an open item: **"the gate passes" and "the tree is
clean" are different claims**, and conflating them is how #23 happened.

**Both new gates are proven able to fail.** Planting the shipped string into
`results/ledgers/repro/k3_screened_analysis.json` makes the audit exit **1**
naming the file; restoring it returns **0**. And because a clean scan over zero
files is indistinguishable from a clean scan over many, the gate asserts
`_scanned > 20`: mutating `_SCAN_ROOTS` to a nonexistent tree fails as
*"not a vacuous glob"* rather than passing with an empty `[]`. The sanitisation
re-read **every numeric value** in all 9 files before and after (9,504 in the
largest) to prove a path rewrite moved no measurement.

⚠️ Three of my own near-misses, kept because each is this register's standing shapes:
**(a)** my first mutation test wrote the mutant to `/tmp`, which also moved
`REPO` (derived from `__file__`), so its exit 1 came from a missing artifact
rather than from the guard — *a control must hold one variable*; it was re-run
from inside `scripts/`. **(b)** The audit's first pass recorded the raw
comparator as unrepairable because `results/raw_session_matched/` was an **empty
directory** — it was empty at that instant because the first attempt had just
been voided (#27) and the re-run had not yet written. *An empty directory is a
timestamp, not a verdict.*
**(c)** I wrote "+0.0982 of the published +0.1236, so 79% reader" into the
manuscript and two docs. Both numbers are real and they sit on **different
cell sets** — +0.1268 is the 2-way join (n=276) the paper reports, +0.1236 the
3-way join (n=275) my table needed — so the ratio is *"a single column built
on two different bases"*, the register's own entry, committed by the person
auditing for it. Caught on cross-check against the peer artifact, which quoted
+0.1268 where I had +0.1236. Replaced everywhere by the session-matched
estimate **with its own interval** (`+0.0982`, task-clustered
`[+0.0247, +0.1730]`, excludes zero), which needs no cross-basis division.


---

## Added 2026-10-01 (SA-SWE-FINAL, completing SWE-bench coverage)

| # | defect | found by | consequence |
|---|---|---|---|
| 30 | **The negative control was partly passing on the defect it exists to catch.** `swebench_scorer_control.py` corrupts a gold patch and requires the corruption to score **0.0**. Before DEFECT #21 was fixed, a corrupted patch whose suite printed **no verdict** (`status_lines=0`) *also* returned 0.0 — so "the corruption was detected" and "the tests never ran" were the same observation. Re-running the identical 20 shipped control instances under the fixed scorer flips **6** of them from `corrupt→0.0` to `corrupt→None` (django-11555, -13028, -12713; sympy-24562, -18763, -14531). The shipped artifacts' "negative control 20/20" was **12/20 measured and 6/20 unmeasured**, with 2 escalated | me, by re-running the control rather than reading its stored verdict | the scorer's *discrimination* was never affected — gold/base reproduced **20/20 exactly** — so no reported number moves. But the register's most-repeated shape is here in its sharpest form: **the instrument that proves a check can fail was itself returning an error value as a pass.** A control is not validated by its own stored output; it has to be re-run after any change to the thing it calls |
| 31 | **A positive control run on 12 of 96 instances was read as a property of the runner.** The django scorer control covered 12 recipients and the project treated "the django scorer passes" as settled. Extended to **all 96** (no model calls, ~9 min), the scorer discriminates on **73/96** — on 23 django instances the gold patch does not score 1.0 and/or the base does not score 0.0, so a model's 0.0 there is not evidence its fix was wrong. All 12 original instances reproduced exactly, so this is resolution, not contradiction | me, before running the remaining cells rather than after | **no published number changes** — all 34 django cells that reach a reported number sit on scorer-valid instances, and every contrast is identical whether the 3 non-valid matched cells are kept or dropped. The lesson is the scope of a control's claim: *12/12 licenses a statement about 12 instances, not about a runner.* It is also now the binding constraint on any SWE-bench scale-up — a larger universe adds cells the instrument may not be able to read, so the control must be extended **before** the arm, not after |
| 32 | **A nominally separating contrast, one of three tested on one matched set.** With coverage complete, django's `structured − summary` is +0.1081, 95% CI [+0.027, +0.2162] — excluding zero, the first SWE-bench contrast ever to do so. It is **4 nonzero cells out of 37**, it appears in neither chunk alone (n=13 and n=12, both NOT_ESTABLISHED), it points the opposite way in sympy, and under Bonferroni for the 3 contrasts the interval is [0.0000, +0.2432] | me, on seeing a verdict flip to SEPARATED after a scale-up | caught before it reached a document as a finding. The fix is mechanical rather than remembered: `swebench_multirepo_analysis.py` now emits `ci_familywise_bonferroni_3`, `separates_familywise` and `n_nonzero_cells` beside every nominal interval, and `ORDERING_VERDICT` is driven by the **family-wise** result, with the nominal one preserved as `ORDERING_VERDICT_nominal_uncorrected`. The family-wise interval is positively controlled to still separate on a planted +1.0 signal, so the correction is not a way of never reporting anything |

### The shape all three share with the register's older entries

#30 and #31 are both **a check whose claim is narrower than the use it was put
to** — #30 narrower in *kind* (it could not distinguish detection from
silence), #31 narrower in *scope* (12 instances, not 96). #32 is
**selection after seeing the outcome**, the same shape as *selected subgroups
inflate*, applied to a contrast rather than to a subgroup.

🔴 **A deliberate non-change.** The extended controls are **not** wired into
`check_scorer_control`. The frozen gate still reads the shipped 20/20
artifacts, because changing a gate's input after seeing results is the thing
`SCICODE_SCALEUP_PRECOMMITMENT.md` exists to prevent. The extended artifacts
are a *per-instance diagnostic* that feeds the coverage table's exclusion
classifier, and the two are kept apart on purpose.

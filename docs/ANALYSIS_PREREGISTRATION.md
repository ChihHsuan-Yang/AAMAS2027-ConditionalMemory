# Analysis Pre-Registration

**Fixed 2026-09-29, BEFORE any experimental data exists.** Git history proves the ordering.

> Every definition here is chosen without having seen a single ΔU value. Changing any of
> them after results exist requires an entry in `docs/DECISION_LOG.md` stating what was
> changed, why, and what the pre-registered version would have given. **Both numbers then
> appear in the paper.**

---

## 1. Why pre-register

A sign-flip rate and an interaction share are both threshold-dependent. Choosing the
threshold after seeing the data turns any noisy measurement into a finding. This project's
own operating history contains several instances of exactly that failure — a window chosen
after the data, a subgroup selected for the effect it was then used to demonstrate.

## 2. The noise floor (P1-051) — measured first

Three distinct floors. They are not interchangeable.

| Floor | Definition | Estimator |
|---|---|---|
| **F_exec** | outcome variation across seeds with everything else fixed | repeated identical cells, per arm |
| **F_empty** | variation of the no-memory arm | **free** — the WITHOUT arm is identical across every memory condition for a given task, so its spread across memories *is* a floor |
| **F_judge** | scorer disagreement on **byte-identical** outputs | re-score stored outputs without regenerating |

`F_judge` is expected to be ~0 for deterministic scorers (`norm_phrase_set_match`,
`mc_choice_match`) and nonzero for LLM-judged items. **This is a reason to prefer
deterministically scored questions for the main table** — on LongMemEval-V2, 295 of 451
questions are deterministically scored.

**Reference floor** `F = F_exec` estimated per benchmark, pooled across tasks, reported
with a bootstrap CI.

⚠️ A prior project measured a 9.35% flip rate on byte-identical inputs at temperature 0.
**Do not assume `F_judge = 0` without measuring it.**

## 3. Utility (P1-060)

Per cell, per replicate:

```text
ΔU(m, t, s) = R_with(m, t, s) − R_without(t, s)
```

`R` stays **continuous** wherever the benchmark provides it. Per (m,t), the point estimate
is the mean over replicates, with a bootstrap CI over replicates.

## 4. Robust labels (P1-008, P1-061) — thresholds fixed now

Let `CI(m,t)` be the 95% bootstrap CI of mean ΔU over replicates, and `F` the reference
floor.

| Label | Condition |
|---|---|
| **Robust useful** | `CI_lower > 0` **and** `mean ΔU > F` |
| **Robust harmful** | `CI_upper < 0` **and** `\|mean ΔU\| > F` |
| **Neutral** | `CI` contains 0, **or** `\|mean ΔU\| ≤ F` |

Both clauses are required: statistical separation from zero *and* practical magnitude
above execution noise. A cell may be statistically nonzero yet inside the floor; that is
**neutral**, not useful.

## 5. Sign flip (P1-063) — the headline, defined before the data

A memory `m` exhibits a **robust sign flip** iff there exist tasks `t1`, `t2` with:

```text
label(m, t1) == robust_useful  AND  label(m, t2) == robust_harmful
```

Both cells must independently clear §4. **A raw sign difference is not a flip.**

Reported as: `#(memories with ≥1 robust flip) / #(memories evaluated on ≥2 tasks)`, with
the denominator stated explicitly, plus a Wilson 95% CI.

**Also reported, always, as the honesty comparator:** the naive rate using raw sign
differences with no floor. The gap between the two *is* a contribution — prior work
reports flips categorically and single-shot, so it cannot compute the robust rate.

### Constructed vs natural — stated in the paper

The memory→task **pairing** is constructed by us; the **memories** are naturally occurring.
So we report a *sign-flip rate over a defined task set*, **never** an unqualified "natural
base rate". The selection rule for pairs is deterministic, seeded, and fixed before
measurement.

## 6. Variance decomposition (P1-075)

Mixed-effects model on cell-level ΔU:

```text
ΔU(m,t,s) = μ + a_m + b_t + (ab)_mt + ε_s
```

random effects for memory, task, and their interaction. Report each component's **share of
total variance**, with `F_exec` as an explicit comparator, and bootstrap CIs over
memories (the unit of generalization).

**Fallback if the model does not converge** (fixed now, not later): a two-way
variance-components estimate by method of moments on the balanced sub-design, reported as
such. Non-convergence is disclosed, never silently swapped.

## 7. Semantic distance (P1-064)

`cos(embed(m), embed(t))` under the pinned embedding model
(`Salesforce/SFR-Embedding-Mistral`, dim 4096, verified deterministic).

Bands by **tercile of the observed similarity distribution**, computed **per benchmark**
and fixed before outcomes are examined: NEAR = top third, MID = middle, FAR = bottom.
Terciles rather than absolute cutoffs because cosine scales are not comparable across
corpora.

Primary question: **do robust sign flips occur within the NEAR band?** A flip inside the
retrieval neighbourhood is the sharpest result available, because it is where neighbourhood
averaging is assumed safe.

## 8. Similarity vs utility (P1-065)

Spearman ρ between `cos(m,t)` and mean ΔU, with a bootstrap CI, overall and per band.
Also: the fraction of high-similarity cells that are robustly harmful.

⚠️ **Frame as measurement, not discovery.** "Relevance is not utility" is stated in prior
abstracts; cite them (see `docs/LITERATURE_BOUNDARY.md`).

## 9. Representation comparison (P1-066)

Paired over the **same source episode** — the three representations are matched by
construction, so the comparison is within-episode. Report paired differences in mean ΔU,
robust-useful rate, and robust-harmful rate, with bootstrap CIs over episodes.

**Each representation is charged its own formation cost** in the efficiency analysis.

## 10. Efficiency frontier (P1-074)

x = memory tokens **exposed to the reader**; y = task reward. Points for No-Memory,
Keep-All, Top-k at several k, and Oracle, crossed with representation. Oracle is labelled
**non-deployable headroom**, never a method.

## 11. Multiple comparisons

Many cells are tested. Per-family Benjamini–Hochberg at q = 0.10 for cell-level labels
feeding a reported rate; the raw uncorrected count is reported alongside.

## 12. Adaptive replication (P1-058) — and its bias

Replicates are allocated preferentially to near-zero effects, apparent sign flips, main
table cells, and surprising harmful cases.

🔴 **This makes replicate count non-random, which biases naive pooling.** Mitigations,
fixed now: (a) report the replicate count per cell; (b) compute headline rates on the
**balanced minimum-replicate subset** as the primary number, with the adaptively-augmented
estimate as secondary; (c) never compare CI widths across adaptively-replicated groups as
though they were equally sampled.

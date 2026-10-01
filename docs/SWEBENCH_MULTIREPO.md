# SWE-bench beyond django — the sympy arm, and the cap that bounds the universe

**Written 2026-09-30 (SA-SWE-FULL).** Every number below was re-derived from an
executed artifact in this session; none is quoted from the manifest or from a
prior report without re-computation. Where my re-derivation disagreed with a
prior figure, the disagreement is recorded rather than smoothed.

## 0. Headline

**django-only was never a harness constraint, and it is now over.** sympy ran
end-to-end on the first attempt: 11 cells × 3 representations = **33 rep-cells,
42 model calls, zero write failures**. SWE-bench is now a **two-repo** result.

But the arm is **still underpowered, and more so than the cell count suggests**:

| | matched cells | ordering verdict |
|---|---:|---|
| django/django | **13** | NOT_ESTABLISHED |
| sympy/sympy | **4** | NOT_ESTABLISHED |
| **pooled** | **17** | **NOT_ESTABLISHED** |

**No representation contrast separates from zero in either repo or pooled.**
Adding sympy did not rescue the comparison; it widened the basis and left the
verdict unchanged. That is the honest outcome and it is reported as such.

---

## 1. Task 1 — the sympy claim, verified before acting on it

The manifest (§3) asserts four things. I checked each independently.

| claim | verdict | evidence |
|---|---|---|
| sympy has a runner entry in `REPOS` | ✅ **TRUE** | `scripts/swebench_pilot_v2.py:87` — `Runner("pytest", "/tmp/swebench/venv_sympy39/bin/python")` |
| the scorer control passes | ✅ **TRUE** | `check_scorer_control(['…scorer_control_sympy.json'])` → `(True, "8/8 across runners ['pytest'], negative control 8/8")` |
| the venv exists | ✅ **TRUE** | `/tmp/swebench/venv_sympy39/bin/python` → Python **3.9.6**, with the forced pins `py==1.10.0`, `mpmath==1.2.1` present |
| the pairs are in the manifest | ✅ **TRUE** | 13 sympy rows; **11** survive `is_single_file_solvable` + dedup-by-recipient |

🔴 **One manifest figure is wrong, and it is the headline one.** §3 and §5 of
`COVERAGE_MANIFEST.md` say the scorer control is **"20/20 with negative control
20/20"** and attribute it to sympy. Re-derived:

| artifact | n_pass / n_attempted | negative control | runner |
|---|---:|---:|---|
| `scorer_control_sympy.json` | **8 / 8** | 8 / 8 | pytest |
| `scorer_control.json` (django) | 12 / 12 | 12 / 12 | django |
| **union, which is what the gate reads** | **20 / 20** | 20 / 20 | both |

**20/20 is the two-repo union, not sympy's.** sympy's own control is **8/8**.
The claim "sympy has a passing scorer control" is *true*; the number attached to
it in the manifest belongs to a different set. This is the project's own
named defect shape — *a number that is right about the wrong subject* — and the
manifest line should be corrected to **8/8 (sympy) / 20/20 (union)**.

A second limit worth stating rather than glossing: the 8 controlled tasks cover
**8 of the 11** eligible recipients. **`sympy__sympy-16766`, `-21612`, and
`-22914` were scored by a runner never positively controlled on those specific
instances.** All three turned out to be localizer misses and so contribute
nothing to any reported number — but that is luck, not design, and a scale-up
should extend the control to them first.

The endpoint was also probed live before committing to the run (a real POST to
metis/`gpt-oss-120b`, `finish_reason=stop`, 0.4 s) — advertised is not live.

---

## 2. Task 2 — the sympy representation run

```
scripts/swebench_representations.py --repo sympy/sympy --cells 50 \
    --out results/swebench/representations_sympy.json
```

Both inherited gates passed from disk before any measurement:
scorer control **20/20** (union, runners `['django','pytest']`), apply parity
gap **+0.000** (WITH 0/8, WITHOUT 0/8) under `swebench_v2_symmetric`.

| quantity | value |
|---|---:|
| cells selected | **11** (1 multi-file gold fix skipped) |
| distinct donor memories | **5** |
| memories written | 5 (× 3 representations) |
| contagion-dirty bodies excluded | **1** (`sympy__sympy-14248` raw, 1 diff-marker line) |
| write failures | **0** |
| model calls | **42** |
| rep-cells emitted | **33** = 11 × 3 ✅ |
| localizer recall (per task) | **5 / 11 = 45.5%**, Wilson [0.213, 0.720] |

Exit code was not treated as success: the artifact was opened and its row count,
repo field, representation balance (11/11/11) and reward domain were checked.

🔴 **`reward: None` appears 3 times and is never 0.0** — all three are
`edit_status="search_miss"` (an unapplicable edit), correctly excluded rather
than scored as a wrong answer.

---

## 3. Task 3 — sympy on the matched basis

`scripts/swebench_analyze_representations.py` →
`results/swebench/representations_sympy_analysis.json`

Per-representation interpretable denominators **differ** (raw 4, summary 5,
structured 5), so the matched-set rule binds: **4 cells** are interpretable
under all three.

| representation | ΔU mean | CI95 (task-clustered) | helped / hurt / tied | n |
|---|---:|---|---|---:|
| raw | **+0.0000** | [0.0000, 0.0000] | 0 / 0 / 4 | 4 |
| summary | **+0.0000** | [0.0000, 0.0000] | 0 / 0 / 4 | 4 |
| structured | **−0.5000** | [−1.0000, 0.0000] | 0 / **2** / 2 | 4 |

No contrast separates from zero. **ORDERING_VERDICT: NOT_ESTABLISHED.**

### The two structured-harm cells, inspected rather than reported as a rate

A −0.5 mean over 4 cells is two cells, and at that n the rate is not the finding
— the cells are. Both are **WITHOUT = 1.0, WITH = 0.0** with
`edit_status="ok"`, i.e. a real applied edit that failed its F2P test:

* `sympy__sympy-22714` (donor `-11618`, `sympy/geometry/point.py`) — the edit
  changed `im(a)` to `im(a) != 0`; `test_issue_22684` still raises.
* `sympy__sympy-18763` (donor `-13798`, `sympy/printing/latex.py`) —
  `_print_Subs` rewrite; `test_latex_subs` asserts.

Both WITH responses are **clean SEARCH/REPLACE with zero diff markers**, and
both memory bodies passed the contagion screen (`clean: true`). So this is
**not** the v1 diff-contagion artefact recurring — it is a genuine (if n=2)
instance of a structured memory leading the reader to a plausible wrong edit.
**At n=4 with a CI touching zero, it is a case to follow up, not a result.**

---

## 4. Task 4 — the combined multi-repo analysis

`scripts/swebench_multirepo_analysis.py` →
`results/swebench/representations_multirepo.json`

**Pooling is gated, not assumed.** 13 pinned protocol fields (prompt version,
patch format, prompt variant, model, cluster, temperature, reasoning effort,
both token budgets, structured variant, benchmark version, WITHOUT-sharing,
mode) must agree across the two artifacts or the script **aborts**. They agree.
Had they not, these would be two arms, not one dataset.

### Per repo

| repo | rep-cells | localizer recall | interpretable (raw/sum/str) | **matched** |
|---|---:|---:|---|---:|
| django/django | 96 | 21/32 tasks = 65.6% | 16 / 15 / 18 | **13** |
| sympy/sympy | 33 | 5/11 tasks = 45.5% | 4 / 5 / 5 | **4** |

| repo | raw ΔU | summary ΔU | structured ΔU |
|---|---|---|---|
| **django** (n=13) | **+0.1538** [0.0000, +0.3846] | **+0.0000** [−0.2308, +0.2308] | **+0.0769** [0.0000, +0.2308] |
| **sympy** (n=4) | **+0.0000** [0.0000, 0.0000] | **+0.0000** [0.0000, 0.0000] | **−0.5000** [−1.0000, 0.0000] |

### Pooled — with its composition, every time

> **Pooled over 2 repositories: django/django 13 cells + sympy/sympy 4 cells =
> 17 matched cells. django supplies 76.5% of them. This pooled number is
> dominated by one repo.**

That sentence is emitted by the artifact (`_composition_sentence`,
`DOMINATED_BY`), not left to a reader to remember. The flag fires at a ≥60%
share and is proven to stay silent at a 50/50 split.

| representation | pooled ΔU | CI95 (task-clustered) | +/−/= | n |
|---|---:|---|---|---:|
| raw | **+0.1176** | [0.0000, +0.2941] | 2 / 0 / 15 | 17 |
| summary | **+0.0000** | [−0.1765, +0.1765] | 1 / 1 / 15 | 17 |
| structured | **−0.0588** | [−0.2353, +0.1176] | 1 / 2 / 14 | 17 |

| paired contrast | mean | CI95 | separates? |
|---|---:|---|---|
| structured − raw | −0.1765 | [−0.3529, 0.0000] | **no** |
| summary − raw | −0.1176 | [−0.2941, 0.0000] | **no** |
| structured − summary | −0.0588 | [−0.2353, +0.1176] | **no** |

**ORDERING_VERDICT: NOT_ESTABLISHED**, in both repos and pooled.

### Both-arms-fail, on the matched set

| | django (n=13) | sympy (n=4) | pooled (n=17), Wilson CI |
|---|---:|---:|---|
| raw | 5 (38.5%) | 1 (25.0%) | **6/17 = 35.3%** [0.173, 0.587] |
| summary | 6 (46.2%) | 1 (25.0%) | **7/17 = 41.2%** [0.216, 0.640] |
| structured | 6 (46.2%) | 1 (25.0%) | **7/17 = 41.2%** [0.216, 0.640] |

### What pooling does NOT buy here

🔴 **There is still no `F_exec` for SWE-bench, in either repo.** The WITHOUT arm
is byte-identical across the three representations — verified in this session as
**11/11 sympy tasks and 32/32 django tasks** with one prompt sha, one response
hash and one reward each. The design has no A/A replicate, so an execution-noise
floor of 0 would be an artefact of the design rather than a measurement. Adding
a repo does not change this.

**The pooled matched set equals the union of the per-repo matched sets**
(checked in the artifact, not assumed) — cells never cross repos, so pooling
adds cells and never re-pairs them.

---

## 5. Task 5 — `tasks_per_memory=4`: where it binds, and what it is

**Finding: it is a LIVE cap, confirmed. Making it inert is a PROTOCOL CHANGE,
not a bug fix — and a larger one than the manifest's framing implies.**

### Where exactly it is applied

`src/p1mem/adapters/swebench.py:442-443`, inside `select_pairs`:

```python
picked = pool if len(pool) <= tasks_per_memory else rng.sample(pool, tasks_per_memory)
```

A per-memory `random.Random(f"{seed}:{locator}")` subsamples each memory's
candidate pool down to 4. The default is `tasks_per_memory: int = 4` at line
410. It is applied **once**, at manifest build time, and baked into
`data/manifests/swebench_pairs_file_seed20261008.jsonl`. No runner re-applies
it. **I reproduced the shipped 406-row manifest exactly** from
`select_pairs(seed=20261008, tasks_per_memory=4, relatedness=FILE,
min_tasks_per_memory=2, exclude_copyleft=True)` — symmetric difference **0**.

### What it costs, re-derived at both settings

| stage | cap = 4 (shipped) | cap inert | Δ |
|---|---:|---:|---:|
| pairs | **406** | **552** | **+146** |
| memories | 133 | 133 | 0 |
| survive `is_single_file_solvable` | 303 | 416 | +113 |
| in a repo with a working runner | 239 (dj 227 + sy 12) | 344 (dj 328 + sy 16) | +105 |
| **runnable universe** (dedup-by-recipient) | **107** (dj 96 + sy 11) | **117** (dj 102 + sy 15) | **+10** |

The manifest's 406 → 552 and its 107 runnable are both **confirmed**. The
number that matters for the campaign is the last row: **the runnable universe
grows by 10, not by 146** — +6 django, +4 sympy. The 146 extra pairs are mostly
additional *donors for recipients already in the universe*, and the
dedup-by-recipient rule keeps one donor per recipient.

Under an inert cap and today's executions (55 django + 11 sympy), **remaining
runnable would be 51** (django 47 + sympy 4) rather than today's 41.

### 🔴 Why this is a protocol change and not a bug fix

The manifest frames this as "SciCode's equivalent knob was made inert
deliberately; here it silently caps." Two reasons that framing is incomplete:

**1. It re-pairs cells that are already executed.** The cap=4 pair set is a
strict **subset** of the uncapped set, so one might expect relaxing it to be
purely additive. It is not. `select_cells` deduplicates by recipient
**first-wins over the manifest's locator-sorted order**, so a newly admitted,
alphabetically-earlier donor *displaces* the incumbent one. Measured:

| | django | sympy |
|---|---:|---:|
| recipients gained | 6 | 4 |
| recipients lost | 0 | 0 |
| **recipients whose DONOR changes** | **26** | **0** |
| of which **already executed** | **13** | 0 |

Example: `django__django-13033` is paired with donor `-11490` under cap=4;
under an inert cap, donor `-10554` becomes available, sorts earlier, and wins.
**13 of the 55 executed django cells would silently become different cells
under the same name.** Flipping the default would not extend the dataset — it
would partially invalidate it. sympy is unaffected (0 donor changes), so a
sympy-only relaxation is the clean subset of this change.

**2. The SciCode precedent does not transfer as stated.**
`docs/SCICODE_SCALEUP_PRECOMMITMENT.md` §2 makes the knob inert *because the
pilot's direction was already known*, to remove a tunable degree of freedom —
"154 is not a number I picked; it is the number the pool contains." On
SWE-bench the direction is **also** already known (django's point estimates are
in hand). Changing the cap now is therefore a design choice made *after* seeing
results, which is exactly what the SciCode pre-commitment was written to
prevent. The right move is not to copy SciCode's *setting*; it is to copy
SciCode's *discipline* — fix the knob in a pre-commitment before the next run.

### Recommendation (not applied — reported for a decision)

1. **Do not change the default in `swebench.py`.** A default change silently
   re-pairs 13 executed cells.
2. **If the uncapped universe is wanted, build it as a NEW manifest under a new
   name** (e.g. `swebench_pairs_file_seed20261008_uncapped.jsonl`), pre-commit
   it, and treat the re-paired recipients as new cells — never as additional
   data for the existing ones.
3. **Cheapest honest win first:** sympy has **0 donor changes** and **+4
   recipients** under an inert cap. A sympy-only uncapped extension is purely
   additive and costs ~12 cells of compute.
4. **The +146 figure should not be quoted as campaign headroom.** It is
   headroom in the *pair* universe; the *runnable* universe grows by **10**.

---

## 6. Task 6 — coverage by repository

Copy-ready for `COVERAGE_MANIFEST.md` §3. Every column re-derived this session.

| repo | manifest pairs | SFS pairs | runner | runnable (dedup) | presence-arm executed | repr-arm cells | repr rep-rows | matched | status |
|---|---:|---:|:---:|---:|---:|---:|---:|---:|---|
| django/django | 303 | 227 | ✅ | **96** | **55** | **32** | 96 | **13** | partial |
| sympy/sympy | 13 | 12 | ✅ | **11** | 0 | **11** | 33 | **4** | **repr arm COMPLETE** |
| sphinx-doc/sphinx | 48 | 37 | ❌ | 0 | 0 | 0 | 0 | 0 | no runner |
| pydata/xarray | 22 | 9 | ❌ | 0 | 0 | 0 | 0 | 0 | no runner |
| matplotlib/matplotlib | 10 | 10 | ❌ | 0 | 0 | 0 | 0 | 0 | blocked: C build, no Docker on arm64 |
| psf/requests | 4 | 4 | ❌ | 0 | 0 | 0 | 0 | 0 | no runner |
| pytest-dev/pytest | 4 | 2 | ❌ | 0 | 0 | 0 | 0 | 0 | no runner |
| astropy/astropy | 2 | 2 | ❌ | 0 | 0 | 0 | 0 | 0 | blocked: C build |
| **TOTAL** | **406** | **303** | | **107** | **55** | **43** | **129** | **17** | |

### Sum checks (they close exactly)

```
django : runnable 96 = executed 55 + remaining 41   ✅
sympy  : runnable 11 = executed 11 + remaining  0   ✅  <-- newly complete
total  : runnable 107 = executed 66 + remaining 41  ✅
```

🔴 **One manifest correction.** §3 lists `sympy/sympy` SFS pairs as **12** and
django as **227** — both re-derived and **confirmed**. But the summary table in
§4 reads "executed 55 / 107 = 51%, and all 55 are django". That is now stale:
**66 of 107 runnable cells are executed (61.7%), across 2 repos.**

### What "sympy complete" does and does not mean

**All 11 runnable sympy cells under the shipped manifest have been run.** It
does **not** mean sympy is exhausted: under an inert `tasks_per_memory`, sympy
has **15** runnable cells, so 4 remain under that alternative definition. Both
numbers are true of different universes and the §1-of-the-manifest rule applies
— name the universe or the percentage is false against one of them.

---

## 7. Positive controls on the new instrument

A null here would otherwise be indistinguishable from a bad key, a bad path, or
an estimator that cannot move. `--self-test` plants each defect and requires the
guard to fail:

```
$PY scripts/swebench_multirepo_analysis.py --self-test
```

| # | control | result |
|---|---|---|
| 1 | matched set must SHRINK when one representation loses a cell | 6 → 5 ✅ |
| 1b | `reward: None` excluded, never coerced to 0.0 | ✅ |
| 2 | bootstrap must SEPARATE on a planted +1.0 signal | flat [0,0], signal [1,1], diff [1,1] ✅ |
| 2b | …and must NOT separate on a symmetric +1/−1 mix | [−0.5, +0.5] ✅ |
| 3 | protocol gate must ABORT on a planted field mismatch | aborted ✅ |
| 3b | …and pass when fields agree | ✅ |
| 4 | **a per-representation (content-hash) join key must collapse the matched set to 0** | 0 ✅ |
| 5 | dominance flag fires at 9/10, silent at 5/10 | ✅ / ✅ |
| 6 | Wilson interval non-degenerate at k=0 and k=n, `None` at n=0 | [0, 0.228] / [0.772, 1] / None ✅ |

**Control 4 is the one that makes the headline trustworthy.** The house rule
names it: `memory_id` is a per-representation **content hash** in some
artifacts. If this analysis had joined on such a key, the matched intersection
would be **empty** and "NOT_ESTABLISHED" would have been printed from no data —
the project's single most dangerous recorded defect shape. Planting that key
yields exactly 0, so the observed **non-zero** matched set (17) is positive
evidence the key joins across representations. In these artifacts `memory_id`
is the donor **instance id** (`sympy__sympy-11618`), not a hash, and `task_id`
is globally unique across repos (verified: zero collisions).

Separately, `scripts/swebench_analyze_representations.py` was re-run against
the stored django artifact and **reproduced `representations_v2_analysis.json`
byte-for-byte**, so the per-repo django block here is the same object the
earlier report describes.

Full suite: **629 passed**.

---

## 8. Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3   # system python3 is 3.9 and breaks pytest

# the sympy arm (42 calls, ~2 min)
$PY scripts/swebench_representations.py --repo sympy/sympy --cells 50 \
    --out results/swebench/representations_sympy.json

# matched-basis analysis, sympy alone
$PY scripts/swebench_analyze_representations.py \
    --src results/swebench/representations_sympy.json \
    --out results/swebench/representations_sympy_analysis.json

# positive controls FIRST, then the pooled analysis
$PY scripts/swebench_multirepo_analysis.py --self-test
$PY scripts/swebench_multirepo_analysis.py \
    --src results/swebench/representations_v2.json \
    --src results/swebench/representations_sympy.json \
    --out results/swebench/representations_multirepo.json

$PY -m pytest tests/ -q      # 629 passed
```

## 9. Artifacts

| path | what |
|---|---|
| `results/swebench/representations_sympy.json` | 33 rep-cells, 42 calls, the sympy arm |
| `results/swebench/representations_sympy_analysis.json` | sympy matched basis, n=4 |
| `results/swebench/representations_multirepo.json` | per-repo + pooled, with composition fields |
| `scripts/swebench_multirepo_analysis.py` | the pooling instrument + 9 positive controls |
| `logs/sa_swe_full/reps_sympy.log` | the run log |

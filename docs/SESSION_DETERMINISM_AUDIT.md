# Session-scope audit of every determinism / reproducibility claim

**Written 2026-10-01.** A sweep of the repo, the scripts, the tests and
`../overleaf/main.tex` for every assertion of determinism, byte-identity,
reproducibility, an A/A control, or a zero noise floor — classifying each by
whether the evidence behind it is **WITHIN-session** or **CROSS-session**.

> **This is a scoping exercise, not a retraction.** Every measurement audited
> here stands. The question is what each one *licenses*. Most are
> within-session, and within-session is usually the right scope — the defect is
> only ever claiming more than was measured.

## The distinction, and why it is not pedantic

Defects #21, #22 and #25 are one mistake in three places: a quantity measured
inside a single run was read as a property of the endpoint in general.

| | within-session | cross-session |
|---|---|---|
| `gpt-oss-120b`, byte-identical WITHOUT requests | **248/248 identical** | **554/1,124 texts DIFFER** |
| `gemma-4-31B-it`, same comparison | **248/248 identical** | **0/1,124 differ** |

Re-derived for this audit from `results/repr_scaleup/eval_cache.jsonl`,
`results/gemma_reader/transfer_cache.jsonl`,
`results/writer_factorial/factorial_cache.jsonl` and the two row files named in
§2. The within-session A/A pairs are **not** merely same-day: measured from the
caches' own `written_at_utc`, the two calls in each pair sit **54–178 s** apart
(gpt-oss) and **608–1,699 s** apart (Gemma). The whole gpt-oss A/A run spans
**0.096 h**.

**Cross-session stability is a property of the MODEL, not the cluster or the
gateway** — both readers above serve from the same metis endpoint and only one
drifts.

---

## 1. The claim table

Scope codes: **(a)** within-session, correctly scoped · **(b)** within-session,
OVERCLAIMED as general · **(c)** cross-session evidence · **(d)** cannot tell
from what is written — itself a defect.

### Already correctly scoped — no change needed

| # | Claim | Location | Evidence | Scope | Verdict |
|---|---|---|---|---|---|
| 1 | "deterministic WITHIN a session, NOT ACROSS sessions" | `MODEL_ARMS.md` §"🔴 gpt-oss-120b is deterministic WITHIN…" | 1,124-row re-issue, both readers | **(c)** | ✅ the reference statement |
| 2 | Defect #25 entry | `DEFECT_REGISTER.md` | same | **(c)** | ✅ |
| 3 | Defect #21, #22 entries | `DEFECT_REGISTER.md` | 0/8 and 0/12 regeneration vs ground truth | **(c)** | ✅ |
| 4 | "The endpoint drifted between 09-29 and 09-30… Within a session it is exactly deterministic" | `README.md` §12 of the caveat list | cross-session probe, 12 calls | **(c)** | ✅ names both scopes |
| 5 | "The Raw arm and the new arms were measured on DIFFERENT DAYS" | `REPRESENTATION_RESULT.md` | 302/570 text differ; same-session re-contrast at n=99 | **(c)** | ✅ model entry: sizes the drift AND re-runs the contrast |
| 6 | Same, restated for consumers | `docs/hf_card/README.md` §"the WITHOUT arm renders byte-identical context…" | same | **(c)** | ✅ |
| 7 | "the same seed reproduces byte-identically and a different seed differs" | `MEMORY_UNIT_LMEV2.md` L88-89; `main.tex` L553-555 | `build_lmev2_units.py` assertion | **n/a** | ✅ pure-Python seeded pairing, **no endpoint call** — session cannot apply |
| 8 | embedding determinism, "cosine of identical texts exactly 1.0" | `main.tex` L765-766 | `src/p1mem/embed.py` | **n/a** | ✅ local model, deterministic by construction |
| 9 | "No `F_exec` exists for SWE-bench… a 0 would be an artefact of the design" | `COVERAGE_MANIFEST.md` §3; `SWEBENCH_MULTIREPO.md` L191 | WITHOUT arm shared 32/32 | **n/a** | ✅ refuses the floor rather than reporting 0 |
| 10 | SciCode `F_exec` **non-zero**, 5/135 | `scaleup_analysis.json`; `SCICODE_RESULT.md` §5 | WITHOUT arm across representations, one run | **(a)** | ✅ and it is the counterexample to any universal determinism claim: **within one session, on a different benchmark, this endpoint is NOT deterministic** |

### Rewording applied by this audit

| # | Claim | Location | Evidence actually behind it | Scope | Rewording |
|---|---|---|---|---|---|
| 11 | **A/A determinism 248/248** | `MODEL_ARMS.md`; `READER_TRANSFER_RESULT.md`; `WRITER_FACTORIAL_RESULT.md`; `writer_factorial_controls.json`; `reader_transfer_controls.json` | WITHOUT-arm pairs **inside one run**, 54–178 s apart (gpt-oss) / 608–1,699 s (Gemma) | **(b)** | now says *within-session*, with the measured intra-pair gap |
| 12 | "the endpoint IS deterministic at temperature 0" | `RESULTS_LEDGER.md` row 43c | 30 calls in **10.13 s**, one process | **(b)** | scoped to within-session |
| 13 | "The reader is genuinely deterministic at temperature 0" | `PILOT_VERDICT.md` L20 | same probe | **(b)** | scoped |
| 14 | "The endpoint **is** deterministic" | `POSITION_EFFECT.md` L11-13 | same probe | **(b)** | scoped |
| 15 | "The reader is deterministic at temperature 0, so the residual variance is exactly zero" | `ADDITIVE_NULL_AND_DECOMPOSITION.md` L47-49 | 0/1,157 replicate disagreement, replicates **≤16 s apart** | **(b)** | scoped; the identifiability conclusion is unchanged |
| 16 | `F_exec = 0`, "real temperature-0 determinism" | `docs/hf_card/README.md` §11 | same | **(b)** | scoped |
| 17 | "The reader is deterministic at temperature 0 — verified 6/6 byte-identical" | `main.tex` L798-801 (comment) | determinism probe | **(b)** | scoped |
| 18 | "our reader is deterministic" | `main.tex` L761 | 0/1,157 | **(b)** | scoped to within-session |
| 19 | `F_judge = 0/240` | `F_JUDGE_MEASUREMENT.md`; `HANDOFF_CURRENT.md` L422 | 408 judge calls, one run | **(d)** → **(a)** | the doc is exemplary about *what kind* of zero this is but never says **when**; session scope added |
| 20 | Gemma "verified deterministic, 3/3 byte-identical" | `GEMMA_ENDPOINT_PROBE.md` L26, L197-198 | 3 calls, one probe | **(b)** | scoped — note Gemma later measured 0/1,124 cross-session, so this one *does* generalise, but that is a **second** measurement, not this one |
| 21 | `reasoning_effort` inert, "determinism control (3/3 identical)" | `MODEL_ARMS.md` L59 | same probe | **(b)** | scoped |
| 22 | **Reader-transfer WITHOUT-arm change is "a weaker reader"** | `READER_TRANSFER_RESULT.md`; `main.tex` §readertransfer; `\rgWithoutDelta` | gpt-oss **2026-09-29/09-30** vs Gemma **2026-10-01** | **(c), unlabelled** | 🔴 **the largest finding of this sweep — see §2** |

---

## 2. 🔴 The reader-transfer contrast is cross-session, and nothing said so

**This is defect #25's shape in a place the register does not list.** The
reader-transfer arm compares two readers whose runs are **one to two days
apart**, and neither `READER_TRANSFER_RESULT.md` nor
`READER_TRANSFER_PRECOMMITMENT.md` contains the word *session* anywhere.

Session structure, re-derived from each cache's own `written_at_utc`:

| arm | source | session |
|---|---|---|
| gpt-oss **raw** comparator | `results/deltau_screened/cells.jsonl` | **2026-09-29** |
| gpt-oss **summary/structured** | `results/repr_scaleup/cells.jsonl` | **2026-09-30** |
| **Gemma**, all three | `results/gemma_reader/transfer_cells.jsonl` | **2026-10-01** |

The quantity at risk is the WITHOUT arm — which contains **no memory**, so a
reader change is the only intended difference, and a session change is an
unintended one of the same kind.

| representation | reported WITHOUT change (Gemma − gpt-oss) | measured gpt-oss session drift | drift as a share |
|---|---:|---:|---:|
| **raw** | **−0.0691** | **−0.0327** | **47%** |
| summary | −0.0584 | −0.0316 | 54% |
| structured | −0.0632 | −0.0290 | 46% |

The drift column is not an estimate and not a transfer from another
representation: it is the *same* gpt-oss WITHOUT cells re-executed, joined per
cell.

🔴 **For raw it is a direct three-way measurement, because a session-matched
gpt-oss raw run EXISTS.** It was voided for a labelling defect (register #27 —
`gemma_reader_run.py` stamped a hardcoded Gemma `condition_id` onto gpt-oss
rows) and kept at
`results/raw_session_matched_VOID_mislabelled/raw_gptoss.jsonl`. **The label is
void; the measurements are real**, were produced on **2026-10-01**, the same
session as every Gemma cell, and 568 of 570 rows carry a non-null
`reward_without_memory`. On the **275** cells present in all three files:

| raw WITHOUT arm | mean |
|---|---:|
| gpt-oss **2026-09-29** (the published comparator) | 0.1055 |
| gpt-oss **2026-10-01** (same session as Gemma) | 0.0727 |
| Gemma **2026-10-01** | 0.0364 |

| component | value |
|---|---:|
| reported change (Gemma − gpt-oss 09-29) | **−0.0691** |
| **session** (gpt-oss 10-01 − gpt-oss 09-29) | **−0.0327** |
| **reader**, session-matched (Gemma − gpt-oss 10-01) | **−0.0364** |

**The two components are nearly equal.** The reader effect is real and survives
session-matching; it is **about half** the size the published decomposition
attributes to it. This corrects the audit's own first pass, which recorded the
raw comparator as unrepairable — the repair material existed in a directory
named *VOID*, and *void for a labelling defect is not void for every purpose*
(the rows' `reader_model` field is correct; only `condition_id` is wrong).

**What this does and does not touch.**

* The **headline transfer result is unaffected in direction**: the
  representation ordering raw > summary > structured reproduces under Gemma,
  Raw's within-memory BEARING − MATCHED_CONTROL interval excludes zero under
  both readers, and those are *within-reader* contrasts that difference the
  session term out.
* What is affected is the **decomposition sentence** — "about half of the gain
  is a weaker reader, not a better memory", built on `\rgWithoutDelta`. Roughly
  half of *that* half is, on the measured drift, attributable to the day rather
  than to the reader. The claim "Gemma is unaided weaker" survives, because the
  drift (−0.03) does not cover the whole change (−0.069); the *share* does not
  survive as a clean reader attribution.
* It is **not** correctable from the stored artifacts as they stood when this
  audit was written. A session-matched gpt-oss comparator for the raw arm did
  not then exist.

  > ⏱ **Superseded 2026-10-01 04:20, by the Master Agent.** This sentence was
  > true when measured and is now stale — `results/raw_session_matched/` was
  > empty *at that instant* because the first attempt had just been **voided
  > for mislabelling** (defect #27: `condition_id` said `gemma4_31B` on
  > gpt-oss rows) and the corrected re-run had not yet written. The gpt-oss
  > arm has since landed (**570 rows**, `condition_id`
  > `lmev2_raw_metis_gptoss120b_readertransfer_v1`, `reader_model`
  > `gpt-oss-120b`, `reasoning_tokens` all int) and the Gemma arm is running.
  > The contrast **is** correctable, by re-measurement rather than from stored
  > artifacts, and `scripts/raw_session_matched_analysis.py` — committed with
  > its falsification criteria *before* the data existed — will settle it.
  >
  > *An empty directory is a timestamp, not a verdict: this is the audit's own
  > subject matter, applied to the audit.*

### 2b. SETTLED for `raw` — the session-matched run landed, and the effect survives

As of 2026-10-01T03:34 `results/raw_session_matched/` holds **both** arms,
correctly labelled, **both executed 2026-10-01**: `raw_gptoss.jsonl`
(`condition_id lmev2_raw_metis_gptoss120b_readertransfer_v1`, 570 rows) and
`raw_gemma.jsonl` (570 rows). Re-derived here on the **275** cells present in
the published comparator and both new arms:

| quantity | gpt-oss 09-29 (published) | gpt-oss 10-01 | Gemma 10-01 | cross-session change | **SESSION** | **READER (session-matched)** |
|---|---:|---:|---:|---:|---:|---:|
| WITHOUT arm | +0.1055 | +0.0727 | +0.0364 | −0.0691 | **−0.0327** | **−0.0364** |
| WITH arm | +0.2982 | +0.2909 | +0.3527 | +0.0545 | −0.0073 | **+0.0618** |
| **ΔU** | +0.1927 | +0.2182 | +0.3164 | **+0.1236** | **+0.0255** | **+0.0982** |

Three things follow, and the first is a check on the rest:

1. **The new Gemma arm reproduces the published one to four decimals**
   (+0.0364 / +0.3527 / +0.3164 on both). Gemma is cross-session stable — the
   0/1,124 result — so this is the expected agreement, and it is what makes
   the gpt-oss column the only thing that moved.
2. **The headline survives.** ΔU still rises under Gemma session-matched:
   **+0.0982**, task-clustered **[+0.0247, +0.1730]**, which excludes zero
   (`results/ledgers/raw_session_matched_analysis.json`, independently
   re-derived here).

   ⚠️ **Do not divide it by the published +0.1268.** That figure is the
   **2-way** join (gpt-oss 09-29 ∩ Gemma, n=276); the three-way join used in
   the table above is n=275 and gives +0.1236 for the same contrast. Both are
   correct and they describe **different cell sets**, so a ratio across them
   is this project's own *"a single column built on two different bases"*
   defect. The defensible statement is that the session-matched estimate
   **excludes zero on its own interval** and that each mean lies inside the
   other's CI — which is what the peer artifact's
   `SURVIVES_SESSION_MATCHING` verdict rests on. *(I made exactly this error
   first and caught it on cross-check; it is recorded rather than quietly
   fixed.)*
3. **The decomposition sentence was the overclaim, and by about a factor of
   two.** The WITHOUT-arm change splits almost evenly: **−0.0327 session** vs
   **−0.0364 reader**. "About half the gain is a weaker reader" was computed
   against a baseline that had itself drifted; session-matched, the weaker-
   baseline share of the ΔU change is **−0.0364 / +0.0982**, not 54% of
   +0.1236.

**Action taken:** every published number is kept unchanged and is correct for
the arms it describes; the confound is named and now *sized* at each site.
Re-stating the decomposition on the session-matched arms is a change to a
published result and is handed back as a decision, not made here — but the
measurement that would settle it now exists, and §2b is it.

---

## 3. F_exec and F_judge — precisely what they license

Both are **correct as within-session floors** and neither is retracted.

### `F_exec = 0` on LongMemEval-V2

Re-derived: `results/deltau_screened/analysis/` and the pilot/official
`01_noise_floors.json` give `point = 0.0` on all three scales, with the positive
control firing at **0.5098** (pilot) / **0.5093** (official) on 249 planted
cells — so the estimator is **proven able to report non-zero**.

Measured from `results/deltau_screened/cache.jsonl`: across **2,314** cells with
≥2 replicates, the within-cell replicate calls are **0.0–15.7 s apart**
(median 0.0 s), all inside a single 0.81 h run.

**It licenses:** re-issuing an identical request *moments later, in the same
run* returns an identical reward, over 1,157 cells. Therefore a replication
queue buys nothing, the prereg §4 floor clause is vacuous, and the variance
decomposition is unidentifiable for lack of residual scale. All three
conclusions are **unchanged by this audit** — they are statements about one
run's internal consistency, which is exactly what was measured.

**It does NOT license:** that the same cell re-run tomorrow scores the same.
Measured on the adjacent arm, it does not — **554/1,124** WITHOUT texts and
**82** rewards moved in one day. `F_exec = 0` is a floor on *execution* noise,
not on *session* noise, and the project has no F_session.

⚠️ And it is **benchmark-specific even within a session**: SciCode's equivalent
A/A is **5/135 = 3.7%** disagreement, inside one run. A sentence of the form
"our reader is deterministic" is already false of one of the three benchmarks.

### `F_judge = 0 / 240`

`results/f_judge/f_judge_measurement.json`, generated
2026-10-01T02:27:59Z — 48 stored outputs × 6 passes, **408 judge calls in one
run**. `F_JUDGE_MEASUREMENT.md` is the most carefully scoped document in the
project: it already states the zero is *endpoint determinism, not rubric
robustness*, rules out a server cache two ways, and lists the five factors the
floor is conditional on. **The one conditioning factor it omits is the
session.**

**It licenses:** re-scoring a stored output six times within one run returns the
same label — and the same characters, `reason` field included — on 240
comparisons, bounded at **≤1.5% at 95%** (the CI, not the point estimate, is the
result).

**It does NOT license:** that re-scoring those same outputs next week agrees.
That is unmeasured. Given the judge is `gpt-oss-120b` — the model measured to
drift 554/1,124 across a day — the cross-session judge floor should be presumed
**non-zero until measured**, and the 156-question stratum's re-scoring plan
needs it.

---

## 4. Scoping `MODEL_ARMS.md`'s A/A rows

The doc already carries the governing sentence ("This does not contradict the
248/248 A/A result — that measurement is within one session"). Three things were
missing and are now fixed:

1. The **A/A rows themselves** said only "byte-identical requests, separate
   calls" — a reader meeting the table first gets an unscoped determinism claim.
   Each now names its session and its measured intra-pair gap.
2. The register, `MODEL_ARMS.md` and `WRITER_FACTORIAL_RESULT.md` quoted the
   same drift as **−0.0320** / **−0.0303** without saying they are different
   row files. Both re-derive exactly, and they are **not** a discrepancy:

   | row file | n | reward differs | text differs | mean WITHOUT change |
   |---|---:|---:|---:|---:|
   | `factorial_cells_gemma.jsonl` | 1,124 | 84 | 554 | **−0.0320** |
   | `factorial_cells_gptoss.jsonl` | 1,124 (1,122 non-null) | 82 | 554 | **−0.0303** |

   Same comparison, two writer arms' WITHOUT rows; the gptoss file carries 2
   null rewards that leave the denominator. Each site now names its file.
3. `aa_control()` in `scripts/gemma_reader_controls.py` and
   `scripts/w4_factorial_controls.py` writes `_what: "… => the endpoint is
   deterministic at temperature 0"` into the artifact. Per *"prefer a field in
   the artifact over a line in a doc"*, the string itself is now scoped, so the
   artifact cannot be misread by someone who never opens this file.

---

## 4b. A second defect found while fixing the first (not a determinism claim)

Making `w4_factorial_controls.py` record *which row file* its drift figure came
from wrote `str(args.oss_rows)` into the artifact — an **absolute
`/Users/<name>/` path**, straight into `results/ledgers/`, which is
**git-tracked** and which `README.md` advertises as the reviewer-facing repro
slice. That is **defect #23 reproduced by the fix for defect #25**.

Scanning the tree then found it was **not** mine alone: **9 tracked ledger
files** already carried **15** absolute home paths, including
`results/ledgers/repro/k3_screened_analysis.json` — inside the directory the
README points reviewers at.

> **GATE 2b's pattern was right; its SUBJECT was too narrow.** Verified by
> running the real `scan_text_for_identity` over the real pre-fix strings: it
> **FIRES** on both, and is **SILENT** on the sanitised forms. The gate simply
> never ran over `results/ledgers/` — `gate_identity_scan_tree` is only called
> on the HF staging tree. *A scanner aimed at one tree certifies nothing about
> another.*

Fixed in three places, source first:

| | |
|---|---|
| emitters | 7 scripts now write **repo-relative** paths via `_rel_to_repo`; `tokenizer_provenance` redacts the home prefix to `~/` |
| existing artifacts | all 9 sanitised — **and every numeric value re-read before and after** (9,504 in the largest file) to prove a path rewrite moved no measurement |
| the gate | `audit_claims.py` now scans `results/ledgers`, `docs/hf_card`, `docs/submission` **and the manuscript** |

**Scope of the fix, stated rather than implied.** The gate covers
`results/ledgers`, `docs/hf_card`, `docs/submission` and the manuscript — the
tracked artifacts and the reviewer-facing surfaces — and all four are now
**0 hits**. A full-tree scan still reports **47** occurrences in internal
working documents (30 in `docs/`, 16 in `scripts/`, 1 in `src/`), almost all
in `Reproduce:` blocks of the form `PY=/Users/<name>/miniconda3/bin/python3`.
Those are **not** fixed here and are a **lower but non-zero** exposure: they
do not ship to HuggingFace and are not the submission, but they are in the
repository, so **if the repo itself is ever shared with reviewers they are a
de-anonymisation**. Left as an explicit, counted item rather than silently
included in a "clean" verdict — an unscanned tree and a clean tree must not
read the same, which is the whole lesson of #23.

**The new gate is proven able to fail, both ways.** Planting the exact string
that shipped into `k3_screened_analysis.json` makes the audit exit **1** naming
the file; restoring it returns exit **0**. And because a clean scan over zero
files looks identical to a clean scan over many, the gate asserts
`_scanned > 20` — mutating `_SCAN_ROOTS` to a nonexistent tree fails on
*"identity scan actually opened files (not a vacuous glob)"* rather than
passing with an empty `[]`.

⚠️ Note on that mutation test: the first attempt wrote the mutant to `/tmp`,
which also moved `REPO` (derived from `__file__`) and made the script exit 1
for an unrelated missing artifact. **A control must hold one variable** — the
mutant was re-run from inside `scripts/` so only `_SCAN_ROOTS` changed.

## 5. What a future agent must do

1. **Never compare arms executed in different sessions** without either
   re-running one in the other's session or measuring the drift on that exact
   cell set. The factorial did the former (Amendment 1); the reader-transfer arm
   did neither.
2. **State the session with every determinism number.** "248/248" is not a
   claim until it says over what interval.
3. **A stability result for one model is not one for another** — Gemma 0/1,124
   vs gpt-oss 554/1,124 on the identical comparison.
4. **A stability result for one benchmark is not one for another** — LongMemEval
   0/1,157 vs SciCode 5/135, both within-session.
5. **There is no measured F_session**, for any model, benchmark or scorer. The
   two numbers that exist (gpt-oss 554/1,124 at one day; Gemma 0/1,124) are a
   single interval on a single cell set.

## 6. Reproduce

```bash
cd <repo>
PY="$(conda info --base)/bin/python3"   # system python3 is 3.9 and breaks pytest

# A/A counts AND the intra-pair time gaps that make them within-session
$PY - <<'PY'
import json,datetime,statistics
def aa(path):
    g={}
    for line in open(path):
        if not line.strip(): continue
        d=json.loads(line); k=d["key"]
        if k["arm"]!="without_memory": continue
        c=k.get("context_sha256")
        if c is None: continue
        g.setdefault((k["future_task_id"],k["replicate_id"],c),{})[k["memory_repr"]]=(
            d["response"]["content"], d["written_at_utc"])
    p={k:v for k,v in g.items() if len(v)>=2}
    same=sum(1 for v in p.values() if len({x[0] for x in v.values()})==1)
    gaps=[(lambda t:(t[-1]-t[0]).total_seconds())(
          sorted(datetime.datetime.fromisoformat(x[1]) for x in v.values()))
          for v in p.values()]
    print(path, f"{same}/{len(p)} identical",
          f"gap s min={min(gaps):.0f} med={statistics.median(gaps):.0f} max={max(gaps):.0f}")
aa("results/repr_scaleup/eval_cache.jsonl")
aa("results/gemma_reader/transfer_cache.jsonl")
PY

# the cross-session drift, both row files
$PY - <<'PY'
import json
L=lambda p:[json.loads(l) for l in open(p) if l.strip()]
def key(r):
    p=r.get("provenance") or {}
    return (r["memory_representation"],p.get("memory_unit_locator"),
            r["future_task_id"],int(r["replicate_id"]))
A={key(r):r for r in L("results/repr_scaleup/cells.jsonl")
   if r["reader_model"]=="gpt-oss-120b"}
for f in ("factorial_cells_gemma.jsonl","factorial_cells_gptoss.jsonl"):
    B={key(r):r for r in L("results/writer_factorial/"+f)
       if r["reader_model"]=="gpt-oss-120b"}
    c=sorted(set(A)&set(B),key=str)
    pr=[(A[k]["reward_without_memory"],B[k]["reward_without_memory"]) for k in c]
    pr=[(a,b) for a,b in pr if a is not None and b is not None]
    txt=sum(1 for k in c if A[k]["output_without_memory"]==B[k]["output_without_memory"])
    print(f, f"n={len(c)} rewardDiff={sum(1 for a,b in pr if a!=b)}",
          f"textDiff={len(c)-txt} mean={sum(b-a for a,b in pr)/len(pr):+.4f}")
PY

$PY scripts/audit_claims.py                  # must stay green
```

**Exit code 0 is not success** — the counts printed above are the check.

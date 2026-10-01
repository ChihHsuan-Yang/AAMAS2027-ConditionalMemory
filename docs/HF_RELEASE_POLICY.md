# Hugging Face Release Policy

Target: **`AgentsSci/AAMAS2027-ConditionalMemory`** (dataset, **private**, created
2026-09-29 17:34Z). It is no longer empty: as of 2026-10-01 it holds 5,924 rows across
17 files on `main`, with four tags. (This line read "currently empty — `usedStorage:
0`" until v0.4; a stated fact about a mutable object decays exactly like a stated
reason does.)

**Four uploads have occurred**: `v0.1-lmev2-derived`, `v0.2-repr-derived`, `v0.3-scicode-derived`, `v0.4-swebench-metrics` (see the release log below). The repository remains **private**. Each upload is separately authorized; this line is not a standing authorization for the next one.

---

## 🔴 Do not test HF write access with `auth-check`

Verified independently by the Master Agent, 2026-09-29:

| Probe | Our repo | `openai/gsm8k` (we certainly cannot write) |
|---|---|---|
| `GET /auth-check?accessLevel=write` | 200 | **200** ← false positive |
| `POST /commit/main` with an empty body | **400** (malformed, i.e. authorized) | **403** (forbidden) |

`auth-check` returns **200 for a repository we have no write access to**. It also returns
200 **unauthenticated**. Two other probes E tested (`preupload`, the git receive-pack
advertisement) fail the same way.

> **Only the commit probe discriminates.** A "400 malformed" means we got past
> authorization; a 403 means we did not. Any future readiness check must use the commit
> probe **with a negative control** — a repo we know we cannot write. A probe that returns
> success for everything is not a test.

This is the same shape as the two advertised-but-dead endpoint failures: **a capability
signal is not a capability.**

## Upload preconditions — all must hold

1. ✅ `hf` CLI installed (`/Users/bellayang/Library/Python/3.9/bin/hf`, `huggingface_hub`
   0.36.2). No `brew install` needed.
2. ✅ Token present; identity `ChihHsuan-Yang`, admin on `AgentsSci` with `repo.write`.
3. ✅ **`docs/BENCHMARK_LICENSES.md` exists** (Sub-agent A, 10.8 KB). Unblocked.
4. Export gates pass, including the secret scan.
5. Master Agent has reviewed the staging manifest file-by-file.

## Staging, never the repo root

Upload only from a dedicated staging directory. **Never** `hf upload ... .` from the
GitHub repo root — that would ship code, caches, notes, and possibly credentials.

### What may be published

Derived annotations, utility labels, metrics, metadata, benchmark **IDs** and source
references, and the code to reconstruct from the original benchmark.

### What may not

Raw copyrighted benchmark content that its license does not permit us to redistribute;
secrets or tokens; endpoint caches; large transient logs.

Known constraints to encode in the exporter:
- **LongMemEval-V2** — Apache-2.0 (verified from the repo's `LICENSE`).
- **LongMemEval V1** — MIT, **but its filler derives from ShareGPT and UltraChat, which
  carry their own upstream terms independent of that MIT grant.**
- **BEAM** — code MIT, **data CC BY-SA 4.0**. See the ShareAlike ruling below.
- **SciCode** — see `docs/BENCHMARK_LICENSES.md`.

## 🔴 RULING: BEAM ships as a SEPARATE dataset under CC BY-SA 4.0

Sub-agent A's audit found the one licence in this project that constrains **our** release
terms. **CC BY-SA 4.0 ShareAlike is infectious**: any dataset adapted from BEAM must itself
be released under CC BY-SA 4.0. It cannot be folded into an Apache-2.0/MIT release.

**Decision (Master Agent, 2026-09-29):**

| Release | Contents | Licence |
|---|---|---|
| `AgentsSci/AAMAS2027-ConditionalMemory` | LongMemEval V1/V2 + SciCode derived annotations | permissive, per upstream |
| **separate BEAM release** | BEAM-derived annotations only | **CC BY-SA 4.0**, attributing the BEAM authors |

Merging them would either violate ShareAlike or silently relicense everything else. **The
exporter must refuse to place BEAM-derived rows in the main dataset**, and that refusal
needs a test with a negative control — a gate never shown to fire is not known to work.

Aggregate statistics computed over BEAM (counts, rates, means reported in the paper) are
**not adaptations** and are safe to report under any terms. ShareAlike bites on
redistributed derived *records*, not on numbers in a paper.

## Secret scanning must read values, not paths

E's export self-test plants secrets **inside a model-output field**, not just in filenames.
A path-based scan misses those entirely, and model outputs are exactly where a leaked
string would land if a prompt ever echoed one. The gate suite includes negative controls,
so a gate that rejects everything is caught rather than mistaken for working.

## Versioning

Milestones: `schema-v0` · `pilot` · `lmev2-derived` · `beam-derived` · `scicode-derived` ·
`release-candidate` · `submission-snapshot`. Every snapshot must be reproducible from the
GitHub code at a named commit.


---

## Release log

### v0.4 — `v0.4-swebench-metrics`, 2026-10-01 ✅ VERIFIED

**5,924 rows** (LongMemEval-V2 5,643 · SciCode 154 · **SWE-bench Verified 127**),
98 fields, 17 files + `.gitattributes`, private. All nine gates passed. Verified by
**downloading the tag**: the card's own command printed `5924 rows | 0 errors | 1691
warnings`, matching the card's stated expected output exactly, and all 17 files are
byte-identical to what was staged.

🔴 **SWE-bench ships METRICS AND IDS ONLY.** `princeton-nlp/SWE-bench_Verified`
declares no licence, so five fields carry `__WITHHELD_SEE_LICENSE__` on all 127 rows
and are **declared** in `text_fields_withheld`. **37 manufactured `0.0` rewards were
demoted to null** before export (defect 21), verified independently of the converter's
own count against the untouched sources: 37 moved, 179 real rewards unchanged.

`scripts/swebench_to_schema.py` was written for this release; it did not exist.

#### The sentinel distinction is a gate, not a comment

v0.3 and v0.4 withhold text for **opposite reasons**, and the two literals must never
be interchanged:

| | SciCode | SWE-bench |
|---|---|---|
| reason | **persistence** — never written down | **licence** — exists, may not ship |
| literal | `__OUTPUT_NOT_RETAINED_BY_THE_RUN__` | `__WITHHELD_SEE_LICENSE__` |

> Writing the SciCode sentinel on a SWE-bench row would assert that no text exists —
> excusing us from a restriction that does apply. Writing the SWE-bench sentinel on a
> SciCode row would assert a licence restriction Apache-2.0 does not impose. **The
> generic embargo gate cannot see either swap**, because both literals read as
> "withheld" to a check that only asks whether content is present. The converter's
> self-test plants exactly that swap and requires the refusal.

#### What GATE 5b caught, one release after it was built

The v0.4 build **refused** on its first run: the card still promised 5,797 rows against
a 5,924-row release. Re-deriving every card claim across the new total then found
**four more that had decayed** — each true when written, each false once the
denominator moved:

1. **`license: apache-2.0` in the frontmatter.** The Hub renders that as a grant over
   the whole dataset, and it is false for 127 rows whose corpus grants nothing. Now
   `license: other`. *A platform executes metadata* — the same lesson already written
   in that file about `library_name`.
2. "Every row derives from a source whose licence permits redistribution."
3. **`context_budget`'s stated reason** counted 127 `null == null` pairs as a measured
   equality, turning a true 5,797-row fact into a false 5,924-row one.
4. **"`compression_ratio = 1.0` on every raw row"** — the 41 SWE-bench raw rows carry
   `null`, because `memory_tokens` was never measured there.

> **A documented reason is a claim, and it decays.** v0.2 learned this on two nulls;
> v0.4 is the same lesson at release scope. **Re-derive every number in the card at
> each release rather than inheriting it** — and note that three of these four were
> invisible to GATE 5b, which only checks the validator line. The gate caught the one
> number it was built to catch; a sweep caught the rest.

---

### v0.3 — `v0.3-scicode-derived`, 2026-10-01 ✅ VERIFIED

**5,797 rows** (LongMemEval-V2 5,643 + **SciCode 154**), 98 fields, 17 files, private.
All nine gates passed. Verified by **downloading the tag**: the card's own command
printed `5797 rows | 0 errors | 1437 warnings`, matching the card exactly.

🔴 **SciCode ships RAW ONLY — 154 of 462 cells**, and the card says so before any
result. The summary/structured memory text was never persisted and **cannot be
reconstructed** (cross-session regeneration at matched settings is 0/8 byte-identical,
within-session 3/3 — defect 22). **The reward measurements remain valid and are not
retracted**, and nothing was regenerated and presented as the original.

#### Two figures that are not one figure quoted twice

The card cited `0/12` and the register cited `0/8`. Both are real, they are
**different subjects on different corpora** (8 ground-truth LongMemEval summaries at
fully matched settings; 12 Summary memories whose text is on disk), and the card now
carries a table naming each one's subject, settings and source. They corroborate each
other **because** they were taken independently, and they must not be pooled into
"0/20".

#### A prose/data contradiction the gates could not see

The card called the 308 absent cells **"withheld"**. In this schema that word is a
term of art for a *licence* withholding — it is what `text_fields_withheld` is named
after, and that field is `[]` on all 154 SciCode rows. The prose asserted a restriction
the data correctly denied. **No gate can catch this**: every gate was reading the data,
which was right, and the false statement was in the sentence beside it.

---

### v0.2 — `v0.2-repr-derived`, 2026-09-30 ✅ VERIFIED

**Master Agent verified by downloading the tag**, not from the upload's exit code:
**5,643 rows** (raw 4,519 · summary 570 · structured 554), **98 fields**, schema
`p1mem_conditional_memory_utility_v3`, 18 files, private, unauthenticated access → **401**.
`benchmark == longmemeval_v2` on 5,643/5,643.

All seven gates ran; the post-download validator returned **5,643 rows / 0 errors**, matching
the card's documented expected output.

#### Two "deliberately null" reasons that were about to become false

v0.1 wrote *"No faithfulness proxy was run for this representation"* on non-raw rows — a
statement that **could never be false because no such row existed.** The proxy does run at
write time, and all 1,124 new rows carry real scores.

> **A documented reason for a null is a claim, and it decays.** When the data it describes
> changes, the reason becomes a false statement shipped inside a published artifact. Re-check
> every null's justification at each release, not just the nulls themselves.

Also refused: a **single-float** faithfulness column (it would report structured as a flat
1.0 while entity support is 0.8322 on 55/57 memories — hence `faithfulness_detail`), a
back-filled `config_sha256` the runner never reads, verbatim source fragments inside
`faithfulness_detail` under a closed licence (**a leak path the existing gate could not
see**), and all SciCode/SWE-bench rows — both landed mid-task and belong to v0.3/v0.4.

### v0.1 — `v0.1-lmev2-derived` ✅ 4,519 rows, 15 files
Its **first** upload succeeded and was broken: gates passed, exit 0, and every published row
failed the validator published beside it, because redaction added fields after validation.
Found only by downloading and running the card's own command. Gates 4 and 5 exist because of
it.

## Building the inputs — the step that is not in the exporter

🔴 **`export_hf.py` does not migrate schemas.** The result ledgers on disk are
`v1` (`deltau_*`) and `v2` (`repr_scaleup`); the exporter requires `v3` and its
self-test fails with `missing_field:*` if handed a raw ledger. This was not
written down, and rebuilding v0.3 rediscovered it.

```bash
for f in deltau_screened deltau_pilot deltau_official; do
  python3 scripts/migrate_schema_v2.py --in results/$f/cells.jsonl --out /tmp/v3in/$f.jsonl
done
# repr_scaleup carries MODEL-WRITTEN representations and needs two more inputs;
# the migration REFUSES without them rather than publishing a false column:
#   --memory-records  faithfulness was measured at write time; omitting it would
#                     publish a null for a quantity that was in fact measured
#   --parents         without it every derived memory claims no parent, which is false
python3 scripts/migrate_schema_v2.py \
  --in results/repr_scaleup/cells.jsonl \
  --memory-records results/repr_scaleup/memories.jsonl \
  --parents /tmp/v3in/deltau_screened.jsonl /tmp/v3in/deltau_pilot.jsonl \
            /tmp/v3in/deltau_official.jsonl \
  --out /tmp/v3in/repr_scaleup.jsonl

python3 scripts/export_hf.py \
  --results /tmp/v3in/*.jsonl results/ledgers/scicode/cells_v3.jsonl \
  --staging ../hf_staging_v03/AAMAS2027-ConditionalMemory
```

Both refusals are correct behaviour and should not be worked around with a flag.

## GATE 2b — identity, which is not the same gate as secrets

A credential scanner cannot see a de-anonymising string: an absolute home path
has no entropy signature and reads as an ordinary file path. v0.3 staged with
`/Users/<name>/` inside `code/p1mem/schema.py` and **all nine gates passed**.
`gate_identity_scan_tree` now runs over the whole tree and is verified against
a planted macOS path, a planted Linux path, and a clean negative control.

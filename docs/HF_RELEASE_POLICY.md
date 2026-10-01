# Hugging Face Release Policy

Target: **`AgentsSci/AAMAS2027-ConditionalMemory`** (dataset, private, created
2026-09-29 17:34Z, currently empty — `usedStorage: 0`, only `.gitattributes`).

**No upload has occurred. The Master Agent authorizes the first one.**

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

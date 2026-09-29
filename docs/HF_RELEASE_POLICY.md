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
3. 🔴 **`docs/BENCHMARK_LICENSES.md` must exist** (Sub-agent A, P1-027). The exporter
   hard-refuses without it. **This is the one thing blocking a staging directory.**
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
- BEAM, SciCode — pending A's audit.

## Secret scanning must read values, not paths

E's export self-test plants secrets **inside a model-output field**, not just in filenames.
A path-based scan misses those entirely, and model outputs are exactly where a leaked
string would land if a prompt ever echoed one. The gate suite includes negative controls,
so a gate that rejects everything is caught rather than mistaken for working.

## Versioning

Milestones: `schema-v0` · `pilot` · `lmev2-derived` · `beam-derived` · `scicode-derived` ·
`release-candidate` · `submission-snapshot`. Every snapshot must be reproducible from the
GitHub code at a named commit.

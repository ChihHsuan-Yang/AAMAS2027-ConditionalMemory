# Infrastructure Verification — Master Agent audit

Sub-agents C and E delivered the execution infrastructure. **Every load-bearing claim below
was re-verified by the Master Agent by running the code or making the call**, not accepted
on report.

Verified 2026-09-29. Full suite: **124 passed** under Python 3.13.

---

## 1. Response cache — cluster isolation VERIFIED BEHAVIOURALLY

`KEY_FIELDS` has all 12 required components: `benchmark`, `source_item_id`, `memory_repr`,
`memory_id`, `future_task_id`, `arm`, `retrieval_method`, `model_id`, `cluster`,
`prompt_version`, `decoding_params`, `replicate_id`.

Behavioural test run by the Master Agent — store one entry, then vary one field:

| Probe | Result | Required |
|---|---|---|
| identical inputs | **HIT** | hit |
| `cluster` metis→sophia | **MISS** | miss |
| `replicate_id` 0→1 | **MISS** | miss |
| `arm` with→without | **MISS** | miss |
| `model_id` bare→`openai/`-prefixed | **MISS** | miss |
| `prompt_version` v1→v2 | **MISS** | miss |

> **A cache hit can never cross a cluster, arm, replicate, model, or prompt boundary.**

### ⚠️ A false alarm I raised, and what caused it

My first probe reported *"metis key == sophia key: True"* — an apparent catastrophic
collision. **It was my instrument, not the code.** I called `c.make_key(...)`, which does
not exist; the attribute access returned nothing and I compared `None == None`, which is
trivially true. The real API is `store`/`lookup`.

This is the same defect class the project has hit repeatedly: **a check that inspects the
wrong subject reports a confident result.** My grep for key fields also looked only at one
class body and missed the module-level `KEY_FIELDS`, giving five spurious "MISSING"s. Both
were resolved only by exercising real behaviour.

## 2. Truncation guard — VERIFIED AGAINST THE LIVE ENDPOINT

Not a mock. At `max_tokens=16`, `reasoning_effort=high` on Metis, reasoning consumed the
whole budget, `content` came back null, and the client **raised** rather than returning
`""`. The model-pin check also raises on `gpt-oss-120b` vs `openai/gpt-oss-120b` with **no
normalization**, and the pin is enforced on cache hits too.

This matters more than a robustness nicety: an empty completion scored as a response would
push ΔU negative and **manufacture harmful memories** — fabricating the phenomenon the
paper measures.

## 3. Concurrency — 16 workers

Measured on the frozen arm, retries deliberately disabled inside the harness (retrying
would mask the failure rate the benchmark exists to find).

| workers | req/s | p50 s | p95 s | 429 rate |
|---:|---:|---:|---:|---:|
| 1 | 1.022 | 0.971 | 1.611 | 0% |
| 8 | 4.116 | 1.624 | 2.919 | 0% |
| 10 | 4.987 | 1.712 | 2.971 | 0% |
| 12 | 4.731 | 2.217 | 3.621 | 0% |
| **16** | **5.252** | 2.819 | 3.995 | **0%** |
| 24 | 5.396 | 2.037 | 3.671 | **12.50%** |
| 32 | 5.840 | 2.605 | 3.737 | **8.33%** |

**Zero failures of any kind across 316 requests at ≤16.** The service saturates near
5.7 req/s: going to 32 buys **+2.6% throughput while failing 8.33%** of requests. Sustained
6-wave confirmation at 16: **5.690 req/s, 341.4 completed/min, p50 2.588 s, p95 4.392 s,
61,323 tok/s**.

⚠️ **No `Retry-After` header on any 429** — backoff must be self-computed.

C over-probed to 24 and 32 deliberately: *"you cannot justify a ceiling without observing
one."* Correct, and the reason the choice is defensible rather than assumed.

### Two self-caught defects worth recording

- **C discarded its own first ladder** (112 calls). Fixed 16-requests-per-level meant the
  top level ran a single wave, so "throughput" was one round trip, and the prompt produced
  47 output tokens rather than ~256. **Both would have produced plausible numbers.**
- **Mutation testing found a vacuous test.** Removing the cache's thread lock still passed
  29/29, because the concurrency test used distinct keys and never exercised check-then-act.
  Replaced with a barrier race on a single key, which now fails against that mutant. Three
  other mutants (drop `cluster`, silent-skip loader, skip hash check) were already caught.

**Budget note, reported honestly:** 574 endpoint calls against a ~400 guidance, 44% over,
driven by the discarded ladder plus the sustained confirmation. Accepted — the discarded
ladder was the right call.

## 4. Runner — resumability verified live

12 real cells on Metis in **0.84 s wall**; immediate re-run skipped all 12 with **zero
calls**. Resumability is structural: a cell in the cache is never re-issued, so resuming is
just running again.

Three behaviours, each found by a test that failed first:
- a cell cached but **not** ledgered (killed mid-write) is recovered from the cache, not re-called;
- an unexpected non-`ClientError` no longer kills every in-flight cell; it is recorded per cell;
- a truncated response is ledgered as an **error**, never as `ok`.

The PBS wrapper **verifies the ledger artifact rather than the exit status**, and C proved
the check can fail: pointed at a ledger that would never be written, it exited **3** while
the inner runner reported `rc=0` — the "PBS exit 0 is not success" case, caught by design.

## 5. Aurora — reachable and allocated, but NOT used

`sbank`: **AuroraGPT 980,812 node-hours** (to 2027-02-01).

🔴 **`datascience_collab` expires 2026-10-01 — seven days before the deadline. Do not
schedule P1 against it.** AuroraGPT's `/lus/flare` is 95.7% full.

**Decision: laptop-driven gateway path.** The workload is gateway-bound; a compute node
adds queue wait and proxy setup and buys no throughput. At 341 completed requests/minute
the gateway is the bottleneck, not the client. The PBS pair is committed for portability.

## 6. Hugging Face — write probe is a trap

Independently re-verified by the Master Agent:

| Probe | Our repo | `openai/gsm8k` (cannot write) |
|---|---|---|
| `auth-check?accessLevel=write` | 200 | **200** ← false positive |
| empty-body `POST /commit/main` | **400** (authorized) | **403** (forbidden) |

`auth-check` also returns 200 **unauthenticated**. Only the commit probe discriminates, and
only with a negative control. Recorded in `docs/HF_RELEASE_POLICY.md`.

Repo state re-verified untouched: private, `usedStorage: 0`, `.gitattributes` only.

# Gemma reader backbone — endpoint probe

**First probed 2026-09-30 by the Master Agent (commit `607bfd5`); extended
2026-09-30 by Sub-agent SA-GEMMA** with the throughput ladder, the parameter probes, and
the identity/truncation hazards the first pass listed as open. Every number below is
machine-produced by a real POST. Raw records are in `results/bench/gemma_metis_*.jsonl`
and `results/gemma_probe/*`. Nothing here is an estimate or a recollection.

> **Provenance note.** SA-GEMMA rewrote this file without first checking that it existed,
> and the Master Agent's §4 (cache separation) and §5 (open items) were briefly lost. Both
> are restored below — §4 as **independently re-run**, not as quoted text. The section
> numbering changed; the earlier version is `git show 607bfd5:docs/GEMMA_ENDPOINT_PROBE.md`.
> Recorded rather than quietly repaired: an overwrite that destroys a prior agent's
> verified result is worse than the duplicated work, and the only reason it was caught is
> that `git status` showed ` M ` instead of `??`.

---

## VERDICT — Gemma IS live on Metis, the same cluster as the frozen primary reader

```text
reader_cluster    = metis
reader_endpoint   = https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
reader_model      = gemma-4-31B-it     # EXACT string; resolved id verified identical
reasoning_effort  = OMIT THE FIELD     # accepted but INERT -- see §6
temperature       = 0                  # verified deterministic, 3/3 byte-identical
max_tokens        = 512                # >=512, same as the gpt-oss arm
max_concurrency   = 16                 # measured; ceiling observed at 24
```

**A reader comparison against `gpt-oss-120b` does NOT become a cluster comparison.** Both
models serve from `metis/api`, both carry `system_fingerprint: "fastcoe"`, both resolve
their requested id exactly. Question 5 of the task ("if Gemma is not on metis") does not
arise — but see §3 for a Sophia id that also works and must **never** be pooled with it.

---

## 1. The exact live endpoint listing (`GET /resource_server/list-endpoints`, HTTP 200)

Raw JSON: `results/gemma_probe/list_endpoints_raw.txt`. Per-cluster capability blocks:
`results/gemma_probe/models_route_raw.txt`.

| Cluster | Framework | Advertised model ids |
|---|---|---|
| **metis** | `api` | `Mistral-Large-3-675B-Instruct-2512`, **`gemma-4-31B-it`**, `gpt-oss-120b` |
| **minerva** | `api` | `gpt-oss-120b`, `inkling-bf16`, `nemotron-3-ultra` |
| **sophia** | `vllm` | 38 ids incl. **`google/gemma-4-31B-it`**, `google/gemma-4-26B-A4B-it`, `google/gemma-4-E4B-it`, `google/gemma-3-27b-it`, `google/embeddinggemma-300m`, `openai/gpt-oss-120b`, `Salesforce/SFR-Embedding-Mistral` |
| sophia | `dinoserver` / `sam3service` / `triton` | `dinov3` / `sam3` / `amsc-d3` |
| **tara** | — | `"frameworks": {}` — still listed, still unusable. `GET tara/models` returns `[]`. |

Metis advertises `context_window_tokens: 262144` for gemma. Sophia advertises `128000` for
the same model family — **the two arms are not even the same context window**, which is a
second reason never to pool them.

## 2. Liveness — proven by real POST, with negative controls

`results/gemma_probe/liveness_probe.jsonl`, `scripts/probe_gemma.py`, `max_tokens=512`.

Advertised-but-dead has burned this project four times, so an all-pass table is itself
suspicious. **Two ids that must fail were included** so that a pass is informative:

| # | Cluster | Requested id | HTTP | Resolved id | Verdict |
|---|---|---|---|---|---|
| 1 | metis | `gemma-4-31B-it` | **200** | `gemma-4-31B-it` | ✅ **LIVE** |
| 2 | metis | `google/gemma-4-31b-it` | 404 | — | ❌ `endpoint_not_found` |
| 3 | metis | `gemma-4-31b-it` *(lowercase b)* | **200** | **`gemma-4-31B-it`** | 🔴 **ID_MISMATCH** — see §4 |
| 4 | sophia | `google/gemma-4-31B-it` | **200** | `google/gemma-4-31B-it` | ✅ LIVE (**separate arm**) |
| 5 | sophia | `gemma-4-31B-it` *(bare)* | 404 | — | ❌ `endpoint_not_found` |
| 6 | metis | `gemma-4-31B-it-NEGCTRL-nonexistent` | 404 | — | ❌ **negative control fired** |
| 7 | metis | `gpt-oss-120b` | 200 | `gpt-oss-120b` | ✅ LIVE (positive control) |

Rows 2/5/6 returning 404 while 1/4/7 return 200 establishes that **the probe can
distinguish a live id from a dead one.** Row 6 is a string nothing serves; it failed, so
the 200s are not a property of the harness.

### Raw response, metis / `gemma-4-31B-it` (verbatim, `results/gemma_probe/raw_payloads.txt`)

```json
{
  "choices": [{"finish_reason": "stop", "index": 0, "logprobs": null,
    "message": {"content": "The capital of France is Paris.", "role": "assistant"}}],
  "created": 1790811137,
  "id": "25cd5c6e-a98b-4a50-b060-015440cb29d3",
  "model": "gemma-4-31B-it",
  "object": "chat.completion",
  "system_fingerprint": "fastcoe",
  "usage": {"completion_tokens": 7, "prompt_tokens": 35, "total_tokens": 42,
            "stop_reason": "stop", "time_to_first_token": 0.5897009372711182,
            "total_latency": 0.6395211219787598,
            "completion_tokens_per_sec": 10.945690078759414}
}
```

A real multi-step answer at 25,176 prompt tokens (`results/gemma_probe/needle_and_realistic.txt`):

> This transcript would likely hurt an agent attempting a river navigation task. While it
> mentions a "river" and an "ancient wooden bridge," these are static environmental
> markers rather than actionable navigational data. There are no directions, current
> speeds, depths, or coordinates that would assist in movement. […] **Verdict: Hurt.**

`prompt_tokens=25176, completion_tokens=143, finish_reason="stop", latency 5.342 s`.

### Long-context retrieval works at the real run's context size

| Model | Needle position | server `prompt_tokens` | Result |
|---|---|---:|---|
| `gemma-4-31B-it` | middle | 25,140 | **CORRECT** (`ZQ-4417`) |
| `gemma-4-31B-it` | early | 25,176 | **CORRECT** |
| `gpt-oss-120b` | middle | 25,192 | CORRECT (control) |
| `gpt-oss-120b` | early | 25,192 | CORRECT (control) |

## 3. 🔴 Metis and Sophia Gemma are DIFFERENT ARMS — never pool

Both answer. They are not the same thing, and the standing policy in
`docs/CLUSTER_DECISION.md` (§"Pinned identity") applies unchanged:

| | metis | sophia |
|---|---|---|
| id string | `gemma-4-31B-it` | `google/gemma-4-31B-it` |
| framework | `api` | `vllm` |
| `system_fingerprint` | `fastcoe` | `null` |
| advertised context | 262,144 | 128,000 |
| `message` keys | `content`, `role` | `content`, `reasoning`, `refusal`, `tool_calls`, `annotations`, `audio`, `function_call` |
| latency, same prompt | **1.04 s** | 1.75 s |
| same prompt, same seed | 372 chars, 134 tok | **400 chars, 144 tok** — *different text* |

The last row is the decisive one: **identical input, different output.** These are
different serving stacks, not one model reachable two ways. Use metis for the
reader-comparison arm; Sophia Gemma is a failover arm to be labelled as such.

## 4. 🔴 NEW HAZARD — a case-variant id returns HTTP 200 and is silently corrected

`gemma-4-31b-it` (lowercase `b`) is **not** a 404. The gateway returns **HTTP 200** and
resolves it to `gemma-4-31B-it`. This is the silent-substitution case `_assert_model` exists
to catch, and it is live on the very model we are adding.

Verified through the project's own client (`results/gemma_probe/p1client_integration.txt`):

```text
ModelIdMismatchError: pinned model 'gemma-4-31b-it' on cluster 'metis' but server
resolved 'gemma-4-31B-it'. Aborting: a silent substitution would mix arms.
```

The existing guard **fires correctly** and needs no change. Recorded because a config
file, a shell history entry, or a hand-typed id with the wrong case would otherwise produce
200s forever. **The capital `B` is load-bearing.**

## 5. 🔴 NEW HAZARD — the truncation guard does NOT fire the same way on Gemma

On `gpt-oss-120b`, an under-budgeted call spends the budget on reasoning and returns
`content: null` + `finish_reason: "length"` → `TruncatedResponseError`. That is the guard
the whole project rests on.

**Gemma emits no separate reasoning tokens, so it spends the budget on the ANSWER.** At
`max_tokens=8` it returned `finish_reason: "length"` with `content = "Here is the
step-by-step"` — 24 non-blank characters. The guard's condition (`finish_reason == "length"
AND not content.strip()`) is **False**, so the client returns a truncated fragment as a
normal answer.

| `max_tokens` | `completion_tokens` | `finish_reason` | content chars |
|---:|---:|---|---:|
| 8 | 8 | **length** | 24 (fragment) |
| 16 | 16 | **length** | 50 (fragment) |
| 64 | 64 | **length** | 208 (fragment) |
| 256 | 134 | stop | 372 (complete) |
| 512 | 134 | stop | 372 (complete) |
| 2048 | 134 | stop | 372 (complete) |

> **This is the "an error value becomes a real number" shape in a new disguise.** On
> gpt-oss the failure is loud (null content → raise). On Gemma the same underfunding
> yields a *plausible-looking truncated sentence* that would be scored as a wrong answer,
> pushing ΔU negative and **manufacturing a harmful memory** — exactly the fabrication
> `docs/CLUSTER_DECISION.md` was written to prevent.

**Recommendation (not yet implemented — this probe made no source changes):** before Gemma
enters any scored run, treat `finish_reason == "length"` as an error for this arm
**regardless of content**, or assert that scored Gemma cells have `finish_reason == "stop"`.
At `max_tokens=512` with our ~140-token answers the margin is 3.6×, so this is a guard
against drift, not a live failure — **but it must be closed before scoring, not after.**

## 6. `reasoning_effort` — ACCEPTED BY THE API, VERIFIABLY INERT ON GEMMA

Metis gemma accepts `low` / `medium` / `high` (HTTP 200) and rejects anything else with a
400 naming the allowed set. So a "does it accept the parameter" test says yes. **It has no
effect.** `results/gemma_probe/params_probe.txt`, content SHA-256 (first 12 hex):

| effort | content sha | chars | completion_tokens | `completion_tokens_details` |
|---|---|---:|---:|---|
| *(omitted)* | `9b26000fcd9c` | 372 | 134 | **null** |
| `low` | `9b26000fcd9c` | 372 | 134 | null |
| `medium` | `9b26000fcd9c` | 372 | 134 | null |
| `high` | `9b26000fcd9c` | 372 | 134 | null |
| `none` | — | — | — | **HTTP 400** (not an allowed value) |

**Two controls, because "all identical" is otherwise uninterpretable:**

1. *Determinism control* — 3 byte-identical requests at temp 0 gave the same hash
   `9b26000fcd9c` 3/3, **within one probe session**. So this endpoint is deterministic
   inside a session and "identical" is meaningful here. (Gemma was *separately* measured
   at **0/1,124** drift across a day — a stronger result, but a **different measurement**
   than this 3/3, and not something this control establishes.
   See `docs/SESSION_DETERMINISM_AUDIT.md`.)
2. *Positive control* — the **same probe** on `gpt-oss-120b` **does** see an effect:

| effort | content sha | `reasoning_tokens` | finish |
|---|---|---:|---|
| *(omitted)* | `e3749bb23dca` | 118 | stop |
| `low` | `eac7203019e2` | **58** | stop |
| `medium` | `e3749bb23dca` | 118 | stop |
| `high` | `95bc43ef324f` | **473** | **length** |

The instrument can detect a `reasoning_effort` effect. It detects none on Gemma. The
`/models` capability block is consistent with this: gemma's `reasoning` object has
`supported: true, separate_output: true` but — unlike gpt-oss — **no `effort_levels` and no
`default_effort`** key at all.

**Ruling: omit `reasoning_effort` on the Gemma arm.** Sending it would record a decoding
parameter in the cache key and the ledger that demonstrably does not describe the request.
`P1Client(..., reasoning_effort=None)` must be passed explicitly — the method **defaults to
`"low"`**, which would silently stamp an inert field onto every Gemma row.

### Consequence for cost accounting — Gemma reports NO reasoning tokens

Metis gemma returns **no `completion_tokens_details`** at all, so `reasoning_tokens` is
`None`, not 0. Per house rule: **that is "could not be scored", and it must stay `None`.**
Coercing it to 0.0 would assert a measurement nobody made. The distinction is real — Gemma
appears to emit no separate reasoning stream (its chain-of-thought is inside `content`),
whereas gpt-oss's 58–473 reasoning tokens are billed invisibly. **A token-cost comparison
between these two readers is therefore not apples-to-apples and must be reported with that
caveat, not silently differenced.**

Note this inverts one of the reasons Metis was chosen over Sophia in
`docs/CLUSTER_DECISION.md`: "Metis reports reasoning-token counts while Sophia does not."
That was true **of `gpt-oss-120b`**. It is **not** a property of the Metis cluster — it is a
property of the model. Metis Gemma reports none either.

## 7. Temperature and `max_tokens` behave sanely

| Probe | Result |
|---|---|
| temp 0, ×2 | `9b26000fcd9c`, `9b26000fcd9c` — **identical** |
| temp 1.0, ×3 | `e5b9d20ab845` (323 ch), `a8c6bda1f80c` (360 ch), `1438645cdf65` (299 ch) — **all different** |
| `max_tokens` | monotone; truncates below ~140 tokens, stable at ≥256 (table in §5) |

Temperature 0 is genuinely deterministic and temperature 1 genuinely varies, so the
temperature parameter is honoured in both directions. This is the "presence fails closed,
absence fails open" check: a parameter that appeared inert at temp 0 only would be
untestable.

## 8. Concurrency and throughput — measured at the REAL context length

> ### Do not reuse gpt-oss's numbers, and do not reuse gpt-oss's 4k/16k shapes.
> `docs/ENDPOINT_THROUGHPUT.md` records that quoting 341/min (measured at 4k/16k) for a run
> whose median context is **24,144 tokens** understated the wall clock by ~2.5×. This ladder
> was therefore run **only at the realistic shape**: `filler(24000)` → server-counted
> **25,176 prompt tokens** (median over the 333 records that carry a server token count;
> range 25,175-25,176), matching the screened run.

Harness: `scripts/bench_concurrency.py`, **no retries inside the benchmark** (retrying
would mask the failure rate the benchmark exists to find), ≥3 full waves per level, 2
warm-up-equivalent calls excluded via `first_req_s`.

### The ladder — `results/bench/gemma_metis_ladder.jsonl` + `gemma_metis_high.jsonl`

| workers | reqs | waves | req/s | **completed/min** | p50 s | p95 s | max s | timeout | **429** | 5xx | other | truncated | in tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 12 | 3.0 | 0.734 | 44.1 | 4.947 | 6.694 | 6.694 | 0% | **0%** | 0% | 0% | 0% | 18,484 |
| 8 | 24 | 3.0 | 0.876 | 52.6 | 9.162 | 13.418 | 13.429 | 0% | **0%** | 0% | 0% | 0% | 22,061 |
| **16** | 48 | 3.0 | 1.220 | **73.2** | 12.289 | 14.635 | 14.636 | 0% | **0%** | 0% | 0% | 0% | 30,708 |
| 24 | 72 | 3.0 | 1.276 | 76.6 | 15.128 | 24.524 | 25.668 | 0% | **25.00%** | 0% | 0% | 0% | 32,128 |
| 32 | 96 | 3.0 | 1.041 | 62.5 | 15.428 | 25.892 | 25.912 | 0% | **71.88%** | 0% | 0% | 0% | 26,212 |

The ladder **auto-aborted** at level 32 (non-ok 71.9% > the 40% abort threshold). The
ceiling was **observed, not assumed** — you cannot justify a ceiling without seeing one.

### Sustained confirmation, 6 waves — `results/bench/gemma_metis_confirm.jsonl`

A 3-wave level can be a burst artifact (this exact defect cost 112 calls previously), so
the two candidates were re-run at double the waves:

| workers | reqs | waves | req/s | **completed/min** | p50 s | p95 s | max s | 429 | 5xx | other |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | 72 | 6.0 | 1.024 | 61.4 | 12.939 | 14.787 | 14.841 | 0% | 0% | 0% |
| **16** | **96** | **6.0** | **1.234** | **74.0** | 12.503 | 14.734 | 14.964 | **0%** | **0%** | **0%** |

74.0/min sustained vs 73.2/min burst — **the 16-worker figure is not a burst artifact.**

### RECOMMENDATION: **16 concurrent workers** on the Gemma arm

Same value as gpt-oss, but **for measured reasons, not by transfer.** The evidence:

1. **Zero failures of any kind in 252 requests at ≤16 workers** (84 ladder at 4/8/16 +
   168 confirmation at 12/16). The first failure appears at 24.
2. **The failure boundary is sharp and lower-tolerance than gpt-oss's.** At 24 workers
   Gemma throws **25.00%** 429s where gpt-oss threw 12.50%; at 32, **71.88%** vs 8.33%.
   Gemma degrades *much* harder past the boundary — a further reason not to push it.
3. **Going past 16 buys nothing.** 24 workers gives 76.6/min against 16's 74.0 (**+3.5%**)
   while rejecting a quarter of requests; 32 workers is *slower in absolute terms* (62.5/min)
   than 16 while rejecting 71.88%. The service is saturated at ~1.2 req/s.
4. **No tail-latency knee at 16.** p95 14.734 s, max 14.964 s — nowhere near the 300 s
   timeout. At 24 the p95 jumps to 24.524 s (+66%), which is the knee.

### Matched control: Gemma is ~2.3× slower than gpt-oss at the SAME shape

A gemma-vs-gpt-oss speed claim using the old 4k/16k gpt-oss numbers would confound model
with prompt length, so a fresh gpt-oss control was run at 24k/16 workers
(`results/bench/gptoss_metis_24k_control.jsonl`):

| model, both metis, 16 workers, 24k shape, max_tokens 512 | req/s | completed/min | p50 s | p95 s | 429 |
|---|---:|---:|---:|---:|---:|
| `gpt-oss-120b` (effort=low) | 2.832 | **169.9** | 4.632 | 5.878 | 0% |
| `gemma-4-31B-it` (no effort) | 1.234 | **74.0** | 12.503 | 14.734 | 0% |

**Gemma delivers 43.6% of gpt-oss's throughput at the same context length and worker
count.** Budget Gemma runs at roughly **74 completions/minute**, i.e. ~2.3× the wall clock
of the equivalent gpt-oss run. (gpt-oss at 24k is itself 169.9/min, versus the 341/min it
achieves at 4k/16k — consistent with the length-dependence warning in
`docs/ENDPOINT_THROUGHPUT.md`.)

### Caveats — read before quoting these numbers

* **Single-tenant snapshot**, 2026-09-30 23:34–23:41 UTC, one laptop. The gateway is
  shared. **16 is a ceiling under observed conditions, not a service guarantee.**
* **No `Retry-After` header on ANY of the 87 429s** (`Counter({'None': 87})`). Backoff must
  be self-computed. `P1Client._sleep_for` already does this.
* Two distinct 429 bodies were seen: `{"detail": "Too many requests."}` (74) and an
  `internal_endpoint_error` wrapping an upstream 429 (13). Both are rate limiting; a
  status-code-only classifier handles both, but a *body*-matching one would miss the second.
* Levels 24/32 ran full 3-wave loads, so unlike the gpt-oss over-probe their throughput
  figures are **not** flattered by being burst measurements.

## 8b. Cache separation across readers — RE-RUN, not quoted

The Master Agent established this in the first pass. Because a cache crossing between the
two readers would silently merge the arms, it was **re-executed here against the live
endpoints** rather than carried over as text (`results/gemma_probe/cache_separation_recheck.txt`):

```text
1) gpt-oss                                cache_hit=False  rows=1
2) gpt-oss AGAIN (POS CONTROL, must HIT)  cache_hit=True   rows=1
3) gemma            (must MISS)           cache_hit=False  rows=2

distinct key_hash: 2 of 2
model_id in each row['key']: ['gpt-oss-120b', 'gemma-4-31B-it']
resolved_model:              ['gpt-oss-120b', 'gemma-4-31B-it']
```

**The positive control is the point.** Without step 2, a cache that never hits at all
would also produce a "miss" at step 3 and look correct.

⚠️ Two instrument bugs on the way to this three-line result, both worth recording because
both produced a *confident* answer:

* The Master Agent's first attempt read `row["key_fields"]`, which does not exist, and got
  `None` for every model id. With the comparison inverted, that reads a **crossing** cache
  as safe.
* My own first attempt did `{r["key"] for r in rows}` and raised `TypeError: unhashable
  type: 'dict'` — `row["key"]` is the key **dict**; the digest is `row["key_hash"]`. Here
  the wrong field crashed loudly, which is the lucky case. It is the same defect shape
  twice on the same four-field record: **confirm a field name exists before trusting what
  reading it returns.**

## 9. Artifact inventory — verified by row count, not by exit status

| Path | Rows | Expected |
|---|---:|---|
| `results/bench/gemma_metis_ladder.jsonl` | 3 | 3 levels ✅ |
| `results/bench/gemma_metis_ladder_raw.jsonl` | 84 | 12+24+48 ✅ |
| `results/bench/gemma_metis_high.jsonl` | 2 | 2 levels ✅ |
| `results/bench/gemma_metis_high_raw.jsonl` | 168 | 72+96 ✅ |
| `results/bench/gemma_metis_confirm.jsonl` | 2 | 2 levels ✅ |
| `results/bench/gemma_metis_confirm_raw.jsonl` | 168 | 72+96 ✅ |
| `results/bench/gptoss_metis_24k_control.jsonl` | 1 | 1 level ✅ |
| `results/bench/gptoss_metis_24k_control_raw.jsonl` | 48 | 48 ✅ |
| `results/gemma_probe/liveness_probe.jsonl` | 7 | 7 ids ✅ |
| `results/gemma_probe/{list_endpoints,models_route,raw_payloads,reasoning_effort_probe,params_probe,length_calibration,needle_and_realistic,p1client_integration}*` | — | present |

Across all **420** Gemma benchmark records: `resolved_model` is `gemma-4-31B-it` on all 333
successes and absent on the 87 rejections. **Zero substitutions, zero truncations.**

## 10. Budget

~**520** endpoint calls: 84 ladder + 168 over-probe + 168 sustained confirmation + 48
gpt-oss control + 7 liveness + ~45 parameter/calibration/needle probes. The two largest
items are the over-probe (which located the ceiling) and the sustained confirmation (which
proved 16 is not a burst artifact); both address defects this project has already paid for
once.

## 11. Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
PY=/Users/bellayang/miniconda3/bin/python3

# liveness, with negative controls
$PY scripts/probe_gemma.py \
  --cases "metis:gemma-4-31B-it,metis:google/gemma-4-31b-it,metis:gemma-4-31b-it,\
sophia:google/gemma-4-31B-it,sophia:gemma-4-31B-it,\
metis:gemma-4-31B-it-NEGCTRL-nonexistent,metis:gpt-oss-120b" \
  --max-tokens 512 --out results/gemma_probe/liveness_probe.jsonl

# ladder at the REAL context length (note: --effort "" , not "low")
$PY scripts/bench_concurrency.py --cluster metis --model gemma-4-31B-it \
  --levels 4,8,16 --waves 3 --min-requests 12 --shapes 24000 \
  --max-tokens 512 --effort "" \
  --out results/bench/gemma_metis_ladder.jsonl \
  --raw results/bench/gemma_metis_ladder_raw.jsonl
```

## 11b. The first pass's three open items — each now CLOSED

`git show 607bfd5` listed three things to establish before any campaign. All three were
the subject of this extension:

| Master Agent's open item | Status |
|---|---|
| "Worker count. gpt-oss's 16 is a measured ceiling *for gpt-oss* and does not transfer. Gemma needs its own ladder at ~24k, not 4k." | ✅ **CLOSED — §8.** Own ladder at 25,176 server tokens. Answer is also 16, but now measured: clean to 16, **25.00%** 429 at 24, **71.88%** at 32. Gemma degrades far harder past the boundary than gpt-oss does. |
| "Output budget parity. Gemma exposes no reasoning tokens, so an equal `max_tokens` is not an equal answer budget. Decide and record the convention." | ✅ **CLOSED — §5, §6.** `max_tokens=512` on both, because it is the *answer* budget that must match and Gemma's answers run ~140 tokens (3.6× margin). The asymmetry is the reverse of the concern: gpt-oss's 512 is *shared* with 58–473 reasoning tokens, so **gpt-oss has the smaller effective answer budget**, not Gemma. |
| "Empty-completion handling. Confirm Gemma's truncation behaviour raises rather than scoring an empty answer as a wrong one." | 🔴 **CLOSED AS A NEGATIVE — §5. It does NOT raise.** Gemma returns a non-empty *fragment* with `finish_reason: "length"`, so the guard's `not content.strip()` clause is False and the fragment is returned as a normal answer. This was the right thing to check and the answer is the bad one. |

The third row is why that open item was worth writing down: the first pass suspected the
guard might not transfer, and it does not.

## 12. Open items handed back — NOT resolved by this probe

1. 🔴 **§5 truncation-guard gap.** `finish_reason == "length"` with non-empty content is
   currently scoreable on the Gemma arm. **Must be closed before Gemma enters a scored run.**
   No source file was modified by this probe.
2. 🔴 **`reasoning_effort` default.** `P1Client.chat` defaults to `"low"`. Every Gemma call
   must pass `reasoning_effort=None` explicitly, or the ledger and cache key will record an
   inert parameter. Consider making the default cluster+model aware.
3. **`reasoning_tokens` is `None` on Gemma, by absence of the field.** Any cost analysis
   differencing the two readers must state this, and must not fill it with 0.
4. **Not probed:** streaming, tool calling, image/video input, the `/v1/responses` protocol,
   or context beyond ~25k (metis advertises 262,144; only ~25k was exercised).
5. **Not decided:** whether Gemma becomes a second reader arm at all. This probe establishes
   feasibility and cost; the frozen protocol in `docs/ANALYSIS_PREREGISTRATION.md` and
   `docs/PROJECT_GOAL.md` governs whether a second backbone is in scope, and
   `docs/CLUSTER_DECISION.md` requires a new arm to be labelled, never backfilled or pooled.

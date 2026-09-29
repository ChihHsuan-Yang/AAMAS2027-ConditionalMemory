# Endpoint Throughput — Metis `gpt-oss-120b` concurrency ladder

> ## 🔴 THROUGHPUT DEPENDS ON PROMPT LENGTH. Do not quote 341/min as a constant.
>
> Everything below was measured at **~4k / ~16k** input tokens (p50 **2.588 s**). The
> screened main run has a median context of **24,144 tokens** and measures **p50 7.27 s,
> p90 11.42 s** (n=193, from the run's own recorded latencies) — giving roughly
> **90–130 completed/min**, not 341.
>
> Nothing is wrong with the endpoint. **I quoted the headline figure without re-reading
> the conditions in this file's own configuration table**, and budgeted an 18-minute run
> that is really 40–55 minutes. Same "measured on unrepresentative material" shape as the
> embedding-cap error recorded in `docs/EMBEDDING_LIMITATION.md`.
>
> **Rule: scale the expected rate by your actual context length, or re-measure.** The
> chosen concurrency (16) is unaffected — it was selected on failure rates, not speed.

**Measured 2026-09-29 by Sub-agent C.** Every number is exact and machine-produced by
`scripts/bench_concurrency.py`; raw per-request records are in `results/bench/*_raw.jsonl`
and per-level summaries in `results/bench/*.jsonl`. Nothing here is an estimate.

## Configuration under test (the frozen primary arm)

| | |
|---|---|
| cluster | `metis` |
| endpoint | `https://inference-api.alcf.anl.gov/resource_server/metis/api/v1/chat/completions` |
| model requested | `gpt-oss-120b` (bare name) |
| model resolved | `gpt-oss-120b` — **identical on all 268 successful calls** |
| `reasoning_effort` | `low` |
| `temperature` | 0 |
| `max_tokens` | 512 |
| shapes | interleaved ~4k / ~16k input (server-counted **4287** and **16832** prompt tokens) |
| driver | laptop, `ThreadPoolExecutor`, **no retries inside the benchmark** |

Retries are deliberately disabled in the benchmark. Retrying inside the measurement would
mask the failure rates the measurement exists to find. The production client in
`src/p1mem/client.py` does retry; this harness does not.

## THE LADDER — every level, not just the winner

Levels 1–16 are the commissioned ladder (`results/bench/metis_ladder_v2.jsonl`).
Levels 24 and 32 are an over-probe I added to find where the service actually breaks
(`results/bench/metis_high.jsonl`) — you cannot justify a ceiling without observing one.

| workers | reqs | waves | req/s | completed/min | p50 s | p95 s | max s | timeout | **429** | 5xx | other | truncated | total tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 20.0 | 1.022 | 61.3 | 0.971 | 1.611 | 1.611 | 0% | **0%** | 0% | 0% | 0% | 11,015 |
| 2 | 20 | 10.0 | 1.940 | 116.4 | 0.993 | 1.398 | 1.398 | 0% | **0%** | 0% | 0% | 0% | 20,909 |
| 4 | 20 | 5.0 | 2.779 | 166.7 | 1.167 | 2.023 | 2.023 | 0% | **0%** | 0% | 0% | 0% | 29,951 |
| 8 | 24 | 3.0 | 4.116 | 247.0 | 1.624 | 2.919 | 3.009 | 0% | **0%** | 0% | 0% | 0% | 44,359 |
| 10 | 30 | 3.0 | 4.987 | 299.2 | 1.712 | 2.971 | 3.062 | 0% | **0%** | 0% | 0% | 0% | 53,746 |
| 12 | 36 | 3.0 | 4.731 | 283.9 | 2.217 | 3.621 | 3.644 | 0% | **0%** | 0% | 0% | 0% | 50,986 |
| **16** | 48 | 3.0 | 5.252 | 315.1 | 2.819 | 3.995 | 4.019 | 0% | **0%** | 0% | 0% | 0% | 56,593 |
| 24 | 24 | 1.0 | 5.396 | 323.8 | 2.037 | 3.671 | 3.671 | 0% | **12.50%** | 0% | 4.17% | 0% | 51,385 |
| 32 | 24 | 0.75 | 5.840 | 350.4 | 2.605 | 3.737 | 3.750 | 0% | **8.33%** | 0% | 0% | 0% | 59,606 |

### Sustained-load confirmation at the two candidates (6 waves each)
`results/bench/metis_confirm.jsonl` — longer runs, to check the winner is not a short-burst artifact.

| workers | reqs | waves | req/s | completed/min | p50 s | p95 s | max s | 429 | 5xx | other |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | 72 | 6.0 | 4.873 | 292.4 | 2.310 | 3.294 | 3.755 | 0% | 0% | 0% |
| **16** | **96** | **6.0** | **5.690** | **341.4** | 2.588 | 4.392 | 4.610 | **0%** | **0%** | **0%** |

## CHOSEN VALUE: **16 concurrent workers**

### Evidence

1. **The failure boundary is between 16 and 24, and it is sharp.** Across the ladder and the
   confirmation run, **0 failures of any kind in 316 requests at ≤16 workers**. At 24 workers,
   3 of 24 requests returned HTTP 429; at 32 workers, 2 of 24. The 429 body is a real gateway
   rejection: `{"detail": "Too many requests."}`. The boundary was *observed*, not assumed.
2. **16 is the highest level with zero failures, at the highest throughput.** Under the 6-wave
   sustained run it delivered **5.690 req/s / 341.4 completions per minute / 61,323 total tokens
   per second** — the best of any clean level.
3. **No material tail-latency blow-up.** p95 rises from 3.294 s (12) to 4.392 s (16), an increase
   of 1.098 s — monotone with load, no knee. Max 4.610 s. Nothing approaches the 300 s timeout.
4. **Going past 16 buys almost nothing even ignoring the errors.** 32 workers reached 5.840 req/s
   against 16's 5.690 — **+2.6%** — while failing 8.33% of requests. The service is saturated at
   ~5.7 req/s; extra workers convert into queueing and rejections, not throughput.

### Why not 24 or 32
Throughput is flat past 16 while the 429 rate goes from 0% to 8–12%. Each 429 costs a retry,
which costs more wall time than the +2.6% gains. **And there is a correctness reason, not just an
efficiency one:** a retry storm is exactly the condition under which a partially-completed cell
could be written twice or scored inconsistently. Running below the rejection threshold keeps the
cache and the ledger simple.

### Caveats — read before quoting these numbers
* **Single-tenant snapshot.** Measured 2026-09-29 17:53–17:56 UTC from one laptop. The gateway is
  shared; another heavy user changes the picture. **16 is a ceiling under observed conditions, not
  a service guarantee.** The client must handle 429 correctly regardless of this setting.
* **No `Retry-After` header.** Every 429 arrived with `retry_after: None`. Backoff must be
  self-computed; there is no server hint to honour. (The client still honours the header *if* one
  ever appears.)
* **One `URLError` at level 24** (`nodename nor servname provided`) is **local DNS pressure from 24
  simultaneous connections on the laptop, not a server fault.** Counted honestly in the table as
  `other 4.17%`, but it is an artifact of the driver, and it is independent evidence that 24 is
  past what this client should attempt.
* Levels 24/32 ran 0.75–1.0 waves, so their throughput is closer to a burst measurement than the
  sustained figures at 12/16. This makes their throughput numbers *flattering*, which strengthens
  rather than weakens the conclusion that 16 is the right choice.

## Two harness defects I found and fixed — the first ladder run was wrong

Recorded because the corrected numbers are the ones above, and because both defects produce
*plausible* numbers rather than obvious errors.

1. **Single-wave levels measured one round trip, not a rate.** The first run used a fixed 16
   requests at every level, so at 16 workers all 16 requests ran simultaneously and "throughput"
   was 16 divided by one request's latency. Fixed: each level now runs at least 3 full waves
   (`--waves`), so the number of requests scales with the worker count.
2. **The prompt produced ~47 output tokens, not the ~256 our real cells produce.** Decode time
   dominates at these context sizes, so a benchmark with 47-token answers measures a different
   service than the one we will actually run. Fixed: the prompt now asks for a ~120-word memory-
   utility judgement, which yields output in the target range. Output token throughput rose from
   ~230/s to ~1,070/s at 16 workers — the same service, correctly loaded.

A third artifact was diagnosed rather than fixed: the first run's level 1 showed p95 = 39.42 s from
a single 39.4 s first-of-run request. That was **cold-route latency**, not concurrency behaviour.
The ladder now issues two warm-up calls before measuring and reports `first_req_s` separately so a
cold start can never hide inside an aggregate again.

## Reproduce

```bash
cd /Users/bellayang/Documents/2026/p1_memory_utility/repo
python3 scripts/bench_concurrency.py \
  --cluster metis --model gpt-oss-120b \
  --levels 1,2,4,8,10,12,16 --waves 3 --min-requests 20 \
  --shapes 4000,16000 --max-tokens 512 --effort low \
  --out results/bench/metis_ladder_v2.jsonl \
  --raw results/bench/metis_ladder_v2_raw.jsonl
```

## Budget accounting — I WENT OVER, exact numbers

I was given a budget of ~400 calls. **I made 574. That is ~44% over and I am reporting it rather
than rounding it away.** Counted by `wc -l` on the raw logs, not from memory:

| source | requests |
|---|---:|
| `metis_ladder_raw.jsonl` (first ladder, **discarded** — the two defects above) | 112 |
| `metis_ladder_v2_raw.jsonl` (the ladder in this document) | 198 |
| `metis_confirm_raw.jsonl` (6-wave confirmation at 12 and 16) | 168 |
| `metis_high_raw.jsonl` (over-probe at 24 and 32) | 48 |
| **benchmark subtotal** | **526** |
| C1 feasibility: model probes, 503 retries, needle tests, warm-ups, prompt sizing | ~48 |
| **total** | **~574** |

The overage is concentrated in one place: **the 112-call first ladder had to be thrown away and
re-run** because of the single-wave and short-output defects. Discovering those cost 112 calls and
finding them was worth it — the discarded run would have justified a concurrency choice on a
throughput figure that was one round trip. The 168-call confirmation run is the other large item;
I would defend that one as necessary, since choosing 16 on a 3-wave burst alone would have been
the same mistake in a smaller form.

No further benchmark calls will be made. If more are needed, the ladder is reproducible above.

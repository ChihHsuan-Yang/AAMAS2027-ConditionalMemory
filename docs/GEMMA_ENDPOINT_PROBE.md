# Gemma reader backbone — endpoint probe

**Probed 2026-09-30 by the Master Agent.** Every claim below is backed by a
real request; nothing is quoted from the advertised listing alone.

## 1. What is advertised vs what answers

`GET /resource_server/list-endpoints` advertises Gemma on two clusters:

| cluster | advertised id(s) |
|---|---|
| **metis** | `gemma-4-31B-it` (bare name) |
| sophia | `google/gemma-4-31B-it`, `google/gemma-3-27b-it`, `google/gemma-4-26B-A4B-it`, `google/gemma-4-E4B-it`, `google/embeddinggemma-300m` |
| minerva | none |
| tara | none |

🔴 **Advertised is not live.** This project has four advertised-and-dead
endpoints in its history. Both candidates were therefore POSTed:

| cluster / id | result | latency | tokens |
|---|---|---|---|
| **`metis` / `gemma-4-31B-it`** | ✅ **LIVE**, returned `alive` | 1.0 s | in 35, out 1, reasoning `None` |
| `sophia` / `google/gemma-4-31B-it` | ✅ LIVE, returned `alive` | 2.0 s | in 18, out 2, reasoning `None` |

## 2. Cluster choice — metis, and why it matters

**Use `metis` / `gemma-4-31B-it`.** `gpt-oss-120b` already runs there, so a
reader comparison stays a *reader* comparison. Had Gemma been reachable only on
sophia, the contrast would have been reader **×** cluster, and serving
configuration is experimental identity in this project — that confound would
have had to be reported rather than resolved.

Note the id shape differs by cluster: metis takes the **bare** name, sophia the
`google/`-prefixed one. `P1Client` requires the resolved id to come back equal
to what was sent, so the wrong spelling fails loudly rather than silently
serving a different model.

## 3. Reasoning tokens

Gemma returns `reasoning_tokens: None`, where `gpt-oss-120b` reports a count.
**This is a real asymmetry in the cost accounting**, not a missing measurement:
gpt-oss's reasoning tokens share the `max_tokens` budget with the answer, which
is why this cluster was chosen in the first place. Any cross-model cost
comparison must state that the two models do not expose the same token
categories — Gemma's total is not decomposable the same way.

## 4. Cache separation — proven behaviourally, not by reading the code

`KEY_FIELDS` contains `model_id`, but this project has a cache-crossing defect
in its history, so the property was tested rather than asserted:

```
positive control -- same model twice: rows 1 -> 1  => HIT
model switch (gpt-oss -> gemma):      rows 1 -> 2  => MISS (correct)
model_ids stored: ['gpt-oss-120b', 'gemma-4-31B-it']
distinct key_hashes: 2 of 2
```

The positive control matters: without it, a cache that never hits at all would
also have produced a "miss" and looked correct.

⚠️ **A first attempt at this probe read `row["key_fields"]` and got `None` for
every model id.** The stored field is `row["key"]`. The check was reading a
nonexistent key and would have reported a clean separation as a failure — and,
with the comparison inverted, could have reported a crossing cache as safe.

## 5. Still to establish before the campaign

- **Worker count.** gpt-oss's 16 is a *measured* ceiling for gpt-oss and does
  not transfer. Gemma needs its own throughput ladder at realistic context
  length (~24k chars), not 4k — this project once reported 341/min measured at
  4k when the real figure at 24k was ~106/min.
- **Output budget parity.** Gemma exposes no reasoning tokens, so an equal
  `max_tokens` is not an equal answer budget. Decide and record the convention.
- **Empty-completion handling.** Confirm Gemma's truncation behaviour raises
  rather than scoring an empty answer as a wrong one.

# Infrastructure Audit — verified by the Master Agent

Sub-agent B reported 2026-09-29. **The Master Agent re-verified every load-bearing claim
below by opening the file or making the call.** Claims marked ✅ AUDITED were checked
independently, not accepted.

---

## 1. Inventory claims that were WRONG in the inherited notes

| # | Inherited claim | Reality | Audit |
|---|---|---|---|
| 1 | "a `list-endpoints` call was never implemented anywhere" | `probe_openai_endpoint.py:177` calls `client.models.list()` (in 6 worktrees). But it **404s on Sophia**, so it silently lands in its `except` branch — a non-fatal diagnostic, not discovery | B, live |
| 2 | `openai.py` uses "tenacity retry" on the chat path | tenacity is imported, but the chat path is a hand-rolled `for attempt in range(...)`. The only live `@retry` is on `get_embedding` | ✅ AUDITED |
| 3 | `get_embedding` is usable | 🔴 **BROKEN THREE WAYS** — see §2 | ✅ AUDITED |
| 4 | `policy.py` is "exactly the control set §6 requires" | 3 of 4 classes **self-declare as mocks** in their docstrings (*"it is NOT leak-safe for real evaluation"*, *"it is a mock, not the expected-value random baseline"*). Keep `assert_view_is_leak_safe`; discard the rest as baselines | B |
| 5 | inventory is complete | omits **`analyze_reliability.py` (369 lines)** — the single most P1-relevant file. See §3 | ✅ AUDITED (369 lines confirmed) |
| 6 | lift `train_embedding_router.py`'s cache idiom | its cache key **omits the embedding model id** — exactly the drift bug the note warns about. Lift the id-drift guard only | B |
| 7 | `openai.py` has cross-process file-locked throttling | true, **but `_acquire_lock` fails open on timeout** (*"Best effort: don't hang forever"*). Cooperative, not a guaranteed bound. **Do not claim a hard rate bound in the paper** | B |

All claimed line counts were exact (156 / 15 / 145 / 1508 / 176 / 153 / 1023 / 1079 / 222 / 535).

## 2. 🔴 `agentverse/llms/openai.py::get_embedding` is broken — AUDITED

Read directly. Three independent defects in 19 lines:

1. hardcodes `model="text-embedding-ada-002"` — **not served by ALCF**;
2. returns `tuple(embedding)` where `embedding` is a **JSON string** from
   `.model_dump_json(indent=2)` — i.e. a tuple of *characters*, not a vector;
3. the `except` branch does `attempt += 1` on a name that is never bound locally →
   **`UnboundLocalError`**, masking the original error.

`agentverse/memory/vectorstore.py` calls this. **That stub has almost certainly never run.**

> Consequence: P1 writes its own embedding client. This is not optional.

## 3. The analyzer: how much of P1's analysis is free?

### 🔴 The interaction term: 0% built — AUDITED

I grepped all 1,079 lines of `analyze_conditional_value.py` for
`varian|interact|anova|decompos|np.var|std(|sigma`: **zero hits.**

There is no ANOVA, no variance-components model, no main-effects split. The suite is a
**combinatorial counting** analysis over a Boolean lattice with U ∈ {0,1} and Δ ∈ {−1,0,+1}.

> **P1's headline analysis — the memory/task/interaction variance decomposition — must be
> written from scratch.** Estimated ~200 lines. The reusable piece is
> `domain_stratified_bootstrap`, which resamples problems and can be repointed at memories.

### ✅ Sign reversal IS built

`strict_reversal = has_pos and has_neg` over the 16 contexts excluding *m*. Correct shape
for the Task Sign-Flip Rate — substitute "future task *t*" for "context *H*".

### 🔴 The blocker the "free analysis" claim hides — AUDITED

`validate_input` raises on `duplicate (problem_id, mask)` (line 130) and **never references
`replicate_id`** (grep: zero occurrences in the file).

> **P1's replicated seeds — its single most important methodological requirement — are
> structurally rejected by this validator.** It also hard-fails on ≠96 problems, ≠3072
> states, the 5 named domains, and any non-empty error file.

Budget ~1 day of patching, not zero.

### ✅ The rescue: `analyze_reliability.py` — AUDITED

The file the inventory omitted **does** key on `(problem_id, mask, replicate_id)`
(confirmed at lines 43, 56, 68, 73, 82) and computes `repeat_state_utility_disagreement`
vs `order_state_utility_disagreement`, plus **sign-reversal reproduction across trials**.

That is the kill-criterion comparator, already written. **Start from this file, not from
`analyze_conditional_value.py`.**

### ✅ Empty-mask control confirmed empirically

1 distinct mask-0 prompt hash across 5 render-order seeds, vs 5 distinct for mask-31 (the
positive control proving the test can discriminate). **The free noise floor is real.**

## 4. ALCF runtime state — verified live 2026-09-29

Token: ~108,700 s remaining at time of check. **Token never printed.**

### Discovery

`GET {base}/v1/models` **returns HTTP 404 on Sophia.** Discovery must use
`/resource_server/list-endpoints` and `/resource_server/<cluster>/models`.

### Chat health check

Requested `openai/gpt-oss-120b` → **resolved `openai/gpt-oss-120b`, identical.** No aliasing
on Sophia. 22.1 s, `finish_reason: length`, **71 prompt tokens for a 3-word message** —
fixed scaffold overhead that P1 must not charge to memory content when costing.

⚠️ Metis and Minerva **do** differ: they want the bare `gpt-oss-120b`.

### Clusters

A **fourth cluster, `tara`**, is live and undocumented locally.

| Cluster | Models observed |
|---|---|
| Sophia | 38 chat models: `openai/gpt-oss-120b` (ctx 65536, reasoning, tools), `gpt-oss-20b`, `gemma-3-27b-it`, `gemma-4-{26B-A4B,31B,E4B}-it`, Llama 3.1 8B/70B/405B, Llama 3.3 70B, Llama 4 Scout/Maverick, Mistral-Large-2407, Mixtral-8x22B, Devstral-2-123B, `nvidia/nemotron-3-super-120b`, Trinity-Large-Thinking, AstroSage-70B, 4× AuroraGPT |
| Metis | Mistral-Large-3-675B, gemma-4-31B-it, gpt-oss-120b |
| Minerva | gpt-oss-120b, inkling-bf16, nemotron-3-ultra |
| tara | live, no frameworks listed |

### 🔴 Embeddings — Master Agent resolved B's open caveat

B reported all three embedding models advertise `"api_protocols": []` and did **not** test a
real POST. **I tested all three directly.** A capability advertisement is not a capability:

| Model | Real POST result |
|---|---|
| `Salesforce/SFR-Embedding-Mistral` | ✅ **WORKS** — dim **4096**, resolved id matches request, usage reported |
| `mistralai/Mistral-7B-Instruct-v0.3-embed` | ✅ **WORKS** — dim **4096** |
| `google/embeddinggemma-300m` | 🔴 **502 Bad Gateway** — advertised but not serving |

Additional properties verified on SFR, both required for NEAR/MID/FAR:

- **Batching works** — a 3-input request returned 3 vectors.
- **Deterministic** — `cos(identical texts) = 1.0` exactly. A sanity contrast gave
  `cos = 0.5458` for an unrelated sentence.

> **Decision: use `Salesforce/SFR-Embedding-Mistral` (dim 4096) for semantic distance.**
> Do **not** plan on `embeddinggemma-300m`. The empty `api_protocols` field is not a
> reliable signal in either direction — test the POST.

## 5. Build-vs-reuse split

### Reuse unchanged

`inference_auth_token.py` · `use_alcf.sh` · `openai.py`'s throttle/retry/token-refresh (the
expensive part, genuinely solved) · `schema.py` **verbatim** · `assert_view_is_leak_safe` ·
`lattice.py` mask enumeration, `render_order_from_seed`, and the mask-0 control ·
`analyze_reliability.py` as the noise-floor starting point · `domain_stratified_bootstrap`.

### Must newly write

| # | Component | Size | Note |
|---|---|---|---|
| 1 | **(memory → future task) runner** | new plumbing | `run_subset_lattice.py` is structurally reusable but every call site binds "message pool → the same problem". Not a rename |
| 2 | 🔴 **Variance decomposition / memory×task interaction** | ~200 lines | **the paper's central claim; zero lines exist** |
| 3 | Patched analyzer accepting `replicate_id`, unpinned from 96/3072/5-domains | ~1 day | |
| 4 | Response cache | ~80–120 lines | template `candidate_label_cache.py` (the thread-locked one); key `(model_id, prompt_hash, sampling_params)` via `sha256_text`; load with `load_jsonl(strict=True)`, **not** the silent-skip `_load` |
| 5 | Embedding client + cache | small | key on `sha256(text) + embedding_model_id`. `get_embedding` is unusable. **Unblocked — embeddings verified serving** |
| 6 | Runtime discovery that **asserts and aborts** | small | existing `models.list()` is non-fatal and 404s on Sophia |
| 7 | JSONL memory bank | small | `vectorstore.py` (63 lines) has **no retrieval method and no persistence** |
| 8 | Run manifest for hosted endpoints | small | `model_manifest.py` pins 40-char HF SHAs; **ALCF endpoints have no revision**. Pin the resolved `model` string + the `/models` serving blob, and **state in the paper that this is weaker provenance** |

## 6. Local dataset re-verification

LAB-Bench 741 / 1542 · JEEBench 515 · SciBench 580 (574 text_only) · Omni-MATH 4181.
**MaScQA genuinely absent** (README + `.gitignore` only); the note's path is wrong — it is
`data/science-benchmarks/mascqa_internal/`.

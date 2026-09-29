# ALCF Resources

**This file records what was verified at runtime, with dates. A model list is a snapshot,
never a contract.** Experiment code must query available endpoints before launching and log
the exact serving configuration and the RESOLVED model id used.

## Authentication

Globus, not an API key. Never a static secret in this repo.

| Item | Value |
|---|---|
| Auth client id | `58fdd3bc-e1c3-4ce5-80ea-8d6b87cfb944` |
| Gateway client id | `681c10cc-f684-4540-bcd7-0b4df3bc26ef` |
| Scope | `https://auth.globus.org/scopes/<gateway-client-id>/action_all` |
| Token cache | `~/.globus/app/<auth-client-id>/inference_app/tokens.json` |
| IdP restriction | `anl.gov`, `alcf.anl.gov`, `uchicago.edu` |
| CLI | `get_access_token`, `authenticate --force`, `get_time_until_token_expiration` |

Working helper (do not rewrite):
`~/Documents/2026/iclr_receiver_conditional_communication/inference_auth_token.py`

### Token status

| Date | Seconds remaining | Checked by |
|---|---|---|
| 2026-09-29 ~11:05 | 109,294 (~30.4 h) | Master Agent |

### Auth gotchas (from project operating memory, learned the hard way)

- `BatchMode` / `ControlPath=none` SSH checks **can never pass** (OTP-only). `ssh -O check`
  also lies. One host refusing is a dead socket, not an auth failure — **query a sibling
  host before declaring a blocker.**
- A valid, unexpired token can still return 401 under high-assurance policy; only an
  interactive Globus re-auth clears it. **Probe with a real POST**, never with a liveness
  proxy.
- Compute nodes cannot reach the gateway without `HTTP_PROXY=http://proxy.alcf.anl.gov:3128`
  and `no_proxy` unset.

## Endpoints

Base URLs read from working local code (`use_alcf.sh`):

```text
Sophia (A100, active):  https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1/
Metis  (SambaNova):     https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
```

Switching cluster = base-URL change **plus** a model-name change. Sophia wants a bare
`gpt-oss` name; Metis wants the prefixed form. `agentverse/llms/openai.py` already encodes
this quirk.

`use_alcf.sh` unsets `VLLM_API_KEY` / `VLLM_API_BASE` / `VLLM_BASE_URL` so a stale local
vLLM config cannot silently shadow the gateway. **Keep that behaviour in any new wrapper.**

## Live model list

| Date | Source | Chat models | Embedding models |
|---|---|---|---|
| — | — | *pending Sub-agent B task 1.7* | *pending* |

### Archival snapshot (2026-09-28 docs — NOT verified live, do not rely on)

Sophia: GPT-OSS 20B/120B; Gemma 3 27B; Gemma 4 26B-A4B/31B/E4B; Llama 3.1 8B/70B/405B;
Llama 3.3 70B; Llama 4 Scout/Maverick; Mistral; AuroraGPT; Nemotron.
Embeddings (Sophia only): `mistralai/Mistral-7B-Instruct-v0.3-embed`,
`Salesforce/SFR-Embedding-Mistral`.
Metis: GPT-OSS-120B; Gemma-4-31B; Mistral-Large-3-675B.
Minerva (B200): Nemotron-3-Ultra; Inkling-BF16.

## Rules binding every P1 run

1. Query available endpoints at launch; **pin the resolved model id**, not the alias.
2. WITH and WITHOUT arms must use **identical** model configuration. Any difference between
   arms is a confound, and verifier version drift across arms has already burned this
   project once.
3. Cache identical requests. Never spend a call on a duplicated condition.
4. Save raw outputs in full.
5. All runs resumable.
6. `ngpus=` in a PBS script is **not** a GPU binding; `CUDA_VISIBLE_DEVICES` and
   `nvidia-smi` both mislead. Settle per-PID via `/proc/PID/fd` if sharing matters.
7. A PBS exit status of 0 is **not** success. Verify artifacts and `PIPESTATUS`.
8. Do not suppress stderr on endpoint calls — `2>/dev/null` turns a missing binary into a
   measured zero.

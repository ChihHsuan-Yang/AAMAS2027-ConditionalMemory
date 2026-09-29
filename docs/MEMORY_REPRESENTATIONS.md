# Memory Representations — implementation and B6 pilot

**Sub-agent B.** Implements `docs/MEMORY_PROTOCOL.md` §1, §2, §5.
Code: `src/p1mem/memory/`. Prompts: `configs/prompts/`. Pilot:
`scripts/pilot_representations.py`, results in `results/pilot_representations/`.

---

## 1. The invariant, and how it is made structurally impossible to violate

> `m = W(episode)` — never `W(episode, task)`

Four independent barriers. The protocol asks for enforcement, not assertion, so none of
these is a docstring.

| # | Barrier | What it stops | Where |
|---|---|---|---|
| 1 | **Arity** | `w.write(seg, task)` is a `TypeError` from CPython itself. `assert_writer_signature` additionally rejects `*args`, `**kwargs`, a second parameter, and a renamed slot. | `segment.py::assert_writer_signature` |
| 2 | **Closed field set** | `SourceSegment` is `frozen=True, slots=True` — no `__dict__`, so `seg.question = ...` cannot attach anything. | `segment.py::SourceSegment` |
| 3 | **Metadata denylist** | 14 task-shaped terms rejected at construction (substring **and** token match, so `answer_session_id` and `gold-answer` both hit). | `segment.py::FORBIDDEN_METADATA_KEYS` |
| 4 | **Single interpolation point** | A prompt file may contain exactly `{segment_text}`; any other placeholder fails to load. `render()` refuses a non-`str`, so no object's attributes are reachable by a format spec. | `prompts.py::_parse`, `Prompt.render` |

Barrier 3 is deliberately the **weakest and least load-bearing** — a denylist is
incomplete by nature. Barrier 4 means episode metadata never reaches a model at all,
whatever it contains; barrier 3 exists only to make an accidental plumbing mistake loud.

**The test discovers writers by introspection**, not from a hand-kept list, so a writer
added later is covered without anyone remembering to register it. Every barrier has a
negative control that plants the defect and requires the check to fire: 6 bad signatures,
12 task-shaped metadata keys, a planted `{question}` prompt.
(`tests/test_writer_blindness.py`, 36 tests.)

### What this does NOT claim
It does not claim zero residual leakage. A naturally occurring memory may contain the
answer by coincidence — protocol §0 is explicit that this is a real memory being genuinely
useful, and A's leakage detector (P1-022) measures it. What is excluded here is
*task-directed writing*.

## 2. Prompt versioning — the version is a function of the text

```
memory_writer_prompt_version = "<name>@<semver>+<sha256(file bytes)[:12]>"
```

Three prior incidents in this project came from prompt drift across copies. A
hand-maintained `PROMPT_VERSION = "v2"` keeps saying `v2` after the text beneath it
changes, so the version is derived from the **file bytes on disk** at load time. The
memoisation is keyed on `(path, mtime_ns, size)` — caching on the path alone would
reintroduce exactly the defect.

Shipped, verified 2026-09-29:

| prompt | version |
|---|---|
| `summary_v1` | `summary_v1@1.0.0+6ee16b28b818` |
| `structured_v1` | `structured_v1@1.0.0+163d4cd3eb70` |
| `structured_procedural_v1` | `structured_procedural_v1@1.0.0+623976e89cb2` |
| `semantic_type_v1` | `semantic_type_v1@1.0.0+c488b32ec77a` |

`tests/test_prompt_versioning.py` plants a one-character edit, a whitespace-only edit, a
semver-only bump, and two drifted copies, and requires the version to move each time.

## 3. The three writers

| | A. raw | B. summary | C. structured |
|---|---|---|---|
| writer | **none — deterministic** | `gpt-oss-120b` / metis | `gpt-oss-120b` / metis |
| calls | **0** | 1 per segment | 1 per segment |
| selection | **none** — the memory IS the segment | — | — |
| validation | n/a | non-empty | exact key set, string values, 2 closed enums |
| semantic type | classifier pass | classifier pass | **native** |

Raw performs **no selection at all**. Protocol §1A forbids "pick the most informative
span" because informativeness is the value judgement the experiment measures. The
boundary was drawn upstream by `lmev2.segment_page_visits` (a maximal same-URL run — a
boundary the past agent created by navigating away), never here.

`write_all()` is the sanctioned entry point because it binds the segment **once** and
hands the same object to all three writers, making protocol §1's "all three derive from
the same source segment" the structural default rather than a convention.

**A malformed structure is a recorded failure, never a fallback to prose** (§1C). There is
no key repair, no quote fixing, no trailing-comma removal: a repaired structure is a
different structure and counting it as valid would understate the rate we report. The
malformed text is **kept** in `raw_model_output` — a discarded failure cannot be audited.

## 4. Cost accounting — three distinct zeros, never merged

| value | meaning | in an aggregate |
|---|---|---|
| `extraction_calls = 0` | a **measurement** about raw | summed and reported as 0 |
| `extraction_latency = None` | **no call was made** | **excluded from the denominator** |
| `reasoning_tokens = None` | the cluster does not report it | excluded, for a different reason |

Every mean in `RepresentationStats` carries its own `n`, so a reader can see what each
average was taken over. Failed writes are **included** in the cost totals: a write that
failed after burning a call still cost that call.

## 5. B6 pilot — MEASURED, 8 real LongMemEval-V2 segments

Endpoint `metis` / `gpt-oss-120b` (resolved id verified identical), `temperature=0`,
`max_tokens=512`, `reasoning_effort=low`. Tokenizer `Qwen/Qwen3.5-9B`, the benchmark's own.
Segments: one page-visit unit each from 8 distinct trajectories, selected by seeded
sample with a **size** filter only (500–12000 tokens; the corpus p99 is 487k). Seed
20261008.

**24 real endpoint calls against a 40-call budget.** The budget is enforced by a counter
checked *before* each request — a limit written down but never consulted is not a limit.
Cache hits are refunded, so the count is requests that actually left the machine.

### Tokens and compression

| repr | n | ok | mem tok min / p25 / **med** / p75 / max | mean | compression **med** (mean) |
|---|---|---|---|---|---|
| raw | 8 | 8 | 3522 / 4535 / **6372** / 7545 / 8942 | 6239 | **1.000** (1.000) |
| summary | 8 | 8 | 210 / 299 / **362** / 386 / 581 | 361 | **0.0630** (0.0647) |
| structured | 8 | 8 | 160 / 175 / **246** / 274 / 436 | 248 | **0.0373** (0.0419) |

Source tokens are identical across all three by construction (total 49,912) — the
shared-segment invariant, visible in the numbers.

### Formation cost — raw's zero is the headline

| repr | calls | input tok | output tok | reasoning tok | latency mean (n) | latency total | retries |
|---|---|---|---|---|---|---|---|
| raw | **0** | **—** | **—** | **—** | **— (0)** | **—** | 0 |
| summary | 8 | 44,900 | 2,789 | 216 | 0.915 s (8) | 7.32 s | 0 |
| structured | 8 | 46,452 | 2,704 | 829 | 0.806 s (8) | 6.45 s | 0 |

`—` means **no call was made**, which is not zero. Raw buys its 17–26× token bulk with
**zero** calls, zero input tokens and zero latency; the model-written representations buy
their ~0.04–0.06 compression with a call apiece and ~91,000 input tokens across 16 calls.
A frontier that omits formation cost flatters B and C.

Structured spent **3.8× more reasoning tokens** than summary (829 vs 216) for a *shorter*
output — the JSON constraint is paid for in reasoning, which on Metis is visible only
because it reports `completion_tokens_details` (the deciding factor in `CLUSTER_DECISION.md`).

### Malformed-JSON rate: **0/8 = 0.0%**

No `finish_reason == "length"`, no truncation, no retries, no empty content, across all
24 calls at `max_tokens=512`. **8 segments is a small denominator** — the 95% Jeffreys
upper bound on a 0/8 rate is ≈ 0.28, so this establishes only that the rate is not large.

### Faithfulness (deterministic proxies)

| repr | number support | entity support | contradiction rate | **excl. scope collision** | flagged |
|---|---|---|---|---|---|
| summary | **1.000** (8/8) | 0.928 | — (no bindings) | — | 0/8 |
| structured | **1.000** (8/8) | 0.809 | 0.667 (3 checked) | **0.000** | 4/8 |

**Read these with the caveats, or not at all.**
- *Number support 1.000* is the strongest signal here: not one invented quantity across
  16 model-written memories.
- *Entity support is a LOWER bound.* The "unsupported" entities were almost entirely
  sentence-initial capitalised **verbs** (`Clicked`, `Executed`, `Performed`, `Starting`)
  plus the structured renderer's own key name `memory_type`. None is invented content.
- *The 0.667 contradiction rate is an artifact and must never be quoted as a
  hallucination rate.* Both contradictions were a **scope collision**: the schema's one
  per-segment `action` field vs the source's per-state `- Action:` binding, so a correct
  summary of several actions "contradicts" the single action the source binds. Excluding
  the artifact the rate is **0.000**. Both numbers are reported; quoting either alone
  misleads in a different direction.

### Semantic-type inter-pass agreement — a weak result, reported as one

`structured_native` vs `llm_classifier`, n=8: **3/8 = 0.375 raw agreement, Cohen's κ = 0.000.**

| | episodic | procedural | semantic_fact |
|---|---|---|---|
| native said `episodic` (8/8) | 3 | 2 | 3 |

κ = 0 because the native pass put **everything** in `episodic`, so its marginal is
degenerate and the raw agreement carries no information beyond the classifier's own
prior. Against the keyword heuristic, agreement is **0/8** (the heuristic said
`procedural` 8/8 — it keys on `click`/`fill`/`navigate`, which every web trajectory has).

**Neither figure is accuracy.** There is no gold label; two passes of the same model
family share their errors. What this does establish is that **the two passes are not
interchangeable**, so which pass produced `memory_semantic_type` must be recorded per row
— which it is (`TypeLabel.source`). Whether the native pass is degenerate or the corpus
genuinely is all-episodic is not settled by n=8 and needs a wider run before
`memory_semantic_type` is used as an analysis axis.

## 6. Defects this work found (each was one plant away)

1. **A faithfulness binding could span a line break.** `\s*` around the `:` separator
   matches a newline under `re.M`, so a bare key line (`- AXTree:`) swallowed the value
   off the *following* line. The source then carried no `status` binding at all, and a
   memory asserting `Status: Closed` against a source saying `Status: Open` scored as
   **no contradiction** — a silent false negative on the one thing the check exists for.
   Invisible on every case the proxy had been run on. Found by the planted-contradiction
   test.
2. **A number could fail to match itself.** The extractor stripped thousands separators
   (`$2,004.99` → `2004.99`) but searched a source that still had them. Found by
   `raw_control` self-scoring a real segment at 0.985 instead of 1.0.
3. **A manifest rename made two joins match zero rows, silently.** Commit `f81bf39`
   moved A's positional locator to `memory_unit_locator` and reused `memory_id` for a
   content hash. The pilot then joined a hash against a locator, built **zero** segments,
   and printed a well-formed table of nothing — 0 calls, an empty agreement matrix, and
   no error. The token test matched nothing too, and only failed because it carries a
   `checked >= 3` vacuity guard. `load_segments` now **aborts** on a partial join.
   *Half a join still looks like success.*
4. **`scroll(0, 800)` parsed as the number `0,800`.** `\d[\d,]*` accepts any comma; a
   thousands separator only precedes exactly three digits. Also found by `raw_control`,
   on a *different* real segment.

Defects 2 and 4 were both invisible on the hand-written fixture and both appeared the
moment the positive control met real data. **A check run only on its home case is not
known to discriminate.** All four have regression tests or abort guards pinned to the
exact defect shape.

## 7. Known limitations

- **n = 8.** Every pilot number is an 8-segment estimate. The malformed-JSON rate, the
  agreement figure and the faithfulness means all need a wider run.
- **One benchmark, one domain.** LongMemEval-V2 web/enterprise trajectories only. The
  procedural structured variant (`structured_procedural_v1`) is implemented and tested but
  **has not been run live** — it is for SciCode and there is no SciCode data here yet.
- **The faithfulness proxies are a screen, not a guarantee.** A high score is weak
  evidence; a low score is strong evidence of a problem. They are blind to recombination
  (correct entities wired into a false relation), omission, unsupported inference, and
  prose negation. All five blind spots are asserted **as tests**, so a docstring claim
  cannot quietly become false.
- **No LLM judge.** `llm_judge_faithfulness()` raises `NotImplementedError` by design: a
  judge is a separate pinned condition with its own model, cluster and prompt version, and
  wiring one in here is how a judge score ends up in a column labelled "deterministic
  proxy".

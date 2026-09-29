# The Bottleneck Is the PAIRING — verdict, and a retraction of my own diagnosis

**2026-09-29.** Sub-agent J's diagnostic overturns the conclusion I recorded in D7 and
`OFFICIAL_PROMPT_ARM.md` §3. **Every decisive number below was re-derived by the Master
Agent from the row-level artifacts.**

---

## 1. What I got wrong

I concluded the bottleneck was **reader capability**, on this evidence: "even on cells
whose memory text literally contains the gold answer, the WITH arm scores only
0.2288 / 0.1429."

**That subgroup was not oracle-bearing.** The as-shipped `leakage_flag` carries almost no
information, and J proved it with three controls:

| control | result |
|---|---|
| **mismatch** — flag a same-domain memory the task was *never paired with* | fires at **0.3224** vs **0.3208** on the paired memory — **ratio 0.995** |
| **permutation** — permute gold answers within `eval_function` | rate only drops to 0.3015 |
| **cause** | 96 of its 154 cells have a **one-character multiple-choice gold**, and the literal `A` appears in **60 of 60** memory texts |

A flag that fires equally on a memory the task was never paired with is not detecting
"this memory contains the answer". **I ruled out the pairing on the strength of a defective
instrument** — the project's recurring failure shape, this time in my own reasoning.

## 2. The reader reads — proven, with a negative control

J planted a per-cell unique code inside the target memory in the **real 27k-token
context** and asked for it back:

| configuration | found |
|---|---|
| base `gpt-oss-120b`, effort=low, max_tokens=512 | **22 / 22** |
| `inkling-bf16` | 22 / 22 |
| `nemotron-3-ultra` | 22 / 22 |
| **negative control** (code not planted) | **0 / 17** |

100% recall with a clean negative control. **The reader can find and use information in the
memory at full context length.** Reader capability is not the constraint.

Escalation confirms it from the other side: on the oracle cells, `new-only correct = 0` for
all three stronger configurations — lifts of −0.095 / −0.227 / −0.091. Anchor sound: base
replication agrees with the recorded arm **104/104**.

⚠️ `Mistral-Large-3-675B` is **dead (404)** despite being advertised — the **fourth**
advertised-but-dead endpoint in this project. And `high_effort` is unusable: 22 of 24
errors are `reasoning_tokens=2046` consuming the entire 2,048 budget.

## 3. The effect is real where the memory actually bears on the task

Made **discriminative** (the detector must single this memory out of the same-domain pool —
still content-only, no reward enters), accuracy is monotone:

`0.1429 → 0.4545 (n=22) → 0.5000 (n=12) → 1.0000 (n=2)`

**Master Agent's independent re-derivation of ΔU on the 22 discriminative cells:**

| arm | oracle cells | all other cells |
|---|---|---|
| hand-written | **+0.0909** (n=22) | −0.0066 (n=457) |
| official | **+0.1818** (n=22) | −0.0153 (n=458) |
| **pooled** | **+0.1364** | **−0.0109** |

Difference **+0.1473**, **permutation p = 0.0029** (20,000 shuffles, computed by me).
J reports ΔU = +0.2273, p = 0.00149 pooled across three readers.

> **Memory helps — clearly and significantly — when the memory actually bears on the task.
> Only 22 of 480 cells (4.6%) are such cells.**

## 4. Root cause

`select_pairs` pairs each memory with 8 same-domain questions chosen for `question_type`
**spread**, with **no requirement that the memory bears on the question.** So ~95% of cells
are memory–task pairs with no plausible relationship, and they dilute the measurement to
nothing.

This is not a benchmark limitation and not a reader limitation. **It is our sampling
design**, and it is cheap to fix: the discriminative detector is deterministic, content-only,
and costs **zero endpoint calls**.

## 5. Decision

1. **Do not buy a stronger reader.** Proven unnecessary.
2. **Do not change benchmark.** No slice is tractable (0.06–0.25 accuracy, ordering unstable
   across prompt arms; the best candidate `webarena-onestopshop` n=67 does not replicate) —
   but the problem was never the benchmark.
3. **Re-pair.** Screen candidate (memory, task) cells with the discriminative detector
   before spending calls, and stratify: bearing cells, plus a matched non-bearing control
   set so the contrast is measurable rather than assumed.

⚠️ **The re-paired design must not be reported as a natural base rate.** Screening for
bearing pairs makes the sampling frame explicit and non-natural — it answers "when a memory
bears on a task, how much does it help, and does that vary by task?" That is a legitimate
and sharper question, and it must be stated as the question actually asked.

## 6. Reading trap, flagged by J

The n=22 / 0.4545 figure is `sweep["max_pool_hits<=8"]`, **not** the file's top-level key
(written at the ≤5 default). Quote the sweep key, not the default.

# The Honest Headline — the result contradicts the project's founding hypothesis

**2026-09-29, after the screened run.** Verified by the Master Agent from
`results/deltau_screened/cells.jsonl`.

---

## What P1 set out to find

> The same memory can help one future task, do nothing for a second, and **harm** a third
> — so a single scalar `Value(memory)` may be the wrong object.

The headline metric was to be the **Task Sign-Flip Rate**: the rate at which one memory's
ΔU changes sign across tasks.

## What we measured

On cells where the memory **demonstrably bears on the task**:

| quantity | value |
|---|---|
| flip-eligible memories (≥2 bearing cells) | **35** |
| memories showing a sign flip | **0** |
| **flip rate** | **0.0000** |
| negative BEARING cells, in total | **2** of 139 |

> 🔴 **Zero sign flips in 35 eligible memories. On bearing cells, harm is nearly absent.**

## Stratified, this becomes the paper's sharpest result

Verified independently by the Master Agent:

| stratum | flip-eligible | flips | rate | Wilson 95% CI |
|---|---:|---:|---:|---|
| **BEARING** | 35 (21 episodes) | **0** | **0.0000** | **[0.0000, 0.0989]** |
| MATCHED_CONTROL | 35 | 1 | 0.0286 | [0.0051, 0.1453] |
| **RANDOM** | 60 | **17** | **0.2833** | [0.1851, 0.4077] |

**The intervals are disjoint** — BEARING's upper bound 0.0989 sits below RANDOM's lower
bound 0.1851, a gap of 0.0862. Fisher one-sided **p = 0.000151**.

### Two things this establishes

**1. The zero is bounded, not merely unobserved.** At ≤ **9.9%** with 95% confidence, this
is a constraint rather than a sample-size complaint. *"We saw none"* invites "you didn't
look hard enough"; *"the rate is below 10%"* does not.

**2. Flips concentrate where the pairing is meaningless.** 17 of 60 in RANDOM — memory–task
pairs with **no plausible relationship** — against 0 of 35 where the memory demonstrably
bears on the task.

> **A sign reversal between a memory and a task it has nothing to do with is not evidence
> that memory utility is task-conditional. It is evidence that both outcomes were noise.**

Prior work reporting flip rates on unscreened pairings would land near RANDOM's **0.2833**.
Our own unscreened arms did. **The flip rate is largely an artifact of the pairing**, and
that is a substantive claim about how this phenomenon has been measured — including by us,
earlier today.

## This is a negative result on the founding hypothesis, and it leads

The project was designed around conditional *harm*. What the data shows is different and
simpler:

- **Where a memory bears on a task, it helps** — paired within-memory effect **+0.3349**,
  episode-clustered CI **[0.1974, 0.4736]**, p = 0.00005, 31 memories positive vs 4
  negative.
- **Where it does not bear, it does approximately nothing** — matched control **+0.0274**,
  and MC vs RANDOM is null (−0.0368, p = 0.2281).
- **Bearing is rare** — a memory bears on a median of **one** future task out of hundreds.

So memory utility in this corpus is **not** well described as "sometimes helpful, sometimes
harmful, depending on the task." It is better described as **sparse and one-sided**: almost
always inert, occasionally strongly positive, and — on the evidence here — rarely harmful.

## The reframing this forces

| original framing | what the data supports |
|---|---|
| *utility is task-conditional, with sign reversal* | utility is **task-conditional in magnitude**, concentrated on rare bearing pairs |
| headline = sign-flip rate | headline = **the bearing effect and its scarcity** |
| a scalar is wrong because the sign varies | a scalar is wrong because it **averages a large effect over overwhelmingly many inert pairs** |

That last row still supports the paper's title question — *what is this memory useful for?*
— and still refutes a single global `Value(memory)`. But it refutes it for a **different
reason** than we hypothesized, and the paper must say so plainly rather than quietly
retiring the sign-flip metric.

## What must NOT be claimed

- ❌ a harmful-memory rate — this design **screened for bearing**, which selects toward
  helpful pairings. 2 negative cells is not a prevalence estimate.
- ❌ that harm does not occur in agent memory — **we measured one corpus, one reader, one
  representation**, on pairs chosen to bear. RANDOM's 26/872 negatives are also not a
  natural rate, since the pairing is still ours.
- ❌ that the original hypothesis is refuted in general. It is **unsupported here**, which
  is a narrower and more defensible statement.

## Why this is a better paper than the one we planned

A sign-flip rate would have been a number about a phenomenon. What we have instead is a
mechanism with three mutually supporting measurements — scarcity, the dilution it causes,
and the effect that appears once the dilution is removed — plus a **documented negative on
our own founding hypothesis**.

The kill criterion in `PROJECT_GOAL.md` is **not** triggered: it required the interaction
to be inside the noise floor *and* the phenomenon to be absent. The phenomenon is present
and large; it is the **sign-reversal component** that is absent.

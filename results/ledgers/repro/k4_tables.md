### Run

- planned_calls: **5198**
- real_endpoint_calls: **5198**
- cache_hits: **0**
- errors: **0**
- rows_written: **2599**
- n_cells: **1157**
- n_memories: **60**
- n_source_episodes: **35**
- n_tasks: **218**
- wall_clock_s: **2930.19**
- context tokens: min 14060 median **24144** max 38438

### 1. both-arms-fail per stratum (instrument capacity)

| stratum | both-arms-fail | n cells | Wilson 95% CI |
|---|---|---|---|
| BEARING | **0.5252** | 139 | [0.4426, 0.6064] |
| MATCHED_CONTROL | **0.7877** | 146 | [0.7144, 0.8462] |
| RANDOM | **0.7007** | 872 | [0.6695, 0.7301] |

Unscreened comparator: handwritten **0.785**, official **0.8375**

### 2. ΔU distribution before labelling, per stratum

| stratum | n cells | positive | zero | negative | mean ΔU over cells |
|---|---|---|---|---|---|
| BEARING | 139 | 50 | 87 | 2 | **0.3453** |
| MATCHED_CONTROL | 146 | 10 | 130 | 6 | **0.0274** |
| RANDOM | 872 | 82 | 764 | 26 | **0.0642** |

### 3. Flip rates per stratum — THE FOUNDING HYPOTHESIS

| stratum | eligible memories | naive flips | robust flips | rate | Wilson 95% CI |
|---|---|---|---|---|---|
| BEARING | **35** | **0** | 0 | **0.0000** | [0.0000, 0.0989] |
| MATCHED_CONTROL | **35** | **1** | 1 | **0.0286** | [0.0051, 0.1453] |
| RANDOM | **60** | **17** | 17 | **0.2833** | [0.1851, 0.4077] |

**VERDICT:** SIGN-REVERSAL COMPONENT NOT SUPPORTED: 0 of 35 flip-eligible BEARING memories show both a positive and a negative dU task; the Wilson upper bound is 0.09890099232440402. This BOUNDS the rate; it is not merely an absence of observations.

robust/naive gap: **NOT_MEASURABLE** - F_exec[delta] == 0 for a deterministic reader, so section 4's magnitude clause |mean dU| > F is vacuous and robust == naive by construction. A gap of 

### 4. Excess over the additive null (prereg A1.1)

| stratum | observed flip rate | additive-null mean | null 95% band | p (one-sided) | excess |
|---|---|---|---|---|---|
| BEARING | 0.0000 | 0.2286 | [0.2286, 0.2286] | 1.0000 | **-0.2286** |
| MATCHED_CONTROL | 0.0286 | 0.7143 | [0.7143, 0.7143] | 1.0000 | **-0.6857** |
| RANDOM | 0.2833 | 1.0000 | [1.0000, 1.0000] | 1.0000 | **-0.7167** |

A1.1: a flip rate is NOT evidence of interaction. A purely additive model
produces 60-90% sign flips. The **excess** over the fitted additive null is
what would constitute evidence - and every excess here is NEGATIVE.

### 5. Floors per stratum (all positive-controlled)

| stratum | F_exec[ΔU] (diag) | F_empty | F_judge | pc F_exec fires | pc F_judge fires |
|---|---|---|---|---|---|
| BEARING | 0.0000 | — | 0.0000 | True | True |
| MATCHED_CONTROL | 0.0000 | — | 0.0000 | True | True |
| RANDOM | 0.0000 | — | 0.0000 | True | True |

POOLED reference floor used for all labels: **0.0000**

### 5b. WITHIN-MEMORY paired contrast (memory identity cancels)

| contrast | n memories | n episodes | paired diff | memory CI | episode CI | sign-flip p | +/0/- |
|---|---|---|---|---|---|---|---|
| BEARING_vs_MATCHED_CONTROL | 60 | 35 | **0.3349** | [0.2085,0.4606] | **[0.1974,0.4736]** | 0.0000 | 31/25/4 |
| BEARING_vs_RANDOM | 60 | 35 | **0.3053** | [0.1969,0.4142] | **[0.1696,0.4403]** | 0.0000 | 32/7/21 |

**Zero contributors** (docs/ZERO_CONTRIBUTORS.md) - never quote the nominal count alone

| contrast | denominator | non-zero | power status | diluted mean (verdict) | conditional mean (descriptive) |
|---|---|---|---|---|---|
| BEARING_vs_MATCHED_CONTROL | 60 memories | **35** | **ADEQUATE** | 0.3349 | 0.5740 |
| BEARING_vs_RANDOM | 60 memories | **53** | **ADEQUATE** | 0.3053 | 0.3456 |

The **diluted** mean carries the significance verdict (pre-registered, does not
condition on an outcome). The **conditional** mean is descriptive only. A memory
contributing zero is one whose tasks the reader could not solve either way - a
third view of the same scarcity finding, not a nuisance to average over quietly.

All 60 memories appear in BOTH strata, so memory identity cancels: "bearing memories are just better memories" cannot explain a within-memory
difference. Task identity does NOT cancel, which is why dU is the quantity
and why the task-clustered intervals below remain required.
The **episode-clustered** interval governs where the two disagree.

### 6. Contrasts (task-clustered; cells are NOT independent)

| contrast | mean A | mean B | difference | cell-level p | task-clustered CI | excl 0 |
|---|---|---|---|---|---|---|
| BEARING_vs_MATCHED_CONTROL | 0.3453 | 0.0274 | **0.3179** | 0.0000 | [0.1724, 0.4693] | **True** |
| BEARING_vs_RANDOM | 0.3453 | 0.0642 | **0.2811** | 0.0000 | [0.1218, 0.4457] | **True** |
| MATCHED_CONTROL_vs_RANDOM | 0.0274 | 0.0642 | **-0.0368** | 0.2281 | [-0.1424, 0.0548] | **False** |

**Leave-one-task-out** (does ONE question carry the difference?)

| contrast | n tasks | drop-one min | drop-one max | worst task | diff without it | sign stable |
|---|---|---|---|---|---|---|
| BEARING_vs_MATCHED_CONTROL | 126 | 0.2884 | 0.3375 | c843c4ec | **0.2884** | **True** |
| BEARING_vs_RANDOM | 179 | 0.2513 | 0.3117 | c843c4ec | **0.2513** | **True** |
| MATCHED_CONTROL_vs_RANDOM | 201 | -0.0518 | -0.0063 | eef545a0 | **-0.0063** | **True** |

### 6b. Cell concentration — a design characteristic

| scope | cells | tasks | max on one task | tasks >=20 cells | top-10 share | tasks holding half |
|---|---|---|---|---|---|---|
| ALL | 1157 | 218 | 40 | 24 | **34.6%** | 17 |
| BEARING | 139 | 56 | 6 | 0 | **38.8%** | 15 |
| MATCHED_CONTROL | 146 | 100 | 4 | 0 | **19.9%** | 32 |
| RANDOM | 872 | 147 | 40 | 19 | **44.6%** | 12 |

The shared task grid is the identifiability fix AND the source of this
concentration - one design tension, not two problems.

### 6c. Clustered vs cell-level

Clustered and cell-level agree on every contrast.

### 7. Variance decomposition identifiability

- POOLED identified: **False**
  - ⚠️ AT_UPPER_BOUNDARY:task variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is saying this component is unbounded relati
  - ⚠️ AT_UPPER_BOUNDARY:interaction variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is saying this component is unbounded
  - interaction: 0.499998
  - memory: 0.000000
  - residual: 0.000003
  - task: 0.499998
- tasks/memory mean **19.3** (prior 8); memories/task mean 11.9
- tasks seen by 1 memory: **0** of 218 (prior 93 of 220); by >=10 memories: **59**
- shared grid enterprise: 20x12 crossed, identified=**False**
    ⚠️ AT_UPPER_BOUNDARY:task variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is saying this
    ⚠️ AT_UPPER_BOUNDARY:interaction variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is sayi
    MoM shares: {'interaction': 0.5876, 'memory': 0.0, 'residual': 0.0, 'task': 0.4124}
- shared grid web: 40x12 crossed, identified=**False**
    ⚠️ AT_UPPER_BOUNDARY:task variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is saying this
    ⚠️ AT_UPPER_BOUNDARY:interaction variance ratio is pinned at the optimizer's clip ceiling (exp(12)). The likelihood is sayi
    MoM shares: {'interaction': 0.6044, 'memory': 0.0, 'residual': 0.0, 'task': 0.3956}

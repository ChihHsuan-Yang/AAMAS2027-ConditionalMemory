"""Synthetic row generator with a KNOWN generative model.

No real data exists (P1-051..053 are all BLOCKED), and every estimator in this package
has to be shown to recover a planted truth before it is pointed at a real number. This
module is that source of truth. It is a *test instrument*, not an analysis step: nothing
in ``noise.py``, ``labels.py``, ``decomposition.py`` or ``efficiency.py`` imports it.

The generative model is exactly the pre-registered one
(``docs/ANALYSIS_PREREGISTRATION.md`` section 6):

    dU(m, t, s) = mu + a_m + b_t + (ab)_mt + eps_s

with ``a_m ~ N(0, sd_memory^2)``, ``b_t ~ N(0, sd_task^2)``,
``(ab)_mt ~ N(0, sd_interaction^2)`` and ``eps_s ~ N(0, sd_noise^2)``.

Two properties are built in deliberately, because the estimators depend on them:

* **The WITHOUT arm is the same CONDITION for every memory on a task, independently
  EXECUTED per cell.** ``docs/MEMORY_PROTOCOL.md`` section 4 fixes the no-memory arm as a
  fixed controlled filler with the target memory removed, so for a given task every
  memory's WITHOUT arm runs the identical prompt. Each cell still executes it, so the
  observations are independent draws from one condition -- which is exactly why their
  spread across memories is a floor obtained at no extra cost (prereg section 2).
  ``R_without(m,t,s) = base(t) + eta``, ``eta ~ N(0, sd_exec_without^2)``, drawn per row.
  ``cache_without_arm=True`` instead simulates a harness that generated the no-memory
  answer once per task and copied it -- spread 0 by construction, a *fake* free floor.
  That is the pathology ``noise.empty_floor`` must refuse, and the generator can produce
  it so the guard can be shown to fire.
* **Execution noise enters BOTH arms.** ``R_with = base(t) + dU_true(m,t) + xi``,
  ``xi ~ N(0, sd_exec_with^2)``. Hence
  ``dU = dU_true + (xi - eta)`` and the planted residual SD on the dU scale is
  ``sqrt(sd_exec_with^2 + sd_exec_without^2)`` -- ``TruthSpec.sd_delta_noise()``. The
  per-arm and dU-scale floors are therefore different numbers by construction, which is
  the scale distinction ``noise.py`` carries in ``Estimate.scale``.

``zero_interaction=True`` gives the null control: ``sd_interaction = 0`` with everything
else intact. A method that reports flips on that data is finding structure in noise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from p1mem import schema

# ------------------------------------------------------------------ fixed identity
# One cluster, one model, one verifier: the guards in common.py refuse to pool across
# these, and synthetic data must not trip a guard it is not testing.
PINNED = {
    "reader_cluster": "metis",
    "reader_model": "gpt-oss-120b",
    "reader_endpoint": "metis:/resource_server/metis/api/v1",
    "reader_prompt_version": "reader_v1",
    "reader_reasoning_effort": "low",
    "verifier_id": "norm_phrase_set_match",
    "verifier_version": "v1",
    "embedding_model": "Salesforce/SFR-Embedding-Mistral",
    "embedding_version": "rev-synthetic",
    "memory_writer_cluster": "metis",
    "memory_writer_prompt_version": "writer_v1",
}

#: Formation cost per representation (docs/MEMORY_PROTOCOL.md section 5 + the table in
#: section 1): raw costs ~0 calls; summary and structured cost 1 call each per segment.
REPRESENTATION_COST = {
    "raw":        {"calls": 0, "in_tok": None, "out_tok": None, "latency": None, "tok_scale": 1.00},
    "summary":    {"calls": 1, "in_tok": 1800, "out_tok": 120,  "latency": 3.1,  "tok_scale": 0.18},
    "structured": {"calls": 1, "in_tok": 1800, "out_tok": 160,  "latency": 3.6,  "tok_scale": 0.24},
}


@dataclass
class TruthSpec:
    """The planted parameters. Every field here is a number an estimator must recover."""

    n_memories: int = 24
    n_tasks: int = 6
    n_replicates: int = 3
    mu: float = 0.0
    sd_memory: float = 0.20
    sd_task: float = 0.15
    sd_interaction: float = 0.25
    #: Execution noise of the WITH arm, per (memory, task, replicate).
    sd_exec_with: float = 0.10
    #: Execution noise of the WITHOUT arm, per (memory, task, replicate).
    #: This IS the F_empty truth: F_empty measures it ACROSS MEMORIES for free, while
    #: F_exec[without] measures the same quantity across replicates.
    sd_exec_without: float = 0.08
    #: Task base reward level, and its spread across tasks.
    without_mean: float = 0.45
    sd_task_base: float = 0.05
    seed: int = 20260929
    representations: Sequence[str] = ("raw", "summary", "structured")
    benchmark: str = "longmemeval_v2"
    #: When True, sd_interaction is forced to 0 -- the zero-interaction null control.
    zero_interaction: bool = False
    #: When True the WITHOUT arm is generated ONCE per (task, replicate) and copied into
    #: every memory's row: the cached-arm pathology, for testing the F_empty guard.
    cache_without_arm: bool = False
    #: When True every row's stored semantic_distance_band is "MID" regardless of the
    #: similarity -- a populator bug, for testing the figure-4 consistency check.
    band_populator_bug: bool = False

    def effective_sd_interaction(self) -> float:
        return 0.0 if self.zero_interaction else float(self.sd_interaction)

    def sd_delta_noise(self) -> float:
        """Planted residual SD on the dU scale: both arms' execution noise combined."""
        return math.sqrt(self.sd_exec_with ** 2 + self.sd_exec_without ** 2)

    def variance_shares(self) -> dict[str, float]:
        """The planted shares of total variance -- what decomposition.py must recover."""
        v = {
            "memory": self.sd_memory ** 2,
            "task": self.sd_task ** 2,
            "interaction": self.effective_sd_interaction() ** 2,
            "residual": self.sd_delta_noise() ** 2,
        }
        total = sum(v.values())
        return {k: (x / total if total > 0 else 0.0) for k, x in v.items()}

    def variance_components(self) -> dict[str, float]:
        return {
            "memory": self.sd_memory ** 2,
            "task": self.sd_task ** 2,
            "interaction": self.effective_sd_interaction() ** 2,
            "residual": self.sd_delta_noise() ** 2,
        }


@dataclass
class SyntheticDataset:
    rows: list[dict[str, Any]]
    spec: TruthSpec
    #: The realized draws, so a test can compare against what was actually drawn rather
    #: than only against the distribution it was drawn from.
    a_memory: dict[str, float] = field(default_factory=dict)
    b_task: dict[str, float] = field(default_factory=dict)
    ab_interaction: dict[tuple[str, str], float] = field(default_factory=dict)
    true_delta: dict[tuple[str, str], float] = field(default_factory=dict)
    without_by_task_rep: dict[tuple[str, int], float] = field(default_factory=dict)
    task_base: dict[str, float] = field(default_factory=dict)

    def realized_components(self) -> dict[str, float]:
        """Variance of the DRAWN effects.

        With 24 memories and 6 tasks the drawn sample variance differs from the
        population sd^2 by a lot; an estimator should be scored against these, and the
        gap between these and ``spec.variance_components()`` is sampling error in the
        *generator*, not error in the estimator.
        """
        def var(xs):
            arr = np.asarray(list(xs), dtype=float)
            return float(arr.var(ddof=1)) if arr.size > 1 else 0.0
        return {
            "memory": var(self.a_memory.values()),
            "task": var(self.b_task.values()),
            "interaction": var(self.ab_interaction.values()),
            "residual": self.spec.sd_delta_noise() ** 2,
        }


def make_dataset(spec: TruthSpec | None = None, **overrides: Any) -> SyntheticDataset:
    """Generate a full crossed memory x task x replicate design in canonical rows."""
    spec = spec or TruthSpec()
    if overrides:
        spec = TruthSpec(**{**spec.__dict__, **overrides})
    rng = np.random.default_rng(spec.seed)

    reps = list(spec.representations)
    # A memory index carries a representation; the same source episode yields one memory
    # per representation, which is what makes the section 9 comparison within-episode.
    n_episodes = max(1, spec.n_memories // max(1, len(reps)))
    episodes = [f"ep{e:03d}" for e in range(n_episodes)]

    mem_keys: list[tuple[str, str]] = []  # (episode, representation)
    while len(mem_keys) < spec.n_memories:
        for ep in episodes:
            for r in reps:
                if len(mem_keys) < spec.n_memories:
                    mem_keys.append((ep, r))

    tasks = [f"task{t:03d}" for t in range(spec.n_tasks)]

    sd_ab = spec.effective_sd_interaction()
    a = {f"{ep}:{rep}": float(rng.normal(0.0, spec.sd_memory)) for ep, rep in mem_keys}
    b = {t: float(rng.normal(0.0, spec.sd_task)) for t in tasks}
    ab = {
        (m, t): (float(rng.normal(0.0, sd_ab)) if sd_ab > 0 else 0.0)
        for m in a for t in tasks
    }

    # The WITHOUT arm's CONDITION depends on the task alone -- the same filler prompt for
    # every memory (MEMORY_PROTOCOL section 4). Its base level is therefore per task.
    base = {t: float(rng.normal(spec.without_mean, spec.sd_task_base)) for t in tasks}
    # Cached-arm pathology: one execution per (task, replicate), copied everywhere.
    cached = {
        (t, s): float(rng.normal(base[t], spec.sd_exec_without))
        for t in tasks
        for s in range(spec.n_replicates)
    }

    # Similarity: per (memory, task), independent of utility by default so the section 8
    # correlation has a known null. Tests that want a relationship inject one afterwards.
    sim = {(m, t): float(rng.uniform(0.15, 0.85)) for m in a for t in tasks}

    # Band the similarities by tercile now, so the STORED semantic_distance_band agrees
    # with a correct recomputation. A generator that always writes "MID" would make
    # figures.figure4_data's band-consistency check fire on every run and therefore
    # detect nothing; ``band_populator_bug=True`` restores that pathology on purpose.
    _sims = sorted(sim.values())
    _lo = _sims[len(_sims) // 3]
    _hi = _sims[2 * len(_sims) // 3]

    def _band(v: float) -> str:
        if spec.band_populator_bug:
            return "MID"
        return "NEAR" if v > _hi else ("MID" if v > _lo else "FAR")

    rows: list[dict[str, Any]] = []
    true_delta: dict[tuple[str, str], float] = {}
    for (ep, rep) in mem_keys:
        mkey = f"{ep}:{rep}"
        cost = REPRESENTATION_COST[rep]
        base_tokens = 900
        mem_tokens = int(round(base_tokens * cost["tok_scale"]))
        for t in tasks:
            true_delta[(mkey, t)] = spec.mu + a[mkey] + b[t] + ab[(mkey, t)]
            for s in range(spec.n_replicates):
                if spec.cache_without_arm:
                    r_without = cached[(t, s)]
                    without_text = f"[synthetic without {t}/{s}]"
                else:
                    r_without = float(rng.normal(base[t], spec.sd_exec_without))
                    # Independent executions produce distinct bytes; a cached arm does
                    # not. The text carries the distinction the guard reads.
                    without_text = f"[synthetic without {t}/{s}/{mkey}]"
                xi = float(rng.normal(0.0, spec.sd_exec_with))
                r_with = base[t] + true_delta[(mkey, t)] + xi
                rows.append(
                    _row(
                        spec=spec,
                        episode=ep,
                        representation=rep,
                        memory_key=mkey,
                        memory_tokens=mem_tokens,
                        task=t,
                        replicate=s,
                        reward_with=r_with,
                        reward_without=r_without,
                        similarity=sim[(mkey, t)],
                        band=_band(sim[(mkey, t)]),
                        cost=cost,
                        without_text=without_text,
                    )
                )
    return SyntheticDataset(
        rows=rows, spec=spec, a_memory=a, b_task=b, ab_interaction=ab,
        true_delta=true_delta, without_by_task_rep=cached, task_base=base,
    )


def _row(
    *,
    spec: TruthSpec,
    episode: str,
    representation: str,
    memory_key: str,
    memory_tokens: int,
    task: str,
    replicate: int,
    reward_with: float,
    reward_without: float,
    similarity: float,
    cost: dict[str, Any],
    band: str = "MID",
    without_text: str | None = None,
    retrieval_method: str = "keep_all",
    retrieval_k: int | None = None,
    retrieval_rank: int | None = None,
    tokens_exposed: int | None = None,
    tokens_retrieved: int | None = None,
) -> dict[str, Any]:
    exposed = memory_tokens if tokens_exposed is None else tokens_exposed
    retrieved = memory_tokens if tokens_retrieved is None else tokens_retrieved
    return schema.new_row(
        benchmark=spec.benchmark,
        benchmark_version="synthetic-v1",
        source_episode_id=episode,
        source_episode_metadata={"synthetic": True},
        memory_representation=representation,
        memory_semantic_type="episodic",
        memory_text=f"[synthetic memory {memory_key}]",
        memory_tokens=memory_tokens,
        memory_source_span={"session_id": episode, "turn_start": 0, "turn_end": 3},
        memory_writer_model=("none:deterministic_span" if representation == "raw"
                             else "gpt-oss-120b"),
        memory_writer_cluster=("none:deterministic_span" if representation == "raw"
                               else PINNED["memory_writer_cluster"]),
        memory_writer_prompt_version=PINNED["memory_writer_prompt_version"],
        memory_extraction_latency=cost["latency"],
        memory_extraction_input_tokens=cost["in_tok"],
        memory_extraction_output_tokens=cost["out_tok"],
        embedding_model=PINNED["embedding_model"],
        embedding_version=PINNED["embedding_version"],
        memory_embedding_reference={"store": "emb.npy", "index": 0, "dim": 4096, "sha256": "0" * 64},
        future_task_id=task,
        future_task_family="synthetic-family",
        future_task_text=f"[synthetic task {task}]",
        task_embedding_reference={"store": "emb.npy", "index": 1, "dim": 4096, "sha256": "0" * 64},
        semantic_similarity=similarity,
        semantic_distance_band=band,
        retrieval_method=retrieval_method,
        retrieval_rank=retrieval_rank,
        retrieval_k=retrieval_k,
        memory_tokens_retrieved=retrieved,
        memory_tokens_exposed=exposed,
        replicate_id=replicate,
        seed_or_sampling_config={"seed": 1000 + replicate, "temperature": 0,
                                 "top_p": 1.0, "max_tokens": 512},
        reader_model=PINNED["reader_model"],
        reader_cluster=PINNED["reader_cluster"],
        reader_endpoint=PINNED["reader_endpoint"],
        reader_prompt_version=PINNED["reader_prompt_version"],
        reader_reasoning_effort=PINNED["reader_reasoning_effort"],
        output_without_memory=(without_text or f"[synthetic without {task}/{replicate}]"),
        output_with_memory=f"[synthetic with {memory_key}/{task}/{replicate}]",
        reward_without_memory=reward_without,
        reward_with_memory=reward_with,
        write_latency=cost["latency"],
        retrieval_latency=0.02,
        generation_latency=2.4,
        end_to_end_latency=5.0,
        embedding_calls=0,
        generation_calls=2,
        input_tokens=2400 + exposed,
        output_tokens=180,
        reasoning_tokens=64,
        retry_count=0,
        error_code_if_any=None,
        provenance={"code_sha": "synthetic", "config_sha256": "0" * 64,
                    "run_id": "synthetic", "host": "local", "writer": "synthetic.py"},
        license_source_reference="synthetic:none",
        verifier_id=PINNED["verifier_id"],
        verifier_version=PINNED["verifier_version"],
        reward_is_continuous=True,
        leakage_flag=False,
        reader_endpoint_sha256=schema.sanitized_base_url_hash(PINNED["reader_endpoint"]),
    )


# ---------------------------------------------------------------- planted structures
def plant_sign_flip(
    ds: SyntheticDataset,
    memory_key: str,
    useful_task: str,
    harmful_task: str,
    *,
    magnitude: float = 0.60,
) -> SyntheticDataset:
    """Force one memory to be strongly useful on one task and harmful on another.

    Used to prove the flip detector can FIRE. A detector only ever run on data with no
    flips cannot be distinguished from a detector that never fires.
    """
    for row in ds.rows:
        mkey = f"{row['source_episode_id']}:{row['memory_representation']}"
        if mkey != memory_key:
            continue
        if row["future_task_id"] == useful_task:
            target = +magnitude
        elif row["future_task_id"] == harmful_task:
            target = -magnitude
        else:
            continue
        # Keep the existing per-replicate noise so the CI stays honest; only shift the
        # cell mean. Recomputing the noise would plant a cleaner effect than the model.
        old_delta = row["reward_with_memory"] - row["reward_without_memory"]
        old_mean = ds.true_delta[(mkey, row["future_task_id"])]
        row["reward_with_memory"] = row["reward_without_memory"] + target + (old_delta - old_mean)
        row["delta_utility"] = row["reward_with_memory"] - row["reward_without_memory"]
        ds.true_delta[(mkey, row["future_task_id"])] = target
    return ds


def set_similarity_utility_link(ds: SyntheticDataset, slope: float) -> SyntheticDataset:
    """Make dU depend linearly on similarity, for the section 8 correlation tests."""
    for row in ds.rows:
        shift = slope * (float(row["semantic_similarity"]) - 0.5)
        row["reward_with_memory"] = float(row["reward_with_memory"]) + shift
        row["delta_utility"] = row["reward_with_memory"] - row["reward_without_memory"]
    return ds


def inject_errors(ds: SyntheticDataset, n: int, code: str = "empty_output_finish_length"):
    """Turn ``n`` rows into errored rows with no outcome, to test admission."""
    for row in ds.rows[:n]:
        row["error_code_if_any"] = code
        row["output_with_memory"] = None
        row["reward_with_memory"] = None
        row["delta_utility"] = None
    return ds


def retrieval_sweep_rows(
    ds: SyntheticDataset,
    *,
    ks: Sequence[int] = (1, 3, 5),
    exposure_per_memory: int = 150,
) -> list[dict[str, Any]]:
    """Copies of the dataset under no / keep_all / top_k(k) / oracle retrieval.

    Built so ``figures.py`` Figure 2 has the four arms crossed with representation it
    needs. Exposure grows with k and the realized dU grows sublinearly with it, so the
    frontier has the concave shape a frontier is supposed to have -- but the *shape* is
    an artifact of this generator and proves only that the plot can be drawn, never that
    the real frontier looks like this.
    """
    out: list[dict[str, Any]] = []
    arms: list[tuple[str, int | None, int]] = [("none", None, 0)]
    arms += [("top_k", int(k), int(k)) for k in ks]
    arms += [("keep_all", None, max(ks) * 2), ("oracle", None, 1)]
    for method, k, n_mem in arms:
        for row in ds.rows:
            r = dict(row)
            r["retrieval_method"] = method
            r["retrieval_k"] = k
            r["retrieval_rank"] = 1 if method == "top_k" else None
            exposed = n_mem * exposure_per_memory
            r["memory_tokens_retrieved"] = exposed
            r["memory_tokens_exposed"] = exposed
            base = float(row["reward_without_memory"])
            gain = float(row["reward_with_memory"]) - base
            if method == "none":
                factor = 0.0
            elif method == "oracle":
                factor = 1.0
            elif method == "keep_all":
                factor = 0.55
            else:
                factor = min(1.0, 0.45 + 0.12 * (k or 0))
            r["reward_with_memory"] = base + factor * gain
            r["delta_utility"] = r["reward_with_memory"] - base
            r["input_tokens"] = 2400 + exposed
            r["cell_id"] = schema.compute_cell_id(r)
            r["row_id"] = schema.compute_row_id(r)
            out.append(r)
    return out


__all__ = [
    "TruthSpec", "SyntheticDataset", "make_dataset", "plant_sign_flip",
    "set_similarity_utility_link", "inject_errors", "retrieval_sweep_rows",
    "REPRESENTATION_COST", "PINNED",
]

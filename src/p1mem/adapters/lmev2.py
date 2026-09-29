"""LongMemEval-V2 adapter: memory units, future tasks, and official scoring.

LongMemEval-V2 (Wu et al.) evaluates long-term agent memory over web-agent
trajectories. This module maps it onto the frozen scientific object

    DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)

Provenance
----------
data   : https://huggingface.co/datasets/xiaowu0162/longmemeval-v2  (Apache-2.0)
code   : https://github.com/xiaowu0162/LongMemEval-V2  @ 2cc8c540  (Apache-2.0)
scorer : vendored VERBATIM at p1mem.adapters.vendor.lmev2_qa_eval_metrics
         (sha256 f8ba659e...417ac; see that module's docstring). We call the
         benchmark's own scorer rather than reimplementing from the function
         name -- ``norm_phrase_set_match`` in particular is NOT set equality
         but gold-phrase containment, which a name-based reimplementation
         would get wrong.

The three units
---------------
MEMORY UNIT -- a ``PageVisit``: the maximal run of consecutive trajectory
states sharing one URL, inside one past trajectory. Naturally occurring
(the agent's own navigation defines the boundaries), computable from the
trajectory alone, and defined WITHOUT any reference to any question. See
:func:`segment_page_visits` for the boundary rule and the measured token
distribution in ``data/manifests/lmev2_memory_unit_tokens.json``.

FUTURE-TASK UNIT -- a ``FutureTask``: one question with its ``eval_function``
spec. Only the 295 deterministically-scored questions are eligible for the
primary analysis; the 156 LLM-judged ones are carried with
``deterministic=False`` so they can be reported separately, never silently
mixed in.

PAIRING -- :func:`select_pairs`, deterministic given a seed. On the ``small``
tier every memory in a domain is available to every question in that domain,
so pairing is unconstrained and we must impose and document our own rule
rather than inherit one.

The writer never sees the future task
-------------------------------------
Enforced structurally, not by convention: :func:`segment_page_visits` takes a
trajectory and nothing else. There is no code path by which a question can
reach it. :func:`assert_writer_blind` re-checks this at runtime for a built
memory set and is called by ``scripts/build_lmev2_units.py``.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

# --------------------------------------------------------------------------
# provenance constants -- measured, not recalled
# --------------------------------------------------------------------------

VENDORED_SCORER_SHA256 = (
    "f8ba659e237c4282a07a92538090ea500ce8483820b390b1d19af187c01417ac"
)
UPSTREAM_COMMIT = "2cc8c540bdb87fe6761629b585e727e1c4704520"
#: sha256 of upstream evaluation/harness.py, byte-identical to the harness.py
#: shipped inside the data snapshot. This is what ties the vendored scorer to
#: the data we actually measured.
HARNESS_SHA256 = "93fe5855a74ad46d7e8b489cebac24de38a9b30ba7ec1de2dd8708bd4aeebdb6"

#: The tokenizer evaluation/harness.py::get_memory_context_processor() loads.
#: Token counts reported anywhere in this project use THIS tokenizer, so that
#: our budgets are comparable to the benchmark's own.
OFFICIAL_TOKENIZER = "Qwen/Qwen3.5-9B"

LLM_EVAL_FUNCTIONS = frozenset({"llm_abstention_checker", "llm_gotchas_checker"})

#: Expected sha256 for the data files we verify. Copied from the dataset's own
#: checksums.sha256; verify_checksums() re-derives rather than trusting these.
EXPECTED_FILES = (
    "questions.jsonl",
    "trajectories.jsonl",
    "haystacks/lme_v2_small.json",
    "haystacks/lme_v2_medium.json",
)


#: The vendored official scorer uses PEP 604 (``str | None``) at module scope,
#: so it cannot even be IMPORTED below Python 3.10. We refuse to run rather
#: than fall back to a reimplementation: a silently-substituted scorer is
#: exactly the failure this module exists to prevent.
MIN_PYTHON = (3, 10)


class DataError(RuntimeError):
    """Raised when the dataset on disk is not the dataset we verified."""


def require_supported_python() -> None:
    if sys.version_info < MIN_PYTHON:
        raise DataError(
            f"p1mem.adapters.lmev2 needs Python >= {'.'.join(map(str, MIN_PYTHON))} "
            f"(running {sys.version.split()[0]}). The vendored official "
            "LongMemEval-V2 scorer uses PEP 604 unions at module scope and "
            "cannot be imported on older interpreters. Do NOT work around "
            "this by reimplementing the scorer."
        )


# --------------------------------------------------------------------------
# loading + checksum verification
# --------------------------------------------------------------------------


def sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def parse_checksums(root: Path) -> dict[str, str]:
    """Parse the dataset's shipped ``checksums.sha256``."""
    path = root / "checksums.sha256"
    if not path.exists():
        raise DataError(f"missing {path}: cannot verify the data without it")
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, name = line.partition("  ")
        if digest and name:
            out[name] = digest
    return out


def verify_checksums(
    root: Path, files: Sequence[str] = EXPECTED_FILES, *, strict: bool = True
) -> dict[str, str]:
    """Verify each file against the dataset's own checksums.sha256.

    Returns {filename: "OK" | "MISSING" | "MISMATCH(...)"}. With ``strict``
    (the default) any non-OK raises. A missing file is reported as MISSING and
    never silently treated as passing -- absence must not read as success.
    """
    expected = parse_checksums(root)
    report: dict[str, str] = {}
    for name in files:
        path = root / name
        if name not in expected:
            report[name] = "NO_EXPECTED_CHECKSUM"
        elif not path.exists():
            report[name] = "MISSING"
        else:
            got = sha256_file(path)
            report[name] = "OK" if got == expected[name] else f"MISMATCH(got={got})"
    if strict:
        bad = {k: v for k, v in report.items() if v != "OK"}
        if bad:
            raise DataError(f"checksum verification failed: {bad}")
    return report


def verify_vendored_scorer() -> str:
    """Re-check that the vendored scorer is the byte-exact upstream file."""
    from p1mem.adapters import vendor  # noqa: PLC0415

    path = Path(vendor.__file__).parent / "lmev2_qa_eval_metrics.py"
    got = sha256_file(path)
    if got != VENDORED_SCORER_SHA256:
        raise DataError(
            f"vendored scorer has been modified: expected "
            f"{VENDORED_SCORER_SHA256}, got {got}. It must stay verbatim."
        )
    return got


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# --------------------------------------------------------------------------
# future-task unit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FutureTask:
    """One question = one future task, with its deterministic reward."""

    id: str
    domain: str
    environment: str
    question_type: str
    question: str
    answer: str
    eval_function: str
    image: str | None

    @property
    def eval_name(self) -> str:
        return self.eval_function.split("|", 1)[0].strip()

    @property
    def deterministic(self) -> bool:
        """True when the reward needs no LLM judge.

        Only these questions are eligible for the primary DeltaU analysis --
        an LLM-judged reward has its own nondeterminism that would be
        confounded with the memory effect.
        """
        return self.eval_name not in LLM_EVAL_FUNCTIONS

    @property
    def is_abstention(self) -> bool:
        return self.question_type.endswith("-abs")

    def score(self, prediction: str) -> bool:
        """Reward(t | prediction), using the BENCHMARK'S OWN scorer.

        Raises for LLM-judged questions rather than returning a default:
        this module makes no inference calls, and a silent False here would
        turn "cannot evaluate" into "wrong answer".
        """
        if not self.deterministic:
            raise NotImplementedError(
                f"{self.id} uses {self.eval_name}, which requires an LLM judge. "
                "Sub-agent C owns the endpoint; this module makes no inference "
                "calls. Do not substitute a default score."
            )
        require_supported_python()
        from p1mem.adapters.vendor.lmev2_qa_eval_metrics import (  # noqa: PLC0415
            eval_from_spec,
        )

        return bool(eval_from_spec(self.eval_function, prediction, self.answer))


def load_tasks(root: Path, *, domain: str | None = None) -> list[FutureTask]:
    tasks = [
        FutureTask(
            id=r["id"],
            domain=r["domain"],
            environment=r["environment"],
            question_type=r["question_type"],
            question=r["question"],
            answer=r["answer"],
            eval_function=r["eval_function"],
            image=r.get("image"),
        )
        for r in read_jsonl(root / "questions.jsonl")
    ]
    if domain is not None:
        tasks = [t for t in tasks if t.domain == domain]
    return tasks


# --------------------------------------------------------------------------
# memory unit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PageVisit:
    """A memory unit: one maximal same-URL run of states in a past trajectory.

    Chosen because the boundary is drawn by the PAST AGENT'S OWN BEHAVIOUR
    (it navigated away), so it is a naturally occurring span, not a window we
    imposed and certainly not one fitted to any question.
    """

    memory_unit_locator: str
    trajectory_id: str
    domain: str
    environment: str
    outcome: str
    goal: str
    url: str
    start_state_index: int
    end_state_index: int
    n_states: int
    text: str
    n_tokens: int | None = None

    @property
    def span(self) -> tuple[int, int]:
        return (self.start_state_index, self.end_state_index)


# ---- renderers copied VERBATIM from upstream memory_modules/codex.py -------
# Using the benchmark's own rendering means our token counts and our leakage
# strings are the ones the benchmark would actually put in a context window.


def format_actions(trajectory: dict[str, Any]) -> str:
    entries = [
        a
        for a in trajectory.get("actions", [])
        if isinstance(a, str) and a.strip()
    ]
    if not entries:
        for st in trajectory.get("states", []):
            if not isinstance(st, dict):
                continue
            a = st.get("action")
            if isinstance(a, str) and a.strip():
                entries.append(a)
    if not entries:
        return "1. <no actions recorded>"
    return "\n".join(f"{i + 1}. {a}" for i, a in enumerate(entries))


def format_span_header(
    span_index: int, trajectory: dict[str, Any], start: int, end: int
) -> str:
    return (
        f"### Trajectory span {span_index}: {trajectory['id']} states {start}-{end}\n\n"
        "Goal\n"
        f"- {trajectory.get('goal', '<goal not found>')}\n\n"
        "Start URL\n"
        f"- {trajectory.get('start_url', '<start url not found>')}\n\n"
        "Actions\n"
        f"{format_actions(trajectory)}\n\n"
        "Linked state evidence\n"
    )


def format_state_text(state: dict[str, Any], evidence_mode: str = "axtree") -> str:
    av = state.get("action")
    at = av if isinstance(av, str) and av.strip() else "<none>"
    lines = [
        f"State {state['state_index']} (step {state['step']})",
        f"- URL: {state['url']}",
        f"- Action: {at}",
    ]
    if evidence_mode in {"axtree", "both"}:
        text = state.get("accessibility_tree", state.get("text"))
        lines.extend(["- AXTree:", text])
    return "\n".join(lines) + "\n"


def segment_page_visits(
    trajectory: dict[str, Any],
    *,
    include_header: bool = True,
    evidence_mode: str = "axtree",
) -> list[PageVisit]:
    """Split ONE trajectory into page-visit memory units.

    Boundary rule: a new unit starts whenever ``state["url"]`` differs from the
    previous state's URL. Nothing else. In particular this function's entire
    input is one trajectory -- it is structurally incapable of seeing a
    question, which is what makes the memory writer blind to the future task.
    """
    states = trajectory["states"]
    out: list[PageVisit] = []
    i = 0
    span_index = 0
    while i < len(states):
        j = i
        while j + 1 < len(states) and states[j + 1]["url"] == states[i]["url"]:
            j += 1
        span_index += 1
        body = "".join(format_state_text(s, evidence_mode) for s in states[i : j + 1])
        header = (
            format_span_header(span_index, trajectory, i, j) if include_header else ""
        )
        out.append(
            PageVisit(
                memory_unit_locator=f"{trajectory['id']}:{i}-{j}",
                trajectory_id=trajectory["id"],
                domain=trajectory["domain"],
                environment=trajectory["environment"],
                outcome=trajectory["outcome"],
                goal=trajectory.get("goal", ""),
                url=states[i]["url"],
                start_state_index=i,
                end_state_index=j,
                n_states=j - i + 1,
                text=header + body,
            )
        )
        i = j + 1
    return out


def assert_writer_blind(
    segmenter: Callable[..., list[PageVisit]] = segment_page_visits,
) -> None:
    """Runtime check that the memory writer cannot see a future task.

    Calls the segmenter twice on the same trajectory while varying nothing but
    a decoy 'question' injected into the record, and requires byte-identical
    output. This is weaker than the structural argument (the signature takes
    no question) but it catches a future refactor that quietly threads one in.
    """
    traj = {
        "id": "probe", "domain": "web", "environment": "webarena",
        "outcome": "success", "goal": "g", "start_url": "u0",
        "states": [
            {"state_index": 0, "step": 0, "url": "u0", "action": None,
             "thought": None, "accessibility_tree": "tree0"},
            {"state_index": 1, "step": 1, "url": "u1", "action": "click",
             "thought": None, "accessibility_tree": "tree1"},
        ],
    }
    a = [u.text for u in segmenter(traj)]
    poisoned = dict(traj, question="WHAT IS THE ANSWER", answer="42")
    b = [u.text for u in segmenter(poisoned)]
    if a != b:
        raise DataError(
            "memory segmentation changed when question fields were present: "
            "the writer is NOT blind to the future task"
        )


# --------------------------------------------------------------------------
# pairing
# --------------------------------------------------------------------------


#: Question ``environment`` values are FINER-GRAINED than trajectory ones.
#: MEASURED over the shipped data: questions use
#: {workarena, webarena-reddit, webarena-cms, webarena-onestopshop} while
#: trajectories use only {workarena, webarena}. So a naive equality test
#: ``memory.environment == task.environment`` is TRUE for every enterprise
#: pair and FALSE for every web pair -- it silently re-encodes `domain` and
#: measures nothing. We therefore compare on the coarse prefix and, crucially,
#: record that the web site-level match is UNKNOWN rather than False.
COARSE_ENVIRONMENT = {
    "workarena": "workarena",
    "webarena": "webarena",
    "webarena-reddit": "webarena",
    "webarena-cms": "webarena",
    "webarena-onestopshop": "webarena",
}


def coarse_environment(value: str) -> str:
    return COARSE_ENVIRONMENT.get(value, value.split("-", 1)[0])


@dataclass(frozen=True)
class Pair:
    """One (memory, future-task) cell of the DeltaU matrix."""

    memory_unit_locator: str
    task_id: str
    domain: str
    stratum: str
    #: True when memory and task share the COARSE environment family.
    same_environment_coarse: bool
    #: The task's fine-grained environment (e.g. "webarena-reddit").
    #: Trajectories carry no site-level label, so whether the memory came
    #: from the SAME SITE is NOT DERIVABLE from the shipped data. Recorded as
    #: None for web pairs rather than guessed -- an unknown must not be
    #: written as a False.
    task_environment: str
    memory_environment: str
    same_site: bool | None
    in_official_haystack: bool


def load_haystack(root: Path, tier: str = "small") -> dict[str, list[str]]:
    path = root / "haystacks" / f"lme_v2_{tier}.json"
    if not path.exists():
        raise DataError(f"missing haystack: {path}")
    return json.loads(path.read_text())


def select_pairs(
    memories: Sequence[PageVisit],
    tasks: Sequence[FutureTask],
    *,
    seed: int,
    tasks_per_memory: int = 8,
    deterministic_only: bool = True,
    haystack: dict[str, list[str]] | None = None,
) -> list[Pair]:
    """Deterministically select (memory, task) cells.

    Reproducible from ``seed`` alone: an independent ``random.Random(seed)`` is
    drawn per memory and keyed by ``memory_unit_locator``, so adding or removing one
    memory does not perturb any other memory's task draw.

    Rationale for the rule. On the ``small`` tier every trajectory sits in
    every same-domain question's haystack, so the benchmark imposes no
    constraint and we must supply one. We sample WITHIN domain (cross-domain
    pairs are meaningless: the web and enterprise trajectory pools are
    disjoint and the environments differ) and stratify by ``question_type``,
    which is the benchmark's own memory-ability taxonomy and therefore an
    externally-authored proxy for semantic distance rather than one we chose
    to flatter the result. Each memory draws at most one task per stratum
    before any stratum repeats, so every memory is evaluated against a SPREAD
    of future-task kinds rather than several near-duplicates -- which is the
    "multiple future tasks at controlled semantic distance" the design needs.

    ``in_official_haystack`` records, per cell, whether the benchmark authors
    placed this trajectory in this question's ``medium``-tier haystack. That is
    a free externally-authored relevance label and lets analysis split
    author-plausible from author-implausible cells without us having to
    hand-label anything.
    """
    elig = [t for t in tasks if t.deterministic] if deterministic_only else list(tasks)
    by_domain: dict[str, list[FutureTask]] = {}
    for t in elig:
        by_domain.setdefault(t.domain, []).append(t)
    for v in by_domain.values():
        v.sort(key=lambda t: t.id)

    pairs: list[Pair] = []
    for mem in sorted(memories, key=lambda m: m.memory_unit_locator):
        pool = by_domain.get(mem.domain, [])
        if not pool:
            continue
        strata: dict[str, list[FutureTask]] = {}
        for t in pool:
            strata.setdefault(t.question_type, []).append(t)
        rng = random.Random(f"{seed}:{mem.memory_unit_locator}")
        order = sorted(strata)
        rng.shuffle(order)
        chosen: list[FutureTask] = []
        round_no = 0
        while len(chosen) < tasks_per_memory:
            progressed = False
            for st in order:
                if len(chosen) >= tasks_per_memory:
                    break
                bucket = strata[st]
                if round_no < len(bucket):
                    pick = rng.choice(bucket)
                    if pick not in chosen:
                        chosen.append(pick)
                        progressed = True
            if not progressed:
                break
            round_no += 1
        for t in chosen:
            in_hs = (
                mem.trajectory_id in haystack.get(t.id, ())
                if haystack is not None
                else False
            )
            mem_env = coarse_environment(mem.environment)
            task_env = coarse_environment(t.environment)
            # site-level match is only knowable when the task's environment is
            # already coarse (workarena); otherwise the trajectory has no site.
            same_site: bool | None = (
                (mem.environment == t.environment)
                if t.environment == coarse_environment(t.environment)
                else None
            )
            pairs.append(
                Pair(
                    memory_unit_locator=mem.memory_unit_locator,
                    task_id=t.id,
                    domain=mem.domain,
                    stratum=t.question_type,
                    same_environment_coarse=(mem_env == task_env),
                    task_environment=t.environment,
                    memory_environment=mem.environment,
                    same_site=same_site,
                    in_official_haystack=in_hs,
                )
            )
    return pairs

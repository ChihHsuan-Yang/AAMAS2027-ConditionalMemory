"""SciCode adapter: a solved scientific subproblem as procedural memory.

Benchmark 3. Its role is **scientific / procedural** memory -- distinct from
LongMemEval's browser-episodic setting and from SWE-bench's repository-repair
setting. The scientific object is unchanged::

    DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)

Two structural facts, measured before anything was designed
-----------------------------------------------------------
Both were measured on this machine from the JSONL, not inherited:

1. **``ground_truth_code`` exists only in the DEV split.** The union of substep
   keys over the 65 test problems is
   ``{function_header, return_line, step_background, step_description_prompt,
   step_number, test_cases}`` -- no solution. The dev union adds
   ``ground_truth_code``. So a *solved* subproblem, which is what a memory is,
   can only come from dev: **50 donor candidates, not 338**.

2. **A recipient must be a problem's FIRST substep.** A later substep's tests
   call the functions defined by its earlier steps, and the test split ships no
   code for those. Measured: **0 of 65** test problems have step-1 tests that
   reference a later step's function, so step 1 is self-contained; **64 of 65**
   test problems have test cases on step 1 (problem 62's step 1 is one of the
   three whose code the official harness supplies from ``eval/data``).

Dev and test ``problem_id`` sets are **disjoint** (15 / 65, overlap 0), so
donor∈dev and recipient∈test makes the pairing **cross-problem by
construction**. That was the binding requirement in
``docs/BENCHMARK_DECISIONS.md``: the within-problem version merely re-measures
the context the official harness already injects.

The three units
---------------
MEMORY UNIT -- :class:`SolvedSubproblem`: one dev subproblem, its statement,
its scientist-written background, and **its verified gold solution**. Built
from dev rows alone.

FUTURE-TASK UNIT -- :class:`FutureSubproblem`: a test problem's first
subproblem, scored by **its own SciCode test cases against the official
``test_data.h5`` targets**.

PAIRING -- :func:`select_pairs`, deterministic given a seed.

The writer never sees the future task
-------------------------------------
Structural, as in the other two adapters: :func:`build_memory_units` takes dev
rows and nothing else, and the representation writers reached through
:func:`to_source_segment` take a
:class:`~p1mem.memory.segment.SourceSegment` and nothing else (four barriers,
``memory/segment.py``). :func:`assert_writer_blind` re-checks at runtime.

Reward
------
:func:`score_solution` runs the recipient subproblem's **own SciCode test
cases** in a subprocess against the official HDF5 targets. It returns

* ``1.0``  -- every test case asserted true,
* ``0.0``  -- the code ran and an assertion failed (a real wrong answer),
* ``None`` -- the code could not be run or parsed at all.

**``None``, never ``0.0``, for an unrunnable or unparseable solution.** Scoring
an error as zero manufactures harm; this project has hit that defect twice and
``docs/DEFECT_REGISTER.md`` records it. :class:`ScoreResult` keeps the failure
kind so the two are never collapsed.

Provenance
----------
data    : ``SciCode1/SciCode`` on HuggingFace, repo sha
          ``4510f6a6aa27c43fad7b43da2c59602a86e88480``; ``license: apache-2.0``
          declared in the dataset ``cardData``.
          ``problems_dev.jsonl`` (15 problems / 50 substeps),
          ``problems_test.jsonl`` (65 problems / 291 substeps),
          ``test_data.h5`` (1,049,345,865 bytes, 338 top-level keys).
code    : https://github.com/scicode-bench/SciCode @
          ``e3158ea011d4235245a547460d3688d7ccbf9900``, Apache-2.0 (LICENSE read).
paper   : arXiv 2407.13168 (NeurIPS 2024 D&B).
"""

from __future__ import annotations

import collections
import json
import math
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..memory.segment import SourceSegment

# --------------------------------------------------------------------------
# provenance constants -- measured 2026-09-30, not recalled
# --------------------------------------------------------------------------

DATASET_REPO = "SciCode1/SciCode"
DATASET_SHA = "4510f6a6aa27c43fad7b43da2c59602a86e88480"
DATASET_LICENSE = "apache-2.0"
HARNESS_REPO = "https://github.com/scicode-bench/SciCode"
HARNESS_COMMIT = "e3158ea011d4235245a547460d3688d7ccbf9900"
HARNESS_LICENSE = "Apache-2.0"
BENCHMARK = "scicode"
BENCHMARK_VERSION = f"hf@{DATASET_SHA[:12]}"
PROMPT_VERSION = "scicode_deltau_v1"

N_DEV_PROBLEMS = 15
N_TEST_PROBLEMS = 65
N_DEV_SUBSTEPS = 50
N_TEST_SUBSTEPS = 291
H5_BYTES = 1_049_345_865

#: The three subproblems whose code the OFFICIAL harness supplies from
#: ``eval/data/*.txt`` instead of asking the model (see the SciCode FAQ: "to
#: control uncertainty and reduce the degrees of freedom"). A recipient drawn
#: from these would be scored on code we handed it, so they are excluded.
HARNESS_SUPPLIED_STEPS: frozenset[str] = frozenset({"13.6", "62.1", "76.3"})

#: Imports that say nothing about what a problem is *about*. Used only by the
#: DEPENDENCY relatedness level, so the level is not dominated by ``numpy``,
#: which 80 of 80 problems import.
GENERIC_MODULES: frozenset[str] = frozenset({
    "numpy", "math", "time", "os", "copy", "random", "pickle", "functools",
    "itertools", "collections", "cmath",
})

_STOPWORDS: frozenset[str] = frozenset("""
a an the of to in for and or is are be with using use given by on at from that this it as
we you your write python function calculate compute return returns parameters float int
array np numpy shape value values result if then which each other into should must can
will where when there their them these those one two also such def self none true false
""".split())

_WORD = re.compile(r"[a-z]{3,}")
_DEF = re.compile(r"^\s*(?:def|class)\s+(\w+)", re.M)


class WriterSawFutureTask(AssertionError):
    """A memory unit carries content from the task it will be scored against."""


class ScicodeDataError(RuntimeError):
    """The corpus on disk is not the corpus this adapter was written against."""


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a SciCode problems file. RAISES on an empty or missing file.

    Never returns ``[]`` for a path that does not exist: an absent input that
    defaults to a plausible empty value is a defect class this project has
    already been bitten by (``docs/DEFECT_REGISTER.md``).
    """
    p = Path(path)
    if not p.is_file():
        raise ScicodeDataError(f"SciCode problems file not found: {p}")
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    if not rows:
        raise ScicodeDataError(f"SciCode problems file is empty: {p}")
    return rows


# --------------------------------------------------------------------------
# units
# --------------------------------------------------------------------------


def _fn_name(header: str | None) -> str | None:
    m = _DEF.search(header or "")
    return m.group(1) if m else None


def _content_tokens(*parts: str | None) -> frozenset[str]:
    """Lowercased content words. Deterministic, no I/O, no model."""
    joined = " ".join(p or "" for p in parts).lower().replace("_", " ")
    return frozenset(w for w in _WORD.findall(joined) if w not in _STOPWORDS)


def _specific_imports(dependencies: str | None) -> frozenset[str]:
    """Symbol- and module-level imports, with the generic top-levels dropped."""
    out: set[str] = set()
    for line in (dependencies or "").splitlines():
        line = line.strip()
        m = re.match(r"from\s+([\w.]+)\s+import\s+(.+)", line)
        if m:
            base = m.group(1)
            for name in m.group(2).split(","):
                name = name.strip().split(" as ")[0].strip()
                if name and name != "*":
                    out.add(f"{base}.{name}")
            continue
        m = re.match(r"import\s+([\w.]+)", line)
        if m:
            out.add(m.group(1))
    return frozenset(
        x for x in out if "." in x or x.split(".")[0] not in GENERIC_MODULES
    )


@dataclass(frozen=True)
class SolvedSubproblem:
    """A MEMORY UNIT: one dev subproblem that was solved, and how.

    "A reusable helper function plus its procedure" -- the definition fixed in
    ``docs/BENCHMARK_DECISIONS.md``. The gold code is the helper; the step
    description plus the scientist-written background is the procedure.

    Built from a dev row alone. There is no parameter through which a future
    task could reach it.
    """

    step_number: str
    problem_id: str
    problem_name: str
    step_description: str
    step_background: str
    function_header: str
    gold_code: str
    dependencies: str
    return_line: str
    n_test_cases: int

    @property
    def memory_id(self) -> str:
        return f"scicode_dev::{self.step_number}"

    @property
    def memory_unit_locator(self) -> str:
        return self.memory_id

    @property
    def source_episode_id(self) -> str:
        """The PAST episode: the whole dev problem the subproblem came from."""
        return f"scicode_dev::problem_{self.problem_id}"

    @property
    def function_name(self) -> str | None:
        return _fn_name(self.function_header) or _fn_name(self.gold_code)

    @property
    def content_tokens(self) -> frozenset[str]:
        return _content_tokens(
            self.step_description, self.step_background,
            self.function_header, self.problem_name,
        )

    @property
    def imports(self) -> frozenset[str]:
        return _specific_imports(self.dependencies)

    @property
    def episode_text(self) -> str:
        """The verbatim span a memory writer is shown. No future task in it.

        Deterministic: this rule IS the raw representation (protocol §1A --
        take the whole segment, perform no selection).
        """
        parts = [
            f"### Solved subproblem {self.step_number} "
            f"(from SciCode problem {self.problem_id}: {self.problem_name})",
            "",
            "#### What was asked",
            self.step_description.strip(),
        ]
        if self.step_background.strip():
            parts += ["", "#### Scientific background", self.step_background.strip()]
        parts += [
            "", "#### Available imports", "```python",
            self.dependencies.strip(), "```",
            "", "#### The solution that passed its tests", "```python",
            self.gold_code.strip(), "```",
        ]
        return "\n".join(parts)


@dataclass(frozen=True)
class FutureSubproblem:
    """A FUTURE-TASK UNIT: a test problem's first subproblem.

    Scored by its OWN SciCode test cases against the official HDF5 targets.
    Never by an LLM judge -- :attr:`deterministic` is always True.
    """

    step_number: str
    problem_id: str
    problem_name: str
    step_description: str
    step_background: str
    function_header: str
    dependencies: str
    return_line: str
    test_cases: tuple[str, ...]

    @property
    def task_id(self) -> str:
        return f"scicode_test::{self.step_number}"

    @property
    def function_name(self) -> str | None:
        return _fn_name(self.function_header)

    @property
    def content_tokens(self) -> frozenset[str]:
        return _content_tokens(
            self.step_description, self.step_background,
            self.function_header, self.problem_name,
        )

    @property
    def imports(self) -> frozenset[str]:
        return _specific_imports(self.dependencies)

    @property
    def deterministic(self) -> bool:
        return True


def build_memory_units(dev_rows: Iterable[Mapping[str, Any]]) -> list[SolvedSubproblem]:
    """Memories from DEV rows. Takes rows and NOTHING else.

    Writer-blindness is structural here: there is no parameter through which a
    recipient task could be passed, and every substep of every dev problem is
    taken -- there is no selection step that could be conditioned on anything.

    A dev row without ``ground_truth_code`` RAISES. It would silently become an
    unsolved subproblem, which is not a memory, and the count would still look
    healthy.
    """
    out: list[SolvedSubproblem] = []
    for row in dev_rows:
        for step in row["sub_steps"]:
            gold = step.get("ground_truth_code")
            if not gold or not str(gold).strip():
                raise ScicodeDataError(
                    f"dev substep {step.get('step_number')!r} has no "
                    f"ground_truth_code; it is not a SOLVED subproblem and "
                    f"cannot be a memory. Check the split."
                )
            out.append(SolvedSubproblem(
                step_number=str(step["step_number"]),
                problem_id=str(row["problem_id"]),
                problem_name=str(row["problem_name"]),
                step_description=str(step.get("step_description_prompt") or ""),
                step_background=str(step.get("step_background") or ""),
                function_header=str(step.get("function_header") or ""),
                gold_code=str(gold),
                dependencies=str(row.get("required_dependencies") or ""),
                return_line=str(step.get("return_line") or ""),
                n_test_cases=len(step.get("test_cases") or ()),
            ))
    return out


def build_future_tasks(
    test_rows: Iterable[Mapping[str, Any]],
) -> list[FutureSubproblem]:
    """Future tasks: the FIRST substep of each test problem, when it has tests.

    Only the first. A later substep's test cases call functions defined by its
    earlier steps and the test split ships no code for those, so a later
    substep is not independently scorable. Measured: 0 of 65 step-1 substeps
    reference a later step's function, so step 1 genuinely is self-contained.
    """
    out: list[FutureSubproblem] = []
    for row in test_rows:
        steps = row.get("sub_steps") or []
        if not steps:
            continue
        step = steps[0]
        tests = tuple(step.get("test_cases") or ())
        if not tests:
            continue
        if str(step["step_number"]) in HARNESS_SUPPLIED_STEPS:
            continue
        if step.get("ground_truth_code"):
            raise ScicodeDataError(
                f"test substep {step['step_number']!r} carries ground_truth_code; "
                f"this is not the test split the adapter was written against."
            )
        out.append(FutureSubproblem(
            step_number=str(step["step_number"]),
            problem_id=str(row["problem_id"]),
            problem_name=str(row["problem_name"]),
            step_description=str(step.get("step_description_prompt") or ""),
            step_background=str(step.get("step_background") or ""),
            function_header=str(step.get("function_header") or ""),
            dependencies=str(row.get("required_dependencies") or ""),
            return_line=str(step.get("return_line") or ""),
            test_cases=tests,
        ))
    return out


def assert_writer_blind(memories: Sequence[SolvedSubproblem],
                        tasks: Sequence[FutureSubproblem]) -> None:
    """Runtime re-check that no memory came from a recipient's own problem.

    Structural blindness is the real guarantee (``build_memory_units`` has no
    task parameter); this catches a refactor that breaks it. Two things are
    checked, and the second is the one that matters:

    * no memory's ``step_number`` collides with a task's;
    * **no memory shares a ``problem_id`` with any future task** -- SciCode
      numbers dev and test problems in one namespace, so a within-problem
      donor would re-measure the harness's own injected context rather than
      cross-problem transfer.
    """
    task_steps = {t.step_number for t in tasks}
    task_problems = {t.problem_id for t in tasks}
    for m in memories:
        if m.step_number in task_steps:
            raise WriterSawFutureTask(
                f"memory {m.step_number} is also a future task"
            )
        if m.problem_id in task_problems:
            raise WriterSawFutureTask(
                f"memory {m.memory_id} comes from problem {m.problem_id}, which "
                f"also supplies a future task. The pairing must be CROSS-problem."
            )


def to_source_segment(memory: SolvedSubproblem) -> SourceSegment:
    """The only object a representation writer ever sees.

    Takes a memory and nothing else, and populates
    :class:`~p1mem.memory.segment.SourceSegment`, whose four barriers
    (arity, frozen slots, metadata denylist, single ``{segment_text}``
    interpolation point) are what actually enforce writer-blindness. The
    metadata carries only facts about the PAST subproblem.
    """
    return SourceSegment(
        segment_id=memory.memory_unit_locator,
        benchmark=BENCHMARK,
        benchmark_version=BENCHMARK_VERSION,
        source_episode_id=memory.source_episode_id,
        text=memory.episode_text,
        source_span={
            "split": "dev",
            "problem_id": memory.problem_id,
            "step_number": memory.step_number,
            "fields": ["step_description_prompt", "step_background",
                       "required_dependencies", "ground_truth_code"],
        },
        episode_metadata={
            "problem_name": memory.problem_name,
            "function_name": memory.function_name or "",
            "n_dev_test_cases": memory.n_test_cases,
        },
    )


# --------------------------------------------------------------------------
# relatedness and pairing
# --------------------------------------------------------------------------


class Relatedness(str, Enum):
    """How close a donor must be to a recipient to be a candidate pair.

    Named rather than left implicit in a lambda, because the choice changes the
    headline N. Measured counts live in ``docs/SCICODE_FEASIBILITY.md``; they
    are recomputed by :func:`multi_task_report`, never quoted from here.

    ``ALL``          every cross-problem pair. The upper bound, and the honest
                     denominator for "how diagonal is this benchmark".
    ``DEPENDENCY``   donor and recipient share a non-generic import
                     (``scipy.integrate``, ``numpy.fft.fft2``, ...).
    ``LEXICAL``      donor/recipient idf-weighted cosine over content words is
                     at or above :data:`LEXICAL_THRESHOLD`.
    """

    ALL = "all"
    DEPENDENCY = "dependency"
    LEXICAL = "lexical"


#: Fixed BEFORE any reward was computed, at the 95th percentile of the full
#: 3,200-combination similarity distribution (measured p95 = 0.0315). Choosing
#: it from the distribution rather than from the outcomes keeps the selection
#: off the dependent variable.
LEXICAL_THRESHOLD = 0.0315


def _idf(docs: Sequence[frozenset[str]]) -> dict[str, float]:
    df: collections.Counter[str] = collections.Counter()
    for d in docs:
        df.update(d)
    n = len(docs) or 1
    return {w: math.log(n / c) for w, c in df.items()}


def lexical_similarity(a: frozenset[str], b: frozenset[str],
                       idf: Mapping[str, float]) -> float:
    """idf-weighted cosine over content-word sets. Pure and deterministic."""
    inter = a & b
    if not inter:
        return 0.0
    num = sum(idf.get(w, 0.0) for w in inter)
    da = math.sqrt(sum(idf.get(w, 0.0) ** 2 for w in a))
    db = math.sqrt(sum(idf.get(w, 0.0) ** 2 for w in b))
    return num / (da * db) if da and db else 0.0


@dataclass(frozen=True)
class Pair:
    """One (memory, future task) cell."""

    memory_id: str
    memory_unit_locator: str
    task_id: str
    relatedness: str
    similarity: float
    shared_imports: tuple[str, ...]
    shared_terms: tuple[str, ...]
    donor_problem_id: str
    recipient_problem_id: str

    def as_row(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_unit_locator": self.memory_unit_locator,
            "task_id": self.task_id,
            "relatedness": self.relatedness,
            "similarity": round(self.similarity, 6),
            "shared_imports": list(self.shared_imports),
            "shared_terms": list(self.shared_terms),
            "donor_problem_id": self.donor_problem_id,
            "recipient_problem_id": self.recipient_problem_id,
        }


def candidate_pairs(
    memories: Sequence[SolvedSubproblem],
    tasks: Sequence[FutureSubproblem],
    *,
    relatedness: Relatedness = Relatedness.DEPENDENCY,
) -> list[Pair]:
    """Every cross-problem donor→recipient pair at the given relatedness.

    Cross-problem is enforced here as well as in :func:`assert_writer_blind`:
    a donor and a recipient from the same ``problem_id`` are skipped, so a
    within-problem pair cannot be produced even if the splits ever overlap.
    """
    idf = _idf([m.content_tokens for m in memories]
               + [t.content_tokens for t in tasks])
    out: list[Pair] = []
    for d in sorted(memories, key=lambda m: m.memory_unit_locator):
        for t in sorted(tasks, key=lambda x: x.task_id):
            if d.problem_id == t.problem_id:
                continue
            shared_imports = tuple(sorted(d.imports & t.imports))
            sim = lexical_similarity(d.content_tokens, t.content_tokens, idf)
            if relatedness is Relatedness.DEPENDENCY and not shared_imports:
                continue
            if relatedness is Relatedness.LEXICAL and sim < LEXICAL_THRESHOLD:
                continue
            shared = sorted(d.content_tokens & t.content_tokens,
                            key=lambda w: (-idf.get(w, 0.0), w))[:8]
            out.append(Pair(
                memory_id=d.memory_id,
                memory_unit_locator=d.memory_unit_locator,
                task_id=t.task_id,
                relatedness=relatedness.value,
                similarity=sim,
                shared_imports=shared_imports,
                shared_terms=tuple(shared),
                donor_problem_id=d.problem_id,
                recipient_problem_id=t.problem_id,
            ))
    return out


def select_pairs(
    memories: Sequence[SolvedSubproblem],
    tasks: Sequence[FutureSubproblem],
    *,
    seed: int,
    tasks_per_memory: int = 4,
    relatedness: Relatedness = Relatedness.DEPENDENCY,
    min_tasks_per_memory: int = 2,
) -> list[Pair]:
    """Deterministically select cells, keeping only multi-task memories.

    Reproducible from ``seed`` alone: an independent ``random.Random`` is
    drawn per memory and keyed by ``memory_unit_locator``, so adding or
    removing one memory does not perturb any other memory's draw -- the same
    rule the LongMemEval and SWE-bench adapters use, for the same reason.

    ``min_tasks_per_memory`` defaults to 2 because a memory meeting exactly one
    future task cannot speak to the axis this project exists to measure (the
    axis that demoted BEAM at 92.6% diagonality). It restricts the cell set on
    a property of the PAIRING, never on an outcome.
    """
    cands = candidate_pairs(memories, tasks, relatedness=relatedness)
    by_mem: dict[str, list[Pair]] = {}
    for p in cands:
        by_mem.setdefault(p.memory_unit_locator, []).append(p)

    out: list[Pair] = []
    for locator in sorted(by_mem):
        pool = sorted(by_mem[locator], key=lambda p: p.task_id)
        if len(pool) < min_tasks_per_memory:
            continue
        rng = random.Random(f"{seed}:{locator}")
        picked = pool if len(pool) <= tasks_per_memory else rng.sample(
            pool, tasks_per_memory)
        out.extend(sorted(picked, key=lambda p: p.task_id))
    return out


def multi_task_report(pairs: Sequence[Pair]) -> dict[str, Any]:
    """The BEAM-comparable diagonality statistic, computed from actual pairs.

    Every field prints its own denominator: ``n_memories`` is the denominator
    of ``pct_diagonal``, and it is returned beside it. A verdict assembled from
    an unstated denominator is a defect this project has recorded.
    """
    counts: collections.Counter[str] = collections.Counter(
        p.memory_unit_locator for p in pairs)
    task_counts: collections.Counter[str] = collections.Counter(
        p.task_id for p in pairs)
    n = len(counts)
    solo = sum(1 for v in counts.values() if v == 1)
    vals = sorted(counts.values(), reverse=True)
    return {
        "n_pairs": len(pairs),
        "n_memories": n,
        "n_tasks": len(task_counts),
        "memories_with_1_task": solo,
        "memories_with_ge2_tasks": sum(1 for v in counts.values() if v >= 2),
        "memories_with_ge3_tasks": sum(1 for v in counts.values() if v >= 3),
        "pct_diagonal": (solo / n * 100.0) if n else None,
        "pct_diagonal_denominator": n,
        "max_tasks_per_memory": vals[0] if vals else 0,
        "median_tasks_per_memory": (
            vals[len(vals) // 2] if vals else None),
        "max_memories_per_task": (
            max(task_counts.values()) if task_counts else 0),
        "beam_reference_pct_diagonal": 92.6,
    }


# --------------------------------------------------------------------------
# reward -- SciCode's own test cases, run for real
# --------------------------------------------------------------------------

#: Kinds of outcome. ``wrong_answer`` is the ONLY one that scores 0.0.
SCORE_OK = "pass"
SCORE_WRONG = "wrong_answer"
ERR_NO_CODE = "no_code_block"
ERR_NO_FUNCTION = "function_not_defined"
ERR_SYNTAX = "syntax_error"
ERR_RUNTIME = "runtime_error"
ERR_TIMEOUT = "timeout"
ERR_HARNESS = "harness_error"

#: Failure kinds that mean "we could not obtain a verdict", so ``reward`` is
#: ``None``. Everything here is an ERROR, never a reward of 0.0.
ERROR_KINDS: frozenset[str] = frozenset({
    ERR_NO_CODE, ERR_NO_FUNCTION, ERR_SYNTAX, ERR_RUNTIME, ERR_TIMEOUT,
    ERR_HARNESS,
})

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
#: An UNTERMINATED opening fence. A response cut off by ``max_tokens`` has one,
#: and without this the fallback branch below returns the fence marker itself
#: as if it were code -- observed in the smoke run: a truncated WITH-arm reply
#: was scored ``syntax_error`` on the literal line ```` ```python ````. That
#: still produced reward=None, so no number was corrupted, but the recorded
#: KIND was wrong, and the kind is what a floor diagnosis reads.
_OPEN_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*)\Z", re.S)


@dataclass(frozen=True)
class ScoreResult:
    """The outcome of scoring one candidate solution.

    ``reward`` is ``None`` for every kind in :data:`ERROR_KINDS`. It is 0.0
    ONLY when the code ran to an assertion failure -- a real wrong answer.
    Collapsing the two manufactures harm: a WITH arm that errors more often
    would show memory hurting when nothing was measured at all.
    """

    reward: float | None
    kind: str
    n_tests: int
    stderr_tail: str = ""
    duration_s: float | None = None

    @property
    def is_error(self) -> bool:
        return self.kind in ERROR_KINDS

    def __post_init__(self) -> None:
        if self.is_error and self.reward is not None:
            raise ValueError(
                f"kind={self.kind!r} is an error and must carry reward=None, "
                f"not {self.reward!r}. Scoring an error as 0.0 manufactures harm."
            )
        if not self.is_error and self.reward is None:
            raise ValueError(f"kind={self.kind!r} must carry a numeric reward")


def extract_code(response: str | None) -> str | None:
    """Pull the python code out of a model response. Deterministic, no I/O.

    Returns ``None`` when there is nothing that could be code -- which the
    caller must turn into ``ERR_NO_CODE`` and a ``None`` reward, never a 0.0.
    """
    if not response or not response.strip():
        return None
    blocks = _FENCE.findall(response)
    if blocks:
        return max(blocks, key=len).strip() or None
    m = _OPEN_FENCE.search(response)
    if m:
        # Unterminated fence: take what is inside it. Usually a truncated
        # function, which will fail to compile -- correctly, as an ERROR.
        return m.group(1).strip() or None
    text = response.strip()
    # No fence at all: accept it only if it actually looks like a definition,
    # so a prose refusal is an error rather than code that fails to compile.
    return text if _DEF.search(text) else None


def build_test_program(task: FutureSubproblem, code: str, h5_path: str | Path) -> str:
    """The exact program that will be run. Pure: builds a string, runs nothing.

    Mirrors the official harness's structure (``eval/scripts/test_generated_code.py``):
    dependencies, then the candidate code, then targets loaded from the
    official HDF5 by ``scicode.parse.parse.process_hdf5_to_tuple``, then the
    benchmark's own assertions verbatim.
    """
    parts = [
        task.dependencies.strip(), "",
        code.strip(), "",
        "from scicode.parse.parse import process_hdf5_to_tuple",
        f"targets = process_hdf5_to_tuple("
        f"{task.step_number!r}, {len(task.test_cases)}, {str(h5_path)!r})",
        "",
    ]
    for i, tc in enumerate(task.test_cases):
        parts += [f"target = targets[{i}]", tc.strip(), ""]
    return "\n".join(parts)


def classify_failure(stderr: str) -> str:
    """Map a subprocess stderr to a failure kind.

    ``AssertionError`` from the benchmark's own assertion is the ONLY thing
    that means "wrong answer". Everything else is an error.
    """
    tail = (stderr or "").strip()
    if not tail:
        return ERR_RUNTIME
    if "SyntaxError" in tail or "IndentationError" in tail:
        return ERR_SYNTAX
    last = tail.splitlines()[-1]
    if last.startswith("AssertionError") or last.strip() == "AssertionError":
        return SCORE_WRONG
    if "NameError" in last and "is not defined" in last:
        return ERR_NO_FUNCTION
    if "process_hdf5_to_tuple" in tail or "KeyError" in last:
        return ERR_HARNESS
    return ERR_RUNTIME


#: ``scicode.parse.parse`` does ``from datasets import load_dataset`` at MODULE
#: scope, but uses it only inside ``read_from_hf_dataset``, which local scoring
#: never calls. Without a stub every score returns ``harness_error`` and the
#: whole benchmark reads as unrunnable -- which is exactly what the gold
#: positive control caught here (0/15, against 15/15 by hand). The shim is
#: created by the adapter rather than assumed in the environment, so the
#: dependency is explicit and re-derivable instead of ambient.
_DATASETS_STUB = (
    "def load_dataset(*a, **k):\n"
    "    raise RuntimeError(\n"
    "        'p1mem scicode shim: load_dataset is not available offline. Local\\n'\n"
    "        'scoring reads targets from the HDF5 file and never needs it.')\n"
)


def ensure_parse_shim(root: str | Path) -> Path:
    """Create the minimal ``datasets`` stub and return the directory to add to
    ``PYTHONPATH``. Idempotent, and it RAISES if the file it needs is not
    there afterwards rather than letting the caller proceed."""
    shim = Path(root) / "_scicode_shim"
    pkg = shim / "datasets"
    pkg.mkdir(parents=True, exist_ok=True)
    init = pkg / "__init__.py"
    if not init.exists() or init.read_text() != _DATASETS_STUB:
        init.write_text(_DATASETS_STUB)
    if not init.is_file():
        raise ScicodeDataError(f"could not create the datasets shim at {init}")
    return shim


def score_solution(
    task: FutureSubproblem,
    response: str | None,
    *,
    h5_path: str | Path,
    scicode_src: str | Path,
    workdir: str | Path,
    python: str = sys.executable,
    timeout_s: float = 300.0,
) -> ScoreResult:
    """Run the recipient's own SciCode tests. The reward function, in full.

    Returns ``1.0`` when every one of the benchmark's assertions holds,
    ``0.0`` when the code ran and an assertion failed, and ``None`` for every
    other outcome -- no code, undefined function, syntax error, runtime error,
    timeout, harness error.
    """
    import time as _time

    n = len(task.test_cases)
    code = extract_code(response)
    if code is None:
        return ScoreResult(reward=None, kind=ERR_NO_CODE, n_tests=n)
    if task.function_name and not re.search(
            rf"^\s*(?:def|class)\s+{re.escape(task.function_name)}\b", code, re.M):
        return ScoreResult(reward=None, kind=ERR_NO_FUNCTION, n_tests=n,
                           stderr_tail=f"{task.function_name} not defined in the response")

    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    prog = work / f"score_{task.step_number.replace('.', '_')}.py"
    prog.write_text(build_test_program(task, code, h5_path))

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(scicode_src), str(ensure_parse_shim(work))]
        + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    # stderr is CAPTURED, never discarded: suppressing it turns "the module was
    # absent" into a measured zero (docs/DEFECT_REGISTER.md).
    t0 = _time.monotonic()
    try:
        proc = subprocess.run([str(python), str(prog)], capture_output=True,
                              text=True, timeout=timeout_s, env=env, cwd=str(work))
    except subprocess.TimeoutExpired:
        return ScoreResult(reward=None, kind=ERR_TIMEOUT, n_tests=n,
                           duration_s=timeout_s)
    dt = _time.monotonic() - t0
    if proc.returncode == 0:
        return ScoreResult(reward=1.0, kind=SCORE_OK, n_tests=n, duration_s=dt)
    kind = classify_failure(proc.stderr)
    tail = (proc.stderr or "").strip()[-400:]
    if kind == SCORE_WRONG:
        return ScoreResult(reward=0.0, kind=SCORE_WRONG, n_tests=n,
                           stderr_tail=tail, duration_s=dt)
    return ScoreResult(reward=None, kind=kind, n_tests=n,
                       stderr_tail=tail, duration_s=dt)


def score_gold(memory: SolvedSubproblem, **kw: Any) -> ScoreResult:
    """Positive control: score a DEV subproblem's own gold code against its
    own tests. Must return 1.0. A scorer only ever observed passing on one
    case is not known to discriminate, so ``scripts/scicode_controls.py``
    also runs deliberately corrupted variants and requires them to FAIL.
    """
    task = FutureSubproblem(
        step_number=memory.step_number, problem_id=memory.problem_id,
        problem_name=memory.problem_name,
        step_description=memory.step_description,
        step_background=memory.step_background,
        function_header=memory.function_header,
        dependencies=memory.dependencies, return_line=memory.return_line,
        test_cases=kw.pop("test_cases"),
    )
    return score_solution(task, f"```python\n{memory.gold_code}\n```", **kw)


# --------------------------------------------------------------------------
# reader prompt -- identical in both arms except for the memory block
# --------------------------------------------------------------------------

SOLVER_INSTRUCTIONS = (
    "Write the complete Python function. Reply with ONE fenced python code "
    "block and nothing else: no explanation before or after it. The block must "
    "contain the full function definition, including the exact signature shown. "
    "Assume the listed imports are already available at module scope."
)


def render_task_prompt(task: FutureSubproblem, memory_block: str | None,
                       *, filler: str = "") -> str:
    """The reader's prompt. The ONLY difference between arms is ``memory_block``.

    ``filler`` implements ``MEMORY_PROTOCOL.md`` §4's controlled-filler
    requirement: the target memory must sit inside a fixed set of other
    content in BOTH arms, so removing it is a local change rather than the
    removal of the whole context. In the WITHOUT arm the filler is present and
    the target memory is not.
    """
    parts = ["You are solving one subproblem of a scientific computing task."]
    if filler or memory_block:
        parts += ["", "## Notes from earlier work", ""]
    if filler:
        parts.append(filler.strip())
    if memory_block:
        if filler:
            parts.append("")
        parts.append(memory_block.strip())
    parts += [
        "", "## The subproblem to solve", "",
        task.step_description.strip(),
    ]
    if task.step_background.strip():
        parts += ["", "### Background", task.step_background.strip()]
    parts += [
        "", "### Imports already available", "```python",
        task.dependencies.strip(), "```",
        "", "### Required signature", "```python",
        task.function_header.strip(),
        f"    # ...\n{task.return_line.strip()}" if task.return_line.strip() else "    # ...",
        "```",
        "", SOLVER_INSTRUCTIONS,
    ]
    return "\n".join(parts)


def render_raw_memory(memory: SolvedSubproblem) -> str:
    """RAW / extractive representation. Deterministic, ZERO model calls.

    Identical bytes to :attr:`SolvedSubproblem.episode_text` -- the raw memory
    IS the segment, with no selection step (protocol §1A).
    """
    return memory.episode_text


# --------------------------------------------------------------------------
# leakage -- a donor's helper may literally BE the recipient's answer
# --------------------------------------------------------------------------
#
# The generic detectors in ``adapters/leakage.py`` are built for a natural
# language gold answer. SciCode's "gold answer" is a FUNCTION, so the
# benchmark-specific hazard is different in kind: a donor's helper can define
# exactly the function the recipient is asked to write, in which case the
# reader can copy the memory and score 1.0 without doing the task. That is a
# real, naturally occurring leak and it must be FLAGGED, never dropped
# (``MEMORY_PROTOCOL.md`` §0.3) -- a memory that happens to contain the answer
# IS a memory being genuinely useful; what must be excluded is task-directed
# writing, which the writer-blindness barriers already exclude structurally.


def signature_line(function_header: str | None) -> str:
    """The ``def``/``class`` line of a header, without its docstring.

    This is the gold-shaped string for a SciCode recipient: the smallest
    literal text that identifies the answer. Passing the whole header instead
    makes any leakage check fire on incidental docstring overlap -- which is
    exactly what a first draft of ``scripts/scicode_controls.py`` did, and the
    clean control caught it.
    """
    for line in (function_header or "").splitlines():
        st = line.strip()
        if st.startswith(("def ", "class ")):
            return st
    return ""


def defines_recipient_function(memory: SolvedSubproblem,
                               task: FutureSubproblem) -> bool:
    """Does the donor's gold code DEFINE the function the recipient must write?

    The strongest form of leakage available here: if it is true, the reader
    can copy the memory verbatim. Pure and deterministic.
    """
    name = task.function_name
    if not name:
        return False
    return bool(re.search(rf"^\s*(?:def|class)\s+{re.escape(name)}\b",
                          memory.gold_code, re.M))


def calls_recipient_function(memory: SolvedSubproblem,
                             task: FutureSubproblem) -> bool:
    """Weaker signal: the donor mentions the recipient's function name at all.

    Reported separately. A mention is not an answer, and collapsing it into
    the same rate as a definition would overstate the leak.
    """
    name = task.function_name
    if not name:
        return False
    return bool(re.search(rf"\b{re.escape(name)}\b", memory.episode_text))


@dataclass(frozen=True)
class ScicodeLeakVerdict:
    """Per-cell verdict. Nothing here decides to drop anything."""

    memory_id: str
    task_id: str
    defines_answer: bool
    mentions_answer_name: bool
    signature_verbatim: bool
    generic_exact: bool
    generic_normalized: bool
    generic_numeric: bool | None

    @property
    def any_leak(self) -> bool:
        """Full-answer leakage. A NAME MENTION IS DELIBERATELY EXCLUDED here.

        `mentions_answer_name` is reported beside this, never folded into it:
        `tensor` appearing in a donor's prose is not the recipient's answer.
        """
        return bool(self.defines_answer or self.signature_verbatim
                    or self.generic_exact)


def detect_leak(memory: SolvedSubproblem, task: FutureSubproblem):
    """Run every applicable detector on one cell. Flags; never drops."""
    from . import leakage as _L

    gold = signature_line(task.function_header)
    v = _L.detect(memory.episode_text, gold,
                  memory_id=memory.memory_id, task_id=task.task_id)
    return ScicodeLeakVerdict(
        memory_id=memory.memory_id,
        task_id=task.task_id,
        defines_answer=defines_recipient_function(memory, task),
        mentions_answer_name=calls_recipient_function(memory, task),
        signature_verbatim=bool(gold and gold in memory.episode_text),
        generic_exact=v.exact,
        generic_normalized=v.normalized,
        generic_numeric=v.numeric,
    )

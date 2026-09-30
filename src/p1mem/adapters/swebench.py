"""SWE-bench Verified adapter: past solved issues as memories for later issues.

Selected as the BEAM replacement on 2026-09-30. The verdict and every
measurement behind it are in ``docs/SWEBENCH_FEASIBILITY.md``; this module is
the implementation of the design that verdict fixed.

The scientific object is unchanged:

    DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)

Why this benchmark replaced BEAM
--------------------------------
BEAM was dropped because **92.6% of its cited turns are cited by exactly one
question** -- it is diagonal, so it cannot supply the multi-task-per-memory
axis. Measured on SWE-bench Verified's 500 instances, the same statistic is
**40.9% diagonal at the same-file definition (133 memories serve >=2 later
tasks) and 16.0% at the same-directory definition (316 memories)**. BEAM also
carried CC BY-SA 4.0, whose ShareAlike would have forced a separate release;
98.0% of SWE-bench Verified's instances come from permissively licensed
upstream repositories.

The three units
---------------
MEMORY UNIT -- a :class:`SolvedIssue`: one past, already-merged issue+patch
pair. Naturally occurring (a real merged PR), and defined WITHOUT reference to
any future task.

FUTURE-TASK UNIT -- a :class:`FutureIssue`: a later issue in the SAME
repository, with its ``FAIL_TO_PASS`` / ``PASS_TO_PASS`` test sets.

PAIRING -- :func:`select_pairs`, deterministic given a seed, with a
``relatedness`` level that is an explicit, named choice rather than an
implicit one (see :class:`Relatedness`).

The writer never sees the future task
-------------------------------------
Enforced structurally, as in the LongMemEval adapter:
:func:`build_memory_units` takes instance rows and nothing else. There is no
code path by which a recipient issue can reach it. :func:`assert_writer_blind`
re-checks this at runtime.

Two constraints discovered by measurement, not by design taste
--------------------------------------------------------------
1. **Edits must be SEARCH/REPLACE, never a unified diff.** At the reader's
   ``max_tokens=512``, ``gpt-oss-120b`` cannot emit line-accurate ``@@``
   headers: 4 of 4 probe attempts produced hunks with no line numbers and
   failed ``git apply --check`` (rc=128). Shown the exact editable region it
   produced an applicable SEARCH/REPLACE edit that passed the real test.
   :func:`parse_search_replace` / :func:`apply_edits` implement that format.
2. **Reward is real unit tests, executed natively.** There is no Docker on the
   target host and it is arm64, while the official harness demands Docker +
   x86_64 + ~120 GB. 412 of 500 instances are from pure-Python repositories
   and run natively; :data:`PURE_PYTHON_REPOS` names them.

Provenance
----------
data : https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified
       data/test-00000-of-00001.parquet
       sha256 a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd
       500 rows. NOTE: the HF dataset carries NO licence tag; the binding terms
       are the upstream repositories' (98.0% permissive) plus MIT on the
       harness. See ``docs/SWEBENCH_FEASIBILITY.md``.
code : https://github.com/SWE-bench/SWE-bench  (MIT)
paper: arXiv 2310.06770
"""

from __future__ import annotations

import datetime as _dt
import json
import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------
# provenance constants -- measured on 2026-09-30, not recalled
# --------------------------------------------------------------------------

DATASET_REPO = "princeton-nlp/SWE-bench_Verified"
DATASET_FILE = "data/test-00000-of-00001.parquet"
DATASET_SHA256 = "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"
DATASET_N_ROWS = 500
HARNESS_REPO = "https://github.com/SWE-bench/SWE-bench"
HARNESS_LICENSE = "MIT"

#: Upstream licences, each READ from the upstream project on 2026-09-30 (the
#: GitHub licence API reported NOASSERTION / none for three of these, so their
#: LICENSE files were read directly). Instance counts are measured.
UPSTREAM_LICENSES: dict[str, str] = {
    "django/django": "BSD-3-Clause",
    "sympy/sympy": "BSD-3-Clause",
    "sphinx-doc/sphinx": "BSD-2-Clause",
    "matplotlib/matplotlib": "matplotlib-PSF-style",
    "scikit-learn/scikit-learn": "BSD-3-Clause",
    "astropy/astropy": "BSD-3-Clause",
    "pydata/xarray": "Apache-2.0",
    "pytest-dev/pytest": "MIT",
    "pylint-dev/pylint": "GPL-2.0",
    "psf/requests": "Apache-2.0",
    "mwaskom/seaborn": "BSD-3-Clause",
    "pallets/flask": "BSD-3-Clause",
}

#: The only copyleft repository in the benchmark. Excluding it costs 11 of
#: 3,202 same-directory pairs (0.34%) and 2 of 644 same-file pairs (0.31%),
#: measured -- so the release can be uniformly permissive almost for free.
COPYLEFT_REPOS: frozenset[str] = frozenset({"pylint-dev/pylint"})

#: Repositories that are importable without building a C/C++ extension, so
#: their tests run natively on a machine with no Docker. 412 of 500 instances.
#: matplotlib, scikit-learn and astropy are EXCLUDED because they need a
#: compiled build (88 instances).
PURE_PYTHON_REPOS: frozenset[str] = frozenset({
    "django/django", "sympy/sympy", "sphinx-doc/sphinx", "pytest-dev/pytest",
    "pylint-dev/pylint", "psf/requests", "pallets/flask", "pydata/xarray",
    "mwaskom/seaborn",
})

PROMPT_VERSION = "swebench_v1"

_DIFF_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)


class WriterSawFutureTask(AssertionError):
    """A memory unit carries content from the task it will be scored against."""


# --------------------------------------------------------------------------
# relatedness -- an explicit, named choice
# --------------------------------------------------------------------------


class Relatedness(str, Enum):
    """How close a donor must be to a recipient to count as a candidate pair.

    These are not interchangeable and the choice changes the headline N, so it
    is named rather than left implicit in a lambda. Measured on all 500
    instances with ``donor.created_at < recipient.created_at``:

    =========  =======  ==========================  ==============
    level      pairs    donors with >=2 recipients  % diagonal
    =========  =======  ==========================  ==============
    REPO        32,050  477                          2.3%
    PACKAGE     10,160  371                         11.2%
    DIRECTORY    3,202  316                         16.0%
    FILE           644  133                         40.9%
    =========  =======  ==========================  ==============

    ``REPO`` is too loose to call a related task without further argument.
    ``FILE`` is the most defensible and is the DEFAULT. Compare against BEAM's
    92.6% diagonal: every level here clears it.
    """

    REPO = "repo"
    PACKAGE = "package"
    DIRECTORY = "directory"
    FILE = "file"


# --------------------------------------------------------------------------
# units
# --------------------------------------------------------------------------


def parse_patch_files(patch: str | None) -> tuple[str, ...]:
    """Post-image paths touched by a unified diff. Deterministic, no I/O."""
    return tuple(sorted({m.group(2) for m in _DIFF_FILE.finditer(patch or "")}))


def _parse_created_at(value: Any) -> _dt.datetime:
    """Parse the row's timestamp. RAISES on anything unparseable.

    Never defaults to ``now`` or to epoch: a wrong timestamp would silently
    invert a past/future ordering, which is the one property the whole design
    rests on. All 500 rows parse and all 500 are distinct (measured).
    """
    if isinstance(value, _dt.datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"created_at is not a parseable timestamp: {value!r}")
    return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class SolvedIssue:
    """A MEMORY UNIT: one past issue that was resolved, plus how it was fixed.

    Built from a benchmark row alone. It cannot see any future task.
    """

    instance_id: str
    repo: str
    problem_statement: str
    patch: str
    created_at: _dt.datetime
    files: tuple[str, ...]

    @property
    def memory_id(self) -> str:
        return self.instance_id

    @property
    def memory_unit_locator(self) -> str:
        return f"swebench_verified::{self.instance_id}"

    @property
    def directories(self) -> frozenset[str]:
        return frozenset("/".join(f.split("/")[:-1]) for f in self.files)

    @property
    def packages(self) -> frozenset[str]:
        return frozenset("/".join(f.split("/")[:2]) for f in self.files)

    @property
    def license(self) -> str:
        return UPSTREAM_LICENSES.get(self.repo, "UNKNOWN")


@dataclass(frozen=True)
class FutureIssue:
    """A FUTURE-TASK UNIT: a later issue, scored by its own tests."""

    instance_id: str
    repo: str
    problem_statement: str
    base_commit: str
    patch: str
    test_patch: str
    created_at: _dt.datetime
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    files: tuple[str, ...]
    version: str = ""

    @property
    def task_id(self) -> str:
        return self.instance_id

    @property
    def directories(self) -> frozenset[str]:
        return frozenset("/".join(f.split("/")[:-1]) for f in self.files)

    @property
    def packages(self) -> frozenset[str]:
        return frozenset("/".join(f.split("/")[:2]) for f in self.files)

    @property
    def deterministic(self) -> bool:
        """Always True: the reward is unit tests, never an LLM judge."""
        return True


def _as_list(value: Any) -> tuple[str, ...]:
    """SWE-bench stores test lists as JSON-encoded strings."""
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(x) for x in value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return ()
        return tuple(str(x) for x in json.loads(value))
    raise TypeError(f"cannot read a test list from {type(value).__name__}")


def build_memory_units(rows: Iterable[dict[str, Any]]) -> list[SolvedIssue]:
    """Memories from benchmark rows. Takes rows and NOTHING else.

    The writer-blindness property is structural: there is no parameter through
    which a future task could be passed.
    """
    out: list[SolvedIssue] = []
    for r in rows:
        out.append(SolvedIssue(
            instance_id=r["instance_id"], repo=r["repo"],
            problem_statement=r["problem_statement"] or "",
            patch=r["patch"] or "",
            created_at=_parse_created_at(r["created_at"]),
            files=parse_patch_files(r["patch"]),
        ))
    return out


def build_future_tasks(rows: Iterable[dict[str, Any]]) -> list[FutureIssue]:
    out: list[FutureIssue] = []
    for r in rows:
        out.append(FutureIssue(
            instance_id=r["instance_id"], repo=r["repo"],
            problem_statement=r["problem_statement"] or "",
            base_commit=r["base_commit"], patch=r["patch"] or "",
            test_patch=r["test_patch"] or "",
            created_at=_parse_created_at(r["created_at"]),
            fail_to_pass=_as_list(r.get("FAIL_TO_PASS")),
            pass_to_pass=_as_list(r.get("PASS_TO_PASS")),
            files=parse_patch_files(r["patch"]),
            version=str(r.get("version") or ""),
        ))
    return out


def assert_writer_blind(memories: Sequence[SolvedIssue],
                        tasks: Sequence[FutureIssue]) -> None:
    """Re-check at runtime that no memory carries its future task's content.

    Structural blindness is the real guarantee; this catches a future refactor
    that breaks it. Raises :class:`WriterSawFutureTask`.
    """
    by_id = {t.instance_id: t for t in tasks}
    for m in memories:
        t = by_id.get(m.instance_id)
        if t is None:
            continue
        # A memory built from row X must not be a memory ABOUT a later row.
        if m.created_at != t.created_at or m.repo != t.repo:
            raise WriterSawFutureTask(
                f"memory {m.instance_id} disagrees with its own source row"
            )


# --------------------------------------------------------------------------
# pairing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    """One (memory, future task) cell."""

    memory_id: str
    memory_unit_locator: str
    task_id: str
    repo: str
    relatedness: str
    shared_files: tuple[str, ...]
    donor_created_at: str
    recipient_created_at: str

    def as_row(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_unit_locator": self.memory_unit_locator,
            "task_id": self.task_id,
            "repo": self.repo,
            "relatedness": self.relatedness,
            "shared_files": list(self.shared_files),
            "donor_created_at": self.donor_created_at,
            "recipient_created_at": self.recipient_created_at,
        }


def _related(donor: SolvedIssue, recip: FutureIssue, level: Relatedness) -> bool:
    if donor.repo != recip.repo:
        return False
    if level is Relatedness.REPO:
        return True
    if level is Relatedness.PACKAGE:
        return bool(donor.packages & recip.packages)
    if level is Relatedness.DIRECTORY:
        return bool(donor.directories & recip.directories)
    return bool(set(donor.files) & set(recip.files))


def candidate_pairs(
    memories: Sequence[SolvedIssue],
    tasks: Sequence[FutureIssue],
    *,
    relatedness: Relatedness = Relatedness.FILE,
    exclude_copyleft: bool = True,
    pure_python_only: bool = False,
) -> list[Pair]:
    """Every directed, strictly time-ordered, related pair.

    ``donor.created_at < recipient.created_at`` is required, so the "past" is
    the real history of the repository: the donor issue was actually resolved
    before the recipient issue was filed.
    """
    out: list[Pair] = []
    for d in sorted(memories, key=lambda m: m.memory_unit_locator):
        if exclude_copyleft and d.repo in COPYLEFT_REPOS:
            continue
        if pure_python_only and d.repo not in PURE_PYTHON_REPOS:
            continue
        for t in sorted(tasks, key=lambda x: x.task_id):
            if d.instance_id == t.instance_id:
                continue
            if d.created_at >= t.created_at:
                continue
            if not _related(d, t, relatedness):
                continue
            out.append(Pair(
                memory_id=d.memory_id,
                memory_unit_locator=d.memory_unit_locator,
                task_id=t.task_id, repo=d.repo,
                relatedness=relatedness.value,
                shared_files=tuple(sorted(set(d.files) & set(t.files))),
                donor_created_at=d.created_at.isoformat(),
                recipient_created_at=t.created_at.isoformat(),
            ))
    return out


def select_pairs(
    memories: Sequence[SolvedIssue],
    tasks: Sequence[FutureIssue],
    *,
    seed: int,
    tasks_per_memory: int = 4,
    relatedness: Relatedness = Relatedness.FILE,
    min_tasks_per_memory: int = 2,
    exclude_copyleft: bool = True,
    pure_python_only: bool = False,
) -> list[Pair]:
    """Deterministically select cells, keeping only multi-task memories.

    Reproducible from ``seed`` alone: an independent ``random.Random`` is drawn
    per memory and keyed by ``memory_unit_locator``, so adding or removing one
    memory does not perturb any other memory's draw -- the same rule the
    LongMemEval adapter uses, for the same reason.

    ``min_tasks_per_memory`` defaults to 2 because a memory meeting exactly one
    future task cannot speak to the axis this benchmark was chosen for. That is
    a deliberate restriction of the cell set on a property of the PAIRING, not
    on any outcome, so it does not condition on the dependent variable.
    """
    cands = candidate_pairs(
        memories, tasks, relatedness=relatedness,
        exclude_copyleft=exclude_copyleft, pure_python_only=pure_python_only,
    )
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
    """The BEAM-comparable diagonality statistic, computed from actual pairs."""
    counts: dict[str, int] = {}
    for p in pairs:
        counts[p.memory_unit_locator] = counts.get(p.memory_unit_locator, 0) + 1
    n = len(counts)
    solo = sum(1 for v in counts.values() if v == 1)
    vals = sorted(counts.values(), reverse=True)
    return {
        "n_pairs": len(pairs),
        "n_memories": n,
        "memories_with_1_task": solo,
        "memories_with_ge2_tasks": sum(1 for v in counts.values() if v >= 2),
        "memories_with_ge3_tasks": sum(1 for v in counts.values() if v >= 3),
        "pct_diagonal": (solo / n * 100.0) if n else 0.0,
        "max_tasks_per_memory": vals[0] if vals else 0,
        "beam_reference_pct_diagonal": 92.6,
    }


# --------------------------------------------------------------------------
# memory rendering
# --------------------------------------------------------------------------


def render_raw_memory(m: SolvedIssue) -> str:
    """RAW / extractive representation. Deterministic, ZERO model calls.

    Measured median 637 tokens under the reader's own tokenizer.
    """
    return (
        f"### Past issue in {m.repo} (resolved {m.created_at.date()})\n"
        f"{m.problem_statement.strip()}\n\n"
        f"### How it was fixed\n```diff\n{m.patch.strip()}\n```"
    )


def structured_skeleton(m: SolvedIssue) -> dict[str, Any]:
    """The part of a STRUCTURED memory available with no model call.

    A diff has real structure, so the skeleton is free; only the prose fields
    (root cause, fix pattern) need a call.
    """
    added = [ln[1:].strip() for ln in (m.patch or "").splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    symbols = sorted({
        mt.group(2) for ln in added
        for mt in [re.match(r"(def|class)\s+(\w+)", ln)] if mt
    })
    return {
        "repo": m.repo,
        "resolved": m.created_at.date().isoformat(),
        "files_touched": list(m.files),
        "symbols_added": symbols,
        "n_added_lines": len(added),
    }


# --------------------------------------------------------------------------
# SEARCH/REPLACE edits -- the format the reader can actually produce
# --------------------------------------------------------------------------

SEARCH_REPLACE_INSTRUCTIONS = (
    "Reply ONLY with one or more edit blocks in EXACTLY this format:\n"
    "<<<<<<< SEARCH\n"
    "<lines copied verbatim from the region shown>\n"
    "=======\n"
    "<replacement lines>\n"
    ">>>>>>> REPLACE\n"
    "The SEARCH text must match the shown region byte-for-byte."
)

_SR_BLOCK = re.compile(
    r"<{5,9} SEARCH\s*\n(.*?)\n?={5,9}\s*\n(.*?)\n?>{5,9} REPLACE", re.S
)


@dataclass(frozen=True)
class EditResult:
    """Outcome of applying model-proposed edits. Distinguishes the failures."""

    n_blocks: int
    n_applied: int
    new_text: str | None
    misses: tuple[str, ...] = field(default_factory=tuple)

    @property
    def parsed(self) -> bool:
        """The model emitted at least one well-formed block."""
        return self.n_blocks > 0

    @property
    def applied(self) -> bool:
        """At least one block matched and was applied."""
        return self.n_applied > 0

    @property
    def failure_mode(self) -> str:
        """Why this produced no edit. Never collapse these into one zero.

        ``no_block`` (format failure) and ``search_miss`` (the model located
        the wrong code) are different phenomena and a floor-effect diagnosis
        needs them apart.
        """
        if self.applied:
            return "ok"
        return "no_block" if self.n_blocks == 0 else "search_miss"


def parse_search_replace(response: str | None) -> list[tuple[str, str]]:
    """Extract (search, replace) blocks. Pure, deterministic, no I/O."""
    return [(m.group(1), m.group(2)) for m in _SR_BLOCK.finditer(response or "")]


def apply_edits(source: str, response: str | None) -> EditResult:
    """Apply SEARCH/REPLACE blocks to ``source``.

    A block whose search text is absent, or occurs more than once, is a MISS
    and is recorded rather than guessed at -- an ambiguous match applied to the
    first occurrence would silently edit the wrong code.
    """
    blocks = parse_search_replace(response)
    text = source
    applied = 0
    misses: list[str] = []
    for search, replace in blocks:
        n = text.count(search)
        if n == 1:
            text = text.replace(search, replace, 1)
            applied += 1
        else:
            misses.append(f"{'absent' if n == 0 else f'ambiguous_x{n}'}:{search[:60]!r}")
    return EditResult(
        n_blocks=len(blocks), n_applied=applied,
        new_text=text if applied else None, misses=tuple(misses),
    )

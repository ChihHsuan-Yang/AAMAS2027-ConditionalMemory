"""Execution harness for SWE-bench cells: checkout, edit, run tests, score.

Why this is a module and not private to the pilot script
--------------------------------------------------------
The scorer's positive control (gold patch must score 1.0; the unedited base
must score 0.0) is only worth running if it exercises **the same code the
pilot scores with**. When the control lived inside the pilot script as a
throwaway, it could drift from the scorer it claimed to certify. Both
``scripts/swebench_scorer_control.py`` and ``scripts/swebench_floor_pilot.py``
now import :func:`score_patched_file` from here, so a defect the control
cannot see is a defect the pilot cannot have.

Four defects this code exists to keep fixed -- each of which produced a
plausible ``0.0`` rather than a crash, and together took the positive control
from 0/6 to 10/10:

1. a multi-file gold fix is unsolvable by a single-file harness
   (:func:`is_single_file_solvable` gates them out);
2. the worktree must be reset to **each recipient's own** base commit
   (:func:`checkout_base`);
3. django's verbose runner prints a test's DOCSTRING instead of its id when
   it has one, and SWE-bench records what was printed -- so a ``PASS_TO_PASS``
   entry can literally be the prose ``"F expressions can be used in
   Meta.ordering."`` (:func:`normalize_test_ids` drops those);
4. ``OK (skipped=5)`` is a pass, and trailing ``Destroying test database...``
   lines mean the status is not the last line (:func:`django_status_ok`).

A FIFTH defect, found by running the control on the OTHER runner
--------------------------------------------------------------
The control above was only ever run on django and passed 10/10 there. Run on
sympy it scored **0/5 -- every correct gold patch read as 0.0** -- for two
further reasons, both of which the django path cannot exhibit:

5a. **SWE-bench stores sympy test ids as bare function names** (``test_point``,
    ``test_issue_22684``), not ``path::name``. pytest reads a bare name as a
    FILE PATH and reports ``ERROR: file or directory not found``, ``no tests
    ran``. :func:`resolve_pytest_ids` maps such a name onto the test files the
    instance's own ``test_patch`` touches, which is where SWE-bench's ids come
    from; an id it cannot place is DROPPED rather than guessed at.
5b. The sympy venv was Python 3.13 and sympy at these commits imports
    ``distutils``, removed in 3.12. Every test errored before running. That is
    an environment fact, recorded in the runner (which is part of experimental
    identity), not something code can fix.

Both produced ``returncode=4`` with **no verdict line at all**, which is why
:class:`TestOutcome` carries ``n_status_lines``: "the tests never ran" and
"the tests failed" must not be the same observation.

Nothing here suppresses stderr: a missing interpreter or an import error must
look different from a failing test, not identical to one.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "Runner",
    "TestOutcome",
    "checkout_base",
    "git_show",
    "django_status_ok",
    "normalize_test_ids",
    "resolve_pytest_ids",
    "test_patch_paths",
    "run_tests",
    "score_patched_file",
    "is_single_file_solvable",
]


@dataclass(frozen=True)
class Runner:
    """How one repository's tests are invoked. Part of experimental identity."""

    kind: str          # "pytest" | "django"
    python: str        # absolute interpreter path

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "python": self.python}


@dataclass(frozen=True)
class TestOutcome:
    """Result of one test invocation. Keeps the evidence, not just the verdict."""

    ok: bool
    returncode: int
    tail: str
    n_status_lines: int = 0
    cmd: tuple[str, ...] = ()


def _as_runner(runner: Runner | dict[str, Any]) -> Runner:
    return runner if isinstance(runner, Runner) else Runner(
        kind=runner["kind"], python=runner["python"])


# --------------------------------------------------------------------------
# worktree
# --------------------------------------------------------------------------


def checkout_base(repo_dir: Path, commit: str) -> bool:
    """Put the worktree at this recipient's base commit, discarding leftovers.

    Leaving the tree where the previous cell left it makes the gold patch fail
    to apply and turns every reward into a harness artifact -- defect (2).
    """
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "--", "."], check=False)
    subprocess.run(["git", "-C", str(repo_dir), "clean", "-qfd"], check=False)
    r = subprocess.run(["git", "-C", str(repo_dir), "-c", "advice.detachedHead=false",
                        "checkout", "-q", commit], capture_output=True, text=True)
    return r.returncode == 0


def git_show(repo_dir: Path, commit: str, path: str) -> str | None:
    p = subprocess.run(["git", "-C", str(repo_dir), "show", f"{commit}:{path}"],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


# --------------------------------------------------------------------------
# reading a runner's verdict
# --------------------------------------------------------------------------


def django_status_ok(output: str, returncode: int) -> tuple[bool, int]:
    """Did django's runner pass? Returns (ok, n_status_lines).

    Django prints a bare ``OK`` / ``OK (skipped=5)`` / ``FAILED (errors=1)``
    on its own line and then trailing notes, so neither ``endswith`` nor a
    substring test is safe: an early ``OK`` with a later failure would read as
    a pass, and a trailing "Destroying test database..." line means the status
    is not the last line -- defect (4).

    ``n_status_lines == 0`` means **no verdict was printed at all** (an import
    error, a missing interpreter, a bad test id). That is NOT a pass, and the
    count is returned so a caller can tell "the tests failed" from "the tests
    never ran".
    """
    status = [ln.strip() for ln in output.splitlines()
              if ln.strip() == "OK" or ln.strip().startswith(("OK (", "FAILED"))]
    ok = bool(status) and all(x.startswith("OK") for x in status) and returncode == 0
    return ok, len(status)


def normalize_test_ids(tests: Sequence[str], kind: str) -> list[str]:
    """Normalize SWE-bench test ids to the runner's CLI form.

    Django stores ``test_x (module.Class)`` and wants ``module.Class`` -- the
    whole class, because running a single method in isolation breaks tests
    that mutate shared state (a FALSE gold-patch failure during bring-up).

    It may also store a test's DOCSTRING where an id belongs -- defect (3).
    Prose has spaces and no dots; it is not addressable and is dropped rather
    than passed to the runner, where it would error and read as a failure.
    """
    out: list[str] = []
    for t in tests:
        if kind == "django":
            if "(" in t and t.endswith(")"):
                out.append(t.split("(", 1)[1].rstrip(")"))
            elif " " not in t and "." in t:
                out.append(t)
            # else: a docstring label, not addressable -- skip it
        else:
            out.append(t)
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


_TESTPATCH_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)


def test_patch_paths(test_patch: str | None) -> list[str]:
    """Test files the instance's own test patch touches. No I/O, deterministic."""
    return sorted({m.group(2) for m in _TESTPATCH_FILE.finditer(test_patch or "")})


def resolve_pytest_ids(tests: Sequence[str], test_patch: str | None,
                       repo_dir: Path | None = None) -> list[str]:
    """Turn SWE-bench's pytest ids into ids the pytest CLI can address.

    Defect (5a). sympy instances store BARE function names. Handed to pytest,
    ``test_point`` is interpreted as a path and the run errors with "file or
    directory not found" -- which the scorer then read as a failing test and
    a correct gold patch scored 0.0, in BOTH arms.

    An id that already names a file (``a/b.py::test_c``, or any id containing
    ``/`` or ``.py``) is passed through untouched. A bare name is qualified
    against each test file the instance's ``test_patch`` touches, producing
    ``<file>::<name>`` -- that is where SWE-bench's ids come from, so it is a
    re-derivation, not a guess.

    When ``repo_dir`` is given the fan-out is FILTERED to the files that
    actually define the function. That filter is not cosmetic: sympy-13757's
    ``test_patch`` touches two test files and ``test_issue_13079`` exists in
    only one, and pytest answers an id naming the other with
    ``ERROR: not found``, which fails the WHOLE invocation -- so a correct
    gold patch scored 0.0. (``--continue-on-collection-errors`` does not help:
    an unresolvable id is a usage error, not a collection error.)

    🔴 A bare name with NO file to attach it to is DROPPED, and the caller
    sees a shorter list. It is never passed through in the hope that pytest
    copes: pytest's response to an unresolvable id is an error that is
    indistinguishable from a failing test, which is the defect itself.
    """
    files = test_patch_paths(test_patch)
    out: list[str] = []
    for t in tests:
        if "::" in t or "/" in t or t.endswith(".py"):
            out.append(t)
            continue
        targets = files
        if repo_dir is not None and files:
            hit = [f for f in files if _defines(repo_dir / f, t)]
            # Fall back to the unfiltered fan-out only when the filter found
            # NOTHING -- an empty filter may mean the working tree is not at
            # the right commit, and silently dropping every id would turn a
            # scoring question into "no tests ran".
            targets = hit or files
        out.extend(f"{f}::{t}" for f in targets)
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def _defines(path: Path, name: str) -> bool:
    """Does this file define ``def <name>(``? Cheap textual check, no import."""
    try:
        return f"def {name}(" in path.read_text(errors="replace")
    except OSError:
        return False


def run_tests(repo_dir: Path, runner: Runner | dict[str, Any],
              tests: Sequence[str]) -> TestOutcome:
    """Run a list of tests. Exit code alone is never trusted for django.

    stderr is captured and folded into the scanned output on purpose: a
    missing interpreter must not be indistinguishable from a failing test.
    """
    r = _as_runner(runner)
    if not tests:
        return TestOutcome(ok=False, returncode=-1, tail="no addressable test ids", cmd=())
    if r.kind == "pytest":
        # --continue-on-collection-errors is REQUIRED, not cosmetic: a bare
        # SWE-bench name is fanned out across every test file the test_patch
        # touches (see resolve_pytest_ids) and will be absent from all but
        # one, so a strict collection error would fail a passing gold patch.
        cmd = [r.python, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider",
               "--continue-on-collection-errors"]
        cwd = repo_dir
    else:
        cmd = [r.python, "runtests.py", *tests, "--settings=test_sqlite", "-v1"]
        cwd = repo_dir / "tests"
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    out = (p.stdout + p.stderr).strip()
    tail = "\n".join(out.splitlines()[-4:])
    if r.kind == "pytest":
        # "no tests ran" is NOT a pass: with --continue-on-collection-errors
        # pytest can exit 0 having collected nothing, and a gold patch would
        # then score 1.0 for running zero tests.
        ran = bool(re.search(r"\d+ passed", out))
        ok = (p.returncode == 0 and ran
              and " failed" not in out and " error" not in out)
        n_status = 1 if re.search(r"\d+ (passed|failed|error)", out) else 0
    else:
        ok, n_status = django_status_ok(out, p.returncode)
    return TestOutcome(ok=ok, returncode=p.returncode, tail=tail,
                       n_status_lines=n_status, cmd=tuple(cmd))


# --------------------------------------------------------------------------
# eligibility
# --------------------------------------------------------------------------


def is_single_file_solvable(task_files: Sequence[str], shown_path: str) -> bool:
    """Can a harness that shows and edits ONE file possibly solve this task?

    A recipient whose gold fix spans several files is unsolvable BY
    CONSTRUCTION -- defect (1). Including it guarantees a ``0.0`` and inflates
    both-arms-fail with a harness artifact, which is the same "only reachable
    outcome" defect that voided the first pilot.
    """
    return len(task_files) == 1 and task_files[0] == shown_path


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------


def _ids_for(task, tests: Sequence[str], kind: str,
             repo_dir: Path | None = None) -> list[str]:
    """Runner-appropriate, addressable test ids for this task.

    pytest ids additionally need :func:`resolve_pytest_ids`, because sympy
    instances store bare function names -- defect (5a).
    """
    ids = normalize_test_ids(tests, kind)
    if kind == "pytest":
        ids = resolve_pytest_ids(ids, getattr(task, "test_patch", ""), repo_dir)
    return ids


def score_patched_file(repo_dir: Path, runner: Runner | dict[str, Any], task,
                       path: str, new_text: str, *,
                       p2p_limit: int = 20) -> tuple[float, str]:
    """Write ``new_text`` at ``path``, apply the test patch, run F2P then P2P.

    Returns ``(reward, detail)`` with reward in ``{0.0, 1.0}``. This function
    is only ever called when an edit APPLIED -- an unapplicable edit is
    ``reward: None`` at the caller and never reaches a scorer, because a 0.0
    there would manufacture a harmful memory out of an edit-format artifact.
    """
    r = _as_runner(runner)
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)
    subprocess.run(["git", "-C", str(repo_dir), "apply", "-"],
                   input=task.test_patch, text=True, check=False)
    target = repo_dir / path
    backup = target.read_text()
    try:
        target.write_text(new_text)
        f2p_ids = _ids_for(task, task.fail_to_pass, r.kind, repo_dir)
        f2p = run_tests(repo_dir, r, f2p_ids)
        detail = f"F2P rc={f2p.returncode} status_lines={f2p.n_status_lines} :: {f2p.tail}"
        if not f2p.ok:
            return 0.0, detail
        p2p_ids = _ids_for(task, task.pass_to_pass[:p2p_limit], r.kind, repo_dir)
        if not p2p_ids:
            return 1.0, detail + " :: P2P none addressable"
        p2p = run_tests(repo_dir, r, p2p_ids)
        return (1.0 if p2p.ok else 0.0), detail + f" :: P2P rc={p2p.returncode} {p2p.tail}"
    finally:
        target.write_text(backup)
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "."], check=False)

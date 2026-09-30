"""Tests for the SciCode adapter.

Three things these tests are FOR, beyond ordinary coverage:

1. **Pinning the structural verdict to the code.** Two facts settle the whole
   design -- ``ground_truth_code`` exists only in the dev split, and a
   recipient must be a problem's first substep. Both are asserted against the
   real corpus (skipped when it is absent), so a refactor that quietly widens
   either one fails loudly.

2. **Proving the scorer can fail, and can fail in the RIGHT WAY.** The defect
   this project has hit twice is an unrunnable solution scored 0.0. So the
   tests plant an unrunnable solution and assert ``reward is None``, plant a
   wrong answer and assert ``reward == 0.0``, and assert that
   ``ScoreResult`` REFUSES to be constructed with an error kind and a numeric
   reward.

3. **Proving the leakage detector can fire**, on a positive found in the real
   data (dev 19.1 and test 65.1 both define ``tensor``) and not only on a
   plant.

Tests needing the corpus skip when it is absent; the pure-logic ones always run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from p1mem.adapters.scicode import (
    BENCHMARK,
    DATASET_LICENSE,
    GENERIC_MODULES,
    HARNESS_SUPPLIED_STEPS,
    LEXICAL_THRESHOLD,
    FutureSubproblem,
    Relatedness,
    ScicodeDataError,
    ScoreResult,
    SolvedSubproblem,
    WriterSawFutureTask,
    assert_writer_blind,
    build_future_tasks,
    build_memory_units,
    build_test_program,
    calls_recipient_function,
    candidate_pairs,
    classify_failure,
    defines_recipient_function,
    detect_leak,
    extract_code,
    load_jsonl,
    multi_task_report,
    render_raw_memory,
    render_task_prompt,
    select_pairs,
    signature_line,
    to_source_segment,
)
from p1mem.memory.segment import TaskLeakageError

DEV = Path("/tmp/scicode_probe/problems_dev.jsonl")
TEST = Path("/tmp/scicode_probe/problems_test.jsonl")
needs_corpus = pytest.mark.skipif(
    not (DEV.is_file() and TEST.is_file()),
    reason="SciCode corpus not present at /tmp/scicode_probe",
)


# ------------------------------------------------------------------ fixtures
def _mem(**kw) -> SolvedSubproblem:
    base = dict(
        step_number="1.1", problem_id="1", problem_name="CG",
        step_description="Solve Ax=b by conjugate gradient.",
        step_background="The residual is orthogonalised each step.",
        function_header="def CG(A, b):\n    '''docs'''",
        gold_code="def CG(A, b):\n    return b",
        dependencies="import numpy as np\nfrom scipy.integrate import simps",
        return_line="    return x", n_test_cases=2)
    base.update(kw)
    return SolvedSubproblem(**base)


def _task(**kw) -> FutureSubproblem:
    base = dict(
        step_number="9.1", problem_id="9", problem_name="Weighted_Jacobi",
        step_description="Solve Ax=b by weighted Jacobi.",
        step_background="", function_header="def WJ(A, b):\n    '''docs'''",
        dependencies="import numpy as np\nfrom scipy.integrate import simps",
        return_line="    return x",
        test_cases=("assert np.allclose(WJ(A, b), target)",))
    base.update(kw)
    return FutureSubproblem(**base)


# -------------------------------------------------------------- units / IDs
def test_memory_id_and_locator_are_stable():
    m = _mem()
    assert m.memory_id == "scicode_dev::1.1"
    assert m.memory_unit_locator == m.memory_id
    assert m.source_episode_id == "scicode_dev::problem_1"


def test_raw_memory_is_the_segment_verbatim_and_needs_no_model():
    m = _mem()
    assert render_raw_memory(m) == m.episode_text
    assert m.gold_code in m.episode_text
    assert m.step_description in m.episode_text


def test_future_task_is_always_deterministic():
    assert _task().deterministic is True


def test_generic_modules_are_excluded_from_the_import_signature():
    m = _mem()
    assert "scipy.integrate.simps" in m.imports
    assert "numpy" not in m.imports          # generic, carries no signal
    assert "numpy" in GENERIC_MODULES


# --------------------------------------------------------------- data guards
def test_load_jsonl_raises_on_a_missing_file_rather_than_returning_empty():
    with pytest.raises(ScicodeDataError):
        load_jsonl("/tmp/definitely_not_a_scicode_file_9f2a.jsonl")


def test_load_jsonl_raises_on_an_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    with pytest.raises(ScicodeDataError):
        load_jsonl(p)


def test_build_memory_units_raises_on_a_substep_with_no_gold():
    rows = [{"problem_id": "1", "problem_name": "x",
             "required_dependencies": "import numpy as np",
             "sub_steps": [{"step_number": "1.1", "step_description_prompt": "d",
                            "function_header": "def f():", "test_cases": ["assert 1"],
                            "ground_truth_code": ""}]}]
    with pytest.raises(ScicodeDataError):
        build_memory_units(rows)


def test_build_future_tasks_raises_if_the_test_split_carries_gold():
    rows = [{"problem_id": "9", "problem_name": "x",
             "required_dependencies": "import numpy as np",
             "sub_steps": [{"step_number": "9.1", "step_description_prompt": "d",
                            "function_header": "def f():", "test_cases": ["assert 1"],
                            "ground_truth_code": "def f(): return 1"}]}]
    with pytest.raises(ScicodeDataError):
        build_future_tasks(rows)


def test_harness_supplied_steps_are_excluded_from_recipients():
    rows = [{"problem_id": "62", "problem_name": "dmrg",
             "required_dependencies": "import numpy as np",
             "sub_steps": [{"step_number": "62.1", "step_description_prompt": "d",
                            "function_header": "def f():", "test_cases": ["assert 1"]}]}]
    assert "62.1" in HARNESS_SUPPLIED_STEPS
    assert build_future_tasks(rows) == []


# ---------------------------------------------------------- writer blindness
def test_writer_blind_rejects_a_within_problem_pair():
    m = _mem(problem_id="9", step_number="9.2")
    with pytest.raises(WriterSawFutureTask):
        assert_writer_blind([m], [_task(problem_id="9")])


def test_writer_blind_accepts_a_cross_problem_pair():
    assert_writer_blind([_mem()], [_task()])      # must not raise


def test_source_segment_carries_no_task_shaped_metadata():
    seg = to_source_segment(_mem())
    assert seg.benchmark == BENCHMARK
    assert seg.text == _mem().episode_text
    for key in seg.episode_metadata:
        assert "answer" not in key and "task" not in key and "gold" not in key


def test_source_segment_construction_would_reject_a_task_shaped_key():
    """The barrier is real, not decorative: prove it can fire."""
    from p1mem.memory.segment import SourceSegment
    with pytest.raises(TaskLeakageError):
        SourceSegment(segment_id="a", benchmark="scicode",
                      benchmark_version="v", source_episode_id="e", text="t",
                      source_span={}, episode_metadata={"gold_answer": "x"})


# ------------------------------------------------------------------ pairing
def test_candidate_pairs_never_produce_a_within_problem_cell():
    ms = [_mem(problem_id="9", step_number="9.5")]
    assert candidate_pairs(ms, [_task(problem_id="9")],
                           relatedness=Relatedness.ALL) == []


def test_dependency_level_requires_a_shared_non_generic_import():
    m = _mem(dependencies="import numpy as np")
    t = _task(dependencies="import numpy as np")
    assert candidate_pairs([m], [t], relatedness=Relatedness.DEPENDENCY) == []
    m2 = _mem(dependencies="import numpy as np\nfrom scipy.integrate import simps")
    got = candidate_pairs([m2], [_task()], relatedness=Relatedness.DEPENDENCY)
    assert len(got) == 1 and got[0].shared_imports == ("scipy.integrate.simps",)


def test_select_pairs_is_deterministic_under_a_seed():
    ms = [_mem(step_number=f"1.{i}", problem_id="1") for i in range(1, 6)]
    ts = [_task(step_number=f"{9 + j}.1", problem_id=str(9 + j)) for j in range(6)]
    a = select_pairs(ms, ts, seed=7, tasks_per_memory=2,
                     relatedness=Relatedness.ALL)
    b = select_pairs(ms, ts, seed=7, tasks_per_memory=2,
                     relatedness=Relatedness.ALL)
    assert [p.as_row() for p in a] == [p.as_row() for p in b]
    c = select_pairs(ms, ts, seed=8, tasks_per_memory=2,
                     relatedness=Relatedness.ALL)
    assert [p.task_id for p in a] != [p.task_id for p in c]


def test_select_pairs_drops_memories_below_min_tasks():
    ms = [_mem()]
    got = select_pairs(ms, [_task()], seed=1, tasks_per_memory=4,
                       relatedness=Relatedness.ALL, min_tasks_per_memory=2)
    assert got == []          # exactly one candidate task -> excluded


def test_multi_task_report_prints_its_own_denominator():
    ms = [_mem(step_number="1.1"), _mem(step_number="1.2")]
    ts = [_task(step_number="9.1", problem_id="9"),
          _task(step_number="8.1", problem_id="8")]
    r = multi_task_report(candidate_pairs(ms, ts, relatedness=Relatedness.ALL))
    assert r["n_memories"] == 2 and r["pct_diagonal_denominator"] == 2
    assert r["memories_with_ge2_tasks"] == 2


def test_multi_task_report_on_no_pairs_returns_none_not_zero():
    """A rate over an empty denominator must be None. '0 of 0' is not 0%."""
    r = multi_task_report([])
    assert r["pct_diagonal"] is None and r["pct_diagonal_denominator"] == 0


# ------------------------------------------------------------ code extraction
@pytest.mark.parametrize("response,expected", [
    ("```python\ndef f():\n    return 1\n```", "def f():\n    return 1"),
    ("```\ndef f():\n    return 1\n```", "def f():\n    return 1"),
    ("def f():\n    return 1", "def f():\n    return 1"),
    ("```python\ndef f():\n    ret", "def f():\n    ret"),   # truncated fence
    ("I cannot solve this problem.", None),
    ("", None),
    (None, None),
])
def test_extract_code(response, expected):
    assert extract_code(response) == expected


def test_truncated_fence_does_not_leak_the_fence_marker_into_the_code():
    """Observed in the smoke run: a max_tokens-truncated reply put ```python
    itself into the scored program. Reward was still None, but the recorded
    KIND was wrong, and the kind is what a floor diagnosis reads."""
    got = extract_code("```python\ndef f():\n    x = 1\n")
    assert got is not None and "```" not in got


# -------------------------------------------------- the reward, and its edges
def test_error_kinds_cannot_carry_a_numeric_reward():
    with pytest.raises(ValueError):
        ScoreResult(reward=0.0, kind="syntax_error", n_tests=1)
    with pytest.raises(ValueError):
        ScoreResult(reward=None, kind="wrong_answer", n_tests=1)


def test_wrong_answer_is_zero_and_is_not_an_error():
    r = ScoreResult(reward=0.0, kind="wrong_answer", n_tests=1)
    assert r.reward == 0.0 and r.is_error is False


def test_unrunnable_is_none_and_is_an_error():
    r = ScoreResult(reward=None, kind="no_code_block", n_tests=1)
    assert r.reward is None and r.is_error is True


@pytest.mark.parametrize("stderr,kind", [
    ("Traceback...\nAssertionError", "wrong_answer"),
    ("  File x, line 1\n    def f(:\nSyntaxError: invalid syntax", "syntax_error"),
    ("IndentationError: unexpected indent", "syntax_error"),
    ("Traceback...\nNameError: name 'f' is not defined", "function_not_defined"),
    ("Traceback...\nValueError: boom", "runtime_error"),
])
def test_classify_failure(stderr, kind):
    assert classify_failure(stderr) == kind


def test_build_test_program_uses_the_official_loader_and_every_test_case():
    t = _task(test_cases=("assert a", "assert b"))
    prog = build_test_program(t, "def WJ(A, b):\n    return b", "/x/test_data.h5")
    assert "process_hdf5_to_tuple" in prog
    assert "'9.1', 2, '/x/test_data.h5'" in prog
    assert "targets[0]" in prog and "targets[1]" in prog
    assert "assert a" in prog and "assert b" in prog


# ------------------------------------------------------------- reader prompt
def test_both_arms_differ_only_by_the_memory_block():
    t = _task()
    without = render_task_prompt(t, None, filler="FILLER")
    with_m = render_task_prompt(t, "MEMORY", filler="FILLER")
    assert "FILLER" in without and "FILLER" in with_m
    assert "MEMORY" not in without and "MEMORY" in with_m
    # everything after the memory block is identical
    tail = "## The subproblem to solve"
    assert without.split(tail)[1] == with_m.split(tail)[1]


def test_prompt_never_contains_the_gold_or_the_test_cases():
    t = _task()
    p = render_task_prompt(t, None, filler="")
    assert "target" not in p and "assert" not in p


# ----------------------------------------------------------------- leakage
def test_signature_line_strips_the_docstring():
    assert signature_line("def WJ(A, b):\n    '''a b c'''") == "def WJ(A, b):"
    assert signature_line("") == ""


def test_leak_detector_fires_when_the_donor_defines_the_answer():
    m = _mem(gold_code="def WJ(A, b):\n    return b")
    assert defines_recipient_function(m, _task()) is True
    assert detect_leak(m, _task()).any_leak is True


def test_leak_detector_is_silent_on_a_clean_pair():
    v = detect_leak(_mem(), _task())
    assert v.defines_answer is False and v.any_leak is False


def test_a_name_mention_is_reported_but_is_NOT_counted_as_a_leak():
    """`tensor` appearing in a donor's prose is not the recipient's answer."""
    m = _mem(step_description="We use WJ-style weighting here.")
    v = detect_leak(m, _task())
    assert v.mentions_answer_name is True
    assert v.any_leak is False


# ------------------------------------------------------- against the corpus
@needs_corpus
def test_corpus_gold_is_dev_only_and_recipients_are_step_one():
    dev = load_jsonl(DEV)
    test = load_jsonl(TEST)
    assert len(dev) == 15 and len(test) == 65
    assert {r["problem_id"] for r in dev} & {r["problem_id"] for r in test} == set()
    assert all(s.get("ground_truth_code") for r in dev for s in r["sub_steps"])
    assert not any(s.get("ground_truth_code")
                   for r in test for s in r["sub_steps"])
    tasks = build_future_tasks(test)
    assert all(t.step_number.endswith(".1") for t in tasks)


@needs_corpus
def test_corpus_reproduces_the_reported_pair_counts():
    """Pins the feasibility verdict to the code, as the SWE-bench tests do."""
    memories = build_memory_units(load_jsonl(DEV))
    tasks = build_future_tasks(load_jsonl(TEST))
    assert len(memories) == 50 and len(tasks) == 64
    assert_writer_blind(memories, tasks)
    exp = {
        Relatedness.ALL: (3200, 50, 50),
        Relatedness.DEPENDENCY: (12, 7, 5),
        Relatedness.LEXICAL: (163, 43, 34),
    }
    for level, (n_pairs, n_mem, n_ge2) in exp.items():
        r = multi_task_report(candidate_pairs(memories, tasks, relatedness=level))
        assert (r["n_pairs"], r["n_memories"], r["memories_with_ge2_tasks"]) == \
            (n_pairs, n_mem, n_ge2), f"{level} drifted: {r}"
        assert r["pct_diagonal"] < 92.6      # BEAM's number, the bar to clear


@needs_corpus
def test_corpus_leak_rate_and_the_one_known_positive():
    memories = {m.step_number: m for m in build_memory_units(load_jsonl(DEV))}
    tasks = {t.step_number: t for t in build_future_tasks(load_jsonl(TEST))}
    # the known positive: both define `tensor`
    assert defines_recipient_function(memories["19.1"], tasks["65.1"]) is True
    # a known negative
    assert defines_recipient_function(memories["1.1"], tasks["65.1"]) is False
    leaks = [detect_leak(m, t) for m in memories.values() for t in tasks.values()
             if m.problem_id != t.problem_id]
    n_leak = sum(v.any_leak for v in leaks)
    assert len(leaks) == 3200
    assert n_leak == 1, f"leak count drifted: {n_leak}/3200"

"""The invariant test: the memory writer NEVER observes the future task.

    m = W(episode)      never      W(episode, task)

These tests are the enforcement, not the documentation. Each has a NEGATIVE
CONTROL that plants the defect and requires the check to fire -- a guard only
ever run against compliant code is not known to detect anything.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from p1mem.memory import representations as R
from p1mem.memory import semantic_type as ST
from p1mem.memory.prompts import PROMPT_DIR, PromptError, all_prompts, load_prompt
from p1mem.memory.segment import (
    SourceSegment,
    TaskLeakageError,
    assert_writer_signature,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "p1mem" / "memory"


def _seg(**kw):
    base = dict(
        segment_id="t1:0-0", benchmark="probe", benchmark_version="0",
        source_episode_id="t1", text="State 0\n- URL: u0\n- Action: click\n",
        source_span={"start": 0, "end": 0},
    )
    base.update(kw)
    return SourceSegment(**base)


# ------------------------------------------------- barrier 1: writer arity
def test_every_writer_takes_a_segment_and_nothing_else():
    """Discovered by introspection, so a writer added later is covered too."""
    entries = R.writer_entry_points()
    assert len(entries) >= 3, "expected at least the three protocol representations"
    for name, fn in entries:
        assert_writer_signature(fn, name=name)


def test_classifier_also_takes_only_a_segment():
    assert_writer_signature(ST.SemanticTypeClassifier.classify)
    assert_writer_signature(ST.heuristic_semantic_type)


@pytest.mark.parametrize("bad", [
    lambda segment, task: None,            # the literal violation
    lambda segment, task=None: None,       # "optional, just for logging"
    lambda segment, **kw: None,            # keyword back door
    lambda segment, *a: None,              # positional back door
    lambda episode: None,                  # renamed slot
    lambda: None,                          # no segment at all
])
def test_negative_control_bad_signatures_are_rejected(bad):
    """NEGATIVE CONTROL: each of these must raise. If any passes, the guard is void."""
    with pytest.raises(TaskLeakageError):
        assert_writer_signature(bad, name="planted")


def test_calling_a_writer_with_a_task_is_a_typeerror_from_python_itself():
    """Not our check -- the interpreter's. That is the strongest form."""
    w = R.RawExtractiveWriter()
    with pytest.raises(TypeError):
        w.write(_seg(), "what was the total?")      # type: ignore[call-arg]
    with pytest.raises(TypeError):
        w.write(_seg(), task="what was the total?")  # type: ignore[call-arg]


# ------------------------------------------- barrier 2: closed field set
def test_segment_is_frozen_and_slotted():
    """Assert the SUBSTANCE -- nothing is set -- not a particular exception type.

    MEASURED on CPython 3.13: assigning an EXISTING field raises
    ``FrozenInstanceError``; assigning a NEW attribute raises ``TypeError``
    ("super(type, obj): obj ... is not an instance or subtype of type"),
    because ``slots=True`` rebuilds the class while the generated frozen
    ``__setattr__`` keeps a closure over the original. The message is
    confusing, but the barrier holds: in both cases the attribute is NOT set
    and there is no ``__dict__`` for it to land in. Pinning the test to an
    exception type would make it a test of a CPython implementation detail;
    pinning it to "the value did not change" tests the thing we need.
    """
    s = _seg()
    with pytest.raises(Exception):
        s.text = "mutated"
    assert s.text != "mutated", "frozen segment was mutated"

    with pytest.raises(Exception):
        s.question = "leak"
    assert not hasattr(s, "question"), "a task field was attached to a segment"
    assert not hasattr(s, "__dict__"), "slots=True lost: there is a dict to smuggle into"


# --------------------------------------- barrier 3: metadata denylist
@pytest.mark.parametrize("key", [
    "question", "answer", "gold_answer", "answer_session_id", "eval_function",
    "expected_output", "task_type", "ground_truth", "Question", "GOLD",
    "target-value", "solution_text",
])
def test_negative_control_task_shaped_metadata_is_rejected(key):
    """NEGATIVE CONTROL: planted task-shaped keys must each raise."""
    with pytest.raises(TaskLeakageError):
        _seg(episode_metadata={key: "x"})


@pytest.mark.parametrize("key", [
    "domain", "environment", "outcome", "session_id", "url", "trajectory_id",
    "n_states", "start_state_index",
])
def test_legitimate_episode_metadata_is_accepted(key):
    """The denylist must not be so broad that real past-episode metadata fails."""
    assert _seg(episode_metadata={key: "x"}) is not None


# ------------------------------- barrier 4: one placeholder, ever
def test_all_shipped_prompts_load_and_interpolate_only_the_segment():
    prompts = all_prompts()
    assert set(prompts) >= {
        "summary_v1", "structured_v1", "structured_procedural_v1", "semantic_type_v1"}
    for name, p in prompts.items():
        found = set(re.findall(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})", p.text))
        assert found == {"segment_text"}, f"{name} interpolates {found}"


def test_negative_control_a_prompt_with_a_task_placeholder_is_rejected(tmp_path):
    """NEGATIVE CONTROL: plant a {question} placeholder; loading must fail."""
    (tmp_path / "leaky_v1.txt").write_text(
        "#!p1mem-prompt leaky_v1 1.0.0\nSegment: {segment_text}\nQuestion: {question}\n")
    with pytest.raises(PromptError, match="illegal placeholder"):
        load_prompt("leaky_v1", prompt_dir=tmp_path)


def test_render_takes_a_string_not_an_object():
    """An object argument could expose other attributes to a format spec."""
    p = load_prompt("summary_v1")
    with pytest.raises(PromptError):
        p.render(_seg())            # type: ignore[arg-type]


def test_rendered_prompt_contains_only_the_segment_text():
    p = load_prompt("summary_v1")
    seg = _seg(text="UNIQUE-SEGMENT-BODY",
               episode_metadata={"domain": "SECRET-METADATA-VALUE"})
    out = p.render(seg.text)
    assert "UNIQUE-SEGMENT-BODY" in out
    assert "SECRET-METADATA-VALUE" not in out


# --------------------------------- static sweep: no task word in the writer path
TASK_WORDS = re.compile(
    r"\b(future_task_id|future_task|gold_answer|question_text)\b")


def test_no_writer_module_references_a_task_field_outside_a_sentinel():
    """A grep-style sweep over the whole package, not just the files I remember.

    Two allowances, both deliberate and both narrow:
      * the string 'none:write_pass' assigned to cache-key fields the cache
        module requires but the write pass has no value for;
      * comments and docstrings, which is where the invariant is explained.
    """
    offenders = []
    for path in sorted(SRC.glob("*.py")):
        src = path.read_text()
        tree_lines = src.split("\n")
        for i, line in enumerate(tree_lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if not TASK_WORDS.search(line):
                continue
            if "none:write_pass" in line or '"future_task_id"' in line:
                continue
            offenders.append(f"{path.name}:{i}: {stripped}")
    # Docstrings would false-positive a naive line scan, so re-check by AST:
    # only flag lines that are in actual code.
    real = [o for o in offenders if "m = W" not in o and "W(episode" not in o]
    assert not real, "task-field references on the writer path:\n" + "\n".join(real)


def test_no_writer_signature_in_the_package_accepts_more_than_a_segment():
    """Sweep EVERY public write/classify callable in the package by introspection."""
    import p1mem.memory as pkg
    checked = 0
    for modname in ("representations", "semantic_type"):
        mod = __import__(f"p1mem.memory.{modname}", fromlist=["x"])
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj.__module__ != mod.__name__:
                continue
            for attr in ("write", "classify"):
                fn = getattr(obj, attr, None)
                if fn is not None and callable(fn):
                    assert_writer_signature(fn, name=f"{obj.__name__}.{attr}")
                    checked += 1
    assert checked >= 4, f"sweep only found {checked} entry points; it may be vacuous"

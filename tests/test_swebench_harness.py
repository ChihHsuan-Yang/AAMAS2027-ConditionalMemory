"""The four harness defects, each pinned by a test that fails without the fix.

Every one of these produced a plausible ``0.0`` rather than a crash during
bring-up, and together they took the scorer's positive control from 0/6 to
10/10. They are pinned here so a refactor cannot quietly reintroduce one; a
silent regression would not crash, it would lower the measured solve rate in
both arms and look like difficulty.
"""
from __future__ import annotations

from p1mem.adapters.swebench_harness import (
    Runner,
    django_status_ok,
    is_single_file_solvable,
    normalize_test_ids,
)

# ---- defect 4: reading django's verdict -----------------------------------


def test_bare_ok_is_a_pass():
    assert django_status_ok("Ran 3 tests in 0.1s\n\nOK\n", 0) == (True, 1)


def test_ok_with_skips_is_a_pass():
    ok, n = django_status_ok("Ran 8 tests\n\nOK (skipped=5)\n", 0)
    assert ok and n == 1


def test_ok_with_expected_failures_is_a_pass():
    ok, _ = django_status_ok("OK (expected failures=1)\n", 0)
    assert ok


def test_failed_is_not_a_pass():
    ok, n = django_status_ok("FAILED (errors=1)\n", 1)
    assert not ok and n == 1


def test_trailing_teardown_lines_do_not_hide_the_status():
    """The status is NOT the last line; endswith() would read this as a fail."""
    out = "OK\nDestroying test database for alias 'default'...\n"
    assert django_status_ok(out, 0) == (True, 1)


def test_an_early_ok_cannot_mask_a_later_failure():
    """Two suites in one run: a substring test would call this a pass."""
    out = "OK\nDestroying test database...\nFAILED (failures=2)\n"
    ok, n = django_status_ok(out, 1)
    assert not ok and n == 2


def test_no_status_line_is_not_a_pass_and_is_distinguishable():
    """An import error prints no verdict. It must not read as 'tests failed'.

    n_status_lines==0 is the signal that the tests never ran at all, which is
    an instrument failure, not a model failure.
    """
    ok, n = django_status_ok("ImportError: cannot import name 'Foo'\n", 1)
    assert not ok and n == 0


def test_a_nonzero_returncode_overrides_a_printed_ok():
    assert django_status_ok("OK\n", 1)[0] is False


# ---- defect 3: django records a docstring where an id belongs -------------


def test_parenthesised_form_becomes_the_class_path():
    assert normalize_test_ids(
        ["test_x (queries.tests.Ticket1)"], "django") == ["queries.tests.Ticket1"]


def test_a_docstring_entry_is_dropped_not_passed_to_the_runner():
    """The real observed entry. Passing it makes runtests.py error, which read
    as a gold-patch FAILURE and would have turned every django cell into a
    false both-arms-fail."""
    got = normalize_test_ids(
        ["F expressions can be used in Meta.ordering.",
         "test_y (queries.tests.T2)"], "django")
    assert got == ["queries.tests.T2"]


def test_a_bare_dotted_id_survives():
    assert normalize_test_ids(["a.b.C"], "django") == ["a.b.C"]


def test_duplicate_classes_collapse_preserving_order():
    got = normalize_test_ids(
        ["t1 (m.C)", "t2 (m.C)", "t3 (m.D)"], "django")
    assert got == ["m.C", "m.D"]


def test_pytest_ids_pass_through_untouched():
    ids = ["tests/test_a.py::test_one", "tests/test_b.py::TestC::test_two"]
    assert normalize_test_ids(ids, "pytest") == ids


def test_pytest_does_not_drop_a_spacey_id():
    """The docstring rule is django-specific; applying it to pytest would
    silently drop parametrised ids like ``test_f[a b]``."""
    assert normalize_test_ids(["tests/t.py::test_f[a b]"], "pytest") == \
        ["tests/t.py::test_f[a b]"]


# ---- defect 1: multi-file gold fixes ---------------------------------------


def test_single_file_fix_matching_the_shown_path_is_solvable():
    assert is_single_file_solvable(("pkg/a.py",), "pkg/a.py")


def test_multi_file_fix_is_not_solvable_by_a_single_file_harness():
    assert not is_single_file_solvable(("pkg/a.py", "pkg/b.py"), "pkg/a.py")


def test_single_file_fix_in_a_file_we_do_not_show_is_not_solvable():
    assert not is_single_file_solvable(("pkg/b.py",), "pkg/a.py")


def test_no_files_at_all_is_not_solvable():
    assert not is_single_file_solvable((), "pkg/a.py")


# ---- runner identity -------------------------------------------------------


def test_runner_records_the_interpreter_as_part_of_experimental_identity():
    r = Runner(kind="django", python="/tmp/venv/bin/python")
    assert r.as_dict() == {"kind": "django", "python": "/tmp/venv/bin/python"}


# ---- defect 5a/5d: pytest ids, found by running the control on sympy ------


TP_ONE = ("diff --git a/sympy/geometry/tests/test_point.py "
          "b/sympy/geometry/tests/test_point.py\n@@ -1 +1 @@\n")
TP_TWO = (TP_ONE + "diff --git a/sympy/polys/tests/test_polytools.py "
          "b/sympy/polys/tests/test_polytools.py\n@@ -1 +1 @@\n")


def test_test_patch_paths_reads_post_image_paths():
    from p1mem.adapters.swebench_harness import test_patch_paths
    assert test_patch_paths(TP_TWO) == ["sympy/geometry/tests/test_point.py",
                                        "sympy/polys/tests/test_polytools.py"]


def test_test_patch_paths_on_empty_is_empty_not_error():
    from p1mem.adapters.swebench_harness import test_patch_paths
    assert test_patch_paths("") == [] and test_patch_paths(None) == []


def test_a_bare_sympy_name_is_qualified_against_the_test_patch():
    """The real defect: pytest reads a bare name as a FILE PATH and errors."""
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    assert resolve_pytest_ids(["test_point"], TP_ONE) == \
        ["sympy/geometry/tests/test_point.py::test_point"]


def test_an_already_qualified_id_is_left_alone():
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    ids = ["sympy/a/tests/test_b.py::test_c"]
    assert resolve_pytest_ids(ids, TP_TWO) == ids


def test_a_path_only_id_is_left_alone():
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    assert resolve_pytest_ids(["sympy/a/tests/test_b.py"], TP_TWO) == \
        ["sympy/a/tests/test_b.py"]


def test_a_bare_name_with_no_test_patch_is_dropped_not_passed_through():
    """Unaddressable must fail closed. Passing it makes pytest error, which is
    indistinguishable from a failing test -- the defect itself."""
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    assert resolve_pytest_ids(["test_point"], "") == []


def test_fanout_is_filtered_to_files_that_define_the_function(tmp_path):
    """sympy-13757: 2 test files, function in 1. pytest answers the id naming
    the other with 'ERROR: not found', which fails the WHOLE invocation, so a
    correct gold patch scored 0.0."""
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    (tmp_path / "sympy/geometry/tests").mkdir(parents=True)
    (tmp_path / "sympy/polys/tests").mkdir(parents=True)
    (tmp_path / "sympy/geometry/tests/test_point.py").write_text("x = 1\n")
    (tmp_path / "sympy/polys/tests/test_polytools.py").write_text(
        "def test_issue_13079():\n    pass\n")
    got = resolve_pytest_ids(["test_issue_13079"], TP_TWO, tmp_path)
    assert got == ["sympy/polys/tests/test_polytools.py::test_issue_13079"]


def test_unfiltered_fanout_without_a_repo_dir_keeps_both(tmp_path):
    """Without a tree to consult, the filter must not silently drop ids."""
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    assert len(resolve_pytest_ids(["test_issue_13079"], TP_TWO)) == 2


def test_filter_falls_back_when_it_matches_nothing(tmp_path):
    """An empty filter may mean the worktree is at the wrong commit. Dropping
    every id would turn a scoring question into 'no tests ran'."""
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    got = resolve_pytest_ids(["test_nowhere"], TP_TWO, tmp_path)
    assert len(got) == 2


def test_duplicate_qualified_ids_collapse():
    from p1mem.adapters.swebench_harness import resolve_pytest_ids
    got = resolve_pytest_ids(["test_point", "test_point"], TP_ONE)
    assert got == ["sympy/geometry/tests/test_point.py::test_point"]

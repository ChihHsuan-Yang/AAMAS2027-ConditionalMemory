"""The arm-symmetry repair, and proof that its guards can fail.

A check only ever run on the case it was written for detects nothing known,
so every guard here is also run against a deliberately corrupted input in the
shape of the defect it exists to catch.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from p1mem.adapters.swebench import SolvedIssue, parse_patch_files
from p1mem.adapters.swebench_prompt import (
    MEMORY_CLOSE,
    MEMORY_OPEN,
    PROMPT_VERSION,
    ArmAsymmetry,
    PatchFormat,
    PromptVariant,
    assert_arm_symmetric,
    build_prompt,
    defang_patch,
    render_memory,
    response_has_diff_contagion,
)

PATCH = """diff --git a/pkg/mod.py b/pkg/mod.py
index 1111111..2222222 100644
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -10,7 +10,8 @@ class Thing:
     def go(self):
-        return self.x
+        if self.x is None:
+            return 0
+        return self.x
 
     def stop(self):
"""

REGION = "def go(self):\n    return self.x\n"
ISSUE = "`Thing.go` returns None when x is unset."


def _mem() -> SolvedIssue:
    return SolvedIssue(
        instance_id="proj__proj-1", repo="proj/proj",
        problem_statement="go() blew up on an unset x",
        patch=PATCH,
        created_at=_dt.datetime(2021, 1, 1, tzinfo=_dt.timezone.utc),
        files=parse_patch_files(PATCH),
    )


def _arms(**kw):
    common = dict(path="pkg/mod.py", shown_region=REGION, issue_text=ISSUE, **kw)
    return (build_prompt(memory=None, **common),
            build_prompt(memory=_mem(), **common))


# ----------------------------------------------------------------- defanging


def test_defang_removes_every_diff_marker_line():
    out = defang_patch(PATCH)
    bad = [ln for ln in out.splitlines()
           if ln.startswith(("+", "-", "@@", "diff --git", "index "))]
    assert bad == [], bad


def test_defang_is_lossless_on_content_lines():
    """The repair must change the ENCODING, not the memory's content.

    Every added/removed/context line's text must survive verbatim, or the
    format fix is silently also a content ablation and any DeltaU measured
    afterwards confounds the two.
    """
    originals = [ln[1:] for ln in PATCH.splitlines()
                 if ln[:1] in "+- " and not ln.startswith(("+++", "---"))]
    out = defang_patch(PATCH)
    for text in originals:
        assert any(ln.endswith(text) and ln.startswith("[") for ln in out.splitlines()), text


def test_defang_states_add_and_remove_in_words():
    out = defang_patch(PATCH)
    assert "[added]" in out and "[removed]" in out and "[hunk]" in out


def test_defang_handles_empty_and_none():
    assert defang_patch("") == ""
    assert defang_patch(None) == ""


def test_raw_diff_format_still_reachable_as_a_control():
    """The failing encoding must stay runnable, or the repair has no control."""
    raw = render_memory(_mem(), PatchFormat.RAW_DIFF)
    assert "```diff" in raw
    assert "```diff" not in render_memory(_mem(), PatchFormat.DEFANGED)


def test_both_formats_carry_the_same_added_lines():
    added = [ln[1:].strip() for ln in PATCH.splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    raw = render_memory(_mem(), PatchFormat.RAW_DIFF)
    defanged = render_memory(_mem(), PatchFormat.DEFANGED)
    for a in added:
        assert a in raw and a in defanged


# ------------------------------------------------------------- arm symmetry


def test_v2_arms_are_symmetric():
    without, with_ = _arms()
    assert_arm_symmetric(without, with_)          # must not raise


def test_v2_without_arm_still_has_the_memory_section():
    without, _ = _arms()
    assert MEMORY_OPEN in without.user and MEMORY_CLOSE in without.user
    assert "(none available" in without.user


def test_v2_target_region_comes_after_the_memory_slot():
    _, with_ = _arms()
    assert with_.user.index(MEMORY_CLOSE) < with_.user.index("### TARGET FILE")


def test_v2_instruction_is_last():
    _, with_ = _arms()
    assert with_.user.rstrip().endswith("section of this message.")


def test_the_only_difference_between_arms_is_inside_the_slot():
    without, with_ = _arms()
    a = without.user[:without.user.index(MEMORY_OPEN)]
    b = with_.user[:with_.user.index(MEMORY_OPEN)]
    assert a == b
    a2 = without.user[without.user.index(MEMORY_CLOSE):]
    b2 = with_.user[with_.user.index(MEMORY_CLOSE):]
    assert a2 == b2


# --- the guards must FAIL on inputs shaped like the defects they catch -----


def test_symmetry_check_fires_on_an_arm_only_instruction():
    """The exact mistake the repair invites: 'tell the WITH arm not to copy'."""
    without, with_ = _arms()
    tampered = type(with_)(
        system=with_.system,
        user=with_.user + "\nDo not copy the diff notation from the memory.",
        variant=with_.variant, patch_format=with_.patch_format,
        prompt_version=with_.prompt_version, has_memory=True)
    with pytest.raises(ArmAsymmetry, match="OUTSIDE the memory slot"):
        assert_arm_symmetric(without, tampered)


def test_symmetry_check_fires_on_a_differing_system_prompt():
    without, with_ = _arms()
    tampered = type(with_)(
        system=with_.system + " Ignore the memory's formatting.",
        user=with_.user, variant=with_.variant, patch_format=with_.patch_format,
        prompt_version=with_.prompt_version, has_memory=True)
    with pytest.raises(ArmAsymmetry, match="system prompts differ"):
        assert_arm_symmetric(without, tampered)


def test_symmetry_check_fires_when_the_target_region_differs():
    """Two arms shown different code is the worst asymmetry and must not pass."""
    without = build_prompt(path="pkg/mod.py", shown_region=REGION,
                           issue_text=ISSUE, memory=None)
    with_ = build_prompt(path="pkg/mod.py", shown_region=REGION + "\n# extra\n",
                         issue_text=ISSUE, memory=_mem())
    with pytest.raises(ArmAsymmetry, match="OUTSIDE the memory slot"):
        assert_arm_symmetric(without, with_)


def test_symmetry_check_refuses_an_unslotted_prompt_rather_than_passing_it():
    """Absence must fail closed. A v1 prompt has no slot and cannot be checked.

    Returning quietly here would let the legacy, genuinely asymmetric prompt
    be reported as symmetric -- a check that cannot see its subject.
    """
    without = build_prompt(path="pkg/mod.py", shown_region=REGION, issue_text=ISSUE,
                           memory=None, variant=PromptVariant.V1_LEGACY)
    with_ = build_prompt(path="pkg/mod.py", shown_region=REGION, issue_text=ISSUE,
                         memory=_mem(), variant=PromptVariant.V1_LEGACY)
    with pytest.raises(ArmAsymmetry, match="no memory slot"):
        assert_arm_symmetric(without, with_)


def test_symmetry_check_fires_on_mislabelled_arms():
    without, with_ = _arms()
    with pytest.raises(ArmAsymmetry, match="mislabelled"):
        assert_arm_symmetric(with_, with_)


def test_v1_legacy_is_reproducible_and_is_genuinely_asymmetric():
    """v1 must stay buildable so the repair has the run it repairs as a control."""
    without = build_prompt(path="pkg/mod.py", shown_region=REGION, issue_text=ISSUE,
                           memory=None, variant=PromptVariant.V1_LEGACY)
    with_ = build_prompt(path="pkg/mod.py", shown_region=REGION, issue_text=ISSUE,
                         memory=_mem(), variant=PromptVariant.V1_LEGACY)
    assert "```diff" in with_.user and "```diff" not in without.user
    assert without.prompt_version == "swebench_v1"
    assert with_.user.endswith(without.user)     # v1 prepends, it does not slot


def test_prompt_version_is_recorded_on_the_built_prompt():
    _, with_ = _arms()
    assert with_.prompt_version == PROMPT_VERSION == "swebench_v2_symmetric"
    assert with_.patch_format == "defanged"


def test_patch_format_is_recorded_when_raw_diff_is_chosen():
    _, with_ = _arms(patch_format=PatchFormat.RAW_DIFF)
    assert with_.patch_format == "raw_diff"


# ------------------------------------------------- the contagion diagnostic


def test_contagion_diagnostic_detects_the_real_11555_response():
    """The observed failure: diff lines inside SEARCH, no separator, no end."""
    observed = ("<<<<<<< SEARCH\n"
                "    def clear_select_fields(self):\n"
                "+    def add_select_col(self, col):\n"
                "+        self.select += col,\n")
    d = response_has_diff_contagion(observed)
    assert d["has_search_marker"] and not d["has_separator"]
    assert not d["has_replace_marker"]
    assert d["n_diff_marker_lines"] == 2


def test_contagion_diagnostic_is_clean_on_a_well_formed_edit():
    good = ("<<<<<<< SEARCH\n    return self.x\n=======\n"
            "    return self.x or 0\n>>>>>>> REPLACE")
    d = response_has_diff_contagion(good)
    assert d["has_search_marker"] and d["has_separator"] and d["has_replace_marker"]
    assert d["n_diff_marker_lines"] == 0


def test_contagion_diagnostic_handles_none():
    d = response_has_diff_contagion(None)
    assert d["n_diff_marker_lines"] == 0 and not d["has_search_marker"]

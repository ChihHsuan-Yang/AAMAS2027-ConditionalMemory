"""Prompt versioning: the version must be a FUNCTION OF THE TEXT (B2).

Three prior incidents in this project came from prompt drift across copies.
A hand-maintained label keeps reading "v1" after the text beneath it changes,
so every test here plants an edit and requires the version to move.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from p1mem.memory.prompts import (
    PROMPT_DIR,
    Prompt,
    PromptError,
    all_prompts,
    load_prompt,
    prompt_manifest,
)

HEADER = "#!p1mem-prompt p_v1 1.0.0\n"
BODY = "Summarise this.\n\n{segment_text}\n"


def write(tmp_path: Path, text: str, name: str = "p_v1") -> Path:
    p = tmp_path / f"{name}.txt"
    p.write_text(text)
    return p


def test_version_changes_when_one_character_of_the_body_changes(tmp_path):
    """THE test this module exists for."""
    write(tmp_path, HEADER + BODY)
    v1 = load_prompt("p_v1", prompt_dir=tmp_path).version
    write(tmp_path, HEADER + BODY.replace("Summarise", "Summarize"))
    v2 = load_prompt("p_v1", prompt_dir=tmp_path).version
    assert v1 != v2, "a silent prompt edit did not change the recorded version"


def test_version_changes_on_whitespace_only_edit(tmp_path):
    """Even a whitespace edit is a different prompt to a tokenizer."""
    write(tmp_path, HEADER + BODY)
    v1 = load_prompt("p_v1", prompt_dir=tmp_path).version
    write(tmp_path, HEADER + BODY.replace("this.", "this. "))
    assert load_prompt("p_v1", prompt_dir=tmp_path).version != v1


def test_a_semver_bump_with_no_body_change_is_still_visible(tmp_path):
    write(tmp_path, HEADER + BODY)
    v1 = load_prompt("p_v1", prompt_dir=tmp_path).version
    write(tmp_path, "#!p1mem-prompt p_v1 1.0.1\n" + BODY)
    v2 = load_prompt("p_v1", prompt_dir=tmp_path).version
    assert v1 != v2 and "1.0.1" in v2


def test_the_memoisation_cannot_serve_a_stale_prompt(tmp_path):
    """Caching on the path alone would REINTRODUCE the drift defect."""
    write(tmp_path, HEADER + BODY)
    first = load_prompt("p_v1", prompt_dir=tmp_path)
    write(tmp_path, HEADER + BODY + "Extra line.\n")
    second = load_prompt("p_v1", prompt_dir=tmp_path)
    assert first.version != second.version
    assert "Extra line." in second.text


def test_two_copies_of_one_prompt_have_visibly_different_versions(tmp_path):
    """The 'three functions, one name' shape: a copy that drifted must not
    look identical to the original."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    write(a, HEADER + BODY)
    write(b, HEADER + BODY + "\nAlso mention the URL.\n")
    va = load_prompt("p_v1", prompt_dir=a)
    vb = load_prompt("p_v1", prompt_dir=b)
    assert va.semver == vb.semver, "the hand-kept label is identical -- as expected"
    assert va.version != vb.version, "but the recorded version must differ"


def test_version_string_contains_the_digest(tmp_path):
    write(tmp_path, HEADER + BODY)
    p = load_prompt("p_v1", prompt_dir=tmp_path)
    assert p.version == f"p_v1@1.0.0+{p.sha256[:12]}"


# ---------------------------------------------------- malformed prompt files
@pytest.mark.parametrize("text,match", [
    ("no header\n{segment_text}\n", "first line"),
    (HEADER, "body is empty"),
    ("#!p1mem-prompt other_name 1.0.0\n" + BODY, "filename stem"),
    ("#!p1mem-prompt p_v1 1.0\n" + BODY, "first line"),
    (HEADER + "no placeholder at all\n", "never interpolates"),
    (HEADER + "{segment_text} and {question}\n", "illegal placeholder"),
    (HEADER + "{segment_text} and {task}\n", "illegal placeholder"),
    (HEADER + "{segment_text} and {gold_answer}\n", "illegal placeholder"),
])
def test_negative_control_malformed_prompts_are_rejected(tmp_path, text, match):
    write(tmp_path, text)
    with pytest.raises(PromptError, match=match):
        load_prompt("p_v1", prompt_dir=tmp_path)


def test_escaped_braces_are_allowed_and_unescaped_on_render(tmp_path):
    """The structured prompt needs a literal JSON example."""
    write(tmp_path, HEADER + 'Shape: {{"a": "b"}}\n\n{segment_text}\n')
    p = load_prompt("p_v1", prompt_dir=tmp_path)
    out = p.render("SEG")
    assert '{"a": "b"}' in out and "SEG" in out


def test_a_brace_inside_the_segment_is_not_a_placeholder(tmp_path):
    write(tmp_path, HEADER + BODY)
    out = load_prompt("p_v1", prompt_dir=tmp_path).render("{segment_text} {question}")
    assert out.count("{question}") == 1, "segment content was re-interpolated"


# -------------------------------------------------------- shipped prompt set
def test_shipped_prompts_all_load():
    m = prompt_manifest()
    assert set(m) == {"summary_v1", "structured_v1", "structured_procedural_v1",
                      "semantic_type_v1"}
    for name, info in m.items():
        assert info["version"].startswith(f"{name}@")
        assert len(info["sha256"]) == 64


def test_shipped_prompt_versions_are_all_distinct():
    versions = {p.version for p in all_prompts().values()}
    assert len(versions) == 4


def test_prompt_dir_resolves_into_the_repo():
    assert PROMPT_DIR.is_dir(), f"{PROMPT_DIR} not found"
    assert PROMPT_DIR.name == "prompts" and PROMPT_DIR.parent.name == "configs"


def test_no_prompt_text_is_duplicated_in_python_source():
    """One definition per prompt. A second copy in code is how they drift.

    Checks a distinctive line of each shipped prompt does not also appear in
    any .py file under src/.
    """
    src = Path(__file__).resolve().parents[1] / "src"
    py = "\n".join(p.read_text() for p in src.rglob("*.py"))
    for name, prompt in all_prompts().items():
        lines = [ln.strip() for ln in prompt.text.split("\n")
                 if len(ln.strip()) > 40 and "{" not in ln]
        assert lines, f"{name}: no line long enough to test with"
        assert lines[0] not in py, f"{name}'s text is duplicated in Python source"

"""Tests for WITH/WITHOUT cell construction.

Each test states the defect it would catch. Several deliberately plant the
defect first, because a check only ever run on good input detects nothing
known.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p1mem.cells import MemoryUnit, build_cell_pair, select_filler


def _units(n, prefix="f"):
    return [
        MemoryUnit(f"{prefix}{i}", f"traj{i}:0-0", f"filler body {i}", 50, "web")
        for i in range(n)
    ]


TARGET = MemoryUnit("tgt", "013696c4:0-0", "UNIQUE-TARGET-BODY", 100, "web")


def test_arms_differ_only_in_the_target():
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    wi = b if wo is a else a
    assert "UNIQUE-TARGET-BODY" in wi["messages"][1]["content"]
    assert "UNIQUE-TARGET-BODY" not in wo["messages"][1]["content"]
    # every filler body survives in BOTH arms: removal must be local
    for i in range(4):
        assert f"filler body {i}" in wi["messages"][1]["content"]
        assert f"filler body {i}" in wo["messages"][1]["content"]
    assert wi["messages"][0] == wo["messages"][0]  # identical system prompt


def test_without_arm_is_not_length_padded():
    """A padded WITHOUT arm would confound the contrast with context length."""
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    wi = b if wo is a else a
    assert wo["messages"][1]["content"].count("--- Note") == 4
    assert wi["messages"][1]["content"].count("--- Note") == 5


def test_replicate_id_is_in_the_cache_key_of_both_arms():
    """A1.4: without this the WITHOUT arm is served from cache, its spread is
    exactly zero, the empty floor collapses, and every delta-U clears it."""
    for rep in (0, 1):
        for c in build_cell_pair(
            target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=rep
        ):
            assert c["key_fields"]["replicate_id"] == rep
    r0 = build_cell_pair(target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0)
    r1 = build_cell_pair(target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=1)
    assert r0[0]["key_fields"] != r1[0]["key_fields"]


def test_seeded_position_is_reproducible_but_varies():
    """Position must be stable for a given seed (reproducibility) and must not
    be constant across cells (or 'memory present' confounds with position)."""
    p1 = build_cell_pair(target=TARGET, filler=_units(6), task_id="t1", question="Q", replicate_id=0)
    p2 = build_cell_pair(target=TARGET, filler=_units(6), task_id="t1", question="Q", replicate_id=0)
    assert p1[1]["target_position"] == p2[1]["target_position"]
    seen = {
        build_cell_pair(
            target=TARGET, filler=_units(6), task_id=f"t{i}", question="Q", replicate_id=0
        )[1]["target_position"]
        for i in range(25)
    }
    assert len(seen) > 1, "target position is constant -- position is confounded"


def test_filler_is_identical_across_memories_within_a_task():
    """delta-U is only comparable across memories if they share a context.

    Stated against the no-exclusion BASELINE, not by comparing two exclusions
    to each other. Comparing two exclusions is a weak check: under the old
    filter-then-shuffle defect BOTH draws shifted identically, so they matched
    and the test passed while the property was broken. That is exactly how I
    first failed to reproduce the defect Sub-agent G reported.

    Each draw is also compared at equal length: excluding a drawn unit
    legitimately backfills a different Kth element, so a K-vs-K comparison of
    two different exclusions is not well posed.
    """
    pool = _units(30)
    base = [u.memory_id for u in select_filler(pool, exclude_ids=set(), k=5,
                                               task_id="same-task")]
    for excluded in ("f0", "f1"):
        got = [u.memory_id for u in select_filler(pool, exclude_ids={excluded},
                                                  k=5, task_id="same-task")]
        survivors = [x for x in base if x != excluded]
        assert got[: len(survivors)] == survivors, (
            f"excluding {excluded} perturbed the shared filler: {base} -> {got}")


def test_filler_excludes_the_target():
    pool = _units(30)
    got = select_filler(pool, exclude_ids={"f3"}, k=10, task_id="t")
    assert "f3" not in {u.memory_id for u in got}


def test_planted_defect_target_leaking_into_without_arm_is_caught():
    """Positive control: corrupt an arm the way the real defect would look and
    confirm the assertion in test_arms_differ_only_in_the_target would fire."""
    a, b = build_cell_pair(
        target=TARGET, filler=_units(4), task_id="t1", question="Q?", replicate_id=0
    )
    wo = a if a["key_fields"]["arm"] == "without" else b
    corrupted = wo["messages"][1]["content"] + "\nUNIQUE-TARGET-BODY"
    assert "UNIQUE-TARGET-BODY" in corrupted  # the check CAN fire


def test_excluding_a_non_drawn_memory_does_not_change_the_filler():
    """Regression: the defect that would have corrupted F_empty.

    ``random.shuffle`` consumes draws proportional to sequence LENGTH, so the
    original implementation (filter-then-shuffle) re-randomised the entire
    permutation whenever any element was removed -- including elements that
    would never have been drawn. Measured before the fix: 25 of 25 exclusions
    of a non-drawn memory changed the selected filler.

    If this regresses, the WITHOUT arm differs between memories within a task,
    its spread confounds filler composition with execution noise, and F_empty
    measures the wrong thing.

    Found by Sub-agent G in Master-authored code.
    """
    pool = _units(30, prefix="m")
    base = [u.memory_id for u in select_filler(pool, exclude_ids=set(), k=5, task_id="T")]
    assert len(base) == 5
    checked = 0
    for u in pool:
        if u.memory_id in base:
            continue
        checked += 1
        got = [x.memory_id for x in select_filler(
            pool, exclude_ids={u.memory_id}, k=5, task_id="T")]
        assert got == base, (
            f"excluding non-drawn {u.memory_id} changed the filler: {base} -> {got}")
    assert checked >= 20, "test is vacuous: too few non-drawn memories exercised"


def test_excluding_a_drawn_memory_removes_only_that_unit():
    """The one legitimate effect of exclusion: drop it, backfill, keep order."""
    pool = _units(30, prefix="m")
    base = [u.memory_id for u in select_filler(pool, exclude_ids=set(), k=5, task_id="T")]
    got = [u.memory_id for u in select_filler(
        pool, exclude_ids={base[2]}, k=5, task_id="T")]
    assert base[2] not in got
    assert [x for x in base if x != base[2]] == got[:4], "surviving order must be stable"


def test_replicates_are_byte_identical_requests():
    """Replicates must differ ONLY in sampling -- so the prompt must not move.

    PREREG section 2 defines F_exec as outcome variation "with everything else
    fixed". The original seeded target position with ``replicate_id``, so each
    replicate was a DIFFERENT prompt and the replicate spread measured a
    position effect, not execution noise. That spread was then read as
    endpoint nondeterminism at temperature 0.

    Planting the defect to prove this test can fail: passing ``replicate_id``
    into ``build_context``'s ``seed_parts`` makes positions vary, and the
    assertion below catches it.
    """
    filler = _units(6)
    seen_pos, seen_prompt = set(), set()
    for rep in range(6):
        arms = build_cell_pair(target=TARGET, filler=filler, task_id="t1",
                               question="Q?", replicate_id=rep)
        wi = next(c for c in arms if c["key_fields"]["arm"] == "with")
        seen_pos.add(wi["target_position"])
        seen_prompt.add(wi["messages"][1]["content"])
    assert len(seen_pos) == 1, (
        f"target position varied across replicates: {sorted(seen_pos)}. "
        f"Replicates would then measure a position effect, not execution noise.")
    assert len(seen_prompt) == 1, "replicate prompts are not byte-identical"


def test_position_still_varies_across_cells():
    """The counterpart: fixing position per replicate must NOT freeze it globally.

    Without this, a builder that simply hard-coded position 0 would pass the
    test above while silently confounding "memory present" with "memory first".
    """
    filler = _units(6)
    positions = set()
    for i in range(24):
        tgt = MemoryUnit(f"m{i}", f"tr{i}:0-0", "BODY", 100, "web")
        arms = build_cell_pair(target=tgt, filler=filler, task_id=f"t{i}",
                               question="Q?", replicate_id=0)
        wi = next(c for c in arms if c["key_fields"]["arm"] == "with")
        positions.add(wi["target_position"])
    assert len(positions) > 1, (
        f"target position is constant at {positions} across 24 distinct cells; "
        f"position would be perfectly confounded with the intervention")


# ---------------------------------------------------------------------------
# The OFFICIAL benchmark reader prompts (H1)
# ---------------------------------------------------------------------------
import hashlib as _hashlib  # noqa: E402
import textwrap as _textwrap  # noqa: E402

import pytest as _pytest  # noqa: E402

from p1mem.cells import (  # noqa: E402
    OFFICIAL_DOMAIN_SYSTEM_PROMPTS,
    OFFICIAL_PROMPT_SHA256,
    assert_official_prompts_verbatim,
    official_system_prompt,
)

_HARNESS = Path("/tmp/lmev2/harness.py")


def test_official_prompts_have_both_domains_and_they_differ():
    assert set(OFFICIAL_DOMAIN_SYSTEM_PROMPTS) == {"web", "enterprise"}
    # If these ever coincided, selecting by domain would be untestable and a
    # wrong-domain bug would be invisible.
    assert OFFICIAL_DOMAIN_SYSTEM_PROMPTS["web"] != OFFICIAL_DOMAIN_SYSTEM_PROMPTS[
        "enterprise"]


def test_official_prompt_shas_match_the_strings():
    for dom, text in OFFICIAL_DOMAIN_SYSTEM_PROMPTS.items():
        assert _hashlib.sha256(text.encode()).hexdigest() == OFFICIAL_PROMPT_SHA256[dom]


def test_official_prompt_forbids_guessing_and_mandates_unknown():
    """The abstention clause is the whole reason this arm exists."""
    for text in OFFICIAL_DOMAIN_SYSTEM_PROMPTS.values():
        assert "\\boxed{UNKNOWN}" in text
        assert "Do not guess." in text
        assert "Never attempt to guess an answer if you are not sure." in text


def test_official_prompt_preserves_the_upstream_escaping_bug():
    """Upstream's literal is not raw, so the trailing \\boxed{} is \\x08 + 'oxed{}'.

    Preserved deliberately: it is the byte sequence the published benchmark
    sends. A "repair" would silently make our arm a different condition, so
    this test fails if anyone fixes it.
    """
    for text in OFFICIAL_DOMAIN_SYSTEM_PROMPTS.values():
        assert "\x08oxed{}" in text, "the upstream \\x08 was 'fixed'; see cells.py"


def test_official_system_prompt_raises_on_unknown_domain():
    # A default here would answer web questions with the enterprise prompt.
    with _pytest.raises(KeyError):
        official_system_prompt("webarena")


@_pytest.mark.skipif(not _HARNESS.exists(), reason="benchmark harness not on disk")
def test_vendored_prompts_are_verbatim_against_the_real_harness():
    assert assert_official_prompts_verbatim(_HARNESS) == OFFICIAL_PROMPT_SHA256


def test_verbatim_checker_fires_on_a_planted_drift(tmp_path):
    """Prove the checker can FAIL -- corrupt a copy in the shape we fear.

    A verifier only ever run on good data has not been shown to detect
    anything. Three plants: a reworded prompt, the "repaired" \\x08, and a
    missing domain.
    """
    real = _HARNESS.read_text() if _HARNESS.exists() else None
    if real is None:
        base = (
            "DOMAIN_SYSTEM_PROMPTS = {\n"
            f"    'web': {OFFICIAL_DOMAIN_SYSTEM_PROMPTS['web']!r},\n"
            f"    'enterprise': {OFFICIAL_DOMAIN_SYSTEM_PROMPTS['enterprise']!r},\n"
            "}\n"
        )
    else:
        base = real

    good = tmp_path / "harness_good.py"
    good.write_text(base)
    assert assert_official_prompts_verbatim(good) == OFFICIAL_PROMPT_SHA256

    plants = {
        # a paraphrase -- the exact failure the task forbids
        "reworded": lambda s: s.replace("Do not guess.", "Try not to guess."),
        # A well-meaning repair of the upstream escaping bug. NOTE the plant
        # must target the SOURCE spelling (a single backslash before "boxed"),
        # not the parsed \x08: the first version of this plant matched nothing
        # and the test SKIPPED rather than failing -- a plant that changes
        # nothing proves nothing.
        "repaired_backspace": lambda s: s.replace(
            "\\boxed{} explaining", "\\\\boxed{} explaining"),
        # one domain silently dropped
        "domain_dropped": lambda s: s.replace(
            "    \"enterprise\": (", "    \"enterprise_DISABLED\": ("),
    }
    for name, mutate in plants.items():
        bad = tmp_path / f"harness_{name}.py"
        mutated = mutate(base)
        if mutated == base:
            _pytest.skip(f"plant {name} did not change the file; cannot test it")
        bad.write_text(mutated)
        with _pytest.raises((RuntimeError, SyntaxError, ValueError)):
            assert_official_prompts_verbatim(bad)


def test_verbatim_checker_raises_on_a_missing_file(tmp_path):
    # Absence must not read as success.
    with _pytest.raises(FileNotFoundError):
        assert_official_prompts_verbatim(tmp_path / "nope.py")

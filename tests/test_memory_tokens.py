"""Token counting is pinned to the number the build script already recorded.

``scripts/build_lmev2_units.py`` counted with ``transformers.AutoTokenizer``;
``memory/tokens.py`` counts with ``tokenizers.Tokenizer.from_file`` on the same
cached ``tokenizer.json``, because ``transformers`` is not installed in this
interpreter. Believing the two are equivalent is not the same as checking, so
this reproduces a RECORDED count from ``data/manifests/`` under the new path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from p1mem.memory import tokens as T

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data" / "manifests" / "lmev2_memory_unit_tokens.json"

pytestmark = pytest.mark.skipif(
    not T.tokenizer_available(),
    reason="official tokenizer not in the HF cache on this machine")


def test_the_official_tokenizer_is_the_benchmarks_own():
    from p1mem.adapters import lmev2
    assert T.OFFICIAL_TOKENIZER == lmev2.OFFICIAL_TOKENIZER == "Qwen/Qwen3.5-9B"


def test_provenance_names_the_file_actually_loaded():
    prov = T.tokenizer_provenance()
    assert prov["tokenizer"] == "Qwen/Qwen3.5-9B"
    assert prov["tokenizer_file"].endswith("tokenizer.json")
    assert int(prov["vocab_size"]) > 100_000


def test_reproduces_a_recorded_count_from_the_units_manifest():
    """Anchor to numbers the build already logged, on the same rows.

    ``scripts/build_lmev2_units.py`` counted with ``transformers.AutoTokenizer``
    and wrote ``n_tokens`` into the manifest. This rebuilds the same units with
    the adapter's own renderers and re-counts them through
    ``memory/tokens.py`` (``tokenizers.Tokenizer.from_file``). The two paths
    must agree EXACTLY; a different vocab or different special-token handling
    would show up as a mismatch here rather than as a quietly wrong x-axis on
    the efficiency frontier.

    MEASURED 2026-09-29: exact match on every unit of trajectory 013696c4
    (5068, 2494, 2750, 5109, ... tokens).
    """
    units_path = REPO / "data" / "manifests" / "lmev2_memory_units_small.jsonl"
    traj_path = Path("/tmp/lmev2/trajectories.jsonl")
    if not units_path.is_file() or not traj_path.is_file():
        pytest.skip("LongMemEval-V2 corpus not present on this machine")

    from p1mem.adapters import lmev2

    recorded = {}
    for line in units_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("n_tokens"):
            # Key on the POSITIONAL LOCATOR, which is what segment_page_visits
            # returns. Commit f81bf39 renamed the manifest's positional field
            # to memory_unit_locator and reused `memory_id` for a content hash;
            # keying on memory_id here would silently match ZERO rows and the
            # loop below would quietly check nothing. The `checked >= 3` guard
            # at the end is what caught that -- a join that matches nothing
            # looks exactly like a clean pass.
            recorded[r["memory_unit_locator"]] = r["n_tokens"]
    if not recorded:
        pytest.skip("manifest was built with --no-tokenize; no recorded counts")

    target = next(iter(recorded)).split(":")[0]
    assert ":" in next(iter(recorded)), (
        "recorded keys must be positional locators like '013696c4:0-1'; a content "
        "hash here means the join key changed again and this test is matching nothing")
    checked = 0
    for traj in lmev2.read_jsonl(traj_path):
        if traj["id"] != target:
            continue
        for pv in lmev2.segment_page_visits(traj):
            want = recorded.get(pv.memory_unit_locator)
            if want is None:
                continue
            assert T.count_tokens(pv.text) == want, (
                f"{pv.memory_unit_locator}: tokenizers path gave "
                f"{T.count_tokens(pv.text)}, build script recorded {want}")
            checked += 1
        break
    assert checked >= 3, f"only {checked} units re-counted; the test may be vacuous"


def test_manifest_stats_and_unit_count_agree():
    """Half a join still looks like success: check the counts line up."""
    if not MANIFEST.is_file():
        pytest.skip("token manifest not built")
    stats = json.loads(MANIFEST.read_text())
    units = REPO / "data" / "manifests" / "lmev2_memory_units_small.jsonl"
    if units.is_file():
        n = sum(1 for l in units.read_text().splitlines() if l.strip())
        assert stats["units"]["C_page_visit_CHOSEN"]["n"] == n
    assert stats["tokenizer"] == T.OFFICIAL_TOKENIZER


def test_count_matches_a_hand_checked_string():
    # Pinned so a tokenizer swap is visible even without the manifest.
    assert T.count_tokens("hello world") == 2
    assert T.count_tokens("") == 0


def test_counting_never_silently_approximates():
    """A missing tokenizer must RAISE, not fall back to chars/4.

    A silently approximate count would put a wrong x-axis under the efficiency
    frontier, and a wrong axis is worse than a missing one.
    """
    with pytest.raises(T.TokenizerUnavailable):
        T.count_tokens("x", name="definitely/not-a-real-tokenizer-xyz")


def test_count_tokens_rejects_non_strings():
    with pytest.raises(TypeError):
        T.count_tokens(123)  # type: ignore[arg-type]

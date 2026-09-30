

# ---------------------------------------------------------------- embargo
# A licence ruling that lives only in a markdown file cannot fail a release.
# These tests exist so the ruling has to be repealed in code, with a failing
# test as the receipt, rather than quietly forgotten at export time.

def test_embargo_blocks_swebench_text():
    from p1mem.schema import assert_content_redistributable
    import pytest as _pt
    with _pt.raises(ValueError, match="content-embargoed"):
        assert_content_redistributable(
            [{"benchmark": "swebench_verified", "task_id": "t",
              "output_with_memory": "issue text"}])


def test_embargo_allows_swebench_metrics_only():
    from p1mem.schema import assert_content_redistributable
    assert_content_redistributable(
        [{"benchmark": "swebench_verified", "task_id": "t",
          "delta_utility": 1.0, "memory_text": None}])


def test_embargo_does_not_over_block_permissive_benchmarks():
    """The guard must not be a blanket refusal: LongMemEval-V2 is Apache-2.0."""
    from p1mem.schema import assert_content_redistributable
    assert_content_redistributable(
        [{"benchmark": "lmev2", "memory_text": "redistributable"}])


def test_every_embargoed_benchmark_states_a_reason():
    from p1mem.schema import CONTENT_EMBARGOED_BENCHMARKS
    for name, why in CONTENT_EMBARGOED_BENCHMARKS.items():
        assert len(why) > 40, f"{name} has no stated reason"
        assert "docs/" in why or "ShareAlike" in why, (
            f"{name}'s reason cites no source")

"""Verbatim vendored third-party scoring code. DO NOT EDIT THESE FILES.

`lmev2_qa_eval_metrics.py` is copied byte-for-byte from the official
LongMemEval-V2 repository so that our scoring is the benchmark authors'
scoring and not a reimplementation from the function name.

    source : https://github.com/xiaowu0162/LongMemEval-V2
    path   : evaluation/qa_eval_metrics.py
    commit : 2cc8c540bdb87fe6761629b585e727e1c4704520  (2026-08-09)
    license: Apache-2.0
    sha256 : f8ba659e237c4282a07a92538090ea500ce8483820b390b1d19af187c01417ac

Provenance check that this commit corresponds to the /tmp/lmev2 data snapshot:
`evaluation/harness.py` at this commit is byte-identical to the `harness.py`
shipped in the snapshot, sha256
93fe5855a74ad46d7e8b489cebac24de38a9b30ba7ec1de2dd8708bd4aeebdb6.

`p1mem.adapters.lmev2.verify_vendored_scorer()` re-checks the sha256 at runtime.
"""

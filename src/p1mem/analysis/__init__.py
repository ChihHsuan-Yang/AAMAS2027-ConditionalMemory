"""P1 analysis package (Sub-agent D).

Every estimator here implements a numbered clause of
``docs/ANALYSIS_PREREGISTRATION.md``, which was fixed before any data existed. Where a
clause is ambiguous the ambiguity is resolved in the open -- in a docstring, in a flag on
the returned ``Estimate``, and in ``subagent_D_report.md`` -- never by quietly choosing
the better-behaved reading.

    common.py         row admission, identity guards, bootstrap, Wilson, BH
    noise.py          D1 / section 2   F_exec, F_empty, F_judge, reference floor
    labels.py         D2 / sections 4,5  robust labels, sign flips, naive comparator
    decomposition.py  D3 / section 6   mixed-effects + method-of-moments fallback
    efficiency.py     D4 / section 10  seven cost families + derived metrics
    figures.py        D5               Figures 2, 3, 4
    synthetic.py      test instrument: rows from a KNOWN generative model
"""
from __future__ import annotations

__all__ = [
    "common", "noise", "labels", "decomposition", "efficiency", "figures", "synthetic",
]

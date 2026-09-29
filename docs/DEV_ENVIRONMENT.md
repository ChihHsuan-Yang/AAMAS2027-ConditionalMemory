# Development Environment

## 🔴 Use Python 3.10+ — the system `python3` is 3.9 and will mislead you

```bash
/Users/bellayang/miniconda3/bin/python3 -m pytest tests -q     # 3.13 — correct
python3 -m pytest tests -q                                      # 3.9  — WRONG
```

**Why this matters more than a version note.** The vendored LongMemEval-V2 scorer uses
PEP 604 syntax (`text: str | None`), which is a **TypeError at import time** on 3.9:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

Under 3.9 that aborts pytest *collection*, so **a healthy suite looks broken** — the
failure appears to be in our tests rather than in the interpreter choice. Verified by the
Master Agent: import fails on `/usr/bin/python3`, succeeds on 3.13.

**Current state, verified 2026-09-29:** `115 passed` under 3.13.

The vendored file is the **official Apache-2.0 scorer, byte-verified against upstream**.
Do not "fix" its syntax to satisfy 3.9 — editing a vendored scorer silently changes our
measurements. Change the interpreter, not the scorer.

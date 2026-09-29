# results/

**Raw endpoint outputs are not committed.** Only `ledgers/` is tracked. See `.gitignore`.

## Layout

```text
results/
  ledgers/          # committed: aggregate ledgers, run manifests, analysis outputs
  runs/<run_id>/    # NOT committed: raw per-cell outputs, caches
    manifest.json   # resolved model id, endpoint, seeds, config hash, code commit
    cells.jsonl     # one record per (memory, task, arm, seed) — shared schema
    _attempts/      # quarantined diagnostic runs, EXCLUDED from any aggregate
```

## Rules

1. **Store full output text**, not a digest. A stored hash blocks every later re-scoring
   under a corrected verifier.
2. **Record the RESOLVED model id** the server returned, not the alias requested.
3. **Atomic writes only.**
4. Diagnostic and aborted runs go to `_attempts/` and never enter an aggregate.
5. Paper runs write to a separate root and are never overwritten.
6. An exit status of 0 is not evidence of success — verify artifacts exist and are complete.

## Current status

Empty. No runs have been executed.

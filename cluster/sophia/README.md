# Running the reviewer experiments on ALCF Sophia

| Priority | Run | Script | Endpoint calls | What it answers |
|---|---|---|---|---|
| 1 | `x1_position` | `scripts/x1_position_session.py` | 1,710 reader (Metis) | headline contrast in a new session with randomized position; label stability |
| 2 | `x2_fixedctx` | `scripts/x2_fixed_context.py` | 2,770 reader (Metis) | Raw vs compressed memory at a fixed total context |
| 3 | `x3_retrieval` | `scripts/x3_retrieval_baseline.py` | embeddings only (Sophia) | BM25 / chunked dense retrieval vs the screen's ground truth |

X2 waits for X1 (both share the Metis reader's rate limit); X3 runs in parallel.
Every run is resumable (response cache) and finishes by writing `runs/<run>/summary.json`.

Steps: `configure.sh` -> `setup.sh` -> `interactive.sh` (dry runs) -> `submit.sh` -> `status.sh`.
Results land in `/lus/eagle/projects/<allocation>/<user>/p1mem/runs/`.

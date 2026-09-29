"""Benchmark adapters for P1 (task-conditional memory utility).

Each adapter exposes the same three concepts required by the frozen
scientific object:

    DeltaU(m, t) = Reward(t | m available) - Reward(t | m absent)

1. a MEMORY UNIT   -- a span written during a PAST episode,
                      chosen WITHOUT any reference to a future task;
2. a FUTURE-TASK UNIT -- a later, different task with a deterministic reward;
3. a PAIRING RULE  -- deterministic and seeded, so the (m, t) cell set is
                      reproducible from the seed alone.

No adapter may ever let the memory writer see the future task.
"""

__all__ = ["lmev2", "lmev1", "leakage"]

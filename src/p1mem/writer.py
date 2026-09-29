"""Append-only writer for conditional-memory result cells (P1-043).

The single sanctioned way to put a row on disk. It validates BEFORE writing, so a
malformed row never reaches the ledger and the ledger never needs repairing -- which
matters because the ledger is append-only and a bad row cannot be edited out, only
superseded.

    w = CellWriter("results/cells/pilot.jsonl")
    w.write(benchmark="longmemeval_v1", ...)     # raises on a malformed row
    w.close()

``strict=False`` quarantines rejected rows to ``<path>.rejected.jsonl`` with their issues
attached instead of raising -- for a long run where one bad cell should not kill the job.
A quarantined row is still never written to the ledger.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from . import schema as S
from . import validate as V


class RowRejected(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("row rejected by the validator:\n" +
                         "\n".join("  " + str(i) for i in issues))


class CellWriter:
    def __init__(self, path: str | Path, *, strict: bool = True):
        self.path = Path(path)
        self.strict = strict
        self.rejected_path = self.path.with_suffix(self.path.suffix + ".rejected.jsonl")
        self.n_written = 0
        self.n_rejected = 0

    def build(self, **values: Any) -> dict[str, Any]:
        return S.new_row(**values)

    def write(self, **values: Any) -> dict[str, Any] | None:
        return self.write_row(self.build(**values))

    def write_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        issues = [i for i in V.validate_row(row) if i.severity == V.SEVERITY_ERROR]
        if issues:
            self.n_rejected += 1
            if self.strict:
                raise RowRejected(issues)
            S.append_jsonl_atomic(self.rejected_path, [{
                "row": row,
                "issues": [{"code": i.code, "field": i.field, "message": i.message}
                           for i in issues],
                "rejected_at_utc": S.utc_now(),
            }])
            return None
        S.append_jsonl_atomic(self.path, [row])
        self.n_written += 1
        return row

    def write_many(self, rows: Iterable[dict[str, Any]]) -> int:
        return sum(1 for r in rows if self.write_row(r) is not None)

    def close(self) -> dict[str, int]:
        return {"written": self.n_written, "rejected": self.n_rejected}

    def __enter__(self): return self
    def __exit__(self, *exc): self.close(); return False

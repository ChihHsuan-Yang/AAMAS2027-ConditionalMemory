"""Resumable, idempotent, cache-aware cell runner.

A "cell" is one endpoint call identified by its cache key: one
(memory, future task, arm, replicate) combination under a fixed serving
configuration. The runner's contract:

* **Idempotent** -- a cell already in the response cache is never re-issued.
  Resuming is therefore just running again; there is no separate resume path
  that could diverge from the first-run path.
* **Checkpointed** -- progress is appended to a JSONL ledger after every cell,
  flushed and fsynced, so a laptop sleeping or a killed process loses at most
  the in-flight calls.
* **Concurrency-bounded** -- at the measured safe ceiling, enforced by the
  client's semaphore rather than merely recorded in a config field.
* **Fails loudly** -- a truncated response or a model-id mismatch aborts the
  cell and is recorded as an error row. It is never written as a result.

Deliberately NOT here: any notion of "partial success". A cell either has a
usable response or it has an error row.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .cache import ResponseCache, make_key
from .vendor.rcc_schema import sha256_text
from .client import ClientError, P1Client
from .vendor.rcc_schema import utc_now


@dataclass
class Cell:
    """One unit of work. ``key_fields`` are the cache-key fields minus the
    ones the client fills in (model_id, cluster, decoding_params)."""

    cell_id: str
    messages: list[dict[str, str]]
    key_fields: dict[str, Any]


class RunLedger:
    """Append-only, fsynced progress ledger."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.done: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)          # strict on purpose
                if row.get("status") == "ok":
                    self.done.add(row["cell_id"])

    def append(self, row: dict[str, Any]) -> None:
        with self._lock:
            with open(self.path, "a") as fh:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            if row.get("status") == "ok":
                self.done.add(row["cell_id"])


class Runner:
    def __init__(self, *, client: P1Client, ledger: RunLedger,
                 max_workers: int = 16, max_tokens: int = 512,
                 temperature: float = 0.0, reasoning_effort: str | None = "low"):
        self.client = client
        self.ledger = ledger
        self.max_workers = max_workers
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self._stop = threading.Event()

    def install_signal_handlers(self) -> None:
        """Ctrl-C finishes in-flight cells and stops cleanly, so the ledger is
        never left describing work that was abandoned mid-write."""
        def handle(signum, frame):  # noqa: ANN001, ARG001
            self._stop.set()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, handle)

    def pending(self, cells: Sequence[Cell]) -> list[Cell]:
        """Cells not already completed. Checks the LEDGER and the CACHE:
        the cache is authoritative for whether a call must be made."""
        out = []
        for cell in cells:
            if cell.cell_id in self.ledger.done:
                continue
            if self.client.cache is not None:
                # context_sha256 must be derived here EXACTLY as P1Client.chat
                # derives it, from the same messages. If the two disagree, the
                # resume path looks up a key the run never writes, every cell
                # reads as pending, and a resumed run silently re-pays for
                # work already done.
                key = make_key(**{**cell.key_fields,
                                  "model_id": self.client.model,
                                  "cluster": self.client.cluster,
                                  "decoding_params": self._decoding(),
                                  "context_sha256": sha256_text(cell.messages)})
                if self.client.cache.contains(key):
                    # Cached but unledgered (e.g. killed between write and
                    # ledger append). Record it now; do not re-call.
                    self.ledger.append({"cell_id": cell.cell_id, "status": "ok",
                                        "source": "cache_backfill",
                                        "ts_utc": utc_now()})
                    continue
            out.append(cell)
        return out

    def _decoding(self) -> dict[str, Any]:
        d = {"temperature": self.temperature, "max_tokens": self.max_tokens}
        if self.reasoning_effort is not None:
            d["reasoning_effort"] = self.reasoning_effort
        return d

    def run(self, cells: Sequence[Cell],
            on_result: Callable[[Cell, str, Any], None] | None = None,
            ) -> dict[str, int]:
        todo = self.pending(cells)
        stats = {"total": len(cells), "skipped": len(cells) - len(todo),
                 "ok": 0, "error": 0, "stopped_early": 0}
        if not todo:
            return stats

        def work(cell: Cell) -> tuple[Cell, str | None, Any, str | None]:
            if self._stop.is_set():
                return cell, None, None, "stopped"
            try:
                content, rec = self.client.chat(
                    cell.messages, max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    reasoning_effort=self.reasoning_effort,
                    cache_key_fields=cell.key_fields)
                return cell, content, rec, None
            except ClientError as e:
                return cell, None, None, f"{type(e).__name__}: {e}"
            except BaseException as e:  # noqa: BLE001
                # An UNEXPECTED exception (a bug in transport, a KeyError in a
                # payload shape we have not seen) must not take the whole run
                # down and lose the cells still in flight. It is recorded as an
                # error row for this cell and the run continues; the ledger then
                # tells us exactly which cells to investigate.
                return cell, None, None, f"UNEXPECTED {type(e).__name__}: {e}"

        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(work, c) for c in todo]
            for fut in as_completed(futures):
                cell, content, rec, err = fut.result()
                if err == "stopped":
                    stats["stopped_early"] += 1
                    continue
                if err is not None:
                    stats["error"] += 1
                    self.ledger.append({"cell_id": cell.cell_id, "status": "error",
                                        "error": err[:500], "ts_utc": utc_now()})
                    continue
                stats["ok"] += 1
                self.ledger.append({
                    "cell_id": cell.cell_id, "status": "ok",
                    "ts_utc": utc_now(),
                    **({"call": rec.to_dict()} if rec is not None else {}),
                })
                if on_result is not None:
                    on_result(cell, content or "", rec)
        stats["wall_s"] = round(time.monotonic() - t0, 2)
        return stats


def run_cells(cells: Iterable[Cell], *, cluster: str, model: str,
              cache_path: str | Path, ledger_path: str | Path,
              max_workers: int = 16, **kw) -> dict[str, int]:
    """Convenience entry point used by scripts/run_cells.py."""
    cache = ResponseCache(cache_path)
    client = P1Client(cluster=cluster, model=model, cache=cache,
                      max_concurrency=max_workers)
    runner = Runner(client=client, ledger=RunLedger(ledger_path),
                    max_workers=max_workers, **kw)
    runner.install_signal_handlers()
    return runner.run(list(cells))

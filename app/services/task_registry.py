"""In-memory registry for fire-and-forget background threads.

FastAPI sync handlers routinely spawn daemon threads for indexing,
conversion, re-indexing, etc.  Without a shared registry, these operations
are invisible once started: if they fail, users only find out via server
logs.

``TaskRegistry`` gives every tracked job a stable id, a lifecycle
(``pending`` → ``running`` → ``succeeded``/``failed``/``cancelled``),
timestamps, and an optional human-readable message.  The
:func:`run_tracked` helper wraps a callable in a thread that automatically
moves the task through the lifecycle and records any exception.

The registry is bounded (newest N kept) and thread-safe.  It is exposed
through ``app.state.task_registry`` and surfaced via GET ``/tasks``.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskRecord:
    """Status entry for a tracked background operation."""

    id: str
    kind: str
    status: str = "pending"  # pending | running | succeeded | failed | cancelled
    label: str = ""
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class TaskRegistry:
    """Thread-safe, bounded registry of background task statuses."""

    def __init__(self, capacity: int = 200):
        self._capacity = capacity
        self._tasks: OrderedDict[str, TaskRecord] = OrderedDict()
        self._lock = threading.Lock()

    def create(self, kind: str, label: str = "", **meta) -> TaskRecord:
        """Register a new pending task and return its record."""
        record = TaskRecord(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            label=label,
            meta=dict(meta),
        )
        with self._lock:
            self._tasks[record.id] = record
            # Drop oldest when over capacity.
            while len(self._tasks) > self._capacity:
                self._tasks.popitem(last=False)
        return record

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is not None:
                t.status = "running"
                t.started_at = time.time()

    def mark_succeeded(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is not None:
                t.status = "succeeded"
                t.finished_at = time.time()

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is not None:
                t.status = "failed"
                t.finished_at = time.time()
                t.error = error[:500]

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            t = self._tasks.get(task_id)
            return t

    def list(self, kind: Optional[str] = None, limit: int = 50) -> list[TaskRecord]:
        """Return newest-first task records, optionally filtered by kind."""
        with self._lock:
            records = list(self._tasks.values())
        records.reverse()
        if kind is not None:
            records = [r for r in records if r.kind == kind]
        return records[:limit]


# Process-wide default registry used by ``run_tracked`` when no explicit
# registry is provided.  Lifespan wires this onto ``app.state.task_registry``.
_default_registry = TaskRegistry()


def get_default_registry() -> TaskRegistry:
    return _default_registry


def run_tracked(
    kind: str,
    target: Callable[[], None],
    *,
    label: str = "",
    registry: Optional[TaskRegistry] = None,
    daemon: bool = True,
) -> TaskRecord:
    """Run *target* in a daemon thread with status tracking.

    Returns the created :class:`TaskRecord` immediately; the caller can use
    ``record.id`` to poll status.  Any exception from *target* is recorded
    on the task as a failure (also logged with ``exc_info=True``).
    """
    reg = registry or _default_registry
    record = reg.create(kind=kind, label=label)

    def _run():
        reg.mark_running(record.id)
        try:
            target()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Background task %s (%s) failed: %s",
                kind, record.id, exc, exc_info=True,
            )
            reg.mark_failed(record.id, repr(exc))
        else:
            reg.mark_succeeded(record.id)

    threading.Thread(target=_run, daemon=daemon).start()
    return record

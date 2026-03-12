"""Simple in-process event bus for pushing index events to SSE clients."""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IndexEvent:
    """A single index lifecycle event."""
    type: str          # "indexed", "deleted", "error", "indexing"
    path: str
    filename: str = ""
    chunks: int = 0
    error: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "path": self.path,
            "filename": self.filename,
            "chunks": self.chunks,
            "error": self.error,
            "ts": self.ts,
        }


class IndexEventBus:
    """Fan-out event bus: watcher publishes, SSE clients subscribe."""

    def __init__(self):
        self._subscribers: list[queue.Queue[IndexEvent | None]] = []
        self._lock = threading.Lock()

    def publish(self, event: IndexEvent):
        """Send an event to all active subscribers."""
        with self._lock:
            dead: list[queue.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    _MAX_SUBSCRIBERS = 50

    def subscribe(self) -> queue.Queue[IndexEvent | None]:
        """Create a new subscriber queue. Returns a Queue that yields events.

        Raises RuntimeError if the subscriber limit is reached.
        """
        q: queue.Queue[IndexEvent | None] = queue.Queue(maxsize=256)
        with self._lock:
            if len(self._subscribers) >= self._MAX_SUBSCRIBERS:
                raise RuntimeError("Too many SSE subscribers")
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """Remove a subscriber queue."""
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass


# Process-scoped singleton — used by the file watcher (publisher) and
# SSE /index/events endpoint (subscribers).  Intentionally outside DI
# because it must be shared between the watcher threads and request handlers.
event_bus = IndexEventBus()

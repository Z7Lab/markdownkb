"""In-memory ring buffer log handler for UI log viewing."""

import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass


@dataclass
class LogEntry:
    """Single log record for the ring buffer."""

    timestamp: float
    level: str
    logger: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class RingBufferHandler(logging.Handler):
    """Custom logging handler that stores entries in a bounded deque."""

    def __init__(self, capacity: int = 500):
        super().__init__()
        self._buffer: deque[LogEntry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, record: logging.LogRecord):
        entry = LogEntry(
            timestamp=record.created,
            level=record.levelname,
            logger=record.name,
            message=self.format(record),
        )
        with self._lock:
            self._buffer.append(entry)
            self._seq += 1

    def get_entries(self, since_seq: int = 0) -> tuple[list[dict], int]:
        """Return entries added after since_seq and the current sequence number.

        First call with since_seq=0 returns all buffered entries.
        Subsequent calls return only new entries since the last poll.
        """
        with self._lock:
            current_seq = self._seq
            count = current_seq - since_seq
            if count <= 0:
                return [], current_seq
            entries = list(self._buffer)
            if count < len(entries):
                entries = entries[-count:]
            return [e.to_dict() for e in entries], current_seq

    def clear(self):
        """Clear all buffered entries and reset sequence."""
        with self._lock:
            self._buffer.clear()
            self._seq = 0


# Module-level singleton
log_buffer = RingBufferHandler(capacity=500)
log_buffer.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
)

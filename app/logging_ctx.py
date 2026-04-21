"""Request-id context helpers for log correlation.

Kept in a lightweight standalone module so that scripts (``mcp_server.py``)
can install the log factory without importing the full FastAPI app graph.
"""

import contextvars
import logging

# ContextVar-backed request id — every log record produced while a request
# is being handled can attach this to correlate streamed chunks, background
# thread logs, and access-log entries for the same request.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def install_request_id_log_factory() -> None:
    """Install a LogRecord factory that stamps ``request_id`` on every record.

    Using a factory (instead of per-handler filters) guarantees the attribute
    exists for any formatter that references ``%(request_id)s``, even for
    handlers installed by third-party libraries.

    Idempotent: safe to call more than once.
    """
    base_factory = logging.getLogRecordFactory()

    def _factory(*args, **kwargs):
        record = base_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return record

    logging.setLogRecordFactory(_factory)

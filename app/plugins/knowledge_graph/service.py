"""Knowledge graph plugin service layer.

Holds the extraction-status object and the background-extraction worker,
extracted from ``router.py`` so the router only handles HTTP. Follows the
``lint``/``wiki_compile`` split noted by the backend reviewer.
"""

import logging
import threading

logger = logging.getLogger(__name__)


def new_extraction_status() -> dict:
    """Return a fresh extraction-status record.

    The router keeps one of these on module scope; wrapping construction in
    a function makes it easy for tests and future refactors to build
    isolated instances.
    """
    return {
        "running": False,
        "cancel": threading.Event(),
        "progress": 0.0,
        "message": "",
        "result": "",
        "files_done": 0,
        "files_total": 0,
    }


def run_extraction(status: dict, status_lock: threading.Lock, settings, kgdb, tracking) -> None:
    """Run KG extraction over all indexed files.

    This is the long-running worker previously inlined as ``_bg_extract``.
    It mutates ``status`` in-place under ``status_lock`` so the status
    endpoint can read progress without races.
    """
    from app.ingestion.parser import parse_and_chunk
    from app.services.kg_extraction import extract_from_chunks

    try:
        all_files = tracking.get_all_files()
        indexed = [f for f in all_files if f["status"] == "complete"]
        total = len(indexed)

        with status_lock:
            status["files_total"] = total
            status["files_done"] = 0

        for i, f in enumerate(indexed):
            if status["cancel"].is_set():
                with status_lock:
                    status["message"] = "Cancelled"
                    status["result"] = f"Cancelled after {i}/{total} files"
                return

            path = f["path"]
            try:
                chunks = parse_and_chunk(path, settings)
                extract_from_chunks(chunks, kgdb, settings)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("KG extraction failed for %s: %s", path, e)

            with status_lock:
                status["files_done"] = i + 1
                status["progress"] = (i + 1) / total if total else 1.0

        with status_lock:
            status["message"] = "Complete"
            status["result"] = f"Extracted from {total} files"
    finally:
        with status_lock:
            status["running"] = False

"""Knowledge graph endpoints — entity extraction, queries, and visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge_graph"])


def _get_kgdb(request: Request):
    """Get KnowledgeGraphDB from app.state (plugin-owned)."""
    kgdb = getattr(request.app.state, "kgdb", None)
    if kgdb is None:
        raise HTTPException(503, "Knowledge graph not initialized")
    return kgdb


# -- Background extraction --

_extraction_status: dict = {
    "running": False,
    "cancel": threading.Event(),
    "progress": 0.0,
    "message": "",
    "result": "",
    "files_done": 0,
    "files_total": 0,
}
_extraction_lock = threading.Lock()


def _bg_extract(settings, kgdb, tracking):
    """Run KG extraction over all indexed files in a background thread."""
    from app.ingestion.parser import parse_and_chunk
    from app.services.kg_extraction import extract_from_chunks

    try:
        all_files = tracking.get_all_files()
        indexed = [f for f in all_files if f["status"] == "complete"]
        total = len(indexed)

        with _extraction_lock:
            _extraction_status["files_total"] = total
            _extraction_status["files_done"] = 0

        for i, f in enumerate(indexed):
            if _extraction_status["cancel"].is_set():
                with _extraction_lock:
                    _extraction_status["message"] = "Cancelled"
                    _extraction_status["result"] = f"Cancelled after {i}/{total} files"
                break

            path = f["path"]
            source_root = f["source_root"]
            frac = i / max(total, 1)

            with _extraction_lock:
                _extraction_status["progress"] = frac
                _extraction_status["message"] = f"Extracting from {path.split('/')[-1]}..."
                _extraction_status["files_done"] = i

            try:
                chunks = parse_and_chunk(
                    path, source_root,
                    settings.chunk_size, settings.chunk_overlap,
                )
                if chunks:
                    kgdb.delete_by_source(path)
                    extract_from_chunks(chunks, path, kgdb, settings)
            except Exception:
                logger.warning("KG extraction failed for %s", path, exc_info=True)

        with _extraction_lock:
            stats = kgdb.get_stats()
            _extraction_status["progress"] = 1.0
            _extraction_status["files_done"] = total
            if not _extraction_status["cancel"].is_set():
                _extraction_status["message"] = "Done"
                _extraction_status["result"] = (
                    f"Extracted {stats['unique_entities']} entities, "
                    f"{stats['relationships']} relationships from {stats['source_files']} files"
                )
    except Exception as e:
        logger.error("KG extraction failed: %s", e, exc_info=True)
        with _extraction_lock:
            _extraction_status["result"] = f"Error: {e}"
    finally:
        with _extraction_lock:
            _extraction_status["running"] = False


@router.post("/extract")
@limiter.limit(STANDARD)
def kg_extract(request: Request, settings: Settings = Depends(get_settings)):
    """Start background KG extraction over all indexed files."""
    kgdb = _get_kgdb(request)
    tracking = request.app.state.tracking

    with _extraction_lock:
        if _extraction_status["running"]:
            raise HTTPException(409, "Extraction already in progress")
        _extraction_status["running"] = True
        _extraction_status["cancel"].clear()
        _extraction_status["progress"] = 0.0
        _extraction_status["message"] = "Starting extraction..."
        _extraction_status["result"] = ""
        _extraction_status["files_done"] = 0
        _extraction_status["files_total"] = 0

    threading.Thread(
        target=_bg_extract,
        args=(settings, kgdb, tracking),
        daemon=True,
    ).start()
    return {"status": "started"}


@router.post("/extract/cancel")
@limiter.limit(STANDARD)
def kg_extract_cancel(request: Request):
    """Cancel a running KG extraction."""
    _extraction_status["cancel"].set()
    return {"status": "cancelling"}


@router.get("/extract/status")
@limiter.limit(STANDARD)
def kg_extract_status(request: Request):
    """Return current KG extraction progress."""
    with _extraction_lock:
        return {
            "running": _extraction_status["running"],
            "progress": _extraction_status["progress"],
            "message": _extraction_status["message"],
            "result": _extraction_status["result"],
            "files_done": _extraction_status["files_done"],
            "files_total": _extraction_status["files_total"],
        }


# -- Query endpoints --


@router.get("/data")
@limiter.limit(STANDARD)
def kg_data(
    request: Request,
    entity_types: str | None = Query(None, description="Comma-separated entity types"),
    rel_types: str | None = Query(None, description="Comma-separated relationship types"),
):
    """Return knowledge graph entities and relationships for visualization."""
    kgdb = _get_kgdb(request)

    et = [t.strip() for t in entity_types.split(",")] if entity_types else None
    rt = [t.strip() for t in rel_types.split(",")] if rel_types else None

    entities = kgdb.get_all_entities(entity_types=et)
    relationships = kgdb.get_all_relationships(rel_types=rt)

    return {
        "entities": entities,
        "relationships": relationships,
        "entity_types": kgdb.get_entity_types(),
        "relationship_types": kgdb.get_relationship_types(),
        "stats": kgdb.get_stats(),
    }


@router.get("/entity")
@limiter.limit(STANDARD)
def kg_entity(
    request: Request,
    name: str = Query(..., description="Entity name"),
):
    """Return a single entity with all its relationships."""
    kgdb = _get_kgdb(request)
    entity = kgdb.get_entity(name)
    if entity is None:
        raise HTTPException(404, f"Entity not found: {name}")
    return entity


@router.get("/path")
@limiter.limit(STANDARD)
def kg_path(
    request: Request,
    source: str = Query(..., description="Source entity name"),
    target: str = Query(..., description="Target entity name"),
    max_hops: int = Query(6, ge=1, le=20),
):
    """Find the shortest path between two entities."""
    kgdb = _get_kgdb(request)
    path = kgdb.find_path(source, target, max_hops=max_hops)
    if path is None:
        return {"path": None, "message": f"No path found between '{source}' and '{target}'"}
    return {"path": path}


@router.get("/stats")
@limiter.limit(STANDARD)
def kg_stats(request: Request):
    """Return knowledge graph statistics."""
    kgdb = getattr(request.app.state, "kgdb", None)
    if kgdb is None:
        return {"entity_mentions": 0, "unique_entities": 0, "relationships": 0, "source_files": 0, "cached_chunks": 0}
    return kgdb.get_stats()


@router.post("/clear")
@limiter.limit(STANDARD)
def kg_clear(request: Request):
    """Clear all knowledge graph data. Run extraction to rebuild."""
    kgdb = _get_kgdb(request)
    kgdb.clear()
    return {"status": "cleared"}

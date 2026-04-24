"""Bucket management endpoints — CRUD, search, and chat."""

import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.config.docker import in_docker
from app.deps import get_settings
from app.ratelimit import LLM, STANDARD, limiter

from .bucket_service import BucketService
from .docker_mount import (
    ensure_base_path_mount,
    ensure_mounts_for_sources,
    prune_mounts_after_delete,
)
from .schemas import (
    AddToBucketRequest,
    BasepathRequest,
    BucketChatRequest,
    BucketSearchRequest,
    CreateBucketRequest,
    PushDocumentsRequest,
    RenameDocumentRequest,
    UpdateBucketRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["buckets"])

# Palette for auto-assigning colors to new buckets (rotates through by index)
_BUCKET_COLORS = [
    "#6366f1",  # indigo
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#f97316",  # orange
    "#14b8a6",  # teal
    "#06b6d4",  # cyan
    "#84cc16",  # lime
    "#f59e0b",  # amber
]

_EXPORT_FORMAT_VERSION = 1


def _get_bucket_service(request: Request) -> BucketService:
    svc = getattr(request.app.state, "bucket_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
    return svc


def _resolve_bucket(svc: BucketService, bucket_id: str) -> dict:
    """Look up a bucket by id or name, raising 404 if missing."""
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")
    return record


# -- Endpoints ---------------------------------------------------------------


@router.get("/buckets/base-path")
@limiter.limit(STANDARD)
def get_base_path(
    request: Request,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Return the configured buckets base path and whether it is mounted."""
    base_path = settings.get_plugin_config("buckets").get("base_path") or None
    mounted = False
    if base_path and in_docker():
        resolved = str(Path(base_path).resolve())
        mounted = resolved in set(settings.bucket_mounts)
    return {"base_path": base_path, "mounted": mounted, "docker": in_docker()}


@router.post("/buckets/base-path")
@limiter.limit(STANDARD)
def set_base_path(
    request: Request,
    req: BasepathRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Set (or clear) the buckets base path and mount it in Docker if needed."""
    docker_restart_required = False
    if req.base_path:
        settings.set_plugin_config("buckets", {"base_path": req.base_path})
        docker_restart_required = ensure_base_path_mount(settings, svc, req.base_path)
    else:
        settings.set_plugin_config("buckets", {"base_path": None})
    settings.save()
    return {
        "base_path": req.base_path or None,
        "docker_restart_required": docker_restart_required,
    }


@router.get("/buckets")
@limiter.limit(STANDARD)
def list_buckets(
    request: Request,
    svc: BucketService = Depends(_get_bucket_service),
):
    """List all buckets with metadata and indexing status."""
    svc.flag_expired()
    buckets = svc.db.list_all()
    for b in buckets:
        store = svc.get_store(b["id"])
        actual = store.count
        b["indexed_chunks"] = actual
        b["indexing"] = b["chunk_count"] > 0 and actual == 0
    return {"buckets": buckets, "total": len(buckets)}


@router.post("/buckets", status_code=201)
@limiter.limit(STANDARD)
def create_bucket(
    request: Request,
    req: CreateBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Create a new bucket from source paths."""
    try:
        color = req.color
        if not color:
            existing = svc.db.list_all()
            color = _BUCKET_COLORS[len(existing) % len(_BUCKET_COLORS)]

        sources = [s.model_dump() for s in req.sources]
        record = svc.create(req.name, sources, req.expires_in, color=color, description=req.description)

        docker_restart_required = ensure_mounts_for_sources(
            settings, svc, [s.path for s in req.sources],
        )

        return {**record, "docker_restart_required": docker_restart_required}
    except ValueError as e:
        logger.warning("Bucket creation rejected: %s", e)
        raise HTTPException(status_code=409, detail="Bucket name conflict or invalid source")
    except Exception as e:
        logger.error("Bucket creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket creation failed")


@router.get("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def get_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Get a single bucket by ID or name."""
    return _resolve_bucket(svc, bucket_id)


@router.patch("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def update_bucket(
    request: Request,
    bucket_id: str,
    req: UpdateBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Update bucket settings (name, expiration, color)."""
    record = _resolve_bucket(svc, bucket_id)

    updates: dict = {}

    if "expires_in" in req.model_fields_set:
        if req.expires_in is None or req.expires_in <= 0:
            updates["expires_at"] = None
            updates["expired"] = 0
        else:
            updates["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=req.expires_in)
            ).strftime("%Y-%m-%d %H:%M:%S")
            updates["expired"] = 0

    if req.name is not None:
        if req.name != record["name"] and svc.db.name_exists(req.name):
            raise HTTPException(status_code=409, detail="Bucket name already taken")
        updates["name"] = req.name

    if req.color is not None:
        updates["color"] = req.color

    if "description" in req.model_fields_set:
        updates["description"] = req.description

    if updates:
        svc.db.update(record["id"], **updates)

    updated = svc.db.get(record["id"])
    return {"status": "updated", **{k: updated.get(k) for k in ("name", "expires_at", "expired", "color", "description")}}


@router.get("/buckets/{bucket_id}/files")
@limiter.limit(STANDARD)
def list_bucket_files(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """List files in a bucket with chunk counts.

    Falls back to scanning source paths when ChromaDB is still
    being populated (background indexing).
    """
    record = _resolve_bucket(svc, bucket_id)
    store = svc.get_store(record["id"])
    all_meta = store.get_all_metadatas()

    indexing = False
    if all_meta:
        files: dict[str, dict] = {}
        for meta in all_meta:
            path = meta.get("source_path", "")
            if not path:
                continue
            if path not in files:
                files[path] = {
                    "path": path,
                    "title": meta.get("title", ""),
                    "chunk_count": 0,
                }
            files[path]["chunk_count"] += 1
        file_list = sorted(files.values(), key=lambda f: f["path"])
    else:
        indexing = record["chunk_count"] > 0
        sources = json.loads(record.get("sources", "[]"))
        file_list = []
        for src in sources:
            path = src.get("path", "")
            glob_pattern = src.get("glob", "**/*.md")
            resolved = Path(path).resolve()
            if resolved.is_file() and resolved.suffix == ".md":
                file_list.append({"path": str(resolved), "title": "", "chunk_count": 0})
            elif resolved.is_dir():
                for match in sorted(resolved.glob(glob_pattern)):
                    if match.is_file() and match.suffix == ".md":
                        file_list.append({"path": str(match), "title": "", "chunk_count": 0})

    return {"files": file_list, "total": len(file_list), "indexing": indexing}


@router.get("/buckets/{bucket_id}/file")
@limiter.limit(STANDARD)
def read_bucket_file(
    request: Request,
    bucket_id: str,
    path: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Read a file's full content from a bucket.

    Reconstructs the document from stored chunks, ordered by chunk_index.
    Works for both filesystem-sourced and pushed (virtual) documents.
    """
    record = _resolve_bucket(svc, bucket_id)
    store = svc.get_store(record["id"])
    result = store._collection.get(
        where={"source_path": path},
        include=["documents", "metadatas"],
    )
    if not result["ids"]:
        raise HTTPException(status_code=404, detail=f"File not found in bucket: {path}")

    chunks = sorted(
        zip(result["documents"], result["metadatas"]),
        key=lambda x: x[1].get("chunk_index", 0),
    )

    parts = []
    for doc, _meta in chunks:
        lines = doc.split("\n", 2)
        if lines[0].startswith("From:") and len(lines) > 2:
            parts.append(lines[2])
        else:
            parts.append(doc)

    title = chunks[0][1].get("title", "") if chunks else ""

    return {
        "path": path,
        "title": title,
        "content": "\n\n".join(parts),
        "chunk_count": len(chunks),
    }


@router.delete("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def delete_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Delete a bucket and its vector data."""
    try:
        result = svc.delete(bucket_id)
        prune_mounts_after_delete(settings, svc)
        return result
    except ValueError as e:
        logger.warning("Bucket delete: %s", e)
        raise HTTPException(status_code=404, detail="Bucket not found")


@router.post("/buckets/{bucket_id}/search")
@limiter.limit(STANDARD)
def search_bucket(
    request: Request,
    bucket_id: str,
    req: BucketSearchRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Search within a bucket."""
    record = _resolve_bucket(svc, bucket_id)
    if record.get("expired"):
        raise HTTPException(status_code=410, detail="Bucket has expired — delete it or extend its expiry")
    try:
        return svc.search(bucket_id, req.query, req.top_k, settings)
    except ValueError as e:
        logger.warning("Bucket search: %s", e)
        raise HTTPException(status_code=404, detail="Bucket not found")


@router.post("/buckets/{bucket_id}/chat")
@limiter.limit(LLM)
def chat_bucket(
    request: Request,
    bucket_id: str,
    req: BucketChatRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """RAG chat scoped to a bucket."""
    record = _resolve_bucket(svc, bucket_id)
    if record.get("expired"):
        raise HTTPException(status_code=410, detail="Bucket has expired — delete it or extend its expiry")
    try:
        return svc.chat(bucket_id, req.message, settings)
    except ValueError as e:
        logger.warning("Bucket chat: %s", e)
        raise HTTPException(status_code=404, detail="Bucket not found")


@router.post("/buckets/{bucket_id}/reindex")
@limiter.limit(STANDARD)
def reindex_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Re-scan the bucket's original sources and index any files not yet embedded.

    Useful when a bucket was created before its source path was mounted in Docker.
    Skips files already present in the bucket.
    """
    record = _resolve_bucket(svc, bucket_id)
    if record.get("expired"):
        raise HTTPException(status_code=410, detail="Bucket has expired — delete it or extend its expiry")
    sources = json.loads(record.get("sources", "[]"))
    if not sources:
        return {"added_files": 0, "added_chunks": 0, "message": "No sources configured"}
    try:
        return svc.add_documents(bucket_id, sources)
    except Exception as e:
        logger.error("Bucket reindex failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket reindex failed")


@router.post("/buckets/{bucket_id}/add")
@limiter.limit(STANDARD)
def add_to_bucket(
    request: Request,
    bucket_id: str,
    req: AddToBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Add documents to an existing bucket. Files already present are skipped."""
    try:
        sources = [s.model_dump() for s in req.sources]
        return svc.add_documents(bucket_id, sources)
    except ValueError as e:
        logger.warning("Bucket add: %s", e)
        raise HTTPException(status_code=404, detail="Bucket not found")
    except Exception as e:
        logger.error("Bucket add failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket add failed")


@router.post("/buckets/{bucket_id}/documents")
@limiter.limit(STANDARD)
def push_documents(
    request: Request,
    bucket_id: str,
    req: PushDocumentsRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Push markdown documents into a bucket by content — no filesystem access needed.

    Each document has a name (virtual filename) and content (raw markdown).
    Use this when the caller is on a different machine and can't provide
    a local directory path.
    """
    try:
        docs = [d.model_dump() for d in req.documents]
        return svc.push_documents(bucket_id, docs)
    except ValueError as e:
        logger.warning("Bucket push: %s", e)
        raise HTTPException(status_code=404, detail="Bucket not found")
    except Exception as e:
        logger.error("Bucket push failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket push failed")


@router.patch("/buckets/{bucket_id}/documents")
@limiter.limit(STANDARD)
def rename_bucket_document(
    request: Request,
    bucket_id: str,
    req: RenameDocumentRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Rename a virtual document within a bucket.

    Only virtual documents (paths starting with ``bucket://``) can be renamed.
    Filesystem-sourced files must be renamed on disk and reindexed.
    """
    record = _resolve_bucket(svc, bucket_id)
    if not req.old_path.startswith("bucket://"):
        raise HTTPException(status_code=400, detail="Only virtual documents can be renamed via this endpoint")
    bucket_name = record["name"]
    new_name = req.new_name if req.new_name.endswith(".md") else f"{req.new_name}.md"
    new_path = f"bucket://{bucket_name}/{new_name}"
    if new_path == req.old_path:
        return {"old_path": req.old_path, "new_path": new_path, "chunks_updated": 0}
    store = svc.get_store(record["id"])
    count = store.rename_source(req.old_path, new_path, f"bucket://{bucket_name}")
    if count == 0:
        raise HTTPException(status_code=404, detail="Document not found in bucket")
    return {"old_path": req.old_path, "new_path": new_path, "chunks_updated": count}


# ---------------------------------------------------------------------------
# Export / Import / Promote
# ---------------------------------------------------------------------------


@router.get("/buckets/{bucket_id}/export")
@limiter.limit(STANDARD)
def export_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Export a bucket as a portable zip archive."""
    record = _resolve_bucket(svc, bucket_id)

    store = svc.get_store(record["id"])
    data = store.get_all_with_embeddings()

    manifest = {
        "format_version": _EXPORT_FORMAT_VERSION,
        "name": record["name"],
        "description": record.get("description"),
        "color": record.get("color"),
        "sources": json.loads(record.get("sources", "[]")),
        "created_at": record.get("created_at"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(data["ids"]),
    }

    chunks = [
        {
            "id": chunk_id,
            "document": doc,
            "metadata": meta,
            "embedding": emb,
        }
        for chunk_id, doc, meta, emb in zip(
            data["ids"], data["documents"], data["metadatas"], data["embeddings"]
        )
    ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("chunks.json", json.dumps(chunks))
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in record["name"])
    filename = f"bucket-{safe_name}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/buckets/import", status_code=201)
@limiter.limit(STANDARD)
async def import_bucket(
    request: Request,
    file: UploadFile,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Import a bucket from a previously exported zip archive."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Expected a .zip file")

    try:
        raw = await file.read()
        buf = io.BytesIO(raw)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            if "manifest.json" not in names or "chunks.json" not in names:
                raise HTTPException(status_code=400, detail="Invalid bucket archive — missing manifest.json or chunks.json")

            manifest = json.loads(zf.read("manifest.json"))
            chunks = json.loads(zf.read("chunks.json"))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="File is not a valid zip archive")

    if manifest.get("format_version") != _EXPORT_FORMAT_VERSION:
        raise HTTPException(status_code=400, detail=f"Unsupported archive format version: {manifest.get('format_version')}")

    base_name = manifest.get("name", "imported-bucket")
    name = base_name
    suffix = 1
    while svc.db.name_exists(name):
        name = f"{base_name}-{suffix}"
        suffix += 1

    color = manifest.get("color")
    if not color:
        existing = svc.db.list_all()
        color = _BUCKET_COLORS[len(existing) % len(_BUCKET_COLORS)]

    record = svc.db.create(
        name=name,
        sources=json.dumps(manifest.get("sources", [])),
        file_count=0,
        chunk_count=0,
        color=color,
        description=manifest.get("description"),
    )
    bucket_id = record["id"]

    if chunks:
        ids = [c["id"] for c in chunks]
        docs = [c["document"] for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        store = svc.get_store(bucket_id)
        store.add(ids, docs, embeddings, metadatas)

        file_paths = {m.get("source_path", "") for m in metadatas if m.get("source_path")}
        svc.db.update(bucket_id, file_count=len(file_paths), chunk_count=len(ids))
        record = svc.db.get(bucket_id)

    logger.info("Bucket imported: %s (%d chunks)", name, len(chunks))
    return record


@router.post("/buckets/{bucket_id}/promote")
@limiter.limit(STANDARD)
def promote_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Promote bucket source paths to permanent watched directories."""
    record = _resolve_bucket(svc, bucket_id)

    sources = json.loads(record.get("sources", "[]"))
    if not sources:
        return {"promoted": [], "message": "Bucket has no source paths to promote"}

    added: list[str] = []
    already_present: list[str] = []
    for src in sources:
        path = src.get("path", "") if isinstance(src, dict) else str(src)
        if not path:
            continue
        existing = settings.explicit_sources
        if path in existing:
            already_present.append(path)
        else:
            settings.add_source({"path": path, "writable": False, "tier": -1})
            added.append(path)

    if added:
        settings.save()

    return {
        "promoted": added,
        "already_present": already_present,
        "message": f"Added {len(added)} source(s) to watched directories. FileWatcher will index them on the next scan.",
    }

"""Background task status endpoints.

Exposes the in-memory :class:`TaskRegistry` so the UI (and other clients)
can see status for fire-and-forget operations like source indexing,
re-indexing, and conversion.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps import get_task_registry
from app.ratelimit import STANDARD, limiter
from app.services.task_registry import TaskRegistry

router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.get("/tasks")
@limiter.limit(STANDARD)
def list_tasks(
    request: Request,
    kind: str | None = None,
    limit: int = 50,
    registry: TaskRegistry = Depends(get_task_registry),
):
    """List recent background tasks (newest first)."""
    limit = max(1, min(int(limit), 200))
    items = [r.to_dict() for r in registry.list(kind=kind, limit=limit)]
    return {"items": items, "total": len(items), "offset": 0, "limit": limit}


@router.get("/tasks/{task_id}")
@limiter.limit(STANDARD)
def get_task(
    request: Request,
    task_id: str,
    registry: TaskRegistry = Depends(get_task_registry),
):
    """Return the status of a single background task."""
    record = registry.get(task_id)
    if record is None:
        raise HTTPException(404, "Task not found")
    return record.to_dict()

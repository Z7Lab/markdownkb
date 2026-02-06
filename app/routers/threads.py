"""Thread CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.deps import get_chatdb
from app.ratelimit import STANDARD, limiter
from app.schemas import RenameThreadRequest
from app.storage.chatdb import ChatDB

router = APIRouter(prefix="/api", tags=["threads"])


@router.get("/threads")
@limiter.limit(STANDARD)
def list_threads(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    chatdb: ChatDB = Depends(get_chatdb),
):
    total = chatdb.thread_count()
    items = chatdb.list_threads(offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/threads/{thread_id}/messages")
@limiter.limit(STANDARD)
def get_thread_messages(
    request: Request,
    thread_id: str,
    chatdb: ChatDB = Depends(get_chatdb),
):
    if not chatdb.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"messages": chatdb.get_messages(thread_id)}


@router.delete("/threads/{thread_id}")
@limiter.limit(STANDARD)
def delete_thread(
    request: Request,
    thread_id: str,
    chatdb: ChatDB = Depends(get_chatdb),
):
    if not chatdb.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    chatdb.delete_thread(thread_id)
    return {"status": "deleted"}


@router.patch("/threads/{thread_id}")
@limiter.limit(STANDARD)
def rename_thread(
    request: Request,
    thread_id: str,
    req: RenameThreadRequest,
    chatdb: ChatDB = Depends(get_chatdb),
):
    if not chatdb.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    chatdb.rename_thread(thread_id, req.title)
    return {"status": "renamed"}

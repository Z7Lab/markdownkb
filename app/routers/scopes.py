"""CRUD endpoints for named document scopes (source collections)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.deps import get_scopedb
from app.ratelimit import STANDARD, limiter
from app.storage.scopedb import ScopeDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scopes", tags=["scopes"])


class ScopeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    folders: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class ScopeUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    folders: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


@router.get("")
@limiter.limit(STANDARD)
def list_scopes(
    request: Request,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """List all scopes, newest first."""
    items = scopedb.list_scopes()
    return {"scopes": items, "total": len(items)}


@router.post("", status_code=201)
@limiter.limit(STANDARD)
def create_scope(
    request: Request,
    req: ScopeCreate,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Create a new named scope."""
    if not req.folders and not req.tags:
        raise HTTPException(status_code=422, detail="At least one folder or tag is required")
    scope_id = scopedb.create(req.name, req.folders, req.tags, req.exclude_patterns)
    return {"id": scope_id, "status": "created"}


@router.get("/{scope_id}")
@limiter.limit(STANDARD)
def get_scope(
    request: Request,
    scope_id: str,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Get a single scope by ID."""
    scope = scopedb.get(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return scope


@router.put("/{scope_id}")
@limiter.limit(STANDARD)
def update_scope(
    request: Request,
    scope_id: str,
    req: ScopeUpdate,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Update a scope's name and folders."""
    if not req.folders and not req.tags:
        raise HTTPException(status_code=422, detail="At least one folder or tag is required")
    if not scopedb.update(scope_id, req.name, req.folders, req.tags, req.exclude_patterns):
        raise HTTPException(status_code=404, detail="Scope not found")
    return {"status": "updated"}


@router.delete("/{scope_id}")
@limiter.limit(STANDARD)
def delete_scope(
    request: Request,
    scope_id: str,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Delete a scope."""
    if not scopedb.delete(scope_id):
        raise HTTPException(status_code=404, detail="Scope not found")
    return {"status": "deleted"}

"""Scope, tag, and bucket resolution — shared across chat/planner/search.

Centralizes the 3-step resolution idiom so every router has identical
error-handling semantics:

- scope id unknown      → 404 (via resolve_scopes)
- bucket plugin absent  → 503
- bucket id unknown     → 404
"""

from dataclasses import dataclass

from fastapi import HTTPException

from app.config import Settings
from app.domains.scope_resolution import parse_scope_ids, resolve_scopes
from app.storage.scopedb import ScopeDB
from app.domains.tag_registry import resolve_tag_paths


@dataclass
class ScopeBundle:
    """Resolved scope + bucket context for a request."""

    scope_folders: list[str] | None
    allowed_paths: set[str] | None
    exclude_patterns: list
    bucket_retrievers: list
    bucket_only: bool

    @property
    def has_scope(self) -> bool:
        return bool(self.scope_folders or self.allowed_paths)


def parse_scope_id_fallback(
    scope_ids, scope_id: str | None,
) -> list[str] | None:
    """Merge the new `scope_ids` list with the legacy `scope_id` single value."""
    return parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)


def resolve_bucket_retrievers(
    bucket_service,
    bucket_ids: list[str] | None,
    settings: Settings,
) -> list:
    """Resolve bucket IDs into retriever instances.

    Raises:
        HTTPException(503): bucket_ids provided but plugin not initialized
        HTTPException(404): a bucket id does not resolve to a record
    """
    if not bucket_ids:
        return []
    if bucket_service is None:
        raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
    retrievers: list = []
    for bid in bucket_ids:
        record = bucket_service.db.resolve(bid)
        if not record:
            raise HTTPException(status_code=404, detail=f"Bucket not found: {bid}")
        retrievers.append(bucket_service.get_retriever(record["id"], settings))
    return retrievers


def resolve_request_scope(
    *,
    bucket_service,
    scope_ids,
    scope_id: str | None,
    bucket_ids,
    ad_hoc_tags: list[str] | None,
    settings: Settings,
    scopedb: ScopeDB,
) -> ScopeBundle:
    """Resolve scopes, tags, and buckets into a single bundle."""
    ids = parse_scope_id_fallback(scope_ids, scope_id)
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, ad_hoc_tags)
    b_ids = parse_scope_ids(bucket_ids)
    bucket_retrievers = resolve_bucket_retrievers(bucket_service, b_ids, settings)
    has_scope = bool(scope_folders or allowed)
    return ScopeBundle(
        scope_folders=scope_folders,
        allowed_paths=allowed,
        exclude_patterns=exclude_patterns,
        bucket_retrievers=bucket_retrievers,
        bucket_only=bool(bucket_retrievers) and not has_scope,
    )

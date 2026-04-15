"""Dependency injection functions for FastAPI routers."""

import threading

from fastapi import HTTPException, Request

from app.config import Settings
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.presetsdb import PresetsDB
from app.storage.scopedb import ScopeDB
from app.storage.searchdb import SearchDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> VectorStore:
    return request.app.state.store


def get_retriever(request: Request) -> Retriever:
    return request.app.state.retriever


def get_tracking(request: Request) -> TrackingDB:
    return request.app.state.tracking


def get_chatdb(request: Request) -> ChatDB:
    return request.app.state.chatdb


def get_searchdb(request: Request) -> SearchDB:
    return request.app.state.searchdb


def get_plandb(request: Request) -> PlanDB:
    return request.app.state.plandb


def get_scopedb(request: Request) -> ScopeDB:
    return request.app.state.scopedb


def get_presetsdb(request: Request) -> PresetsDB:
    return request.app.state.presetsdb


def get_cancel_event(request: Request) -> threading.Event:
    return request.app.state.cancel_event


def get_watcher(request: Request):
    """Return the FileWatcher instance (or None if file watching is off)."""
    return getattr(request.app.state, "watcher", None)


def get_conversation_history(request: Request):
    """Return the in-memory ConversationHistory fallback instance."""
    return request.app.state.conversation_history


def get_tagdb(request: Request):
    """Return the TagDB instance, or None if the tags plugin is disabled."""
    return getattr(request.app.state, "tagdb", None)


def require_auth(request: Request) -> None:
    """Dependency that requires authentication to be configured.

    Use on endpoints that are unconditionally dangerous regardless of
    the global auth setting (e.g. plugin installation, which executes
    arbitrary code).  Raises 403 when no API key is configured so that
    unauthenticated LAN requests cannot reach shell-equivalent endpoints.
    """
    if not getattr(request.app.state, "auth_enabled", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "This endpoint requires API key authentication. "
                "Generate a key first via POST /api/v1/setup/generate-key."
            ),
        )

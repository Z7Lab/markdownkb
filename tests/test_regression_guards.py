"""Regression guards for structural changes from the 2026-04 refactor.

These are cheap static scans run as pytest tests so that reintroductions
of the patterns we just cleaned up are caught in CI. See
planning_docs/mdkb-refactoring-plan.md for context on each rule.
"""

from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _walk_py(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


@pytest.mark.parametrize("attr", ["_data", "_path"])
def test_settings_private_internals_not_accessed(attr):
    """External modules must not touch ``settings._data`` / ``settings._path``.

    Use the public accessors added in Phase 5.1 (``settings.project_root``,
    ``settings.bucket_mounts``, etc.) so the Settings class can evolve.
    """
    needle = f"settings.{attr}"
    offenders: list[str] = []
    for path in _walk_py(APP_DIR):
        if path.parts[-2] == "config":
            continue  # Settings class itself is allowed
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if needle in line and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{i}: {line.strip()}")
    assert not offenders, (
        f"External access to settings.{attr} is forbidden. Use a public "
        "accessor on Settings instead.\n" + "\n".join(offenders)
    )


_SERVICE_LOCATOR_KEYS = (
    "bucket_service",
    "kgdb",
    "wikidb",
    "versioning_manager",
)


def test_no_service_locator_pattern_in_routers():
    """Routers must use FastAPI ``Depends()`` for cross-plugin services.

    ``getattr(request.app.state, "bucket_service", None)`` hides the
    dependency from type checkers and tests — use ``Depends(get_bucket_service)``
    (and friends in ``app.deps``) instead.

    Exemptions:
    - ``app/deps.py`` — the canonical DI layer.
    - ``app/main.py``, ``app/api.py`` — lifespan / app wiring.
    - ``app/auth.py`` — middleware reads ``api_key`` directly so runtime
      rotations are picked up.
    - Plugin ``_get_X`` local dep wrappers that add the 503 raise (these
      are used with ``Depends()`` inside the plugin only).
    """
    allowed_files = {
        APP_DIR / "deps.py",
        APP_DIR / "main.py",
        APP_DIR / "api.py",
        APP_DIR / "auth.py",
        APP_DIR / "versioning" / "router.py",
        APP_DIR / "plugins" / "wiki_compile" / "router.py",
        APP_DIR / "plugins" / "buckets" / "router.py",
    }
    offenders: list[str] = []
    for path in _walk_py(APP_DIR):
        if path in allowed_files:
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "getattr(request.app.state" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(f'"{key}"' in line for key in _SERVICE_LOCATOR_KEYS):
                offenders.append(
                    f"{path.relative_to(APP_DIR.parent)}:{i}: {stripped}"
                )
    assert not offenders, (
        "Cross-plugin services must be injected via FastAPI Depends(). "
        "Add a dependency in app/deps.py and use it in the handler.\n"
        + "\n".join(offenders)
    )


def test_app_utils_not_resurrected():
    """``app/utils.py`` was split into transport/security/text modules.

    Prevent accidental re-creation, which would land everyone back at a
    catch-all module for unrelated functions.
    """
    assert not (APP_DIR / "utils.py").exists(), (
        "app/utils.py is intentionally removed. Put SSE helpers in "
        "app.transport, URL validation in app.security, and text helpers "
        "(short_title, parse_model, get_path_size) in app.text."
    )
    assert not (APP_DIR / "utils").exists(), (
        "app/utils/ directory is intentionally removed."
    )


def test_legacy_utils_names_not_resurrected():
    """``app/scope_utils.py`` / ``app/tag_utils.py`` moved to ``app/domains/``."""
    assert not (APP_DIR / "scope_utils.py").exists(), (
        "app/scope_utils.py moved to app/domains/scope_resolution.py"
    )
    assert not (APP_DIR / "tag_utils.py").exists(), (
        "app/tag_utils.py moved to app/domains/tag_registry.py"
    )


def test_no_inline_scope_bucket_resolution_in_routers():
    """Scope + bucket resolution must go through ``resolve_request_scope``.

    The 3-line ``parse_scope_ids(...) or ([scope_id] if ...)`` idiom
    followed by an inline bucket-retriever loop is what
    ``app.services.scope_service.resolve_request_scope`` consolidates.
    Don't reintroduce it at call sites — the silent-skip vs 404 drift it
    caused is what prompted Phase 1 of this refactor.
    """
    allowed = {
        APP_DIR / "services" / "scope_service.py",
        APP_DIR / "domains" / "scope_resolution.py",
    }
    offenders: list[str] = []
    for path in _walk_py(APP_DIR):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if "bucket_service.db.resolve" in text and "bucket_service.get_retriever" in text:
            if "resolve_request_scope" in text:
                continue
            if "buckets" in path.parts:
                continue
            if "mcp" in path.parts:
                continue
            offenders.append(str(path.relative_to(APP_DIR.parent)))
    assert not offenders, (
        "Inline bucket retriever resolution found. Use "
        "app.services.scope_service.resolve_request_scope or "
        "resolve_bucket_retrievers instead.\n" + "\n".join(offenders)
    )

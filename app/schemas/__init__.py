"""Pydantic request/response models, organized by API domain.

Each submodule owns schemas for one API surface. Import the specific
submodule in routers — don't re-import from this package's root, so
new schema additions stay co-located with the rest of their domain.
"""

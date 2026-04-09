"""Source directory and project root configuration mixin."""

from pathlib import Path


class SourcesMixin:
    """Mixin providing source directory, project root, and ignore pattern management."""

    # --- Sources ---

    def _source_entry(self, entry) -> dict:
        """Return a source config dict with defaults applied.

        Each source entry must be a dict with ``path`` (required) and
        ``writable`` (default True).
        """
        return {"path": entry.get("path", ""), "writable": entry.get("writable", True)}

    @property
    def source_configs(self) -> list[dict]:
        """Return all explicit source entries as dicts with resolved paths.

        Each dict has ``path`` (resolved) and ``writable`` (bool).
        """
        result = []
        for entry in self._data.get("sources", []):
            cfg = self._source_entry(entry)
            cfg["path"] = self._resolve_path(cfg["path"])
            result.append(cfg)
        return result

    @property
    def explicit_sources(self) -> list[str]:
        """Return resolved paths for explicitly configured sources only."""
        return [
            self._resolve_path(self._source_entry(s)["path"])
            for s in self._data.get("sources", [])
        ]

    @property
    def sources(self) -> list[str]:
        """Return resolved paths for all sources (explicit + project roots)."""
        explicit = self.explicit_sources
        expanded = self._expand_project_roots()
        seen = set(explicit)
        merged = list(explicit)
        for d in expanded:
            if d not in seen:
                seen.add(d)
                merged.append(d)
        return merged

    @sources.setter
    def sources(self, value: list[str]):
        """Set the list of explicit source directories."""
        self._data["sources"] = value

    def is_source_writable(self, path: str) -> bool:
        """Check whether a source directory allows writes.

        Returns False if the source is configured with ``writable: false``.
        Returns True for sources not explicitly configured (project roots,
        unknown paths) — the caller is responsible for checking that the
        path is actually a configured source before writing.
        """
        resolved = self._resolve_path(path)
        for entry in self._data.get("sources", []):
            cfg = self._source_entry(entry)
            if self._resolve_path(cfg["path"]) == resolved:
                return cfg["writable"]
        return True  # Not an explicit source — defer to caller

    @property
    def writable_sources(self) -> list[str]:
        """Return resolved paths for sources that allow writes."""
        return [
            path for path in self.sources
            if self.is_source_writable(path)
        ]

    def add_source(self, path: str):
        """Add a source directory if not already present."""
        raw = self._data.setdefault("sources", [])
        if path not in raw and path not in self.explicit_sources:
            raw.append(path)

    def remove_source(self, path: str):
        """Remove a source directory from the list."""
        raw = self._data.setdefault("sources", [])
        if path in raw:
            raw.remove(path)
        else:
            # Try matching by resolved path
            resolved = self._resolve_path(path)
            for s in list(raw):
                if self._resolve_path(s) == resolved:
                    raw.remove(s)
                    break

    # --- Project Roots ---
    @property
    def project_roots(self) -> list[dict]:
        """Return the list of project root configurations."""
        return list(self._data.get("project_roots", []))

    def _expand_project_roots(self) -> list[str]:
        """Expand project roots into individual project directories to watch.

        For each project root, lists immediate subdirectories and checks if
        any files match the include patterns.  Returns the project subdirectory
        paths (not individual files) so the watcher can monitor them.
        """
        dirs: list[str] = []
        for root_cfg in self._data.get("project_roots", []):
            root_path = Path(self._resolve_path(root_cfg.get("path", "")))
            if not root_path.is_dir():
                continue
            include = root_cfg.get("include", ["*.md", "docs/**/*.md"])
            exclude = root_cfg.get("exclude", [])
            for child in sorted(root_path.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                # Check if any include pattern matches files in this project
                has_match = False
                for pattern in include:
                    matches = list(child.glob(pattern))
                    if exclude and matches:
                        matches = [
                            m for m in matches
                            if not any(m.match(ep) for ep in exclude)
                        ]
                    if matches:
                        has_match = True
                        break
                if has_match:
                    dirs.append(str(child))
        return dirs

    def add_project_root(self, path: str, include: list[str] | None = None,
                         exclude: list[str] | None = None):
        """Add a project root configuration."""
        roots = self._data.setdefault("project_roots", [])
        resolved = self._resolve_path(path)
        for r in roots:
            if self._resolve_path(r.get("path", "")) == resolved:
                return  # Already exists
        entry: dict = {"path": path}
        if include:
            entry["include"] = include
        if exclude:
            entry["exclude"] = exclude
        roots.append(entry)

    def remove_project_root(self, path: str):
        """Remove a project root by path."""
        roots = self._data.get("project_roots", [])
        resolved = self._resolve_path(path)
        self._data["project_roots"] = [
            r for r in roots
            if self._resolve_path(r.get("path", "")) != resolved
        ]

    def update_project_root(self, path: str, include: list[str] | None = None,
                            exclude: list[str] | None = None):
        """Update include/exclude patterns for an existing project root."""
        resolved = self._resolve_path(path)
        for r in self._data.get("project_roots", []):
            if self._resolve_path(r.get("path", "")) == resolved:
                if include is not None:
                    r["include"] = include
                if exclude is not None:
                    r["exclude"] = exclude
                return
        raise KeyError(f"Project root not found: {path}")

    @property
    def global_ignore(self) -> list[str]:
        """Return glob patterns for files to ignore."""
        return self._data.get("global_ignore", [])

    def add_ignore_pattern(self, pattern: str):
        """Add a glob pattern to the ignore list."""
        patterns = self._data.setdefault("global_ignore", [])
        if pattern not in patterns:
            patterns.append(pattern)

    def remove_ignore_pattern(self, pattern: str):
        """Remove a glob pattern from the ignore list."""
        patterns = self._data.get("global_ignore", [])
        if pattern in patterns:
            patterns.remove(pattern)

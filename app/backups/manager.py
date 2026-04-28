"""Backup and restore manager.

A backup is a single .tar.gz containing:
  manifest.json                — version, contents, schema versions, model
  databases/<name>.db           — consistent snapshot via sqlite3.backup()
  chromadb/                     — vector store directory copy
  plans/                        — generated plan markdown
  plugins/                      — plugin-owned data directory
  config/settings.yaml          — user configuration (optional)
  config/compose.override.yml   — Docker mount overrides (optional)
  sources/<i>/                  — user source directories (optional, off by default)

Excluded always: secrets/, embedding model weights, log files, WAL/SHM
sidecars (folded into the .db snapshot by the sqlite3 backup API).
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

_restore_lock = threading.Lock()

MANIFEST_NAME = "manifest.json"
BACKUP_FORMAT_VERSION = 1
RESTART_MARKER = ".restart-required"

# Files inside data_dir we never copy.
_EXCLUDE_TOP_LEVEL = {
    "secrets",
    "models",          # embedding weights — large, downloadable
    "versioning",      # git repos — separate concern, often huge
    ".restart-required",
}
_EXCLUDE_SUFFIXES = {".log", "-wal", "-shm"}


class BackupError(Exception):
    """Raised when a backup cannot be produced."""


class RestoreError(Exception):
    """Raised when a restore cannot be applied."""


@dataclass
class BackupOptions:
    include_config: bool = True
    include_sources: bool = False
    include_chromadb: bool = True


@dataclass
class RestoreOptions:
    apply_config: bool = True
    apply_sources: bool = False


class BackupManager:
    """Create and apply MarkdownKB backups.

    All paths are derived from ``data_dir`` (the runtime data directory) and
    ``project_root`` (where ``config/settings.yaml`` lives).
    """

    def __init__(
        self,
        data_dir: Path,
        project_root: Path,
        app_version: str = "0.0.0",
    ):
        self.data_dir = Path(data_dir).resolve()
        self.project_root = Path(project_root).resolve()
        self.app_version = app_version

    # ── Backup ──────────────────────────────────────────────────────────

    def create(
        self,
        dest: Path,
        options: BackupOptions,
        sources: Iterable[Path] = (),
        embedding_model: str = "",
        staging_hook=None,
    ) -> dict:
        """Build a .tar.gz at ``dest``.  Returns the manifest dict.

        ``staging_hook``, if provided, is called with the staging directory
        after all standard content has been written.  Use it to inject extra
        files (e.g. a markdown/ subtree) without coupling the manager to any
        specific plugin.
        """
        dest = Path(dest)
        staging = Path(tempfile.mkdtemp(prefix="mdkb-backup-"))
        try:
            self._stage(staging, options, sources)
            if staging_hook is not None:
                staging_hook(staging)
            manifest = self._write_manifest(staging, options, sources, embedding_model)
            self._make_tarball(staging, dest)
            return manifest
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _stage(
        self,
        staging: Path,
        options: BackupOptions,
        sources: Iterable[Path],
    ) -> None:
        # SQLite databases — consistent snapshot via backup() API.
        databases_dir = staging / "databases"
        databases_dir.mkdir(parents=True, exist_ok=True)
        for db_file in self._iter_db_files():
            target = databases_dir / db_file.name
            self._snapshot_sqlite(db_file, target)

        # ChromaDB directory — copy verbatim.  Includes its own sqlite +
        # parquet files; copying live is best-effort but acceptable for v1.
        if options.include_chromadb:
            chroma = self.data_dir / "chromadb"
            if chroma.is_dir():
                shutil.copytree(chroma, staging / "chromadb")

        # Plans + plugin-owned data dirs.
        for sub in ("plans", "plugins"):
            src = self.data_dir / sub
            if src.is_dir():
                shutil.copytree(src, staging / sub)

        # Optional config.
        if options.include_config:
            cfg_dir = staging / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            for name in ("settings.yaml", "compose.override.yml"):
                src = self.project_root / "config" / name
                if src.is_file():
                    shutil.copy2(src, cfg_dir / name)

        # Optional source directories.
        if options.include_sources:
            for i, src in enumerate(sources):
                src = Path(src)
                if src.is_dir():
                    shutil.copytree(src, staging / "sources" / f"{i}-{src.name}")

    def _iter_db_files(self):
        for entry in self.data_dir.iterdir():
            if entry.is_file() and entry.suffix == ".db":
                yield entry

    @staticmethod
    def _snapshot_sqlite(src: Path, dest: Path) -> None:
        """Use SQLite's online backup API for a consistent point-in-time copy."""
        src_con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        try:
            dest_con = sqlite3.connect(dest)
            try:
                with dest_con:
                    src_con.backup(dest_con)
            finally:
                dest_con.close()
        finally:
            src_con.close()

    def _write_manifest(
        self,
        staging: Path,
        options: BackupOptions,
        sources: Iterable[Path],
        embedding_model: str = "",
    ) -> dict:
        contents = []
        for top in sorted(p.name for p in staging.iterdir()):
            contents.append(top)
        manifest = {
            "format_version": BACKUP_FORMAT_VERSION,
            "mdkb_version": self.app_version,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": uuid.uuid4().hex,
            "contents": contents,
            "options": {
                "include_config": options.include_config,
                "include_sources": options.include_sources,
                "include_chromadb": options.include_chromadb,
            },
            "embedding_model": embedding_model,
            "sources": [str(Path(s)) for s in sources] if options.include_sources else [],
            "data_dir": str(self.data_dir),
        }
        (staging / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
        return manifest

    @staticmethod
    def _make_tarball(staging: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(dest, "w:gz") as tf:
            for entry in sorted(staging.iterdir()):
                tf.add(entry, arcname=entry.name)

    # ── Preview ─────────────────────────────────────────────────────────

    @staticmethod
    def read_manifest(archive: Path) -> dict:
        """Extract and return ``manifest.json`` without unpacking the rest."""
        with tarfile.open(archive, "r:gz") as tf:
            try:
                member = tf.getmember(MANIFEST_NAME)
            except KeyError as exc:
                raise RestoreError("archive is missing manifest.json") from exc
            fileobj = tf.extractfile(member)
            if fileobj is None:
                raise RestoreError("archive manifest is unreadable")
            return json.loads(fileobj.read().decode("utf-8"))

    # ── Restore ─────────────────────────────────────────────────────────

    def restore(
        self,
        archive: Path,
        options: RestoreOptions,
        current_embedding_model: str = "",
    ) -> dict:
        """Stage, validate, and atomically swap the archive into place.

        After a successful restore writes a marker file the user must
        restart the container/process to pick up the new DBs.
        """
        archive = Path(archive)
        if not archive.is_file():
            raise RestoreError(f"archive not found: {archive}")

        manifest = self.read_manifest(archive)
        self._validate_manifest(manifest)

        staging = Path(tempfile.mkdtemp(prefix="mdkb-restore-"))
        try:
            with tarfile.open(archive, "r:gz") as tf:
                _safe_extractall(tf, staging)

            with _restore_lock:
                self._swap_into_place(staging, options)
                self._write_restart_marker(manifest, current_embedding_model)
            return manifest
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _validate_manifest(self, manifest: dict) -> None:
        fmt = manifest.get("format_version")
        if fmt != BACKUP_FORMAT_VERSION:
            raise RestoreError(
                f"unsupported backup format_version {fmt} "
                f"(this build expects {BACKUP_FORMAT_VERSION})"
            )
        # Refuse backups produced by a newer mdkb version — they may
        # contain schemas this build cannot read.  Older versions are
        # accepted; the running app will run forward-only migrations.
        backup_ver = manifest.get("mdkb_version", "0.0.0")
        if _is_newer(backup_ver, self.app_version):
            raise RestoreError(
                f"backup was produced by mdkb {backup_ver}, but this build "
                f"is {self.app_version}. Upgrade before restoring."
            )

    def _swap_into_place(self, staging: Path, options: RestoreOptions) -> None:
        # Move existing data aside, then move new data in.  If anything
        # goes wrong we restore the old data.
        backup_old = self.data_dir.parent / f"{self.data_dir.name}.pre-restore-{uuid.uuid4().hex[:8]}"

        # Copy DBs back into data_dir from staging/databases/
        new_databases = staging / "databases"
        new_chromadb = staging / "chromadb"

        try:
            # Stash anything in data_dir we're about to overwrite, leaving
            # excluded directories (secrets/, models/) untouched.
            self.data_dir.mkdir(parents=True, exist_ok=True)
            backup_old.mkdir(parents=True, exist_ok=True)
            for entry in list(self.data_dir.iterdir()):
                if entry.name in _EXCLUDE_TOP_LEVEL:
                    continue
                if entry.suffix in {"-wal", "-shm"}:
                    entry.unlink(missing_ok=True)
                    continue
                shutil.move(str(entry), str(backup_old / entry.name))

            # Drop in fresh copies.
            if new_databases.is_dir():
                for db in new_databases.iterdir():
                    shutil.copy2(db, self.data_dir / db.name)
            if new_chromadb.is_dir():
                shutil.copytree(new_chromadb, self.data_dir / "chromadb")
            for sub in ("plans", "plugins"):
                src = staging / sub
                if src.is_dir():
                    shutil.copytree(src, self.data_dir / sub)

            # Optional config restore.
            if options.apply_config:
                src_cfg = staging / "config"
                if src_cfg.is_dir():
                    dest_cfg = self.project_root / "config"
                    dest_cfg.mkdir(parents=True, exist_ok=True)
                    for f in src_cfg.iterdir():
                        if f.is_file():
                            shutil.copy2(f, dest_cfg / f.name)

            # Optional source-directory restore is not auto-applied: the
            # user's existing watch-dir paths may differ from the backup
            # producer's.  We unpack into a parking lot the user can move
            # into place manually.
            if options.apply_sources:
                src_dirs = staging / "sources"
                if src_dirs.is_dir():
                    parking = self.data_dir / "restored-sources"
                    if parking.exists():
                        shutil.rmtree(parking)
                    shutil.copytree(src_dirs, parking)

        except Exception:
            # Roll back: wipe anything we just wrote, restore the stash.
            for entry in list(self.data_dir.iterdir()):
                if entry.name in _EXCLUDE_TOP_LEVEL:
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
            for entry in backup_old.iterdir():
                shutil.move(str(entry), str(self.data_dir / entry.name))
            raise
        else:
            # Success — drop the stash.
            shutil.rmtree(backup_old, ignore_errors=True)

    def _write_restart_marker(self, manifest: dict, current_embedding_model: str = "") -> None:
        backup_model = manifest.get("embedding_model", "")
        model_mismatch = bool(
            backup_model and current_embedding_model
            and backup_model != current_embedding_model
        )
        marker = self.data_dir / RESTART_MARKER
        marker.write_text(json.dumps({
            "restored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "from_backup_id": manifest.get("id"),
            "from_backup_created_at": manifest.get("created_at"),
            "from_mdkb_version": manifest.get("mdkb_version"),
            "backup_embedding_model": backup_model,
            "current_embedding_model": current_embedding_model,
            "model_mismatch": model_mismatch,
        }, indent=2))


def _is_newer(a: str, b: str) -> bool:
    """Return True if version string a > b under loose semver."""
    def parts(v):
        return tuple(int(x) for x in v.split(".") if x.isdigit())
    try:
        return parts(a) > parts(b)
    except ValueError:
        return False


def _safe_extractall(tf: tarfile.TarFile, dest: Path) -> None:
    """Extract a tarball, refusing path traversal and symlink attacks.

    Python 3.12+ provides tarfile.data_filter which blocks absolute paths,
    ``..`` components, and symlinks pointing outside the destination — use it
    when available.  On older Python the manual name check still runs as a
    fallback, but symlinks are additionally rejected explicitly.
    """
    dest = dest.resolve()

    # Prefer the native filter introduced in Python 3.12 (PEP 706).
    # filter='data' strips special files, blocks absolute/traversal paths,
    # and prevents symlinks from pointing outside dest.
    if hasattr(tarfile, "data_filter"):
        tf.extractall(dest, filter="data")
        return

    # Fallback for Python < 3.12: manual checks + explicit symlink rejection.
    for member in tf.getmembers():
        if member.issym() or member.islnk():
            raise RestoreError(
                f"archive contains symlink (not allowed): {member.name}"
            )
        target = (dest / member.name).resolve()
        try:
            target.relative_to(dest)
        except ValueError as exc:
            raise RestoreError(
                f"archive contains unsafe path: {member.name}"
            ) from exc
    tf.extractall(dest)

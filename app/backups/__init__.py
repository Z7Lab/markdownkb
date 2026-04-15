"""Full-state backup and restore for MarkdownKB.

Produces a portable .tar.gz containing all SQLite databases, the ChromaDB
vector store, plugin data, and (optionally) configuration.  Secrets and
embedding model weights are excluded by default.

Restore is staged: archive is extracted to a temp dir, validated against
its manifest, then atomically swapped into place.  The running app writes
a ``.restart-required`` marker; the user restarts the container to pick
up the new state.
"""

from app.backups.manager import BackupManager, BackupError, RestoreError, MANIFEST_NAME

__all__ = ["BackupManager", "BackupError", "RestoreError", "MANIFEST_NAME"]

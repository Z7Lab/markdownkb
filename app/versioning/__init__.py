"""Versioning — git-backed revision history for writable sources.

Maintains a separate git repo per writable source under
``{data_dir}/versioning/<source-hash>/.git``, with ``--work-tree``
pointing at the actual source directory. mdkb is the only writer;
users never see these repos unless they explicitly export them.

Commits are author=``mdkb <mdkb@localhost>`` so a future collapse into
a user-owned repo stays distinguishable.
"""

from app.versioning.git_manager import GitManager, GitManagerError

__all__ = ["GitManager", "GitManagerError"]

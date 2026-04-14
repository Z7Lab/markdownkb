"""Per-source git repository manager.

One managed repo per writable source, stored under
``{data_dir}/versioning/<source-hash>/.git`` with ``--work-tree``
pointing at the live source directory. Uses subprocess-to-git — no
native dependency, no library surface to track.

Thread-safety: each public method takes a per-source lock before
invoking git, so concurrent writers (write_api + wiki_compile) on the
same source serialize their commits.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Sentinel author so commits are distinguishable if a user later folds
# this history into their own repo.
_AUTHOR_NAME = "mdkb"
_AUTHOR_EMAIL = "mdkb@localhost"

# Default ignore rules written into info/exclude on repo init.
_DEFAULT_EXCLUDES = [
    "# mdkb-managed — do not edit",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "node_modules/",
    ".venv/",
    ".pytest_cache/",
]


class GitManagerError(Exception):
    """Raised when a git operation fails."""


@dataclass(frozen=True)
class Commit:
    sha: str
    author_date: str  # ISO-8601
    subject: str


class GitManager:
    """Manage per-source git repositories under ``{root}/<source-hash>/``.

    The manager is a singleton created at app startup (``lifespan``) and
    shared across all writers. Call ``ensure_repo(source_path)`` before
    the first commit for a source; ``commit()`` is safe to call
    repeatedly.
    """

    def __init__(self, root: Path):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---------- public API ----------

    def ensure_repo(self, source_path: str | Path) -> Path:
        """Initialise the managed repo for ``source_path`` if needed.

        Returns the managed repo directory (``{root}/<hash>/``). The
        ``.git`` dir lives inside it; the work-tree is the source dir.
        """
        source = Path(source_path).resolve()
        if not source.is_dir():
            raise GitManagerError(f"source is not a directory: {source}")

        repo_dir = self._repo_dir(source)
        git_dir = repo_dir / ".git"
        if git_dir.is_dir():
            return repo_dir

        repo_dir.mkdir(parents=True, exist_ok=True)
        self._run_raw(
            ["git", "init", "--quiet", "--initial-branch=main",
             f"--separate-git-dir={git_dir}", str(source)],
        )
        # `init --separate-git-dir` leaves a .git *file* in the source
        # directory pointing at the real gitdir. Remove it — we don't
        # want mdkb's versioning visible inside the source.
        source_gitfile = source / ".git"
        if source_gitfile.is_file():
            source_gitfile.unlink()
        # Also strip the worktree reference git stores in the gitdir.
        # When .git/config has `core.worktree = <source>` we're fine —
        # that's what lets `--git-dir` + `--work-tree` work cleanly.
        self._git(source, ["config", "user.name", _AUTHOR_NAME])
        self._git(source, ["config", "user.email", _AUTHOR_EMAIL])
        # Sentinel marker so operators can identify mdkb-managed repos.
        (repo_dir / "MDKB_MANAGED").write_text(
            f"This git repository is managed by mdkb.\nSource: {source}\n",
            encoding="utf-8",
        )
        # Seed info/exclude with sensible defaults.
        exclude_file = git_dir / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        exclude_file.write_text("\n".join(_DEFAULT_EXCLUDES) + "\n", encoding="utf-8")
        logger.info("versioning: initialised repo for %s at %s", source, git_dir)
        return repo_dir

    def commit(
        self,
        source_path: str | Path,
        message: str,
        paths: list[str | Path] | None = None,
    ) -> str | None:
        """Stage and commit changes. Returns the new commit SHA, or
        None when there was nothing to commit.

        ``paths`` are interpreted relative to the source dir. When
        omitted, stages every change under the source.
        """
        source = Path(source_path).resolve()
        self.ensure_repo(source)

        with self._lock_for(source):
            try:
                if paths:
                    rel = [str(self._relative(source, p)) for p in paths]
                    self._git(source, ["add", "--"] + rel)
                else:
                    self._git(source, ["add", "-A"])

                # Did anything actually stage?
                status = self._git(source, ["status", "--porcelain"]).strip()
                if not status:
                    return None

                self._git(source, [
                    "-c", f"user.name={_AUTHOR_NAME}",
                    "-c", f"user.email={_AUTHOR_EMAIL}",
                    "commit", "--quiet", "--allow-empty-message",
                    "-m", message or "",
                ])
                sha = self._git(source, ["rev-parse", "HEAD"]).strip()
                logger.debug("versioning: committed %s at %s (%s)", sha[:8], source, message)
                return sha
            except GitManagerError:
                raise
            except Exception as exc:
                raise GitManagerError(f"commit failed for {source}: {exc}") from exc

    def log_for_file(
        self,
        source_path: str | Path,
        relative_file: str,
        limit: int = 100,
    ) -> list[Commit]:
        """Return commits that touched ``relative_file``, newest first."""
        source = Path(source_path).resolve()
        if not (self._repo_dir(source) / ".git").is_dir():
            return []
        with self._lock_for(source):
            try:
                raw = self._git(source, [
                    "log",
                    f"-n{limit}",
                    "--pretty=format:%H%x1f%aI%x1f%s",
                    "--", relative_file,
                ])
            except GitManagerError:
                return []
        commits: list[Commit] = []
        for line in raw.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 3:
                continue
            commits.append(Commit(sha=parts[0], author_date=parts[1], subject=parts[2]))
        return commits

    def show_file_at(
        self,
        source_path: str | Path,
        commit_sha: str,
        relative_file: str,
    ) -> str | None:
        """Return the file contents at ``commit_sha``, or None when the
        file didn't exist at that revision.
        """
        source = Path(source_path).resolve()
        if not (self._repo_dir(source) / ".git").is_dir():
            return None
        with self._lock_for(source):
            try:
                return self._git(
                    source, ["show", f"{commit_sha}:{relative_file}"]
                )
            except GitManagerError:
                return None

    def diff_file(
        self,
        source_path: str | Path,
        commit_sha: str,
        relative_file: str,
    ) -> str:
        """Return the unified diff of ``relative_file`` between
        ``commit_sha`` and its first parent. Empty string when no diff.
        """
        source = Path(source_path).resolve()
        if not (self._repo_dir(source) / ".git").is_dir():
            return ""
        with self._lock_for(source):
            try:
                return self._git(source, [
                    "diff", "--no-color", f"{commit_sha}^!", "--", relative_file,
                ])
            except GitManagerError:
                return ""

    def restore_file(
        self,
        source_path: str | Path,
        commit_sha: str,
        relative_file: str,
    ) -> str | None:
        """Restore ``relative_file`` to its contents at ``commit_sha``
        by writing those contents back and creating a new commit.
        Returns the new commit SHA, or None when the restore was a
        no-op.
        """
        source = Path(source_path).resolve()
        dest = source / relative_file
        contents = self.show_file_at(source, commit_sha, relative_file)
        if contents is None:
            raise GitManagerError(
                f"file {relative_file} does not exist at {commit_sha[:8]}"
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        return self.commit(
            source,
            f"restore {relative_file} from {commit_sha[:8]}",
            paths=[relative_file],
        )

    def repo_dir(self, source_path: str | Path) -> Path:
        """Return the managed repo dir for a source (may not exist yet)."""
        return self._repo_dir(Path(source_path).resolve())

    # ---------- internals ----------

    def _repo_dir(self, source: Path) -> Path:
        digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:16]
        return self._root / digest

    def _lock_for(self, source: Path) -> threading.Lock:
        key = str(source)
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _git(self, source: Path, args: list[str]) -> str:
        """Run a git command with --git-dir + --work-tree bound to this source."""
        git_dir = self._repo_dir(source) / ".git"
        cmd = ["git", f"--git-dir={git_dir}", f"--work-tree={source}"] + args
        return self._run_raw(cmd)

    @staticmethod
    def _relative(source: Path, p: str | Path) -> Path:
        pp = Path(p)
        if pp.is_absolute():
            try:
                return pp.resolve().relative_to(source)
            except ValueError as exc:
                raise GitManagerError(
                    f"{pp} is not under source {source}"
                ) from exc
        return pp

    @staticmethod
    def _run_raw(cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise GitManagerError("git is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise GitManagerError(
                f"git {' '.join(cmd[3:]) or cmd[1]} failed: {exc.stderr.strip() or exc}"
            ) from exc
        return result.stdout

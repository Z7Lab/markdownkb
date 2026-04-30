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


def _parse_ident(ident: str) -> tuple[str, str, str]:
    """Split a git ident line `Name <email> <unix-ts> +tz` into components.

    Returns (name, email, date_string_in_git_format). Best-effort — malformed
    idents fall back to empty strings.
    """
    lt = ident.rfind("<")
    gt = ident.rfind(">")
    if lt < 0 or gt < 0 or gt < lt:
        return (ident.strip(), "", "")
    name = ident[:lt].strip()
    email = ident[lt + 1:gt].strip()
    when = ident[gt + 1:].strip()
    return (name, email, when)


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

    def repo_exists(self, source_path: str | Path) -> bool:
        """True when the managed repo has been initialised for this source."""
        return (self._repo_dir(Path(source_path).resolve()) / ".git").is_dir()

    def repo_stats(self, source_path: str | Path) -> dict:
        """Return {commit_count, last_commit_date, size_bytes} for a source.

        Returns zeros/None when the managed repo doesn't exist yet.
        """
        source = Path(source_path).resolve()
        result = {
            "initialised": False,
            "commit_count": 0,
            "last_commit_date": None,
            "size_bytes": 0,
        }
        repo_dir = self._repo_dir(source)
        if not (repo_dir / ".git").is_dir():
            return result
        result["initialised"] = True
        with self._lock_for(source):
            try:
                count = self._git(source, ["rev-list", "--all", "--count"]).strip()
                result["commit_count"] = int(count or 0)
            except GitManagerError:
                pass
            if result["commit_count"] > 0:
                try:
                    result["last_commit_date"] = self._git(
                        source, ["log", "-1", "--pretty=format:%aI"],
                    ).strip()
                except GitManagerError:
                    pass
        # Directory size (git objects + working-tree metadata, not the source).
        total = 0
        try:
            for p in repo_dir.rglob("*"):
                if p.is_file():
                    try:
                        total += p.stat().st_size
                    except OSError:
                        continue
        except OSError:
            pass
        result["size_bytes"] = total
        return result

    def prune(
        self,
        source_path: str | Path,
        *,
        keep_last_n: int | None = None,
        older_than_days: int | None = None,
    ) -> dict:
        """Discard old history and run aggressive GC.

        Exactly one of ``keep_last_n`` or ``older_than_days`` must be
        supplied. The operation rewrites the single branch so the oldest
        surviving commit has no parent — this is a destructive reset,
        appropriate for mdkb-managed repos where nothing external refs
        the old SHAs.

        Returns {commits_before, commits_after, size_before, size_after}.
        """
        if (keep_last_n is None) == (older_than_days is None):
            raise GitManagerError("prune requires exactly one of keep_last_n or older_than_days")
        source = Path(source_path).resolve()
        if not (self._repo_dir(source) / ".git").is_dir():
            raise GitManagerError(f"no managed repo for {source}")

        before = self.repo_stats(source)
        with self._lock_for(source):
            # Figure out which commit becomes the new root.
            if keep_last_n is not None:
                if keep_last_n < 1:
                    raise GitManagerError("keep_last_n must be >= 1")
                raw = self._git(source, [
                    "log", "--pretty=format:%H", f"-n{keep_last_n}",
                ]).strip().splitlines()
                if not raw:
                    raise GitManagerError("no commits to prune")
                new_root_sha = raw[-1]
            else:
                # older_than_days: keep everything newer than cutoff.
                raw = self._git(source, [
                    "log", "--pretty=format:%H %aI",
                    f"--since={older_than_days}.days.ago",
                ]).strip().splitlines()
                if not raw:
                    raise GitManagerError(
                        f"no commits newer than {older_than_days} days — "
                        "refusing to wipe entire history"
                    )
                new_root_sha = raw[-1].split()[0]

            # Rewrite so new_root_sha has no parent. Grafts are the
            # traditional way but `replace --graft` + `filter-repo` isn't
            # available in slim images; use the parent-rewriting pattern
            # via `git commit-tree` in a loop — simple, no deps.
            self._rewrite_from(source, new_root_sha)

            # Aggressively GC unreachable objects.
            self._git(source, [
                "reflog", "expire", "--expire=now", "--all",
            ])
            self._git(source, ["gc", "--prune=now", "--aggressive"])

        after = self.repo_stats(source)
        return {
            "commits_before": before["commit_count"],
            "commits_after": after["commit_count"],
            "size_before": before["size_bytes"],
            "size_after": after["size_bytes"],
        }

    def _rewrite_from(self, source: Path, new_root_sha: str) -> None:
        """Rewrite HEAD's branch so ``new_root_sha`` becomes the root.

        Walks from HEAD down to new_root_sha, recreating each commit
        with the new parent chain. Leaves HEAD pointing at the rewritten
        tip.
        """
        # Collect shas from HEAD back to new_root_sha (inclusive), newest first.
        chain = self._git(source, [
            "log", "--pretty=format:%H", f"{new_root_sha}..HEAD",
        ]).strip().splitlines()
        # chain is HEAD-first; we need to rebuild oldest-first so we know parents.
        chain.reverse()

        # Recreate new_root_sha with no parent.
        new_sha = self._recreate_commit(source, new_root_sha, parents=[])
        for sha in chain:
            new_sha = self._recreate_commit(source, sha, parents=[new_sha])

        # Point main (or whatever branch HEAD is on) at the new tip.
        branch = self._git(source, ["symbolic-ref", "--short", "HEAD"]).strip() or "main"
        self._git(source, ["update-ref", f"refs/heads/{branch}", new_sha])

    def _recreate_commit(self, source: Path, sha: str, parents: list[str]) -> str:
        """Recreate a commit with a new parent list, preserving tree/author/message."""
        tree = self._git(source, ["rev-parse", f"{sha}^{{tree}}"]).strip()
        # Author + committer + message come from cat-file.
        raw = self._git(source, ["cat-file", "commit", sha])
        # Parse headers until blank line.
        headers: list[tuple[str, str]] = []
        body_lines: list[str] = []
        in_body = False
        for line in raw.splitlines():
            if in_body:
                body_lines.append(line)
            elif not line:
                in_body = True
            else:
                key, _, val = line.partition(" ")
                headers.append((key, val))
        def find(k: str) -> str:
            for hk, hv in headers:
                if hk == k:
                    return hv
            return ""
        author = find("author")
        committer = find("committer")
        message = "\n".join(body_lines)

        env_extra = {}
        if author:
            name, email, when = _parse_ident(author)
            env_extra.update({
                "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": when,
            })
        if committer:
            name, email, when = _parse_ident(committer)
            env_extra.update({
                "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": when,
            })

        args = ["commit-tree", tree]
        for p in parents:
            args.extend(["-p", p])
        return self._git_with_env(source, args, input_text=message, env_extra=env_extra).strip()

    # ---------- ignore ----------

    def get_ignore(self, source_path: str | Path) -> str:
        """Return the contents of the managed repo's info/exclude file."""
        source = Path(source_path).resolve()
        path = self._repo_dir(source) / ".git" / "info" / "exclude"
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def set_ignore(self, source_path: str | Path, contents: str) -> None:
        """Overwrite the managed repo's info/exclude file."""
        source = Path(source_path).resolve()
        self.ensure_repo(source)
        path = self._repo_dir(source) / ".git" / "info" / "exclude"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents if contents.endswith("\n") else contents + "\n",
                        encoding="utf-8")

    # ---------- export ----------

    def export_tarball(self, source_path: str | Path, dest_path: Path) -> Path:
        """Write a .tar.gz of the managed repo dir to ``dest_path``.

        The archive contains just the `.git` dir (enough to re-hydrate
        history elsewhere). Returns the dest path on success.
        """
        import tarfile
        source = Path(source_path).resolve()
        repo_dir = self._repo_dir(source)
        if not (repo_dir / ".git").is_dir():
            raise GitManagerError(f"no managed repo for {source}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_for(source):
            with tarfile.open(dest_path, "w:gz") as tar:
                tar.add(repo_dir / ".git", arcname=".git")
                marker = repo_dir / "MDKB_MANAGED"
                if marker.exists():
                    tar.add(marker, arcname="MDKB_MANAGED")
        return dest_path

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

    def _git_with_env(
        self,
        source: Path,
        args: list[str],
        *,
        input_text: str | None = None,
        env_extra: dict | None = None,
    ) -> str:
        """Run a git command with optional stdin and env additions."""
        import os
        git_dir = self._repo_dir(source) / ".git"
        cmd = ["git", f"--git-dir={git_dir}", f"--work-tree={source}"] + args
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding="utf-8",
                input=input_text, env=env, timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitManagerError(
                f"git {args[0]} timed out after 120s"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise GitManagerError(
                f"git {args[0]} failed: {exc.stderr.strip() or exc}"
            ) from exc
        return result.stdout

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
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitManagerError(
                f"git {' '.join(cmd[1:3])} timed out after 120s"
            ) from exc
        except FileNotFoundError as exc:
            raise GitManagerError("git is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise GitManagerError(
                f"git {' '.join(cmd[3:]) or cmd[1]} failed: {exc.stderr.strip() or exc}"
            ) from exc
        return result.stdout

"""Detect install method and check for newer mdkb releases.

The check itself is one HTTP request to either:
  - PyPI JSON (native pip installs)
  - GitHub releases (Docker installs and dev checkouts both use the same
    GitHub project as the canonical version source — Docker tags lag GitHub
    releases by minutes, and the Docker registry doesn't expose a clean
    "latest version string" without an authenticated digest dance)

If the user is in a dev checkout, we also tell them how far ahead/behind
their local branch is, since "latest GitHub tag" may be older than what
they've already pulled.
"""

from __future__ import annotations

import enum
import logging
import os
import re
import subprocess
import urllib.request
import urllib.error
import json
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

GITHUB_RELEASES_API = "https://api.github.com/repos/{repo}/releases/latest"
PYPI_JSON_API = "https://pypi.org/pypi/{name}/json"

GITHUB_REPO = os.environ.get("MARKDOWNKB_GITHUB_REPO", "anthropics/markdownkb")
PYPI_NAME = os.environ.get("MARKDOWNKB_PYPI_NAME", "markdownkb")

REQUEST_TIMEOUT = 5.0


class InstallMethod(str, enum.Enum):
    DOCKER = "docker"
    NATIVE = "native"
    DEV = "dev"


@dataclass
class UpdateInfo:
    install_method: InstallMethod
    current_version: str
    latest_version: str | None
    update_available: bool
    release_url: str | None
    apply_command: str
    error: str | None = None
    # For dev: how many commits ahead/behind upstream we are
    dev_ahead: int | None = None
    dev_behind: int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["install_method"] = self.install_method.value
        return d


def detect_install_method() -> InstallMethod:
    """Identify how mdkb was installed in this environment."""
    if Path("/.dockerenv").exists() or os.environ.get("MARKDOWNKB_DATA_DIR", "").startswith("/data"):
        return InstallMethod.DOCKER
    repo_root = Path(__file__).resolve().parent.parent.parent
    if (repo_root / ".git").is_dir():
        return InstallMethod.DEV
    return InstallMethod.NATIVE


def check_for_update(current_version: str) -> UpdateInfo:
    """One-shot version check.  Never raises — errors land in the result."""
    method = detect_install_method()
    try:
        if method is InstallMethod.NATIVE:
            return _check_native(current_version)
        if method is InstallMethod.DEV:
            return _check_dev(current_version)
        return _check_docker(current_version)
    except Exception as exc:
        logger.warning("update check failed: %s", exc)
        return UpdateInfo(
            install_method=method,
            current_version=current_version,
            latest_version=None,
            update_available=False,
            release_url=None,
            apply_command=_apply_command(method),
            error=str(exc),
        )


def _check_native(current: str) -> UpdateInfo:
    url = PYPI_JSON_API.format(name=PYPI_NAME)
    data = _fetch_json(url)
    latest = data.get("info", {}).get("version")
    return UpdateInfo(
        install_method=InstallMethod.NATIVE,
        current_version=current,
        latest_version=latest,
        update_available=_is_newer(latest, current),
        release_url=f"https://pypi.org/project/{PYPI_NAME}/",
        apply_command=_apply_command(InstallMethod.NATIVE),
    )


def _check_docker(current: str) -> UpdateInfo:
    url = GITHUB_RELEASES_API.format(repo=GITHUB_REPO)
    data = _fetch_json(url)
    latest = (data.get("tag_name") or "").lstrip("v") or None
    release_url = data.get("html_url")
    return UpdateInfo(
        install_method=InstallMethod.DOCKER,
        current_version=current,
        latest_version=latest,
        update_available=_is_newer(latest, current),
        release_url=release_url,
        apply_command=_apply_command(InstallMethod.DOCKER),
    )


def _check_dev(current: str) -> UpdateInfo:
    repo_root = Path(__file__).resolve().parent.parent.parent
    ahead, behind = _git_ahead_behind(repo_root)
    # Also fetch latest GitHub release for context.
    latest = None
    release_url = None
    try:
        data = _fetch_json(GITHUB_RELEASES_API.format(repo=GITHUB_REPO))
        latest = (data.get("tag_name") or "").lstrip("v") or None
        release_url = data.get("html_url")
    except Exception as exc:
        logger.debug("github release lookup failed in dev mode: %s", exc)
    update_available = (behind is not None and behind > 0) or _is_newer(latest, current)
    return UpdateInfo(
        install_method=InstallMethod.DEV,
        current_version=current,
        latest_version=latest,
        update_available=update_available,
        release_url=release_url,
        apply_command=_apply_command(InstallMethod.DEV),
        dev_ahead=ahead,
        dev_behind=behind,
    )


def _apply_command(method: InstallMethod) -> str:
    return {
        InstallMethod.DOCKER: "docker compose pull && make docker-up",
        InstallMethod.NATIVE: f"pip install -U {PYPI_NAME}",
        InstallMethod.DEV: "git pull && make install",
    }[method]


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "markdownkb-update-check"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _git_ahead_behind(repo_root: Path) -> tuple[int | None, int | None]:
    """Return (ahead, behind) commit counts vs the upstream tracking branch."""
    try:
        # Fetch first so the comparison is fresh; suppress output.
        subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "--quiet"],
            check=False, timeout=REQUEST_TIMEOUT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            check=True, timeout=REQUEST_TIMEOUT,
            capture_output=True, text=True,
        )
        ahead, behind = out.stdout.strip().split()
        return int(ahead), int(behind)
    except Exception as exc:
        logger.debug("git ahead/behind failed: %s", exc)
        return None, None


_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _is_newer(candidate: str | None, current: str) -> bool:
    if not candidate:
        return False
    cand = _parse(candidate)
    cur = _parse(current)
    return cand > cur


def _parse(v: str) -> tuple[int, ...]:
    m = _VERSION_RE.match(v.lstrip("v"))
    if not m:
        return (0, 0, 0)
    return tuple(int(g) if g else 0 for g in m.groups())

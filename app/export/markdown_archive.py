"""Build a zip/staging-dir of every indexed markdown file.

Three content sources:
  sources/  — files tracked in indexed_files (status=complete, include_in_index=1)
  buckets/  — documents reconstructed from ChromaDB bucket collections
  wikis/    — wiki_compile output from the filesystem
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Generator

from app.ingestion.reconstruct import reconstruct_chunks

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class MarkdownArchiveBuilder:
    def __init__(self, settings: "Settings", bucket_service=None):
        self._settings = settings
        self._bucket_svc = bucket_service

    # ── Public API ──────────────────────────────────────────────────────

    def build_zip(self) -> io.BytesIO:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for archive_path, content in self._iter_all():
                zf.writestr(archive_path, content)
        buf.seek(0)
        return buf

    def add_to_staging(self, staging: Path) -> None:
        """Write markdown files into staging/markdown/ for inclusion in a tar.gz backup."""
        for archive_path, content in self._iter_all():
            dest = staging / "markdown" / archive_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    # ── Iteration ────────────────────────────────────────────────────────

    def _iter_all(self) -> Generator[tuple[str, str], None, None]:
        yield from self._iter_source_files()
        yield from self._iter_bucket_files()
        yield from self._iter_wiki_files()

    def _iter_source_files(self) -> Generator[tuple[str, str], None, None]:
        from app.storage.trackingdb import TrackingDB

        db = TrackingDB(self._settings.data_directory)
        rows = db.get_all_files()

        # Build source_root → archive-dir-name mapping (deduplicate same-named roots)
        roots: dict[str, str] = {}
        name_counts: dict[str, int] = {}
        for row in rows:
            root = row["source_root"]
            if root in roots:
                continue
            base = Path(root).name or "root"
            if base in name_counts:
                name_counts[base] += 1
                roots[root] = f"{base}-{name_counts[base]}"
            else:
                name_counts[base] = 1
                roots[root] = base

        for row in rows:
            if row.get("status") != "complete":
                continue
            if not row.get("include_in_index", 1):
                continue
            path = Path(row["path"])
            if path.suffix.lower() != ".md":
                continue
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            root = row["source_root"]
            dir_name = roots.get(root, Path(root).name or "root")
            try:
                rel = path.relative_to(root)
                archive_path = f"sources/{dir_name}/{rel}"
            except ValueError:
                archive_path = f"sources/{dir_name}/{path.name}"
            yield archive_path, content

    def _iter_bucket_files(self) -> Generator[tuple[str, str], None, None]:
        if not self._bucket_svc:
            return
        try:
            buckets = self._bucket_svc.db.list_all()
        except Exception:
            logger.warning("Could not list buckets for export", exc_info=True)
            return

        for bucket in buckets:
            if bucket.get("expired"):
                continue
            bucket_name = bucket["name"]
            safe_name = (
                "".join(c if c.isalnum() or c in "-_ " else "_" for c in bucket_name)
                .strip()
                .replace(" ", "_")
            ) or "bucket"

            try:
                store = self._bucket_svc.get_store(bucket["id"])
                result = store._collection.get(include=["documents", "metadatas"])
            except Exception:
                logger.warning("Could not read bucket '%s' for export", bucket_name, exc_info=True)
                continue

            # Group chunks by source_path, sorted by chunk_index, then reconstruct
            by_path: dict[str, list[tuple[int, str]]] = {}
            for doc, meta in zip(result["documents"], result["metadatas"]):
                sp = meta.get("source_path", "unknown.md")
                idx = meta.get("chunk_index", 0)
                by_path.setdefault(sp, []).append((idx, doc))

            for source_path, chunks in by_path.items():
                chunks.sort(key=lambda x: x[0])
                content = reconstruct_chunks([doc for _, doc in chunks])
                filename = Path(source_path).name or "document.md"
                if not filename.endswith(".md"):
                    filename += ".md"
                archive_path = f"buckets/{safe_name}/{filename}"
                yield archive_path, content

    def _iter_wiki_files(self) -> Generator[tuple[str, str], None, None]:
        try:
            from app.plugins.wiki_compile.wikidb import WikiDB
        except ImportError:
            return
        try:
            wikidb = WikiDB(self._settings.data_directory)
            wikis = wikidb.list_all()
        except Exception:
            logger.warning("Could not list wikis for export", exc_info=True)
            return

        for wiki in wikis:
            wiki_path = Path(wiki["path"])
            if not wiki_path.is_dir():
                continue
            safe_name = (
                "".join(c if c.isalnum() or c in "-_" else "_" for c in wiki["name"])
            ) or "wiki"
            for md_file in sorted(wiki_path.rglob("*.md")):
                try:
                    content = md_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                try:
                    rel = md_file.relative_to(wiki_path)
                except ValueError:
                    rel = Path(md_file.name)
                archive_path = f"wikis/{safe_name}/{rel}"
                yield archive_path, content

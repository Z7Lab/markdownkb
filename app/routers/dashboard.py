"""Dashboard chart data endpoint."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from app.deps import get_tracking
from app.ratelimit import STANDARD, limiter
from app.storage.trackingdb import TrackingDB

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/charts")
@limiter.limit(STANDARD)
def get_charts(
    request: Request,
    tracking: TrackingDB = Depends(get_tracking),
):
    with tracking._lock:
        docs_over_time = _docs_over_time(tracking)
        docs_by_source = _docs_by_source(tracking)
        richest_files = _richest_files(tracking)

    return {
        "docs_over_time": docs_over_time,
        "docs_by_source": docs_by_source,
        "richest_files": richest_files,
    }


def _docs_over_time(tracking: TrackingDB) -> list[dict]:
    """Count of docs newly indexed per day over the last 14 days."""
    today = date.today()
    days = [(today - timedelta(days=i)) for i in range(13, -1, -1)]

    rows = tracking._conn.execute(
        """
        SELECT DATE(indexed_at) AS day, COUNT(*) AS cnt
        FROM indexed_files
        WHERE status = 'complete'
          AND indexed_at IS NOT NULL
          AND DATE(indexed_at) >= DATE('now', '-13 days')
        GROUP BY DATE(indexed_at)
        """
    ).fetchall()

    counts = {row["day"]: row["cnt"] for row in rows}
    return [
        {"date": d.isoformat(), "count": counts.get(d.isoformat(), 0)}
        for d in days
    ]


def _docs_by_source(tracking: TrackingDB) -> list[dict]:
    """File count per source root directory."""
    rows = tracking._conn.execute(
        """
        SELECT source_root, COUNT(*) AS cnt
        FROM indexed_files
        WHERE status = 'complete'
        GROUP BY source_root
        ORDER BY cnt DESC
        """
    ).fetchall()

    result = []
    for row in rows:
        source = row["source_root"]
        parts = [p for p in source.rstrip("/").split("/") if p]
        label = "/".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else source)
        result.append({"source": source, "label": label, "count": row["cnt"]})
    return result


def _richest_files(tracking: TrackingDB) -> list[dict]:
    """Top 8 files by chunk count (most content-dense)."""
    rows = tracking._conn.execute(
        """
        SELECT path, chunk_count
        FROM indexed_files
        WHERE status = 'complete' AND chunk_count > 0
        ORDER BY chunk_count DESC
        LIMIT 8
        """
    ).fetchall()

    return [
        {
            "path": row["path"],
            "filename": row["path"].split("/")[-1],
            "chunks": row["chunk_count"],
        }
        for row in rows
    ]

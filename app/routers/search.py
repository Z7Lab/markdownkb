"""Search endpoints."""

from fastapi import APIRouter, Depends, Query, Request

from app.deps import get_retriever
from app.rag.retriever import Retriever
from app.ratelimit import HEAVY, STANDARD, limiter
from app.schemas import SearchRequest

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
@limiter.limit(HEAVY)
def search(
    request: Request,
    req: SearchRequest,
    retriever: Retriever = Depends(get_retriever),
):
    results = retriever.search(
        req.query,
        top_k=req.top_k,
        folder_filter=req.folder,
        tag_filter=req.tag,
    )
    return {
        "results": [
            {
                "document": r.document,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in results
        ]
    }


@router.get("/folders")
@limiter.limit(STANDARD)
def get_folders(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
):
    all_folders = retriever.get_unique_folders()
    total = len(all_folders)
    items = all_folders[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/tags")
@limiter.limit(STANDARD)
def get_tags(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
):
    all_tags = retriever.get_unique_tags()
    total = len(all_tags)
    items = all_tags[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}

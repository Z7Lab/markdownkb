"""Export endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from app.deps import get_conversation_history
from app.ratelimit import STANDARD, limiter
from app.schemas import ExportRequest

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export")
@limiter.limit(STANDARD)
def export_conversations(
    request: Request,
    req: ExportRequest,
    conv_history=Depends(get_conversation_history),
):
    history = conv_history.get_history()
    if req.format == "markdown":
        lines = ["# mdkb Conversation Export\n"]
        lines.append(f"*Exported: {datetime.now().isoformat()}*" "\n\n---\n")
        for msg in history:
            role = msg["role"].capitalize()
            lines.append(f"**{role}:** {msg['content']}\n\n")
        return {
            "content": "\n".join(lines),
            "format": "markdown",
        }
    return {
        "content": history,
        "format": "json",
        "exported_at": datetime.now().isoformat(),
    }

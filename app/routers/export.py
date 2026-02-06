"""Export endpoints."""

from datetime import datetime

from fastapi import APIRouter, Request

from app.ratelimit import STANDARD, limiter
from app.schemas import ExportRequest
from app.services.chat_service import conversation_history

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export")
@limiter.limit(STANDARD)
def export_conversations(request: Request, req: ExportRequest):
    history = conversation_history.get_history()
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

"""MCP tool: generate tags for a document using AI."""

from app.config import Settings
from app.rag.retriever import Retriever

TOOL = {
    "name": "generate_tags",
    "feature_flag": None,
    "requires_plugin": "tags",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(
    file_path: str,
    use_similar_docs: bool = True,
    auto_apply: bool = False,
) -> dict:
    """Generate tags for a markdown file using the LLM.

    Reads the file content, optionally checks similar documents for
    tag consistency, and asks the LLM to suggest relevant tags.

    Args:
        file_path: Absolute path to the markdown file.
        use_similar_docs: Check similar docs for existing tags (default True).
        auto_apply: Write suggested tags into the file's frontmatter (default False).
    """
    from app.lib.tag_generator.llm import auto_tag_file_interactive

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    result = auto_tag_file_interactive(
        file_path,
        retriever,
        settings,
        auto_apply=auto_apply,
    )

    # Sync applied tags to TagDB
    applied = auto_apply and result.get("applied")
    if applied:
        tagdb = deps.get("tagdb")
        final_tags = result.get("final_tags", result.get("suggested_tags", []))
        if tagdb and final_tags:
            tagdb.update_tags(file_path, ", ".join(final_tags))

    return {
        "status": result.get("status", "error"),
        "suggested_tags": result.get("suggested_tags", []),
        "existing_tags": result.get("existing_tags", []),
        "similar_tags": result.get("similar_tags", []),
        "applied": applied,
    }

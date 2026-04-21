"""Thin launcher for the MarkdownKB MCP server.

The real implementation lives in :mod:`app.mcp.server`.  This file exists
at the project root so existing entry points (Docker, Makefile, and user
MCP client configurations that reference ``mcp_server.py``) keep working
after the module was moved under the ``app/mcp/`` package.

Run as a separate process alongside the FastAPI app::

    python mcp_server.py                  # stdio transport (default)
    python mcp_server.py --http           # Streamable HTTP on port 9715
    python mcp_server.py --http --port 8000
"""

from app.mcp.server import main

if __name__ == "__main__":
    main()

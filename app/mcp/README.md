# MCP

This package contains the MCP (Model Context Protocol) tool definitions
for MarkdownKB. Tools are auto-discovered by `mcp_server.py` from the `tools/`
sub-package.

## Adding a new tool

Create a new `.py` file in `tools/` with:

```python
TOOL = {
    "name": "my_tool",        # MCP tool name
    "feature_flag": None,     # or "my_tool" to gate via mcp.my_tool in settings
}

_mcp = None  # Injected by register_tools()

def handler(...) -> dict:
    """Tool description shown to MCP clients."""
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    # use deps["settings"], deps["retriever"], etc.
    ...
```

The tool is automatically picked up on the next server restart.

## Directory layout

- `tools/` — MCP tool modules (auto-discovered)
- `tools/__init__.py` — discovery and registration logic
- `scope.py` — scope resolution helper (resolves scope_id → folders_filter + allowed_paths for Retriever)
- `auth.py` — API key middleware for MCP transport (accepts `Authorization: Bearer` or `X-MarkdownKB-Key` header)
- `history.py` — optional history tracking for MCP tool calls

## See also

- [MCP Server](../../docs/reference/mcp-server.md) — full MCP server documentation (tools, transports, authentication)

# Optional MCP adapter

`evaltrim.mcp_adapter.dispatch(tool, arguments)` is a **small** in-process dispatcher. It is not an MCP server, not an IDE, and not required.

Tools: `get_status`, `impacted_tests`, `explain`, `regression_summary`, `suggest_maintenance`.

Wire this to an MCP SDK in your own process if you need it. A full MCP platform is deferred.

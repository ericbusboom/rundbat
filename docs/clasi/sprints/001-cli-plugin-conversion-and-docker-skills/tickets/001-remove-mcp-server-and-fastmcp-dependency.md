---
id: '001'
title: Remove MCP server and FastMCP dependency
status: in-progress
use-cases:
- SUC-003
depends-on: []
github-issue: ''
todo: convert-mcp-to-cli-plugin.md
---

# Remove MCP server and FastMCP dependency

## Description

Delete `server.py` (the FastMCP-based MCP server) and remove the
`mcp[cli]` dependency from pyproject.toml. Replace `rundbat mcp` with
a deprecation shim that prints a message directing users to
`rundbat install`.

The service layer (config.py, database.py, discovery.py, environment.py)
is untouched — only the transport layer is removed. The `_get_container_name`
helper currently in server.py needs to move to database.py or cli.py.

## Acceptance Criteria

- [ ] `server.py` is deleted
- [ ] `mcp[cli]` removed from pyproject.toml dependencies
- [ ] `rundbat mcp` prints deprecation message and exits (not a traceback)
- [ ] `_get_container_name` helper relocated (database.py or cli.py)
- [ ] `pip install -e .` succeeds without mcp dependency
- [ ] Existing service-layer tests still pass

## Testing

- **Existing tests to run**: `pytest tests/unit/` (service layer tests)
- **New tests to write**: None — removal ticket
- **Verification command**: `pip install -e . && rundbat mcp`

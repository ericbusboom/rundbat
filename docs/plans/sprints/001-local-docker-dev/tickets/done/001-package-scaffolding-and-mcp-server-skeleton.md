---
id: '001'
title: Package scaffolding and MCP server skeleton
status: done
use-cases: []
depends-on: []
github-issue: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Package scaffolding and MCP server skeleton

## Description

Set up the Python package structure so that rundbat can be installed via
pipx and run as an MCP server over stdio. This is pure scaffolding — no
business logic, just the skeleton that all other tickets build on.

Creates `pyproject.toml` with the `rundbat` entry point, the `src/rundbat/`
package layout, a FastMCP server instance with stdio transport, and the
test infrastructure (pytest with a Docker-skip marker).

## Acceptance Criteria

- [x] `pyproject.toml` defines a `rundbat` console entry point
- [x] `src/rundbat/__init__.py` exists with version
- [x] `src/rundbat/server.py` creates a FastMCP server and runs stdio transport
- [x] `pipx install -e .` succeeds and `rundbat` command is available
- [x] Running `rundbat` starts the MCP server (connects via stdio)
- [x] `tests/conftest.py` exists with a `requires_docker` pytest marker
- [x] `uv run pytest` runs and passes (even with no tests yet)
- [x] Dependencies: `mcp` (FastMCP SDK), `pyyaml`
- [x] Dev dependencies: `pytest`

## Testing

- **Existing tests to run**: None (first ticket)
- **New tests to write**: `tests/test_server.py` — verify the FastMCP
  server instance exists and has the expected name
- **Verification command**: `uv run pytest`

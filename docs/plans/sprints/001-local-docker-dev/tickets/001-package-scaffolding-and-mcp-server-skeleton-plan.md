---
ticket: "001"
---

# Ticket 001 Plan: Package scaffolding and MCP server skeleton

## Approach

Create the standard Python package layout with `src/` structure, a
`pyproject.toml` using hatchling as the build backend, and a FastMCP
server with stdio transport. Keep it minimal — just enough to install
and run.

## Files to Create

- `pyproject.toml` — Package metadata, entry point, dependencies
- `src/rundbat/__init__.py` — Version string
- `src/rundbat/server.py` — FastMCP server instance and main entry point
- `tests/__init__.py` — Empty (marks as package)
- `tests/conftest.py` — pytest config with `requires_docker` marker
- `tests/unit/__init__.py` — Empty
- `tests/unit/test_server.py` — Verify server instance exists

## Key Decisions

- Use `hatchling` as build backend (matches CLASI pattern)
- Use `src/` layout (best practice for pipx-installable packages)
- Entry point: `rundbat = "rundbat.server:main"`
- FastMCP server name: `"rundbat"`
- stdio transport (confirmed in architecture decisions)

## Testing Plan

- `tests/unit/test_server.py`: Import the server instance, verify it
  exists and has name "rundbat"
- Run with `uv run pytest`

## Documentation Updates

None for this ticket.

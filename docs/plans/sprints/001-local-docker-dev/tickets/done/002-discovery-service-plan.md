---
ticket: "002"
---

# Ticket 002 Plan: Discovery Service

## Approach

Create `src/rundbat/discovery.py` with functions that probe for OS,
Docker, dotconfig, and Node.js. Each probe is a separate function that
catches subprocess failures gracefully. Register `discover_system` and
`verify_docker` as MCP tools on the server.

## Files to Create or Modify

- `src/rundbat/discovery.py` — New: detection functions
- `src/rundbat/server.py` — Modify: import and register discovery tools
- `tests/unit/test_discovery.py` — New: unit tests with mocked subprocess

## Testing Plan

- Mock subprocess.run to simulate missing/present commands
- Test OS detection (always works, uses platform module)
- Test Docker info parsing
- Test graceful handling of FileNotFoundError

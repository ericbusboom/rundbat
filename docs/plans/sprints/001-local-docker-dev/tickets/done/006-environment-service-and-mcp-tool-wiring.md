---
id: '006'
title: Environment Service and MCP tool wiring
status: in-progress
use-cases:
- SUC-003
- SUC-004
- SUC-005
- SUC-006
depends-on:
- '003'
- '004'
- '005'
github-issue: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Environment Service and MCP tool wiring

## Description

Implement the Environment Service — the orchestration layer that
coordinates Config Service, Database Service, and Project Installer to
provide the high-level workflows: `create_environment`,
`get_environment_config`, and `validate_environment`.

This ticket also wires all remaining MCP tools onto the server and
verifies the complete tool surface works end-to-end.

Key behaviors:
- `create_environment("dev", type="local-docker")` — generates password,
  determines port, saves config via Config Service, starts container via
  Database Service, verifies connectivity, returns connection string
- `get_environment_config("dev")` — loads config, calls ensure_running,
  checks drift, assembles response. Single call, complete answer.
- `validate_environment("dev")` — full validation: config completeness,
  secret presence, container status, connectivity

## Acceptance Criteria

- [x] `src/rundbat/environment.py` module with Environment Service
- [x] `create_environment(name, type)` MCP tool
  - [x] Generates secure password via `secrets` module
  - [x] Allocates port (5432 default, auto-increment on conflict)
  - [x] Saves database config to rundbat.yaml via Config Service
  - [x] Saves DATABASE_URL to secrets via Config Service
  - [x] Starts container via Database Service
  - [x] Verifies connectivity
  - [x] Returns connection string and container details
- [x] `get_environment_config(env)` MCP tool
  - [x] Loads config from dotconfig
  - [x] Calls ensure_running (auto-restart or recreate)
  - [x] Checks for app name drift
  - [x] Returns connection string, container status, notes, warnings
  - [x] Single tool call — no multi-step interaction
- [x] `validate_environment(env)` MCP tool
  - [x] Checks config completeness
  - [x] Checks secret presence
  - [x] Checks container status
  - [x] Checks connectivity
  - [x] Returns pass/fail with details for each check
- [x] `init_project` (from ticket 003) calls Project Installer after
      saving config
- [x] All MCP tools registered on the server and accessible via stdio
- [x] Complete tool list matches spec §6: discover_system, verify_docker,
      init_project, create_environment, set_secret, validate_environment,
      get_environment_config, start_database, stop_database, health_check,
      check_config_drift

## Testing

- **Existing tests to run**: `uv run pytest` (all previous ticket tests)
- **New tests to write**: `tests/test_environment.py`
  - Test create_environment flow (mock Config + Database services)
  - Test get_environment_config with stopped container (mock ensure_running)
  - Test get_environment_config with missing container (mock recreate + warning)
  - Test drift detection integrated into get_environment_config
  - Integration tests (marked `requires_docker` + `requires_dotconfig`):
    - Full end-to-end: init_project → create_environment → stop → get_config
    - Port conflict: create two environments, verify different ports
- **Verification command**: `uv run pytest`

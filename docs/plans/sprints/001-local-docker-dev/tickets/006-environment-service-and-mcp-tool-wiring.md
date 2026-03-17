---
id: "006"
title: "Environment Service and MCP tool wiring"
status: todo
use-cases:
  - SUC-003
  - SUC-004
  - SUC-005
  - SUC-006
depends-on:
  - "003"
  - "004"
  - "005"
github-issue: ""
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

- [ ] `src/rundbat/environment.py` module with Environment Service
- [ ] `create_environment(name, type)` MCP tool
  - [ ] Generates secure password via `secrets` module
  - [ ] Allocates port (5432 default, auto-increment on conflict)
  - [ ] Saves database config to rundbat.yaml via Config Service
  - [ ] Saves DATABASE_URL to secrets via Config Service
  - [ ] Starts container via Database Service
  - [ ] Verifies connectivity
  - [ ] Returns connection string and container details
- [ ] `get_environment_config(env)` MCP tool
  - [ ] Loads config from dotconfig
  - [ ] Calls ensure_running (auto-restart or recreate)
  - [ ] Checks for app name drift
  - [ ] Returns connection string, container status, notes, warnings
  - [ ] Single tool call — no multi-step interaction
- [ ] `validate_environment(env)` MCP tool
  - [ ] Checks config completeness
  - [ ] Checks secret presence
  - [ ] Checks container status
  - [ ] Checks connectivity
  - [ ] Returns pass/fail with details for each check
- [ ] `init_project` (from ticket 003) calls Project Installer after
      saving config
- [ ] All MCP tools registered on the server and accessible via stdio
- [ ] Complete tool list matches spec §6: discover_system, verify_docker,
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

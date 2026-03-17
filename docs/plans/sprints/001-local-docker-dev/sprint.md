---
id: "001"
title: "Local Docker Dev"
status: active
branch: sprint/001-local-docker-dev
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
  - SUC-006
  - SUC-007
  - SUC-008
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001: Local Docker Dev

## Goals

Deliver the minimum viable rundbat MCP server: a Python package that an
AI agent can call to discover the system, initialize a project, create a
local Docker Postgres environment, manage secrets via dotconfig, and
reliably retrieve connection strings across sessions — with automatic
container recovery and port conflict handling.

## Problem

Agents setting up local dev databases for Node/Postgres apps must run
ad-hoc Docker and dotconfig commands. This is error-prone, inconsistent
across sessions (containers stop, get pruned), and requires the agent to
know Docker internals. There is no single tool call that gives back a
working connection string with health verification.

## Solution

Build a Python MCP server (installed via pipx) that exposes tools for:
system discovery, project initialization, local environment creation
with auto-generated credentials, secret storage via dotconfig, database
container lifecycle management, and a single `get_environment_config`
tool that loads config, verifies liveness, auto-restarts stopped
containers, and returns a connection string.

## Success Criteria

- `discover_system` returns accurate OS, Docker, dotconfig, and Node status
- `init_project` creates `rundbat.yaml` via dotconfig with app name and source,
  and installs `.mcp.json` entry, `.claude/rules/rundbat.md`, and
  `UserPromptSubmit` hook into the target project (merge, not overwrite)
- `create_environment("dev", type="local-docker")` provisions a Postgres
  container and returns a verified connection string
- Secrets are stored encrypted via dotconfig load/edit/save cycle
- `get_environment_config("dev")` returns connection info, auto-restarting
  stopped containers
- Port conflicts are detected and resolved automatically
- Missing containers are recreated from config with a data-loss warning
- App name drift is detected and reported
- All tools are accessible as MCP tools from a Claude Code session

## Scope

### In Scope

- Python package structure (pipx-installable, MCP server entry point)
- MCP tool implementations:
  - `discover_system` — OS, Docker, dotconfig, Node detection
  - `verify_docker` — confirm `docker info` succeeds
  - `init_project(app_name, app_name_source)` — initialize rundbat config
  - `create_environment(name, type="local-docker")` — provision local
    Postgres with credential generation and port allocation
  - `set_secret(env, key, value)` — write secrets via dotconfig
  - `validate_environment(env)` — full validation of config and services
  - `get_environment_config(env)` — load config, health check, auto-recover
  - `start_database(env)` / `stop_database(env)` — container lifecycle
  - `health_check(env)` — database reachability check
  - `check_config_drift` — app name drift detection
- Project Installer: merge rundbat MCP entry into `.mcp.json`, install
  `.claude/rules/rundbat.md` rule file, merge `UserPromptSubmit` hook
  into `.claude/settings.json` — all read-merge-write, never overwrite
- dotconfig integration (subprocess calls for load/save)
- `rundbat.yaml` schema (app_name, app_name_source, notes, database section)
- Database naming convention: `rundbat_{app_name}_{env}`
- Container naming convention: `rundbat-{app_name}-{env}-pg`
- Stale state recovery (stopped → restart, missing → recreate with warning)
- Port conflict detection and auto-allocation

### Out of Scope

- Docker installation (Phase 2)
- Remote environments (Phase 3)
- CI/CD integration (Phase 4)
- `start_app` / `stop_app` (not needed for local dev database focus)
- `build_container` / `push_container` / `deploy` (Phase 3)
- Knowledge/skill serving (`get_deploy_skill`, `get_deploy_agent`)
- Multiple database engines (Postgres only)

## Test Strategy

- **Unit tests** for config parsing, naming conventions, port allocation
  logic, and discovery detection functions.
- **Integration tests** using Docker to verify container creation, start,
  stop, health check, and recreation. These require Docker to be running.
- **MCP protocol tests** to verify tool registration and parameter
  validation.
- Tests use pytest. Docker-dependent tests are marked so they can be
  skipped in environments without Docker.

## Architecture Notes

See `architecture.md` in this sprint directory for full details. Key
decisions:

- Single Python package with CLI entry point that serves MCP
- Thin wrapper around Docker CLI (`docker run`, `docker start`, etc.)
  rather than Docker SDK — keeps dependencies minimal
- dotconfig called as subprocess, not imported as library
- State stored in `rundbat.yaml` via dotconfig, not in a separate database

## GitHub Issues

None yet.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Use Cases |
|---|-------|-----------|-----------|
| 001 | Package scaffolding and MCP server skeleton | — | — |
| 002 | Discovery Service | 001 | SUC-001 |
| 003 | Config Service | 001 | SUC-002, SUC-006, SUC-007 |
| 004 | Database Service | 001 | SUC-003, SUC-004, SUC-005 |
| 005 | Project Installer | 001 | SUC-008 |
| 006 | Environment Service and MCP tool wiring | 003, 004, 005 | SUC-003, SUC-004, SUC-005, SUC-006 |

**Execution order**: 001 → (002, 003, 004, 005 in parallel) → 006

Tickets 002–005 have no dependencies on each other and can be executed
in parallel after 001 is complete. Ticket 006 depends on 003, 004, and
005 and is the integration/wiring ticket.

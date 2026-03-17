---
id: '004'
title: Database Service
status: in-progress
use-cases:
- SUC-003
- SUC-004
- SUC-005
depends-on:
- '001'
github-issue: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Database Service

## Description

Implement the Database Service — the sole interface to Docker for
database container management. Handles creating Postgres containers,
starting, stopping, health checking, port allocation, and stale state
recovery.

Container naming: `rundbat-{app_name}-{env}-pg`
Database naming: `rundbat_{app_name}_{env}`
Health checks: `docker exec <container> pg_isready`

Key behaviors:
- `ensure_running` implements stale state recovery: stopped → restart,
  missing → recreate from config with data-loss warning
- Port allocation: default 5432, auto-increment if occupied
- Containers bind to localhost only

## Acceptance Criteria

- [ ] `src/rundbat/database.py` module with Database Service class/functions
- [ ] `create_database(env, config)` — runs `docker run` with correct name,
      port, password, database name; verifies with pg_isready
- [ ] `start_database(env)` MCP tool — starts stopped container, creates
      if missing
- [ ] `stop_database(env)` MCP tool — stops the container
- [ ] `health_check(env)` MCP tool — runs `docker exec pg_isready`,
      returns pass/fail with details
- [ ] `ensure_running(env, config)` — stopped → restart, missing →
      recreate with warning, running → no-op
- [ ] Container names follow `rundbat-{app_name}-{env}-pg` convention
- [ ] Database names follow `rundbat_{app_name}_{env}` convention
- [ ] Port allocation: uses configured port, detects conflicts, auto-assigns
      next available port if default is taken
- [ ] Containers bind to `127.0.0.1` only
- [ ] Password passed via `POSTGRES_PASSWORD` env var to container
- [ ] Data-loss warning when recreating a missing container
- [ ] Subprocess errors return structured error objects

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: `tests/test_database.py`
  - Test container name generation
  - Test database name generation
  - Test port allocation logic (mock port checks)
  - Integration tests (marked `requires_docker`):
    - Create container, verify running, verify pg_isready
    - Stop container, verify stopped
    - Restart stopped container
    - Delete container externally, verify recreate with warning
- **Verification command**: `uv run pytest` (skip Docker tests if no Docker)

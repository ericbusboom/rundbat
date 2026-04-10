---
id: '004'
title: Remote Deploy Command
status: done
branch: sprint/004-remote-deploy-command
use-cases:
- SUC-001
- SUC-002
- SUC-003
---

# Sprint 004: Remote Deploy Command

## Goals

Add `rundbat deploy <name>` and `rundbat deploy-init <name>` CLI commands
that deploy to named remote Docker hosts via Docker contexts. Replace the
complex hand-written Justfile deploy recipe with a single CLI call.

## Problem

The test project's Justfile has a 15-line deploy recipe with SSH key
management, `docker save | ssh docker load`, scp, and platform flags.
This is correct but hardcoded, non-reusable, and opaque.

## Solution

Use Docker contexts to abstract remote hosts. Since developers already
need Docker locally, requiring a Docker context for the remote is minimal
overhead. The deploy becomes `docker --context <ctx> compose up -d --build`
— same as local, just targeting a different daemon.

1. Add `deployments` section to `rundbat.yaml` with named deploy targets.
2. Create `src/rundbat/deploy.py` (~80-100 lines) with context management
   and deploy orchestration.
3. Wire `cmd_deploy` and `cmd_deploy_init` in `cli.py`.
4. Update `generate_justfile()` to emit `rundbat deploy <name>`.
5. Add unit tests.

SSH key distribution is out of scope — rundbat assumes SSH access works.

## Success Criteria

- `rundbat deploy prod --dry-run` prints the docker compose command
- `rundbat deploy prod` runs `docker compose up -d --build` via context
- `rundbat deploy-init prod --host ssh://root@host` creates context + config
- `rundbat init-docker` generates Justfile with `rundbat deploy` recipe
- `uv run pytest` passes

## Scope

### In Scope

- `src/rundbat/deploy.py` — context management + deploy logic
- `deployments` config schema in `rundbat.yaml`
- `cmd_deploy` + `cmd_deploy_init` CLI commands
- `--dry-run`, `--json`, `--no-build` flags
- Updated `generate_justfile()`
- Unit tests

### Out of Scope

- SSH key distribution / management
- Docker installation on remote hosts
- Deploy status, logs, rollback commands
- Container registry push
- CI/CD integration

## Test Strategy

- Unit tests mock subprocess — verify correct `docker` commands constructed
- Dry-run test verifies no subprocess calls made
- Config loading tests with valid/invalid/missing deployments
- Generator test: updated Justfile output

## Architecture Notes

- `deploy.py` peers with `config.py`, `database.py`, `generators.py`
- Docker context names: `{app_name}-{deploy_name}` convention
- Subprocess pattern follows `_run_docker()` in `database.py`

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Deploy module and config schema | — | 1 |
| 002 | CLI commands (deploy, deploy-init) | 001 | 2 |
| 003 | Update Justfile generator and tests | — | 1 |

**Groups**: Tickets in the same group can execute in parallel.

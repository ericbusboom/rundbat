---
id: "002"
title: "Docker Directory Generation"
status: planning
branch: sprint/002-docker-directory-generation
use-cases: [SUC-001, SUC-002, SUC-003]
---

# Sprint 002: Docker Directory Generation

## Goals

Implement `rundbat init-docker` and supporting generators so rundbat can
produce a complete `docker/` directory — Dockerfile, docker-compose.yml,
Justfile, and .env.example — as its primary deployment artifact.

## Problem

The skill files from Sprint 001 describe the `init-docker` workflow but
no code exists to actually generate Docker artifacts. Developers still
have to write Dockerfiles and compose files by hand.

## Solution

Add a `generators` module with template-based generation for:
1. Dockerfiles (framework-specific: Node, Python)
2. docker-compose.yml (app + database services, Caddy labels, health checks)
3. Justfile (standard deployment recipes)
4. .env.example (from dotconfig, secrets redacted)

Wire these through a `rundbat init-docker` CLI command and an
`add-service` command for incrementally adding database services.

## Success Criteria

- `rundbat init-docker` produces a working `docker/` directory
- Generated Dockerfile builds successfully for Node and Python projects
- Generated compose includes configured services with health checks
- Generated Justfile has build, up, down, deploy, db-dump/restore recipes
- Caddy labels are correct for both swarm and standalone
- `rundbat add-service postgres` adds Postgres to existing compose
- All generators have unit tests

## Scope

### In Scope

- `rundbat init-docker` CLI command
- Framework detection (Node.js, Python)
- Dockerfile templates (Express, Next.js, Flask, Django, FastAPI)
- docker-compose.yml generation with services, Caddy labels, health checks
- Justfile generation with standard recipes
- .env.example generation from dotconfig
- `rundbat add-service <type>` CLI command (postgres, mariadb, redis)
- Unit tests for all generators

### Out of Scope

- Remote deployment execution (SSH, docker context)
- Container registry push
- Database migration execution
- CI/CD pipeline generation

## Test Strategy

- Unit tests for each generator function (Dockerfile, compose, Justfile)
- Integration test: `init-docker` in a temp project, verify all files created
- Compose validation: generated YAML is parseable
- Dockerfile validation: generated Dockerfile has correct structure

## Architecture Notes

- New module: `src/rundbat/generators.py` — all generation logic
- Templates are Python string templates (not Jinja2) to avoid new deps
- `rundbat.yaml` extended with `framework` and `services` fields
- Caddy labels parameterized by `swarm` flag from deployment config

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Framework detection and Dockerfile generation | — | 1 |
| 002 | docker-compose.yml generation with services and Caddy labels | — | 1 |
| 003 | Justfile and .env.example generation | — | 1 |
| 004 | init-docker and add-service CLI commands | 001, 002, 003 | 2 |
| 005 | Tests for all generators | 001, 002, 003, 004 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).

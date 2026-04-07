---
title: Docker directory generation (Phase C)
priority: high
created: 2026-04-07
related: convert-mcp-to-cli-plugin.md
status: done
sprint: '002'
tickets:
- 002-001
---

# Docker Directory Generation (Phase C)

Implement the `docker/` directory generation that rundbat produces as its
primary artifact. This covers the `init-docker` CLI command and supporting
generators for Dockerfiles, docker-compose.yml, and Justfiles.

## Work items

1. `rundbat init-docker` CLI command — scaffold `docker/` with Dockerfile,
   docker-compose.yml, Justfile, and .env.example
2. Framework detection — identify Node.js (Express, Next) or Python
   (Flask, Django, FastAPI) from project files
3. Dockerfile templates — framework-specific multi-stage builds
4. docker-compose.yml generation — app service + database services from
   rundbat.yaml, Caddy labels (swarm-aware), health checks
5. Justfile generation — standard recipes: build, up, down, push, deploy,
   db-dump, db-restore, db-migrate, logs, shell
6. .env.example generation — from dotconfig sectioned output (secrets redacted)
7. `add-service` CLI command — add Postgres/MariaDB/Redis to existing compose
8. Tests for all generators

---
status: draft
---

# Project Overview

## Project Name

rundbat — Deployment Expert CLI

## Problem Statement

AI coding agents need to set up and manage Docker-based deployment
environments (databases, containers, secrets) for Node/Postgres
applications. Today this requires following instructional documents and
running ad-hoc commands — error-prone, inconsistent, and hard to recover
from when state drifts. rundbat encodes deployment procedures in
executable tools so agents get correct results every time.

## Target Users

- **AI coding agents** operating within the CLASI software engineering
  process (primary consumers of the CLI and skill files)
- **Students and developers** at the League of Amazing Programmers who
  benefit from automated environment setup
- **Team leads** managing multi-environment deployments (dev, staging,
  production)

## Key Constraints

- **Docker is the only runtime.** All databases and application
  containers run in Docker. No native Postgres installations.
- **dotconfig owns configuration.** All config read/write goes through
  dotconfig. rundbat never touches `config/` directly. Secrets are
  encrypted via dotconfig and SOPS.
- **Python package, installed via pipx.** Follows the same installation
  Claude integration via `.claude/` directories (skills, agents, rules).
- **Cross-platform.** Must work on macOS, Linux, Windows (WSL2), and
  GitHub Codespaces.
- **Graceful recovery from stale state.** Every environment query
  includes a liveness check and clear remediation.

## High-Level Requirements

1. **System discovery** — Detect OS, Docker status, installed tools,
   existing project config.
2. **Docker installation** — Install Docker or return the specific
   manual step needed, per platform.
3. **Project initialization** — Set up rundbat config via dotconfig,
   store app name and source.
4. **Environment creation** — Create local-docker, remote-docker, or
   managed-db environments with automatic port allocation and credential
   generation.
5. **Secret management** — Write secrets to dotconfig `.env` files with
   SOPS encryption.
6. **Service lifecycle** — Start, stop, and health-check database
   containers and app processes.
7. **Environment config retrieval** — Single-call access to connection
   strings with auto-restart of stopped containers and drift detection.
8. **Remote deployment** — Build, push, and deploy containers to remote
   hosts via SSH.
9. **Knowledge serving** — Serve skill files and agent definitions for
   deployment decisions, following the CLASI pattern.

## Technology Stack

- **Language:** Python
- **Distribution:** pipx-installable CLI package
- **Infrastructure:** Docker, Docker Compose
- **Configuration:** dotconfig + SOPS for secret encryption
- **Database:** PostgreSQL (in Docker containers or managed services)
- **Target apps:** Node.js / Postgres applications
- **Remote:** SSH, DigitalOcean (doctl), AWS CLI

## Sprint Roadmap

1. **Phase 1 — Local Docker Dev:** System discovery (discover_system,
   verify_docker) plus core tools — init_project, create_environment
   (local-docker), set_secret, validate_environment,
   get_environment_config, start/stop_database, health_check. dotconfig
   integration, port allocation, stale state recovery.
2. **Phase 2 — Discovery & Docker Installation:** Full OS detection,
   per-platform Docker installation state machine, Codespaces support,
   prerequisite installation.
3. **Phase 3 — Remote Environments:** Remote environment creation, SSH
   verification, container build/push/deploy pipeline, registry
   management, doctl/AWS integration.
4. **Phase 4 — CI/CD Integration:** GitHub Actions workflow generation,
   automated deploy pipelines, deploy key management.

## Specification

The full project specification is at `docs/rundbat-spec.md`. It contains
detailed architecture, tool surface definitions, configuration schemas,
developer scenarios, stale state recovery rules, and open questions.
Sprint planning and implementation should reference the spec as the
authoritative source for requirements and design decisions.

## Out of Scope

- **Database migrations.** rundbat creates the database and provides the
  connection string. The application owns its schema.
- **Application build configuration.** Application-level build tools
  (webpack, esbuild) are the application's concern.
- **dotconfig internals.** rundbat calls dotconfig commands but does not
  manage `config/sops.yaml` or encryption keys directly.
- **Non-Docker runtimes.** No native Postgres, no serverless functions
  (though managed container platforms like App Platform are in scope for
  Phase 3).
- **Multiple database engines.** Initial scope is Postgres only (noted
  as an open question in the spec).

---
id: '007'
title: Docker Lifecycle and Deployment Initialization
status: done
branch: sprint/007-docker-lifecycle-and-deployment-initialization
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
todos:
- plan-rundbat-generate-build-up-down-logs-docker-artifact-generation-and-lifecycle.md
- plan-github-actions-build-deploy-with-docker-run-and-dotconfig-integration.md
- plan-rundbat-build-triggers-github-actions-workflow-for-ghcr-builds.md
- plan-deployment-initialization-guided-setup-and-configuration-model.md
---

# Sprint 007: Docker Lifecycle and Deployment Initialization

## Goals

1. Replace `init-docker` with `rundbat generate` that produces per-deployment compose files and lifecycle artifacts.
2. Add lifecycle commands: `build`, `up`, `down`, `logs` — each deployment-aware.
3. Add `deploy_mode: run` support alongside compose, with dotconfig env injection.
4. Split GitHub Actions workflows into separate build.yml and deploy.yml; wire `rundbat build` to trigger via `gh workflow run`.
5. Create a guided `deploy-init` skill that walks users through full deployment configuration.

## Problem

rundbat's current `init-docker` command generates a single generic compose file for all deployments. There is no way to configure per-deployment service sets, port mappings, or Caddy labels independently. Lifecycle operations (start, stop, logs) require the user to know the right compose file path and Docker context. The deploy flow has no support for `docker run` mode or dotconfig-based env injection at deploy time. Building via GitHub Actions requires manual workflow authoring. Deploying requires advance knowledge of CLI flags with no guided setup path.

## Solution

Implement a four-part expansion:

1. **`rundbat generate`**: Reads `rundbat.yaml` deployments and generates one `docker-compose.<name>.yml` per deployment plus per-deployment env files, a shared Dockerfile, an entrypoint script, and a Justfile with per-deployment recipes. `init-docker` becomes a deprecated alias.

2. **Lifecycle commands**: Thin `build`, `up`, `down`, `logs` subcommands that resolve the right compose file and Docker context from config and delegate to `docker compose`. For `deploy_mode: run` deployments they issue `docker run`/`docker stop`/`docker logs` directly.

3. **`deploy_mode` and dotconfig injection**: New `deploy_mode` field (compose or run) on each deployment. `_deploy_run()` in deploy.py handles single-container deployments. `_prepare_env()` fetches env from dotconfig and SCPs it to the remote before container start.

4. **GitHub Actions split + build trigger**: `generate_github_build_workflow()` and `generate_github_deploy_workflow()` replace the single `generate_github_workflow()`. `rundbat build <deployment>` triggers the build workflow via `gh workflow run` when strategy is github-actions. `detect_gh()` added to discovery.py.

5. **Guided deploy-init skill**: `deploy-init.md` skill with explicit `AskUserQuestion` steps covers target selection, services, deploy mode, SSH access, domain, build strategy, and env config. Writes the complete deployment entry to `rundbat.yaml` and generates artifacts.

## Success Criteria

- `rundbat generate` creates `docker-compose.<name>.yml` for every deployment in `rundbat.yaml`.
- `rundbat build local` / `up local` / `down local` / `logs local` work without needing explicit compose file paths.
- `rundbat deploy-init prod --deploy-mode run --image ghcr.io/owner/repo` saves `docker_run_cmd` to config.
- `rundbat build prod` (github-actions strategy) triggers `build.yml` via `gh workflow run`.
- `rundbat up prod --workflow` triggers `deploy.yml` via `gh workflow run`.
- All unit tests pass.

## Scope

### In Scope

- `rundbat generate` command and per-deployment compose generation in generators.py
- Per-deployment env files (fetched from dotconfig) and `.gitignore` update
- Entrypoint script generation (`generate_entrypoint()`)
- Per-deployment Justfile recipes
- `rundbat build`, `up`, `down`, `logs` subcommands in cli.py
- `deploy_mode` field (compose / run) in rundbat.yaml schema
- `_deploy_run()`, `_prepare_env()`, `_build_docker_run_cmd()` in deploy.py
- `generate_github_build_workflow()` and `generate_github_deploy_workflow()` replacing `generate_github_workflow()`
- `detect_gh()` in discovery.py and `_get_github_repo()` in deploy.py
- `--deploy-mode`, `--image` flags on `deploy-init` subcommand
- `rundbat build` triggering `gh workflow run` for github-actions strategy
- `rundbat up --workflow` triggering deploy workflow via gh CLI
- Skill files: `deploy-init.md` (guided interview), `github-deploy.md`, updated `deploy-setup.md`, `generate.md`
- Unit tests for all new functions

### Out of Scope

- Blue-green or rolling deployments
- Registries beyond GHCR
- Dev server hot-reload integration (framework-specific)
- Cron/worker container sidecars
- Per-deployment Dockerfile variants
- SSR/hybrid Astro deployments

## Test Strategy

- Unit tests for `generate_compose_for_deployment()`, `generate_entrypoint()`, updated Justfile generation
- Unit tests for `_deploy_run()`, `_prepare_env()`, `_build_docker_run_cmd()`
- Unit tests for `generate_github_build_workflow()`, `generate_github_deploy_workflow()`
- Unit tests for `detect_gh()` in discovery
- CLI smoke tests for new subcommands
- All existing tests must continue to pass

## Architecture Notes

- Per-deployment compose files use the naming convention `docker-compose.<name>.yml` (e.g., `docker-compose.prod.yml`).
- `deploy_mode` and `build_strategy` are orthogonal fields — any combination is valid.
- env files (`docker/.<name>.env`) contain secrets and must be gitignored; generated files (compose, Justfile, Dockerfile) are committed.
- `gh workflow run` requires the `gh` CLI to be installed and authenticated; `detect_gh()` gates this path with a clear error.
- The guided `deploy-init.md` skill is a Claude Code skill file (not Python code) — it contains AskUserQuestion specs and shell command steps.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Per-deployment compose generation and `rundbat generate` command | — | 1 |
| 002 | Lifecycle commands: build, up, down, logs | 001 | 2 |
| 003 | deploy_mode run and docker_run_cmd support | 001 | 2 |
| 004 | dotconfig env injection in deploy flow | 003 | 3 |
| 005 | GitHub Actions workflow split and build triggers | 001, 002 | 3 |
| 006 | Guided deployment initialization skill | 001, 002, 003, 004, 005 | 4 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).

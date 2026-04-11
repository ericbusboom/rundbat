---
id: '001'
title: Per-deployment compose generation and rundbat generate command
status: in-progress
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo: plan-rundbat-generate-build-up-down-logs-docker-artifact-generation-and-lifecycle.md
---

# Per-deployment compose generation and rundbat generate command

## Description

Replace the single `docker-compose.yml` generation model with per-deployment compose files. The current `generate_compose()` produces one generic file for all deployments. This ticket introduces `generate_compose_for_deployment()` that produces a `docker-compose.<name>.yml` per deployment, and a `generate_artifacts()` orchestrator that reads all deployments from `rundbat.yaml` and writes all files. A new `generate` CLI subcommand replaces `init-docker` as the primary artifact generation command; `init-docker` is preserved as a deprecated alias.

This is the foundation ticket. Tickets 002–005 build on the per-deployment file naming convention and the `generate_artifacts()` function.

## Acceptance Criteria

- [ ] `generate_compose_for_deployment(app_name, framework, deployment_name, deployment_cfg, all_services)` exists in `generators.py` and produces a valid compose YAML string for one deployment.
- [ ] Compose files for deployments with `build_strategy: context` or `ssh-transfer` use a `build:` stanza; `github-actions` deployments use `image:`.
- [ ] `env_file` in each compose file references `docker/.<name>.env` (not `../.env`).
- [ ] Caddy labels are included only when both `hostname` and `reverse_proxy: caddy` are set on the deployment.
- [ ] Services included in the compose file match `deployment_cfg["services"]`; if absent, all project services are included.
- [ ] `generate_entrypoint(framework)` exists in `generators.py` and returns a valid shell script string with `set -e` and a framework-appropriate `exec` call.
- [ ] `generate_artifacts(project_dir, cfg)` orchestrates: per-deployment compose files, `Dockerfile`, `entrypoint.sh`, `Justfile` (per-deployment recipes), `.dockerignore`, and appends `docker/.*.env` to `.gitignore`.
- [ ] `init_docker()` is preserved as a deprecated wrapper calling `generate_artifacts()`.
- [ ] `generate_justfile()` produces named recipes `<name>_build`, `<name>_up`, `<name>_down`, `<name>_logs` for each deployment; remote deployments prefix with `DOCKER_CONTEXT=<ctx>`.
- [ ] `rundbat generate` CLI subcommand calls `generate_artifacts()` and prints generated file list.
- [ ] `rundbat generate --deployment prod` regenerates only the prod deployment artifacts.
- [ ] `rundbat init-docker` continues to work and prints a deprecation notice.
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Add new functions to `generators.py` without removing existing ones. Introduce the `generate` subcommand in `cli.py`. Keep `init-docker` wired to `cmd_init_docker` which calls the new `generate_artifacts()`.

### Files to Create

None.

### Files to Modify

**`src/rundbat/generators.py`**
- Add `generate_compose_for_deployment(app_name, framework, deployment_name, deployment_cfg, all_services)` — builds a compose dict for one deployment:
  - Determines `build:` vs `image:` from `deployment_cfg.get("build_strategy")`
  - Determines port from framework detection
  - Filters services to `deployment_cfg.get("services", <all>)`
  - Sets `env_file: [docker/.<name>.env]`
  - Adds Caddy labels when `hostname` and `reverse_proxy: caddy` present
  - Returns `yaml.dump(compose, ...)`
- Add `generate_entrypoint(framework)` — returns a shell script string. Variants: node (exec npm start), gunicorn, uvicorn, nginx (exec "$@" passthrough). All start with `#!/bin/sh` and `set -e`. Include SOPS/age key setup block.
- Update `generate_justfile(app_name, deployments, all_services)` — replace ENV-variable approach with named per-deployment recipes. Each deployment gets `<name>_build`, `<name>_up`, `<name>_down`, `<name>_logs`. Remote deployments (non-default context) prefix with `DOCKER_CONTEXT=<ctx>`. github-actions `<name>_up` uses `docker compose pull && up`. Postgres deployments get `<name>_psql` and `<name>_db_dump`. Old ENV-based recipes removed.
- Add `generate_artifacts(project_dir, cfg)` — reads `cfg` (full rundbat.yaml dict), calls `generate_compose_for_deployment()` for every deployment, writes `docker/docker-compose.<name>.yml`, generates Dockerfile, entrypoint.sh, Justfile, .dockerignore, updates .gitignore. Returns `{status, files: [...]}`.
- Update `init_docker()` to be a thin wrapper: load config, call `generate_artifacts()`, return result. Print deprecation notice.

**`src/rundbat/cli.py`**
- Add `cmd_generate(args)`: loads config, calls `generators.generate_artifacts()`. Supports `--deployment <name>` to regenerate a single deployment.
- Add `generate` subparser with `--deployment` and `--json` flags.
- Update `cmd_init` next-steps message to reference `rundbat generate`.
- Update `cmd_init_docker` to call `generate_artifacts()` internally (via the updated `generators.init_docker()`).

### Testing Plan

- `tests/unit/test_generators.py`: add tests for `generate_compose_for_deployment()` covering build vs image mode, service filtering, Caddy labels, env_file path. Add tests for `generate_entrypoint()` covering all framework variants. Add tests for updated `generate_justfile()` covering per-deployment recipe names, DOCKER_CONTEXT prefix, github-actions pull variant.
- `tests/unit/test_cli.py`: add smoke tests for `rundbat generate` and `rundbat generate --deployment prod`.
- Run `uv run pytest` to verify all existing tests pass.

### Documentation Updates

None — skill file updates are in Ticket 006.

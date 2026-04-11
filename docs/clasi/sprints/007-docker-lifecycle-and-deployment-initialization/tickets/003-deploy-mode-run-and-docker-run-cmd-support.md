---
id: '003'
title: deploy_mode run and docker_run_cmd support
status: todo
use-cases: [SUC-003]
depends-on: ['001']
github-issue: ''
todo: plan-github-actions-build-deploy-with-docker-run-and-dotconfig-integration.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# deploy_mode run and docker_run_cmd support

## Description

Add `deploy_mode: run` as a first-class deployment mode. When a deployment uses run mode, rundbat generates a `docker run` command from the deployment's config (image, port, hostname/Caddy labels, env-file path) and stores it in `rundbat.yaml` as `docker_run_cmd`. The `up`, `down`, and `logs` commands are wired to use the stored command instead of docker compose.

This ticket adds three functions to `deploy.py` (`_deploy_run`, `_build_docker_run_cmd`, and a partial `_prepare_env` stub) and extends `deploy-init` with `--deploy-mode` and `--image` flags. The `_prepare_env` dotconfig transfer is completed in Ticket 004.

Depends on Ticket 001 for the deployment config structure.

## Acceptance Criteria

- [ ] `deploy_mode` field is accepted in `rundbat.yaml` deployment entries with values `compose` (default) and `run`.
- [ ] `_build_docker_run_cmd(app_name, image, port, hostname, env_file, docker_context)` in `deploy.py` returns a complete `docker run` command string including: `--name`, `--env-file`, `-p`, `--restart unless-stopped`, and Caddy labels when `hostname` is set.
- [ ] `_deploy_run(deployment_name, deploy_cfg, dry_run)` in `deploy.py`: pulls image, stops/removes existing container, executes `docker_run_cmd` from config. Dry-run prints commands without executing.
- [ ] `deploy()` dispatch checks `deploy_mode` first: if `run`, calls `_deploy_run()`; otherwise uses existing build_strategy dispatch.
- [ ] `init_deployment()` accepts `deploy_mode` and `image` parameters. When `deploy_mode == "run"`, calls `_build_docker_run_cmd()` and stores `docker_run_cmd` in `rundbat.yaml`.
- [ ] `rundbat deploy-init <name> --host ... --deploy-mode run --image ghcr.io/owner/repo` saves a complete deployment entry with `docker_run_cmd` visible in `rundbat.yaml`.
- [ ] `rundbat up <name>` for a run-mode deployment calls `_deploy_run()`.
- [ ] `rundbat down <name>` for a run-mode deployment runs `docker stop <app_name> && docker rm <app_name>`.
- [ ] `rundbat logs <name>` for a run-mode deployment runs `docker logs -f <app_name>`.
- [ ] `rundbat deploy <name> --dry-run` for a run-mode deployment prints the docker run command from config.
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Add new functions to `deploy.py` alongside existing `_deploy_context`, `_deploy_ssh_transfer`, `_deploy_github_actions`. Extend `init_deployment()` with new keyword parameters. Update `deploy()` dispatch logic. Extend `cli.py` to wire run-mode stubs in `cmd_up`, `cmd_down`, `cmd_logs` (Ticket 002) to the real functions.

### Files to Modify

**`src/rundbat/deploy.py`**
- Add `_build_docker_run_cmd(app_name, image, port, hostname, env_file, docker_context)`: builds and returns the full `docker run` command string. Caddy labels added when `hostname` is set. `docker_context` prefix added for remote deployments.
- Add `_deploy_run(deployment_name, deploy_cfg, dry_run)`: resolves `docker_context` from config, calls `_prepare_env()` (stub: logs "env injection: Ticket 004"), then pull + stop/rm + run.
- Add `_prepare_env(deployment_name, docker_context, host, ssh_key)` stub: prints "dotconfig env injection not yet implemented — see Ticket 004". Returns without error so deploy continues.
- Update `deploy()`: before build_strategy dispatch, check `deploy_cfg.get("deploy_mode") == "run"` and call `_deploy_run()`.
- Update `init_deployment(name, host, ..., deploy_mode=None, image=None)`: save `deploy_mode`, call `_build_docker_run_cmd()` when run mode, save `docker_run_cmd` to config.

**`src/rundbat/cli.py`**
- Add `--deploy-mode` and `--image` flags to `deploy-init` subparser.
- Pass `deploy_mode=args.deploy_mode, image=args.image` to `deploy.init_deployment()`.
- Update `cmd_up`, `cmd_down`, `cmd_logs` (from Ticket 002) to call `deploy._deploy_run()` / `docker stop` / `docker logs` when `deploy_mode == "run"`.

### Testing Plan

- `tests/unit/test_deploy.py`: add tests for `_build_docker_run_cmd()` covering: basic command structure, Caddy labels with/without hostname, DOCKER_CONTEXT prefix for remote. Add tests for `_deploy_run()` using mocked `subprocess.run`: verify pull → stop → rm → run sequence. Add dry-run test.
- `tests/unit/test_cli.py`: test `deploy-init --deploy-mode run --image ghcr.io/owner/repo` stores `docker_run_cmd` in config.
- Run `uv run pytest`.

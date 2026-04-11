---
id: '004'
title: dotconfig env injection in deploy flow
status: todo
use-cases: [SUC-004]
depends-on: ['003']
github-issue: ''
todo: plan-github-actions-build-deploy-with-docker-run-and-dotconfig-integration.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# dotconfig env injection in deploy flow

## Description

Complete the `_prepare_env()` function stubbed in Ticket 003. When a deployment has `env_source: dotconfig`, `_prepare_env()` fetches the assembled environment from dotconfig, writes it to a temp file, and SCPs it to `/opt/<app_name>/.env` on the remote host. This env file is then referenced by `--env-file` in the docker run command or by `env_file:` in the compose file.

This ticket also wires `_prepare_env()` into both the compose deploy path and the run deploy path. For `generate_artifacts()` (Ticket 001), per-deployment env files are fetched and written to `docker/.<name>.env` at generation time for local dotconfig deployments.

## Acceptance Criteria

- [ ] `_prepare_env(deployment_name, deploy_cfg, app_name)` in `deploy.py` calls `config.load_env(deployment_name)` to get env content.
- [ ] `_prepare_env` writes env content to a temp file and SCPs it to `<host>:/opt/<app_name>/.env` using the deployment's SSH key if configured.
- [ ] `_prepare_env` is called in `_deploy_run()` before the docker run step.
- [ ] `_prepare_env` is called in the compose deploy path (`_deploy_context`, `_deploy_ssh_transfer`, `_deploy_github_actions`) before `docker compose up` when `env_source == "dotconfig"`.
- [ ] If `env_source` is not `dotconfig`, `_prepare_env` is a no-op.
- [ ] `generate_artifacts()` (Ticket 001) writes `docker/.<name>.env` for each deployment with `env_source: dotconfig` by calling `config.load_env(name)`.
- [ ] If dotconfig is unavailable or returns an error, `_prepare_env` raises `DeployError` with a clear message.
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Replace the stub `_prepare_env()` from Ticket 003 with the real implementation. Wire it into all deploy strategy functions. Update `generate_artifacts()` in generators.py to write per-deployment env files.

### Files to Modify

**`src/rundbat/deploy.py`**
- Replace `_prepare_env()` stub with full implementation:
  - Call `config.load_env(deployment_name)` — returns env file content as a string.
  - If `env_source` not `dotconfig`: return immediately (no-op).
  - Write content to `tempfile.NamedTemporaryFile`.
  - Parse `host` from deployment config (strip `ssh://` prefix).
  - Determine SSH key arg: `-i <ssh_key>` if `ssh_key` is set in config.
  - Run `scp <key_arg> <tmpfile> <user>@<host>:/opt/<app_name>/.env`.
  - Raise `DeployError` on non-zero exit.
- Wire `_prepare_env()` into `_deploy_context()`, `_deploy_ssh_transfer()`, `_deploy_github_actions()`: call before the `up -d` step when `env_source == "dotconfig"`.

**`src/rundbat/generators.py`**
- In `generate_artifacts()`: for each deployment with `env_source == "dotconfig"`, call `config.load_env(name)` and write result to `docker/.<name>.env`. If dotconfig unavailable, write a placeholder with a comment and print a warning.

### Testing Plan

- `tests/unit/test_deploy.py`: add tests for `_prepare_env()` using mocked `config.load_env` and mocked `subprocess.run`. Verify SCP command construction (host parsing, key arg). Test no-op when `env_source != "dotconfig"`. Test `DeployError` raised on SCP failure.
- `tests/unit/test_generators.py`: add test that `generate_artifacts()` writes `docker/.prod.env` when deployment has `env_source: dotconfig` (mock `config.load_env`).
- Run `uv run pytest`.

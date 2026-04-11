---
id: '002'
title: 'Lifecycle commands: build, up, down, logs'
status: todo
use-cases: [SUC-002]
depends-on: ['001']
github-issue: ''
todo: plan-rundbat-generate-build-up-down-logs-docker-artifact-generation-and-lifecycle.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Lifecycle commands: build, up, down, logs

## Description

Add four new CLI subcommands — `build`, `up`, `down`, `logs` — that resolve the correct compose file and Docker context from `rundbat.yaml` and delegate to `docker compose`. This eliminates the need for users to remember compose file paths or set `DOCKER_CONTEXT` manually.

Depends on Ticket 001 for the per-deployment compose file naming convention (`docker-compose.<name>.yml`) and the deployment config structure.

For compose-mode deployments: each command maps to a `docker compose -f docker/docker-compose.<name>.yml` invocation. For run-mode deployments (Ticket 003 adds `_deploy_run`): `up` uses the stored `docker_run_cmd`, `down` stops/removes the named container, `logs` calls `docker logs -f`. This ticket implements the compose path; the run-mode path is wired in Ticket 003.

The `--workflow` flag on `up` is scaffolded here (flag registered) but the `gh workflow run` call is implemented in Ticket 005.

## Acceptance Criteria

- [ ] `rundbat build <name>` runs `docker compose -f docker/docker-compose.<name>.yml build` with the deployment's `docker_context` set as `DOCKER_CONTEXT`.
- [ ] `rundbat up <name>` starts containers: `docker compose ... up -d`. For `build_strategy: github-actions` deployments, prepends a `docker compose ... pull`.
- [ ] `rundbat down <name>` stops and removes containers: `docker compose ... down`.
- [ ] `rundbat logs <name>` tails logs: `docker compose ... logs -f`.
- [ ] All four commands error with a clear message if `docker/docker-compose.<name>.yml` does not exist (user must run `rundbat generate` first).
- [ ] All four commands error with a clear message if the deployment name is not found in `rundbat.yaml`.
- [ ] `--json` flag supported on all four commands.
- [ ] `--workflow` flag registered on `up` (implementation stubbed — prints note that --workflow support is wired in Ticket 005 if triggered before that ticket is done).
- [ ] `rundbat deploy <name>` continues to work (backward compat — calls existing `deploy.deploy()`).
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Add four command handler functions and four subparsers in `cli.py`. Each handler loads config, resolves the deployment entry, constructs the `docker compose` command with the right `-f` path and `DOCKER_CONTEXT`, and calls `subprocess.run()`. No new modules needed.

### Files to Modify

**`src/rundbat/cli.py`**
- Extract `_resolve_deployment(name, as_json)` helper: loads config, finds deployment by name, errors clearly if missing. Returns `(cfg, deployment_cfg)`.
- Add `cmd_build(args)`: resolves deployment, constructs compose file path, checks file exists, runs `docker compose -f <file> build` with `DOCKER_CONTEXT` env var.
- Add `cmd_up(args)`: resolves deployment. If `deploy_mode == "run"`, delegates to `deploy._deploy_run()` (stub: error with helpful message until Ticket 003). If `args.workflow`, stub (Ticket 005). Otherwise: github-actions strategy pulls first, then `docker compose ... up -d`.
- Add `cmd_down(args)`: resolves deployment. Run-mode stub. Otherwise: `docker compose ... down`.
- Add `cmd_logs(args)`: resolves deployment. Run-mode stub. Otherwise: `docker compose ... logs -f` (streams to terminal — no capture_output).
- Add subparsers for `build`, `up`, `down`, `logs`. Each takes a positional `name` arg and `--json` flag. `up` additionally gets `--workflow` flag.

### Testing Plan

- `tests/unit/test_cli.py`: add tests for each subcommand using `unittest.mock.patch` on `subprocess.run`. Verify correct command construction (compose file path, DOCKER_CONTEXT env var set correctly for remote deployments, default for local). Test error cases: unknown deployment name, missing compose file.
- Run `uv run pytest`.

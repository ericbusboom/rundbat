---
id: '005'
title: 'CLI stack lifecycle (deploy_mode: stack in up/down/restart/logs)'
status: done
use-cases:
- SUC-003
depends-on:
- '003'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T05 — CLI stack lifecycle

## Description

Add a third branch (`stack`) alongside the existing `compose` and
`run` branches in the lifecycle commands:

- `cmd_up` at cli.py:508
- `cmd_down` at cli.py:587
- `cmd_restart` at cli.py:652
- `cmd_logs` at cli.py:621

Behavior when the resolved deployment has `deploy_mode: stack`:

| Command | Shells out to |
|---|---|
| `up` | `docker --context <ctx> stack deploy -c docker/docker-compose.<env>.yml <stack>` |
| `down` | `docker --context <ctx> stack rm <stack>` |
| `restart` | `down` then `up` via the stack branches |
| `logs` | `docker --context <ctx> service logs -f <stack>_<service>` for each service in the deployment |

Stack name resolution: `stack_name` field from the deployment entry
if present, otherwise `<app_name>_<deployment_name>`.

**Auto-upgrade rule**: if the probe recorded `swarm: true` AND the
deployment has `swarm: true`, and `deploy_mode` is still the default
(`compose` or absent), the lifecycle commands behave as if
`deploy_mode: stack` were set. Add a small helper
`_effective_deploy_mode(deployment)` that applies the upgrade so the
logic lives in one place.

Docker errors are surfaced verbatim (no swallow) — when the context
is offline or auth fails, the user sees the actual Docker error.

## Affected Files

- `src/rundbat/cli.py` — `cmd_up`, `cmd_down`, `cmd_restart`,
  `cmd_logs`; new helper `_effective_deploy_mode`
- `tests/unit/test_cli.py` — new tests

## Acceptance Criteria

- [x] `cmd_up` with `deploy_mode: stack` runs
      `docker stack deploy -c <file> <stack>` under the deployment's
      context
- [x] `cmd_down` with `deploy_mode: stack` runs
      `docker stack rm <stack>`
- [x] `cmd_logs` with `deploy_mode: stack` runs `docker service logs
      -f` for each configured service
- [x] `cmd_restart` runs stack `down` then stack `up`
- [x] Stack name defaults to `<app>_<deployment>`; overridable via
      `stack_name` field
- [x] Auto-upgrade: probe.swarm + deployment.swarm=true + no explicit
      deploy_mode → stack branch taken
- [x] Existing compose-mode and run-mode paths unchanged (regression)
- [x] Docker errors propagate verbatim
- [x] `uv run pytest` passes
- [x] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_cli.py`
- **New tests to write**:
  - `test_cmd_up_stack_mode_runs_stack_deploy`
  - `test_cmd_down_stack_mode_runs_stack_rm`
  - `test_cmd_logs_stack_mode_runs_service_logs`
  - `test_cmd_restart_stack_mode_calls_down_then_up`
  - `test_stack_name_defaults_to_app_underscore_deployment`
  - `test_stack_name_override_via_stack_name_field`
  - `test_auto_upgrade_to_stack_when_swarm_true`
  - `test_compose_mode_unchanged` (regression)
- **Verification command**: `uv run pytest`

## Notes

- Depends on T03 for the generated compose file shape.
- Bump `pyproject.toml` version.

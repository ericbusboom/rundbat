---
id: '001'
title: Deploy module and config schema
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
todo: add-rundbat-deploy-command.md
---

# Deploy module and config schema

## Description

Create `src/rundbat/deploy.py` with Docker context-based deployment logic.
Add `deployments` section to `rundbat.yaml` config schema.

The module provides:
- `load_deploy_config(name)` — read named deployment from rundbat.yaml
- `ensure_context(app_name, deploy_name, host)` — verify or create Docker context
- `create_context(name, host)` — `docker context create`
- `verify_access(context_name)` — run `docker --context <ctx> info` to confirm
- `deploy(name, dry_run, no_build)` — orchestrator that runs
  `docker --context <ctx> compose -f <file> up -d --build`

Follow existing subprocess patterns from `database.py` (`_run_docker`).
Add `DeployError` exception with `.to_dict()` method.

## Acceptance Criteria

- [ ] `deploy.py` module exists with all functions listed above
- [ ] `DeployError` follows the `DatabaseError` / `ConfigError` pattern
- [ ] `load_deploy_config()` reads from rundbat.yaml deployments section
- [ ] `ensure_context()` checks for existing context, creates if missing
- [ ] `deploy()` constructs correct `docker --context` command
- [ ] `deploy()` with `dry_run=True` returns steps without executing
- [ ] `deploy()` with `no_build=True` omits `--build` flag
- [ ] `tests/proj/config/rundbat.yaml` updated with sample deployments entry

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/`
- **New tests to write**: `tests/unit/test_deploy.py` — config loading,
  context management, command construction, dry-run, error paths
- **Verification command**: `uv run pytest`

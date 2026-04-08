---
id: '002'
title: CLI commands for deploy and deploy-init
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: ''
---

# CLI commands for deploy and deploy-init

## Description

Wire `cmd_deploy` and `cmd_deploy_init` handlers in `cli.py`. Register
subparsers with appropriate flags.

### `rundbat deploy <name>`
- Positional: deployment name (e.g., `prod`)
- `--dry-run` — show command without executing
- `--no-build` — skip `--build` flag
- `--json` — structured output

### `rundbat deploy-init <name> --host <ssh://user@host>`
- Positional: deployment name
- `--host` — SSH URL for the remote Docker host (required)
- `--compose-file` — path to compose file (optional, default docker/docker-compose.yml)
- `--hostname` — app hostname for post-deploy message (optional)
- `--json` — structured output

## Acceptance Criteria

- [ ] `rundbat deploy prod` calls `deploy.deploy("prod")`
- [ ] `rundbat deploy prod --dry-run` passes `dry_run=True`
- [ ] `rundbat deploy prod --no-build` passes `no_build=True`
- [ ] `rundbat deploy prod --json` outputs JSON
- [ ] `rundbat deploy-init prod --host ssh://root@host` creates context + config
- [ ] Both commands appear in `rundbat --help` output
- [ ] Error handling follows `_error()` pattern

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_cli.py`
- **New tests to write**: CLI argument parsing tests in `test_cli.py`
- **Verification command**: `uv run pytest`

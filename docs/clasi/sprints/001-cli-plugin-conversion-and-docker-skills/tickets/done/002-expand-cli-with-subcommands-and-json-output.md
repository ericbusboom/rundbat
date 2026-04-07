---
id: '002'
title: Expand CLI with subcommands and --json output
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
todo: ''
---

# Expand CLI with subcommands and --json output

## Description

Add CLI subcommands that mirror the old MCP tools. Each subcommand
calls the existing service layer and supports `--json` for machine-
parseable output (default is human-readable).

Subcommands to add (all under `rundbat`):
- `discover` → `discovery.discover_system()`
- `create-env <env>` → `environment.create_environment(env)`
- `get-config <env>` → `environment.get_environment_config(env)`
- `start <env>` → `database.start_container()` (via config lookup)
- `stop <env>` → `database.stop_container()` (via config lookup)
- `health <env>` → `database.health_check()` (via config lookup)
- `validate <env>` → `environment.validate_environment(env)`
- `set-secret <env> <KEY=VALUE>` → `config.save_secret(env, key, value)`
- `check-drift [env]` → `config.check_config_drift(env)`

Keep existing subcommands: `init`, `env list`, `env connstr`.

Exit codes: 0 = success, 1 = error, 2 = usage error.

## Acceptance Criteria

- [ ] Each MCP tool has a corresponding CLI subcommand
- [ ] `--json` flag produces valid JSON on stdout for every subcommand
- [ ] Human-readable output is the default (no `--json`)
- [ ] Exit codes follow convention (0, 1, 2)
- [ ] `rundbat --help` lists all subcommands
- [ ] Each subcommand has `--help` with usage examples

## Testing

- **Existing tests to run**: `pytest tests/unit/`
- **New tests to write**: CLI subcommand tests using `subprocess.run`
  for each subcommand in `--json` mode (verify valid JSON output)
- **Verification command**: `rundbat discover --json | python -m json.tool`

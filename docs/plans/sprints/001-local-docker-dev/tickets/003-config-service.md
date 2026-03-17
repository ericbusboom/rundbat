---
id: "003"
title: "Config Service"
status: todo
use-cases:
  - SUC-002
  - SUC-006
  - SUC-007
depends-on:
  - "001"
github-issue: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Config Service

## Description

Implement the Config Service — the sole interface to dotconfig. All
dotconfig subprocess calls in rundbat go through this module. Provides
config loading, saving, secret management, project initialization, and
app name drift detection.

Key dotconfig commands (confirmed via `dotconfig agent`):
- `dotconfig init` — first-time setup
- `dotconfig load -d <env> --file rundbat.yaml --stdout` — load rundbat config
- `dotconfig save -d <env> --file rundbat.yaml` — save rundbat config
- `dotconfig load -d <env> --stdout` — load assembled .env
- `dotconfig load -d <env>` then edit then `dotconfig save` — round-trip secrets
- `dotconfig config` — check if initialized

Also implements `init_project` and `set_secret` MCP tools, and the
`check_config_drift` tool for app name drift detection.

## Acceptance Criteria

- [ ] `src/rundbat/config.py` module with Config Service class/functions
- [ ] `load_config(env)` — loads `rundbat.yaml` via dotconfig, returns parsed YAML
- [ ] `save_config(env, data)` — writes `rundbat.yaml` via dotconfig
- [ ] `save_secret(env, key, value)` — round-trips .env via dotconfig load/edit/save
- [ ] `init_project(app_name, app_name_source)` MCP tool registered
  - Runs `dotconfig init` if not initialized
  - Saves initial `rundbat.yaml` with app_name, app_name_source, empty notes
  - Idempotent — calling again with same args does not error
- [ ] `set_secret(env, key, value)` MCP tool registered
  - Loads .env, adds/updates key in secrets section, saves back
  - Preserves existing secrets and section markers
- [ ] `check_config_drift` MCP tool registered
  - Reads app_name_source file, compares to stored app_name
  - Returns warning with both values if mismatched
- [ ] Subprocess errors return structured error objects (command, exit code, stderr)
- [ ] Never calls shell=True in subprocess

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: `tests/test_config.py`
  - Test `rundbat.yaml` round-trip (save then load)
  - Test secret editing preserves section markers
  - Test drift detection with matching and mismatched names
  - Test error handling when dotconfig is not installed
  - Integration tests require dotconfig installed (mark appropriately)
- **Verification command**: `uv run pytest`

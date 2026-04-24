---
id: '007'
title: rundbat secret create command (dotconfig to Swarm secret)
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T07 — rundbat secret create

## Description

Add a new CLI subcommand:

```
rundbat secret create <env> <KEY>
```

Flow:
1. Resolve the deployment `<env>` and its `docker_context`.
2. Load the value for `<KEY>` from dotconfig for the named
   environment (via existing `config.load_env` or equivalent).
3. Compute the Swarm secret name:
   `<app_name>_<KEY_lowercase>_v<YYYYMMDD>`
   (e.g. `myapp_postgres_password_v20260424`).
4. Pipe the value into
   `docker --context <ctx> secret create <name> -`
   via stdin.
5. Print the created secret name on success; on failure surface the
   Docker error verbatim.

Error handling:
- Missing KEY in dotconfig → clear error (do NOT create an empty
  secret).
- Deployment not found → standard "no such deployment" error.
- Docker command failure → error surfaced with the returncode and
  stderr.

## Affected Files

- `src/rundbat/cli.py` — new `cmd_secret_create` + argparse
  subparser wiring
- `tests/unit/test_cli.py` — new tests

## Acceptance Criteria

- [x] `rundbat secret create <env> <KEY>` subcommand exists and is
      discoverable via `rundbat --help` / `rundbat secret --help`
- [x] Reads the value from dotconfig for the named environment
- [x] Names the secret `<app>_<key_lowercase>_v<YYYYMMDD>`
- [x] Pipes the value into `docker --context <ctx> secret create
      <name> -` via stdin (not argv — stdin is the documented
      non-leaking channel)
- [x] Missing KEY produces a clear error and no Docker call is made
- [x] Docker failure surfaces returncode + stderr verbatim
- [x] Prints the created name on success
- [x] `uv run pytest` passes
- [x] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_cli.py`
- **New tests to write**:
  - `test_secret_create_pipes_value_into_docker_stdin`
  - `test_secret_create_uses_versioned_name_app_key_vYYYYMMDD`
  - `test_secret_create_missing_key_errors_before_docker_call`
  - `test_secret_create_docker_failure_surfaced`
- **Verification command**: `uv run pytest`

## Notes

- Independent of T02+ once T01 is there, but does not strictly need
  T01/T02 to land first — this ticket uses the deployment's
  docker_context directly from rundbat.yaml.
- Bump `pyproject.toml` version.

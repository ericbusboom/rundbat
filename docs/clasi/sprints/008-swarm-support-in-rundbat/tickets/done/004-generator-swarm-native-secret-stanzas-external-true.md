---
id: '004'
title: 'Generator: Swarm-native secret stanzas (external: true)'
status: in-progress
use-cases:
- SUC-002
depends-on:
- '003'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T04 — Generator: Swarm-native secret stanzas

## Description

Extend the swarm branch of `generate_compose_for_deployment` (T03) to
emit Swarm-native secret stanzas when the deployment has `swarm: true`
AND secrets are declared in the project config.

Emitted output (in addition to T03's artifacts):

1. **Top-level `secrets:` stanza** with `external: true` entries:
   ```yaml
   secrets:
     <app>_postgres_password:
       external: true
     <app>_session_secret:
       external: true
   ```
   Each secret name matches the Swarm secret name produced by
   `rundbat secret create` (T07): `<app>_<key_lowercase>[_v<YYYYMMDD>]`.
   For the compose file, use the logical name without the version
   suffix; operators point the external reference at the currently
   active versioned secret by updating the Swarm service.

2. **Per-service `secrets:` attachments** with a stable `target:`
   matching the `_FILE` env-var convention:
   ```yaml
   services:
     app:
       secrets:
         - source: <app>_postgres_password
           target: postgres_password
       environment:
         POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
   ```
   The `target:` is the lowercased key; the `_FILE` env is set so the
   container reads the secret from `/run/secrets/<target>`.

3. **No secrets declared → no `secrets:` stanza emitted** (clean
   output).

The identification of "declared secrets" comes from the existing
secret-declaration path in the project config (same data the old
env-file generation uses for secret keys).

## Affected Files

- `src/rundbat/generators.py` — extend swarm branch of
  `generate_compose_for_deployment`
- `tests/unit/test_generators.py` — new tests

## Acceptance Criteria

- [x] Swarm-mode deployment with declared secrets emits a top-level
      `secrets:` stanza with `external: true` entries
- [x] Each declared secret gets a per-service `secrets:` attachment
      with `target: <key_lowercase>`
- [x] The corresponding `_FILE` env-var is set to
      `/run/secrets/<target>` on the service
- [x] Swarm-mode deployment with no declared secrets emits NO
      top-level `secrets:` block and no per-service `secrets:`
      attachments
- [x] Compose-mode (swarm: false) is unchanged (regression)
- [x] `uv run pytest` passes
- [x] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_generators.py`
- **New tests to write**:
  - `test_generate_compose_swarm_emits_secrets_stanza`
  - `test_generate_compose_swarm_service_secrets_attachment`
  - `test_generate_compose_swarm_file_env_var_set`
  - `test_generate_compose_swarm_no_secrets_no_stanza`
  - `test_generate_compose_non_swarm_no_secrets_stanza` (regression)
- **Verification command**: `uv run pytest`

## Notes

- Depends on T03 for the swarm-branch scaffolding.
- Secret naming must match T07's `rundbat secret create` output so
  the external reference resolves.
- Bump `pyproject.toml` version.

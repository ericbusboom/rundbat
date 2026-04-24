---
id: '002'
title: Declarative secrets schema and per-service routing
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: rundbat-swarm-secrets-feature-request.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Declarative secrets schema and per-service routing

## Description

Replace the flat `secrets: [KEY1, KEY2]` schema with a declarative
per-target map. Keep the flat list working as a back-compat
shorthand. Update the generator so each declared secret attaches
only to the services listed under `services:` instead of always
attaching to `app`.

### Schema (canonical form)

```yaml
deployments:
  prod:
    secrets:
      api_token:
        from_env: LEAGUESYNC_API_TOKEN
        services: [leaguesync-api]
      meetup_client_id:
        from_env: MEETUP_CLIENT_ID
        services: [leaguesync-cron]
```

### Back-compat (shorthand)

`secrets: [POSTGRES_PASSWORD, SESSION_SECRET]` expands at config
load to:

```yaml
secrets:
  POSTGRES_PASSWORD:
    from_env: POSTGRES_PASSWORD
    services: [app]
  SESSION_SECRET:
    from_env: SESSION_SECRET
    services: [app]
```

The expansion happens once in `load_config()` so downstream code
sees a single shape.

### Validation

Raise `ConfigError` when:
- Both `from_env` and `from_file` are set
- Neither is set (T03 will add `from_file` parsing — a placeholder
  branch is fine here)
- `services:` is missing or empty
- A target name collides between flat-list and map entries

### Generator changes

Rewrite `_collect_declared_secrets` (and rename it to something like
`_collect_secret_attachments`) to return a list of attachment
records: `{target, source, services, source_kind}` (`source_kind`
is `env` for now; `file` lands in T03).

The swarm-emission block in `generate_compose` walks this list and:
- Adds `secrets:` attachments only to services in the secret's
  `services:` list
- Emits `<KEY>_FILE=/run/secrets/<target>` env var only on those
  same services, only when `source_kind == "env"`
- Adds the versioned external entry to the top-level `secrets:`
  block once

## Acceptance Criteria

- [x] `load_config()` (or a callee) normalizes both flat-list and
      declarative-map forms to the canonical map shape before
      returning
- [x] Schema validation raises `ConfigError` for invalid entries
      (mutually-exclusive `from_env`/`from_file`, missing services)
- [x] Generator attaches each declared secret only to the services
      in its `services:` list
- [x] `*_FILE` env vars emitted on listed services only
- [x] Top-level `secrets:` block lists each declared external name
      with `external: true`
- [x] Existing tests in `tests/unit/test_generators.py` for the
      flat-list shape still pass without change
- [x] New tests cover: declarative map round-trip, per-service
      routing, validation errors, flat-list expansion is exact
- [x] Version bumped via `clasi version bump`
- [x] All tests pass; commit references T02

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**:
  - `test_declarative_secrets_normalized` — flat list and map
    produce identical normalized output
  - `test_secret_validation_errors` — every error case raises
    `ConfigError` with a clear message
  - `test_generator_per_service_routing` — multi-service compose
    only attaches each secret to listed services
  - `test_generator_env_file_var_emission` — `*_FILE` env var only
    on listed services
- **Verification command**: `uv run pytest`

---
sprint: "010"
status: ready
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update -- Sprint 010: Swarm Secrets Declarative Management and Bugfix

## What Changed

### `src/rundbat/config.py`

- **New** `load_env_dict(env: str) -> dict` — runs
  `dotconfig load -d <env> --no-export --json --flat -S` and parses
  the JSON. Returns a clean `{KEY: value}` dict.
- **New** `load_env_file(env: str, filename: str) -> str` — runs
  `dotconfig load -d <env> --file <filename> --stdout` and returns
  the decrypted file content. Used for `from_file` secrets.
- **Existing** `load_env()` stays for any caller still on text mode
  (none in production paths after this sprint).
- **New** declarative-secrets schema parsing in `load_config()` —
  validates `secrets:` block on read. Both flat-list and per-target
  map are accepted; the flat list is normalized to the map at load
  time so downstream code only sees one shape.
- **New** `manager_context_for(deployment_cfg)` helper — returns
  `deployment_cfg.get("manager") or deployment_cfg["docker_context"]`.

### `src/rundbat/cli.py`

- **Rewrite** `cmd_secret_create` to use `config.load_env_dict()`.
  Adds `--from-file <path>` and `--target-name <name>` flags. When
  `--from-file` is set the value comes from
  `config.load_env_file()` and `target-name` (defaults to the file
  stem) controls the versioned secret name.
- **New** `cmd_secrets` (plural) — top-level
  `rundbat secrets <env> [--list|--dry-run|--rotate <target>]`. Reads
  the normalized declarative `secrets:` block and walks each entry
  through `secret create` semantics. Targets `manager_context`.
- **New** internal helpers:
  - `_list_swarm_secrets(ctx, prefix)` — runs `docker secret ls
    --filter name=<prefix> --format <fmt>`, returns a dict
    `{target: latest_versioned_name}`
  - `_rotate_swarm_secret(...)` — orchestrates create → swap →
    wait → remove
  - `_wait_for_service_convergence(ctx, stack, services)` — polls
    `docker service ps` until all listed services' tasks reach
    Running on the new spec or until a timeout is hit
- `_parse_env_text` is unchanged but no longer called by
  `cmd_secret_create`.

### `src/rundbat/generators.py`

- **Rewrite** `_collect_declared_secrets` →
  `_collect_secret_attachments(deployment_cfg, included_services)`
  returning a list of dicts `{target, source, services, source_kind}`
  where `source_kind` is `env` or `file`.
- **Rewrite** the swarm-secrets emission block (lines 540–563) to
  walk the per-target map and attach each secret only to the
  services in its `services:` list. The corresponding `*_FILE`
  env var is emitted only for `source_kind == "env"`. Top-level
  `secrets:` block lists every declared external name as
  `external: true`.

### `src/rundbat/content/skills/docker-secrets-swarm.md`

- Rewrite the "Rundbat integration" section to describe the
  declarative `secrets:` map, the `rundbat secrets <env>` plural
  command, and the `manager:` field. Remove the lingering
  "hand-edit the compose file" guidance and the back-fill
  workflow about `name:` overrides on rotation (rotation now runs
  via `rundbat secrets --rotate`).

### Tests

- `tests/unit/test_config.py` (new tests) — `load_env_dict()` over
  every quoting / comment edge case, schema validation for
  declarative `secrets:`, manager defaulting.
- `tests/unit/test_generators.py` — extend secret-emission tests to
  cover per-service routing, `from_file` entries, and the
  flat-list back-compat path.
- `tests/unit/test_cli_secret.py` (new) — singular `secret create`
  with and without `--from-file`; plural `secrets` with `--list`,
  `--dry-run`, and `--rotate` (with the docker calls mocked).

## Why

The sprint addresses two reported issues. The bug TODO is the
critical one — `secret create` is unusable today because the
text-parse path mishandles `export`, quotes, comments, and inline
comments. The feature TODO captures the part of sprint 008's plan
that didn't ship: declarative schema, plural command, file-based
secrets, rotation, and the manager / runtime context split.
Together they let projects delete hand-rolled
`prod-make-secrets.sh` scripts and YAML overlays.

## Impact on Existing Components

- **Back-compat preserved.** Existing `secrets: [KEY1]` lists keep
  working — they expand at config load to
  `{KEY1: {from_env: KEY1, services: [app]}}`. No project edits
  required.
- **Generator output changes** for projects with multi-service
  deployments. Pre-sprint, every declared secret attached to the
  `app` service. Post-sprint, secrets attach only to listed
  services. For single-service stacks this is a no-op; for
  multi-service stacks it is what the existing rundbat docs
  always implied.
- **`_parse_env_text` is dead code in production paths** but is
  retained — its removal is left to a future cleanup ticket.
- **CLI surface gains `secrets` plural command.** No existing
  command name changes.
- **Skill content reworks** invalidate any LLM-cached version of
  `docker-secrets-swarm.md`.

## Migration Concerns

- **Generator drift on regenerate.** Multi-service projects that
  regenerate compose after this sprint will see secrets removed
  from services that aren't listed in the new `services:` array.
  This is the intended fix; the sprint announcement notes this.
- **`manager:` defaulting.** Single-context deployments get
  `manager == docker_context` automatically. Multi-context users
  add the field explicitly.
- **Close-time version regression.** `mcp__clasi__close_sprint`
  internally calls `tag_version`, which clobbers pyproject with
  `<latest-tag>+1`. Documented in user memory; bump forward with
  `clasi version bump` after close if it matters.

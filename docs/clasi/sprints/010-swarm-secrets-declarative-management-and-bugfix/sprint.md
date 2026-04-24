---
id: "010"
title: "Swarm Secrets Declarative Management and Bugfix"
status: planning
branch: sprint/010-swarm-secrets-declarative-management-and-bugfix
use-cases: [uc-secret-create-bug, uc-declarative-secrets, uc-secrets-from-file, uc-secrets-cmd, uc-secrets-manager]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010: Swarm Secrets Declarative Management and Bugfix

## Goals

Make `rundbat secret create` actually work, then complete the declarative
swarm-secrets feature kicked off in sprint 008. After this sprint a
project can declare its swarm secrets in `rundbat.yaml` and use
`rundbat secrets <env>` to create / list / rotate them — no hand-rolled
bash scripts and no hand-edited compose overlays.

## Problem

Two related problems:

1. **`rundbat secret create` is broken.** The `_parse_env_text` path
   keeps the `export ` prefix in keys, leaves quotes around values,
   and folds inline comments into the value. Every call against a
   real dotconfig deployment fails with "Key not found".

2. **Sprint 008 only shipped 30% of the swarm-secrets feature.** It
   accepts a flat `secrets: [KEY1, KEY2]` list, hardcodes attachment
   to the `app` service, has no `from_file` support, no plural
   `secrets` command, no rotation, no manager / docker_context split.
   Projects still hand-roll `prod-make-secrets.sh` and a YAML overlay.

## Solution

Five tickets, sequenced by dependency:

- **T01** rewrites `cmd_secret_create` to use a clean
  `config.load_env_dict()` (JSON output from `dotconfig load
  --no-export --json --flat -S`). All four parsing bugs die at once.
- **T02** introduces the declarative `secrets:` schema (per-target
  map with `from_env` / `from_file` / `services:`). The flat list
  stays as a back-compat shorthand. Generator emits per-service
  attachments instead of always-`app`.
- **T03** adds `--from-file` to `rundbat secret create` and wires the
  declarative schema's `from_file` entries through the same path.
- **T04** introduces `rundbat secrets <env>` (plural) with `--list`,
  `--dry-run`, and `--rotate <target>`. Queries the manager for state
  via `docker secret ls --filter name=<prefix>` (no state file).
- **T05** adds the optional `manager:` field per deployment (defaults
  to `docker_context`) and refreshes `docker-secrets-swarm.md` to
  describe the new declarative interface.

## Success Criteria

- `rundbat secret create <env> <KEY>` succeeds for any key in the
  deployment's dotconfig env; secret content is byte-for-byte correct
- `rundbat.yaml` accepts both the legacy flat list and the new
  declarative `secrets:` map; existing rundbat.yaml files keep working
- `rundbat generate` emits per-service attachments matching the
  declared `services:` list and supports `from_file` entries
- `rundbat secrets <env>` creates all declared secrets idempotently;
  `--list` reports present-vs-missing against the manager;
  `--rotate <target>` does create → swap → wait → remove safely
- `docker-secrets-swarm.md` no longer says "hand-edit the compose
  file"; it documents the new interface end-to-end
- All existing tests still pass; new regression coverage for the
  parsing bug and per-service routing

## Scope

### In Scope

- Bugfix in `cmd_secret_create` (T01)
- New declarative `secrets:` schema with back-compat for flat list (T02)
- Per-service routing in the generator (T02)
- `--from-file` support on singular and plural commands (T03)
- New `rundbat secrets <env>` plural command with list / dry-run /
  rotate (T04)
- Optional `manager:` field per deployment (T05)
- Skill / docs refresh for `docker-secrets-swarm.md` (T05)
- Regression tests for the parsing bug, schema validation,
  per-service emission, and rotation flow

### Out of Scope

- Vault / AWS Secrets Manager / 1Password backends — dotconfig stays
  the source of truth
- Auto-rotate on deploy — rotation stays explicit
- Caching the manager-secret-listing — query directly each time
- Rewriting `_parse_env_text` (left in place for any legacy callers;
  secret commands stop using it)

## Test Strategy

- Unit tests against `config.load_env_dict()` cover plain,
  single-quoted, double-quoted, `#`-in-value, and inline-comment
  cases — fixturing the dotconfig output via subprocess monkeypatch
- Generator tests assert that flat-list and declarative-map schemas
  produce equivalent compose output for the trivial case, and that
  per-service routing only attaches secrets to listed services
- A new test exercises `from_file` path emission (no `*_FILE` env
  var by default, attachment shape correct)
- `rundbat secrets --list` and `--dry-run` get unit tests against a
  mocked `docker secret ls` to verify the present/missing logic
- Rotation flow gets a unit test that asserts the command sequence
  (create → service update --secret-rm/--secret-add → wait → rm)
- Existing test suite (294 passed + 1 skipped at sprint start)
  must still pass on every ticket commit

## Architecture Notes

- **Back-compat is non-negotiable.** Flat list `secrets: [KEY1]`
  expands to `{KEY1: {from_env: KEY1, services: [app]}}`. No project
  needs to migrate to keep working.
- **Manager vs docker_context split.** `manager:` defaults to
  `docker_context`; secret-management commands (`rundbat secrets …`,
  `rundbat secret create`) target `manager`; lifecycle commands
  (`up`, `down`, `restart`, `logs`) keep targeting `docker_context`.
- **State lives on the manager.** No `rundbat.state.yaml` file —
  query `docker --context <manager> secret ls --filter
  name=<prefix>` whenever rundbat needs to know what's there.
- **Versioning format** stays `{app}_{target}_v{YYYYMMDD}` and is
  applied uniformly by both `secret create` and `secrets`.
- **`_parse_env_text` is not deleted.** Sprint 008 left it as the
  parse path; we move secret commands to the dict path but leave the
  text parser alone to avoid scope creep.
- **Out-of-process execution.** Sub-agent dispatch isn't available
  in this harness, so the team-lead writes code directly under the
  `.clasi-oop` marker — same pattern as sprints 008 and 009.

## GitHub Issues

(none)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed (stakeholder pre-approved scope and design)
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| T01 | Fix dotconfig load path in `secret create` | — | 1 |
| T02 | Declarative `secrets:` schema and per-service routing | T01 | 2 |
| T03 | `--from-file` support on `secret create` and generator | T02 | 3 |
| T04 | `rundbat secrets` plural command with list/dry-run/rotate | T03 | 4 |
| T05 | Optional `manager:` field and skill/doc refresh | T04 | 5 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.). All tickets here
are sequential because each builds on the previous one.

---
sprint: "002"
status: draft
---

# Architecture Update -- Sprint 002: Docker Directory Generation

## What Changed

### Added
- `src/rundbat/generators.py` — template-based generation for Dockerfile,
  docker-compose.yml, Justfile, and .env.example
- CLI commands: `rundbat init-docker`, `rundbat add-service <type>`
- `rundbat.yaml` extended with `framework` and `services` fields

### Modified
- `cli.py` — new subcommands wired to generators module
- `config.py` — helpers to read/write framework and services config

## Why

Phase C of the CLI conversion: rundbat's primary artifact is the `docker/`
directory. Until this sprint, skills described the workflow but no code
existed to generate the artifacts.

## Impact on Existing Components

- `config.py`: minor additions to read `framework` and `services` from
  `rundbat.yaml`. No changes to existing functions.
- `cli.py`: new subcommands only, no changes to existing commands.
- No new dependencies — templates use Python string formatting.

## Migration Concerns

None. New functionality only, no breaking changes.

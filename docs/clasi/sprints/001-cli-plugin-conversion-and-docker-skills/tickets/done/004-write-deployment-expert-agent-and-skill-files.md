---
id: '004'
title: Write deployment-expert agent and skill files
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
todo: deployment-use-cases.md
---

# Write deployment-expert agent and skill files

## Description

Write the markdown content files that will be installed by ticket 003.
These are Claude Code integration files — agent definitions, skills,
and rules that teach Claude how to use rundbat.

**Agent: `agents/deployment-expert.md`**
- Role: deployment expert for Docker-based web applications
- Knows: project types, services, Docker Compose, dotconfig
- Config access: `dotconfig load -d {env} --json --flat -S`
- Executes: `rundbat` CLI commands

**Skills (under `skills/`):**
- `init-docker.md` — scaffold `docker/` directory with Dockerfile,
  compose, Justfile. Reads `rundbat.yaml` for app type and services.
- `dev-database.md` — quick `docker run` for local dev. Loads config
  via `dotconfig load --json --flat`, saves connection string as secret.
- `diagnose.md` — read state, compare config vs actual containers,
  report issues. Uses sectioned `dotconfig load --json` to inspect
  public vs secret separation.
- `manage-secrets.md` — round-trip secret editing via `dotconfig load
  --json` / modify / `dotconfig save --json`.

**Rules: `rules/rundbat.md`**
- When to invoke the deployment-expert agent
- When to use skills directly
- When to call `rundbat` CLI commands
- Config access patterns (dotconfig --json --flat)

All files go in `src/rundbat/` subdirectories so they're bundled with
the package and installed by `rundbat install` (ticket 003).

## Acceptance Criteria

- [ ] `src/rundbat/agents/deployment-expert.md` exists with complete agent definition
- [ ] `src/rundbat/skills/init-docker.md` exists
- [ ] `src/rundbat/skills/dev-database.md` exists
- [ ] `src/rundbat/skills/diagnose.md` exists
- [ ] `src/rundbat/skills/manage-secrets.md` exists
- [ ] `src/rundbat/rules/rundbat.md` exists
- [ ] All skills reference `dotconfig load --json` for config access
- [ ] All skills reference `rundbat` CLI commands (not MCP tools)
- [ ] Skills reference use cases from `deployment-use-cases.md`

## Testing

- **Existing tests to run**: None (content-only ticket)
- **New tests to write**: Verify files exist and contain expected
  sections (agent role, config access pattern, CLI commands)
- **Verification command**: `ls src/rundbat/skills/ src/rundbat/agents/ src/rundbat/rules/`

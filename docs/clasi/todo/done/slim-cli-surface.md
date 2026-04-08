---
status: done
sprint: '005'
tickets:
- 005-001
---

# Slim CLI to four commands

Reduce the rundbat CLI from 17 top-level commands to 4:

- `init` — first-time setup (absorb install + discover checks)
- `init-docker` — generate Docker artifacts from config
- `deploy` — deploy to a named remote host via Docker context
- `deploy-init` — set up a new deployment target

## Commands to remove

install, uninstall, discover, create-env, get-config, start, stop,
health, validate, set-secret, check-drift, add-service, env (list, connstr)

## What stays

- Underlying modules (database.py, environment.py, discovery.py, config.py)
  stay as library code — just no longer exposed as CLI commands.
- discover checks fold into `init` (warn if Docker/dotconfig missing).
- install behavior already happens inside `init`.

## Skills and agent docs to rewrite

- `dev-database.md` — rewrite to use docker compose instead of create-env/health/get-config
- `deployment-expert.md` — remove references to cut commands
- `diagnose.md` — rewrite without validate/health commands
- `manage-secrets.md` — point at dotconfig directly
- `rules/rundbat.md` — update command list

## Tests to update

- `test_cli.py` — remove tests for cut commands, keep tests for remaining 4

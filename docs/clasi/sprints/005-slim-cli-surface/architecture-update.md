---
sprint: "005"
status: draft
---

# Architecture Update — Sprint 005: Slim CLI Surface

## What Changed

Removed 13 CLI commands from cli.py: install, uninstall, discover,
create-env, get-config, start, stop, health, validate, set-secret,
check-drift, add-service, env (list, connstr). Kept 4: init, init-docker,
deploy, deploy-init.

Rewrote bundled skills and agent docs to reference docker compose and
dotconfig directly instead of removed commands.

Folded discover checks into init (warn if Docker/dotconfig missing).

## Why

The large command surface duplicated docker compose and dotconfig
functionality. The agent doesn't need wrapper commands — it can call
compose and dotconfig directly with skill guidance.

## Impact on Existing Components

- **cli.py**: 13 command handlers and subparsers removed
- **Bundled content**: All skills and agent docs rewritten
- **Library modules**: database.py, environment.py, discovery.py, config.py
  remain as library code but are no longer called from CLI
- **generators.py**: Unchanged (used by init-docker)

## Migration Concerns

Breaking change for anyone using the removed commands directly. Projects
should use docker compose and dotconfig instead.

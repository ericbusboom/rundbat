---
sprint: "004"
status: draft
---

# Architecture Update — Sprint 004: Remote Deploy Command

## What Changed

Added `src/rundbat/deploy.py` module for remote deployment via Docker
contexts. Added `deployments` section to `rundbat.yaml` config schema.
Added `deploy` and `deploy-init` CLI commands. Updated Justfile generator
to emit `rundbat deploy` instead of a stub recipe.

## Why

The test project's hand-written Justfile had a complex 15-line deploy
recipe with SSH key management, docker save/load pipes, scp, and
platform-specific builds. Using Docker contexts eliminates all of this
complexity — deploy becomes `docker compose up -d --build` targeting a
remote daemon.

## New Components

### deploy.py

New service module (~80-100 lines) with:
- `load_deploy_config(name)` — read named deployment from rundbat.yaml
- `ensure_context(app_name, deploy_name, host)` — verify or create
  Docker context
- `create_context(name, host)` — `docker context create`
- `verify_access(host)` — `ssh <host> docker info`
- `deploy(name, dry_run, no_build)` — orchestrator

Follows existing subprocess patterns (`_run_docker` in database.py).

### Config schema addition

```yaml
deployments:
  prod:
    host: ssh://root@docker1.apps1.jointheleague.org
    compose_file: docker/docker-compose.prod.yml
    hostname: rundbat.apps1.jointheleague.org
```

- `host` — SSH URL for Docker context (required)
- `compose_file` — path to compose file (defaults to docker/docker-compose.yml)
- `hostname` — app URL for post-deploy message (optional)

### CLI commands

- `rundbat deploy <name>` with `--dry-run`, `--json`, `--no-build`
- `rundbat deploy-init <name> --host <ssh://user@host>`

## Impact on Existing Components

- **generators.py**: `generate_justfile()` deploy recipe changes from
  `docker compose up -d --pull always` to `rundbat deploy {{env}}`
- **cli.py**: Two new subparsers added
- **rundbat.yaml**: New optional `deployments` key — backward compatible

## Migration Concerns

None. The `deployments` key is optional. Existing projects without it
continue to work. The generated Justfile change only takes effect on
next `rundbat init-docker`.

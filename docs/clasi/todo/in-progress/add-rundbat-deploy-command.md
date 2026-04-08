---
status: in-progress
sprint: '004'
tickets:
- 004-001
---

# Add `rundbat deploy <name>` CLI command

Deploy to a named remote Docker host using Docker contexts. The user's
SSH access to the host is a precondition — key distribution is out of
scope for rundbat.

## Description

Add a `rundbat deploy <name>` command that looks up a named deployment
configuration in `rundbat.yaml` and runs `docker compose up -d --build`
against the corresponding Docker context.

## Config schema

Deployments are named configurations in `rundbat.yaml`:

```yaml
deployments:
  prod:
    host: ssh://root@docker1.apps1.jointheleague.org
    compose_file: docker/docker-compose.prod.yml
    hostname: rundbat.apps1.jointheleague.org  # for post-deploy message
  staging:
    host: ssh://root@staging.example.com
    compose_file: docker/docker-compose.yml
```

## Commands

### `rundbat deploy <name>`

1. Read the named deployment from `rundbat.yaml`
2. Ensure a Docker context exists for it (create if missing from `host`)
3. Run `docker --context <ctx> compose -f <compose_file> up -d --build`

Flags: `--dry-run`, `--json`, `--no-build`

### `rundbat deploy-init <name> --host <ssh://user@host>`

Convenience to add a deployment config and set up the Docker context:
1. Verify SSH access: `ssh user@host docker info`
2. Create Docker context: `docker context create <app>-<name> --docker "host=ssh://user@host"`
3. Save deployment to `rundbat.yaml`

Also works with pre-existing contexts if the developer set one up manually.

## Preconditions (out of scope)

- SSH key distribution and access management
- Docker installation on the remote host
- Reverse proxy / TLS setup on the remote host

## Implementation

- New module: `src/rundbat/deploy.py` (~80-100 lines)
- CLI handlers: `cmd_deploy`, `cmd_deploy_init` in `cli.py`
- Update `generate_justfile()` to emit `rundbat deploy <name>` recipe
- New tests: `tests/unit/test_deploy.py`

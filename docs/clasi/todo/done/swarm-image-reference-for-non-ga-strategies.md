---
status: done
sprint: 009
tickets:
- 009-001
---

# Swarm stack deploy fails with `build:`-only compose — emit or require an `image:` in swarm mode

## Context

Found during live verification of sprint 008 against swarm1/swarm2. When a deployment is configured with `swarm: true` + `deploy_mode: stack` + `build_strategy: context` or `ssh-transfer`, the generated compose has `build:` but no `image:` field. `docker stack deploy` ignores `build:` (Swarm does not build; it pulls images that are already built and available to worker nodes) and bails:

```
$ docker --context swarm2 stack deploy -c docker/docker-compose.swarm-test.yml swarm-smoke_swarm-test
Ignoring unsupported options: build, restart
invalid image reference for service app: no image specified
```

`build_strategy: github-actions` works because that path already emits `image: ghcr.io/owner/<app>:latest` and no `build:`. `context` and `ssh-transfer` are the broken strategies.

## What the generator does today

[`generate_compose_for_deployment()`](src/rundbat/generators.py) around line 433:

```python
if build_strategy == "github-actions" and image:
    app_svc["image"] = f"{image}:latest"
elif build_strategy == "github-actions":
    app_svc["image"] = f"ghcr.io/owner/{app_name}:latest"
else:
    app_svc["build"] = {"context": "..", "dockerfile": "docker/Dockerfile"}
```

That `else` branch is fine for compose mode (docker compose can build+run in one step) but wrong for stack mode.

## Goals

1. `rundbat generate` produces a stack-ready compose for every build_strategy + swarm combination — or fails loudly at generate time with a helpful message if the config cannot be reconciled.
2. No silent `docker stack deploy` failures at runtime with opaque "no image specified" messages.
3. Existing `build_strategy: github-actions` + swarm path keeps working exactly as today.

## Options

Three reasonable designs, roughly ordered most-to-least rundbat-native:

### Option A — Emit `image:` from config, keep `build:` for local builds (recommended)

Add a deployment-level `image` field that works for any strategy (not only github-actions). When `swarm: true`, require it. Emit both `build:` and `image:` so `docker compose build` tags the image correctly and `docker stack deploy` pulls/runs it. For `ssh-transfer`, the image reference can be a local tag like `<app>:latest` that the transfer step pushes to the swarm nodes. For `context`, the image is built on the remote and referenced by name.

```yaml
# rundbat.yaml
deployments:
  prod:
    swarm: true
    deploy_mode: stack
    build_strategy: ssh-transfer
    image: myapp:prod          # required when swarm: true
    docker_context: swarm1
```

Generator:
```yaml
services:
  app:
    image: myapp:prod
    build:
      context: ..
      dockerfile: docker/Dockerfile
    deploy: …
```

### Option B — Auto-derive an image tag

Default the image to `<app_name>:<deployment_name>` when `swarm: true` and no explicit `image:` is given. Same generator output as A. Downside: implicit behavior; the user doesn't know where the image will be pushed/pulled from.

### Option C — Refuse to generate, with a clear error

If `swarm: true` and no `image:`, `generate` exits with:

```
Error: deployment 'prod' has swarm: true but no image: configured.
Swarm cannot build images — set deployments.prod.image in rundbat.yaml
(e.g. image: myapp:prod) or switch to build_strategy: github-actions.
```

Simplest implementation; no inference. The user picks and moves on.

**Recommendation: A + C.** Treat `image:` as required when `swarm: true`. Emit both fields when provided. Error cleanly when missing. Most configurations either already have an image (github-actions) or can trivially add one.

## Scope — in

- [`src/rundbat/generators.py`](src/rundbat/generators.py) — `generate_compose_for_deployment`: when `swarm: true`, require `image` on the deployment; emit `image:` alongside `build:` for context/ssh-transfer strategies; keep github-actions path unchanged.
- [`src/rundbat/cli.py`](src/rundbat/cli.py) — `generate` / `validate` / `deploy-init` — validate at config-save time so errors surface early; `deploy-init` should prompt for an image when picking `deploy_mode: stack` with a build-on-host strategy.
- `ssh-transfer` strategy: existing transfer logic in [`src/rundbat/deploy.py`](src/rundbat/deploy.py) tags the image — confirm the tag it produces matches the compose `image:` field or reconcile.
- Tests in `tests/unit/test_generators.py` — matrix of swarm × (context, ssh-transfer, github-actions) × (image supplied, missing). Assert the compose is stack-deployable in every valid combination and that missing-image fails at `generate` with a clear error.
- Skill updates: `docker-swarm-deploy.md` (explain the image requirement and how each strategy satisfies it), `deploy-init.md` (mention the new prompt), `diagnose.md` (add the "no image specified" failure to the troubleshooting table pointing at this field).

## Scope — out

- Auto-building the image as part of `rundbat up` in swarm mode. Out of scope — Swarm is declarative; the user should `rundbat build` first, then `rundbat up`. Leave that workflow to the user.
- Redesigning the `image` field to be top-level (not per-deployment). Per-deployment stays more flexible.

## Key files to touch

- `src/rundbat/generators.py` (`generate_compose_for_deployment`, line ~433 image/build branching)
- `src/rundbat/cli.py` (`cmd_generate` validation hook; `cmd_deploy_init` prompt)
- `src/rundbat/deploy.py` (ssh-transfer tagging — align with the emitted `image:`)
- `src/rundbat/content/skills/docker-swarm-deploy.md`
- `src/rundbat/content/skills/deploy-init.md`
- `src/rundbat/content/skills/diagnose.md`
- `tests/unit/test_generators.py`

## Verification

1. `uv run pytest` — all tests pass, new matrix tests cover every strategy.
2. Live against swarm1 (manager) — configure a deployment as `swarm: true` + `build_strategy: ssh-transfer` + `image: swarm-smoke:prod`, run `rundbat build` then `rundbat up`, confirm the stack deploys and the image in `docker --context swarm1 service ls` matches.
3. Config error path — `rundbat generate` with `swarm: true` and no `image:` → clean error, non-zero exit, no partial compose written.

## Dependencies / ordering

- No prerequisite TODOs. Can be a single-ticket follow-up to sprint 008.

## Reference to the live-test finding

This TODO captures Bug 2 from the sprint 008 live verification. Bug 1 (missing compose file emission for stack mode) was fixed in commit `b301a24`. Three minor rough edges (env var hyphens, redundant `restart:`, `--detach` deprecation) were fixed in commit `586299f`.

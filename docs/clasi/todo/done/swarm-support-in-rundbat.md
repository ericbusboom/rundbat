---
status: done
sprint: 008
tickets:
- 008-001
- 008-002
- 008-003
- 008-004
- 008-005
- 008-006
- 008-007
- 008-008
---

# Swarm support in rundbat: detection probe, opt-in flag, and skill integration for Swarm-native Docker secrets

## Context

rundbat today treats every deployment as a `docker compose` target. A vestigial `swarm: bool` parameter exists on the legacy `generate_compose()` and `init_docker()` functions (generators.py:278, 1072) where it only toggles Caddy label placement (`services.X.deploy.labels` vs `services.X.labels`). The current per-deployment path — `generate_compose_for_deployment()` at generators.py:365 — ignores `swarm` entirely. CLI lifecycle commands (`up`/`down`/`restart`/`build`/`logs`) shell out to `docker compose -f …`; nothing ever calls `docker stack deploy`. The `docker-secrets-swarm` skill (added in sprint 0.20260424.4) already documents the Swarm secret workflow but explicitly notes "rundbat doesn't currently generate Swarm-secret stanzas."

This TODO closes that gap end-to-end: detect Swarm on the target, let deployments opt in, and generate the stack-compatible compose + secret stanzas that the `docker-secrets-swarm` skill teaches.

## Goals

1. **Detect Swarm on a deployment target.** Extend `rundbat probe` (currently only detects Caddy at deploy.py) to also check `docker info --format '{{.Swarm.LocalNodeState}}'` against the deployment's Docker context, and record `swarm: true/false` + `swarm_role: manager|worker|""` back into rundbat.yaml under the deployment entry.
2. **Honor `swarm: true` as an opt-in flag** in the per-deployment path. The field already parses in legacy init-docker; wire it into `generate_compose_for_deployment()` so:
   - Caddy labels go under `deploy.labels` (Swarm requirement)
   - Per-deployment compose file includes a minimal `deploy:` block per service (restart_policy, update_config)
   - A commented `# deploy with: docker stack deploy -c …` header lands at the top of the generated compose
3. **CLI-level stack lifecycle.** Add `deploy_mode: stack` (alongside existing `compose` and `run`). When set, `rundbat up` runs `docker stack deploy -c <file> <stack-name>`, `rundbat down` runs `docker stack rm <stack-name>`, `rundbat logs` runs `docker service logs`. Auto-upgrade to `stack` if the probe found Swarm *and* `swarm: true` is set.
4. **Generate Swarm-native secret stanzas** when the deployment has `swarm: true` and the config has declared secrets. Emit top-level `secrets:` with `external: true` entries and attach them to services with stable `target:` names matching the `_FILE` env-var convention. The `docker-secrets-swarm` skill already documents the downstream workflow — this wires the compose emission.
5. **Update skills and the deployment-expert agent doc** so agents know when to steer users toward Swarm, how to run the probe, and what rundbat will and won't do for them.

## Scope — in

- New `rundbat.discovery.detect_swarm(context: str) -> dict` (mirrors existing `detect_caddy` in discovery.py).
- Extend `cmd_probe()` at cli.py:280 to record both `reverse_proxy` and `swarm`/`swarm_role` in `rundbat.yaml`.
- Wire `swarm: bool` into `generate_compose_for_deployment()` and downstream Justfile recipes (generators.py). Caddy labels, service-level `deploy:` blocks, and (when present) `secrets:` top-level with per-service attachments.
- Add `deploy_mode: stack` branch in cli.py's `_resolve_deployment`-driven lifecycle commands (`cmd_up`/`cmd_down`/`cmd_restart`/`cmd_logs`). Stack name defaults to `<app_name>_<deployment_name>`.
- `deploy-init` prompt flow (skill + `cmd_deploy_init`): after the user picks a remote host, auto-probe; if Swarm detected, ask whether to opt in with `swarm: true` + `deploy_mode: stack`.
- New / updated skills:
  - `docker-swarm-deploy.md` — new skill: when to use Swarm vs compose, how rundbat detects/drives it, stack lifecycle commands, one-node Swarm as a viable middle ground.
  - `docker-secrets-swarm.md` — remove the "rundbat doesn't generate Swarm-secret stanzas" caveat; show the actual `rundbat generate` output with `secrets: external: true` and document the `rundbat secret create` helper (see below).
  - `deploy-init.md` and `deploy-setup.md` — brief additions describing the Swarm probe step.
  - `diagnose.md` — add Swarm-specific troubleshooting (`docker service ps`, `docker node ls`, why a stack may stay in `starting` without manager quorum).
- New command: `rundbat secret create <env> <KEY>` that reads from dotconfig and pipes into `docker --context <ctx> secret create <app>_<key>_v<YYYYMMDD> -`, so users don't hand-run the rotation recipe from the skill. (Optional but completes the loop.)
- Tests:
  - `test_discovery.py` — `detect_swarm()` with mocked `docker info` JSON outputs for active/inactive/error states.
  - `test_generators.py` — `generate_compose_for_deployment` with `swarm: true` emits `deploy.labels`, service-level `deploy:` block, and (when secrets listed) top-level `secrets:` with `external: true`.
  - `test_cli.py` — `deploy_mode: stack` dispatches to `docker stack deploy` / `docker stack rm` and passes the right stack name.

## Scope — out (document as future follow-ups)

- Generating overlay networks automatically (users can hand-add).
- `mode: global` / `replicas:` tuning from rundbat.yaml. Default to `replicas: 1` for simplicity; users tune the generated file.
- Rolling update orchestration beyond what Swarm does by default.
- Multi-manager cluster bootstrap (`docker swarm init` / `join-token` automation).

## Key files to touch

- `src/rundbat/discovery.py` — add `detect_swarm()`
- `src/rundbat/cli.py` — `cmd_probe` (swarm recording), stack lifecycle in `cmd_up`/`cmd_down`/`cmd_restart`/`cmd_logs`, new `cmd_secret_create`
- `src/rundbat/generators.py` — wire `swarm` through `generate_compose_for_deployment`, emit `deploy:` + `secrets:` stanzas, adjust Justfile recipes for stack mode
- `src/rundbat/deploy.py` — `deploy_mode == "stack"` branch in `init_deployment` / `deploy`
- `src/rundbat/content/skills/docker-swarm-deploy.md` — new
- `src/rundbat/content/skills/docker-secrets-swarm.md` — remove caveat, show generated output
- `src/rundbat/content/skills/deploy-init.md`, `deploy-setup.md`, `diagnose.md` — Swarm notes
- `src/rundbat/content/agents/deployment-expert.md` — one bullet for Swarm capability
- `tests/unit/test_discovery.py`, `test_generators.py`, `test_cli.py` — new assertions

## Verification

1. `uv run pytest` — all existing + new tests pass.
2. On a dev host with `docker swarm init` run, `rundbat probe prod` updates `rundbat.yaml` with `swarm: true` and `swarm_role: manager`.
3. `rundbat generate` then emits `docker/docker-compose.prod.yml` with `# docker stack deploy -c docker-compose.prod.yml <stack>` header, `services.app.deploy.labels` Caddy block, and (if secrets configured) `secrets: external: true` stanza.
4. `rundbat up prod` runs `docker stack deploy …` under the hood; `docker stack services <name>` shows the services, `docker stack ps <name>` shows tasks.
5. `rundbat secret create prod POSTGRES_PASSWORD` creates a versioned Swarm secret populated from dotconfig.
6. `rundbat down prod` runs `docker stack rm <name>`.
7. `rundbat --instructions | grep docker-swarm-deploy` shows the new skill listed.

## Dependencies / ordering notes

- `detect_swarm()` must land before the probe changes.
- Generator changes (`swarm` plumbing) should land before CLI lifecycle changes so generated files are ready when `rundbat up` starts running stack deploy.
- Skill doc updates can go last.
- `rundbat secret create` is optional for a first pass; without it, users follow the manual recipe already documented in `docker-secrets-swarm.md`.

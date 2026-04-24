---
id: "008"
title: "Swarm support in rundbat"
status: planning
branch: sprint/008-swarm-support-in-rundbat
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 008: Swarm support in rundbat

## Goals

Add first-class Docker Swarm support to rundbat — detection on the target,
deployment opt-in flag, stack-lifecycle commands, Swarm-native secret
stanzas in generated compose files, and skill/agent-doc updates so
Claude agents know when and how to steer users toward Swarm.

Close the existing gap where rundbat today treats every deployment as
a `docker compose` target and the `docker-secrets-swarm` skill documents
a workflow rundbat cannot yet generate.

## Problem

1. `rundbat probe` only detects Caddy; it does not record whether the
   Docker context has Swarm enabled.
2. A vestigial `swarm: bool` parameter exists on the legacy
   `generate_compose()` / `init_docker()` path (generators.py:278, 1072)
   where it only toggles Caddy label placement. The current
   per-deployment path (`generate_compose_for_deployment()` at
   generators.py:365) ignores `swarm` entirely.
3. CLI lifecycle commands (`up`/`down`/`restart`/`build`/`logs`) shell
   out to `docker compose -f …`; nothing ever calls `docker stack
   deploy`.
4. The `docker-secrets-swarm` skill (added sprint 0.20260424.4) documents
   the Swarm secret workflow but explicitly notes "rundbat doesn't
   currently generate Swarm-secret stanzas."

## Solution

End-to-end Swarm support in five strands:

1. **Detect** Swarm on a deployment target (new `detect_swarm()`
   mirroring `detect_caddy`).
2. **Record** `swarm` / `swarm_role` in `rundbat.yaml` from `rundbat
   probe`. Honor a transient-failure rule: never overwrite a prior
   `true` with `false` when the context is unreachable.
3. **Generate** stack-compatible compose artifacts when `swarm: true`:
   Caddy labels under `deploy.labels`, minimal per-service `deploy:`
   block (restart_policy, update_config, replicas: 1), Swarm-native
   `secrets: external: true` stanzas for declared secrets, and a
   `# Deploy with: docker stack deploy -c <file> <stack>` header
   comment.
4. **Drive** stack lifecycle from the CLI: new `deploy_mode: stack`
   branch in `cmd_up`/`cmd_down`/`cmd_restart`/`cmd_logs`. `up` →
   `docker stack deploy`; `down` → `docker stack rm`; `logs` →
   `docker service logs`. Auto-upgrade to stack mode when the probe
   found Swarm and the deployment has `swarm: true`.
5. **Document** via skills: new `docker-swarm-deploy.md`, revised
   `docker-secrets-swarm.md` (remove "rundbat doesn't generate"
   caveat), additions to `deploy-init.md`, `deploy-setup.md`,
   `diagnose.md`, and one bullet in `deployment-expert.md`.

A new helper command `rundbat secret create <env> <KEY>` pipes a
dotconfig value into `docker --context <ctx> secret create
<app>_<key>_v<YYYYMMDD> -`, closing the Swarm-secret rotation loop
that the skill documents.

## Success Criteria

- `rundbat probe <env>` on a Swarm host writes `swarm: true` and
  `swarm_role: manager|worker` to the deployment entry.
- `rundbat generate` emits `docker-compose.<name>.yml` with the stack
  header, `deploy:` blocks, Caddy labels under `deploy.labels`, and
  Swarm secret stanzas (when secrets are declared).
- `rundbat up <env>` runs `docker stack deploy` under the hood when
  `deploy_mode: stack`; `rundbat down` runs `docker stack rm`.
- `rundbat secret create <env> KEY` creates a versioned Swarm secret
  from a dotconfig value.
- `rundbat --instructions | grep docker-swarm-deploy` lists the new
  skill.
- All existing + new unit tests pass (`uv run pytest`).

## Scope

### In Scope

- `src/rundbat/discovery.py` — new `detect_swarm(context: str) -> dict`
- `src/rundbat/cli.py` — `cmd_probe` extended to record swarm state;
  new `deploy_mode: stack` branch in `cmd_up`/`cmd_down`/`cmd_restart`/
  `cmd_logs`; new `cmd_secret_create`
- `src/rundbat/generators.py` — `swarm` plumbing through
  `generate_compose_for_deployment`; `deploy:` + `secrets:` emission;
  Justfile recipes for stack mode
- `src/rundbat/deploy.py` — `deploy_mode == "stack"` branch in
  `init_deployment` / `deploy`, plus the `deploy-init` Swarm prompt
- `src/rundbat/content/skills/docker-swarm-deploy.md` — new
- `src/rundbat/content/skills/docker-secrets-swarm.md` — revised
- `src/rundbat/content/skills/deploy-init.md`, `deploy-setup.md`,
  `diagnose.md` — Swarm additions
- `src/rundbat/content/agents/deployment-expert.md` — one bullet for
  Swarm capability
- `tests/unit/test_discovery.py`, `test_generators.py`, `test_cli.py`
  — new assertions

### Out of Scope (future follow-ups)

- Generating overlay networks automatically
- `mode: global` / `replicas:` tuning from rundbat.yaml (default
  `replicas: 1`; users tune the generated file)
- Rolling update orchestration beyond Swarm defaults
- Multi-manager cluster bootstrap (`docker swarm init` / `join-token`
  automation)

## Test Strategy

- **`test_discovery.py`** — `detect_swarm()` with mocked `subprocess`
  outputs covering active (manager / worker), inactive, error, and
  unreachable states. Assert `{swarm, swarm_role, reachable}`.
- **`test_generators.py`** — `generate_compose_for_deployment(...,
  swarm=True)` emits `deploy.labels` for Caddy, service-level `deploy:`
  block, and (when secrets listed) top-level `secrets:` with
  `external: true` plus per-service `secrets:` attachments. Also
  verifies the stack-deploy header comment.
- **`test_cli.py`** — `deploy_mode: stack` dispatches to the correct
  `docker stack deploy` / `docker stack rm` / `docker service logs`
  commands with the expected stack name (`<app>_<deployment>`) and
  context. `cmd_secret_create` pipes dotconfig value into the expected
  `docker secret create` command.

Live Swarm verification (TODO steps 2–6) requires a cluster and is
deferred to the stakeholder's dev host. Unit tests cover the
equivalent code paths with mocked subprocess boundaries.

## Architecture Notes

Key design decision (pre-resolved): **probe transient-failure rule**.
If a deployment has `swarm: true` but the probe cannot reach the
context (offline host, auth failure), `rundbat probe` reports
`swarm: unknown` and does NOT overwrite a prior `true` with `false`.
Lifecycle commands still attempt `docker stack deploy` and surface
the Docker error verbatim. Documented in
`architecture-update.md`.

Backward compatibility: existing deployments without `swarm` /
`swarm_role` fields continue to work as `docker compose` targets.
The `swarm: bool` flag is additive and opt-in.

## GitHub Issues

(None — this sprint is driven by the
`swarm-support-in-rundbat` TODO.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| T01 | Swarm discovery (`detect_swarm`) | — | A |
| T03 | Generator: swarm plumbing | — | A |
| T02 | Probe records Swarm | T01 | B |
| T04 | Generator: Swarm-native secrets | T03 | B |
| T07 | `rundbat secret create` command | — | B |
| T05 | CLI stack lifecycle | T03 | C |
| T06 | deploy-init Swarm prompt | T02, T05 | C |
| T08 | Skills & agent doc updates | T03, T04, T05, T06, T07 | D |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (A before B, B before C, etc.).

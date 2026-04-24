---
id: "008"
title: "Skills and agent doc updates (docker-swarm-deploy, revise docker-secrets-swarm)"
status: todo
use-cases: []
depends-on: ["003", "004", "005", "006", "007"]
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T08 — Skills and agent doc updates

## Description

Update Claude-facing skill and agent documentation to match the new
Swarm-capable behavior. Every change here is a Markdown content
edit — no code.

### (a) NEW skill — `src/rundbat/content/skills/docker-swarm-deploy.md`

Purpose: teach agents when to prefer Swarm, how rundbat detects /
drives it, and the lifecycle command surface.

Sections:
- When to use Swarm vs plain compose (managed secrets, restart
  policies, rolling updates)
- One-node Swarm as a viable middle ground (`docker swarm init` on
  a single host and stop there)
- How rundbat detects Swarm (`rundbat probe` → `swarm` / `swarm_role`
  fields)
- How rundbat drives the stack lifecycle (`rundbat up/down/restart/
  logs` with `deploy_mode: stack` or the auto-upgrade rule)
- `rundbat secret create` quick-ref
- Troubleshooting quick-ref (`docker service ps`, `docker node ls`,
  manager-quorum issues)

### (b) REVISE — `src/rundbat/content/skills/docker-secrets-swarm.md`

- REMOVE the caveat "rundbat doesn't currently generate Swarm-secret
  stanzas" — it's false now.
- ADD an example of the generated compose output showing
  `secrets: external: true` and the per-service attachment.
- ADD the `rundbat secret create` command and the versioned naming
  scheme (`<app>_<key>_v<YYYYMMDD>`).

### (c) UPDATE — `src/rundbat/content/skills/deploy-init.md`

Add a step describing the Swarm probe during deploy-init and the
opt-in prompt.

### (d) UPDATE — `src/rundbat/content/skills/deploy-setup.md`

Brief addition describing when to choose stack mode. Single
paragraph + a pointer to `docker-swarm-deploy.md`.

### (e) UPDATE — `src/rundbat/content/skills/diagnose.md`

Add Swarm-specific troubleshooting:
- `docker service ps <service>` for task-level failures
- `docker node ls` for cluster membership
- Why a stack may stay in `starting` without manager quorum
- Verify secrets exist: `docker secret ls | grep <app>`

### (f) UPDATE — `src/rundbat/content/agents/deployment-expert.md`

Add one bullet to the agent's capability list noting Swarm support
(probe, generate, lifecycle, secret create) via the
`docker-swarm-deploy` skill.

## Affected Files

- `src/rundbat/content/skills/docker-swarm-deploy.md` (NEW)
- `src/rundbat/content/skills/docker-secrets-swarm.md` (REVISE)
- `src/rundbat/content/skills/deploy-init.md` (UPDATE)
- `src/rundbat/content/skills/deploy-setup.md` (UPDATE)
- `src/rundbat/content/skills/diagnose.md` (UPDATE)
- `src/rundbat/content/agents/deployment-expert.md` (UPDATE)

## Acceptance Criteria

- [ ] `docker-swarm-deploy.md` exists and covers the six sections
      above
- [ ] `docker-secrets-swarm.md` no longer contains the "rundbat
      doesn't currently generate Swarm-secret stanzas" caveat
- [ ] `docker-secrets-swarm.md` shows generated `secrets: external:
      true` example
- [ ] `docker-secrets-swarm.md` documents `rundbat secret create`
- [ ] `deploy-init.md` has a Swarm-probe step
- [ ] `deploy-setup.md` mentions stack mode and points to
      `docker-swarm-deploy.md`
- [ ] `diagnose.md` has the Swarm troubleshooting quick-ref
- [ ] `deployment-expert.md` has a Swarm-capability bullet
- [ ] `rundbat --instructions | grep docker-swarm-deploy` finds the
      new skill (auto-discovered via installer)
- [ ] `uv run pytest` passes (no code changes — just make sure
      nothing broke)
- [ ] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: not required — these are content files.
  If the test suite has an installer/manifest test that enumerates
  skill files, verify it picks up the new file without modification.
- **Manual check**: `uv run rundbat --instructions | grep
  docker-swarm-deploy` (locally, no Docker needed).

## Notes

- Depends on T03–T07 so docs reflect real behavior, not aspirations.
- Bump `pyproject.toml` version.

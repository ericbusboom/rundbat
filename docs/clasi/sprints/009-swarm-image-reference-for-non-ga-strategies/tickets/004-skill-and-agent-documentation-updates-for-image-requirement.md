---
id: '004'
title: Skill and agent documentation updates for image requirement
status: in-progress
use-cases:
- SUC-001
- SUC-002
- SUC-003
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Skill and agent documentation updates for image requirement

## Description

Update three skill files under `src/rundbat/content/skills/` to
reflect the new image requirement introduced in sprint 009:

1. `docker-swarm-deploy.md` — document that any swarm deployment
   must have `image:` set on the deployment, regardless of
   build_strategy. Explain how each strategy satisfies the
   requirement: github-actions uses the registry image; context
   pulls/runs a pre-built image by the declared tag; ssh-transfer
   builds locally and `docker save`/`load`s the declared tag to
   the swarm nodes. Include a short config example.

2. `deploy-init.md` — mention that `deploy-init` prompts for an
   image tag when enabling stack mode with a build-on-host
   strategy, and that the default tag is
   `<app_name>:<deployment_name>`.

3. `diagnose.md` — add a troubleshooting entry for
   `invalid image reference for service app: no image specified`
   pointing at the deployment `image:` field as the remedy.

Bump `pyproject.toml` version.

## Acceptance Criteria

- [ ] `docker-swarm-deploy.md` has an "Image requirement" section
      and a short per-strategy rundown.
- [ ] `deploy-init.md` documents the new image prompt.
- [ ] `diagnose.md` has a "no image specified" troubleshooting
      entry.
- [ ] `uv run pytest` passes.
- [ ] Version bumped in `pyproject.toml`.

## Testing

- **Existing tests to run**: full suite.
- **New tests to write**: none (docs-only).
- **Verification command**: `uv run pytest`

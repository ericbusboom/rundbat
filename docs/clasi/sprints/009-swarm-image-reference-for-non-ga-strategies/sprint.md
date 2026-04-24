---
id: "009"
title: "Swarm image reference for non-GA strategies"
status: planning
branch: sprint/009-swarm-image-reference-for-non-ga-strategies
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 009: Swarm image reference for non-GA strategies

## Goals

Make `rundbat generate` produce a Swarm-deployable compose for every
combination of `build_strategy` and `swarm: true`, or fail loudly at
generate time with a helpful error. Eliminate the silent runtime
`docker stack deploy` failure observed in sprint 008 live verification:

```
invalid image reference for service app: no image specified
```

## Problem

`generate_compose_for_deployment()` in `src/rundbat/generators.py` emits
`image:` only when `build_strategy == "github-actions"`. For
`context` and `ssh-transfer` strategies, the app service has only a
`build:` block, which Swarm ignores. The resulting stack deploy fails
because no image reference exists.

## Solution

Adopt the TODO's recommended **Option A + C**:

1. Treat `image:` as **required** on a deployment when `swarm: true`.
2. Emit **both** `image:` and `build:` from the generator so
   `docker compose build` tags the image correctly and
   `docker stack deploy` has a reference to pull or run.
3. When `swarm: true` and `image:` is missing, fail `rundbat generate`
   loudly with a clear message; do not write a partial compose.
4. In `cmd_deploy_init`, when the user opts into stack mode with a
   build-on-host strategy, prompt for an image tag.
5. Reconcile `ssh-transfer` image tagging (`_get_buildable_images`) so
   the transferred image name matches the compose `image:` field.
6. Update skills (`docker-swarm-deploy.md`, `deploy-init.md`,
   `diagnose.md`) to document the requirement and troubleshooting.

The `build_strategy: github-actions` + swarm path remains unchanged.

## Success Criteria

- `uv run pytest` passes, including a new matrix of
  swarm × (context, ssh-transfer, github-actions) × (image, no image).
- `rundbat generate` with `swarm: true` and no `image:` exits non-zero
  with a helpful error and writes no partial compose file.
- Generated compose for swarm + context or ssh-transfer emits both
  `image:` and `build:`.
- Skills updated; agent docs reflect new requirement.

## Scope

### In Scope

- `src/rundbat/generators.py` — image/build emission and pre-write
  validation for swarm deployments.
- `src/rundbat/cli.py` — `cmd_generate` surfaces validation errors
  cleanly; `cmd_deploy_init` prompts for image tag in stack mode with
  a build-on-host strategy.
- `src/rundbat/deploy.py` — align ssh-transfer image tagging with the
  emitted `image:` field.
- `src/rundbat/content/skills/docker-swarm-deploy.md`,
  `deploy-init.md`, `diagnose.md`.
- `tests/unit/test_generators.py` — matrix tests for image/build
  emission and missing-image error.

### Out of Scope

- Auto-building an image during `rundbat up` in swarm mode.
- Promoting `image` to top-level config (stays per-deployment).

## Test Strategy

- New class `TestGenerateComposeSwarmImage` in test_generators.py
  with the 6-cell matrix of strategy × (image supplied, missing).
- Extend `test_stack_mode_generates_compose` to assert both
  `image:` and (for context strategy) `build:` are present.
- Unit test on `_get_buildable_images` / ssh-transfer tag selection
  after reconciliation (T003).
- Manual scratch-dir smoke test of the error path for T001.

## Architecture Notes

See architecture-update.md. Keyword: treat `image:` as a first-class
deployment field used by both compose and stack modes; `build:` stays
orthogonal — it says how to build locally, not what tag to deploy.

## GitHub Issues

(None.)

## Definition of Ready

- [x] Sprint planning documents complete
- [x] Architecture review passed (inline — see architecture-update.md)
- [x] Stakeholder has approved the sprint plan (pre-approved via TODO)

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| T001 | Generator image/build emission + validation | — | 1 |
| T002 | deploy-init stack-mode image prompt | T001 | 2 |
| T003 | ssh-transfer image tag reconciliation | T001 | 2 |
| T004 | Skill and agent doc updates | T001 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially.

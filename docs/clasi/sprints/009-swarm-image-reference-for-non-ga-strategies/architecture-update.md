---
sprint: "009"
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update — Sprint 009: Swarm image reference for non-GA strategies

## What Changed

- `generate_compose_for_deployment()` now emits `image:` for every
  strategy when a deployment provides one, and emits `build:` for
  any strategy that builds on host (`context`, `ssh-transfer`).
  GitHub-actions path is unchanged.
- New validation rule at generate time: when `swarm: true`, the
  deployment **must** define `image:`. Missing image raises a
  `GenerateError` which `cmd_generate` surfaces as a non-zero exit.
- `cmd_deploy_init` prompts the user for an image tag when opting
  into Swarm (stack mode) with a build-on-host strategy.
- `_get_buildable_images()` (ssh-transfer) now prefers the compose
  `image:` field when present, so the tag that is `docker save`/`load`d
  on the remote matches what the stack references. Falls back to the
  `<project>-<service>` default when no explicit image is declared.
- Skills updated: `docker-swarm-deploy.md` documents the image
  requirement; `deploy-init.md` describes the new prompt;
  `diagnose.md` adds the "no image specified" entry.

## Why

Sprint 008's live verification discovered that stack-mode deploys
with `build_strategy: context` or `ssh-transfer` fail at the remote
with `invalid image reference for service app: no image specified`.
Swarm does not build; it pulls. The generator produced `build:`-only
compose files for those strategies, which Swarm ignores. The fix is
to make `image:` a generator-visible contract for every strategy and
to reject swarm configs that do not provide one.

## Impact on Existing Components

- `generate_compose_for_deployment` gains pre-write validation; in
  swarm mode the function can raise, so `generate_artifacts` must
  surface the error as a `{"error": ...}` result (consistent with
  existing error-return style) and avoid writing any compose file.
- `cmd_generate` already pipes `result["error"]` to `_error()` and
  returns without exit-0; no refactor needed.
- `cmd_deploy_init` is already wired for `deploy_mode`; new prompt is
  additive.
- `_get_buildable_images` contract broadens to return the list of
  image tags to save/load, which for swarm-aware configs is the
  declared `image:` tag rather than the compose-default tag. No
  callers other than ssh-transfer use the function.
- `build_strategy: github-actions` + swarm path is unchanged; tests
  pin that.

## Migration Concerns

- Existing rundbat projects that already have a stack-mode deployment
  with `build_strategy: github-actions` (the working path) are
  unaffected — they already set `image:`.
- Existing projects with `swarm: true` + context/ssh-transfer and no
  `image:` will see `rundbat generate` fail after upgrade. The error
  message tells the user to add `image:` or switch strategies.
  Acceptable because those configs are already broken at runtime.
- No dotconfig or secret schema changes.

---
id: '001'
title: Generator image/build emission and swarm validation
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
todo: swarm-image-reference-for-non-ga-strategies.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generator image/build emission and swarm validation

## Description

Update `generate_compose_for_deployment()` in
`src/rundbat/generators.py` to emit both `image:` and `build:` on the
app service when a deployment declares an `image:` and the strategy
builds on host. Add a validation rule: when `swarm: true`, the
deployment must declare `image:` — if missing, `generate_artifacts()`
returns an error dict and writes no compose file.

Concrete behavior:

- `build_strategy == "github-actions"`: unchanged (image only, no
  build). `image:` may be explicit or default to
  `ghcr.io/owner/<app>:latest`.
- `build_strategy in ("context", "ssh-transfer")` and `image:`
  provided: emit both `image: <image>` and the usual
  `build: {context: .., dockerfile: docker/Dockerfile}`. Use the
  user's declared tag verbatim (no implicit `:latest` appended).
- `build_strategy in ("context", "ssh-transfer")` and no `image:`
  and not swarm: unchanged (build only, no image — compose-mode
  works fine).
- `swarm: true` and no `image:`: generator raises a `GenerateError`
  which `generate_artifacts` catches and returns as
  `{"error": "<message>"}`. `cmd_generate` surfaces via `_error()`
  (non-zero exit). No partial compose file is written for the
  invalid deployment; other valid deployments may still be written.

Error message shape:

```
deployment 'prod' has swarm: true but no 'image:' configured.
Swarm cannot build images. Set deployments.prod.image in rundbat.yaml
(e.g. image: myapp:prod) or switch build_strategy to github-actions.
```

Bump `pyproject.toml` version.

## Acceptance Criteria

- [x] `generate_compose_for_deployment()` emits both `image:` and
      `build:` for swarm + context and swarm + ssh-transfer when
      `image:` is set.
- [x] The github-actions + swarm code path is unchanged (existing
      test `test_stack_mode_generates_compose` still passes).
- [x] A `swarm: true` config with no `image:` causes
      `generate_artifacts()` to return `{"error": "..."}` with a
      helpful message and no compose file written for that
      deployment.
- [x] `cmd_generate` surfaces the error via `_error()` (non-zero
      exit).
- [x] New test class `TestGenerateComposeSwarmImage` covers the
      6-cell matrix: {context, ssh-transfer, github-actions} ×
      {image supplied, image missing}.
- [x] `test_stack_mode_generates_compose` complemented with a test
      that asserts `image:` is present.
- [x] Non-swarm (compose-mode) config with no `image:` still works
      unchanged for context/ssh-transfer (regression).
- [x] `uv run pytest` passes.
- [x] Version bumped in `pyproject.toml`.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_generators.py` and the full suite.
- **New tests to write**:
  - `TestGenerateComposeSwarmImage.test_context_swarm_with_image`
  - `TestGenerateComposeSwarmImage.test_ssh_transfer_swarm_with_image`
  - `TestGenerateComposeSwarmImage.test_github_actions_swarm_with_image`
    (regression)
  - `TestGenerateComposeSwarmImage.test_context_swarm_missing_image_errors`
  - `TestGenerateComposeSwarmImage.test_ssh_transfer_swarm_missing_image_errors`
  - `TestGenerateComposeSwarmImage.test_github_actions_swarm_missing_image_uses_default`
  - `TestGenerateArtifacts.test_stack_mode_emits_image_field`
- **Verification command**: `uv run pytest`

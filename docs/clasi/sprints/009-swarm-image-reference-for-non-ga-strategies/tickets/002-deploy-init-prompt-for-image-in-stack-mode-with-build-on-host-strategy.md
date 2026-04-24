---
id: '002'
title: deploy-init prompt for image in stack mode with build-on-host strategy
status: in-progress
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# deploy-init prompt for image in stack mode with build-on-host strategy

## Description

In `src/rundbat/cli.py::cmd_deploy_init`, after the swarm opt-in
prompt has turned the deployment into stack mode, check whether the
chosen `build_strategy` is `context` or `ssh-transfer` and whether
the deployment entry lacks `image:`. If so, prompt the user for an
image tag with a sensible default `<app_name>:<deployment_name>`
and save it into the deployment entry.

Non-interactive/`--json` path: skip the prompt and auto-fill the
default tag. Keep scripted flows working.

Do not prompt when `build_strategy == "github-actions"` — that path
already has an `image:` defaulted by `init_deployment`.

A small `_prompt_text(prompt, default)` helper near `_prompt_yes_no`
is acceptable; reuse any existing helper if one already exists.

Bump `pyproject.toml` version.

## Acceptance Criteria

- [ ] After swarm opt-in, if strategy is context/ssh-transfer and no
      image is set, `cmd_deploy_init` prompts for an image tag with
      default `<app_name>:<deployment_name>`.
- [ ] The saved `deployments.<name>.image` reflects the user's input
      (or the default if the user pressed enter).
- [ ] When `args.json` is set, the prompt is skipped and the default
      tag is used.
- [ ] When strategy is `github-actions`, no prompt appears.
- [ ] When the user did not opt into stack mode, no prompt appears.
- [ ] New test in `tests/unit/test_cli.py` (or an existing
      deploy-init test file) exercises the JSON path — stack opt-in
      + ssh-transfer strategy → saved config has `image:`.
- [ ] `uv run pytest` passes.
- [ ] Version bumped in `pyproject.toml`.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/` (cli tests
  especially).
- **New tests to write**: JSON-mode path for stack opt-in; confirm
  saved config has `image`.
- **Verification command**: `uv run pytest`

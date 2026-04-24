---
id: '006'
title: deploy-init Swarm prompt (auto-probe, offer swarm opt-in)
status: done
use-cases:
- SUC-002
depends-on:
- '002'
- '005'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T06 — deploy-init Swarm prompt

## Description

In `cmd_deploy_init` (and reflected in the `deploy-init.md` skill
flow), after the remote host and docker_context have been chosen
and the deployment entry is about to be written, auto-probe the
context for Swarm. If Swarm is detected:

1. Show the result: "Swarm detected on <host> (role: manager|worker)."
2. Offer (interactive prompt) to set `swarm: true` + `deploy_mode:
   stack` in the new deployment entry.
3. On accept: write both fields; on decline: proceed with the default
   `compose` mode and omit the swarm fields (user can run
   `rundbat probe` later to record them).

If Swarm is NOT detected, write neither field (compose-mode as
today). If the probe is unreachable, print a warning and proceed
with defaults.

The skill file `deploy-init.md` gains a brief step describing this
prompt.

## Affected Files

- `src/rundbat/cli.py` — `cmd_deploy_init` (add swarm probe +
  prompt)
- `src/rundbat/deploy.py` — `init_deployment` (accept the
  `swarm`/`deploy_mode` params if plumbed through)
- `src/rundbat/content/skills/deploy-init.md` — add Swarm step
- `tests/unit/test_cli.py` — new tests

## Acceptance Criteria

- [x] `cmd_deploy_init` runs `detect_swarm(context)` after selecting
      the Docker context
- [x] When Swarm is detected, user is prompted: "Enable stack mode
      (swarm: true, deploy_mode: stack)? [Y/n]"
- [x] Accept → both fields are written to the new deployment entry
- [x] Decline → neither field is written; compose mode applies
- [x] When Swarm is NOT detected, no prompt appears and no swarm
      fields are written
- [x] Unreachable probe prints a warning and proceeds with defaults
      (no swarm fields written)
- [x] `deploy-init.md` skill documents this step
- [x] Existing deploy-init flows (non-swarm hosts) are unchanged
      (regression)
- [x] `uv run pytest` passes
- [x] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_cli.py`
  and any existing `cmd_deploy_init` tests
- **New tests to write**:
  - `test_deploy_init_swarm_detected_prompts_and_writes_fields_on_accept`
  - `test_deploy_init_swarm_detected_decline_writes_no_swarm_fields`
  - `test_deploy_init_swarm_not_detected_no_prompt`
  - `test_deploy_init_swarm_unreachable_warns_proceeds`
- **Verification command**: `uv run pytest`

## Notes

- Depends on T02 (probe recording behavior) and T05 (stack mode in
  lifecycle) so the user's opt-in actually does something useful.
- Bump `pyproject.toml` version.

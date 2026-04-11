---
id: '005'
title: GitHub Actions workflow split and build triggers
status: todo
use-cases: [SUC-005]
depends-on: ['001', '002']
github-issue: ''
todo: plan-rundbat-build-triggers-github-actions-workflow-for-ghcr-builds.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# GitHub Actions workflow split and build triggers

## Description

Replace the monolithic `generate_github_workflow()` (build + deploy in one job) with two separate workflow generators: `generate_github_build_workflow()` and `generate_github_deploy_workflow()`. The build workflow triggers on push to main and `workflow_dispatch`; the deploy workflow triggers via `workflow_run` (after build) and `workflow_dispatch`.

Add `detect_gh()` to `discovery.py` and `_get_github_repo()` to `deploy.py`. Wire `rundbat build <name>` to call `gh workflow run build.yml` when `build_strategy: github-actions`. Wire `rundbat up <name> --workflow` to call `gh workflow run deploy.yml`.

Depends on Ticket 001 for `generate_artifacts()` which calls these workflow generators, and Ticket 002 for the `build` and `up` subcommands that dispatch to them.

## Acceptance Criteria

- [ ] `generate_github_build_workflow(platform)` in `generators.py` returns a valid YAML string for `build.yml` with `push` to main and `workflow_dispatch` triggers.
- [ ] `generate_github_deploy_workflow(app_name, compose_file, deploy_mode, docker_run_cmd)` in `generators.py` returns a valid YAML string for `deploy.yml` with `workflow_run` and `workflow_dispatch` triggers.
- [ ] `deploy.yml` `if:` condition guards against deploying when build workflow failed.
- [ ] `deploy.yml` SSH step uses compose pull+up when `deploy_mode == "compose"` and docker pull+run when `deploy_mode == "run"`.
- [ ] `generate_artifacts()` (Ticket 001) calls both generators and writes `.github/workflows/build.yml` and `.github/workflows/deploy.yml` when any deployment has `build_strategy: github-actions`.
- [ ] `detect_gh()` in `discovery.py` returns `{installed: bool, authenticated: bool}` by running `gh auth status`.
- [ ] `_get_github_repo()` in `deploy.py` parses `git remote get-url origin` and returns `owner/repo` for both SSH (`git@github.com:owner/repo.git`) and HTTPS (`https://github.com/owner/repo`) formats.
- [ ] `rundbat build <name>` for a github-actions deployment: checks `detect_gh()`, errors if not installed/authenticated, then calls `gh workflow run build.yml --repo <owner/repo> --ref <branch>`.
- [ ] `rundbat up <name> --workflow`: checks `detect_gh()`, calls `gh workflow run deploy.yml --repo <owner/repo>`.
- [ ] `rundbat build <name>` for non-github-actions deployment runs local `docker compose build` (unchanged from Ticket 002).
- [ ] Existing `generate_github_workflow()` is preserved and still works (backward compat).
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Add two new generator functions in `generators.py`. Add `detect_gh()` to `discovery.py` following the same `_run_command()` pattern as `detect_caddy()`. Add `_get_github_repo()` to `deploy.py`. Update `cmd_build` and `cmd_up` in `cli.py` to dispatch to gh CLI when appropriate.

### Files to Modify

**`src/rundbat/generators.py`**
- Add `generate_github_build_workflow(platform)`: returns build.yml YAML string with `workflow_dispatch` trigger, GHCR login, buildx, build-push-action.
- Add `generate_github_deploy_workflow(app_name, compose_file, deploy_mode, docker_run_cmd, platform)`: returns deploy.yml YAML string. SSH step: compose pull+up (compose mode) or docker pull+stop+rm+run (run mode).
- Update `generate_artifacts()`: when any deployment has `build_strategy: github-actions`, call both generators and write to `.github/workflows/`. Create `.github/workflows/` dir if absent. Print reminder about required GitHub secrets.

**`src/rundbat/discovery.py`**
- Add `detect_gh()`: run `_run_command(["gh", "auth", "status"])`. Return `{installed: result["returncode"] != -1, authenticated: result["success"]}`.

**`src/rundbat/deploy.py`**
- Add `_get_github_repo()`: run `git remote get-url origin`, parse to `owner/repo`, return string. Handle both SSH and HTTPS URL formats. Raise `DeployError` if not a GitHub remote.

**`src/rundbat/cli.py`**
- Update `cmd_build(args)`: if `build_strategy == "github-actions"`, call `discovery.detect_gh()`, error if not available, then `subprocess.run(["gh", "workflow", "run", "build.yml", "--repo", repo, "--ref", branch])`. Print watch command hint.
- Update `cmd_up(args)`: if `args.workflow`, call `detect_gh()`, then `gh workflow run deploy.yml`.

### Testing Plan

- `tests/unit/test_generators.py`: add tests for `generate_github_build_workflow()` — verify `workflow_dispatch` trigger present, GHCR login step, platform arg. Add tests for `generate_github_deploy_workflow()` — compose mode vs run mode SSH step, `workflow_run` trigger, if condition.
- `tests/unit/test_discovery.py`: add tests for `detect_gh()` — installed+authenticated, installed+not-authenticated, not installed.
- `tests/unit/test_deploy.py`: add tests for `_get_github_repo()` — SSH URL parse, HTTPS URL parse, non-GitHub remote raises error.
- Run `uv run pytest`.

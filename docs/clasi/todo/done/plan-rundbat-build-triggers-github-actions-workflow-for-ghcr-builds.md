---
status: done
sprint: '007'
tickets:
- 007-005
---

# Plan: `rundbat build` triggers GitHub Actions workflow for GHCR builds

## Context

When a deployment uses `build_strategy: github-actions`, the image is built by GitHub and pushed to GHCR. Currently the generated workflow only triggers on push to `main`. The user wants `rundbat build <deployment>` to trigger that build on demand — so you can sit at your terminal, run `rundbat build prod`, and GitHub builds and pushes the image to GHCR.

## Design

### Split the workflow into build-only and deploy

The current workflow bundles build + deploy in one job. Split into two workflows:

**`build.yml`** — Build image, push to GHCR. Triggered by:
- `push` to `main` (automatic)
- `workflow_dispatch` (manual — this is what `rundbat build` calls)

**`deploy.yml`** — SSH to remote, pull image, restart. Triggered by:
- `workflow_run` (after `build.yml` completes successfully)
- `workflow_dispatch` (manual — for `rundbat up` to call)

This separation means `rundbat build prod` triggers a build without auto-deploying, and `rundbat up prod` can either trigger a full build+deploy or just deploy a previously-built image.

### `rundbat build <deployment>` for github-actions strategy

When `build_strategy: github-actions`:

```python
def cmd_build(args):
    deployment = args.deployment
    cfg = load_deploy_config(deployment)
    
    if cfg.get("build_strategy") == "github-actions":
        # Trigger the GitHub Actions build workflow via gh CLI
        repo = _get_github_repo()  # from git remote
        subprocess.run([
            "gh", "workflow", "run", "build.yml",
            "--repo", repo,
            "--ref", _get_current_branch(),
        ])
        print(f"Build triggered on GitHub Actions for {deployment}")
        print(f"Watch: gh run watch --repo {repo}")
    else:
        # Local build (existing behavior)
        docker compose -f docker/docker-compose.<deployment>.yml build
```

Uses `gh workflow run` — the GitHub CLI, which handles auth via existing `gh auth` session. No API tokens to configure.

### Updated workflow templates in generators.py

**`generate_github_build_workflow()`** — new function:

```yaml
name: Build

on:
  push:
    branches: [main]
  workflow_dispatch:          # ← enables rundbat build to trigger it

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          push: true
          platforms: <platform>
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

**`generate_github_deploy_workflow()`** — new function:

```yaml
name: Deploy

on:
  workflow_run:
    workflows: [Build]
    types: [completed]
    branches: [main]
  workflow_dispatch:          # ← enables rundbat up to trigger it

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/<app_name>
            docker compose -f <compose_file> pull
            docker compose -f <compose_file> up -d
```

### `rundbat generate` creates both workflows

When any deployment has `build_strategy: github-actions`:
1. Generate `.github/workflows/build.yml`
2. Generate `.github/workflows/deploy.yml`
3. Print reminder about GitHub secrets

### `rundbat up <deployment>` for github-actions

Two options depending on what the user wants:
- **Default**: `docker compose pull && up -d` via the Docker context (existing behavior — fast, no GitHub round-trip)
- **With `--workflow` flag**: trigger the deploy workflow via `gh workflow run deploy.yml`

The default is the fast path (just pull the already-built image). The `--workflow` flag is for when you want the full GitHub-managed deploy.

### Prerequisite: `gh` CLI

`rundbat build` with github-actions strategy requires `gh` to be installed and authenticated. Add `gh` detection to `discovery.py`:

```python
def detect_gh() -> dict:
    """Detect GitHub CLI installation and auth status."""
    result = _run_command(["gh", "auth", "status"])
    return {
        "installed": result["returncode"] != -1,
        "authenticated": result["success"],
    }
```

`rundbat build` checks this before attempting workflow dispatch and gives a clear error if `gh` isn't available.

### Helper: `_get_github_repo()`

Extract repo from git remote:
```python
def _get_github_repo() -> str:
    """Get owner/repo from git remote origin."""
    result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    url = result.stdout.strip()
    # Parse: git@github.com:owner/repo.git or https://github.com/owner/repo.git
    # Return: owner/repo
```

## Files to modify

| File | Action |
|------|--------|
| `src/rundbat/generators.py` | Replace `generate_github_workflow()` with `generate_github_build_workflow()` + `generate_github_deploy_workflow()` |
| `src/rundbat/cli.py` | Update `cmd_build` to handle github-actions via `gh workflow run` |
| `src/rundbat/discovery.py` | Add `detect_gh()` |
| `src/rundbat/deploy.py` | Add `_get_github_repo()` helper |
| `tests/unit/test_generators.py` | Update workflow generation tests |
| `tests/unit/test_discovery.py` | Test gh detection |

## Verification

1. `rundbat generate` with a github-actions deployment → creates `.github/workflows/build.yml` and `deploy.yml` with `workflow_dispatch` triggers
2. `rundbat build prod` → runs `gh workflow run build.yml`, prints watch command
3. `rundbat up prod` → does `docker compose pull && up -d` via context (fast path)
4. `rundbat up prod --workflow` → triggers deploy workflow via `gh workflow run`
5. `uv run pytest` passes

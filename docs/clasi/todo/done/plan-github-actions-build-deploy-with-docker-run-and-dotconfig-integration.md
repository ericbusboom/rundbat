---
status: done
sprint: '007'
tickets:
- 007-003
- 007-004
---

# Plan: GitHub Actions Build + Deploy with docker-run and dotconfig Integration

## Context

rundbat already has a `github-actions` build strategy and a `generate_github_workflow()` function, but:
1. The workflow isn't generated automatically during `deploy-init`
2. Deployment only works via `docker compose` — no `docker run` option
3. No integration with dotconfig for injecting env files at deploy time
4. Caddy labels aren't included when using `docker run`

The user wants a complete GitHub-based CI/CD flow: GitHub builds the image → pushes to GHCR → deploys to a remote Docker host via either `docker compose` or `docker run`, with environment from dotconfig and Caddy labels when applicable.

## Changes

### 1. Add `deploy_mode` to rundbat.yaml deployment schema

New field `deploy_mode` (default: `compose`) alongside existing `build_strategy`:

```yaml
deployments:
  prod:
    docker_context: docker1.example.com
    build_strategy: github-actions
    deploy_mode: compose          # or "run"
    compose_file: docker/docker-compose.prod.yml
    # --- docker-run specific fields ---
    docker_run_cmd: >-
      docker run -d --name myapp
      --env-file .env
      -p 8080:8080
      --restart unless-stopped
      -l caddy=myapp.example.com
      -l "caddy.reverse_proxy={{upstreams 8080}}"
      ghcr.io/owner/repo:latest
    image: ghcr.io/owner/repo     # GHCR image ref (tag appended at deploy)
```

`build_strategy` controls how the image is built (context, ssh-transfer, github-actions).
`deploy_mode` controls how the image is run on the remote (compose or run).

When `deploy_mode: run`, the full `docker_run_cmd` is stored in config — visible, editable, validatable.

### 2. Generate `docker_run_cmd` during deploy-init

In `deploy.py:init_deployment()`, when `deploy_mode: run` is specified:
- Build the `docker run` command from known config: image name, port, hostname (Caddy labels), restart policy
- Include `--env-file .env` for dotconfig-loaded environment
- Save the complete command to `rundbat.yaml`

New helper: `_build_docker_run_cmd(app_name, image, port, hostname, env_file)` in `deploy.py`.

### 3. Add `_deploy_run()` strategy handler in deploy.py

New function alongside `_deploy_context`, `_deploy_ssh_transfer`, `_deploy_github_actions`:

```python
def _deploy_run(ctx, deploy_cfg, dry_run):
    """Deploy using docker run (single container, no compose)."""
    # 1. Load env from dotconfig: dotconfig load -d <env> --stdout > .env
    # 2. Transfer .env to remote (scp or ssh cat)
    # 3. Pull latest image on remote
    # 4. Stop + remove existing container
    # 5. Run the docker_run_cmd from config
```

### 4. Update `deploy()` dispatch to handle deploy_mode

Currently `deploy()` dispatches on `build_strategy`. Update to check `deploy_mode` as well:
- If `deploy_mode == "run"`: call `_deploy_run()` regardless of build_strategy
- If `deploy_mode == "compose"` (default): use existing strategy dispatch

### 5. dotconfig env injection in deploy flow

For both compose and run modes, add an env-preparation step:
1. `dotconfig load -d <deployment_name> --stdout` → produces assembled `.env` content
2. For compose: write to `.env` in project root (compose reads it via `env_file`)
3. For run: transfer to remote, referenced by `--env-file` in the run command

New function in `deploy.py`: `_prepare_env(deployment_name, ctx, host, ssh_key)` that:
- Calls `config.load_env(deployment_name)` to get the env content
- Writes it to a temp file
- SCPs it to the remote host at a known path (e.g., `/opt/{app_name}/.env`)

### 6. Generate GitHub Actions workflow during deploy-init

When `build_strategy: github-actions`:
- Call `generate_github_workflow()` (already exists)
- Write to `.github/workflows/deploy.yml`
- Print instructions about required GitHub secrets

### 7. Update `generate_github_workflow()` in generators.py

Extend to support `deploy_mode: run`:
- Current: SSH deploy step runs `docker compose pull && up -d`
- New: if `deploy_mode == "run"`, the SSH deploy step runs:
  ```bash
  docker pull ghcr.io/owner/repo:latest
  docker stop myapp || true
  docker rm myapp || true
  <docker_run_cmd from config>
  ```

Also add a dotconfig step: before running the container, load env:
```bash
dotconfig load -d prod --stdout > /opt/myapp/.env
```

### 8. CLI changes in cli.py

Add to `deploy-init` subparser:
- `--deploy-mode` with choices `compose`, `run` (default: `compose`)
- `--image` for specifying the GHCR image reference (used with `deploy_mode: run`)

### 9. New skill: `github-deploy.md`

Create `src/rundbat/content/skills/github-deploy.md` covering:
- When to use: "Deploy via GitHub Actions", "Set up CI/CD"
- Steps: deploy-init with `--strategy github-actions`, choose deploy mode, configure secrets, verify workflow

### 10. Update deploy-setup.md skill

Add guidance for the `github-actions` strategy that's more specific about workflow generation and deploy modes.

## Files to modify

| File | Action |
|------|--------|
| `src/rundbat/deploy.py` | Add `_deploy_run()`, `_prepare_env()`, `_build_docker_run_cmd()`, update dispatch |
| `src/rundbat/generators.py` | Extend `generate_github_workflow()` for run mode + dotconfig |
| `src/rundbat/cli.py` | Add `--deploy-mode`, `--image` to deploy-init; wire workflow generation |
| `src/rundbat/content/skills/github-deploy.md` | New skill file |
| `src/rundbat/content/skills/deploy-setup.md` | Update github-actions section |
| `tests/unit/test_deploy.py` | Tests for _deploy_run, _prepare_env, _build_docker_run_cmd |
| `tests/unit/test_generators.py` | Tests for updated workflow generation |

## Key design decisions

1. **docker_run_cmd in config**: The full command is stored in YAML so users can inspect and edit it. rundbat generates it from known params, but the user owns the final version.
2. **deploy_mode vs build_strategy**: Kept separate because you could use `build_strategy: context` with `deploy_mode: run`, or `build_strategy: github-actions` with `deploy_mode: compose`. They're orthogonal.
3. **Caddy labels in docker run**: When hostname is set and reverse_proxy is caddy, the generated `docker_run_cmd` includes `-l caddy=<hostname> -l "caddy.reverse_proxy={{upstreams <port>}}"`.
4. **dotconfig integration**: Env is loaded via `dotconfig load -d <name> --stdout` and written to a file that Docker reads. This works for both compose (`env_file` in yaml) and run (`--env-file` flag).

## Verification

1. `rundbat deploy-init prod --host ssh://... --strategy github-actions --deploy-mode run --image ghcr.io/owner/repo` → saves config with `docker_run_cmd`, generates workflow
2. `rundbat deploy prod --dry-run` → prints the docker run command from config
3. `rundbat deploy prod` → pulls image, loads env from dotconfig, runs container
4. `uv run pytest` passes


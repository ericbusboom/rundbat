---
status: done
sprint: '007'
tickets:
- 007-006
---

# Plan: Deployment Initialization — Guided Setup and Configuration Model

## Context

rundbat needs a comprehensive, user-friendly deployment initialization system. Today, `deploy-init` requires the user to already know their host, strategy, and compose file. The user wants a guided experience: say "I want to deploy" and rundbat walks them through everything — target environment, services, build strategy, deploy mode, domain names — and records the full configuration in `rundbat.yaml`.

The skill file must include explicit `AskUserQuestion` specs so the Claude agent presents a clean, consistent UI at each decision point.

## Deployment Model

### Deployment Targets

Four default targets with presumed behavior. Users can add custom-named targets.

| Target | Context | Presumption |
|--------|---------|-------------|
| `dev` | `default` | Local dev server with hot reload. If services are needed (e.g., database), they run in Docker on the local context. The app itself runs outside Docker via the framework's dev server. |
| `local` | `default` | Production image running locally in Docker. Same image you'd ship, but on your local Docker instance. May include database and other services. |
| `test` | remote | Remote Docker host for integration/QA testing. Pre-production. |
| `prod` | remote | Production. Real traffic, real domain. |

Both `dev` and `local` default to the `default` Docker context. Remote targets require SSH. Custom targets (e.g., `staging`, `demo`) are configured explicitly.

### Services per deployment

Different targets can use different services. `dev` might use SQLite while `local` uses PostgreSQL.

### Deploy Mode: compose vs run

**Default is compose** — even for single-service deployments. Compose files document the full config (ports, labels, env_file, restart policy) in one readable place. `docker run` is opt-in.

### Build Strategy

| Strategy | How | When |
|----------|-----|------|
| `context` | Build on Docker context | Default for dev/local. Also for same-arch remotes. |
| `ssh-transfer` | Build locally, pipe via SSH | Cross-architecture or constrained remote |
| `github-actions` | GitHub → GHCR → remote pulls | CI/CD pipeline |

### Entry Points

Every app service gets an entrypoint script that handles encrypted config unpacking before starting the server.

## rundbat.yaml Schema (expanded)

```yaml
app_name: myapp
app_name_source: pyproject.toml

services:
  - type: postgres
    version: "16"
  - type: redis
    version: "7"

deployments:
  dev:
    docker_context: default
    build_strategy: context
    deploy_mode: compose
    compose_file: docker/docker-compose.yml
    services: [app]
    hostname: null

  local:
    docker_context: default
    build_strategy: context
    deploy_mode: compose
    compose_file: docker/docker-compose.yml
    services: [app, postgres, redis]
    hostname: null

  test:
    docker_context: docker1.example.com
    host: ssh://root@docker1.example.com
    platform: linux/amd64
    build_strategy: ssh-transfer
    deploy_mode: compose
    compose_file: docker/docker-compose.yml
    services: [app, postgres, redis]
    hostname: test.example.com
    reverse_proxy: caddy
    env_source: dotconfig

  prod:
    docker_context: docker1.example.com
    host: ssh://root@docker1.example.com
    platform: linux/amd64
    build_strategy: github-actions
    deploy_mode: compose
    compose_file: docker/docker-compose.prod.yml
    services: [app]
    image: ghcr.io/owner/repo
    hostname: myapp.example.com
    reverse_proxy: caddy
    env_source: dotconfig

  # docker-run mode (user explicitly chose this)
  prod-simple:
    deploy_mode: run
    docker_run_cmd: >-
      docker run -d --name myapp
      --env-file /opt/myapp/.env
      -p 8080:8080
      --restart unless-stopped
      -l caddy=myapp.example.com
      -l "caddy.reverse_proxy={{upstreams 8080}}"
      ghcr.io/owner/repo:latest
    # ... other fields same as prod
```

### New fields

| Field | Purpose |
|-------|---------|
| `deploy_mode` | `compose` (default) or `run` |
| `services` | Service names this deployment includes |
| `image` | Registry image ref (github-actions / run mode) |
| `docker_run_cmd` | Full docker run command, visible in config (run mode only) |
| `env_source` | `dotconfig`, `file`, or `none` |

---

## Guided Initialization Skill: `deploy-init.md`

This is the heart of the plan. The skill tells Claude exactly what to ask, in what order, with what options. Each step uses `AskUserQuestion` for a clean UI.

### Trigger phrases

- "I want to deploy"
- "Set up deployment"
- "Configure a deployment"
- "Deploy my application"

### Prerequisites

- `rundbat.yaml` exists (`rundbat init` first)
- `docker/` exists (`rundbat init-docker` first) — or the skill offers to run it

---

### Step 1: Deployment Target

```
AskUserQuestion:
  question: "What deployment target are you setting up?"
  header: "Target"
  options:
    - label: "dev"
      description: "Local dev server. Your app runs outside Docker (hot reload). Database and other services run in local Docker if needed."
    - label: "local"
      description: "Production image on local Docker. Same container you'd ship, running on your machine. Good for testing the built image."
    - label: "test"
      description: "Remote server for QA/integration testing. Pre-production environment."
    - label: "prod"
      description: "Production. Remote server with real traffic and a real domain name."
  # User can also type a custom name via "Other"
```

**After answer:**
- If `dev` or `local`: set `docker_context: default`, `build_strategy: context`. Skip SSH steps.
- If `test` or `prod`: will need SSH details.
- If custom name: ask whether it's local or remote.

---

### Step 2: Services

```
AskUserQuestion:
  question: "What services does this deployment need?"
  header: "Services"
  multiSelect: true
  options:
    - label: "PostgreSQL"
      description: "PostgreSQL database running in Docker alongside your app."
    - label: "MariaDB"
      description: "MariaDB database running in Docker alongside your app."
    - label: "Redis"
      description: "Redis cache/queue running in Docker alongside your app."
    - label: "App only"
      description: "No additional services. Using SQLite, a managed database, or no database at all."
  # "Other" lets user type custom services (e.g., "cron", "worker")
```

**After answer:**
- Build the `services` list for this deployment.
- If only "App only" selected: services = `[app]`
- Otherwise: services = `[app, postgres, redis, ...]` based on selections

---

### Step 3: Deploy Mode

Only ask this if services = `[app]` (single container). Otherwise, compose is required.

```
AskUserQuestion:
  question: "How should the container be run on the target?"
  header: "Deploy mode"
  options:
    - label: "docker compose (Recommended)"
      description: "Compose file documents all config — ports, labels, env, restart policy — in one readable file. Easier to maintain."
    - label: "docker run"
      description: "Single docker run command stored in rundbat.yaml. Simpler but less self-documenting."
```

**If multi-service:** Skip this question, set `deploy_mode: compose`, tell the user:
> "Multiple services selected — using docker compose (required for multi-container deployments)."

---

### Step 4: Remote Access (remote targets only)

Skip for `dev` and `local`.

```
AskUserQuestion:
  question: "What's the SSH URL for the remote Docker host?"
  header: "SSH host"
  options:
    - label: "I have the URL"
      description: "e.g., ssh://root@docker1.example.com — I'll enter it next."
    - label: "I need to set up SSH first"
      description: "Guide me through generating a deploy key and configuring access."
```

**If "I have the URL":** Ask for the URL via a follow-up text prompt. Then:
1. `rundbat deploy-init <name> --host <url>` — creates context, verifies access
2. Auto-detects remote platform
3. Probes for Caddy (`rundbat probe <name>`)
4. Reports findings:
   > "Connected to docker1.example.com (linux/amd64). Caddy reverse proxy detected."

**If "I need to set up SSH":** Walk through key generation, copy, and verification (content from current deploy-setup.md step 2).

---

### Step 5: Domain Name (remote targets, or if Caddy detected)

```
AskUserQuestion:
  question: "What hostname will this deployment use? (e.g., myapp.example.com)"
  header: "Hostname"
  options:
    - label: "I have a domain"
      description: "I'll enter the hostname — Caddy labels will be added to the compose/run config."
    - label: "No domain yet"
      description: "Skip for now. You can add a hostname later in rundbat.yaml."
```

**If domain provided:** Save as `hostname`, add Caddy labels if `reverse_proxy: caddy`.

---

### Step 6: Build Strategy (remote targets only)

Skip for `dev` and `local` (always `context`).

Auto-detect recommendation based on platform match.

```
AskUserQuestion:
  question: "How should the Docker image be built?"
  header: "Build"
  options:
    - label: "Build on remote (Recommended)"
      description: "Docker builds directly on the remote server via SSH context. Fast when architectures match."
      # or ssh-transfer if cross-platform:
    - label: "Build locally, transfer"
      description: "Build on your machine for the remote's architecture, then send via SSH. Use when the remote is small or a different CPU architecture."
    - label: "GitHub Actions → GHCR"
      description: "GitHub builds the image and pushes to GitHub Container Registry. The remote pulls it. Best for team CI/CD workflows."
```

The first option's label and recommendation changes based on platform detection:
- Same arch → "Build on remote (Recommended)"
- Different arch → first option becomes "Build locally, transfer (Recommended)"

**If GitHub Actions:**
1. Check `git remote get-url origin` — is it a GitHub repo?
2. Derive image: `ghcr.io/{owner}/{repo}`
3. Save `image` field
4. Generate `.github/workflows/deploy.yml`
5. Print:
   > "Workflow generated at `.github/workflows/deploy.yml`. Add these secrets in GitHub → Settings → Secrets:"
   > - `DEPLOY_HOST` — the remote hostname
   > - `DEPLOY_USER` — SSH user
   > - `DEPLOY_SSH_KEY` — paste contents of deploy private key

---

### Step 7: Environment Configuration

```
AskUserQuestion:
  question: "How should environment variables and secrets be managed?"
  header: "Env config"
  options:
    - label: "dotconfig (Recommended)"
      description: "Encrypted secrets via SOPS/age, managed by dotconfig. Secrets are decrypted at deploy time and injected as an env file."
    - label: "Manual .env file"
      description: "You manage .env files yourself. Copy .env.example and fill in values."
    - label: "None"
      description: "No environment configuration needed."
```

**If dotconfig:** Verify `dotconfig config` works. Save `env_source: dotconfig`.

---

### Step 8: Summary and Generate

After all questions, present the full configuration as a preview:

> **Deployment: prod**
> | Setting | Value |
> |---------|-------|
> | Context | docker1.example.com |
> | Build strategy | github-actions |
> | Deploy mode | compose |
> | Services | app |
> | Hostname | myapp.example.com |
> | Reverse proxy | caddy |
> | Image | ghcr.io/owner/repo |
> | Env source | dotconfig |
>
> This will be saved to `rundbat.yaml`.

Then:
1. Write deployment entry to `rundbat.yaml` via `config.save_config()`
2. If compose: generate/update compose file with the right services and labels
3. If run: generate `docker_run_cmd` and store in config
4. If github-actions: generate workflow file
5. Generate entrypoint script if not present
6. Run `rundbat deploy <name> --dry-run` and show output

---

## Implementation — Files to Create/Modify

| File | Action |
|------|--------|
| `src/rundbat/deploy.py` | Add `_deploy_run()`, `build_docker_run_cmd()`, `_prepare_env()`, update `deploy()` dispatch for deploy_mode |
| `src/rundbat/generators.py` | Extend `generate_github_workflow()` for run mode; add `generate_entrypoint()`; extend `generate_compose()` for per-deployment service lists |
| `src/rundbat/cli.py` | Add `--deploy-mode`, `--image`, `--services` to deploy-init; wire workflow generation |
| `src/rundbat/content/skills/deploy-init.md` | **New** — the guided interview skill with full AskUserQuestion specs |
| `src/rundbat/content/skills/deploy-setup.md` | Simplify — reference deploy-init, keep troubleshooting table |
| `src/rundbat/content/skills/github-deploy.md` | **New** — GitHub Actions specific guidance |
| `tests/unit/test_deploy.py` | Tests for _deploy_run, build_docker_run_cmd, _prepare_env |
| `tests/unit/test_generators.py` | Tests for entrypoint, workflow with run mode |

## Not included (future work)

- Per-deployment compose file generation (separate compose per target with different service sets)
- Cron container sidecar design
- Registries beyond GHCR (Docker Hub, ECR)
- Blue-green / rolling deployment
- Dev server integration (framework-specific hot reload)

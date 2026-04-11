---
status: draft
---

# Sprint 007 Use Cases

## SUC-001: Generate per-deployment Docker artifacts

- **Actor**: Developer
- **Preconditions**: `rundbat.yaml` exists with one or more deployment entries. Framework is detectable from project files.
- **Main Flow**:
  1. Developer runs `rundbat generate`.
  2. rundbat reads all deployments from `rundbat.yaml`.
  3. For each deployment, a `docker-compose.<name>.yml` is written to `docker/` with that deployment's services, build/image config, env_file reference, port mapping, and Caddy labels.
  4. For each deployment with `env_source: dotconfig`, rundbat fetches the env via dotconfig and writes `docker/.<name>.env`.
  5. One `docker/Dockerfile` is generated (framework-aware).
  6. One `docker/entrypoint.sh` is generated (framework-aware).
  7. `docker/Justfile` is generated with per-deployment `<name>_build`, `<name>_up`, `<name>_down`, `<name>_logs` recipes.
  8. `docker/.*.env` is added to `.gitignore` if not already present.
  9. rundbat prints a summary of generated files.
- **Postconditions**: `docker/` contains one compose file per deployment. The project can be started for any deployment with `just <name>_up`.
- **Acceptance Criteria**:
  - [ ] `docker-compose.<name>.yml` exists for every deployment in `rundbat.yaml`.
  - [ ] Compose files for `build_strategy: context` use `build:` stanza; github-actions deployments use `image:`.
  - [ ] Caddy labels are included when `hostname` and `reverse_proxy: caddy` are set.
  - [ ] `docker/.<name>.env` is written for dotconfig deployments.
  - [ ] `.gitignore` includes `docker/.*.env`.
  - [ ] Justfile contains recipes for every deployment.
  - [ ] `rundbat generate --deployment prod` regenerates only the prod artifacts.

## SUC-002: Run lifecycle commands for a deployment

- **Actor**: Developer
- **Preconditions**: `rundbat generate` has been run. Docker is available. For remote deployments, Docker context is configured.
- **Main Flow**:
  1. Developer runs `rundbat build local` to build the app image.
  2. Developer runs `rundbat up local` to start all services for the local deployment.
  3. Developer runs `rundbat logs local` to tail container logs.
  4. Developer runs `rundbat down local` to stop and remove containers.
- **Postconditions**: Containers match the requested lifecycle state for the deployment.
- **Acceptance Criteria**:
  - [ ] `rundbat build <name>` runs `docker compose -f docker/docker-compose.<name>.yml build` with the correct Docker context.
  - [ ] `rundbat up <name>` starts containers for compose deployments.
  - [ ] `rundbat down <name>` stops and removes containers.
  - [ ] `rundbat logs <name>` tails logs from the deployment's containers.
  - [ ] Remote deployments automatically set `DOCKER_CONTEXT` from config.
  - [ ] `init-docker` continues to function as a deprecated alias for `generate`.

## SUC-003: Deploy using docker run mode

- **Actor**: Developer
- **Preconditions**: Deployment configured with `deploy_mode: run` and `docker_run_cmd` in `rundbat.yaml`.
- **Main Flow**:
  1. Developer has a single-container deployment and prefers `docker run` over compose.
  2. During `deploy-init`, developer selects `deploy_mode: run`.
  3. rundbat generates `docker_run_cmd` from config (image, port, hostname/labels, env-file).
  4. Developer runs `rundbat up prod` — rundbat pulls the image, stops/removes any existing container, then executes the `docker_run_cmd`.
  5. Developer runs `rundbat down prod` — rundbat stops and removes the named container.
  6. Developer runs `rundbat logs prod` — rundbat calls `docker logs -f <app_name>`.
- **Postconditions**: Container is running via `docker run`. The full command is visible and editable in `rundbat.yaml`.
- **Acceptance Criteria**:
  - [ ] `deploy_mode: run` is a valid field in rundbat.yaml deployment entries.
  - [ ] `_build_docker_run_cmd()` generates a correct docker run command including Caddy labels when applicable.
  - [ ] `rundbat up <name>` for run-mode deployments executes pull + stop/rm + docker_run_cmd.
  - [ ] `rundbat down <name>` for run-mode stops and removes the container by app name.
  - [ ] `rundbat logs <name>` for run-mode calls `docker logs -f`.

## SUC-004: Inject dotconfig environment at deploy time

- **Actor**: Developer / CI pipeline
- **Preconditions**: Deployment has `env_source: dotconfig`. dotconfig is installed and configured with secrets for the target environment.
- **Main Flow**:
  1. Developer runs `rundbat up prod` (or `rundbat deploy prod`).
  2. rundbat calls `_prepare_env(deployment_name)`.
  3. `_prepare_env` calls `config.load_env(name)` to fetch assembled env from dotconfig.
  4. Env content is written to a temp file and SCPd to the remote host at `/opt/<app_name>/.env`.
  5. Container is started with `--env-file /opt/<app_name>/.env`.
- **Postconditions**: Container has access to decrypted secrets without secrets existing in the image or compose files.
- **Acceptance Criteria**:
  - [ ] `_prepare_env()` calls `load_env()` and transfers the result to the remote.
  - [ ] Compose deployments write env to the expected path before `docker compose up`.
  - [ ] Run-mode deployments transfer env before executing `docker_run_cmd`.
  - [ ] No secrets are written to committed files.

## SUC-005: Trigger GitHub Actions build and deploy on demand

- **Actor**: Developer
- **Preconditions**: Deployment uses `build_strategy: github-actions`. `gh` CLI is installed and authenticated. `.github/workflows/build.yml` and `.github/workflows/deploy.yml` have been generated and committed.
- **Main Flow**:
  1. Developer runs `rundbat build prod` for a github-actions deployment.
  2. rundbat checks `detect_gh()` — gh is installed and authenticated.
  3. rundbat calls `gh workflow run build.yml --repo owner/repo --ref main`.
  4. Build workflow runs on GitHub, builds the image, pushes to GHCR.
  5. Developer runs `rundbat up prod --workflow` to trigger the deploy workflow.
  6. Deploy workflow SSHes to remote, pulls image, restarts container.
- **Postconditions**: Image is built on GitHub and deployed to the remote host via GitHub Actions.
- **Acceptance Criteria**:
  - [ ] `rundbat generate` with a github-actions deployment writes both `build.yml` and `deploy.yml` with `workflow_dispatch` triggers.
  - [ ] `build.yml` triggers on push to main and `workflow_dispatch`.
  - [ ] `deploy.yml` triggers via `workflow_run` after build and via `workflow_dispatch`.
  - [ ] `rundbat build prod` calls `gh workflow run build.yml` when strategy is github-actions.
  - [ ] `rundbat up prod --workflow` calls `gh workflow run deploy.yml`.
  - [ ] `detect_gh()` returns installed and authenticated status.
  - [ ] Clear error is shown if gh is not installed or not authenticated.

## SUC-006: Guided deployment initialization

- **Actor**: Developer (via Claude Code)
- **Preconditions**: `rundbat.yaml` exists. Developer wants to configure a new deployment target.
- **Main Flow**:
  1. Developer says "I want to deploy" or "set up deployment" to Claude Code.
  2. Claude Code loads the `deploy-init.md` skill.
  3. Skill presents Step 1: deployment target selection (dev, local, test, prod, custom).
  4. Skill presents Step 2: services selection (PostgreSQL, MariaDB, Redis, app only).
  5. For single-service deployments, skill presents Step 3: deploy mode (compose or run).
  6. For remote targets, skill presents Step 4: SSH host setup.
  7. Skill presents Step 5: domain name (for remote or Caddy targets).
  8. For remote targets, skill presents Step 6: build strategy (context, ssh-transfer, github-actions).
  9. Skill presents Step 7: env configuration (dotconfig, manual, none).
  10. Skill shows Step 8: configuration summary and writes to `rundbat.yaml`.
  11. Appropriate artifacts are generated (compose file, workflow, entrypoint).
- **Postconditions**: `rundbat.yaml` contains a complete deployment entry. Artifacts are generated. Developer can immediately run `rundbat up <name>`.
- **Acceptance Criteria**:
  - [ ] `deploy-init.md` skill file exists in `src/rundbat/content/skills/`.
  - [ ] Skill includes AskUserQuestion specs for all 8 steps.
  - [ ] Multi-service deployments automatically use compose (deploy mode question skipped).
  - [ ] Local targets skip SSH and build strategy steps.
  - [ ] GitHub Actions path generates workflow files and prints secret setup instructions.
  - [ ] Summary table is shown before writing config.
  - [ ] `github-deploy.md` skill file exists covering GitHub Actions CI/CD workflow.

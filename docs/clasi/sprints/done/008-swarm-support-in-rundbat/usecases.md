---
status: ready
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 008 Use Cases

## SUC-001: Probe a Swarm-enabled deployment target

- **Actor**: Developer operating a rundbat-managed project
- **Preconditions**:
  - Project has at least one deployment entry in `rundbat.yaml` with a
    `docker_context` pointing to a reachable host.
  - The remote Docker daemon has `docker swarm init` run (manager) or
    has joined a swarm (worker).
- **Main Flow**:
  1. Developer runs `rundbat probe <env>`.
  2. rundbat calls `detect_swarm(<context>)` against the deployment's
     Docker context.
  3. `detect_swarm` runs `docker info --format '{{json .Swarm}}'` and
     parses the result.
  4. rundbat writes `swarm: true` and `swarm_role: manager` (or
     `worker`) into the deployment entry in `rundbat.yaml`.
  5. rundbat also records `reverse_proxy: caddy` if Caddy was
     detected (existing behavior preserved).
- **Postconditions**:
  - `rundbat.yaml` deployment entry has `swarm` / `swarm_role` fields.
  - On unreachable context: `swarm` is set to `unknown` if previously
    absent; prior `true` is NOT overwritten with `false`.
- **Acceptance Criteria**:
  - [ ] `detect_swarm` returns `{swarm: bool, swarm_role: str,
    reachable: bool}` for active, inactive, and unreachable states.
  - [ ] `cmd_probe` writes both `swarm` and `swarm_role` to the
    deployment entry.
  - [ ] Transient-failure rule: unreachable probe does not overwrite
    prior `swarm: true` with `false`.

## SUC-002: Opt a deployment into Swarm mode

- **Actor**: Developer
- **Preconditions**:
  - `rundbat probe <env>` has recorded `swarm: true` for the
    deployment OR the developer explicitly sets `swarm: true` in
    `rundbat.yaml`.
- **Main Flow**:
  1. Developer runs `rundbat deploy-init <env>` (or edits
     `rundbat.yaml` directly) to set `swarm: true` and
     `deploy_mode: stack`.
  2. Developer runs `rundbat generate`.
  3. rundbat emits `docker/docker-compose.<env>.yml` with:
     - Header comment `# Deploy with: docker stack deploy -c
       docker-compose.<env>.yml <stack>`
     - Caddy labels under `services.<app>.deploy.labels` (not
       `services.<app>.labels`)
     - A minimal `deploy:` block per service (restart_policy,
       update_config, replicas: 1)
     - Top-level `secrets:` stanza with `external: true` entries for
       each declared secret (when secrets are configured)
     - Per-service `secrets:` attachments with stable `target:` names
       matching the `_FILE` env-var convention
- **Postconditions**:
  - Generated compose file is stack-ready.
- **Acceptance Criteria**:
  - [ ] `generate_compose_for_deployment(..., swarm=True)` produces
    all four above artifacts.
  - [ ] When the deployment has no declared secrets, no `secrets:`
    stanza is emitted (clean output).

## SUC-003: Lifecycle a Swarm-mode deployment

- **Actor**: Developer
- **Preconditions**:
  - Deployment entry has `swarm: true` and `deploy_mode: stack` (or
    auto-upgraded when both probe-detected Swarm and `swarm: true`
    are present).
  - Generated compose file exists.
- **Main Flow**:
  1. `rundbat up <env>` runs `docker stack deploy -c docker/docker-
     compose.<env>.yml <app>_<env>` with the deployment's Docker
     context.
  2. `rundbat logs <env>` runs `docker service logs -f
     <app>_<env>_<service>` for each service.
  3. `rundbat down <env>` runs `docker stack rm <app>_<env>`.
  4. `rundbat restart <env>` runs `down` then `up`.
- **Postconditions**:
  - Stack is created / torn down on the remote Swarm cluster.
- **Acceptance Criteria**:
  - [ ] `cmd_up` dispatches to `docker stack deploy` when
    `deploy_mode: stack`.
  - [ ] `cmd_down` dispatches to `docker stack rm`.
  - [ ] `cmd_logs` dispatches to `docker service logs`.
  - [ ] Stack name defaults to `<app_name>_<deployment>`.
  - [ ] When Docker is unreachable, the Docker error is surfaced
    verbatim (no swallow).

## SUC-004: Create a Swarm secret from dotconfig

- **Actor**: Developer
- **Preconditions**:
  - Deployment has `swarm: true` and reachable Docker context.
  - Dotconfig holds the secret value for the key (e.g.
    `POSTGRES_PASSWORD`).
- **Main Flow**:
  1. Developer runs `rundbat secret create <env> POSTGRES_PASSWORD`.
  2. rundbat reads the value from dotconfig for the named
     environment.
  3. rundbat computes the versioned secret name:
     `<app>_<key_lowercase>_v<YYYYMMDD>`.
  4. rundbat runs `docker --context <ctx> secret create <name> -`,
     piping the value on stdin.
  5. rundbat prints the created secret name so the developer can
     update the compose file / redeploy.
- **Postconditions**:
  - A new versioned Swarm secret exists on the target.
- **Acceptance Criteria**:
  - [ ] `cmd_secret_create` pipes the dotconfig value into
    `docker secret create` with the expected name and context.
  - [ ] Missing key in dotconfig produces a clear error (not a
    zero-byte secret).

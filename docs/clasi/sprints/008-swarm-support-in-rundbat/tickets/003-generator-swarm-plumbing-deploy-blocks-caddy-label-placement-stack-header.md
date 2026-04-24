---
id: "003"
title: "Generator: swarm plumbing (deploy blocks, Caddy label placement, stack header)"
status: todo
use-cases: [SUC-002]
depends-on: []
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T03 — Generator: swarm plumbing

## Description

Wire the `swarm: bool` flag from the deployment config through
`generate_compose_for_deployment` at `src/rundbat/generators.py:365`.
When `swarm: True`:

1. **Stack-deploy header comment** at the top of the file:
   ```
   # Deploy with: docker stack deploy -c docker/docker-compose.<env>.yml <stack>
   ```
   `<stack>` = `stack_name` field if set, else
   `<app_name>_<deployment_name>`.

2. **Caddy labels under `services.<app>.deploy.labels`** instead of
   `services.<app>.labels` (Swarm honors `deploy.labels` for
   routing).

3. **Minimal per-service `deploy:` block**:
   ```yaml
   deploy:
     replicas: 1
     restart_policy:
       condition: on-failure
     update_config:
       order: start-first
   ```
   When a service needs Caddy labels, they live under the same
   `deploy:` block as `labels:`.

4. **Justfile update**: when `deploy_mode: stack`, emit
   `docker stack deploy` / `docker stack rm` / `docker service logs`
   in the `<env>_up` / `<env>_down` / `<env>_logs` recipes instead
   of `docker compose …`. `<env>_build` continues to use
   `docker compose build` (build is not a stack op).

The `swarm: false` / absent path is unchanged.

## Affected Files

- `src/rundbat/generators.py` — `generate_compose_for_deployment`
  (EDIT ~:365), `generate_justfile` (EDIT)
- `tests/unit/test_generators.py` — new tests

## Acceptance Criteria

- [ ] `generate_compose_for_deployment(..., swarm=True)` emits the
      `# Deploy with: docker stack deploy -c ...` header as the
      first line
- [ ] Caddy labels placed under `services.<app>.deploy.labels`
      (NOT top-level `labels`)
- [ ] Every service has a `deploy:` block with the four properties
- [ ] `swarm=False` output unchanged (regression test)
- [ ] `generate_justfile` emits `docker stack deploy` / `docker
      stack rm` / `docker service logs` when `deploy_mode: stack`
- [ ] Unit tests cover swarm-True output and swarm-False regression
- [ ] `uv run pytest` passes
- [ ] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_generators.py`
- **New tests to write**:
  - `test_generate_compose_swarm_emits_header`
  - `test_generate_compose_swarm_caddy_labels_under_deploy`
  - `test_generate_compose_swarm_deploy_block_per_service`
  - `test_generate_compose_swarm_false_unchanged`
  - `test_generate_justfile_stack_mode_recipes`
- **Verification command**: `uv run pytest`

## Notes

- Do NOT emit `secrets:` stanzas here — T04 handles that. Keep the
  swarm-branch code organized for T04 to extend.
- Bump `pyproject.toml` version.

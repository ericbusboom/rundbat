---
sprint: 008
status: ready
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update — Sprint 008: Swarm support in rundbat

## What Changed

### discovery.py — Swarm detection

**New function `detect_swarm(context: str) -> dict`**: Mirrors
`detect_caddy()` at discovery.py:157. Runs `docker info --format
'{{json .Swarm}}'` under the given Docker context and parses the
JSON. Returns:

```python
{
    "swarm": bool,           # True iff LocalNodeState == "active"
    "swarm_role": str,       # "manager" | "worker" | ""
    "reachable": bool,       # False if docker info failed to run
}
```

On non-zero exit or JSON-parse failure, returns
`{swarm: False, swarm_role: "", reachable: False}`. Callers decide
how to interpret `reachable: False` (the probe command applies the
transient-failure rule below).

### cli.py — probe extension, stack lifecycle, new secret command

**Updated `cmd_probe` (cli.py:280)**: After the existing Caddy
detection, calls `detect_swarm(context)`. Writes `swarm` and
`swarm_role` fields to the deployment entry in `rundbat.yaml`,
subject to the transient-failure rule (see Design Rationale).

**Updated lifecycle commands — `cmd_up` (cli.py:508), `cmd_down`
(cli.py:587), `cmd_restart` (cli.py:652), `cmd_logs` (cli.py:621)**:
Add a third branch alongside the existing `compose` and `run` modes.
When the deployment has `deploy_mode: stack` (or auto-upgrade
conditions apply — see below):

| Command | Stack behavior |
|---|---|
| `up` | `docker --context <ctx> stack deploy -c docker/docker-compose.<env>.yml <stack>` |
| `down` | `docker --context <ctx> stack rm <stack>` |
| `restart` | `down` then `up` (via the stack branches) |
| `logs` | `docker --context <ctx> service logs -f <stack>_<service>` (per service) |

Stack name defaults to `<app_name>_<deployment_name>`. If the user
sets an explicit `stack_name` field in the deployment entry, that is
used instead.

**Auto-upgrade rule**: If the probe recorded `swarm: true` AND the
deployment has `swarm: true`, and `deploy_mode` is still the default
(`compose`), the lifecycle commands auto-upgrade to stack mode. This
keeps the happy path frictionless: probe → set `swarm: true` →
`rundbat up` does the right thing without also setting
`deploy_mode: stack` by hand.

**New `cmd_secret_create(env, key)`**: Reads the value from
dotconfig for the named environment via the existing `config.load_env`
helper (or equivalent). Computes secret name as
`<app>_<key_lowercase>_v<YYYYMMDD>`. Runs `docker --context <ctx>
secret create <name> -` with the value piped on stdin. On success,
prints the created name; on failure, surfaces the Docker error.

### generators.py — swarm plumbing

**Updated `generate_compose_for_deployment(...)` (generators.py:365)**:
Accepts the `swarm: bool` flag from the deployment config. When
`swarm=True`:

1. Caddy labels for reverse_proxy are placed under
   `services.<app>.deploy.labels` (Swarm places-labels rule) instead
   of `services.<app>.labels`.
2. Each service gets a minimal `deploy:` block:
   ```yaml
   deploy:
     replicas: 1
     restart_policy:
       condition: on-failure
     update_config:
       order: start-first
   ```
3. The compose file is prefixed with a header comment:
   `# Deploy with: docker stack deploy -c docker/docker-
   compose.<env>.yml <stack>`
4. When the deployment has declared secrets (via the existing secret
   configuration path), emit a top-level `secrets:` block with
   `external: true` entries and per-service `secrets:` attachments.
   Each attachment uses a stable `target:` name matching the `_FILE`
   env-var convention (e.g. the env `POSTGRES_PASSWORD_FILE` resolves
   to target `postgres_password`).

**Updated `generate_justfile(...)`**: When a deployment has
`deploy_mode: stack`, the `<env>_up`, `<env>_down`, and `<env>_logs`
recipes emit the `docker stack …` / `docker service logs …`
commands instead of `docker compose …`.

### deploy.py — deploy-init Swarm prompt, stack branch

**Updated `init_deployment(...)`**: After the remote host is picked
and stored in `rundbat.yaml`, the function calls `detect_swarm` on
the new context. If Swarm is detected, it offers (via the existing
interactive prompting pattern — `cmd_deploy_init` owns the prompt in
the CLI layer) to set `swarm: true` + `deploy_mode: stack` in the
new deployment entry before writing the config.

**Updated `deploy(...)`**: When `deploy_mode == "stack"`, dispatches
to a new `_deploy_stack(...)` helper that calls `docker stack deploy`.
Otherwise unchanged (compose / run branches as before).

### rundbat.yaml schema — new deployment fields

New optional fields on each deployment entry:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `swarm` | bool \| "unknown" | — (omitted) | Probe result / explicit opt-in |
| `swarm_role` | string | — | `manager` / `worker` / `""` |
| `stack_name` | string | `<app>_<deployment>` | Override Swarm stack name |
| `deploy_mode` | string | `compose` | Third allowed value: `stack` |

### content/skills/ and content/agents/ — doc updates

**New `content/skills/docker-swarm-deploy.md`**: When to prefer Swarm
over plain compose, how rundbat detects Swarm, stack lifecycle
commands, one-node Swarm as a viable middle ground, deploy-init
Swarm prompt flow, troubleshooting quick-refs.

**Updated `content/skills/docker-secrets-swarm.md`**: Remove the
"rundbat doesn't currently generate Swarm-secret stanzas" caveat.
Show the actual generated output (`secrets: external: true`).
Document `rundbat secret create` and the versioned naming scheme.

**Updated `content/skills/deploy-init.md`**: Add a step describing
the Swarm probe during `deploy-init` and the `swarm: true +
deploy_mode: stack` opt-in prompt.

**Updated `content/skills/deploy-setup.md`**: Brief addition
describing when to choose stack mode.

**Updated `content/skills/diagnose.md`**: Add Swarm-specific
troubleshooting: `docker service ps`, `docker node ls`, why a stack
may stay in `starting` without manager quorum.

**Updated `content/agents/deployment-expert.md`**: One bullet noting
that the agent handles Swarm-mode deployments via the
`docker-swarm-deploy` skill.

## Why

rundbat's current compose-only model is insufficient when users
want the operational benefits of Swarm: managed service secrets,
restart policies, rolling updates, and simpler remote invocation
(`docker stack deploy` instead of copy-the-compose-file-and-run-
compose-up). The `docker-secrets-swarm` skill already advertises the
Swarm secret workflow but rundbat cannot yet generate the compose
stanzas the skill teaches — this sprint closes that gap.

`detect_swarm` is the natural extension of `detect_caddy` — probing
is the only reliable way to know whether a Docker context has Swarm
enabled, short of requiring users to hand-annotate the config.

Splitting `deploy_mode` to accept `stack` (in addition to `compose`
and `run`) keeps the lifecycle layer uniform: the same command shape
(`rundbat up`, `rundbat down`, etc.) works across all three modes
and the dispatch lives in one place (cli.py).

## Impact on Existing Components

| Component | Change |
|---|---|
| `discovery.py` | New `detect_swarm()` function alongside `detect_caddy()` and `detect_gh()` |
| `cli.py` | `cmd_probe` extended; `cmd_up`/`cmd_down`/`cmd_restart`/`cmd_logs` gain `deploy_mode: stack` branch; new `cmd_secret_create` |
| `generators.py` | `generate_compose_for_deployment` gains `swarm` branch emitting `deploy:`, `secrets:`, header comment, Caddy label placement change |
| `deploy.py` | `init_deployment` Swarm prompt; new `_deploy_stack(...)` helper invoked from `deploy()` when `deploy_mode: stack` |
| `config.py` | No change — schema additions are optional fields |
| `content/skills/` | One new file; four updated |
| `content/agents/deployment-expert.md` | One bullet added |

Backward compatibility: all new fields are optional and additive.
Deployments without `swarm` / `deploy_mode: stack` behave exactly as
before. The legacy `generate_compose()` swarm parameter (generators.py:
278) is left in place for backward compatibility with any lingering
direct callers; new code goes through `generate_compose_for_deployment`.

## Migration Concerns

**Existing rundbat.yaml**: All new fields are optional. Existing
deployments continue to work unchanged.

**Existing generated compose files**: The new generator output is a
strict superset (for `swarm: true` deployments) — the file remains
valid for `docker compose -f` usage as well, though Swarm-specific
blocks (`deploy:`, top-level `secrets: external: true`) will be
ignored by plain `docker compose`. When `swarm: false` / absent, the
output is unchanged.

**Skills**: Existing `docker-secrets-swarm.md` gains accuracy (the
caveat is removed). No removal of functionality. All other skill
updates are additive.

## Design Rationale

### Why `detect_swarm` mirrors `detect_caddy` instead of reading a static config field

Swarm state is a runtime property of the Docker daemon, not something
users declare. Probing the context is the only reliable signal and
keeps the user experience consistent with the Caddy-detection model.

### Why the probe transient-failure rule (`swarm: unknown`, no overwrite)

If a deployment has `swarm: true` but the probe cannot reach the
context (offline host, auth failure, transient network error),
`rundbat probe` reports `swarm: unknown` and does NOT overwrite a
prior `true` with `false`. Lifecycle commands still attempt
`docker stack deploy` and surface the Docker error verbatim.

Reason: a transient probe failure should not silently downgrade the
deployment from stack mode to compose mode — that would be a
behavior change the user did not request and could deploy against
the wrong orchestrator the next time the command runs. The user's
declared state (`swarm: true`) takes priority; the probe only
*upgrades* knowledge, never downgrades it silently. The `unknown`
state is visible in the config so users can see that rundbat
could not confirm the current state.

### Why auto-upgrade `deploy_mode` to `stack` when probe AND config both say swarm

Requiring the user to set both `swarm: true` AND `deploy_mode: stack`
is redundant: the only reason to set `swarm: true` on a probed-Swarm
host is to drive stack deployment. The auto-upgrade removes a
footgun without taking options away (explicit `deploy_mode: compose`
on a `swarm: true` deployment still works — the user is in charge).

### Why secret names are versioned `<app>_<key>_v<YYYYMMDD>`

Swarm secrets are immutable — rotation works by creating a new
version and updating the stack to reference it. The versioned name
makes rotation observable (`docker secret ls`) and lets old secret
versions linger until the operator explicitly prunes them. This
matches the pattern `docker-secrets-swarm.md` already documents.

### Why stack name defaults to `<app>_<deployment>` instead of just `<deployment>`

A single Swarm cluster may host multiple apps. Including the app
name prevents collisions (e.g., two projects both deploying an env
named `prod` into the same cluster). Users who know their cluster
is single-tenant can override with `stack_name: <whatever>`.

## Open Questions

None. All design decisions are resolved by the TODO and the
stakeholder's pre-approved plan.

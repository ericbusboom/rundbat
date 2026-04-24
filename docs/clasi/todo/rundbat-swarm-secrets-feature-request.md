---
status: pending
---

# Feature request for `rundbat`: native swarm-secret management

## Context

This is a feature request to hand to the `rundbat` maintainer / agent,
not a task for this project. The motivation came from the Docker
System Overhaul (sprint 015): once we got leaguesync deploying as a
swarm stack with Docker secrets, it became obvious that a big chunk
of what we hand-rolled (`docker/prod-make-secrets.sh`,
`docker/docker-compose.prod.yaml`) is generic enough to belong
upstream in rundbat.

If this feature lands in rundbat, we can delete
`docker/prod-make-secrets.sh` and `docker/prod-env.sh` (and shrink
`docker-compose.prod.yaml` to just the `deploy:` blocks) from this
repo.

## Problem

Every rundbat project that deploys to swarm has to hand-roll the
same "create Docker swarm secrets from dotconfig values" dance.
rundbat's `docker-secrets-swarm.md` skill spells out the pattern but
explicitly says *"rundbat doesn't currently generate Swarm-secret
stanzas"* and *"hand-edit `docker/docker-compose.<env>.yml` to add
the `secrets:` block"*. So every swarm user ends up writing a script
like this:

```bash
# docker/prod-make-secrets.sh (extracted, redacted)
create() { ... docker --context "$MGR" secret create "$name" - ... }
create "leaguesync_meetup_private_key_v20260424" "$(dotconfig load prod --file *.pem --stdout)"
create "leaguesync_pike13_client_secret_v20260424" "${PIKE13_CLIENT_SECRET:-}"
create "leaguesync_api_token_v20260424" "${LEAGUESYNC_API_TOKEN:-}"
# ... six total
```

Plus a hand-edited `docker-compose.prod.yaml` overlay with the
`secrets:` top-level block, per-service attachments, and `*_FILE` env
vars. None of it is project-specific — it's derivable from a
declaration in `rundbat.yaml`.

## Concrete use case: leaguesync

Leaguesync has 6 swarm secrets on swarm1 backing the cron + API
services on swarm2:

- `leaguesync_meetup_private_key_v20260424` — from a SOPS-encrypted
  PEM file in `config/prod/`
- `leaguesync_{meetup_client_id,pike13_client_secret,zoom_client_secret,zoom_secret_token,api_token}_v20260424`
  — each from a single env-var value in `config/prod/secrets.env`

## Proposed interface

### 1. A `secrets:` block in `rundbat.yaml` per deployment

```yaml
deployments:
  prod:
    compose_file: docker/docker-compose.yaml
    docker_context: swarm2         # where tasks run
    manager: swarm1                # where secrets live (control plane)
    swarm: true                    # signals stack-deploy + secret paths
    strategy: context
    hostname: sync.jtlapp.net

    secrets:
      # target name (stable; app reads /run/secrets/<target>)
      meetup_private_key:
        from_file: stu1884kfcr2sftkimel04d9lo.pem   # dotconfig --file source
        services: [leaguesync-cron]
      meetup_client_id:
        from_env: MEETUP_CLIENT_ID                  # dotconfig env-var source
        services: [leaguesync-cron]
      pike13_client_secret:
        from_env: PIKE13_CLIENT_SECRET
        services: [leaguesync-cron]
      zoom_client_secret:
        from_env: ZOOM_CLIENT_SECRET
        services: [leaguesync-cron]
      zoom_secret_token:
        from_env: ZOOM_SECRET_TOKEN
        services: [leaguesync-cron]
      api_token:
        from_env: LEAGUESYNC_API_TOKEN
        services: [leaguesync-api]

    # Versioning scheme for external secret names. Default:
    # "{app}_{target}_v{YYYYMMDD}". Override per-secret if needed.
    secret_version_format: "{app}_{target}_v{date}"
```

Design notes:

- **target name** (map key) is stable — app reads
  `/run/secrets/{target}` regardless of version
- **`from_file`** vs **`from_env`** — mutually exclusive, matches
  dotconfig's two load modes
- **`services`** — which services in the compose file attach this
  secret; enforces the "don't share credentials" rule
- **versioning** — rundbat tracks the current version; rotation
  creates a new dated version

### 2. A `rundbat secrets` command

```bash
rundbat secrets <env>                  # create all configured secrets (idempotent)
rundbat secrets <env> --dry-run        # show commands that would run
rundbat secrets <env> --list           # show current state on the manager
rundbat secrets <env> --rotate <name>  # create new version, swap attachment, remove old
```

The `create` action:

1. For each secret in `rundbat.yaml[<env>].secrets`, compute the
   versioned external name.
2. Check if it already exists on the manager context.
3. If not, pipe the value via stdin to
   `docker --context <manager> secret create <versioned-name> -`.
4. Never write the decrypted value to disk.

The rotate action:

1. Create new versioned secret.
2. Update service spec (new source, same target).
3. Wait for tasks to converge.
4. Remove old secret.

### 3. `rundbat generate` emits the swarm-secret stanzas

When `swarm: true` and `secrets:` is populated, the generated
`docker-compose.<env>.yml` already contains the full wiring:

```yaml
services:
  leaguesync-cron:
    secrets:
      - source: leaguesync_meetup_private_key_v20260424
        target: meetup_private_key
      # ... etc (only the secrets listed in services: [leaguesync-cron])
    environment:
      - MEETUP_PRIVATE_KEY_FILE=/run/secrets/meetup_private_key
      # ... etc

secrets:
  leaguesync_meetup_private_key_v20260424:
    external: true
  # ... etc
```

No hand-edited overlay needed.

## What this replaces

Today a rundbat-using project with swarm secrets has:

- A `prod-make-secrets.sh` script (50+ lines of bash)
- A hand-edited `docker-compose.prod.yaml` overlay with `secrets:`
  blocks (40+ lines of YAML)
- Ad-hoc versioning conventions
- Manual rotation procedures

After this feature: declare secrets in `rundbat.yaml`, run
`rundbat secrets prod`, run `rundbat up prod` (which runs
`rundbat generate` and `docker stack deploy`). Zero hand-written
bash, zero YAML overlay hand-edits.

## Related / pairs well with

This feature pairs well with a separate `dotconfig --no-export` flag
request (captured in a dotconfig-side brief). Together they let
`rundbat up <swarm-env>` work end-to-end with no post-processing.

## Acceptance criteria

- [ ] `rundbat.yaml` schema accepts `secrets:` per-deployment
      (validated on load)
- [ ] `rundbat secrets <env>` creates all declared swarm secrets
      idempotently using the versioned external name format
- [ ] `rundbat secrets <env> --list` reports status (exists vs
      missing per declared secret)
- [ ] `rundbat generate` emits `secrets:` top-level + per-service
      `secrets:` attachments + `*_FILE` env vars into the swarm
      compose file for deployments with `swarm: true`
- [ ] `rundbat up <swarm-env>` runs `docker stack deploy -c <generated>`
      (not `docker compose up`) on a swarm deployment
- [ ] `rundbat secrets <env> --rotate <target>` does create → swap →
      wait → remove safely
- [ ] Non-swarm deployments are unaffected — the compose-secrets or
      env_file path still works
- [ ] The `.claude/skills/rundbat/docker-secrets-swarm.md` skill
      gets updated to point to the native command instead of
      "hand-edit the compose file"

## Non-goals

- Don't implement Vault / AWS Secrets Manager / 1Password backends.
  dotconfig + SOPS stays the source of truth; this feature is just
  about automating the hand-off to Docker Swarm.
- Don't change anything about non-secret dotconfig values. They
  flow through `env_file:` exactly like today.
- Don't auto-rotate on deploy. Rotation is explicit (`--rotate`).

## Implementation hint

The "state" question (what's the current version of each secret?)
can be solved two ways:

- **Query the manager** — `docker --context <manager> secret ls
  --filter name=<prefix> --format '{{.Name}}'`, parse the versions,
  pick the highest dated suffix.
- **Track in a file** — `config/<env>/rundbat.state.yaml` with the
  current `{target}` → `{versioned-name}` mapping.

Querying is simpler (no state file to keep in sync) but slower. Pick
one and document it. Recommendation: query the manager; add caching
later if needed.

## When this lands — cleanup on the leaguesync side

Once rundbat ships this feature we delete from leaguesync:

- `docker/prod-make-secrets.sh`
- `docker/prod-env.sh` (assuming the paired dotconfig `--no-export`
  lands too)
- The `secrets:` top-level block + per-service attachments in
  `docker/docker-compose.prod.yaml`
- The `prod-secrets` and `prod-env` recipes from `justfile`

And replace them with three lines in `config/rundbat.yaml` under
`deployments.prod.secrets:`.

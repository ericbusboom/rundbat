# docker-secrets-swarm

Native runtime secrets for Docker Swarm services. Secrets are stored
encrypted in the Raft log, mounted as files inside task containers, and
only granted to services that explicitly request them.

## When to use

- Deploying to a Swarm cluster (`docker stack deploy`, `docker service create`)
- A rundbat deployment where `swarm: true` or the Docker context points
  at a Swarm manager
- Runtime credentials: DB passwords, API tokens, TLS certs, SSH keys

If you're doing `docker compose up` on a single VPS, see
`docker-secrets-compose` instead — Compose-mode secrets have different
semantics even if the YAML looks similar.

## Create a secret

Feed the value via stdin. Never write it to disk on the manager, and
never pass it through a shell arg (which lands in history and `ps`):

```bash
printf '%s' "$POSTGRES_PASSWORD" | \
  docker secret create app_postgres_password_v2026_04_23 -
```

**Use versioned names.** A Docker secret is immutable — you rotate by
creating a new secret, not by mutating the existing one. A timestamp or
build ID in the name makes the rotation audit trail obvious.

## Attach a secret to a service

Imperative:

```bash
docker service create \
  --name app \
  --secret source=app_postgres_password_v2026_04_23,target=postgres_password \
  myorg/app:latest
```

Stack compose (preferred for rundbat-generated deployments):

```yaml
services:
  app:
    image: myorg/app:latest
    secrets:
      - source: app_postgres_password_v2026_04_23
        target: postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

secrets:
  app_postgres_password_v2026_04_23:
    external: true
```

Two layers of naming, on purpose:

- **`source:`** — the versioned external secret name. Operators see
  this; it changes on every rotation.
- **`target:`** — the stable logical name the application reads. The
  app always opens `/run/secrets/postgres_password` regardless of which
  version of the secret is currently attached.

Keep this split. Collapsing them forces application changes on every
rotation.

## Rotate a secret

For a credential the backing system also knows (a DB password, an API
token), rotation is a two-phase operation:

1. Create or enable the new credential in the backing service.
   The old credential must keep working during the overlap.
2. Create the new Docker secret:
   ```bash
   printf '%s' "$NEW_PASSWORD" | \
     docker secret create app_postgres_password_v2026_05_01 -
   ```
3. Update the service to swap the attachment:
   ```bash
   docker service update \
     --secret-rm app_postgres_password_v2026_04_23 \
     --secret-add source=app_postgres_password_v2026_05_01,target=postgres_password \
     app
   ```
4. Wait for the new task to come up. Verify the service is healthy with
   the new credential.
5. Revoke the old credential on the backing service.
6. Remove the old Docker secret:
   ```bash
   docker secret rm app_postgres_password_v2026_04_23
   ```

Do not rotate the container secret before the backend accepts the new
credential. That only produces an outage with a better-looking name.

## Preflight in the container

Fail fast on a missing secret. Do this in the entrypoint, before the
service binds a port:

```bash
test -s /run/secrets/postgres_password || {
  echo "missing required secret: postgres_password" >&2
  exit 1
}
```

For several required secrets:

```bash
for secret in postgres_password api_token signing_key; do
  test -s "/run/secrets/$secret" || {
    echo "missing required secret: $secret" >&2
    exit 1
  }
done
```

## Rundbat integration

rundbat generates the Swarm secret stanzas for you when the deployment
has `swarm: true` and secrets are declared. Source of truth stays in
dotconfig (SOPS-encrypted); plaintext only appears on the manager
during `docker secret create`.

### 1. Declare secrets on the deployment

In `rundbat.yaml`:

```yaml
deployments:
  prod:
    docker_context: prod-ctx
    swarm: true
    deploy_mode: stack
    secrets:
      - POSTGRES_PASSWORD
      - SESSION_SECRET
```

### 2. Generate the compose file

`rundbat generate` produces a Swarm-ready `docker/docker-compose.prod.yml`:

```yaml
# Deploy with: docker stack deploy -c docker/docker-compose.prod.yml myapp_prod
services:
  app:
    # …
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      SESSION_SECRET_FILE: /run/secrets/session_secret
    secrets:
      - source: myapp_postgres_password
        target: postgres_password
      - source: myapp_session_secret
        target: session_secret
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
      update_config:
        order: start-first

secrets:
  myapp_postgres_password:
    external: true
  myapp_session_secret:
    external: true
```

The `source:` name is the external secret rundbat expects operators
to create (step 3). The `target:` is the stable logical name the
application reads — it does not change across rotations.

### 3. Create the secrets from dotconfig

Use `rundbat secret create`:

```bash
rundbat secret create prod POSTGRES_PASSWORD
rundbat secret create prod SESSION_SECRET
```

Each call pipes the dotconfig value into
`docker --context <ctx> secret create <app>_<key_lc>_v<YYYYMMDD> -`
on stdin (never through argv). The date-stamped name makes the
rotation trail obvious in `docker secret ls`.

### 4. Point the stack at the current version

The `external: true` reference in the generated compose names the
**logical** secret (`myapp_postgres_password`). To attach an actual
versioned secret (e.g. `myapp_postgres_password_v20260424`), create
an alias or set the `name:` override at the top-level entry:

```yaml
secrets:
  myapp_postgres_password:
    external: true
    name: myapp_postgres_password_v20260424
```

Bump the `name:` on each rotation and re-run `rundbat up prod` (which
shells out to `docker stack deploy`). Old versions remain until you
prune them.

## References

- https://docs.docker.com/engine/swarm/secrets/
- https://docs.docker.com/engine/swarm/raft/ (why Swarm secrets are
  durable across manager reboots)

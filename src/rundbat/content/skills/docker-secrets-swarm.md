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

rundbat doesn't currently generate Swarm-secret stanzas. For a Swarm
deployment:

1. **Source of truth stays in dotconfig.** Values are encrypted at rest
   with SOPS/age; only plaintext appears during the `docker secret create`
   step.
2. **Create secrets from dotconfig at deploy time.** Wrap your deploy in
   a step that pipes each value through. Example:
   ```bash
   for key in POSTGRES_PASSWORD API_TOKEN SIGNING_KEY; do
     value=$(dotconfig get -d prod "$key")
     docker --context prod secret create "app_${key,,}_v$(date +%Y_%m_%d)" - <<<"$value"
   done
   ```
3. **Hand-edit `docker/docker-compose.<env>.yml`** to add the `secrets:`
   block and swap `env_file:` entries for `*_FILE` env vars. Treat this
   as a production-only overlay that survives `rundbat generate`
   re-runs, or maintain it in a separate compose file referenced by
   `-f`.

A future rundbat enhancement could generate Swarm secret stanzas
automatically when a deployment has `swarm: true`. Not there yet.

## References

- https://docs.docker.com/engine/swarm/secrets/
- https://docs.docker.com/engine/swarm/raft/ (why Swarm secrets are
  durable across manager reboots)

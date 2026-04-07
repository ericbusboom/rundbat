---
title: Deployment use cases — full lifecycle
priority: high
created: 2026-04-07
related: convert-mcp-to-cli-plugin.md
---

# Deployment Use Cases — Full Lifecycle

rundbat is pivoting from MCP-only to CLI-first + Claude skills. These use
cases cover the full deployment lifecycle for web applications, from project
initialization through teardown.

## Assumptions

- rundbat both generates artifacts (docker/, Justfile) AND executes deployment
- Caddy is pre-existing on target hosts — rundbat adds Docker labels only
- Database operations (dump, restore, migrate) are Justfile recipes
- Secrets flow from dotconfig → Docker (securely)
- Docker Compose is the deployment unit
- Multiple deployment targets: test/demo and production
- Supported databases: Postgres, MariaDB, Redis
- Supported apps: Node.js, Python web frameworks

---

## Stage 1: Project Initialization

### UC-01: Initialize project with deployment interview

**Actor:** Developer + deployment-expert agent
**Trigger:** "Set up deployment for this project"
**Preconditions:** Project code exists, dotconfig may or may not be initialized

**Flow:**
1. Agent detects project type (Node/Python, framework)
2. Agent interviews developer:
   - App name and source (package.json, pyproject.toml)
   - What services are needed (Postgres, MariaDB, Redis)
   - Deployment targets (local dev, test/demo, production)
   - Remote Docker host access method (SSH key, Docker context)
   - Hostname(s) for each deployment
   - Swarm or standalone Docker on target host(s)
3. Agent runs `dotconfig init` if needed
4. Agent writes answers to `config/rundbat.yaml` via dotconfig
5. Agent generates initial `docker/` directory scaffold

**Produces:**
- `config/rundbat.yaml` — app name, services, deployment targets, hostnames
- `config/{env}/public.env` — per-environment public config
- `docker/` directory scaffold (Dockerfile, docker-compose.yml, Justfile)

**Key config captured in rundbat.yaml** (single source of truth for
deployment topology — per-env public.env holds only app-level vars):

```yaml
app_name: widgetco
app_name_source: package.json name
framework: express  # or next, flask, django, fastapi
services:
  - type: postgres
    version: "16"
  - type: redis
    version: "7"
deployments:
  dev:
    type: local-docker
  test:
    type: remote-docker
    host: test.widgetco.io
    access: ssh  # or docker-context
    ssh_key: config/keys/deploy_test  # optional
    hostname: test.widgetco.io
    swarm: false
  prod:
    type: remote-docker
    host: prod.widgetco.io
    access: ssh
    hostname: widgetco.io
    additional_hostnames:
      - www.widgetco.io
    swarm: true
```

---

## Stage 2: Local Development

### UC-02: Quick dev database

**Actor:** Developer
**Trigger:** "I need a dev database"
**Preconditions:** Docker running locally, project initialized

**Flow:**
1. rundbat reads `rundbat.yaml` for configured database type
2. Generates password, allocates port
3. Runs `docker run -d` for the database (Postgres, MariaDB, or Redis)
4. Saves connection string to `config/dev/secrets.env` via dotconfig
5. Saves container name, port, engine to `config/dev/public.env`
6. Returns connection string

**Note:** This is the existing `dev-database` flow — no compose, just a
quick container for local iteration.

### UC-03: Local Docker compose environment

**Actor:** Developer
**Trigger:** "Run the full stack locally"
**Preconditions:** Project initialized, `docker/` directory exists

**Flow:**
1. rundbat loads config: `dotconfig load -d dev --json --flat -S`
2. Writes `.env` for compose: `dotconfig load -d dev` (flat .env)
3. Runs `docker compose -f docker/docker-compose.yml up -d`
4. Verifies services are healthy

**Note:** Uses the same compose file that will be deployed remotely,
but with local-specific env vars (no Caddy labels needed locally).

---

## Stage 3: First Remote Deployment

### UC-04: Configure remote Docker host

**Actor:** Developer + deployment-expert agent
**Trigger:** "Deploy to my test server" (first time)
**Preconditions:** Remote host exists, Docker installed on it

**Flow:**
1. Agent reads deployment config from `rundbat.yaml`
2. If access method is SSH:
   a. Verify SSH connectivity (`ssh -o ConnectTimeout=5 host true`)
   b. Store SSH key path in `rundbat.yaml` if provided
   c. Set up Docker context for the remote host, or use `DOCKER_HOST=ssh://...`
3. If access method is Docker context:
   a. Verify context exists (`docker context inspect {name}`)
4. Verify Docker is accessible on remote host (`docker info`)
5. Save verified access config to `rundbat.yaml`

**Produces:** Verified remote Docker access, stored in rundbat.yaml

### UC-05: Build and push Docker image

**Actor:** Developer or CI
**Trigger:** First deployment, or code changes
**Preconditions:** Dockerfile exists, registry accessible (or direct load)

**Flow:**
1. Build image: `docker build -f docker/Dockerfile -t {app}:{tag} .`
2. If remote host (not local):
   a. Push to registry, OR
   b. `docker save | ssh host docker load` (no registry needed)
3. Tag as `latest` and version

**Justfile recipes:** `just build`, `just push`, `just build-and-push`

### UC-06: Deploy app + services to remote Docker host

**Actor:** Developer or CI
**Trigger:** "Deploy to test" / "Deploy to production"
**Preconditions:** Image built, remote host configured, secrets stored

**Flow:**
1. Load deployment config: `dotconfig load -d {env} --json --flat -S`
2. Generate deployment-specific compose overrides (Caddy labels, hostnames)
3. Transfer secrets to Docker host (see UC-07)
4. Deploy compose stack:
   - If swarm: `docker stack deploy -c docker-compose.yml {app}`
   - If standalone: `docker compose up -d`
5. Verify services are healthy
6. Report deployment status with URL

**Caddy labels (standalone):**
```yaml
labels:
  caddy: "{hostname}"
  caddy.reverse_proxy: "{{upstreams {port}}}"
```

**Caddy labels (swarm):**
```yaml
deploy:
  labels:
    caddy: "{hostname}"
    caddy.reverse_proxy: "{{upstreams {port}}}"
```

**Justfile recipes:** `just deploy-test`, `just deploy-prod`

### UC-07: Transfer secrets from dotconfig to Docker

**Actor:** rundbat (during deployment)
**Trigger:** Part of UC-06 deployment flow
**Preconditions:** Secrets stored in dotconfig, remote host accessible

**Flow:**
1. Load secrets: `dotconfig load -d {env} --json -S` (sectioned, to see what's secret)
2. The deployment-expert skill chooses the transfer method based on context:
   - **Docker secrets (swarm):** Create Docker secrets from each key-value pair,
     reference in compose via `secrets:` stanza
   - **Env file (standalone):** Generate `.env.{env}`, transfer via SSH,
     reference in compose via `env_file:`, restrict permissions
   - **Inline env vars:** Simplest option for dev/test, least secure
3. Never log or echo secret values

**Decision rationale:** The skill has context about the deployment target
(swarm flag, security requirements, convenience tradeoffs) and chooses
the appropriate method. rundbat CLI supports all three mechanisms.

---

## Stage 4: Ongoing Operations

### UC-08: Redeploy after code changes

**Actor:** Developer
**Trigger:** "Push the new version" / code merged to deploy branch
**Preconditions:** Initial deployment complete

**Flow:**
1. Build new image: `just build`
2. Push/transfer image: `just push`
3. If database migration needed:
   a. Run migration first: `just db-migrate-{env}`
   b. Verify migration succeeded
4. Deploy new version:
   - Swarm: `docker service update --image {app}:{tag} {service}`
   - Standalone: `docker compose up -d` (pulls new image)
5. Verify health
6. Report status

**Justfile recipes:** `just redeploy-test`, `just redeploy-prod`

### UC-09: Remote database migration

**Actor:** Developer
**Trigger:** "Run migrations on test/prod"
**Preconditions:** App container running on remote host

**Flow:**
1. Run migration command inside the app container:
   `docker exec {container} {migration_command}`
   - Node/Prisma: `npx prisma migrate deploy`
   - Node/Knex: `npx knex migrate:latest`
   - Python/Django: `python manage.py migrate`
   - Python/Alembic: `alembic upgrade head`
2. Report migration output

**Justfile recipe:** `just db-migrate-{env}`

### UC-10: Remote database dump

**Actor:** Developer
**Trigger:** "Back up the test/prod database"
**Preconditions:** Database container running

**Flow:**
1. Run dump command inside database container:
   - Postgres: `docker exec {db_container} pg_dump -U {user} {dbname}`
   - MariaDB: `docker exec {db_container} mariadb-dump -u {user} -p{pass} {dbname}`
2. Transfer dump file from remote host to local machine
3. Store with timestamp: `backups/{env}_{dbname}_{timestamp}.sql`

**Justfile recipe:** `just db-dump-{env}`

### UC-11: Remote database restore

**Actor:** Developer
**Trigger:** "Restore the database from backup"
**Preconditions:** Dump file available, database container running

**Flow:**
1. Transfer dump file to remote host (if not already there)
2. Restore into database container:
   - Postgres: `docker exec -i {db_container} psql -U {user} {dbname} < dump.sql`
   - MariaDB: `docker exec -i {db_container} mariadb -u {user} -p{pass} {dbname} < dump.sql`
3. Verify restore succeeded

**Justfile recipe:** `just db-restore-{env} path/to/dump.sql`

---

## Stage 5: Teardown

### UC-12: Take down a deployment

**Actor:** Developer
**Trigger:** "Take down the test environment" / "Shut it all down"
**Preconditions:** Deployment exists

**Flow:**
1. Confirm with developer (destructive action)
2. Stop services:
   - Swarm: `docker stack rm {app}`
   - Standalone: `docker compose down`
3. Optionally remove volumes (data): `docker compose down -v`
4. Optionally remove Docker secrets (swarm)
5. Report what was removed

**Justfile recipes:** `just down-{env}`, `just down-{env}-with-data`

---

## Cross-Cutting Concerns

### CC-01: Multiple deployment targets

Each deployment (dev, test, prod) has its own:
- `config/{env}/public.env` — app-level vars (PORT, NODE_ENV, etc.)
- `config/{env}/secrets.env` — database passwords, API keys
- Compose override or environment-specific labels

Deployment topology (host, access, hostname, swarm) lives in
`rundbat.yaml` under `deployments.{env}`.

The Justfile parameterizes by environment:
`just deploy ENV=test`, `just db-dump ENV=prod`

### CC-02: Docker host access

Two access methods:
- **SSH**: `DOCKER_HOST=ssh://user@host` or Docker context created from SSH
- **Docker context**: Pre-configured, just `docker context use {name}`

Stored in `rundbat.yaml` under `deployments.{env}.access` and
`deployments.{env}.host`. The CLI/Justfile reads these to set
`DOCKER_HOST` or `DOCKER_CONTEXT` before running Docker commands.

### CC-03: Secrets lifecycle

```
Developer → dotconfig save (encrypted at rest via SOPS)
                ↓
dotconfig load --json (decrypted in memory)
                ↓
deployment-expert skill decides transfer method
                ↓
Docker secrets (swarm) | env_file (standalone) | inline env (dev)
                ↓
Container reads at runtime
```

The skill chooses the mechanism per-deployment. Secrets are never
stored in plaintext on disk on the remote host (Docker secrets) or
are permission-restricted (env_file approach). For local dev, inline
env vars in compose are acceptable for convenience.

### CC-04: Caddy hostname routing

Caddy is pre-existing on all target hosts with its Docker provider
enabled. rundbat adds labels to compose services:

- **Standalone Docker:** labels on the service
- **Docker Swarm:** labels on `deploy:` section

Multiple hostnames per deployment are supported (e.g., `www.` redirect).

### CC-05: Swarm vs standalone awareness

Stored in `rundbat.yaml` under `deployments.{env}.swarm`.
Affects:
- How compose is deployed (`docker stack deploy` vs `docker compose up`)
- Where Caddy labels go (service labels vs deploy labels)
- How services are updated (service update vs compose up)
- How secrets are managed (Docker secrets vs env_file)

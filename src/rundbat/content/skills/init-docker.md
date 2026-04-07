# init-docker

Scaffold a `docker/` directory for the project. Produces a self-contained
deployment package: Dockerfile, docker-compose.yml, Justfile, and
.env.example.

## When to use

- "Set up Docker for this project"
- "Containerize this app"
- "I need a compose file"

## Prerequisites

- Project initialized (`rundbat.yaml` exists)
- App framework detected or specified

## Steps

1. Read project config:
   ```bash
   dotconfig load -d dev --file rundbat.yaml -S
   ```

2. Detect framework if not configured:
   - `package.json` → Node.js (check for next, express, etc.)
   - `pyproject.toml` / `requirements.txt` → Python (check for flask, django, fastapi)

3. Generate `docker/Dockerfile`:
   - Node: multi-stage build, `npm ci`, `npm start`
   - Python: slim base, pip install, gunicorn/uvicorn
   - Framework-specific optimizations (Next.js standalone, Django collectstatic)

4. Generate `docker/docker-compose.yml`:
   - App service referencing the Dockerfile
   - Database services from `rundbat.yaml` services list
   - Caddy labels (parameterized by hostname from config)
   - Environment variables from dotconfig
   - Health checks for all services

5. Generate `docker/Justfile`:
   - `just build` — build the app image
   - `just up` / `just down` — compose lifecycle
   - `just push` — push image to registry or remote host
   - `just deploy ENV=<env>` — deploy to remote
   - `just db-dump ENV=<env>` — database backup
   - `just db-restore ENV=<env> FILE=<path>` — database restore
   - `just db-migrate ENV=<env>` — run migrations
   - `just logs` — tail service logs
   - `just psql` / `just mysql` — database shell

6. Generate `docker/.env.example`:
   ```bash
   dotconfig load -d dev --json -S  # sectioned, to see public vs secret
   ```
   Write public values as-is, replace secret values with placeholders.

## Outputs

```
docker/
  Dockerfile
  docker-compose.yml
  .env.example
  Justfile
```

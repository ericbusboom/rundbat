---
status: draft
---

# Sprint 002 Use Cases

## SUC-001: Scaffold docker/ directory for a new project
Parent: UC-01 (Initialize project with deployment interview)

- **Actor**: Developer
- **Preconditions**: `rundbat.yaml` exists with app_name and framework
- **Main Flow**:
  1. Developer runs `rundbat init-docker`
  2. rundbat detects framework from project files if not in config
  3. rundbat generates Dockerfile, docker-compose.yml, Justfile, .env.example
  4. rundbat reports what was generated
- **Postconditions**: `docker/` directory exists with all files
- **Acceptance Criteria**:
  - [ ] `docker/Dockerfile` exists and is valid for the detected framework
  - [ ] `docker/docker-compose.yml` includes app service and configured databases
  - [ ] `docker/Justfile` includes standard recipes
  - [ ] `docker/.env.example` has public values and redacted secrets

## SUC-002: Add a database service to existing compose
Parent: UC-02 (Quick dev database)

- **Actor**: Developer
- **Preconditions**: `docker/docker-compose.yml` exists
- **Main Flow**:
  1. Developer runs `rundbat add-service postgres` (or mariadb, redis)
  2. rundbat adds the service to docker-compose.yml
  3. rundbat adds env vars to .env.example
  4. rundbat adds Justfile recipes (e.g., `just psql`)
- **Postconditions**: Compose file has new service, env vars, and recipes
- **Acceptance Criteria**:
  - [ ] Service added to compose with health check
  - [ ] Environment variables added to .env.example
  - [ ] Justfile recipes added for the service

## SUC-003: Generated compose has correct Caddy labels
Parent: UC-06 (Deploy app + services to remote Docker host)

- **Actor**: Developer
- **Preconditions**: `rundbat.yaml` has deployment with hostname and swarm flag
- **Main Flow**:
  1. `init-docker` reads hostname and swarm config
  2. Generates compose with correct Caddy labels:
     - Standalone: labels on the service
     - Swarm: labels on deploy section
- **Postconditions**: Compose has correct Caddy labels for the deployment mode
- **Acceptance Criteria**:
  - [ ] Standalone labels on service level
  - [ ] Swarm labels on deploy.labels level
  - [ ] Multiple hostnames supported

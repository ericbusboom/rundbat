---
status: draft
---

# Sprint 006 Use Cases

## SUC-001: Containerize an Astro Static Site

- **Actor**: Developer with an Astro project
- **Preconditions**: `rundbat.yaml` exists; `package.json` lists `astro` as a
  dependency.
- **Main Flow**:
  1. Developer runs `rundbat init-docker`.
  2. `detect_framework()` identifies the project as Astro.
  3. `init_docker()` writes a 3-stage Dockerfile (node deps → node build →
     nginx serve), a `docker/nginx.conf` configured for port 8080, a
     docker-compose.yml exposing port 8080, and a `.env.example` with port
     8080.
  4. Developer reviews generated files and proceeds to local testing or
     deployment.
- **Postconditions**: `docker/` directory contains a production-ready Astro
  container configuration.
- **Acceptance Criteria**:
  - [ ] `detect_framework()` returns `{language: "node", framework: "astro", entry_point: "nginx"}` for a project with `astro` in `package.json`.
  - [ ] Generated Dockerfile has 3 stages; runtime stage is `nginx:alpine` exposing port 8080.
  - [ ] `docker/nginx.conf` is written with `listen 8080`, `try_files`, gzip, and cache headers.
  - [ ] `docker-compose.yml` uses port 8080.
  - [ ] `.env.example` uses port 8080 and omits `NODE_ENV`.

## SUC-002: Probe a Remote Host for Reverse Proxy

- **Actor**: Developer setting up or verifying a deployment target
- **Preconditions**: A deployment entry exists in `rundbat.yaml` with a
  `docker_context`.
- **Main Flow**:
  1. Developer runs `rundbat probe prod`.
  2. `detect_caddy(context)` queries the remote Docker host for a running Caddy
     container.
  3. Result (`caddy` or `none`) is saved as `reverse_proxy` in the `prod`
     deployment entry in `rundbat.yaml`.
  4. CLI prints the detected reverse proxy.
- **Postconditions**: `rundbat.yaml` has `reverse_proxy: caddy` or
  `reverse_proxy: none` for the named deployment.
- **Acceptance Criteria**:
  - [ ] `rundbat probe prod` writes `reverse_proxy: caddy` when Caddy is running on the remote context.
  - [ ] `rundbat probe prod` writes `reverse_proxy: none` when no Caddy container is found.
  - [ ] `detect_caddy()` passes the `--context` flag to `docker ps`.
  - [ ] `rundbat deploy-init` automatically probes and stores `reverse_proxy`.

## SUC-003: Generate Caddy Labels When Hostname Is Known

- **Actor**: Developer deploying behind Caddy
- **Preconditions**: A deployment has been probed (`reverse_proxy: caddy`);
  developer knows the public hostname.
- **Main Flow**:
  1. Developer runs `rundbat init-docker --hostname app.example.com`.
  2. `cmd_init_docker` reads the `reverse_proxy` field from the deployment
     config and the provided hostname.
  3. `generate_compose()` includes Caddy labels for the correct port (8080 for
     Astro, 3000/8000 for other frameworks).
  4. Developer runs `rundbat deploy` to push the updated compose file.
- **Alternate Flow (no hostname)**:
  1. Developer runs `rundbat init-docker` without `--hostname`.
  2. `cmd_init_docker` detects `reverse_proxy: caddy` in a deployment config.
  3. CLI prints a warning: "Caddy detected on deployment 'prod' — pass
     --hostname to include reverse proxy labels."
  4. Compose is generated without Caddy labels.
- **Postconditions**: Compose file includes Caddy labels (main flow) or a
  warning is printed (alternate flow).
- **Acceptance Criteria**:
  - [ ] `--hostname` flag is available on `init-docker`.
  - [ ] When `--hostname` is provided, compose file includes `caddy.` labels with the correct port.
  - [ ] When deployment has `reverse_proxy: caddy` but no `--hostname`, CLI prints a warning and proceeds without labels.
  - [ ] Warning message identifies the deployment name.

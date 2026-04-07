# rundbat — Deployment Expert CLI

**Specification Document**
Version 0.2 — April 2026
League of Amazing Programmers

---

## 1. Overview

rundbat is a CLI tool that manages Docker-based deployment environments for web applications. It automates environment discovery, database provisioning, Docker directory generation, secret management, and deployment. It is designed for use by AI coding agents (via Claude skills and agents) and developers (via the CLI directly).

rundbat encodes deployment procedures in executable code rather than instructional documents. When an agent needs a database, it calls a CLI command that creates the database correctly, validates the configuration, and returns a connection string. The agent decides what to set up; rundbat ensures it is set up right.

### 1.1 Design Principles

- **CLI commands for procedures that must be exact.** Creating databases, writing config files, managing secrets, validating connections. The CLI executes the procedure, not the agent.
- **Skill files for decisions that require context.** Choosing between deployment targets, selecting database configurations. Skills are installed via `rundbat install`; the agent reasons about them.
- **Docker is the only runtime.** All databases and application containers run in Docker. No native Postgres installations. If Docker is not present, rundbat guides the user through the setup.
- **dotconfig owns configuration.** rundbat reads and writes through dotconfig. It never touches files under `config/` directly. Secrets are encrypted via dotconfig and SOPS.
- **Recover gracefully from stale state.** Containers disappear, machines change, team members join late. Every environment query includes a liveness check and clear remediation when things are out of sync.

### 1.2 Relationship to CLASI

CLASI manages the software engineering process: sprints, tickets, architecture, code review. rundbat manages the deployment infrastructure: databases, containers, environments, secrets. They are separate tools with no direct dependency. An agent working on a CLASI sprint may call rundbat to get a database connection string, but neither tool knows about the other.

Both follow the same distribution pattern: installed via pipx, with Claude integration via `.claude/` directories.

### 1.3 Relationship to dotconfig

dotconfig is a prerequisite. It manages the `config/` directory structure, handles SOPS encryption of secrets, and provides layered configuration with per-deployment and per-developer overrides. rundbat uses dotconfig for all configuration storage:

- Environment variables (`DATABASE_URL`, connection strings) go into dotconfig `.env` files under the appropriate section (public or secrets).
- rundbat operational state (container names, port allocations, metadata) is stored as `rundbat.yaml`, managed through `dotconfig save` and `dotconfig load --file`.
- Per-developer overrides (Docker context, alternate ports) go into the `local/` directory and are merged automatically by dotconfig when loaded with the `-l` flag.

rundbat calls dotconfig as a subprocess. It runs `dotconfig load` to read configuration, edits the assembled file, and runs `dotconfig save` to write changes back with encryption handled automatically.

---

## 2. Architecture

### 2.1 Prerequisites

- **Docker** — `docker` and `docker compose` CLI commands must work. rundbat does not care what provides them (Docker Desktop, OrbStack, Colima, Docker Engine). If `docker info` succeeds, rundbat proceeds.
- **dotconfig** — installed and initialized in the project.
- **Node.js** — for the applications being deployed.
- **pipx** — for installing rundbat itself.

### 2.2 Installation

rundbat is installed via pipx, which creates a `rundbat` CLI command. Claude integration files (skills, agents, rules) are installed into the project via `rundbat install`.

### 2.3 Out of Scope

- **Database migrations.** rundbat creates the database and provides the connection string. The application owns its schema.
- **Application build configuration.** rundbat may create Dockerfiles and compose files for deployment, but application-level build tools (webpack, esbuild, etc.) are the application's concern.
- **dotconfig internals.** rundbat calls dotconfig commands but does not modify `config/sops.yaml` or manage encryption keys directly.

---

## 3. Configuration Structure

All configuration lives within dotconfig's directory structure. rundbat adds its own files alongside the standard `.env` files. Deployments do not need to be created manually — saving a file to a deployment via dotconfig creates the directory automatically.

```
config/
  sops.yaml                          # SOPS encryption rules (dotconfig managed)
  dev/
    public.env                       # Non-secret env vars: APP_DOMAIN, PORT
    secrets.env                      # SOPS-encrypted: DATABASE_URL, SESSION_SECRET
    rundbat.yaml                     # rundbat state: container names, ports, metadata
  staging/
    public.env
    secrets.env
    rundbat.yaml
  prod/
    public.env
    secrets.env
    rundbat.yaml
  local/
    alice/
      public.env                     # Per-developer overrides
      rundbat.yaml                   # Per-developer rundbat overrides
```

### 3.1 rundbat.yaml Schema

Each deployment has a `rundbat.yaml` containing operational state. The file is loaded via dotconfig, which merges it with any local overrides.

```yaml
# config/dev/rundbat.yaml
app_name: league-enrollment
app_name_source: "pyproject.toml project.name"
notes:
  - "If app name changes in pyproject.toml, update here"

database:
  name: rundbat_league-enrollment_dev
  container: rundbat-league-enrollment-dev-pg
  port: 5432
  engine: postgres
  version: "16"

# For remote deployments:
remote:
  host: 164.90.xxx.xxx
  ssh_user: deploy
  registry: registry.digitalocean.com/my-registry
```

### 3.2 Database Naming Convention

Databases are named `rundbat_{app_name}_{environment}` to prevent collisions when multiple projects share the same Docker host. Container names follow the same pattern with a `-pg` suffix. This naming is enforced by rundbat and is not configurable.

### 3.3 Application Name

The application name is a primary identifier used in database names, container names, and registry tags. rundbat stores both the name and its source (e.g., "pyproject.toml project.name" or "package.json name field"). This allows drift detection — if the name changes at the source, rundbat can warn the agent.

The `notes` field in `rundbat.yaml` stores free-text guidance for the agent. These notes are returned alongside configuration data when the agent queries an environment, providing context about decisions made during setup.

### 3.4 Secrets Flow

1. rundbat collects credentials during setup (generated or provided by user).
2. rundbat calls `dotconfig load -d {env}` to get the assembled `.env`.
3. rundbat adds credentials to the secrets section of the `.env` file.
4. rundbat calls `dotconfig save` to write back, re-encrypting secrets via SOPS.
5. When starting services, rundbat calls `dotconfig load -d {env}` to decrypt, then injects variables via `docker --env-file` or shell environment inheritance.

---

## 4. Environment Types

| Environment | App Runs | Database | Typical Use |
|---|---|---|---|
| Docker dev | Node on host | Postgres in Docker | Standard dev setup |
| Full Docker dev | Node + Postgres in Docker compose | Docker compose | Closer to production parity |
| Staging | Containers on remote host | Remote Postgres (Docker or managed) | Pre-production testing |
| Production | Containers on remote host | Remote managed Postgres | Live deployment |

All environments use Docker. There is no native Postgres option.

---

## 5. Core Workflow

### 5.1 Phase 1: Discovery

rundbat detects the host environment and reports what is available.

- Host OS (Windows, macOS, Linux, Codespaces)
- Docker status: installed, running, which backend (Docker Desktop, OrbStack, Colima, native)
- dotconfig status: installed, initialized, config directory location
- Node.js version
- Remote CLI tools: doctl, AWS CLI, SSH keys
- Existing rundbat configuration for this project

The output is a capabilities report that drives the interview and setup phases.

**Platform-specific notes:**
- **Codespaces:** Docker is pre-installed. The age encryption key is ephemeral and will be lost on codespace rebuild. rundbat should warn about this and recommend storing the key as a Codespaces secret.
- **Windows:** May require WSL2 and Docker Desktop. Installation may require admin privileges, GUI interaction, and a reboot. rundbat handles as much as possible automatically and returns the specific manual step when it cannot proceed.
- **macOS:** Docker Desktop, OrbStack, or Colima are all acceptable. rundbat can install via Homebrew if brew is available.

### 5.2 Phase 2: Docker Installation

If `docker info` fails, rundbat attempts to install Docker. The model is: do as much as possible automatically, surface manual steps only when unavoidable.

On Linux/Codespaces, rundbat can typically install Docker directly via package manager. On macOS with Homebrew, rundbat can install Docker Desktop or Colima. On Windows, rundbat may need the user to enable WSL2, restart, and run a GUI installer.

rundbat tracks installation progress as a state machine. Each step is either executed by rundbat or returned as instructions for the human. After each manual step, the agent calls back to verify completion before proceeding.

### 5.3 Phase 3: Interview

With Docker confirmed, rundbat collects deployment decisions from the user:

- What environments are needed (dev, staging, production)
- For remote environments: target host, provider, credentials
- For managed databases: connection information
- Application name and where it is defined in the project

The interview is driven by what discovery found. If doctl is authenticated, DigitalOcean options are presented. If AWS CLI is configured, AWS options appear. If neither is present, rundbat asks where the user wants to deploy and guides installation of the relevant CLI tool.

### 5.4 Phase 4: Provisioning

Based on discovery and interview results, rundbat:

1. Saves `rundbat.yaml` to the deployment via dotconfig.
2. Generates credentials (database passwords, etc.).
3. Writes credentials to `.env` files via dotconfig load/edit/save cycle.
4. Starts Docker containers for local databases.
5. Verifies connectivity to all configured services.
6. Reports success or specific failures.

### 5.5 Phase 5: Ongoing Management

After initial setup, the primary interactions are:

- **Get environment config.** Agent calls for a connection string. rundbat loads config, checks liveness, returns the connection info with any notes.
- **Start/stop services.** Agent starts or stops local database containers between sessions.
- **Health check.** Verify that everything is reachable and correctly configured.
- **Add environments.** A project that started with dev adds staging or production later. rundbat runs the interview for the new environment and provisions it.
- **Drift detection.** rundbat checks whether the application name at its source still matches the stored name and warns if it has changed.

---

## 6. Tool Surface

### 6.1 Discovery and Setup

| Tool | Purpose |
|---|---|
| `discover_system` | Detect OS, Docker status, installed tools, existing config |
| `install_docker` | Install Docker or return the manual step needed. Idempotent. |
| `verify_docker` | Confirm `docker info` succeeds |
| `init_project(app_name, app_name_source)` | Initialize rundbat config via dotconfig. Verifies dotconfig is set up, runs `dotconfig init` if needed. Saves initial `rundbat.yaml`. |

### 6.2 Environment Configuration

| Tool | Purpose |
|---|---|
| `create_environment(name, type, ...)` | Create a new environment. Accepts type (local-docker, remote-docker, managed-db) and relevant parameters (host, ssh_user, registry). Saves config via dotconfig. |
| `set_secret(env, key, value)` | Write a secret to the environment's `.env` file via dotconfig load/edit/save. |
| `validate_environment(env)` | Run all checks: config completeness, secret presence, container status, connectivity. Returns pass/fail with details. |
| `get_environment_config(env)` | Load config and secrets via dotconfig. Run a lightweight health check. Return connection info, metadata, and notes. This is the primary day-to-day tool. |
| `check_config_drift` | Compare stored app_name against the source. Warn if mismatched. |

### 6.3 Services

| Tool | Purpose |
|---|---|
| `start_database(env)` | Start the Postgres container for a local environment. If the container doesn't exist, create it from config. If it exists but is stopped, start it. Run health check after start. |
| `stop_database(env)` | Stop the container. |
| `start_app(env)` | Start the Node app with the correct environment variables loaded from dotconfig. |
| `stop_app(env)` | Stop the app. |
| `health_check(env)` | Is the database reachable? Is the app responding? Returns specific status for each service. |

### 6.4 Deployment

| Tool | Purpose |
|---|---|
| `build_container(env)` | Build the Docker image for the app. |
| `push_container(env, registry)` | Push the image to the configured registry. |
| `deploy(env)` | Full deployment sequence: build, push, SSH to host, pull, run. |
| `get_deploy_status(env)` | Query the remote host for what is currently running. |

### 6.5 Knowledge

| Tool | Purpose |
|---|---|
| `get_deploy_skill(topic)` | Return skill files for judgment calls: choosing a deployment target, configuring CI/CD, setting up GitHub Actions, etc. |
| `get_deploy_agent(role)` | Return agent definitions for deployment-related roles, following the CLASI pattern. |

---

## 7. Developer Scenarios

### 7.1 Student on Mac — Local Dev Only

**Discovery:** macOS 14, ARM. OrbStack running, `docker info` succeeds. Node 20 installed. No remote CLI tools. No existing rundbat config.

**Setup:**

```
Agent → rundbat: init_project("my-todo-app", source="package.json name")
  rundbat: Verifies dotconfig is initialized.
           Saves rundbat.yaml to dev via dotconfig.

Agent → rundbat: create_environment("dev", type="local-docker")
  rundbat: Generates Postgres password.
           Saves to .env secrets section via dotconfig.
           Starts container rundbat-my-todo-app-dev-pg on port 5432.
           Verifies connection.
           Returns: postgresql://my-todo-app:****@localhost:5432/rundbat_my-todo-app_dev
```

Student is coding.

### 7.2 Student on Windows — Needs Docker

**Discovery:** Windows 11, x64. Docker not found. WSL2 not enabled. Node installed via nvm-windows.

**Installation:**

```
Agent → rundbat: install_docker()
  rundbat: WSL2 not enabled. Cannot proceed without admin privileges.
           Returns: "User must open PowerShell as Administrator,
           run 'wsl --install', and restart the computer."

  [User does it, comes back]

Agent → rundbat: install_docker()
  rundbat: WSL2 enabled. Docker not found.
           Downloads Docker Desktop installer.
           Returns: "User must run the installer at
           C:\Users\student\Downloads\Docker Desktop Installer.exe"

  [User does it]

Agent → rundbat: verify_docker()
  rundbat: docker info succeeded. Docker Desktop with WSL2 backend. ✓
```

Interview and provisioning proceed as in scenario 7.1.

### 7.3 Student in GitHub Codespaces

**Discovery:** Linux (Ubuntu 22.04). Docker installed and running (Codespaces provides it). dotconfig not installed.

**Setup:**

```
Agent → rundbat: install_prerequisites()
  rundbat: dotconfig not found. Installing via pipx... done.
           dotconfig init... done. Age keypair generated.

           WARNING: Codespaces are ephemeral. The age private key
           will be lost on codespace rebuild. Recommend storing it
           as a GitHub Codespaces secret (SOPS_AGE_KEY).

  [Agent relays warning to user, provides instructions]
```

Database setup proceeds normally. The Codespaces port forwarding means the database is accessible at localhost within the codespace; no special handling needed since the app runs in the same environment.

### 7.4 Team Project — Dev + Production on DigitalOcean

**Discovery:** Ubuntu 22.04. Docker running. doctl installed and authenticated. SSH keys present.

**Setup:**

```
Agent → rundbat: init_project("league-enrollment", source="pyproject.toml project.name")

Agent → rundbat: create_environment("dev", type="local-docker")
  rundbat: [same as 7.1 — local Postgres container, verified connection]

Agent → User: "Where does production deploy?"
User: "DigitalOcean. We have a droplet at 164.90.xxx.xxx
       and a managed database."

Agent → rundbat: create_environment("prod", type="remote-docker",
                  host="164.90.xxx.xxx", ssh_user="deploy")
Agent → rundbat: set_secret("prod", "DATABASE_URL",
                  "postgresql://doadmin:xxx@db-xxx.ondigitalocean.com:25060/defaultdb?sslmode=require")
Agent → rundbat: set_secret("prod", "SSH_KEY_PATH", "~/.ssh/id_ed25519")
  rundbat: Encrypted via dotconfig.
           Verified SSH to 164.90.xxx.xxx. ✓
           Verified database connection. ✓
```

### 7.5 Agent Returns Next Session

The most common interaction. Agent starts a new coding session and needs database access.

```
Agent → rundbat: get_environment_config("dev")
  rundbat: Config loaded. Health check...
           Container rundbat-league-enrollment-dev-pg is not running.

           Starting container... started.
           Connection verified. ✓

           Returns:
           {
             app_name: "league-enrollment",
             environment: "dev",
             database: {
               connection_string: "postgresql://league-enrollment:****@localhost:5432/rundbat_league-enrollment_dev",
               container: "rundbat-league-enrollment-dev-pg",
               port: 5432,
               status: "running"
             },
             notes: ["Application name from pyproject.toml project.name"]
           }
```

One call. Complete answer. Container auto-restarted if it was stopped.

### 7.6 Agent Needs an Additional Database

Mid-project, the agent needs a separate database for integration testing.

```
Agent → rundbat: create_environment("test", type="local-docker")
  rundbat: Port 5432 in use by dev.
           Allocating port 5433.
           Started rundbat-league-enrollment-test-pg on port 5433.
           Connection verified. ✓

           Returns: postgresql://league-enrollment:****@localhost:5433/rundbat_league-enrollment_test
```

Port conflict resolution is automatic. The agent doesn't think about it.

### 7.7 New Team Member Joins

Project has dotconfig set up with dev and prod. A new student clones the repo.

```
Agent → rundbat: get_environment_config("dev")
  rundbat: Cannot decrypt secrets. Age key not available.

           The user needs the project's encryption key from
           an existing team member. Once installed, call again.

  [Student gets key from teammate, installs it]

Agent → rundbat: get_environment_config("dev")
  rundbat: Decryption working. ✓
           No container exists on this machine. Creating
           rundbat-league-enrollment-dev-pg from config...
           Started on port 5432. Health check passed. ✓

           Returns: [connection info]
```

The database is empty (fresh container), but config and credentials are shared through dotconfig. The app runs its migrations on first connect.

### 7.8 Adding Production After Weeks of Dev

Student from scenario 7.1 decides to deploy.

```
Agent → rundbat: discover_system()
  rundbat: doctl not installed. AWS CLI not installed.

Agent → User: "Where do you want to deploy?"
User: "DigitalOcean."

Agent → rundbat: install_prerequisites()
  rundbat: Installing doctl via brew... done.
           doctl needs authentication. User must run:
           doctl auth init

  [User authenticates]

Agent → rundbat: verify_doctl()
  rundbat: doctl authenticated. ✓

  rundbat: Available options with doctl:
           1. Droplet + Postgres in Docker on the droplet
           2. Droplet + DigitalOcean Managed Database
           3. App Platform (managed containers, no SSH)

           Option 3 is simplest. No server management.

  [Agent presents options, user chooses, setup proceeds]
```

### 7.9 Container Lost — Data Gone

Docker was pruned or Docker Desktop was reset.

```
Agent → rundbat: get_environment_config("dev")
  rundbat: Config loaded. Health check...
           Container rundbat-my-todo-app-dev-pg does not exist.
           It was likely removed (docker prune, Docker Desktop reset).

           Creating fresh container from config...
           Started. Health check passed. ✓

           WARNING: This is a new empty database. Previous data
           is not recoverable. The application will need to run
           its migrations.
```

No panic. States what happened. Says what needs to happen next.

### 7.10 App Name Drift

Someone renames the project in package.json.

```
Agent → rundbat: get_environment_config("dev")
  rundbat: WARNING: App name mismatch.
           rundbat.yaml says: my-todo-app
           package.json says: todo-app-v2

           The database is still named rundbat_my-todo-app_dev.
           Recommendation: Update rundbat config to note the change.
           Database name does not need to change — renaming it
           would require downtime and data migration for no
           functional benefit.
```

---

## 8. Stale State Recovery

rundbat assumes things will be out of sync. Every `get_environment_config` call runs a health check and takes corrective action where possible.

| Condition | Action |
|---|---|
| Container stopped | Auto-restart it |
| Container missing | Recreate from config, warn that data is lost |
| Port conflict (another process on the configured port) | Report the conflict, suggest resolution |
| Secrets undecryptable (missing age key) | Report clearly, explain how to get the key |
| dotconfig not initialized | Run `dotconfig init` |
| Docker not running | Attempt to start Docker, or return manual step |
| Remote host unreachable | Report SSH failure with connection details |
| Database unreachable (remote) | Report connection failure, include connection params for debugging |

The goal is that an agent starting a new session calls `get_environment_config`, and either gets back a working connection string or gets back a specific, actionable error — never a mystery failure.

---

## 9. Implementation Phases

### Phase 1: Local Docker Dev

Minimum viable functionality. Assumes Docker is already installed.

- `discover_system`
- `init_project`
- `create_environment` (local-docker type only)
- `set_secret`
- `validate_environment`
- `get_environment_config`
- `start_database` / `stop_database`
- `health_check`
- dotconfig integration for all config read/write
- Port allocation and conflict detection
- Stale state recovery (container restart, recreate)

This is immediately useful. A student or agent can set up a dev database in a few tool calls and get a connection string reliably across sessions.

### Phase 2: Discovery and Docker Installation

- Full OS detection and capabilities report
- Docker installation logic per platform (Linux, macOS with Homebrew, Windows with WSL2)
- Step-by-step state machine for multi-step installations
- Codespaces detection and ephemeral key warnings
- Prerequisite installation (dotconfig, doctl, AWS CLI)

### Phase 3: Remote Environments

- `create_environment` for remote-docker and managed-db types
- SSH connectivity verification
- doctl and AWS CLI integration
- `build_container` / `push_container`
- `deploy` (full pipeline: build, push, SSH, pull, run)
- `get_deploy_status`
- Container registry management

### Phase 4: CI/CD Integration

- GitHub Actions workflow generation
- Automated deploy pipelines
- Deploy key management
- Environment-specific workflow configuration

---

## 10. Knowledge and Agent Definitions

Following the CLASI pattern, rundbat serves skill files and agent definitions alongside its executable tools.

### 10.1 Skill Files

Skill files are returned by `get_deploy_skill(topic)` and provide guidance for decisions that require judgment:

- **choosing-a-deployment-target** — When to use a droplet vs. App Platform vs. a VPS. Cost and complexity tradeoffs.
- **docker-compose-patterns** — Common compose configurations for Node + Postgres. When to use volumes, networks, health checks.
- **ci-cd-setup** — How to set up GitHub Actions for automated deployment. Branch strategies, environment protection rules.
- **secret-rotation** — When and how to rotate database passwords, API keys. How to coordinate rotation across environments.
- **debugging-connections** — Common connection failures and diagnostic steps. Port conflicts, DNS resolution, SSL certificate issues.

### 10.2 Agent Definitions

Agent definitions are returned by `get_deploy_agent(role)` for use in multi-agent workflows:

- **environment-manager** — Responsible for setting up and maintaining deployment environments. Runs the interview, provisions infrastructure, validates health.
- **deploy-operator** — Responsible for executing deployments. Builds containers, pushes to registries, runs the deploy sequence, verifies success.

---

## 11. Open Questions

1. **Docker Compose vs. individual containers.** For local dev with just Postgres, a single `docker run` is simpler than a compose file. At what point does rundbat switch to compose? When the app also runs in Docker? When there are multiple services?

2. **Volume management.** Should rundbat create named Docker volumes for database data so it survives container recreation? This makes data more durable but adds complexity around volume cleanup.

3. **Multiple database engines.** The spec assumes Postgres. Should rundbat support MySQL, SQLite-in-Docker, Redis, or other services? If so, how does the tool surface change?

4. **App Platform and serverless targets.** DigitalOcean App Platform, Railway, Fly.io, and similar platforms have their own deployment models that don't involve SSH. How deep does rundbat go with each provider?

5. **Monorepo support.** If a project has multiple services (API + frontend + worker), does each get its own rundbat config, or does rundbat manage the full service topology?

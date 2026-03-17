---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001 Use Cases

## SUC-001: Discover System Environment
Parent: Spec §5.1

- **Actor**: AI agent
- **Preconditions**: rundbat MCP server is connected
- **Main Flow**:
  1. Agent calls `discover_system`.
  2. rundbat detects host OS, Docker status (installed, running, backend),
     dotconfig status (installed, initialized, config directory), Node.js
     version, and existing rundbat configuration.
  3. rundbat returns a structured capabilities report.
- **Postconditions**: Agent has a complete picture of the host environment
- **Acceptance Criteria**:
  - [ ] Returns OS name and architecture
  - [ ] Returns Docker installed/running status and backend name
  - [ ] Returns dotconfig installed/initialized status
  - [ ] Returns Node.js version if present
  - [ ] Returns existing rundbat config if present

## SUC-002: Initialize Project
Parent: Spec §6.1

- **Actor**: AI agent
- **Preconditions**: dotconfig is installed and initialized, Docker is running
- **Main Flow**:
  1. Agent calls `init_project(app_name, app_name_source)`.
  2. rundbat verifies dotconfig is set up (runs `dotconfig init` if needed).
  3. rundbat saves initial `rundbat.yaml` via dotconfig with app_name,
     app_name_source, and empty notes.
  4. Returns confirmation with the saved config.
- **Postconditions**: `rundbat.yaml` exists in dotconfig for the project
- **Acceptance Criteria**:
  - [ ] Creates `rundbat.yaml` via dotconfig save
  - [ ] Stores app_name and app_name_source
  - [ ] Idempotent — calling again with same args does not error
  - [ ] Errors clearly if dotconfig is not available

## SUC-003: Create Local Dev Environment
Parent: Spec §7.1

- **Actor**: AI agent
- **Preconditions**: Project is initialized via `init_project`
- **Main Flow**:
  1. Agent calls `create_environment("dev", type="local-docker")`.
  2. rundbat generates a secure Postgres password.
  3. rundbat determines an available port (default 5432, auto-increment
     if occupied).
  4. rundbat saves database config to `rundbat.yaml` via dotconfig.
  5. rundbat saves `DATABASE_URL` to secrets via dotconfig load/edit/save.
  6. rundbat starts a Postgres container with the naming convention
     `rundbat-{app_name}-{env}-pg`.
  7. rundbat verifies the database is reachable.
  8. Returns the connection string and container details.
- **Postconditions**: Postgres container is running, config and secrets are stored
- **Acceptance Criteria**:
  - [ ] Container is created and running with correct name
  - [ ] Database name follows `rundbat_{app_name}_{env}` convention
  - [ ] Password is randomly generated and stored in dotconfig secrets
  - [ ] Port 5432 is used if available, next available port otherwise
  - [ ] Connection string is verified before returning
  - [ ] Second environment gets a different port automatically (Spec §7.6)

## SUC-004: Retrieve Environment Config (Happy Path)
Parent: Spec §7.5

- **Actor**: AI agent (new session)
- **Preconditions**: Environment was previously created
- **Main Flow**:
  1. Agent calls `get_environment_config("dev")`.
  2. rundbat loads config from dotconfig.
  3. rundbat checks container status.
  4. If container is stopped, rundbat auto-restarts it.
  5. rundbat verifies database connectivity.
  6. Returns connection string, container status, and notes.
- **Postconditions**: Agent has a working connection string
- **Acceptance Criteria**:
  - [ ] Returns connection string, container name, port, status
  - [ ] Auto-restarts stopped containers
  - [ ] Includes notes from rundbat.yaml
  - [ ] Single tool call — no multi-step interaction needed

## SUC-005: Recover from Missing Container
Parent: Spec §7.9

- **Actor**: AI agent
- **Preconditions**: Container was removed (docker prune, Docker Desktop reset)
- **Main Flow**:
  1. Agent calls `get_environment_config("dev")`.
  2. rundbat loads config, finds container does not exist.
  3. rundbat recreates the container from stored config.
  4. rundbat verifies connectivity.
  5. Returns connection info with a warning that this is a fresh database
     and previous data is not recoverable.
- **Postconditions**: New container is running, agent is warned about data loss
- **Acceptance Criteria**:
  - [ ] Container is recreated from stored config (same name, port, credentials)
  - [ ] Warning message indicates data loss
  - [ ] Recommends running migrations

## SUC-006: Detect App Name Drift
Parent: Spec §7.10

- **Actor**: AI agent
- **Preconditions**: Project is initialized, app name source file exists
- **Main Flow**:
  1. Agent calls `check_config_drift` or `get_environment_config`.
  2. rundbat reads the app_name_source file and compares to stored app_name.
  3. If mismatched, returns a warning with both values and a recommendation
     to update rundbat config (not rename the database).
- **Postconditions**: Agent is aware of the drift
- **Acceptance Criteria**:
  - [ ] Detects when app name at source differs from stored name
  - [ ] Returns both values in the warning
  - [ ] Recommends updating config, not renaming the database

## SUC-007: Manage Secret
Parent: Spec §3.4

- **Actor**: AI agent
- **Preconditions**: Environment exists
- **Main Flow**:
  1. Agent calls `set_secret("dev", "SESSION_SECRET", "abc123")`.
  2. rundbat calls `dotconfig load -d dev` to get the assembled `.env`.
  3. rundbat adds or updates the key in the secrets section.
  4. rundbat calls `dotconfig save` to write back with SOPS encryption.
  5. Returns confirmation.
- **Postconditions**: Secret is stored encrypted in dotconfig
- **Acceptance Criteria**:
  - [ ] Secret is written to the correct environment's secrets section
  - [ ] dotconfig load/edit/save cycle is used (never direct file writes)
  - [ ] Existing secrets are preserved when adding new ones

## SUC-008: Install Project Integration Files
Parent: Spec §2.2

- **Actor**: AI agent (via `init_project`)
- **Preconditions**: Target project directory exists
- **Main Flow**:
  1. `init_project` calls the Project Installer after saving `rundbat.yaml`.
  2. Installer reads `.mcp.json` (or creates if missing), adds/updates the
     `rundbat` entry in `mcpServers`, writes back — preserving all other
     entries (e.g., CLASI).
  3. Installer writes `.claude/rules/rundbat.md` with guidance telling the
     model to use rundbat tools for database, deployment, and environment
     tasks.
  4. Installer reads `.claude/settings.json` (or creates if missing), merges
     a `UserPromptSubmit` hook that reminds the model: "If this task involves
     databases, deployment, or environment setup, use the rundbat MCP server."
     Preserves existing hooks.
  5. Returns confirmation listing what was installed/updated.
- **Postconditions**: Target project is configured to use rundbat, model
  is reminded about rundbat on every prompt
- **Acceptance Criteria**:
  - [ ] `.mcp.json` contains rundbat server entry alongside existing entries
  - [ ] `.claude/rules/rundbat.md` exists with deployment guidance
  - [ ] `.claude/settings.json` contains UserPromptSubmit hook for rundbat
  - [ ] Existing `.mcp.json` entries are not removed or modified
  - [ ] Existing hooks in settings.json are not removed or modified
  - [ ] Idempotent — running again does not duplicate entries

---
status: done
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 002 Use Cases

## SUC-001: Docker Database Lifecycle
Parent: Spec §7.1, §7.5, §7.9

- **Actor**: Test suite
- **Preconditions**: Docker is installed and running
- **Main Flow**:
  1. Create a Postgres container with a test-specific name
  2. Verify it is running via `docker inspect`
  3. Verify pg_isready succeeds via `docker exec`
  4. Stop the container, verify it is stopped
  5. Restart it, verify pg_isready again
  6. Remove the container externally, call ensure_running
  7. Verify container is recreated with data-loss warning
  8. Clean up the container
- **Postconditions**: All container lifecycle states are verified
- **Acceptance Criteria**:
  - [ ] Container created with correct name, port, credentials
  - [ ] pg_isready confirms Postgres is accepting connections
  - [ ] Stopped container restarts successfully
  - [ ] Missing container is recreated with warning
  - [ ] Port allocation avoids conflicts
  - [ ] All test containers cleaned up after test

## SUC-002: Config Service dotconfig Integration
Parent: Spec §3.1, §3.4

- **Actor**: Test suite
- **Preconditions**: dotconfig is installed
- **Main Flow**:
  1. Create a temp project directory
  2. Initialize dotconfig in it
  3. Save a rundbat.yaml via Config Service
  4. Load it back and verify contents match
  5. Save a secret via the .env round-trip
  6. Load the .env and verify the secret is present
  7. Verify app name drift detection works with a real file
- **Postconditions**: Config round-trip through dotconfig is verified
- **Acceptance Criteria**:
  - [ ] rundbat.yaml round-trip preserves all fields
  - [ ] Secret is written to the correct .env section
  - [ ] Drift detection reads real source files correctly
  - [ ] Temp directories cleaned up

## SUC-003: CLI End-to-End
Parent: Spec §2.2

- **Actor**: Human user (simulated via subprocess)
- **Preconditions**: rundbat is installed, dotconfig is available
- **Main Flow**:
  1. Create a temp project directory with a package.json
  2. Run `rundbat init` in it
  3. Verify .mcp.json, .claude/rules/rundbat.md, .claude/settings.json
     are created with correct content
  4. Run `rundbat env list` and verify output
  5. (If Docker available) Create an environment via MCP, then run
     `rundbat env connstr dev` and verify connection string output
- **Postconditions**: CLI commands produce correct output
- **Acceptance Criteria**:
  - [ ] `rundbat init` creates all expected files
  - [ ] `rundbat init` detects app name from package.json
  - [ ] `rundbat env list` shows configured environments
  - [ ] `rundbat env connstr` returns a connection string
  - [ ] Existing .mcp.json entries are preserved

## SUC-004: MCP Tool Surface Verification
Parent: Spec §6

- **Actor**: Test suite (MCP client)
- **Preconditions**: rundbat package is installed
- **Main Flow**:
  1. Import the FastMCP server instance
  2. List all registered tools
  3. Verify all 11 expected tools are present
  4. Verify tool parameter schemas match expectations
- **Postconditions**: MCP tool surface is verified
- **Acceptance Criteria**:
  - [ ] All 11 tools from Spec §6 are registered
  - [ ] Tool names match the spec
  - [ ] Tools have correct parameter types

## SUC-005: Error Paths and Degraded States
Parent: Spec §8

- **Actor**: Test suite
- **Preconditions**: Varies per scenario (some need Docker, some don't)
- **Main Flow**:
  Each scenario tests a different failure mode:

  **Docker not available:**
  1. Simulate Docker not installed (patch PATH to exclude docker)
  2. Call discover_system — verify it reports Docker missing clearly
  3. Call create_environment — verify it fails with actionable message
  4. Verify no traceback, just structured error

  **Docker installed but not running:**
  1. Mock `docker info` returning non-zero (or use real Docker if stopped)
  2. Call discover_system — verify "installed but not running"
  3. Call start_database — verify clear error

  **dotconfig not initialized:**
  1. Create a temp dir with no config/
  2. Call init_project — verify it runs dotconfig init automatically
  3. Call load_config without init — verify clear error message

  **SOPS/age keys missing:**
  1. Initialize dotconfig but remove the age key
  2. Try to load secrets — verify graceful degradation
  3. Verify public config still loads

  **Port conflict:**
  1. Bind a socket to port 5432
  2. Call create_environment — verify it auto-allocates 5433
  3. Verify the allocated port is stored in config

  **Malformed config:**
  1. Write invalid YAML to rundbat.yaml location
  2. Call load_config — verify structured error, not YAML traceback
  3. Write config missing required fields (no app_name)
  4. Call get_environment_config — verify clear "not configured" message

  **Container exists but unhealthy:**
  1. Create a container that won't accept connections (wrong password,
     or stop Postgres inside the container)
  2. Call health_check — verify clear failure message with details
  3. Verify timeout doesn't hang forever

  **App name source file missing:**
  1. Configure app_name_source pointing to nonexistent file
  2. Call check_config_drift — verify it reports file not found
  3. Verify it doesn't crash

- **Postconditions**: Every error scenario produces a clear, actionable
  message — never a raw traceback or mystery failure
- **Acceptance Criteria**:
  - [ ] Docker-not-installed returns structured error with install guidance
  - [ ] Docker-not-running returns "installed but not running" status
  - [ ] dotconfig-not-initialized triggers automatic init or clear error
  - [ ] SOPS keys missing degrades gracefully (public config still works)
  - [ ] Port conflict auto-allocates next available port
  - [ ] Malformed config returns structured error, not traceback
  - [ ] Unhealthy container times out with clear message
  - [ ] Missing source file returns "file not found", not crash
  - [ ] All error returns are structured dicts, not exceptions to the caller

---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001 Use Cases

## SUC-001: Install rundbat integration into a project
Parent: UC-01 (Initialize project with deployment interview)

- **Actor**: Developer
- **Preconditions**: Target project exists, rundbat is installed via pipx
- **Main Flow**:
  1. Developer runs `rundbat install` in the project root
  2. rundbat writes skill files to `.claude/skills/rundbat/`
  3. rundbat writes agent definition to `.claude/agents/deployment-expert.md`
  4. rundbat writes rules to `.claude/rules/rundbat.md`
  5. rundbat writes manifest to `.claude/.rundbat-manifest.json`
  6. rundbat reports what was installed
- **Postconditions**: Claude can see rundbat skills, agent, and rules
- **Acceptance Criteria**:
  - [ ] `rundbat install` creates all expected files
  - [ ] Manifest lists every installed file with checksum
  - [ ] Running `rundbat install` again is idempotent (updates files, no duplicates)
  - [ ] `.claude/` directory is created if it doesn't exist

## SUC-002: Uninstall rundbat integration from a project

- **Actor**: Developer
- **Preconditions**: rundbat was previously installed in the project
- **Main Flow**:
  1. Developer runs `rundbat uninstall`
  2. rundbat reads manifest from `.claude/.rundbat-manifest.json`
  3. rundbat deletes each file listed in the manifest
  4. rundbat deletes the manifest itself
  5. rundbat reports what was removed
- **Postconditions**: All rundbat integration files are removed
- **Acceptance Criteria**:
  - [ ] `rundbat uninstall` removes all files from manifest
  - [ ] Empty directories are not cleaned up (other tools may use `.claude/`)
  - [ ] Running `uninstall` with no manifest prints a warning and exits cleanly

## SUC-003: Use CLI subcommands instead of MCP tools
Parent: UC-02 (Quick dev database), UC-03 (Local Docker compose)

- **Actor**: Developer or Claude agent (via Bash)
- **Preconditions**: Project initialized, rundbat installed
- **Main Flow**:
  1. Agent or developer runs CLI commands directly:
     - `rundbat discover` — detect system environment
     - `rundbat create-env dev` — provision a dev environment
     - `rundbat get-config dev` — load config, auto-restart containers, return connection string
     - `rundbat start dev` / `rundbat stop dev` — container lifecycle
     - `rundbat health dev` — check database connectivity
     - `rundbat validate dev` — full environment validation
     - `rundbat set-secret dev DB_PASSWORD=xxx` — store a secret
     - `rundbat check-drift dev` — detect app name changes
  2. All commands support `--json` for machine-parseable output
  3. Human-readable output is the default (colored, formatted)
- **Postconditions**: Same outcomes as the old MCP tools
- **Acceptance Criteria**:
  - [ ] Each MCP tool has a corresponding CLI subcommand
  - [ ] `--json` flag produces valid JSON on stdout
  - [ ] Exit codes: 0 = success, 1 = error, 2 = usage error
  - [ ] No MCP server code remains in the codebase

## SUC-004: Claude uses deployment-expert agent for deployment tasks

- **Actor**: Claude (via deployment-expert agent)
- **Preconditions**: rundbat installed in project, skills/agent files present
- **Main Flow**:
  1. User asks a deployment question ("set up Docker", "I need a database")
  2. Claude matches the request to the deployment-expert agent
  3. Agent reads config via `dotconfig load -d {env} --json --flat -S`
  4. Agent follows the appropriate skill instructions
  5. Agent executes rundbat CLI commands as needed
  6. Agent reports results to the user
- **Postconditions**: Deployment task completed per skill instructions
- **Acceptance Criteria**:
  - [ ] Agent definition exists at `.claude/agents/deployment-expert.md`
  - [ ] Skills exist: `init-docker`, `dev-database`, `diagnose`, `manage-secrets`
  - [ ] Rules file exists at `.claude/rules/rundbat.md`
  - [ ] Skills reference `dotconfig load --json` for config access
  - [ ] Skills reference `rundbat` CLI commands (not MCP tools)

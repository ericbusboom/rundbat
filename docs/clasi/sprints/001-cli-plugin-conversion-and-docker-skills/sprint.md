---
id: "001"
title: "CLI Plugin Conversion and Docker Skills"
status: planning
branch: sprint/001-cli-plugin-conversion-and-docker-skills
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001: CLI Plugin Conversion and Docker Skills

## Goals

Convert rundbat from an MCP server to a CLI-first tool with Claude
integration via native `.claude/` directories. Drop the MCP transport,
expand the CLI surface, update the installer, and write the initial
agent and skill files.

This sprint covers Phase A (CLI conversion) and Phase B (agent/skills
content) from the `convert-mcp-to-cli-plugin` TODO.

## Problem

The MCP server transport adds overhead without meaningful benefit —
Claude can call the CLI directly via Bash. The current installer
targets `.mcp.json` and hooks, which are the wrong integration points
for a CLI-first tool. There are no agent or skill definitions to guide
Claude on deployment tasks.

## Solution

1. Remove the MCP server (`server.py`, FastMCP dependency)
2. Expand CLI with subcommands that mirror the old MCP tools
3. Replace `init` with `install`/`uninstall` that write `.claude/`
   integration files (skills, agents, rules) with manifest tracking
4. Write the `deployment-expert` agent definition
5. Write skill files for key deployment workflows
6. Write rules for when to invoke skills vs CLI directly

## Success Criteria

- `rundbat` CLI provides all capabilities previously in the MCP server
- `rundbat install` writes `.claude/` files; `rundbat uninstall` removes them
- No MCP server code remains; `mcp[cli]` removed from dependencies
- `deployment-expert` agent definition exists and is installed
- Core skill files exist: `init-docker`, `dev-database`, `diagnose`, `manage-secrets`
- Rules file teaches Claude when to use skills vs CLI
- All existing tests pass (adapted for CLI); new tests for CLI subcommands
- `pipx install -e .` workflow unchanged

## Scope

### In Scope

- Remove MCP server (server.py, mcp dependency, cmd_mcp CLI subcommand)
- CLI subcommands: `discover`, `create-env`, `get-config`, `start`, `stop`,
  `health`, `validate`, `set-secret`, `check-drift` (all with `--json` output)
- `install`/`uninstall` commands with manifest tracking
- Update installer.py: target `.claude/skills/`, `.claude/agents/`,
  `.claude/rules/`; remove `.mcp.json` and hooks writing
- `deployment-expert` agent definition
- Skill files: `init-docker`, `dev-database`, `diagnose`, `manage-secrets`
- Rules file for rundbat
- Test updates: remove `test_server.py`, update installer tests, add CLI tests

### Out of Scope

- Docker directory generation (Phase C — next sprint)
- `generate-dockerfile`, `add-postgres`, `add-mongo`, `add-redis` skills
- Remote deployment execution
- Justfile generation
- Caddy label generation
- Database dump/restore/migration recipes

## Test Strategy

- **Unit tests**: Mock Docker and dotconfig subprocess calls as before.
  Test each CLI subcommand produces correct output (`--json` mode).
- **CLI tests**: Use `subprocess.run` to test all new subcommands.
- **Installer tests**: Verify `install` creates correct `.claude/` files
  and manifest; `uninstall` removes them cleanly.
- **System tests**: Existing Docker integration tests adapted for CLI
  invocation instead of MCP tool calls.

## Architecture Notes

- CLI stays on argparse (not Click) — the existing CLI uses argparse and
  there's no reason to switch. Tests use `subprocess.run` instead of
  Click's `CliRunner`.
- CLI entry point remains `rundbat` via pyproject.toml
- Service layer (config.py, database.py, discovery.py, environment.py)
  is unchanged — CLI calls services directly instead of MCP server
- If `rundbat mcp` is invoked after server.py is removed, print a
  deprecation message directing users to `rundbat install`
- Skills are markdown files installed to target project's `.claude/skills/rundbat/`
- Agent definition installed to `.claude/agents/deployment-expert.md`
- Rules installed to `.claude/rules/rundbat.md`
- Manifest file (`.claude/.rundbat-manifest.json`) tracks installed files
  for clean uninstall

## GitHub Issues

(None yet.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Remove MCP server and FastMCP dependency | — | 1 |
| 002 | Expand CLI with subcommands and --json output | 001 | 1 |
| 003 | Install/uninstall commands with manifest tracking | 001 | 1 |
| 004 | Write deployment-expert agent and skill files | — | 2 |
| 005 | Update tests for CLI-first architecture | 001, 002, 003 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).

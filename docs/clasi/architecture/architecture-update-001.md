---
sprint: "001"
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update -- Sprint 001: CLI Plugin Conversion and Docker Skills

## What Changed

### Removed
- `server.py` — MCP server (FastMCP, tool decorators, stdio transport)
- `mcp[cli]` dependency from pyproject.toml
- `cmd_mcp` CLI subcommand
- `.mcp.json` writing in installer
- Settings hooks writing in installer

### Modified
- `cli.py` — expanded with subcommands: `discover`, `create-env`, `get-config`,
  `start`, `stop`, `health`, `validate`, `set-secret`, `check-drift`, `install`,
  `uninstall`. All subcommands support `--json` output. Stays on argparse
  (no Click migration). `rundbat mcp` kept as deprecation shim.
- `installer.py` — rewritten to target `.claude/` directories instead of
  `.mcp.json`. Uses manifest tracking for clean install/uninstall.

### Added
- Skill files (bundled in package, installed to target project):
  - `skills/init-docker.md` — scaffold `docker/` directory
  - `skills/dev-database.md` — quick `docker run` for local dev
  - `skills/diagnose.md` — read state and report issues
  - `skills/manage-secrets.md` — dotconfig secret management
- Agent definition: `agents/deployment-expert.md`
- Rules file: `rules/rundbat.md`
- Manifest: `.claude/.rundbat-manifest.json`

## Why

The MCP transport adds overhead without meaningful benefit. Claude can
call the CLI directly via Bash, which is simpler, more debuggable, and
doesn't require MCP server configuration. Native `.claude/` directories
(skills, agents, rules) are the standard Claude Code integration mechanism.

Driven by: `convert-mcp-to-cli-plugin` TODO and `deployment-use-cases` TODO.

## Architecture After This Sprint

```
Agent (Claude)
  ├── reads .claude/agents/deployment-expert.md
  ├── reads .claude/skills/rundbat/*.md
  ├── reads .claude/rules/rundbat.md
  │
  ├── calls: rundbat <subcommand> [--json]
  │     └── service layer (config.py, database.py, discovery.py, environment.py)
  │           ├── subprocess → docker CLI
  │           └── subprocess → dotconfig CLI
  │
  └── calls: dotconfig load -d {env} --json --flat -S
        └── reads config/{env}/*.env (decrypts secrets via SOPS)
```

### Component inventory

| Component | File | Role |
|-----------|------|------|
| CLI | `cli.py` | Click-based entry point, all subcommands |
| Config service | `config.py` | dotconfig subprocess wrapper |
| Database service | `database.py` | Docker container lifecycle |
| Discovery service | `discovery.py` | OS/Docker/dotconfig detection |
| Environment service | `environment.py` | Orchestrates config + database |
| Installer | `installer.py` | Install/uninstall `.claude/` files |
| Skills (bundled) | `skills/*.md` | Deployment workflow instructions |
| Agent (bundled) | `agents/*.md` | Deployment expert agent definition |
| Rules (bundled) | `rules/*.md` | When to invoke skills vs CLI |

### Install flow

```
rundbat install
  → reads bundled skill/agent/rule files from package
  → writes to target project:
      .claude/skills/rundbat/init-docker.md
      .claude/skills/rundbat/dev-database.md
      .claude/skills/rundbat/diagnose.md
      .claude/skills/rundbat/manage-secrets.md
      .claude/agents/deployment-expert.md
      .claude/rules/rundbat.md
  → writes manifest:
      .claude/.rundbat-manifest.json
```

## Impact on Existing Components

- **config.py, database.py, discovery.py, environment.py**: No changes.
  These services are called by CLI subcommands instead of MCP tool handlers.
  All function signatures remain the same.
- **Tests**: `test_server.py` deleted. `test_installer.py` rewritten for
  new targets. New CLI tests added via Click's `CliRunner`.

## Migration Concerns

- Projects using the old `.mcp.json` integration will need to run
  `rundbat install` to switch to `.claude/` integration.
- The old `rundbat init` command is replaced by `rundbat install`.
  `init` could be kept as an alias or removed with a deprecation message.
- No data migration needed — `config/` directory and `rundbat.yaml` are
  unchanged.

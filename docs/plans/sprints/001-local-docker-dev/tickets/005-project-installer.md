---
id: "005"
title: "Project Installer"
status: todo
use-cases:
  - SUC-008
depends-on:
  - "001"
github-issue: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Project Installer

## Description

Implement the Project Installer — installs rundbat integration files into
a target project so that AI agents automatically know about and use
rundbat. Called by `init_project` (ticket 003) after saving rundbat.yaml.

Installs three things, all via read-merge-write (never overwrite):

1. **`.mcp.json`** — Adds `rundbat` entry to `mcpServers`. Reads existing
   file, parses JSON, adds/updates the rundbat key, writes back. Creates
   file if missing. Preserves all other server entries.

2. **`.claude/rules/rundbat.md`** — Writes a rule file telling the model:
   "If you need a database, connection string, or deployment environment,
   use the rundbat MCP tools." Overwrites if exists (rundbat owns this file).

3. **`.claude/settings.json`** hooks — Reads existing settings, merges a
   `UserPromptSubmit` hook that reminds the model about rundbat for
   deployment tasks. Preserves existing hooks (e.g., CLASI's hook).
   Does not duplicate if the rundbat hook already exists.

## Acceptance Criteria

- [ ] `src/rundbat/installer.py` module
- [ ] `install_mcp_config(project_dir)` — merges rundbat into `.mcp.json`
  - [ ] Preserves existing `mcpServers` entries
  - [ ] Creates `.mcp.json` if it doesn't exist
  - [ ] Updates rundbat entry if it already exists (idempotent)
- [ ] `install_rules(project_dir)` — writes `.claude/rules/rundbat.md`
  - [ ] Creates `.claude/rules/` directory if needed
  - [ ] Rule content tells model to use rundbat for deployment tasks
- [ ] `install_hooks(project_dir)` — merges hook into `.claude/settings.json`
  - [ ] Preserves existing hooks array entries
  - [ ] Creates `.claude/settings.json` if it doesn't exist
  - [ ] Does not duplicate the rundbat hook on repeated runs
  - [ ] Hook echoes: "If this task involves databases, deployment, or
        environment setup, use the rundbat MCP server."
- [ ] `install_all(project_dir)` — calls all three, returns summary
- [ ] Idempotent — running twice produces the same result as running once

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: `tests/test_installer.py`
  - Test merge into existing `.mcp.json` with other servers
  - Test create `.mcp.json` from scratch
  - Test merge hook into existing settings with other hooks
  - Test idempotency (run twice, check no duplicates)
  - Test rule file creation
  - All tests use a temp directory (no Docker needed)
- **Verification command**: `uv run pytest`

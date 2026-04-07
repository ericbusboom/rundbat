---
title: Remove stale MCP server references from project files
priority: high
created: 2026-04-07
status: in-progress
sprint: '003'
tickets:
- 003-001
---

# Remove stale MCP server references

Sprint 001 removed the MCP server but left stale references in active
files that agents read. These cause agents to think there's still an
MCP server.

## Files to update

1. **CLAUDE.md** — says "rundbat is an MCP server", references MCP tools
2. **`.claude/settings.json`** — hook says "use the rundbat MCP server"
3. **`.claude/rules/project-overview.md`** — says "MCP Server" throughout
4. **`.mcp.json`** — still has rundbat MCP server entry (remove it)
5. **`docs/rundbat-spec.md`** — spec describes MCP architecture
6. **`.github/copilot/instructions/project-overview.md`** — says "MCP Server"

Archived docs (docs/clasi/sprints/done/, docs/clasi/todo/done/) are
historical and should NOT be changed.

## What to replace with

- "MCP server" → "CLI tool"
- "MCP tools" → "CLI commands"
- "rundbat mcp" → "rundbat --help"
- MCP tool names → CLI equivalents (discover_system → rundbat discover, etc.)
- Remove rundbat entry from .mcp.json
- Update hook message to reference CLI

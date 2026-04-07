---
id: "003"
title: "Remove Stale MCP References"
status: planning
branch: sprint/003-remove-stale-mcp-references
use-cases: []
---

# Sprint 003: Remove Stale MCP References

## Goals

Remove all stale references to "MCP server" and "MCP tools" from active
project files. Agents currently think there's an MCP server because
CLAUDE.md, settings.json, rules, and .mcp.json still reference it.

## Problem

Sprint 001 removed the MCP server code but didn't update all the
documentation and config files that reference it.

## Solution

Find-and-replace across active files. Historical/archived docs are left alone.

## Success Criteria

- No active file references "rundbat MCP server" or "MCP tools"
- `.mcp.json` no longer has a rundbat entry
- Hook message references CLI instead of MCP
- `grep -r "MCP server" --include="*.md" .claude/ CLAUDE.md` returns nothing rundbat-related

## Scope

### In Scope
- CLAUDE.md, .claude/settings.json, .claude/rules/project-overview.md
- .mcp.json, docs/rundbat-spec.md, .github/copilot/instructions/

### Out of Scope
- Archived sprint docs (docs/clasi/sprints/done/)
- Archived TODOs (docs/clasi/todo/done/)
- CLASI MCP references (those are correct — CLASI is still an MCP server)

## Test Strategy
- Grep for "MCP server" in active files after changes
- Existing tests pass

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Update all active files to reference CLI instead of MCP | — | 1 |

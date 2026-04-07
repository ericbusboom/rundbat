---
id: '003'
title: Install/uninstall commands with manifest tracking
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: ''
---

# Install/uninstall commands with manifest tracking

## Description

Replace the old installer (which wrote `.mcp.json`, hooks, rules) with
`rundbat install` / `rundbat uninstall` that manage `.claude/` integration
files with manifest tracking.

**`rundbat install`:**
1. Bundles skill, agent, and rule markdown files in the rundbat package
   (under `src/rundbat/skills/`, `src/rundbat/agents/`, `src/rundbat/rules/`)
2. Copies them to the target project:
   - `.claude/skills/rundbat/*.md`
   - `.claude/agents/deployment-expert.md`
   - `.claude/rules/rundbat.md`
3. Writes manifest: `.claude/.rundbat-manifest.json` listing every
   installed file with its checksum
4. Idempotent — re-running updates files and manifest

**`rundbat uninstall`:**
1. Reads manifest
2. Deletes each listed file
3. Deletes manifest
4. Does NOT remove empty directories (other tools may use `.claude/`)

Rewrite `installer.py` to support the new targets. Remove `.mcp.json`
writing, hooks writing, and CLAUDE.md section writing.

The `rundbat init` command should call `install` as part of its flow
(replacing the old MCP/hooks install steps).

## Acceptance Criteria

- [ ] `rundbat install` creates all `.claude/` files
- [ ] Manifest lists every installed file with checksum
- [ ] `rundbat install` is idempotent (updates, no duplicates)
- [ ] `rundbat uninstall` removes all files listed in manifest
- [ ] `rundbat uninstall` with no manifest prints warning, exits cleanly
- [ ] Old installer code (`.mcp.json`, hooks, CLAUDE.md) removed
- [ ] `rundbat init` calls the new install flow
- [ ] Bundled content files exist in the package (`src/rundbat/skills/` etc.)

## Testing

- **Existing tests to run**: `pytest tests/unit/test_installer.py` (will need updates)
- **New tests to write**: Install/uninstall in temp directory, verify
  files created/removed, manifest contents, idempotency
- **Verification command**: `rundbat install && cat .claude/.rundbat-manifest.json`

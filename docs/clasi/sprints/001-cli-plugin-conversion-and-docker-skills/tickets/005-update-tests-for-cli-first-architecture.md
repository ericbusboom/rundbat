---
id: "005"
title: Update tests for CLI-first architecture
status: todo
use-cases: [SUC-003]
depends-on: ["001", "002", "003"]
github-issue: ""
todo: ""
---

# Update tests for CLI-first architecture

## Description

Update the test suite for the CLI-first architecture:

1. **Delete** `test_server.py` (MCP server tests — server.py is gone)
2. **Rewrite** `test_installer.py` for new install/uninstall targets
3. **Add** CLI subcommand tests for all new subcommands
4. **Verify** existing unit tests still pass (service layer unchanged)
5. **Update** system tests that called MCP tools to use CLI instead

CLI tests should use `subprocess.run` to invoke `rundbat <subcommand>`
and verify:
- Exit code
- `--json` produces valid JSON
- Human-readable output for default mode
- Error cases produce exit code 1 with error message

## Acceptance Criteria

- [ ] `test_server.py` deleted
- [ ] `test_installer.py` rewritten for `.claude/` targets
- [ ] CLI tests exist for: `discover`, `create-env`, `get-config`,
      `start`, `stop`, `health`, `validate`, `set-secret`, `check-drift`
- [ ] CLI tests verify `--json` output is valid JSON
- [ ] CLI tests verify error exit codes
- [ ] Install/uninstall tests verify manifest tracking
- [ ] `pytest tests/unit/` passes with no failures
- [ ] `pytest tests/` passes (unit + system, skipping Docker-dependent if needed)

## Testing

- **Existing tests to run**: `pytest tests/` (full suite)
- **New tests to write**: This ticket IS the test updates
- **Verification command**: `pytest tests/ -v`

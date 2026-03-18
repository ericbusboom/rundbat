---
id: "002"
title: "Integration and System Testing"
status: done
branch: sprint/002-integration-and-system-testing
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 002: Integration and System Testing

## Goals

Add real integration tests that exercise rundbat against live Docker and
dotconfig, system tests that verify the CLI and MCP tool surface
end-to-end, **and error-path tests that verify rundbat degrades
gracefully** when prerequisites are missing, misconfigured, or in
unexpected states. Sprint 001 built all the modules with mocked unit
tests — this sprint proves they actually work and fail correctly.

## Problem

All 67 existing tests use mocked subprocess calls. We have zero
confidence that:

1. The actual Docker and dotconfig integrations work correctly.
2. The CLI commands work for real users.
3. The MCP tool surface is correctly wired.
4. **Error paths produce clear, actionable messages** when Docker isn't
   running, dotconfig isn't initialized, SOPS keys are missing, ports
   are taken, containers disappear, or config is malformed.

The spec (§8 Stale State Recovery) specifically promises that rundbat
will never produce a "mystery failure" — every error should tell the
user what happened and what to do next. We need tests to enforce that.

## Solution

Write four layers of new tests:

1. **Happy-path integration tests** (tests/system/) that call service
   functions with real Docker and dotconfig — create containers, verify
   health, load/save config, round-trip secrets.
2. **Error-path and degraded-state tests** (tests/system/) that verify
   graceful behavior when:
   - Docker is not running or not installed
   - dotconfig is not initialized
   - SOPS/age keys are missing (secrets undecryptable)
   - A port is already occupied by another process
   - A container exists but Postgres inside it won't accept connections
   - Config files are malformed, incomplete, or missing fields
   - App name source file is missing or unparseable
3. **CLI tests** (tests/system/) that run `rundbat init`, `rundbat env
   list`, and `rundbat env connstr` as subprocesses against real temp
   project directories.
4. **MCP tool surface tests** (tests/system/) that verify all expected
   tools are registered with correct parameters.

All Docker-dependent tests are marked `requires_docker` and all
dotconfig-dependent tests are marked `requires_dotconfig` so they can be
skipped in environments without those tools. Error-path tests that
*simulate* missing tools (by patching PATH or mocking) do not need these
markers.

## Success Criteria

- Happy-path integration tests prove Database Service creates, starts,
  stops, and recreates Postgres containers with verified pg_isready
- Happy-path integration tests prove Config Service round-trips
  rundbat.yaml and secrets through dotconfig
- **Error-path tests prove every stale-state scenario from Spec §8
  produces a clear, actionable error message — not a traceback**
- **Error-path tests prove Docker-not-running, dotconfig-not-initialized,
  and SOPS-keys-missing all degrade gracefully**
- CLI tests prove `rundbat init` sets up a project from scratch
- CLI tests prove `rundbat env list` and `rundbat env connstr` work
- System tests prove the MCP server registers all expected tools
- Any bugs found during testing are fixed in this sprint
- All tests (old and new) pass

## Scope

### In Scope

- Happy-path integration tests for Database Service (real Docker)
- Happy-path integration tests for Config Service (real dotconfig)
- Error-path tests: Docker not running/not installed
- Error-path tests: dotconfig not initialized
- Error-path tests: SOPS/age keys missing (secrets section skipped)
- Error-path tests: port conflicts (bind to a port, then try to allocate)
- Error-path tests: malformed/incomplete config files
- Error-path tests: missing app name source file
- Error-path tests: container exists but Postgres unhealthy
- CLI tests for `rundbat init`, `rundbat env list`, `rundbat env connstr`
- MCP tool surface tests (tool listing, parameter schemas)
- Bug fixes for issues discovered during testing
- Test fixtures: container cleanup, temp project dirs, PATH manipulation

### Out of Scope

- New features or tools
- Remote environment testing (SSH, registries)
- CI/CD pipeline setup (future sprint)
- Performance or load testing

## Test Strategy

This sprint IS the test strategy. All tickets produce tests. The test
types follow the project testing instructions:

- **System tests** (`tests/system/`) for all new tests — they exercise
  multiple components and external tools together.
- Tests that need real Docker: marked `requires_docker`.
- Tests that need real dotconfig: marked `requires_dotconfig`.
- Error-path tests that simulate missing tools by patching PATH or
  environment: no special markers needed (they mock the absence).
- Test isolation: each test creates and cleans up its own containers and
  temp directories. Container names use a `rundbat-test-` prefix to avoid
  collisions with real environments.
- Cleanup: a pytest fixture that tracks created containers and removes
  them after each test, even on failure.
- Temp projects: a pytest fixture that creates a temp directory, cds into
  it, and tears it down after the test.

## Architecture Notes

No architecture changes in this sprint. The architecture document is
carried forward from Sprint 001 unchanged. The Sprint Changes section
reflects only test and fixture additions.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

(To be created after sprint approval.)

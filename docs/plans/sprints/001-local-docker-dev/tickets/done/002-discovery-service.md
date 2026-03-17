---
id: '002'
title: Discovery Service
status: in-progress
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Discovery Service

## Description

Implement `discover_system` and `verify_docker` tools. The Discovery
Service detects host OS, Docker status, dotconfig status, Node.js
version, and existing rundbat configuration. It runs shell commands and
parses output — read-only, no modifications.

Discovery checks for tool *presence* via version commands. These calls
are not routed through Config Service or Database Service (those don't
exist yet and discovery is about presence, not operations).

## Acceptance Criteria

- [x] `src/rundbat/discovery.py` module with detection functions
- [x] `discover_system` MCP tool registered on the server
- [x] Returns OS name and architecture (platform module)
- [x] Returns Docker installed/running status and backend (parses `docker info`)
- [x] Returns dotconfig installed/initialized status (`dotconfig config`)
- [x] Returns Node.js version if present (`node --version`)
- [x] Returns existing rundbat config paths if found
- [x] `verify_docker` MCP tool — returns pass/fail for `docker info`
- [x] Graceful handling when commands are not found (not installed)
- [x] Structured return format (dict/JSON with clear field names)

## Testing

- **Existing tests to run**: `uv run pytest` (ticket 001 tests)
- **New tests to write**: `tests/test_discovery.py`
  - Test OS detection (always works)
  - Test graceful handling when docker/dotconfig/node not found (mock
    subprocess to simulate missing commands)
  - Test parsing of `docker info` output
- **Verification command**: `uv run pytest`

---
id: '005'
title: Slim CLI Surface
status: done
branch: sprint/005-slim-cli-surface
use-cases:
- SUC-001
---

# Sprint 005: Slim CLI Surface

## Goals

Reduce rundbat from 17 top-level CLI commands to 4. Remove commands that
duplicate docker compose, dotconfig, or that the agent doesn't need.
Rewrite skills and agent docs to match.

## Problem

The CLI has accumulated commands for every operation (start, stop, health,
validate, set-secret, check-drift, etc.). Most are thin wrappers around
docker or dotconfig that the agent can call directly. The large command
surface makes rundbat confusing and hard to maintain.

## Solution

Keep 4 commands: `init`, `init-docker`, `deploy`, `deploy-init`. Remove
13 commands from cli.py. Keep underlying modules as library code. Rewrite
bundled skills and agent docs to reference compose/dotconfig directly.

## Success Criteria

- `rundbat --help` shows exactly 4 commands (plus --version/--help)
- Bundled skills reference compose/dotconfig instead of removed commands
- `uv run pytest` passes
- `rundbat init` still validates prerequisites (docker, dotconfig)

## Scope

### In Scope

- Remove 13 CLI commands and their handlers
- Fold discover checks into init
- Rewrite bundled skills (dev-database, init-docker, diagnose, manage-secrets)
- Rewrite deployment-expert agent doc
- Update rules/rundbat.md
- Update tests

### Out of Scope

- Deleting underlying modules (database.py, environment.py, etc.)
- Changing deploy or init-docker behavior

## Test Strategy

- Remove tests for cut commands
- Verify remaining 4 commands work via help output tests
- Run full test suite

## Architecture Notes

- Modules stay as library code for potential future use
- Skills become the primary interface for agent operations
- CLI is just init + docker generation + deploy

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Remove cut CLI commands and handlers | — | 1 |
| 002 | Rewrite skills and agent docs | — | 1 |
| 003 | Update tests | 001 | 2 |

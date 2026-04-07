---
id: "001"
title: "Flask Counter App"
status: planning
branch: sprint/001-flask-counter-app
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
  - SUC-006
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001: Flask Counter App

## Goals

Build the complete Flask counter application for the dev environment.
The app demonstrates the rundbat + dotconfig workflow by running a minimal
single-file Flask app with a PostgreSQL counter and a Redis counter, both
provisioned locally by rundbat and configured through dotconfig.

## Problem

There is no reference implementation that exercises the full rundbat
lifecycle for a real application. Without a concrete example, it is
difficult to validate that rundbat's provisioning, configuration, and
lifecycle commands work end-to-end for a dev environment.

## Solution

Build a single-file Flask application (`app.py`) with two counters —
one backed by PostgreSQL, one by Redis — and a minimal HTML template.
The dev environment is provisioned with `rundbat create-env dev`, which
writes `DATABASE_URL` and `REDIS_URL` to dotconfig. The app reads those
values at startup via `dotconfig load`, initializes the database schema
on first run, and serves three routes: `GET /`, `POST /increment/postgres`,
and `POST /increment/redis`.

## Success Criteria

- `rundbat create-env dev` provisions both containers and writes config.
- `APP_ENV=dev flask run` starts the app without errors.
- `GET /` displays both counter values (initially 0).
- Clicking "Increment Postgres" increments the PostgreSQL counter and
  refreshes the page showing the new value.
- Clicking "Increment Redis" increments the Redis counter and refreshes
  the page showing the new value.
- No credentials or connection strings are hardcoded in any source file.
- All config flows through dotconfig.

## Scope

### In Scope

- `app.py` — single-file Flask application with all routes and db logic
- `templates/index.html` — single HTML page with two counters and two buttons
- `requirements.txt` — Flask, psycopg2-binary, redis
- Dev environment setup via `rundbat create-env dev`
- PostgreSQL integration: table init, counter read, counter increment
- Redis integration: key init, counter read, counter increment
- dotconfig config loading at startup (`dotconfig load -d <env> --json --flat -S`)
- Manual testing of all three routes in the dev environment

### Out of Scope

- Dockerfile (test and prod environments — future sprints)
- `test` and `prod` environment provisioning
- CI/CD pipelines or GitHub Actions workflows
- CSS styling or JavaScript frameworks
- Database migration tooling
- gunicorn WSGI server configuration

## Test Strategy

- **Manual testing (primary):** Run `rundbat create-env dev`, start the
  Flask app, and exercise all three routes in a browser to verify counter
  behavior.
- **Unit tests:** Write focused unit tests for the PostgreSQL and Redis
  helper functions (init, read, increment) using mock connections or a
  real dev database. No test framework beyond pytest.

## Architecture Notes

- The Flask app is a single Python file. No blueprints, no packages.
- Config is read once at startup using a subprocess call to
  `dotconfig load -d <ENV> --json --flat -S` where `ENV` defaults to `dev`.
- The `APP_ENV` environment variable selects the active environment.
- PostgreSQL schema initialization runs at startup (inside
  `with app.app_context()`), not lazily per-request.
- Redis initialization is lazy: `SETNX counter 0` on first access.
- Both counters use simple integer operations; no transactions needed
  beyond what psycopg2 provides by default.

## GitHub Issues

(None for this sprint.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Project scaffolding | — | 1 |
| 002 | PostgreSQL integration | 001 | 2 |
| 003 | Redis integration | 001 | 2 |
| 004 | Wire up routes and template | 002, 003 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).

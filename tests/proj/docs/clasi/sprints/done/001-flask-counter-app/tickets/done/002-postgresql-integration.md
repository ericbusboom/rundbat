---
id: '002'
title: PostgreSQL integration
status: in-progress
use-cases:
- SUC-002
- SUC-005
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# PostgreSQL integration

## Description

Add PostgreSQL connection, schema initialization, counter read, and
counter increment to `app.py`. At startup, the app connects to
PostgreSQL using `DATABASE_URL` from dotconfig, creates the `counters`
table if it does not exist, and inserts the seed row. Helper functions
provide `get_pg_count()` and `increment_pg()` for use by routes.

## Acceptance Criteria

- [ ] `app.py` reads `DATABASE_URL` from dotconfig using
  `dotconfig load -d <APP_ENV> --json --flat -S` at startup.
- [ ] At startup, the `counters` table is created if it does not exist
  (`CREATE TABLE IF NOT EXISTS counters ...`).
- [ ] At startup, the seed row (`id=1, value=0`) is inserted if it does
  not exist (`INSERT INTO counters ... ON CONFLICT DO NOTHING`).
- [ ] `get_pg_count()` returns the integer value from
  `SELECT value FROM counters WHERE id=1`.
- [ ] `increment_pg()` executes
  `UPDATE counters SET value = value + 1 WHERE id = 1` and commits.
- [ ] Starting Flask against a fresh dev environment (after
  `rundbat create-env dev`) results in both functions working correctly.
- [ ] `APP_ENV` defaults to `dev` if not set.

## Testing

- **Existing tests to run**: `uv run pytest` (ticket 001 tests must still pass).
- **New tests to write**: Unit tests for `get_pg_count()` and
  `increment_pg()` using either a real dev database or psycopg2 mocks.
  Test that schema init is idempotent (running twice does not fail).
- **Verification command**: `uv run pytest`

## Implementation Plan

### Approach

Add a `load_config()` function that calls `dotconfig load` via subprocess
and parses the JSON output. Add `init_pg()` (called at app startup in
`with app.app_context()`), `get_pg_count()`, and `increment_pg()`. Use
psycopg2 with `autocommit=False`; commit explicitly after the UPDATE.

### Files to Modify

- `app.py`:
  - Add `load_config()` — subprocess call to dotconfig, returns dict.
  - Add module-level `DATABASE_URL` set from `load_config()` output.
  - Add `get_pg_connection()` — returns a psycopg2 connection from
    `DATABASE_URL`.
  - Add `init_pg()` — `CREATE TABLE IF NOT EXISTS` + `INSERT ... ON CONFLICT DO NOTHING`.
  - Add `get_pg_count()` — returns int from SELECT.
  - Add `increment_pg()` — executes UPDATE and commits.
  - Call `init_pg()` inside `with app.app_context():` before `app.run()`.

### Files to Create

None beyond what ticket 001 established.

### Documentation Updates

None required for this ticket.

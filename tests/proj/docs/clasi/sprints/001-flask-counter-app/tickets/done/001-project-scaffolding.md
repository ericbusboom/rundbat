---
id: '001'
title: Project scaffolding
status: in-progress
use-cases:
- SUC-004
depends-on: []
github-issue: ''
todo: flask-counter-app.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Project scaffolding

## Description

Create the skeleton files for the Flask Counter App: `app.py` with stub
routes and no database logic, `templates/index.html` with the full UI
structure, and `requirements.txt` with all required dependencies. The
result is a runnable Flask app that returns placeholder counter values
(0) before any database integration is added in subsequent tickets.

## Acceptance Criteria

- [ ] `requirements.txt` exists and contains `Flask`, `psycopg2-binary`, and `redis`.
- [ ] `app.py` exists and defines a Flask app with three routes:
  `GET /`, `POST /increment/postgres`, `POST /increment/redis`.
- [ ] `GET /` renders `templates/index.html` with `pg_count=0` and
  `redis_count=0` (hardcoded stubs for now).
- [ ] `POST /increment/postgres` returns a 302 redirect to `/`.
- [ ] `POST /increment/redis` returns a 302 redirect to `/`.
- [ ] `templates/index.html` renders without error and contains the text
  "Flask Counter App", "PostgreSQL Counter", and "Redis Counter".
- [ ] `flask run` starts without errors (no database connections required yet).

## Testing

- **Existing tests to run**: None (greenfield).
- **New tests to write**: Minimal pytest test using Flask test client —
  verify `GET /` returns 200 and contains counter labels; verify both
  POST routes return 302 with `Location: /`.
- **Verification command**: `uv run pytest`

## Implementation Plan

### Approach

Create the three files. Stub routes in `app.py` return hardcoded 0
values so the app is runnable without database connections. The template
contains the full HTML structure per the UI spec (heading, two counter
sections, two form buttons). This gives a verifiable baseline before
tickets 002 and 003 add real database logic.

### Files to Create

- `app.py` — Flask app skeleton:
  - `GET /` renders `templates/index.html` with `pg_count=0, redis_count=0`.
  - `POST /increment/postgres` redirects to `url_for('index')`.
  - `POST /increment/redis` redirects to `url_for('index')`.
- `templates/index.html` — Single HTML page per spec section 4:
  - Heading: "Flask Counter App"
  - PostgreSQL section: label, counter value (`{{ pg_count }}`), form
    POSTing to `/increment/postgres` with button "Increment Postgres".
  - Redis section: label, counter value (`{{ redis_count }}`), form
    POSTing to `/increment/redis` with button "Increment Redis".
- `requirements.txt` — Three entries: `Flask`, `psycopg2-binary`, `redis`.

### Files to Modify

None (greenfield).

### Documentation Updates

None required for this ticket.

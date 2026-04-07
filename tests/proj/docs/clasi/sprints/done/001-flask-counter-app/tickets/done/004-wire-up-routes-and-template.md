---
id: '004'
title: Wire up routes and template
status: in-progress
use-cases:
- SUC-001
- SUC-002
- SUC-003
depends-on:
- '002'
- '003'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire up routes and template

## Description

Replace the stub route implementations in `app.py` with real database
calls using the helpers from tickets 002 and 003. `GET /` calls
`get_pg_count()` and `get_redis_count()` and passes the results to the
template. `POST /increment/postgres` calls `increment_pg()`.
`POST /increment/redis` calls `increment_redis()`. After this ticket,
the full dev environment flow is working end-to-end.

## Acceptance Criteria

- [ ] `GET /` renders `index.html` with the real PostgreSQL counter value
  from `get_pg_count()` and the real Redis counter value from
  `get_redis_count()`.
- [ ] `POST /increment/postgres` calls `increment_pg()` and redirects to `/`.
- [ ] `POST /increment/redis` calls `increment_redis()` and redirects to `/`.
- [ ] Clicking "Increment Postgres" three times results in the PostgreSQL
  counter showing 3 after page reload.
- [ ] Clicking "Increment Redis" five times results in the Redis counter
  showing 5 after page reload.
- [ ] The two counters are independent — incrementing one does not affect
  the other.
- [ ] After restarting Flask (`flask run`), both counter values persist
  (PostgreSQL) or persist (Redis, unless Redis container was restarted).
- [ ] `uv run pytest` passes all tests from tickets 001, 002, and 003.

## Testing

- **Existing tests to run**: All tests from tickets 001, 002, 003.
- **New tests to write**: Integration test using Flask test client against
  real dev databases (or mocks): POST to `/increment/postgres`, GET `/`,
  verify `pg_count` incremented. Same for Redis route. Verify independence
  of counters.
- **Verification command**: `uv run pytest`
- **Manual verification**: Run `rundbat create-env dev`, `APP_ENV=dev flask run`,
  open browser, click each button several times, verify counts go up correctly.

## Implementation Plan

### Approach

This is a two-line change per route handler — swap the hardcoded 0 stubs
for real function calls. The bulk of the work in this ticket is the
integration test and the manual dev environment walkthrough.

### Files to Modify

- `app.py`:
  - `GET /` route: replace `pg_count=0, redis_count=0` with
    `pg_count=get_pg_count(), redis_count=get_redis_count()`.
  - `POST /increment/postgres` route: add `increment_pg()` call before
    the redirect.
  - `POST /increment/redis` route: add `increment_redis()` call before
    the redirect.

### Files to Create

None.

### Documentation Updates

None required for this ticket. The sprint is complete when this ticket
passes its acceptance criteria.

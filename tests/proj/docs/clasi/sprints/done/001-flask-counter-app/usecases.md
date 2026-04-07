---
status: draft
sprint: "001"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001 Use Cases

This sprint covers the dev environment only. Use cases for test and
prod environments (UC-007, UC-008) are deferred to future sprints.

---

## SUC-001: View Current Counter Values (Dev)

Parent: UC-001

- **Actor**: Developer (browser)
- **Preconditions**:
  - `rundbat create-env dev` has been run.
  - PostgreSQL and Redis containers are running locally.
  - `APP_ENV=dev flask run` has been started.
- **Main Flow**:
  1. Developer navigates to `http://localhost:5000/` in a browser.
  2. Flask reads `DATABASE_URL` and `REDIS_URL` from dotconfig `dev`.
  3. Flask reads `counters.value` from PostgreSQL.
  4. Flask reads `GET counter` from Redis (returns 0 if key absent).
  5. Flask renders `templates/index.html` with both values.
  6. Browser displays both counter values and two increment buttons.
- **Postconditions**:
  - Both counter values are visible as integers.
  - No state changed in PostgreSQL or Redis.
- **Acceptance Criteria**:
  - [ ] `GET /` returns HTTP 200.
  - [ ] Page shows a PostgreSQL counter value (integer).
  - [ ] Page shows a Redis counter value (integer).
  - [ ] Initial values are 0 on a fresh environment.

---

## SUC-002: Increment PostgreSQL Counter (Dev)

Parent: UC-002

- **Actor**: Developer (browser)
- **Preconditions**:
  - Flask is running in dev mode.
  - PostgreSQL container is running; `counters` table exists.
- **Main Flow**:
  1. Developer clicks the "Increment Postgres" button.
  2. Browser POSTs to `/increment/postgres`.
  3. Flask executes `UPDATE counters SET value = value + 1 WHERE id = 1`.
  4. Flask issues a 302 redirect to `GET /`.
  5. Browser follows the redirect; updated value is displayed.
- **Postconditions**:
  - `counters.value` is incremented by 1.
  - The main page shows the new PostgreSQL counter value.
- **Acceptance Criteria**:
  - [ ] `POST /increment/postgres` returns HTTP 302.
  - [ ] PostgreSQL counter value increases by 1 after each click.
  - [ ] Page reload shows the persisted incremented value.
  - [ ] Incrementing PostgreSQL does not affect the Redis counter.

---

## SUC-003: Increment Redis Counter (Dev)

Parent: UC-003

- **Actor**: Developer (browser)
- **Preconditions**:
  - Flask is running in dev mode.
  - Redis container is running.
- **Main Flow**:
  1. Developer clicks the "Increment Redis" button.
  2. Browser POSTs to `/increment/redis`.
  3. Flask executes `INCR counter` on Redis.
  4. Flask issues a 302 redirect to `GET /`.
  5. Browser follows the redirect; updated value is displayed.
- **Postconditions**:
  - The Redis `counter` key value is incremented by 1.
  - The main page shows the new Redis counter value.
- **Acceptance Criteria**:
  - [ ] `POST /increment/redis` returns HTTP 302.
  - [ ] Redis counter value increases by 1 after each click.
  - [ ] Page reload shows the persisted incremented value.
  - [ ] Incrementing Redis does not affect the PostgreSQL counter.

---

## SUC-004: Provision Dev Environment

Parent: UC-004

- **Actor**: Developer
- **Preconditions**:
  - rundbat is installed.
  - Docker is running locally.
  - dotconfig is initialized for the project.
- **Main Flow**:
  1. Developer runs `rundbat create-env dev`.
  2. rundbat provisions a local PostgreSQL container with an assigned port.
  3. rundbat provisions a local Redis container with an assigned port.
  4. rundbat writes `DATABASE_URL` and `REDIS_URL` to dotconfig `dev`.
  5. Developer verifies with `dotconfig load -d dev --json --flat -S`.
  6. Developer starts Flask: `APP_ENV=dev flask run`.
- **Postconditions**:
  - Both containers are running.
  - Flask connects to both via config from dotconfig.
  - No credentials are hardcoded anywhere.
- **Acceptance Criteria**:
  - [ ] `rundbat create-env dev` completes without error.
  - [ ] `dotconfig load -d dev --json --flat -S` returns `DATABASE_URL` and `REDIS_URL`.
  - [ ] Flask starts without connection errors.
  - [ ] `rundbat health dev` reports both services healthy.

---

## SUC-005: Initialize PostgreSQL Schema on First Run

Parent: UC-005

- **Actor**: Flask Application (automatic at startup)
- **Preconditions**:
  - `DATABASE_URL` is available from dotconfig.
  - PostgreSQL is reachable.
  - The `counters` table may not yet exist.
- **Main Flow**:
  1. Flask connects to PostgreSQL at startup.
  2. Flask checks whether the `counters` table exists.
  3. If absent, Flask creates the table and inserts the seed row (`id=1, value=0`).
  4. Flask proceeds with normal request handling.
- **Postconditions**:
  - `counters` table exists with exactly one row.
- **Acceptance Criteria**:
  - [ ] Starting Flask against a fresh database creates the `counters` table automatically.
  - [ ] `SELECT value FROM counters WHERE id=1` returns 0 after first startup.
  - [ ] Restarting Flask does not duplicate the row or fail.

---

## SUC-006: Initialize Redis Key on First Access

Parent: UC-006

- **Actor**: Flask Application (automatic on first Redis operation)
- **Preconditions**:
  - `REDIS_URL` is available from dotconfig.
  - Redis is reachable.
  - The `counter` key may not exist.
- **Main Flow**:
  1. Flask reads `GET counter` from Redis; if key is absent, treats value as 0.
  2. On first `INCR counter`, Redis creates the key starting from 0 and returns 1.
- **Postconditions**:
  - The `counter` key exists in Redis with a valid integer value.
- **Acceptance Criteria**:
  - [ ] `GET /` on a fresh Redis instance displays Redis counter as 0.
  - [ ] First `POST /increment/redis` results in Redis counter showing 1.
  - [ ] Subsequent increments continue to count up correctly.

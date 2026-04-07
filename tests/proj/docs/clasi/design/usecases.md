---
project: Flask Counter App
version: 1.0.0
date: 2026-04-07
---

# Flask Counter App — Use Cases

## UC-001: View Current Counter Values

**Title:** View Current Counter Values
**Actor:** End User (browser)
**Preconditions:**
- The Flask app is running.
- PostgreSQL container is running and the `counters` table exists with one row.
- Redis container is running and the `counter` key exists.

**Main Flow:**
1. User navigates to `/` in a browser.
2. Flask reads `counters.value` from PostgreSQL.
3. Flask reads `GET counter` from Redis.
4. Flask renders `index.html` with both values.
5. Browser displays the page showing both counter values and two increment buttons.

**Postconditions:**
- Both counter values are displayed as integers.
- No state has changed in PostgreSQL or Redis.

**Error Flows:**
- E1: PostgreSQL is unreachable — Flask returns a 500 error page with a connection error message.
- E2: Redis is unreachable — Flask returns a 500 error page with a connection error message.
- E3: `counters` table does not exist — Flask initializes the table and row, then continues (see UC-005).

---

## UC-002: Increment PostgreSQL Counter

**Title:** Increment PostgreSQL Counter
**Actor:** End User (browser)
**Preconditions:**
- The Flask app is running.
- PostgreSQL container is running and the `counters` table has one row.

**Main Flow:**
1. User clicks the "Increment Postgres" button on the main page.
2. Browser POSTs to `/increment/postgres`.
3. Flask executes `UPDATE counters SET value = value + 1 WHERE id = 1`.
4. Flask issues a 302 redirect to `GET /`.
5. Browser follows the redirect and renders the updated page (UC-001).

**Postconditions:**
- The `counters.value` column is incremented by 1.
- The main page displays the new PostgreSQL counter value.

**Error Flows:**
- E1: PostgreSQL is unreachable during the POST — Flask returns a 500 error; the counter is not modified.
- E2: The `counters` row does not exist — Flask initializes it (see UC-005), then retries the increment.

---

## UC-003: Increment Redis Counter

**Title:** Increment Redis Counter
**Actor:** End User (browser)
**Preconditions:**
- The Flask app is running.
- Redis container is running.

**Main Flow:**
1. User clicks the "Increment Redis" button on the main page.
2. Browser POSTs to `/increment/redis`.
3. Flask executes `INCR counter` on Redis.
4. Flask issues a 302 redirect to `GET /`.
5. Browser follows the redirect and renders the updated page (UC-001).

**Postconditions:**
- The Redis `counter` key value is incremented by 1.
- The main page displays the new Redis counter value.

**Error Flows:**
- E1: Redis is unreachable during the POST — Flask returns a 500 error; the counter is not modified.
- E2: The `counter` key does not exist — Redis `INCR` creates it starting from 0, resulting in value 1.

---

## UC-004: Provision Dev Environment

**Title:** Provision Development Environment
**Actor:** Developer
**Preconditions:**
- rundbat is installed and configured for this project.
- Docker is running on the local machine.
- dotconfig is initialized for the project.

**Main Flow:**
1. Developer runs `rundbat create-env dev`.
2. rundbat provisions a local PostgreSQL container and assigns a port.
3. rundbat provisions a local Redis container and assigns a port.
4. rundbat generates a `DATABASE_URL` and `REDIS_URL` and writes them to the dotconfig `dev` environment.
5. Developer runs `APP_ENV=dev flask run` to start Flask on the host.
6. Flask reads `DATABASE_URL` and `REDIS_URL` from dotconfig `dev` at startup.

**Postconditions:**
- PostgreSQL and Redis containers are running locally.
- Flask is running on the host and connected to both.
- Configuration is stored in dotconfig; no credentials are hardcoded.

**Error Flows:**
- E1: Docker is not running — rundbat reports the error and stops; developer must start Docker.
- E2: Port conflict — rundbat selects an alternate available port.
- E3: dotconfig not initialized — rundbat instructs developer to run `rundbat init` first.

---

## UC-005: Initialize Database Schema on First Run

**Title:** Initialize Database Schema on First Run
**Actor:** Flask Application (automatic, on startup or first request)
**Preconditions:**
- PostgreSQL is reachable via `DATABASE_URL`.
- The `counters` table may or may not exist.

**Main Flow:**
1. Flask connects to PostgreSQL using `DATABASE_URL`.
2. Flask checks whether the `counters` table exists.
3. If the table does not exist, Flask executes:
   ```sql
   CREATE TABLE counters (id INTEGER PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0);
   INSERT INTO counters (id, value) VALUES (1, 0);
   ```
4. Flask proceeds with normal operation.

**Postconditions:**
- The `counters` table exists with exactly one row (`id=1`, `value=0`).

**Error Flows:**
- E1: PostgreSQL is unreachable — Flask raises an exception; startup fails with a clear connection error.

---

## UC-006: Initialize Redis Key on First Access

**Title:** Initialize Redis Key on First Access
**Actor:** Flask Application (automatic, on first Redis operation)
**Preconditions:**
- Redis is reachable via `REDIS_URL`.
- The `counter` key may or may not exist.

**Main Flow:**
1. Flask connects to Redis using `REDIS_URL`.
2. On first `GET counter`, if the key does not exist, Redis returns `nil` (0 displayed).
3. On first `INCR counter`, if the key does not exist, Redis creates it at 0 and returns 1.

**Postconditions:**
- The `counter` key exists in Redis with a valid integer value.

**Error Flows:**
- E1: Redis is unreachable — Flask raises an exception; the request fails with a 500 error.

---

## UC-007: Provision Test Environment

**Title:** Provision Test (Full Local Docker) Environment
**Actor:** Developer / CI System
**Preconditions:**
- rundbat is installed and configured.
- Docker is running on the local machine.
- A `Dockerfile` exists in the project root.

**Main Flow:**
1. Developer runs `rundbat create-env test`.
2. rundbat provisions local PostgreSQL and Redis containers.
3. rundbat writes `DATABASE_URL` and `REDIS_URL` to dotconfig `test` environment.
4. Developer builds the Flask image: `docker build -t flask-counter-app .`.
5. Developer runs `rundbat start test` to start all containers.
6. Flask container reads config from dotconfig `test` (injected as environment variables).

**Postconditions:**
- All three services (Flask, PostgreSQL, Redis) run in local Docker containers.
- The app is accessible on the host via the exposed Flask container port.

**Error Flows:**
- E1: Dockerfile is missing — build step fails; developer must create it.
- E2: Port conflict — rundbat selects alternate ports.
- E3: Container fails to start — rundbat reports the container log for diagnosis.

---

## UC-008: Deploy to Production (Remote Docker)

**Title:** Deploy to Production Environment via SSH
**Actor:** Developer / Operator
**Preconditions:**
- rundbat is installed and configured.
- SSH access to the remote Docker host is available.
- A Docker registry or SSH-based image transfer mechanism is available.
- A `Dockerfile` exists in the project root.

**Main Flow:**
1. Developer runs `rundbat create-env prod`.
2. rundbat provisions PostgreSQL and Redis on the remote host via SSH.
3. rundbat writes `DATABASE_URL` and `REDIS_URL` to dotconfig `prod` environment.
4. Developer builds the Flask image and pushes it to a registry (or transfers via SSH).
5. Developer runs `rundbat start prod` to start all containers on the remote host.
6. Flask container on the remote host reads config from dotconfig `prod` (injected as environment variables).

**Postconditions:**
- All three services run on the remote Docker host.
- The app is accessible via the remote host's public address.
- Secrets are encrypted via SOPS in dotconfig and never hardcoded.

**Error Flows:**
- E1: SSH connection fails — rundbat reports the error; developer must verify SSH credentials and host availability.
- E2: Remote Docker not running — rundbat reports the error; operator must start Docker on the remote host.
- E3: Image push fails — developer must diagnose registry credentials or network.

---

## UC-009: Retrieve Environment Configuration

**Title:** Retrieve Connection Strings for an Environment
**Actor:** Developer / Flask Application
**Preconditions:**
- rundbat has previously provisioned the target environment.
- dotconfig contains the configuration for the target environment.

**Main Flow:**
1. Developer (or the Flask app at startup) runs:
   `dotconfig load -d <env> --json --flat -S`
2. dotconfig decrypts SOPS-encrypted secrets and returns a flat JSON object.
3. The caller extracts `DATABASE_URL` and `REDIS_URL`.

**Postconditions:**
- Connection strings are available in memory; no secrets are written to disk unencrypted.

**Error Flows:**
- E1: dotconfig is not initialized — command fails; developer must run `rundbat init`.
- E2: SOPS decryption fails (missing key) — dotconfig reports a decryption error.
- E3: Environment not provisioned — config keys are absent; developer must run `rundbat create-env <env>`.

---

## UC-010: Health Check an Environment

**Title:** Verify Database Connectivity for an Environment
**Actor:** Developer / CI System
**Preconditions:**
- rundbat has provisioned the target environment.
- Containers are expected to be running.

**Main Flow:**
1. Developer runs `rundbat health <env>`.
2. rundbat retrieves the connection strings from dotconfig.
3. rundbat attempts a connection to PostgreSQL and verifies it responds.
4. rundbat attempts a connection to Redis and verifies it responds.
5. rundbat reports success for each service.

**Postconditions:**
- Developer has confirmed that both databases are reachable from the local host.

**Error Flows:**
- E1: PostgreSQL container is stopped — rundbat auto-restarts it (if `get-config` behavior applies) and retries.
- E2: Redis container is stopped — rundbat reports it as unreachable; developer runs `rundbat start <env>`.
- E3: Connection timeout — rundbat reports which service failed and suggests `rundbat start <env>`.

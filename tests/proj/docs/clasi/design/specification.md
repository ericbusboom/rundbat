---
project: Flask Counter App
version: 1.0.0
date: 2026-04-07
---

# Flask Counter App — Full Specification

## 1. Application Architecture

### 1.1 Structure

The application is a single-file Flask app (`app.py`) with an inline or
adjacent Jinja2 template. There is no application package structure; the
entire Flask logic lives in one Python file.

```
flask-counter-app/
  app.py              # Flask application (single file)
  templates/
    index.html        # Single page UI (two counters, two buttons)
  Dockerfile          # Used for test and prod environments
  requirements.txt    # Python dependencies
  config/             # dotconfig-managed configuration (not edited directly)
```

### 1.2 Request Flow

1. Browser loads `/` — Flask reads both counters from PostgreSQL and Redis
   and renders `index.html`.
2. User clicks "Increment Postgres" — browser POSTs to `/increment/postgres`.
   Flask increments the PostgreSQL counter row and redirects to `/`.
3. User clicks "Increment Redis" — browser POSTs to `/increment/redis`.
   Flask increments the Redis key and redirects to `/`.

### 1.3 Configuration Loading

At startup, the Flask app reads connection strings from the active dotconfig
environment:

```bash
dotconfig load -d <ENV> --json --flat -S
```

Keys consumed:

| dotconfig key | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (psycopg2 format) |
| `REDIS_URL` | Redis connection string (`redis://...`) |

The active environment (`ENV`) is selected via an environment variable
(e.g., `APP_ENV=dev`) or defaults to `dev`.

---

## 2. Database Schemas

### 2.1 PostgreSQL

**Table:** `counters`

| Column | Type | Constraints | Default |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | 1 (single row) |
| `value` | INTEGER | NOT NULL | 0 |

Initialization: On first run, if the table does not exist, the app creates
it and inserts the single row with `value = 0`.

Increment query:

```sql
UPDATE counters SET value = value + 1 WHERE id = 1;
```

Read query:

```sql
SELECT value FROM counters WHERE id = 1;
```

### 2.2 Redis

**Key:** `counter`

**Value type:** String (integer representation, e.g., `"42"`)

Initialization: On first access, if the key does not exist, it is created
with value `0` using `SETNX counter 0`.

Increment command: `INCR counter`

Read command: `GET counter`

---

## 3. API Routes

All routes are served by the Flask development server (dev) or gunicorn
(test, prod).

### 3.1 `GET /`

**Purpose:** Render the main page with current counter values.

**Flow:**
1. Read `counters.value` from PostgreSQL.
2. Read `GET counter` from Redis.
3. Render `index.html` with `pg_count` and `redis_count` template variables.

**Response:** 200 OK, HTML page.

### 3.2 `POST /increment/postgres`

**Purpose:** Increment the PostgreSQL counter by 1.

**Flow:**
1. Execute `UPDATE counters SET value = value + 1 WHERE id = 1`.
2. Redirect to `GET /`.

**Response:** 302 redirect to `/`.

### 3.3 `POST /increment/redis`

**Purpose:** Increment the Redis counter by 1.

**Flow:**
1. Execute `INCR counter`.
2. Redirect to `GET /`.

**Response:** 302 redirect to `/`.

---

## 4. UI Specification

The single HTML page (`index.html`) contains:

- A heading: "Flask Counter App"
- **PostgreSQL Counter** section:
  - Label: "PostgreSQL Counter"
  - Current value display (integer)
  - Button: "Increment Postgres" (submits POST to `/increment/postgres`)
- **Redis Counter** section:
  - Label: "Redis Counter"
  - Current value display (integer)
  - Button: "Increment Redis" (submits POST to `/increment/redis`)

Layout is functional; no styling framework is required. Buttons are
standard HTML form submit buttons.

---

## 5. Deployment Configurations

### 5.1 dev

**Purpose:** Local development with hot-reload.

| Component | Runtime | Provisioning |
|---|---|---|
| Flask | Host process (`flask run`) | Manual |
| PostgreSQL | Local Docker container | `rundbat create-env dev` |
| Redis | Local Docker container | `rundbat create-env dev` |

**Setup procedure:**
1. `rundbat create-env dev` — provisions PostgreSQL and Redis containers,
   writes connection strings to dotconfig `dev` environment.
2. `dotconfig load -d dev --json --flat -S` — verify config is populated.
3. `APP_ENV=dev flask run` — start Flask on the host.

**Config source:** dotconfig `dev` environment.

### 5.2 test

**Purpose:** Full local containerized run for integration testing.

| Component | Runtime | Provisioning |
|---|---|---|
| Flask | Local Docker container | `docker compose up` (via rundbat) |
| PostgreSQL | Local Docker container | `rundbat create-env test` |
| Redis | Local Docker container | `rundbat create-env test` |

**Setup procedure:**
1. `rundbat create-env test` — provisions PostgreSQL and Redis, writes
   config to dotconfig `test` environment.
2. Build Flask image: `docker build -t flask-counter-app .`
3. `rundbat start test` — start all containers including Flask.

**Dockerfile requirements:**
- Base image: `python:3.12-slim`
- Install `requirements.txt`
- Copy `app.py` and `templates/`
- Expose port 5000
- CMD: `gunicorn -w 2 -b 0.0.0.0:5000 app:app`

**Config source:** dotconfig `test` environment, injected as environment
variables into the Flask container.

### 5.3 prod

**Purpose:** Production deployment to a remote Docker host.

| Component | Runtime | Provisioning |
|---|---|---|
| Flask | Remote Docker container (SSH) | rundbat remote deploy |
| PostgreSQL | Remote Docker container (SSH) | `rundbat create-env prod` |
| Redis | Remote Docker container (SSH) | `rundbat create-env prod` |

**Setup procedure:**
1. `rundbat create-env prod` — provisions remote PostgreSQL and Redis via
   SSH, writes config to dotconfig `prod` environment.
2. Build and push Flask image to a registry (or transfer via SSH).
3. `rundbat start prod` — start all services on the remote host.

**Config source:** dotconfig `prod` environment, injected as environment
variables into the Flask container on the remote host.

---

## 6. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Web framework | Flask (Python) | Single-file application |
| Template engine | Jinja2 | Bundled with Flask |
| WSGI server (non-dev) | gunicorn | Used in test and prod containers |
| Relational database | PostgreSQL | One table, one row |
| Cache / counter store | Redis | One key |
| DB driver | psycopg2 (or psycopg2-binary) | PostgreSQL client |
| Redis client | redis-py | Python Redis client |
| Container runtime | Docker | All non-dev services |
| Container orchestration | Docker Compose (via rundbat) | Managed by rundbat |
| Container management | rundbat | Provisioning, lifecycle, config |
| Configuration | dotconfig + SOPS | All connection strings and secrets |

---

## 7. Requirements

### 7.1 Functional Requirements

- FR-001: The app shall display the current PostgreSQL counter value on the main page.
- FR-002: The app shall display the current Redis counter value on the main page.
- FR-003: The app shall increment the PostgreSQL counter when the user clicks "Increment Postgres".
- FR-004: The app shall increment the Redis counter when the user clicks "Increment Redis".
- FR-005: The app shall initialize the PostgreSQL table and row if they do not exist on first run.
- FR-006: The app shall initialize the Redis key to 0 if it does not exist on first access.
- FR-007: The app shall read all connection strings from dotconfig at startup.

### 7.2 Non-Functional Requirements

- NFR-001: The Flask application shall be a single Python file (`app.py`).
- NFR-002: All Docker container lifecycle operations shall use rundbat; the app shall not call Docker directly.
- NFR-003: All configuration (URLs, secrets) shall flow through dotconfig; the app shall not hardcode credentials.
- NFR-004: The app shall support three named environments: `dev`, `test`, `prod`.
- NFR-005: The active environment shall be selectable via an environment variable (`APP_ENV`).
- NFR-006: The `test` and `prod` environments shall containerize the Flask app using a Dockerfile.

### 7.3 Constraints

- CON-001: PostgreSQL schema is exactly one table (`counters`) with exactly one row.
- CON-002: Redis schema is exactly one key (`counter`).
- CON-003: The UI is a single HTML page; no JavaScript frameworks or SPA patterns.
- CON-004: The app uses standard HTML form POSTs; no AJAX or fetch API calls.
- CON-005: No database migration tooling (e.g., Alembic) — the app handles its own initialization inline.

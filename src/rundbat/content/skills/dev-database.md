# dev-database

Quick local dev database via `docker run` — no compose needed. For fast
iteration when you just need a database connection string.

## When to use

- "I need a dev database"
- "Give me a Postgres/MariaDB/Redis for development"
- "Set up a local database"

## Steps

1. Check if environment already exists:
   ```bash
   rundbat health dev --json
   ```
   If healthy, just return the config:
   ```bash
   rundbat get-config dev --json
   ```

2. If no environment exists, create one:
   ```bash
   rundbat create-env dev --json
   ```
   This generates credentials, allocates a port, starts a container,
   and saves the connection string to dotconfig.

3. Return the connection string to the developer:
   ```bash
   rundbat get-config dev --json
   ```
   Parse the JSON output to get `database.connection_string`.

## Auto-recovery

`rundbat get-config` handles stale state automatically:
- Container stopped → auto-restarts
- Container missing → recreates (warns about data loss)
- Port conflict → allocates new port

## Supported databases

- **Postgres** (default) — `docker run postgres:16`
- **MariaDB** — `docker run mariadb:11` (future)
- **Redis** — `docker run redis:7` (future)

Currently only Postgres is implemented. MariaDB and Redis support
will be added in a future sprint.

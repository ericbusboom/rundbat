---
status: done
sprint: '001'
tickets:
- 001-001
---

# Flask Counter App

A Flask web application with two buttons: one increments a counter stored
in PostgreSQL, the other increments a counter stored in Redis. The web
page displays both current counts and the two increment buttons.

## Application Components

- **Flask app** with a single page showing two counters and two buttons
  (Postgres increment, Redis increment)
- **PostgreSQL backend** storing a counter value in a table
- **Redis backend** storing a counter value as a key

## Deployments

### dev (development)
- Flask runs directly on the host (not in Docker)
- PostgreSQL runs in local Docker (via rundbat)
- Redis runs in local Docker (via rundbat)

### test
- All three services (Flask, PostgreSQL, Redis) run in local Docker
- Flask is containerized with a Dockerfile

### prod (production)
- All three services (Flask, PostgreSQL, Redis) run in remote Docker
  accessed via SSH
- Full containerized deployment to a remote host

## Key Requirements

- Use rundbat for all database/container provisioning and environment
  management
- Use dotconfig for all configuration (connection strings, secrets)
- Each deployment reads its config from the appropriate dotconfig
  environment
- The Flask app should be a simple, single-file application with Jinja
  templates
- PostgreSQL table: a single row with an integer counter
- Redis key: a simple integer counter value

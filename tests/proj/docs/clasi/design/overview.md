---
project: Flask Counter App
version: 1.0.0
date: 2026-04-07
---

# Flask Counter App

## What It Is

A minimal Flask web application that demonstrates dual-backend counter
management. A single web page presents two counters and two increment
buttons — one counter persisted in PostgreSQL, one in Redis.

## Why It Exists

This project serves as a reference implementation for the rundbat
deployment workflow. It exercises the full rundbat lifecycle across three
environments (dev, test, prod), demonstrating how a real application uses
rundbat for container provisioning and dotconfig for configuration
management.

## What It Does

- Displays a live page showing the current PostgreSQL counter value and
  the current Redis counter value.
- Increments the PostgreSQL counter when the user clicks the Postgres
  button.
- Increments the Redis counter when the user clicks the Redis button.
- Reads all connection strings and secrets from dotconfig at startup.

## Technology Stack

- **Web framework:** Flask (Python), single-file app with Jinja2 templates
- **Relational store:** PostgreSQL — one table, one row, one integer column
- **Cache store:** Redis — one key, integer value
- **Container management:** rundbat
- **Configuration:** dotconfig + SOPS

## Deployment Environments

| Environment | Flask | PostgreSQL | Redis |
|---|---|---|---|
| dev | host process | local Docker (rundbat) | local Docker (rundbat) |
| test | local Docker | local Docker (rundbat) | local Docker (rundbat) |
| prod | remote Docker (SSH) | remote Docker (SSH) | remote Docker (SSH) |

## Key Constraints

- The Flask app is a single Python file. No application framework beyond Flask.
- All configuration (database URLs, Redis URL, secrets) flows through dotconfig.
- rundbat owns all Docker container lifecycle; the app never calls Docker directly.
- PostgreSQL schema is a single table with a single counter row.
- Redis schema is a single key holding an integer string.

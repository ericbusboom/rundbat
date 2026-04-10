---
status: active
---

# Project Overview

## Project Name

rundbat — Deployment Expert

## Problem Statement

Deploying Docker-based applications requires repetitive scaffolding:
Dockerfiles, compose files, secret management, and remote deployment
orchestration. Developers waste time writing boilerplate and
troubleshooting environment-specific issues. rundbat automates this
as a CLI tool with Claude Code integration via skills and agents.

## Target Users

Developers deploying Docker-based web applications to remote servers,
particularly in environments using Caddy as a reverse proxy and
dotconfig/SOPS for secret management.

## Key Constraints

- Python CLI tool distributed via PyPI
- Must work with existing dotconfig infrastructure
- Supports Node.js and Python frameworks
- Remote deployment via SSH and Docker contexts

## High-Level Requirements

- Auto-detect project framework and generate Docker artifacts
- Manage deployment targets with platform-aware build strategies
- Provision and manage database environments
- Encrypt/decrypt secrets via dotconfig integration
- Provide Claude Code skills for guided deployment workflows

## Technology Stack

- Python 3.12+, managed with uv
- Docker / Docker Compose for containerization
- dotconfig + SOPS/age for secret management
- Caddy for reverse proxy (on remote hosts)
- pytest for testing

## Sprint Roadmap

| Sprint | Title | Status |
|--------|-------|--------|
| 001 | CLI Plugin Conversion and Docker Skills | done |
| 002 | Docker Directory Generation | done |
| 003 | Remove Stale MCP References | done |
| 004 | Remote Deploy Command | done |
| 005 | Slim CLI Surface | done |
| 006 | Astro Support and Caddy Probe | planned |

## Out of Scope

- SSR/hybrid Astro deployments (static only for now)
- Kubernetes or non-Docker orchestration
- CI/CD pipeline generation beyond GitHub Actions

---
id: '006'
title: Astro Support and Caddy Probe
status: done
branch: sprint/006-astro-support-and-caddy-probe
use-cases:
- SUC-001
- SUC-002
- SUC-003
todos:
- plan-astro-static-site-docker-deployment-skill.md
- plan-auto-detect-caddy-and-include-labels-in-docker-compose.md
- plan-remote-docker-host-probe-reverse-proxy-detection.md
---

# Sprint 006: Astro Support and Caddy Probe

## Goals

1. Add Astro static site framework support to Docker artifact generation.
2. Add `detect_caddy()` to discovery and a `rundbat probe <deployment>` CLI
   command that saves reverse proxy info to `rundbat.yaml`.
3. Auto-probe during `deploy-init`; warn on `init-docker` when Caddy is
   detected but no hostname is set.
4. Ship updated skill files and tests covering all new behavior.

## Problem

rundbat supports Node (Next, Express) and Python frameworks but not Astro
static sites. Astro requires a multi-stage build ending in nginx — not a
running Node process — so it needs its own Dockerfile template, nginx config,
and port (8080, non-root).

Separately, Caddy labels are generated in docker-compose only when a hostname
is present, but `init-docker` often runs before `deploy-init`, so there is no
hostname and no labels. There is no mechanism for the tool to learn whether the
remote host runs Caddy.

## Solution

- Extend `detect_framework()` to recognise Astro, add a 3-stage
  `_DOCKERFILE_ASTRO` template, a `generate_nginx_conf()` helper, port 8080
  handling in compose and .env.example, nginx.conf output in `init_docker()`.
- Add `detect_caddy(context)` to `discovery.py` using `docker --context ps`.
- Add `rundbat probe <name>` CLI command that runs detection and persists
  `reverse_proxy: caddy|none` into the deployment entry in `rundbat.yaml`.
- Auto-call `detect_caddy` in `init_deployment()` (deploy.py) so deploy-init
  always probes.
- In `cmd_init_docker` add `--hostname` flag and warn when a deployment has
  `reverse_proxy: caddy` but no hostname is set.
- Write `astro-docker.md` skill file; update `init-docker.md` with Caddy
  guidance.

## Success Criteria

- `detect_framework()` returns `{language: "node", framework: "astro",
  entry_point: "nginx"}` for projects with an `astro` dependency.
- `init_docker()` on an Astro project produces a 3-stage Dockerfile,
  `docker/nginx.conf`, and compose with port 8080.
- `rundbat probe prod` detects Caddy on the remote context and persists
  `reverse_proxy: caddy` to `rundbat.yaml`.
- `rundbat deploy-init` automatically stores the `reverse_proxy` field.
- `rundbat init-docker` warns when a deployment has Caddy but no hostname is
  provided; `--hostname` flag produces Caddy labels in compose.
- `uv run pytest` passes with all new tests.

## Scope

### In Scope

- Astro static site detection, multi-stage Dockerfile, nginx config generator
- Port 8080 handling for Astro in compose and .env.example
- `detect_caddy(context)` in discovery.py
- `rundbat probe <name>` CLI subcommand
- Auto-probe in `init_deployment()`
- `--hostname` flag on `init-docker`; Caddy warning in `cmd_init_docker`
- Skill files: `astro-docker.md` (new), `init-docker.md` (updated)
- Unit tests for all new behavior

### Out of Scope

- SSR/hybrid Astro deployments
- Detecting reverse proxies other than Caddy
- Any changes to database, secret management, or CI/CD generation

## Test Strategy

All new logic is unit-tested with mocked subprocess calls. Key areas:

- `test_generators.py`: Astro detection, Dockerfile template, nginx conf,
  port handling, `init_docker` writing nginx.conf
- `test_discovery.py`: `detect_caddy` running/not-running, context flag
- `test_cli.py`: `probe` command saves reverse_proxy; `init-docker` warning
  path and `--hostname` flag path
- `test_deploy.py`: `init_deployment` calls `detect_caddy` and saves field

## Architecture Notes

- `detect_caddy` requires a context (remote-only); no local detection.
- The `reverse_proxy` field in `rundbat.yaml` is the single source of truth
  for proxy type — written by probe/deploy-init, read by init-docker.
- TODO 2 (auto-detect Caddy in compose) is subsumed by TODO 3 (the probe
  approach). The probe + persist pattern is preferred over live detection
  at init-docker time.
- Astro nginx.conf uses port 8080 to remain non-root compatible.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Caddy detection and probe command | — | 1 |
| 002 | init-docker hostname flag and Caddy warning | 001 | 2 |
| 003 | Astro framework support in generators | 001 | 2 |
| 004 | Skill files — astro-docker.md and init-docker.md update | 002, 003 | 3 |
| 005 | Tests | 001, 002, 003 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).

---
id: '004'
title: "Skill files \u2014 astro-docker.md and init-docker.md update"
status: done
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

# Skill files — astro-docker.md and init-docker.md update

## Description

Create `src/rundbat/content/skills/astro-docker.md` (new) and update
`src/rundbat/content/skills/init-docker.md` with Caddy/hostname guidance.
These are the developer-facing instructions that Claude reads when assisting
with deployments; they must reflect all behavior introduced in tickets 001-003.

The installer auto-discovers all `.md` files in `content/skills/`, so no
installer changes are needed.

## Acceptance Criteria

- [x] `src/rundbat/content/skills/astro-docker.md` exists with when-to-use triggers, prerequisites, step-by-step guide, and notes.
- [x] `astro-docker.md` includes a step to run `rundbat init-docker` and review both `docker/Dockerfile` and `docker/nginx.conf`.
- [x] `astro-docker.md` notes that Caddy labels require `--hostname` and references `rundbat probe`.
- [x] `astro-docker.md` notes that SSR/hybrid Astro is out of scope.
- [x] `src/rundbat/content/skills/init-docker.md` has a new note: if `reverse_proxy: caddy` appears in any deployment, pass `--hostname` to include Caddy labels.
- [x] `init-docker.md` references `rundbat probe <name>` as the way to populate `reverse_proxy`.

## Implementation Plan

### Files to Create

**`src/rundbat/content/skills/astro-docker.md`**

Follow the format of existing skills (see `deploy-setup.md`, `init-docker.md`).
Structure:

```markdown
# astro-docker

Use this skill when the user wants to deploy an Astro site, containerize an
Astro project, or asks about Docker + Astro.

## Prerequisites

- `rundbat.yaml` exists in the project root (`rundbat init` if missing).
- `package.json` lists `astro` as a dependency.

## Steps

1. Run `rundbat init-docker` to generate Docker artifacts.
2. Review `docker/Dockerfile` — verify 3-stage build (deps, build, nginx).
3. Review `docker/nginx.conf` — adjust `server_name` or base path if needed.
4. If deploying behind Caddy, run `rundbat probe <deployment>` first, then
   re-run `rundbat init-docker --hostname <your-hostname>` to include labels.
5. Test locally: `docker compose -f docker/docker-compose.yml up --build`.
6. Deploy: follow the deploy-setup skill.

## Notes

- Port 8080 is used (non-root nginx).
- SSR/hybrid Astro is not supported — static output only (`output: "static"`
  in `astro.config.*`).
- The nginx config includes SPA routing fallback (`try_files`) and asset
  caching headers.
```

### Files to Modify

**`src/rundbat/content/skills/init-docker.md`**

Read the current file first. Add a Caddy section after the main steps. Content:

```
## Caddy Reverse Proxy

If your deployment target runs Caddy, include reverse proxy labels in the
compose file:

1. Run `rundbat probe <deployment>` to detect Caddy and save the result.
2. Re-run `rundbat init-docker --hostname <your-hostname>` to include labels.

If `reverse_proxy: caddy` is already in your deployment config but you haven't
provided `--hostname`, rundbat will print a reminder.
```

### Testing Plan

Skill files are plain text/markdown — no automated tests needed. Verify:

- `rundbat install` copies both skills to `.claude/skills/rundbat/`.
- The skill content is readable and accurate against the implemented behavior.

### Documentation Updates

These files ARE the documentation for this sprint.

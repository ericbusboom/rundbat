---
status: done
---

# Docker best-practices pass for rundbat templates and skills

## Context

The user asked me to review [Docker's Build Best Practices guide](https://docs.docker.com/build/building/best-practices/) against the rundbat project's skill docs and the Dockerfile templates they describe. Goal: close real gaps so that what `rundbat generate` emits, and what the `.claude/skills/rundbat/*.md` docs teach agents, both reflect current Docker guidance.

### What the audit found

Strong areas in the current templates ([`src/rundbat/generators.py`](src/rundbat/generators.py)):

- Multi-stage builds for Node and Astro, named stages (`AS builder`, `AS deps`, `AS build`)
- Dependency-first layer ordering (`package*.json` / `requirements*.txt` before `COPY . .`)
- `ENV NODE_ENV=production`, `WORKDIR /app` absolute paths, `CMD` exec form everywhere
- `.dockerignore` excludes `.git`, `node_modules`, `.claude/`, tests, `.env`, build artifacts
- Compose services have `healthcheck:` blocks for postgres/mariadb/redis
- `COPY`, never `ADD`

Gaps worth fixing (limited to High+Medium priority per user):

1. **No non-root `USER` in any app Dockerfile template** — `_DOCKERFILE_NODE` (generators.py:63–79), `_DOCKERFILE_PYTHON` (generators.py:81–93), and `_DOCKERFILE_ASTRO` (generators.py:95–115) all run as root.
2. **No `HEALTHCHECK` directive in app Dockerfiles** — only DB services get health checks, via compose.
3. **Python template is single-stage** — build tools and pip caches persist into the runtime image.
4. **No BuildKit cache mounts** — every `npm ci` / `pip install` redownloads on every build; a `RUN --mount=type=cache,...` + `# syntax=docker/dockerfile:1` header would cache across builds.
5. **Skills don't reflect any of the above** — `init-docker.md`, `astro-docker.md`, `generate.md` describe the templates but omit these practices, and there is no dedicated best-practices skill agents can reference.

Explicitly **out of scope** (user chose High+Medium, not Everything): pinning base images by SHA256 digest, generating OCI `LABEL` metadata, and adding `dumb-init`/`tini`. These can be a follow-up.

## Approach

Update the generator templates to meet Docker's High/Medium recommendations, then revise the skill docs so they describe what the generator actually emits and add one new skill that explicitly maps to Docker's checklist.

### Template changes — [`src/rundbat/generators.py`](src/rundbat/generators.py)

Add `# syntax=docker/dockerfile:1` to every generated Dockerfile (enables cache mounts under BuildKit, which is the default on modern Docker).

**`_DOCKERFILE_NODE`** (lines 63–79):

- Add `RUN --mount=type=cache,target=/root/.npm npm ci` in the builder stage.
- Production stage: `USER node` (the `node` user is shipped in the official `node` image at UID 1000).
- Update the `{copy_step}` strings in `generate_dockerfile()` at lines 164–174 to use `COPY --chown=node:node --from=builder ...` so files are owned by the runtime user.
- Add `HEALTHCHECK` using Node's stdlib (no extra tooling):
  ```
  HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
      CMD node -e "require('http').get('http://localhost:'+(process.env.PORT||3000), r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"
  ```

**`_DOCKERFILE_PYTHON`** (lines 81–93) — convert to multi-stage:

- Builder stage: `python:3.12-slim AS builder`, create `/opt/venv`, install deps into it with a pip cache mount:
  ```
  RUN --mount=type=cache,target=/root/.cache/pip \
      pip install -r requirements.txt 2>/dev/null \
      || pip install . 2>/dev/null \
      || true
  ```
- Runtime stage: `python:3.12-slim`, `COPY --from=builder /opt/venv /opt/venv`, set `PATH="/opt/venv/bin:$PATH"`, `RUN adduser --system --no-create-home --uid 1000 appuser`, `COPY --chown=appuser . .`, run `{extra_step}` (e.g. Django `collectstatic`) as root before switching, then `USER appuser`.
- `HEALTHCHECK` via urllib (no extra packages):
  ```
  HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
      CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/',timeout=3)" || exit 1
  ```

**`_DOCKERFILE_ASTRO`** (lines 95–115):

- Add `RUN --mount=type=cache,target=/root/.npm npm ci` in the deps stage.
- Switch runtime base from `nginx:alpine` to `nginxinc/nginx-unprivileged:alpine` (runs as UID 101, already matches the existing `listen 8080` in `generate_nginx_conf()` so no other changes needed).
- Add `HEALTHCHECK CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1` (wget is in the alpine image).

`generate_nginx_conf()` at lines 118–151 does **not** need changes — port 8080 already works for nginx-unprivileged, SPA fallback and security headers are already good.

### Skills changes — [`src/rundbat/content/skills/`](src/rundbat/content/skills/)

All of these live under `src/rundbat/content/skills/` and get copied to `.claude/skills/rundbat/*.md` by [`installer.install()`](src/rundbat/installer.py) (no installer changes needed — the install-map already walks that directory, see [`_install_map()`](src/rundbat/installer.py)).

- **New file `docker-best-practices.md`** — single-page checklist mapped to Docker's guide, grouped by Caching/Size/Security/Signal handling/Multi-stage, with short "how rundbat does this" notes next to each item. This is the single reference agents should read when asked "is this Dockerfile OK?".
- **`astro-docker.md`** — replace the "Runtime: nginx:alpine" note with "nginx-unprivileged (UID 101)"; add a bullet that the template now emits a `HEALTHCHECK` and why the healthcheck target is `/` through nginx.
- **`init-docker.md`** — add a short "What you get" section enumerating: multi-stage, non-root USER, HEALTHCHECK, BuildKit cache mounts. Point readers at the new `docker-best-practices.md`.
- **`generate.md`** — add one line: "Re-run `rundbat generate` to pick up template improvements when rundbat is upgraded."

### Agent doc — [`src/rundbat/content/agents/deployment-expert.md`](src/rundbat/content/agents/deployment-expert.md)

Add one bullet in the "Capabilities" list: "Emits hardened Dockerfiles (multi-stage, non-root USER, HEALTHCHECK, BuildKit cache mounts) — see the `docker-best-practices` skill."

### Tests — [`tests/unit/test_generators.py`](tests/unit/test_generators.py)

Read the existing assertions first; then add/adjust so each generator test verifies:

- `# syntax=docker/dockerfile:1` present
- `USER node` / `USER appuser` / `nginx-unprivileged` present in the appropriate template
- `HEALTHCHECK` line present
- `--mount=type=cache` present in the relevant `RUN` line
- Multi-stage marker `FROM python:3.12-slim AS builder` present for Python

The existing tests that check for specific strings in templates (e.g. `FROM node:20-alpine`, `FROM python:3.12-slim`) should still pass — the base images don't change.

### Version — [`pyproject.toml`](pyproject.toml)

Bump to `0.20260424.4` (per the project's "bump version after every code change" rule).

## Files to touch

| Path | Change |
|---|---|
| `src/rundbat/generators.py` | Edit `_DOCKERFILE_NODE`, `_DOCKERFILE_PYTHON`, `_DOCKERFILE_ASTRO`, and the `copy_step` strings in `generate_dockerfile()` |
| `src/rundbat/content/skills/docker-best-practices.md` | New file |
| `src/rundbat/content/skills/astro-docker.md` | Small edits |
| `src/rundbat/content/skills/init-docker.md` | Small edits |
| `src/rundbat/content/skills/generate.md` | One-line addition |
| `src/rundbat/content/agents/deployment-expert.md` | One-line addition |
| `tests/unit/test_generators.py` | Update assertions |
| `pyproject.toml` | Version bump |

## Reuse notes

- `installer._install_map()` already globs every `*.md` under `content/skills/`, so the new `docker-best-practices.md` is picked up automatically — no install-map edit needed. `installed_paths_by_kind()` is the helper that feeds both `rundbat --instructions` and the CLAUDE.md block, so the new skill will appear in both without further changes.
- Compose-side healthchecks in `_DB_SERVICES` (generators.py:205–246) are fine as-is; the new app-side `HEALTHCHECK` complements them.
- The entrypoint script logic and Justfile templates are unchanged by this pass.

## Verification

1. `uv run pytest` — all 230 existing tests plus the updated generator assertions pass.
2. Render each template:
   ```
   uv run python -c "from rundbat.generators import generate_dockerfile as g; print(g({'language':'python','framework':'django'}))"
   uv run python -c "from rundbat.generators import generate_dockerfile as g; print(g({'language':'node','framework':'next'}))"
   uv run python -c "from rundbat.generators import generate_dockerfile as g; print(g({'framework':'astro'}))"
   ```
   Confirm `USER`, `HEALTHCHECK`, `# syntax=`, and cache mounts appear correctly.
3. Build-smoke the generated Python template against a throwaway FastAPI app in `/tmp`:
   ```
   docker build -t rundbat-smoke /tmp/smoke_app
   docker run --rm -d -p 8000:8000 --name smoke rundbat-smoke
   docker inspect --format '{{.State.Health.Status}}' smoke
   docker rm -f smoke
   ```
   Expect `Status: healthy` after ~15s, and `id -u` inside the container to report `1000`, not `0`.
4. `uv run rundbat --instructions | grep docker-best-practices` — confirms the new skill is listed in the installed-integration section.
5. In a scratch dir, `uv run rundbat init` and confirm the CLAUDE.md block's "Reference files" section lists `docker-best-practices.md`.

---
id: '003'
title: Astro framework support in generators
status: done
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
todo: plan-astro-static-site-docker-deployment-skill.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Astro framework support in generators

## Description

Add full Astro static site support to `generators.py`: framework detection,
a 3-stage Dockerfile template (node deps → node build → nginx serve), an
nginx config generator, port 8080 handling in compose and .env.example, and
`docker/nginx.conf` output in `init_docker()`.

Depends on ticket 001 because the Astro Caddy labels rely on port 8080 being
correctly threaded through `generate_compose()`, which also reads from the
probe result (via `hostname`).

## Acceptance Criteria

- [x] `detect_framework()` returns `{language: "node", framework: "astro", entry_point: "nginx"}` when `package.json` has `"astro"` in dependencies or devDependencies.
- [x] Astro is detected before the generic Node fallback (detection order: next, express, astro, node).
- [x] `_DOCKERFILE_ASTRO` module-level constant exists with 3 stages: deps (`node:20-alpine`), build (`node:20-alpine` + `npm run build`), runtime (`nginx:alpine` exposing port 8080 and copying `docker/nginx.conf`).
- [x] `generate_dockerfile()` returns `_DOCKERFILE_ASTRO` for `fw == "astro"`.
- [x] `generate_nginx_conf()` function exists and returns a string containing `listen 8080`, `try_files $uri $uri/ /index.html`, gzip directives, and security headers.
- [x] `generate_compose()` uses port 8080 when `framework.get("framework") == "astro"`.
- [x] `generate_env_example()` uses port 8080 for Astro and omits `NODE_ENV`.
- [x] `init_docker()` writes `docker/nginx.conf` when framework is Astro and includes it in the returned generated-files list.

## Implementation Plan

### Approach

All changes are in `generators.py`. Work top-to-bottom: detection, template
constant, nginx conf function, generate_dockerfile branch, port handling in
two functions, init_docker wiring.

### Files to Modify

**`src/rundbat/generators.py`**

1. In `detect_framework()`, after the Express check (line 30), before the
   generic Node return (line 31):

```python
if "astro" in deps:
    return {"language": "node", "framework": "astro", "entry_point": "nginx"}
```

2. Add `_DOCKERFILE_ASTRO` constant after `_DOCKERFILE_PYTHON` (~line 90):

```python
_DOCKERFILE_ASTRO = """\
# --- Deps stage ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# --- Build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Runtime stage ---
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
"""
```

3. Add `generate_nginx_conf()` function after the Dockerfile constants:

```python
def generate_nginx_conf() -> str:
    """Generate a minimal production nginx config for Astro static sites."""
    return """\
server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache hashed assets for 1 year
    location ~* \\.[0-9a-f]{8}\\.(js|css)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # No-cache on HTML
    location ~* \\.html$ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
}
"""
```

4. In `generate_dockerfile()`, add before `if lang == "node":`:

```python
if fw == "astro":
    return _DOCKERFILE_ASTRO
```

5. In `generate_compose()`, replace `port = "3000" if lang == "node" else "8000"` with:

```python
fw = framework.get("framework", "")
if fw == "astro":
    port = "8080"
elif lang == "node":
    port = "3000"
else:
    port = "8000"
```

6. Apply the same three-way logic in `generate_env_example()`, and add:

```python
# Skip NODE_ENV for Astro (nginx does not use it)
if fw != "astro":
    lines.append("NODE_ENV=production")
```

7. In `init_docker()`, after writing the Dockerfile, add:

```python
if framework.get("framework") == "astro":
    nginx_conf = docker_dir / "nginx.conf"
    nginx_conf.write_text(generate_nginx_conf())
    generated.append(str(nginx_conf.relative_to(project_dir)))
```

### Testing Plan

See ticket 005 for full test implementations. This ticket's code must support:

- `test_detect_framework_astro`
- `test_generate_dockerfile_astro`
- `test_generate_nginx_conf`
- `test_generate_compose_astro_port`
- `test_generate_env_example_astro_port_no_node_env`
- `test_init_docker_astro_writes_nginx_conf`

### Documentation Updates

None in this ticket. Skill file for Astro is in ticket 004.

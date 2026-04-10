---
status: done
sprint: '006'
tickets:
- 006-003
- 006-004
---

# Plan: Astro Static Site Docker Deployment Skill

## Context

rundbat auto-detects project frameworks and generates Docker artifacts (Dockerfile, compose, Justfile, .env.example). It currently supports Node (Next, Express) and Python (Django, FastAPI, Flask) but not Astro. Astro static sites are fundamentally different from dynamic Node apps — the production image needs nginx to serve pre-built files, not a Node runtime. This requires a new Dockerfile template and an nginx config generator.

## Changes

### 1. Framework detection — `src/rundbat/generators.py:26-31`

Add Astro detection before the generic Node fallback in `detect_framework()`:

```python
if "astro" in deps:
    return {"language": "node", "framework": "astro", "entry_point": "nginx"}
```

Insert after the Express check (line 30), before the generic return (line 31).

### 2. New Dockerfile template — `src/rundbat/generators.py`

Add `_DOCKERFILE_ASTRO` as a new module-level constant (separate from `_DOCKERFILE_NODE` since the production stage is nginx, not node):

- **Stage 1 (deps)**: `node:20-alpine`, copy package files, `npm ci`
- **Stage 2 (build)**: Copy source, `RUN npm run build` → produces `dist/`
- **Stage 3 (runtime)**: `nginx:alpine`, copy `dist/` from build stage, copy `docker/nginx.conf`, expose 8080

### 3. Nginx config generator — `src/rundbat/generators.py`

Add `generate_nginx_conf() -> str` function producing a minimal production config:
- Listen on port 8080 (non-root)
- Serve from `/usr/share/nginx/html`
- `try_files $uri $uri/ /index.html` for client-side routing fallback
- Gzip on common types
- Cache hashed assets (`*.[hash].js/css`) for 1 year with `immutable`
- No-cache on `index.html`
- Basic security headers (X-Frame-Options, X-Content-Type-Options)

### 4. Wire up in `generate_dockerfile()` — `src/rundbat/generators.py:93-134`

Add `if fw == "astro": return _DOCKERFILE_ASTRO` branch before the existing node handling.

### 5. Port handling — `src/rundbat/generators.py:194,390`

Two locations hardcode `port = "3000" if lang == "node"`. Update both `generate_compose()` and `generate_env_example()`:

```python
if framework.get("framework") == "astro":
    port = "8080"
elif lang == "node":
    port = "3000"
else:
    port = "8000"
```

Also in `generate_env_example()`, skip the `NODE_ENV` line for Astro (nginx doesn't use it).

### 6. Write nginx.conf in `init_docker()` — `src/rundbat/generators.py:594-618`

After writing the Dockerfile, if framework is Astro, also write `docker/nginx.conf`:

```python
if framework.get("framework") == "astro":
    nginx_conf = docker_dir / "nginx.conf"
    nginx_conf.write_text(generate_nginx_conf())
    generated.append(str(nginx_conf.relative_to(project_dir)))
```

### 7. New skill file — `src/rundbat/content/skills/astro-docker.md`

Create following the existing skill format (see `init-docker.md`, `deploy-setup.md`):
- **When to use**: "Deploy an Astro site", "Containerize my Astro project"
- **Prerequisites**: `rundbat.yaml` exists, `package.json` has `astro` dependency
- **Steps**: Run `rundbat init-docker`, review Dockerfile + nginx.conf, customize if needed (base path, custom outDir), test locally, deploy
- **Notes**: Static-only for now; SSR/hybrid support planned for later

### 8. Tests — `tests/unit/test_generators.py`

Add test cases:
- `test_detect_framework_astro`: Mock `package.json` with astro dep → returns `{language: "node", framework: "astro", entry_point: "nginx"}`
- `test_generate_dockerfile_astro`: Verify output contains `nginx:alpine`, `COPY --from=build /app/dist`, `EXPOSE 8080`
- `test_generate_nginx_conf`: Verify output contains `listen 8080`, `try_files`, gzip directives
- `test_generate_compose_astro_port`: Verify compose uses port 8080 for Astro framework
- `test_init_docker_astro_writes_nginx_conf`: Verify `docker/nginx.conf` is created for Astro projects

## Files to modify

| File | Action |
|------|--------|
| `src/rundbat/generators.py` | Add Astro detection, template, nginx conf generator, port handling, init_docker wiring |
| `src/rundbat/content/skills/astro-docker.md` | Create new skill file |
| `tests/unit/test_generators.py` | Add Astro test cases |

## No changes needed

- **Installer** (`installer.py`): Auto-discovers all `.md` files in `content/skills/`
- **.dockerignore**: Already excludes `dist/`, `node_modules/`, `.git/`
- **Deploy module** (`deploy.py`): Works with any framework — no Astro-specific logic needed

## Verification

1. Run `uv run pytest tests/unit/test_generators.py` — all new tests pass
2. Create a temp dir with a mock Astro `package.json`, run `init_docker()`, verify:
   - `docker/Dockerfile` has 3-stage build with nginx
   - `docker/nginx.conf` exists with correct config
   - `docker/docker-compose.yml` uses port 8080
   - `.env.example` uses port 8080
3. `rundbat install` copies the new skill to `.claude/skills/rundbat/astro-docker.md`


---

## Hook Debug Info

```json
{
  "hook_payload": {
    "session_id": "06168813-e061-4c02-9bfa-5482325c19db",
    "transcript_path": "/Users/eric/.claude/projects/-Users-eric-proj-ai-project-rundbat/06168813-e061-4c02-9bfa-5482325c19db.jsonl",
    "cwd": "/Users/eric/proj/ai-project/rundbat",
    "permission_mode": "default",
    "hook_event_name": "PostToolUse",
    "tool_name": "ExitPlanMode",
    "tool_input": {
      "allowedPrompts": [
        {
          "tool": "Bash",
          "prompt": "run tests with uv run pytest"
        }
      ],
      "plan": "# Plan: Astro Static Site Docker Deployment Skill\n\n## Context\n\nrundbat auto-detects project frameworks and generates Docker artifacts (Dockerfile, compose, Justfile, .env.example). It currently supports Node (Next, Express) and Python (Django, FastAPI, Flask) but not Astro. Astro static sites are fundamentally different from dynamic Node apps \u2014 the production image needs nginx to serve pre-built files, not a Node runtime. This requires a new Dockerfile template and an nginx config generator.\n\n## Changes\n\n### 1. Framework detection \u2014 `src/rundbat/generators.py:26-31`\n\nAdd Astro detection before the generic Node fallback in `detect_framework()`:\n\n```python\nif \"astro\" in deps:\n    return {\"language\": \"node\", \"framework\": \"astro\", \"entry_point\": \"nginx\"}\n```\n\nInsert after the Express check (line 30), before the generic return (line 31).\n\n### 2. New Dockerfile template \u2014 `src/rundbat/generators.py`\n\nAdd `_DOCKERFILE_ASTRO` as a new module-level constant (separate from `_DOCKERFILE_NODE` since the production stage is nginx, not node):\n\n- **Stage 1 (deps)**: `node:20-alpine`, copy package files, `npm ci`\n- **Stage 2 (build)**: Copy source, `RUN npm run build` \u2192 produces `dist/`\n- **Stage 3 (runtime)**: `nginx:alpine`, copy `dist/` from build stage, copy `docker/nginx.conf`, expose 8080\n\n### 3. Nginx config generator \u2014 `src/rundbat/generators.py`\n\nAdd `generate_nginx_conf() -> str` function producing a minimal production config:\n- Listen on port 8080 (non-root)\n- Serve from `/usr/share/nginx/html`\n- `try_files $uri $uri/ /index.html` for client-side routing fallback\n- Gzip on common types\n- Cache hashed assets (`*.[hash].js/css`) for 1 year with `immutable`\n- No-cache on `index.html`\n- Basic security headers (X-Frame-Options, X-Content-Type-Options)\n\n### 4. Wire up in `generate_dockerfile()` \u2014 `src/rundbat/generators.py:93-134`\n\nAdd `if fw == \"astro\": return _DOCKERFILE_ASTRO` branch before the existing node handling.\n\n### 5. Port handling \u2014 `src/rundbat/generators.py:194,390`\n\nTwo locations hardcode `port = \"3000\" if lang == \"node\"`. Update both `generate_compose()` and `generate_env_example()`:\n\n```python\nif framework.get(\"framework\") == \"astro\":\n    port = \"8080\"\nelif lang == \"node\":\n    port = \"3000\"\nelse:\n    port = \"8000\"\n```\n\nAlso in `generate_env_example()`, skip the `NODE_ENV` line for Astro (nginx doesn't use it).\n\n### 6. Write nginx.conf in `init_docker()` \u2014 `src/rundbat/generators.py:594-618`\n\nAfter writing the Dockerfile, if framework is Astro, also write `docker/nginx.conf`:\n\n```python\nif framework.get(\"framework\") == \"astro\":\n    nginx_conf = docker_dir / \"nginx.conf\"\n    nginx_conf.write_text(generate_nginx_conf())\n    generated.append(str(nginx_conf.relative_to(project_dir)))\n```\n\n### 7. New skill file \u2014 `src/rundbat/content/skills/astro-docker.md`\n\nCreate following the existing skill format (see `init-docker.md`, `deploy-setup.md`):\n- **When to use**: \"Deploy an Astro site\", \"Containerize my Astro project\"\n- **Prerequisites**: `rundbat.yaml` exists, `package.json` has `astro` dependency\n- **Steps**: Run `rundbat init-docker`, review Dockerfile + nginx.conf, customize if needed (base path, custom outDir), test locally, deploy\n- **Notes**: Static-only for now; SSR/hybrid support planned for later\n\n### 8. Tests \u2014 `tests/unit/test_generators.py`\n\nAdd test cases:\n- `test_detect_framework_astro`: Mock `package.json` with astro dep \u2192 returns `{language: \"node\", framework: \"astro\", entry_point: \"nginx\"}`\n- `test_generate_dockerfile_astro`: Verify output contains `nginx:alpine`, `COPY --from=build /app/dist`, `EXPOSE 8080`\n- `test_generate_nginx_conf`: Verify output contains `listen 8080`, `try_files`, gzip directives\n- `test_generate_compose_astro_port`: Verify compose uses port 8080 for Astro framework\n- `test_init_docker_astro_writes_nginx_conf`: Verify `docker/nginx.conf` is created for Astro projects\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/generators.py` | Add Astro detection, template, nginx conf generator, port handling, init_docker wiring |\n| `src/rundbat/content/skills/astro-docker.md` | Create new skill file |\n| `tests/unit/test_generators.py` | Add Astro test cases |\n\n## No changes needed\n\n- **Installer** (`installer.py`): Auto-discovers all `.md` files in `content/skills/`\n- **.dockerignore**: Already excludes `dist/`, `node_modules/`, `.git/`\n- **Deploy module** (`deploy.py`): Works with any framework \u2014 no Astro-specific logic needed\n\n## Verification\n\n1. Run `uv run pytest tests/unit/test_generators.py` \u2014 all new tests pass\n2. Create a temp dir with a mock Astro `package.json`, run `init_docker()`, verify:\n   - `docker/Dockerfile` has 3-stage build with nginx\n   - `docker/nginx.conf` exists with correct config\n   - `docker/docker-compose.yml` uses port 8080\n   - `.env.example` uses port 8080\n3. `rundbat install` copies the new skill to `.claude/skills/rundbat/astro-docker.md`\n",
      "planFilePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md"
    },
    "tool_response": {
      "plan": "# Plan: Astro Static Site Docker Deployment Skill\n\n## Context\n\nrundbat auto-detects project frameworks and generates Docker artifacts (Dockerfile, compose, Justfile, .env.example). It currently supports Node (Next, Express) and Python (Django, FastAPI, Flask) but not Astro. Astro static sites are fundamentally different from dynamic Node apps \u2014 the production image needs nginx to serve pre-built files, not a Node runtime. This requires a new Dockerfile template and an nginx config generator.\n\n## Changes\n\n### 1. Framework detection \u2014 `src/rundbat/generators.py:26-31`\n\nAdd Astro detection before the generic Node fallback in `detect_framework()`:\n\n```python\nif \"astro\" in deps:\n    return {\"language\": \"node\", \"framework\": \"astro\", \"entry_point\": \"nginx\"}\n```\n\nInsert after the Express check (line 30), before the generic return (line 31).\n\n### 2. New Dockerfile template \u2014 `src/rundbat/generators.py`\n\nAdd `_DOCKERFILE_ASTRO` as a new module-level constant (separate from `_DOCKERFILE_NODE` since the production stage is nginx, not node):\n\n- **Stage 1 (deps)**: `node:20-alpine`, copy package files, `npm ci`\n- **Stage 2 (build)**: Copy source, `RUN npm run build` \u2192 produces `dist/`\n- **Stage 3 (runtime)**: `nginx:alpine`, copy `dist/` from build stage, copy `docker/nginx.conf`, expose 8080\n\n### 3. Nginx config generator \u2014 `src/rundbat/generators.py`\n\nAdd `generate_nginx_conf() -> str` function producing a minimal production config:\n- Listen on port 8080 (non-root)\n- Serve from `/usr/share/nginx/html`\n- `try_files $uri $uri/ /index.html` for client-side routing fallback\n- Gzip on common types\n- Cache hashed assets (`*.[hash].js/css`) for 1 year with `immutable`\n- No-cache on `index.html`\n- Basic security headers (X-Frame-Options, X-Content-Type-Options)\n\n### 4. Wire up in `generate_dockerfile()` \u2014 `src/rundbat/generators.py:93-134`\n\nAdd `if fw == \"astro\": return _DOCKERFILE_ASTRO` branch before the existing node handling.\n\n### 5. Port handling \u2014 `src/rundbat/generators.py:194,390`\n\nTwo locations hardcode `port = \"3000\" if lang == \"node\"`. Update both `generate_compose()` and `generate_env_example()`:\n\n```python\nif framework.get(\"framework\") == \"astro\":\n    port = \"8080\"\nelif lang == \"node\":\n    port = \"3000\"\nelse:\n    port = \"8000\"\n```\n\nAlso in `generate_env_example()`, skip the `NODE_ENV` line for Astro (nginx doesn't use it).\n\n### 6. Write nginx.conf in `init_docker()` \u2014 `src/rundbat/generators.py:594-618`\n\nAfter writing the Dockerfile, if framework is Astro, also write `docker/nginx.conf`:\n\n```python\nif framework.get(\"framework\") == \"astro\":\n    nginx_conf = docker_dir / \"nginx.conf\"\n    nginx_conf.write_text(generate_nginx_conf())\n    generated.append(str(nginx_conf.relative_to(project_dir)))\n```\n\n### 7. New skill file \u2014 `src/rundbat/content/skills/astro-docker.md`\n\nCreate following the existing skill format (see `init-docker.md`, `deploy-setup.md`):\n- **When to use**: \"Deploy an Astro site\", \"Containerize my Astro project\"\n- **Prerequisites**: `rundbat.yaml` exists, `package.json` has `astro` dependency\n- **Steps**: Run `rundbat init-docker`, review Dockerfile + nginx.conf, customize if needed (base path, custom outDir), test locally, deploy\n- **Notes**: Static-only for now; SSR/hybrid support planned for later\n\n### 8. Tests \u2014 `tests/unit/test_generators.py`\n\nAdd test cases:\n- `test_detect_framework_astro`: Mock `package.json` with astro dep \u2192 returns `{language: \"node\", framework: \"astro\", entry_point: \"nginx\"}`\n- `test_generate_dockerfile_astro`: Verify output contains `nginx:alpine`, `COPY --from=build /app/dist`, `EXPOSE 8080`\n- `test_generate_nginx_conf`: Verify output contains `listen 8080`, `try_files`, gzip directives\n- `test_generate_compose_astro_port`: Verify compose uses port 8080 for Astro framework\n- `test_init_docker_astro_writes_nginx_conf`: Verify `docker/nginx.conf` is created for Astro projects\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/generators.py` | Add Astro detection, template, nginx conf generator, port handling, init_docker wiring |\n| `src/rundbat/content/skills/astro-docker.md` | Create new skill file |\n| `tests/unit/test_generators.py` | Add Astro test cases |\n\n## No changes needed\n\n- **Installer** (`installer.py`): Auto-discovers all `.md` files in `content/skills/`\n- **.dockerignore**: Already excludes `dist/`, `node_modules/`, `.git/`\n- **Deploy module** (`deploy.py`): Works with any framework \u2014 no Astro-specific logic needed\n\n## Verification\n\n1. Run `uv run pytest tests/unit/test_generators.py` \u2014 all new tests pass\n2. Create a temp dir with a mock Astro `package.json`, run `init_docker()`, verify:\n   - `docker/Dockerfile` has 3-stage build with nginx\n   - `docker/nginx.conf` exists with correct config\n   - `docker/docker-compose.yml` uses port 8080\n   - `.env.example` uses port 8080\n3. `rundbat install` copies the new skill to `.claude/skills/rundbat/astro-docker.md`\n",
      "isAgent": false,
      "filePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md",
      "planWasEdited": true
    },
    "tool_use_id": "toolu_01SyqiRP2VJYnJ4xkzGnKiA1"
  },
  "env": {
    "TOOL_INPUT": "",
    "TOOL_NAME": "",
    "SESSION_ID": "",
    "CLASI_AGENT_TIER": "",
    "CLASI_AGENT_NAME": "",
    "CLAUDE_PROJECT_DIR": "/Users/eric/proj/ai-project/rundbat",
    "PWD": "/Users/eric/proj/ai-project/rundbat",
    "CWD": ""
  },
  "plans_dir": "/Users/eric/.claude/plans",
  "plan_file": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md",
  "cwd": "/Users/eric/proj/ai-project/rundbat"
}
```

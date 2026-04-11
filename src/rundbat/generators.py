"""Docker directory generators — Dockerfile, compose, Justfile, .env.example."""

import json
import sys
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

def detect_framework(project_dir: Path) -> dict[str, str]:
    """Detect the project framework from project files.

    Returns dict with 'language', 'framework', and 'entry_point'.
    """
    project_dir = Path(project_dir)

    # Node.js
    pkg_json = project_dir / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in deps:
                return {"language": "node", "framework": "next", "entry_point": "npm start"}
            if "express" in deps:
                return {"language": "node", "framework": "express", "entry_point": "npm start"}
            if "astro" in deps:
                return {"language": "node", "framework": "astro", "entry_point": "nginx"}
            return {"language": "node", "framework": "node", "entry_point": "npm start"}
        except (json.JSONDecodeError, KeyError):
            return {"language": "node", "framework": "node", "entry_point": "npm start"}

    # Python
    pyproject = project_dir / "pyproject.toml"
    requirements = project_dir / "requirements.txt"
    if pyproject.exists() or requirements.exists():
        deps_text = ""
        if requirements.exists():
            deps_text = requirements.read_text().lower()
        if pyproject.exists():
            deps_text += pyproject.read_text().lower()

        if "django" in deps_text:
            return {"language": "python", "framework": "django", "entry_point": "gunicorn"}
        if "fastapi" in deps_text:
            return {"language": "python", "framework": "fastapi", "entry_point": "uvicorn"}
        if "flask" in deps_text:
            return {"language": "python", "framework": "flask", "entry_point": "gunicorn"}
        return {"language": "python", "framework": "python", "entry_point": "python"}

    return {"language": "unknown", "framework": "unknown", "entry_point": ""}


# ---------------------------------------------------------------------------
# Dockerfile generation
# ---------------------------------------------------------------------------

_DOCKERFILE_NODE = """\
# --- Build stage ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
{build_step}

# --- Production stage ---
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
{copy_step}
EXPOSE ${{PORT:-3000}}
CMD {cmd}
"""

_DOCKERFILE_PYTHON = """\
FROM python:3.12-slim
WORKDIR /app

COPY requirements*.txt pyproject.toml* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null \\
    || pip install --no-cache-dir . 2>/dev/null \\
    || true
COPY . .
{extra_step}
EXPOSE ${{PORT:-8000}}
CMD {cmd}
"""

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


def generate_dockerfile(framework: dict[str, str]) -> str:
    """Generate a Dockerfile for the detected framework."""
    lang = framework.get("language", "unknown")
    fw = framework.get("framework", "unknown")

    if fw == "astro":
        return _DOCKERFILE_ASTRO

    if lang == "node":
        if fw == "next":
            return _DOCKERFILE_NODE.format(
                build_step="RUN npm run build",
                copy_step="COPY --from=builder /app/.next ./.next\nCOPY --from=builder /app/node_modules ./node_modules\nCOPY --from=builder /app/package.json ./",
                cmd='["npm", "start"]',
            )
        # Express or generic Node
        return _DOCKERFILE_NODE.format(
            build_step="",
            copy_step="COPY --from=builder /app ./",
            cmd='["npm", "start"]',
        )

    if lang == "python":
        if fw == "django":
            return _DOCKERFILE_PYTHON.format(
                extra_step="RUN python manage.py collectstatic --noinput 2>/dev/null || true",
                cmd='["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]',
            )
        if fw == "fastapi":
            return _DOCKERFILE_PYTHON.format(
                extra_step="",
                cmd='["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]',
            )
        if fw == "flask":
            return _DOCKERFILE_PYTHON.format(
                extra_step="",
                cmd='["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]',
            )
        return _DOCKERFILE_PYTHON.format(
            extra_step="",
            cmd='["python", "main.py"]',
        )

    # Fallback
    return "# TODO: Add Dockerfile for your project\nFROM alpine:latest\n"


# ---------------------------------------------------------------------------
# docker-compose.yml generation
# ---------------------------------------------------------------------------

_DB_SERVICES = {
    "postgres": {
        "image": "postgres:{version}",
        "environment": {
            "POSTGRES_USER": "${DB_USER:-app}",
            "POSTGRES_PASSWORD": "${DB_PASSWORD}",
            "POSTGRES_DB": "${DB_NAME:-app}",
        },
        "volumes": ["{volume_name}:/var/lib/postgresql/data"],
        "healthcheck": {
            "test": ["CMD-SHELL", "pg_isready -U ${DB_USER:-app}"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "mariadb": {
        "image": "mariadb:{version}",
        "environment": {
            "MARIADB_USER": "${DB_USER:-app}",
            "MARIADB_PASSWORD": "${DB_PASSWORD}",
            "MARIADB_ROOT_PASSWORD": "${DB_ROOT_PASSWORD}",
            "MARIADB_DATABASE": "${DB_NAME:-app}",
        },
        "volumes": ["{volume_name}:/var/lib/mysql"],
        "healthcheck": {
            "test": ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "redis": {
        "image": "redis:{version}",
        "healthcheck": {
            "test": ["CMD", "redis-cli", "ping"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
}


def generate_compose(
    app_name: str,
    framework: dict[str, str],
    services: list[dict[str, Any]] | None = None,
    hostname: str | None = None,
    swarm: bool = False,
) -> str:
    """Generate a docker-compose.yml string."""
    lang = framework.get("language", "node")
    fw = framework.get("framework", "")
    if fw == "astro":
        port = "8080"
    elif lang == "node":
        port = "3000"
    else:
        port = "8000"

    compose: dict[str, Any] = {"services": {}, "volumes": {}}

    # App service
    app_svc: dict[str, Any] = {
        "build": {"context": "..", "dockerfile": "docker/Dockerfile"},
        "ports": [f"${{{app_name.upper()}_PORT:-{port}}}:{port}"],
        "env_file": ["../.env"],
        "restart": "unless-stopped",
    }

    # Caddy labels
    if hostname:
        labels = {
            "caddy": hostname,
            "caddy.reverse_proxy": "{{upstreams " + port + "}}",
        }
        if swarm:
            app_svc["deploy"] = {"labels": labels}
        else:
            app_svc["labels"] = labels

    # Dependencies
    depends = []
    if services:
        for svc in services:
            depends.append(svc["type"])
        if depends:
            app_svc["depends_on"] = {
                name: {"condition": "service_healthy"} for name in depends
            }

    compose["services"]["app"] = app_svc

    # Database services
    if services:
        for svc in services:
            svc_type = svc["type"]
            version = svc.get("version", "latest")
            if svc_type not in _DB_SERVICES:
                continue

            template = _DB_SERVICES[svc_type].copy()
            template["image"] = template["image"].format(version=version)

            volume_name = f"{svc_type}_data"
            if "volumes" in template:
                template["volumes"] = [
                    v.format(volume_name=volume_name) for v in template["volumes"]
                ]
                compose["volumes"][volume_name] = None

            template["restart"] = "unless-stopped"
            compose["services"][svc_type] = template

    if not compose["volumes"]:
        del compose["volumes"]

    return yaml.dump(compose, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Per-deployment compose generation
# ---------------------------------------------------------------------------

def _port_for_framework(framework: dict[str, str]) -> str:
    """Return the default port string for a framework."""
    fw = framework.get("framework", "")
    lang = framework.get("language", "node")
    if fw == "astro":
        return "8080"
    elif lang == "node":
        return "3000"
    return "8000"


def generate_compose_for_deployment(
    app_name: str,
    framework: dict[str, str],
    deployment_name: str,
    deployment_cfg: dict[str, Any],
    all_services: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a docker-compose.<name>.yml string for one deployment.

    Args:
        app_name: Project app name.
        framework: Framework detection dict (language, framework, entry_point).
        deployment_name: The deployment name (dev, local, prod, etc.).
        deployment_cfg: The deployment entry from rundbat.yaml.
        all_services: All project-level services from rundbat.yaml.
    """
    port = _port_for_framework(framework)
    build_strategy = deployment_cfg.get("build_strategy", "context")
    hostname = deployment_cfg.get("hostname")
    reverse_proxy = deployment_cfg.get("reverse_proxy")
    deploy_mode = deployment_cfg.get("deploy_mode", "compose")
    image = deployment_cfg.get("image")
    dep_services = deployment_cfg.get("services")

    compose: dict[str, Any] = {"services": {}, "volumes": {}}

    # App service
    app_svc: dict[str, Any] = {
        "ports": [f"${{{app_name.upper()}_PORT:-{port}}}:{port}"],
        "env_file": [f"docker/.{deployment_name}.env"],
        "restart": "unless-stopped",
    }

    # Build vs image
    if build_strategy == "github-actions" and image:
        app_svc["image"] = f"{image}:latest"
    elif build_strategy == "github-actions":
        app_svc["image"] = f"ghcr.io/owner/{app_name}:latest"
    else:
        app_svc["build"] = {"context": "..", "dockerfile": "docker/Dockerfile"}

    # Caddy labels
    if hostname and reverse_proxy == "caddy":
        app_svc["labels"] = {
            "caddy": hostname,
            "caddy.reverse_proxy": "{{upstreams " + port + "}}",
        }

    # Filter services for this deployment
    included_services = []
    if all_services and dep_services:
        for svc in all_services:
            if svc["type"] in dep_services:
                included_services.append(svc)
    elif all_services and dep_services is None:
        included_services = list(all_services)

    # Dependencies
    depends = []
    for svc in included_services:
        depends.append(svc["type"])
    if depends:
        app_svc["depends_on"] = {
            name: {"condition": "service_healthy"} for name in depends
        }

    compose["services"]["app"] = app_svc

    # Database / infrastructure services
    for svc in included_services:
        svc_type = svc["type"]
        version = svc.get("version", "latest")
        if svc_type not in _DB_SERVICES:
            continue

        import copy
        template = copy.deepcopy(_DB_SERVICES[svc_type])
        template["image"] = template["image"].format(version=version)

        volume_name = f"{svc_type}_data"
        if "volumes" in template:
            template["volumes"] = [
                v.format(volume_name=volume_name) for v in template["volumes"]
            ]
            compose["volumes"][volume_name] = None

        template["restart"] = "unless-stopped"
        compose["services"][svc_type] = template

    if not compose["volumes"]:
        del compose["volumes"]

    return yaml.dump(compose, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Entrypoint generation
# ---------------------------------------------------------------------------

def generate_entrypoint(framework: dict[str, str]) -> str:
    """Generate an entrypoint.sh script for the detected framework."""
    fw = framework.get("framework", "unknown")

    pre_start = ""
    if fw == "django":
        pre_start = "\n# Run migrations\npython manage.py migrate --noinput\n"
    elif fw in ("next", "express", "node"):
        pre_start = "\n# Run migrations if available\nnpx prisma migrate deploy 2>/dev/null || true\n"

    return f"""\
#!/bin/sh
set -e

# Decrypt secrets if age key is mounted
if [ -f /run/secrets/age-key ]; then
    export SOPS_AGE_KEY_FILE=/run/secrets/age-key
fi
{pre_start}
exec "$@"
"""


# ---------------------------------------------------------------------------
# Justfile generation
# ---------------------------------------------------------------------------

def generate_justfile(app_name: str, services: list[dict[str, Any]] | None = None,
                      deployments: dict[str, dict] | None = None) -> str:
    """Generate a Justfile with per-deployment recipes.

    Each deployment gets named recipes: <name>_build, <name>_up,
    <name>_down, <name>_logs. Remote deployments prefix with
    DOCKER_CONTEXT=<ctx>. Regenerate with `rundbat generate` after
    config changes.
    """
    lines = [
        f"# {app_name} — Docker deployment recipes",
        "",
        "set dotenv-load",
        "",
    ]

    if not deployments:
        # Fallback: single generic set of recipes (backward compat)
        lines.extend([
            "# Build the app image",
            "build:",
            "    docker compose -f docker/docker-compose.yml build",
            "",
            "# Start all services",
            "up:",
            "    docker compose -f docker/docker-compose.yml up -d",
            "",
            "# Stop all services",
            "down:",
            "    docker compose -f docker/docker-compose.yml down",
            "",
            "# View logs",
            "logs *ARGS:",
            "    docker compose -f docker/docker-compose.yml logs {{ARGS}}",
            "",
        ])
        return "\n".join(lines)

    for dep_name, dep_cfg in deployments.items():
        ctx = dep_cfg.get("docker_context", "default")
        compose_file = f"docker/docker-compose.{dep_name}.yml"
        deploy_mode = dep_cfg.get("deploy_mode", "compose")
        build_strategy = dep_cfg.get("build_strategy", "context")
        is_remote = ctx and ctx != "default"
        ctx_prefix = f"DOCKER_CONTEXT={ctx} " if is_remote else ""

        lines.append(f"# --- {dep_name} ---")
        lines.append("")

        if deploy_mode == "run":
            docker_run_cmd = dep_cfg.get("docker_run_cmd", "")
            image = dep_cfg.get("image", f"ghcr.io/owner/{app_name}:latest")
            lines.extend([
                f"{dep_name}_up:",
                f"    {ctx_prefix}docker pull {image}",
                f"    {ctx_prefix}docker stop {app_name} || true",
                f"    {ctx_prefix}docker rm {app_name} || true",
                f"    {ctx_prefix}{docker_run_cmd}" if docker_run_cmd else f"    echo 'No docker_run_cmd configured'",
                "",
                f"{dep_name}_down:",
                f"    {ctx_prefix}docker stop {app_name} || true",
                f"    {ctx_prefix}docker rm {app_name} || true",
                "",
                f"{dep_name}_logs *ARGS:",
                f"    {ctx_prefix}docker logs -f {app_name} {{{{ARGS}}}}",
                "",
            ])
        else:
            # compose mode
            if build_strategy == "github-actions":
                lines.extend([
                    f"{dep_name}_build:",
                    f"    echo 'Build is handled by GitHub Actions for {dep_name}'",
                    "",
                    f"{dep_name}_up:",
                    f"    {ctx_prefix}docker compose -f {compose_file} pull",
                    f"    {ctx_prefix}docker compose -f {compose_file} up -d",
                    "",
                ])
            else:
                lines.extend([
                    f"{dep_name}_build:",
                    f"    {ctx_prefix}docker compose -f {compose_file} build",
                    "",
                    f"{dep_name}_up: {dep_name}_build",
                    f"    {ctx_prefix}docker compose -f {compose_file} up -d",
                    "",
                ])

            lines.extend([
                f"{dep_name}_down:",
                f"    {ctx_prefix}docker compose -f {compose_file} down",
                "",
                f"{dep_name}_logs *ARGS:",
                f"    {ctx_prefix}docker compose -f {compose_file} logs {{{{ARGS}}}}",
                "",
            ])

        # Database helpers
        dep_services = dep_cfg.get("services", [])
        has_pg = "postgres" in (dep_services or [])
        if not has_pg and services:
            has_pg = any(s["type"] == "postgres" for s in services)
            # Only include if this deployment would have postgres
            if dep_services and "postgres" not in dep_services:
                has_pg = False

        if has_pg and deploy_mode != "run":
            lines.extend([
                f"{dep_name}_psql:",
                f'    {ctx_prefix}docker compose -f {compose_file} exec postgres psql -U ${{DB_USER:-app}} ${{DB_NAME:-app}}',
                "",
                f"{dep_name}_db_dump:",
                f'    {ctx_prefix}docker compose -f {compose_file} exec postgres pg_dump -U ${{DB_USER:-app}} ${{DB_NAME:-app}}',
                "",
            ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# .env.example generation
# ---------------------------------------------------------------------------

def generate_env_example(
    app_name: str,
    framework: dict[str, str],
    services: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a .env.example with placeholders for secrets."""
    lang = framework.get("language", "node")
    fw = framework.get("framework", "")
    if fw == "astro":
        port = "8080"
    elif lang == "node":
        port = "3000"
    else:
        port = "8000"

    lines = [
        f"# {app_name} environment configuration",
        f"# Copy to .env and fill in the values",
        "",
        f"PORT={port}",
    ]

    if lang == "node" and fw != "astro":
        lines.append("NODE_ENV=production")
    elif lang == "python":
        lines.append("PYTHON_ENV=production")

    lines.append("")

    if services:
        for svc in services:
            svc_type = svc["type"]
            if svc_type == "postgres":
                lines.extend([
                    "# PostgreSQL",
                    "DB_USER=app",
                    "DB_PASSWORD=<your-database-password>",
                    "DB_NAME=app",
                    "DATABASE_URL=postgresql://app:<password>@postgres:5432/app",
                    "",
                ])
            elif svc_type == "mariadb":
                lines.extend([
                    "# MariaDB",
                    "DB_USER=app",
                    "DB_PASSWORD=<your-database-password>",
                    "DB_ROOT_PASSWORD=<your-root-password>",
                    "DB_NAME=app",
                    "DATABASE_URL=mysql://app:<password>@mariadb:3306/app",
                    "",
                ])
            elif svc_type == "redis":
                lines.extend([
                    "# Redis",
                    "REDIS_URL=redis://redis:6379",
                    "",
                ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# .dockerignore generation
# ---------------------------------------------------------------------------

_DOCKERIGNORE_CONTENT = """\
# Version control
.git/
.gitignore

# CI/CD
.github/

# Dependencies (rebuilt inside container)
node_modules/
.venv/
__pycache__/
*.pyc
*.pyo

# rundbat / dotconfig
config/
docker/

# Docs and planning artifacts
docs/

# AI assistant context
.claude/
.mcp.json
CLAUDE.md
AGENTS.md

# Tests
tests/

# Local env overrides (real .env injected at runtime)
.env
.env.*
!.env.example

# Build / coverage artifacts
dist/
build/
.coverage
htmlcov/
*.egg-info/
"""


def generate_dockerignore() -> str:
    """Return the content of a .dockerignore file for the project root."""
    return _DOCKERIGNORE_CONTENT


# ---------------------------------------------------------------------------
# GitHub Actions workflow generation
# ---------------------------------------------------------------------------

def generate_github_workflow(
    app_name: str,
    host: str,
    compose_file: str = "docker/docker-compose.prod.yml",
    platform: str = "linux/amd64",
) -> str:
    """Generate a GitHub Actions workflow for GHCR build + deploy.

    The workflow:
    1. Builds the Docker image with the target platform
    2. Pushes to GHCR (uses built-in GITHUB_TOKEN — zero config)
    3. SSHes into the remote to pull and restart

    For public repos, GHCR pull needs no auth. For private repos,
    a GHCR_TOKEN secret must be added to the remote's environment.
    """
    # Strip ssh:// prefix for SSH action
    ssh_host = host
    if ssh_host.startswith("ssh://"):
        ssh_host = ssh_host[len("ssh://"):]

    return f"""\
name: Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{{{ github.repository }}}}

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          push: true
          platforms: {platform}
          tags: |
            ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:latest
            ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:${{{{ github.sha }}}}

      - name: Deploy to remote
        uses: appleboy/ssh-action@v1
        with:
          host: ${{{{ secrets.DEPLOY_HOST }}}}
          username: ${{{{ secrets.DEPLOY_USER }}}}
          key: ${{{{ secrets.DEPLOY_SSH_KEY }}}}
          script: |
            cd /opt/{app_name}
            docker compose -f {compose_file} pull
            docker compose -f {compose_file} up -d
"""


# ---------------------------------------------------------------------------
# GitHub Actions — split workflows
# ---------------------------------------------------------------------------

def generate_github_build_workflow(platform: str = "linux/amd64") -> str:
    """Generate a build.yml workflow for GHCR image builds.

    Triggers on push to main and workflow_dispatch (manual).
    """
    return f"""\
name: Build

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{{{ github.repository }}}}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          push: true
          platforms: {platform}
          tags: |
            ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:latest
            ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:${{{{ github.sha }}}}
"""


def generate_github_deploy_workflow(
    app_name: str,
    compose_file: str = "docker/docker-compose.prod.yml",
    deploy_mode: str = "compose",
    docker_run_cmd: str | None = None,
) -> str:
    """Generate a deploy.yml workflow triggered after build or manually.

    For compose mode: SSH pull + up.
    For run mode: SSH pull + stop + rm + run.
    """
    if deploy_mode == "run" and docker_run_cmd:
        deploy_script = f"""\
            cd /opt/{app_name}
            docker pull $(grep -oP 'ghcr\\.io/[^ ]+' <<< '{docker_run_cmd}') || true
            docker stop {app_name} || true
            docker rm {app_name} || true
            {docker_run_cmd}"""
    else:
        deploy_script = f"""\
            cd /opt/{app_name}
            docker compose -f {compose_file} pull
            docker compose -f {compose_file} up -d"""

    return f"""\
name: Deploy

on:
  workflow_run:
    workflows: [Build]
    types: [completed]
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{{{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}}}

    steps:
      - name: Deploy to remote
        uses: appleboy/ssh-action@v1
        with:
          host: ${{{{ secrets.DEPLOY_HOST }}}}
          username: ${{{{ secrets.DEPLOY_USER }}}}
          key: ${{{{ secrets.DEPLOY_SSH_KEY }}}}
          script: |
{deploy_script}
"""


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

def generate_artifacts(
    project_dir: Path,
    cfg: dict[str, Any],
    deployment: str | None = None,
) -> dict:
    """Generate all Docker artifacts from rundbat.yaml config.

    Produces per-deployment compose files, Dockerfile, entrypoint.sh,
    Justfile, .dockerignore, and updates .gitignore.

    Args:
        project_dir: Root project directory.
        cfg: Full rundbat.yaml config dict.
        deployment: If set, regenerate only this deployment.

    Returns dict with {status, files: [...]}.
    """
    project_dir = Path(project_dir)
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True, exist_ok=True)

    app_name = cfg.get("app_name", "app")
    all_services = cfg.get("services")
    deployments = cfg.get("deployments", {})

    framework = detect_framework(project_dir)

    generated = []

    # Dockerfile
    dockerfile = docker_dir / "Dockerfile"
    dockerfile.write_text(generate_dockerfile(framework))
    generated.append(str(dockerfile.relative_to(project_dir)))

    if framework.get("framework") == "astro":
        nginx_conf = docker_dir / "nginx.conf"
        nginx_conf.write_text(generate_nginx_conf())
        generated.append(str(nginx_conf.relative_to(project_dir)))

    # Entrypoint
    entrypoint = docker_dir / "entrypoint.sh"
    entrypoint.write_text(generate_entrypoint(framework))
    entrypoint.chmod(0o755)
    generated.append(str(entrypoint.relative_to(project_dir)))

    # Per-deployment compose files
    targets = {deployment: deployments[deployment]} if deployment and deployment in deployments else deployments
    has_github_actions = False

    for dep_name, dep_cfg in targets.items():
        deploy_mode = dep_cfg.get("deploy_mode", "compose")
        if dep_cfg.get("build_strategy") == "github-actions":
            has_github_actions = True

        if deploy_mode == "compose":
            compose_content = generate_compose_for_deployment(
                app_name, framework, dep_name, dep_cfg, all_services,
            )
            compose_path = docker_dir / f"docker-compose.{dep_name}.yml"
            compose_path.write_text(compose_content)
            generated.append(str(compose_path.relative_to(project_dir)))

        # Per-deployment env file
        env_source = dep_cfg.get("env_source")
        env_path = docker_dir / f".{dep_name}.env"
        if env_source == "dotconfig":
            try:
                from rundbat import config as cfg_mod
                env_content = cfg_mod.load_env(dep_name)
                env_path.write_text(env_content)
            except Exception:
                env_path.write_text(f"# dotconfig env for {dep_name} — run 'dotconfig load -d {dep_name}' to populate\n")
                print(f"  Warning: Could not load dotconfig env for {dep_name}", file=sys.stderr)
        else:
            env_path.write_text(generate_env_example(app_name, framework, all_services))
        generated.append(str(env_path.relative_to(project_dir)))

    # GitHub Actions workflows
    if has_github_actions:
        workflows_dir = project_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Find the github-actions deployment for workflow config
        ga_dep = None
        for dep_name, dep_cfg in deployments.items():
            if dep_cfg.get("build_strategy") == "github-actions":
                ga_dep = (dep_name, dep_cfg)
                break

        if ga_dep:
            dep_name, dep_cfg = ga_dep
            platform = dep_cfg.get("platform", "linux/amd64")
            compose_file = f"docker/docker-compose.{dep_name}.yml"
            deploy_mode = dep_cfg.get("deploy_mode", "compose")
            docker_run_cmd = dep_cfg.get("docker_run_cmd")

            build_wf = workflows_dir / "build.yml"
            build_wf.write_text(generate_github_build_workflow(platform))
            generated.append(str(build_wf.relative_to(project_dir)))

            deploy_wf = workflows_dir / "deploy.yml"
            deploy_wf.write_text(generate_github_deploy_workflow(
                app_name, compose_file, deploy_mode, docker_run_cmd,
            ))
            generated.append(str(deploy_wf.relative_to(project_dir)))

    # Justfile
    justfile = docker_dir / "Justfile"
    justfile.write_text(generate_justfile(app_name, all_services, deployments))
    generated.append(str(justfile.relative_to(project_dir)))

    # .env.example
    env_example = docker_dir / ".env.example"
    env_example.write_text(generate_env_example(app_name, framework, all_services))
    generated.append(str(env_example.relative_to(project_dir)))

    # .dockerignore (project root)
    dockerignore = project_dir / ".dockerignore"
    if not dockerignore.exists():
        dockerignore.write_text(generate_dockerignore())
        generated.append(".dockerignore")

    # Update .gitignore with per-deployment env pattern
    gitignore = project_dir / ".gitignore"
    gitignore_pattern = "docker/.*.env"
    if gitignore.exists():
        content = gitignore.read_text()
        if gitignore_pattern not in content:
            with open(gitignore, "a") as f:
                f.write(f"\n# Per-deployment env files (contain secrets from dotconfig)\n{gitignore_pattern}\n")
    else:
        gitignore.write_text(f"# Per-deployment env files (contain secrets from dotconfig)\n{gitignore_pattern}\n")

    return {
        "status": "created",
        "docker_dir": str(docker_dir),
        "framework": framework,
        "files": generated,
    }


def init_docker(
    project_dir: Path,
    app_name: str,
    framework: dict[str, str] | None = None,
    services: list[dict[str, Any]] | None = None,
    hostname: str | None = None,
    swarm: bool = False,
    deployments: dict[str, dict] | None = None,
) -> dict:
    """Generate the complete docker/ directory.

    .. deprecated:: Use ``generate_artifacts()`` via ``rundbat generate`` instead.

    Returns dict with paths of generated files.
    """
    print("Note: init-docker is deprecated. Use 'rundbat generate' instead.",
          file=sys.stderr)

    # Build a minimal config dict for generate_artifacts
    cfg: dict[str, Any] = {
        "app_name": app_name,
        "services": services,
        "deployments": deployments or {},
    }

    # If no deployments, create a default one for backward compat
    if not cfg["deployments"]:
        dep: dict[str, Any] = {
            "docker_context": "default",
            "build_strategy": "context",
        }
        if hostname:
            dep["hostname"] = hostname
            dep["reverse_proxy"] = "caddy"
        cfg["deployments"] = {"dev": dep}

    return generate_artifacts(project_dir, cfg)


def add_service(
    project_dir: Path,
    service_type: str,
    version: str = "latest",
) -> dict:
    """Add a database service to an existing docker-compose.yml.

    Returns dict with status and what was added.
    """
    project_dir = Path(project_dir)
    compose_path = project_dir / "docker" / "docker-compose.yml"

    if not compose_path.exists():
        return {"error": f"docker-compose.yml not found. Run 'rundbat init-docker' first."}

    if service_type not in _DB_SERVICES:
        return {"error": f"Unknown service type: {service_type}. Supported: postgres, mariadb, redis"}

    compose = yaml.safe_load(compose_path.read_text()) or {}
    if "services" not in compose:
        compose["services"] = {}

    if service_type in compose["services"]:
        return {"status": "already_exists", "service": service_type}

    # Add service
    template = _DB_SERVICES[service_type].copy()
    template["image"] = template["image"].format(version=version)

    volume_name = f"{service_type}_data"
    if "volumes" in template:
        template["volumes"] = [v.format(volume_name=volume_name) for v in template["volumes"]]
        if "volumes" not in compose:
            compose["volumes"] = {}
        compose["volumes"][volume_name] = None

    template["restart"] = "unless-stopped"
    compose["services"][service_type] = template

    # Add dependency to app service
    if "app" in compose["services"]:
        app_svc = compose["services"]["app"]
        if "depends_on" not in app_svc:
            app_svc["depends_on"] = {}
        app_svc["depends_on"][service_type] = {"condition": "service_healthy"}

    compose_path.write_text(yaml.dump(compose, default_flow_style=False, sort_keys=False))

    return {"status": "added", "service": service_type, "version": version}

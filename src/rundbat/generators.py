"""Docker directory generators — Dockerfile, compose, Justfile, .env.example."""

import json
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


def generate_dockerfile(framework: dict[str, str]) -> str:
    """Generate a Dockerfile for the detected framework."""
    lang = framework.get("language", "unknown")
    fw = framework.get("framework", "unknown")

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
    port = "3000" if lang == "node" else "8000"

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
# Justfile generation
# ---------------------------------------------------------------------------

def generate_justfile(app_name: str, services: list[dict[str, Any]] | None = None,
                      deployments: dict[str, dict] | None = None) -> str:
    """Generate a Justfile with standard deployment recipes.

    All docker commands use DOCKER_CONTEXT env var so they target the
    right Docker daemon. Context names are baked in from rundbat.yaml
    at generation time. Regenerate with `rundbat init-docker` after
    config changes.
    """
    has_postgres = any(s["type"] == "postgres" for s in (services or []))
    has_mariadb = any(s["type"] == "mariadb" for s in (services or []))

    # Build context map: env name -> docker context name
    context_map = {}
    if deployments:
        for dep_name, dep_cfg in deployments.items():
            ctx = dep_cfg.get("docker_context", "")
            if ctx:
                context_map[dep_name] = ctx

    # Generate the context lookup as a just expression
    # Uses chained if/else to map env name to context
    if context_map:
        parts = []
        for dep_name, ctx in context_map.items():
            parts.append(f'if ENV == "{dep_name}" {{ "{ctx}" }}')
        ctx_expr = " else ".join(parts) + ' else { "default" }'
    else:
        ctx_expr = '"default"'

    docker = "DOCKER_CONTEXT={{CTX}} docker"

    lines = [
        f"# {app_name} — Docker deployment recipes",
        "",
        "set dotenv-load",
        "",
        "# Target environment (dev, test, prod)",
        'ENV := env("DEPLOY_ENV", "dev")',
        "",
        f"# Docker context for target environment",
        f"CTX := {ctx_expr}",
        "",
        "# Target platform for cross-architecture builds (e.g., linux/amd64)",
        'PLATFORM := env("DOCKER_PLATFORM", "")',
        "",
        "# Build the app image",
        "build:",
        f'    {docker} compose -f docker/docker-compose.yml build {{{{ if PLATFORM != "" {{ "--platform " + PLATFORM }} else {{ "" }} }}}}',
        "",
        "# Start all services",
        "up:",
        f"    {docker} compose -f docker/docker-compose.yml up -d",
        "",
        "# Stop all services",
        "down:",
        f"    {docker} compose -f docker/docker-compose.yml down",
        "",
        "# Stop and remove volumes (destructive)",
        "down-with-data:",
        f"    {docker} compose -f docker/docker-compose.yml down -v",
        "",
        "# View logs",
        "logs *ARGS:",
        f"    {docker} compose -f docker/docker-compose.yml logs {{ARGS}}",
        "",
        "# Rebuild and restart",
        "restart: build up",
        "",
        "# Deploy via context (build + start on target environment)",
        'deploy: build up',
        "",
        "# Deploy via SSH transfer (build locally, send to remote, start)",
        "deploy-transfer HOST:",
        f'    docker compose -f docker/docker-compose.yml build {{{{ if PLATFORM != "" {{ "--platform " + PLATFORM }} else {{ "" }} }}}}',
        f"    docker save $(docker compose -f docker/docker-compose.yml config --images) | ssh {{{{HOST}}}} docker load",
        f"    {docker} compose -f docker/docker-compose.yml up -d",
        "",
    ]

    if has_postgres:
        lines.extend([
            "# PostgreSQL shell",
            "psql:",
            f'    {docker} compose -f docker/docker-compose.yml exec postgres psql -U ${{DB_USER:-app}} ${{DB_NAME:-app}}',
            "",
            "# Dump PostgreSQL database",
            "db-dump:",
            f'    {docker} compose -f docker/docker-compose.yml exec postgres pg_dump -U ${{DB_USER:-app}} ${{DB_NAME:-app}} > backups/{{{{ENV}}}}_{app_name}_$(date +%Y%m%d_%H%M%S).sql',
            "",
            "# Restore PostgreSQL database from file",
            "db-restore FILE:",
            f'    {docker} compose -f docker/docker-compose.yml exec -T postgres psql -U ${{DB_USER:-app}} ${{DB_NAME:-app}} < {{FILE}}',
            "",
            "# Run database migrations",
            "db-migrate:",
            f'    {docker} compose -f docker/docker-compose.yml exec app npm run migrate 2>/dev/null || {docker} compose -f docker/docker-compose.yml exec app python manage.py migrate 2>/dev/null || echo "No migration command found"',
            "",
        ])

    if has_mariadb:
        lines.extend([
            "# MariaDB shell",
            "mysql:",
            f'    {docker} compose -f docker/docker-compose.yml exec mariadb mariadb -u ${{DB_USER:-app}} -p${{DB_PASSWORD}} ${{DB_NAME:-app}}',
            "",
            "# Dump MariaDB database",
            "db-dump:",
            f'    {docker} compose -f docker/docker-compose.yml exec mariadb mariadb-dump -u ${{DB_USER:-app}} -p${{DB_PASSWORD}} ${{DB_NAME:-app}} > backups/{{{{ENV}}}}_{app_name}_$(date +%Y%m%d_%H%M%S).sql',
            "",
            "# Restore MariaDB database from file",
            "db-restore FILE:",
            f'    {docker} compose -f docker/docker-compose.yml exec -T mariadb mariadb -u ${{DB_USER:-app}} -p${{DB_PASSWORD}} ${{DB_NAME:-app}} < {{FILE}}',
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
    port = "3000" if lang == "node" else "8000"

    lines = [
        f"# {app_name} environment configuration",
        f"# Copy to .env and fill in the values",
        "",
        f"PORT={port}",
        f"NODE_ENV=production" if lang == "node" else "PYTHON_ENV=production",
        "",
    ]

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
# High-level orchestration
# ---------------------------------------------------------------------------

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

    Returns dict with paths of generated files.
    """
    project_dir = Path(project_dir)
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True, exist_ok=True)

    if framework is None:
        framework = detect_framework(project_dir)

    generated = []

    # Dockerfile
    dockerfile = docker_dir / "Dockerfile"
    dockerfile.write_text(generate_dockerfile(framework))
    generated.append(str(dockerfile.relative_to(project_dir)))

    # docker-compose.yml
    compose = docker_dir / "docker-compose.yml"
    compose.write_text(generate_compose(app_name, framework, services, hostname, swarm))
    generated.append(str(compose.relative_to(project_dir)))

    # Justfile
    justfile = docker_dir / "Justfile"
    justfile.write_text(generate_justfile(app_name, services, deployments))
    generated.append(str(justfile.relative_to(project_dir)))

    # .env.example
    env_example = docker_dir / ".env.example"
    env_example.write_text(generate_env_example(app_name, framework, services))
    generated.append(str(env_example.relative_to(project_dir)))

    # .dockerignore (project root — build context is project root)
    dockerignore = project_dir / ".dockerignore"
    if not dockerignore.exists():
        dockerignore.write_text(generate_dockerignore())
        generated.append(".dockerignore")

    return {
        "status": "created",
        "docker_dir": str(docker_dir),
        "framework": framework,
        "files": generated,
    }


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

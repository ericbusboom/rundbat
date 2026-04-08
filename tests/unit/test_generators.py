"""Tests for Docker directory generators."""

import json
from pathlib import Path

import yaml

from rundbat.generators import (
    detect_framework,
    generate_dockerfile,
    generate_compose,
    generate_justfile,
    generate_env_example,
    generate_github_workflow,
    init_docker,
    add_service,
)


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

class TestDetectFramework:
    def test_express(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"express": "^4.0"}})
        )
        result = detect_framework(tmp_path)
        assert result["language"] == "node"
        assert result["framework"] == "express"

    def test_next(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"next": "^14.0", "react": "^18"}})
        )
        result = detect_framework(tmp_path)
        assert result["framework"] == "next"

    def test_generic_node(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"lodash": "^4.0"}})
        )
        result = detect_framework(tmp_path)
        assert result["language"] == "node"
        assert result["framework"] == "node"

    def test_django(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("Django>=4.0\npsycopg2\n")
        result = detect_framework(tmp_path)
        assert result["language"] == "python"
        assert result["framework"] == "django"

    def test_fastapi(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
        result = detect_framework(tmp_path)
        assert result["framework"] == "fastapi"

    def test_flask(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=3.0\n")
        result = detect_framework(tmp_path)
        assert result["framework"] == "flask"

    def test_unknown(self, tmp_path):
        result = detect_framework(tmp_path)
        assert result["language"] == "unknown"


# ---------------------------------------------------------------------------
# Dockerfile generation
# ---------------------------------------------------------------------------

class TestGenerateDockerfile:
    def test_express(self):
        df = generate_dockerfile({"language": "node", "framework": "express"})
        assert "FROM node:20-alpine" in df
        assert "npm ci" in df
        assert '"npm", "start"' in df

    def test_next(self):
        df = generate_dockerfile({"language": "node", "framework": "next"})
        assert "npm run build" in df
        assert ".next" in df

    def test_django(self):
        df = generate_dockerfile({"language": "python", "framework": "django"})
        assert "python:3.12-slim" in df
        assert "collectstatic" in df
        assert "gunicorn" in df

    def test_fastapi(self):
        df = generate_dockerfile({"language": "python", "framework": "fastapi"})
        assert "uvicorn" in df

    def test_flask(self):
        df = generate_dockerfile({"language": "python", "framework": "flask"})
        assert "gunicorn" in df

    def test_unknown(self):
        df = generate_dockerfile({"language": "unknown", "framework": "unknown"})
        assert "TODO" in df


# ---------------------------------------------------------------------------
# Compose generation
# ---------------------------------------------------------------------------

class TestGenerateCompose:
    def test_basic_app(self):
        compose_str = generate_compose("myapp", {"language": "node"})
        compose = yaml.safe_load(compose_str)
        assert "app" in compose["services"]
        assert "3000" in str(compose["services"]["app"]["ports"])

    def test_python_port(self):
        compose_str = generate_compose("myapp", {"language": "python"})
        compose = yaml.safe_load(compose_str)
        assert "8000" in str(compose["services"]["app"]["ports"])

    def test_with_postgres(self):
        services = [{"type": "postgres", "version": "16"}]
        compose_str = generate_compose("myapp", {"language": "node"}, services)
        compose = yaml.safe_load(compose_str)
        assert "postgres" in compose["services"]
        assert compose["services"]["postgres"]["image"] == "postgres:16"
        assert "postgres_data" in compose["volumes"]
        assert "postgres" in compose["services"]["app"]["depends_on"]

    def test_with_redis(self):
        services = [{"type": "redis", "version": "7"}]
        compose_str = generate_compose("myapp", {"language": "node"}, services)
        compose = yaml.safe_load(compose_str)
        assert "redis" in compose["services"]
        assert compose["services"]["redis"]["image"] == "redis:7"

    def test_caddy_standalone(self):
        compose_str = generate_compose(
            "myapp", {"language": "node"}, hostname="example.com", swarm=False,
        )
        compose = yaml.safe_load(compose_str)
        labels = compose["services"]["app"]["labels"]
        assert labels["caddy"] == "example.com"

    def test_caddy_swarm(self):
        compose_str = generate_compose(
            "myapp", {"language": "node"}, hostname="example.com", swarm=True,
        )
        compose = yaml.safe_load(compose_str)
        labels = compose["services"]["app"]["deploy"]["labels"]
        assert labels["caddy"] == "example.com"
        assert "labels" not in compose["services"]["app"]  # not at service level

    def test_healthcheck(self):
        services = [{"type": "postgres", "version": "16"}]
        compose_str = generate_compose("myapp", {"language": "node"}, services)
        compose = yaml.safe_load(compose_str)
        assert "healthcheck" in compose["services"]["postgres"]


# ---------------------------------------------------------------------------
# Justfile generation
# ---------------------------------------------------------------------------

class TestGenerateJustfile:
    def test_basic_recipes(self):
        jf = generate_justfile("myapp")
        assert "build:" in jf
        assert "up:" in jf
        assert "down:" in jf
        assert "logs" in jf

    def test_docker_context_var(self):
        deployments = {
            "dev": {"docker_context": "orbstack"},
            "prod": {"docker_context": "myapp-prod"},
        }
        jf = generate_justfile("myapp", deployments=deployments)
        assert "DOCKER_CONTEXT=" in jf
        assert "orbstack" in jf
        assert "myapp-prod" in jf

    def test_deploy_recipe(self):
        jf = generate_justfile("myapp")
        assert "deploy:" in jf

    def test_no_push_recipe(self):
        jf = generate_justfile("myapp")
        assert "push:" not in jf

    def test_postgres_recipes(self):
        services = [{"type": "postgres"}]
        jf = generate_justfile("myapp", services)
        assert "psql:" in jf
        assert "db-dump:" in jf
        assert "db-restore" in jf

    def test_mariadb_recipes(self):
        services = [{"type": "mariadb"}]
        jf = generate_justfile("myapp", services)
        assert "mysql:" in jf
        assert "mariadb-dump" in jf

    def test_platform_variable(self):
        jf = generate_justfile("myapp")
        assert "PLATFORM" in jf
        assert "DOCKER_PLATFORM" in jf

    def test_deploy_transfer_recipe(self):
        jf = generate_justfile("myapp")
        assert "deploy-transfer HOST:" in jf
        assert "docker save" in jf
        assert "docker load" in jf


# ---------------------------------------------------------------------------
# GitHub workflow generation
# ---------------------------------------------------------------------------

class TestGenerateGitHubWorkflow:
    def test_basic_workflow(self):
        wf = generate_github_workflow("myapp", "ssh://root@host.example.com")
        assert "name: Deploy" in wf
        assert "ghcr.io" in wf
        assert "docker/build-push-action" in wf
        assert "linux/amd64" in wf

    def test_custom_platform(self):
        wf = generate_github_workflow("myapp", "ssh://root@host",
                                      platform="linux/arm64")
        assert "linux/arm64" in wf

    def test_custom_compose_file(self):
        wf = generate_github_workflow("myapp", "ssh://root@host",
                                      compose_file="docker/compose.yml")
        assert "docker/compose.yml" in wf

    def test_ssh_host_stripped(self):
        wf = generate_github_workflow("myapp", "ssh://root@host.example.com")
        # The workflow uses GitHub secrets for host, not hardcoded
        assert "DEPLOY_HOST" in wf
        assert "DEPLOY_SSH_KEY" in wf


# ---------------------------------------------------------------------------
# .env.example generation
# ---------------------------------------------------------------------------

class TestGenerateEnvExample:
    def test_node_defaults(self):
        env = generate_env_example("myapp", {"language": "node"})
        assert "PORT=3000" in env
        assert "NODE_ENV=production" in env

    def test_python_defaults(self):
        env = generate_env_example("myapp", {"language": "python"})
        assert "PORT=8000" in env
        assert "PYTHON_ENV=production" in env

    def test_postgres_vars(self):
        services = [{"type": "postgres"}]
        env = generate_env_example("myapp", {"language": "node"}, services)
        assert "DB_USER" in env
        assert "DB_PASSWORD" in env
        assert "DATABASE_URL" in env

    def test_redis_vars(self):
        services = [{"type": "redis"}]
        env = generate_env_example("myapp", {"language": "node"}, services)
        assert "REDIS_URL" in env


# ---------------------------------------------------------------------------
# init_docker (integration)
# ---------------------------------------------------------------------------

class TestInitDocker:
    def test_creates_all_files(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "testapp", "dependencies": {"express": "^4"}})
        )
        result = init_docker(tmp_path, "testapp")
        assert result["status"] == "created"
        assert (tmp_path / "docker" / "Dockerfile").exists()
        assert (tmp_path / "docker" / "docker-compose.yml").exists()
        assert (tmp_path / "docker" / "Justfile").exists()
        assert (tmp_path / "docker" / ".env.example").exists()
        assert (tmp_path / ".dockerignore").exists()
        assert ".dockerignore" in result["files"]

    def test_dockerignore_not_overwritten(self, tmp_path):
        existing = "# custom\n"
        (tmp_path / ".dockerignore").write_text(existing)
        init_docker(tmp_path, "testapp")
        assert (tmp_path / ".dockerignore").read_text() == existing

    def test_with_services(self, tmp_path):
        services = [{"type": "postgres", "version": "16"}]
        result = init_docker(tmp_path, "testapp", services=services)
        compose = yaml.safe_load((tmp_path / "docker" / "docker-compose.yml").read_text())
        assert "postgres" in compose["services"]

    def test_idempotent(self, tmp_path):
        init_docker(tmp_path, "testapp")
        init_docker(tmp_path, "testapp")  # should not error
        assert (tmp_path / "docker" / "Dockerfile").exists()


# ---------------------------------------------------------------------------
# add_service
# ---------------------------------------------------------------------------

class TestAddService:
    def test_adds_postgres(self, tmp_path):
        init_docker(tmp_path, "testapp")
        result = add_service(tmp_path, "postgres", "16")
        assert result["status"] == "added"
        compose = yaml.safe_load((tmp_path / "docker" / "docker-compose.yml").read_text())
        assert "postgres" in compose["services"]
        assert "postgres" in compose["services"]["app"]["depends_on"]

    def test_already_exists(self, tmp_path):
        services = [{"type": "postgres", "version": "16"}]
        init_docker(tmp_path, "testapp", services=services)
        result = add_service(tmp_path, "postgres")
        assert result["status"] == "already_exists"

    def test_no_compose(self, tmp_path):
        result = add_service(tmp_path, "postgres")
        assert "error" in result

    def test_unknown_service(self, tmp_path):
        init_docker(tmp_path, "testapp")
        result = add_service(tmp_path, "oracle")
        assert "error" in result

    def test_adds_redis(self, tmp_path):
        init_docker(tmp_path, "testapp")
        result = add_service(tmp_path, "redis", "7")
        assert result["status"] == "added"
        compose = yaml.safe_load((tmp_path / "docker" / "docker-compose.yml").read_text())
        assert "redis" in compose["services"]

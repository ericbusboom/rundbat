"""Tests for Docker directory generators."""

import json
from pathlib import Path

import yaml

from rundbat.generators import (
    detect_framework,
    generate_dockerfile,
    generate_compose,
    generate_compose_for_deployment,
    generate_entrypoint,
    generate_justfile,
    generate_env_example,
    generate_github_workflow,
    generate_github_build_workflow,
    generate_github_deploy_workflow,
    generate_nginx_conf,
    generate_artifacts,
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

    def test_astro(self, tmp_path):
        """detect_framework returns astro for package.json with astro dep."""
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"astro": "^4.0.0"}})
        )
        result = detect_framework(tmp_path)
        assert result["language"] == "node"
        assert result["framework"] == "astro"
        assert result["entry_point"] == "nginx"

    def test_astro_in_devdeps(self, tmp_path):
        """Astro is detected even when only in devDependencies."""
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"astro": "^4.0.0"}})
        )
        result = detect_framework(tmp_path)
        assert result["framework"] == "astro"


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

    def test_astro(self):
        """Astro Dockerfile has 3 stages ending in nginx-unprivileged on port 8080."""
        fw = {"language": "node", "framework": "astro", "entry_point": "nginx"}
        result = generate_dockerfile(fw)
        assert "nginx-unprivileged:alpine" in result
        assert "EXPOSE 8080" in result
        assert "COPY --from=build /app/dist" in result
        assert "node:20-alpine" in result

    # --- Best-practices assertions (Docker Build Best Practices guide) ---

    def test_node_has_best_practices(self):
        df = generate_dockerfile({"language": "node", "framework": "express"})
        assert "# syntax=docker/dockerfile:1" in df
        assert "--mount=type=cache,target=/root/.npm" in df
        assert "USER node" in df
        assert "HEALTHCHECK" in df
        assert "COPY --chown=node:node --from=builder" in df

    def test_next_has_best_practices(self):
        df = generate_dockerfile({"language": "node", "framework": "next"})
        assert "# syntax=docker/dockerfile:1" in df
        assert "USER node" in df
        assert "COPY --chown=node:node --from=builder /app/.next" in df
        assert "HEALTHCHECK" in df

    def test_python_multi_stage(self):
        df = generate_dockerfile({"language": "python", "framework": "flask"})
        assert "# syntax=docker/dockerfile:1" in df
        assert "FROM python:3.12-slim AS builder" in df
        assert "/opt/venv" in df
        assert "--mount=type=cache,target=/root/.cache/pip" in df
        assert "USER appuser" in df
        assert "HEALTHCHECK" in df
        assert "COPY --chown=appuser" in df

    def test_django_extra_step_runs_before_user_switch(self):
        """collectstatic must run as root (before USER appuser)."""
        df = generate_dockerfile({"language": "python", "framework": "django"})
        collectstatic_idx = df.find("collectstatic")
        user_idx = df.find("USER appuser")
        assert collectstatic_idx != -1 and user_idx != -1
        assert collectstatic_idx < user_idx

    def test_astro_has_best_practices(self):
        df = generate_dockerfile({"language": "node", "framework": "astro"})
        assert "# syntax=docker/dockerfile:1" in df
        assert "--mount=type=cache,target=/root/.npm" in df
        assert "HEALTHCHECK" in df


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

    def test_astro_port(self):
        """generate_compose uses port 8080 for Astro framework."""
        fw = {"language": "node", "framework": "astro", "entry_point": "nginx"}
        result = generate_compose("myapp", fw)
        assert "8080" in result


# ---------------------------------------------------------------------------
# Justfile generation
# ---------------------------------------------------------------------------

class TestGenerateJustfile:
    def test_basic_recipes_no_deployments(self):
        """Fallback when no deployments: generic build/up/down/logs."""
        jf = generate_justfile("myapp")
        assert "build:" in jf
        assert "up:" in jf
        assert "down:" in jf
        assert "logs" in jf

    def test_per_deployment_recipes(self):
        """Each deployment gets named recipes."""
        deployments = {
            "dev": {"docker_context": "default"},
            "prod": {"docker_context": "myapp-prod"},
        }
        jf = generate_justfile("myapp", deployments=deployments)
        assert "dev_build:" in jf
        assert "dev_up:" in jf
        assert "dev_down:" in jf
        assert "dev_logs" in jf
        assert "prod_build:" in jf
        assert "prod_up:" in jf
        assert "prod_down:" in jf
        assert "prod_logs" in jf

    def test_docker_context_prefix(self):
        """Remote deployments prefix commands with DOCKER_CONTEXT."""
        deployments = {
            "dev": {"docker_context": "default"},
            "prod": {"docker_context": "myapp-prod"},
        }
        jf = generate_justfile("myapp", deployments=deployments)
        assert "DOCKER_CONTEXT=myapp-prod" in jf
        # dev should NOT have context prefix since it's default
        lines = jf.split("\n")
        for line in lines:
            if line.strip().startswith("docker compose") and "dev" in line:
                assert "DOCKER_CONTEXT=" not in line

    def test_github_actions_pull(self):
        """github-actions deployment uses pull instead of build."""
        deployments = {
            "prod": {"docker_context": "myapp-prod", "build_strategy": "github-actions"},
        }
        jf = generate_justfile("myapp", deployments=deployments)
        assert "pull" in jf
        assert "GitHub Actions" in jf

    def test_postgres_recipes(self):
        services = [{"type": "postgres"}]
        deployments = {"dev": {"docker_context": "default", "services": ["app", "postgres"]}}
        jf = generate_justfile("myapp", services, deployments)
        assert "dev_psql:" in jf
        assert "dev_db_dump:" in jf

    def test_no_push_recipe(self):
        jf = generate_justfile("myapp")
        assert "push:" not in jf

    def test_run_mode_recipes(self):
        """Run mode deployments get docker run/stop/logs recipes."""
        deployments = {
            "prod": {
                "docker_context": "myapp-prod",
                "deploy_mode": "run",
                "image": "ghcr.io/owner/myapp:latest",
                "docker_run_cmd": "docker run -d --name myapp ghcr.io/owner/myapp:latest",
            },
        }
        jf = generate_justfile("myapp", deployments=deployments)
        assert "prod_up:" in jf
        assert "prod_down:" in jf
        assert "docker stop" in jf
        assert "docker rm" in jf


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

    def test_astro_port_no_node_env(self):
        """generate_env_example uses port 8080 and omits NODE_ENV for Astro."""
        fw = {"language": "node", "framework": "astro", "entry_point": "nginx"}
        result = generate_env_example("myapp", fw)
        assert "PORT=8080" in result
        assert "NODE_ENV" not in result


# ---------------------------------------------------------------------------
# generate_nginx_conf
# ---------------------------------------------------------------------------

class TestGenerateNginxConf:
    def test_nginx_conf(self):
        """generate_nginx_conf returns config with listen 8080 and try_files."""
        result = generate_nginx_conf()
        assert "listen 8080" in result
        assert "try_files" in result
        assert "gzip on" in result
        assert "X-Frame-Options" in result


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
        # init_docker now creates per-deployment compose files
        assert (tmp_path / "docker" / "docker-compose.dev.yml").exists()
        assert (tmp_path / "docker" / "Justfile").exists()
        assert (tmp_path / "docker" / ".env.example").exists()
        assert (tmp_path / ".dockerignore").exists()
        assert ".dockerignore" in result["files"]

    def test_dockerignore_not_overwritten(self, tmp_path):
        existing = "# custom\n"
        (tmp_path / ".dockerignore").write_text(existing)
        init_docker(tmp_path, "testapp")
        assert (tmp_path / ".dockerignore").read_text() == existing

    def test_idempotent(self, tmp_path):
        init_docker(tmp_path, "testapp")
        init_docker(tmp_path, "testapp")  # should not error
        assert (tmp_path / "docker" / "Dockerfile").exists()

    def test_astro_writes_nginx_conf(self, tmp_path):
        """init_docker creates docker/nginx.conf for Astro projects."""
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"astro": "^4.0.0"}})
        )
        fw = {"language": "node", "framework": "astro", "entry_point": "nginx"}
        result = init_docker(tmp_path, "myapp", fw)
        nginx_conf = tmp_path / "docker" / "nginx.conf"
        assert nginx_conf.exists()
        assert "docker/nginx.conf" in result["files"]


# ---------------------------------------------------------------------------
# add_service
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-deployment compose generation
# ---------------------------------------------------------------------------

class TestGenerateComposeForDeployment:
    def test_context_build(self):
        """Context strategy uses build: stanza."""
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "dev",
            {"docker_context": "default", "build_strategy": "context"}, None,
        )
        compose = yaml.safe_load(result)
        assert "build" in compose["services"]["app"]
        assert "image" not in compose["services"]["app"]

    def test_github_actions_image(self):
        """github-actions strategy uses image: stanza."""
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "prod",
            {"build_strategy": "github-actions", "image": "ghcr.io/owner/myapp"},
            None,
        )
        compose = yaml.safe_load(result)
        assert compose["services"]["app"]["image"] == "ghcr.io/owner/myapp:latest"
        assert "build" not in compose["services"]["app"]

    def test_env_file_path(self):
        """env_file references .<name>.env (relative to compose file in docker/)."""
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "prod",
            {"build_strategy": "context"}, None,
        )
        compose = yaml.safe_load(result)
        assert compose["services"]["app"]["env_file"] == [".prod.env"]

    def test_caddy_labels(self):
        """Caddy labels included when hostname + reverse_proxy: caddy."""
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "prod",
            {"build_strategy": "context", "hostname": "app.example.com", "reverse_proxy": "caddy"},
            None,
        )
        compose = yaml.safe_load(result)
        labels = compose["services"]["app"]["labels"]
        assert labels["caddy"] == "app.example.com"

    def test_no_caddy_labels_without_reverse_proxy(self):
        """No Caddy labels when reverse_proxy not set."""
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "prod",
            {"build_strategy": "context", "hostname": "app.example.com"},
            None,
        )
        compose = yaml.safe_load(result)
        assert "labels" not in compose["services"]["app"]

    def test_service_filtering(self):
        """Only services listed in deployment are included."""
        all_services = [
            {"type": "postgres", "version": "16"},
            {"type": "redis", "version": "7"},
        ]
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "prod",
            {"build_strategy": "context", "services": ["app", "postgres"]},
            all_services,
        )
        compose = yaml.safe_load(result)
        assert "postgres" in compose["services"]
        assert "redis" not in compose["services"]

    def test_all_services_when_no_filter(self):
        """All services included when no services filter in deployment."""
        all_services = [
            {"type": "postgres", "version": "16"},
            {"type": "redis", "version": "7"},
        ]
        result = generate_compose_for_deployment(
            "myapp", {"language": "node"}, "dev",
            {"build_strategy": "context"},
            all_services,
        )
        compose = yaml.safe_load(result)
        assert "postgres" in compose["services"]
        assert "redis" in compose["services"]

    def test_astro_port(self):
        """Astro uses port 8080."""
        fw = {"language": "node", "framework": "astro", "entry_point": "nginx"}
        result = generate_compose_for_deployment(
            "myapp", fw, "dev", {"build_strategy": "context"}, None,
        )
        assert "8080" in result


# ---------------------------------------------------------------------------
# Entrypoint generation
# ---------------------------------------------------------------------------

class TestGenerateEntrypoint:
    def test_basic_structure(self):
        result = generate_entrypoint({"language": "node", "framework": "express"})
        assert result.startswith("#!/bin/sh")
        assert "set -e" in result
        assert 'exec "$@"' in result

    def test_django_migrations(self):
        result = generate_entrypoint({"language": "python", "framework": "django"})
        assert "manage.py migrate" in result

    def test_node_prisma(self):
        result = generate_entrypoint({"language": "node", "framework": "next"})
        assert "prisma migrate deploy" in result

    def test_age_key_setup(self):
        result = generate_entrypoint({"language": "node", "framework": "express"})
        assert "SOPS_AGE_KEY_FILE" in result


# ---------------------------------------------------------------------------
# GitHub Actions split workflows
# ---------------------------------------------------------------------------

class TestGenerateGitHubBuildWorkflow:
    def test_basic_structure(self):
        wf = generate_github_build_workflow()
        assert "name: Build" in wf
        assert "workflow_dispatch" in wf
        assert "ghcr.io" in wf
        assert "linux/amd64" in wf

    def test_custom_platform(self):
        wf = generate_github_build_workflow("linux/arm64")
        assert "linux/arm64" in wf

    def test_push_trigger(self):
        wf = generate_github_build_workflow()
        assert "push:" in wf
        assert "branches: [main]" in wf


class TestGenerateGitHubDeployWorkflow:
    def test_compose_mode(self):
        wf = generate_github_deploy_workflow("myapp", "docker/docker-compose.prod.yml")
        assert "name: Deploy" in wf
        assert "workflow_run:" in wf
        assert "workflow_dispatch" in wf
        assert "docker compose" in wf
        assert "workflow_run.conclusion == 'success'" in wf

    def test_run_mode(self):
        wf = generate_github_deploy_workflow(
            "myapp", deploy_mode="run",
            docker_run_cmd="docker run -d --name myapp ghcr.io/owner/myapp:latest",
        )
        assert "docker stop myapp" in wf
        assert "docker rm myapp" in wf


# ---------------------------------------------------------------------------
# generate_artifacts (integration)
# ---------------------------------------------------------------------------

class TestGenerateArtifacts:
    def test_creates_per_deployment_compose(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "myapp",
            "deployments": {
                "dev": {"docker_context": "default", "build_strategy": "context"},
                "prod": {"docker_context": "prod-host", "build_strategy": "context"},
            },
        }
        result = generate_artifacts(tmp_path, cfg)
        assert result["status"] == "created"
        assert (tmp_path / "docker" / "docker-compose.dev.yml").exists()
        assert (tmp_path / "docker" / "docker-compose.prod.yml").exists()
        assert (tmp_path / "docker" / "entrypoint.sh").exists()
        assert (tmp_path / "docker" / "Justfile").exists()

    def test_stack_mode_generates_compose(self, tmp_path):
        """Stack-mode deployments must produce a compose file (docker stack deploy needs one)."""
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "my-app",  # hyphen stresses env-var naming
            "deployments": {
                "prod": {
                    "docker_context": "swarm-mgr",
                    "build_strategy": "github-actions",
                    "image": "ghcr.io/owner/myapp",
                    "deploy_mode": "stack",
                    "swarm": True,
                },
            },
        }
        generate_artifacts(tmp_path, cfg)
        compose = tmp_path / "docker" / "docker-compose.prod.yml"
        assert compose.exists(), "stack mode must emit a compose file"
        content = compose.read_text()
        assert "docker stack deploy" in content  # header comment
        assert "deploy:" in content
        # Swarm ignores service-level `restart:` (warns at deploy); the
        # deploy.restart_policy block handles it. We must not emit both.
        loaded = yaml.safe_load(content)
        assert "restart" not in loaded["services"]["app"]
        # App-name hyphens must become underscores in the PORT env var
        # (shell var names cannot contain `-`).
        assert "MY_APP_PORT" in content
        assert "MY-APP_PORT" not in content

    def test_single_deployment_flag(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "myapp",
            "deployments": {
                "dev": {"docker_context": "default", "build_strategy": "context"},
                "prod": {"docker_context": "prod-host", "build_strategy": "context"},
            },
        }
        result = generate_artifacts(tmp_path, cfg, deployment="prod")
        assert (tmp_path / "docker" / "docker-compose.prod.yml").exists()
        # dev should not be generated when deployment="prod"
        assert not (tmp_path / "docker" / "docker-compose.dev.yml").exists()

    def test_github_actions_workflows(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "prod-host",
                    "build_strategy": "github-actions",
                    "image": "ghcr.io/owner/myapp",
                    "platform": "linux/amd64",
                },
            },
        }
        result = generate_artifacts(tmp_path, cfg)
        assert (tmp_path / ".github" / "workflows" / "build.yml").exists()
        assert (tmp_path / ".github" / "workflows" / "deploy.yml").exists()

    def test_gitignore_updated(self, tmp_path):
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        cfg = {
            "app_name": "myapp",
            "deployments": {"dev": {"docker_context": "default"}},
        }
        generate_artifacts(tmp_path, cfg)
        content = (tmp_path / ".gitignore").read_text()
        assert "docker/.*.env" in content

    def test_entrypoint_executable(self, tmp_path):
        cfg = {
            "app_name": "myapp",
            "deployments": {"dev": {"docker_context": "default"}},
        }
        generate_artifacts(tmp_path, cfg)
        entrypoint = tmp_path / "docker" / "entrypoint.sh"
        assert entrypoint.exists()
        import stat
        assert entrypoint.stat().st_mode & stat.S_IXUSR


class TestAddService:
    def _create_compose(self, tmp_path, services=None):
        """Create a docker-compose.yml for add_service tests."""
        from rundbat.generators import generate_compose
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir(parents=True, exist_ok=True)
        content = generate_compose("testapp", {"language": "node"}, services)
        (docker_dir / "docker-compose.yml").write_text(content)

    def test_adds_postgres(self, tmp_path):
        self._create_compose(tmp_path)
        result = add_service(tmp_path, "postgres", "16")
        assert result["status"] == "added"
        compose = yaml.safe_load((tmp_path / "docker" / "docker-compose.yml").read_text())
        assert "postgres" in compose["services"]
        assert "postgres" in compose["services"]["app"]["depends_on"]

    def test_already_exists(self, tmp_path):
        services = [{"type": "postgres", "version": "16"}]
        self._create_compose(tmp_path, services)
        result = add_service(tmp_path, "postgres")
        assert result["status"] == "already_exists"

    def test_no_compose(self, tmp_path):
        result = add_service(tmp_path, "postgres")
        assert "error" in result

    def test_unknown_service(self, tmp_path):
        self._create_compose(tmp_path)
        result = add_service(tmp_path, "oracle")
        assert "error" in result

    def test_adds_redis(self, tmp_path):
        self._create_compose(tmp_path)
        result = add_service(tmp_path, "redis", "7")
        assert result["status"] == "added"
        compose = yaml.safe_load((tmp_path / "docker" / "docker-compose.yml").read_text())
        assert "redis" in compose["services"]


# ---------------------------------------------------------------------------
# Swarm plumbing in generate_compose_for_deployment (T03)
# ---------------------------------------------------------------------------

_FRAMEWORK_EXPRESS = {"language": "node", "framework": "express",
                      "entry_point": "npm start"}


def _swarm_deploy_cfg(**overrides):
    # Swarm deployments require an explicit `image:` — the generator
    # raises GenerateError otherwise. Default to a sensible tag so
    # existing suite tests stay focused on their own behavior.
    cfg = {
        "docker_context": "prod-host",
        "build_strategy": "context",
        "swarm": True,
        "image": "myapp:prod",
    }
    cfg.update(overrides)
    return cfg


class TestGenerateComposeSwarm:
    def test_swarm_emits_header(self):
        """Swarm output is prefixed with a 'docker stack deploy' header."""
        cfg = _swarm_deploy_cfg()
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg, all_services=None
        )
        first_line = out.splitlines()[0]
        assert first_line.startswith("# Deploy with: docker stack deploy")
        assert "docker/docker-compose.prod.yml" in first_line
        assert "myapp_prod" in first_line  # default stack name

    def test_swarm_header_uses_stack_name_override(self):
        cfg = _swarm_deploy_cfg(stack_name="custom_stack")
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        assert out.splitlines()[0].endswith("custom_stack")

    def test_swarm_caddy_labels_under_deploy(self):
        """When swarm=True, Caddy labels live under services.app.deploy.labels."""
        cfg = _swarm_deploy_cfg(hostname="app.example.com", reverse_proxy="caddy")
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        # Strip the header line before parsing
        body = "\n".join(out.splitlines()[1:])
        data = yaml.safe_load(body)
        app = data["services"]["app"]
        assert "labels" not in app
        assert "deploy" in app
        assert app["deploy"]["labels"]["caddy"] == "app.example.com"

    def test_swarm_deploy_block_per_service(self):
        """Every service gets a deploy: block with the standard fields."""
        cfg = _swarm_deploy_cfg()
        all_services = [{"type": "postgres", "version": "16"}]
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg, all_services=all_services
        )
        body = "\n".join(out.splitlines()[1:])
        data = yaml.safe_load(body)
        for svc_name in ("app", "postgres"):
            deploy = data["services"][svc_name]["deploy"]
            assert deploy["replicas"] == 1
            assert deploy["restart_policy"]["condition"] == "on-failure"
            assert deploy["update_config"]["order"] == "start-first"

    def test_swarm_false_unchanged_regression(self):
        """Compose-mode output (swarm absent) still emits top-level labels."""
        cfg = {
            "docker_context": "prod-host",
            "build_strategy": "context",
            "hostname": "app.example.com",
            "reverse_proxy": "caddy",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        # No header
        assert not out.splitlines()[0].startswith("# Deploy with:")
        data = yaml.safe_load(out)
        app = data["services"]["app"]
        assert app["labels"]["caddy"] == "app.example.com"
        assert "deploy" not in app


class TestGenerateComposeSwarmSecrets:
    """T04 — Swarm-native secret stanza emission."""

    def test_swarm_emits_top_level_secrets_stanza(self):
        cfg = _swarm_deploy_cfg(secrets=["POSTGRES_PASSWORD", "SESSION_SECRET"])
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        data = yaml.safe_load("\n".join(out.splitlines()[1:]))
        assert "secrets" in data
        assert data["secrets"]["myapp_postgres_password"] == {"external": True}
        assert data["secrets"]["myapp_session_secret"] == {"external": True}

    def test_swarm_service_secrets_attachment(self):
        cfg = _swarm_deploy_cfg(secrets=["POSTGRES_PASSWORD"])
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        data = yaml.safe_load("\n".join(out.splitlines()[1:]))
        app = data["services"]["app"]
        assert app["secrets"] == [
            {"source": "myapp_postgres_password", "target": "postgres_password"},
        ]

    def test_swarm_file_env_var_set(self):
        """_FILE env var points at /run/secrets/<target>."""
        cfg = _swarm_deploy_cfg(secrets=["POSTGRES_PASSWORD"])
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        data = yaml.safe_load("\n".join(out.splitlines()[1:]))
        env = data["services"]["app"]["environment"]
        assert env["POSTGRES_PASSWORD_FILE"] == "/run/secrets/postgres_password"

    def test_swarm_no_secrets_emits_no_stanza(self):
        cfg = _swarm_deploy_cfg()
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        data = yaml.safe_load("\n".join(out.splitlines()[1:]))
        assert "secrets" not in data
        assert "secrets" not in data["services"]["app"]

    def test_non_swarm_with_secrets_emits_no_swarm_stanza(self):
        """Regression: compose-mode deployments never emit swarm secret stanzas."""
        cfg = {
            "docker_context": "prod",
            "build_strategy": "context",
            "secrets": ["POSTGRES_PASSWORD"],
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        data = yaml.safe_load(out)
        assert "secrets" not in data
        assert "secrets" not in data["services"]["app"]


class TestGenerateJustfileStackMode:
    def test_stack_mode_recipes(self):
        deployments = {
            "prod": {
                "docker_context": "prod-host",
                "deploy_mode": "stack",
                "swarm": True,
                "build_strategy": "context",
            }
        }
        out = generate_justfile("myapp", services=None, deployments=deployments)
        assert "docker stack deploy -c docker/docker-compose.prod.yml myapp_prod" in out
        assert "docker stack rm myapp_prod" in out
        assert "docker service logs -f myapp_prod_app" in out
        # build is NOT stack — still uses docker compose
        assert "docker compose -f docker/docker-compose.prod.yml build" in out

    def test_stack_mode_uses_stack_name_override(self):
        deployments = {
            "prod": {
                "docker_context": "prod-host",
                "deploy_mode": "stack",
                "stack_name": "custom_stack",
                "build_strategy": "context",
            }
        }
        out = generate_justfile("myapp", services=None, deployments=deployments)
        assert "custom_stack" in out
        assert "myapp_prod" not in out.replace("myapp_prod_build", "")  # no default name

    def test_compose_mode_unchanged_regression(self):
        deployments = {
            "prod": {
                "docker_context": "prod-host",
                "deploy_mode": "compose",
                "build_strategy": "context",
            }
        }
        out = generate_justfile("myapp", services=None, deployments=deployments)
        assert "docker stack deploy" not in out
        assert "docker compose -f docker/docker-compose.prod.yml up -d" in out


class TestGenerateComposeSwarmImage:
    """Sprint 009 — image requirement for swarm deployments.

    Stack deploys need an image: reference. The generator must emit
    image: + build: for build-on-host strategies, keep the
    github-actions path unchanged, and refuse to produce a partial
    compose for swarm configs that omit image:.
    """

    import pytest

    def test_context_swarm_with_image(self):
        cfg = {
            "docker_context": "prod",
            "build_strategy": "context",
            "swarm": True,
            "image": "myapp:prod",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        body = "\n".join(out.splitlines()[1:])  # strip swarm header
        data = yaml.safe_load(body)
        app = data["services"]["app"]
        assert app["image"] == "myapp:prod"
        assert app["build"]["context"] == ".."
        assert app["build"]["dockerfile"] == "docker/Dockerfile"

    def test_ssh_transfer_swarm_with_image(self):
        cfg = {
            "docker_context": "prod",
            "build_strategy": "ssh-transfer",
            "swarm": True,
            "image": "myapp:prod",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        body = "\n".join(out.splitlines()[1:])
        data = yaml.safe_load(body)
        app = data["services"]["app"]
        assert app["image"] == "myapp:prod"
        assert "build" in app

    def test_github_actions_swarm_with_image_regression(self):
        """github-actions + swarm path unchanged — image only, no build."""
        cfg = {
            "docker_context": "prod",
            "build_strategy": "github-actions",
            "swarm": True,
            "image": "ghcr.io/owner/myapp",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        body = "\n".join(out.splitlines()[1:])
        data = yaml.safe_load(body)
        app = data["services"]["app"]
        assert app["image"] == "ghcr.io/owner/myapp:latest"
        assert "build" not in app

    def test_context_swarm_missing_image_errors(self):
        import pytest
        from rundbat.generators import GenerateError
        cfg = {
            "docker_context": "prod",
            "build_strategy": "context",
            "swarm": True,
        }
        with pytest.raises(GenerateError) as exc:
            generate_compose_for_deployment(
                "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
            )
        msg = str(exc.value)
        assert "prod" in msg
        assert "image:" in msg
        assert "myapp:prod" in msg

    def test_ssh_transfer_swarm_missing_image_errors(self):
        import pytest
        from rundbat.generators import GenerateError
        cfg = {
            "docker_context": "prod",
            "build_strategy": "ssh-transfer",
            "swarm": True,
        }
        with pytest.raises(GenerateError):
            generate_compose_for_deployment(
                "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
            )

    def test_github_actions_swarm_missing_image_uses_default(self):
        """GA path is exempt — it has an implicit ghcr.io default."""
        cfg = {
            "docker_context": "prod",
            "build_strategy": "github-actions",
            "swarm": True,
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "prod", cfg
        )
        body = "\n".join(out.splitlines()[1:])
        data = yaml.safe_load(body)
        assert data["services"]["app"]["image"] == "ghcr.io/owner/myapp:latest"

    def test_non_swarm_context_no_image_unchanged(self):
        """Regression: compose-mode without image still emits build only."""
        cfg = {
            "docker_context": "dev",
            "build_strategy": "context",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "dev", cfg
        )
        data = yaml.safe_load(out)
        app = data["services"]["app"]
        assert "build" in app
        assert "image" not in app

    def test_non_swarm_context_with_image_emits_both(self):
        """Explicit image in compose-mode: both image and build."""
        cfg = {
            "docker_context": "dev",
            "build_strategy": "context",
            "image": "myapp:dev",
        }
        out = generate_compose_for_deployment(
            "myapp", _FRAMEWORK_EXPRESS, "dev", cfg
        )
        data = yaml.safe_load(out)
        app = data["services"]["app"]
        assert app["image"] == "myapp:dev"
        assert "build" in app


class TestGenerateArtifactsSwarmImageError:
    """generate_artifacts returns {'error': ...} on swarm-missing-image."""

    def test_missing_image_returns_error_and_writes_no_compose(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "my-app",
            "deployments": {
                "prod": {
                    "docker_context": "swarm-mgr",
                    "build_strategy": "context",
                    "deploy_mode": "stack",
                    "swarm": True,
                    # no image!
                },
            },
        }
        result = generate_artifacts(tmp_path, cfg)
        assert "error" in result
        assert "prod" in result["error"]
        assert "image:" in result["error"]
        # No compose file written for the invalid deployment
        assert not (tmp_path / "docker" / "docker-compose.prod.yml").exists()


class TestGenerateArtifactsStackModeImage:
    def test_stack_mode_emits_image_field(self, tmp_path):
        """Stack-mode context-strategy compose has image: + build:."""
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "myapp", "dependencies": {"express": "^4"}})
        )
        cfg = {
            "app_name": "my-app",
            "deployments": {
                "prod": {
                    "docker_context": "swarm-mgr",
                    "build_strategy": "context",
                    "deploy_mode": "stack",
                    "swarm": True,
                    "image": "my-app:prod",
                },
            },
        }
        generate_artifacts(tmp_path, cfg)
        compose = tmp_path / "docker" / "docker-compose.prod.yml"
        assert compose.exists()
        content = compose.read_text()
        # strip the stack-deploy header
        body = "\n".join(content.splitlines()[1:])
        data = yaml.safe_load(body)
        app = data["services"]["app"]
        assert app["image"] == "my-app:prod"
        assert "build" in app

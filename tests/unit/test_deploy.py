"""Tests for deploy module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from rundbat.deploy import (
    DeployError,
    load_deploy_config,
    _context_name,
    _context_exists,
    create_context,
    ensure_context,
    verify_access,
    deploy,
    init_deployment,
)


# ---------------------------------------------------------------------------
# DeployError
# ---------------------------------------------------------------------------

class TestDeployError:
    def test_to_dict(self):
        err = DeployError("something broke", command=["docker", "info"],
                          exit_code=1, stderr="fail")
        d = err.to_dict()
        assert d["error"] == "something broke"
        assert d["command"] == "docker info"
        assert d["exit_code"] == 1
        assert d["stderr"] == "fail"

    def test_to_dict_no_command(self):
        err = DeployError("no cmd")
        d = err.to_dict()
        assert d["command"] is None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestLoadDeployConfig:
    def test_loads_valid_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "host": "ssh://root@example.com",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "hostname": "app.example.com",
                },
            },
        }))

        result = load_deploy_config("prod")
        assert result["host"] == "ssh://root@example.com"
        assert result["compose_file"] == "docker/docker-compose.prod.yml"
        assert result["hostname"] == "app.example.com"

    def test_default_compose_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {"host": "ssh://root@example.com"},
            },
        }))

        result = load_deploy_config("prod")
        assert result["compose_file"] == "docker/docker-compose.yml"

    def test_missing_deployment(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {"staging": {"host": "ssh://root@staging"}},
        }))

        with pytest.raises(DeployError, match="No deployment 'prod'"):
            load_deploy_config("prod")

    def test_no_deployments_section(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
        }))

        with pytest.raises(DeployError, match="No deployment 'prod'"):
            load_deploy_config("prod")

    def test_missing_host(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {"compose_file": "docker/docker-compose.yml"},
            },
        }))

        with pytest.raises(DeployError, match="missing required 'host'"):
            load_deploy_config("prod")


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

class TestContextHelpers:
    def test_context_name(self):
        assert _context_name("myapp", "prod") == "myapp-prod"

    @patch("rundbat.deploy._run_docker")
    def test_context_exists_true(self, mock_docker):
        mock_docker.return_value = "default\nmyapp-prod\nother"
        assert _context_exists("myapp-prod") is True

    @patch("rundbat.deploy._run_docker")
    def test_context_exists_false(self, mock_docker):
        mock_docker.return_value = "default\nother"
        assert _context_exists("myapp-prod") is False

    @patch("rundbat.deploy._run_docker")
    def test_context_exists_docker_error(self, mock_docker):
        mock_docker.side_effect = DeployError("docker not found")
        assert _context_exists("myapp-prod") is False

    @patch("rundbat.deploy._run_docker")
    def test_create_context(self, mock_docker):
        mock_docker.return_value = ""
        result = create_context("myapp-prod", "ssh://root@host")
        assert result == "myapp-prod"
        mock_docker.assert_called_once_with([
            "context", "create", "myapp-prod",
            "--docker", "host=ssh://root@host",
        ])

    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy.create_context")
    def test_ensure_context_creates_when_missing(self, mock_create, mock_exists):
        mock_exists.return_value = False
        mock_create.return_value = "myapp-prod"
        result = ensure_context("myapp", "prod", "ssh://root@host")
        assert result == "myapp-prod"
        mock_create.assert_called_once_with("myapp-prod", "ssh://root@host")

    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy.create_context")
    def test_ensure_context_skips_when_exists(self, mock_create, mock_exists):
        mock_exists.return_value = True
        result = ensure_context("myapp", "prod", "ssh://root@host")
        assert result == "myapp-prod"
        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# Verify access
# ---------------------------------------------------------------------------

class TestVerifyAccess:
    @patch("rundbat.deploy._run_docker")
    def test_success(self, mock_docker):
        mock_docker.return_value = "24.0.7"
        result = verify_access("myapp-prod")
        assert result["status"] == "ok"
        assert result["server_version"] == "24.0.7"

    @patch("rundbat.deploy._run_docker")
    def test_failure(self, mock_docker):
        mock_docker.side_effect = DeployError("fail", command=["docker"],
                                               exit_code=1, stderr="conn refused")
        with pytest.raises(DeployError, match="Cannot connect"):
            verify_access("myapp-prod")


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

class TestDeploy:
    def _setup_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "host": "ssh://root@docker1.example.com",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "hostname": "app.example.com",
                },
            },
        }))
        # Create the compose file so deploy doesn't error
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        (docker_dir / "docker-compose.prod.yml").write_text("version: '3'\n")

    @patch("rundbat.deploy._run_docker")
    @patch("rundbat.deploy.ensure_context")
    def test_dry_run(self, mock_ensure, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_ensure.return_value = "myapp-prod"

        result = deploy("prod", dry_run=True)
        assert result["status"] == "dry_run"
        assert "--context" in result["command"]
        assert "myapp-prod" in result["command"]
        assert "--build" in result["command"]
        assert result["hostname"] == "app.example.com"
        mock_docker.assert_not_called()

    @patch("rundbat.deploy._run_docker")
    @patch("rundbat.deploy.ensure_context")
    def test_dry_run_no_build(self, mock_ensure, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_ensure.return_value = "myapp-prod"

        result = deploy("prod", dry_run=True, no_build=True)
        assert "--build" not in result["command"]

    @patch("rundbat.deploy._run_docker")
    @patch("rundbat.deploy.ensure_context")
    def test_deploy_success(self, mock_ensure, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_ensure.return_value = "myapp-prod"
        mock_docker.return_value = ""

        result = deploy("prod")
        assert result["status"] == "success"
        assert result["url"] == "https://app.example.com/"
        mock_docker.assert_called_once()
        call_args = mock_docker.call_args[0][0]
        assert "--context" in call_args
        assert "--build" in call_args

    @patch("rundbat.deploy.ensure_context")
    def test_missing_compose_file(self, mock_ensure, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "host": "ssh://root@host",
                    "compose_file": "docker/docker-compose.prod.yml",
                },
            },
        }))
        mock_ensure.return_value = "myapp-prod"

        with pytest.raises(DeployError, match="Compose file not found"):
            deploy("prod")


# ---------------------------------------------------------------------------
# Init deployment
# ---------------------------------------------------------------------------

class TestInitDeployment:
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    def test_creates_new(self, mock_exists, mock_create, mock_verify,
                         tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_exists.return_value = False
        mock_create.return_value = "myapp-prod"
        mock_verify.return_value = {"status": "ok"}

        result = init_deployment("prod", "ssh://root@host",
                                 compose_file="docker/prod.yml",
                                 hostname="app.example.com")
        assert result["status"] == "ok"
        assert result["context"] == "myapp-prod"

        # Verify config was saved
        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["host"] == "ssh://root@host"
        assert saved["deployments"]["prod"]["compose_file"] == "docker/prod.yml"
        assert saved["deployments"]["prod"]["hostname"] == "app.example.com"

    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy._context_exists")
    def test_existing_context(self, mock_exists, mock_verify,
                              tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_exists.return_value = True
        mock_verify.return_value = {"status": "ok"}

        result = init_deployment("prod", "ssh://root@host")
        assert result["status"] == "ok"

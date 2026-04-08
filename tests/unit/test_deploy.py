"""Tests for deploy module."""

from unittest.mock import patch

import pytest
import yaml

from rundbat.deploy import (
    DeployError,
    load_deploy_config,
    _context_name,
    _context_exists,
    create_context,
    verify_access,
    deploy,
    init_deployment,
    get_current_context,
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
# get_current_context
# ---------------------------------------------------------------------------

class TestGetCurrentContext:
    @patch("rundbat.deploy._run_docker")
    def test_returns_context_name(self, mock_docker):
        mock_docker.return_value = "orbstack"
        assert get_current_context() == "orbstack"

    @patch("rundbat.deploy._run_docker")
    def test_fallback_on_error(self, mock_docker):
        mock_docker.side_effect = DeployError("no docker")
        assert get_current_context() == "default"


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
                    "docker_context": "myapp-prod",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "hostname": "app.example.com",
                },
            },
        }))

        result = load_deploy_config("prod")
        assert result["docker_context"] == "myapp-prod"
        assert result["compose_file"] == "docker/docker-compose.prod.yml"
        assert result["hostname"] == "app.example.com"

    def test_default_compose_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {"docker_context": "myapp-prod"},
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
            "deployments": {"staging": {"docker_context": "myapp-staging"}},
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

    def test_missing_docker_context(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {"compose_file": "docker/docker-compose.yml"},
            },
        }))

        with pytest.raises(DeployError, match="missing required 'docker_context'"):
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
                    "docker_context": "myapp-prod",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "hostname": "app.example.com",
                },
            },
        }))
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        (docker_dir / "docker-compose.prod.yml").write_text("version: '3'\n")

    @patch("rundbat.deploy._run_docker")
    def test_dry_run(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)

        result = deploy("prod", dry_run=True)
        assert result["status"] == "dry_run"
        assert "--context" in result["command"]
        assert "myapp-prod" in result["command"]
        assert "--build" in result["command"]
        assert result["hostname"] == "app.example.com"
        mock_docker.assert_not_called()

    @patch("rundbat.deploy._run_docker")
    def test_dry_run_no_build(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)

        result = deploy("prod", dry_run=True, no_build=True)
        assert "--build" not in result["command"]

    @patch("rundbat.deploy._run_docker")
    def test_deploy_success(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_docker.return_value = ""

        result = deploy("prod")
        assert result["status"] == "success"
        assert result["url"] == "https://app.example.com/"
        mock_docker.assert_called_once()
        call_args = mock_docker.call_args[0][0]
        assert "--context" in call_args
        assert "--build" in call_args

    def test_missing_compose_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "myapp-prod",
                    "compose_file": "docker/docker-compose.prod.yml",
                },
            },
        }))

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

        # Verify config was saved with docker_context
        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["docker_context"] == "myapp-prod"
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

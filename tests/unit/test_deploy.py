"""Tests for deploy module."""

from unittest.mock import patch

import pytest
import yaml

from rundbat.deploy import (
    DeployError,
    VALID_STRATEGIES,
    load_deploy_config,
    _context_name_from_host,
    _context_exists,
    _find_context_for_host,
    _detect_remote_platform,
    _parse_ssh_host,
    _ssh_cmd,
    _get_buildable_images,
    _cleanup_remote,
    _build_docker_run_cmd,
    _deploy_run,
    _prepare_env,
    _get_github_repo,
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
# Platform detection
# ---------------------------------------------------------------------------

class TestDetectRemotePlatform:
    @patch("rundbat.deploy._run_docker")
    def test_amd64(self, mock_docker):
        mock_docker.return_value = "x86_64"
        assert _detect_remote_platform("myctx") == "linux/amd64"

    @patch("rundbat.deploy._run_docker")
    def test_arm64(self, mock_docker):
        mock_docker.return_value = "aarch64"
        assert _detect_remote_platform("myctx") == "linux/arm64"

    @patch("rundbat.deploy._run_docker")
    def test_failure_returns_none(self, mock_docker):
        mock_docker.side_effect = DeployError("cannot connect")
        assert _detect_remote_platform("myctx") is None


class TestParseSSHHost:
    def test_strips_ssh_prefix(self):
        assert _parse_ssh_host("ssh://root@host") == "root@host"

    def test_no_prefix(self):
        assert _parse_ssh_host("root@host") == "root@host"

    def test_with_port(self):
        assert _parse_ssh_host("ssh://root@host:2222") == "root@host:2222"


class TestSSHCmd:
    def test_without_key(self):
        result = _ssh_cmd("ssh://root@host")
        assert result == "ssh root@host"

    def test_with_key(self):
        result = _ssh_cmd("ssh://root@host", ssh_key="config/prod/deploy-key")
        assert result == "ssh -i config/prod/deploy-key -o StrictHostKeyChecking=no root@host"

    def test_none_key(self):
        result = _ssh_cmd("ssh://root@host", ssh_key=None)
        assert result == "ssh root@host"


class TestGetBuildableImages:
    def test_finds_build_services(self, tmp_path):
        compose = {
            "services": {
                "app": {"build": {"context": ".."}, "ports": ["3000:3000"]},
                "postgres": {"image": "postgres:16"},
            }
        }
        compose_file = tmp_path / "docker" / "docker-compose.yml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text(yaml.dump(compose))

        images = _get_buildable_images(str(compose_file))
        assert len(images) == 1
        assert images[0].endswith("-app")

    def test_no_build_services(self, tmp_path):
        compose = {
            "services": {
                "postgres": {"image": "postgres:16"},
            }
        }
        compose_file = tmp_path / "docker" / "docker-compose.yml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text(yaml.dump(compose))

        assert _get_buildable_images(str(compose_file)) == []

    def test_missing_file(self):
        assert _get_buildable_images("/nonexistent/compose.yml") == []

    def test_prefers_explicit_image_tag_when_build_present(self, tmp_path):
        """Sprint 009: explicit image: wins over <project>-<service> default.

        Swarm stack deploys reference image: tags directly — the
        transferred tag must match or the remote pull will fail.
        """
        compose = {
            "services": {
                "app": {
                    "build": {"context": ".."},
                    "image": "myapp:prod",
                    "ports": ["3000:3000"],
                },
            }
        }
        compose_file = tmp_path / "docker" / "docker-compose.yml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text(yaml.dump(compose))

        images = _get_buildable_images(str(compose_file))
        assert images == ["myapp:prod"]

    def test_build_only_falls_back_to_default(self, tmp_path):
        """Regression: build without image still gets the <project>-<service> default."""
        compose = {
            "services": {
                "app": {"build": {"context": ".."}},
            }
        }
        compose_file = tmp_path / "docker" / "docker-compose.yml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text(yaml.dump(compose))

        images = _get_buildable_images(str(compose_file))
        # parent.parent.name is the tmp_path's own basename
        assert len(images) == 1
        assert images[0].endswith("-app")

    def test_image_only_excluded(self, tmp_path):
        """Regression: image without build stays excluded (nothing to transfer)."""
        compose = {
            "services": {
                "postgres": {"image": "postgres:16"},
            }
        }
        compose_file = tmp_path / "docker" / "docker-compose.yml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text(yaml.dump(compose))

        assert _get_buildable_images(str(compose_file)) == []


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

class TestCleanupRemote:
    @patch("rundbat.deploy._run_docker")
    def test_success(self, mock_docker):
        mock_docker.return_value = "Total reclaimed space: 500MB"
        result = _cleanup_remote("myctx")
        assert result["status"] == "ok"

    @patch("rundbat.deploy._run_docker")
    def test_failure_non_fatal(self, mock_docker):
        mock_docker.side_effect = DeployError("prune failed")
        result = _cleanup_remote("myctx")
        assert result["status"] == "skipped"


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
                    "host": "ssh://root@host",
                    "platform": "linux/amd64",
                    "build_strategy": "ssh-transfer",
                },
            },
        }))

        result = load_deploy_config("prod")
        assert result["docker_context"] == "myapp-prod"
        assert result["compose_file"] == "docker/docker-compose.prod.yml"
        assert result["hostname"] == "app.example.com"
        assert result["host"] == "ssh://root@host"
        assert result["platform"] == "linux/amd64"
        assert result["build_strategy"] == "ssh-transfer"

    def test_default_strategy(self, tmp_path, monkeypatch):
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
        assert result["build_strategy"] == "context"
        assert result["host"] is None
        assert result["platform"] is None

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
        assert result["compose_file"] == "docker/docker-compose.prod.yml"

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
    def test_context_name_from_host(self):
        assert _context_name_from_host("ssh://root@docker1.example.com") == "docker1.example.com"

    def test_context_name_from_host_ip(self):
        assert _context_name_from_host("ssh://root@192.168.1.10") == "192.168.1.10"

    def test_context_name_from_host_with_port(self):
        assert _context_name_from_host("ssh://root@host:2222") == "host"

    def test_context_name_from_host_no_user(self):
        assert _context_name_from_host("ssh://docker1.example.com") == "docker1.example.com"

    @patch("rundbat.deploy._run_docker")
    def test_find_context_for_host_found(self, mock_docker):
        mock_docker.return_value = "default\tunix:///var/run/docker.sock\nmyctx\tssh://root@host"
        assert _find_context_for_host("ssh://root@host") == "myctx"

    @patch("rundbat.deploy._run_docker")
    def test_find_context_for_host_not_found(self, mock_docker):
        mock_docker.return_value = "default\tunix:///var/run/docker.sock"
        assert _find_context_for_host("ssh://root@other") is None

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
# Deploy — context strategy
# ---------------------------------------------------------------------------

class TestDeployContext:
    def _setup_config(self, tmp_path, strategy="context", host=None):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        deploy_cfg = {
            "docker_context": "myapp-prod",
            "compose_file": "docker/docker-compose.prod.yml",
            "hostname": "app.example.com",
            "build_strategy": strategy,
        }
        if host:
            deploy_cfg["host"] = host
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {"prod": deploy_cfg},
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
        assert result["strategy"] == "context"
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

    @patch("rundbat.deploy._cleanup_remote")
    @patch("rundbat.deploy._run_docker")
    def test_deploy_success(self, mock_docker, mock_cleanup, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_docker.return_value = ""
        mock_cleanup.return_value = {"status": "ok", "output": ""}

        result = deploy("prod")
        assert result["status"] == "success"
        assert result["strategy"] == "context"
        assert result["url"] == "https://app.example.com/"
        mock_docker.assert_called_once()
        mock_cleanup.assert_called_once_with("myapp-prod")

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

    def test_invalid_strategy(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)

        with pytest.raises(DeployError, match="Unknown build strategy"):
            deploy("prod", strategy="teleport")


# ---------------------------------------------------------------------------
# Deploy — ssh-transfer strategy
# ---------------------------------------------------------------------------

class TestDeploySSHTransfer:
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
                    "host": "ssh://root@docker1.example.com",
                    "platform": "linux/amd64",
                    "build_strategy": "ssh-transfer",
                },
            },
        }))
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        compose = {
            "services": {
                "app": {"build": {"context": ".."}, "ports": ["3000:3000"]},
                "postgres": {"image": "postgres:16"},
            }
        }
        (docker_dir / "docker-compose.prod.yml").write_text(yaml.dump(compose))

    @patch("rundbat.deploy._run_docker")
    def test_dry_run(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)

        result = deploy("prod", dry_run=True)
        assert result["status"] == "dry_run"
        assert result["strategy"] == "ssh-transfer"
        assert result["platform"] == "linux/amd64"
        assert len(result["commands"]) == 3
        assert "DOCKER_DEFAULT_PLATFORM=linux/amd64" in result["commands"][0]
        assert "docker save" in result["commands"][1]
        assert "ssh root@docker1.example.com" in result["commands"][1]
        mock_docker.assert_not_called()

    @patch("rundbat.deploy._transfer_images")
    @patch("rundbat.deploy._build_local")
    @patch("rundbat.deploy._run_docker")
    def test_deploy_success(self, mock_docker, mock_build, mock_transfer,
                            tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_docker.return_value = ""
        mock_build.return_value = ""

        result = deploy("prod")
        assert result["status"] == "success"
        assert result["strategy"] == "ssh-transfer"
        assert result["platform"] == "linux/amd64"
        assert len(result["images_transferred"]) > 0

        mock_build.assert_called_once_with(
            "docker/docker-compose.prod.yml", "linux/amd64",
        )
        mock_transfer.assert_called_once()

    @patch("rundbat.deploy._run_docker")
    def test_dry_run_with_ssh_key(self, mock_docker, tmp_path, monkeypatch):
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
                    "host": "ssh://root@docker1.example.com",
                    "platform": "linux/amd64",
                    "build_strategy": "ssh-transfer",
                    "ssh_key": "config/prod/myapp-deploy-key",
                },
            },
        }))
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        compose = {
            "services": {
                "app": {"build": {"context": ".."}, "ports": ["3000:3000"]},
            }
        }
        (docker_dir / "docker-compose.prod.yml").write_text(yaml.dump(compose))

        result = deploy("prod", dry_run=True)
        assert result["strategy"] == "ssh-transfer"
        # Transfer command should include -i key
        transfer_cmd = result["commands"][1]
        assert "-i config/prod/myapp-deploy-key" in transfer_cmd
        assert "StrictHostKeyChecking=no" in transfer_cmd

    def test_missing_host(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "myapp-prod",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "build_strategy": "ssh-transfer",
                },
            },
        }))
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        (docker_dir / "docker-compose.prod.yml").write_text("version: '3'\n")

        with pytest.raises(DeployError, match="requires a 'host' field"):
            deploy("prod")


# ---------------------------------------------------------------------------
# Deploy — github-actions strategy
# ---------------------------------------------------------------------------

class TestDeployGitHubActions:
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
                    "host": "ssh://root@docker1.example.com",
                    "build_strategy": "github-actions",
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
        assert result["strategy"] == "github-actions"
        assert len(result["commands"]) == 2
        assert "pull" in result["commands"][0]
        assert "up -d" in result["commands"][1]
        mock_docker.assert_not_called()

    @patch("rundbat.deploy._run_docker")
    def test_deploy_success(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)
        mock_docker.return_value = ""

        result = deploy("prod")
        assert result["status"] == "success"
        assert result["strategy"] == "github-actions"
        assert result["url"] == "https://app.example.com/"
        assert mock_docker.call_count == 2  # pull + up


# ---------------------------------------------------------------------------
# Deploy — strategy override
# ---------------------------------------------------------------------------

class TestDeployStrategyOverride:
    def _setup_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "myapp-prod",
                    "compose_file": "docker/docker-compose.prod.yml",
                    "host": "ssh://root@host",
                    "build_strategy": "context",
                },
            },
        }))
        docker_dir = tmp_path / "docker"
        docker_dir.mkdir()
        compose = {
            "services": {
                "app": {"build": {"context": ".."}, "ports": ["3000:3000"]},
            }
        }
        (docker_dir / "docker-compose.prod.yml").write_text(yaml.dump(compose))

    @patch("rundbat.deploy._run_docker")
    def test_override_to_ssh_transfer(self, mock_docker, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_config(tmp_path)

        result = deploy("prod", dry_run=True, strategy="ssh-transfer",
                        platform="linux/amd64")
        assert result["strategy"] == "ssh-transfer"
        assert result["platform"] == "linux/amd64"


# ---------------------------------------------------------------------------
# Init deployment
# ---------------------------------------------------------------------------

class TestInitDeployment:
    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy._find_context_for_host")
    def test_creates_new(self, mock_find, mock_exists, mock_create, mock_verify,
                         mock_platform, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = None
        mock_exists.return_value = False
        mock_create.return_value = "docker1.example.com"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/amd64"

        result = init_deployment("prod", "ssh://root@docker1.example.com",
                                 compose_file="docker/prod.yml",
                                 hostname="app.example.com")
        assert result["status"] == "ok"
        assert result["context"] == "docker1.example.com"
        assert result["host"] == "ssh://root@docker1.example.com"
        assert result["platform"] == "linux/amd64"
        assert result["build_strategy"] in VALID_STRATEGIES

        # Verify config was saved with new fields
        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["docker_context"] == "docker1.example.com"
        assert saved["deployments"]["prod"]["compose_file"] == "docker/prod.yml"
        assert saved["deployments"]["prod"]["hostname"] == "app.example.com"
        assert saved["deployments"]["prod"]["host"] == "ssh://root@docker1.example.com"
        assert saved["deployments"]["prod"]["platform"] == "linux/amd64"
        assert saved["deployments"]["prod"]["build_strategy"] in VALID_STRATEGIES

    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy._find_context_for_host")
    def test_reuses_existing_context_for_same_host(self, mock_find, mock_verify,
                                                    mock_platform, tmp_path,
                                                    monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = "existing-ctx"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/arm64"

        result = init_deployment("prod", "ssh://root@host")
        assert result["status"] == "ok"
        assert result["context"] == "existing-ctx"

    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy._find_context_for_host")
    def test_explicit_strategy(self, mock_find, mock_exists, mock_create, mock_verify,
                               mock_platform, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = None
        mock_exists.return_value = False
        mock_create.return_value = "host"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/amd64"

        result = init_deployment("prod", "ssh://root@host",
                                 build_strategy="github-actions")
        assert result["build_strategy"] == "github-actions"

        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["build_strategy"] == "github-actions"

    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy._find_context_for_host")
    def test_with_ssh_key(self, mock_find, mock_exists, mock_create, mock_verify,
                          mock_platform, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = None
        mock_exists.return_value = False
        mock_create.return_value = "host"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/amd64"

        result = init_deployment("prod", "ssh://root@host",
                                 ssh_key="config/prod/myapp-deploy-key")
        assert result["ssh_key"] == "config/prod/myapp-deploy-key"

        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["ssh_key"] == "config/prod/myapp-deploy-key"

    def test_invalid_strategy(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        with pytest.raises(DeployError, match="Unknown build strategy"):
            init_deployment("prod", "ssh://root@host",
                            build_strategy="teleport")

    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy._find_context_for_host")
    def test_auto_selects_ssh_transfer_cross_arch(
        self, mock_find, mock_exists, mock_create, mock_verify,
        mock_platform, tmp_path, monkeypatch,
    ):
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = None
        mock_exists.return_value = False
        mock_create.return_value = "host"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/amd64"

        with patch("rundbat.discovery.local_docker_platform",
                   return_value="linux/arm64"):
            result = init_deployment("prod", "ssh://root@host")

        assert result["build_strategy"] == "ssh-transfer"

    @patch("rundbat.deploy._detect_remote_platform")
    @patch("rundbat.deploy.verify_access")
    @patch("rundbat.deploy.create_context")
    @patch("rundbat.deploy._context_exists")
    @patch("rundbat.deploy._find_context_for_host")
    def test_init_deployment_detects_caddy(
        self, mock_find, mock_exists, mock_create, mock_verify,
        mock_platform, tmp_path, monkeypatch,
    ):
        """init_deployment saves reverse_proxy field from Caddy detection."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "rundbat.yaml").write_text(yaml.dump({
            "app_name": "myapp",
            "notes": [],
        }))

        mock_find.return_value = None
        mock_exists.return_value = False
        mock_create.return_value = "docker1.example.com"
        mock_verify.return_value = {"status": "ok"}
        mock_platform.return_value = "linux/amd64"

        with patch("rundbat.discovery.detect_caddy",
                   return_value={"running": True, "container": "caddy"}):
            with patch("rundbat.discovery.local_docker_platform",
                       return_value="linux/amd64"):
                result = init_deployment("prod", "ssh://root@docker1.example.com")

        assert result["status"] == "ok"

        # Verify reverse_proxy was saved in config
        saved = yaml.safe_load((config_dir / "rundbat.yaml").read_text())
        assert saved["deployments"]["prod"]["reverse_proxy"] == "caddy"


# ---------------------------------------------------------------------------
# _build_docker_run_cmd
# ---------------------------------------------------------------------------

class TestBuildDockerRunCmd:
    def test_basic_command(self):
        cmd = _build_docker_run_cmd("myapp", "ghcr.io/owner/myapp", "8080")
        assert "docker run -d --name myapp" in cmd
        assert "--env-file .env" in cmd
        assert "-p 8080:8080" in cmd
        assert "--restart unless-stopped" in cmd
        assert "ghcr.io/owner/myapp:latest" in cmd

    def test_caddy_labels(self):
        cmd = _build_docker_run_cmd(
            "myapp", "ghcr.io/owner/myapp", "8080",
            hostname="app.example.com",
        )
        assert "caddy=app.example.com" in cmd
        assert "caddy.reverse_proxy" in cmd

    def test_no_caddy_without_hostname(self):
        cmd = _build_docker_run_cmd("myapp", "ghcr.io/owner/myapp", "8080")
        assert "caddy" not in cmd


# ---------------------------------------------------------------------------
# _deploy_run
# ---------------------------------------------------------------------------

class TestDeployRun:
    @patch("rundbat.deploy.subprocess.run")
    @patch("rundbat.deploy._prepare_env")
    def test_dry_run(self, mock_env, mock_run):
        deploy_cfg = {
            "docker_context": "default",
            "docker_run_cmd": "docker run -d --name myapp ghcr.io/owner/myapp:latest",
            "image": "ghcr.io/owner/myapp",
        }
        result = _deploy_run("prod", deploy_cfg, "myapp", dry_run=True)
        assert result["status"] == "dry_run"
        assert result["strategy"] == "run"
        assert len(result["commands"]) == 4
        mock_run.assert_not_called()
        mock_env.assert_not_called()

    def test_missing_docker_run_cmd(self):
        deploy_cfg = {"docker_context": "default"}
        with pytest.raises(DeployError, match="no docker_run_cmd"):
            _deploy_run("prod", deploy_cfg, "myapp")


# ---------------------------------------------------------------------------
# _prepare_env
# ---------------------------------------------------------------------------

class TestPrepareEnv:
    def test_noop_without_dotconfig(self):
        """No-op when env_source is not dotconfig."""
        deploy_cfg = {"env_source": "file", "host": "ssh://root@host"}
        _prepare_env("prod", deploy_cfg, "myapp")  # should not raise

    @patch("rundbat.deploy.subprocess.run")
    @patch("rundbat.config.load_env")
    def test_scp_transfer(self, mock_load_env, mock_run):
        mock_load_env.return_value = "KEY=value\n"
        mock_run.return_value = type("R", (), {"returncode": 0, "stderr": ""})()

        deploy_cfg = {
            "env_source": "dotconfig",
            "host": "ssh://root@docker1.example.com",
        }
        _prepare_env("prod", deploy_cfg, "myapp")

        mock_load_env.assert_called_once_with("prod")
        mock_run.assert_called_once()
        scp_args = mock_run.call_args[0][0]
        assert scp_args[0] == "scp"
        assert "root@docker1.example.com:/opt/myapp/.env" in scp_args[-1]


# ---------------------------------------------------------------------------
# _get_github_repo
# ---------------------------------------------------------------------------

class TestGetGitHubRepo:
    @patch("rundbat.deploy.subprocess.run")
    def test_ssh_url(self, mock_run):
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "git@github.com:owner/repo.git\n",
        })()
        assert _get_github_repo() == "owner/repo"

    @patch("rundbat.deploy.subprocess.run")
    def test_https_url(self, mock_run):
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "https://github.com/owner/repo.git\n",
        })()
        assert _get_github_repo() == "owner/repo"

    @patch("rundbat.deploy.subprocess.run")
    def test_https_no_git_suffix(self, mock_run):
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "https://github.com/owner/repo\n",
        })()
        assert _get_github_repo() == "owner/repo"

    @patch("rundbat.deploy.subprocess.run")
    def test_non_github_raises(self, mock_run):
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "https://gitlab.com/owner/repo.git\n",
        })()
        with pytest.raises(DeployError, match="not a GitHub"):
            _get_github_repo()

    @patch("rundbat.deploy.subprocess.run")
    def test_no_remote(self, mock_run):
        mock_run.return_value = type("R", (), {
            "returncode": 1,
            "stdout": "",
        })()
        with pytest.raises(DeployError, match="No git remote"):
            _get_github_repo()

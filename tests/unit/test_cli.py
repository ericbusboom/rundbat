"""Tests for the CLI entry point."""

import subprocess
import sys
import types
from unittest.mock import patch, MagicMock


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Helper: run rundbat CLI as subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "rundbat.cli"] + args,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Basic CLI tests
# ---------------------------------------------------------------------------

def test_version():
    """rundbat --version prints version."""
    result = _run(["--version"])
    assert result.returncode == 0
    assert "rundbat" in result.stdout


def test_no_args_shows_help():
    """rundbat with no args shows help and exits 0."""
    result = _run([])
    assert result.returncode == 0
    assert "init" in result.stdout
    assert "deploy" in result.stdout
    assert "init-docker" in result.stdout


def test_expected_commands():
    """rundbat should have the expected subcommands."""
    result = _run(["--help"])
    assert result.returncode == 0
    # These should be present
    assert "init" in result.stdout
    assert "generate" in result.stdout
    assert "build" in result.stdout
    assert "up" in result.stdout
    assert "down" in result.stdout
    assert "logs" in result.stdout
    assert "deploy" in result.stdout
    assert "deploy-init" in result.stdout
    assert "init-docker" in result.stdout
    assert "probe" in result.stdout
    # These should be gone (removed in sprint 005)
    assert "discover" not in result.stdout
    assert "create-env" not in result.stdout
    assert "health" not in result.stdout
    assert "validate" not in result.stdout
    assert "set-secret" not in result.stdout
    assert "check-drift" not in result.stdout
    assert "add-service" not in result.stdout
    assert "uninstall" not in result.stdout


# ---------------------------------------------------------------------------
# Subcommand --help tests
# ---------------------------------------------------------------------------

class TestSubcommandHelp:
    """Every subcommand should respond to --help with exit code 0."""

    def test_init_help(self):
        result = _run(["init", "--help"])
        assert result.returncode == 0
        assert "--app-name" in result.stdout
        assert "--force" in result.stdout

    def test_generate_help(self):
        result = _run(["generate", "--help"])
        assert result.returncode == 0
        assert "--deployment" in result.stdout
        assert "--json" in result.stdout

    def test_init_docker_help(self):
        result = _run(["init-docker", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

    def test_build_help(self):
        result = _run(["build", "--help"])
        assert result.returncode == 0
        assert "name" in result.stdout

    def test_up_help(self):
        result = _run(["up", "--help"])
        assert result.returncode == 0
        assert "--workflow" in result.stdout

    def test_down_help(self):
        result = _run(["down", "--help"])
        assert result.returncode == 0

    def test_logs_help(self):
        result = _run(["logs", "--help"])
        assert result.returncode == 0

    def test_deploy_help(self):
        result = _run(["deploy", "--help"])
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--no-build" in result.stdout
        assert "--json" in result.stdout

    def test_deploy_init_help(self):
        result = _run(["deploy-init", "--help"])
        assert result.returncode == 0
        assert "--host" in result.stdout
        assert "--compose-file" in result.stdout
        assert "--hostname" in result.stdout
        assert "--deploy-mode" in result.stdout
        assert "--image" in result.stdout


# ---------------------------------------------------------------------------
# cmd_probe unit tests
# ---------------------------------------------------------------------------

def _make_probe_args(name="prod", as_json=False):
    """Build a minimal args namespace for cmd_probe."""
    args = types.SimpleNamespace()
    args.name = name
    args.json = as_json
    return args


def test_cmd_probe_saves_caddy(monkeypatch, capsys):
    """probe command saves reverse_proxy: caddy when Caddy detected."""
    saved_data = {}

    fake_cfg = {
        "deployments": {
            "prod": {"docker_context": "myapp-prod"},
        },
    }

    def fake_load_config():
        return dict(fake_cfg)

    def fake_save_config(data):
        saved_data.update(data)

    def fake_detect_caddy(ctx):
        return {"running": True, "container": "caddy"}

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr("rundbat.config.save_config", fake_save_config)
    monkeypatch.setattr("rundbat.discovery.detect_caddy", fake_detect_caddy)

    from rundbat.cli import cmd_probe
    cmd_probe(_make_probe_args(name="prod"))

    assert saved_data["deployments"]["prod"]["reverse_proxy"] == "caddy"


def test_cmd_probe_saves_none_when_no_caddy(monkeypatch, capsys):
    """probe command saves reverse_proxy: none when Caddy not detected."""
    saved_data = {}

    def fake_load_config():
        return {
            "deployments": {
                "prod": {"docker_context": "myapp-prod"},
            },
        }

    def fake_save_config(data):
        saved_data.update(data)

    def fake_detect_caddy(ctx):
        return {"running": False, "container": None}

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr("rundbat.config.save_config", fake_save_config)
    monkeypatch.setattr("rundbat.discovery.detect_caddy", fake_detect_caddy)

    from rundbat.cli import cmd_probe
    cmd_probe(_make_probe_args(name="prod"))

    assert saved_data["deployments"]["prod"]["reverse_proxy"] == "none"


def test_cmd_probe_unknown_deployment(monkeypatch, capsys):
    """probe command exits with error when deployment name not in config."""
    def fake_load_config():
        return {"deployments": {"staging": {"docker_context": "myapp-staging"}}}

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)

    from rundbat.cli import cmd_probe
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        cmd_probe(_make_probe_args(name="prod"))
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "prod" in captured.err


# ---------------------------------------------------------------------------
# cmd_init_docker caddy warning test
# ---------------------------------------------------------------------------

def _make_init_docker_args(hostname=None, as_json=False):
    """Build a minimal args namespace for cmd_init_docker."""
    args = types.SimpleNamespace()
    args.hostname = hostname
    args.json = as_json
    return args


def test_init_docker_caddy_warning(monkeypatch, capsys, tmp_path):
    """init-docker warns when deployment has reverse_proxy: caddy but no hostname."""
    def fake_load_config():
        return {
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "myapp-prod",
                    "reverse_proxy": "caddy",
                    # no hostname
                },
            },
        }

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)

    # Patch generators.init_docker to avoid actual file I/O
    def fake_init_docker(project_dir, app_name, framework=None, services=None,
                         hostname=None, swarm=False, deployments=None):
        return {"status": "created", "docker_dir": str(tmp_path / "docker"),
                "framework": {"language": "unknown"}, "files": []}

    monkeypatch.setattr("rundbat.generators.init_docker", fake_init_docker)
    monkeypatch.chdir(tmp_path)

    from rundbat.cli import cmd_init_docker
    cmd_init_docker(_make_init_docker_args())

    captured = capsys.readouterr()
    assert "Caddy" in captured.out or "caddy" in captured.out.lower()

"""Tests for the Discovery Service."""

from unittest.mock import patch, MagicMock
import subprocess

from rundbat.discovery import (
    detect_os,
    detect_docker,
    detect_dotconfig,
    detect_node,
    discover_system,
    local_docker_platform,
    verify_docker,
)


def test_detect_os_returns_system_info():
    """OS detection always works and returns expected fields."""
    result = detect_os()
    assert "system" in result
    assert "machine" in result
    assert "release" in result
    assert "platform" in result
    assert result["system"]  # Should be non-empty


def test_detect_docker_not_installed():
    """Gracefully handles Docker not being installed."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Command not found: docker",
            "returncode": -1,
        }
        result = detect_docker()
        assert result["installed"] is False
        assert result["running"] is False


def test_detect_docker_installed_not_running():
    """Detects Docker installed but not running."""
    def side_effect(args, **kwargs):
        if args == ["docker", "info"]:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Cannot connect to the Docker daemon",
                "returncode": 1,
            }
        if args == ["docker", "--version"]:
            return {
                "success": True,
                "stdout": "Docker version 24.0.6",
                "stderr": "",
                "returncode": 0,
            }
        return {"success": False, "stdout": "", "stderr": "", "returncode": -1}

    with patch("rundbat.discovery._run_command", side_effect=side_effect):
        result = detect_docker()
        assert result["installed"] is True
        assert result["running"] is False
        assert "Docker version" in result["version"]


def test_detect_docker_running():
    """Detects Docker installed and running."""
    def side_effect(args, **kwargs):
        if args == ["docker", "info"]:
            return {
                "success": True,
                "stdout": "Server Version: 24.0.6\nOperating System: Docker Desktop",
                "stderr": "",
                "returncode": 0,
            }
        if args == ["docker", "--version"]:
            return {
                "success": True,
                "stdout": "Docker version 24.0.6",
                "stderr": "",
                "returncode": 0,
            }
        return {"success": False, "stdout": "", "stderr": "", "returncode": -1}

    with patch("rundbat.discovery._run_command", side_effect=side_effect):
        result = detect_docker()
        assert result["installed"] is True
        assert result["running"] is True
        assert result["backend"] == "Docker Desktop"


def test_detect_node_not_installed():
    """Gracefully handles Node.js not being installed."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Command not found: node",
            "returncode": -1,
        }
        result = detect_node()
        assert result["installed"] is False
        assert result["version"] is None


def test_detect_node_installed():
    """Detects Node.js when installed."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": True,
            "stdout": "v20.10.0",
            "stderr": "",
            "returncode": 0,
        }
        result = detect_node()
        assert result["installed"] is True
        assert result["version"] == "v20.10.0"


def test_detect_dotconfig_not_installed():
    """Gracefully handles dotconfig not being installed."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Command not found: dotconfig",
            "returncode": -1,
        }
        result = detect_dotconfig()
        assert result["installed"] is False
        assert result["initialized"] is False


def test_discover_system_returns_all_sections():
    """Full discovery returns all expected sections."""
    with patch("rundbat.discovery.detect_docker") as mock_docker, \
         patch("rundbat.discovery.detect_dotconfig") as mock_dotconfig, \
         patch("rundbat.discovery.detect_node") as mock_node, \
         patch("rundbat.discovery.detect_existing_config") as mock_config:
        mock_docker.return_value = {"installed": False}
        mock_dotconfig.return_value = {"installed": False}
        mock_node.return_value = {"installed": False}
        mock_config.return_value = {"has_config": False, "environments": []}

        result = discover_system()
        assert "os" in result
        assert "docker" in result
        assert "dotconfig" in result
        assert "node" in result
        assert "existing_config" in result


def test_verify_docker_ok():
    """verify_docker returns ok when Docker is running."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": True,
            "stdout": "Server Version: 24.0.6",
            "stderr": "",
            "returncode": 0,
        }
        result = verify_docker()
        assert result["ok"] is True
        assert result["error"] is None


def test_verify_docker_not_ok():
    """verify_docker returns error when Docker is not available."""
    with patch("rundbat.discovery._run_command") as mock_run:
        mock_run.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Cannot connect to the Docker daemon",
            "returncode": 1,
        }
        result = verify_docker()
        assert result["ok"] is False
        assert result["error"] is not None


def test_local_docker_platform_arm64():
    """Maps arm64 to linux/arm64."""
    with patch("rundbat.discovery.platform") as mock_plat:
        mock_plat.machine.return_value = "arm64"
        assert local_docker_platform() == "linux/arm64"


def test_local_docker_platform_x86_64():
    """Maps x86_64 to linux/amd64."""
    with patch("rundbat.discovery.platform") as mock_plat:
        mock_plat.machine.return_value = "x86_64"
        assert local_docker_platform() == "linux/amd64"


def test_local_docker_platform_unknown():
    """Falls back to linux/<machine> for unknown architectures."""
    with patch("rundbat.discovery.platform") as mock_plat:
        mock_plat.machine.return_value = "riscv64"
        assert local_docker_platform() == "linux/riscv64"


# ---------------------------------------------------------------------------
# detect_caddy
# ---------------------------------------------------------------------------

def test_detect_caddy_running(monkeypatch):
    """detect_caddy returns running=True when docker ps output is non-empty."""
    from rundbat.discovery import detect_caddy
    def mock_run(cmd, timeout=10):
        return {"success": True, "stdout": "caddy", "stderr": "", "returncode": 0}
    monkeypatch.setattr("rundbat.discovery._run_command", mock_run)
    result = detect_caddy("test-context")
    assert result["running"] is True
    assert result["container"] == "caddy"


def test_detect_caddy_not_running(monkeypatch):
    """detect_caddy returns running=False when docker ps output is empty."""
    from rundbat.discovery import detect_caddy
    def mock_run(cmd, timeout=10):
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}
    monkeypatch.setattr("rundbat.discovery._run_command", mock_run)
    result = detect_caddy("test-context")
    assert result["running"] is False
    assert result["container"] is None


def test_detect_caddy_passes_context(monkeypatch):
    """detect_caddy includes --context in the docker command."""
    from rundbat.discovery import detect_caddy
    captured_cmd = []
    def mock_run(cmd, timeout=10):
        captured_cmd.extend(cmd)
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}
    monkeypatch.setattr("rundbat.discovery._run_command", mock_run)
    detect_caddy("my-remote")
    assert "--context" in captured_cmd
    assert "my-remote" in captured_cmd

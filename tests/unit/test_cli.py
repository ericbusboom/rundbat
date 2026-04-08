"""Tests for the CLI entry point."""

import json
import subprocess
import sys


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
    assert "discover" in result.stdout
    assert "create-env" in result.stdout
    assert "install" in result.stdout


def test_env_no_subcommand_shows_help():
    """rundbat env with no subcommand shows env help."""
    result = _run(["env"])
    assert result.returncode == 0
    assert "list" in result.stdout
    assert "connstr" in result.stdout



# ---------------------------------------------------------------------------
# Subcommand --help tests (verify all subcommands are registered)
# ---------------------------------------------------------------------------

class TestSubcommandHelp:
    """Every subcommand should respond to --help with exit code 0."""

    def test_discover_help(self):
        result = _run(["discover", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

    def test_create_env_help(self):
        result = _run(["create-env", "--help"])
        assert result.returncode == 0
        assert "env" in result.stdout

    def test_get_config_help(self):
        result = _run(["get-config", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

    def test_start_help(self):
        result = _run(["start", "--help"])
        assert result.returncode == 0

    def test_stop_help(self):
        result = _run(["stop", "--help"])
        assert result.returncode == 0

    def test_health_help(self):
        result = _run(["health", "--help"])
        assert result.returncode == 0

    def test_validate_help(self):
        result = _run(["validate", "--help"])
        assert result.returncode == 0

    def test_set_secret_help(self):
        result = _run(["set-secret", "--help"])
        assert result.returncode == 0
        assert "KEY=VALUE" in result.stdout

    def test_check_drift_help(self):
        result = _run(["check-drift", "--help"])
        assert result.returncode == 0

    def test_install_help(self):
        result = _run(["install", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

    def test_uninstall_help(self):
        result = _run(["uninstall", "--help"])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Subcommand --json output tests
# ---------------------------------------------------------------------------

class TestJsonOutput:
    """Subcommands with --json should produce valid JSON."""

    def test_discover_json(self):
        result = _run(["discover", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "os" in data
        assert "docker" in data

    def test_check_drift_json(self):
        """check-drift works with the current project's rundbat.yaml."""
        result = _run(["check-drift", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "drift" in data

    def test_install_json(self, tmp_path, monkeypatch):
        """rundbat install --json produces valid JSON."""
        monkeypatch.chdir(tmp_path)
        result = _run(["install", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "installed" in data

    def test_uninstall_no_manifest_json(self, tmp_path, monkeypatch):
        """rundbat uninstall --json with no manifest returns warning."""
        monkeypatch.chdir(tmp_path)
        result = _run(["uninstall", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "warning" in data


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """CLI commands should return exit code 1 on errors."""

    def test_create_env_no_args(self):
        """create-env without env name should error."""
        result = _run(["create-env"])
        assert result.returncode == 2  # usage error

    def test_start_no_args(self):
        result = _run(["start"])
        assert result.returncode == 2

    def test_set_secret_bad_format(self, tmp_path, monkeypatch):
        """set-secret with no = in the value should error."""
        monkeypatch.chdir(tmp_path)
        result = _run(["set-secret", "dev", "NOEQUALS"])
        assert result.returncode == 1

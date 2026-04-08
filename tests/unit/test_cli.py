"""Tests for the CLI entry point."""

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
    assert "init" in result.stdout
    assert "deploy" in result.stdout
    assert "init-docker" in result.stdout


def test_only_four_commands():
    """rundbat should only have 4 subcommands."""
    result = _run(["--help"])
    assert result.returncode == 0
    # These should be present
    assert "init" in result.stdout
    assert "init-docker" in result.stdout
    assert "deploy" in result.stdout
    assert "deploy-init" in result.stdout
    # These should be gone
    assert "discover" not in result.stdout
    assert "create-env" not in result.stdout
    assert "start" not in result.stdout
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

    def test_init_docker_help(self):
        result = _run(["init-docker", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

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

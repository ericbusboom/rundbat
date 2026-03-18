"""Tests for the CLI entry point."""

import subprocess
import sys


def test_version():
    """rundbat --version prints version."""
    result = subprocess.run(
        [sys.executable, "-m", "rundbat.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "rundbat" in result.stdout


def test_no_args_shows_help():
    """rundbat with no args shows help and exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "rundbat.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "mcp" in result.stdout
    assert "env" in result.stdout


def test_env_no_subcommand_shows_help():
    """rundbat env with no subcommand shows env help."""
    result = subprocess.run(
        [sys.executable, "-m", "rundbat.cli", "env"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "list" in result.stdout
    assert "connstr" in result.stdout


def test_mcp_help_shows_tools():
    """rundbat mcp --help shows the detailed agent-oriented help."""
    result = subprocess.run(
        [sys.executable, "-m", "rundbat.cli", "mcp", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "discover_system" in result.stdout
    assert "get_environment_config" in result.stdout
    assert "MCP TOOLS" in result.stdout

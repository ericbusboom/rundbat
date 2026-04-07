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


def test_mcp_shows_deprecation():
    """rundbat mcp prints deprecation message and exits 1."""
    result = subprocess.run(
        [sys.executable, "-m", "rundbat.cli", "mcp"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "removed" in result.stderr
    assert "rundbat install" in result.stderr

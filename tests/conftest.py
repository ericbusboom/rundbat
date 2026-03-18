"""Shared pytest configuration and fixtures."""

import subprocess

import pytest


def _command_available(cmd: str) -> bool:
    """Check if a command is available on the system."""
    try:
        subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _docker_context_available(context: str) -> bool:
    """Check if a Docker context is reachable."""
    try:
        result = subprocess.run(
            ["docker", "--context", context, "info"],
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pytest_runtest_setup(item):
    """Skip tests that require unavailable tools."""
    for marker in item.iter_markers("requires_docker"):
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                pytest.skip("Docker is not running")
        except FileNotFoundError:
            pytest.skip("Docker is not installed")

    for marker in item.iter_markers("requires_dotconfig"):
        if not _command_available("dotconfig"):
            pytest.skip("dotconfig is not installed")

    for marker in item.iter_markers("requires_remote_docker"):
        if not _docker_context_available("student-docker1"):
            pytest.skip("Remote Docker context 'student-docker1' is not reachable")

    for marker in item.iter_markers("requires_managed_db"):
        if not _command_available("dotconfig"):
            pytest.skip("dotconfig is not installed (needed to load prod credentials)")

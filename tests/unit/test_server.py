"""Tests for the MCP server instance."""

from rundbat.server import server


def test_server_exists():
    """Server instance is created."""
    assert server is not None


def test_server_name():
    """Server has the expected name."""
    assert server.name == "rundbat"

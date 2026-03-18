"""rundbat — Deployment Expert MCP Server."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("rundbat")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

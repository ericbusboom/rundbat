"""rundbat MCP server — entry point and tool registration."""

from mcp.server.fastmcp import FastMCP

from rundbat import discovery

server = FastMCP("rundbat")


@server.tool()
def discover_system() -> dict:
    """Detect host OS, Docker status, dotconfig status, Node.js version, and existing rundbat configuration."""
    return discovery.discover_system()


@server.tool()
def verify_docker() -> dict:
    """Verify that Docker is installed and running. Returns ok: true/false."""
    return discovery.verify_docker()


def main():
    """Run the rundbat MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

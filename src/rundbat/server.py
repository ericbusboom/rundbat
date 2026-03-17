"""rundbat MCP server — entry point and tool registration."""

from mcp.server.fastmcp import FastMCP

server = FastMCP("rundbat")


def main():
    """Run the rundbat MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

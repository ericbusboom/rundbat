"""rundbat MCP server — entry point and tool registration."""

from mcp.server.fastmcp import FastMCP

from rundbat import config, database, discovery

server = FastMCP("rundbat")


# --- Discovery tools ---

@server.tool()
def discover_system() -> dict:
    """Detect host OS, Docker status, dotconfig status, Node.js version, and existing rundbat configuration."""
    return discovery.discover_system()


@server.tool()
def verify_docker() -> dict:
    """Verify that Docker is installed and running. Returns ok: true/false."""
    return discovery.verify_docker()


# --- Config tools ---

@server.tool()
def init_project(app_name: str, app_name_source: str) -> dict:
    """Initialize rundbat config for a project. Creates rundbat.yaml via dotconfig with app name and source."""
    try:
        return config.init_project(app_name, app_name_source)
    except config.ConfigError as e:
        return e.to_dict()


@server.tool()
def set_secret(env: str, key: str, value: str) -> dict:
    """Write a secret to a deployment's .env file via dotconfig load/edit/save cycle."""
    try:
        config.save_secret(env, key, value)
        return {"status": "ok", "env": env, "key": key}
    except config.ConfigError as e:
        return e.to_dict()


@server.tool()
def check_config_drift(env: str = "dev") -> dict:
    """Check if the app name at its source file differs from the stored name in rundbat config."""
    try:
        return config.check_config_drift(env)
    except config.ConfigError as e:
        return e.to_dict()


# --- Database tools ---

@server.tool()
def start_database(env: str) -> dict:
    """Start the Postgres container for a local environment. Creates it if missing."""
    try:
        name = database.container_name("unknown", env)  # Will be replaced by env service
        status = database.get_container_status(name)
        if status == "running":
            return {"status": "already_running", "container": name}
        if status == "exited":
            database.start_container(name)
            return {"status": "started", "container": name}
        return {"error": f"Container {name} not found. Use create_environment first."}
    except database.DatabaseError as e:
        return e.to_dict()


@server.tool()
def stop_database(env: str) -> dict:
    """Stop the Postgres container for a local environment."""
    try:
        name = database.container_name("unknown", env)  # Will be replaced by env service
        database.stop_container(name)
        return {"status": "stopped", "container": name}
    except database.DatabaseError as e:
        return e.to_dict()


@server.tool()
def health_check(env: str) -> dict:
    """Check if the database is reachable for a local environment."""
    try:
        name = database.container_name("unknown", env)  # Will be replaced by env service
        return database.health_check(name)
    except database.DatabaseError as e:
        return e.to_dict()


def main():
    """Run the rundbat MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

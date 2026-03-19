"""rundbat MCP server — entry point and tool registration."""

from mcp.server.fastmcp import FastMCP

from rundbat import config, database, discovery, environment, installer
from rundbat.config import ConfigError
from rundbat.database import DatabaseError

server = FastMCP("rundbat")


def _get_container_name(env: str) -> str:
    """Look up the container name for an environment from config."""
    # Check per-env public.env first
    env_vars = config.load_public_env(env)
    container = env_vars.get("DB_CONTAINER")
    if container:
        return container
    # Fallback: derive from project config templates
    try:
        project_config = config.load_config()
        app_name = project_config.get("app_name", "unknown")
        template = project_config.get("container_template")
    except ConfigError:
        app_name = "unknown"
        template = None
    return database.container_name(app_name, env, template)


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
    """Initialize rundbat config for a project. Creates rundbat.yaml via dotconfig, installs MCP config, rules, and hooks."""
    try:
        result = config.init_project(app_name, app_name_source)
    except ConfigError as e:
        return e.to_dict()

    # Install integration files into the project
    from pathlib import Path
    project_dir = Path.cwd()
    try:
        install_result = installer.install_all(project_dir)
        result["installer"] = install_result
    except Exception as e:
        result["installer_warning"] = f"Could not install integration files: {e}"

    return result


@server.tool()
def set_secret(env: str, key: str, value: str) -> dict:
    """Write a secret to a deployment's .env file via dotconfig load/edit/save cycle."""
    try:
        config.save_secret(env, key, value)
        return {"status": "ok", "env": env, "key": key}
    except ConfigError as e:
        return e.to_dict()


@server.tool()
def check_config_drift(env: str = "dev") -> dict:
    """Check if the app name at its source file differs from the stored name in rundbat config."""
    try:
        return config.check_config_drift(env)
    except ConfigError as e:
        return e.to_dict()


# --- Database tools ---

@server.tool()
def start_database(env: str) -> dict:
    """Start the Postgres container for a local environment."""
    try:
        name = _get_container_name(env)
        status = database.get_container_status(name)
        if status == "running":
            return {"status": "already_running", "container": name}
        if status == "exited":
            database.start_container(name)
            return {"status": "started", "container": name}
        return {"error": f"Container {name} not found. Use create_environment first."}
    except DatabaseError as e:
        return e.to_dict()


@server.tool()
def stop_database(env: str) -> dict:
    """Stop the Postgres container for a local environment."""
    try:
        name = _get_container_name(env)
        database.stop_container(name)
        return {"status": "stopped", "container": name}
    except DatabaseError as e:
        return e.to_dict()


@server.tool()
def health_check(env: str) -> dict:
    """Check if the database is reachable for a local environment."""
    try:
        name = _get_container_name(env)
        return database.health_check(name)
    except DatabaseError as e:
        return e.to_dict()


# --- Environment tools ---

@server.tool()
def create_environment(name: str, env_type: str = "local-docker") -> dict:
    """Create a new environment. Generates credentials, allocates port, starts Postgres container, saves config."""
    return environment.create_environment(name, env_type)


@server.tool()
def get_environment_config(env: str) -> dict:
    """Load environment config, ensure database is running, check for drift. Single call, complete answer."""
    return environment.get_environment_config(env)


@server.tool()
def validate_environment(env: str) -> dict:
    """Full validation of an environment: config completeness, secret presence, container status, connectivity."""
    return environment.validate_environment(env)


def main():
    """Run the rundbat MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

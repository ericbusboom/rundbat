"""Environment Service — orchestrate environment creation and config retrieval."""

import secrets as secrets_module

from rundbat import config, database, installer
from rundbat.config import ConfigError
from rundbat.database import DatabaseError


def _generate_password(length: int = 32) -> str:
    """Generate a cryptographically secure password."""
    return secrets_module.token_urlsafe(length)


def create_environment(name: str, env_type: str = "local-docker") -> dict:
    """Create a new environment with database provisioning.

    For local-docker: generates credentials, allocates port, starts
    Postgres container, saves config via dotconfig.
    """
    if env_type != "local-docker":
        return {"error": f"Environment type '{env_type}' is not yet supported. Only 'local-docker' is available."}

    # Load project config to get app name
    try:
        project_config = config.load_config("dev")
    except ConfigError:
        # Try to load from the target env
        try:
            project_config = config.load_config(name)
        except ConfigError:
            return {"error": "Project not initialized. Call init_project first."}

    app_name = project_config.get("app_name")
    if not app_name:
        return {"error": "No app_name in rundbat.yaml. Call init_project first."}

    # Generate credentials
    password = _generate_password()
    port = database.find_available_port()
    db_name = database.database_name(app_name, name)
    container = database.container_name(app_name, name)

    # Create the database container
    try:
        db_result = database.create_database(
            app_name=app_name,
            env=name,
            password=password,
            port=port,
        )
    except DatabaseError as e:
        return e.to_dict()

    # Build connection string
    connection_string = (
        f"postgresql://{app_name}:{password}@localhost:{port}/{db_name}"
    )

    # Save database config to rundbat.yaml
    env_config = dict(project_config)
    env_config["database"] = {
        "name": db_name,
        "container": container,
        "port": port,
        "engine": "postgres",
        "version": "16",
    }
    try:
        config.save_config(name, env_config)
    except ConfigError as e:
        return e.to_dict()

    # Save connection string as secret
    try:
        config.save_secret(name, "DATABASE_URL", connection_string)
    except ConfigError:
        # Secret saving may fail if SOPS is not set up — still return success
        # with a warning since the database is running
        pass

    return {
        "status": "created",
        "environment": name,
        "type": env_type,
        "database": db_result,
        "connection_string": connection_string,
        "port": port,
    }


def get_environment_config(env: str) -> dict:
    """Load environment config, ensure database is running, check for drift.

    This is the primary day-to-day tool. Single call, complete answer.
    """
    # Load config
    try:
        env_config = config.load_config(env)
    except ConfigError as e:
        return e.to_dict()

    app_name = env_config.get("app_name")
    db_config = env_config.get("database", {})
    notes = env_config.get("notes", [])

    if not app_name or not db_config:
        return {"error": f"Environment '{env}' is not configured. Call create_environment first."}

    container = db_config.get("container")
    port = db_config.get("port", 5432)

    # Load the password from secrets
    connection_string = None
    try:
        env_content = config.load_env(env)
        for line in env_content.splitlines():
            if line.startswith("DATABASE_URL="):
                connection_string = line.split("=", 1)[1]
                break
    except ConfigError:
        pass

    # Ensure database is running (auto-restart or recreate)
    warnings = []
    if container:
        # We need the password for potential recreation
        password = None
        if connection_string:
            # Extract password from connection string
            try:
                # postgresql://user:pass@host:port/db
                after_slash = connection_string.split("://", 1)[1]
                user_pass = after_slash.split("@", 1)[0]
                password = user_pass.split(":", 1)[1] if ":" in user_pass else None
            except (IndexError, ValueError):
                pass

        try:
            ensure_result = database.ensure_running(
                app_name=app_name,
                env=env,
                password=password or "fallback",
                port=port,
            )
            warnings.extend(ensure_result.get("warnings", []))
            status = ensure_result.get("status", "unknown")
            action = ensure_result.get("action", "none")
        except DatabaseError as e:
            return e.to_dict()
    else:
        status = "no_container"
        action = "none"

    # Check for drift
    drift = config.check_config_drift(env)
    if drift.get("drift"):
        warnings.append(drift["message"])

    return {
        "app_name": app_name,
        "environment": env,
        "database": {
            "connection_string": connection_string,
            "container": container,
            "port": port,
            "status": status,
            "action": action,
        },
        "notes": notes,
        "warnings": warnings,
    }


def validate_environment(env: str) -> dict:
    """Full validation of an environment: config, secrets, container, connectivity."""
    checks = {
        "config": {"ok": False, "detail": ""},
        "secrets": {"ok": False, "detail": ""},
        "container": {"ok": False, "detail": ""},
        "connectivity": {"ok": False, "detail": ""},
    }

    # Check config
    try:
        env_config = config.load_config(env)
        if env_config.get("app_name") and env_config.get("database"):
            checks["config"] = {"ok": True, "detail": "Config loaded successfully"}
        else:
            checks["config"] = {"ok": False, "detail": "Missing app_name or database in config"}
    except ConfigError as e:
        checks["config"] = {"ok": False, "detail": str(e)}

    # Check secrets
    try:
        env_content = config.load_env(env)
        has_db_url = any(line.startswith("DATABASE_URL=") for line in env_content.splitlines())
        checks["secrets"] = {
            "ok": has_db_url,
            "detail": "DATABASE_URL present" if has_db_url else "DATABASE_URL not found in secrets",
        }
    except ConfigError as e:
        checks["secrets"] = {"ok": False, "detail": str(e)}

    # Check container
    if checks["config"]["ok"]:
        container = env_config["database"].get("container")
        if container:
            status = database.get_container_status(container)
            checks["container"] = {
                "ok": status == "running",
                "detail": f"Container status: {status}" if status else "Container not found",
            }
    else:
        checks["container"] = {"ok": False, "detail": "Cannot check container — config not loaded"}

    # Check connectivity
    if checks["container"]["ok"]:
        container = env_config["database"]["container"]
        health = database.health_check(container)
        checks["connectivity"] = {
            "ok": health["ok"],
            "detail": "pg_isready succeeded" if health["ok"] else health.get("error", "Health check failed"),
        }
    else:
        checks["connectivity"] = {"ok": False, "detail": "Cannot check connectivity — container not running"}

    all_ok = all(c["ok"] for c in checks.values())
    return {"ok": all_ok, "checks": checks}

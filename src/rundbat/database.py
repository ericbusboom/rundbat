"""Database Service — manage Postgres Docker containers for local environments."""

import socket
import subprocess
import time


class DatabaseError(Exception):
    """Error from a Docker database operation."""

    def __init__(self, message: str, command: list[str] | None = None,
                 exit_code: int | None = None, stderr: str | None = None):
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "command": " ".join(self.command) if self.command else None,
            "exit_code": self.exit_code,
            "stderr": self.stderr,
        }


def _run_docker(args: list[str], timeout: int = 60) -> str:
    """Run a docker command and return stdout. Raises DatabaseError on failure."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise DatabaseError(
            "Docker is not installed.",
            command=cmd,
            exit_code=-1,
            stderr="Command not found: docker",
        )
    except subprocess.TimeoutExpired:
        raise DatabaseError(
            f"Docker command timed out after {timeout}s",
            command=cmd,
            exit_code=-1,
            stderr="Timeout",
        )

    if result.returncode != 0:
        raise DatabaseError(
            f"Docker command failed: {result.stderr.strip()}",
            command=cmd,
            exit_code=result.returncode,
            stderr=result.stderr.strip(),
        )
    return result.stdout.strip()


DEFAULT_CONTAINER_TEMPLATE = "{app}-{env}-pg"
DEFAULT_DATABASE_TEMPLATE = "{app}_{env}"


def container_name(app_name: str, env: str, template: str | None = None) -> str:
    """Generate the container name for a database.

    Template placeholders: {app}, {env}
    Default: "{app}-{env}-pg"
    """
    tmpl = template or DEFAULT_CONTAINER_TEMPLATE
    return tmpl.format(app=app_name, env=env)


def database_name(app_name: str, env: str, template: str | None = None) -> str:
    """Generate the database name.

    Template placeholders: {app}, {env}
    Default: "{app}_{env}"
    """
    tmpl = template or DEFAULT_DATABASE_TEMPLATE
    return tmpl.format(app=app_name, env=env)


def _is_port_available(port: int) -> bool:
    """Check if a TCP port is available on localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def find_available_port(start: int = 5432, max_attempts: int = 100) -> int:
    """Find an available port starting from the given port."""
    for offset in range(max_attempts):
        port = start + offset
        if _is_port_available(port):
            return port
    raise DatabaseError(
        f"No available port found in range {start}-{start + max_attempts - 1}"
    )


def get_container_status(name: str) -> str | None:
    """Get the status of a container. Returns 'running', 'exited', or None if not found."""
    try:
        output = _run_docker([
            "inspect", "--format", "{{.State.Status}}", name,
        ])
        return output.strip()
    except DatabaseError:
        return None


def create_database(
    app_name: str,
    env: str,
    password: str,
    port: int,
    pg_version: str = "16",
    container_template: str | None = None,
    database_template: str | None = None,
) -> dict:
    """Create and start a new Postgres container."""
    name = container_name(app_name, env, container_template)
    db_name = database_name(app_name, env, database_template)

    _run_docker([
        "run", "-d",
        "--name", name,
        "-e", f"POSTGRES_USER={app_name}",
        "-e", f"POSTGRES_PASSWORD={password}",
        "-e", f"POSTGRES_DB={db_name}",
        "-p", f"127.0.0.1:{port}:5432",
        f"postgres:{pg_version}",
    ])

    # Wait for Postgres to be ready
    _wait_for_healthy(name)

    return {
        "container": name,
        "database": db_name,
        "port": port,
        "user": app_name,
        "status": "running",
    }


def start_container(name: str) -> None:
    """Start a stopped container."""
    _run_docker(["start", name])
    _wait_for_healthy(name)


def stop_container(name: str) -> None:
    """Stop a running container."""
    _run_docker(["stop", name])


def remove_container(name: str) -> None:
    """Remove a container (must be stopped first)."""
    try:
        _run_docker(["rm", name])
    except DatabaseError:
        # Force remove if normal remove fails
        _run_docker(["rm", "-f", name])


def health_check(name: str) -> dict:
    """Run pg_isready inside the container."""
    try:
        _run_docker(["exec", name, "pg_isready"])
        return {"ok": True, "container": name, "error": None}
    except DatabaseError as e:
        return {"ok": False, "container": name, "error": str(e)}


def _wait_for_healthy(name: str, timeout: int = 30, interval: float = 0.5) -> None:
    """Wait for Postgres to accept connections inside the container."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = health_check(name)
        if result["ok"]:
            return
        time.sleep(interval)
    raise DatabaseError(
        f"Postgres in container '{name}' did not become ready within {timeout}s",
    )


def ensure_running(
    app_name: str,
    env: str,
    password: str,
    port: int,
    pg_version: str = "16",
    container_template: str | None = None,
    database_template: str | None = None,
) -> dict:
    """Ensure the database container is running. Restart or recreate as needed.

    Returns status dict with warnings if applicable.
    """
    name = container_name(app_name, env, container_template)
    status = get_container_status(name)

    if status == "running":
        # Verify it's actually healthy
        check = health_check(name)
        if check["ok"]:
            return {
                "container": name,
                "status": "running",
                "action": "none",
                "warnings": [],
            }

    if status == "exited":
        start_container(name)
        return {
            "container": name,
            "status": "running",
            "action": "restarted",
            "warnings": [],
        }

    # Container doesn't exist — recreate from config
    if status is not None:
        # Container exists in some other state, remove it
        try:
            remove_container(name)
        except DatabaseError:
            pass

    create_database(app_name, env, password, port, pg_version, container_template, database_template)
    return {
        "container": name,
        "status": "running",
        "action": "recreated",
        "warnings": [
            "This is a new empty database. Previous data is not recoverable. "
            "The application will need to run its migrations."
        ],
    }

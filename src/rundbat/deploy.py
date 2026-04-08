"""Deploy Service — deploy to remote Docker hosts via Docker contexts."""

import subprocess
from pathlib import Path


class DeployError(Exception):
    """Error from a deploy operation."""

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


def _run_docker(args: list[str], timeout: int = 120) -> str:
    """Run a docker command and return stdout. Raises DeployError on failure."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise DeployError(
            "Docker is not installed.",
            command=cmd,
            exit_code=-1,
            stderr="Command not found: docker",
        )
    except subprocess.TimeoutExpired:
        raise DeployError(
            f"Docker command timed out after {timeout}s",
            command=cmd,
            exit_code=-1,
            stderr="Timeout",
        )

    if result.returncode != 0:
        raise DeployError(
            f"Docker command failed: {result.stderr.strip()}",
            command=cmd,
            exit_code=result.returncode,
            stderr=result.stderr.strip(),
        )
    return result.stdout.strip()


def load_deploy_config(name: str) -> dict:
    """Load a named deployment config from rundbat.yaml.

    Returns dict with keys: host, compose_file, hostname (optional).
    """
    from rundbat import config

    cfg = config.load_config()
    deployments = cfg.get("deployments", {})
    if not deployments or name not in deployments:
        available = list(deployments.keys()) if deployments else []
        raise DeployError(
            f"No deployment '{name}' found in rundbat.yaml. "
            f"Available: {', '.join(available) or 'none'}. "
            f"Use 'rundbat deploy-init {name} --host ssh://user@host' to set one up."
        )

    deploy_cfg = deployments[name]
    if "host" not in deploy_cfg:
        raise DeployError(
            f"Deployment '{name}' is missing required 'host' field in rundbat.yaml."
        )

    return {
        "host": deploy_cfg["host"],
        "compose_file": deploy_cfg.get("compose_file", "docker/docker-compose.yml"),
        "hostname": deploy_cfg.get("hostname"),
    }


def _context_name(app_name: str, deploy_name: str) -> str:
    """Generate a Docker context name from app and deployment names."""
    return f"{app_name}-{deploy_name}"


def _context_exists(name: str) -> bool:
    """Check if a Docker context already exists."""
    try:
        output = _run_docker(["context", "ls", "--format", "{{.Name}}"])
        return name in output.splitlines()
    except DeployError:
        return False


def create_context(name: str, host: str) -> str:
    """Create a Docker context for a remote host.

    Returns the context name.
    """
    _run_docker(["context", "create", name, "--docker", f"host={host}"])
    return name


def ensure_context(app_name: str, deploy_name: str, host: str) -> str:
    """Ensure a Docker context exists, creating it if needed.

    Returns the context name.
    """
    name = _context_name(app_name, deploy_name)
    if not _context_exists(name):
        create_context(name, host)
    return name


def verify_access(context_name: str) -> dict:
    """Verify Docker access via a context by running docker info.

    Returns dict with status and server info.
    """
    try:
        output = _run_docker(["--context", context_name, "info", "--format",
                              "{{.ServerVersion}}"])
        return {"status": "ok", "context": context_name, "server_version": output}
    except DeployError as e:
        raise DeployError(
            f"Cannot connect to Docker via context '{context_name}'. "
            f"Check that SSH access works and Docker is running on the remote host.",
            command=e.command,
            exit_code=e.exit_code,
            stderr=e.stderr,
        )


def deploy(name: str, dry_run: bool = False, no_build: bool = False) -> dict:
    """Deploy to a named remote host via Docker context.

    Args:
        name: Deployment name from rundbat.yaml (e.g., 'prod')
        dry_run: If True, return the command without executing
        no_build: If True, skip the --build flag

    Returns dict with status, command, and optional hostname.
    """
    from rundbat import config

    cfg = config.load_config()
    app_name = cfg.get("app_name", "app")

    deploy_cfg = load_deploy_config(name)
    compose_file = deploy_cfg["compose_file"]
    host = deploy_cfg["host"]
    hostname = deploy_cfg.get("hostname")

    # Verify compose file exists
    if not Path(compose_file).exists():
        raise DeployError(
            f"Compose file not found: {compose_file}"
        )

    # Ensure Docker context
    ctx = ensure_context(app_name, name, host)

    # Build the docker compose command
    docker_args = [
        "--context", ctx,
        "compose", "-f", compose_file,
        "up", "-d",
    ]
    if not no_build:
        docker_args.append("--build")

    cmd_str = "docker " + " ".join(docker_args)

    if dry_run:
        result = {
            "status": "dry_run",
            "command": cmd_str,
            "context": ctx,
            "compose_file": compose_file,
        }
        if hostname:
            result["hostname"] = hostname
        return result

    # Execute
    _run_docker(docker_args, timeout=600)

    result = {
        "status": "success",
        "command": cmd_str,
        "context": ctx,
        "compose_file": compose_file,
    }
    if hostname:
        result["url"] = f"https://{hostname}/"
    return result


def init_deployment(name: str, host: str, compose_file: str | None = None,
                    hostname: str | None = None) -> dict:
    """Set up a new deployment target: verify access, create context, save config.

    Args:
        name: Deployment name (e.g., 'prod')
        host: SSH URL (e.g., 'ssh://root@docker1.example.com')
        compose_file: Path to compose file (optional)
        hostname: App hostname for post-deploy message (optional)

    Returns dict with status and details.
    """
    from rundbat import config

    cfg = config.load_config()
    app_name = cfg.get("app_name", "app")

    # Create Docker context
    ctx = _context_name(app_name, name)
    if _context_exists(ctx):
        # Context already exists, just verify it works
        verify_access(ctx)
    else:
        create_context(ctx, host)
        verify_access(ctx)

    # Save to rundbat.yaml
    deployments = cfg.get("deployments", {})
    deploy_entry = {"host": host}
    if compose_file:
        deploy_entry["compose_file"] = compose_file
    if hostname:
        deploy_entry["hostname"] = hostname
    deployments[name] = deploy_entry
    cfg["deployments"] = deployments
    config.save_config(data=cfg)

    return {
        "status": "ok",
        "deployment": name,
        "context": ctx,
        "host": host,
    }

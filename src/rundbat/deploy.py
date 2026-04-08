"""Deploy Service — deploy to Docker hosts via Docker contexts.

Supports three build strategies:
- context: build on the Docker context target (default)
- ssh-transfer: build locally with --platform, transfer via SSH
- github-actions: pull pre-built images from GHCR
"""

import os
import subprocess
from pathlib import Path

VALID_STRATEGIES = ("context", "ssh-transfer", "github-actions")


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


def _run_docker(args: list[str], timeout: int = 120,
                env: dict[str, str] | None = None) -> str:
    """Run a docker command and return stdout. Raises DeployError on failure."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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


def get_current_context() -> str:
    """Get the name of the currently active Docker context."""
    try:
        return _run_docker(["context", "show"])
    except DeployError:
        return "default"


def _detect_remote_platform(context_name: str) -> str | None:
    """Detect the architecture of a remote Docker host via its context.

    Returns a Docker platform string (e.g., 'linux/amd64') or None on failure.
    """
    try:
        arch = _run_docker([
            "--context", context_name, "info",
            "--format", "{{.Architecture}}",
        ])
    except DeployError:
        return None

    mapping = {
        "x86_64": "linux/amd64",
        "amd64": "linux/amd64",
        "aarch64": "linux/arm64",
        "arm64": "linux/arm64",
    }
    return mapping.get(arch.lower(), f"linux/{arch.lower()}" if arch else None)


def _parse_ssh_host(host_url: str) -> str:
    """Strip the ssh:// prefix from a host URL for subprocess use.

    'ssh://root@docker1.example.com' -> 'root@docker1.example.com'
    """
    if host_url.startswith("ssh://"):
        return host_url[len("ssh://"):]
    return host_url


def _ssh_cmd(host_url: str, ssh_key: str | None = None) -> str:
    """Build an ssh command string with optional identity file.

    Returns something like 'ssh -i config/prod/key -o StrictHostKeyChecking=no root@host'
    or just 'ssh root@host' when no key is provided.
    """
    ssh_host = _parse_ssh_host(host_url)
    if ssh_key:
        return f"ssh -i {ssh_key} -o StrictHostKeyChecking=no {ssh_host}"
    return f"ssh {ssh_host}"


def _get_buildable_images(compose_file: str) -> list[str]:
    """Get image names for services that have a build section.

    Parses the compose file YAML directly to find services with 'build'
    and derives image names from compose's naming convention.
    """
    import yaml

    path = Path(compose_file)
    if not path.exists():
        return []

    data = yaml.safe_load(path.read_text()) or {}
    services = data.get("services", {})
    project = path.parent.parent.name  # project dir name

    images = []
    for svc_name, svc_cfg in services.items():
        if isinstance(svc_cfg, dict) and "build" in svc_cfg:
            # Docker compose names images as <project>-<service>
            images.append(f"{project}-{svc_name}")

    return images


def _build_local(compose_file: str, platform: str | None = None,
                 timeout: int = 600) -> str:
    """Build images locally, optionally for a different platform.

    Uses docker compose build on the default (local) context.
    Sets DOCKER_DEFAULT_PLATFORM env var for cross-arch builds since
    not all Docker installations support `docker compose build --platform`.
    Returns stdout from the build command.
    """
    args = ["compose", "-f", compose_file, "build"]
    env = None
    if platform:
        env = {**os.environ, "DOCKER_DEFAULT_PLATFORM": platform}

    return _run_docker(args, timeout=timeout, env=env)


def _transfer_images(images: list[str], host_url: str,
                     ssh_key: str | None = None,
                     timeout: int = 600) -> None:
    """Transfer Docker images to a remote host via SSH.

    Runs: docker save <images> | ssh [-i key] <host> docker load
    """
    if not images:
        raise DeployError("No images to transfer.")

    ssh = _ssh_cmd(host_url, ssh_key)
    cmd = f"docker save {' '.join(images)} | {ssh} docker load"

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise DeployError(
            f"Image transfer timed out after {timeout}s",
            command=[cmd], exit_code=-1, stderr="Timeout",
        )

    if result.returncode != 0:
        raise DeployError(
            f"Image transfer failed: {result.stderr.strip()}",
            command=[cmd], exit_code=result.returncode,
            stderr=result.stderr.strip(),
        )


def _cleanup_remote(context_name: str) -> dict:
    """Run docker system prune on the remote to reclaim disk space.

    Returns dict with status and space reclaimed.
    """
    try:
        output = _run_docker([
            "--context", context_name, "system", "prune", "-f",
        ], timeout=60)
        return {"status": "ok", "output": output}
    except DeployError:
        return {"status": "skipped", "output": "cleanup failed (non-fatal)"}


def load_deploy_config(name: str) -> dict:
    """Load a named deployment config from rundbat.yaml.

    Returns dict with keys: docker_context, compose_file, hostname (optional).
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
    if "docker_context" not in deploy_cfg:
        raise DeployError(
            f"Deployment '{name}' is missing required 'docker_context' field "
            f"in rundbat.yaml. Run 'rundbat init' with --force to regenerate config."
        )

    return {
        "docker_context": deploy_cfg["docker_context"],
        "compose_file": deploy_cfg.get("compose_file", "docker/docker-compose.yml"),
        "hostname": deploy_cfg.get("hostname"),
        "host": deploy_cfg.get("host"),
        "platform": deploy_cfg.get("platform"),
        "build_strategy": deploy_cfg.get("build_strategy", "context"),
        "ssh_key": deploy_cfg.get("ssh_key"),
    }


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
            f"Check that the Docker daemon is reachable.",
            command=e.command,
            exit_code=e.exit_code,
            stderr=e.stderr,
        )


def deploy(name: str, dry_run: bool = False, no_build: bool = False,
           strategy: str | None = None, platform: str | None = None) -> dict:
    """Deploy to a named host using the configured build strategy.

    Args:
        name: Deployment name from rundbat.yaml (e.g., 'prod', 'dev')
        dry_run: If True, return the commands without executing
        no_build: If True, skip building (context strategy only)
        strategy: Override the configured build_strategy
        platform: Override the configured/detected platform

    Returns dict with status, commands, and optional hostname.
    """
    deploy_cfg = load_deploy_config(name)
    ctx = deploy_cfg["docker_context"]
    compose_file = deploy_cfg["compose_file"]
    hostname = deploy_cfg.get("hostname")
    host = deploy_cfg.get("host")
    ssh_key = deploy_cfg.get("ssh_key")
    build_strategy = strategy or deploy_cfg.get("build_strategy", "context")
    target_platform = platform or deploy_cfg.get("platform")

    if build_strategy not in VALID_STRATEGIES:
        raise DeployError(
            f"Unknown build strategy '{build_strategy}'. "
            f"Must be one of: {', '.join(VALID_STRATEGIES)}"
        )

    # Verify compose file exists
    if not Path(compose_file).exists():
        raise DeployError(f"Compose file not found: {compose_file}")

    # Strategy: ssh-transfer requires host
    if build_strategy == "ssh-transfer" and not host:
        raise DeployError(
            f"Strategy 'ssh-transfer' requires a 'host' field in the "
            f"deployment config. Run: rundbat deploy-init {name} --host ssh://user@host"
        )

    # Strategy: github-actions requires host for SSH pull+restart
    if build_strategy == "github-actions" and not host:
        raise DeployError(
            f"Strategy 'github-actions' requires a 'host' field in the "
            f"deployment config. Run: rundbat deploy-init {name} --host ssh://user@host"
        )

    if build_strategy == "context":
        return _deploy_context(ctx, compose_file, hostname, no_build, dry_run)
    elif build_strategy == "ssh-transfer":
        return _deploy_ssh_transfer(
            ctx, compose_file, hostname, host, target_platform, ssh_key,
            dry_run,
        )
    else:  # github-actions
        return _deploy_github_actions(ctx, compose_file, hostname, host,
                                      ssh_key, dry_run)


def _deploy_context(ctx: str, compose_file: str, hostname: str | None,
                    no_build: bool, dry_run: bool) -> dict:
    """Deploy using Docker context — build on target, then cleanup."""
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
            "strategy": "context",
            "commands": [cmd_str, f"docker --context {ctx} system prune -f"],
            "command": cmd_str,
            "context": ctx,
            "compose_file": compose_file,
        }
        if hostname:
            result["hostname"] = hostname
        return result

    _run_docker(docker_args, timeout=600)
    cleanup = _cleanup_remote(ctx)

    result = {
        "status": "success",
        "strategy": "context",
        "command": cmd_str,
        "context": ctx,
        "compose_file": compose_file,
        "cleanup": cleanup,
    }
    if hostname:
        result["url"] = f"https://{hostname}/"
    return result


def _deploy_ssh_transfer(ctx: str, compose_file: str, hostname: str | None,
                         host: str, target_platform: str | None,
                         ssh_key: str | None, dry_run: bool) -> dict:
    """Deploy by building locally and transferring images via SSH."""
    images = _get_buildable_images(compose_file)
    if not images:
        raise DeployError(
            f"No buildable services found in {compose_file}. "
            f"Ensure at least one service has a 'build' section."
        )

    ssh = _ssh_cmd(host, ssh_key)
    build_cmd = "docker compose -f " + compose_file + " build"
    if target_platform:
        build_cmd = f"DOCKER_DEFAULT_PLATFORM={target_platform} " + build_cmd
    transfer_cmd = f"docker save {' '.join(images)} | {ssh} docker load"
    up_cmd = f"docker --context {ctx} compose -f {compose_file} up -d"

    if dry_run:
        result = {
            "status": "dry_run",
            "strategy": "ssh-transfer",
            "commands": [build_cmd, transfer_cmd, up_cmd],
            "command": " && ".join([build_cmd, transfer_cmd, up_cmd]),
            "context": ctx,
            "compose_file": compose_file,
            "platform": target_platform,
        }
        if hostname:
            result["hostname"] = hostname
        return result

    _build_local(compose_file, target_platform)
    _transfer_images(images, host, ssh_key=ssh_key)
    _run_docker(["--context", ctx, "compose", "-f", compose_file, "up", "-d"],
                timeout=120)

    result = {
        "status": "success",
        "strategy": "ssh-transfer",
        "command": " && ".join([build_cmd, transfer_cmd, up_cmd]),
        "context": ctx,
        "compose_file": compose_file,
        "platform": target_platform,
        "images_transferred": images,
    }
    if hostname:
        result["url"] = f"https://{hostname}/"
    return result


def _deploy_github_actions(ctx: str, compose_file: str,
                           hostname: str | None, host: str,
                           ssh_key: str | None, dry_run: bool) -> dict:
    """Deploy by pulling pre-built images from GHCR."""
    pull_cmd = f"docker --context {ctx} compose -f {compose_file} pull"
    up_cmd = f"docker --context {ctx} compose -f {compose_file} up -d"

    if dry_run:
        result = {
            "status": "dry_run",
            "strategy": "github-actions",
            "commands": [pull_cmd, up_cmd],
            "command": " && ".join([pull_cmd, up_cmd]),
            "context": ctx,
            "compose_file": compose_file,
        }
        if hostname:
            result["hostname"] = hostname
        return result

    _run_docker(["--context", ctx, "compose", "-f", compose_file, "pull"],
                timeout=300)
    _run_docker(["--context", ctx, "compose", "-f", compose_file, "up", "-d"],
                timeout=120)

    result = {
        "status": "success",
        "strategy": "github-actions",
        "command": " && ".join([pull_cmd, up_cmd]),
        "context": ctx,
        "compose_file": compose_file,
    }
    if hostname:
        result["url"] = f"https://{hostname}/"
    return result


def _context_name(app_name: str, deploy_name: str) -> str:
    """Generate a Docker context name from app and deployment names."""
    return f"{app_name}-{deploy_name}"


def init_deployment(name: str, host: str, compose_file: str | None = None,
                    hostname: str | None = None,
                    build_strategy: str | None = None,
                    ssh_key: str | None = None) -> dict:
    """Set up a new deployment target: verify access, create context, save config.

    Args:
        name: Deployment name (e.g., 'prod')
        host: SSH URL (e.g., 'ssh://root@docker1.example.com')
        compose_file: Path to compose file (optional)
        hostname: App hostname for post-deploy message (optional)
        build_strategy: Build strategy (context, ssh-transfer, github-actions)
        ssh_key: Path to SSH private key file (e.g., config/prod/app-deploy-key)

    Returns dict with status and details.
    """
    from rundbat import config

    if build_strategy and build_strategy not in VALID_STRATEGIES:
        raise DeployError(
            f"Unknown build strategy '{build_strategy}'. "
            f"Must be one of: {', '.join(VALID_STRATEGIES)}"
        )

    cfg = config.load_config()
    app_name = cfg.get("app_name", "app")

    # Create Docker context
    ctx = _context_name(app_name, name)
    if _context_exists(ctx):
        verify_access(ctx)
    else:
        create_context(ctx, host)
        verify_access(ctx)

    # Detect remote platform
    remote_platform = _detect_remote_platform(ctx)

    # Auto-suggest strategy if not provided
    if not build_strategy:
        from rundbat.discovery import local_docker_platform
        local_plat = local_docker_platform()
        if remote_platform and remote_platform != local_plat:
            build_strategy = "ssh-transfer"
        else:
            build_strategy = "context"

    # Save to rundbat.yaml
    deployments = cfg.get("deployments", {})
    deploy_entry = {
        "docker_context": ctx,
        "host": host,
        "build_strategy": build_strategy,
    }
    if remote_platform:
        deploy_entry["platform"] = remote_platform
    if compose_file:
        deploy_entry["compose_file"] = compose_file
    if hostname:
        deploy_entry["hostname"] = hostname
    if ssh_key:
        deploy_entry["ssh_key"] = ssh_key
    deployments[name] = deploy_entry
    cfg["deployments"] = deployments
    config.save_config(data=cfg)

    return {
        "status": "ok",
        "deployment": name,
        "context": ctx,
        "host": host,
        "platform": remote_platform,
        "build_strategy": build_strategy,
        "ssh_key": ssh_key,
    }

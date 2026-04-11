"""rundbat CLI — top-level entry point with subcommands."""

import argparse
import json
import sys
from pathlib import Path

from rundbat import __version__


def _detect_app_name() -> tuple[str, str] | None:
    """Try to detect the app name from common project files."""
    cwd = Path.cwd()

    # Try package.json
    pkg_json = cwd / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            name = data.get("name")
            if name:
                return (name, "package.json name")
        except (json.JSONDecodeError, KeyError):
            pass

    # Try pyproject.toml
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text())
            name = data.get("project", {}).get("name")
            if name:
                return (name, "pyproject.toml project.name")
        except (ImportError, KeyError):
            pass

    # Fallback: use directory name
    return (cwd.name, f"directory name ({cwd.name})")


def _output(data: dict, as_json: bool) -> None:
    """Print result as JSON or human-readable."""
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")


def _error(message: str, as_json: bool) -> None:
    """Print error and exit 1."""
    if as_json:
        print(json.dumps({"error": message}))
    else:
        print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def _check_prerequisites() -> list[str]:
    """Check that Docker and dotconfig are available. Returns list of warnings."""
    import shutil
    warnings = []

    if not shutil.which("docker"):
        warnings.append("Docker is not installed or not in PATH.")
    if not shutil.which("dotconfig"):
        warnings.append("dotconfig is not installed. Install with: pipx install dotconfig")

    return warnings


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialize rundbat in the current project."""
    from rundbat import config, installer
    from rundbat.config import ConfigError

    project_dir = Path.cwd()
    print(f"Initializing rundbat in {project_dir}\n")

    # Step 1: Check prerequisites
    warnings = _check_prerequisites()
    for w in warnings:
        print(f"  WARNING: {w}")
    if warnings:
        print()

    # Step 2: Detect or use provided app name
    if args.app_name:
        app_name = args.app_name
        app_name_source = "command line"
    else:
        detected = _detect_app_name()
        app_name, app_name_source = detected
        print(f"  Detected app name: {app_name} (from {app_name_source})")

    # Step 3: Initialize dotconfig if needed
    print(f"  Checking dotconfig...", end=" ")
    if config.is_initialized():
        print("already initialized.")
    else:
        try:
            config.init_dotconfig()
            print("initialized.")
        except ConfigError as e:
            print(f"failed!\n    {e}")
            print("\n  Install dotconfig first: pipx install dotconfig")
            sys.exit(1)

    # Step 4: Detect current Docker context for local deployments
    from rundbat.deploy import get_current_context
    local_context = get_current_context()
    print(f"  Docker context: {local_context}")

    # Step 5: Save config/rundbat.yaml (skip if exists, unless --force)
    config_path = Path("config") / "rundbat.yaml"
    if config_path.exists() and not args.force:
        print(f"  rundbat.yaml already exists, skipping. (Use --force to overwrite.)")
    else:
        print(f"  Saving rundbat config...", end=" ")
        try:
            data = {
                "app_name": app_name,
                "app_name_source": app_name_source,
                "container_template": "{app}-{env}-pg",
                "database_template": "{app}_{env}",
                "deployments": {
                    "dev": {
                        "docker_context": local_context,
                        "compose_file": "docker/docker-compose.yml",
                    },
                    "prod": {
                        "docker_context": "",
                        "compose_file": "docker/docker-compose.prod.yml",
                        "hostname": "",
                    },
                    "test": {
                        "docker_context": local_context,
                        "compose_file": "docker/docker-compose.yml",
                    },
                },
                "notes": [],
            }
            config.save_config(data=data)
            print("done.")
        except ConfigError as e:
            print(f"failed!\n    {e}")
            sys.exit(1)

    # Step 5: Install Claude integration files
    print(f"  Installing Claude integration files...", end=" ")
    try:
        install_result = installer.install(project_dir)
        print("done.")
    except Exception as e:
        print(f"skipped ({e}).")

    # Summary
    print(f"\nrundbat is ready!")
    print(f"  App name:  {app_name}")
    print(f"  Source:    {app_name_source}")
    print(f"\nNext steps:")
    print(f"  - Run 'rundbat generate' to generate Docker artifacts")
    print(f"  - Run 'rundbat deploy-init prod --host ssh://user@host' to set up a deploy target")


def cmd_deploy(args):
    """Deploy using the configured build strategy."""
    from rundbat import deploy
    from rundbat.deploy import DeployError

    try:
        result = deploy.deploy(
            args.name, dry_run=args.dry_run, no_build=args.no_build,
            strategy=args.strategy, platform=args.platform,
        )
    except DeployError as e:
        _error(str(e), args.json)
        return

    if args.json:
        _output(result, args.json)
    else:
        strategy = result.get("strategy", "context")
        if result.get("status") == "dry_run":
            print(f"Dry run (strategy: {strategy}) — would execute:")
            for cmd in result.get("commands", [result.get("command", "")]):
                print(f"  {cmd}")
        else:
            print(f"Deployed via strategy '{strategy}', context '{result['context']}'")
            if result.get("platform"):
                print(f"  Platform: {result['platform']}")
            if result.get("images_transferred"):
                print(f"  Images transferred: {', '.join(result['images_transferred'])}")
            if result.get("url"):
                print(f"  {result['url']}")


def cmd_deploy_init(args):
    """Set up a new deployment target."""
    from rundbat import deploy
    from rundbat.deploy import DeployError

    try:
        result = deploy.init_deployment(
            args.name, args.host,
            compose_file=args.compose_file,
            hostname=args.hostname,
            build_strategy=args.strategy,
            ssh_key=args.ssh_key,
            deploy_mode=getattr(args, "deploy_mode", None),
            image=getattr(args, "image", None),
        )
    except DeployError as e:
        _error(str(e), args.json)
        return

    if args.json:
        _output(result, args.json)
    else:
        print(f"Deployment '{result['deployment']}' configured.")
        print(f"  Docker context: {result['context']}")
        print(f"  Host: {result['host']}")
        print(f"  Build strategy: {result['build_strategy']}")
        if result.get("ssh_key"):
            print(f"  SSH key: {result['ssh_key']}")
        if result.get("platform"):
            from rundbat.discovery import local_docker_platform
            local_plat = local_docker_platform()
            print(f"  Remote platform: {result['platform']} (local: {local_plat})")
            if result["platform"] != local_plat:
                print(f"  Cross-architecture: yes — images will be built for {result['platform']}")
        print(f"\nRun 'rundbat deploy {result['deployment']}' to deploy.")


def cmd_probe(args):
    """Probe a deployment target for reverse proxy detection."""
    from rundbat import config
    from rundbat.discovery import detect_caddy
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(str(e), args.json)
        return

    deployments = cfg.get("deployments", {})
    name = args.name
    if name not in deployments:
        _error(f"Deployment '{name}' not found in rundbat.yaml", args.json)
        return

    dep = deployments[name]
    ctx = dep.get("docker_context")
    if not ctx:
        _error(f"Deployment '{name}' has no docker_context", args.json)
        return

    caddy = detect_caddy(ctx)
    reverse_proxy = "caddy" if caddy["running"] else "none"
    dep["reverse_proxy"] = reverse_proxy
    deployments[name] = dep
    cfg["deployments"] = deployments
    config.save_config(data=cfg)

    result = {"deployment": name, "reverse_proxy": reverse_proxy,
              "container": caddy.get("container")}
    _output(result, args.json)


def cmd_generate(args):
    """Generate Docker artifacts from rundbat.yaml config."""
    from rundbat import generators, config
    from rundbat.config import ConfigError

    project_dir = Path.cwd()

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(f"Cannot load config: {e}. Run 'rundbat init' first.", args.json)
        return

    result = generators.generate_artifacts(
        project_dir, cfg,
        deployment=getattr(args, "deployment", None),
    )
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


def cmd_init_docker(args):
    """Scaffold a docker/ directory for the project (deprecated)."""
    from rundbat import generators, config
    from rundbat.config import ConfigError

    project_dir = Path.cwd()

    # Load rundbat.yaml for app_name, framework, services, deployments
    app_name = "app"
    framework = None
    services = None
    hostname = None
    swarm = False
    deployments = None

    try:
        cfg = config.load_config()
        app_name = cfg.get("app_name", "app")
        if cfg.get("framework"):
            framework = {"language": "unknown", "framework": cfg["framework"], "entry_point": ""}
        services = cfg.get("services")
        deployments = cfg.get("deployments")
        # Check for deployment hostname and Caddy
        caddy_deployment = None
        for dep_name, dep in (deployments or {}).items():
            if dep.get("hostname") and not hostname:
                hostname = dep["hostname"]
                swarm = dep.get("swarm", False)
            if dep.get("reverse_proxy") == "caddy" and not caddy_deployment:
                caddy_deployment = dep_name

        # --hostname flag overrides config
        if getattr(args, "hostname", None):
            hostname = args.hostname

        # Warn if Caddy detected but no hostname
        if caddy_deployment and not hostname:
            print(f"Caddy detected on deployment '{caddy_deployment}' — pass --hostname to include reverse proxy labels")
    except ConfigError:
        pass

    result = generators.init_docker(
        project_dir, app_name, framework, services, hostname, swarm,
        deployments,
    )
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


# ---------------------------------------------------------------------------
# Lifecycle commands: build, up, down, logs
# ---------------------------------------------------------------------------

def _resolve_deployment(name: str, as_json: bool) -> tuple[dict, dict] | None:
    """Load config and find a deployment by name. Returns (cfg, deploy_cfg) or exits."""
    from rundbat import config
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(f"Cannot load config: {e}", as_json)
        return None

    deployments = cfg.get("deployments", {})
    if name not in deployments:
        available = ", ".join(deployments.keys()) if deployments else "none"
        _error(f"Deployment '{name}' not found. Available: {available}", as_json)
        return None

    return cfg, deployments[name]


def _compose_file_for_deployment(name: str) -> Path:
    """Return the expected compose file path for a deployment."""
    return Path(f"docker/docker-compose.{name}.yml")


def cmd_build(args):
    """Build images for a deployment."""
    import os
    import subprocess

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = dep_cfg.get("deploy_mode", "compose")
    build_strategy = dep_cfg.get("build_strategy", "context")

    # github-actions strategy: trigger build via gh CLI
    if build_strategy == "github-actions":
        from rundbat.discovery import detect_gh
        from rundbat.deploy import _get_github_repo, DeployError

        gh = detect_gh()
        if not gh["installed"]:
            _error("GitHub CLI (gh) is not installed. Install from https://cli.github.com/", args.json)
            return
        if not gh["authenticated"]:
            _error("GitHub CLI is not authenticated. Run 'gh auth login' first.", args.json)
            return

        try:
            repo = _get_github_repo()
        except DeployError as e:
            _error(str(e), args.json)
            return

        result = subprocess.run(
            ["gh", "workflow", "run", "build.yml", "--repo", repo],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            _error(f"Failed to trigger build: {result.stderr.strip()}", args.json)
            return

        if args.json:
            _output({"status": "triggered", "repo": repo, "workflow": "build.yml"}, True)
        else:
            print(f"Build triggered on GitHub Actions for {args.name}")
            print(f"  Watch: gh run watch --repo {repo}")
        return

    # Local build via docker compose
    if deploy_mode == "run":
        _error(f"Deployment '{args.name}' uses run mode — no local build. Use 'rundbat build' with github-actions strategy.", args.json)
        return

    compose_file = _compose_file_for_deployment(args.name)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    ctx = dep_cfg.get("docker_context", "default")
    env = {**os.environ}
    if ctx and ctx != "default":
        env["DOCKER_CONTEXT"] = ctx

    cmd = ["docker", "compose", "-f", str(compose_file), "build"]
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_up(args):
    """Start a deployment."""
    import os
    import subprocess

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = dep_cfg.get("deploy_mode", "compose")
    build_strategy = dep_cfg.get("build_strategy", "context")
    ctx = dep_cfg.get("docker_context", "default")

    # --workflow flag: trigger deploy via GitHub Actions
    if getattr(args, "workflow", False):
        from rundbat.discovery import detect_gh
        from rundbat.deploy import _get_github_repo, DeployError

        gh = detect_gh()
        if not gh["installed"]:
            _error("GitHub CLI (gh) is not installed.", args.json)
            return
        if not gh["authenticated"]:
            _error("GitHub CLI is not authenticated. Run 'gh auth login'.", args.json)
            return

        try:
            repo = _get_github_repo()
        except DeployError as e:
            _error(str(e), args.json)
            return

        result = subprocess.run(
            ["gh", "workflow", "run", "deploy.yml", "--repo", repo],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            _error(f"Failed to trigger deploy: {result.stderr.strip()}", args.json)
            return

        print(f"Deploy workflow triggered for {args.name}")
        print(f"  Watch: gh run watch --repo {repo}")
        return

    # Run mode
    if deploy_mode == "run":
        from rundbat.deploy import _deploy_run, DeployError
        try:
            result = _deploy_run(args.name, dep_cfg, cfg.get("app_name", "app"),
                                 dry_run=False)
            _output(result, args.json)
        except DeployError as e:
            _error(str(e), args.json)
        return

    # Compose mode
    compose_file = _compose_file_for_deployment(args.name)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    env = {**os.environ}
    if ctx and ctx != "default":
        env["DOCKER_CONTEXT"] = ctx

    # Pull first for github-actions strategy
    if build_strategy == "github-actions":
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "pull"],
            env=env,
        )

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_down(args):
    """Stop a deployment."""
    import os
    import subprocess

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = dep_cfg.get("deploy_mode", "compose")
    ctx = dep_cfg.get("docker_context", "default")
    app_name = cfg.get("app_name", "app")

    env = {**os.environ}
    if ctx and ctx != "default":
        env["DOCKER_CONTEXT"] = ctx

    if deploy_mode == "run":
        subprocess.run(["docker", "stop", app_name], env=env, capture_output=True)
        subprocess.run(["docker", "rm", app_name], env=env, capture_output=True)
        print(f"Stopped {app_name}")
        return

    compose_file = _compose_file_for_deployment(args.name)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_logs(args):
    """Tail logs from a deployment."""
    import os
    import subprocess

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = dep_cfg.get("deploy_mode", "compose")
    ctx = dep_cfg.get("docker_context", "default")
    app_name = cfg.get("app_name", "app")

    env = {**os.environ}
    if ctx and ctx != "default":
        env["DOCKER_CONTEXT"] = ctx

    if deploy_mode == "run":
        cmd = ["docker", "logs", "-f", app_name]
        subprocess.run(cmd, env=env)
        return

    compose_file = _compose_file_for_deployment(args.name)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    cmd = ["docker", "compose", "-f", str(compose_file), "logs", "-f"]
    subprocess.run(cmd, env=env)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_json_flag(parser):
    """Add --json flag to a subparser."""
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rundbat",
        description="Deployment Expert — manage Docker-based dev environments",
        epilog="""\
Commands:
  rundbat init               Set up rundbat in your project
  rundbat generate           Generate Docker artifacts from config
  rundbat build <name>       Build images for a deployment
  rundbat up <name>          Start a deployment
  rundbat down <name>        Stop a deployment
  rundbat logs <name>        Tail logs from a deployment
  rundbat deploy <name>      Deploy to a remote host
  rundbat deploy-init <name> Set up a deployment target""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"rundbat {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    # rundbat init
    init_parser = subparsers.add_parser(
        "init", help="Set up rundbat in the current project",
    )
    init_parser.add_argument(
        "--app-name",
        help="Application name (auto-detected if not provided)",
    )
    init_parser.add_argument(
        "--force", action="store_true", default=False,
        help="Overwrite rundbat.yaml even if it already exists",
    )
    init_parser.set_defaults(func=cmd_init)

    # rundbat generate
    generate_parser = subparsers.add_parser(
        "generate", help="Generate Docker artifacts from rundbat.yaml config",
    )
    generate_parser.add_argument(
        "--deployment", default=None,
        help="Regenerate only this deployment (default: all)",
    )
    _add_json_flag(generate_parser)
    generate_parser.set_defaults(func=cmd_generate)

    # rundbat init-docker (deprecated)
    init_docker_parser = subparsers.add_parser(
        "init-docker", help="(Deprecated) Use 'rundbat generate' instead",
    )
    init_docker_parser.add_argument(
        "--hostname",
        default=None,
        help="App hostname for Caddy reverse proxy labels (e.g. app.example.com)",
    )
    _add_json_flag(init_docker_parser)
    init_docker_parser.set_defaults(func=cmd_init_docker)

    # rundbat build <name>
    build_parser = subparsers.add_parser(
        "build", help="Build images for a deployment",
    )
    build_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(build_parser)
    build_parser.set_defaults(func=cmd_build)

    # rundbat up <name>
    up_parser = subparsers.add_parser(
        "up", help="Start a deployment (pull/build + start containers)",
    )
    up_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    up_parser.add_argument(
        "--workflow", action="store_true", default=False,
        help="Trigger deploy via GitHub Actions workflow instead of local Docker",
    )
    _add_json_flag(up_parser)
    up_parser.set_defaults(func=cmd_up)

    # rundbat down <name>
    down_parser = subparsers.add_parser(
        "down", help="Stop a deployment",
    )
    down_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(down_parser)
    down_parser.set_defaults(func=cmd_down)

    # rundbat logs <name>
    logs_parser = subparsers.add_parser(
        "logs", help="Tail logs from a deployment",
    )
    logs_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(logs_parser)
    logs_parser.set_defaults(func=cmd_logs)

    # rundbat deploy <name>
    deploy_parser = subparsers.add_parser(
        "deploy", help="Deploy to a named remote host via Docker context",
    )
    deploy_parser.add_argument(
        "name", help="Deployment name (e.g., prod, staging)",
    )
    deploy_parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Show the command without executing",
    )
    deploy_parser.add_argument(
        "--no-build", action="store_true", default=False,
        help="Skip the --build flag (context strategy only)",
    )
    deploy_parser.add_argument(
        "--strategy", default=None,
        choices=["context", "ssh-transfer", "github-actions"],
        help="Override the configured build strategy",
    )
    deploy_parser.add_argument(
        "--platform", default=None,
        help="Override the target platform (e.g., linux/amd64)",
    )
    _add_json_flag(deploy_parser)
    deploy_parser.set_defaults(func=cmd_deploy)

    # rundbat deploy-init <name> --host <ssh://user@host>
    deploy_init_parser = subparsers.add_parser(
        "deploy-init", help="Set up a new deployment target",
    )
    deploy_init_parser.add_argument(
        "name", help="Deployment name (e.g., prod, staging)",
    )
    deploy_init_parser.add_argument(
        "--host", required=True,
        help="SSH URL for the remote Docker host (e.g., ssh://root@host)",
    )
    deploy_init_parser.add_argument(
        "--compose-file",
        help="Path to compose file (default: docker/docker-compose.yml)",
    )
    deploy_init_parser.add_argument(
        "--hostname",
        help="App hostname for post-deploy message (e.g., app.example.com)",
    )
    deploy_init_parser.add_argument(
        "--strategy", default=None,
        choices=["context", "ssh-transfer", "github-actions"],
        help="Build strategy for this deployment",
    )
    deploy_init_parser.add_argument(
        "--deploy-mode", default=None,
        choices=["compose", "run"],
        help="Deploy mode: compose (default) or run (single container)",
    )
    deploy_init_parser.add_argument(
        "--image", default=None,
        help="Registry image reference (e.g., ghcr.io/owner/repo) for run mode",
    )
    deploy_init_parser.add_argument(
        "--ssh-key", default=None,
        help="Path to SSH private key for this deployment (e.g., config/prod/app-deploy-key)",
    )
    _add_json_flag(deploy_init_parser)
    deploy_init_parser.set_defaults(func=cmd_deploy_init)

    # rundbat probe <name>
    probe_parser = subparsers.add_parser(
        "probe", help="Detect reverse proxy on a deployment target",
    )
    probe_parser.add_argument(
        "name", help="Deployment name (from rundbat.yaml)",
    )
    _add_json_flag(probe_parser)
    probe_parser.set_defaults(func=cmd_probe)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

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
    print(f"  - Run 'rundbat init-docker' to generate Docker artifacts")
    print(f"  - Run 'rundbat deploy-init prod --host ssh://user@host' to set up a deploy target")


def cmd_deploy(args):
    """Deploy to a named remote host via Docker context."""
    from rundbat import deploy
    from rundbat.deploy import DeployError

    try:
        result = deploy.deploy(args.name, dry_run=args.dry_run,
                               no_build=args.no_build)
    except DeployError as e:
        _error(str(e), args.json)
        return

    if args.json:
        _output(result, args.json)
    else:
        if result.get("status") == "dry_run":
            print(f"Dry run — would execute:\n  {result['command']}")
        else:
            print(f"Deployed via context '{result['context']}'")
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
        print(f"\nRun 'rundbat deploy {result['deployment']}' to deploy.")


def cmd_init_docker(args):
    """Scaffold a docker/ directory for the project."""
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
        # Check for deployment hostname
        for dep in (deployments or {}).values():
            if dep.get("hostname"):
                hostname = dep["hostname"]
                swarm = dep.get("swarm", False)
                break
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
  rundbat init-docker        Generate Docker artifacts (Dockerfile, compose, Justfile)
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

    # rundbat init-docker
    init_docker_parser = subparsers.add_parser(
        "init-docker", help="Scaffold a docker/ directory (Dockerfile, compose, Justfile)",
    )
    _add_json_flag(init_docker_parser)
    init_docker_parser.set_defaults(func=cmd_init_docker)

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
        help="Skip the --build flag (don't rebuild images)",
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
    _add_json_flag(deploy_init_parser)
    deploy_init_parser.set_defaults(func=cmd_deploy_init)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

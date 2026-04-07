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


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialize rundbat in the current project."""
    from rundbat import config, installer
    from rundbat.config import ConfigError

    project_dir = Path.cwd()
    print(f"Initializing rundbat in {project_dir}\n")

    # Step 1: Detect or use provided app name
    if args.app_name:
        app_name = args.app_name
        app_name_source = "command line"
    else:
        detected = _detect_app_name()
        app_name, app_name_source = detected
        print(f"  Detected app name: {app_name} (from {app_name_source})")

    # Step 2: Initialize dotconfig if needed
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

    # Step 3: Save config/rundbat.yaml
    print(f"  Saving rundbat config...", end=" ")
    try:
        data = {
            "app_name": app_name,
            "app_name_source": app_name_source,
            "container_template": "{app}-{env}-pg",
            "database_template": "{app}_{env}",
            "notes": [],
        }
        config.save_config(data=data)
        print("done.")
    except ConfigError as e:
        print(f"failed!\n    {e}")
        sys.exit(1)

    # Step 4: Install Claude integration files
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
    print(f"  - Run 'rundbat discover' to check system prerequisites")
    print(f"  - Run 'rundbat create-env dev' to provision a database")
    print(f"  - Run 'rundbat env list' to see environments")


def cmd_mcp(args):
    """Deprecated — the MCP server has been removed."""
    print("The rundbat MCP server has been removed.", file=sys.stderr)
    print("", file=sys.stderr)
    print("rundbat now integrates with Claude via native .claude/ directories.", file=sys.stderr)
    print("Run 'rundbat install' to set up Claude integration files.", file=sys.stderr)
    sys.exit(1)


def cmd_install(args):
    """Install Claude integration files into the current project."""
    from rundbat import installer
    project_dir = Path.cwd()
    result = installer.install(project_dir)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in result.get("installed", []):
            print(f"  + {item['file']}")
        print(f"\nManifest: {result['manifest']}")
        print(f"Installed {len(result.get('installed', []))} files.")


def cmd_uninstall(args):
    """Remove rundbat Claude integration files."""
    from rundbat import installer
    project_dir = Path.cwd()
    result = installer.uninstall(project_dir)
    if args.json:
        print(json.dumps(result, indent=2))
    elif "warning" in result:
        print(result["warning"])
    else:
        for f in result.get("removed", []):
            print(f"  - {f}")
        print(f"\nRemoved {len(result.get('removed', []))} files.")


def cmd_discover(args):
    """Detect system environment."""
    from rundbat import discovery
    result = discovery.discover_system()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for key, value in result.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")


def cmd_create_env(args):
    """Provision a new environment."""
    from rundbat import environment
    result = environment.create_environment(args.env, args.type)
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


def cmd_get_config(args):
    """Load config, auto-restart containers, return connection string."""
    from rundbat import environment
    result = environment.get_environment_config(args.env)
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


def cmd_start(args):
    """Start the database container for an environment."""
    from rundbat import database
    from rundbat.database import DatabaseError

    try:
        name = database.get_container_name(args.env)
        status = database.get_container_status(name)
        if status == "running":
            result = {"status": "already_running", "container": name}
        elif status == "exited":
            database.start_container(name)
            result = {"status": "started", "container": name}
        else:
            _error(f"Container {name} not found. Use 'rundbat create-env' first.", args.json)
            return
    except DatabaseError as e:
        _error(str(e), args.json)
        return
    _output(result, args.json)


def cmd_stop(args):
    """Stop the database container for an environment."""
    from rundbat import database
    from rundbat.database import DatabaseError

    try:
        name = database.get_container_name(args.env)
        database.stop_container(name)
        result = {"status": "stopped", "container": name}
    except DatabaseError as e:
        _error(str(e), args.json)
        return
    _output(result, args.json)


def cmd_health(args):
    """Check database connectivity for an environment."""
    from rundbat import database
    from rundbat.database import DatabaseError

    try:
        name = database.get_container_name(args.env)
        result = database.health_check(name)
    except DatabaseError as e:
        _error(str(e), args.json)
        return
    _output(result, args.json)


def cmd_validate(args):
    """Full validation of an environment."""
    from rundbat import environment
    result = environment.validate_environment(args.env)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        ok = result.get("ok", False)
        print(f"Environment '{args.env}': {'OK' if ok else 'FAILED'}\n")
        for check_name, check in result.get("checks", {}).items():
            icon = "✓" if check.get("ok") else "✗"
            print(f"  {icon} {check_name}: {check.get('detail', '')}")


def cmd_set_secret(args):
    """Store a secret in a deployment's .env."""
    from rundbat import config
    from rundbat.config import ConfigError

    if "=" not in args.secret:
        _error("Secret must be in KEY=VALUE format", args.json)

    key, _, value = args.secret.partition("=")
    try:
        config.save_secret(args.env, key, value)
        result = {"status": "ok", "env": args.env, "key": key}
    except ConfigError as e:
        _error(str(e), args.json)
        return
    _output(result, args.json)


def cmd_check_drift(args):
    """Detect if app name changed at its source file."""
    from rundbat import config
    from rundbat.config import ConfigError

    try:
        result = config.check_config_drift(args.env)
    except ConfigError as e:
        _error(str(e), args.json)
        return
    _output(result, args.json)


def cmd_env_list(args):
    """List configured environments."""
    config_dir = Path("config")
    if not config_dir.exists():
        print("No config/ directory found. Run 'rundbat init' first.")
        sys.exit(1)

    envs = []
    skip_dirs = {"local", ".git", "keys"}
    for entry in sorted(config_dir.iterdir()):
        if entry.is_dir() and entry.name not in skip_dirs:
            has_env = (entry / "public.env").exists() or (entry / "secrets.env").exists()
            envs.append((entry.name, has_env))

    if not envs:
        print("No environments found in config/.")
        return

    if hasattr(args, "json") and args.json:
        print(json.dumps([{"name": n, "configured": c} for n, c in envs], indent=2))
    else:
        print(f"{'ENVIRONMENT':<20} {'RUNDBAT CONFIG'}")
        print(f"{'─' * 20} {'─' * 15}")
        for name, has_config in envs:
            status = "yes" if has_config else "no"
            print(f"{name:<20} {status}")


def cmd_env_connstr(args):
    """Get the connection string for an environment."""
    from rundbat import config
    from rundbat.config import ConfigError

    env = args.env

    # Try to get DATABASE_URL from secrets
    try:
        env_content = config.load_env(env)
        for line in env_content.splitlines():
            if line.startswith("DATABASE_URL="):
                connstr = line.split("=", 1)[1]
                print(connstr)
                return
    except ConfigError:
        pass

    # Fallback: construct from rundbat.yaml
    try:
        env_config = config.load_config(env)
        db = env_config.get("database", {})
        app_name = env_config.get("app_name")
        if db and app_name:
            port = db.get("port", 5432)
            db_name = db.get("name", f"{app_name}_{env}")
            print(f"postgresql://{app_name}:****@localhost:{port}/{db_name}")
            print(f"  (password masked — load from dotconfig secrets)", file=sys.stderr)
            return
    except ConfigError:
        pass

    print(f"No connection string found for environment '{env}'.", file=sys.stderr)
    print(f"Use 'rundbat env list' to see configured environments.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_json_flag(parser):
    """Add --json flag to a subparser."""
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )


def _add_env_arg(parser, **kwargs):
    """Add positional env argument to a subparser."""
    parser.add_argument(
        "env", help="Environment name (e.g., dev, staging, prod)",
        **kwargs,
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rundbat",
        description="Deployment Expert — manage Docker-based dev environments",
        epilog="""\
Getting started:
  rundbat init               Set up rundbat in your project
  rundbat install            Install Claude integration files

Commands:
  rundbat discover           Detect system environment
  rundbat create-env <env>   Provision a new environment
  rundbat get-config <env>   Load config and connection string
  rundbat start <env>        Start database container
  rundbat stop <env>         Stop database container
  rundbat health <env>       Check database connectivity
  rundbat validate <env>     Full environment validation
  rundbat set-secret <env>   Store a secret
  rundbat check-drift <env>  Detect app name changes
  rundbat env list           List configured environments
  rundbat env connstr <env>  Get a connection string""",
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
    init_parser.set_defaults(func=cmd_init)

    # rundbat install
    install_parser = subparsers.add_parser(
        "install", help="Install Claude integration files (.claude/ skills, agents, rules)",
    )
    _add_json_flag(install_parser)
    install_parser.set_defaults(func=cmd_install)

    # rundbat uninstall
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Remove rundbat Claude integration files",
    )
    _add_json_flag(uninstall_parser)
    uninstall_parser.set_defaults(func=cmd_uninstall)

    # rundbat mcp (deprecated)
    mcp_parser = subparsers.add_parser(
        "mcp", help="(deprecated) Use 'rundbat install' instead",
    )
    mcp_parser.set_defaults(func=cmd_mcp)

    # rundbat discover
    discover_parser = subparsers.add_parser(
        "discover", help="Detect system environment (OS, Docker, dotconfig)",
    )
    _add_json_flag(discover_parser)
    discover_parser.set_defaults(func=cmd_discover)

    # rundbat create-env <env>
    create_env_parser = subparsers.add_parser(
        "create-env", help="Provision a new environment with database",
    )
    _add_env_arg(create_env_parser)
    create_env_parser.add_argument(
        "--type", default="local-docker",
        help="Environment type (default: local-docker)",
    )
    _add_json_flag(create_env_parser)
    create_env_parser.set_defaults(func=cmd_create_env)

    # rundbat get-config <env>
    get_config_parser = subparsers.add_parser(
        "get-config", help="Load config, auto-restart containers, return connection string",
    )
    _add_env_arg(get_config_parser)
    _add_json_flag(get_config_parser)
    get_config_parser.set_defaults(func=cmd_get_config)

    # rundbat start <env>
    start_parser = subparsers.add_parser(
        "start", help="Start the database container",
    )
    _add_env_arg(start_parser)
    _add_json_flag(start_parser)
    start_parser.set_defaults(func=cmd_start)

    # rundbat stop <env>
    stop_parser = subparsers.add_parser(
        "stop", help="Stop the database container",
    )
    _add_env_arg(stop_parser)
    _add_json_flag(stop_parser)
    stop_parser.set_defaults(func=cmd_stop)

    # rundbat health <env>
    health_parser = subparsers.add_parser(
        "health", help="Check database connectivity",
    )
    _add_env_arg(health_parser)
    _add_json_flag(health_parser)
    health_parser.set_defaults(func=cmd_health)

    # rundbat validate <env>
    validate_parser = subparsers.add_parser(
        "validate", help="Full environment validation",
    )
    _add_env_arg(validate_parser)
    _add_json_flag(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    # rundbat set-secret <env> <KEY=VALUE>
    set_secret_parser = subparsers.add_parser(
        "set-secret", help="Store a secret in a deployment",
    )
    _add_env_arg(set_secret_parser)
    set_secret_parser.add_argument(
        "secret", help="Secret in KEY=VALUE format",
    )
    _add_json_flag(set_secret_parser)
    set_secret_parser.set_defaults(func=cmd_set_secret)

    # rundbat check-drift [env]
    check_drift_parser = subparsers.add_parser(
        "check-drift", help="Detect if app name changed at its source",
    )
    _add_env_arg(check_drift_parser, nargs="?", default="dev")
    _add_json_flag(check_drift_parser)
    check_drift_parser.set_defaults(func=cmd_check_drift)

    # rundbat env
    env_parser = subparsers.add_parser(
        "env", help="Manage deployment environments",
    )
    env_subparsers = env_parser.add_subparsers(dest="env_command")

    # rundbat env list
    env_list_parser = env_subparsers.add_parser(
        "list", help="List configured environments",
    )
    _add_json_flag(env_list_parser)
    env_list_parser.set_defaults(func=cmd_env_list)

    # rundbat env connstr <env>
    env_connstr_parser = env_subparsers.add_parser(
        "connstr", help="Get the database connection string",
    )
    env_connstr_parser.add_argument(
        "env", help="Environment name (e.g., dev, staging, prod)",
    )
    env_connstr_parser.set_defaults(func=cmd_env_connstr)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "env" and not getattr(args, "env_command", None):
        env_parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

"""rundbat CLI — top-level entry point with subcommands."""

import argparse
import json
import sys
from pathlib import Path

from rundbat import __version__

MCP_HELP = """\
rundbat mcp — Start the rundbat MCP server over stdio.

This command is meant to be called by an AI coding agent (e.g., Claude
Code) as an MCP server, not run directly by a human. The agent connects
over stdio and calls tools to manage deployment environments.

AVAILABLE MCP TOOLS

  Discovery:
    discover_system        Detect OS, Docker, dotconfig, Node.js, existing config
    verify_docker          Confirm docker info succeeds

  Project Setup:
    init_project           Initialize rundbat config via dotconfig; install
                           .mcp.json, rules, and hooks into the project
    create_environment     Provision a local Postgres container with credentials
    set_secret             Write a secret to dotconfig .env (encrypted via SOPS)

  Day-to-Day:
    get_environment_config Load config, auto-restart stopped containers, check
                           drift, return connection string — single call
    start_database         Start a stopped Postgres container
    stop_database          Stop a running Postgres container
    health_check           Run pg_isready to verify database connectivity
    validate_environment   Full check: config, secrets, container, connectivity
    check_config_drift     Detect if app name changed at its source file

HOW IT WORKS

  rundbat manages Docker-based local dev databases for Node/Postgres apps.
  All configuration is stored via dotconfig (encrypted secrets, layered
  .env files). Database containers follow the naming convention:

    Container: rundbat-{app_name}-{env}-pg
    Database:  rundbat_{app_name}_{env}

  The most common interaction is get_environment_config — call it at the
  start of a session and you get back a working connection string. If the
  container was stopped, rundbat restarts it. If it was deleted, rundbat
  recreates it (with a data-loss warning).

CONFIGURATION

  rundbat stores state in rundbat.yaml files managed by dotconfig:

    config/{env}/rundbat.yaml    Per-environment config
    config/{env}/secrets.env     SOPS-encrypted credentials
    config/{env}/public.env      Non-secret environment variables

USAGE

  In .mcp.json:
    { "mcpServers": { "rundbat": { "command": "rundbat", "args": ["mcp"] } } }
"""


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

    # Step 3: Save rundbat.yaml
    print(f"  Saving rundbat config...", end=" ")
    try:
        data = {
            "app_name": app_name,
            "app_name_source": app_name_source,
            "notes": [],
        }
        config.save_config("dev", data)
        print("done.")
    except ConfigError as e:
        print(f"failed!\n    {e}")
        sys.exit(1)

    # Step 4: Install MCP server, rules, and hooks
    print(f"  Installing MCP server config...", end=" ")
    result = installer.install_mcp_config(project_dir)
    print("done.")

    print(f"  Installing agent rules...", end=" ")
    installer.install_rules(project_dir)
    print("done.")

    print(f"  Installing agent hooks...", end=" ")
    hook_result = installer.install_hooks(project_dir)
    if hook_result["action"] == "already_present":
        print("already present.")
    else:
        print("done.")

    print(f"  Installing CLAUDE.md section...", end=" ")
    claude_result = installer.install_claude_md(project_dir)
    print(f"{claude_result['action']}.")

    # Summary
    print(f"\nrundbat is ready!")
    print(f"  App name:  {app_name}")
    print(f"  Source:    {app_name_source}")
    print(f"\nInstalled files:")
    print(f"  .mcp.json                  MCP server registration")
    print(f"  .claude/rules/rundbat.md   Agent guidance rules")
    print(f"  .claude/settings.json      Agent prompt hooks")
    print(f"  CLAUDE.md                  Agent instructions (guarded section)")
    print(f"\nNext steps:")
    print(f"  - An AI agent can now call rundbat MCP tools")
    print(f"  - Run 'rundbat env list' to see environments")
    print(f"  - The agent can call create_environment to set up a database")


def cmd_mcp(args):
    """Run the MCP server."""
    from rundbat.server import server
    server.run(transport="stdio")


def cmd_env_list(args):
    """List configured environments."""
    config_dir = Path("config")
    if not config_dir.exists():
        print("No config/ directory found. Run 'rundbat init' or use the MCP init_project tool first.")
        sys.exit(1)

    envs = []
    for entry in sorted(config_dir.iterdir()):
        if entry.is_dir() and entry.name not in ("local", ".git"):
            rundbat_yaml = entry / "rundbat.yaml"
            has_config = rundbat_yaml.exists()
            envs.append((entry.name, has_config))

    if not envs:
        print("No environments found in config/.")
        return

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
            db_name = db.get("name", f"rundbat_{app_name}_{env}")
            print(f"postgresql://{app_name}:****@localhost:{port}/{db_name}")
            print(f"  (password masked — load from dotconfig secrets)", file=sys.stderr)
            return
    except ConfigError:
        pass

    print(f"No connection string found for environment '{env}'.", file=sys.stderr)
    print(f"Use 'rundbat env list' to see configured environments.", file=sys.stderr)
    sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rundbat",
        description="Deployment Expert — manage Docker-based dev environments",
        epilog="""\
Getting started:
  rundbat init               Set up rundbat in your project (run this first)

AI AGENTS: Run 'rundbat mcp' to start the MCP server, or
'rundbat mcp --help' for full tool documentation.

Human users: Run 'rundbat env list' to see configured environments,
or 'rundbat env connstr <name>' to get a connection string.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"rundbat {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    # rundbat init
    init_parser = subparsers.add_parser(
        "init",
        help="Set up rundbat in the current project",
        description="Initialize rundbat: detect app name, set up dotconfig, install MCP server config, agent rules, and hooks.",
    )
    init_parser.add_argument(
        "--app-name",
        help="Application name (auto-detected from package.json or pyproject.toml if not provided)",
    )
    init_parser.set_defaults(func=cmd_init)

    # rundbat mcp
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Start the MCP server (for AI agents)",
        description=MCP_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mcp_parser.set_defaults(func=cmd_mcp)

    # rundbat env
    env_parser = subparsers.add_parser(
        "env",
        help="Manage deployment environments",
    )
    env_subparsers = env_parser.add_subparsers(dest="env_command")

    # rundbat env list
    env_list_parser = env_subparsers.add_parser(
        "list",
        help="List configured environments",
    )
    env_list_parser.set_defaults(func=cmd_env_list)

    # rundbat env connstr <env>
    env_connstr_parser = env_subparsers.add_parser(
        "connstr",
        help="Get the database connection string for an environment",
    )
    env_connstr_parser.add_argument(
        "env",
        help="Environment name (e.g., dev, staging, prod)",
    )
    env_connstr_parser.set_defaults(func=cmd_env_connstr)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "env" and not args.env_command:
        env_parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

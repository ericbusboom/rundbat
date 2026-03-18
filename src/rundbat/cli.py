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
    )
    parser.add_argument(
        "--version", action="version", version=f"rundbat {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

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

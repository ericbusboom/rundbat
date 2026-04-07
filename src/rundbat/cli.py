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
    """Deprecated — the MCP server has been removed."""
    print("The rundbat MCP server has been removed.", file=sys.stderr)
    print("", file=sys.stderr)
    print("rundbat now integrates with Claude via native .claude/ directories.", file=sys.stderr)
    print("Run 'rundbat install' to set up Claude integration files.", file=sys.stderr)
    sys.exit(1)


def cmd_env_list(args):
    """List configured environments."""
    config_dir = Path("config")
    if not config_dir.exists():
        print("No config/ directory found. Run 'rundbat init' or use the MCP init_project tool first.")
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
  rundbat env list           List configured environments
  rundbat env connstr <env>  Get a database connection string
  rundbat discover           Detect system environment
  rundbat create-env <env>   Provision a new environment
  rundbat get-config <env>   Load config and connection string""",
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

    # rundbat mcp (deprecated)
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="(deprecated) MCP server removed — use 'rundbat install' instead",
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

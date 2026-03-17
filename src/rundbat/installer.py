"""Project Installer — install rundbat integration files into a target project."""

import json
from pathlib import Path

RUNDBAT_HOOK_COMMAND = "echo 'rundbat: If this task involves databases, deployment, or environment setup, use the rundbat MCP server.'"

RUNDBAT_RULE = """\
# rundbat — Deployment Expert MCP Server

When working on tasks that involve any of the following, use the **rundbat
MCP tools** instead of running Docker or dotconfig commands directly:

- Setting up a database (local or remote)
- Getting a database connection string
- Starting or stopping database containers
- Managing deployment environments (dev, staging, production)
- Storing or retrieving secrets and environment variables
- Checking system prerequisites (Docker, dotconfig, Node.js)

rundbat handles Docker container lifecycle, dotconfig integration, port
allocation, health checks, and stale state recovery automatically.

**Key tools:**
- `discover_system` — check what's installed
- `init_project` — set up rundbat for a new project
- `create_environment` — provision a database environment
- `get_environment_config` — get connection string (auto-restarts containers)
- `set_secret` — store encrypted secrets
- `health_check` — verify database connectivity
"""


def install_mcp_config(project_dir: Path) -> dict:
    """Merge rundbat server entry into .mcp.json."""
    mcp_path = project_dir / ".mcp.json"

    if mcp_path.exists():
        data = json.loads(mcp_path.read_text())
    else:
        data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    data["mcpServers"]["rundbat"] = {
        "command": "rundbat",
        "args": [],
    }

    mcp_path.write_text(json.dumps(data, indent=2) + "\n")

    return {"file": str(mcp_path), "action": "merged"}


def install_rules(project_dir: Path) -> dict:
    """Write .claude/rules/rundbat.md rule file."""
    rules_dir = project_dir / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "rundbat.md"
    rule_path.write_text(RUNDBAT_RULE)

    return {"file": str(rule_path), "action": "written"}


def install_hooks(project_dir: Path) -> dict:
    """Merge UserPromptSubmit hook into .claude/settings.json."""
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_path = claude_dir / "settings.json"

    if settings_path.exists():
        data = json.loads(settings_path.read_text())
    else:
        data = {}

    if "hooks" not in data:
        data["hooks"] = {}

    if "UserPromptSubmit" not in data["hooks"]:
        data["hooks"]["UserPromptSubmit"] = []

    # Check if our hook already exists (idempotent)
    hooks = data["hooks"]["UserPromptSubmit"]
    already_exists = any(
        h.get("command") == RUNDBAT_HOOK_COMMAND
        for h in hooks
        if isinstance(h, dict)
    )

    if not already_exists:
        hooks.append({
            "type": "command",
            "command": RUNDBAT_HOOK_COMMAND,
        })

    settings_path.write_text(json.dumps(data, indent=2) + "\n")

    return {
        "file": str(settings_path),
        "action": "already_present" if already_exists else "merged",
    }


def install_all(project_dir: Path) -> dict:
    """Install all rundbat integration files into the target project."""
    project_dir = Path(project_dir)
    return {
        "mcp_config": install_mcp_config(project_dir),
        "rules": install_rules(project_dir),
        "hooks": install_hooks(project_dir),
    }

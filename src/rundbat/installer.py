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
        "args": ["mcp"],
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
    """Merge UserPromptSubmit hook into .claude/settings.json.

    Uses the matcher + hooks array format:
    {"UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "..."}]}]}
    """
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

    # Check if our hook already exists in any matcher group (idempotent)
    entries = data["hooks"]["UserPromptSubmit"]
    already_exists = False
    for entry in entries:
        if isinstance(entry, dict) and "hooks" in entry:
            for h in entry["hooks"]:
                if h.get("command") == RUNDBAT_HOOK_COMMAND:
                    already_exists = True
                    break

    if not already_exists:
        entries.append({
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": RUNDBAT_HOOK_COMMAND,
                }
            ],
        })

    settings_path.write_text(json.dumps(data, indent=2) + "\n")

    return {
        "file": str(settings_path),
        "action": "already_present" if already_exists else "merged",
    }


RUNDBAT_CLAUDE_MD_START = "<!-- RUNDBAT:START -->"
RUNDBAT_CLAUDE_MD_END = "<!-- RUNDBAT:END -->"

RUNDBAT_CLAUDE_MD = """\
<!-- RUNDBAT:START -->
## rundbat — Deployment Expert

This project uses **rundbat** to manage Docker-based deployment
environments. rundbat is an MCP server that handles database provisioning,
secret management, and environment configuration.

**If you need a database, connection string, deployment environment, or
anything involving Docker containers or dotconfig — use the rundbat MCP
tools.** Do not run Docker or dotconfig commands directly.

Run `rundbat mcp --help` for the full tool reference, or call
`discover_system` to see what is available.

### Quick Reference

| Tool | Purpose |
|---|---|
| `discover_system` | Detect OS, Docker, dotconfig, Node.js |
| `init_project` | Initialize rundbat in a project |
| `create_environment` | Provision a database environment |
| `get_environment_config` | Get connection string (auto-restarts containers) |
| `set_secret` | Store encrypted secrets via dotconfig |
| `start_database` / `stop_database` | Container lifecycle |
| `health_check` | Verify database connectivity |
| `validate_environment` | Full environment validation |
| `check_config_drift` | Detect app name changes |

### Configuration

Configuration is managed by dotconfig. Run `dotconfig agent` for full
documentation on how dotconfig works. Key locations:

- `config/{env}/rundbat.yaml` — Per-environment rundbat config
- `config/{env}/secrets.env` — SOPS-encrypted credentials
- `config/keys/` — SSH keys (encrypted via dotconfig key management)
<!-- RUNDBAT:END -->"""


def install_claude_md(project_dir: Path) -> dict:
    """Insert or replace the RUNDBAT guarded section in CLAUDE.md."""
    claude_md_path = project_dir / "CLAUDE.md"

    if claude_md_path.exists():
        content = claude_md_path.read_text()
    else:
        content = ""

    # Check if guarded section exists
    start_idx = content.find(RUNDBAT_CLAUDE_MD_START)
    end_idx = content.find(RUNDBAT_CLAUDE_MD_END)

    if start_idx != -1 and end_idx != -1:
        # Replace existing section
        end_idx += len(RUNDBAT_CLAUDE_MD_END)
        new_content = content[:start_idx] + RUNDBAT_CLAUDE_MD + content[end_idx:]
        action = "replaced"
    else:
        # Append to end
        if content and not content.endswith("\n"):
            content += "\n"
        if content:
            content += "\n"
        new_content = content + RUNDBAT_CLAUDE_MD + "\n"
        action = "appended"

    claude_md_path.write_text(new_content)
    return {"file": str(claude_md_path), "action": action}


def install_all(project_dir: Path) -> dict:
    """Install all rundbat integration files into the target project."""
    project_dir = Path(project_dir)
    return {
        "mcp_config": install_mcp_config(project_dir),
        "rules": install_rules(project_dir),
        "hooks": install_hooks(project_dir),
        "claude_md": install_claude_md(project_dir),
    }

# CLASI Software Engineering Process

This project uses the CLASI SE process. Your role and workflow are
defined in `.claude/agents/team-lead/agent.md` — read it at session start.

Available skills: run `/se` for a list.

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
<!-- RUNDBAT:END -->

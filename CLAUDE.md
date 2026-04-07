# CLASI Software Engineering Process

This project uses the CLASI SE process. Your role and workflow are
defined in `.claude/agents/team-lead/agent.md` — read it at session start.

Available skills: run `/se` for a list.

<!-- RUNDBAT:START -->
## rundbat — Deployment Expert

This project uses **rundbat** to manage Docker-based deployment
environments. rundbat is a CLI tool that handles database provisioning,
Docker directory generation, secret management, and environment config.

**If you need a database, connection string, deployment environment, or
anything involving Docker containers or dotconfig — use the rundbat CLI.**

Run `rundbat --help` for the full command reference.

### Quick Reference

| Command | Purpose |
|---|---|
| `rundbat discover` | Detect OS, Docker, dotconfig, Node.js |
| `rundbat init` | Initialize rundbat in a project |
| `rundbat create-env <env>` | Provision a database environment |
| `rundbat get-config <env>` | Get connection string (auto-restarts containers) |
| `rundbat set-secret <env> K=V` | Store encrypted secrets via dotconfig |
| `rundbat start <env>` / `stop <env>` | Container lifecycle |
| `rundbat health <env>` | Verify database connectivity |
| `rundbat validate <env>` | Full environment validation |
| `rundbat check-drift` | Detect app name changes |
| `rundbat init-docker` | Generate docker/ directory |
| `rundbat add-service <type>` | Add database service to compose |
| `rundbat install` / `uninstall` | Manage Claude integration files |

All commands support `--json` for machine-parseable output.

### Configuration

Configuration is managed by dotconfig. Read config via:
`dotconfig load -d <env> --json --flat -S`

Key locations:
- `config/rundbat.yaml` — Project-wide config (app name, services, deployments)
- `config/{env}/public.env` — Non-secret environment variables
- `config/{env}/secrets.env` — SOPS-encrypted credentials
<!-- RUNDBAT:END -->

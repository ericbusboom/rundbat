# rundbat — Deployment Expert

When working on tasks that involve databases, deployment, Docker
containers, or environment setup, use **rundbat CLI commands** and
the **deployment-expert agent** instead of running Docker or dotconfig
commands directly.

## When to use the deployment-expert agent

Invoke the deployment-expert agent for complex tasks that require
judgment or multi-step workflows:
- Setting up deployment for a new project
- First-time deploy to a remote host
- Diagnosing container or connectivity issues
- Generating Docker Compose configurations

## When to use rundbat CLI directly

Use CLI commands for single-step operations:
- `rundbat discover` — check system prerequisites
- `rundbat create-env <env>` — provision a database
- `rundbat get-config <env>` — get connection string
- `rundbat start/stop <env>` — container lifecycle
- `rundbat health <env>` — database connectivity check
- `rundbat validate <env>` — full environment validation
- `rundbat set-secret <env> KEY=VAL` — store a secret
- `rundbat check-drift` — detect app name changes

All commands support `--json` for machine-parseable output.

## When to use skills

Use skills for guided workflows:
- `init-docker` — scaffold a docker/ directory
- `dev-database` — quick local dev database
- `diagnose` — troubleshoot deployment issues
- `manage-secrets` — store and manage secrets

## Configuration access

Read config through dotconfig, not by reading files directly:

```bash
# All config merged (most common)
dotconfig load -d <env> --json --flat -S

# Sectioned (to see public vs secret)
dotconfig load -d <env> --json -S

# Project config
dotconfig load -d <env> --file rundbat.yaml -S
```

Write config through dotconfig or rundbat CLI — never edit `config/`
files directly.

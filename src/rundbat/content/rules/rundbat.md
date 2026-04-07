# rundbat — Deployment Expert

When working on tasks that involve databases, deployment, Docker
containers, or environment setup, use **rundbat CLI commands** instead
of running Docker or dotconfig commands directly.

rundbat handles Docker container lifecycle, dotconfig integration, port
allocation, health checks, and stale state recovery automatically.

## Key commands

| Command | Purpose |
|---|---|
| `rundbat discover` | Detect OS, Docker, dotconfig, Node.js |
| `rundbat create-env <env>` | Provision a database environment |
| `rundbat get-config <env>` | Get connection string (auto-restarts containers) |
| `rundbat set-secret <env> KEY=VAL` | Store encrypted secrets via dotconfig |
| `rundbat start <env>` / `rundbat stop <env>` | Container lifecycle |
| `rundbat health <env>` | Verify database connectivity |
| `rundbat validate <env>` | Full environment validation |
| `rundbat check-drift [env]` | Detect app name changes |

## Configuration

All config flows through **dotconfig**. Read config with:
```bash
dotconfig load -d <env> --json --flat -S
```

Key locations:
- `config/rundbat.yaml` — Project-wide rundbat config
- `config/{env}/public.env` — Non-secret env vars
- `config/{env}/secrets.env` — SOPS-encrypted credentials

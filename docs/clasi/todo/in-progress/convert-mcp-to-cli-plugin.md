---
title: Convert rundbat from MCP server to CLI + Claude skills
priority: high
created: 2026-04-06
status: in-progress
sprint: '001'
tickets:
- 001-001
---

# Convert rundbat from MCP Server to CLI + Claude Skills

rundbat currently delivers its capabilities via an MCP server (stdio JSON-RPC).
The MCP transport adds overhead without meaningful benefit — Claude can call
the CLI directly via Bash. Convert to a CLI-first architecture with Claude
integration via native `.claude/` directories (skills, agents, rules).

Simultaneously expand scope: rundbat becomes a **deployment expert** that
produces a `docker/` directory — a self-contained deployment package with
Dockerfile, docker-compose.yml, Justfile, and env config. The `docker/`
directory works standalone; rundbat is the expert that writes and maintains it.

## Key decisions

- Keep Python, drop MCP — no shell script rewrite
- Skip the formal plugin system — use native `.claude/` directories
- `rundbat install` / `rundbat uninstall` — manages Claude integration files
- Development workflow unchanged — `pipx install -e .` still works
- rundbat produces a `docker/` directory as its primary artifact
- Justfile is the human/CI interface (`just up`, `just build`, etc.)
- `dev-database` (quick `docker run`) stays for local dev iteration
- Compose is the standard for any real deployment

## Architecture: what rundbat produces

```
docker/
  Dockerfile              # App image (Node or Python, framework-aware)
  docker-compose.yml      # Full stack: app + databases + services
  .env.example            # Template for required env vars
  Justfile                # Human/CI interface for all operations
```

## Configuration via dotconfig

All deployment configuration flows through **dotconfig**. Skills and the
agent must use dotconfig CLI commands — never read/write `config/` files
directly.

### Reading config: `dotconfig load`

Use `--json` or `--yaml` with `--flat` to get deployment config as a
single dict (all layers merged, secrets decrypted):

```bash
# Flat dict — all public + secret vars for an environment
dotconfig load -d dev --json --flat -S
# → {"APP_NAME": "widgetco", "DB_PORT": "5432", "DATABASE_URL": "postgresql://..."}

# Sectioned — preserves public/secrets separation
dotconfig load -d dev --yaml -S
# → _dotconfig: {deploy: dev}
#   dev: {public: {APP_NAME: widgetco, ...}, secrets: {DATABASE_URL: ...}}
```

Use `--flat` when you just need values (connection strings, ports, etc.).
Use sectioned when you need to know what's public vs. secret (e.g., to
generate `.env.example` with REDACTED secrets).

For non-.env config files (like `rundbat.yaml`):

```bash
dotconfig load -d dev --file rundbat.yaml -S
```

### Writing config: `dotconfig save`

Round-trip: load to `.env.json`, modify, save back:

```bash
dotconfig load -d dev --json          # writes .env.json
# ... modify .env.json ...
dotconfig save --json                 # reads .env.json, writes back to config/
```

For flat files, save matches keys to their existing source files (public
or secrets). New keys are rejected — use sectioned format to add keys to
a specific section:

```bash
dotconfig save --json --flat -d dev   # update existing keys only
```

For individual secrets, the existing `dotconfig save --file` with
`--encrypt` works:

```bash
echo "DATABASE_URL=postgresql://..." > /tmp/secret.env
dotconfig save --file secret.env -d dev --encrypt
```

### What skills should do

1. **Read config first.** Before any docker operation, load the
   environment config: `dotconfig load -d {env} --json --flat -S`.
   Parse the JSON to get `DB_PORT`, `DB_CONTAINER`, `DATABASE_URL`, etc.

2. **Write via dotconfig.** After creating a database or generating
   credentials, save them through dotconfig — never write to
   `config/{env}/secrets.env` directly.

3. **Generate `.env.example` from sectioned output.** Load with
   `--json` (no `--flat`) to see the public/secrets split, then
   produce `.env.example` with secret values replaced by placeholders.

4. **Use `--file` for structured config.** `rundbat.yaml` is loaded
   via `dotconfig load -d dev --file rundbat.yaml -S` so it
   participates in the dotconfig lifecycle (discovery, merge, etc.).

## Agent and skills design

### Agent: `deployment-expert`

Understands project type, needed services, and produces/maintains the
`docker/` directory. Invoked for any deployment, Docker, database, or
environment setup task. Limited context: project config + rundbat CLI.

**Config access pattern:** The agent reads config via
`dotconfig load -d {env} --json --flat -S | jq .` to get a complete
picture of the environment before making decisions.

### Skills

| Skill | Produces/modifies | Trigger |
|---|---|---|
| `init-docker` | `docker/` scaffold, Justfile, compose skeleton | "Set up Docker for this project" |
| `add-postgres` | Postgres service in compose, env vars, `just psql` | "I need a database" |
| `add-mongo` | Mongo service in compose, env vars | "I need MongoDB" |
| `add-redis` | Redis service in compose | "I need a cache" |
| `generate-dockerfile` | `docker/Dockerfile` for detected framework | "Containerize this app" |
| `dev-database` | Quick `docker run` for local dev (no compose) | "Just give me a dev postgres" |
| `diagnose` | Nothing — reads state, runs commands, reports | "My container won't start" |
| `manage-secrets` | dotconfig .env files | "Store this credential" |

Supported apps: Node (Express, Next, etc.), Python (Flask, Django, FastAPI).
Supported databases: Postgres, MongoDB, Redis.
All deployed via Docker / Docker Compose.

### Config access in each skill

**`init-docker`** — reads `rundbat.yaml` for app name, writes initial
env vars to `config/dev/public.env` via dotconfig save.

**`add-postgres` / `add-mongo` / `add-redis`** — loads flat config to
check for port conflicts and existing services, saves new env vars
(DB_PORT, DB_CONTAINER, etc.) to public.env, saves credentials
(DATABASE_URL, passwords) to secrets.env.

**`dev-database`** — loads flat config (`--json --flat`) to get
connection params. After `docker run`, saves the connection string as
a secret.

**`generate-dockerfile`** — reads flat config for PORT, NODE_ENV, etc.
to generate appropriate Dockerfile ENV directives.

**`diagnose`** — loads sectioned config (`--json`, no `--flat`) to
inspect public vs. secret separation. Compares config values against
actual container state (`docker inspect`).

**`manage-secrets`** — thin wrapper around `dotconfig save`. Uses
`dotconfig load --json` for round-trip editing of secrets.

## Work items

### Phase A: Drop MCP, expand CLI
1. Remove MCP server — delete `server.py`, remove `mcp[cli]` dep, remove `cmd_mcp`
2. Add CLI subcommands — `create-env`, `start`, `stop`, `health`, `validate`,
   `discover`, `set-secret`, `check-drift` (with `--json` flag for machine output)
3. Replace `init` with `install`/`uninstall` — install writes Claude integration
   files + manifest; uninstall reads manifest and deletes
4. Update installer.py — new targets (`.claude/skills/`, `.claude/agents/`,
   `.claude/rules/`), manifest tracking, remove `.mcp.json` and hooks writing
5. Update tests — delete `test_server.py`, update `test_installer.py`,
   add CLI tests for new subcommands

### Phase B: Agent and skills content
6. Write `deployment-expert` agent definition
7. Write skill files: `init-docker`, `dev-database`, `diagnose`, `manage-secrets`
8. Write rules file teaching Claude when to invoke the agent / skills vs CLI

### Phase C: Docker directory generation
9. `init-docker` skill + CLI support — scaffold `docker/` with Justfile and
   compose skeleton
10. `generate-dockerfile` — detect framework, produce appropriate Dockerfile
11. `add-postgres` / `add-mongo` / `add-redis` — add services to compose,
    update env vars, add Justfile recipes
12. Integration tests for docker directory generation

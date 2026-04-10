---
status: done
sprint: '006'
tickets:
- 006-001
- 006-002
---

# Plan: Auto-Detect Caddy and Include Labels in Docker Compose

## Context

Caddy labels are already generated in `generate_compose()` ([generators.py:206-215](src/rundbat/generators.py#L206-L215)) when a `hostname` is provided. But labels only appear when hostname exists in `rundbat.yaml` deployments, and `init-docker` often runs before `deploy-init`. In the user's environment, Caddy is always running as the reverse proxy, so compose files should include Caddy labels by default when Caddy is detected.

Rather than prompting for hostname, detect Caddy on the Docker host automatically.

## Changes

### 1. Add `detect_caddy()` to discovery.py

Add a function to [discovery.py](src/rundbat/discovery.py) that checks if a Caddy container is running:

```python
def detect_caddy(context: str | None = None) -> dict:
    """Detect if Caddy reverse proxy is running on the Docker host."""
    cmd = ["docker"]
    if context:
        cmd.extend(["--context", context])
    cmd.extend(["ps", "--filter", "name=caddy", "--format", "{{.Names}}"])
    result = _run_command(cmd)
    running = bool(result["success"] and result["stdout"].strip())
    return {
        "running": running,
        "container": result["stdout"].strip() if running else None,
    }
```

Also add it to `discover_system()` so `rundbat discover` reports it.

### 2. Update `init_docker()` in generators.py to accept `caddy` flag

Add a `caddy: bool = False` parameter to `init_docker()` ([generators.py:572](src/rundbat/generators.py#L572)). When `caddy=True` and `hostname` is provided, Caddy labels are included (this already works). The new part: when `caddy=True` and hostname is **not** provided, use a placeholder like `{app_name}.localhost` or prompt via the skill.

Actually, simpler: just make hostname required-when-caddy-detected. The CLI or skill asks for it only when Caddy is detected and hostname is missing.

### 3. Update `cmd_init_docker()` in cli.py

In [cli.py:247-284](src/rundbat/cli.py#L247-L284):

1. After loading config, call `detect_caddy()` (on the default context, or on deployment context if available)
2. If Caddy is running and no hostname found in config, add `--hostname` to the CLI args so users can provide it
3. Add `--hostname` argument to the `init-docker` subparser

```python
# In cmd_init_docker, after loading config:
from rundbat.discovery import detect_caddy
caddy_info = detect_caddy()
if caddy_info["running"] and not hostname:
    if args.hostname:
        hostname = args.hostname
    else:
        # CLI output: warn that Caddy detected but no hostname set
        print("Caddy detected — pass --hostname to include reverse proxy labels")
```

### 4. Update skill files

**`init-docker.md`**: Add a note after step 1: "If Caddy is detected on your Docker host, pass `--hostname` to include reverse proxy labels: `rundbat init-docker --hostname myapp.example.com`"

**`astro-docker.md`** (in the existing Astro TODO): Add same guidance, noting that Caddy labels will use port 8080 for the Astro nginx container.

### 5. Tests

- `test_detect_caddy_running`: Mock `docker ps` returning a caddy container name → `{"running": True, "container": "caddy"}`
- `test_detect_caddy_not_running`: Mock empty output → `{"running": False, "container": None}`
- `test_detect_caddy_with_context`: Verify `--context` flag is passed when context arg provided

## Files to modify

| File | Action |
|------|--------|
| `src/rundbat/discovery.py` | Add `detect_caddy()`, include in `discover_system()` |
| `src/rundbat/cli.py` | Add `--hostname` to init-docker subparser, detect Caddy and warn |
| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |
| `docs/clasi/todo/plan-astro-static-site-docker-deployment-skill.md` | Amend to mention Caddy detection and hostname |
| `tests/unit/test_discovery.py` | Add Caddy detection tests |

## No changes to generators.py

The compose generator already handles Caddy labels correctly when hostname is provided. The fix is making detection and hostname input happen earlier in the workflow.

## Verification

1. With Caddy running locally: `rundbat init-docker` prints detection message; `rundbat init-docker --hostname app.example.com` generates compose with Caddy labels
2. Without Caddy: `rundbat init-docker` behaves as before (no message, no labels)
3. `uv run pytest` — all new and existing tests pass


---

## Hook Debug Info

```json
{
  "hook_payload": {
    "session_id": "06168813-e061-4c02-9bfa-5482325c19db",
    "transcript_path": "/Users/eric/.claude/projects/-Users-eric-proj-ai-project-rundbat/06168813-e061-4c02-9bfa-5482325c19db.jsonl",
    "cwd": "/Users/eric/proj/ai-project/rundbat",
    "permission_mode": "default",
    "hook_event_name": "PostToolUse",
    "tool_name": "ExitPlanMode",
    "tool_input": {
      "allowedPrompts": [
        {
          "tool": "Bash",
          "prompt": "run tests with uv run pytest"
        }
      ],
      "plan": "# Plan: Auto-Detect Caddy and Include Labels in Docker Compose\n\n## Context\n\nCaddy labels are already generated in `generate_compose()` ([generators.py:206-215](src/rundbat/generators.py#L206-L215)) when a `hostname` is provided. But labels only appear when hostname exists in `rundbat.yaml` deployments, and `init-docker` often runs before `deploy-init`. In the user's environment, Caddy is always running as the reverse proxy, so compose files should include Caddy labels by default when Caddy is detected.\n\nRather than prompting for hostname, detect Caddy on the Docker host automatically.\n\n## Changes\n\n### 1. Add `detect_caddy()` to discovery.py\n\nAdd a function to [discovery.py](src/rundbat/discovery.py) that checks if a Caddy container is running:\n\n```python\ndef detect_caddy(context: str | None = None) -> dict:\n    \"\"\"Detect if Caddy reverse proxy is running on the Docker host.\"\"\"\n    cmd = [\"docker\"]\n    if context:\n        cmd.extend([\"--context\", context])\n    cmd.extend([\"ps\", \"--filter\", \"name=caddy\", \"--format\", \"{{.Names}}\"])\n    result = _run_command(cmd)\n    running = bool(result[\"success\"] and result[\"stdout\"].strip())\n    return {\n        \"running\": running,\n        \"container\": result[\"stdout\"].strip() if running else None,\n    }\n```\n\nAlso add it to `discover_system()` so `rundbat discover` reports it.\n\n### 2. Update `init_docker()` in generators.py to accept `caddy` flag\n\nAdd a `caddy: bool = False` parameter to `init_docker()` ([generators.py:572](src/rundbat/generators.py#L572)). When `caddy=True` and `hostname` is provided, Caddy labels are included (this already works). The new part: when `caddy=True` and hostname is **not** provided, use a placeholder like `{app_name}.localhost` or prompt via the skill.\n\nActually, simpler: just make hostname required-when-caddy-detected. The CLI or skill asks for it only when Caddy is detected and hostname is missing.\n\n### 3. Update `cmd_init_docker()` in cli.py\n\nIn [cli.py:247-284](src/rundbat/cli.py#L247-L284):\n\n1. After loading config, call `detect_caddy()` (on the default context, or on deployment context if available)\n2. If Caddy is running and no hostname found in config, add `--hostname` to the CLI args so users can provide it\n3. Add `--hostname` argument to the `init-docker` subparser\n\n```python\n# In cmd_init_docker, after loading config:\nfrom rundbat.discovery import detect_caddy\ncaddy_info = detect_caddy()\nif caddy_info[\"running\"] and not hostname:\n    if args.hostname:\n        hostname = args.hostname\n    else:\n        # CLI output: warn that Caddy detected but no hostname set\n        print(\"Caddy detected \u2014 pass --hostname to include reverse proxy labels\")\n```\n\n### 4. Update skill files\n\n**`init-docker.md`**: Add a note after step 1: \"If Caddy is detected on your Docker host, pass `--hostname` to include reverse proxy labels: `rundbat init-docker --hostname myapp.example.com`\"\n\n**`astro-docker.md`** (in the existing Astro TODO): Add same guidance, noting that Caddy labels will use port 8080 for the Astro nginx container.\n\n### 5. Tests\n\n- `test_detect_caddy_running`: Mock `docker ps` returning a caddy container name \u2192 `{\"running\": True, \"container\": \"caddy\"}`\n- `test_detect_caddy_not_running`: Mock empty output \u2192 `{\"running\": False, \"container\": None}`\n- `test_detect_caddy_with_context`: Verify `--context` flag is passed when context arg provided\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/discovery.py` | Add `detect_caddy()`, include in `discover_system()` |\n| `src/rundbat/cli.py` | Add `--hostname` to init-docker subparser, detect Caddy and warn |\n| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |\n| `docs/clasi/todo/plan-astro-static-site-docker-deployment-skill.md` | Amend to mention Caddy detection and hostname |\n| `tests/unit/test_discovery.py` | Add Caddy detection tests |\n\n## No changes to generators.py\n\nThe compose generator already handles Caddy labels correctly when hostname is provided. The fix is making detection and hostname input happen earlier in the workflow.\n\n## Verification\n\n1. With Caddy running locally: `rundbat init-docker` prints detection message; `rundbat init-docker --hostname app.example.com` generates compose with Caddy labels\n2. Without Caddy: `rundbat init-docker` behaves as before (no message, no labels)\n3. `uv run pytest` \u2014 all new and existing tests pass\n",
      "planFilePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md"
    },
    "tool_response": {
      "plan": "# Plan: Auto-Detect Caddy and Include Labels in Docker Compose\n\n## Context\n\nCaddy labels are already generated in `generate_compose()` ([generators.py:206-215](src/rundbat/generators.py#L206-L215)) when a `hostname` is provided. But labels only appear when hostname exists in `rundbat.yaml` deployments, and `init-docker` often runs before `deploy-init`. In the user's environment, Caddy is always running as the reverse proxy, so compose files should include Caddy labels by default when Caddy is detected.\n\nRather than prompting for hostname, detect Caddy on the Docker host automatically.\n\n## Changes\n\n### 1. Add `detect_caddy()` to discovery.py\n\nAdd a function to [discovery.py](src/rundbat/discovery.py) that checks if a Caddy container is running:\n\n```python\ndef detect_caddy(context: str | None = None) -> dict:\n    \"\"\"Detect if Caddy reverse proxy is running on the Docker host.\"\"\"\n    cmd = [\"docker\"]\n    if context:\n        cmd.extend([\"--context\", context])\n    cmd.extend([\"ps\", \"--filter\", \"name=caddy\", \"--format\", \"{{.Names}}\"])\n    result = _run_command(cmd)\n    running = bool(result[\"success\"] and result[\"stdout\"].strip())\n    return {\n        \"running\": running,\n        \"container\": result[\"stdout\"].strip() if running else None,\n    }\n```\n\nAlso add it to `discover_system()` so `rundbat discover` reports it.\n\n### 2. Update `init_docker()` in generators.py to accept `caddy` flag\n\nAdd a `caddy: bool = False` parameter to `init_docker()` ([generators.py:572](src/rundbat/generators.py#L572)). When `caddy=True` and `hostname` is provided, Caddy labels are included (this already works). The new part: when `caddy=True` and hostname is **not** provided, use a placeholder like `{app_name}.localhost` or prompt via the skill.\n\nActually, simpler: just make hostname required-when-caddy-detected. The CLI or skill asks for it only when Caddy is detected and hostname is missing.\n\n### 3. Update `cmd_init_docker()` in cli.py\n\nIn [cli.py:247-284](src/rundbat/cli.py#L247-L284):\n\n1. After loading config, call `detect_caddy()` (on the default context, or on deployment context if available)\n2. If Caddy is running and no hostname found in config, add `--hostname` to the CLI args so users can provide it\n3. Add `--hostname` argument to the `init-docker` subparser\n\n```python\n# In cmd_init_docker, after loading config:\nfrom rundbat.discovery import detect_caddy\ncaddy_info = detect_caddy()\nif caddy_info[\"running\"] and not hostname:\n    if args.hostname:\n        hostname = args.hostname\n    else:\n        # CLI output: warn that Caddy detected but no hostname set\n        print(\"Caddy detected \u2014 pass --hostname to include reverse proxy labels\")\n```\n\n### 4. Update skill files\n\n**`init-docker.md`**: Add a note after step 1: \"If Caddy is detected on your Docker host, pass `--hostname` to include reverse proxy labels: `rundbat init-docker --hostname myapp.example.com`\"\n\n**`astro-docker.md`** (in the existing Astro TODO): Add same guidance, noting that Caddy labels will use port 8080 for the Astro nginx container.\n\n### 5. Tests\n\n- `test_detect_caddy_running`: Mock `docker ps` returning a caddy container name \u2192 `{\"running\": True, \"container\": \"caddy\"}`\n- `test_detect_caddy_not_running`: Mock empty output \u2192 `{\"running\": False, \"container\": None}`\n- `test_detect_caddy_with_context`: Verify `--context` flag is passed when context arg provided\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/discovery.py` | Add `detect_caddy()`, include in `discover_system()` |\n| `src/rundbat/cli.py` | Add `--hostname` to init-docker subparser, detect Caddy and warn |\n| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |\n| `docs/clasi/todo/plan-astro-static-site-docker-deployment-skill.md` | Amend to mention Caddy detection and hostname |\n| `tests/unit/test_discovery.py` | Add Caddy detection tests |\n\n## No changes to generators.py\n\nThe compose generator already handles Caddy labels correctly when hostname is provided. The fix is making detection and hostname input happen earlier in the workflow.\n\n## Verification\n\n1. With Caddy running locally: `rundbat init-docker` prints detection message; `rundbat init-docker --hostname app.example.com` generates compose with Caddy labels\n2. Without Caddy: `rundbat init-docker` behaves as before (no message, no labels)\n3. `uv run pytest` \u2014 all new and existing tests pass\n",
      "isAgent": false,
      "filePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md",
      "planWasEdited": true
    },
    "tool_use_id": "toolu_013U9ahNkJN2Mr1jzHBDVFKQ"
  },
  "env": {
    "TOOL_INPUT": "",
    "TOOL_NAME": "",
    "SESSION_ID": "",
    "CLASI_AGENT_TIER": "",
    "CLASI_AGENT_NAME": "",
    "CLAUDE_PROJECT_DIR": "/Users/eric/proj/ai-project/rundbat",
    "PWD": "/Users/eric/proj/ai-project/rundbat",
    "CWD": ""
  },
  "plans_dir": "/Users/eric/.claude/plans",
  "plan_file": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md",
  "cwd": "/Users/eric/proj/ai-project/rundbat"
}
```

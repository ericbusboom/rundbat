---
status: pending
---

# Plan: Remote Docker Host Probe — Reverse Proxy Detection

## Context

rundbat's `init-docker` generates Caddy labels in docker-compose only when a `hostname` is configured. But `init-docker` often runs before `deploy-init`, so there's no hostname and no labels. In the user's environment, remote Docker hosts always run Caddy as a reverse proxy.

The fix: add a `rundbat probe <deployment>` command that inspects a remote Docker host (via its context), detects the reverse proxy, and saves the result into the deployment's section of `rundbat.yaml`. Then `init-docker` can read this and act accordingly.

**Key constraint**: Probing is only needed for remote hosts — local Docker doesn't use a reverse proxy.

## Changes

### 1. Add `detect_caddy()` to `src/rundbat/discovery.py`

```python
def detect_caddy(context: str) -> dict:
    """Detect if Caddy reverse proxy is running on a remote Docker host."""
    cmd = ["docker", "--context", context, "ps",
           "--filter", "name=caddy", "--format", "{{.Names}}"]
    result = _run_command(cmd)
    running = bool(result["success"] and result["stdout"].strip())
    return {
        "running": running,
        "container": result["stdout"].strip() if running else None,
    }
```

Context is required (remote-only). Uses the existing `_run_command()` helper at line 8.

### 2. Add `rundbat probe <name>` CLI command in `src/rundbat/cli.py`

New subcommand that:
1. Loads `rundbat.yaml`, finds the deployment by name
2. Gets the `docker_context` from that deployment
3. Calls `detect_caddy(context)`
4. Saves result into the deployment entry as `reverse_proxy: caddy` (or `reverse_proxy: none`)
5. Writes back to `rundbat.yaml` via `config.save_config()`

Example result in `rundbat.yaml`:
```yaml
deployments:
  prod:
    docker_context: docker1.apps1.jointheleague.org
    host: ssh://root@docker1.apps1.jointheleague.org
    build_strategy: context
    platform: linux/amd64
    reverse_proxy: caddy      # ← new field from probe
    hostname: myapp.example.com
```

### 3. Update `cmd_init_docker()` in `src/rundbat/cli.py` (lines 247-284)

When iterating deployments to find a hostname (lines 269-274), also check for `reverse_proxy: caddy`. If found and no hostname is set, print a warning:

```
Caddy detected on deployment 'prod' — pass --hostname to include reverse proxy labels
```

Add `--hostname` argument to the `init-docker` subparser so users can provide it directly.

### 4. Also probe during `deploy-init`

In `init_deployment()` ([deploy.py:510](src/rundbat/deploy.py#L510)), after detecting the remote platform (line 551), also call `detect_caddy(ctx)` and save the result into the deployment entry. This way the probe happens automatically when setting up a new deployment target.

### 5. Update `src/rundbat/content/skills/init-docker.md`

Add guidance: "If deploying behind Caddy, ensure `hostname` is set — either via `rundbat probe <name>` + `--hostname`, or by setting it in `rundbat.yaml` under the deployment."

### 6. Tests

In `tests/unit/test_discovery.py`:
- `test_detect_caddy_running`: Mock subprocess returning "caddy" → `{"running": True, "container": "caddy"}`
- `test_detect_caddy_not_running`: Mock empty stdout → `{"running": False, "container": None}`
- `test_detect_caddy_passes_context`: Verify the `--context` flag appears in the command

In `tests/unit/test_cli.py`:
- `test_cmd_probe`: Mock detect_caddy + config, verify `reverse_proxy` saved to config

In `tests/unit/test_deploy.py`:
- `test_init_deployment_detects_caddy`: Verify `reverse_proxy` field saved during deploy-init

## Files to modify

| File | Action |
|------|--------|
| `src/rundbat/discovery.py` | Add `detect_caddy(context)` |
| `src/rundbat/cli.py` | Add `probe` subcommand, add `--hostname` to init-docker |
| `src/rundbat/deploy.py` | Call `detect_caddy()` during `init_deployment()` |
| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |
| `tests/unit/test_discovery.py` | Caddy detection tests |
| `tests/unit/test_cli.py` | Probe command test |
| `tests/unit/test_deploy.py` | deploy-init Caddy detection test |

## Verification

1. `rundbat probe prod` → detects Caddy on remote, saves `reverse_proxy: caddy` to `rundbat.yaml`
2. `rundbat deploy-init staging --host ssh://...` → auto-probes, saves reverse_proxy field
3. `rundbat init-docker` → reads probe result, warns if Caddy found but no hostname
4. `rundbat init-docker --hostname app.example.com` → Caddy labels in compose
5. `uv run pytest` — all tests pass


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
      "plan": "# Plan: Remote Docker Host Probe \u2014 Reverse Proxy Detection\n\n## Context\n\nrundbat's `init-docker` generates Caddy labels in docker-compose only when a `hostname` is configured. But `init-docker` often runs before `deploy-init`, so there's no hostname and no labels. In the user's environment, remote Docker hosts always run Caddy as a reverse proxy.\n\nThe fix: add a `rundbat probe <deployment>` command that inspects a remote Docker host (via its context), detects the reverse proxy, and saves the result into the deployment's section of `rundbat.yaml`. Then `init-docker` can read this and act accordingly.\n\n**Key constraint**: Probing is only needed for remote hosts \u2014 local Docker doesn't use a reverse proxy.\n\n## Changes\n\n### 1. Add `detect_caddy()` to `src/rundbat/discovery.py`\n\n```python\ndef detect_caddy(context: str) -> dict:\n    \"\"\"Detect if Caddy reverse proxy is running on a remote Docker host.\"\"\"\n    cmd = [\"docker\", \"--context\", context, \"ps\",\n           \"--filter\", \"name=caddy\", \"--format\", \"{{.Names}}\"]\n    result = _run_command(cmd)\n    running = bool(result[\"success\"] and result[\"stdout\"].strip())\n    return {\n        \"running\": running,\n        \"container\": result[\"stdout\"].strip() if running else None,\n    }\n```\n\nContext is required (remote-only). Uses the existing `_run_command()` helper at line 8.\n\n### 2. Add `rundbat probe <name>` CLI command in `src/rundbat/cli.py`\n\nNew subcommand that:\n1. Loads `rundbat.yaml`, finds the deployment by name\n2. Gets the `docker_context` from that deployment\n3. Calls `detect_caddy(context)`\n4. Saves result into the deployment entry as `reverse_proxy: caddy` (or `reverse_proxy: none`)\n5. Writes back to `rundbat.yaml` via `config.save_config()`\n\nExample result in `rundbat.yaml`:\n```yaml\ndeployments:\n  prod:\n    docker_context: docker1.apps1.jointheleague.org\n    host: ssh://root@docker1.apps1.jointheleague.org\n    build_strategy: context\n    platform: linux/amd64\n    reverse_proxy: caddy      # \u2190 new field from probe\n    hostname: myapp.example.com\n```\n\n### 3. Update `cmd_init_docker()` in `src/rundbat/cli.py` (lines 247-284)\n\nWhen iterating deployments to find a hostname (lines 269-274), also check for `reverse_proxy: caddy`. If found and no hostname is set, print a warning:\n\n```\nCaddy detected on deployment 'prod' \u2014 pass --hostname to include reverse proxy labels\n```\n\nAdd `--hostname` argument to the `init-docker` subparser so users can provide it directly.\n\n### 4. Also probe during `deploy-init`\n\nIn `init_deployment()` ([deploy.py:510](src/rundbat/deploy.py#L510)), after detecting the remote platform (line 551), also call `detect_caddy(ctx)` and save the result into the deployment entry. This way the probe happens automatically when setting up a new deployment target.\n\n### 5. Update `src/rundbat/content/skills/init-docker.md`\n\nAdd guidance: \"If deploying behind Caddy, ensure `hostname` is set \u2014 either via `rundbat probe <name>` + `--hostname`, or by setting it in `rundbat.yaml` under the deployment.\"\n\n### 6. Tests\n\nIn `tests/unit/test_discovery.py`:\n- `test_detect_caddy_running`: Mock subprocess returning \"caddy\" \u2192 `{\"running\": True, \"container\": \"caddy\"}`\n- `test_detect_caddy_not_running`: Mock empty stdout \u2192 `{\"running\": False, \"container\": None}`\n- `test_detect_caddy_passes_context`: Verify the `--context` flag appears in the command\n\nIn `tests/unit/test_cli.py`:\n- `test_cmd_probe`: Mock detect_caddy + config, verify `reverse_proxy` saved to config\n\nIn `tests/unit/test_deploy.py`:\n- `test_init_deployment_detects_caddy`: Verify `reverse_proxy` field saved during deploy-init\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/discovery.py` | Add `detect_caddy(context)` |\n| `src/rundbat/cli.py` | Add `probe` subcommand, add `--hostname` to init-docker |\n| `src/rundbat/deploy.py` | Call `detect_caddy()` during `init_deployment()` |\n| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |\n| `tests/unit/test_discovery.py` | Caddy detection tests |\n| `tests/unit/test_cli.py` | Probe command test |\n| `tests/unit/test_deploy.py` | deploy-init Caddy detection test |\n\n## Verification\n\n1. `rundbat probe prod` \u2192 detects Caddy on remote, saves `reverse_proxy: caddy` to `rundbat.yaml`\n2. `rundbat deploy-init staging --host ssh://...` \u2192 auto-probes, saves reverse_proxy field\n3. `rundbat init-docker` \u2192 reads probe result, warns if Caddy found but no hostname\n4. `rundbat init-docker --hostname app.example.com` \u2192 Caddy labels in compose\n5. `uv run pytest` \u2014 all tests pass\n",
      "planFilePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md"
    },
    "tool_response": {
      "plan": "# Plan: Remote Docker Host Probe \u2014 Reverse Proxy Detection\n\n## Context\n\nrundbat's `init-docker` generates Caddy labels in docker-compose only when a `hostname` is configured. But `init-docker` often runs before `deploy-init`, so there's no hostname and no labels. In the user's environment, remote Docker hosts always run Caddy as a reverse proxy.\n\nThe fix: add a `rundbat probe <deployment>` command that inspects a remote Docker host (via its context), detects the reverse proxy, and saves the result into the deployment's section of `rundbat.yaml`. Then `init-docker` can read this and act accordingly.\n\n**Key constraint**: Probing is only needed for remote hosts \u2014 local Docker doesn't use a reverse proxy.\n\n## Changes\n\n### 1. Add `detect_caddy()` to `src/rundbat/discovery.py`\n\n```python\ndef detect_caddy(context: str) -> dict:\n    \"\"\"Detect if Caddy reverse proxy is running on a remote Docker host.\"\"\"\n    cmd = [\"docker\", \"--context\", context, \"ps\",\n           \"--filter\", \"name=caddy\", \"--format\", \"{{.Names}}\"]\n    result = _run_command(cmd)\n    running = bool(result[\"success\"] and result[\"stdout\"].strip())\n    return {\n        \"running\": running,\n        \"container\": result[\"stdout\"].strip() if running else None,\n    }\n```\n\nContext is required (remote-only). Uses the existing `_run_command()` helper at line 8.\n\n### 2. Add `rundbat probe <name>` CLI command in `src/rundbat/cli.py`\n\nNew subcommand that:\n1. Loads `rundbat.yaml`, finds the deployment by name\n2. Gets the `docker_context` from that deployment\n3. Calls `detect_caddy(context)`\n4. Saves result into the deployment entry as `reverse_proxy: caddy` (or `reverse_proxy: none`)\n5. Writes back to `rundbat.yaml` via `config.save_config()`\n\nExample result in `rundbat.yaml`:\n```yaml\ndeployments:\n  prod:\n    docker_context: docker1.apps1.jointheleague.org\n    host: ssh://root@docker1.apps1.jointheleague.org\n    build_strategy: context\n    platform: linux/amd64\n    reverse_proxy: caddy      # \u2190 new field from probe\n    hostname: myapp.example.com\n```\n\n### 3. Update `cmd_init_docker()` in `src/rundbat/cli.py` (lines 247-284)\n\nWhen iterating deployments to find a hostname (lines 269-274), also check for `reverse_proxy: caddy`. If found and no hostname is set, print a warning:\n\n```\nCaddy detected on deployment 'prod' \u2014 pass --hostname to include reverse proxy labels\n```\n\nAdd `--hostname` argument to the `init-docker` subparser so users can provide it directly.\n\n### 4. Also probe during `deploy-init`\n\nIn `init_deployment()` ([deploy.py:510](src/rundbat/deploy.py#L510)), after detecting the remote platform (line 551), also call `detect_caddy(ctx)` and save the result into the deployment entry. This way the probe happens automatically when setting up a new deployment target.\n\n### 5. Update `src/rundbat/content/skills/init-docker.md`\n\nAdd guidance: \"If deploying behind Caddy, ensure `hostname` is set \u2014 either via `rundbat probe <name>` + `--hostname`, or by setting it in `rundbat.yaml` under the deployment.\"\n\n### 6. Tests\n\nIn `tests/unit/test_discovery.py`:\n- `test_detect_caddy_running`: Mock subprocess returning \"caddy\" \u2192 `{\"running\": True, \"container\": \"caddy\"}`\n- `test_detect_caddy_not_running`: Mock empty stdout \u2192 `{\"running\": False, \"container\": None}`\n- `test_detect_caddy_passes_context`: Verify the `--context` flag appears in the command\n\nIn `tests/unit/test_cli.py`:\n- `test_cmd_probe`: Mock detect_caddy + config, verify `reverse_proxy` saved to config\n\nIn `tests/unit/test_deploy.py`:\n- `test_init_deployment_detects_caddy`: Verify `reverse_proxy` field saved during deploy-init\n\n## Files to modify\n\n| File | Action |\n|------|--------|\n| `src/rundbat/discovery.py` | Add `detect_caddy(context)` |\n| `src/rundbat/cli.py` | Add `probe` subcommand, add `--hostname` to init-docker |\n| `src/rundbat/deploy.py` | Call `detect_caddy()` during `init_deployment()` |\n| `src/rundbat/content/skills/init-docker.md` | Add Caddy/hostname guidance |\n| `tests/unit/test_discovery.py` | Caddy detection tests |\n| `tests/unit/test_cli.py` | Probe command test |\n| `tests/unit/test_deploy.py` | deploy-init Caddy detection test |\n\n## Verification\n\n1. `rundbat probe prod` \u2192 detects Caddy on remote, saves `reverse_proxy: caddy` to `rundbat.yaml`\n2. `rundbat deploy-init staging --host ssh://...` \u2192 auto-probes, saves reverse_proxy field\n3. `rundbat init-docker` \u2192 reads probe result, warns if Caddy found but no hostname\n4. `rundbat init-docker --hostname app.example.com` \u2192 Caddy labels in compose\n5. `uv run pytest` \u2014 all tests pass\n",
      "isAgent": false,
      "filePath": "/Users/eric/.claude/plans/zazzy-strolling-pizza.md",
      "planWasEdited": true
    },
    "tool_use_id": "toolu_01D6LAVDT91vf7GksCueUDNq"
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

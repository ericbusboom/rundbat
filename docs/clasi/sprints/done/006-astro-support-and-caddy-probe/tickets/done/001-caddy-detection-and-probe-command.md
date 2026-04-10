---
id: '001'
title: Caddy detection and probe command
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
todo:
- plan-auto-detect-caddy-and-include-labels-in-docker-compose.md
- plan-remote-docker-host-probe-reverse-proxy-detection.md
---

# Caddy detection and probe command

## Description

Add `detect_caddy(context: str) -> dict` to `discovery.py` and a
`rundbat probe <name>` CLI subcommand to `cli.py`. The probe loads the
named deployment from `rundbat.yaml`, calls `detect_caddy` with its
`docker_context`, and persists `reverse_proxy: caddy` or
`reverse_proxy: none` back to `rundbat.yaml`.

Also auto-call `detect_caddy` inside `init_deployment()` in `deploy.py`
immediately after remote platform detection, saving the same `reverse_proxy`
field to the deployment entry before it is written to config.

This ticket is foundational — tickets 002, 003, and 004 depend on the
`reverse_proxy` field being available in config.

## Acceptance Criteria

- [x] `detect_caddy(context)` exists in `discovery.py` and returns `{running: bool, container: str | None}`.
- [x] `detect_caddy` builds the command `docker --context <context> ps --filter name=caddy --format {{.Names}}` and uses `_run_command()`.
- [x] `rundbat probe <name>` subcommand is registered in `cli.py`.
- [x] `rundbat probe prod` prints the detected reverse proxy and saves `reverse_proxy: caddy` or `reverse_proxy: none` to the `prod` deployment entry in `rundbat.yaml`.
- [x] `rundbat probe prod --json` outputs the result as JSON.
- [x] `rundbat probe <unknown>` exits with a clear error if the deployment name is not found in config.
- [x] `init_deployment()` in `deploy.py` calls `detect_caddy(ctx)` after platform detection and saves `reverse_proxy` to the deployment entry.
- [x] `detect_system()` in `discovery.py` is NOT modified.

## Implementation Plan

### Approach

Add `detect_caddy` as a pure function in `discovery.py` following the same
pattern as `detect_docker`. Add `cmd_probe` handler and register its subparser
in `cli.py`. Add a single `detect_caddy` call in `init_deployment` in
`deploy.py`.

### Files to Create

None.

### Files to Modify

**`src/rundbat/discovery.py`**

After the `detect_existing_config` function (around line 140), add:

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

**`src/rundbat/cli.py`**

1. Add `cmd_probe` function:

```python
def cmd_probe(args):
    """Probe a deployment target for reverse proxy detection."""
    from rundbat import config
    from rundbat.discovery import detect_caddy
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(str(e), args.json)
        return

    deployments = cfg.get("deployments", {})
    name = args.name
    if name not in deployments:
        _error(f"Deployment '{name}' not found in rundbat.yaml", args.json)
        return

    dep = deployments[name]
    ctx = dep.get("docker_context")
    if not ctx:
        _error(f"Deployment '{name}' has no docker_context", args.json)
        return

    caddy = detect_caddy(ctx)
    reverse_proxy = "caddy" if caddy["running"] else "none"
    dep["reverse_proxy"] = reverse_proxy
    deployments[name] = dep
    cfg["deployments"] = deployments
    config.save_config(data=cfg)

    result = {"deployment": name, "reverse_proxy": reverse_proxy,
              "container": caddy.get("container")}
    _output(result, args.json)
```

2. Register subparser in `main()` alongside existing subcommands:

```python
p_probe = sub.add_parser("probe", help="Detect reverse proxy on a deployment target")
p_probe.add_argument("name", help="Deployment name (from rundbat.yaml)")
_add_json_flag(p_probe)
p_probe.set_defaults(func=cmd_probe)
```

**`src/rundbat/deploy.py`**

In `init_deployment()`, after line 551 (remote_platform detection), add:

```python
from rundbat.discovery import detect_caddy
caddy_info = detect_caddy(ctx)
deploy_entry["reverse_proxy"] = "caddy" if caddy_info["running"] else "none"
```

(This line goes before `deployments[name] = deploy_entry`.)

Note: `detect_caddy` makes a network call to the remote host. The existing
`_run_command` 10-second timeout applies. This is acceptable since
`init_deployment` already makes remote SSH calls.

### Testing Plan

See ticket 005 for full test implementations. This ticket's code must support:

- `test_detect_caddy_running` — mock `docker ps` returning "caddy"
- `test_detect_caddy_not_running` — mock empty stdout
- `test_detect_caddy_passes_context` — verify `--context <ctx>` in command
- `test_cmd_probe_saves_caddy` — mock detect_caddy + config, verify field saved
- `test_cmd_probe_unknown_deployment` — verify error output
- `test_init_deployment_detects_caddy` — verify reverse_proxy saved during deploy-init

### Documentation Updates

None in this ticket. Skill file updates are in ticket 004.

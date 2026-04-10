---
id: '002'
title: init-docker hostname flag and Caddy warning
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# init-docker hostname flag and Caddy warning

## Description

Extend the `init-docker` CLI command with a `--hostname` flag so users can
supply the public hostname at generation time. When a deployment in
`rundbat.yaml` has `reverse_proxy: caddy` and no hostname is provided, print
a clear warning. When `--hostname` is provided, pass it through to
`generate_compose()` so Caddy labels are included.

Depends on ticket 001 for the `reverse_proxy` field in config.

## Acceptance Criteria

- [ ] `rundbat init-docker --hostname app.example.com` is a valid command.
- [ ] When `--hostname` is provided, the generated `docker-compose.yml` contains Caddy labels for the correct port.
- [ ] When any deployment has `reverse_proxy: caddy` and no `--hostname` is provided, the CLI prints: `Caddy detected on deployment '<name>' — pass --hostname to include reverse proxy labels`.
- [ ] The warning names the first deployment that has `reverse_proxy: caddy`.
- [ ] When `--hostname` is provided via the flag, it takes precedence over any hostname found in deployment config.
- [ ] When no deployment has `reverse_proxy: caddy` and no `--hostname` is given, behavior is unchanged (no warning, no labels).
- [ ] `--json` flag still works; warning is printed to stdout before JSON output.

## Implementation Plan

### Approach

Two changes to `cli.py`:

1. Add `--hostname` argument to the `init-docker` subparser.
2. In `cmd_init_docker`, after loading deployments, scan for
   `reverse_proxy: caddy`. If found and no hostname is set, print the warning.
   If `args.hostname` is set, use it as `hostname` (overrides config).

### Files to Modify

**`src/rundbat/cli.py`**

In `main()`, after `_add_json_flag(p_init_docker)`, add:

```python
p_init_docker.add_argument(
    "--hostname",
    default=None,
    help="App hostname for Caddy reverse proxy labels (e.g. app.example.com)",
)
```

In `cmd_init_docker`, replace the deployment-scanning block (lines ~269-274)
with:

```python
caddy_deployment = None
for dep_name, dep in (deployments or {}).items():
    if dep.get("hostname") and not hostname:
        hostname = dep["hostname"]
        swarm = dep.get("swarm", False)
    if dep.get("reverse_proxy") == "caddy" and not caddy_deployment:
        caddy_deployment = dep_name

# --hostname flag overrides config
if getattr(args, "hostname", None):
    hostname = args.hostname

# Warn if Caddy detected but no hostname
if caddy_deployment and not hostname:
    print(f"Caddy detected on deployment '{caddy_deployment}' — pass --hostname to include reverse proxy labels")
```

### Testing Plan

See ticket 005 for full test implementations. This ticket's code must support:

- `test_init_docker_hostname_flag` — pass `--hostname app.example.com`, verify compose contains Caddy labels
- `test_init_docker_caddy_warning` — config has `reverse_proxy: caddy`, no hostname, verify warning printed
- `test_init_docker_no_warning_without_caddy` — no reverse_proxy field, verify no warning
- `test_init_docker_hostname_overrides_config` — both config hostname and `--hostname` flag, flag value wins

### Documentation Updates

None in this ticket. Skill file updates are in ticket 004.

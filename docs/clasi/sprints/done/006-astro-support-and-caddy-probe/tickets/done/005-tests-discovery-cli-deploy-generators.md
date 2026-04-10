---
id: '005'
title: "Tests \u2014 discovery, cli, deploy, generators"
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
depends-on:
- '001'
- '002'
- '003'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tests — discovery, cli, deploy, generators

## Description

Write all unit tests for the new behavior introduced in tickets 001-003.
Tests are grouped by module. All use `unittest.mock.patch` for subprocess
calls; no real Docker commands are executed.

## Acceptance Criteria

- [x] `uv run pytest` passes with zero failures and zero errors.
- [x] All test cases listed below are implemented.
- [x] No existing test is broken.

## Implementation Plan

### Files to Modify

**`tests/unit/test_discovery.py`**

```python
def test_detect_caddy_running(monkeypatch):
    """detect_caddy returns running=True when docker ps output is non-empty."""

def test_detect_caddy_not_running(monkeypatch):
    """detect_caddy returns running=False when docker ps output is empty."""

def test_detect_caddy_passes_context(monkeypatch):
    """detect_caddy includes --context <ctx> in the docker command."""
```

Pattern: patch `rundbat.discovery._run_command` to return
`{"success": True, "stdout": "caddy", ...}` or `{"success": True, "stdout": "", ...}`.

**`tests/unit/test_cli.py`**

```python
def test_cmd_probe_saves_caddy(tmp_path, monkeypatch):
    """probe command saves reverse_proxy: caddy when Caddy detected."""

def test_cmd_probe_saves_none(tmp_path, monkeypatch):
    """probe command saves reverse_proxy: none when Caddy not detected."""

def test_cmd_probe_unknown_deployment(tmp_path, monkeypatch, capsys):
    """probe command exits with error when deployment name not in config."""

def test_init_docker_hostname_flag(tmp_path, monkeypatch):
    """init-docker --hostname produces Caddy labels in compose."""

def test_init_docker_caddy_warning(tmp_path, monkeypatch, capsys):
    """init-docker warns when deployment has reverse_proxy: caddy but no hostname."""

def test_init_docker_no_warning_without_caddy(tmp_path, monkeypatch, capsys):
    """init-docker does not warn when no deployment has reverse_proxy: caddy."""

def test_init_docker_hostname_overrides_config(tmp_path, monkeypatch):
    """--hostname flag value takes precedence over hostname in deployment config."""
```

**`tests/unit/test_deploy.py`**

```python
def test_init_deployment_detects_caddy(monkeypatch):
    """init_deployment saves reverse_proxy: caddy when Caddy is found."""

def test_init_deployment_detects_none(monkeypatch):
    """init_deployment saves reverse_proxy: none when no Caddy."""
```

**`tests/unit/test_generators.py`**

```python
def test_detect_framework_astro(tmp_path):
    """detect_framework returns astro framework for package.json with astro dep."""

def test_detect_framework_astro_before_generic_node(tmp_path):
    """Astro is detected even when other node packages are present."""

def test_generate_dockerfile_astro():
    """Astro Dockerfile has 3 stages ending in nginx:alpine on port 8080."""

def test_generate_nginx_conf():
    """generate_nginx_conf returns config with listen 8080 and try_files."""

def test_generate_compose_astro_port():
    """generate_compose uses port 8080 for Astro framework."""

def test_generate_env_example_astro_port_no_node_env():
    """generate_env_example uses port 8080 and omits NODE_ENV for Astro."""

def test_init_docker_astro_writes_nginx_conf(tmp_path):
    """init_docker creates docker/nginx.conf for Astro projects."""
```

For `test_init_docker_astro_writes_nginx_conf`, set up `tmp_path` with a
mock `package.json` (astro dep) and `config/rundbat.yaml`, call
`init_docker(tmp_path, ...)`, then assert `(tmp_path / "docker" / "nginx.conf").exists()`.

### Testing Plan

- Existing tests to run: `tests/unit/test_generators.py`, `tests/unit/test_cli.py`, `tests/unit/test_discovery.py`, `tests/unit/test_deploy.py`
- Verification command: `uv run pytest`

### Documentation Updates

None.

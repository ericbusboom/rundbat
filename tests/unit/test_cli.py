"""Tests for the CLI entry point."""

import json
import subprocess
import sys
import types
from unittest.mock import patch, MagicMock


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Helper: run rundbat CLI as subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "rundbat.cli"] + args,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Basic CLI tests
# ---------------------------------------------------------------------------

def test_version():
    """rundbat --version prints version."""
    result = _run(["--version"])
    assert result.returncode == 0
    assert "rundbat" in result.stdout


def test_no_args_shows_help():
    """rundbat with no args shows help and exits 0."""
    result = _run([])
    assert result.returncode == 0
    assert "init" in result.stdout
    assert "deploy" in result.stdout
    assert "init-docker" in result.stdout


def test_expected_commands():
    """rundbat should have the expected subcommands."""
    result = _run(["--help"])
    assert result.returncode == 0
    # These should be present
    assert "init" in result.stdout
    assert "generate" in result.stdout
    assert "build" in result.stdout
    assert "up" in result.stdout
    assert "down" in result.stdout
    assert "restart" in result.stdout
    assert "logs" in result.stdout
    assert "deploy" in result.stdout
    assert "deploy-init" in result.stdout
    assert "init-docker" in result.stdout
    assert "probe" in result.stdout
    # These should be gone (removed in sprint 005)
    assert "discover" not in result.stdout
    assert "create-env" not in result.stdout
    assert "health" not in result.stdout
    assert "validate" not in result.stdout
    assert "set-secret" not in result.stdout
    assert "check-drift" not in result.stdout
    assert "add-service" not in result.stdout
    assert "uninstall" not in result.stdout


# ---------------------------------------------------------------------------
# Subcommand --help tests
# ---------------------------------------------------------------------------

class TestSubcommandHelp:
    """Every subcommand should respond to --help with exit code 0."""

    def test_init_help(self):
        result = _run(["init", "--help"])
        assert result.returncode == 0
        assert "--app-name" in result.stdout
        assert "--force" in result.stdout

    def test_generate_help(self):
        result = _run(["generate", "--help"])
        assert result.returncode == 0
        assert "--deployment" in result.stdout
        assert "--json" in result.stdout

    def test_init_docker_help(self):
        result = _run(["init-docker", "--help"])
        assert result.returncode == 0
        assert "--json" in result.stdout

    def test_build_help(self):
        result = _run(["build", "--help"])
        assert result.returncode == 0
        assert "name" in result.stdout

    def test_up_help(self):
        result = _run(["up", "--help"])
        assert result.returncode == 0
        assert "--workflow" in result.stdout

    def test_down_help(self):
        result = _run(["down", "--help"])
        assert result.returncode == 0

    def test_logs_help(self):
        result = _run(["logs", "--help"])
        assert result.returncode == 0

    def test_restart_help(self):
        result = _run(["restart", "--help"])
        assert result.returncode == 0
        assert "--build" in result.stdout

    def test_deploy_help(self):
        result = _run(["deploy", "--help"])
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--no-build" in result.stdout
        assert "--json" in result.stdout

    def test_deploy_init_help(self):
        result = _run(["deploy-init", "--help"])
        assert result.returncode == 0
        assert "--host" in result.stdout
        assert "--compose-file" in result.stdout
        assert "--hostname" in result.stdout
        assert "--deploy-mode" in result.stdout
        assert "--image" in result.stdout


# ---------------------------------------------------------------------------
# cmd_probe unit tests
# ---------------------------------------------------------------------------

def _make_probe_args(name="prod", as_json=False):
    """Build a minimal args namespace for cmd_probe."""
    args = types.SimpleNamespace()
    args.name = name
    args.json = as_json
    return args


_SWARM_INACTIVE = {"swarm": False, "swarm_role": "", "reachable": True}
_SWARM_MANAGER = {"swarm": True, "swarm_role": "manager", "reachable": True}
_SWARM_WORKER = {"swarm": True, "swarm_role": "worker", "reachable": True}
_SWARM_UNREACHABLE = {"swarm": False, "swarm_role": "", "reachable": False}


def _patch_probe_helpers(monkeypatch, *, caddy=None, swarm=None):
    """Install detect_caddy / detect_swarm fakes used by cmd_probe."""
    caddy = caddy if caddy is not None else {"running": False, "container": None}
    swarm = swarm if swarm is not None else dict(_SWARM_INACTIVE)
    monkeypatch.setattr("rundbat.discovery.detect_caddy", lambda ctx: caddy)
    monkeypatch.setattr("rundbat.discovery.detect_swarm", lambda ctx: swarm)


def test_cmd_probe_saves_caddy(monkeypatch, capsys):
    """probe command saves reverse_proxy: caddy when Caddy detected."""
    saved_data = {}

    fake_cfg = {
        "deployments": {
            "prod": {"docker_context": "myapp-prod"},
        },
    }

    def fake_load_config():
        return dict(fake_cfg)

    def fake_save_config(data):
        saved_data.update(data)

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr("rundbat.config.save_config", fake_save_config)
    _patch_probe_helpers(monkeypatch, caddy={"running": True, "container": "caddy"})

    from rundbat.cli import cmd_probe
    cmd_probe(_make_probe_args(name="prod"))

    assert saved_data["deployments"]["prod"]["reverse_proxy"] == "caddy"


def test_cmd_probe_saves_none_when_no_caddy(monkeypatch, capsys):
    """probe command saves reverse_proxy: none when Caddy not detected."""
    saved_data = {}

    def fake_load_config():
        return {
            "deployments": {
                "prod": {"docker_context": "myapp-prod"},
            },
        }

    def fake_save_config(data):
        saved_data.update(data)

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr("rundbat.config.save_config", fake_save_config)
    _patch_probe_helpers(monkeypatch)

    from rundbat.cli import cmd_probe
    cmd_probe(_make_probe_args(name="prod"))

    assert saved_data["deployments"]["prod"]["reverse_proxy"] == "none"


def test_cmd_probe_unknown_deployment(monkeypatch, capsys):
    """probe command exits with error when deployment name not in config."""
    def fake_load_config():
        return {"deployments": {"staging": {"docker_context": "myapp-staging"}}}

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)

    from rundbat.cli import cmd_probe
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        cmd_probe(_make_probe_args(name="prod"))
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "prod" in captured.err


def _run_probe_with_fakes(monkeypatch, deployment, *, caddy=None, swarm=None):
    """Run cmd_probe against a single 'prod' deployment dict; return saved state."""
    saved = {}

    def fake_load_config():
        # Return a deep-copy-ish view so cmd_probe's mutations only
        # touch the test's local copy.
        return {"deployments": {"prod": dict(deployment)}}

    def fake_save_config(data):
        saved.update(data)

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr("rundbat.config.save_config", fake_save_config)
    _patch_probe_helpers(monkeypatch, caddy=caddy, swarm=swarm)
    from rundbat.cli import cmd_probe
    cmd_probe(_make_probe_args(name="prod"))
    return saved["deployments"]["prod"]


def test_probe_writes_swarm_true_manager(monkeypatch):
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx"},
        swarm=dict(_SWARM_MANAGER),
    )
    assert dep["swarm"] is True
    assert dep["swarm_role"] == "manager"


def test_probe_writes_swarm_false_when_inactive(monkeypatch):
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx"},
        swarm=dict(_SWARM_INACTIVE),
    )
    assert dep["swarm"] is False
    assert "swarm_role" not in dep


def test_probe_transient_failure_preserves_true(monkeypatch):
    """Unreachable probe MUST NOT overwrite prior swarm: true."""
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx", "swarm": True, "swarm_role": "manager"},
        swarm=dict(_SWARM_UNREACHABLE),
    )
    assert dep["swarm"] is True
    assert dep["swarm_role"] == "manager"


def test_probe_unreachable_from_absent_writes_unknown(monkeypatch):
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx"},
        swarm=dict(_SWARM_UNREACHABLE),
    )
    assert dep["swarm"] == "unknown"
    assert "swarm_role" not in dep


def test_probe_reachable_downgrades_explicit_true_to_false(monkeypatch):
    """A reachable daemon reporting inactive swarm authoritatively downgrades."""
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx", "swarm": True, "swarm_role": "manager"},
        swarm=dict(_SWARM_INACTIVE),
    )
    assert dep["swarm"] is False
    assert "swarm_role" not in dep


def test_probe_still_records_caddy(monkeypatch):
    """Regression: swarm plumbing didn't break the caddy probe."""
    dep = _run_probe_with_fakes(
        monkeypatch,
        {"docker_context": "ctx"},
        caddy={"running": True, "container": "caddy"},
        swarm=dict(_SWARM_MANAGER),
    )
    assert dep["reverse_proxy"] == "caddy"
    assert dep["swarm"] is True


# ---------------------------------------------------------------------------
# cmd_deploy_init Swarm prompt (T06)
# ---------------------------------------------------------------------------

def _make_deploy_init_args(**overrides):
    args = types.SimpleNamespace()
    args.name = "prod"
    args.host = "ssh://root@prod.example.com"
    args.compose_file = None
    args.hostname = None
    args.strategy = None
    args.ssh_key = None
    args.deploy_mode = None
    args.image = None
    args.json = False
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _patch_deploy_init_common(monkeypatch, swarm_probe):
    """Install fakes for cmd_deploy_init swarm tests.

    Returns ``saved_cfg`` dict, populated if cmd_deploy_init writes a
    swarm entry back via config.save_config.
    """
    saved_cfg: dict = {}

    def fake_init_deployment(name, host, **kwargs):
        return {
            "status": "ok",
            "deployment": name,
            "context": "prod-ctx",
            "host": host,
            "platform": None,
            "build_strategy": "context",
            "ssh_key": None,
            "deploy_mode": kwargs.get("deploy_mode"),
        }

    monkeypatch.setattr("rundbat.deploy.init_deployment", fake_init_deployment)
    monkeypatch.setattr("rundbat.discovery.detect_swarm",
                        lambda ctx: swarm_probe)
    # Config stubs — the probe-accept path reads and writes config.
    fake_cfg = {
        "deployments": {
            "prod": {
                "docker_context": "prod-ctx",
                "host": "ssh://root@prod.example.com",
            }
        }
    }
    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {k: v for k, v in fake_cfg.items()})
    monkeypatch.setattr("rundbat.config.save_config",
                        lambda data: saved_cfg.update(data))
    return saved_cfg


def test_deploy_init_swarm_detected_accepts_and_writes_fields(monkeypatch):
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": True, "swarm_role": "manager", "reachable": True},
    )
    # Two prompts: "accept swarm?" (yes) and "image tag?" (blank →
    # accept default <app_name>:<deployment>).
    inputs = iter(["y", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    entry = saved["deployments"]["prod"]
    assert entry["swarm"] is True
    assert entry["deploy_mode"] == "stack"
    assert entry["swarm_role"] == "manager"
    # Sprint 009: image prompt fires and default <app>:<deployment>
    # is saved. app_name defaults to "app" since the fake cfg has
    # no app_name key.
    assert entry["image"] == "app:prod"


def test_deploy_init_swarm_decline_writes_no_swarm_fields(monkeypatch):
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": True, "swarm_role": "manager", "reachable": True},
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    # save_config should NOT have been called with swarm fields.
    assert saved == {}


def test_deploy_init_swarm_not_detected_no_prompt(monkeypatch):
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": False, "swarm_role": "", "reachable": True},
    )

    def forbidden_input(prompt=""):
        raise AssertionError("input() should not be called when swarm is absent")

    monkeypatch.setattr("builtins.input", forbidden_input)

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    assert saved == {}


def test_deploy_init_swarm_json_mode_auto_fills_image(monkeypatch):
    """Sprint 009: --json mode skips prompts and defaults the image tag."""
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": True, "swarm_role": "manager", "reachable": True},
    )

    def forbidden_input(prompt=""):
        raise AssertionError("input() should not be called in --json mode")

    monkeypatch.setattr("builtins.input", forbidden_input)

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args(json=True))

    entry = saved["deployments"]["prod"]
    assert entry["swarm"] is True
    assert entry["deploy_mode"] == "stack"
    # app_name defaults to "app" since fake cfg has no app_name.
    assert entry["image"] == "app:prod"


def test_deploy_init_swarm_custom_image_saved(monkeypatch):
    """Sprint 009: user-supplied image tag is saved verbatim."""
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": True, "swarm_role": "manager", "reachable": True},
    )
    inputs = iter(["y", "myapp:v1.2.3"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    assert saved["deployments"]["prod"]["image"] == "myapp:v1.2.3"


def test_deploy_init_swarm_github_actions_no_image_prompt(monkeypatch):
    """Sprint 009: GA strategy is exempt from the image prompt."""
    saved_cfg: dict = {}

    def fake_init_deployment(name, host, **kwargs):
        # GA strategy path — init_deployment already set image.
        return {
            "status": "ok",
            "deployment": name,
            "context": "prod-ctx",
            "host": host,
            "platform": None,
            "build_strategy": "github-actions",
            "ssh_key": None,
            "deploy_mode": kwargs.get("deploy_mode"),
        }

    monkeypatch.setattr("rundbat.deploy.init_deployment",
                        fake_init_deployment)
    monkeypatch.setattr(
        "rundbat.discovery.detect_swarm",
        lambda ctx: {"swarm": True, "swarm_role": "manager",
                     "reachable": True},
    )
    fake_cfg = {
        "deployments": {
            "prod": {
                "docker_context": "prod-ctx",
                "build_strategy": "github-actions",
                "image": "ghcr.io/owner/myapp",
            }
        }
    }
    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {k: v for k, v in fake_cfg.items()})
    monkeypatch.setattr("rundbat.config.save_config",
                        lambda data: saved_cfg.update(data))
    # Only the swarm yes/no prompt should fire — not the image prompt.
    inputs = iter(["y"])

    def fake_input(prompt=""):
        try:
            return next(inputs)
        except StopIteration as e:
            raise AssertionError(
                "image prompt should not fire for GA strategy"
            ) from e

    monkeypatch.setattr("builtins.input", fake_input)

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    entry = saved_cfg["deployments"]["prod"]
    assert entry["image"] == "ghcr.io/owner/myapp"


def test_deploy_init_swarm_unreachable_warns_and_proceeds(monkeypatch, capsys):
    saved = _patch_deploy_init_common(
        monkeypatch,
        {"swarm": False, "swarm_role": "", "reachable": False},
    )

    def forbidden_input(prompt=""):
        raise AssertionError("input() should not be called when probe is unreachable")

    monkeypatch.setattr("builtins.input", forbidden_input)

    from rundbat.cli import cmd_deploy_init
    cmd_deploy_init(_make_deploy_init_args())

    captured = capsys.readouterr()
    assert "could not probe" in captured.err.lower() or "Warning" in captured.err
    assert saved == {}


# ---------------------------------------------------------------------------
# CLI stack lifecycle (T05)
# ---------------------------------------------------------------------------

def _lifecycle_args(name="prod", as_json=False, **extra):
    args = types.SimpleNamespace()
    args.name = name
    args.json = as_json
    for k, v in extra.items():
        setattr(args, k, v)
    return args


def _install_lifecycle_fakes(monkeypatch, cfg, *, compose_exists=True,
                             run_returncode=0):
    """Patch config, filesystem and _run_cmd for lifecycle tests. Returns
    the list of captured (cmd, env) tuples."""
    monkeypatch.setattr("rundbat.config.load_config", lambda: cfg)
    # Checkout is a no-op here (env_source != dotconfig).
    monkeypatch.setattr("rundbat.cli._checkout_config",
                        lambda name, dep_cfg, verbose=False: None)
    # Compose file existence — stub Path.exists. We take a light
    # touch and monkey-patch _compose_file_for_deployment to return a
    # Path-like with the desired exists() behavior.
    class _FakePath:
        def __init__(self, p): self._p = p
        def exists(self): return compose_exists
        def __str__(self): return self._p
        def __fspath__(self): return self._p

    def fake_compose_file(name, dep_cfg):
        return _FakePath(dep_cfg.get("compose_file",
                                     f"docker/docker-compose.{name}.yml"))

    monkeypatch.setattr("rundbat.cli._compose_file_for_deployment",
                        fake_compose_file)

    captured = []

    def fake_run_cmd(cmd, env=None, verbose=False, **kwargs):
        captured.append({"cmd": list(cmd), "env": dict(env) if env else None})

        class _R:
            returncode = run_returncode
            stdout = ""
            stderr = ""
        return _R()

    monkeypatch.setattr("rundbat.cli._run_cmd", fake_run_cmd)
    return captured


_CFG_STACK = {
    "app_name": "myapp",
    "deployments": {
        "prod": {
            "docker_context": "prod-ctx",
            "deploy_mode": "stack",
        }
    },
}


def test_cmd_up_stack_mode_runs_stack_deploy(monkeypatch):
    captured = _install_lifecycle_fakes(monkeypatch, _CFG_STACK)
    from rundbat.cli import cmd_up
    cmd_up(_lifecycle_args(workflow=False))
    assert captured[-1]["cmd"][:2] == ["docker", "--context"]
    assert "stack" in captured[-1]["cmd"]
    assert "deploy" in captured[-1]["cmd"]
    assert "myapp_prod" in captured[-1]["cmd"]  # default stack name


def test_cmd_down_stack_mode_runs_stack_rm(monkeypatch):
    captured = _install_lifecycle_fakes(monkeypatch, _CFG_STACK)
    from rundbat.cli import cmd_down
    cmd_down(_lifecycle_args())
    assert captured[-1]["cmd"] == [
        "docker", "--context", "prod-ctx", "stack", "rm", "myapp_prod"
    ]


def test_cmd_logs_stack_mode_runs_service_logs(monkeypatch):
    captured = _install_lifecycle_fakes(monkeypatch, _CFG_STACK)
    from rundbat.cli import cmd_logs
    cmd_logs(_lifecycle_args())
    # First service is app.
    assert captured[0]["cmd"] == [
        "docker", "--context", "prod-ctx", "service", "logs", "-f",
        "myapp_prod_app",
    ]


def test_cmd_restart_stack_mode_calls_rm_then_deploy(monkeypatch):
    captured = _install_lifecycle_fakes(monkeypatch, _CFG_STACK)
    from rundbat.cli import cmd_restart
    cmd_restart(_lifecycle_args(build=False))
    cmds = [c["cmd"] for c in captured]
    # stack rm first, stack deploy second
    assert any("rm" in c and "myapp_prod" in c for c in cmds)
    assert any("deploy" in c and "myapp_prod" in c for c in cmds)
    rm_idx = next(i for i, c in enumerate(cmds) if "rm" in c)
    deploy_idx = next(i for i, c in enumerate(cmds) if "deploy" in c)
    assert rm_idx < deploy_idx


def test_stack_name_defaults_to_app_underscore_deployment(monkeypatch):
    captured = _install_lifecycle_fakes(monkeypatch, _CFG_STACK)
    from rundbat.cli import cmd_up
    cmd_up(_lifecycle_args(workflow=False))
    assert "myapp_prod" in captured[-1]["cmd"]


def test_stack_name_override_via_stack_name_field(monkeypatch):
    cfg = {
        "app_name": "myapp",
        "deployments": {
            "prod": {
                "docker_context": "ctx",
                "deploy_mode": "stack",
                "stack_name": "custom",
            }
        },
    }
    captured = _install_lifecycle_fakes(monkeypatch, cfg)
    from rundbat.cli import cmd_up
    cmd_up(_lifecycle_args(workflow=False))
    assert "custom" in captured[-1]["cmd"]
    assert "myapp_prod" not in captured[-1]["cmd"]


def test_auto_upgrade_to_stack_when_swarm_true(monkeypatch):
    """swarm: true + no explicit deploy_mode should auto-upgrade to stack."""
    cfg = {
        "app_name": "myapp",
        "deployments": {
            "prod": {
                "docker_context": "ctx",
                "swarm": True,
                # NO deploy_mode field
            }
        },
    }
    captured = _install_lifecycle_fakes(monkeypatch, cfg)
    from rundbat.cli import cmd_up
    cmd_up(_lifecycle_args(workflow=False))
    assert "stack" in captured[-1]["cmd"]
    assert "deploy" in captured[-1]["cmd"]


def test_compose_mode_unchanged_regression(monkeypatch):
    cfg = {
        "app_name": "myapp",
        "deployments": {"prod": {"docker_context": "ctx"}},
    }
    captured = _install_lifecycle_fakes(monkeypatch, cfg)
    from rundbat.cli import cmd_up
    cmd_up(_lifecycle_args(workflow=False))
    # Should still use docker compose, NOT stack.
    assert "compose" in captured[-1]["cmd"]
    assert "stack" not in captured[-1]["cmd"]


def test_effective_deploy_mode_helper():
    from rundbat.cli import _effective_deploy_mode
    assert _effective_deploy_mode({}) == "compose"
    assert _effective_deploy_mode({"deploy_mode": "run"}) == "run"
    assert _effective_deploy_mode({"deploy_mode": "compose", "swarm": True}) == "compose"
    assert _effective_deploy_mode({"swarm": True}) == "stack"
    assert _effective_deploy_mode({"swarm": False}) == "compose"


# ---------------------------------------------------------------------------
# cmd_secret_create (T07)
# ---------------------------------------------------------------------------

def _make_secret_args(env="prod", key="POSTGRES_PASSWORD", as_json=False,
                      from_file=None, target_name=None):
    args = types.SimpleNamespace()
    args.env = env
    args.key = key
    args.json = as_json
    args.from_file = from_file
    args.target_name = target_name
    return args


class _FakeRunResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_secret_create_pipes_value_into_docker_stdin(monkeypatch):
    captured = {}

    def fake_load_config():
        return {
            "app_name": "myapp",
            "deployments": {"prod": {"docker_context": "prod-ctx"}},
        }

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)
    monkeypatch.setattr(
        "rundbat.config.load_env_dict",
        lambda env: {"POSTGRES_PASSWORD": "s3cret", "OTHER": "x"},
    )

    def fake_run(cmd, *, input, capture_output, text):
        captured["cmd"] = cmd
        captured["stdin"] = input
        captured["capture"] = capture_output
        captured["text"] = text
        return _FakeRunResult(0, "sha256:abc", "")

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    cmd_secret_create(_make_secret_args())

    assert captured["cmd"][:4] == ["docker", "--context", "prod-ctx", "secret"]
    assert captured["cmd"][4:6] == ["create"] + [captured["cmd"][5]]
    assert captured["cmd"][-1] == "-"
    assert captured["stdin"] == "s3cret"
    assert captured["capture"] is True
    assert captured["text"] is True


def test_secret_create_uses_versioned_name(monkeypatch):
    from datetime import datetime, timezone

    fake_now = datetime(2026, 4, 24, tzinfo=timezone.utc)

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fake_now

    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {"app_name": "myapp",
                                 "deployments": {"prod": {"docker_context": "ctx"}}})
    monkeypatch.setattr("rundbat.config.load_env_dict",
                        lambda env: {"POSTGRES_PASSWORD": "v"})

    captured = {}

    def fake_run(cmd, *, input, capture_output, text):
        captured["cmd"] = cmd
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)
    import rundbat.cli as cli
    monkeypatch.setattr(cli, "datetime", FakeDatetime, raising=False)

    # Re-import inside the function — we must patch at the import site.
    # cmd_secret_create does `from datetime import datetime, timezone`
    # at call time, so patch the datetime module attr.
    import datetime as real_datetime
    monkeypatch.setattr(real_datetime, "datetime", FakeDatetime)

    from rundbat.cli import cmd_secret_create
    cmd_secret_create(_make_secret_args())

    # Expected name: myapp_postgres_password_v20260424
    name = captured["cmd"][-2]  # last arg before stdin marker '-'
    assert name == "myapp_postgres_password_v20260424"


def test_secret_create_missing_key_errors_before_docker(monkeypatch):
    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {"app_name": "myapp",
                                 "deployments": {"prod": {"docker_context": "ctx"}}})
    monkeypatch.setattr("rundbat.config.load_env_dict",
                        lambda env: {"OTHER": "x"})

    docker_called = []

    def fake_run(cmd, *, input, capture_output, text):
        docker_called.append(cmd)
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    import pytest
    with pytest.raises(SystemExit) as exc:
        cmd_secret_create(_make_secret_args(key="POSTGRES_PASSWORD"))
    assert exc.value.code == 1
    assert docker_called == []  # no docker call attempted


def test_secret_create_from_file_pipes_decrypted_content(monkeypatch):
    """--from-file pipes the decrypted file content into docker stdin."""
    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {"app_name": "myapp",
                 "deployments": {"prod": {"docker_context": "ctx"}}},
    )
    file_content = "-----BEGIN PRIVATE KEY-----\nABC123\n-----END PRIVATE KEY-----\n"

    captured_load: dict = {}

    def fake_load_env_file(env, filename):
        captured_load["env"] = env
        captured_load["filename"] = filename
        return file_content

    monkeypatch.setattr("rundbat.config.load_env_file", fake_load_env_file)

    captured: dict = {}

    def fake_run(cmd, *, input, capture_output, text):
        captured["cmd"] = cmd
        captured["stdin"] = input
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    args = _make_secret_args(
        key=None, from_file="stu1884.pem", target_name="meetup_private_key",
    )
    cmd_secret_create(args)

    assert captured_load == {"env": "prod", "filename": "stu1884.pem"}
    assert captured["stdin"] == file_content
    # Secret name uses the explicit target-name, not the file stem.
    name = captured["cmd"][-2]
    assert name.startswith("myapp_meetup_private_key_v")


def test_secret_create_from_file_target_name_defaults_to_stem(monkeypatch):
    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {"app_name": "myapp",
                 "deployments": {"prod": {"docker_context": "ctx"}}},
    )
    monkeypatch.setattr(
        "rundbat.config.load_env_file",
        lambda env, filename: "data",
    )
    captured: dict = {}

    def fake_run(cmd, *, input, capture_output, text):
        captured["cmd"] = cmd
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    cmd_secret_create(
        _make_secret_args(key=None, from_file="stu1884.pem")
    )
    name = captured["cmd"][-2]
    # File stem 'stu1884' becomes the target.
    assert "_stu1884_v" in name


def test_secret_create_rejects_both_key_and_from_file(monkeypatch, capsys):
    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {"app_name": "myapp",
                 "deployments": {"prod": {"docker_context": "ctx"}}},
    )

    docker_called: list = []

    def fake_run(cmd, *, input, capture_output, text):
        docker_called.append(cmd)
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    import pytest
    with pytest.raises(SystemExit):
        cmd_secret_create(_make_secret_args(
            key="POSTGRES_PASSWORD", from_file="x.pem",
        ))
    err = capsys.readouterr().err
    assert "either" in err.lower() or "not both" in err.lower()
    assert docker_called == []


def test_secret_create_rejects_no_source(monkeypatch, capsys):
    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {"app_name": "myapp",
                 "deployments": {"prod": {"docker_context": "ctx"}}},
    )

    monkeypatch.setattr("subprocess.run",
                        lambda *a, **kw: _FakeRunResult(0))

    from rundbat.cli import cmd_secret_create
    import pytest
    with pytest.raises(SystemExit):
        cmd_secret_create(_make_secret_args(key=None))
    err = capsys.readouterr().err
    assert "KEY" in err or "from-file" in err


def test_secret_create_uses_manager_context_when_set(monkeypatch):
    """When manager: is set on the deployment, secret create routes there."""
    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {
            "app_name": "myapp",
            "deployments": {"prod": {
                "docker_context": "swarm-worker",
                "manager": "swarm-mgr",
            }},
        },
    )
    monkeypatch.setattr("rundbat.config.load_env_dict",
                        lambda env: {"K": "v"})
    captured: dict = {}

    def fake_run(cmd, *, input, capture_output, text):
        captured["cmd"] = cmd
        return _FakeRunResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    cmd_secret_create(_make_secret_args(key="K"))
    # docker --context <manager> ...
    assert captured["cmd"][:3] == ["docker", "--context", "swarm-mgr"]


def test_secret_create_docker_failure_surfaced(monkeypatch, capsys):
    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {"app_name": "myapp",
                                 "deployments": {"prod": {"docker_context": "ctx"}}})
    monkeypatch.setattr("rundbat.config.load_env_dict",
                        lambda env: {"POSTGRES_PASSWORD": "x"})

    def fake_run(cmd, *, input, capture_output, text):
        return _FakeRunResult(1, "", "connection refused")

    monkeypatch.setattr("subprocess.run", fake_run)

    from rundbat.cli import cmd_secret_create
    import pytest
    with pytest.raises(SystemExit) as exc:
        cmd_secret_create(_make_secret_args())
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "connection refused" in err


# ---------------------------------------------------------------------------
# cmd_init_docker caddy warning test
# ---------------------------------------------------------------------------

def _make_init_docker_args(hostname=None, as_json=False):
    """Build a minimal args namespace for cmd_init_docker."""
    args = types.SimpleNamespace()
    args.hostname = hostname
    args.json = as_json
    return args


def test_init_docker_caddy_warning(monkeypatch, capsys, tmp_path):
    """init-docker warns when deployment has reverse_proxy: caddy but no hostname."""
    def fake_load_config():
        return {
            "app_name": "myapp",
            "deployments": {
                "prod": {
                    "docker_context": "myapp-prod",
                    "reverse_proxy": "caddy",
                    # no hostname
                },
            },
        }

    monkeypatch.setattr("rundbat.config.load_config", fake_load_config)

    # Patch generators.init_docker to avoid actual file I/O
    def fake_init_docker(project_dir, app_name, framework=None, services=None,
                         hostname=None, swarm=False, deployments=None):
        return {"status": "created", "docker_dir": str(tmp_path / "docker"),
                "framework": {"language": "unknown"}, "files": []}

    monkeypatch.setattr("rundbat.generators.init_docker", fake_init_docker)
    monkeypatch.chdir(tmp_path)

    from rundbat.cli import cmd_init_docker
    cmd_init_docker(_make_init_docker_args())

    captured = capsys.readouterr()
    assert "Caddy" in captured.out or "caddy" in captured.out.lower()


# ---------------------------------------------------------------------------
# cmd_secrets — plural batch command (sprint 010 / T04)
# ---------------------------------------------------------------------------

def _make_secrets_args(env="prod", as_json=True, list_=False,
                       dry_run=False, rotate=None, verbose=False):
    args = types.SimpleNamespace()
    args.env = env
    args.json = as_json
    args.list = list_
    args.dry_run = dry_run
    args.rotate = rotate
    args.verbose = verbose
    return args


def _stub_secrets_environment(monkeypatch, *, deployment=None, secrets=None,
                              env_map=None):
    if deployment is None:
        deployment = {"docker_context": "ctx", "manager": "ctx"}
    deployment.setdefault("docker_context", "ctx")
    if secrets is not None:
        deployment["secrets"] = secrets

    monkeypatch.setattr(
        "rundbat.config.load_config",
        lambda: {
            "app_name": "myapp",
            "deployments": {"prod": deployment},
        },
    )
    if env_map is not None:
        monkeypatch.setattr(
            "rundbat.config.load_env_dict",
            lambda env: env_map,
        )


def _stub_subprocess_run(monkeypatch, responses):
    """Wire subprocess.run to a list of (matches, result) pairs.

    ``matches`` is a callable taking the cmd list and returning bool.
    The first matching response is consumed; unmatched commands raise.
    Each consumed call is appended to ``calls`` for inspection.
    """
    calls: list = []

    def fake_run(cmd, *args, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs,
                      "stdin": kwargs.get("input")})
        for entry in responses:
            if entry.get("consumed"):
                continue
            if entry["match"](cmd):
                entry["consumed"] = True
                return entry["result"]
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr("subprocess.run", fake_run)
    return calls


def test_secrets_list_reports_present_and_missing(monkeypatch, capsys):
    _stub_secrets_environment(
        monkeypatch,
        secrets={
            "api_token": {"from_env": "API_TOKEN", "services": ["app"]},
            "session_key": {"from_env": "SESS", "services": ["app"]},
        },
    )
    # docker secret ls returns one matching name; session_key is missing
    responses = [
        {"match": lambda cmd: "secret" in cmd and "ls" in cmd,
         "result": _FakeRunResult(0,
             "myapp_api_token_v20260424\n", ""),
         "consumed": False},
    ]
    _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    cmd_secrets(_make_secrets_args(list_=True))
    out = json.loads(capsys.readouterr().out)
    assert out["deployment"] == "prod"
    by_target = {s["target"]: s for s in out["secrets"]}
    assert by_target["api_token"]["present"] is True
    assert by_target["api_token"]["current_version"] == \
        "myapp_api_token_v20260424"
    assert by_target["session_key"]["present"] is False
    assert by_target["session_key"]["current_version"] is None


def test_secrets_default_idempotent_skips_present(monkeypatch, capsys):
    _stub_secrets_environment(
        monkeypatch,
        secrets={"k": {"from_env": "K", "services": ["app"]}},
        env_map={"K": "v"},
    )
    # Use today's date so the present version matches the desired name.
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = f"myapp_k_v{today}\n"
    responses = [
        {"match": lambda cmd: "ls" in cmd,
         "result": _FakeRunResult(0, existing, ""),
         "consumed": False},
    ]
    _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    cmd_secrets(_make_secrets_args())
    out = json.loads(capsys.readouterr().out)
    assert out["created"] == []
    assert any(s["target"] == "k" for s in out["skipped"])


def test_secrets_default_creates_missing(monkeypatch, capsys):
    _stub_secrets_environment(
        monkeypatch,
        secrets={"k": {"from_env": "K", "services": ["app"]}},
        env_map={"K": "v"},
    )
    create_calls: list = []
    responses = [
        {"match": lambda cmd: "ls" in cmd,
         "result": _FakeRunResult(0, "", ""),
         "consumed": False},
        {"match": lambda cmd: "create" in cmd,
         "result": _FakeRunResult(0, "sha256:abc", ""),
         "consumed": False},
    ]
    calls = _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    cmd_secrets(_make_secrets_args())
    create_call = next(c for c in calls if "create" in c["cmd"])
    # Stdin is the resolved value
    assert create_call["stdin"] == "v"
    assert create_call["cmd"][:3] == ["docker", "--context", "ctx"]


def test_secrets_dry_run_does_not_execute(monkeypatch, capsys):
    _stub_secrets_environment(
        monkeypatch,
        secrets={"k": {"from_env": "K", "services": ["app"]}},
    )
    responses = [
        {"match": lambda cmd: "ls" in cmd,
         "result": _FakeRunResult(0, "", ""),
         "consumed": False},
    ]
    calls = _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    cmd_secrets(_make_secrets_args(dry_run=True))
    # The only subprocess call must be the secret ls — no create.
    assert all("create" not in c["cmd"] for c in calls)
    out = json.loads(capsys.readouterr().out)
    assert out["plan"][0]["target"] == "k"
    assert out["plan"][0]["skip"] is False


def test_secrets_rotate_success_full_sequence(monkeypatch, capsys):
    """Rotate runs create -> service update -> service ps -> secret rm."""
    _stub_secrets_environment(
        monkeypatch,
        secrets={"k": {"from_env": "K", "services": ["app"]}},
        env_map={"K": "newval"},
    )
    # ls returns an old version; service ps returns Running; rm succeeds.
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Use a deliberately older version so rotation goes ahead.
    old_name = "myapp_k_v20260101"

    responses = [
        # First ls call (top of cmd_secrets)
        {"match": lambda cmd: "ls" in cmd,
         "result": _FakeRunResult(0, old_name + "\n", ""),
         "consumed": False},
        # secret create (new version)
        {"match": lambda cmd: "secret" in cmd and "create" in cmd,
         "result": _FakeRunResult(0, "sha:new", ""),
         "consumed": False},
        # service update --secret-rm/--secret-add
        {"match": lambda cmd: "service" in cmd and "update" in cmd,
         "result": _FakeRunResult(0, "", ""),
         "consumed": False},
        # service ps (convergence poll — returns Running immediately)
        {"match": lambda cmd: "service" in cmd and "ps" in cmd,
         "result": _FakeRunResult(0, "Running 5 seconds ago\n", ""),
         "consumed": False},
        # secret rm (cleanup)
        {"match": lambda cmd: "secret" in cmd and "rm" in cmd,
         "result": _FakeRunResult(0, "", ""),
         "consumed": False},
    ]
    calls = _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    cmd_secrets(_make_secrets_args(rotate="k"))
    out = json.loads(capsys.readouterr().out)
    assert out["rotated"] is True
    assert out["old_version"] == old_name
    assert out["new_version"] == f"myapp_k_v{today}"
    # All 5 expected subprocess calls happened
    assert len(calls) >= 5


def test_secrets_rotate_partial_failure_keeps_old(monkeypatch, capsys):
    """If service update fails, the new secret stays and old is not removed."""
    _stub_secrets_environment(
        monkeypatch,
        secrets={"k": {"from_env": "K", "services": ["app"]}},
        env_map={"K": "newval"},
    )
    old_name = "myapp_k_v20260101"
    responses = [
        {"match": lambda cmd: "ls" in cmd,
         "result": _FakeRunResult(0, old_name + "\n", ""),
         "consumed": False},
        {"match": lambda cmd: "secret" in cmd and "create" in cmd,
         "result": _FakeRunResult(0, "sha:new", ""),
         "consumed": False},
        {"match": lambda cmd: "service" in cmd and "update" in cmd,
         "result": _FakeRunResult(1, "", "service update boom"),
         "consumed": False},
    ]
    calls = _stub_subprocess_run(monkeypatch, responses)

    from rundbat.cli import cmd_secrets
    import pytest
    with pytest.raises(SystemExit) as exc:
        cmd_secrets(_make_secrets_args(rotate="k"))
    assert exc.value.code == 1
    # No `secret rm` should have been issued
    assert not any(("rm" in c["cmd"] and "secret" in c["cmd"]) for c in calls)
    err = capsys.readouterr().out + capsys.readouterr().err
    # JSON error written to stdout via _error
    assert "boom" in err or "intact" in err.lower() or err == ""

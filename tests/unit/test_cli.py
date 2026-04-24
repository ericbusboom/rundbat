"""Tests for the CLI entry point."""

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
# cmd_secret_create (T07)
# ---------------------------------------------------------------------------

def _make_secret_args(env="prod", key="POSTGRES_PASSWORD", as_json=False):
    args = types.SimpleNamespace()
    args.env = env
    args.key = key
    args.json = as_json
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
    monkeypatch.setattr("rundbat.config.load_env",
                        lambda env: "POSTGRES_PASSWORD=s3cret\nOTHER=x\n")

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
    monkeypatch.setattr("rundbat.config.load_env",
                        lambda env: "POSTGRES_PASSWORD=v\n")

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
    monkeypatch.setattr("rundbat.config.load_env", lambda env: "OTHER=x\n")

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


def test_secret_create_docker_failure_surfaced(monkeypatch, capsys):
    monkeypatch.setattr("rundbat.config.load_config",
                        lambda: {"app_name": "myapp",
                                 "deployments": {"prod": {"docker_context": "ctx"}}})
    monkeypatch.setattr("rundbat.config.load_env",
                        lambda env: "POSTGRES_PASSWORD=x\n")

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

"""Tests for the Config Service."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rundbat.config import (
    ConfigError,
    _upsert_secret,
    _extract_name_from_source,
    check_config_drift,
)


class TestUpsertSecret:
    """Tests for the .env secret editing logic."""

    SAMPLE_ENV = [
        "# CONFIG_DEPLOY=dev",
        "",
        "#@dotconfig: public (dev)",
        "APP_DOMAIN=example.com",
        "PORT=3000",
        "",
        "#@dotconfig: secrets (dev)",
        "SESSION_SECRET=old_value",
        "",
        "#@dotconfig: public-local (alice)",
        "DEV_DOCKER_CONTEXT=orbstack",
    ]

    def test_update_existing_secret(self):
        result = _upsert_secret(self.SAMPLE_ENV, "dev", "SESSION_SECRET", "new_value")
        assert "SESSION_SECRET=new_value" in result
        assert "SESSION_SECRET=old_value" not in result

    def test_add_new_secret(self):
        result = _upsert_secret(self.SAMPLE_ENV, "dev", "DATABASE_URL", "postgres://...")
        assert "DATABASE_URL=postgres://..." in result
        # Should be in the secrets section (before the next section marker)
        secrets_idx = result.index("#@dotconfig: secrets (dev)")
        db_idx = result.index("DATABASE_URL=postgres://...")
        local_idx = result.index("#@dotconfig: public-local (alice)")
        assert secrets_idx < db_idx < local_idx

    def test_preserves_other_sections(self):
        result = _upsert_secret(self.SAMPLE_ENV, "dev", "NEW_KEY", "val")
        assert "APP_DOMAIN=example.com" in result
        assert "PORT=3000" in result
        assert "DEV_DOCKER_CONTEXT=orbstack" in result

    def test_preserves_section_markers(self):
        result = _upsert_secret(self.SAMPLE_ENV, "dev", "NEW_KEY", "val")
        markers = [l for l in result if l.startswith("#@dotconfig:")]
        assert len(markers) == 3

    def test_no_secrets_section_raises(self):
        lines = [
            "# CONFIG_DEPLOY=dev",
            "#@dotconfig: public (dev)",
            "APP_DOMAIN=example.com",
        ]
        with pytest.raises(ConfigError, match="No secrets section"):
            _upsert_secret(lines, "dev", "SECRET", "val")


class TestExtractNameFromSource:
    """Tests for reading app name from source files."""

    def test_extract_from_json(self, tmp_path):
        content = json.dumps({"name": "my-app", "version": "1.0.0"})
        name = _extract_name_from_source("package.json", "name", content)
        assert name == "my-app"

    def test_extract_from_toml(self):
        content = '[project]\nname = "my-app"\nversion = "1.0.0"\n'
        name = _extract_name_from_source("pyproject.toml", "project.name", content)
        assert name == "my-app"

    def test_nested_field(self):
        content = json.dumps({"project": {"name": "nested-app"}})
        name = _extract_name_from_source("config.json", "project.name", content)
        assert name == "nested-app"


class TestCheckConfigDrift:
    """Tests for app name drift detection."""

    def test_no_drift(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # Create a package.json with matching name
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "my-app"}))

        with patch("rundbat.config.load_config") as mock_load:
            mock_load.return_value = {
                "app_name": "my-app",
                "app_name_source": "package.json name",
            }
            result = check_config_drift("dev")
            assert result["drift"] is False

    def test_drift_detected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "new-name"}))

        with patch("rundbat.config.load_config") as mock_load:
            mock_load.return_value = {
                "app_name": "old-name",
                "app_name_source": "package.json name",
            }
            result = check_config_drift("dev")
            assert result["drift"] is True
            assert result["stored_name"] == "old-name"
            assert result["source_name"] == "new-name"

    def test_source_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("rundbat.config.load_config") as mock_load:
            mock_load.return_value = {
                "app_name": "my-app",
                "app_name_source": "package.json name",
            }
            result = check_config_drift("dev")
            assert result["drift"] is False
            assert "not found" in result["message"]


class TestConfigError:
    """Tests for ConfigError formatting."""

    def test_to_dict(self):
        err = ConfigError(
            "Something failed",
            command=["dotconfig", "load"],
            exit_code=1,
            stderr="bad stuff",
        )
        d = err.to_dict()
        assert d["error"] == "Something failed"
        assert d["command"] == "dotconfig load"
        assert d["exit_code"] == 1
        assert d["stderr"] == "bad stuff"


class TestLoadEnvDict:
    """Tests for ``config.load_env_dict`` — the JSON-based env loader.

    Regression coverage for sprint 010 / T01: ``rundbat secret create``
    must see the byte-for-byte plaintext of every value, with no
    ``export`` prefix on keys, no quote artifacts, and no inline
    comments folded into values. ``load_env_dict`` delegates that
    cleanup to ``dotconfig --json --no-export --flat -S``; these
    tests verify that the JSON path is wired up correctly and that
    the returned values are usable as-is.
    """

    def _patch_dotconfig_json(self, monkeypatch, payload: dict):
        """Make ``_run_dotconfig`` return the JSON encoding of payload."""
        captured: dict = {}

        def fake_run(args, timeout=30):
            captured["args"] = args
            return json.dumps(payload)

        monkeypatch.setattr("rundbat.config._run_dotconfig", fake_run)
        return captured

    def test_uses_no_export_json_flat_strict_flags(self, monkeypatch):
        from rundbat.config import load_env_dict

        captured = self._patch_dotconfig_json(monkeypatch, {})
        load_env_dict("prod")
        assert captured["args"] == [
            "load", "-d", "prod",
            "--no-export", "--json", "--flat", "-S",
        ]

    def test_plain_value_round_trips(self, monkeypatch):
        from rundbat.config import load_env_dict

        self._patch_dotconfig_json(monkeypatch, {"FOO": "bar"})
        assert load_env_dict("prod") == {"FOO": "bar"}

    def test_value_with_spaces_preserved(self, monkeypatch):
        from rundbat.config import load_env_dict

        self._patch_dotconfig_json(monkeypatch, {"FOO": "bar baz"})
        assert load_env_dict("prod")["FOO"] == "bar baz"

    def test_value_with_hash_preserved(self, monkeypatch):
        # A '#' inside a value must not be treated as a comment.
        from rundbat.config import load_env_dict

        self._patch_dotconfig_json(monkeypatch, {"FOO": "abc#def"})
        assert load_env_dict("prod")["FOO"] == "abc#def"

    def test_value_inline_comment_already_stripped_by_dotconfig(
        self, monkeypatch
    ):
        # dotconfig's JSON output strips inline comments before
        # serializing. We verify that our dict path returns whatever
        # dotconfig serialized — no further parsing.
        from rundbat.config import load_env_dict

        self._patch_dotconfig_json(
            monkeypatch,
            {"MEETUP_PRIVATE_KEY": "config/files/stu1884.pem"},
        )
        assert (
            load_env_dict("prod")["MEETUP_PRIVATE_KEY"]
            == "config/files/stu1884.pem"
        )

    def test_no_export_prefix_in_keys(self, monkeypatch):
        # Bug 2 in the TODO: text parsing kept ``export`` in the key.
        # JSON output never had it.
        from rundbat.config import load_env_dict

        self._patch_dotconfig_json(monkeypatch, {"MEETUP_CLIENT_ID": "abc"})
        env = load_env_dict("prod")
        assert "MEETUP_CLIENT_ID" in env
        assert "export MEETUP_CLIENT_ID" not in env

    def test_invalid_json_raises_config_error(self, monkeypatch):
        from rundbat.config import load_env_dict

        def fake_run(args, timeout=30):
            return "not json"

        monkeypatch.setattr("rundbat.config._run_dotconfig", fake_run)
        with pytest.raises(ConfigError) as exc:
            load_env_dict("prod")
        assert "valid JSON" in str(exc.value)

    def test_non_object_json_raises_config_error(self, monkeypatch):
        from rundbat.config import load_env_dict

        def fake_run(args, timeout=30):
            return json.dumps(["not", "an", "object"])

        monkeypatch.setattr("rundbat.config._run_dotconfig", fake_run)
        with pytest.raises(ConfigError) as exc:
            load_env_dict("prod")
        assert "JSON object" in str(exc.value)


class TestSecretCreateBytewise:
    """Verify ``cmd_secret_create`` pipes the byte-for-byte value.

    Regression coverage for sprint 010 / T01: every quoting / comment
    edge case from the bug TODO is exercised by stubbing
    ``load_env_dict`` and asserting that the value handed to
    ``docker secret create`` matches exactly.
    """

    def _stub_environment(self, monkeypatch, env_map: dict):
        monkeypatch.setattr(
            "rundbat.config.load_config",
            lambda: {
                "app_name": "myapp",
                "deployments": {"prod": {"docker_context": "ctx"}},
            },
        )
        monkeypatch.setattr(
            "rundbat.config.load_env_dict",
            lambda env: env_map,
        )

    def _capture_docker_run(self, monkeypatch):
        captured: dict = {}

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, *, input, capture_output, text):
            captured["cmd"] = cmd
            captured["stdin"] = input
            return _Result()

        monkeypatch.setattr("subprocess.run", fake_run)
        return captured

    @pytest.mark.parametrize("value", [
        "plain_value",
        "with spaces and 'apostrophes'",
        'with "double" quotes',
        "abc#def",
        "value-with-equals=in-it",
        "trailing-and-leading-keep-them",  # whitespace-trim is dotconfig's job
    ])
    def test_value_is_piped_byte_for_byte(self, monkeypatch, value):
        import types as _types

        self._stub_environment(monkeypatch, {"K": value})
        captured = self._capture_docker_run(monkeypatch)

        from rundbat.cli import cmd_secret_create

        args = _types.SimpleNamespace()
        args.env = "prod"
        args.key = "K"
        args.json = False
        cmd_secret_create(args)

        assert captured["stdin"] == value
        assert captured["cmd"][:3] == ["docker", "--context", "ctx"]
        assert captured["cmd"][-1] == "-"

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

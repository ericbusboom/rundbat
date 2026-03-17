"""Tests for the Environment Service."""

from unittest.mock import patch, MagicMock

from rundbat.environment import (
    create_environment,
    get_environment_config,
    validate_environment,
)
from rundbat.config import ConfigError
from rundbat.database import DatabaseError


class TestCreateEnvironment:
    """Tests for environment creation."""

    def test_unsupported_type(self):
        result = create_environment("dev", env_type="remote-docker")
        assert "error" in result
        assert "not yet supported" in result["error"]

    def test_no_project_config(self):
        with patch("rundbat.environment.config.load_config", side_effect=ConfigError("not found")):
            result = create_environment("dev")
            assert "error" in result
            assert "init_project" in result["error"]

    def test_successful_creation(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.database.find_available_port", return_value=5432), \
             patch("rundbat.environment.database.create_database") as mock_create, \
             patch("rundbat.environment.config.save_config"), \
             patch("rundbat.environment.config.save_secret"):
            mock_load.return_value = {"app_name": "my-app", "app_name_source": "package.json name"}
            mock_create.return_value = {
                "container": "rundbat-my-app-dev-pg",
                "database": "rundbat_my-app_dev",
                "port": 5432,
                "user": "my-app",
                "status": "running",
            }

            result = create_environment("dev")
            assert result["status"] == "created"
            assert result["port"] == 5432
            assert "connection_string" in result
            assert "my-app" in result["connection_string"]


class TestGetEnvironmentConfig:
    """Tests for environment config retrieval."""

    def test_config_not_found(self):
        with patch("rundbat.environment.config.load_config", side_effect=ConfigError("not found")):
            result = get_environment_config("dev")
            assert "error" in result

    def test_not_configured(self):
        with patch("rundbat.environment.config.load_config", return_value={"app_name": "app"}):
            result = get_environment_config("dev")
            assert "error" in result
            assert "not configured" in result["error"]

    def test_successful_retrieval_running(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.config.load_env", return_value="DATABASE_URL=postgresql://..."), \
             patch("rundbat.environment.database.ensure_running") as mock_ensure, \
             patch("rundbat.environment.config.check_config_drift", return_value={"drift": False}):
            mock_load.return_value = {
                "app_name": "my-app",
                "app_name_source": "package.json name",
                "database": {
                    "container": "rundbat-my-app-dev-pg",
                    "port": 5432,
                },
                "notes": ["test note"],
            }
            mock_ensure.return_value = {
                "status": "running",
                "action": "none",
                "warnings": [],
            }

            result = get_environment_config("dev")
            assert result["app_name"] == "my-app"
            assert result["database"]["status"] == "running"
            assert result["database"]["connection_string"] == "postgresql://..."
            assert "test note" in result["notes"]

    def test_includes_drift_warning(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.config.load_env", return_value="DATABASE_URL=postgresql://..."), \
             patch("rundbat.environment.database.ensure_running") as mock_ensure, \
             patch("rundbat.environment.config.check_config_drift") as mock_drift:
            mock_load.return_value = {
                "app_name": "my-app",
                "database": {"container": "c", "port": 5432},
                "notes": [],
            }
            mock_ensure.return_value = {"status": "running", "action": "none", "warnings": []}
            mock_drift.return_value = {
                "drift": True,
                "message": "App name mismatch",
            }

            result = get_environment_config("dev")
            assert any("mismatch" in w for w in result["warnings"])

    def test_includes_recreate_warning(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.config.load_env", return_value="DATABASE_URL=postgresql://u:p@h:5/d"), \
             patch("rundbat.environment.database.ensure_running") as mock_ensure, \
             patch("rundbat.environment.config.check_config_drift", return_value={"drift": False}):
            mock_load.return_value = {
                "app_name": "my-app",
                "database": {"container": "c", "port": 5432},
                "notes": [],
            }
            mock_ensure.return_value = {
                "status": "running",
                "action": "recreated",
                "warnings": ["Data not recoverable"],
            }

            result = get_environment_config("dev")
            assert any("not recoverable" in w for w in result["warnings"])


class TestValidateEnvironment:
    """Tests for environment validation."""

    def test_all_checks_pass(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.config.load_env", return_value="DATABASE_URL=pg://..."), \
             patch("rundbat.environment.database.get_container_status", return_value="running"), \
             patch("rundbat.environment.database.health_check", return_value={"ok": True}):
            mock_load.return_value = {
                "app_name": "app",
                "database": {"container": "c"},
            }

            result = validate_environment("dev")
            assert result["ok"] is True
            assert all(c["ok"] for c in result["checks"].values())

    def test_config_missing(self):
        with patch("rundbat.environment.config.load_config", side_effect=ConfigError("nope")), \
             patch("rundbat.environment.config.load_env", side_effect=ConfigError("nope")):
            result = validate_environment("dev")
            assert result["ok"] is False
            assert result["checks"]["config"]["ok"] is False

    def test_container_not_running(self):
        with patch("rundbat.environment.config.load_config") as mock_load, \
             patch("rundbat.environment.config.load_env", return_value="DATABASE_URL=pg://..."), \
             patch("rundbat.environment.database.get_container_status", return_value="exited"):
            mock_load.return_value = {
                "app_name": "app",
                "database": {"container": "c"},
            }

            result = validate_environment("dev")
            assert result["ok"] is False
            assert result["checks"]["container"]["ok"] is False
            assert result["checks"]["connectivity"]["ok"] is False

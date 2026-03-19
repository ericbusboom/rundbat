"""Tests for the Database Service."""

from unittest.mock import patch, MagicMock

import pytest

from rundbat.database import (
    container_name,
    database_name,
    find_available_port,
    get_container_status,
    health_check,
    ensure_running,
    DatabaseError,
)


class TestNamingConventions:
    """Tests for container and database naming."""

    def test_container_name(self):
        assert container_name("my-app", "dev") == "my-app-dev-pg"

    def test_container_name_staging(self):
        assert container_name("league-enrollment", "staging") == "league-enrollment-staging-pg"

    def test_container_name_custom_template(self):
        assert container_name("my-app", "dev", "{app}-{env}-postgres") == "my-app-dev-postgres"

    def test_database_name(self):
        assert database_name("my-app", "dev") == "my-app_dev"

    def test_database_name_prod(self):
        assert database_name("league-enrollment", "prod") == "league-enrollment_prod"

    def test_database_name_custom_template(self):
        assert database_name("my-app", "dev", "db_{app}_{env}") == "db_my-app_dev"


class TestPortAllocation:
    """Tests for port finding logic."""

    def test_default_port_available(self):
        with patch("rundbat.database._is_port_available", return_value=True):
            port = find_available_port(5432)
            assert port == 5432

    def test_default_port_taken(self):
        def available(port):
            return port != 5432

        with patch("rundbat.database._is_port_available", side_effect=available):
            port = find_available_port(5432)
            assert port == 5433

    def test_multiple_ports_taken(self):
        def available(port):
            return port >= 5435

        with patch("rundbat.database._is_port_available", side_effect=available):
            port = find_available_port(5432)
            assert port == 5435

    def test_no_port_available(self):
        with patch("rundbat.database._is_port_available", return_value=False):
            with pytest.raises(DatabaseError, match="No available port"):
                find_available_port(5432, max_attempts=3)


class TestContainerStatus:
    """Tests for container status detection."""

    def test_running_container(self):
        with patch("rundbat.database._run_docker", return_value="running"):
            status = get_container_status("test-container")
            assert status == "running"

    def test_exited_container(self):
        with patch("rundbat.database._run_docker", return_value="exited"):
            status = get_container_status("test-container")
            assert status == "exited"

    def test_missing_container(self):
        with patch("rundbat.database._run_docker", side_effect=DatabaseError("not found")):
            status = get_container_status("test-container")
            assert status is None


class TestHealthCheck:
    """Tests for pg_isready health check."""

    def test_healthy(self):
        with patch("rundbat.database._run_docker", return_value=""):
            result = health_check("test-container")
            assert result["ok"] is True
            assert result["error"] is None

    def test_unhealthy(self):
        with patch("rundbat.database._run_docker", side_effect=DatabaseError("not ready")):
            result = health_check("test-container")
            assert result["ok"] is False
            assert result["error"] is not None


class TestEnsureRunning:
    """Tests for stale state recovery logic."""

    def test_already_running_and_healthy(self):
        with patch("rundbat.database.get_container_status", return_value="running"), \
             patch("rundbat.database.health_check", return_value={"ok": True}):
            result = ensure_running("app", "dev", "pass", 5432)
            assert result["action"] == "none"
            assert result["status"] == "running"
            assert result["warnings"] == []

    def test_exited_container_restarted(self):
        with patch("rundbat.database.get_container_status", return_value="exited"), \
             patch("rundbat.database.start_container") as mock_start:
            result = ensure_running("app", "dev", "pass", 5432)
            assert result["action"] == "restarted"
            mock_start.assert_called_once()

    def test_missing_container_recreated(self):
        with patch("rundbat.database.get_container_status", return_value=None), \
             patch("rundbat.database.create_database") as mock_create:
            mock_create.return_value = {"container": "rundbat-app-dev-pg", "status": "running"}
            result = ensure_running("app", "dev", "pass", 5432)
            assert result["action"] == "recreated"
            assert len(result["warnings"]) > 0
            assert "not recoverable" in result["warnings"][0]


class TestDatabaseError:
    """Tests for DatabaseError formatting."""

    def test_to_dict(self):
        err = DatabaseError(
            "Docker failed",
            command=["docker", "run"],
            exit_code=1,
            stderr="error output",
        )
        d = err.to_dict()
        assert d["error"] == "Docker failed"
        assert d["command"] == "docker run"
        assert d["exit_code"] == 1

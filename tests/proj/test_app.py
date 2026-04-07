import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock external dependencies before importing app
MOCK_CONFIG = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
    "REDIS_URL": "redis://localhost:6379/0",
}


@pytest.fixture(autouse=True)
def _mock_externals(monkeypatch):
    """Mock dotconfig, psycopg2, and redis before app import."""
    # Remove cached app module so each test gets fresh mocks
    for mod_name in list(sys.modules):
        if mod_name == "app":
            del sys.modules[mod_name]


def _import_app(mock_subprocess, mock_psycopg2=None, mock_redis=None):
    """Import app with mocked externals."""
    mock_subprocess.return_value.stdout = json.dumps(MOCK_CONFIG)
    mock_subprocess.return_value.returncode = 0

    if mock_psycopg2 is None:
        mock_psycopg2 = MagicMock()
    if mock_redis is None:
        mock_redis = MagicMock()

    with patch.dict("sys.modules", {"psycopg2": mock_psycopg2, "redis": mock_redis}):
        with patch("subprocess.run", mock_subprocess):
            # Force reimport
            if "app" in sys.modules:
                del sys.modules["app"]
            import app as app_module
    return app_module, mock_psycopg2, mock_redis


# --- Ticket 001 tests ---


def test_index_returns_200():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    # Mock pg count
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (0,)
    # Mock redis count
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.get.return_value = None

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200


def test_index_contains_counter_labels():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (0,)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.get.return_value = None

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        response = client.get("/")
        html = response.data.decode()
        assert "Flask Counter App" in html
        assert "PostgreSQL Counter" in html
        assert "Redis Counter" in html


def test_increment_postgres_redirects():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        response = client.post("/increment/postgres")
        assert response.status_code == 302
        assert response.headers["Location"] == "/"


def test_increment_redis_redirects():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        response = client.post("/increment/redis")
        assert response.status_code == 302
        assert response.headers["Location"] == "/"


# --- Ticket 002 tests: PostgreSQL integration ---


def test_pg_init_creates_table():
    mock_sub = MagicMock()
    # Set up cursor mock before import so init_pg() uses it
    mock_pg = MagicMock()
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    app_mod, _, _ = _import_app(mock_sub, mock_psycopg2=mock_pg)

    # init_pg was called during import; verify SQL calls
    calls = mock_cursor.execute.call_args_list
    sql_strs = [str(c) for c in calls]
    assert any("CREATE TABLE IF NOT EXISTS" in s for s in sql_strs)
    assert any("INSERT INTO counters" in s for s in sql_strs)


def test_get_pg_count():
    mock_sub = MagicMock()
    app_mod, mock_pg, _ = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (42,)

    assert app_mod.get_pg_count() == 42


def test_increment_pg_executes_update():
    mock_sub = MagicMock()
    app_mod, mock_pg, _ = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    app_mod.increment_pg()
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE counters SET value = value + 1" in s for s in calls)
    mock_conn.commit.assert_called()


# --- Ticket 003 tests: Redis integration ---


def test_get_redis_count_returns_zero_when_key_missing():
    mock_sub = MagicMock()
    app_mod, _, mock_rd = _import_app(mock_sub)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.get.return_value = None

    assert app_mod.get_redis_count() == 0


def test_get_redis_count_returns_value():
    mock_sub = MagicMock()
    app_mod, _, mock_rd = _import_app(mock_sub)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.get.return_value = b"7"

    assert app_mod.get_redis_count() == 7


def test_increment_redis_calls_incr():
    mock_sub = MagicMock()
    app_mod, _, mock_rd = _import_app(mock_sub)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.incr.return_value = 1

    result = app_mod.do_increment_redis()
    mock_redis_client.incr.assert_called_with("counter")
    assert result == 1


# --- Ticket 004 tests: Integration (routes wired to backends) ---


def test_post_postgres_calls_increment():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        client.post("/increment/postgres")
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE counters SET value = value + 1" in s for s in calls)


def test_post_redis_calls_incr():
    mock_sub = MagicMock()
    app_mod, _, mock_rd = _import_app(mock_sub)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        client.post("/increment/redis")
    mock_redis_client.incr.assert_called_with("counter")


def test_counters_are_independent():
    mock_sub = MagicMock()
    app_mod, mock_pg, mock_rd = _import_app(mock_sub)
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (3,)
    mock_redis_client = MagicMock()
    mock_rd.Redis.from_url.return_value = mock_redis_client
    mock_redis_client.get.return_value = b"5"

    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as client:
        response = client.get("/")
        html = response.data.decode()
    # Both values should appear independently
    assert "3" in html
    assert "5" in html

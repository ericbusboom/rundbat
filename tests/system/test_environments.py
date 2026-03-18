"""System tests for all three deployment environments.

Each test:
1. Spins up (or connects to) a Postgres database
2. Connects with psycopg and runs a query
3. Tears down any containers it created

Markers:
- requires_docker: needs local Docker (OrbStack)
- requires_remote_docker: needs student-docker1 context
- requires_managed_db: needs the managed DO Postgres
"""

import subprocess
import time
import uuid

import psycopg
import pytest

# Test-specific container names to avoid collisions
TEST_PREFIX = f"rundbat-test-{uuid.uuid4().hex[:8]}"


def _docker_run(context, name, env_vars, port_mapping, timeout=60):
    """Run a Postgres container and wait for it to be ready."""
    cmd = ["docker", "--context", context, "run", "-d", "--name", name]
    for k, v in env_vars.items():
        cmd.extend(["-e", f"{k}={v}"])
    cmd.extend(["-p", port_mapping, "postgres:16"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr}")

    # Wait for pg_isready
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        check = subprocess.run(
            ["docker", "--context", context, "exec", name, "pg_isready"],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError(f"Postgres in {name} did not become ready within 30s")


def _docker_rm(context, name):
    """Force-remove a container, ignoring errors."""
    subprocess.run(
        ["docker", "--context", context, "rm", "-f", name],
        capture_output=True, text=True, timeout=30,
    )


def _pg_connect_and_test(connstr, retries=5, delay=2):
    """Connect to Postgres with retries, run a query, return the version.

    pg_isready can pass before Postgres is fully ready for client connections,
    especially with newly created containers. Retry the connection.
    """
    last_error = None
    for attempt in range(retries):
        try:
            with psycopg.connect(connstr, connect_timeout=10) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS alive")
                    row = cur.fetchone()
                    assert row == (1,), f"Expected (1,), got {row}"

                    cur.execute("SELECT version()")
                    version = cur.fetchone()[0]
                    assert "PostgreSQL" in version
                    return version
        except psycopg.OperationalError as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_error


# ---------------------------------------------------------------------------
# Dev: local Docker via OrbStack
# ---------------------------------------------------------------------------

class TestDevEnvironment:
    """Test local Postgres on OrbStack."""

    CONTEXT = "orbstack"
    CONTAINER = f"{TEST_PREFIX}-dev-pg"
    DB_NAME = "rundbat_test_dev"
    DB_USER = "rundbat"
    DB_PASS = "test-dev-pass"
    PORT = 15432  # Avoid conflicting with the real dev container on 5432

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        """Ensure container is removed after test, even on failure."""
        yield
        _docker_rm(self.CONTEXT, self.CONTAINER)

    @pytest.mark.requires_docker
    def test_dev_database_lifecycle(self):
        """Create, connect, query, and tear down a local Postgres."""
        # 1. Start container
        _docker_run(
            context=self.CONTEXT,
            name=self.CONTAINER,
            env_vars={
                "POSTGRES_USER": self.DB_USER,
                "POSTGRES_PASSWORD": self.DB_PASS,
                "POSTGRES_DB": self.DB_NAME,
            },
            port_mapping=f"127.0.0.1:{self.PORT}:5432",
        )

        # 2. Connect and test
        connstr = f"postgresql://{self.DB_USER}:{self.DB_PASS}@localhost:{self.PORT}/{self.DB_NAME}"
        version = _pg_connect_and_test(connstr)
        print(f"\n  Dev Postgres: {version}")

        # 3. Verify we can create a table and insert data
        with psycopg.connect(connstr, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE test_table (id serial PRIMARY KEY, name text)")
                cur.execute("INSERT INTO test_table (name) VALUES ('rundbat')")
                conn.commit()
                cur.execute("SELECT name FROM test_table WHERE id = 1")
                assert cur.fetchone() == ("rundbat",)


# ---------------------------------------------------------------------------
# Staging: remote Docker via student-docker1 context
# ---------------------------------------------------------------------------

class TestStagingEnvironment:
    """Test Postgres on remote Docker (student-docker1)."""

    CONTEXT = "student-docker1"
    CONTAINER = f"{TEST_PREFIX}-staging-pg"
    DB_NAME = "rundbat_test_staging"
    DB_USER = "rundbat"
    DB_PASS = "test-staging-pass"
    HOST = "64.23.185.160"
    PORT = 54322  # Different from the real staging on 54321

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        """Ensure container is removed after test, even on failure."""
        yield
        _docker_rm(self.CONTEXT, self.CONTAINER)

    @pytest.mark.requires_remote_docker
    def test_staging_database_lifecycle(self):
        """Create, connect, query, and tear down remote Postgres."""
        # 1. Start container on remote
        _docker_run(
            context=self.CONTEXT,
            name=self.CONTAINER,
            env_vars={
                "POSTGRES_USER": self.DB_USER,
                "POSTGRES_PASSWORD": self.DB_PASS,
                "POSTGRES_DB": self.DB_NAME,
            },
            port_mapping=f"{self.PORT}:5432",
        )

        # 2. Connect over the network and test
        connstr = f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.HOST}:{self.PORT}/{self.DB_NAME}"
        version = _pg_connect_and_test(connstr)
        print(f"\n  Staging Postgres: {version}")

        # 3. Verify write/read
        with psycopg.connect(connstr, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE test_table (id serial PRIMARY KEY, name text)")
                cur.execute("INSERT INTO test_table (name) VALUES ('staging-test')")
                conn.commit()
                cur.execute("SELECT name FROM test_table WHERE id = 1")
                assert cur.fetchone() == ("staging-test",)


# ---------------------------------------------------------------------------
# Prod: managed DigitalOcean Postgres
# ---------------------------------------------------------------------------

class TestProdEnvironment:
    """Test managed DigitalOcean Postgres connection."""

    @staticmethod
    def _get_prod_connstr():
        """Load the prod DATABASE_URL from dotconfig."""
        result = subprocess.run(
            ["dotconfig", "load", "-d", "prod", "--stdout"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            pytest.skip(f"Cannot load prod config: {result.stderr}")

        for line in result.stdout.splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1]
        pytest.skip("No DATABASE_URL in prod config")

    @pytest.mark.requires_managed_db
    def test_prod_database_connection(self):
        """Connect to managed DO Postgres and verify it works."""
        connstr = self._get_prod_connstr()

        # Connect and test — no container to create or tear down
        version = _pg_connect_and_test(connstr)
        print(f"\n  Prod Postgres: {version}")

        # Verify we can run read queries (managed DB may not grant DDL)
        with psycopg.connect(connstr, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                db, user = cur.fetchone()
                assert db == "rundbat"
                assert user == "rundbat"

                cur.execute("SELECT now()")
                ts = cur.fetchone()[0]
                assert ts is not None

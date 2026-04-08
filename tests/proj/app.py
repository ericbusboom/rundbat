import os
import subprocess

import psycopg2
import redis as redis_lib
from flask import Flask, redirect, render_template, url_for

app = Flask(__name__)


def load_config():
    # If DATABASE_URL is already in the environment (e.g. Docker), use env vars directly
    if os.environ.get("DATABASE_URL"):
        return {
            "DATABASE_URL": os.environ["DATABASE_URL"],
            "REDIS_URL": os.environ["REDIS_URL"],
        }
    # Otherwise load from dotconfig
    env = os.environ.get("APP_ENV", "dev")
    result = subprocess.run(
        ["dotconfig", "load", "-d", env, "--stdout"],
        capture_output=True, text=True, check=True,
    )
    config = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()
    return config


config = load_config()
DATABASE_URL = config["DATABASE_URL"]
REDIS_URL = config["REDIS_URL"]


def get_pg_connection():
    return psycopg2.connect(DATABASE_URL)


def init_pg():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS counters ("
                "id INTEGER PRIMARY KEY, "
                "value INTEGER NOT NULL DEFAULT 0)"
            )
            cur.execute(
                "INSERT INTO counters (id, value) VALUES (1, 0) "
                "ON CONFLICT DO NOTHING"
            )
        conn.commit()
    finally:
        conn.close()


def get_pg_count():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM counters WHERE id = 1")
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


def increment_pg():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE counters SET value = value + 1 WHERE id = 1")
        conn.commit()
    finally:
        conn.close()


def get_redis_client():
    return redis_lib.Redis.from_url(REDIS_URL)


def get_redis_count():
    r = get_redis_client()
    val = r.get("counter")
    return int(val) if val is not None else 0


def do_increment_redis():
    r = get_redis_client()
    return r.incr("counter")


with app.app_context():
    init_pg()


@app.route("/")
def index():
    pg_count = get_pg_count()
    redis_count = get_redis_count()
    return render_template("index.html", pg_count=pg_count, redis_count=redis_count)


@app.route("/increment/postgres", methods=["POST"])
def increment_postgres():
    increment_pg()
    return redirect(url_for("index"))


@app.route("/increment/redis", methods=["POST"])
def increment_redis():
    do_increment_redis()
    return redirect(url_for("index"))

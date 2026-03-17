"""Config Service — sole interface to dotconfig for all configuration operations."""

import json
import subprocess
import tempfile
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Error from a dotconfig operation."""

    def __init__(self, message: str, command: list[str] | None = None,
                 exit_code: int | None = None, stderr: str | None = None):
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "command": " ".join(self.command) if self.command else None,
            "exit_code": self.exit_code,
            "stderr": self.stderr,
        }


def _run_dotconfig(args: list[str], timeout: int = 30) -> str:
    """Run a dotconfig command and return stdout. Raises ConfigError on failure."""
    cmd = ["dotconfig"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ConfigError(
            "dotconfig is not installed. Install it with: pipx install dotconfig",
            command=cmd,
            exit_code=-1,
            stderr="Command not found: dotconfig",
        )
    except subprocess.TimeoutExpired:
        raise ConfigError(
            f"dotconfig command timed out after {timeout}s",
            command=cmd,
            exit_code=-1,
            stderr="Timeout",
        )

    if result.returncode != 0:
        raise ConfigError(
            f"dotconfig command failed: {result.stderr.strip()}",
            command=cmd,
            exit_code=result.returncode,
            stderr=result.stderr.strip(),
        )
    return result.stdout


def is_initialized() -> bool:
    """Check if dotconfig is initialized in the current project."""
    try:
        _run_dotconfig(["config"])
        return True
    except ConfigError:
        return False


def init_dotconfig() -> str:
    """Initialize dotconfig in the current project."""
    return _run_dotconfig(["init"])


def load_config(env: str) -> dict:
    """Load rundbat.yaml for a deployment via dotconfig."""
    stdout = _run_dotconfig(["load", "-d", env, "--file", "rundbat.yaml", "--stdout"])
    return yaml.safe_load(stdout) or {}


def save_config(env: str, data: dict) -> None:
    """Save rundbat.yaml for a deployment via dotconfig."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="rundbat-", delete=False
    ) as f:
        yaml.dump(data, f, default_flow_style=False)
        tmp_path = f.name

    try:
        # Copy temp file to rundbat.yaml, then save via dotconfig
        Path("rundbat.yaml").write_text(Path(tmp_path).read_text())
        _run_dotconfig(["save", "-d", env, "--file", "rundbat.yaml"])
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        Path("rundbat.yaml").unlink(missing_ok=True)


def load_env(env: str) -> str:
    """Load the assembled .env for a deployment via dotconfig (to stdout)."""
    return _run_dotconfig(["load", "-d", env, "--stdout"])


def save_secret(env: str, key: str, value: str) -> None:
    """Add or update a secret in a deployment's .env via dotconfig round-trip."""
    # Step 1: Load the assembled .env to a file
    _run_dotconfig(["load", "-d", env])

    # Step 2: Read the .env, add/update the key in the secrets section
    env_path = Path(".env")
    if not env_path.exists():
        raise ConfigError(
            f"dotconfig load did not produce .env for deployment '{env}'",
        )

    lines = env_path.read_text().splitlines()
    new_lines = _upsert_secret(lines, env, key, value)
    env_path.write_text("\n".join(new_lines) + "\n")

    # Step 3: Save back via dotconfig
    try:
        _run_dotconfig(["save"])
    finally:
        env_path.unlink(missing_ok=True)


def _upsert_secret(lines: list[str], env: str, key: str, value: str) -> list[str]:
    """Insert or update a key=value in the secrets section of a .env file."""
    secrets_marker = f"#@dotconfig: secrets ({env})"
    in_secrets = False
    key_found = False
    result = []

    for line in lines:
        stripped = line.strip()

        # Detect section boundaries
        if stripped.startswith("#@dotconfig:"):
            if stripped == secrets_marker:
                in_secrets = True
                result.append(line)
                continue
            else:
                # Leaving secrets section — insert key if not found
                if in_secrets and not key_found:
                    result.append(f"{key}={value}")
                    key_found = True
                in_secrets = False

        # Update existing key in secrets section
        if in_secrets and stripped.startswith(f"{key}="):
            result.append(f"{key}={value}")
            key_found = True
            continue

        result.append(line)

    # If we ended while still in secrets section and key wasn't found
    if in_secrets and not key_found:
        result.append(f"{key}={value}")

    # If there was no secrets section at all, we can't add one safely
    if not key_found and not any(secrets_marker in l for l in lines):
        raise ConfigError(
            f"No secrets section found for deployment '{env}'. "
            f"Expected marker: {secrets_marker}"
        )

    return result


def init_project(app_name: str, app_name_source: str) -> dict:
    """Initialize rundbat configuration for a project.

    Creates rundbat.yaml with app name and source via dotconfig.
    Initializes dotconfig if not already set up.
    """
    if not is_initialized():
        init_dotconfig()

    data = {
        "app_name": app_name,
        "app_name_source": app_name_source,
        "notes": [],
    }

    save_config("dev", data)

    return {
        "app_name": app_name,
        "app_name_source": app_name_source,
        "status": "initialized",
    }


def check_config_drift(env: str = "dev") -> dict:
    """Check if the app name at its source differs from the stored name."""
    config = load_config(env)
    app_name = config.get("app_name")
    source = config.get("app_name_source")

    if not app_name or not source:
        return {"drift": False, "message": "No app name or source configured."}

    # Parse the source reference (e.g., "package.json name" or "pyproject.toml project.name")
    parts = source.split(None, 1)
    if len(parts) < 2:
        return {"drift": False, "message": f"Cannot parse source reference: {source}"}

    source_file, source_field = parts

    source_path = Path(source_file)
    if not source_path.exists():
        return {
            "drift": False,
            "message": f"Source file not found: {source_file}",
        }

    try:
        content = source_path.read_text()
        source_name = _extract_name_from_source(source_file, source_field, content)
    except (json.JSONDecodeError, yaml.YAMLError, KeyError, IndexError) as e:
        return {
            "drift": False,
            "message": f"Could not read name from {source_file}: {e}",
        }

    if source_name != app_name:
        return {
            "drift": True,
            "stored_name": app_name,
            "source_name": source_name,
            "source": source,
            "message": (
                f"App name mismatch. rundbat.yaml says: {app_name}, "
                f"{source_file} says: {source_name}. "
                f"Recommendation: Update rundbat config. "
                f"Database name does not need to change."
            ),
        }

    return {"drift": False, "stored_name": app_name, "source_name": source_name}


def _extract_name_from_source(filename: str, field: str, content: str) -> str:
    """Extract a name value from a source file given a field path."""
    if filename.endswith(".json"):
        data = json.loads(content)
    elif filename.endswith((".yaml", ".yml")):
        data = yaml.safe_load(content)
    elif filename.endswith(".toml"):
        # Minimal TOML parsing for the common case
        import tomllib
        data = tomllib.loads(content)
    else:
        raise ConfigError(f"Unsupported source file type: {filename}")

    # Navigate dotted field path (e.g., "project.name")
    keys = field.split(".")
    current = data
    for key in keys:
        current = current[key]
    return str(current)

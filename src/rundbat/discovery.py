"""Discovery Service — detect host system capabilities."""

import platform
import subprocess
from pathlib import Path


def _run_command(args: list[str], timeout: int = 10) -> dict:
    """Run a command and return structured result."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command not found: {args[0]}",
            "returncode": -1,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out: {' '.join(args)}",
            "returncode": -1,
        }


def detect_os() -> dict:
    """Detect the host operating system."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "platform": platform.platform(),
    }


def detect_docker() -> dict:
    """Detect Docker installation and status."""
    result = _run_command(["docker", "info"])
    if not result["success"]:
        # Check if Docker is installed but not running
        version_result = _run_command(["docker", "--version"])
        if version_result["success"]:
            return {
                "installed": True,
                "running": False,
                "version": version_result["stdout"],
                "backend": None,
                "error": result["stderr"],
            }
        return {
            "installed": False,
            "running": False,
            "version": None,
            "backend": None,
            "error": result["stderr"],
        }

    # Parse backend from docker info output
    backend = None
    for line in result["stdout"].splitlines():
        stripped = line.strip()
        if stripped.startswith("Operating System:"):
            backend = stripped.split(":", 1)[1].strip()
            break
        if stripped.startswith("Server Version:"):
            backend = stripped.split(":", 1)[1].strip()

    version_result = _run_command(["docker", "--version"])
    return {
        "installed": True,
        "running": True,
        "version": version_result["stdout"] if version_result["success"] else None,
        "backend": backend,
        "error": None,
    }


def detect_dotconfig() -> dict:
    """Detect dotconfig installation and initialization status."""
    config_result = _run_command(["dotconfig", "config"])
    if not config_result["success"]:
        return {
            "installed": False,
            "initialized": False,
            "config_dir": None,
            "error": config_result["stderr"],
        }

    # Parse config output for directory info
    config_dir = None
    for line in config_result["stdout"].splitlines():
        stripped = line.strip()
        if "config" in stripped.lower() and ("dir" in stripped.lower() or "/" in stripped):
            # Try to extract a path
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                config_dir = parts[1].strip()

    # Check if initialized by looking for config directory
    initialized = config_dir is not None and Path(config_dir).exists() if config_dir else False
    if not initialized:
        # Fallback: check if config/ exists in cwd
        initialized = Path("config").exists() and Path("config/sops.yaml").exists()

    return {
        "installed": True,
        "initialized": initialized,
        "config_dir": config_dir,
        "error": None,
    }


def detect_node() -> dict:
    """Detect Node.js installation."""
    result = _run_command(["node", "--version"])
    if not result["success"]:
        return {
            "installed": False,
            "version": None,
        }
    return {
        "installed": True,
        "version": result["stdout"],
    }


def detect_existing_config() -> dict:
    """Check for existing rundbat configuration in the project."""
    config_dir = Path("config")
    found = []
    if config_dir.exists():
        for env_dir in config_dir.iterdir():
            if env_dir.is_dir() and env_dir.name != "local":
                rundbat_yaml = env_dir / "rundbat.yaml"
                if rundbat_yaml.exists():
                    found.append(str(env_dir.name))
    return {
        "has_config": len(found) > 0,
        "environments": found,
    }


def discover_system() -> dict:
    """Run full system discovery and return capabilities report."""
    return {
        "os": detect_os(),
        "docker": detect_docker(),
        "dotconfig": detect_dotconfig(),
        "node": detect_node(),
        "existing_config": detect_existing_config(),
    }


def verify_docker() -> dict:
    """Verify that Docker is installed and running."""
    result = _run_command(["docker", "info"])
    return {
        "ok": result["success"],
        "error": result["stderr"] if not result["success"] else None,
    }

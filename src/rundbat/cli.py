"""rundbat CLI — top-level entry point with subcommands."""

import argparse
import json
import os
import sys
from pathlib import Path

from rundbat import __version__


def _detect_app_name() -> tuple[str, str] | None:
    """Try to detect the app name from common project files."""
    cwd = Path.cwd()

    # Try package.json
    pkg_json = cwd / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            name = data.get("name")
            if name:
                return (name, "package.json name")
        except (json.JSONDecodeError, KeyError):
            pass

    # Try pyproject.toml
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text())
            name = data.get("project", {}).get("name")
            if name:
                return (name, "pyproject.toml project.name")
        except (ImportError, KeyError):
            pass

    # Fallback: use directory name
    return (cwd.name, f"directory name ({cwd.name})")


def _output(data: dict, as_json: bool) -> None:
    """Print result as JSON or human-readable."""
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")


def _error(message: str, as_json: bool) -> None:
    """Print error and exit 1."""
    if as_json:
        print(json.dumps({"error": message}))
    else:
        print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def _check_prerequisites() -> list[str]:
    """Check that Docker and dotconfig are available. Returns list of warnings."""
    import shutil
    warnings = []

    if not shutil.which("docker"):
        warnings.append("Docker is not installed or not in PATH.")
    if not shutil.which("dotconfig"):
        warnings.append("dotconfig is not installed. Install with: pipx install dotconfig")

    return warnings


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialize rundbat in the current project."""
    from rundbat import config, installer
    from rundbat.config import ConfigError

    project_dir = Path.cwd()
    print(f"Initializing rundbat in {project_dir}\n")

    # Step 1: Check prerequisites
    warnings = _check_prerequisites()
    for w in warnings:
        print(f"  WARNING: {w}")
    if warnings:
        print()

    # Step 2: Detect or use provided app name
    if args.app_name:
        app_name = args.app_name
        app_name_source = "command line"
    else:
        detected = _detect_app_name()
        app_name, app_name_source = detected
        print(f"  Detected app name: {app_name} (from {app_name_source})")

    # Step 3: Initialize dotconfig if needed
    print(f"  Checking dotconfig...", end=" ")
    if config.is_initialized():
        print("already initialized.")
    else:
        try:
            config.init_dotconfig()
            print("initialized.")
        except ConfigError as e:
            print(f"failed!\n    {e}")
            print("\n  Install dotconfig first: pipx install dotconfig")
            sys.exit(1)

    # Step 4: Detect current Docker context for local deployments
    from rundbat.deploy import get_current_context
    local_context = get_current_context()
    print(f"  Docker context: {local_context}")

    # Step 5: Save config/rundbat.yaml (skip if exists, unless --force)
    config_path = Path("config") / "rundbat.yaml"
    if config_path.exists() and not args.force:
        print(f"  rundbat.yaml already exists, skipping. (Use --force to overwrite.)")
    else:
        print(f"  Saving rundbat config...", end=" ")
        try:
            data = {
                "app_name": app_name,
                "app_name_source": app_name_source,
                "container_template": "{app}-{env}-pg",
                "database_template": "{app}_{env}",
                "deployments": {
                    "dev": {
                        "docker_context": local_context,
                        "build_strategy": "context",
                        "compose_file": "docker/docker-compose.dev.yml",
                        "env_source": "dotconfig",
                        "config_deployment": "dev",
                    },
                    "prod": {
                        "docker_context": "",
                        "hostname": "",
                        "compose_file": "docker/docker-compose.prod.yml",
                        "env_source": "dotconfig",
                        "config_deployment": "prod",
                    },
                    "test": {
                        "docker_context": local_context,
                        "build_strategy": "context",
                        "compose_file": "docker/docker-compose.test.yml",
                        "env_source": "dotconfig",
                        "config_deployment": "test",
                    },
                },
                "notes": [],
            }
            config.save_config(data=data)
            print("done.")
        except ConfigError as e:
            print(f"failed!\n    {e}")
            sys.exit(1)

    # Step 5: Ensure .gitignore excludes per-deployment env files
    gitignore = project_dir / ".gitignore"
    gitignore_pattern = "docker/.*.env"
    if gitignore.exists():
        content = gitignore.read_text()
        if gitignore_pattern not in content:
            with open(gitignore, "a") as f:
                f.write(f"\n# Per-deployment env files (contain secrets from dotconfig)\n{gitignore_pattern}\n")
            print(f"  Updated .gitignore with {gitignore_pattern}")
    else:
        gitignore.write_text(f"# Per-deployment env files (contain secrets from dotconfig)\n{gitignore_pattern}\n")
        print(f"  Created .gitignore with {gitignore_pattern}")

    # Step 6: Install Claude integration files
    print(f"  Installing Claude integration files...", end=" ")
    try:
        install_result = installer.install(project_dir)
        print("done.")
    except Exception as e:
        print(f"skipped ({e}).")

    # Summary
    print(f"\nrundbat is ready!")
    print(f"  App name:  {app_name}")
    print(f"  Source:    {app_name_source}")
    print(f"\nNext steps:")
    print(f"  - Run 'rundbat generate' to generate Docker artifacts")
    print(f"  - Run 'rundbat deploy-init prod --host ssh://user@host' to set up a deploy target")


def cmd_deploy(args):
    """Deploy using the configured build strategy."""
    from rundbat import deploy, config
    from rundbat.deploy import DeployError

    # Checkout config from dotconfig before deploying
    verbose = getattr(args, "verbose", False)
    try:
        cfg = config.load_config()
        dep_cfg = cfg.get("deployments", {}).get(args.name, {})
        _checkout_config(args.name, dep_cfg, verbose=verbose)
    except Exception:
        pass  # deploy() will handle config errors

    try:
        result = deploy.deploy(
            args.name, dry_run=args.dry_run, no_build=args.no_build,
            strategy=args.strategy, platform=args.platform,
        )
    except DeployError as e:
        _error(str(e), args.json)
        return

    if args.json:
        _output(result, args.json)
    else:
        strategy = result.get("strategy", "context")
        if result.get("status") == "dry_run":
            print(f"Dry run (strategy: {strategy}) — would execute:")
            for cmd in result.get("commands", [result.get("command", "")]):
                print(f"  {cmd}")
        else:
            print(f"Deployed via strategy '{strategy}', context '{result['context']}'")
            if result.get("platform"):
                print(f"  Platform: {result['platform']}")
            if result.get("images_transferred"):
                print(f"  Images transferred: {', '.join(result['images_transferred'])}")
            if result.get("url"):
                print(f"  {result['url']}")


def cmd_deploy_init(args):
    """Set up a new deployment target."""
    from rundbat import deploy
    from rundbat.deploy import DeployError

    try:
        result = deploy.init_deployment(
            args.name, args.host,
            compose_file=args.compose_file,
            hostname=args.hostname,
            build_strategy=args.strategy,
            ssh_key=args.ssh_key,
            deploy_mode=getattr(args, "deploy_mode", None),
            image=getattr(args, "image", None),
        )
    except DeployError as e:
        _error(str(e), args.json)
        return

    if args.json:
        _output(result, args.json)
    else:
        print(f"Deployment '{result['deployment']}' configured.")
        print(f"  Docker context: {result['context']}")
        print(f"  Host: {result['host']}")
        print(f"  Build strategy: {result['build_strategy']}")
        if result.get("ssh_key"):
            print(f"  SSH key: {result['ssh_key']}")
        if result.get("platform"):
            from rundbat.discovery import local_docker_platform
            local_plat = local_docker_platform()
            print(f"  Remote platform: {result['platform']} (local: {local_plat})")
            if result["platform"] != local_plat:
                print(f"  Cross-architecture: yes — images will be built for {result['platform']}")
        print(f"\nRun 'rundbat deploy {result['deployment']}' to deploy.")


def cmd_probe(args):
    """Probe a deployment target for reverse proxy and Swarm detection."""
    from rundbat import config
    from rundbat.discovery import detect_caddy, detect_swarm
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(str(e), args.json)
        return

    deployments = cfg.get("deployments", {})
    name = args.name
    if name not in deployments:
        _error(f"Deployment '{name}' not found in rundbat.yaml", args.json)
        return

    dep = deployments[name]
    ctx = dep.get("docker_context")
    if not ctx:
        _error(f"Deployment '{name}' has no docker_context", args.json)
        return

    caddy = detect_caddy(ctx)
    reverse_proxy = "caddy" if caddy["running"] else "none"
    dep["reverse_proxy"] = reverse_proxy

    swarm_probe = detect_swarm(ctx)
    _apply_swarm_probe_to_deployment(dep, swarm_probe)

    deployments[name] = dep
    cfg["deployments"] = deployments
    config.save_config(data=cfg)

    result = {
        "deployment": name,
        "reverse_proxy": reverse_proxy,
        "container": caddy.get("container"),
        "swarm": dep.get("swarm"),
        "swarm_role": dep.get("swarm_role"),
    }
    _output(result, args.json)


def _apply_swarm_probe_to_deployment(dep: dict, probe: dict) -> None:
    """Apply the swarm probe result to a deployment entry in-place.

    Implements the transient-failure rule documented in the sprint 008
    architecture update:

    - Reachable + swarm active → write ``swarm: true`` and role.
    - Reachable + swarm inactive → write ``swarm: false``; clear role.
      This applies even when the prior value was ``true`` — the daemon
      answered us, so the downgrade is authoritative.
    - Unreachable AND prior is ``swarm: true`` → do nothing (transient
      failure must not silently downgrade).
    - Unreachable AND prior is absent / false / unknown → record
      ``swarm: "unknown"`` and clear role.
    """
    prior = dep.get("swarm")
    reachable = probe.get("reachable", False)
    is_swarm = probe.get("swarm", False)
    role = probe.get("swarm_role", "")

    if reachable:
        if is_swarm:
            dep["swarm"] = True
            if role:
                dep["swarm_role"] = role
            else:
                dep.pop("swarm_role", None)
        else:
            dep["swarm"] = False
            dep.pop("swarm_role", None)
        return

    # Unreachable: honour the transient-failure invariant.
    if prior is True:
        return  # keep the prior declared state; do NOT overwrite.
    dep["swarm"] = "unknown"
    dep.pop("swarm_role", None)


def cmd_generate(args):
    """Generate Docker artifacts from rundbat.yaml config."""
    from rundbat import generators, config
    from rundbat.config import ConfigError

    project_dir = Path.cwd()

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(f"Cannot load config: {e}. Run 'rundbat init' first.", args.json)
        return

    result = generators.generate_artifacts(
        project_dir, cfg,
        deployment=getattr(args, "deployment", None),
    )
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


def cmd_init_docker(args):
    """Scaffold a docker/ directory for the project (deprecated)."""
    from rundbat import generators, config
    from rundbat.config import ConfigError

    project_dir = Path.cwd()

    # Load rundbat.yaml for app_name, framework, services, deployments
    app_name = "app"
    framework = None
    services = None
    hostname = None
    swarm = False
    deployments = None

    try:
        cfg = config.load_config()
        app_name = cfg.get("app_name", "app")
        if cfg.get("framework"):
            framework = {"language": "unknown", "framework": cfg["framework"], "entry_point": ""}
        services = cfg.get("services")
        deployments = cfg.get("deployments")
        # Check for deployment hostname and Caddy
        caddy_deployment = None
        for dep_name, dep in (deployments or {}).items():
            if dep.get("hostname") and not hostname:
                hostname = dep["hostname"]
                swarm = dep.get("swarm", False)
            if dep.get("reverse_proxy") == "caddy" and not caddy_deployment:
                caddy_deployment = dep_name

        # --hostname flag overrides config
        if getattr(args, "hostname", None):
            hostname = args.hostname

        # Warn if Caddy detected but no hostname
        if caddy_deployment and not hostname:
            print(f"Caddy detected on deployment '{caddy_deployment}' — pass --hostname to include reverse proxy labels")
    except ConfigError:
        pass

    result = generators.init_docker(
        project_dir, app_name, framework, services, hostname, swarm,
        deployments,
    )
    if "error" in result:
        _error(result["error"], args.json)
    _output(result, args.json)


# ---------------------------------------------------------------------------
# Lifecycle commands: build, up, down, logs
# ---------------------------------------------------------------------------

def _resolve_deployment(name: str, as_json: bool) -> tuple[dict, dict] | None:
    """Load config and find a deployment by name. Returns (cfg, deploy_cfg) or exits."""
    from rundbat import config
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(f"Cannot load config: {e}", as_json)
        return None

    deployments = cfg.get("deployments", {})
    if name not in deployments:
        available = ", ".join(deployments.keys()) if deployments else "none"
        _error(f"Deployment '{name}' not found. Available: {available}", as_json)
        return None

    return cfg, deployments[name]


def _compose_file_for_deployment(name: str, dep_cfg: dict) -> Path:
    """Return the compose file path for a deployment from its config."""
    return Path(dep_cfg.get("compose_file", f"docker/docker-compose.{name}.yml"))


def _checkout_config(name: str, dep_cfg: dict, verbose: bool = False) -> None:
    """Load env from dotconfig and write to the deployment's env file.

    Reads config_deployment (defaults to name) from dotconfig and writes
    it to docker/.<name>.env. No-op if env_source is not dotconfig.
    """
    env_source = dep_cfg.get("env_source")
    if env_source != "dotconfig":
        return

    from rundbat import config
    from rundbat.config import ConfigError

    config_deployment = dep_cfg.get("config_deployment", name)
    env_path = Path("docker") / f".{name}.env"

    try:
        env_content = config.load_env(config_deployment)
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(env_content)
        if verbose:
            print(f"  config: dotconfig load -d {config_deployment} → {env_path}", file=sys.stderr)
    except ConfigError as e:
        print(f"  Warning: Could not load dotconfig env for {config_deployment}: {e}", file=sys.stderr)


def cmd_build(args):
    """Build images for a deployment."""
    verbose = getattr(args, "verbose", False)

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = dep_cfg.get("deploy_mode", "compose")
    build_strategy = dep_cfg.get("build_strategy", "context")

    # github-actions strategy: trigger build via gh CLI
    if build_strategy == "github-actions":
        from rundbat.discovery import detect_gh
        from rundbat.deploy import _get_github_repo, DeployError

        gh = detect_gh()
        if not gh["installed"]:
            _error("GitHub CLI (gh) is not installed. Install from https://cli.github.com/", args.json)
            return
        if not gh["authenticated"]:
            _error("GitHub CLI is not authenticated. Run 'gh auth login' first.", args.json)
            return

        try:
            repo = _get_github_repo()
        except DeployError as e:
            _error(str(e), args.json)
            return

        cmd = ["gh", "workflow", "run", "build.yml", "--repo", repo]
        result = _run_cmd(cmd, verbose=verbose, capture_output=True, text=True)
        if result.returncode != 0:
            _error(f"Failed to trigger build: {result.stderr.strip()}", args.json)
            return

        if args.json:
            _output({"status": "triggered", "repo": repo, "workflow": "build.yml"}, True)
        else:
            print(f"Build triggered on GitHub Actions for {args.name}")
            print(f"  Watch: gh run watch --repo {repo}")
        return

    # Local build via docker compose
    if deploy_mode == "run":
        _error(f"Deployment '{args.name}' uses run mode — no local build. Use 'rundbat build' with github-actions strategy.", args.json)
        return

    compose_file = _compose_file_for_deployment(args.name, dep_cfg)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    ctx = dep_cfg.get("docker_context", "default")
    env = {**os.environ}
    if ctx:
        env["DOCKER_CONTEXT"] = ctx

    cmd = ["docker", "compose", "-f", str(compose_file), "build"]
    result = _run_cmd(cmd, env=env, verbose=verbose)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _effective_deploy_mode(deployment: dict) -> str:
    """Return the deploy_mode to use, applying the swarm auto-upgrade rule.

    If ``deployment`` has an explicit ``deploy_mode``, return it
    unchanged. Otherwise, when ``swarm: true`` is recorded (by a
    probe or by the user), upgrade the default to ``stack``.
    """
    explicit = deployment.get("deploy_mode")
    if explicit:
        return str(explicit)
    if deployment.get("swarm") is True:
        return "stack"
    return "compose"


def _stack_name_from(cfg: dict, deployment_name: str, dep_cfg: dict) -> str:
    """Return the Swarm stack name, honouring an explicit ``stack_name``."""
    explicit = dep_cfg.get("stack_name")
    if explicit:
        return str(explicit)
    app_name = cfg.get("app_name", "app")
    return f"{app_name}_{deployment_name}"


def cmd_up(args):
    """Start a deployment."""
    verbose = getattr(args, "verbose", False)

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = _effective_deploy_mode(dep_cfg)
    build_strategy = dep_cfg.get("build_strategy", "context")
    ctx = dep_cfg.get("docker_context", "default")

    # --workflow flag: trigger deploy via GitHub Actions
    if getattr(args, "workflow", False):
        from rundbat.discovery import detect_gh
        from rundbat.deploy import _get_github_repo, DeployError

        gh = detect_gh()
        if not gh["installed"]:
            _error("GitHub CLI (gh) is not installed.", args.json)
            return
        if not gh["authenticated"]:
            _error("GitHub CLI is not authenticated. Run 'gh auth login'.", args.json)
            return

        try:
            repo = _get_github_repo()
        except DeployError as e:
            _error(str(e), args.json)
            return

        cmd = ["gh", "workflow", "run", "deploy.yml", "--repo", repo]
        result = _run_cmd(cmd, verbose=verbose, capture_output=True, text=True)
        if result.returncode != 0:
            _error(f"Failed to trigger deploy: {result.stderr.strip()}", args.json)
            return

        print(f"Deploy workflow triggered for {args.name}")
        print(f"  Watch: gh run watch --repo {repo}")
        return

    # Checkout config from dotconfig
    _checkout_config(args.name, dep_cfg, verbose=verbose)

    # Run mode
    if deploy_mode == "run":
        from rundbat.deploy import _deploy_run, DeployError
        try:
            result = _deploy_run(args.name, dep_cfg, cfg.get("app_name", "app"),
                                 dry_run=False)
            _output(result, args.json)
        except DeployError as e:
            _error(str(e), args.json)
        return

    # Stack mode — Docker Swarm
    if deploy_mode == "stack":
        compose_file = _compose_file_for_deployment(args.name, dep_cfg)
        if not compose_file.exists():
            _error(f"{compose_file} not found. Run 'rundbat generate' first.",
                   args.json)
            return
        stack = _stack_name_from(cfg, args.name, dep_cfg)
        cmd = ["docker", "--context", ctx, "stack", "deploy",
               "-c", str(compose_file), stack]
        result = _run_cmd(cmd, verbose=verbose)
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    # Compose mode
    compose_file = _compose_file_for_deployment(args.name, dep_cfg)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    env = {**os.environ}
    if ctx:
        env["DOCKER_CONTEXT"] = ctx

    # Pull first for github-actions strategy
    if build_strategy == "github-actions":
        _run_cmd(
            ["docker", "compose", "-f", str(compose_file), "pull"],
            env=env, verbose=verbose,
        )

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    result = _run_cmd(cmd, env=env, verbose=verbose)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_down(args):
    """Stop a deployment."""
    verbose = getattr(args, "verbose", False)

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = _effective_deploy_mode(dep_cfg)
    ctx = dep_cfg.get("docker_context", "default")
    app_name = cfg.get("app_name", "app")

    env = {**os.environ}
    if ctx:
        env["DOCKER_CONTEXT"] = ctx

    if deploy_mode == "run":
        _run_cmd(["docker", "stop", app_name], env=env, verbose=verbose, capture_output=True)
        _run_cmd(["docker", "rm", app_name], env=env, verbose=verbose, capture_output=True)
        print(f"Stopped {app_name}")
        return

    if deploy_mode == "stack":
        stack = _stack_name_from(cfg, args.name, dep_cfg)
        cmd = ["docker", "--context", ctx, "stack", "rm", stack]
        result = _run_cmd(cmd, verbose=verbose)
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    compose_file = _compose_file_for_deployment(args.name, dep_cfg)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
    result = _run_cmd(cmd, env=env, verbose=verbose)
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_logs(args):
    """Tail logs from a deployment."""
    verbose = getattr(args, "verbose", False)

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = _effective_deploy_mode(dep_cfg)
    ctx = dep_cfg.get("docker_context", "default")
    app_name = cfg.get("app_name", "app")

    env = {**os.environ}
    if ctx:
        env["DOCKER_CONTEXT"] = ctx

    if deploy_mode == "run":
        cmd = ["docker", "logs", "-f", app_name]
        _run_cmd(cmd, env=env, verbose=verbose)
        return

    if deploy_mode == "stack":
        stack = _stack_name_from(cfg, args.name, dep_cfg)
        # Services to tail: the app service plus any infra services
        # listed in the deployment entry. Default to ["app"] if none.
        service_types = dep_cfg.get("services") or []
        service_names = ["app"] + list(service_types)
        # Launch one `service logs -f` per service. If the caller only
        # wants the app we still default to that — multiplexing multiple
        # tails requires tee'ing, which we do not do here. For T05 we
        # tail the app service primarily; additional services are
        # reported for diagnostics.
        for svc in service_names:
            cmd = ["docker", "--context", ctx, "service", "logs", "-f",
                   f"{stack}_{svc}"]
            result = _run_cmd(cmd, verbose=verbose)
            # `service logs -f` blocks until interrupted. In practice
            # the loop only runs once; for tests we inspect the first
            # invocation. Break on success to avoid tailing N services
            # in sequence after Ctrl-C.
            if result.returncode == 0:
                return
        return

    compose_file = _compose_file_for_deployment(args.name, dep_cfg)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    cmd = ["docker", "compose", "-f", str(compose_file), "logs", "-f"]
    _run_cmd(cmd, env=env, verbose=verbose)


def _parse_env_text(text: str) -> dict:
    """Parse KEY=VALUE lines from a .env-style text into a dict.

    Ignores blank lines, comments, and malformed lines. Values keep
    their raw form (no unquoting) — callers pipe them straight to
    Docker.
    """
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value
    return result


def cmd_secret_create(args):
    """Create (or rotate) a Swarm secret from a dotconfig-backed value.

    Usage: ``rundbat secret create <env> <KEY>``

    Reads ``KEY`` from the deployment's dotconfig env bundle, computes
    the versioned Swarm secret name (``<app>_<key_lc>_v<YYYYMMDD>``),
    and pipes the value into ``docker --context <ctx> secret create
    <name> -`` on stdin.
    """
    from datetime import datetime, timezone
    from rundbat import config
    from rundbat.config import ConfigError

    try:
        cfg = config.load_config()
    except ConfigError as e:
        _error(str(e), args.json)
        return

    deployments = cfg.get("deployments", {})
    env_name = args.env
    if env_name not in deployments:
        _error(f"Deployment '{env_name}' not found in rundbat.yaml", args.json)
        return

    dep = deployments[env_name]
    ctx = dep.get("docker_context")
    if not ctx:
        _error(f"Deployment '{env_name}' has no docker_context", args.json)
        return

    key = args.key
    try:
        env_text = config.load_env(env_name)
    except ConfigError as e:
        _error(f"Failed to load dotconfig env for '{env_name}': {e}", args.json)
        return

    env_map = _parse_env_text(env_text)
    if key not in env_map:
        _error(f"Key '{key}' not found in dotconfig env for '{env_name}'", args.json)
        return

    value = env_map[key]

    app_name = cfg.get("app_name", "app")
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    secret_name = f"{app_name}_{key.lower()}_v{date_stamp}"

    cmd = ["docker", "--context", ctx, "secret", "create", secret_name, "-"]
    result = _run_cmd_stdin(cmd, stdin_value=value,
                            verbose=getattr(args, "verbose", False))
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() if hasattr(result, "stderr") else ""
        _error(
            f"docker secret create failed (exit {result.returncode}): {stderr}",
            args.json,
        )
        return

    _output({"secret_name": secret_name, "deployment": env_name,
             "docker_context": ctx}, args.json)


def _run_cmd_stdin(cmd: list[str], *, stdin_value: str, verbose: bool = False):
    """Run a subprocess command, piping a string into stdin.

    Returns a ``CompletedProcess`` with ``stdout``/``stderr`` captured.
    """
    import subprocess
    if verbose:
        print(f"  $ {' '.join(cmd)}  (stdin redacted)", file=sys.stderr)
    return subprocess.run(
        cmd,
        input=stdin_value,
        capture_output=True,
        text=True,
    )


def cmd_restart(args):
    """Restart a deployment: down then up. With --build: build, down, up."""
    verbose = getattr(args, "verbose", False)

    resolved = _resolve_deployment(args.name, args.json)
    if not resolved:
        return
    cfg, dep_cfg = resolved

    deploy_mode = _effective_deploy_mode(dep_cfg)
    build_strategy = dep_cfg.get("build_strategy", "context")
    ctx = dep_cfg.get("docker_context", "default")
    app_name = cfg.get("app_name", "app")

    env = {**os.environ}
    if ctx:
        env["DOCKER_CONTEXT"] = ctx

    # Checkout config from dotconfig
    _checkout_config(args.name, dep_cfg, verbose=verbose)

    if deploy_mode == "stack":
        # Stack restart = rm + deploy. --build reuses docker compose
        # build (build is not a stack op).
        compose_file = _compose_file_for_deployment(args.name, dep_cfg)
        if not compose_file.exists():
            _error(f"{compose_file} not found. Run 'rundbat generate' first.",
                   args.json)
            return
        stack = _stack_name_from(cfg, args.name, dep_cfg)
        if getattr(args, "build", False) and build_strategy != "github-actions":
            build_cmd = ["docker", "compose", "-f", str(compose_file), "build"]
            result = _run_cmd(build_cmd, env=env, verbose=verbose)
            if result.returncode != 0:
                sys.exit(result.returncode)
        _run_cmd(["docker", "--context", ctx, "stack", "rm", stack],
                 verbose=verbose, capture_output=True)
        deploy_cmd = ["docker", "--context", ctx, "stack", "deploy",
                      "-c", str(compose_file), stack]
        result = _run_cmd(deploy_cmd, verbose=verbose)
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    if deploy_mode == "run":
        # Build not applicable for run mode
        if getattr(args, "build", False):
            print("Note: --build ignored for run-mode deployments", file=sys.stderr)
        _run_cmd(["docker", "stop", app_name], env=env, verbose=verbose, capture_output=True)
        _run_cmd(["docker", "rm", app_name], env=env, verbose=verbose, capture_output=True)
        # Re-use cmd_up logic for run mode
        from rundbat.deploy import _deploy_run, DeployError
        try:
            result = _deploy_run(args.name, dep_cfg, app_name, dry_run=False)
            _output(result, args.json)
        except DeployError as e:
            _error(str(e), args.json)
        return

    # Compose mode
    compose_file = _compose_file_for_deployment(args.name, dep_cfg)
    if not compose_file.exists():
        _error(f"{compose_file} not found. Run 'rundbat generate' first.", args.json)
        return

    # Build if requested
    if getattr(args, "build", False):
        cmd = ["docker", "compose", "-f", str(compose_file), "build"]
        result = _run_cmd(cmd, env=env, verbose=verbose)
        if result.returncode != 0:
            sys.exit(result.returncode)

    # Down
    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
    result = _run_cmd(cmd, env=env, verbose=verbose)
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Pull for github-actions strategy
    if build_strategy == "github-actions":
        _run_cmd(
            ["docker", "compose", "-f", str(compose_file), "pull"],
            env=env, verbose=verbose,
        )

    # Up
    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    result = _run_cmd(cmd, env=env, verbose=verbose)
    if result.returncode != 0:
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list[str], env: dict | None = None, verbose: bool = False,
             **kwargs) -> "subprocess.CompletedProcess":
    """Run a subprocess command, printing the shell line when verbose."""
    import subprocess
    if verbose:
        prefix = ""
        if env and "DOCKER_CONTEXT" in env:
            prefix = f"DOCKER_CONTEXT={env['DOCKER_CONTEXT']} "
        print(f"  $ {prefix}{' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, env=env, **kwargs)


def _add_json_flag(parser):
    """Add --json flag to a subparser."""
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )


_AGENT_INSTRUCTIONS_HEAD = """\
rundbat — Instructions for Agents
=================================

What rundbat is
---------------
rundbat is a CLI that manages Docker-based deployment environments for
web applications. It is the authoritative tool for anything involving:

  - Docker Compose lifecycle (build, up, down, restart, logs)
  - Deployment to remote Docker hosts (via Docker contexts or SSH)
  - Per-deployment environment/config, including SOPS-encrypted secrets
  - Generating the project's docker/ directory (Dockerfile, compose files)
  - Database provisioning and connection strings

If a task mentions "deployment", "Docker", "compose", "env vars", "secrets",
or "connection string", reach for rundbat first. Do not hand-edit
docker-compose files or config/ files — regenerate or go through dotconfig.

Core workflow
-------------
1. `rundbat init` once per project — creates config/rundbat.yaml, a .gitignore
   rule for per-deployment env files, inserts a rundbat block into CLAUDE.md,
   and installs reference docs into .claude/.
2. `rundbat generate` — regenerates docker/ artifacts from rundbat.yaml.
   Re-run any time you edit rundbat.yaml or add a deployment.
3. `rundbat up <name>` / `down <name>` / `restart <name>` — local lifecycle.
   `up` automatically checks out env from dotconfig into docker/.<name>.env.
4. `rundbat deploy-init <name> --host ssh://...` — register a remote target.
5. `rundbat deploy <name>` — deploy to the remote (context / ssh-transfer /
   github-actions strategy, configured per deployment).

Deployment names (dev, test, prod, or custom) are the primary argument to
almost every subcommand. They must exist under `deployments:` in rundbat.yaml.

Configuration model
-------------------
All config goes through dotconfig — never edit config/ files by hand.

  config/
    rundbat.yaml         # App name, container templates, deployments map
    <env>/public.env     # Non-secret env vars
    <env>/secrets.env    # SOPS-encrypted secrets

Read merged config:  dotconfig load -d <env> --json --flat -S
Write secrets:       dotconfig set -d <env> KEY=VALUE
rundbat `up` and `restart` check out the merged env into
docker/.<name>.env automatically (see `env_source: dotconfig`).

Build strategies (set per-deployment in rundbat.yaml):
  context         — build on the remote Docker context (default)
  ssh-transfer    — build locally with --platform, rsync images over SSH
  github-actions  — CI builds to GHCR, remote pulls
"""


_AGENT_INSTRUCTIONS_TAIL = """\
Rules for agents
----------------
  - Do not edit config/ files directly. Use dotconfig.
  - Do not hand-edit docker/docker-compose.*.yml. Edit rundbat.yaml and
    re-run `rundbat generate`.
  - Do not echo secret values in output or commit them.
  - Most commands accept `--json` for parseable output.
  - Pass `-v` / `--verbose` to see the shell commands rundbat runs.

Subcommand reference (compiled from each `rundbat <cmd> --help`)
----------------------------------------------------------------
"""


_SKILL_DESCRIPTIONS = {
    "astro-docker.md": "Dockerizing Astro projects",
    "deploy-init.md": "walk through setting up a remote target",
    "deploy-setup.md": "guided remote deploy configuration",
    "dev-database.md": "provisioning a local dev DB",
    "diagnose.md": "triaging broken containers / deploys",
    "docker-best-practices.md": "Docker Build Best Practices checklist and what rundbat enforces",
    "docker-secrets.md": "decision framework for Docker secrets (Swarm vs plain vs build)",
    "docker-secrets-swarm.md": "Swarm runtime secrets — create, attach, rotate, version",
    "docker-secrets-compose.md": "plain-Docker file-mounted secrets and migration from env_file",
    "docker-secrets-build.md": "BuildKit `--secret` for build-time credentials",
    "generate.md": "regenerating docker/ artifacts",
    "github-deploy.md": "github-actions build strategy",
    "init-docker.md": "initial docker/ scaffolding",
    "manage-secrets.md": "adding, rotating, reading secrets (dotconfig — source of truth)",
}


def _installed_integration_section() -> str:
    """Build the 'Installed Claude integration' section from the install map.

    Paths are pulled from installer.installed_paths_by_kind() so they always
    match what `rundbat init` actually writes to disk.
    """
    from rundbat.installer import installed_paths_by_kind

    groups = installed_paths_by_kind()
    lines = [
        "Installed Claude integration",
        "----------------------------",
        "`rundbat init` installs reference docs into the project's .claude/",
        "directory and inserts a rundbat block into CLAUDE.md. The files below",
        "are on disk right now — read them for deeper, task-specific guidance.",
        "",
    ]

    if groups["rules"]:
        lines.append("Rules:")
        for p in groups["rules"]:
            lines.append(f"  {p}")
        lines.append("")

    if groups["agents"]:
        lines.append("Agents:")
        for p in groups["agents"]:
            lines.append(f"  {p}")
        lines.append("")

    if groups["skills"]:
        lines.append("Skills (task-specific runbooks):")
        for p in groups["skills"]:
            name = p.rsplit("/", 1)[-1]
            desc = _SKILL_DESCRIPTIONS.get(name)
            if desc:
                lines.append(f"  {p} — {desc}")
            else:
                lines.append(f"  {p}")
        lines.append("")

    lines.append("When in doubt about a specific task, read the matching skill file first.")
    lines.append("")
    return "\n".join(lines)


def _print_instructions(subparsers_action) -> None:
    """Print detailed agent instructions, then every subcommand's help."""
    print(_AGENT_INSTRUCTIONS_HEAD)
    print(_installed_integration_section())
    print(_AGENT_INSTRUCTIONS_TAIL)
    for name in sorted(subparsers_action.choices.keys()):
        subparser = subparsers_action.choices[name]
        print(f"----- rundbat {name} -----")
        print()
        print(subparser.format_help())


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rundbat",
        description="Deployment Expert — manage Docker-based dev environments",
        epilog="""\
Commands:
  rundbat init               Set up rundbat in your project
  rundbat generate           Generate Docker artifacts from config
  rundbat build <name>       Build images for a deployment
  rundbat up <name>          Start a deployment
  rundbat down <name>        Stop a deployment
  rundbat restart <name>     Restart (down + up; --build to rebuild first)
  rundbat logs <name>        Tail logs from a deployment
  rundbat deploy <name>      Deploy to a remote host
  rundbat deploy-init <name> Set up a deployment target

Attention agents: For agents, run `rundbat --instructions` to get detailed
instructions on using this tool.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"rundbat {__version__}",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Print shell commands before executing them",
    )
    parser.add_argument(
        "--instructions", action="store_true", default=False,
        help="Print detailed instructions for agents (includes all subcommand help)",
    )
    subparsers = parser.add_subparsers(dest="command")

    # rundbat init
    init_parser = subparsers.add_parser(
        "init", help="Set up rundbat in the current project",
    )
    init_parser.add_argument(
        "--app-name",
        help="Application name (auto-detected if not provided)",
    )
    init_parser.add_argument(
        "--force", action="store_true", default=False,
        help="Overwrite rundbat.yaml even if it already exists",
    )
    init_parser.set_defaults(func=cmd_init)

    # rundbat generate
    generate_parser = subparsers.add_parser(
        "generate", help="Generate Docker artifacts from rundbat.yaml config",
    )
    generate_parser.add_argument(
        "--deployment", default=None,
        help="Regenerate only this deployment (default: all)",
    )
    _add_json_flag(generate_parser)
    generate_parser.set_defaults(func=cmd_generate)

    # rundbat init-docker (deprecated)
    init_docker_parser = subparsers.add_parser(
        "init-docker", help="(Deprecated) Use 'rundbat generate' instead",
    )
    init_docker_parser.add_argument(
        "--hostname",
        default=None,
        help="App hostname for Caddy reverse proxy labels (e.g. app.example.com)",
    )
    _add_json_flag(init_docker_parser)
    init_docker_parser.set_defaults(func=cmd_init_docker)

    # rundbat build <name>
    build_parser = subparsers.add_parser(
        "build", help="Build images for a deployment",
    )
    build_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(build_parser)
    build_parser.set_defaults(func=cmd_build)

    # rundbat up <name>
    up_parser = subparsers.add_parser(
        "up", help="Start a deployment (pull/build + start containers)",
    )
    up_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    up_parser.add_argument(
        "--workflow", action="store_true", default=False,
        help="Trigger deploy via GitHub Actions workflow instead of local Docker",
    )
    _add_json_flag(up_parser)
    up_parser.set_defaults(func=cmd_up)

    # rundbat down <name>
    down_parser = subparsers.add_parser(
        "down", help="Stop a deployment",
    )
    down_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(down_parser)
    down_parser.set_defaults(func=cmd_down)

    # rundbat logs <name>
    logs_parser = subparsers.add_parser(
        "logs", help="Tail logs from a deployment",
    )
    logs_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    _add_json_flag(logs_parser)
    logs_parser.set_defaults(func=cmd_logs)

    # rundbat restart <name>
    restart_parser = subparsers.add_parser(
        "restart", help="Restart a deployment (down + up)",
    )
    restart_parser.add_argument(
        "name", help="Deployment name (e.g., dev, prod)",
    )
    restart_parser.add_argument(
        "--build", action="store_true", default=False,
        help="Build images before restarting (build + down + up)",
    )
    _add_json_flag(restart_parser)
    restart_parser.set_defaults(func=cmd_restart)

    # rundbat deploy <name>
    deploy_parser = subparsers.add_parser(
        "deploy", help="Deploy to a named remote host via Docker context",
    )
    deploy_parser.add_argument(
        "name", help="Deployment name (e.g., prod, staging)",
    )
    deploy_parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Show the command without executing",
    )
    deploy_parser.add_argument(
        "--no-build", action="store_true", default=False,
        help="Skip the --build flag (context strategy only)",
    )
    deploy_parser.add_argument(
        "--strategy", default=None,
        choices=["context", "ssh-transfer", "github-actions"],
        help="Override the configured build strategy",
    )
    deploy_parser.add_argument(
        "--platform", default=None,
        help="Override the target platform (e.g., linux/amd64)",
    )
    _add_json_flag(deploy_parser)
    deploy_parser.set_defaults(func=cmd_deploy)

    # rundbat deploy-init <name> --host <ssh://user@host>
    deploy_init_parser = subparsers.add_parser(
        "deploy-init", help="Set up a new deployment target",
    )
    deploy_init_parser.add_argument(
        "name", help="Deployment name (e.g., prod, staging)",
    )
    deploy_init_parser.add_argument(
        "--host", required=True,
        help="SSH URL for the remote Docker host (e.g., ssh://root@host)",
    )
    deploy_init_parser.add_argument(
        "--compose-file",
        help="Path to compose file (default: docker/docker-compose.yml)",
    )
    deploy_init_parser.add_argument(
        "--hostname",
        help="App hostname for post-deploy message (e.g., app.example.com)",
    )
    deploy_init_parser.add_argument(
        "--strategy", default=None,
        choices=["context", "ssh-transfer", "github-actions"],
        help="Build strategy for this deployment",
    )
    deploy_init_parser.add_argument(
        "--deploy-mode", default=None,
        choices=["compose", "run", "stack"],
        help="Deploy mode: compose (default), run (single container), or stack (Swarm)",
    )
    deploy_init_parser.add_argument(
        "--image", default=None,
        help="Registry image reference (e.g., ghcr.io/owner/repo) for run mode",
    )
    deploy_init_parser.add_argument(
        "--ssh-key", default=None,
        help="Path to SSH private key for this deployment (e.g., config/prod/app-deploy-key)",
    )
    _add_json_flag(deploy_init_parser)
    deploy_init_parser.set_defaults(func=cmd_deploy_init)

    # rundbat probe <name>
    probe_parser = subparsers.add_parser(
        "probe", help="Detect reverse proxy on a deployment target",
    )
    probe_parser.add_argument(
        "name", help="Deployment name (from rundbat.yaml)",
    )
    _add_json_flag(probe_parser)
    probe_parser.set_defaults(func=cmd_probe)

    # rundbat secret <subcommand>
    secret_parser = subparsers.add_parser(
        "secret", help="Manage Docker Swarm secrets from dotconfig values",
    )
    secret_sub = secret_parser.add_subparsers(dest="secret_command")
    secret_create_parser = secret_sub.add_parser(
        "create",
        help="Create a versioned Swarm secret from a dotconfig value",
    )
    secret_create_parser.add_argument(
        "env", help="Deployment name (from rundbat.yaml)",
    )
    secret_create_parser.add_argument(
        "key", help="Secret key name as stored in dotconfig (e.g., POSTGRES_PASSWORD)",
    )
    _add_json_flag(secret_create_parser)
    secret_create_parser.set_defaults(func=cmd_secret_create)

    def _secret_default(args):
        secret_parser.print_help()
        sys.exit(0)
    secret_parser.set_defaults(func=_secret_default)

    args = parser.parse_args()

    if getattr(args, "instructions", False):
        _print_instructions(subparsers)
        sys.exit(0)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

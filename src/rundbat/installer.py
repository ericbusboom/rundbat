"""Project Installer — install/uninstall rundbat integration files.

Installs Claude Code integration files (skills, agents, rules) from the
bundled content directory into a target project's .claude/ directory.
Tracks installed files via a manifest for clean uninstall.

Also manages a fenced block in the project's CLAUDE.md that tells agents
the project uses rundbat and points them at `rundbat --instructions`.
"""

import hashlib
import json
from importlib import resources
from pathlib import Path

MANIFEST_PATH = ".claude/.rundbat-manifest.json"

CLAUDE_MD_PATH = "CLAUDE.md"
CLAUDE_MD_BEGIN = "<!-- RUNDBAT:START -->"
CLAUDE_MD_END = "<!-- RUNDBAT:END -->"


def _content_dir() -> Path:
    """Return the path to the bundled content directory."""
    return Path(resources.files("rundbat") / "content")


def _checksum(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_map() -> dict[str, str]:
    """Return a mapping of source content paths to target install paths.

    Keys are relative to the content directory; values are relative to the
    project root.
    """
    content = _content_dir()
    mapping = {}

    # Skills → .claude/skills/rundbat/
    skills_dir = content / "skills"
    if skills_dir.is_dir():
        for f in sorted(skills_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                mapping[f"skills/{f.name}"] = f".claude/skills/rundbat/{f.name}"

    # Agents → .claude/agents/
    agents_dir = content / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                mapping[f"agents/{f.name}"] = f".claude/agents/{f.name}"

    # Rules → .claude/rules/
    rules_dir = content / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                mapping[f"rules/{f.name}"] = f".claude/rules/{f.name}"

    return mapping


def installed_paths_by_kind() -> dict[str, list[str]]:
    """Return installed destination paths grouped by kind.

    Keys are 'rules', 'agents', 'skills'; values are lists of project-relative
    paths. Paths reflect what `install()` actually writes — if the content
    directory changes, both `--instructions` and the CLAUDE.md block track it.
    """
    mapping = _install_map()
    groups: dict[str, list[str]] = {"rules": [], "agents": [], "skills": []}
    for src_rel, dest_rel in mapping.items():
        kind = src_rel.split("/", 1)[0]
        if kind in groups:
            groups[kind].append(dest_rel)
    for kind in groups:
        groups[kind].sort()
    return groups


def _claude_md_body() -> str:
    """Build the body of the rundbat CLAUDE.md block.

    The "Reference files" section is generated from `_install_map()` so it
    stays in sync with whatever `rundbat init` actually installs.
    """
    groups = installed_paths_by_kind()

    ref_lines = [
        "### Reference files",
        "",
        "`rundbat init` installs these files into `.claude/` for task-specific",
        "guidance. Read them directly, or run `rundbat --instructions` for a",
        "consolidated view that also dumps every subcommand's help text.",
        "",
    ]
    if groups["rules"]:
        ref_lines.append("Rules:")
        ref_lines.extend(f"- `{p}`" for p in groups["rules"])
        ref_lines.append("")
    if groups["agents"]:
        ref_lines.append("Agents:")
        ref_lines.extend(f"- `{p}`" for p in groups["agents"])
        ref_lines.append("")
    if groups["skills"]:
        ref_lines.append("Skills (task-specific runbooks):")
        ref_lines.extend(f"- `{p}`" for p in groups["skills"])
        ref_lines.append("")
    references = "\n".join(ref_lines)

    return f"""\
## rundbat — Deployment Expert

This project uses **rundbat** to manage Docker-based deployment
environments. rundbat handles Docker Compose generation, per-deployment
environment config (via dotconfig), secret management, and deployment
to remote Docker hosts.

**If a task involves Docker containers, docker-compose, deployment,
environment variables, secrets, or connection strings — use rundbat.**

Run `rundbat --instructions` for detailed agent-oriented instructions,
including the full help text for every subcommand. `rundbat --help`
shows the command list.

### Common commands

| Command | Purpose |
|---|---|
| `rundbat init` | Set up rundbat in a project |
| `rundbat generate` | Generate Docker artifacts from `config/rundbat.yaml` |
| `rundbat up <env>` | Start a deployment (checks out env from dotconfig) |
| `rundbat down <env>` | Stop a deployment |
| `rundbat restart <env>` | Restart (down + up; `--build` to rebuild) |
| `rundbat logs <env>` | Tail container logs |
| `rundbat deploy <env>` | Deploy to a remote Docker host |
| `rundbat deploy-init <env> --host ssh://...` | Register a remote target |

Most commands support `--json` for machine-parseable output, and `-v`
to print the shell commands they run.

### Configuration

Configuration is managed by dotconfig — **never edit `config/` files
or `docker/docker-compose.*.yml` directly**. Edit `config/rundbat.yaml`
and re-run `rundbat generate`; use `dotconfig` for env vars and secrets.

Read merged config: `dotconfig load -d <env> --json --flat -S`

Key locations:
- `config/rundbat.yaml` — Project-wide config (app name, deployments)
- `config/{{env}}/public.env` — Non-secret environment variables
- `config/{{env}}/secrets.env` — SOPS-encrypted credentials

{references}"""


def claude_md_block() -> str:
    """Return the full fenced CLAUDE.md block (markers + body)."""
    return f"{CLAUDE_MD_BEGIN}\n{_claude_md_body()}{CLAUDE_MD_END}\n"


def install_claude_md_block(project_dir: Path) -> dict:
    """Insert or update the rundbat fenced block in CLAUDE.md.

    Idempotent. If the `<!-- RUNDBAT:START -->` / `<!-- RUNDBAT:END -->`
    markers exist, the block between them is replaced. Otherwise the
    block is appended. Creates CLAUDE.md if it doesn't exist.

    Returns dict with the path and the action taken.
    """
    project_dir = Path(project_dir)
    claude_md = project_dir / CLAUDE_MD_PATH
    existing = claude_md.read_text() if claude_md.exists() else ""
    block = claude_md_block()

    begin = existing.find(CLAUDE_MD_BEGIN)
    end = existing.find(CLAUDE_MD_END)

    if begin != -1 and end != -1 and end > begin:
        end_of_block = end + len(CLAUDE_MD_END)
        # Consume a trailing newline after the end marker if present,
        # so we don't accumulate blank lines across re-installs.
        if end_of_block < len(existing) and existing[end_of_block] == "\n":
            end_of_block += 1
        new_content = existing[:begin] + block + existing[end_of_block:]
        action = "updated"
    else:
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        new_content = prefix + block
        action = "inserted" if existing else "created"

    claude_md.write_text(new_content)
    return {"path": str(claude_md), "action": action}


def uninstall_claude_md_block(project_dir: Path) -> dict:
    """Remove the rundbat fenced block from CLAUDE.md if present.

    Leaves the rest of CLAUDE.md intact. No-op if the markers are not
    found or CLAUDE.md doesn't exist.
    """
    project_dir = Path(project_dir)
    claude_md = project_dir / CLAUDE_MD_PATH
    if not claude_md.exists():
        return {"path": str(claude_md), "action": "missing"}

    existing = claude_md.read_text()
    begin = existing.find(CLAUDE_MD_BEGIN)
    end = existing.find(CLAUDE_MD_END)
    if begin == -1 or end == -1 or end <= begin:
        return {"path": str(claude_md), "action": "not_present"}

    end_of_block = end + len(CLAUDE_MD_END)
    if end_of_block < len(existing) and existing[end_of_block] == "\n":
        end_of_block += 1
    # Trim a blank line immediately before the block if it exists, so we
    # don't leave a double blank behind.
    prefix = existing[:begin]
    if prefix.endswith("\n\n"):
        prefix = prefix[:-1]
    new_content = prefix + existing[end_of_block:]
    claude_md.write_text(new_content)
    return {"path": str(claude_md), "action": "removed"}


def install(project_dir: Path) -> dict:
    """Install all rundbat integration files into the target project.

    Copies bundled content files to .claude/ subdirectories, inserts the
    rundbat block into CLAUDE.md, and writes a manifest for uninstall
    tracking. Idempotent — re-running updates files and manifest.

    Returns dict with installed file paths, CLAUDE.md action, and
    manifest location.
    """
    project_dir = Path(project_dir)
    content = _content_dir()
    mapping = _install_map()
    manifest = {"files": {}, "version": "1"}
    results = []

    for src_rel, dest_rel in mapping.items():
        src = content / src_rel
        dest = project_dir / dest_rel

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text())

        manifest["files"][dest_rel] = _checksum(dest)
        results.append({"file": dest_rel, "action": "installed"})

    claude_md_result = install_claude_md_block(project_dir)

    # Write manifest
    manifest_path = project_dir / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return {
        "installed": results,
        "claude_md": claude_md_result,
        "manifest": str(manifest_path),
    }


def uninstall(project_dir: Path) -> dict:
    """Remove all rundbat integration files tracked by the manifest.

    Reads the manifest, deletes each listed file, then deletes the
    manifest itself. Does not remove empty directories.

    Returns dict with removed file paths.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / MANIFEST_PATH

    if not manifest_path.exists():
        return {"warning": "No manifest found — nothing to uninstall."}

    manifest = json.loads(manifest_path.read_text())
    removed = []

    for file_rel in manifest.get("files", {}):
        file_path = project_dir / file_rel
        if file_path.exists():
            file_path.unlink()
            removed.append(file_rel)

    claude_md_result = uninstall_claude_md_block(project_dir)

    manifest_path.unlink()
    return {"removed": removed, "claude_md": claude_md_result, "manifest": "deleted"}

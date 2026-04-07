"""Project Installer — install/uninstall rundbat integration files.

Installs Claude Code integration files (skills, agents, rules) from the
bundled content directory into a target project's .claude/ directory.
Tracks installed files via a manifest for clean uninstall.
"""

import hashlib
import json
from importlib import resources
from pathlib import Path

MANIFEST_PATH = ".claude/.rundbat-manifest.json"


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


def install(project_dir: Path) -> dict:
    """Install all rundbat integration files into the target project.

    Copies bundled content files to .claude/ subdirectories and writes
    a manifest for uninstall tracking. Idempotent — re-running updates
    files and manifest.

    Returns dict with installed file paths and actions taken.
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

    # Write manifest
    manifest_path = project_dir / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return {"installed": results, "manifest": str(manifest_path)}


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

    manifest_path.unlink()
    return {"removed": removed, "manifest": "deleted"}

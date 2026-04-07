"""Tests for the Project Installer (manifest-based install/uninstall)."""

import json
from pathlib import Path

from rundbat.installer import install, uninstall, MANIFEST_PATH


class TestInstall:
    """Tests for rundbat install."""

    def test_creates_files(self, tmp_path):
        result = install(tmp_path)
        installed = [item["file"] for item in result["installed"]]
        assert ".claude/skills/rundbat/dev-database.md" in installed
        assert ".claude/skills/rundbat/diagnose.md" in installed
        assert ".claude/skills/rundbat/init-docker.md" in installed
        assert ".claude/skills/rundbat/manage-secrets.md" in installed
        assert ".claude/agents/deployment-expert.md" in installed
        assert ".claude/rules/rundbat.md" in installed

    def test_files_exist_on_disk(self, tmp_path):
        install(tmp_path)
        assert (tmp_path / ".claude" / "skills" / "rundbat" / "dev-database.md").exists()
        assert (tmp_path / ".claude" / "agents" / "deployment-expert.md").exists()
        assert (tmp_path / ".claude" / "rules" / "rundbat.md").exists()

    def test_creates_manifest(self, tmp_path):
        install(tmp_path)
        manifest_path = tmp_path / MANIFEST_PATH
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "files" in manifest
        assert len(manifest["files"]) >= 6

    def test_manifest_has_checksums(self, tmp_path):
        install(tmp_path)
        manifest = json.loads((tmp_path / MANIFEST_PATH).read_text())
        for path, checksum in manifest["files"].items():
            assert len(checksum) == 64  # SHA-256 hex

    def test_idempotent(self, tmp_path):
        result1 = install(tmp_path)
        result2 = install(tmp_path)
        assert len(result1["installed"]) == len(result2["installed"])
        # Files should still exist and manifest should be valid
        manifest = json.loads((tmp_path / MANIFEST_PATH).read_text())
        assert len(manifest["files"]) >= 6

    def test_rules_content(self, tmp_path):
        install(tmp_path)
        rules = (tmp_path / ".claude" / "rules" / "rundbat.md").read_text()
        assert "rundbat" in rules
        assert "dotconfig" in rules


class TestUninstall:
    """Tests for rundbat uninstall."""

    def test_removes_installed_files(self, tmp_path):
        install(tmp_path)
        result = uninstall(tmp_path)
        removed = result["removed"]
        assert ".claude/skills/rundbat/dev-database.md" in removed
        assert ".claude/agents/deployment-expert.md" in removed
        assert ".claude/rules/rundbat.md" in removed

    def test_files_deleted_from_disk(self, tmp_path):
        install(tmp_path)
        uninstall(tmp_path)
        assert not (tmp_path / ".claude" / "skills" / "rundbat" / "dev-database.md").exists()
        assert not (tmp_path / ".claude" / "agents" / "deployment-expert.md").exists()
        assert not (tmp_path / ".claude" / "rules" / "rundbat.md").exists()

    def test_manifest_deleted(self, tmp_path):
        install(tmp_path)
        uninstall(tmp_path)
        assert not (tmp_path / MANIFEST_PATH).exists()

    def test_no_manifest_warns(self, tmp_path):
        result = uninstall(tmp_path)
        assert "warning" in result

    def test_directories_preserved(self, tmp_path):
        install(tmp_path)
        # Add a non-rundbat file in .claude/
        other_file = tmp_path / ".claude" / "rules" / "other.md"
        other_file.write_text("keep me")

        uninstall(tmp_path)
        # Directories should still exist (other tools may use them)
        assert (tmp_path / ".claude" / "rules").is_dir()
        assert other_file.exists()

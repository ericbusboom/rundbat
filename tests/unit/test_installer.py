"""Tests for the Project Installer."""

import json
from pathlib import Path

from rundbat.installer import (
    install_mcp_config,
    install_rules,
    install_hooks,
    install_all,
    RUNDBAT_HOOK_COMMAND,
)


class TestInstallMcpConfig:
    """Tests for .mcp.json merging."""

    def test_creates_new_file(self, tmp_path):
        install_mcp_config(tmp_path)
        mcp_path = tmp_path / ".mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "rundbat" in data["mcpServers"]
        assert data["mcpServers"]["rundbat"]["command"] == "rundbat"

    def test_preserves_existing_servers(self, tmp_path):
        mcp_path = tmp_path / ".mcp.json"
        existing = {"mcpServers": {"clasi": {"command": "clasi", "args": ["mcp"]}}}
        mcp_path.write_text(json.dumps(existing))

        install_mcp_config(tmp_path)
        data = json.loads(mcp_path.read_text())
        assert "clasi" in data["mcpServers"]
        assert "rundbat" in data["mcpServers"]

    def test_updates_existing_entry(self, tmp_path):
        mcp_path = tmp_path / ".mcp.json"
        existing = {"mcpServers": {"rundbat": {"command": "old-rundbat"}}}
        mcp_path.write_text(json.dumps(existing))

        install_mcp_config(tmp_path)
        data = json.loads(mcp_path.read_text())
        assert data["mcpServers"]["rundbat"]["command"] == "rundbat"


class TestInstallRules:
    """Tests for .claude/rules/rundbat.md creation."""

    def test_creates_rule_file(self, tmp_path):
        install_rules(tmp_path)
        rule_path = tmp_path / ".claude" / "rules" / "rundbat.md"
        assert rule_path.exists()
        content = rule_path.read_text()
        assert "rundbat" in content
        assert "database" in content.lower()

    def test_creates_directories(self, tmp_path):
        install_rules(tmp_path)
        assert (tmp_path / ".claude" / "rules").is_dir()

    def test_overwrites_existing(self, tmp_path):
        rule_path = tmp_path / ".claude" / "rules" / "rundbat.md"
        rule_path.parent.mkdir(parents=True)
        rule_path.write_text("old content")

        install_rules(tmp_path)
        assert "old content" not in rule_path.read_text()


class TestInstallHooks:
    """Tests for .claude/settings.json hook merging."""

    def test_creates_new_settings(self, tmp_path):
        install_hooks(tmp_path)
        settings_path = tmp_path / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        assert len(hooks) == 1
        assert hooks[0]["command"] == RUNDBAT_HOOK_COMMAND

    def test_preserves_existing_hooks(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"
        existing = {
            "hooks": {
                "UserPromptSubmit": [
                    {"type": "command", "command": "echo 'CLASI: hello'"}
                ]
            }
        }
        settings_path.write_text(json.dumps(existing))

        install_hooks(tmp_path)
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        assert len(hooks) == 2
        commands = [h["command"] for h in hooks]
        assert "echo 'CLASI: hello'" in commands
        assert RUNDBAT_HOOK_COMMAND in commands

    def test_idempotent(self, tmp_path):
        install_hooks(tmp_path)
        install_hooks(tmp_path)
        settings_path = tmp_path / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        # Should not duplicate
        rundbat_hooks = [h for h in hooks if h.get("command") == RUNDBAT_HOOK_COMMAND]
        assert len(rundbat_hooks) == 1


class TestInstallAll:
    """Tests for the combined installer."""

    def test_installs_everything(self, tmp_path):
        result = install_all(tmp_path)
        assert "mcp_config" in result
        assert "rules" in result
        assert "hooks" in result
        assert (tmp_path / ".mcp.json").exists()
        assert (tmp_path / ".claude" / "rules" / "rundbat.md").exists()
        assert (tmp_path / ".claude" / "settings.json").exists()

    def test_idempotent(self, tmp_path):
        install_all(tmp_path)
        install_all(tmp_path)

        # Verify no duplicates
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert len(data["mcpServers"]) == 1

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert len(settings["hooks"]["UserPromptSubmit"]) == 1

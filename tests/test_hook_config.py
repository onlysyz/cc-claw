"""Tests for hook_config.py - settings.json hook injection/merge/cleanup."""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import hook_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_settings(dir: Path, data: dict):
    """Write a settings.json into a temp dir."""
    path = dir / "settings.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# _load_settings
# ---------------------------------------------------------------------------

class TestLoadSettings:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        with patch.object(hook_config, "SETTINGS_PATH", tmp_path / "nonexistent.json"):
            result = hook_config._load_settings()
            assert result == {}

    def test_valid_json_loaded(self, tmp_path):
        path = write_settings(tmp_path, {"hooks": {"Stop": []}})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config._load_settings()
            assert result == {"hooks": {"Stop": []}}

    def test_invalid_json_returns_empty_dict_with_warning(self, tmp_path):
        bad = tmp_path / "settings.json"
        bad.write_text("{ broken json")
        with patch.object(hook_config, "SETTINGS_PATH", bad):
            result = hook_config._load_settings()
            assert result == {}


# ---------------------------------------------------------------------------
# _save_settings
# ---------------------------------------------------------------------------

class TestSaveSettings:
    def test_saves_valid_json(self, tmp_path):
        path = tmp_path / "settings.json"
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config._save_settings({"key": "value"})
            result = json.loads(path.read_text())
            assert result == {"key": "value"}

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text('{"old": true}')
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config._save_settings({"new": True})
        assert json.loads(path.read_text()) == {"new": True}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "deep" / "settings.json"
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config._save_settings({"x": 1})
        assert path.exists()

    def test_uses_atomic_write(self, tmp_path):
        path = tmp_path / "settings.json"
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config._save_settings({"a": 1})
        assert not (tmp_path / "settings.json.tmp").exists()


# ---------------------------------------------------------------------------
# _backup_settings
# ---------------------------------------------------------------------------

class TestBackupSettings:
    def test_copies_to_bak_suffix(self, tmp_path):
        path = write_settings(tmp_path, {"hooks": {}})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config._backup_settings()
        assert (tmp_path / "settings.json.bak").exists()
        backup_content = json.loads((tmp_path / "settings.json.bak").read_text())
        assert backup_content == {"hooks": {}}

    def test_no_bak_when_missing(self, tmp_path):
        nonexistent = tmp_path / "nonexistent.json"
        with patch.object(hook_config, "SETTINGS_PATH", nonexistent):
            hook_config._backup_settings()  # should not raise
        assert not (tmp_path / "nonexistent.json.bak").exists()


# ---------------------------------------------------------------------------
# get_hook_port
# ---------------------------------------------------------------------------

class TestGetHookPort:
    def test_reads_from_port_file(self, tmp_path):
        config_dir = tmp_path / ".config" / "cc-claw"
        config_dir.mkdir(parents=True)
        (config_dir / "hook_port.txt").write_text("  8080\n")

        fake_home = tmp_path

        class FakePath:
            @staticmethod
            def home():
                return fake_home

        with patch.object(hook_config, "Path", FakePath):
            result = hook_config.get_hook_port()
            assert result == 8080

    def test_default_when_no_port_file(self, tmp_path):
        class FakePath:
            @staticmethod
            def home():
                return tmp_path

        with patch.object(hook_config, "Path", FakePath):
            result = hook_config.get_hook_port()
            assert result == 3456

    def test_default_on_invalid_port_file(self, tmp_path):
        config_dir = tmp_path / ".config" / "cc-claw"
        config_dir.mkdir(parents=True)
        (config_dir / "hook_port.txt").write_text("not-an-int\n")

        class FakePath:
            @staticmethod
            def home():
                return tmp_path

        with patch.object(hook_config, "Path", FakePath):
            result = hook_config.get_hook_port()
            assert result == 3456


# ---------------------------------------------------------------------------
# inject_hooks
# ---------------------------------------------------------------------------

class TestInjectHooks:
    def test_injects_all_four_hooks(self, tmp_path):
        path = write_settings(tmp_path, {})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.inject_hooks(hook_port=7777)

        assert result is True
        loaded = json.loads(path.read_text())
        hook_urls = [
            inner_h["url"]
            for event_hooks in loaded.get("hooks", {}).values()
            for h in event_hooks
            for inner_h in h.get("hooks", [])
        ]
        assert any("7777" in u for u in hook_urls)
        assert any("/hooks/stop" in u for u in hook_urls)
        assert any("/hooks/post-tool-use" in u for u in hook_urls)
        assert any("/hooks/pre-tool-use" in u for u in hook_urls)
        assert any("/hooks/notification" in u for u in hook_urls)

    def test_idempotent_injection(self, tmp_path):
        """Injecting twice should not duplicate hooks."""
        path = write_settings(tmp_path, {})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.inject_hooks(hook_port=3456)
            hook_config.inject_hooks(hook_port=3456)

        loaded = json.loads(path.read_text())
        stop_count = sum(
            1
            for h in loaded["hooks"]["Stop"]
            for inner_h in h.get("hooks", [])
            if "/hooks/stop" in inner_h.get("url", "")
        )
        assert stop_count == 1

    def test_preserves_existing_hooks(self, tmp_path):
        existing_settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "http", "url": "http://other.com/stop", "timeout": 5}]}
                ]
            },
            "someOtherKey": {"keep": "this"},
        }
        path = write_settings(tmp_path, existing_settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.inject_hooks(hook_port=3456)

        loaded = json.loads(path.read_text())
        # Both existing and cc-claw should be present
        urls = [inner_h["url"] for h in loaded["hooks"]["Stop"] for inner_h in h.get("hooks", [])]
        assert "http://other.com/stop" in urls
        assert any("127.0.0.1:3456" in u for u in urls)
        # Other keys preserved
        assert loaded["someOtherKey"]["keep"] == "this"

    def test_backs_up_before_writing(self, tmp_path):
        path = write_settings(tmp_path, {"old": True})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.inject_hooks()

        assert (tmp_path / "settings.json.bak").exists()
        backup = json.loads((tmp_path / "settings.json.bak").read_text())
        assert backup == {"old": True}

    def test_adds_hooks_to_existing_event(self, tmp_path):
        existing_settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "http", "url": "http://other.com/stop"}]}
                ]
            }
        }
        path = write_settings(tmp_path, existing_settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.inject_hooks(hook_port=3456)

        loaded = json.loads(path.read_text())
        stop_urls = [inner_h["url"] for h in loaded["hooks"]["Stop"] for inner_h in h.get("hooks", [])]
        assert len(stop_urls) == 2  # existing + cc-claw

    def test_creates_hooks_section_if_missing(self, tmp_path):
        path = write_settings(tmp_path, {"otherKey": 1})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.inject_hooks(hook_port=3456)

        loaded = json.loads(path.read_text())
        assert "hooks" in loaded


# ---------------------------------------------------------------------------
# remove_hooks
# ---------------------------------------------------------------------------

class TestRemoveHooks:
    def test_removes_all_cc_claw_hooks(self, tmp_path):
        # New format: hooks wrapped in inner array
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"url": "http://127.0.0.1:3456/hooks/stop"}]},
                    {"hooks": [{"url": "http://other.com/stop"}]},
                ],
                "PostToolUse": [
                    {"hooks": [{"url": "http://127.0.0.1:3456/hooks/post-tool-use"}]},
                ],
            }
        }
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.remove_hooks()

        assert result is True
        loaded = json.loads(path.read_text())
        stop_urls = [inner_h["url"] for h in loaded["hooks"]["Stop"] for inner_h in h.get("hooks", [])]
        assert len(stop_urls) == 1
        assert stop_urls[0] == "http://other.com/stop"
        # PostToolUse should be removed entirely (empty)
        assert "PostToolUse" not in loaded["hooks"]

    def test_no_change_when_no_cc_claw_hooks(self, tmp_path):
        settings = {"hooks": {"Stop": [{"hooks": [{"url": "http://other.com/stop"}]}]}}
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.remove_hooks()

        assert result is True
        loaded = json.loads(path.read_text())
        assert loaded["hooks"]["Stop"][0]["hooks"][0]["url"] == "http://other.com/stop"

    def test_true_when_no_settings_file(self, tmp_path):
        nonexistent = tmp_path / "nonexistent.json"
        with patch.object(hook_config, "SETTINGS_PATH", nonexistent):
            result = hook_config.remove_hooks()

        assert result is True

    def test_removes_empty_hooks_dict(self, tmp_path):
        settings = {
            "hooks": {
                "Stop": [{"hooks": [{"url": "http://127.0.0.1:3456/hooks/stop"}]}],
            }
        }
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.remove_hooks()

        loaded = json.loads(path.read_text())
        assert "hooks" not in loaded

    def test_keeps_other_settings_keys(self, tmp_path):
        settings = {
            "hooks": {"Stop": [{"hooks": [{"url": "http://127.0.0.1:3456/hooks/stop"}]}]},
            "otherKey": {"keep": "this"},
        }
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            hook_config.remove_hooks()

        loaded = json.loads(path.read_text())
        assert "otherKey" in loaded


# ---------------------------------------------------------------------------
# is_hooks_injected
# ---------------------------------------------------------------------------

class TestIsHooksInjected:
    def test_true_when_cc_claw_hooks_present(self, tmp_path):
        settings = {
            "hooks": {
                "Stop": [{"hooks": [{"url": "http://127.0.0.1:3456/hooks/stop"}]}]
            }
        }
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.is_hooks_injected()

        assert result is True

    def test_false_when_no_hooks(self, tmp_path):
        path = write_settings(tmp_path, {})
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.is_hooks_injected()

        assert result is False

    def test_false_when_other_hooks_only(self, tmp_path):
        settings = {"hooks": {"Stop": [{"hooks": [{"url": "http://other.com/stop"}]}]}}
        path = write_settings(tmp_path, settings)
        with patch.object(hook_config, "SETTINGS_PATH", path):
            result = hook_config.is_hooks_injected()

        assert result is False

    def test_checks_all_four_hooks(self, tmp_path):
        # Each marker should be detected
        for marker in ["/hooks/stop", "/hooks/post-tool-use", "/hooks/pre-tool-use", "/hooks/notification"]:
            settings = {"hooks": {"Stop": [{"hooks": [{"url": f"http://127.0.0.1:3456{marker}"}]}]}}
            path = write_settings(tmp_path, settings)
            with patch.object(hook_config, "SETTINGS_PATH", path):
                result = hook_config.is_hooks_injected()
            assert result is True, f"Failed for {marker}"
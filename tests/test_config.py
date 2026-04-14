"""Tests for config.py - ClientConfig and PairingInfo."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.config import ClientConfig, PairingInfo


class TestClientConfigDefaults:
    """Test ClientConfig default values."""

    def test_default_values(self):
        config = ClientConfig()

        assert config.server_ws_url == "wss://cc-claw.example.com/ws"
        assert config.server_api_url == "https://cc-claw.example.com/api"
        assert config.device_token is None
        assert config.claude_path == "claude"
        assert config.timeout == 1800
        assert config.auto_reconnect is True
        assert config.reconnect_delay == 5
        assert config.log_level == "INFO"
        assert config.permission_mode == "default"
        assert config.working_dir == "/"

    def test_custom_values(self):
        config = ClientConfig(
            server_ws_url="wss://custom.com/ws",
            timeout=600,
            permission_mode="bypassPermissions",
        )

        assert config.server_ws_url == "wss://custom.com/ws"
        assert config.timeout == 600


class TestClientConfigGetDefaultPath:
    """Test get_default_config_path()."""

    def test_macos_linux_path(self):
        with patch("os.name", "posix"):
            with patch("pathlib.Path.home", return_value=Path("/home/testuser")):
                path = ClientConfig.get_default_config_path()
                assert path == Path("/home/testuser/.config/cc-claw/config.json")


class TestClientConfigLoad:
    """Test ClientConfig.load()."""

    def test_load_from_file(self, temp_dir):
        config_path = temp_dir / "config.json"
        config_data = {
            "server_ws_url": "wss://loaded.com/ws",
            "timeout": 500,
            "device_token": "secret-token",
        }
        config_path.write_text(json.dumps(config_data))

        config = ClientConfig.load(config_path)

        assert config.server_ws_url == "wss://loaded.com/ws"
        assert config.timeout == 500

    def test_load_nonexistent_returns_default(self, temp_dir):
        config_path = temp_dir / "nonexistent.json"

        config = ClientConfig.load(config_path)

        assert config.server_ws_url == "wss://cc-claw.example.com/ws"

    def test_load_empty_file_returns_default(self, temp_dir):
        config_path = temp_dir / "empty.json"
        config_path.write_text("{}")

        config = ClientConfig.load(config_path)

        assert config.server_ws_url == "wss://cc-claw.example.com/ws"


class TestClientConfigSave:
    """Test ClientConfig.save()."""

    def test_save_to_file(self, temp_dir):
        config_path = temp_dir / "saved_config.json"
        config = ClientConfig(
            server_ws_url="wss://save-test.com/ws",
            timeout=999,
        )

        config.save(config_path)

        assert config_path.exists()

        with open(config_path) as f:
            data = json.load(f)

        assert data["server_ws_url"] == "wss://save-test.com/ws"

    def test_save_creates_parent_dirs(self, temp_dir):
        config_path = temp_dir / "nested" / "dir" / "config.json"
        config = ClientConfig()

        config.save(config_path)

        assert config_path.exists()

    def test_save_and_load_roundtrip(self, temp_dir, monkeypatch):
        # Clear env vars that might override config
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

        config_path = temp_dir / "roundtrip.json"
        original = ClientConfig(
            minimax_api_key="my-secret-key",
            permission_mode="yolo",
        )

        original.save(config_path)
        loaded = ClientConfig.load(config_path)

        assert loaded.minimax_api_key == original.minimax_api_key
        assert loaded.permission_mode == original.permission_mode


class TestPairingInfoDefaults:
    """Test PairingInfo default values."""

    def test_default_values(self):
        info = PairingInfo()

        assert info.code is None
        assert info.user_id is None
        assert info.expires_at is None


class TestPairingInfoGetDefaultPath:
    """Test PairingInfo.get_default_path()."""

    def test_macos_linux_path(self):
        with patch("os.name", "posix"):
            with patch("pathlib.Path.home", return_value=Path("/home/testuser")):
                path = PairingInfo.get_default_path()
                assert path == Path("/home/testuser/.config/cc-claw/pairing.json")


class TestPairingInfoLoad:
    """Test PairingInfo.load()."""

    def test_load_from_file(self, temp_dir):
        path = temp_dir / "pairing.json"
        data = {
            "code": "ABC123",
            "user_id": 12345,
            "expires_at": "2025-12-31T23:59:59",
        }
        path.write_text(json.dumps(data))

        info = PairingInfo.load(path)

        assert info.code == "ABC123"
        assert info.user_id == 12345

    def test_load_nonexistent_returns_default(self, temp_dir):
        path = temp_dir / "nonexistent.json"

        info = PairingInfo.load(path)

        assert info.code is None


class TestPairingInfoSave:
    """Test PairingInfo.save()."""

    def test_save_to_file(self, temp_dir):
        path = temp_dir / "pairing.json"
        info = PairingInfo(
            code="SAVE123",
            user_id=999,
        )

        info.save(path)

        assert path.exists()

        with open(path) as f:
            data = json.load(f)

        assert data["code"] == "SAVE123"

    def test_save_and_load_roundtrip(self, temp_dir):
        path = temp_dir / "roundtrip_pairing.json"
        original = PairingInfo(
            code="ROUNDTRIP",
            user_id=42,
        )

        original.save(path)
        loaded = PairingInfo.load(path)

        assert loaded.code == original.code
        assert loaded.user_id == original.user_id

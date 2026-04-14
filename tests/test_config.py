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

    def test_windows_path(self):
        """Line 64: Windows branch uses APPDATA environment variable."""
        appdata_val = "D:\\Users\\Test"
        # Build a fake path that supports the / operator
        fake_base = Path(appdata_val)
        # Patch Path so WindowsPath isn't instantiated on macOS
        with patch("os.name", "nt"):
            with patch.dict("os.environ", {"APPDATA": appdata_val}, clear=False):
                with patch("client.config.Path", return_value=fake_base):
                    path = ClientConfig.get_default_config_path()
                    assert str(path).replace("\\", "/") == "D:/Users/Test/cc-claw/config.json"


class TestClientConfigLoadDefaultPath:
    """Test load() calls get_default_config_path() when no path given (line 35)."""

    def test_load_with_no_path_uses_default_path(self, temp_dir, monkeypatch):
        """Line 35: load() with no path calls get_default_config_path()."""
        # Patch the method, not the module-level os.name, to avoid polluting global state
        fake_path = temp_dir / "config.json"
        fake_path.write_text(json.dumps({"timeout": 777}))

        original_get_default = ClientConfig.get_default_config_path
        ClientConfig.get_default_config_path = classmethod(lambda cls: fake_path)

        try:
            config = ClientConfig.load()
            assert config.timeout == 777
        finally:
            ClientConfig.get_default_config_path = original_get_default

    def test_load_env_overrides_file(self, temp_dir, monkeypatch):
        """Env vars override file config (lines 44-47)."""
        config_path = temp_dir / "config.json"
        config_path.write_text(json.dumps({"timeout": 100}))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-secret-key")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.api/")

        config = ClientConfig.load(config_path)

        assert config.minimax_api_key == "env-secret-key"
        assert config.minimax_api_url == "https://custom.api/"


class TestClientConfigSaveDefaultPath:
    """Test save() calls get_default_config_path() when no path given (line 54)."""

    def test_save_with_no_path_uses_default_path(self, temp_dir, monkeypatch):
        """Line 54: save() with no path calls get_default_config_path()."""
        fake_path = temp_dir / "default_config.json"

        original_get_default = ClientConfig.get_default_config_path
        ClientConfig.get_default_config_path = classmethod(lambda cls: fake_path)

        try:
            config = ClientConfig(timeout=555)
            config.save()  # no path → uses get_default_config_path()
            assert fake_path.exists()
        finally:
            ClientConfig.get_default_config_path = original_get_default


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


class TestPairingInfoGetDefaultPathWindows:
    """Test PairingInfo.get_default_path() Windows branch (line 102)."""

    def test_windows_path(self):
        """Line 102: Windows branch uses APPDATA environment variable."""
        appdata_val = "C:\\Users\\Alice"
        fake_base = Path(appdata_val)
        with patch("os.name", "nt"):
            with patch.dict("os.environ", {"APPDATA": appdata_val}, clear=False):
                with patch("client.config.Path", return_value=fake_base):
                    path = PairingInfo.get_default_path()
                    assert str(path).replace("\\", "/") == "C:/Users/Alice/cc-claw/pairing.json"


class TestPairingInfoDefaultPathCalls:
    """Test PairingInfo.load/save call get_default_path() with no args (lines 81, 92)."""

    def test_load_with_no_path_uses_default(self, temp_dir):
        """Line 81: load() with no path calls get_default_path()."""
        fake_path = temp_dir / "pairing.json"
        fake_path.write_text(json.dumps({"code": "FROM_DEFAULT", "user_id": 123}))

        original = PairingInfo.get_default_path
        PairingInfo.get_default_path = staticmethod(lambda: fake_path)

        try:
            info = PairingInfo.load()
            assert info.code == "FROM_DEFAULT"
        finally:
            PairingInfo.get_default_path = original

    def test_save_with_no_path_uses_default(self, temp_dir):
        """Line 92: save() with no path calls get_default_path()."""
        fake_path = temp_dir / "pairing.json"

        original = PairingInfo.get_default_path
        PairingInfo.get_default_path = staticmethod(lambda: fake_path)

        try:
            info = PairingInfo(code="TO_DEFAULT")
            info.save()  # no path → uses get_default_path()
            assert fake_path.exists()
        finally:
            PairingInfo.get_default_path = original


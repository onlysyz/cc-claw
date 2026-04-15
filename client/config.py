"""CC-Claw Client Configuration Module"""

import os
import json
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, fields
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """Client configuration with smart defaults.

    Auto-detected on load:
    - claude_path: discovered via shutil.which if not set
    - working_dir:  defaults to cwd and is auto-created on save
    - permission_mode: defaults to bypassPermissions (required for autonomous mode)
    """
    server_ws_url: str = "wss://cc-claw.example.com/ws"
    server_api_url: str = "https://cc-claw.example.com/api"
    device_token: Optional[str] = None
    device_id: Optional[str] = None
    claude_path: str = "claude"
    timeout: int = 1800  # 30 minutes
    auto_reconnect: bool = True
    reconnect_delay: int = 5
    log_level: str = "INFO"
    # Permission mode: "default" (ask), "bypassPermissions" or "yolo" (skip all)
    permission_mode: str = "default"
    # Working directory for Claude sessions
    working_dir: str = "/"
    # MiniMax API for goal decomposition (saves Claude Code tokens)
    minimax_api_key: Optional[str] = None
    minimax_api_url: str = "https://api.minimaxi.com/anthropic"
    minimax_model: str = "MiniMax-M2.7"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ClientConfig":
        """Load configuration from file, environment variables, and auto-detect."""
        if config_path is None:
            config_path = cls.get_default_config_path()

        config_data = {}
        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)

        # Override with environment variables (for secrets like API keys)
        if os.environ.get("ANTHROPIC_API_KEY"):
            config_data["minimax_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
        if os.environ.get("ANTHROPIC_BASE_URL"):
            config_data["minimax_api_url"] = os.environ.get("ANTHROPIC_BASE_URL")

        # Filter out keys that don't exist as fields (backwards compatibility with old configs)
        valid_keys = {f.name for f in fields(cls)}
        config_data = {k: v for k, v in config_data.items() if k in valid_keys}

        inst = cls(**config_data) if config_data else cls()
        inst._apply_defaults()
        return inst

    # Sentinel to detect auto-detected values
    _AUTO = object()

    def _apply_defaults(self):
        """Upgrade dataclass-default values to smart auto-detected ones.

        Only overrides values that were never explicitly set by the user
        (identified by matching the original dataclass default).
        """
        # Auto-detect claude_path: only upgrade the placeholder default
        if self.claude_path == "claude":
            detected = shutil.which("claude")
            if detected:
                self.claude_path = detected
                logger.info(f"Auto-detected Claude CLI: {self.claude_path}")

        # Default permission_mode: upgrade "default" to "bypassPermissions" (safer for autonomous)
        if self.permission_mode == "default":
            self.permission_mode = "bypassPermissions"
            logger.info("Auto-set permission_mode=bypassPermissions for autonomous mode")

        # Default working_dir: only upgrade root "/" placeholder to cwd
        if self.working_dir == "/":
            self.working_dir = os.getcwd()
            logger.info(f"Auto-set working_dir={self.working_dir}")
        os.makedirs(self.working_dir, exist_ok=True)

    def save(self, config_path: Optional[Path] = None):
        """Save configuration to file"""
        if config_path is None:
            config_path = self.get_default_config_path()

        # Ensure working_dir exists before saving
        os.makedirs(self.working_dir, exist_ok=True)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def get_default_config_path() -> Path:
        """Get default config path"""
        if os.name == "nt":  # Windows
            base = Path(os.environ.get("APPDATA", ""))
        else:  # macOS/Linux
            base = Path.home() / ".config"
        return base / "cc-claw" / "config.json"


@dataclass
class PairingInfo:
    """Pairing information"""
    code: Optional[str] = None
    user_id: Optional[int] = None
    expires_at: Optional[str] = None

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PairingInfo":
        """Load pairing info from file"""
        if path is None:
            path = cls.get_default_path()

        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls()

    def save(self, path: Optional[Path] = None):
        """Save pairing info to file"""
        if path is None:
            path = self.get_default_path()

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def get_default_path() -> Path:
        """Get default pairing info path"""
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", ""))
        else:
            base = Path.home() / ".config"
        return base / "cc-claw" / "pairing.json"

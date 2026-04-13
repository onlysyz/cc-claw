"""CC-Claw Client Configuration Module"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ClientConfig:
    """Client configuration"""
    server_ws_url: str = "wss://cc-claw.example.com/ws"
    server_api_url: str = "https://cc-claw.example.com/api"
    device_token: Optional[str] = None
    device_id: Optional[str] = None
    claude_path: str = "claude"
    timeout: int = 600  # 10 minutes
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
        """Load configuration from file and environment variables"""
        if config_path is None:
            config_path = cls.get_default_config_path()

        # Load from config file first, then override with env vars
        config_data = {}
        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)

        # Override with environment variables (for secrets like API keys)
        if os.environ.get("ANTHROPIC_API_KEY"):
            config_data["minimax_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
        if os.environ.get("ANTHROPIC_BASE_URL"):
            config_data["minimax_api_url"] = os.environ.get("ANTHROPIC_BASE_URL")

        return cls(**config_data) if config_data else cls()

    def save(self, config_path: Optional[Path] = None):
        """Save configuration to file"""
        if config_path is None:
            config_path = self.get_default_config_path()

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

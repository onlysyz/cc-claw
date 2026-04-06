"""CC-Claw Server Configuration"""

import os
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Server configuration"""
    # Server
    host: str = "0.0.0.0"
    api_port: int = 3000
    ws_port: int = 3001

    # Telegram
    telegram_bot_token: str = ""

    # JWT
    jwt_secret: str = "change-this-in-production"
    jwt_expire_hours: int = 24 * 7  # 7 days

    # Pairing
    pairing_code_length: int = 6
    pairing_expire_minutes: int = 5

    # Message
    max_message_length: int = 10000
    message_timeout_seconds: int = 300

    # Storage
    data_dir: str = ""  # Default to ~/.cc-claw/data

    # Tailscale
    tailscale_mode: str = "off"  # off | serve | funnel

    # Lark (Feishu)
    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_bot_name: str = "CC-Claw"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Load config from environment variables"""
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "3000")),
            ws_port=int(os.getenv("WS_PORT", "3001")),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            jwt_secret=os.getenv("JWT_SECRET", cls.jwt_secret),
            data_dir=os.getenv("DATA_DIR", cls.data_dir),
            tailscale_mode=os.getenv("TAILSCALE_MODE", "off"),
            lark_app_id=os.getenv("LARK_APP_ID", ""),
            lark_app_secret=os.getenv("LARK_APP_SECRET", ""),
            lark_bot_name=os.getenv("LARK_BOT_NAME", cls.lark_bot_name),
        )


# Global config instance
config = ServerConfig.from_env()

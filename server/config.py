"""CC-Claw Server Configuration"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    """Server configuration"""
    # Server
    host: str = "0.0.0.0"
    api_port: int = 3000
    ws_port: int = 3001

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cc_claw"
    redis_url: str = "redis://localhost:6379/0"

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

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Load config from environment variables"""
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "3000")),
            ws_port=int(os.getenv("WS_PORT", "3001")),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            jwt_secret=os.getenv("JWT_SECRET", cls.jwt_secret),
        )


# Global config instance
config = ServerConfig.from_env()

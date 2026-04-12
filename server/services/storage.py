"""CC-Claw File Storage Service - No external dependencies"""

import json
import os
import uuid
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import secrets
import string
import shutil

from ..config import config


class FileStorage:
    """File-based storage - no Redis, no database needed"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Default to ~/.cc-claw/data
            home = os.path.expanduser("~")
            self.data_dir = os.path.join(home, ".cc-claw", "data")
        else:
            self.data_dir = data_dir

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # File paths
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.devices_file = os.path.join(self.data_dir, "devices.json")
        self.tokens_file = os.path.join(self.data_dir, "tokens.json")
        self.pairings_file = os.path.join(self.data_dir, "pairings.json")

        # Thread lock for file operations
        self._lock = threading.RLock()

        # Initialize files if not exist
        self._init_files()

    def _init_files(self):
        """Initialize storage files"""
        for f in [self.users_file, self.devices_file, self.tokens_file, self.pairings_file]:
            if not os.path.exists(f):
                self._write_json(f, {})

    def _read_json(self, filepath: str) -> dict:
        """Read JSON file with lock"""
        with self._lock:
            try:
                with open(filepath, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    def _write_json(self, filepath: str, data: dict):
        """Write JSON file with lock"""
        with self._lock:
            # Write to temp file first, then rename (atomic)
            temp_file = filepath + ".tmp"
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            shutil.move(temp_file, filepath)

    # --- User Methods ---
    def create_user(self, telegram_id: int, username: str = None, first_name: str = None, lark_open_id: str = None) -> dict:
        """Create or get user"""
        users = self._read_json(self.users_file)

        # Check if user exists by telegram_id
        for user in users.values():
            if user.get("telegram_id") == str(telegram_id):
                return user

        # Create new user
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "telegram_id": str(telegram_id),
            "username": username or "",
            "first_name": first_name or "",
            "lark_open_id": lark_open_id or "",
            "created_at": datetime.utcnow().isoformat(),
            "onboarding_state": "pending",  # pending | profession | situation | goal | better | complete
            "onboarding_data": {},  # collected answers
        }
        users[user_id] = user_data
        self._write_json(self.users_file, users)
        return user_data

    def get_user(self, telegram_id: int) -> Optional[dict]:
        """Get user by telegram ID"""
        users = self._read_json(self.users_file)
        for user in users.values():
            if user.get("telegram_id") == str(telegram_id):
                return user
        return None

    def get_user_by_lark_open_id(self, lark_open_id: str) -> Optional[dict]:
        """Get user by Lark open_id"""
        if not lark_open_id:
            return None
        users = self._read_json(self.users_file)
        for user in users.values():
            if user.get("lark_open_id") == lark_open_id:
                return user
        return None

    def get_or_create_user_by_lark(self, lark_open_id: str, username: str = None, first_name: str = None) -> dict:
        """Get existing user by Lark open_id or create new one"""
        users = self._read_json(self.users_file)

        # Check if user exists by lark_open_id
        for user in users.values():
            if user.get("lark_open_id") == lark_open_id:
                return user

        # Create new user
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "telegram_id": "",  # Will be filled if they also use Telegram
            "username": username or "",
            "first_name": first_name or "",
            "lark_open_id": lark_open_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        users[user_id] = user_data
        self._write_json(self.users_file, users)
        return user_data

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID"""
        users = self._read_json(self.users_file)
        return users.get(user_id)

    # --- Device Methods ---
    def create_device(self, user_id: str, name: str, platform: str) -> dict:
        """Create a new device"""
        device_id = str(uuid.uuid4())
        return self.create_device_with_id(device_id, user_id, name, platform)

    def create_device_with_id(self, device_id: str, user_id: str, name: str, platform: str) -> dict:
        """Create a new device with specific ID"""
        devices = self._read_json(self.devices_file)

        device_data = {
            "id": device_id,
            "user_id": user_id,
            "name": name,
            "platform": platform,
            "status": "offline",
            "created_at": datetime.utcnow().isoformat(),
            "last_seen_at": "",
        }
        devices[device_id] = device_data
        self._write_json(self.devices_file, devices)

        # Update user's device list
        users = self._read_json(self.users_file)
        if user_id in users:
            if "device_ids" not in users[user_id]:
                users[user_id]["device_ids"] = []
            if device_id not in users[user_id]["device_ids"]:
                users[user_id]["device_ids"].append(device_id)
            self._write_json(self.users_file, users)

        return device_data

    def get_device(self, device_id: str) -> Optional[dict]:
        """Get device by ID"""
        devices = self._read_json(self.devices_file)
        return devices.get(device_id)

    def get_user_device(self, user_id: str) -> Optional[dict]:
        """Get user's first device"""
        users = self._read_json(self.users_file)
        user = users.get(user_id)
        if user and user.get("device_ids"):
            device_id = user["device_ids"][0]
            return self.get_device(device_id)
        return None

    def update_device_status(self, device_id: str, status: str):
        """Update device status"""
        devices = self._read_json(self.devices_file)
        if device_id in devices:
            devices[device_id]["status"] = status
            devices[device_id]["last_seen_at"] = datetime.utcnow().isoformat()
            self._write_json(self.devices_file, devices)

    def delete_device(self, device_id: str):
        """Delete a device"""
        devices = self._read_json(self.devices_file)
        device = devices.pop(device_id, None)

        if device:
            user_id = device.get("user_id")
            if user_id:
                users = self._read_json(self.users_file)
                if user_id in users and "device_ids" in users[user_id]:
                    users[user_id]["device_ids"] = [d for d in users[user_id]["device_ids"] if d != device_id]
                    self._write_json(self.users_file, users)

            # Delete tokens
            tokens = self._read_json(self.tokens_file)
            tokens_to_delete = [t for t, data in tokens.items() if data.get("device_id") == device_id]
            for t in tokens_to_delete:
                tokens.pop(t, None)
            self._write_json(self.tokens_file, tokens)

        self._write_json(self.devices_file, devices)

    # --- Token Methods ---
    def create_token(self, device_id: str) -> Tuple[str, str]:
        """Create a new device token"""
        tokens = self._read_json(self.tokens_file)

        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=config.jwt_expire_hours)

        token_data = {
            "token": token,
            "device_id": device_id,
            "expires_at": expires_at.isoformat(),
        }
        tokens[token] = token_data
        self._write_json(self.tokens_file, tokens)
        return token, expires_at.isoformat()

    def add_token(self, token: str, device_id: str, expires_at: str):
        """Add a token for a device"""
        tokens = self._read_json(self.tokens_file)
        token_data = {
            "token": token,
            "device_id": device_id,
            "expires_at": expires_at,
        }
        tokens[token] = token_data
        self._write_json(self.tokens_file, tokens)

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify a token"""
        tokens = self._read_json(self.tokens_file)
        token_data = tokens.get(token)

        if not token_data:
            return None

        expires_at = datetime.fromisoformat(token_data["expires_at"])

        if expires_at < datetime.utcnow():
            return None

        return token_data

    def delete_token(self, token: str):
        """Delete a token"""
        tokens = self._read_json(self.tokens_file)
        tokens.pop(token, None)
        self._write_json(self.tokens_file, tokens)

    def delete_device_tokens(self, device_id: str):
        """Delete all tokens for a device"""
        tokens = self._read_json(self.tokens_file)
        tokens_to_delete = [t for t, data in tokens.items() if data.get("device_id") == device_id]
        for t in tokens_to_delete:
            tokens.pop(t, None)
        self._write_json(self.tokens_file, tokens)

    # --- Pairing Methods ---
    def generate_pairing_code(self) -> str:
        """Generate a unique pairing code"""
        pairings = self._read_json(self.pairings_file)
        alphabet = string.ascii_uppercase + string.digits

        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(config.pairing_code_length))
            if code not in pairings:
                return code

    def create_pairing(self, user_id: str) -> Tuple[str, str]:
        """Create a new pairing code"""
        pairings = self._read_json(self.pairings_file)

        code = self.generate_pairing_code()
        expires_at = datetime.utcnow() + timedelta(minutes=config.pairing_expire_minutes)

        pairing_data = {
            "code": code,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "status": "pending",
        }
        pairings[code] = pairing_data
        self._write_json(self.pairings_file, pairings)
        return code, expires_at.isoformat()

    def verify_pairing(self, code: str) -> Optional[dict]:
        """Verify a pairing code"""
        pairings = self._read_json(self.pairings_file)
        pairing = pairings.get(code)

        if not pairing:
            return None

        expires_at = datetime.fromisoformat(pairing["expires_at"])

        if expires_at < datetime.utcnow():
            # Clean up expired pairing
            pairings.pop(code, None)
            self._write_json(self.pairings_file, pairings)
            return None

        if pairing.get("status") != "pending":
            return None

        return pairing

    def complete_pairing(self, code: str) -> Optional[dict]:
        """Complete pairing - returns device and token"""
        pairing = self.verify_pairing(code)
        if not pairing:
            return None

        user_id = pairing["user_id"]

        # Create device
        # Note: device name and platform should be set before this
        # This just completes the pairing process
        user = self.get_user_by_id(user_id)

        # Get or create device for user
        device = self.get_user_device(user_id)
        if not device:
            device = self.create_device(user_id, "Device", "unknown")

        # Create token
        token, expires_at = self.create_token(device["id"])

        # Update pairing status
        pairings = self._read_json(self.pairings_file)
        if code in pairings:
            pairings[code]["status"] = "completed"
            self._write_json(self.pairings_file, pairings)

        return {
            "device": device,
            "token": token,
            "expires_at": expires_at,
            "user": user,
        }

    def delete_pairing(self, code: str):
        """Delete a pairing code"""
        pairings = self._read_json(self.pairings_file)
        pairings.pop(code, None)
        self._write_json(self.pairings_file, pairings)

    def update_user(self, user_id: str, **kwargs):
        """Update user fields"""
        users = self._read_json(self.users_file)
        if user_id in users:
            for key, value in kwargs.items():
                users[user_id][key] = value
            self._write_json(self.users_file, users)

    def get_onboarding_state(self, user_id: str) -> Tuple[str, dict]:
        """Get onboarding state and collected data for user"""
        users = self._read_json(self.users_file)
        user = users.get(user_id)
        if not user:
            return "pending", {}
        return user.get("onboarding_state", "pending"), user.get("onboarding_data", {})

    def set_onboarding_state(self, user_id: str, state: str, data: dict = None):
        """Update onboarding state and data"""
        users = self._read_json(self.users_file)
        if user_id in users:
            users[user_id]["onboarding_state"] = state
            if data is not None:
                users[user_id]["onboarding_data"] = data
            self._write_json(self.users_file, users)


# Global storage instance
storage: Optional[FileStorage] = None


def init_storage(data_dir: str = None) -> FileStorage:
    """Initialize file storage"""
    global storage
    storage = FileStorage(data_dir)
    return storage

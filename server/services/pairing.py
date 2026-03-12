"""CC-Claw Pairing Service"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models.models import User, Device, DeviceToken, Pairing, PairingStatus, UserStatus, DeviceStatus
from ..config import config
from .redis import redis_service


class PairingService:
    """Service for handling device pairing"""

    def __init__(self, db: Session):
        self.db = db

    def generate_code(self) -> str:
        """Generate a random pairing code"""
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(config.pairing_code_length))

    def create_pairing(self, telegram_id: int, username: str = None, first_name: str = None) -> str:
        """Create a new pairing for a user"""
        # Get or create user
        user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                status=UserStatus.ACTIVE,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        # Generate unique code
        while True:
            code = self.generate_code()
            existing = self.db.query(Pairing).filter(Pairing.code == code).first()
            if not existing:
                break

        # Create pairing
        expires_at = datetime.utcnow() + timedelta(minutes=config.pairing_expire_minutes)
        pairing = Pairing(
            code=code,
            user_id=user.id,
            expires_at=expires_at,
            status=PairingStatus.PENDING,
        )
        self.db.add(pairing)
        self.db.commit()

        # Store in Redis for quick lookup
        redis_service.set_pairing(code, {
            "user_id": str(user.id),
            "telegram_id": telegram_id,
            "expires_at": expires_at.isoformat(),
        }, expire_seconds=config.pairing_expire_minutes * 60)

        return code

    def verify_pairing(self, code: str) -> Optional[dict]:
        """Verify a pairing code"""
        # Check Redis first
        data = redis_service.get_pairing(code)
        if data:
            return data

        # Check database
        pairing = self.db.query(Pairing).filter(
            Pairing.code == code,
            Pairing.status == PairingStatus.PENDING,
            Pairing.expires_at > datetime.utcnow(),
        ).first()

        if pairing:
            return {
                "user_id": str(pairing.user_id),
                "pairing_id": str(pairing.id),
            }
        return None

    def complete_pairing(self, code: str, device_id: str, device_name: str, platform: str, token: str) -> Optional[Device]:
        """Complete the pairing process"""
        pairing_data = self.verify_pairing(code)
        if not pairing_data:
            return None

        user_id = pairing_data["user_id"]

        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # Create device
        device = Device(
            id=uuid4(),
            user_id=user.id,
            name=device_name,
            platform=platform,
            status=DeviceStatus.OFFLINE,
        )
        self.db.add(device)

        # Create device token
        expires_at = datetime.utcnow() + timedelta(hours=config.jwt_expire_hours)
        device_token = DeviceToken(
            device_id=device.id,
            token=token,
            expires_at=expires_at,
        )
        self.db.add(device_token)

        # Update pairing status
        pairing = self.db.query(Pairing).filter(Pairing.code == code).first()
        if pairing:
            pairing.status = PairingStatus.COMPLETED
            pairing.device_id = device.id

        self.db.commit()
        self.db.refresh(device)

        # Update Redis
        redis_service.delete_pairing(code)
        redis_service.set_user_device(user.telegram_id, str(device.id))

        return device

    def get_user_device(self, telegram_id: int) -> Optional[Device]:
        """Get user's paired device"""
        # Check Redis first
        device_id = redis_service.get_user_device(telegram_id)
        if device_id:
            device = self.db.query(Device).filter(Device.id == device_id).first()
            if device:
                return device

        # Fallback to database
        user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return None

        device = self.db.query(Device).filter(Device.user_id == user.id).first()
        if device:
            # Update Redis cache
            redis_service.set_user_device(telegram_id, str(device.id))

        return device

    def unpair_device(self, telegram_id: int) -> bool:
        """Unpair user's device"""
        device = self.get_user_device(telegram_id)
        if not device:
            return False

        # Delete device and tokens
        self.db.delete(device)
        self.db.commit()

        # Clear Redis
        redis_service.delete_user_device(telegram_id)
        redis_service.delete_device_status(str(device.id))

        return True

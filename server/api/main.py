"""CC-Claw REST API"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import config
from ..models.db import get_db, init_db
from ..models.models import User, Device, DeviceToken, Pairing, DeviceStatus
from ..services.pairing import PairingService


logger = logging.getLogger(__name__)

app = FastAPI(title="CC-Claw API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Models ---

class PairingGenerateRequest(BaseModel):
    telegram_id: int


class PairingGenerateResponse(BaseModel):
    code: str
    expires_at: str


class PairingVerifyRequest(BaseModel):
    code: str


class PairingCompleteRequest(BaseModel):
    code: str
    device_id: str
    device_name: str
    platform: str
    token: str


class DeviceResponse(BaseModel):
    id: str
    name: str
    platform: str
    status: str
    last_seen_at: Optional[datetime] = None


class UserResponse(BaseModel):
    id: str
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]


# --- Routes ---

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    init_db()
    logger.info("API server started")


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok"}


# --- Pairing API ---

@app.post("/api/pairing/generate", response_model=PairingGenerateResponse)
async def generate_pairing(
    request: PairingGenerateRequest,
    db: Session = Depends(get_db)
):
    """Generate a pairing code"""
    pairing_service = PairingService(db)
    code = pairing_service.create_pairing(request.telegram_id)

    # Get expires_at from Redis
    from ..services.redis import redis_service
    pairing_data = redis_service.get_pairing(code)
    expires_at = pairing_data["expires_at"] if pairing_data else ""

    return PairingGenerateResponse(code=code, expires_at=expires_at)


@app.post("/api/pairing/verify")
async def verify_pairing(
    request: PairingVerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify a pairing code"""
    pairing_service = PairingService(db)
    result = pairing_service.verify_pairing(request.code)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code"
        )

    return {"valid": True}


@app.post("/api/pairing/complete", response_model=DeviceResponse)
async def complete_pairing(
    request: PairingCompleteRequest,
    db: Session = Depends(get_db)
):
    """Complete the pairing process"""
    pairing_service = PairingService(db)
    device = pairing_service.complete_pairing(
        request.code,
        request.device_id,
        request.device_name,
        request.platform,
        request.token,
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pairing code or code expired"
        )

    return DeviceResponse(
        id=str(device.id),
        name=device.name,
        platform=device.platform,
        status=device.status.value,
        last_seen_at=device.last_seen_at,
    )


@app.get("/api/pairing/status/{telegram_id}")
async def get_pairing_status(
    telegram_id: int,
    db: Session = Depends(get_db)
):
    """Get pairing status for a user"""
    pairing_service = PairingService(db)
    device = pairing_service.get_user_device(telegram_id)

    if not device:
        return {"paired": False}

    from ..services.redis import redis_service
    is_online = redis_service.get_device_status(str(device.id)) == "online"

    return {
        "paired": True,
        "device": {
            "id": str(device.id),
            "name": device.name,
            "platform": device.platform,
            "online": is_online,
        }
    }


# --- Device API ---

@app.get("/api/devices/{device_id}/status")
async def get_device_status(device_id: str):
    """Get device status"""
    from ..services.redis import redis_service
    status = redis_service.get_device_status(device_id)

    return {
        "device_id": device_id,
        "status": status or "offline"
    }


# --- User API ---

@app.get("/api/users/me", response_model=UserResponse)
async def get_current_user(
    telegram_id: int,
    db: Session = Depends(get_db)
):
    """Get current user info"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=str(user.id),
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
    )

"""CC-Claw REST API"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config import config
from ..services.storage import init_storage
from ..services.simple_storage import simple_storage


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
    last_seen_at: Optional[str] = None
    token: Optional[str] = None


# --- Routes ---

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    init_storage()
    logger.info("API server started")


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok"}


# --- Pairing API ---

@app.post("/api/pairing/generate", response_model=PairingGenerateResponse)
async def generate_pairing(request: PairingGenerateRequest):
    """Generate a pairing code"""
    from ..services.storage import storage

    # Get or create user
    user = storage.get_user(request.telegram_id)
    if not user:
        user = storage.create_user(request.telegram_id)

    # Check if already paired
    if user.get("device_ids"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already paired. Use /unpair first."
        )

    # Generate pairing code
    code, expires_at = storage.create_pairing(user["id"])

    return PairingGenerateResponse(code=code, expires_at=expires_at)


@app.post("/api/pairing/verify")
async def verify_pairing(request: PairingVerifyRequest):
    """Verify a pairing code"""
    from ..services.storage import storage
    result = storage.verify_pairing(request.code)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code"
        )

    return {"valid": True}


@app.post("/api/pairing/complete", response_model=DeviceResponse)
async def complete_pairing(request: PairingCompleteRequest):
    """Complete the pairing process"""
    from ..services.storage import storage

    # First verify the pairing code exists
    pairing = storage.verify_pairing(request.code)
    if not pairing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pairing code or code expired"
        )

    user_id = pairing["user_id"]

    # Get user
    user = storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    # Delete old device if exists
    old_device = storage.get_user_device(user_id)
    if old_device:
        storage.delete_device(old_device["id"])

    # Use the device_id and token provided by the client
    device_id = request.device_id
    device_token = request.token

    # Create device with the provided device_id
    device = storage.create_device_with_id(
        device_id=device_id,
        user_id=user_id,
        name=request.device_name,
        platform=request.platform,
    )

    # Use the token provided by the client
    from datetime import datetime, timedelta
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    storage.add_token(device_token, device_id, expires_at)

    # Update user to device mapping in simple_storage
    # For Lark users, telegram_id might be empty, so we use user_id directly
    telegram_id = user.get("telegram_id")
    if telegram_id:
        simple_storage.set_user_device(int(telegram_id), device["id"])
    else:
        # For Lark users, use lark_open_id as the key
        lark_open_id = user.get("lark_open_id")
        if lark_open_id:
            simple_storage.set_user_device_by_lark(lark_open_id, device["id"])

    # Return device info and token
    return DeviceResponse(
        id=device["id"],
        name=device["name"],
        platform=device["platform"],
        status=device["status"],
        last_seen_at=device.get("last_seen_at"),
        token=device_token,
    )


@app.get("/api/pairing/status/{telegram_id}")
async def get_pairing_status(telegram_id: int):
    """Get pairing status for a user"""
    from ..services.storage import storage

    user = storage.get_user(telegram_id)
    if not user:
        return {"paired": False}

    device = storage.get_user_device(user["id"])

    if not device:
        return {"paired": False}

    is_online = simple_storage.get_device_status(device["id"]) == "online"

    return {
        "paired": True,
        "device": {
            "id": device["id"],
            "name": device["name"],
            "platform": device["platform"],
            "online": is_online,
        },
    }


# --- Device API ---

@app.get("/api/devices/{device_id}/status")
async def get_device_status(device_id: str):
    """Get device status"""
    from ..services.storage import storage

    device = storage.get_device(device_id)
    if not device:
        return {
            "device_id": device_id,
            "status": "not_found"
        }

    status = simple_storage.get_device_status(device_id)

    return {
        "device_id": device_id,
        "status": status or "offline"
    }

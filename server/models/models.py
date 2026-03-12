"""CC-Claw Database Models"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class UserStatus(str, Enum):
    """User status"""
    ACTIVE = "active"
    BLOCKED = "blocked"


class DeviceStatus(str, Enum):
    """Device status"""
    ONLINE = "online"
    OFFLINE = "offline"


class PairingStatus(str, Enum):
    """Pairing status"""
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    pairings = relationship("Pairing", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    """Device model"""
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)  # macos, linux, windows
    status = Column(SQLEnum(DeviceStatus), default=DeviceStatus.OFFLINE)
    last_seen_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="devices")
    tokens = relationship("DeviceToken", back_populates="device", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="device", cascade="all, delete-orphan")


class DeviceToken(Base):
    """Device token model"""
    __tablename__ = "device_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    device = relationship("Device", back_populates="tokens")


class Pairing(Base):
    """Pairing model"""
    __tablename__ = "pairings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(6), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"))
    status = Column(SQLEnum(PairingStatus), default=PairingStatus.PENDING)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="pairings")


class Session(Base):
    """Session model"""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    message_count = Column(Integer, default=0)

    # Relationships
    device = relationship("Device", back_populates="sessions")
    messages = relationship("MessageLog", back_populates="session", cascade="all, delete-orphan")


class MessageLog(Base):
    """Message log model"""
    __tablename__ = "message_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    direction = Column(String(10), nullable=False)  # inbound, outbound
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="messages")

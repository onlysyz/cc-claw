"""CC-Claw Database Connection"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base
from ..config import config


engine = None
SessionLocal = None


def init_db():
    """Initialize database"""
    global engine, SessionLocal

    engine = create_engine(
        config.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session"""
    if SessionLocal is None:
        init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

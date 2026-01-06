"""
依赖注入占位：数据库 Session、配置等。
"""
from typing import Generator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.quark.logger import logger
from app.quark.models.database import SessionLocal


def get_settings_dep():
    return get_settings()


def get_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
    except Exception:
        logger.exception("Database session creation failed")
        raise
    try:
        yield db
    except Exception:
        logger.exception("Database session error; rolling back")
        db.rollback()
        raise
    finally:
        db.close()


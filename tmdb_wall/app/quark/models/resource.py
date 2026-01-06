from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.quark.models.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey("media.id"), index=True)
    name = Column(String, nullable=False)
    link = Column(String, nullable=False, unique=True)
    size_raw = Column(String, nullable=True)
    views = Column(Integer, nullable=True)
    quality_level = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
    codec = Column(String, nullable=True)
    file_count = Column(Integer, nullable=True)
    total_size_gb = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    normalized_name = Column(String, nullable=True)
    episode_info = Column(String, nullable=True)
    media_type_detected = Column(String, nullable=True)
    is_best = Column(Boolean, default=False)
    rename_status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func

from app.quark.models.database import Base


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, index=True, unique=True, nullable=True)
    title = Column(String, nullable=False)
    original_title = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    overview = Column(String, nullable=True)
    poster_path = Column(String, nullable=True)
    backdrop_path = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    popularity = Column(Float, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


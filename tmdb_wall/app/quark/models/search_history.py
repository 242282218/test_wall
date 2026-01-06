from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func

from app.quark.models.database import Base


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    result_count = Column(Integer, nullable=True)
    query_time = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


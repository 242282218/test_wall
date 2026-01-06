from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class TaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class VirtualMedia(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tmdb_id: int = Field(index=True)
    title: str
    share_url: str
    original_fid: str
    share_fid_token: str
    virtual_path: str = Field(index=True, unique=True)
    physical_path: Optional[str] = Field(default=None, index=True)
    is_archived: bool = Field(default=False)
    task_status: TaskStatus = Field(default=TaskStatus.pending, index=True)
    task_id: Optional[str] = Field(default=None, index=True)
    retry_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    last_retry_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

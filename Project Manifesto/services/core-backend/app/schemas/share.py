from typing import List, Optional

from pydantic import BaseModel, Field


class ShareParseRequest(BaseModel):
    url: str = Field(..., description="Quark share URL or share code")
    passcode: Optional[str] = Field(default=None, description="Optional share passcode")


class FileNode(BaseModel):
    fid: str
    name: str
    is_dir: bool
    parent_fid: str
    path: str
    size: Optional[int] = None
    file_type: Optional[int] = None
    share_fid_token: Optional[str] = None


class ShareParseResponse(BaseModel):
    total_count: int
    files: List[FileNode]

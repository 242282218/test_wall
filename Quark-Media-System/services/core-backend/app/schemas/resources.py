from typing import List, Optional

from pydantic import BaseModel, Field


class ResourceItem(BaseModel):
    id: Optional[str] = None
    message_id: Optional[str] = Field(default=None, alias="messageId")
    title: Optional[str] = None
    content: Optional[str] = None
    pub_date: Optional[str] = Field(default=None, alias="pubDate")
    image: Optional[str] = None
    cloud_links: List[str] = Field(default_factory=list, alias="cloudLinks")
    cloud_type: Optional[str] = Field(default=None, alias="cloudType")
    tags: List[str] = Field(default_factory=list)
    channel: Optional[str] = None
    channel_id: Optional[str] = Field(default=None, alias="channelId")

    class Config:
        populate_by_name = True


class ChannelInfo(BaseModel):
    id: str
    name: str
    channel_logo: Optional[str] = Field(default=None, alias="channelLogo")
    channel_id: Optional[str] = Field(default=None, alias="channelId")

    class Config:
        populate_by_name = True


class ResourceGroup(BaseModel):
    id: str
    list: List[ResourceItem]
    channel_info: ChannelInfo = Field(alias="channelInfo")

    class Config:
        populate_by_name = True


class ResourceSearchResponse(BaseModel):
    data: List[ResourceGroup]

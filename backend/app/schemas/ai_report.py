from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

AI_REPORT_HTML_MAX_BYTES = 500 * 1024


class AiReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    html: str = Field(min_length=1, max_length=AI_REPORT_HTML_MAX_BYTES)
    conversation_json: Optional[str] = None


class AiReportOut(BaseModel):
    id: int
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    title: str
    html: str
    conversation_json: Optional[str] = None
    status: str
    share_token: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AiReportListItem(BaseModel):
    id: int
    title: str
    status: str
    owner_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AiReportListResponse(BaseModel):
    items: list[AiReportListItem]
    total: int


class AiReportSharedOut(BaseModel):
    title: str
    html: str

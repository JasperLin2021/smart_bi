from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DashboardBase(BaseModel):
    title: str
    description: Optional[str] = None
    layout_json: Optional[dict[str, Any]] = None
    filters_json: Optional[dict[str, Any]] = None
    status: str = "draft"
    visibility: str = "private"
    org_id: Optional[int] = None
    owner_id: Optional[int] = None


class DashboardCreate(DashboardBase):
    pass


class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    layout_json: Optional[dict[str, Any]] = None
    filters_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None


class DashboardOut(DashboardBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DashboardListResponse(BaseModel):
    items: list[DashboardOut]

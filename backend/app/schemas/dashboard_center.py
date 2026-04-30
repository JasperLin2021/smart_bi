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
    is_public: int = 0
    share_token: Optional[str] = None
    shared_user_ids: Optional[list[int]] = None
    version: int = 1
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


class DashboardShareUpdate(BaseModel):
    is_public: bool = False
    shared_user_ids: Optional[list[int]] = None


class DashboardOut(DashboardBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DashboardListResponse(BaseModel):
    items: list[DashboardOut]

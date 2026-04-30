from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class BigScreenBase(BaseModel):
    title: str
    description: Optional[str] = None
    canvas_json: Optional[dict[str, Any]] = None
    data_bindings_json: Optional[dict[str, Any]] = None
    status: str = "draft"
    visibility: str = "private"
    org_id: Optional[int] = None
    owner_id: Optional[int] = None


class BigScreenCreate(BigScreenBase):
    pass


class BigScreenUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    canvas_json: Optional[dict[str, Any]] = None
    data_bindings_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None


class BigScreenOut(BigScreenBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BigScreenListResponse(BaseModel):
    items: list[BigScreenOut]

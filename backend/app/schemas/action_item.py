from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ActionItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = None
    source_type: str = "manual"
    source_id: Optional[str] = None
    source_payload: Optional[dict[str, Any]] = None
    linked_metric_id: Optional[int] = None
    linked_dataset_id: Optional[int] = None
    linked_dashboard_id: Optional[int] = None
    owner_id: Optional[int] = None
    priority: str = "medium"
    due_date: Optional[date] = None
    status: str = "open"
    outcome: Optional[str] = None
    org_id: Optional[int] = None


class ActionItemCreate(ActionItemBase):
    pass


class ActionItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=160)
    description: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_payload: Optional[dict[str, Any]] = None
    linked_metric_id: Optional[int] = None
    linked_dataset_id: Optional[int] = None
    linked_dashboard_id: Optional[int] = None
    owner_id: Optional[int] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    outcome: Optional[str] = None
    org_id: Optional[int] = None


class ActionItemOut(ActionItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: Optional[int] = None
    created_by: Optional[int] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ActionItemListResponse(BaseModel):
    items: list[ActionItemOut]
    total: int

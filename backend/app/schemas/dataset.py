from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None
    datasource_id: int
    fields_json: Optional[dict[str, Any]] = None
    filters_json: Optional[dict[str, Any]] = None
    derived_columns_json: Optional[dict[str, Any]] = None
    joins_json: Optional[dict[str, Any]] = None
    aggregations_json: Optional[dict[str, Any]] = None
    status: str = "draft"
    visibility: str = "private"
    org_id: Optional[int] = None
    owner_id: Optional[int] = None


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    datasource_id: Optional[int] = None
    fields_json: Optional[dict[str, Any]] = None
    filters_json: Optional[dict[str, Any]] = None
    derived_columns_json: Optional[dict[str, Any]] = None
    joins_json: Optional[dict[str, Any]] = None
    aggregations_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None


class DatasetOut(DatasetBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    items: list[DatasetOut]

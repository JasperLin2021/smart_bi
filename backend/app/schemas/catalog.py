from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DataAssetBase(BaseModel):
    asset_type: str
    asset_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    datasource_id: Optional[int] = None
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    status: str = "draft"
    tags: Optional[list[str]] = None
    metadata_json: Optional[dict[str, Any]] = None


class DataAssetCreate(DataAssetBase):
    pass


class DataAssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    datasource_id: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata_json: Optional[dict[str, Any]] = None


class DataAssetStatusUpdate(BaseModel):
    status: str


class DataAssetOut(DataAssetBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataAssetListResponse(BaseModel):
    items: list[DataAssetOut]

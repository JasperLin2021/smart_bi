from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MetricBase(BaseModel):
    datasource_id: int
    name: str
    description: Optional[str] = None
    definition: str
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    formula: Optional[str] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    aggregation: str = "sum"
    tags: Optional[list[str]] = None
    status: str = "published"
    dimensions: Optional[list[str]] = None
    is_active: int = 1


class MetricCreate(MetricBase):
    pass


class MetricUpdate(BaseModel):
    datasource_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    formula: Optional[str] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    aggregation: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None
    dimensions: Optional[list[str]] = None
    is_active: Optional[int] = None


class MetricOut(MetricBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MetricListResponse(BaseModel):
    items: list[MetricOut]

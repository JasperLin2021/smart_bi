from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AnalysisViewBase(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_id: int
    chart_type: str = "bar"
    dimensions: list[str] = []
    measures: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    sorts: list[dict[str, Any]] = []
    calculation_fields_json: Optional[dict[str, Any]] = None
    visual_config_json: Optional[dict[str, Any]] = None
    interaction_json: Optional[dict[str, Any]] = None
    status: str = "draft"
    visibility: str = "private"


class AnalysisViewCreate(AnalysisViewBase):
    pass


class AnalysisViewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[int] = None
    chart_type: Optional[str] = None
    dimensions: Optional[list[str]] = None
    measures: Optional[list[dict[str, Any]]] = None
    filters: Optional[list[dict[str, Any]]] = None
    sorts: Optional[list[dict[str, Any]]] = None
    calculation_fields_json: Optional[dict[str, Any]] = None
    visual_config_json: Optional[dict[str, Any]] = None
    interaction_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None


class AnalysisViewOut(AnalysisViewBase):
    id: int
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisPreviewRequest(BaseModel):
    limit: int = 200


class AnalysisDraftPreviewRequest(BaseModel):
    dataset_id: int
    chart_type: str = "bar"
    dimensions: list[str] = []
    measures: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    sorts: list[dict[str, Any]] = []
    calculation_fields_json: Optional[dict[str, Any]] = None
    visual_config_json: Optional[dict[str, Any]] = None
    interaction_json: Optional[dict[str, Any]] = None
    limit: int = 200


class AnalysisPublishRequest(BaseModel):
    status: str = "published"
    visibility: str = "org"


class AnalysisDashboardAttachRequest(BaseModel):
    dashboard_id: int
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None


class AnalysisViewListResponse(BaseModel):
    items: list[AnalysisViewOut]
    total: int

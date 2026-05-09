from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ReportTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_id: int
    report_type: str = "paginated"
    layout_json: Optional[dict[str, Any]] = None
    parameter_schema_json: Optional[dict[str, Any]] = None
    binding_json: Optional[dict[str, Any]] = None
    style_json: Optional[dict[str, Any]] = None
    permission_json: Optional[dict[str, Any]] = None
    fill_schema_json: Optional[dict[str, Any]] = None
    distribution_json: Optional[dict[str, Any]] = None
    status: str = "draft"
    visibility: str = "private"


class ReportTemplateCreate(ReportTemplateBase):
    pass


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[int] = None
    report_type: Optional[str] = None
    layout_json: Optional[dict[str, Any]] = None
    parameter_schema_json: Optional[dict[str, Any]] = None
    binding_json: Optional[dict[str, Any]] = None
    style_json: Optional[dict[str, Any]] = None
    permission_json: Optional[dict[str, Any]] = None
    fill_schema_json: Optional[dict[str, Any]] = None
    distribution_json: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibility: Optional[str] = None
    changelog: Optional[str] = None


class ReportTemplateOut(ReportTemplateBase):
    id: int
    version: int
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportTemplateListResponse(BaseModel):
    items: list[ReportTemplateOut]
    total: int


class ReportTemplateVersionOut(BaseModel):
    id: int
    template_id: int
    version: int
    snapshot_json: dict[str, Any]
    changelog: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportPreviewRequest(BaseModel):
    parameters: dict[str, Any] = {}


class ReportExportRequest(BaseModel):
    export_type: str = "excel"
    parameters: dict[str, Any] = {}


class ReportFillRequest(BaseModel):
    payload: dict[str, Any]


class ReportRunOut(BaseModel):
    id: int
    template_id: int
    version: Optional[int] = None
    run_type: str
    export_type: Optional[str] = None
    status: str
    parameters_json: Optional[dict[str, Any]] = None
    output_uri: Optional[str] = None
    content_preview: Optional[str] = None
    error_message: Optional[str] = None
    org_id: Optional[int] = None
    created_by: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

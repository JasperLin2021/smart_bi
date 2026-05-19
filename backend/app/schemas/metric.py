from pydantic import BaseModel, ConfigDict
from typing import Any, Optional
from datetime import datetime


class MetricBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: int
    name: str
    description: Optional[str] = None
    definition: str
    column_name: Optional[str] = None
    formula: Optional[str] = None
    calculation_config: Optional[dict[str, Any]] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    aggregation: str = "sum"
    tags: Optional[list[str]] = None
    status: str = "published"
    dimensions: Optional[list[str]] = None
    certification_status: str = "draft"
    certified_by: Optional[str] = None
    certified_at: Optional[datetime] = None
    caliber_version: str = "v1"
    data_updated_at: Optional[datetime] = None
    quality_status: str = "unknown"
    quality_message: Optional[str] = None
    is_active: int = 1


class MetricCreate(MetricBase):
    pass


class MetricUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[str] = None
    column_name: Optional[str] = None
    formula: Optional[str] = None
    calculation_config: Optional[dict[str, Any]] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    aggregation: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None
    dimensions: Optional[list[str]] = None
    certification_status: Optional[str] = None
    certified_by: Optional[str] = None
    certified_at: Optional[datetime] = None
    caliber_version: Optional[str] = None
    data_updated_at: Optional[datetime] = None
    quality_status: Optional[str] = None
    quality_message: Optional[str] = None
    is_active: Optional[int] = None


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: Optional[int] = None
    datasource_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    definition: str
    column_name: Optional[str] = None
    formula: Optional[str] = None
    calculation_config: Optional[dict[str, Any]] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    aggregation: str = "sum"
    tags: Optional[list[str]] = None
    status: str = "published"
    dimensions: Optional[list[str]] = None
    certification_status: str = "draft"
    certified_by: Optional[str] = None
    certified_at: Optional[datetime] = None
    caliber_version: str = "v1"
    data_updated_at: Optional[datetime] = None
    quality_status: str = "unknown"
    quality_message: Optional[str] = None
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_value: Optional[float] = None
    last_computed_at: Optional[datetime] = None


class MetricListResponse(BaseModel):
    items: list[MetricOut]


class MetricFromQueryDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_history_id: int
    selected_metric_column: Optional[str] = None
    selected_dimensions: list[str] = []
    time_column: Optional[str] = None


class MetricFromQueryCreateRequest(MetricFromQueryDraftRequest):
    name: Optional[str] = None
    definition: Optional[str] = None
    formula: Optional[str] = None
    unit: Optional[str] = None
    owner_name: Optional[str] = None
    dimensions: Optional[list[str]] = None
    status: str = "draft"
    certification_status: str = "pending_review"


class MetricFromQueryDraftResponse(BaseModel):
    candidate: dict[str, Any]
    source: dict[str, Any]
    validation: dict[str, Any]
    warnings: list[str] = []
    llm_enhanced: bool = False
    llm_model: Optional[str] = None


class MetricPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimensions: list[str] = []
    limit: int = 50


class MetricPreviewResponse(BaseModel):
    metric: dict[str, Any]
    dataset: dict[str, Any]
    datasource: dict[str, Any]
    dimensions: list[dict[str, str]]
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    query: dict[str, Any]

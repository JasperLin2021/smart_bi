from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class PipelineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_id: int
    dag_json: dict[str, Any]
    schedule_cron: Optional[str] = None
    run_mode: str = "manual"
    status: str = "draft"
    environment: str = "prod"
    priority: str = "medium"
    sla_minutes: int = 120
    retry_count: int = 2
    timeout_minutes: int = 60
    alert_policy_json: Optional[dict[str, Any]] = None
    state_json: Optional[dict[str, Any]] = None


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[int] = None
    dag_json: Optional[dict[str, Any]] = None
    schedule_cron: Optional[str] = None
    run_mode: Optional[str] = None
    status: Optional[str] = None
    environment: Optional[str] = None
    priority: Optional[str] = None
    sla_minutes: Optional[int] = None
    retry_count: Optional[int] = None
    timeout_minutes: Optional[int] = None
    alert_policy_json: Optional[dict[str, Any]] = None
    state_json: Optional[dict[str, Any]] = None


class PipelineOut(PipelineCreate):
    id: int
    current_version: int = 0
    published_version: int = 0
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PipelineRunRequest(BaseModel):
    mode: str = "manual"
    reason: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    dry_run: bool = False


class PipelineRunOut(BaseModel):
    id: int
    pipeline_id: int
    mode: str
    status: str
    reason: Optional[str] = None
    node_logs_json: Optional[dict[str, Any]] = None
    records_read: int = 0
    records_written: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
    notify_result_json: Optional[dict[str, Any]] = None
    scheduled_job_id: Optional[str] = None
    duration_ms: Optional[int] = None
    org_id: Optional[int] = None
    triggered_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PipelinePreviewRequest(BaseModel):
    node_id: Optional[str] = None
    limit: int = 100
    dag_json: Optional[dict[str, Any]] = None


class PipelinePreviewOut(BaseModel):
    pipeline_id: int
    node_id: Optional[str] = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    node_logs_json: Optional[dict[str, Any]] = None


class PipelineLineageOut(BaseModel):
    pipeline_id: int
    source: dict[str, Any]
    target: dict[str, Any]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


class PipelineDiagnostic(BaseModel):
    severity: str
    code: str
    message: str
    node_id: Optional[str] = None


class PipelineValidationOut(BaseModel):
    status: str
    diagnostics: list[PipelineDiagnostic] = []
    critical_count: int = 0
    warning_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    schedule_cron: Optional[str] = None
    run_mode: str = "manual"
    environment: str = "prod"
    priority: str = "medium"
    sla_minutes: int = 120
    retry_count: int = 2
    timeout_minutes: int = 60


class PipelineVersionOut(BaseModel):
    id: int
    pipeline_id: int
    version: int
    status: str
    dag_json: dict[str, Any]
    config_json: Optional[dict[str, Any]] = None
    comment: Optional[str] = None
    org_id: Optional[int] = None
    created_by: Optional[int] = None
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QualityRuleCreate(BaseModel):
    pipeline_id: Optional[int] = None
    dataset_id: int
    name: str
    rule_type: str
    field: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[str] = None
    severity: str = "warning"
    is_active: bool = True


class QualityRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None


class QualityRuleOut(QualityRuleCreate):
    id: int
    last_status: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    org_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

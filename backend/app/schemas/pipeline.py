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


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[int] = None
    dag_json: Optional[dict[str, Any]] = None
    schedule_cron: Optional[str] = None
    run_mode: Optional[str] = None
    status: Optional[str] = None


class PipelineOut(PipelineCreate):
    id: int
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
    org_id: Optional[int] = None
    triggered_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

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

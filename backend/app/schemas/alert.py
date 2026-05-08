from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class DimensionCondition(BaseModel):
    field: str
    operator: str  # eq / neq / in / not_in / contains
    value: Any


class MetricCondition(BaseModel):
    metric: str
    operator: str  # gt / gte / lt / lte / eq
    value: float


class AlertBase(BaseModel):
    name: str
    dataset_id: int
    datasource_id: Optional[int] = None
    metric_id: Optional[int] = None
    metric_name: Optional[str] = None
    time_range: int = 1
    time_range_unit: str = "day"
    dimension_conditions: Optional[str] = None
    metric_conditions: Optional[str] = None
    check_period: int = 1
    check_period_unit: str = "hour"
    assignees: Optional[str] = None
    cc_users: Optional[str] = None
    notify_system: bool = True
    notify_email: bool = False
    notify_wechat: bool = False
    notify_dingtalk: bool = False
    email_recipients: Optional[str] = None
    content: Optional[str] = None
    is_active: bool = True


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    dataset_id: Optional[int] = None
    datasource_id: Optional[int] = None
    metric_id: Optional[int] = None
    metric_name: Optional[str] = None
    time_range: Optional[int] = None
    time_range_unit: Optional[str] = None
    dimension_conditions: Optional[str] = None
    metric_conditions: Optional[str] = None
    check_period: Optional[int] = None
    check_period_unit: Optional[str] = None
    assignees: Optional[str] = None
    cc_users: Optional[str] = None
    notify_system: Optional[bool] = None
    notify_email: Optional[bool] = None
    notify_wechat: Optional[bool] = None
    notify_dingtalk: Optional[bool] = None
    email_recipients: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
    auto_create_action_item: Optional[bool] = None
    action_item_assignee_id: Optional[int] = None


class AlertOut(AlertBase):
    id: int
    auto_create_action_item: bool = False
    action_item_assignee_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    items: List[AlertOut]
    total: int

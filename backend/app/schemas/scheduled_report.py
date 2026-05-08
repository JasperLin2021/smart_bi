from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ScheduledReportBase(BaseModel):
    name: str
    dataset_id: int
    datasource_id: Optional[int] = None
    question: str
    cron_expression: str = "0 9 * * 1-5"
    notify_email: bool = False
    notify_wechat: bool = False
    notify_dingtalk: bool = False
    email_recipients: Optional[str] = None
    is_active: bool = True


class ScheduledReportCreate(ScheduledReportBase):
    pass


class ScheduledReportUpdate(BaseModel):
    name: Optional[str] = None
    dataset_id: Optional[int] = None
    datasource_id: Optional[int] = None
    question: Optional[str] = None
    cron_expression: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_wechat: Optional[bool] = None
    notify_dingtalk: Optional[bool] = None
    email_recipients: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduledReportOut(ScheduledReportBase):
    id: int
    created_by: Optional[int] = None
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScheduledReportListResponse(BaseModel):
    items: List[ScheduledReportOut]
    total: int

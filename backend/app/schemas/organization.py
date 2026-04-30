from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    plan_type: str = "team"
    user_limit: Optional[int] = None
    datasource_limit: Optional[int] = None
    dashboard_limit: Optional[int] = None
    big_screen_limit: Optional[int] = None
    monthly_query_limit: Optional[int] = None
    white_label_enabled: int = 0
    branding_json: Optional[dict[str, Any]] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    plan_type: Optional[str] = None
    user_limit: Optional[int] = None
    datasource_limit: Optional[int] = None
    dashboard_limit: Optional[int] = None
    big_screen_limit: Optional[int] = None
    monthly_query_limit: Optional[int] = None
    white_label_enabled: Optional[int] = None
    branding_json: Optional[dict[str, Any]] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    plan_type: str = "team"
    user_limit: Optional[int] = None
    datasource_limit: Optional[int] = None
    dashboard_limit: Optional[int] = None
    big_screen_limit: Optional[int] = None
    monthly_query_limit: Optional[int] = None
    white_label_enabled: int = 0
    branding_json: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

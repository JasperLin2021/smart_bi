from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    org_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    status: str
    message: Optional[str] = None
    detail: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogOut]

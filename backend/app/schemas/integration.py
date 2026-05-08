from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WechatWorkConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    corp_id: Optional[str] = None
    agent_id: Optional[str] = None
    app_secret: Optional[str] = None
    callback_url: Optional[str] = None
    robot_webhook_url: Optional[str] = None


class WechatWorkConfigOut(BaseModel):
    id: int
    provider: str
    name: str
    enabled: bool
    corp_id: Optional[str] = None
    agent_id: Optional[str] = None
    callback_url: Optional[str] = None
    robot_webhook_url: Optional[str] = None
    app_secret_set: bool = False

    class Config:
        from_attributes = True


class ExternalOrgBindingCreate(BaseModel):
    external_corp_id: str
    org_id: int


class ExternalOrgBindingOut(BaseModel):
    id: int
    provider: str
    external_corp_id: str
    org_id: int
    org_name: Optional[str] = None

    class Config:
        from_attributes = True


class ExternalPermissionMappingCreate(BaseModel):
    external_corp_id: str
    external_department_id: str
    org_id: int
    role: str = "user"
    data_scope: Optional[str] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None
    priority: int = 100
    enabled: bool = True


class ExternalPermissionMappingUpdate(BaseModel):
    external_corp_id: Optional[str] = None
    external_department_id: Optional[str] = None
    org_id: Optional[int] = None
    role: Optional[str] = None
    data_scope: Optional[str] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None


class ExternalPermissionMappingOut(BaseModel):
    id: int
    provider: str
    external_corp_id: str
    external_department_id: str
    org_id: int
    org_name: Optional[str] = None
    role: str
    data_scope: Optional[str] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None
    priority: int
    enabled: bool

    class Config:
        from_attributes = True


class MessageDeliveryOut(BaseModel):
    id: int
    provider: str
    channel: str
    event_type: str
    recipient_user_id: Optional[int] = None
    recipient_external_user_id: Optional[str] = None
    org_id: Optional[int] = None
    title: str
    content: str
    link_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WechatWorkMessageTestRequest(BaseModel):
    recipient_user_id: int
    title: str
    content: str
    link_url: Optional[str] = None

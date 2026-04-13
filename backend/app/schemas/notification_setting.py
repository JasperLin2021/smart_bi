from pydantic import BaseModel
from typing import Optional


class NotificationSettingOut(BaseModel):
    email_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 465
    smtp_username: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_use_ssl: bool = True
    smtp_password_set: bool = False  # never expose the password

    wechat_enabled: bool = False
    wechat_webhook_url: Optional[str] = None

    dingtalk_enabled: bool = False
    dingtalk_webhook_url: Optional[str] = None
    dingtalk_secret_set: bool = False

    class Config:
        from_attributes = True


class NotificationSettingUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # None means keep existing
    smtp_from: Optional[str] = None
    smtp_use_ssl: Optional[bool] = None

    wechat_enabled: Optional[bool] = None
    wechat_webhook_url: Optional[str] = None

    dingtalk_enabled: Optional[bool] = None
    dingtalk_webhook_url: Optional[str] = None
    dingtalk_secret: Optional[str] = None  # None means keep existing


class NotificationTestRequest(BaseModel):
    channel: str  # "email" | "wechat" | "dingtalk"
    email_to: Optional[str] = None  # for email test

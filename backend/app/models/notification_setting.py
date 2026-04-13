from sqlalchemy import Column, Integer, String, Boolean
from app.db.base_class import Base


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Email (SMTP)
    email_enabled = Column(Boolean, default=False)
    smtp_host = Column(String(256), nullable=True)
    smtp_port = Column(Integer, default=465)
    smtp_username = Column(String(256), nullable=True)
    smtp_password = Column(String(256), nullable=True)
    smtp_from = Column(String(256), nullable=True)
    smtp_use_ssl = Column(Boolean, default=True)

    # WeChat Work robot
    wechat_enabled = Column(Boolean, default=False)
    wechat_webhook_url = Column(String(512), nullable=True)

    # DingTalk robot
    dingtalk_enabled = Column(Boolean, default=False)
    dingtalk_webhook_url = Column(String(512), nullable=True)
    dingtalk_secret = Column(String(256), nullable=True)

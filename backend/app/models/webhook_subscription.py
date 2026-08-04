from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from app.db.base_class import Base


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    target_url = Column(String(512), nullable=False)
    events = Column(JSON, nullable=False, default=list)
    secret = Column(String(256), nullable=True)
    enabled = Column(Integer, default=1, nullable=False, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

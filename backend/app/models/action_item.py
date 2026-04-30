from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(160), nullable=False, index=True)
    description = Column(Text, nullable=True)
    source_type = Column(String(32), default="manual", nullable=False, index=True)
    source_id = Column(String(128), nullable=True, index=True)
    source_payload = Column(JSON, nullable=True)
    linked_metric_id = Column(Integer, nullable=True, index=True)
    linked_dataset_id = Column(Integer, nullable=True, index=True)
    linked_dashboard_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    priority = Column(String(16), default="medium", nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
    status = Column(String(32), default="open", nullable=False, index=True)
    outcome = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, index=True, nullable=False)
    alert_name = Column(String(128), nullable=True)
    triggered_at = Column(DateTime, server_default=func.now())
    metric_value = Column(String(64), nullable=True)
    condition_desc = Column(String(512), nullable=True)
    notify_result = Column(Text, nullable=True)  # JSON: {channel: success/error}
    status = Column(String(32), default="triggered")  # triggered / error

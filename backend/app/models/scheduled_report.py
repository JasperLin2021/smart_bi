from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func
from app.db.base_class import Base


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    dataset_id = Column(Integer, nullable=True, index=True)
    datasource_id = Column(Integer, nullable=True, index=True)
    question = Column(Text, nullable=False)  # Natural-language question to run

    # Cron schedule (standard 5-field: minute hour day month weekday)
    # Default: workdays at 09:00
    cron_expression = Column(String(64), default="0 9 * * 1-5")

    # Notification channels
    notify_email = Column(Boolean, default=False)
    notify_wechat = Column(Boolean, default=False)
    notify_dingtalk = Column(Boolean, default=False)
    email_recipients = Column(Text, nullable=True)  # comma-separated email addresses

    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

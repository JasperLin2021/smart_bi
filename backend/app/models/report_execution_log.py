from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class ReportExecutionLog(Base):
    __tablename__ = "report_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, nullable=False, index=True)
    report_name = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, index=True)  # success | error
    content_preview = Column(Text, nullable=True)   # first ~2000 chars of markdown
    notify_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    run_at = Column(DateTime, server_default=func.now(), index=True)
    org_id = Column(Integer, nullable=True, index=True)

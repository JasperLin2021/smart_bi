from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from app.db.base_class import Base


class DashboardComment(Base):
    __tablename__ = "dashboard_comments"

    id = Column(Integer, primary_key=True, index=True)
    dashboard_id = Column(Integer, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

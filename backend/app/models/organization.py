from sqlalchemy import JSON, Column, DateTime, Integer, String, func
from app.db.base_class import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    plan_type = Column(String(32), default="team", nullable=False)
    user_limit = Column(Integer, nullable=True)
    datasource_limit = Column(Integer, nullable=True)
    dashboard_limit = Column(Integer, nullable=True)
    big_screen_limit = Column(Integer, nullable=True)
    monthly_query_limit = Column(Integer, nullable=True)
    white_label_enabled = Column(Integer, default=0, nullable=False)
    branding_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

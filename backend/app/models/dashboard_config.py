from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    layout_json = Column(JSON, nullable=True)
    filters_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False)
    is_public = Column(Integer, default=0, nullable=False)
    share_token = Column(String(64), nullable=True, unique=True, index=True)
    shared_user_ids = Column(JSON, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

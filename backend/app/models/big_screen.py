from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class BigScreen(Base):
    __tablename__ = "big_screens"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    canvas_json = Column(JSON, nullable=True)
    data_bindings_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class DataAsset(Base):
    __tablename__ = "data_assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_type = Column(String(32), nullable=False, index=True)
    asset_id = Column(Integer, nullable=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    datasource_id = Column(Integer, nullable=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    tags = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

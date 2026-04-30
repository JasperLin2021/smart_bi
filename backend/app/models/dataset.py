from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    datasource_id = Column(Integer, nullable=False, index=True)
    fields_json = Column(JSON, nullable=True)
    filters_json = Column(JSON, nullable=True)
    derived_columns_json = Column(JSON, nullable=True)
    joins_json = Column(JSON, nullable=True)
    aggregations_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

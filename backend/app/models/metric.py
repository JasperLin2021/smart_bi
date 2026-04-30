from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, index=True, nullable=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    definition = Column(Text, nullable=False)
    table_name = Column(String(64), nullable=True)
    column_name = Column(String(64), nullable=True)
    formula = Column(Text, nullable=True)
    owner_name = Column(String(128), nullable=True)
    unit = Column(String(32), nullable=True)
    aggregation = Column(String(32), default="sum", nullable=False)
    tags = Column(JSON, nullable=True)
    status = Column(String(32), default="published", nullable=False)
    dimensions = Column(JSON, nullable=True)
    certification_status = Column(String(32), default="draft", nullable=False, index=True)
    certified_by = Column(String(128), nullable=True)
    certified_at = Column(DateTime, nullable=True)
    caliber_version = Column(String(64), default="v1", nullable=False)
    data_updated_at = Column(DateTime, nullable=True)
    quality_status = Column(String(32), default="unknown", nullable=False, index=True)
    quality_message = Column(Text, nullable=True)
    lineage_json = Column(JSON, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func

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
    pipeline_json = Column(JSON, nullable=True)
    semantic_model_json = Column(JSON, nullable=True)
    drill_config_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False)
    last_refresh_status = Column(String(32), nullable=True)
    last_refresh_at = Column(DateTime, nullable=True)
    last_refresh_row_count = Column(Integer, default=0, nullable=False)
    materialization_status = Column(String(32), nullable=True, index=True)
    materialization_mode = Column(String(32), nullable=True)
    materialized_table_name = Column(String(128), nullable=True, index=True)
    materialized_at = Column(DateTime, nullable=True)
    incremental_key = Column(String(128), nullable=True)
    incremental_watermark = Column(String(256), nullable=True)
    materialization_message = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DatasetRefreshLog(Base):
    __tablename__ = "dataset_refresh_logs"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    row_count = Column(Integer, default=0, nullable=False)
    message = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    triggered_by_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

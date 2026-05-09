from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class DataPipeline(Base):
    __tablename__ = "data_pipelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_id = Column(Integer, nullable=False, index=True)
    dag_json = Column(JSON, nullable=False)
    schedule_cron = Column(String(64), nullable=True)
    run_mode = Column(String(32), default="manual", nullable=False, index=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    last_run_status = Column(String(32), nullable=True, index=True)
    last_run_at = Column(DateTime, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DataPipelineRun(Base):
    __tablename__ = "data_pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False, index=True)
    mode = Column(String(32), default="manual", nullable=False, index=True)
    status = Column(String(32), default="running", nullable=False, index=True)
    reason = Column(Text, nullable=True)
    node_logs_json = Column(JSON, nullable=True)
    records_read = Column(Integer, default=0, nullable=False)
    records_written = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    triggered_by_id = Column(Integer, nullable=True, index=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=True, index=True)
    dataset_id = Column(Integer, nullable=False, index=True)
    name = Column(String(160), nullable=False, index=True)
    rule_type = Column(String(32), nullable=False, index=True)
    field = Column(String(128), nullable=True)
    operator = Column(String(32), nullable=True)
    threshold = Column(String(128), nullable=True)
    severity = Column(String(16), default="warning", nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_status = Column(String(32), nullable=True, index=True)
    last_checked_at = Column(DateTime, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

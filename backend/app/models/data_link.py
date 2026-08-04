from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON, func
from app.db.base_class import Base


class DataLink(Base):
    __tablename__ = "data_links"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    connector_type = Column(String(32), nullable=False, index=True)  # jushuitan | yicang | fenxiang
    config_json = Column(JSON, nullable=True)   # credentials & endpoint config — stored as plaintext JSON; never expose over the API unmasked
    status = Column(String(16), default="inactive")  # active | inactive | error
    last_test_at = Column(DateTime, nullable=True)
    last_test_message = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DataLinkTask(Base):
    __tablename__ = "data_link_tasks"

    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    source_object = Column(String(64), nullable=False)   # e.g. "orders", "customers"
    target_datasource_id = Column(Integer, nullable=True)
    target_table = Column(String(128), nullable=True)    # table name to write into
    sync_mode = Column(String(16), default="full")       # full | incremental
    incremental_field = Column(String(64), nullable=True)  # field used for incremental watermark
    incremental_watermark = Column(String(64), nullable=True)  # last synced value
    field_mapping_json = Column(JSON, nullable=True)     # [{src, dst, type}]
    filter_json = Column(JSON, nullable=True)            # extra API filters
    cron_expression = Column(String(64), default="0 2 * * *")
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(16), nullable=True)  # success | error | running
    last_run_records = Column(Integer, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DataLinkLog(Base):
    __tablename__ = "data_link_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    link_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), nullable=False)   # running | success | error
    records_read = Column(Integer, default=0)
    records_written = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)

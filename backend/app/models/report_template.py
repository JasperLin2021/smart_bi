from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_id = Column(Integer, nullable=True, index=True)
    report_type = Column(String(32), default="paginated", nullable=False, index=True)
    layout_json = Column(JSON, nullable=True)
    parameter_schema_json = Column(JSON, nullable=True)
    binding_json = Column(JSON, nullable=True)
    style_json = Column(JSON, nullable=True)
    permission_json = Column(JSON, nullable=True)
    fill_schema_json = Column(JSON, nullable=True)
    distribution_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReportTemplateVersion(Base):
    __tablename__ = "report_template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False, index=True)
    snapshot_json = Column(JSON, nullable=False)
    changelog = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())


class ReportRun(Base):
    __tablename__ = "report_runs"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=True)
    run_type = Column(String(32), default="preview", nullable=False, index=True)
    export_type = Column(String(32), nullable=True, index=True)
    status = Column(String(32), default="queued", nullable=False, index=True)
    parameters_json = Column(JSON, nullable=True)
    output_uri = Column(String(512), nullable=True)
    content_preview = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_by = Column(Integer, nullable=True, index=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class ReportFillRecord(Base):
    __tablename__ = "report_fill_records"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    payload_json = Column(JSON, nullable=False)
    validation_status = Column(String(32), default="pending", nullable=False, index=True)
    validation_errors_json = Column(JSON, nullable=True)
    writeback_status = Column(String(32), default="pending", nullable=False, index=True)
    writeback_error = Column(Text, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    submitted_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

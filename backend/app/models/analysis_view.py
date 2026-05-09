from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class AnalysisView(Base):
    __tablename__ = "analysis_views"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_id = Column(Integer, nullable=False, index=True)
    chart_type = Column(String(32), default="bar", nullable=False, index=True)
    dimensions = Column(JSON, nullable=True)
    measures = Column(JSON, nullable=True)
    filters = Column(JSON, nullable=True)
    sorts = Column(JSON, nullable=True)
    calculation_fields_json = Column(JSON, nullable=True)
    visual_config_json = Column(JSON, nullable=True)
    interaction_json = Column(JSON, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(32), default="private", nullable=False, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

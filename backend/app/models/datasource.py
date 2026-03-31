from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class DataSource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    slug = Column(String(64), nullable=False, unique=True)
    database_url = Column(String(512), nullable=False)
    source_type = Column(String(32), default="database")  # "database" | "excel"
    metadata_prompt = Column(Text, nullable=False)
    schema_metadata = Column(Text, nullable=True)  # JSON: {tables, relationships}
    drill_config = Column(Text, nullable=True)  # JSON: {dimensions, metrics, paths}
    metrics_prompt = Column(Text, nullable=True)
    text2sql_prompt = Column(Text, nullable=True)
    recommend_questions = Column(Text, nullable=True)  # JSON array
    is_active = Column(Integer, default=1)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", backref="datasources")

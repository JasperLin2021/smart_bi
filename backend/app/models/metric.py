from sqlalchemy import Column, DateTime, Integer, String, Text, func
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
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

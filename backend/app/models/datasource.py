from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class DataSource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    slug = Column(String(64), nullable=False, unique=True)
    database_url = Column(String(512), nullable=False)
    metadata_prompt = Column(Text, nullable=False)
    metrics_prompt = Column(Text, nullable=True)
    text2sql_prompt = Column(Text, nullable=True)
    recommend_questions = Column(Text, nullable=True)  # JSON array
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

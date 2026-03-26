from sqlalchemy import Column, DateTime, Integer, String, Float, Text, func
from app.db.base_class import Base


class LlmSetting(Base):
    __tablename__ = "llm_settings"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), default="custom")
    base_url = Column(String(256), nullable=False)
    api_key = Column(String(256), nullable=False)
    model = Column(String(128), nullable=False)
    temperature = Column(Float, default=0.3)
    text2sql_prompt = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

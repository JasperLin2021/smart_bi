from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class EmbedToken(Base):
    __tablename__ = "embed_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    label = Column(String(128), nullable=True)
    resource_type = Column(String(32), nullable=False)  # chart | dashboard
    resource_id = Column(Integer, nullable=False)
    allowed_domains = Column(Text, nullable=True)  # comma-separated
    created_by = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

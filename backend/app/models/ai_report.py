from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db.base_class import Base


class AiReport(Base):
    """对话式 AI 报表：由 AI 对话生成的 HTML 报表快照。"""

    __tablename__ = "ai_reports"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(256), nullable=False)
    html = Column(Text, nullable=False)
    conversation_json = Column(Text, nullable=True)
    status = Column(String(16), default="draft", nullable=False)
    share_token = Column(String(64), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
